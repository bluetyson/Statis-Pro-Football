"""Core game state and logic for Statis Pro Football."""
import random
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set
from enum import Enum

from .fac_deck import FACDeck, FACCard
from .player_card import PlayerCard
from .team import Team
from .play_resolver import PlayResolver, PlayResult, BigPlayDefense, resolve_z_penalty
from .solitaire import SolitaireAI, GameSituation, PlayCall
from .charts import Charts
from .play_types import (
    DefensivePlay, DefensiveFormation, DefensiveStrategy,
    OffensivePlay, OffensiveStrategy, PlayerInvolved,
    OFFENSIVE_PLAY_NAMES, DEFENSIVE_PLAY_NAMES,
    OFFENSIVE_STRATEGY_NAMES, DEFENSIVE_STRATEGY_NAMES,
    PLAYER_INVOLVED_NAMES, LEGACY_FORMATION_TO_PLAY,
)

# Mapping from 5E OffensivePlay to FAC run direction for blocking matchup
_OFFENSIVE_PLAY_TO_DIRECTION = {
    OffensivePlay.RUNNING_SWEEP_LEFT: "SL",
    OffensivePlay.RUNNING_SWEEP_RIGHT: "SR",
    OffensivePlay.RUNNING_INSIDE_LEFT: "IL",
    OffensivePlay.RUNNING_INSIDE_RIGHT: "IR",
}

# Reverse mapping: FAC direction string → OffensivePlay enum
_DIRECTION_TO_OFFENSIVE_PLAY = {v: k for k, v in _OFFENSIVE_PLAY_TO_DIRECTION.items()}

# Mapping from play_type string to OffensivePlay enum (for human pass calls).
# Special-teams plays (PUNT, FG, KNEEL) are not offensive play cards and use
# dedicated execution paths — their off_play value is only used to build the
# log display string and has no gameplay effect.
_PLAY_TYPE_TO_OFFENSIVE_PLAY = {
    "SHORT_PASS": OffensivePlay.SHORT_PASS,
    "LONG_PASS":  OffensivePlay.LONG_PASS,
    "QUICK_PASS": OffensivePlay.QUICK_PASS,
    "SCREEN":     OffensivePlay.SCREEN_PASS,
}


class Quarter(int, Enum):
    Q1 = 1
    Q2 = 2
    Q3 = 3
    Q4 = 4
    OT = 5


@dataclass
class Score:
    home: int = 0
    away: int = 0


@dataclass
class DriveResult:
    """Result of an entire drive."""
    team: str
    plays: int
    yards: int
    result: str  # TD, FG, PUNT, TURNOVER, DOWNS, MISSED_FG, END_HALF
    points_scored: int
    drive_log: List[str] = field(default_factory=list)


@dataclass
class GameState:
    """Current state of the game."""
    home_team: str
    away_team: str
    quarter: int = 1
    time_remaining: int = 900  # seconds per quarter
    possession: str = "away"   # 'home' or 'away'
    yard_line: int = 25        # distance from own end zone
    down: int = 1
    distance: int = 10
    score: Score = field(default_factory=Score)
    timeouts_home: int = 3
    timeouts_away: int = 3
    play_log: List[str] = field(default_factory=list)
    drives: List[DriveResult] = field(default_factory=list)
    is_over: bool = False
    # 5E: Injury tracking - {player_name: plays_remaining}
    injuries: Dict[str, int] = field(default_factory=dict)
    # 5E: Position injury protection flags (per team).
    # When a starter is injured, their position is flagged so that a second
    # injury to the same position is ignored for the rest of the game.
    # The flag is cleared once the original injured player becomes eligible
    # to return (their injury counter expires).
    # Format: {"home": {"CB", "QB", ...}, "away": {"RB", ...}}
    position_injury_flags: Dict[str, Set[str]] = field(
        default_factory=lambda: {"home": set(), "away": set()}
    )
    # Maps injured player name → (team_side, position) so the position flag
    # can be cleared when that player's injury counter expires.
    _injured_starter_positions: Dict[str, tuple] = field(default_factory=dict)
    # 5E: Track last play's ball carrier for endurance
    last_ball_carrier: Optional[str] = None
    prev_ball_carrier: Optional[str] = None  # Two plays ago for endurance 2
    # 5E: Endurance 3/4 usage tracking
    endurance_used_this_drive: Set[str] = field(default_factory=set)
    endurance_used_this_quarter: Set[str] = field(default_factory=set)
    # Penalty tracking: {team: count}
    penalties: Dict[str, int] = field(default_factory=lambda: {"home": 0, "away": 0})
    penalty_yards: Dict[str, int] = field(default_factory=lambda: {"home": 0, "away": 0})
    # Turnover tracking: {team: count}
    turnovers: Dict[str, int] = field(default_factory=lambda: {"home": 0, "away": 0})
    # Player stats: {player_name: {stat_type: value}}
    player_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # Human PAT/2-pt decision: set True after a human team scores a TD, cleared
    # once the human chooses PAT kick or 2-point conversion.
    pending_extra_point: bool = False

    def get_possession_team(self) -> str:
        return self.possession

    def get_defense_team(self) -> str:
        return "home" if self.possession == "away" else "away"

    def offense_score(self) -> int:
        return self.score.home if self.possession == "home" else self.score.away

    def defense_score(self) -> int:
        return self.score.away if self.possession == "home" else self.score.home

    def score_diff(self) -> int:
        return self.offense_score() - self.defense_score()

    def to_situation(self) -> GameSituation:
        return GameSituation(
            down=self.down,
            distance=self.distance,
            yard_line=self.yard_line,
            score_diff=self.score_diff(),
            quarter=self.quarter,
            time_remaining=self.time_remaining,
            timeouts_offense=self.timeouts_home if self.possession == "home" else self.timeouts_away,
            timeouts_defense=self.timeouts_away if self.possession == "home" else self.timeouts_home,
        )


