"""Team and roster management for Statis Pro Football."""
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from .player_card import PlayerCard


@dataclass
class Roster:
    """Team roster containing player cards."""
    qbs: List[PlayerCard] = field(default_factory=list)
    rbs: List[PlayerCard] = field(default_factory=list)
    wrs: List[PlayerCard] = field(default_factory=list)
    tes: List[PlayerCard] = field(default_factory=list)
    kickers: List[PlayerCard] = field(default_factory=list)
    punters: List[PlayerCard] = field(default_factory=list)
    offensive_line: List[PlayerCard] = field(default_factory=list)
    defenders: List[PlayerCard] = field(default_factory=list)

    def get_starter(self, position: str) -> Optional[PlayerCard]:
        pos_map = {
            "QB": self.qbs, "RB": self.rbs, "WR": self.wrs,
            "TE": self.tes, "K": self.kickers, "P": self.punters,
        }
        players = pos_map.get(position, [])
        return players[0] if players else None

    def all_players(self) -> List[PlayerCard]:
        return (self.qbs + self.rbs + self.wrs + self.tes +
                self.kickers + self.punters + self.offensive_line +
                self.defenders)


@dataclass
class Team:
    """Represents an NFL team with roster and stats."""
    abbreviation: str
    city: str
    name: str
    conference: str  # AFC/NFC
    division: str    # North/South/East/West
    roster: Roster = field(default_factory=Roster)

    wins: int = 0
    losses: int = 0
    ties: int = 0

    offense_rating: int = 0
    defense_rating: int = 0

    # 5E team card fumble fields
    fumbles_lost_max: int = 21       # Fumbles Lost upper range (1-N means lost on PN 1..N)
    def_fumble_adj: int = 0          # Defensive Fumble Adjustment (opponent's adj)

    # Base defensive scheme stored on the team card ("4_3" or "3_4").
    # A team without a Nose Tackle (NT) on their roster is almost certainly
    # a 4-3 team; teams with NT use a 3-4 base.  The AI uses this value as
    # the default formation for all standard-down snaps — it should NOT flip
    # randomly between 4-3 and 3-4 play by play.
    base_defense: str = "4_3"

    # ── 5E Kickoff Table (team card, 12 entries for RN 1-12) ──────────
    # Each entry is a string: "TB", "TB(-3)", "TB(-5)", "1", "3", "GL",
    # "OB", or "special" (RN 12's draw-again sub-table).
    kickoff_table: List[str] = field(default_factory=list)

    # ── 5E Kickoff Return Card ────────────────────────────────────────
    # kickoff_returners: list of {"name": str, "pn_min": int, "pn_max": int}
    # The FAC Pass Number selects which KR handles the return.
    kickoff_returners: List[Dict[str, Any]] = field(default_factory=list)

    # kickoff_return_table: list (one per KR) of 12-entry lists.
    # Each entry is [normal_yard_line, breakaway_yard_line].
    # Special values: "TD" for touchdown, "Xf" for fumble at X.
    kickoff_return_table: List[List[Any]] = field(default_factory=list)

    # ── 5E Punt Return Card ───────────────────────────────────────────
    # punt_returners: list of {"name": str, "pn_min": int, "pn_max": int}
    punt_returners: List[Dict[str, Any]] = field(default_factory=list)

    # punt_return_table: list (one per PR) of 12-entry lists.
    # Each entry is [normal_yard_line, breakaway_yard_line].
    punt_return_table: List[List[Any]] = field(default_factory=list)

    _RETURN_POSITION_BONUS = {
        "KR": {"RB": 14, "WR": 12, "CB": 9, "DB": 8, "TE": 4, "QB": 2},
        "PR": {"WR": 15, "CB": 12, "DB": 11, "RB": 10, "TE": 3, "QB": 1},
    }
    _INELIGIBLE_RETURN_POSITIONS = {
        "K", "P", "LT", "LG", "C", "RG", "RT", "OL",
        "DE", "DT", "DL", "NT", "LB", "OLB", "ILB", "MLB",
    }

    def to_dict(self) -> dict:
        d = {
            "abbreviation": self.abbreviation,
            "city": self.city,
            "name": self.name,
            "conference": self.conference,
            "division": self.division,
            "record": {"wins": self.wins, "losses": self.losses, "ties": self.ties},
            "offense_rating": self.offense_rating,
            "defense_rating": self.defense_rating,
            "fumbles_lost_max": self.fumbles_lost_max,
            "def_fumble_adj": self.def_fumble_adj,
            "base_defense": self.base_defense,
            "players": [p.to_dict() for p in self.roster.all_players()],
        }
        if self.kickoff_table:
            d["kickoff_table"] = self.kickoff_table
        if self.kickoff_returners:
            d["kickoff_returners"] = self.kickoff_returners
        if self.kickoff_return_table:
            d["kickoff_return_table"] = self.kickoff_return_table
        if self.punt_returners:
            d["punt_returners"] = self.punt_returners
        if self.punt_return_table:
            d["punt_return_table"] = self.punt_return_table
        return d

    @staticmethod
    def _grade_score(grade: str) -> int:
        return {"A+": 5, "A": 4, "B": 3, "C": 2, "D": 1}.get(grade.upper(), 0)

    @classmethod
    def _return_score(cls, player: PlayerCard, kind: str) -> float:
        pos = player.position.upper()
        if pos in cls._INELIGIBLE_RETURN_POSITIONS:
            return float("-inf")
        pos_key = "DB" if pos in {"S", "SS", "FS", "DB"} else pos

        stats = player.stats_summary or {}
        score = cls._grade_score(player.overall_grade) * 10
        score += cls._RETURN_POSITION_BONUS.get(kind, {}).get(pos_key, 0)
        score += len([row for row in getattr(player, "rushing", []) if row is not None]) * 0.25
        score += len([row for row in getattr(player, "pass_gain", []) if row is not None]) * 0.15
        score += float(stats.get("ypc", 0)) * 2.0
        score += float(stats.get("avg_yards", 0)) * 0.35
        score += float(stats.get("catch_rate", 0)) * 4.0
        score += max(0, getattr(player, "blocks", 0)) * 0.5
        return score

    def get_return_candidates(self, kind: str) -> List[PlayerCard]:
        kind = kind.upper()
        candidates = [
            p for p in self.roster.all_players()
            if self._return_score(p, kind) != float("-inf")
        ]
        return sorted(
            candidates,
            key=lambda p: (-self._return_score(p, kind), p.number, p.player_name),
        )

    def get_return_specialist(
        self,
        kind: str,
        unavailable_names: Optional[Set[str]] = None,
    ) -> Optional[PlayerCard]:
        unavailable = unavailable_names or set()
        for player in self.get_return_candidates(kind):
            if player.player_name not in unavailable:
                return player
        return None

    def get_standard_lineup(self) -> Dict[str, Any]:
        return {
            "offense": {
                "QB": self.roster.qbs[0] if self.roster.qbs else None,
                "RB": self.roster.rbs[0] if self.roster.rbs else None,
                "WR1": self.roster.wrs[0] if len(self.roster.wrs) > 0 else None,
                "WR2": self.roster.wrs[1] if len(self.roster.wrs) > 1 else None,
                "WR3": self.roster.wrs[2] if len(self.roster.wrs) > 2 else None,
                "TE": self.roster.tes[0] if self.roster.tes else None,
                "K": self.roster.kickers[0] if self.roster.kickers else None,
                "P": self.roster.punters[0] if self.roster.punters else None,
            },
            "offensive_line": self.roster.offensive_line[:5],
            "defense": self.roster.defenders[:11],
            "returners": {
                "KR": self.get_return_specialist("KR"),
                "PR": self.get_return_specialist("PR"),
            },
        }

    # ── 5E Kickoff/Return table accessors ─────────────────────────────

    # Default kickoff table for modern NFL kickers (~75% touchback rate):
    # RN 1-5: TB, RN 6: TB(-5), RN 7-8: TB(-3), RN 9-10: start at 1,
    # RN 11: start at 3, RN 12: special (draw again sub-table)
    DEFAULT_KICKOFF_TABLE = [
        "TB", "TB", "TB", "TB", "TB",  # RN 1-5
        "TB(-5)",                        # RN 6
        "TB(-3)", "TB(-3)",              # RN 7-8
        "1", "1",                        # RN 9-10
        "3",                             # RN 11
        "special",                       # RN 12
    ]

    # Default kickoff return table for an average returner:
    # [normal_yard_line, breakaway_yard_line] for RN 1-12
    DEFAULT_KR_RETURN_TABLE = [
        ["*30", "TD"],  # RN 1: breakaway
        [27, 55],
        [25, 35],
        [24, 35],
        [23, 35],
        [22, 35],
        [21, 35],
        [20, 35],
        [19, 30],
        [17, 28],
        [15, 25],
        ["13f", 25],  # RN 12: fumble
    ]

    # Default punt return table for an average returner:
    DEFAULT_PR_RETURN_TABLE = [
        ["*15", 50],  # RN 1: breakaway
        [12, 40],
        [10, 30],
        [9, 25],
        [8, 22],
        [7, 20],
        [6, 18],
        [5, 18],
        [4, 18],
        [3, 18],
        [2, 18],
        ["1f", 18],  # RN 12: fumble
    ]

    def get_kickoff_table(self) -> List[str]:
        """Return the team's 12-entry kickoff table, or default."""
        if self.kickoff_table and len(self.kickoff_table) == 12:
            return self.kickoff_table
        return list(self.DEFAULT_KICKOFF_TABLE)

    def get_kickoff_returners(self) -> List[Dict[str, Any]]:
        """Return KR assignments [{name, pn_min, pn_max}, ...].

        Falls back to auto-selecting the top 2 return candidates.
        """
        if self.kickoff_returners:
            return self.kickoff_returners
        candidates = self.get_return_candidates("KR")[:2]
        if not candidates:
            return [{"name": "unknown", "pn_min": 1, "pn_max": 48}]
        if len(candidates) == 1:
            return [{"name": candidates[0].player_name, "pn_min": 1, "pn_max": 48}]
        return [
            {"name": candidates[0].player_name, "pn_min": 1, "pn_max": 33},
            {"name": candidates[1].player_name, "pn_min": 34, "pn_max": 48},
        ]

    def get_kickoff_return_table(self) -> List[List[Any]]:
        """Return the kickoff return tables (one 12-row table per KR), or defaults."""
        if self.kickoff_return_table:
            return self.kickoff_return_table
        kr_count = max(1, len(self.get_kickoff_returners()))
        return [list(self.DEFAULT_KR_RETURN_TABLE) for _ in range(kr_count)]

    def get_punt_returners(self) -> List[Dict[str, Any]]:
        """Return PR assignments [{name, pn_min, pn_max}, ...].

        Falls back to auto-selecting the top return candidate.
        """
        if self.punt_returners:
            return self.punt_returners
        candidates = self.get_return_candidates("PR")[:1]
        if not candidates:
            return [{"name": "unknown", "pn_min": 1, "pn_max": 48}]
        return [{"name": candidates[0].player_name, "pn_min": 1, "pn_max": 48}]

    def get_punt_return_table(self) -> List[List[Any]]:
        """Return the punt return tables (one 12-row table per PR), or defaults."""
        if self.punt_return_table:
            return self.punt_return_table
        pr_count = max(1, len(self.get_punt_returners()))
        return [list(self.DEFAULT_PR_RETURN_TABLE) for _ in range(pr_count)]

    @classmethod
    def from_dict(cls, data: dict) -> "Team":
        team = cls(
            abbreviation=data.get("abbreviation", ""),
            city=data.get("city", ""),
            name=data.get("name", ""),
            conference=data.get("conference", "AFC"),
            division=data.get("division", "East"),
        )
        team.offense_rating = data.get("offense_rating", 0)
        team.defense_rating = data.get("defense_rating", 0)
        team.fumbles_lost_max = data.get("fumbles_lost_max", 21)
        team.def_fumble_adj = data.get("def_fumble_adj", 0)
        team.base_defense = data.get("base_defense", "4_3")
        team.kickoff_table = data.get("kickoff_table", [])
        team.kickoff_returners = data.get("kickoff_returners", [])
        team.kickoff_return_table = data.get("kickoff_return_table", [])
        team.punt_returners = data.get("punt_returners", [])
        team.punt_return_table = data.get("punt_return_table", [])
        record = data.get("record", {})
        team.wins = record.get("wins", 0)
        team.losses = record.get("losses", 0)
        team.ties = record.get("ties", 0)

        roster = Roster()
        for p_data in data.get("players", []):
            card = PlayerCard.from_dict(p_data)
            pos = card.position.upper()
            if pos == "QB":
                roster.qbs.append(card)
            elif pos == "RB":
                roster.rbs.append(card)
            elif pos == "WR":
                roster.wrs.append(card)
            elif pos == "TE":
                roster.tes.append(card)
            elif pos == "K":
                roster.kickers.append(card)
            elif pos == "P":
                roster.punters.append(card)
            elif pos in ("LT", "LG", "C", "RG", "RT", "OL"):
                roster.offensive_line.append(card)
            else:
                roster.defenders.append(card)
        team.roster = roster
        return team

    @classmethod
    def load(cls, team_abbr: str, season: Any = "2026_5e") -> "Team":
        """Load team from JSON data file."""
        data_dir = os.path.join(os.path.dirname(__file__), "data", str(season))
        filepath = os.path.join(data_dir, f"{team_abbr}.json")
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Team data not found: {filepath}")
        with open(filepath, "r") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def save(self, season: Any = "2026_5e") -> None:
        """Save team to JSON data file."""
        data_dir = os.path.join(os.path.dirname(__file__), "data", str(season))
        os.makedirs(data_dir, exist_ok=True)
        filepath = os.path.join(data_dir, f"{self.abbreviation}.json")
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)


def list_available_teams(season: Any = "2026_5e") -> List[str]:
    """List all available team abbreviations."""
    data_dir = os.path.join(os.path.dirname(__file__), "data", str(season))
    if not os.path.exists(data_dir):
        return []
    return [f.replace(".json", "") for f in os.listdir(data_dir) if f.endswith(".json")]
