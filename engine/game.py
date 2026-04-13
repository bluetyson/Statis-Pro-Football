"""Core game state and logic for Statis Pro Football."""
import random
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

from .fast_action_dice import FastActionDice, DiceResult, PlayTendency
from .fac_deck import FACDeck, FACCard
from .player_card import PlayerCard
from .team import Team
from .play_resolver import PlayResolver, PlayResult, BigPlayDefense
from .solitaire import SolitaireAI, GameSituation, PlayCall
from .charts import Charts
from .play_types import (
    DefensivePlay, DefensiveFormation, DefensiveStrategy,
    OffensivePlay, OffensiveStrategy, PlayerInvolved,
    OFFENSIVE_PLAY_NAMES, DEFENSIVE_PLAY_NAMES,
    OFFENSIVE_STRATEGY_NAMES, DEFENSIVE_STRATEGY_NAMES,
    PLAYER_INVOLVED_NAMES, LEGACY_FORMATION_TO_PLAY,
)


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
    """Core game logic for Statis Pro Football.

    Supports two modes:
      * Legacy mode (use_5e=False): Uses FastActionDice (d8×d8) — original system
      * 5th-edition mode (use_5e=True): Uses FACDeck (109-card deck)
    """

    def __init__(self, home_team: Team, away_team: Team,
                 solitaire_home: bool = True, solitaire_away: bool = True,
                 use_5e: bool = False, seed: Optional[int] = None):
        self.home_team = home_team
        self.away_team = away_team
        self.dice = FastActionDice()
        # 5E Solitaire: remove 1 Z card when both teams are AI-controlled
        is_solitaire = solitaire_home and solitaire_away
        self.deck = FACDeck(seed=seed, solitaire=is_solitaire)
        self.use_5e = use_5e
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

        kickoff_result = self.resolver.resolve_kickoff(
            returner=self.get_returner(self.get_offense_team(), "KR")
        )
        start_yard = 25 if kickoff_result.result == "TOUCHBACK" else kickoff_result.yards_gained
        self.state.yard_line = start_yard
        self.state.play_log.append(kickoff_result.description)

    def get_offense_team(self) -> Team:
        return self.home_team if self.state.possession == "home" else self.away_team

    def get_defense_team(self) -> Team:
        return self.away_team if self.state.possession == "home" else self.home_team

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

    def validate_player_availability(self, player_name: str) -> PlayerCard:
        for player in self.get_offense_team().roster.all_players():
            if player.player_name == player_name:
                if self._is_player_unavailable(player):
                    raise ValueError(f"{player_name} is injured and unavailable.")
                return player
        raise ValueError(f"{player_name} is not on the current offense.")

    def get_returner(self, team: Team, kind: str) -> Optional[PlayerCard]:
        return team.get_return_specialist(kind, unavailable_names=set(self.state.injuries))

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
        """Track player stats and game-level penalty/turnover counts."""
        stats = self.state.player_stats
        team = self.state.possession

        # Track penalties
        if result.penalty:
            pen_type = result.penalty.get("type", "")
            is_def = "DEF" in pen_type or result.penalty.get("auto_first", False)
            pen_team = self.state.get_defense_team() if is_def else team
            self.state.penalties[pen_team] = self.state.penalties.get(pen_team, 0) + 1
            self.state.penalty_yards[pen_team] = (
                self.state.penalty_yards.get(pen_team, 0) + result.penalty.get("yards", 0)
            )

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

    def execute_play(self, play_call: Optional[PlayCall] = None,
                     defense_formation: Optional[str] = None,
                     player_name: Optional[str] = None,
                     defensive_strategy: Optional[str] = None,
                     defensive_play: Optional[str] = None,
                     blitz_players: Optional[List[str]] = None) -> PlayResult:
        """Execute a single play.

        Args:
            play_call: Optional human-specified offensive play call.
            defense_formation: Optional human-specified defensive formation.
            player_name: Optional specific player to use for the play.
            defensive_strategy: Optional human-specified defensive strategy (5E).
            defensive_play: Optional defensive play type (PASS_DEFENSE, BLITZ, etc.).
            blitz_players: Optional list of player names to blitz (2-5 LBs/DBs).
        """
        self._current_play_personnel_note = None
        if self.use_5e:
            return self._execute_play_5e(play_call, defense_formation,
                                         player_name=player_name,
                                         defensive_strategy=defensive_strategy,
                                         defensive_play=defensive_play,
                                         blitz_players=blitz_players)
        return self._execute_play_legacy(play_call, defense_formation, player_name=player_name)

    def _execute_play_legacy(self, play_call: Optional[PlayCall] = None,
                             defense_formation: Optional[str] = None,
                             player_name: Optional[str] = None) -> PlayResult:
        """Execute a single play using legacy dice system."""
        dice = self.dice.roll()
        situation = self.state.to_situation()

        if play_call is None:
            play_call = self.ai.call_play(situation, dice)

        self.state.play_log.append(
            f"Q{self.state.quarter} {self._time_str()} | "
            f"{'Home' if self.state.possession == 'home' else 'Away'} ball | "
            f"{self.state.down}{self._ordinal_suffix(self.state.down)} & {self.state.distance} | "
            f"Own {self.state.yard_line}"
        )

        if play_call.play_type == "PUNT":
            result = self._execute_punt()
        elif play_call.play_type == "FG":
            result = self._execute_field_goal()
        elif play_call.play_type == "KNEEL":
            result = PlayResult("KNEEL", -1, "KNEEL", description="QB kneels")
            self._advance_down(-1)
        elif play_call.play_type == "RUN":
            result = self._execute_run(dice, play_call, defense_formation)
        elif play_call.play_type == "SCREEN":
            result = self._execute_screen(dice, defense_formation)
        else:
            result = self._execute_pass(dice, play_call, defense_formation)

        self._apply_current_personnel_note(result)
        self.state.play_log.append(f"  \u2192 {result.description}")

        # Track stats
        self._track_play_stats(result)

        if result.penalty:
            self._apply_penalty(result.penalty)
            return result

        if result.turnover:
            self._handle_turnover(result)
            return result

        if result.is_touchdown or result.result == "TD":
            self._score_touchdown()
            kickoff = self.resolver.resolve_kickoff(
                returner=self.get_returner(self.get_defense_team(), "KR")
            )
            self.state.play_log.append(kickoff.description)
            new_yl = 25 if kickoff.result == "TOUCHBACK" else max(1, kickoff.yards_gained)
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

    def _execute_run(self, dice: DiceResult, play_call: PlayCall,
                     defense_formation: Optional[str] = None) -> PlayResult:
        rb = self.get_rb()
        defense = self.get_defense_team()
        def_run_stop = defense.defense_rating
        # Get defensive formation (human override or AI)
        situation = self.state.to_situation()
        def_formation = defense_formation or self.ai.call_defense(situation, dice)

        if rb:
            return self.resolver.resolve_run(
                dice, rb, play_call.direction, def_run_stop,
                defense_formation=def_formation,
                down=self.state.down, distance=self.state.distance,
                yard_line=self.state.yard_line, quarter=self.state.quarter,
                time_remaining=self.state.time_remaining,
            )
        yards = random.choices([-1, 0, 1, 2, 3, 4, 5],
                                weights=[5, 8, 10, 15, 20, 15, 10])[0]
        return PlayResult("RUN", yards, "GAIN", description=f"Run for {yards} yards")

    def _execute_screen(self, dice: DiceResult,
                        defense_formation: Optional[str] = None) -> PlayResult:
        qb = self.get_qb()
        rb = self.get_rb()
        defense = self.get_defense_team()
        situation = self.state.to_situation()
        def_formation = defense_formation or self.ai.call_defense(situation, dice)
        is_blitz = dice.play_tendency == PlayTendency.BLITZ

        if qb and rb:
            return self.resolver.resolve_pass(
                dice, qb, rb, "SCREEN", defense.defense_rating,
                defense_pass_rush=defense.defense_rating,
                defense_formation=def_formation,
                is_blitz_tendency=is_blitz,
                down=self.state.down, distance=self.state.distance,
                yard_line=self.state.yard_line, quarter=self.state.quarter,
                time_remaining=self.state.time_remaining,
            )
        yards = random.randint(2, 8)
        return PlayResult("PASS", yards, "COMPLETE", description=f"Screen pass for {yards} yards")

    def _execute_pass(self, dice: DiceResult, play_call: PlayCall,
                      defense_formation: Optional[str] = None) -> PlayResult:
        qb = self.get_qb()
        receiver = self._pick_receiver(play_call)
        defense = self.get_defense_team()
        situation = self.state.to_situation()
        def_formation = defense_formation or self.ai.call_defense(situation, dice)
        is_blitz = dice.play_tendency == PlayTendency.BLITZ

        length = "LONG" if play_call.play_type == "LONG_PASS" else "SHORT"

        if qb and receiver:
            return self.resolver.resolve_pass(
                dice, qb, receiver, length, defense.defense_rating,
                defense_pass_rush=defense.defense_rating,
                defense_formation=def_formation,
                is_blitz_tendency=is_blitz,
                down=self.state.down, distance=self.state.distance,
                yard_line=self.state.yard_line, quarter=self.state.quarter,
                time_remaining=self.state.time_remaining,
            )

        yards = random.choices([0, 0, 5, 8, 12, 18, 25],
                                weights=[20, 15, 15, 15, 12, 10, 5])[0]
        return PlayResult(
            "PASS", yards,
            "COMPLETE" if yards > 0 else "INCOMPLETE",
            description=f"Pass {'complete' if yards > 0 else 'incomplete'} for {yards} yards",
        )

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
        punter = self.get_punter()
        punt_dice = self.dice.roll()
        returner = self.get_returner(self.get_defense_team(), "PR")

        if punter:
            result = self.resolver.resolve_punt(punter, dice=punt_dice, returner=returner)
        else:
            dist = random.randint(38, 52)
            result = PlayResult("PUNT", dist - 8, "PUNT",
                                description=f"Punt {dist} yards, returned 8 yards")

        punt_distance = random.randint(38, 52)
        new_yl = max(1, 100 - self.state.yard_line - punt_distance + random.randint(0, 10))
        self._change_possession(new_yl)
        return result

    def _handle_turnover(self, result: PlayResult) -> None:
        if result.turnover_type == "INT":
            new_yl = random.randint(20, 45)
            self._change_possession(new_yl)
        elif result.turnover_type == "FUMBLE":
            new_yl = max(1, 100 - self.state.yard_line)
            self._change_possession(new_yl)

    def _apply_penalty(self, penalty: Dict) -> None:
        ptype = penalty.get("type", "HOLDING_OFF")
        yards = penalty.get("yards", 10)
        auto_first = penalty.get("auto_first", False)
        loss_of_down = penalty.get("loss_of_down", False)

        self.state.play_log.append(f"  \u26a0 PENALTY: {ptype} - {yards} yards")

        off_penalties = {
            "FALSE_START", "ILLEGAL_MOTION", "DELAY_OF_GAME", "INELIGIBLE_RECEIVER",
        }
        if "OFF" in ptype or ptype in off_penalties:
            self.state.yard_line = max(1, self.state.yard_line - yards)
            self.state.distance += yards
        else:
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

        # Track defensive penalty for half-cannot-end rule
        if "DEF" in ptype or ptype in ("ROUGHING_PASSER", "FACE_MASK",
            "PASS_INTERFERENCE_DEF", "ENCROACHMENT", "HOLDING_DEF",
            "ROUGHING_KICKER", "ILLEGAL_CONTACT", "UNNECESSARY_ROUGHNESS"):
            self._last_play_had_defensive_penalty = True
        else:
            self._last_play_had_defensive_penalty = False

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
            else:
                self.state.time_remaining = 900
                self.state.play_log.append(
                    f"End of Q{self.state.quarter - 1}, starting Q{self.state.quarter}"
                )
                if self.state.quarter == 3:
                    self.state.possession = (
                        "home" if self.state.possession == "away" else "away"
                    )
                    kickoff = self.resolver.resolve_kickoff(
                        returner=self.get_returner(self.get_offense_team(), "KR")
                    )
                    self.state.play_log.append(f"Second half kickoff: {kickoff.description}")
                    new_yl = 25 if kickoff.result == "TOUCHBACK" else max(1, kickoff.yards_gained)
                    self.state.yard_line = new_yl
                    self.state.down = 1
                    self.state.distance = 10

    # ── 5th-Edition FAC-card-based play execution ────────────────────

    def _get_all_receivers(self) -> list:
        """Get all WR + TE receivers ordered by receiver letter."""
        team = self.get_offense_team()
        receivers = [
            rec for rec in (list(team.roster.wrs) + list(team.roster.tes))
            if not self._is_player_unavailable(rec)
        ]
        # Assign receiver letters if not already set
        letters = ["A", "B", "C", "D", "E"]
        for i, rec in enumerate(receivers[:5]):
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

        if play_call is None:
            play_call = self.ai.call_play_5e(situation, fac_card)

        # ── 5E Play calling with proper types ────────────────────────
        off_play, off_strategy, player_inv = self.ai.call_offense_play_5e(situation, fac_card)
        def_formation_5e, def_play_5e, def_strategy_5e = self.ai.call_defense_play_5e(
            situation, fac_card
        )
        
        # Use provided defensive_strategy or fall back to AI-called strategy
        if defensive_strategy is None:
            defensive_strategy = def_strategy_5e.value

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
            def_form = defense_formation or self.ai.call_defense_5e(situation, fac_card)
            defense = self.get_defense_team()
            if rusher:
                result = self.resolver.resolve_draw(
                    fac_card, self.deck, rusher, def_form,
                    defense_run_stop=defense.defense_rating,
                    defensive_play=defensive_play,
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
            def_form = defense_formation or self.ai.call_defense_5e(situation, fac_card)
            
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
                )
                self._apply_current_personnel_note(result)
                self.state.play_log.append(f"  → {result.description}")
                if result.turnover:
                    self._handle_turnover(result)
                    return result
                if result.is_touchdown or result.result == "TD":
                    self._score_touchdown()
                    kickoff = self.resolver.resolve_kickoff(
                        returner=self.get_returner(self.get_defense_team(), "KR")
                    )
                    self.state.play_log.append(kickoff.description)
                    new_yl = 25 if kickoff.result == "TOUCHBACK" else max(1, kickoff.yards_gained)
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

        # ── 5E Endurance tracking ────────────────────────────────────
        ball_carrier = result.rusher or result.receiver
        self.state.prev_ball_carrier = self.state.last_ball_carrier
        self.state.last_ball_carrier = ball_carrier
        
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
            kickoff = self.resolver.resolve_kickoff(
                returner=self.get_returner(self.get_defense_team(), "KR")
            )
            self.state.play_log.append(kickoff.description)
            new_yl = 25 if kickoff.result == "TOUCHBACK" else max(1, kickoff.yards_gained)
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

        if rusher:
            result = self.resolver.resolve_run_5e(
                fac_card, self.deck, rusher, direction,
                defense_run_stop=def_run_stop,
                defense_formation=def_formation,
                defensive_play_5e=defensive_play_5e,
            )
            result.defense_formation = def_formation
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
                         defensive_play_5e: Optional[DefensivePlay] = None) -> PlayResult:
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

        if play_call.play_type == "LONG_PASS":
            pass_type = "LONG"
        elif play_call.play_type == "QUICK_PASS":
            pass_type = "QUICK"
        else:
            pass_type = "SHORT"

        if qb and receiver:
            result = self.resolver.resolve_pass_5e(
                fac_card, self.deck, qb, receiver, receivers,
                pass_type=pass_type,
                defense_coverage=defense.defense_rating,
                defense_pass_rush=defense.defense_rating,
                defense_formation=def_formation,
                defensive_strategy=defensive_strategy or "NONE",
                defenders=defenders,
                two_minute_offense=self._is_two_minute_offense(),
                defensive_play_5e=defensive_play_5e,
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
        """Simulate an entire drive."""
        plays = 0
        yards = 0
        drive_log = []
        max_plays = 20

        while plays < max_plays and not self.state.is_over:
            situation = self.state.to_situation()
            dice = self.dice.roll()
            play_call = self.ai.call_play(situation, dice)

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
        result = self.resolver.resolve_squib_kick(self.deck)
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
        result = self.resolver.resolve_fake_punt(self.deck, punter)
        self.state.play_log.append(f"FAKE PUNT: {result.description}")
        if result.turnover:
            self._handle_turnover(result)
        elif result.is_touchdown or result.result == "TD":
            self._score_touchdown()
            kickoff = self.resolver.resolve_kickoff(
                returner=self.get_returner(self.get_defense_team(), "KR")
            )
            self.state.play_log.append(kickoff.description)
            new_yl = 25 if kickoff.result == "TOUCHBACK" else max(1, kickoff.yards_gained)
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
            self.deck, qb, minutes_remaining
        )
        self.state.play_log.append(f"FAKE FG: {result.description}")
        if result.turnover:
            self._handle_turnover(result)
        elif result.is_touchdown or result.result == "TD":
            self._score_touchdown()
            kickoff = self.resolver.resolve_kickoff(
                returner=self.get_returner(self.get_defense_team(), "KR")
            )
            self.state.play_log.append(kickoff.description)
            new_yl = 25 if kickoff.result == "TOUCHBACK" else max(1, kickoff.yards_gained)
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
