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

    _RETURN_POSITION_BONUS = {
        "KR": {"RB": 14, "WR": 12, "CB": 9, "DB": 8, "TE": 4, "QB": 2},
        "PR": {"WR": 15, "CB": 12, "DB": 11, "RB": 10, "TE": 3, "QB": 1},
    }
    _INELIGIBLE_RETURN_POSITIONS = {
        "K", "P", "LT", "LG", "C", "RG", "RT", "OL",
        "DE", "DT", "DL", "NT", "LB", "OLB", "ILB", "MLB",
    }

    def to_dict(self) -> dict:
        return {
            "abbreviation": self.abbreviation,
            "city": self.city,
            "name": self.name,
            "conference": self.conference,
            "division": self.division,
            "record": {"wins": self.wins, "losses": self.losses, "ties": self.ties},
            "offense_rating": self.offense_rating,
            "defense_rating": self.defense_rating,
            "players": [p.to_dict() for p in self.roster.all_players()],
        }

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
    def load(cls, team_abbr: str, season: Any = "2025_5e") -> "Team":
        """Load team from JSON data file."""
        data_dir = os.path.join(os.path.dirname(__file__), "data", str(season))
        filepath = os.path.join(data_dir, f"{team_abbr}.json")
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Team data not found: {filepath}")
        with open(filepath, "r") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def save(self, season: Any = "2025_5e") -> None:
        """Save team to JSON data file."""
        data_dir = os.path.join(os.path.dirname(__file__), "data", str(season))
        os.makedirs(data_dir, exist_ok=True)
        filepath = os.path.join(data_dir, f"{self.abbreviation}.json")
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)


def list_available_teams(season: Any = "2025_5e") -> List[str]:
    """List all available team abbreviations."""
    data_dir = os.path.join(os.path.dirname(__file__), "data", str(season))
    if not os.path.exists(data_dir):
        return []
    return [f.replace(".json", "") for f in os.listdir(data_dir) if f.endswith(".json")]