class Game:
    """Core game logic for Statis Pro Football (5th Edition).

    Uses FACDeck (109-card deck) for all play resolution.
    """

    def __init__(self, home_team: Team, away_team: Team,
                 solitaire_home: bool = True, solitaire_away: bool = True,
                 seed: Optional[int] = None, **kwargs):
        # **kwargs absorbs deprecated params (e.g. use_5e) for backward compat
        self.home_team = home_team
        self.away_team = away_team
        # 5E Solitaire: remove 1 Z card when both teams are AI-controlled
        is_solitaire = solitaire_home and solitaire_away
        self.deck = FACDeck(seed=seed, solitaire=is_solitaire)

        self.resolver = PlayResolver()
        self.ai = SolitaireAI()
        self.solitaire_home = solitaire_home
        self.solitaire_away = solitaire_away

        # Seed global random for deterministic game resolution
        if seed is not None:
            random.seed(seed)

        self.state = GameState(
            home_team=home_team.abbreviation,
            away_team=away_team.abbreviation,
        )
        # 5E: Track defensive penalty for half-cannot-end rule
        self._last_play_had_defensive_penalty: bool = False
        # 5E: Track last play time consumption for timeout restriction
        self._last_play_time: int = 0
        # 5E: Manual two-minute offense declaration
        self._two_minute_declared: bool = False
        # 5E: No-Huddle offense flag
        self._no_huddle: bool = False
        # 5E: Big play defense state per team
        self._big_play_defense = {"home": BigPlayDefense(), "away": BigPlayDefense()}
        self._current_play_personnel_note: Optional[str] = None

        # ── On-field slot overrides ───────────────────────────────────
        # Maps slot name → player_name (str).  When set, _get_all_receivers()
        # and the OL blocking lookup use the named player for that slot
        # instead of the default roster-order logic.
        # Skill slots: FL, LE, RE, BK1, BK2  (per team side: "home" / "away")
        # OL slots:    LT, LG, C, RG, RT    (per team side: "home" / "away")
        self._on_field_offense: Dict[str, Dict[str, str]] = {"home": {}, "away": {}}
        self._on_field_ol: Dict[str, Dict[str, str]] = {"home": {}, "away": {}}

        self.state.possession = random.choice(["home", "away"])
        self.state.play_log.append(f"Coin flip: {self.state.possession} team receives")
        self._log_starting_lineups()

        kickoff_result = self._do_kickoff(
            kicking_team=self.get_defense_team(),
            receiving_team=self.get_offense_team(),
        )
        self._log_kickoff(kickoff_result)

        if kickoff_result.is_touchdown or kickoff_result.result == "KR_TD":
            # Receiving team returned the opening kickoff for a TD.
            # Possession is already on the receiving (scoring) team.
            scorer_is_ai = (self.solitaire_home if self.state.possession == "home"
                            else self.solitaire_away)
            if scorer_is_ai:
                self._score_touchdown()
                followup_kickoff = self._do_kickoff(
                    kicking_team=self.get_offense_team(),
                    receiving_team=self.get_defense_team(),
                )
                self._process_kickoff_result(followup_kickoff)
            else:
                # Human scored the opening KR TD; pause for PAT/2-pt choice
                self._score_td_only()
        else:
            start_yard = self._kickoff_yard_line(kickoff_result)
            self.state.yard_line = start_yard

    def get_offense_team(self) -> Team:
        return self.home_team if self.state.possession == "home" else self.away_team

    def get_defense_team(self) -> Team:
        return self.away_team if self.state.possession == "home" else self.home_team

    def _build_ol_by_position(self) -> Dict[str, PlayerCard]:
        """Return a mapping of OL slot → PlayerCard for the current offense.

        Keys: "LT", "LG", "CN" (center), "RG", "RT".
        Respects any on-field OL substitution overrides.
        """
        offense = self.get_offense_team()
        if not offense or not offense.roster:
            return {}
        side = self.state.possession
        ol_overrides = self._on_field_ol.get(side, {})
        ol_name_to_card: Dict[str, PlayerCard] = {
            p.player_name: p for p in offense.roster.offensive_line
        }
        result: Dict[str, PlayerCard] = {}
        _slot_map = {"LT": "LT", "LG": "LG", "C": "CN", "RG": "RG", "RT": "RT"}
        # Apply overrides first
        for slot, cn_slot in _slot_map.items():
            name = ol_overrides.get(slot)
            if name and name in ol_name_to_card:
                result[cn_slot] = ol_name_to_card[name]
        # Fill remaining from roster
        for ol in offense.roster.offensive_line:
            pos = getattr(ol, "position", "").upper()
            if pos == "C":
                if "CN" not in result:
                    result["CN"] = ol
            elif pos in ("LG", "RG", "LT", "RT"):
                if pos not in result:
                    result[pos] = ol
            elif pos == "OL":
                for slot in ("LT", "LG", "CN", "RG", "RT"):
                    if slot not in result:
                        result[slot] = ol
                        break
        return result

    def _build_defenders_by_box(self, defense: Team) -> Dict[str, PlayerCard]:
        """Build a mapping of box letter (A-O) → PlayerCard for current defenders.

        Uses assign_default_display_boxes to get the assignments,
        then builds the reverse mapping.
        """
        if not defense or not defense.roster:
            return {}
        defenders = list(defense.roster.defenders)[:11]
        if not defenders:
            return {}
        # Get player_name → box_letter mapping
        name_to_box = PlayResolver.assign_default_display_boxes(defenders)
        # Reverse to box_letter → PlayerCard
        box_to_defender: Dict[str, PlayerCard] = {}
        name_to_card = {d.player_name: d for d in defenders}
        for pname, box in name_to_box.items():
            card = name_to_card.get(pname)
            if card:
                box_to_defender[box] = card
        return box_to_defender

    def _build_defenders_list_by_box(self, defense: Team) -> Dict[str, List[PlayerCard]]:
        """Build a mapping of box letter → list of PlayerCards (supports double-staffed boxes).

        Uses assign_defenders_to_boxes_multi so that extra DL beyond the five
        Row-1 slots overflow into interior boxes B, D, C — enabling the
        short-yardage crowding-bonus rule in resolve_sneak.
        """
        if not defense or not defense.roster:
            return {}
        defenders = list(defense.roster.defenders)[:11]
        if not defenders:
            return {}
        multi_map = PlayResolver.assign_defenders_to_boxes_multi(defenders)
        name_to_card = {d.player_name: d for d in defenders}
        result: Dict[str, List[PlayerCard]] = {}
        for box, names in multi_map.items():
            cards = [name_to_card[n] for n in names if n in name_to_card]
            if cards:
                result[box] = cards
        return result

    def _is_player_unavailable(self, player: Optional[PlayerCard]) -> bool:
        return bool(player and self.state.injuries.get(player.player_name, 0) > 0)

    def _find_player_side_and_pos(
        self, player_name: str
    ) -> Optional[tuple]:
        """Return (team_side, position) for *player_name*, or None if not found.

        Searches both teams' full rosters.  Used by the position-injury
        protection logic to determine which team flag to set/clear.
        """
        for team, side in ((self.home_team, "home"), (self.away_team, "away")):
            for card in team.roster.all_players():
                if card.player_name == player_name:
                    return (side, card.position.upper())
        return None

    def _record_personnel_note(self, note: Optional[str]) -> None:
        if not note:
            return
        if self._current_play_personnel_note == note:
            return
        if self._current_play_personnel_note:
            self._current_play_personnel_note = f"{self._current_play_personnel_note} {note}"
        else:
            self._current_play_personnel_note = note
        self.state.play_log.append(f"  🔄 {note}")

    def _apply_current_personnel_note(self, result: PlayResult) -> PlayResult:
        if self._current_play_personnel_note:
            result.personnel_note = self._current_play_personnel_note
        return result

    def _resolve_position_player(
        self,
        players: List[PlayerCard],
        position: str,
        player_name: Optional[str] = None,
    ) -> Optional[PlayerCard]:
        if player_name:
            for player in players:
                if player.player_name == player_name:
                    return None if self._is_player_unavailable(player) else player
            return None

        if not players:
            return None

        starter = players[0]
        if not self._is_player_unavailable(starter):
            return starter

        for idx, player in enumerate(players[1:], start=1):
            if self._is_player_unavailable(player):
                continue
            # Promote the healthy backup into the starter slot so future auto-selection
            # and personnel views reflect the active in-game lineup.
            players[0], players[idx] = players[idx], players[0]
            self._record_personnel_note(
                f"Auto-sub at {position}: {player.player_name} replaces injured {starter.player_name}."
            )
            return player
        return None

    def _immediate_injury_swap(self, injured_player_name: str) -> None:
        """Immediately swap an injured player out of their roster slot.

        When a player is injured mid-play, the formation grid must reflect
        the replacement at once — not on the next play.  Walk every position
        list on *both* teams.  If the injured player is found at *any* index
        (not only the starter slot), move them to the end of the list and
        promote the first healthy backup into their vacated slot so that
        subsequent ``_resolve_position_player`` calls and personnel views
        both reflect the active in-game lineup.

        The replacement is logged in the play log as a substitution entry
        so coaches can see exactly who entered the game, at which slot.
        """
        # Default formation slot by position.  Used when no explicit on-field
        # slot override is registered for the injured player.
        _DEFAULT_SLOT: Dict[str, str] = {
            "QB": "QB", "RB": "BK1", "WR": "LE", "TE": "RE", "K": "K", "P": "P",
        }

        # Number of default starting slots per position (roster-order, no overrides).
        # WR: LE (WR1) + FL (WR2) = 2; RB: BK1 + BK2 = 2; TE: RE (TE1) = 1.
        # When an injured player occupies one of these default starter slots and
        # there is no explicit on-field override, the replacement is chosen from
        # the *backup* pool (indices >= n_starters) so the other active starter
        # is not displaced into a different slot — which would pull a bench player
        # onto the field to fill the vacated spot.
        _NUM_DEFAULT_STARTERS: Dict[str, int] = {"WR": 2, "RB": 2, "TE": 1, "QB": 1}

        for team in (self.home_team, self.away_team):
            side = "home" if team == self.home_team else "away"
            pos_lists = [
                (team.roster.qbs, "QB"),
                (team.roster.rbs, "RB"),
                (team.roster.wrs, "WR"),
                (team.roster.tes, "TE"),
                (team.roster.kickers, "K"),
                (team.roster.punters, "P"),
            ]
            for players, pos in pos_lists:
                # Find the injured player at any roster index
                injured_idx = next(
                    (i for i, p in enumerate(players)
                     if p.player_name == injured_player_name),
                    None,
                )
                if injured_idx is None:
                    continue

                # Find the first healthy backup for the injured player.
                #
                # When the injured player is a default starter (no explicit
                # on-field override) AND the position has more than one default
                # starter, search for the replacement *beyond* the last default
                # starter slot.  This keeps the other active starter in their
                # position instead of displacing them into the vacated slot and
                # inadvertently pulling a bench player onto the field.
                #
                # Example (KC WRs: [Rice/LE, Brown/FL, Hardman/bench, ...]):
                #   Rice (idx=0) injured, no override.
                #   Old: replacement = Brown (idx=1) → promotes Brown to LE,
                #        Hardman auto-fills FL — bench player on field (BUG).
                #   New: search_start = max(1, 2) = 2 → replacement = Hardman,
                #        Brown stays at FL — correct formation.
                on_field = self._on_field_offense.get(side, {})
                has_slot_override = any(
                    pname == injured_player_name for pname in on_field.values()
                )
                n_starters = _NUM_DEFAULT_STARTERS.get(pos, 1)
                search_start = injured_idx + 1
                if has_slot_override:
                    # In a package formation (2TE_1WR, 3TE/JUMBO, 3RB, …),
                    # multiple players of the same position may be on the field
                    # via explicit slot overrides.  Skip *all* of them so the
                    # replacement is a true bench player rather than another
                    # active starter who would then be double-assigned to two
                    # formation slots.
                    #
                    # Example (3TE/JUMBO: RE=TE1, LE=TE2, FL=TE3):
                    #   TE1 (idx=0) injured, has_slot_override=True.
                    #   Old: search_start=1 → replacement=TE2 (on-field!)
                    #        → override becomes RE=TE2 AND LE=TE2 (double-assign BUG).
                    #   New: last_on_field_idx=2 → search_start=3 → TE4 fills RE,
                    #        TE2 stays at LE, TE3 stays at FL — correct formation.
                    on_field_names_for_pos = {
                        pname for pname in on_field.values()
                        if any(pl.player_name == pname for pl in players)
                    }
                    if len(on_field_names_for_pos) > 1:
                        last_on_field_idx = max(
                            (i for i, pl in enumerate(players)
                             if pl.player_name in on_field_names_for_pos),
                            default=injured_idx,
                        )
                        search_start = max(search_start, last_on_field_idx + 1)
                elif injured_idx < n_starters:
                    search_start = max(search_start, n_starters)

                replacement = None
                replacement_idx = None
                for idx in range(search_start, len(players)):
                    if not self._is_player_unavailable(players[idx]):
                        replacement = players[idx]
                        replacement_idx = idx
                        break

                # If no true backup is available, fall back to any healthy player
                # after the injured slot (e.g. only 2 WRs total and both start).
                if replacement is None and search_start > injured_idx + 1:
                    for idx in range(injured_idx + 1, len(players)):
                        if not self._is_player_unavailable(players[idx]):
                            replacement = players[idx]
                            replacement_idx = idx
                            break

                if replacement is not None and replacement_idx is not None:
                    # Swap the injured player with the healthy backup so the
                    # backup occupies the vacated slot and the injured player
                    # moves toward the end of the depth chart.
                    players[injured_idx], players[replacement_idx] = (
                        players[replacement_idx], players[injured_idx]
                    )
                    # If there is an explicit on-field slot override pointing
                    # at the injured player, redirect it to the replacement.
                    on_field = self._on_field_offense.get(side, {})
                    slot = next(
                        (s for s, name in on_field.items()
                         if name == injured_player_name),
                        None,
                    )
                    if slot:
                        on_field[slot] = replacement.player_name
                    else:
                        slot = _DEFAULT_SLOT.get(pos, pos)

                    note = (
                        f"Auto-sub at {pos}: {replacement.player_name} "
                        f"replaces injured {injured_player_name} at {slot}"
                    )
                    self._record_personnel_note(note)
                    self.state.play_log.append(
                        f"  SUB IN:  {replacement.player_name} ({pos}) "
                        f"replaces {injured_player_name} ({pos}) at {slot}"
                    )
                return  # each player belongs to one list only

            # ── Defensive players ─────────────────────────────────────────────
            # The injured player was not found in any offensive position list.
            # Check the flat defenders roster (DL + LB + DB in depth-chart order).
            #
            # Replacement priority (to preserve on-field capability as closely
            # as possible, especially important in season-long simulations):
            #
            #   DT / NT injured → ILB / MLB first (gap control / tackle),
            #                     then OLB, then any healthy LB
            #   DE / DL injured → OLB first (edge rusher role),
            #                     then ILB / MLB, then any healthy LB
            #   Any LB injured  → same-type LB, then any healthy LB;
            #                     no DB fallback (LBs are not DB-qualified)
            #   CB injured      → CB, then S / SS / FS;
            #                     OLB emergency-only when healthy DBs drop below 3
            #   S/SS/FS injured → S / SS / FS, then CB;
            #                     OLB emergency-only when healthy DBs drop below 3
            defenders = team.roster.defenders
            def_injured_idx = next(
                (i for i, p in enumerate(defenders)
                 if p.player_name == injured_player_name),
                None,
            )
            if def_injured_idx is None:
                continue  # not on this team

            injured_card = defenders[def_injured_idx]
            injured_pos = injured_card.position.upper()

            # Count healthy DBs remaining *after* this injury (for emergency rule)
            healthy_dbs_after = [
                p for i, p in enumerate(defenders)
                if i != def_injured_idx
                and not self._is_player_unavailable(p)
                and p.position.upper() in self._DB_POS
            ]

            # Build candidates from the bench only (index ≥ n_on_field).
            # Searching from n_on_field ensures we prefer bench call-ups over
            # pulling another active starter off the field (which would just
            # create a new empty slot elsewhere).
            # Two-stage fallback: if no bench player of the preferred type
            # exists (e.g. 11-man roster with no real bench), also consider
            # other on-field players at index > def_injured_idx who are healthy
            # and of the right position — they can shift roles as an emergency.
            n_on_field = min(11, len(defenders))

            def _def_bench(pos_filter):
                """Return healthy defenders matching pos_filter.

                Stage 1: true bench (index >= n_on_field).
                Stage 2 (fallback): on-field player at index > def_injured_idx
                        when no bench candidate of that type is available.
                """
                bench = [
                    (i, p) for i, p in enumerate(defenders)
                    if i >= n_on_field
                    and not self._is_player_unavailable(p)
                    and p.position.upper() in pos_filter
                ]
                if bench:
                    return bench
                # Fallback: on-field player that hasn't played yet in their slot
                return [
                    (i, p) for i, p in enumerate(defenders)
                    if i > def_injured_idx
                    and i < n_on_field
                    and not self._is_player_unavailable(p)
                    and p.position.upper() in pos_filter
                ]

            if injured_pos in self._DL_POS:
                if injured_pos in ("DT", "NT"):
                    # Interior DL → ILB/MLB (gap/tackle) before OLB
                    primary = sorted(
                        _def_bench({"ILB", "MLB"}),
                        key=lambda ip: -(ip[1].tackle_rating + ip[1].pass_rush_rating),
                    )
                    secondary = sorted(
                        _def_bench({"OLB"}),
                        key=lambda ip: -ip[1].pass_rush_rating,
                    )
                else:
                    # Edge DL (DE/DL) → OLB (edge rusher) before ILB/MLB
                    primary = sorted(
                        _def_bench({"OLB"}),
                        key=lambda ip: -ip[1].pass_rush_rating,
                    )
                    secondary = sorted(
                        _def_bench({"ILB", "MLB"}),
                        key=lambda ip: -(ip[1].tackle_rating + ip[1].pass_rush_rating),
                    )
                # Also add any generic LB as tertiary
                tertiary = _def_bench({"LB"})
                candidates = primary + secondary + tertiary

            elif injured_pos in self._LB_POS:
                same_type = _def_bench({injured_pos})
                other_lb = [
                    ip for ip in _def_bench(self._LB_POS)
                    if ip[1].position.upper() != injured_pos
                ]
                # No DB fallback for LBs
                candidates = same_type + other_lb

            elif injured_pos in self._DB_POS:
                if injured_pos == "CB":
                    same_type = sorted(
                        _def_bench({"CB"}),
                        key=lambda ip: -ip[1].pass_defense_rating,
                    )
                    other_db = sorted(
                        _def_bench({"S", "SS", "FS", "DB"}),
                        key=lambda ip: -ip[1].pass_defense_rating,
                    )
                else:
                    same_type = sorted(
                        _def_bench({"S", "SS", "FS"}),
                        key=lambda ip: -ip[1].pass_defense_rating,
                    )
                    other_db = sorted(
                        _def_bench({"CB", "DB"}),
                        key=lambda ip: -ip[1].pass_defense_rating,
                    )
                # OLB may fill in as emergency coverage when fewer than 3 DBs remain
                olb_emergency: list[tuple[int, PlayerCard]] = []
                if len(healthy_dbs_after) < 3:
                    olb_emergency = sorted(
                        _def_bench({"OLB"}),
                        key=lambda ip: -ip[1].pass_defense_rating,
                    )
                candidates = same_type + other_db + olb_emergency

            else:
                # Unknown defensive position — fall back to depth-chart order
                candidates = [
                    (i, p) for i, p in enumerate(defenders)
                    if i > def_injured_idx and not self._is_player_unavailable(p)
                ]

            if not candidates:
                return  # no replacement available — log and give up

            def_replacement_idx, def_replacement = candidates[0]

            # Swap: injured slides back, replacement moves into starter spot
            defenders[def_injured_idx], defenders[def_replacement_idx] = (
                defenders[def_replacement_idx], defenders[def_injured_idx]
            )

            # Determine whether this is a cross-position emergency sub
            same_group = (
                (injured_pos in self._DL_POS and def_replacement.position.upper() in self._DL_POS) or
                (injured_pos in self._LB_POS and def_replacement.position.upper() in self._LB_POS) or
                (injured_pos in self._DB_POS and def_replacement.position.upper() in self._DB_POS)
            )
            is_emergency = not same_group
            prefix = "EMERGENCY " if is_emergency else ""
            note = (
                f"{prefix}Auto-sub at {injured_pos}: "
                f"{def_replacement.player_name} ({def_replacement.position}) "
                f"replaces injured {injured_player_name}"
            )
            self._record_personnel_note(note)
            self.state.play_log.append(
                f"  {prefix}DEF SUB: "
                f"{def_replacement.player_name} ({def_replacement.position}) "
                f"replaces {injured_player_name} ({injured_pos})"
            )
            return

    def validate_player_availability(self, player_name: str) -> PlayerCard:
        for player in self.get_offense_team().roster.all_players():
            if player.player_name == player_name:
                if self._is_player_unavailable(player):
                    raise ValueError(f"{player_name} is injured and unavailable.")
                return player
        raise ValueError(f"{player_name} is not on the current offense.")

    # ── 5E Endurance ─────────────────────────────────────────────────

    def _check_endurance_violation(self, player: PlayerCard,
                                    for_pass: bool = False) -> Optional[str]:
        """Check if directing a play at *player* violates endurance rules.

        Returns a violation string (e.g. ``"endurance_1"``) or ``None``.

        Applies to all skill positions (RB, WR, TE) per 5E rules.
        On run plays the penalty is +2 to Run Number; on pass plays the
        penalty is -5 to the QB's Completion Range.

        Parameters
        ----------
        player : PlayerCard
            The player the play is directed at.
        for_pass : bool
            If True, use the player's pass-receiving endurance
            (``endurance_pass``) instead of rushing endurance.

        5E endurance ratings:
          0 → unlimited ("workhorse" / "D" grade)
          1 → must rest 1 play between uses
          2 → must rest 2 plays between uses
          3 → once per drive / possession
          4 → once per quarter
        """
        if for_pass:
            endurance = getattr(player, "endurance_pass", None)
        else:
            endurance = getattr(player, "endurance_rushing", None)
        if endurance is None or endurance == 0:
            return None
        name = player.player_name
        if endurance == 1:
            if self.state.last_ball_carrier == name:
                return "endurance_1"
        elif endurance == 2:
            if name in (self.state.last_ball_carrier, self.state.prev_ball_carrier):
                return "endurance_2"
        elif endurance == 3:
            if name in self.state.endurance_used_this_drive:
                return "endurance_3"
        elif endurance >= 4:
            if name in self.state.endurance_used_this_quarter:
                return "endurance_4"
        return None

    def _apply_endurance_penalty_to_run(self, player: PlayerCard,
                                         run_number: int) -> tuple:
        """If the ball carrier violates endurance, add +2 to run number.

        Returns ``(adjusted_run_number, violation_string_or_None)``.
        """
        violation = self._check_endurance_violation(player)
        if violation:
            return run_number + 2, violation
        return run_number, None

    def _record_endurance_usage(self, player_name: Optional[str]) -> None:
        """Record that *player_name* was the ball carrier this play."""
        if not player_name:
            return
        self.state.endurance_used_this_drive.add(player_name)
        self.state.endurance_used_this_quarter.add(player_name)

    def get_returner(self, team: Team, kind: str) -> Optional[PlayerCard]:
        return team.get_return_specialist(kind, unavailable_names=set(self.state.injuries))

    def _do_kickoff(self, kicking_team: Team, receiving_team: Team) -> PlayResult:
        """Resolve a kickoff using 5E team card tables when available."""
        ko_table = kicking_team.get_kickoff_table()
        kr_returners = receiving_team.get_kickoff_returners()
        kr_table = receiving_team.get_kickoff_return_table()
        rec_is_home = (receiving_team == self.home_team)
        return self.resolver.resolve_kickoff_5e(
            self.deck, ko_table, kr_returners, kr_table,
            fumbles_lost_max=getattr(receiving_team, 'fumbles_lost_max', 21),
            def_fumble_adj=getattr(kicking_team, 'def_fumble_adj', 0),
            is_home=rec_is_home,
        )

    def _log_kickoff(self, kickoff: PlayResult, prefix: str = "") -> None:
        """Append kickoff description *and* debug-log detail to the play log.

        ``prefix`` is an optional label prepended to the first line
        (e.g. "Second half kickoff: ").
        """
        desc = f"{prefix}{kickoff.description}" if prefix else kickoff.description
        self.state.play_log.append(desc)
        if kickoff.debug_log:
            for entry in kickoff.debug_log:
                self.state.play_log.append(f"    {entry}")

    def _process_kickoff_result(self, kickoff: PlayResult) -> None:
        """Log a kickoff and apply its result to the game state.

        Handles kick-return touchdowns: the receiving team scores 6 points,
        the game pauses for PAT/2-pt choice if that team is human-controlled,
        or auto-resolves the PAT and kicks off again if AI-controlled.

        Call this method when the KICKING team currently has possession.
        """
        self._log_kickoff(kickoff)
        if kickoff.is_touchdown or kickoff.result == "KR_TD":
            # Receiving team returned the kickoff for a TD.
            # Swap possession so the scoring (receiving) team is now the offense.
            # yard_line=99 is a placeholder overridden after the PAT+kickoff.
            self._change_possession(99)
            scorer_is_ai = (self.solitaire_home if self.state.possession == "home"
                            else self.solitaire_away)
            if scorer_is_ai:
                self._score_touchdown()
                ko2 = self._do_kickoff(
                    kicking_team=self.get_offense_team(),
                    receiving_team=self.get_defense_team(),
                )
                self._log_kickoff(ko2)
                self._change_possession(self._kickoff_yard_line(ko2))
            else:
                # Human scored the KR TD; sets pending_extra_point=True so the
                # player must call /pat-kick or /two-point-conversion next.
                self._score_td_only()
        else:
            self._change_possession(self._kickoff_yard_line(kickoff))

    def _kickoff_yard_line(self, kickoff: PlayResult) -> int:
        """Extract the starting yard line from a kickoff result."""
        if kickoff.result == "TOUCHBACK":
            return max(1, kickoff.yards_gained) if kickoff.yards_gained else 20
        if kickoff.result == "OOB":
            return 40
        return max(1, kickoff.yards_gained)

    def _log_starting_lineups(self) -> None:
        """Log both teams' starting lineups and base defensive schemes to the play log.

        Called once at game start so players and coaches can immediately verify
        who is on the field and in what formation — and can spot any roster or
        formation bugs before the first snap.
        """
        self.state.play_log.append("=== STARTING LINEUPS ===")
        for label, team in (("HOME", self.home_team), ("AWAY", self.away_team)):
            abbr = team.abbreviation
            base_def = team.base_defense.replace("_", "-")  # "4_3" → "4-3"

            # ── Offensive starters ────────────────────────────────────
            off_parts: List[str] = []
            if team.roster.qbs:
                off_parts.append(f"QB {team.roster.qbs[0].player_name}")
            if team.roster.rbs:
                off_parts.append(f"RB {team.roster.rbs[0].player_name}")
            wrs = team.roster.wrs[:3]
            if wrs:
                off_parts.append("WR " + ", ".join(p.player_name for p in wrs))
            tes = team.roster.tes[:1]
            if tes:
                off_parts.append(f"TE {tes[0].player_name}")
            ol = team.roster.offensive_line[:5]
            if ol:
                off_parts.append("OL " + " | ".join(p.player_name for p in ol))

            # ── Defensive starters (first 11 in roster order) ─────────
            defs = team.roster.defenders[:11]
            # Compute dynamic box assignments so the log matches the board.
            def_boxes = PlayResolver.assign_default_display_boxes(defs)
            dl_group = [p for p in defs if p.position.upper() in self._DL_POS]
            lb_group = [p for p in defs if p.position.upper() in self._LB_POS]
            db_group = [p for p in defs if p.position.upper() in self._DB_POS]
            def_parts: List[str] = []
            if dl_group:
                def_parts.append("DL " + ", ".join(
                    f"{p.position} {p.player_name}({def_boxes.get(p.player_name, '?')})"
                    for p in dl_group))
            if lb_group:
                def_parts.append("LB " + ", ".join(
                    f"{p.position} {p.player_name}({def_boxes.get(p.player_name, '?')})"
                    for p in lb_group))
            if db_group:
                def_parts.append("DB " + ", ".join(
                    f"{p.position} {p.player_name}({def_boxes.get(p.player_name, '?')})"
                    for p in db_group))

            self.state.play_log.append(
                f"{label} ({abbr}) — Base Defense: {base_def}"
            )
            self.state.play_log.append(
                f"  OFF: {' | '.join(off_parts)}"
            )
            self.state.play_log.append(
                f"  DEF ({base_def}): {' | '.join(def_parts)}"
            )
        self.state.play_log.append("========================")

    def get_qb(self, player_name: Optional[str] = None) -> Optional[PlayerCard]:
        return self._resolve_position_player(self.get_offense_team().roster.qbs, "QB", player_name)

    def get_rb(self, player_name: Optional[str] = None) -> Optional[PlayerCard]:
        return self._resolve_position_player(self.get_offense_team().roster.rbs, "RB", player_name)

    def _pick_fresh_rb(self) -> Optional[PlayerCard]:
        """Return the first healthy RB without an endurance violation.

        Used by AI play calling so a fatigued back is not sent on a run when
        a fresher alternative is available.  Falls back to the first healthy
        RB when every available back has an endurance issue.
        """
        rbs = self.get_offense_team().roster.rbs
        healthy = [r for r in rbs if not self._is_player_unavailable(r)]
        if not healthy:
            return None
        fresh = [r for r in healthy if self._check_endurance_violation(r) is None]
        return fresh[0] if fresh else healthy[0]

    def get_wr(self, player_name: Optional[str] = None) -> Optional[PlayerCard]:
        return self._resolve_position_player(self.get_offense_team().roster.wrs, "WR", player_name)

    def get_te(self) -> Optional[PlayerCard]:
        return self._resolve_position_player(self.get_offense_team().roster.tes, "TE")

    def get_kicker(self) -> Optional[PlayerCard]:
        return self._resolve_position_player(self.get_offense_team().roster.kickers, "K")

    def get_punter(self) -> Optional[PlayerCard]:
        return self._resolve_position_player(self.get_offense_team().roster.punters, "P")

    # ── On-field slot management ─────────────────────────────────────

    # Valid skill slots and OL slots
    _SKILL_SLOTS = {"FL", "LE", "RE", "BK1", "BK2", "BK3"}
    _OL_SLOTS = {"LT", "LG", "C", "RG", "RT"}

    # Defensive position groups (used by apply_defense_package)
    _DL_POS = {"DE", "DT", "DL", "NT"}
    _LB_POS = {"LB", "OLB", "ILB", "MLB"}
    _DB_POS = {"CB", "S", "SS", "FS", "DB"}

    def set_field_slot(self, side: str, slot: str, player_name: Optional[str]) -> str:
        """Assign (or clear) a named player to an on-field slot for *side*.

        Parameters
        ----------
        side : str
            ``'home'`` or ``'away'``.
        slot : str
            Skill slot (``FL``, ``LE``, ``RE``, ``BK1``, ``BK2``, ``BK3``) or
            OL slot (``LT``, ``LG``, ``C``, ``RG``, ``RT``).
        player_name : str or None
            Player name to assign.  Pass ``None`` (or empty string) to clear
            the override and revert to automatic selection.

        Returns a log message string.
        """
        slot = slot.upper()
        side = side.lower()
        if side not in ("home", "away"):
            raise ValueError(f"Invalid side: {side}")

        if player_name:
            # Validate the player exists on the correct team
            team = self.home_team if side == "home" else self.away_team
            all_off = team.roster.all_players()
            found = next((p for p in all_off if p.player_name.lower() == player_name.lower()), None)
            if found is None:
                raise ValueError(f"Player '{player_name}' not found on {side} team")

        if slot in self._SKILL_SLOTS:
            if player_name:
                self._on_field_offense[side][slot] = player_name
                msg = f"ON-FIELD SLOT: {player_name} assigned to {slot} ({side})"
            else:
                # LE and RE must always be occupied (7-man line of scrimmage rule).
                # Clearing them is only allowed if a different player is present via
                # auto-fill logic; reject explicit clears to prevent illegal formations.
                if slot in ("LE", "RE"):
                    raise ValueError(
                        f"Cannot clear {slot}: LE and RE must always be occupied "
                        f"(NFL 7-man line-of-scrimmage rule). "
                        f"Reassign {slot} to a different player instead, "
                        f"or apply the STANDARD package to restore auto-selection."
                    )
                self._on_field_offense[side].pop(slot, None)
                msg = f"ON-FIELD SLOT: {slot} ({side}) cleared — auto-select"
        elif slot in self._OL_SLOTS:
            if player_name:
                self._on_field_ol[side][slot] = player_name
                msg = f"OL SLOT: {player_name} assigned to {slot} ({side})"
            else:
                self._on_field_ol[side].pop(slot, None)
                msg = f"OL SLOT: {slot} ({side}) cleared — auto-select"
        else:
            raise ValueError(
                f"Invalid slot '{slot}'. Skill: {sorted(self._SKILL_SLOTS)}, "
                f"OL: {sorted(self._OL_SLOTS)}"
            )
        self.state.play_log.append(msg)
        return msg

    def get_field_assignments(self, side: str) -> Dict[str, str]:
        """Return the current on-field overrides for *side* (both skill and OL)."""
        side = side.lower()
        assignments: Dict[str, str] = {}
        assignments.update(self._on_field_offense.get(side, {}))
        assignments.update(self._on_field_ol.get(side, {}))
        return assignments

    def apply_formation_package(self, side: str, package: str) -> str:
        """Apply a named formation package, setting on-field slot overrides.

        Supported packages
        ------------------
        ``STANDARD``  — clear all overrides (fall back to roster order).
        ``2TE_1WR``   — WR1→LE, TE1→RE, TE2→FL (two-tight-end set with one wide receiver).
        ``3TE``       — TE1→RE, TE2→LE, TE3→FL (three tight-end set).
        ``JUMBO``     — same as 3TE but logged as Jumbo package.
        ``4WR``       — WR1→LE, WR2→FL, WR3→RE, no TE on field.
        ``3RB``       — WR1→LE (split end on line), TE1→RE (tight end on line),
                        RB1→BK1, RB2→BK2, RB3→BK3; FL is absent.
                        7-man line: 5 OL + LE + RE ✓  Typically FB + two HBs.
        """
        side = side.lower()
        package = package.upper()
        if side not in ("home", "away"):
            raise ValueError(f"Invalid side: {side}")

        team = self.home_team if side == "home" else self.away_team
        unavail = set(self.state.injuries)

        def _healthy(players: List[PlayerCard]) -> List[PlayerCard]:
            return [p for p in players if p.player_name not in unavail]

        wrs = _healthy(team.roster.wrs)
        tes = _healthy(team.roster.tes)
        rbs = _healthy(team.roster.rbs)

        # Clear current overrides first
        self._on_field_offense[side] = {}
        self._on_field_ol[side] = {}

        if package == "STANDARD":
            msg = f"PACKAGE: STANDARD ({side}) — auto-select restored"
        elif package in ("3TE", "JUMBO"):
            # TE1→RE, TE2→LE, TE3→FL
            label = "JUMBO" if package == "JUMBO" else "3TE"
            if len(tes) >= 3:
                self._on_field_offense[side]["RE"] = tes[0].player_name
                self._on_field_offense[side]["LE"] = tes[1].player_name
                self._on_field_offense[side]["FL"] = tes[2].player_name
                msg = (
                    f"PACKAGE: {label} ({side}) — "
                    f"RE={tes[0].player_name}, LE={tes[1].player_name}, "
                    f"FL={tes[2].player_name}"
                )
            elif len(tes) == 2:
                self._on_field_offense[side]["RE"] = tes[0].player_name
                self._on_field_offense[side]["LE"] = tes[1].player_name
                msg = (
                    f"PACKAGE: {label} ({side}) — only 2 TEs available: "
                    f"RE={tes[0].player_name}, LE={tes[1].player_name}"
                )
            else:
                msg = f"PACKAGE: {label} ({side}) — not enough TEs (need 3, have {len(tes)})"
        elif package == "4WR":
            # WR1→LE, WR2→FL, WR3→RE (no TE)
            if len(wrs) >= 3:
                self._on_field_offense[side]["LE"] = wrs[0].player_name
                self._on_field_offense[side]["FL"] = wrs[1].player_name
                self._on_field_offense[side]["RE"] = wrs[2].player_name
                msg = (
                    f"PACKAGE: 4WR ({side}) — "
                    f"LE={wrs[0].player_name}, FL={wrs[1].player_name}, "
                    f"RE={wrs[2].player_name}"
                )
            else:
                msg = f"PACKAGE: 4WR ({side}) — not enough WRs (need 3, have {len(wrs)})"
        elif package == "2TE_1WR":
            # WR1→LE (split end on line), TE1→RE (primary TE on line),
            # TE2→FL (second TE split off the line as flanker).
            # This is the classic "double tight-end" or "two-TE" set used by
            # power running teams.  It is distinct from the standard 2WR+1TE
            # formation — both tight ends are active skill targets.
            new_overrides: Dict[str, str] = {}
            if wrs:
                new_overrides["LE"] = wrs[0].player_name
            if tes:
                new_overrides["RE"] = tes[0].player_name
            if len(tes) >= 2:
                new_overrides["FL"] = tes[1].player_name
            self._on_field_offense[side] = new_overrides
            assignments = ", ".join(f"{k}={v}" for k, v in new_overrides.items())
            msg = f"PACKAGE: 2TE_1WR ({side}) — {assignments}"
        elif package == "3RB":
            # Three-back power set (e.g. I-formation with fullback):
            #   LE = WR1 as split end — on the line of scrimmage (mandatory)
            #   RE = TE1 as tight end — on the line of scrimmage (mandatory)
            #   BK1/BK2/BK3 = three backs in the B-slots
            #   FL = none (no flanker in a 3-back set)
            # Line of scrimmage: 5 OL + LE + RE = 7 players ✓
            new_overrides_3rb: Dict[str, str] = {}
            if wrs:
                new_overrides_3rb["LE"] = wrs[0].player_name   # WR1 as split end on line
            elif tes and len(tes) >= 2:
                new_overrides_3rb["LE"] = tes[1].player_name   # TE2 if no WR available
            if tes:
                new_overrides_3rb["RE"] = tes[0].player_name   # TE1 as tight end on line
            if len(rbs) >= 1:
                new_overrides_3rb["BK1"] = rbs[0].player_name
            if len(rbs) >= 2:
                new_overrides_3rb["BK2"] = rbs[1].player_name
            if len(rbs) >= 3:
                new_overrides_3rb["BK3"] = rbs[2].player_name
            # FL is intentionally absent — 3-back formation has no flanker
            self._on_field_offense[side] = new_overrides_3rb
            assignments_3rb = ", ".join(f"{k}={v}" for k, v in new_overrides_3rb.items())
            msg = f"PACKAGE: 3RB ({side}) — {assignments_3rb}"
        else:
            raise ValueError(
                f"Unknown package '{package}'. "
                f"Valid: STANDARD, 2TE_1WR, 3TE, JUMBO, 4WR, 3RB"
            )

        self.state.play_log.append(msg)
        return msg

    def apply_defense_package(self, side: str, package: str) -> str:
        """Reorder the defense roster to reflect a named coverage/rush package.

        The first 11 entries in ``team.roster.defenders`` are treated as the
        on-field unit.  This method reorders that list so the desired mix of
        DL / LB / DB is at positions 0–10.  It mirrors how individual defensive
        substitutions already work, so existing play logic requires no changes.

        Supported packages
        ------------------
        ``STANDARD``   — restore 4-3 base: up to 4 DL + 3 LB + 4 DB.
        ``NICKEL``     — 4-2-5: 4 DL, 2 LB, 5 DB (drop 1 LB, add 1 DB).
        ``DIME``       — 4-1-6: 4 DL, 1 LB, 6 DB (drop 2 LBs, add 2 DBs).
        ``335``        — 3-3-5: 3 DL, 3 LB, 5 DB (3-4 nickel base).
        ``PREVENT``    — 2-2-7: 2 DL, 2 LB, 7 DB (prevent / cover-2 deep).
        ``GOAL_LINE``  — 5 best-tackle DL/LB on line + 3 LB + 3 DB (no FS).
                         Selects the 5 players (from DL+LB combined) with the
                         highest tackle_rating + pass_rush_rating; fills 3 more
                         LB slots from remaining LBs; completes with DBs
                         excluding any FS-position players.
        """
        side = side.lower()
        package = package.upper()
        if side not in ("home", "away"):
            raise ValueError(f"Invalid side: {side}")

        team = self.home_team if side == "home" else self.away_team
        unavail = set(self.state.injuries)

        all_def = team.roster.defenders
        # Capture the current on-field unit (first 11) BEFORE the change.
        prev_starters = {p.player_name for p in all_def[:11]}

        h_dls = [p for p in all_def if p.position.upper() in self._DL_POS
                 and p.player_name not in unavail]
        h_lbs = [p for p in all_def if p.position.upper() in self._LB_POS
                 and p.player_name not in unavail]
        h_dbs = [p for p in all_def if p.position.upper() in self._DB_POS
                 and p.player_name not in unavail]

        # ── Goal Line: special selection logic ───────────────────────
        if package == "GOAL_LINE":
            # Combine DL + LB and sort by tackle + pass-rush rating (best first)
            dl_lb_pool = sorted(
                h_dls + h_lbs,
                key=lambda p: (
                    getattr(p, 'tackle_rating', 0) + getattr(p, 'pass_rush_rating', 0)
                ),
                reverse=True,
            )
            line_five = dl_lb_pool[:5]
            line_five_ids = {id(p) for p in line_five}

            # Remaining LBs (not already selected as line five) for 3 LB slots
            remaining_lbs = [p for p in h_lbs if id(p) not in line_five_ids][:3]

            # DBs excluding FS; at most 3
            h_dbs_no_fs = [p for p in h_dbs if p.position.upper() != "FS"]
            db_three = h_dbs_no_fs[:3]

            starters = line_five + remaining_lbs + db_three
        else:
            # Packages: (n_dl, n_lb, n_db) wanted in first 11
            _PKG_COUNTS: Dict[str, tuple] = {
                "STANDARD": (4, 3, 4),
                "NICKEL":   (4, 2, 5),
                "DIME":     (4, 1, 6),
                "335":      (3, 3, 5),
                "PREVENT":  (2, 2, 7),
            }
            if package not in _PKG_COUNTS:
                raise ValueError(
                    f"Unknown defense package '{package}'. "
                    f"Valid: {', '.join(sorted(list(_PKG_COUNTS.keys()) + ['GOAL_LINE']))}"
                )

            n_dl, n_lb, n_db = _PKG_COUNTS[package]
            starters = h_dls[:n_dl] + h_lbs[:n_lb] + h_dbs[:n_db]

        # If we still don't have 11 starters (roster shortage), fill with
        # remaining healthy players in their original order.
        # For GOAL_LINE: exclude FS from backups to keep them off the field.
        starter_ids = {id(p) for p in starters}
        if package == "GOAL_LINE":
            backups = [
                p for p in all_def
                if id(p) not in starter_ids and p.position.upper() != "FS"
            ]
        else:
            backups = [p for p in all_def if id(p) not in starter_ids]
        team.roster.defenders = starters + backups

        actual_dl = sum(1 for p in starters if p.position.upper() in self._DL_POS)
        actual_lb = sum(1 for p in starters if p.position.upper() in self._LB_POS)
        actual_db = sum(1 for p in starters if p.position.upper() in self._DB_POS)
        msg = (
            f"DEF PACKAGE: {package} ({side}) — "
            f"{actual_dl} DL / {actual_lb} LB / {actual_db} DB on field"
        )
        self.state.play_log.append(msg)

        # Log specific player substitutions caused by this package change.
        # Include box letters (A-O) using dynamic assignment so it's clear
        # exactly which board position each player is coming in/out of.
        new_starters = {p.player_name for p in starters}
        coming_out = prev_starters - new_starters
        coming_in = new_starters - prev_starters
        name_to_card = {p.player_name: p for p in all_def}
        # Box assignments before the change (for outgoing players).
        pre_boxes = PlayResolver.assign_default_display_boxes(
            [p for p in all_def if p.player_name in prev_starters][:11]
        )
        # Box assignments after the change (for incoming players).
        post_boxes = PlayResolver.assign_default_display_boxes(starters)
        for out_name in sorted(coming_out):
            out_card = name_to_card.get(out_name)
            out_pos = out_card.position if out_card else "?"
            out_box = pre_boxes.get(out_name, "?")
            self.state.play_log.append(
                f"  SUB OUT: {out_name} ({out_pos}) — Box {out_box}"
            )
        for in_name in sorted(coming_in):
            in_card = name_to_card.get(in_name)
            in_pos = in_card.position if in_card else "?"
            in_box = post_boxes.get(in_name, "?")
            self.state.play_log.append(
                f"  SUB IN:  {in_name} ({in_pos}) — Box {in_box}"
            )

        return msg

    def _track_play_stats(self, result) -> None:
        """Track player stats and game-level turnover counts."""
        stats = self.state.player_stats
        team = self.state.possession

        # Track turnovers
        if result.turnover:
            self.state.turnovers[team] = self.state.turnovers.get(team, 0) + 1

        # Track rushing stats
        if result.rusher:
            name = result.rusher
            if name not in stats:
                stats[name] = {"rushing_yards": 0, "rushing_attempts": 0, "rushing_tds": 0,
                               "receiving_yards": 0, "receptions": 0, "receiving_tds": 0,
                               "passing_yards": 0, "pass_attempts": 0, "completions": 0,
                               "passing_tds": 0, "interceptions": 0, "sacks": 0}
            if result.play_type == "RUN":
                stats[name]["rushing_yards"] += result.yards_gained
                stats[name]["rushing_attempts"] += 1
                if result.is_touchdown:
                    stats[name]["rushing_tds"] += 1

        # Track passing stats
        if result.passer:
            name = result.passer
            if name not in stats:
                stats[name] = {"rushing_yards": 0, "rushing_attempts": 0, "rushing_tds": 0,
                               "receiving_yards": 0, "receptions": 0, "receiving_tds": 0,
                               "passing_yards": 0, "pass_attempts": 0, "completions": 0,
                               "passing_tds": 0, "interceptions": 0, "sacks": 0}
            if result.play_type == "PASS":
                stats[name]["pass_attempts"] += 1
                if result.result in ("GAIN", "TD", "COMPLETE"):
                    stats[name]["completions"] += 1
                    stats[name]["passing_yards"] += result.yards_gained
                    if result.is_touchdown:
                        stats[name]["passing_tds"] += 1
                elif result.result == "INT":
                    stats[name]["interceptions"] += 1
                elif result.result == "SACK":
                    stats[name]["sacks"] += 1

        # Track receiving stats
        if result.receiver and result.play_type == "PASS" and result.result in ("GAIN", "TD", "COMPLETE"):
            name = result.receiver
            if name not in stats:
                stats[name] = {"rushing_yards": 0, "rushing_attempts": 0, "rushing_tds": 0,
                               "receiving_yards": 0, "receptions": 0, "receiving_tds": 0,
                               "passing_yards": 0, "pass_attempts": 0, "completions": 0,
                               "passing_tds": 0, "interceptions": 0, "sacks": 0}
            stats[name]["receptions"] += 1
            stats[name]["receiving_yards"] += result.yards_gained
            if result.is_touchdown:
                stats[name]["receiving_tds"] += 1

    def _advance_down(self, yards: int) -> bool:
        """Advance down counter. Returns True if first down achieved."""
        self.state.yard_line = min(99, self.state.yard_line + yards)
        self.state.distance -= yards

        if self.state.yard_line >= 100:
            return True  # Touchdown

        # Safety: ball goes behind own goal line (run loss, sack, etc.)
        if self.state.yard_line <= 0:
            self._score_safety()
            return True

        if self.state.distance <= 0:
            self.state.down = 1
            self.state.distance = 10
            return True

        self.state.down += 1
        return False

    def _turnover_on_downs(self) -> None:
        self.state.possession = "home" if self.state.possession == "away" else "away"
        self.state.yard_line = 100 - self.state.yard_line
        self.state.down = 1
        self.state.distance = 10

    def _change_possession(self, new_yard_line: int) -> None:
        self.state.possession = "home" if self.state.possession == "away" else "away"
        self.state.yard_line = new_yard_line
        self.state.down = 1
        self.state.distance = 10
        # Reset per-drive endurance tracking on possession change
        self.state.endurance_used_this_drive = set()
        # Also reset consecutive-play counters since it's a new possession
        self.state.last_ball_carrier = None
        self.state.prev_ball_carrier = None
        # 5E: two-minute and no-huddle are rescinded on possession change
        if self._two_minute_declared:
            self._two_minute_declared = False
            self.state.play_log.append("  ⏱️ Two-minute offense rescinded (possession changed).")
        if self._no_huddle:
            self._no_huddle = False
            self.state.play_log.append("  🏃 No-huddle offense rescinded (possession changed).")

    def _score_touchdown(self) -> None:
        if self.state.possession == "home":
            self.state.score.home += 6
        else:
            self.state.score.away += 6
        self.state.play_log.append(
            f"TOUCHDOWN! Score: Away {self.state.score.away} - Home {self.state.score.home}"
        )

        kicker = self.get_kicker()
        if kicker:
            xp = self.resolver.resolve_xp(kicker)
            self.state.play_log.append(xp.description)
            if xp.result == "XP_GOOD":
                if self.state.possession == "home":
                    self.state.score.home += 1
                else:
                    self.state.score.away += 1
        else:
            if self.state.possession == "home":
                self.state.score.home += 1
            else:
                self.state.score.away += 1

    def _score_td_only(self) -> None:
        """Score 6 points for a touchdown by the human player's team.

        Unlike _score_touchdown(), this does NOT auto-kick the PAT or perform
        the kickoff — instead it sets pending_extra_point so the human can
        choose between a PAT kick and a 2-point conversion.
        """
        if self.state.possession == "home":
            self.state.score.home += 6
        else:
            self.state.score.away += 6
        self.state.play_log.append(
            f"TOUCHDOWN! Score: Away {self.state.score.away} - Home {self.state.score.home}"
        )
        self.state.pending_extra_point = True

    def execute_pat_kick(self) -> "PlayResult":
        """Execute the PAT (point-after-touchdown) kick chosen by the human.

        Resolves the XP kick, awards 1 point if good, performs the kickoff,
        and clears pending_extra_point.
        """
        if not self.state.pending_extra_point:
            raise ValueError("No pending extra point to resolve")
        self.state.pending_extra_point = False

        kicker = self.get_kicker()
        if kicker:
            xp = self.resolver.resolve_xp(kicker)
            self.state.play_log.append(xp.description)
            if xp.result == "XP_GOOD":
                if self.state.possession == "home":
                    self.state.score.home += 1
                else:
                    self.state.score.away += 1
        else:
            # No kicker on roster — auto-award the point
            if self.state.possession == "home":
                self.state.score.home += 1
            else:
                self.state.score.away += 1
            from .play_resolver import PlayResult as _PR
            xp = _PR("XP", 0, "XP_GOOD", description="Extra point is good! (auto)")

        self.state.play_log.append(
            f"Score: Away {self.state.score.away} - Home {self.state.score.home}"
        )

        # Kickoff after the extra point
        kickoff = self._do_kickoff(
            kicking_team=self.get_offense_team(),
            receiving_team=self.get_defense_team(),
        )
        self._process_kickoff_result(kickoff)

        return xp

    def execute_two_point_conversion_attempt(
        self, play_type: str, player_name: Optional[str] = None
    ) -> tuple:
        """Execute a 2-point conversion attempt chosen by the human.

        Resolves the play at the 2-yard line using the FAC resolver (without
        going through the full execute_play() state machine), awards 2 points
        on success, performs the kickoff, and clears pending_extra_point.

        play_type: 'RUN', 'SHORT_PASS', or 'QUICK_PASS'
        Returns (PlayResult, success: bool).
        """
        if not self.state.pending_extra_point:
            raise ValueError("No pending extra point to resolve")
        self.state.pending_extra_point = False

        fac_card = self.deck.draw()
        situation = self.state.to_situation()

        # AI calls defense for the 2-pt attempt
        def_formation, def_play_5e, def_strategy_5e = self.ai.call_defense_play_5e(
            situation, fac_card,
            base_defense=self.get_defense_team().base_defense,
        )

        play_call = PlayCall(
            play_type=play_type.upper(),
            formation="SHOTGUN",
            direction="MIDDLE",
            reasoning="Two-point conversion attempt",
        )

        self.state.play_log.append(
            f"⚡ 2-PT CONVERSION ATTEMPT — {play_type.upper()}"
        )

        play_upper = play_type.upper()
        if play_upper in ("SHORT_PASS", "QUICK_PASS", "LONG_PASS"):
            result = self._execute_pass_5e(
                fac_card, play_call,
                defense_formation=def_formation.value,
                defensive_strategy=def_strategy_5e.value,
                player_name=player_name,
                defensive_play_5e=def_play_5e,
            )
        else:
            # RUN (or any unrecognised type → default run)
            result = self._execute_run_5e(
                fac_card, play_call,
                defense_formation=def_formation.value,
                player_name=player_name,
                defensive_play_5e=def_play_5e,
            )

        self.state.play_log.append(f"  → {result.description}")
        if getattr(result, 'debug_log', None):
            for dl_entry in result.debug_log:
                self.state.play_log.append(f"    {dl_entry}")

        # Success: 2+ yards gained from the 2-yard line (or any TD result)
        success = result.yards_gained >= 2 or result.is_touchdown or result.result == "TD"

        if success:
            if self.state.possession == "home":
                self.state.score.home += 2
            else:
                self.state.score.away += 2
            self.state.play_log.append("✅ Two-point conversion GOOD!")
        else:
            self.state.play_log.append("❌ Two-point conversion FAILED")

        self.state.play_log.append(
            f"Score: Away {self.state.score.away} - Home {self.state.score.home}"
        )

        # Kickoff after the conversion attempt
        kickoff = self._do_kickoff(
            kicking_team=self.get_offense_team(),
            receiving_team=self.get_defense_team(),
        )
        self._process_kickoff_result(kickoff)

        return result, success

    def _score_safety(self) -> None:
        """Score a safety — 2 points for the defense.

        The defensive team (opponent) gets 2 points, then the team that
        conceded the safety kicks off from their own 20-yard line (a free
        kick).  Because the kick comes from the 20 rather than the normal
        35, any touchback on that kick is taken at the 15-yard line (5 yards
        closer to the goal than a standard kickoff touchback).
        """
        # Award 2 points to the defensive team
        if self.state.possession == "home":
            self.state.score.away += 2
        else:
            self.state.score.home += 2
        self.state.play_log.append(
            f"SAFETY! 2 points for defense. "
            f"Score: Away {self.state.score.away} - Home {self.state.score.home}"
        )
        # The team that conceded the safety kicks off from their own 20.
        # At this point self.state.possession is still the *offense* that
        # got tackled — that team is the kicker.
        kicking_team = self.get_offense_team()
        receiving_team = self.get_defense_team()
        kickoff = self._do_kickoff(kicking_team, receiving_team)
        self._log_kickoff(kickoff, prefix="Safety free kick from the 20: ")
        new_yl = self._safety_kickoff_yard_line(kickoff)
        # Possession transfers to the receiving team
        self._change_possession(new_yl)

    def _safety_kickoff_yard_line(self, kickoff: PlayResult) -> int:
        """Starting yard line after a safety free kick.

        The free kick is from the 20 instead of the normal 35, so all
        results are shifted 15 yards back.  A plain touchback lands at
        the 15 (rather than the normal 20).
        """
        if kickoff.result == "TOUCHBACK":
            # Shift the normal touchback line back by 15 yards
            normal_yl = max(1, kickoff.yards_gained) if kickoff.yards_gained else 20
            return max(1, normal_yl - 5)
        if kickoff.result == "OOB":
            return max(1, 40 - 15)  # OOB spot shifts back 15 yards too
        return max(1, kickoff.yards_gained)

    def execute_play(self, play_call: Optional[PlayCall] = None,
                     defense_formation: Optional[str] = None,
                     player_name: Optional[str] = None,
                     defensive_strategy: Optional[str] = None,
                     defensive_play: Optional[str] = None,
                     blitz_players: Optional[List[str]] = None,
                     backs_blocking: Optional[List[str]] = None) -> PlayResult:
        """Execute a single play using 5th-edition rules.

        Args:
            play_call: Optional human-specified offensive play call.
            defense_formation: Optional human-specified defensive formation.
            player_name: Optional specific player to use for the play.
            defensive_strategy: Optional human-specified defensive strategy (5E).
            defensive_play: Optional defensive play type (PASS_DEFENSE, BLITZ, etc.).
            blitz_players: Optional list of player names to blitz (2-5 LBs/DBs).
            backs_blocking: Optional list of RB player names kept in to pass-block
                instead of running routes (+2 completion range each; FAC redirect
                to a blocking back is incomplete).
        """
        self._current_play_personnel_note = None
        # Resolve backs_blocking player names → receiver indices so the resolver
        # can identify which list positions are blocking (not running routes).
        backing_indices: Optional[List[int]] = None
        if backs_blocking:
            receivers = self._get_all_receivers()
            backing_indices = [
                i for i, rec in enumerate(receivers)
                if rec.player_name in backs_blocking
            ]
        return self._execute_play_5e(play_call, defense_formation,
                                     player_name=player_name,
                                     defensive_strategy=defensive_strategy,
                                     defensive_play=defensive_play,
                                     blitz_players=blitz_players,
                                     backs_blocking=backing_indices)

    def _pick_receiver(self, play_call: PlayCall, player_name: Optional[str] = None) -> Optional[PlayerCard]:
        team = self.get_offense_team()

        # If specific player requested, try to find them among all eligible receivers
        if player_name:
            for p in team.roster.wrs + team.roster.tes + team.roster.rbs:
                if p.player_name == player_name:
                    return None if self._is_player_unavailable(p) else p

        if "DEEP" in play_call.direction:
            receivers = [p for p in team.roster.wrs if not self._is_player_unavailable(p)]
            return random.choice(receivers) if receivers else None

        options = [
            p for p in (team.roster.wrs + team.roster.tes)
            if not self._is_player_unavailable(p)
        ]
        return random.choice(options) if options else None

    def _execute_field_goal(self) -> PlayResult:
        kicker = self.get_kicker()
        distance = (100 - self.state.yard_line) + 17

        if kicker:
            return self.resolver.resolve_field_goal(distance, kicker)

        rate = max(0.3, 0.95 - (distance - 20) * 0.015)
        made = random.random() < rate
        return PlayResult("FG", 0, "FG_GOOD" if made else "FG_NO_GOOD",
                          description=f"{'Makes' if made else 'Misses'} {distance}-yard FG")

    def _execute_punt(self) -> PlayResult:
        """Execute a punt using 5E FAC deck mechanics."""
        punter = self.get_punter()
        if not punter:
            dist = random.randint(38, 52)
            result = PlayResult("PUNT", dist - 8, "PUNT",
                                description=f"Punt {dist} yards, returned 8 yards")
            punt_distance = dist
            new_yl = max(1, 100 - self.state.yard_line - punt_distance + random.randint(0, 10))
            self._change_possession(new_yl)
            return result

        # Draw FAC for RN to determine punt distance
        fac_card = self.deck.draw()
        if fac_card.is_z_card:
            fac_card = self.deck.draw_non_z()
        rn = fac_card.run_num_int or random.randint(1, 12)
        rn = max(1, min(12, rn))

        # RN 12 special handling
        if rn == 12:
            result = self.resolver.resolve_punt_rn12(punter, self.deck)
            if result.result == "BLOCKED_PUNT":
                spot = max(1, self.state.yard_line - 5)
                self._change_possession(100 - spot)
                return result
            elif result.result == "PENALTY":
                self._apply_penalty(result.penalty)
                return result
            # Longest kick — treat as OOB punt
            punt_distance = result.yards_gained
            new_yl = max(1, 100 - self.state.yard_line - punt_distance)
            self._change_possession(new_yl)
            return result

        # Look up punt distance from 5E table
        punt_distance = Charts.get_punt_distance_5e(punter.avg_distance, rn)

        # Check blocked punt
        blocked_num = getattr(punter, 'blocked_punt_number', 0) or 0
        if Charts.check_blocked_punt(blocked_num, rn):
            result = PlayResult("PUNT", -5, "BLOCKED_PUNT",
                                description=f"{punter.player_name}'s punt is BLOCKED!")
            spot = max(1, self.state.yard_line - 5)
            self._change_possession(100 - spot)
            return result

        # Punt return using 5E team card tables
        receiving_team = self.get_defense_team()
        punt_returners = receiving_team.get_punt_returners()
        punt_return_table = receiving_team.get_punt_return_table()
        fumbles_lost_max = getattr(receiving_team, 'fumbles_lost_max', 21)
        def_fumble_adj = getattr(self.get_offense_team(), 'def_fumble_adj', 0)
        is_home = (self.state.possession != "home")  # receiving team is home?

        return_info = self.resolver.resolve_punt_return_5e(
            self.deck, punt_returners, punt_return_table,
            punt_distance, self.state.yard_line,
            fumbles_lost_max=fumbles_lost_max,
            def_fumble_adj=def_fumble_adj,
            is_home=is_home,
        )

        return_yards = return_info.get("return_yards", 0)
        is_fair_catch = return_info.get("is_fair_catch", False)
        is_td = return_info.get("is_td", False)
        is_fumble = return_info.get("is_fumble", False)
        fumble_lost = return_info.get("fumble_lost", False)
        returner_name = return_info.get("returner_name", "unknown")

        net_punt = punt_distance - return_yards
        desc = f"{punter.player_name} punts {punt_distance} yards"
        if is_fair_catch:
            desc += f", fair catch by {returner_name}"
        elif return_yards > 0:
            desc += f", {returner_name} returns it {return_yards} yards"
        if is_td:
            desc += " TOUCHDOWN!"

        result = PlayResult("PUNT", net_punt, "PUNT", description=desc)
        result.debug_log = return_info.get("log_entries", [])

        if is_td:
            # Receiving team returned the punt for a TD.
            # Swap possession so the scoring (receiving) team is now the offense,
            # then handle scoring + PAT/kickoff exactly like any other TD.
            result.is_touchdown = True
            self._change_possession(99)  # placeholder; overridden after PAT+kickoff
            scorer_is_ai = (self.solitaire_home if self.state.possession == "home"
                            else self.solitaire_away)
            if scorer_is_ai:
                self._score_touchdown()
                kickoff = self._do_kickoff(
                    kicking_team=self.get_offense_team(),
                    receiving_team=self.get_defense_team(),
                )
                self._process_kickoff_result(kickoff)
            else:
                # Human scored the punt-return TD; sets pending_extra_point=True
                # so the player must call /pat-kick or /two-point-conversion next.
                self._score_td_only()
            return result

        if is_fumble and fumble_lost:
            result.turnover = True
            result.turnover_type = "FUMBLE"

        new_yl = max(1, 100 - self.state.yard_line - punt_distance + return_yards)
        self._change_possession(new_yl)
        return result

    def _handle_turnover(self, result: PlayResult) -> None:
        if result.turnover_type == "INT":
            if result.is_touchdown:
                # Pick-six: intercepting team (currently defense) scores a TD.
                # Swap possession so the intercepting team becomes the offense,
                # score the TD, then handle PAT + kickoff just like a normal TD.
                # yard_line=99 is a placeholder; scoring doesn't depend on it and
                # it will be overridden by the kickoff (AI) or PAT flow (human).
                self._change_possession(99)
                scorer_is_ai = (self.solitaire_home if self.state.possession == "home"
                                else self.solitaire_away)
                if scorer_is_ai:
                    self._score_touchdown()
                    kickoff = self._do_kickoff(
                        kicking_team=self.get_offense_team(),
                        receiving_team=self.get_defense_team(),
                    )
                    self._process_kickoff_result(kickoff)
                else:
                    # Human scored the pick-six; sets pending_extra_point=True so
                    # the player must call /pat-kick or /two-point-conversion next,
                    # followed by the kickoff before the opponent gets the ball.
                    self._score_td_only()
                return
            if result.interception_point is not None:
                new_yl = result.interception_point
            else:
                new_yl = random.randint(20, 45)
            self._change_possession(new_yl)
        elif result.turnover_type == "FUMBLE":
            new_yl = max(1, 100 - self.state.yard_line)
            self._change_possession(new_yl)

    def _apply_penalty(self, penalty: Dict) -> None:
        """Apply a penalty to the game state.

        Supports the 5E penalty format (from Z-card resolution) which uses
        a 'team' field ('offense'/'defense'/'kicking'/'receiving') and also
        the punt/kickoff penalty dicts which use their own conventions.
        """
        ptype = penalty.get("type", "")
        yards = penalty.get("yards", 10)
        auto_first = penalty.get("auto_first", False)
        loss_of_down = penalty.get("loss_of_down", False)
        name = penalty.get("name", ptype)

        self.state.play_log.append(f"  ⚠ PENALTY: {name} - {yards} yards")

        # Determine whether this is against the offense or defense.
        # 5E Z-card penalties have a "team" field; punt penalties have their own
        # convention.
        team = penalty.get("team", "")
        is_against_offense = team in ("offense", "kicking")
        is_against_defense = team in ("defense", "receiving")

        # Apply half-distance-to-goal
        if is_against_offense:
            yards = PlayResolver.apply_half_distance_penalty(
                yards, self.state.yard_line, is_offense_penalty=True
            )
            self.state.yard_line = max(1, self.state.yard_line - yards)
            self.state.distance += yards
        elif is_against_defense:
            yards = PlayResolver.apply_half_distance_penalty(
                yards, self.state.yard_line, is_offense_penalty=False
            )
            self.state.yard_line = min(99, self.state.yard_line + yards)
            self.state.distance -= yards
            if auto_first:
                self.state.down = 1
                self.state.distance = 10

        if loss_of_down:
            self.state.down += 1

        if self.state.distance <= 0:
            self.state.down = 1
            self.state.distance = 10

        # Track penalty count
        pen_team_key = (self.state.get_defense_team()
                        if is_against_defense
                        else (self.state.possession if self.state.possession else "home"))
        self.state.penalties[pen_team_key] = self.state.penalties.get(pen_team_key, 0) + 1
        self.state.penalty_yards[pen_team_key] = (
            self.state.penalty_yards.get(pen_team_key, 0) + yards
        )

        # Track defensive penalty for half-cannot-end rule
        self._last_play_had_defensive_penalty = is_against_defense

    # ── 5E Timeout Rules ─────────────────────────────────────────────

    def call_timeout(self, team: str = "offense") -> bool:
        """Call a timeout.  5E Rule: only after plays that take > 10 seconds.

        Returns True if timeout was successfully called.
        """
        # 5E restriction: timeout only after plays consuming > 10 seconds
        if self._last_play_time <= self.TIME_CLOCK_STOP:
            self.state.play_log.append(
                "⏱ Timeout denied — only allowed after plays using > 10 seconds"
            )
            return False

        if team == "offense":
            which = "home" if self.state.possession == "home" else "away"
        else:
            which = "away" if self.state.possession == "home" else "home"

        if which == "home" and self.state.timeouts_home > 0:
            self.state.timeouts_home -= 1
            self.state.play_log.append(
                f"⏱ Timeout called by home team ({self.state.timeouts_home} remaining)"
            )
            return True
        elif which == "away" and self.state.timeouts_away > 0:
            self.state.timeouts_away -= 1
            self.state.play_log.append(
                f"⏱ Timeout called by away team ({self.state.timeouts_away} remaining)"
            )
            return True
        self.state.play_log.append("⏱ No timeouts remaining!")
        return False

    # ── 5E: Possession-change timing ─────────────────────────────────

    TIME_POSSESSION_CHANGE = 10  # Possession change plays use 10 seconds
    # Per 5E rules page 4 Timing Table:
    TIME_STANDARD_PLAY = 40   # Run, complete pass, sack — 40 seconds
    TIME_CLOCK_STOP = 10      # Incomplete pass, OOB, injury, penalty, TD — 10 seconds
    TIME_PUNT_KICK = 10       # Punt / kickoff — 10 seconds
    TIME_FIELD_GOAL = 5       # Field goal attempt — 5 seconds
    TIME_KNEEL = 40           # Kneel — maximum clock burn (same as standard play)
    TIME_ZERO = 0             # Touchback, XP, movement penalties — 0 seconds

    def _calculate_time(self, result: PlayResult) -> int:
        """Determine seconds consumed by a play using 5th-edition rules.

        5th-edition Timing Table (Page 4):
          * Run, complete pass, sack     → 40 seconds
          * Incomplete pass, OOB         → 10 seconds
          * Injury, penalty, TD, timeout → 10 seconds
          * Punt, kickoff                → 10 seconds
          * Field goal attempt           → 5 seconds
          * Touchback, XP, movement pen  → 0 seconds
          * Kneel                        → 40 seconds

        Two-Minute Offense: all play times halved (min 1 s).
        No-Huddle Offense: only non-clock-stopping play times halved;
          clock-stopping plays use normal time and auto-rescind no-huddle.
        """
        is_kicking = result.play_type in ("PUNT", "KICKOFF", "FG")

        if result.result in ("TOUCHBACK", "XP_GOOD", "XP_MISS"):
            time = self.TIME_ZERO
        elif result.play_type == "PUNT" or result.play_type == "KICKOFF":
            time = self.TIME_PUNT_KICK
        elif result.play_type == "FG" or result.result in ("FG_GOOD", "FG_MISS"):
            time = self.TIME_FIELD_GOAL
        elif result.penalty:
            time = self.TIME_CLOCK_STOP
        elif result.out_of_bounds:
            time = self.TIME_CLOCK_STOP
        elif result.result == "INCOMPLETE":
            time = self.TIME_CLOCK_STOP
        elif result.is_touchdown or result.result == "TD":
            time = self.TIME_CLOCK_STOP
        elif result.play_type == "KNEEL":
            time = self.TIME_KNEEL
        elif result.play_type == "SPIKE" or result.strategy == "SPIKE":
            time = self.TIME_CLOCK_STOP
        else:
            time = self.TIME_STANDARD_PLAY

        # ── Two-Minute / No-Huddle time halving ───────────────────────
        clock_stopping = (time <= self.TIME_CLOCK_STOP and time > self.TIME_ZERO)
        if not is_kicking:
            if self._is_two_minute_offense():
                # Two-minute halves ALL play times (incl. clock-stopping)
                if time > self.TIME_ZERO:
                    time = max(1, time // 2)
            elif self._no_huddle:
                # No-huddle only halves non-clock-stopping play times
                if not clock_stopping and time > self.TIME_ZERO:
                    time = max(1, time // 2)
                elif clock_stopping:
                    # Clock-stopping play in no-huddle → auto-rescind
                    self._rescind_no_huddle_offense(reason="clock stopped")

        # Track for timeout restriction rule
        self._last_play_time = time
        return time

    def _advance_time(self, seconds: int) -> None:
        self.state.time_remaining -= seconds

        # 5E Rule: Half cannot end on a defensive penalty
        # If time expires and the last play had a defensive penalty,
        # the offense gets one more untimed play
        if self.state.time_remaining <= 0 and self.state.quarter in (2, 4):
            if self._last_play_had_defensive_penalty:
                self.state.time_remaining = 1  # Allow one more play
                self.state.play_log.append(
                    "⏱ Half cannot end on a defensive penalty — untimed play"
                )
                self._last_play_had_defensive_penalty = False
                return

        if self.state.time_remaining <= 0:
            self.state.quarter += 1
            # Reset per-quarter endurance tracking
            self.state.endurance_used_this_quarter = set()
            if self.state.quarter > 4:
                if self.state.score.home == self.state.score.away:
                    self.state.quarter = 5
                    self.state.time_remaining = 600
                    self.state.play_log.append("OVERTIME!")
                else:
                    self.state.is_over = True
                    winner = "Home" if self.state.score.home > self.state.score.away else "Away"
                    self.state.play_log.append(
                        f"GAME OVER! Final: Away {self.state.score.away} - Home {self.state.score.home}"
                    )
                    self.state.play_log.append(f"Winner: {winner} team")
                    self.state.play_log.extend(self.format_boxscore())
            else:
                self.state.time_remaining = 900
                self.state.play_log.append(
                    f"End of Q{self.state.quarter - 1}, starting Q{self.state.quarter}"
                )
                if self.state.quarter == 3:
                    self.state.possession = (
                        "home" if self.state.possession == "away" else "away"
                    )
                    kickoff = self._do_kickoff(
                        kicking_team=self.get_defense_team(),
                        receiving_team=self.get_offense_team(),
                    )
                    self._log_kickoff(kickoff, prefix="Second half kickoff: ")
                    if kickoff.is_touchdown or kickoff.result == "KR_TD":
                        # Receiving team returned the second-half kickoff for a TD.
                        # Possession is already on the receiving (scoring) team.
                        scorer_is_ai = (self.solitaire_home if self.state.possession == "home"
                                        else self.solitaire_away)
                        if scorer_is_ai:
                            self._score_touchdown()
                            ko2 = self._do_kickoff(
                                kicking_team=self.get_offense_team(),
                                receiving_team=self.get_defense_team(),
                            )
                            self._process_kickoff_result(ko2)
                        else:
                            self._score_td_only()
                    else:
                        new_yl = self._kickoff_yard_line(kickoff)
                        self.state.yard_line = new_yl
                        self.state.down = 1
                        self.state.distance = 10

    # ── 5th-Edition FAC-card-based play execution ────────────────────

    def _get_all_receivers(self) -> list:
        """Get on-field receivers in formation position order.

        The board has 6 possible skill slots in this order:
          FL  (Flanker)         — off the line; may be empty (e.g. 3RB set)
          LE  (Left End)        — ON the line of scrimmage; MANDATORY
          RE  (Right End)       — ON the line of scrimmage; MANDATORY
          BK1 (Back 1 / B1)    — backfield
          BK2 (Back 2 / B2)    — backfield
          BK3 (Back 3 / B3)    — backfield; only set via override (e.g. 3RB)

        **7-man line rule**: NFL rules require 7 players on the line of
        scrimmage.  The 5 OL fill 5 of those spots, so LE and RE are *always*
        mandatory.  FL is optional (absent in 3-back formations).

        Each returned PlayerCard has its ``_formation_slot`` attribute set to
        the slot name it occupies (e.g. ``'LE'``, ``'BK1'``).  This is used
        by the FAC targeting system for slot-name based lookups so that
        targeting remains correct even when FL is absent.

        The on-field list is at most 5 receivers (5 OL + QB + 5 skill = 11).
        Any None slot is dropped and the list is capped at 5.

        If on-field slot overrides are set (via set_field_slot or
        apply_formation_package), those player assignments take precedence
        over the default roster-order logic for any slot that is defined.
        """
        team = self.get_offense_team()
        side = self.state.possession
        overrides = self._on_field_offense.get(side, {})

        # Build a name→card lookup across all skill players so we can resolve
        # overrides regardless of which position bucket the player normally
        # lives in (e.g. a TE listed in the overrides as the FL slot).
        all_skill: List[PlayerCard] = (
            team.roster.wrs + team.roster.tes +
            team.roster.rbs + team.roster.qbs
        )
        name_to_card: Dict[str, PlayerCard] = {p.player_name: p for p in all_skill}

        def _resolve_override(slot: str) -> Optional[PlayerCard]:
            """Return the override player for *slot* if set and not injured."""
            name = overrides.get(slot)
            if not name:
                return None
            card = name_to_card.get(name)
            if card is None or self._is_player_unavailable(card):
                return None
            return card

        wrs = [w for w in team.roster.wrs if not self._is_player_unavailable(w)]
        tes = [t for t in team.roster.tes if not self._is_player_unavailable(t)]
        rbs = [r for r in team.roster.rbs if not self._is_player_unavailable(r)]

        # ── Resolve each slot, checking overrides first ───────────────
        fl = _resolve_override("FL")
        le = _resolve_override("LE")
        re = _resolve_override("RE")
        bk1 = _resolve_override("BK1")
        bk2 = _resolve_override("BK2")
        # BK3 is only populated via explicit override (e.g. 3RB package).
        # It is never auto-filled so that the standard 5-slot formation is
        # unchanged when no 3RB package is active.
        bk3 = _resolve_override("BK3")

        # Track which cards are already assigned by overrides (using object id)
        # so the default logic doesn't double-assign them.
        def _assigned_ids() -> set:
            return {id(c) for c in [fl, le, re, bk1, bk2, bk3] if c is not None}

        avail_wrs = [w for w in wrs if id(w) not in _assigned_ids()]
        avail_tes = [t for t in tes if id(t) not in _assigned_ids()]
        avail_rbs = [r for r in rbs if id(r) not in _assigned_ids()]

        # ── Auto-fill FL and LE when neither is overridden ────────────
        # Standard: LE = WR1 (on line), FL = WR2 (off line flanker)
        if le is None and fl is None:
            if len(avail_wrs) >= 2:
                fl = avail_wrs[1]  # WR2 as flanker
                le = avail_wrs[0]  # WR1 at left end
            elif len(avail_wrs) == 1:
                fl = avail_wrs[0]  # Only WR → flanker
                le = avail_tes[0] if avail_tes else None  # TE fills left end
            else:
                le = avail_tes[0] if len(avail_tes) > 0 else None
                fl = avail_tes[1] if len(avail_tes) > 1 else None
        elif le is None:
            # FL is set by override; fill LE from available WRs/TEs (mandatory)
            if avail_wrs:
                le = avail_wrs[0]
            elif avail_tes:
                le = avail_tes[0]
        elif fl is None:
            # LE is set by override; fill FL from available WRs/TEs if any remain.
            # FL is optional — if nothing is left (e.g. 3RB), it stays None.
            if avail_wrs:
                fl = avail_wrs[0]
            elif avail_tes:
                fl = avail_tes[0]

        # Refresh available after FL/LE resolution
        avail_tes = [t for t in tes if id(t) not in _assigned_ids()]
        avail_rbs = [r for r in rbs if id(r) not in _assigned_ids()]

        # RE = first available TE not already used (mandatory)
        if re is None:
            re = avail_tes[0] if avail_tes else None

        # ── Mandatory LE/RE fallback (7-man line-of-scrimmage rule) ───
        # If LE or RE is still None after normal auto-fill (e.g. all WRs/TEs
        # are injured), pull any remaining skill player as an emergency fill.
        # When the only option is an RB, pick by ability grade:
        #   LE (wide-receiver role) → best receiving RB (most pass_gain rows,
        #       then lowest blocks so speed backs are preferred over blockers).
        #   RE (tight-end / blocker role) → best blocking RB (blocks descending).
        def _receiving_sort_key(p: PlayerCard) -> tuple:
            # Count non-empty pass_gain rows (v1 == 0 indicates a blank/placeholder row
            # with no real gain value on the card).
            n_gain = sum(1 for r in p.pass_gain if r is not None and r.v1 != 0)
            return (-n_gain, p.blocks)  # more rows and fewer blocks = better receiver

        if le is None:
            wrs_tes = [p for p in (wrs + tes) if id(p) not in _assigned_ids()]
            rbs_recv = sorted(
                [p for p in rbs if id(p) not in _assigned_ids()],
                key=_receiving_sort_key,
            )
            avail_any = wrs_tes + rbs_recv
            if avail_any:
                le = avail_any[0]
        if re is None:
            wrs_tes = [p for p in (tes + wrs) if id(p) not in _assigned_ids()]
            rbs_block = sorted(
                [p for p in rbs if id(p) not in _assigned_ids()],
                key=lambda p: -p.blocks,  # higher blocks = better blocker
            )
            avail_any = wrs_tes + rbs_block
            if avail_any:
                re = avail_any[0]

        # Update available again for BK slots
        avail_rbs = [r for r in rbs if id(r) not in _assigned_ids()]

        if bk1 is None:
            bk1 = avail_rbs[0] if len(avail_rbs) > 0 else None
        avail_rbs = [r for r in avail_rbs if r is not bk1]
        if bk2 is None:
            bk2 = avail_rbs[0] if avail_rbs else None

        # ── Annotate each card with its slot name ─────────────────────
        # _formation_slot is used by FAC slot-name targeting so that the
        # correct player is found even when FL is absent (e.g. 3RB).
        slot_pairs = [("FL", fl), ("LE", le), ("RE", re),
                      ("BK1", bk1), ("BK2", bk2), ("BK3", bk3)]
        for slot_name, card in slot_pairs:
            if card is not None:
                card._formation_slot = slot_name

        # Build ordered list, drop absent slots, cap at 5.
        receivers = [card for _, card in slot_pairs if card is not None][:5]

        # Assign receiver letters if not already set
        letters = ["A", "B", "C", "D", "E"]
        for i, rec in enumerate(receivers):
            if not rec.receiver_letter:
                rec.receiver_letter = letters[i]
        return receivers

    def _execute_play_5e(self, play_call: Optional[PlayCall] = None,
                        defense_formation: Optional[str] = None,
                        defensive_strategy: Optional[str] = None,
                        defensive_play: Optional[str] = None,
                        player_name: Optional[str] = None,
                        blitz_players: Optional[List[str]] = None,
                        backs_blocking: Optional[List[int]] = None) -> PlayResult:
        """Execute a single play using 5th-edition FAC deck."""
        fac_card = self.deck.draw()
        situation = self.state.to_situation()

        human_provided = play_call is not None

        if play_call is None:
            play_call = self.ai.call_play_5e(situation, fac_card)

        # ── 5E Play calling with proper types ────────────────────────
        # When the human provided a play call, derive the OffensivePlay enum
        # directly from their play_type/direction — never call the AI for the
        # human's offensive side.  AI play-calling is only used when there is
        # no human call (solitaire / sim modes).
        if human_provided:
            off_play = _DIRECTION_TO_OFFENSIVE_PLAY.get(
                play_call.direction,
                _PLAY_TYPE_TO_OFFENSIVE_PLAY.get(play_call.play_type,
                                                  OffensivePlay.SHORT_PASS),
            )
            try:
                off_strategy = OffensiveStrategy(play_call.strategy) if play_call.strategy else OffensiveStrategy.NONE
            except ValueError:
                off_strategy = OffensiveStrategy.NONE
            # player_inv is not used for display when human_provided (player_name is shown
            # instead in off_call_str below).  RB_1 is used as a harmless placeholder
            # for the PlayCall.player_involved field.
            player_inv = PlayerInvolved.RB_1
            if play_call.play_type == "RUN":
                play_call = PlayCall(
                    play_type=play_call.play_type,
                    formation=play_call.formation,
                    direction=play_call.direction,
                    reasoning=play_call.reasoning,
                    strategy=play_call.strategy,
                    offensive_play=off_play.value,
                    player_involved=player_inv.value,
                )
        else:
            off_play, off_strategy, player_inv = self.ai.call_offense_play_5e(situation, fac_card)
            # For AI run plays: sync the play_call direction with the chosen OffensivePlay.
            if play_call.play_type == "RUN" and off_play in _OFFENSIVE_PLAY_TO_DIRECTION:
                play_call = PlayCall(
                    play_type=play_call.play_type,
                    formation=play_call.formation,
                    direction=_OFFENSIVE_PLAY_TO_DIRECTION[off_play],
                    reasoning=play_call.reasoning,
                    strategy=play_call.strategy,
                    offensive_play=off_play.value,
                    player_involved=player_inv.value,
                )

        # If the human provided a defensive play, use it; otherwise use AI
        if defensive_play is not None:
            # Convert string to DefensivePlay enum
            try:
                def_play_5e = DefensivePlay(defensive_play.upper())
            except ValueError:
                def_play_5e = DefensivePlay.PASS_DEFENSE
            # Convert string to DefensiveFormation enum
            if defense_formation is not None:
                try:
                    def_formation_5e = DefensiveFormation(defense_formation.upper())
                except ValueError:
                    # Try mapping legacy formation names
                    from .play_types import LEGACY_FORMATION_TO_FORMATION
                    def_formation_5e = LEGACY_FORMATION_TO_FORMATION.get(
                        defense_formation.upper(), DefensiveFormation.FOUR_THREE
                    )
            else:
                def_formation_5e = DefensiveFormation.FOUR_THREE
            # Convert string to DefensiveStrategy enum
            if defensive_strategy is not None:
                try:
                    def_strategy_5e = DefensiveStrategy(defensive_strategy.upper())
                except ValueError:
                    def_strategy_5e = DefensiveStrategy.NONE
            else:
                def_strategy_5e = DefensiveStrategy.NONE
        else:
            def_formation_5e, def_play_5e, def_strategy_5e = self.ai.call_defense_play_5e(
                situation, fac_card,
                base_defense=self.get_defense_team().base_defense,
            )

        # Ensure defensive_strategy string is always set.
        # When the human provided a defensive_play, def_strategy_5e is derived from the human
        # input (defaulting to NONE) — no AI was called.  When the AI chose the defense, use
        # whatever strategy the AI selected.
        if defensive_strategy is None:
            defensive_strategy = def_strategy_5e.value

        if human_provided:
            # Show the human's actual call: use the named player if given,
            # or "Auto" so no AI-generated label ever appears for a human play.
            player_label = player_name if player_name else "Auto"
            off_call_str = (
                f"{OFFENSIVE_PLAY_NAMES.get(off_play, off_play.value)}"
                f" / {OFFENSIVE_STRATEGY_NAMES.get(off_strategy, off_strategy.value)}"
                f" / {player_label}"
            )
        else:
            off_call_str = (
                f"{OFFENSIVE_PLAY_NAMES.get(off_play, off_play.value)}"
                f" / {OFFENSIVE_STRATEGY_NAMES.get(off_strategy, off_strategy.value)}"
                f" / {PLAYER_INVOLVED_NAMES.get(player_inv, player_inv.value)}"
            )
        def_call_str = (
            f"{def_formation_5e.value} Formation"
            f" / {DEFENSIVE_PLAY_NAMES.get(def_play_5e, def_play_5e.value)}"
            f" / {DEFENSIVE_STRATEGY_NAMES.get(def_strategy_5e, def_strategy_5e.value)}"
        )

        self.state.play_log.append(
            f"Q{self.state.quarter} {self._time_str()} | "
            f"{'Home' if self.state.possession == 'home' else 'Away'} ball | "
            f"{self.state.down}{self._ordinal_suffix(self.state.down)} & {self.state.distance} | "
            f"Own {self.state.yard_line}"
        )
        # Determine which sides are human-controlled so we can suppress AI shadow calls.
        # In full solitaire (both AI) we log both sides for simulation visibility.
        offense_side = self.state.possession
        defense_side = "away" if offense_side == "home" else "home"
        offense_is_ai = self.solitaire_home if offense_side == "home" else self.solitaire_away
        defense_is_ai = self.solitaire_home if defense_side == "home" else self.solitaire_away
        full_solitaire = offense_is_ai and defense_is_ai
        if not offense_is_ai or full_solitaire:
            self.state.play_log.append(f"  OFFENSE: {off_call_str}")
        if not defense_is_ai or full_solitaire:
            self.state.play_log.append(f"  DEFENSE: {def_call_str}")
        if blitz_players:
            self.state.play_log.append(f"  BLITZ PLAYERS: {', '.join(blitz_players)}")

        # ── Auto-apply GOAL_LINE defensive package ────────────────────
        # When the AI (or human) selects GOAL_LINE formation, trigger the
        # personnel substitution so the roster is updated before the play runs.
        if def_formation_5e == DefensiveFormation.GOAL_LINE:
            try:
                self.apply_defense_package(defense_side, "GOAL_LINE")
            except ValueError as pkg_err:
                # Roster may not have enough players; proceed with current personnel
                self.state.play_log.append(
                    f"  NOTE: GOAL_LINE package could not be applied: {pkg_err}"
                )

        # ── AI backs-blocking decision (offense AI only) ──────────────
        _PASS_PLAY_TYPES = {"SHORT_PASS", "LONG_PASS", "QUICK_PASS", "SCREEN"}
        if backs_blocking is None and offense_is_ai and play_call.play_type in _PASS_PLAY_TYPES:
            ai_receivers = self._get_all_receivers()
            backs_blocking = self.ai.decide_backs_blocking(situation, ai_receivers)
        if backs_blocking:
            # Resolve back indices to names for the log
            log_receivers = self._get_all_receivers()
            blocking_names = [
                log_receivers[i].player_name
                for i in backs_blocking
                if i < len(log_receivers)
            ]
            if blocking_names:
                self.state.play_log.append(
                    f"  BACKS BLOCKING: {', '.join(blocking_names)} "
                    f"(+{len(blocking_names) * 2} completion range)"
                )

        # ── 5E Play restrictions ─────────────────────────────────────
        # Long pass within opponent's 20 → auto-convert to short pass
        if play_call.play_type == "LONG_PASS":
            if PlayResolver.check_long_pass_restriction(self.state.yard_line):
                play_call = PlayCall(
                    play_type="SHORT_PASS",
                    formation=play_call.formation,
                    direction=play_call.direction,
                    reasoning="Long pass restricted inside 20; converted to short",
                )
        # Screen pass within 5-yard line → auto-convert to short pass
        if play_call.play_type == "SCREEN":
            if PlayResolver.check_screen_pass_restriction(self.state.yard_line):
                play_call = PlayCall(
                    play_type="SHORT_PASS",
                    formation=play_call.formation,
                    direction=play_call.direction,
                    reasoning="Screen restricted inside 5; converted to short",
                )

        # ── Strategy handling ─────────────────────────────────────────
        strategy = getattr(play_call, 'strategy', None)

        # Guard: ensure strategy is compatible with the play type so that
        # a stale or mis-matched strategy selection never overrides the
        # explicit play call made by the human.
        #   - PLAY_ACTION is a pass strategy; discard it on run plays.
        #   - PLAY_ACTION is illegal from SHOTGUN (can't fake a run from an
        #     obvious passing formation — 5E rule).
        #   - DRAW is a run strategy; discard it on pass/special plays.
        _PASS_TYPES = {"SHORT_PASS", "LONG_PASS", "QUICK_PASS", "SCREEN"}
        _RUN_TYPES  = {"RUN"}
        if strategy == "PLAY_ACTION" and play_call.play_type not in _PASS_TYPES:
            strategy = None
            play_call.strategy = None
        if strategy == "PLAY_ACTION" and getattr(play_call, 'formation', '').upper() == "SHOTGUN":
            strategy = None
            play_call.strategy = None
            self.state.play_log.append(
                "  NOTE: Play-Action not allowed from Shotgun formation — converted to standard pass"
            )
        if strategy == "DRAW" and play_call.play_type not in _RUN_TYPES:
            strategy = None
            play_call.strategy = None
        if strategy == "FLOP":
            qb = self.get_qb(player_name)
            if qb:
                result = self.resolver.resolve_flop(qb)
                self._apply_current_personnel_note(result)
                self.state.play_log.append(f"  → {result.description}")
                self._advance_down(result.yards_gained)
                self._advance_time(self.TIME_STANDARD_PLAY)
                self._track_play_stats(result)
                return result
        elif strategy == "SNEAK":
            qb = self.get_qb(player_name)
            if qb:
                defense = self.get_defense_team()
                ol_by_pos = self._build_ol_by_position()
                def_list_by_box = self._build_defenders_list_by_box(defense)
                result = self.resolver.resolve_sneak(
                    qb, self.deck,
                    ol_by_position=ol_by_pos,
                    defenders_list_by_box=def_list_by_box,
                )
                self._apply_current_personnel_note(result)
                self.state.play_log.append(f"  → {result.description}")
                if hasattr(result, 'debug_log') and result.debug_log:
                    for dl_entry in result.debug_log:
                        self.state.play_log.append(f"    {dl_entry}")
                self._advance_down(result.yards_gained)
                self._advance_time(self.TIME_STANDARD_PLAY)
                self._track_play_stats(result)
                return result
        elif strategy == "DRAW":
            # Draw play can use any back (RB or QB) as ball carrier
            if player_name:
                rusher = self.get_rb(player_name)
            else:
                # AI play: prefer a fresh (non-fatigued) RB
                rusher = self._pick_fresh_rb()
            if rusher is None:
                rusher = self.get_qb(player_name)
            # Use the human-provided defense formation when available; only fall back to AI
            # when no defensive call was provided at all (solitaire/sim mode).
            if defense_formation:
                def_form = defense_formation
            elif defensive_play is None:
                def_form = self.ai.call_defense_5e(
                    situation, fac_card,
                    base_defense=self.get_defense_team().base_defense,
                )
            else:
                def_form = DefensiveFormation.FOUR_THREE.value
            defense = self.get_defense_team()
            defenders_by_box = self._build_defenders_by_box(defense)
            if rusher:
                result = self.resolver.resolve_draw(
                    fac_card, self.deck, rusher, def_form,
                    defense_run_stop=defense.defense_rating,
                    defensive_play=defensive_play,
                    defenders_by_box=defenders_by_box,
                    defensive_play_5e=def_play_5e,
                )
                self._apply_current_personnel_note(result)
                self.state.play_log.append(f"  → {result.description}")
                if hasattr(result, 'debug_log') and result.debug_log:
                    for dl_entry in result.debug_log:
                        self.state.play_log.append(f"    {dl_entry}")
                self._advance_down(result.yards_gained)
                time_used = self._calculate_time(result)
                self._advance_time(time_used)
                return result
        elif strategy == "PLAY_ACTION":
            qb = self.get_qb()
            receiver = self._pick_receiver(play_call)
            receivers = self._get_all_receivers()
            defense = self.get_defense_team()
            # Same logic as DRAW: prefer explicit formation, fall back to AI only in
            # solitaire/sim mode where no defensive call is provided.
            if defense_formation:
                def_form = defense_formation
            elif defensive_play is None:
                def_form = self.ai.call_defense_5e(
                    situation, fac_card,
                    base_defense=defense.base_defense,
                )
            else:
                def_form = DefensiveFormation.FOUR_THREE.value
            
            # Get defensive players for coverage calculations
            defenders = []
            if defense and defense.roster:
                defenders = list(defense.roster.defenders)[:10]
            
            pass_type = "LONG" if play_call.play_type == "LONG_PASS" else "SHORT"
            if qb and receiver:
                result = self.resolver.resolve_play_action(
                    fac_card, self.deck, qb, receiver, receivers,
                    pass_type=pass_type, defense_formation=def_form,
                    defense_coverage=defense.defense_rating,
                    defense_pass_rush=defense.defense_rating,
                    defensive_strategy=defensive_strategy or "NONE",
                    defenders=defenders,
                    defensive_play_5e=def_play_5e,
                    yard_line=self.state.yard_line,
                )
                self._apply_current_personnel_note(result)
                self.state.play_log.append(f"  → {result.description}")
                if hasattr(result, 'debug_log') and result.debug_log:
                    for dl_entry in result.debug_log:
                        self.state.play_log.append(f"    {dl_entry}")
                if result.turnover:
                    self._handle_turnover(result)
                    return result
                if result.is_touchdown or result.result == "TD":
                    if offense_is_ai:
                        self._score_touchdown()
                        kickoff = self._do_kickoff(
                            kicking_team=self.get_offense_team(),
                            receiving_team=self.get_defense_team(),
                        )
                        self._process_kickoff_result(kickoff)
                    else:
                        # Human scored — pause so the player can choose PAT or 2-pt
                        self._score_td_only()
                    return result
                self._advance_down(result.yards_gained)
                time_used = self._calculate_time(result)
                self._advance_time(time_used)
                return result

        if play_call.play_type == "PUNT":
            result = self._execute_punt()
        elif play_call.play_type == "FG":
            result = self._execute_field_goal()
        elif play_call.play_type == "KNEEL":
            result = PlayResult("KNEEL", -1, "KNEEL", description="QB kneels")
            self._advance_down(-1)
        elif play_call.play_type == "SPIKE":
            qb = self.get_qb(player_name) or self.get_qb()
            spike_qb = qb if qb else PlayerCard("QB", "", "QB", 0)
            result = self.resolver.resolve_spike(spike_qb)
        elif play_call.play_type == "RUN":
            result = self._execute_run_5e(fac_card, play_call, defense_formation, player_name,
                                          defensive_play_5e=def_play_5e)
        elif play_call.play_type == "SCREEN":
            result = self._execute_screen_5e(fac_card, defense_formation,
                                             defensive_play_5e=def_play_5e)
        elif play_call.play_type in ("LONG_PASS", "QUICK_PASS"):
            result = self._execute_pass_5e(fac_card, play_call, defense_formation, defensive_strategy, player_name,
                                           defensive_play_5e=def_play_5e, backs_blocking=backs_blocking)
        else:
            result = self._execute_pass_5e(fac_card, play_call, defense_formation, defensive_strategy, player_name,
                                           defensive_play_5e=def_play_5e, backs_blocking=backs_blocking)

        if self._current_play_personnel_note:
            result.personnel_note = self._current_play_personnel_note

        self.state.play_log.append(f"  → {result.description}")

        # ── Append debug log from resolver to play log ────────────────
        if hasattr(result, 'debug_log') and result.debug_log:
            for dl_entry in result.debug_log:
                self.state.play_log.append(f"    {dl_entry}")

        # ── Attach 5E play call info to result ────────────────────────
        result.offensive_play_call = off_call_str
        result.defensive_play_call = def_call_str
        result.defensive_play = def_play_5e.value

        # ── 5E Injury tracking: process Z-card injuries ──────────────
        if result.z_card_event and result.z_card_event.get("type") == "INJURY":
            duration = result.z_card_event.get("injury_duration", 2)
            injured_player = result.rusher or result.receiver or result.passer
            if injured_player:
                # 5E position-injury protection:
                # "If a position has already been hit by an injury, a second
                # injury to that position is ignored."  Find the player's team
                # and position, then check whether that position is currently
                # flagged for that team.
                side_pos = self._find_player_side_and_pos(injured_player)
                if side_pos:
                    p_side, p_pos = side_pos
                    already_flagged = (
                        p_pos in self.state.position_injury_flags.get(p_side, set())
                    )
                else:
                    already_flagged = False
                    p_side = None
                    p_pos = None

                if already_flagged:
                    # Rule: ignore the second injury — the position is protected.
                    self.state.play_log.append(
                        f"  ⚕ Injury to {injured_player} ignored "
                        f"(position {p_pos} already injured this game)."
                    )
                else:
                    # Process the injury normally and set the position flag.
                    self.state.injuries[injured_player] = duration
                    result.injury_player = injured_player
                    result.injury_duration = duration
                    self.state.play_log.append(
                        f"  ⚕ {injured_player} injured! Out for {duration} plays."
                    )
                    if p_side and p_pos:
                        self.state.position_injury_flags[p_side].add(p_pos)
                        self.state._injured_starter_positions[injured_player] = (
                            p_side, p_pos
                        )
                    # Immediately swap injured player out of the starter slot so
                    # the formation grid and personnel views reflect the change.
                    self._immediate_injury_swap(injured_player)
                    # 5E: injury auto-rescinds no-huddle offense
                    self._rescind_no_huddle_offense(reason="injury")

        # ── 5E Z-card penalty resolution ─────────────────────────────
        if result.z_card_event and result.z_card_event.get("type") == "PENALTY":
            pen_detail = result.z_card_event.get("detail", "")
            pen_info = resolve_z_penalty(pen_detail, play_call.play_type)
            if pen_info:
                # Intentional Grounding (#10): only on incomplete passes
                if pen_info.get("only_incomplete") and result.result != "INCOMPLETE":
                    self.state.play_log.append(
                        f"  ⚠ Intentional Grounding ignored (pass was not incomplete)"
                    )
                else:
                    result.penalty = pen_info
                    self.state.play_log.append(
                        f"  ⚠ Z-CARD PENALTY: {pen_info['name']} "
                        f"({pen_info['yards']}y vs {pen_info['team']})"
                    )

        # ── 5E Endurance tracking ────────────────────────────────────
        # Track the *intended* target of the play for endurance purposes.
        # For runs: the ball carrier (result.rusher).
        # For passes: the intended receiver (player_name), not the FAC
        # check-off receiver.  "A play directed at" in the rules means
        # the coach's choice, not the FAC redirect.
        if result.play_type == "PASS" and player_name:
            endurance_target = player_name
        else:
            endurance_target = result.rusher or result.receiver
        self.state.prev_ball_carrier = self.state.last_ball_carrier
        self.state.last_ball_carrier = endurance_target
        # Record usage for endurance 3 (per-drive) and 4 (per-quarter)
        self._record_endurance_usage(endurance_target)
        
        # ── 5E Two-Minute Offense yardage restrictions ───────────────
        if result.play_type in ("RUN", "SCREEN") and not result.turnover:
            result.yards_gained = self._apply_two_minute_yardage(
                result.yards_gained, result.play_type
            )

        # Tick injury counters; clear position-injury flags when players return
        to_remove = []
        for name in list(self.state.injuries):
            self.state.injuries[name] -= 1
            if self.state.injuries[name] <= 0:
                to_remove.append(name)
                self.state.play_log.append(f"  ⚕ {name} returns from injury.")
        for name in to_remove:
            del self.state.injuries[name]
            # Clear the position-injury flag so future injuries at this
            # position are enforced again (rule: protection ends when the
            # originally injured player is eligible to return).
            if name in self.state._injured_starter_positions:
                clr_side, clr_pos = self.state._injured_starter_positions.pop(name)
                self.state.position_injury_flags[clr_side].discard(clr_pos)

        # Track player stats
        self._track_play_stats(result)

        if result.penalty:
            self._apply_penalty(result.penalty)
            return result

        if result.turnover:
            self._handle_turnover(result)
            return result

        if result.is_touchdown or result.result == "TD":
            if offense_is_ai:
                self._score_touchdown()
                kickoff = self._do_kickoff(
                    kicking_team=self.get_offense_team(),
                    receiving_team=self.get_defense_team(),
                )
                self._process_kickoff_result(kickoff)
            else:
                # Human scored — pause so the player can choose PAT or 2-pt
                self._score_td_only()
            return result

        if play_call.play_type == "PUNT":
            return result

        if play_call.play_type == "FG":
            if result.result == "FG_GOOD":
                if self.state.possession == "home":
                    self.state.score.home += 3
                else:
                    self.state.score.away += 3
                self.state.play_log.append(
                    f"Score: Away {self.state.score.away} - Home {self.state.score.home}"
                )
                # Scoring team kicks off to opponent after a field goal
                kickoff = self._do_kickoff(
                    kicking_team=self.get_offense_team(),
                    receiving_team=self.get_defense_team(),
                )
                self._process_kickoff_result(kickoff)
            else:
                # Missed FG: opponent gets ball at spot of kick or 20
                opp_yl = max(20, 100 - self.state.yard_line - 7)
                self._change_possession(opp_yl)
            return result

        if play_call.play_type == "KNEEL":
            self._advance_time(self.TIME_KNEEL)
            return result

        if play_call.play_type == "SPIKE":
            # Retroactively halve the previous play's time (minimum 10 s).
            prev_time = self._last_play_time
            reduced = max(self.TIME_CLOCK_STOP, prev_time // 2)
            refund = max(0, prev_time - reduced)
            if refund > 0:
                self.state.time_remaining += refund
                self.state.play_log.append(
                    f"  ⚡ QB Spike: previous play time halved "
                    f"({prev_time}s → {reduced}s, +{refund}s restored to clock)"
                )
            # Spike is an incomplete pass — advances the down, no yardage change.
            self._advance_down(0)
            if self.state.down > 4:
                self._turnover_on_downs()
            self._last_play_time = self.TIME_CLOCK_STOP
            self._advance_time(self.TIME_CLOCK_STOP)
            return result

        self._advance_down(result.yards_gained)

        if self.state.down > 4:
            self._turnover_on_downs()

        time_used = self._calculate_time(result)
        self._advance_time(time_used)

        return result

    def _execute_run_5e(self, fac_card: FACCard, play_call: PlayCall,
                        defense_formation: Optional[str] = None,
                        player_name: Optional[str] = None,
                        defensive_play_5e: Optional[DefensivePlay] = None) -> PlayResult:
        # Allow QB or WR as ball carrier (end-around, designed QB run)
        if player_name:
            rusher = self.get_rb(player_name)
            if rusher is None or rusher.player_name != player_name:
                # Check if it's a QB or WR being used as ball carrier
                qb = self.get_qb(player_name)
                if qb and qb.player_name == player_name:
                    rusher = qb
                else:
                    wr = self.get_wr(player_name)
                    if wr and wr.player_name == player_name:
                        rusher = wr
        else:
            # AI play: prefer a fresh (non-fatigued) RB when options exist
            rusher = self._pick_fresh_rb()
        if rusher is None:
            rusher = self.get_rb()
        defense = self.get_defense_team()
        def_run_stop = defense.defense_rating
        situation = self.state.to_situation()
        def_formation = defense_formation or self.ai.call_defense_5e(
            situation, fac_card,
            base_defense=self.get_defense_team().base_defense,
        )

        direction = play_call.direction
        # Map legacy directions to 5th-edition
        direction_map = {"LEFT": "IL", "MIDDLE": "IL", "RIGHT": "IR"}
        direction = direction_map.get(direction, direction)

        # Build defenders_by_box mapping for individual tackle ratings
        defenders_by_box = self._build_defenders_by_box(defense)

        # Build offensive_blockers_by_pos mapping for blocking values
        blocking_back_bv = 0
        offense = self.get_offense_team()
        side = self.state.possession
        ol_overrides = self._on_field_ol.get(side, {})
        skill_overrides = self._on_field_offense.get(side, {})
        offensive_blockers_by_pos: Dict[str, PlayerCard] = {}
        if offense and offense.roster:
            # Build name→card lookup for OL override resolution
            ol_name_to_card: Dict[str, PlayerCard] = {
                p.player_name: p for p in offense.roster.offensive_line
            }
            # Apply OL slot overrides first (backup OL subbed into specific slot)
            _ol_slot_map = {"LT": "LT", "LG": "LG", "C": "CN", "RG": "RG", "RT": "RT"}
            for slot, cn_slot in _ol_slot_map.items():
                name = ol_overrides.get(slot)
                if name and name in ol_name_to_card:
                    offensive_blockers_by_pos[cn_slot] = ol_name_to_card[name]
            # Then fill remaining slots from roster order
            for ol in offense.roster.offensive_line:
                pos = getattr(ol, 'position', '').upper()
                if pos == "C":
                    if "CN" not in offensive_blockers_by_pos:
                        offensive_blockers_by_pos["CN"] = ol
                elif pos in ("LG", "RG", "LT", "RT"):
                    if pos not in offensive_blockers_by_pos:
                        offensive_blockers_by_pos[pos] = ol
                elif pos == "OL":
                    # Generic OL: fill first unfilled standard position
                    for slot in ("LT", "LG", "CN", "RG", "RT"):
                        if slot not in offensive_blockers_by_pos:
                            offensive_blockers_by_pos[slot] = ol
                            break
            # Map TEs as LE/RE — check skill overrides first
            all_skill_cards: Dict[str, PlayerCard] = {
                p.player_name: p
                for p in (offense.roster.wrs + offense.roster.tes + offense.roster.rbs)
            }
            for blocker_slot in ("LE", "RE"):
                name = skill_overrides.get(blocker_slot)
                if name and name in all_skill_cards:
                    offensive_blockers_by_pos[blocker_slot] = all_skill_cards[name]
            # Fall back to TE roster order for any unset TE blocker slots
            for te in offense.roster.tes:
                if "LE" not in offensive_blockers_by_pos:
                    offensive_blockers_by_pos["LE"] = te
                elif "RE" not in offensive_blockers_by_pos:
                    offensive_blockers_by_pos["RE"] = te
            # Map BK = blocking back (different RB than the ball carrier)
            if offense.roster.rbs:
                for rb_candidate in offense.roster.rbs:
                    if rb_candidate.player_name != (rusher.player_name if rusher else None):
                        offensive_blockers_by_pos["BK"] = rb_candidate
                        blocking_back_bv = getattr(rb_candidate, 'blocks', 0) or 0
                        break

        if rusher:
            # ── Endurance check: +2 to RN if ball carrier violates ────
            endurance_rn_penalty = 0
            endurance_violation = self._check_endurance_violation(rusher)
            if endurance_violation:
                endurance_rn_penalty = 2
                self._record_personnel_note(
                    f"Endurance violation ({endurance_violation}): "
                    f"+2 RN penalty for {rusher.player_name}."
                )

            # Determine fumble team ratings
            offense = self.get_offense_team()
            off_fumbles_lost_max = getattr(offense, 'fumbles_lost_max', 21) if offense else 21
            off_is_home = (self.state.possession == "home")
            def_fumble_adj_val = getattr(defense, 'def_fumble_adj', 0) if defense else 0

            result = self.resolver.resolve_run_5e(
                fac_card, self.deck, rusher, direction,
                defense_run_stop=def_run_stop,
                defense_formation=def_formation,
                defensive_play_5e=defensive_play_5e,
                extra_rn_modifier=endurance_rn_penalty,
                blocking_back_bv=blocking_back_bv,
                defenders_by_box=defenders_by_box,
                offensive_blockers_by_pos=offensive_blockers_by_pos,
                fumbles_lost_max=off_fumbles_lost_max,
                def_fumble_adj=def_fumble_adj_val,
                is_home=off_is_home,
                yard_line=self.state.yard_line,
            )
            result.defense_formation = def_formation
            # Store box assignments on result for tracking
            if defenders_by_box:
                result.box_assignments = {
                    box: getattr(d, 'player_name', '?')
                    for box, d in defenders_by_box.items()
                }
            return result
        yards = random.choices([-1, 0, 1, 2, 3, 4, 5],
                                weights=[5, 8, 10, 15, 20, 15, 10])[0]
        return PlayResult(
            "RUN", yards, "GAIN",
            description=f"Run for {yards} yards",
            defense_formation=def_formation,
        )

    def _execute_screen_5e(self, fac_card: FACCard,
                           defense_formation: Optional[str] = None,
                           defensive_play_5e: Optional[DefensivePlay] = None) -> PlayResult:
        qb = self.get_qb()
        rb = self.get_rb()
        receivers = self._get_all_receivers()
        situation = self.state.to_situation()
        def_formation = defense_formation or self.ai.call_defense_5e(
            situation, fac_card,
            base_defense=self.get_defense_team().base_defense,
        )

        if qb and rb:
            result = self.resolver.resolve_pass_5e(
                fac_card, self.deck, qb, rb, receivers,
                pass_type="SCREEN",
                defense_formation=def_formation,
                defensive_play_5e=defensive_play_5e,
                yard_line=self.state.yard_line,
            )
            result.defense_formation = def_formation
            return result
        yards = random.randint(2, 8)
        return PlayResult(
            "PASS", yards, "COMPLETE",
            description=f"Screen pass for {yards} yards",
            defense_formation=def_formation,
        )

    def _execute_pass_5e(self, fac_card: FACCard, play_call: PlayCall,
                         defense_formation: Optional[str] = None,
                         defensive_strategy: Optional[str] = None,
                         player_name: Optional[str] = None,
                         defensive_play_5e: Optional[DefensivePlay] = None,
                         backs_blocking: Optional[List[int]] = None) -> PlayResult:
        # player_name on a pass play targets a specific receiver (not QB)
        # Try to find them as a receiver first; fall back to QB selection
        qb = self.get_qb()
        receiver = self._pick_receiver(play_call, player_name)
        if player_name and receiver and receiver.player_name != player_name:
            # If the player wasn't found as a receiver, check if it's a QB
            qb_candidate = self.get_qb(player_name)
            if qb_candidate and qb_candidate.player_name == player_name:
                qb = qb_candidate
        receivers = self._get_all_receivers()
        defense = self.get_defense_team()
        situation = self.state.to_situation()
        def_formation = defense_formation or self.ai.call_defense_5e(
            situation, fac_card,
            base_defense=defense.base_defense,
        )
        
        # Get defensive players for coverage calculations
        defenders = []
        if defense and defense.roster:
            defenders = list(defense.roster.defenders)[:10]

        # Build defenders-by-box mapping for pass defense rating lookups
        defenders_by_box = self._build_defenders_by_box(defense) if defense else {}

        # ── Calculate actual OL pass-blocking sum ─────────────────────
        # Per 5E rules: sum Pass Blocking Values of all five linemen
        offense = self.get_offense_team()
        ol_pass_block_sum = 0
        if offense and offense.roster:
            for ol in offense.roster.offensive_line[:5]:
                ol_pass_block_sum += getattr(ol, 'pass_block_rating', 0)

        # ── Shotgun formation bonuses ──────────────────────────────────
        # House rule: QB in shotgun gains +1 to all completion ranges and
        # +1 to pass blocking (improved pocket / extra depth from center).
        shotgun_completion_bonus = 0
        if getattr(play_call, 'formation', '').upper() == "SHOTGUN":
            shotgun_completion_bonus = 1
            ol_pass_block_sum += 1
            self.state.play_log.append(
                "  SHOTGUN: +1 completion range, +1 pass-block sum"
            )

        # ── Calculate actual DL pass-rush sum ─────────────────────────
        # Per 5E rules: sum Pass Rush Values of all players in Row 1
        # (Defensive Line boxes A-E).  If blitz is in effect, blitzing
        # players have a Pass Rush Value of 2 regardless of printed value.
        dl_pass_rush_sum = 0
        row1_boxes = ('A', 'B', 'C', 'D', 'E')
        blitz_active = (defensive_play_5e == DefensivePlay.BLITZ)
        for box_letter, defender in defenders_by_box.items():
            if box_letter in row1_boxes:
                dl_pass_rush_sum += getattr(defender, 'pass_rush_rating', 0)
        # When blitz is active, blitzing LBs/DBs each add PR=2
        blitzing_names: List[str] = []
        if blitz_active:
            blitz_boxes = set()
            # Per 5E Blitz Summation Chart: PN determines which boxes blitz
            # PN 1-26 → F & J, PN 27-35 → F & J & M, PN 36-48 → F-J
            BLITZ_TWO_PLAYER_MAX = 26   # PN boundary: 2-player blitz
            BLITZ_THREE_PLAYER_MAX = 35  # PN boundary: 3-player blitz
            pn = fac_card.pass_num_int or BLITZ_TWO_PLAYER_MAX
            if pn <= BLITZ_TWO_PLAYER_MAX:
                blitz_boxes = {'F', 'J'}
            elif pn <= BLITZ_THREE_PLAYER_MAX:
                blitz_boxes = {'F', 'J', 'M'}
            else:
                blitz_boxes = {'F', 'G', 'H', 'I', 'J'}
            for box_letter in blitz_boxes:
                if box_letter in defenders_by_box:
                    dl_pass_rush_sum += 2  # Blitzing player PR = 2
                    blitzing_names.append(defenders_by_box[box_letter].player_name)

        # Determine which defender (if any) moved for double coverage.
        # If double coverage is active, the FS (box M) typically leaves
        # their assignment to double-cover the targeted receiver.
        double_coverage_defender_box: Optional[str] = None
        if defensive_strategy in ("DOUBLE_COVERAGE", "ALT_DOUBLE_COVERAGE"):
            # The FS (box M) is the default double-coverage defender
            double_coverage_defender_box = 'M'

        if play_call.play_type == "LONG_PASS":
            pass_type = "LONG"
        elif play_call.play_type == "QUICK_PASS":
            pass_type = "QUICK"
        else:
            pass_type = "SHORT"

        if qb and receiver:
            # ── Endurance check for receiver: -5 to completion range ───
            endurance_comp_penalty = 0
            endurance_violation = self._check_endurance_violation(receiver, for_pass=True)
            if endurance_violation:
                endurance_comp_penalty = -5
                self._record_personnel_note(
                    f"Endurance violation ({endurance_violation}): "
                    f"-5 completion range for targeting {receiver.player_name}."
                )

            result = self.resolver.resolve_pass_5e(
                fac_card, self.deck, qb, receiver, receivers,
                pass_type=pass_type,
                defense_coverage=defense.defense_rating,
                defense_pass_rush=dl_pass_rush_sum,
                offense_pass_block=ol_pass_block_sum,
                defense_formation=def_formation,
                defensive_strategy=defensive_strategy or "NONE",
                defenders=defenders,
                two_minute_offense=self._is_two_minute_offense(),
                completion_modifier=shotgun_completion_bonus,
                defensive_play_5e=defensive_play_5e,
                yard_line=self.state.yard_line,
                defenders_by_box=defenders_by_box,
                backs_blocking=backs_blocking,
                double_coverage_defender_box=double_coverage_defender_box,
                blitzer_names=blitzing_names or None,
                endurance_modifier=endurance_comp_penalty,
            )
            result.defense_formation = def_formation
            return result

        yards = random.choices([0, 0, 5, 8, 12, 18, 25],
                                weights=[20, 15, 15, 15, 12, 10, 5])[0]
        return PlayResult(
            "PASS", yards,
            "COMPLETE" if yards > 0 else "INCOMPLETE",
            description=f"Pass {'complete' if yards > 0 else 'incomplete'} for {yards} yards",
            defense_formation=def_formation,
        )

    def simulate_drive(self) -> DriveResult:
        """Simulate an entire drive using 5E FAC deck."""
        plays = 0
        yards = 0
        drive_log = []
        max_plays = 20

        while plays < max_plays and not self.state.is_over:
            situation = self.state.to_situation()
            fac_card = self.deck.draw()
            play_call = self.ai.call_play_5e(situation, fac_card)

            prev_yl = self.state.yard_line
            prev_possession = self.state.possession

            result = self.execute_play(play_call)
            plays += 1
            yards += abs(result.yards_gained)
            drive_log.append(result.description)

            if result.is_touchdown or result.result == "TD":
                return DriveResult(prev_possession, plays, yards, "TD", 7, drive_log)

            if result.result in ("FG_GOOD", "FG_NO_GOOD"):
                pts = 3 if result.result == "FG_GOOD" else 0
                return DriveResult(prev_possession, plays, yards,
                                   "FG" if pts else "MISSED_FG", pts, drive_log)

            if result.result == "PUNT":
                return DriveResult(prev_possession, plays, yards, "PUNT", 0, drive_log)

            if result.turnover:
                return DriveResult(prev_possession, plays, yards, "TURNOVER", 0, drive_log)

            if self.state.down > 4:
                return DriveResult(prev_possession, plays, yards, "DOWNS", 0, drive_log)

            if self.state.possession != prev_possession:
                return DriveResult(prev_possession, plays, yards, "CHANGE", 0, drive_log)

        return DriveResult(self.state.possession, plays, yards, "END_HALF", 0, drive_log)

    def simulate_game(self) -> GameState:
        """Simulate a complete game."""
        max_drives = 40
        drives = 0

        while not self.state.is_over and drives < max_drives:
            drive = self.simulate_drive()
            self.state.drives.append(drive)
            drives += 1

        if not self.state.is_over:
            self.state.is_over = True

        return self.state

    def format_boxscore(self) -> List[str]:
        """Format a standard player stats boxscore as a list of lines."""
        lines: List[str] = []
        stats = self.state.player_stats
        if not stats:
            return lines

        lines.append("")
        lines.append("=" * 50)
        lines.append("PLAYER STATS")
        lines.append("=" * 50)

        # Collect players with passing stats
        passers = [
            (name, s) for name, s in stats.items()
            if s.get("pass_attempts", 0) > 0
        ]
        if passers:
            lines.append("")
            lines.append("PASSING                  Cmp/Att   Yds  TD INT Sck")
            lines.append("-" * 50)
            for name, s in sorted(passers, key=lambda x: -x[1].get("passing_yards", 0)):
                cmp = s.get("completions", 0)
                att = s.get("pass_attempts", 0)
                yds = s.get("passing_yards", 0)
                td = s.get("passing_tds", 0)
                ints = s.get("interceptions", 0)
                sck = s.get("sacks", 0)
                lines.append(f"  {name:<22s} {cmp:>3d}/{att:<3d} {yds:>5d} {td:>3d} {ints:>3d} {sck:>3d}")

        # Collect players with rushing stats
        rushers = [
            (name, s) for name, s in stats.items()
            if s.get("rushing_attempts", 0) > 0
        ]
        if rushers:
            lines.append("")
            lines.append("RUSHING                    Att   Yds  TD")
            lines.append("-" * 50)
            for name, s in sorted(rushers, key=lambda x: -x[1].get("rushing_yards", 0)):
                att = s.get("rushing_attempts", 0)
                yds = s.get("rushing_yards", 0)
                td = s.get("rushing_tds", 0)
                lines.append(f"  {name:<24s} {att:>3d} {yds:>5d} {td:>3d}")

        # Collect players with receiving stats
        receivers = [
            (name, s) for name, s in stats.items()
            if s.get("receptions", 0) > 0
        ]
        if receivers:
            lines.append("")
            lines.append("RECEIVING                  Rec   Yds  TD")
            lines.append("-" * 50)
            for name, s in sorted(receivers, key=lambda x: -x[1].get("receiving_yards", 0)):
                rec = s.get("receptions", 0)
                yds = s.get("receiving_yards", 0)
                td = s.get("receiving_tds", 0)
                lines.append(f"  {name:<24s} {rec:>3d} {yds:>5d} {td:>3d}")

        # Fumbles lost — tracked at team level
        if any(v > 0 for v in self.state.turnovers.values()):
            lines.append("")
            lines.append("TURNOVERS")
            lines.append("-" * 50)
            for team_key in ("away", "home"):
                team_name = self.state.away_team if team_key == "away" else self.state.home_team
                to = self.state.turnovers.get(team_key, 0)
                if to > 0:
                    lines.append(f"  {team_name}: {to}")

        # Penalties
        if any(v > 0 for v in self.state.penalties.values()):
            lines.append("")
            lines.append("PENALTIES")
            lines.append("-" * 50)
            for team_key in ("away", "home"):
                team_name = self.state.away_team if team_key == "away" else self.state.home_team
                cnt = self.state.penalties.get(team_key, 0)
                yds = self.state.penalty_yards.get(team_key, 0)
                if cnt > 0:
                    lines.append(f"  {team_name}: {cnt} for {yds} yards")

        return lines

    def _time_str(self) -> str:
        mins = self.state.time_remaining // 60
        secs = self.state.time_remaining % 60
        return f"{mins}:{secs:02d}"

    @staticmethod
    def _ordinal_suffix(n: int) -> str:
        return {1: "st", 2: "nd", 3: "rd"}.get(n, "th")

    # ── 5E: Onside kick ─────────────────────────────────────────────

    def execute_onside_kick(self, onside_defense: bool = False) -> PlayResult:
        """Execute an onside kick per 5E rules.

        PN 1-11: kicking team recovers at 50
        PN 12-48: receiving team at 50
        With onside defense: PN 1-7 kicking / 8-48 receiving
        """
        result = self.resolver.resolve_onside_kick(self.deck, onside_defense)
        self.state.play_log.append(result.description)
        if result.result == "ONSIDE_RECOVERED":
            # Kicking team keeps possession at 50
            self.state.yard_line = 50
            self.state.down = 1
            self.state.distance = 10
        else:
            # Receiving team gets ball at 50
            self._change_possession(50)
        return result

    def execute_squib_kick(self) -> PlayResult:
        """Execute a squib kick per 5E rules.

        Normal kickoff + 15 yards to return start + 1 to return Run Number.
        """
        # Current offense is kicking, defense receives
        kicking = self.get_offense_team()
        receiving = self.get_defense_team()
        result = self.resolver.resolve_squib_kick(
            self.deck,
            kickoff_table=kicking.get_kickoff_table(),
            kickoff_returners=receiving.get_kickoff_returners(),
            kickoff_return_table=receiving.get_kickoff_return_table(),
            fumbles_lost_max=getattr(receiving, 'fumbles_lost_max', 21),
            def_fumble_adj=getattr(kicking, 'def_fumble_adj', 0),
            is_home=(receiving == self.home_team),
        )
        self.state.play_log.append(result.description)
        new_yl = max(1, result.yards_gained)
        self._change_possession(new_yl)
        return result

    # ── 5E: Fake punt ────────────────────────────────────────────────

    def execute_fake_punt(self) -> PlayResult:
        """Execute a fake punt per 5E rules (once per game)."""
        punter = self.get_punter()
        if not punter:
            return PlayResult("PUNT", -10, "GAIN",
                              description="Fake punt failed — no punter found")
        result = self.resolver.resolve_fake_punt(self.deck, punter,
                                                yard_line=self.state.yard_line)
        self.state.play_log.append(f"FAKE PUNT: {result.description}")
        if result.turnover:
            self._handle_turnover(result)
        elif result.is_touchdown or result.result == "TD":
            self._score_touchdown()
            kickoff = self._do_kickoff(
                kicking_team=self.get_offense_team(),
                receiving_team=self.get_defense_team(),
            )
            self._process_kickoff_result(kickoff)
        else:
            self._advance_down(result.yards_gained)
            if self.state.down > 4:
                self._turnover_on_downs()
        time_used = self._calculate_time(result)
        self._advance_time(time_used)
        return result

    # ── 5E: Fake field goal ──────────────────────────────────────────

    def execute_fake_field_goal(self) -> PlayResult:
        """Execute a fake field goal per 5E rules (once per game, not in final 2 min)."""
        qb = self.get_qb()
        if not qb:
            return PlayResult("FG", -10, "GAIN",
                              description="Fake FG failed — no holder found")
        minutes_remaining = self.state.time_remaining / 60.0
        result = self.resolver.resolve_fake_field_goal(
            self.deck, qb, minutes_remaining,
            yard_line=self.state.yard_line,
        )
        self.state.play_log.append(f"FAKE FG: {result.description}")
        if result.turnover:
            self._handle_turnover(result)
        elif result.is_touchdown or result.result == "TD":
            self._score_touchdown()
            kickoff = self._do_kickoff(
                kicking_team=self.get_offense_team(),
                receiving_team=self.get_defense_team(),
            )
            self._process_kickoff_result(kickoff)
        else:
            self._advance_down(result.yards_gained)
            if self.state.down > 4:
                self._turnover_on_downs()
        time_used = self._calculate_time(result)
        self._advance_time(time_used)
        return result

    # ── 5E: Coffin corner punt ───────────────────────────────────────

    def execute_coffin_corner_punt(self, deduction: int = 15) -> PlayResult:
        """Execute a coffin corner punt with declared yardage deduction (10-25)."""
        punter = self.get_punter()
        if not punter:
            return PlayResult("PUNT", 30, "PUNT",
                              description="Punt 30 yards (no punter card)")
        result = self.resolver.resolve_coffin_corner_punt(punter, self.deck, deduction)
        self.state.play_log.append(f"COFFIN CORNER: {result.description}")
        punt_net = result.yards_gained
        new_yl = max(1, min(99, 100 - self.state.yard_line - punt_net))
        self._change_possession(new_yl)
        time_used = self._calculate_time(result)
        self._advance_time(time_used)
        return result

    # ── 5E: All-out punt rush ────────────────────────────────────────

    def execute_all_out_punt_rush(self) -> PlayResult:
        """Execute an all-out punt rush (defensive call)."""
        punter = self.get_punter()
        if not punter:
            return PlayResult("PUNT", 30, "PUNT",
                              description="Punt 30 yards (no punter card)")
        result = self.resolver.resolve_all_out_punt_rush(punter, self.deck)
        self.state.play_log.append(f"ALL-OUT RUSH: {result.description}")
        if result.result == "BLOCKED_PUNT":
            # Ball stays at scrimmage - 5 yards behind
            yards_behind = abs(result.yards_gained)
            new_yl = max(1, self.state.yard_line - yards_behind)
            self.state.yard_line = new_yl
            self.state.down = 1
            self.state.distance = 10
            # Defensive team recovers at spot
            self._change_possession(100 - new_yl)
        elif result.penalty and result.is_first_down:
            # Roughing the punter — kicking team keeps ball
            self.state.yard_line = min(99, self.state.yard_line + result.yards_gained)
            self.state.down = 1
            self.state.distance = 10
        else:
            # Hurried punt — normal change of possession
            punt_net = result.yards_gained
            new_yl = max(1, min(99, 100 - self.state.yard_line - punt_net))
            self._change_possession(new_yl)
        time_used = self._calculate_time(result)
        self._advance_time(time_used)
        return result

    # ── 5E: Two-minute offense time adjustment ───────────────────────

    def _is_two_minute_offense(self) -> bool:
        """Check if two-minute offense conditions are met.

        5E rules: 4th quarter, prior to 2:00, trailing by up to 20 points.
        Also active if manually declared.
        """
        return (
            getattr(self, '_two_minute_declared', False)
            or (
                self.state.quarter == 4
                and self.state.time_remaining <= 120
                and self.state.score_diff() < 0
                and self.state.score_diff() >= -20
            )
        )

    def _apply_two_minute_time(self, base_seconds: int) -> int:
        """Halve time expenditure during two-minute offense per 5E rules."""
        if self._is_two_minute_offense():
            return max(1, base_seconds // 2)
        return base_seconds
    
    def _apply_two_minute_yardage(self, yards: int, play_type: str) -> int:
        """Apply two-minute offense yardage restrictions (5E Rule).
        
        Run/screen yardage halved (TD and negative unaffected).
        """
        if not self._is_two_minute_offense():
            return yards
        if play_type in ("RUN", "SCREEN") and yards > 0:
            return max(1, yards // 2)
        return yards

    def activate_big_play_defense(self, team: str) -> bool:
        """Activate Big Play Defense for the specified team this defensive series.

        Returns True if successfully activated, False otherwise.
        """
        if not hasattr(self, '_big_play_defense'):
            self._big_play_defense = {"home": BigPlayDefense(), "away": BigPlayDefense()}

        bpd = self._big_play_defense.get(team)
        if bpd is None:
            return False

        # Check eligibility (needs 9+ wins; default to eligible if wins not set or 0)
        team_obj = self.home_team if team == "home" else self.away_team
        wins = getattr(team_obj, 'wins', 0)
        if wins > 0 and not BigPlayDefense.is_eligible(wins):
            return False

        if bpd._used_this_series:
            return False

        bpd._used_this_series = True
        self.state.play_log.append(f"🛡️ Big Play Defense activated by {team} team!")
        return True

    def declare_two_minute_offense(self):
        """Manually declare two-minute offense mode."""
        self._two_minute_declared = True
        self.state.play_log.append("⏱️ Two-minute offense declared!")

    def rescind_two_minute_offense(self):
        """Voluntarily rescind two-minute offense mode."""
        self._two_minute_declared = False
        self.state.play_log.append("⏱️ Two-minute offense rescinded.")

    # ── No-Huddle Offense ───────────────────────────────────────────────

    def declare_no_huddle_offense(self):
        """Declare no-huddle offense.

        5E rules: May be used at any time.  Halves time for non-clock-stopping
        plays only.  Auto-rescinded when the clock stops, an injury occurs, a
        substitution is made at the end of a play, or possession changes.
        Never in effect on punt or kicking plays.
        """
        self._no_huddle = True
        self.state.play_log.append("🏃 No-huddle offense declared!")

    def _rescind_no_huddle_offense(self, reason: str = ""):
        """Internal helper — clear no-huddle flag and log the reason."""
        if self._no_huddle:
            self._no_huddle = False
            msg = "  🏃 No-huddle offense rescinded"
            if reason:
                msg += f" ({reason})"
            msg += "."
            self.state.play_log.append(msg)

    def rescind_no_huddle_offense(self):
        """Voluntarily rescind no-huddle offense."""
        self._rescind_no_huddle_offense(reason="voluntarily rescinded")
