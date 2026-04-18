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
        # 5E: Big play defense state per team
        self._big_play_defense = {"home": BigPlayDefense(), "away": BigPlayDefense()}
        self._current_play_personnel_note: Optional[str] = None

        self.state.possession = random.choice(["home", "away"])
        self.state.play_log.append(f"Coin flip: {self.state.possession} team receives")

        kickoff_result = self._do_kickoff(
            kicking_team=self.get_defense_team(),
            receiving_team=self.get_offense_team(),
        )
        self._log_kickoff(kickoff_result)

        if kickoff_result.is_touchdown or kickoff_result.result == "TD":
            # Kickoff return TD: score, attempt XP, then kick off again
            self._score_touchdown()
            followup_kickoff = self._do_kickoff(
                kicking_team=self.get_offense_team(),
                receiving_team=self.get_defense_team(),
            )
            self._log_kickoff(followup_kickoff)
            new_yl = self._kickoff_yard_line(followup_kickoff)
            self._change_possession(new_yl)
        else:
            start_yard = self._kickoff_yard_line(kickoff_result)
            self.state.yard_line = start_yard

    def get_offense_team(self) -> Team:
        return self.home_team if self.state.possession == "home" else self.away_team

    def get_defense_team(self) -> Team:
        return self.away_team if self.state.possession == "home" else self.home_team

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

    def _is_player_unavailable(self, player: Optional[PlayerCard]) -> bool:
        return bool(player and self.state.injuries.get(player.player_name, 0) > 0)

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
        """Immediately swap an injured player out of the starter slot.

        When a player is injured mid-play, the formation grid must reflect
        the replacement at once — not on the next play.  Walk every position
        list on *both* teams and, if the injured player sits in the starter
        slot (index 0), promote the first healthy backup.
        """
        for team in (self.home_team, self.away_team):
            pos_lists = [
                (team.roster.qbs, "QB"),
                (team.roster.rbs, "RB"),
                (team.roster.wrs, "WR"),
                (team.roster.tes, "TE"),
                (team.roster.kickers, "K"),
                (team.roster.punters, "P"),
            ]
            for players, pos in pos_lists:
                if not players or players[0].player_name != injured_player_name:
                    continue
                # The injured player is currently in the starter slot — swap.
                self._resolve_position_player(players, pos)
                return  # each player belongs to one list only

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

    def _kickoff_yard_line(self, kickoff: PlayResult) -> int:
        """Extract the starting yard line from a kickoff result."""
        if kickoff.result == "TOUCHBACK":
            return max(1, kickoff.yards_gained) if kickoff.yards_gained else 20
        if kickoff.result == "OOB":
            return 40
        return max(1, kickoff.yards_gained)

    def get_qb(self, player_name: Optional[str] = None) -> Optional[PlayerCard]:
        return self._resolve_position_player(self.get_offense_team().roster.qbs, "QB", player_name)

    def get_rb(self, player_name: Optional[str] = None) -> Optional[PlayerCard]:
        return self._resolve_position_player(self.get_offense_team().roster.rbs, "RB", player_name)

    def get_wr(self, player_name: Optional[str] = None) -> Optional[PlayerCard]:
        return self._resolve_position_player(self.get_offense_team().roster.wrs, "WR", player_name)

    def get_te(self) -> Optional[PlayerCard]:
        return self._resolve_position_player(self.get_offense_team().roster.tes, "TE")

    def get_kicker(self) -> Optional[PlayerCard]:
        return self._resolve_position_player(self.get_offense_team().roster.kickers, "K")

    def get_punter(self) -> Optional[PlayerCard]:
        return self._resolve_position_player(self.get_offense_team().roster.punters, "P")

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
                     blitz_players: Optional[List[str]] = None) -> PlayResult:
        """Execute a single play using 5th-edition rules.

        Args:
            play_call: Optional human-specified offensive play call.
            defense_formation: Optional human-specified defensive formation.
            player_name: Optional specific player to use for the play.
            defensive_strategy: Optional human-specified defensive strategy (5E).
            defensive_play: Optional defensive play type (PASS_DEFENSE, BLITZ, etc.).
            blitz_players: Optional list of player names to blitz (2-5 LBs/DBs).
        """
        self._current_play_personnel_note = None
        return self._execute_play_5e(play_call, defense_formation,
                                     player_name=player_name,
                                     defensive_strategy=defensive_strategy,
                                     defensive_play=defensive_play,
                                     blitz_players=blitz_players)

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
                new_yl = max(1, self.state.yard_line - 5)
                self._change_possession(new_yl)
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
            new_yl = max(1, self.state.yard_line - 5)
            self._change_possession(new_yl)
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

        if is_fumble and fumble_lost:
            result.turnover = True
            result.turnover_type = "FUMBLE"

        new_yl = max(1, 100 - self.state.yard_line - punt_distance + return_yards)
        self._change_possession(new_yl)
        return result

    def _handle_turnover(self, result: PlayResult) -> None:
        if result.turnover_type == "INT":
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
        """
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
        else:
            time = self.TIME_STANDARD_PLAY
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
                    new_yl = self._kickoff_yard_line(kickoff)
                    self.state.yard_line = new_yl
                    self.state.down = 1
                    self.state.distance = 10

    # ── 5th-Edition FAC-card-based play execution ────────────────────

    def _get_all_receivers(self) -> list:
        """Get on-field receivers in formation position order.

        5E formation has 5 receiver-eligible positions in this order:
          [0] FL  (Flanker)   — typically WR2
          [1] LE  (Left End)  — typically WR1 (primary receiver)
          [2] RE  (Right End) — typically TE1
          [3] BK1 (Back 1)   — RB1
          [4] BK2 (Back 2)   — RB2

        The FAC card targeting system (FL→0, LE→1, RE→2, BK1→3, BK2→4)
        relies on this exact ordering so the correct on-field player is
        targeted for each pass.
        """
        team = self.get_offense_team()
        wrs = [w for w in team.roster.wrs if not self._is_player_unavailable(w)]
        tes = [t for t in team.roster.tes if not self._is_player_unavailable(t)]
        rbs = [r for r in team.roster.rbs if not self._is_player_unavailable(r)]

        # Build formation: FL, LE, RE, BK1, BK2
        # LE = primary WR (WR1), FL = secondary WR (WR2), RE = primary TE
        # BK1 = RB1, BK2 = RB2
        if len(wrs) >= 2:
            fl = wrs[1]  # WR2 as flanker
            le = wrs[0]  # WR1 at left end
        elif len(wrs) == 1:
            fl = wrs[0]  # Only WR → flanker
            le = tes[0] if tes else None  # TE fills left end
        else:
            # No WRs: TEs fill LE first (primary), then FL
            le = tes[0] if len(tes) > 0 else None
            fl = tes[1] if len(tes) > 1 else None

        # RE = first TE not already used at LE
        re_candidates = [t for t in tes if t is not le and t is not fl]
        re = re_candidates[0] if re_candidates else None

        bk1 = rbs[0] if len(rbs) > 0 else None
        bk2 = rbs[1] if len(rbs) > 1 else None

        receivers = [r for r in [fl, le, re, bk1, bk2] if r is not None]

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
                        blitz_players: Optional[List[str]] = None) -> PlayResult:
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
                situation, fac_card
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
        self.state.play_log.append(f"  OFFENSE: {off_call_str}")
        self.state.play_log.append(f"  DEFENSE: {def_call_str}")
        if blitz_players:
            self.state.play_log.append(f"  BLITZ PLAYERS: {', '.join(blitz_players)}")

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
        #   - DRAW is a run strategy; discard it on pass/special plays.
        _PASS_TYPES = {"SHORT_PASS", "LONG_PASS", "QUICK_PASS", "SCREEN"}
        _RUN_TYPES  = {"RUN"}
        if strategy == "PLAY_ACTION" and play_call.play_type not in _PASS_TYPES:
            strategy = None
            play_call.strategy = None
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
                return result
        elif strategy == "SNEAK":
            qb = self.get_qb(player_name)
            if qb:
                result = self.resolver.resolve_sneak(qb, self.deck)
                self._apply_current_personnel_note(result)
                self.state.play_log.append(f"  → {result.description}")
                self._advance_down(result.yards_gained)
                self._advance_time(self.TIME_STANDARD_PLAY)
                return result
        elif strategy == "DRAW":
            # Draw play can use any back (RB or QB) as ball carrier
            rusher = self.get_rb(player_name)
            if rusher is None:
                rusher = self.get_qb(player_name)
            # Use the human-provided defense formation when available; only fall back to AI
            # when no defensive call was provided at all (solitaire/sim mode).
            if defense_formation:
                def_form = defense_formation
            elif defensive_play is None:
                def_form = self.ai.call_defense_5e(situation, fac_card)
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
                def_form = self.ai.call_defense_5e(situation, fac_card)
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
                if result.turnover:
                    self._handle_turnover(result)
                    return result
                if result.is_touchdown or result.result == "TD":
                    self._score_touchdown()
                    kickoff = self._do_kickoff(
                        kicking_team=self.get_offense_team(),
                        receiving_team=self.get_defense_team(),
                    )
                    self._log_kickoff(kickoff)
                    new_yl = self._kickoff_yard_line(kickoff)
                    self._change_possession(new_yl)
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
        elif play_call.play_type == "RUN":
            result = self._execute_run_5e(fac_card, play_call, defense_formation, player_name,
                                          defensive_play_5e=def_play_5e)
        elif play_call.play_type == "SCREEN":
            result = self._execute_screen_5e(fac_card, defense_formation,
                                             defensive_play_5e=def_play_5e)
        elif play_call.play_type in ("LONG_PASS", "QUICK_PASS"):
            result = self._execute_pass_5e(fac_card, play_call, defense_formation, defensive_strategy, player_name,
                                           defensive_play_5e=def_play_5e)
        else:
            result = self._execute_pass_5e(fac_card, play_call, defense_formation, defensive_strategy, player_name,
                                           defensive_play_5e=def_play_5e)

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
                self.state.injuries[injured_player] = duration
                result.injury_player = injured_player
                result.injury_duration = duration
                self.state.play_log.append(
                    f"  ⚕ {injured_player} injured! Out for {duration} plays."
                )
                # Immediately swap injured player out of the starter slot so
                # the formation grid and personnel views reflect the change.
                self._immediate_injury_swap(injured_player)

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

        # Tick injury counters
        to_remove = []
        for name in list(self.state.injuries):
            self.state.injuries[name] -= 1
            if self.state.injuries[name] <= 0:
                to_remove.append(name)
                self.state.play_log.append(f"  ⚕ {name} returns from injury.")
        for name in to_remove:
            del self.state.injuries[name]

        # Track player stats
        self._track_play_stats(result)

        if result.penalty:
            self._apply_penalty(result.penalty)
            return result

        if result.turnover:
            self._handle_turnover(result)
            return result

        if result.is_touchdown or result.result == "TD":
            self._score_touchdown()
            kickoff = self._do_kickoff(
                kicking_team=self.get_offense_team(),
                receiving_team=self.get_defense_team(),
            )
            self._log_kickoff(kickoff)
            new_yl = self._kickoff_yard_line(kickoff)
            self._change_possession(new_yl)
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
                self._log_kickoff(kickoff)
                new_yl = self._kickoff_yard_line(kickoff)
                self._change_possession(new_yl)
            else:
                # Missed FG: opponent gets ball at spot of kick or 20
                opp_yl = max(20, 100 - self.state.yard_line - 7)
                self._change_possession(opp_yl)
            return result

        if play_call.play_type == "KNEEL":
            self._advance_time(self.TIME_KNEEL)
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
        rusher = self.get_rb(player_name)
        if player_name and (rusher is None or rusher.player_name != player_name):
            # Check if it's a QB or WR being used as ball carrier
            qb = self.get_qb(player_name)
            if qb and qb.player_name == player_name:
                rusher = qb
            else:
                wr = self.get_wr(player_name)
                if wr and wr.player_name == player_name:
                    rusher = wr
        if rusher is None:
            rusher = self.get_rb()
        defense = self.get_defense_team()
        def_run_stop = defense.defense_rating
        situation = self.state.to_situation()
        def_formation = defense_formation or self.ai.call_defense_5e(situation, fac_card)

        direction = play_call.direction
        # Map legacy directions to 5th-edition
        direction_map = {"LEFT": "IL", "MIDDLE": "IL", "RIGHT": "IR"}
        direction = direction_map.get(direction, direction)

        # Build defenders_by_box mapping for individual tackle ratings
        defenders_by_box = self._build_defenders_by_box(defense)

        # Build offensive_blockers_by_pos mapping for blocking values
        blocking_back_bv = 0
        offense = self.get_offense_team()
        offensive_blockers_by_pos: Dict[str, PlayerCard] = {}
        if offense and offense.roster:
            # Map OL by position: LT, LG, C→CN, RG, RT
            for ol in offense.roster.offensive_line:
                pos = getattr(ol, 'position', '').upper()
                if pos == "C":
                    offensive_blockers_by_pos["CN"] = ol
                elif pos in ("LG", "RG", "LT", "RT"):
                    offensive_blockers_by_pos[pos] = ol
                elif pos == "OL":
                    # Generic OL: fill first unfilled standard position
                    for slot in ("LT", "LG", "CN", "RG", "RT"):
                        if slot not in offensive_blockers_by_pos:
                            offensive_blockers_by_pos[slot] = ol
                            break
            # Map TEs as LE/RE
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
        def_formation = defense_formation or self.ai.call_defense_5e(situation, fac_card)

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
        def_formation = defense_formation or self.ai.call_defense_5e(situation, fac_card)
        
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
            self._log_kickoff(kickoff)
            new_yl = self._kickoff_yard_line(kickoff)
            self._change_possession(new_yl)
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
            self._log_kickoff(kickoff)
            new_yl = self._kickoff_yard_line(kickoff)
            self._change_possession(new_yl)
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
