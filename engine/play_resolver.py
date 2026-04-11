"""Play resolution engine for Statis Pro Football.

Implements the two-stage FAC resolution system:
  Pass plays:  PN → QB card → result ; if COMPLETE → RN → Receiver card → yards
  Run plays:   RN → RB card → result (with OOB support)
  Punt plays:  RN → Punter card column (slot-based)

Defence ratings (pass_rush, coverage, run_stop) are wired into
resolution via effective_* helpers from ``fac_distributions``.
"""
import random
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from .player_card import PlayerCard
from .fast_action_dice import DiceResult, PlayTendency
from .charts import Charts
from .fac_distributions import (
    effective_pass_rush, effective_coverage, effective_run_stop,
    ZCardTrigger, lookup_z_card_event,
)


@dataclass
class PlayResult:
    """Result of a resolved play."""
    play_type: str
    yards_gained: int
    result: str  # GAIN, INCOMPLETE, INT, FUMBLE, SACK, TD, OOB, etc.
    is_touchdown: bool = False
    is_first_down: bool = False
    turnover: bool = False
    turnover_type: Optional[str] = None
    penalty: Optional[Dict[str, Any]] = None
    description: str = ""
    out_of_bounds: bool = False
    z_card_event: Optional[Dict[str, Any]] = None

    passer: Optional[str] = None
    rusher: Optional[str] = None
    receiver: Optional[str] = None


