"""Core game state and logic for Statis Pro Football."""
import random
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

from .fast_action_dice import FastActionDice, DiceResult
from .player_card import PlayerCard
from .team import Team
from .play_resolver import PlayResolver, PlayResult
from .solitaire import SolitaireAI, GameSituation, PlayCall
from .charts import Charts


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
    """Core game logic for Statis Pro Football."""

    def __init__(self, home_team: Team, away_team: Team,
                 solitaire_home: bool = True, solitaire_away: bool = True):
        self.home_team = home_team
        self.away_team = away_team
        self.dice = FastActionDice()
        self.resolver = PlayResolver()
        self.ai = SolitaireAI()
        self.solitaire_home = solitaire_home
        self.solitaire_away = solitaire_away

        self.state = GameState(
            home_team=home_team.abbreviation,
            away_team=away_team.abbreviation,
        )

        self.state.possession = random.choice(["home", "away"])
        self.state.play_log.append(f"Coin flip: {self.state.possession} team receives")

        kickoff_result = self.resolver.resolve_kickoff()
        start_yard = 25 if kickoff_result.result == "TOUCHBACK" else kickoff_result.yards_gained
        self.state.yard_line = start_yard
        self.state.play_log.append(kickoff_result.description)

    def get_offense_team(self) -> Team:
        return self.home_team if self.state.possession == "home" else self.away_team

    def get_defense_team(self) -> Team:
        return self.away_team if self.state.possession == "home" else self.home_team

    def get_qb(self) -> Optional[PlayerCard]:
        return self.get_offense_team().roster.get_starter("QB")

    def get_rb(self) -> Optional[PlayerCard]:
        return self.get_offense_team().roster.get_starter("RB")

    def get_wr(self) -> Optional[PlayerCard]:
        wrs = self.get_offense_team().roster.wrs
        if not wrs:
            return None
        return random.choice(wrs[:3]) if len(wrs) >= 3 else wrs[0]

    def get_te(self) -> Optional[PlayerCard]:
        return self.get_offense_team().roster.get_starter("TE")

    def get_kicker(self) -> Optional[PlayerCard]:
        return self.get_offense_team().roster.get_starter("K")

    def get_punter(self) -> Optional[PlayerCard]:
        return self.get_offense_team().roster.get_starter("P")

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

    def execute_play(self, play_call: Optional[PlayCall] = None) -> PlayResult:
        """Execute a single play."""
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
            result = self._execute_run(dice, play_call)
        elif play_call.play_type == "SCREEN":
            result = self._execute_screen(dice)
        else:
            result = self._execute_pass(dice, play_call)

        self.state.play_log.append(f"  \u2192 {result.description}")

        if result.penalty:
            self._apply_penalty(result.penalty)
            return result

        if result.turnover:
            self._handle_turnover(result)
            return result

        if result.is_touchdown or result.result == "TD":
            self._score_touchdown()
            kickoff = self.resolver.resolve_kickoff()
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
            self._advance_time(40)
            return result

        self._advance_down(result.yards_gained)

        if self.state.down > 4:
            self._turnover_on_downs()

        time_used = self._calculate_time(result)
        self._advance_time(time_used)

        return result

    def _execute_run(self, dice: DiceResult, play_call: PlayCall) -> PlayResult:
        rb = self.get_rb()
        defense = self.get_defense_team()
        def_run_stop = defense.defense_rating

        if rb:
            return self.resolver.resolve_run(dice, rb, play_call.direction, def_run_stop)
        yards = random.choices([-1, 0, 1, 2, 3, 4, 5],
                                weights=[5, 8, 10, 15, 20, 15, 10])[0]
        return PlayResult("RUN", yards, "GAIN", description=f"Run for {yards} yards")

    def _execute_screen(self, dice: DiceResult) -> PlayResult:
        qb = self.get_qb()
        rb = self.get_rb()
        defense = self.get_defense_team()

        if qb and rb:
            return self.resolver.resolve_pass(dice, qb, rb, "SCREEN", defense.defense_rating)
        yards = random.randint(2, 8)
        return PlayResult("PASS", yards, "COMPLETE", description=f"Screen pass for {yards} yards")

    def _execute_pass(self, dice: DiceResult, play_call: PlayCall) -> PlayResult:
        qb = self.get_qb()
        receiver = self._pick_receiver(play_call)
        defense = self.get_defense_team()

        length = "LONG" if play_call.play_type == "LONG_PASS" else "SHORT"

        if qb and receiver:
            return self.resolver.resolve_pass(dice, qb, receiver, length, defense.defense_rating)

        yards = random.choices([0, 0, 5, 8, 12, 18, 25],
                                weights=[20, 15, 15, 15, 12, 10, 5])[0]
        return PlayResult(
            "PASS", yards,
            "COMPLETE" if yards > 0 else "INCOMPLETE",
            description=f"Pass {'complete' if yards > 0 else 'incomplete'} for {yards} yards",
        )

    def _pick_receiver(self, play_call: PlayCall) -> Optional[PlayerCard]:
        team = self.get_offense_team()

        if "DEEP" in play_call.direction:
            receivers = team.roster.wrs
            return random.choice(receivers) if receivers else None

        options = team.roster.wrs + team.roster.tes
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

        if punter:
            result = self.resolver.resolve_punt(punter)
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

    def _calculate_time(self, result: PlayResult) -> int:
        if result.play_type == "RUN":
            return random.randint(25, 45)
        elif result.result == "INCOMPLETE":
            return random.randint(5, 10)
        elif result.play_type == "PASS":
            return random.randint(20, 40)
        return 30

    def _advance_time(self, seconds: int) -> None:
        self.state.time_remaining -= seconds

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
                    kickoff = self.resolver.resolve_kickoff()
                    self.state.play_log.append(f"Second half kickoff: {kickoff.description}")
                    new_yl = 25 if kickoff.result == "TOUCHBACK" else max(1, kickoff.yards_gained)
                    self.state.yard_line = new_yl
                    self.state.down = 1
                    self.state.distance = 10

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
