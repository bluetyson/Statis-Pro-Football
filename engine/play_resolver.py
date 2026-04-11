"""Play resolution engine for Statis Pro Football."""
import random
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from .player_card import PlayerCard
from .fast_action_dice import DiceResult
from .charts import Charts


@dataclass
class PlayResult:
    """Result of a resolved play."""
    play_type: str
    yards_gained: int
    result: str  # GAIN, INCOMPLETE, INT, FUMBLE, SACK, TD, etc.
    is_touchdown: bool = False
    is_first_down: bool = False
    turnover: bool = False
    turnover_type: Optional[str] = None
    penalty: Optional[Dict[str, Any]] = None
    description: str = ""

    passer: Optional[str] = None
    rusher: Optional[str] = None
    receiver: Optional[str] = None


class PlayResolver:
    """Resolves plays by consulting player cards."""

    def __init__(self):
        self.charts = Charts()

    def resolve_run(self, dice: DiceResult, rusher: PlayerCard,
                    play_direction: str = "MIDDLE",
                    defense_run_stop: int = 50) -> PlayResult:
        slot = str(dice.two_digit)

        if play_direction in ("LEFT", "MIDDLE"):
            column = rusher.inside_run
        else:
            column = rusher.outside_run

        if not column:
            yards = random.choices([-2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8],
                                   weights=[2, 3, 5, 8, 10, 12, 12, 10, 8, 5, 3])[0]
            result_type = "GAIN"
            is_td = random.random() < 0.03
        else:
            play_data = column.get(slot, {"result": "GAIN", "yards": 2, "td": False})
            result_type = play_data.get("result", "GAIN")
            yards = play_data.get("yards", 0)
            is_td = play_data.get("td", False)

        def_modifier = (defense_run_stop - 50) / 100.0
        if result_type == "GAIN":
            yards = max(-5, int(yards - def_modifier * 2))

        if result_type == "FUMBLE":
            recovery = Charts.roll_fumble_recovery()
            fumble_yards, fumble_td = Charts.roll_fumble_return()
            is_turnover = recovery == "DEFENSE"
            if is_turnover and fumble_td:
                return PlayResult(
                    play_type="RUN", yards_gained=-fumble_yards,
                    result="FUMBLE_TD", is_touchdown=False,
                    turnover=True, turnover_type="FUMBLE",
                    description=f"{rusher.player_name} fumbles! Returned for TD!",
                    rusher=rusher.player_name,
                )
            return PlayResult(
                play_type="RUN", yards_gained=yards,
                result="FUMBLE", turnover=is_turnover,
                turnover_type="FUMBLE" if is_turnover else None,
                description=(
                    f"{rusher.player_name} fumbles! "
                    f"{'Defense recovers!' if is_turnover else 'Offense recovers.'}"
                ),
                rusher=rusher.player_name,
            )

        penalty_info = None
        if dice.penalty_check:
            penalty_info = Charts.roll_penalty_chart()

        desc = f"{rusher.player_name} runs {play_direction.lower()}"
        if is_td:
            desc += " for a TOUCHDOWN!"
        elif result_type == "GAIN":
            desc += f" for {yards} yard{'s' if yards != 1 else ''}"

        return PlayResult(
            play_type="RUN",
            yards_gained=yards,
            result="TD" if is_td else result_type,
            is_touchdown=is_td,
            penalty=penalty_info,
            description=desc,
            rusher=rusher.player_name,
        )

    def resolve_pass(self, dice: DiceResult, qb: PlayerCard,
                     receiver: PlayerCard, pass_length: str = "SHORT",
                     defense_coverage: int = 50) -> PlayResult:
        slot = str(dice.two_digit)

        if pass_length == "SHORT":
            qb_column = qb.short_pass
            rec_column = receiver.short_reception
        elif pass_length == "SCREEN":
            qb_column = qb.screen_pass
            rec_column = receiver.short_reception
        else:
            qb_column = qb.long_pass
            rec_column = receiver.long_reception

        if not qb_column:
            comp = random.random() < 0.62
            yards = random.randint(5, 15) if comp else 0
            result_type = "COMPLETE" if comp else "INCOMPLETE"
            is_td = comp and random.random() < 0.05
        else:
            qb_data = qb_column.get(slot, {"result": "INCOMPLETE", "yards": 0, "td": False})
            result_type = qb_data.get("result", "INCOMPLETE")
            yards = qb_data.get("yards", 0)
            is_td = qb_data.get("td", False)

        if result_type == "COMPLETE" and rec_column:
            rec_data = rec_column.get(slot, {"result": "CATCH", "yards": yards, "td": is_td})
            if rec_data.get("result") == "INCOMPLETE":
                result_type = "INCOMPLETE"
                yards = 0
                is_td = False

        def_modifier = (defense_coverage - 50) / 200.0
        if result_type == "COMPLETE":
            yards = max(0, int(yards * (1 - def_modifier)))

        if result_type == "INT":
            int_yards, int_td = Charts.roll_int_return()
            return PlayResult(
                play_type="PASS", yards_gained=0,
                result="INT", turnover=True, turnover_type="INT",
                description=(
                    f"{qb.player_name} pass intercepted!"
                    f"{'Returned for TD!' if int_td else f' Returned {int_yards} yards.'}"
                ),
                passer=qb.player_name, receiver=receiver.player_name,
            )

        if result_type == "SACK":
            return PlayResult(
                play_type="PASS", yards_gained=yards,
                result="SACK",
                description=f"{qb.player_name} is sacked for {abs(yards)} yard loss!",
                passer=qb.player_name,
            )

        penalty_info = None
        if dice.penalty_check:
            penalty_info = Charts.roll_penalty_chart()

        if result_type == "COMPLETE":
            desc = f"{qb.player_name} completes to {receiver.player_name}"
            if is_td:
                desc += " for a TOUCHDOWN!"
            else:
                desc += f" for {yards} yard{'s' if yards != 1 else ''}"
        else:
            desc = f"{qb.player_name} pass intended for {receiver.player_name} - INCOMPLETE"

        return PlayResult(
            play_type="PASS",
            yards_gained=yards,
            result="TD" if is_td else result_type,
            is_touchdown=is_td,
            penalty=penalty_info,
            description=desc,
            passer=qb.player_name,
            receiver=receiver.player_name,
        )

    def resolve_field_goal(self, distance: int, kicker: PlayerCard) -> PlayResult:
        fg_chart = kicker.fg_chart

        if distance < 20:
            rate = fg_chart.get("0-19", 0.99)
        elif distance < 30:
            rate = fg_chart.get("20-29", 0.95)
        elif distance < 40:
            rate = fg_chart.get("30-39", 0.88)
        elif distance < 50:
            rate = fg_chart.get("40-49", 0.78)
        elif distance < 60:
            rate = fg_chart.get("50-59", 0.62)
        else:
            rate = fg_chart.get("60+", 0.35)

        made = random.random() < rate
        return PlayResult(
            play_type="FG",
            yards_gained=0,
            result="FG_GOOD" if made else "FG_NO_GOOD",
            description=f"{kicker.player_name} {'makes' if made else 'misses'} {distance}-yard field goal",
        )

    def resolve_punt(self, punter: PlayerCard) -> PlayResult:
        avg = punter.avg_distance
        variance = random.gauss(0, 5)
        distance = max(20, int(avg + variance))

        inside_20 = random.random() < punter.inside_20_rate
        return_yards = Charts.roll_punt_return()

        desc = f"{punter.player_name} punts {distance} yards"
        if inside_20:
            desc += ", downed inside the 20"
            return_yards = 0

        return PlayResult(
            play_type="PUNT",
            yards_gained=distance - return_yards,
            result="PUNT",
            description=desc,
        )

    def resolve_xp(self, kicker: PlayerCard) -> PlayResult:
        made = random.random() < kicker.xp_rate
        return PlayResult(
            play_type="XP",
            yards_gained=0,
            result="XP_GOOD" if made else "XP_NO_GOOD",
            description=f"Extra point {'good' if made else 'no good'}!",
        )

    def resolve_two_point(self, dice: DiceResult, qb: PlayerCard,
                          receiver: PlayerCard) -> PlayResult:
        success = random.random() < 0.48
        return PlayResult(
            play_type="2PT",
            yards_gained=0,
            result="2PT_GOOD" if success else "2PT_NO_GOOD",
            description=f"2-point conversion {'successful!' if success else 'fails.'}",
        )

    def resolve_kickoff(self) -> PlayResult:
        if Charts.is_kickoff_touchback():
            return PlayResult(
                play_type="KICKOFF",
                yards_gained=0,
                result="TOUCHBACK",
                description="Kickoff - touchback, ball at 25-yard line",
            )
        return_yards = Charts.roll_kick_return()
        return PlayResult(
            play_type="KICKOFF",
            yards_gained=return_yards,
            result="RETURN",
            description=f"Kickoff returned {return_yards} yards",
        )