class PlayResolver:
    """Resolves plays by consulting player cards with FAC distributions."""

    def __init__(self):
        self.charts = Charts()

    # ── Z-card helper ────────────────────────────────────────────────

    def _check_z_card(self, dice: DiceResult,
                      down: int = 0, distance: int = 0,
                      yard_line: int = 0, quarter: int = 0,
                      time_remaining: int = 900,
                      is_offense: bool = True) -> Optional[Dict[str, Any]]:
        """Check for a Z-card event and return it if triggered."""
        if ZCardTrigger.is_triggered(
            dice.tens, dice.ones,
            down=down, distance=distance,
            yard_line=yard_line, quarter=quarter,
            time_remaining=time_remaining,
        ):
            z_dice_tens = random.randint(1, 8)
            z_dice_ones = random.randint(1, 8)
            event = lookup_z_card_event(z_dice_tens, z_dice_ones, is_offense)
            if event["event"] != "NO_EFFECT":
                return event
        return None

    # ── Run resolution ───────────────────────────────────────────────

    def resolve_run(self, dice: DiceResult, rusher: PlayerCard,
                    play_direction: str = "MIDDLE",
                    defense_run_stop: int = 50,
                    defense_formation: str = "4_3",
                    down: int = 0, distance: int = 0,
                    yard_line: int = 0, quarter: int = 0,
                    time_remaining: int = 900) -> PlayResult:
        slot = dice.slot

        # Effective run-stop with formation modifier
        eff_run_stop = effective_run_stop(defense_run_stop, defense_formation)

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

        # Defense run-stop modifier: shifts yards based on rating
        def_modifier = (eff_run_stop - 50) / 100.0
        if result_type in ("GAIN", "OOB"):
            yards = max(-5, int(yards - def_modifier * 2))
            # High run-stop can force TFL
            if eff_run_stop >= 80 and random.random() < (eff_run_stop - 75) / 100.0:
                yards = min(yards, random.choice([-2, -1, 0]))
            # High run-stop can force fumble
            if eff_run_stop >= 85 and result_type == "GAIN" and random.random() < 0.03:
                result_type = "FUMBLE"

        # Z-card check
        z_event = self._check_z_card(
            dice, down=down, distance=distance,
            yard_line=yard_line, quarter=quarter,
            time_remaining=time_remaining, is_offense=True,
        )

        # OOB result
        if result_type == "OOB":
            desc = f"{rusher.player_name} runs {play_direction.lower()} for {yards} yards, out of bounds"
            return PlayResult(
                play_type="RUN", yards_gained=yards,
                result="OOB", out_of_bounds=True,
                description=desc, rusher=rusher.player_name,
                z_card_event=z_event,
            )

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
                    rusher=rusher.player_name, z_card_event=z_event,
                )
            return PlayResult(
                play_type="RUN", yards_gained=yards,
                result="FUMBLE", turnover=is_turnover,
                turnover_type="FUMBLE" if is_turnover else None,
                description=(
                    f"{rusher.player_name} fumbles! "
                    f"{'Defense recovers!' if is_turnover else 'Offense recovers.'}"
                ),
                rusher=rusher.player_name, z_card_event=z_event,
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
            z_card_event=z_event,
        )

    # ── Two-stage pass resolution ────────────────────────────────────

    def resolve_pass(self, dice: DiceResult, qb: PlayerCard,
                     receiver: PlayerCard, pass_length: str = "SHORT",
                     defense_coverage: int = 50,
                     defense_pass_rush: int = 50,
                     defense_formation: str = "4_3",
                     is_blitz_tendency: bool = False,
                     down: int = 0, distance: int = 0,
                     yard_line: int = 0, quarter: int = 0,
                     time_remaining: int = 900) -> PlayResult:
        slot = dice.slot

        # Effective ratings with formation + blitz
        eff_pass_rush = effective_pass_rush(
            defense_pass_rush, defense_formation, is_blitz_tendency,
        )
        eff_coverage = effective_coverage(
            defense_coverage, defense_formation, is_blitz_tendency,
        )

        # ── Stage 0: Pass-rush check (before QB card lookup) ────────
        # High pass rush can shift a normal play to SACK/PRESSURE
        sack_chance = (eff_pass_rush - 50) / 200.0  # 0 at 50, 0.125 at 75, 0.245 at 99
        if sack_chance > 0 and random.random() < sack_chance:
            loss = random.choice([-3, -4, -5, -6, -7, -8])
            z_event = self._check_z_card(
                dice, down=down, distance=distance,
                yard_line=yard_line, quarter=quarter,
                time_remaining=time_remaining, is_offense=False,
            )
            return PlayResult(
                play_type="PASS", yards_gained=loss,
                result="SACK",
                description=f"{qb.player_name} is sacked for {abs(loss)} yard loss! (Pass rush pressure)",
                passer=qb.player_name, z_card_event=z_event,
            )

        # ── Stage 1: PN → QB card → pass result ─────────────────────
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

        # ── Stage 2: If COMPLETE → RN → Receiver card → yards/catch ─
        if result_type == "COMPLETE" and rec_column:
            rec_data = rec_column.get(slot, {"result": "CATCH", "yards": yards, "td": is_td})
            if rec_data.get("result") == "INCOMPLETE":
                result_type = "INCOMPLETE"
                yards = 0
                is_td = False
            else:
                # Receiver card provides yardage (use max of QB/WR for realism)
                rec_yards = rec_data.get("yards", yards)
                if rec_yards > 0:
                    yards = max(yards, rec_yards)
                rec_td = rec_data.get("td", False)
                is_td = is_td or rec_td

        # ── Coverage modifier ────────────────────────────────────────
        cov_modifier = (eff_coverage - 50) / 200.0
        if result_type == "COMPLETE":
            yards = max(0, int(yards * (1 - cov_modifier)))
            # High coverage can convert completion → incompletion
            if eff_coverage >= 80 and random.random() < (eff_coverage - 75) / 150.0:
                result_type = "INCOMPLETE"
                yards = 0
                is_td = False
            # Very high coverage can convert completion → INT (tipped ball)
            elif eff_coverage >= 90 and random.random() < 0.03:
                result_type = "INT"
                yards = 0
                is_td = False

        # Z-card check
        z_event = self._check_z_card(
            dice, down=down, distance=distance,
            yard_line=yard_line, quarter=quarter,
            time_remaining=time_remaining,
            is_offense=(result_type != "INT"),
        )

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
                z_card_event=z_event,
            )

        if result_type == "SACK":
            return PlayResult(
                play_type="PASS", yards_gained=yards,
                result="SACK",
                description=f"{qb.player_name} is sacked for {abs(yards)} yard loss!",
                passer=qb.player_name, z_card_event=z_event,
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
            z_card_event=z_event,
        )

    # ── Field goal ───────────────────────────────────────────────────

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

    # ── Punt (slot-based) ────────────────────────────────────────────

    def resolve_punt(self, punter: PlayerCard,
                     dice: Optional[DiceResult] = None) -> PlayResult:
        # Use slot-based punt column if available
        if punter.punt_column and dice is not None:
            slot = dice.slot
            punt_data = punter.punt_column.get(
                slot, {"result": "NORMAL", "yards": int(punter.avg_distance), "td": False},
            )
            punt_result = punt_data.get("result", "NORMAL")

            if punt_result == "INSIDE_20":
                distance = random.randint(
                    max(30, int(punter.avg_distance - 5)),
                    int(punter.avg_distance + 5),
                )
                return PlayResult(
                    play_type="PUNT",
                    yards_gained=distance,
                    result="PUNT",
                    description=f"{punter.player_name} punts {distance} yards, downed inside the 20",
                )
            elif punt_result == "TOUCHBACK":
                distance = random.randint(
                    int(punter.avg_distance + 5),
                    int(punter.avg_distance + 15),
                )
                return PlayResult(
                    play_type="PUNT",
                    yards_gained=distance,
                    result="PUNT",
                    description=f"{punter.player_name} punts {distance} yards, touchback",
                )
            else:
                distance = punt_data.get("yards", int(punter.avg_distance))
                return_yards = Charts.roll_punt_return()
                desc = f"{punter.player_name} punts {distance} yards"
                if return_yards > 0:
                    desc += f", returned {return_yards} yards"
                return PlayResult(
                    play_type="PUNT",
                    yards_gained=distance - return_yards,
                    result="PUNT",
                    description=desc,
                )

        # Legacy fallback for punters without a punt_column
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

    # ── XP / 2PT / Kickoff ──────────────────────────────────────────

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
