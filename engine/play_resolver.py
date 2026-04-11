"""Play resolution engine for Statis Pro Football (5th Edition).

Implements the FAC-card-driven resolution system:

  Pass plays (5th edition):
    1. Draw FAC card
    2. Check ER field for sack
    3. Check receiver target field (QK/SH/LG) for override
    4. PN → QB card → receiver letter / INC / INT
    5. If receiver letter → same PN → Receiver card → yards
    6. Screen uses FAC card SC field directly

  Run plays (5th edition):
    1. Draw FAC card
    2. RUN# → RB card → yards / FUMBLE / BREAKAWAY
    3. FAC blocking matchup fields determine context
    4. OB suffix on RUN# means out-of-bounds

  Legacy (pre-5th-ed) resolution still supported via the old resolve_*
  methods when DiceResult objects are passed.

Defence ratings (pass_rush, coverage, run_stop) are wired into
resolution via effective_* helpers from ``fac_distributions``.
"""
import random
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from .player_card import PlayerCard, RECEIVER_LETTERS
from .fast_action_dice import DiceResult, PlayTendency
from .fac_deck import FACCard, FACDeck
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

    # ══════════════════════════════════════════════════════════════════
    #  5th-EDITION  FAC-CARD  RESOLUTION METHODS
    # ══════════════════════════════════════════════════════════════════

    def _resolve_z_card(self, deck: FACDeck) -> Optional[Dict[str, Any]]:
        """Resolve a Z-card event by drawing the next non-Z card."""
        next_card = deck.draw_non_z()
        z_info = next_card.parse_z_result()
        if z_info["type"] == "NONE":
            return None
        return z_info

    def _find_receiver_by_letter(self, letter: str,
                                 receivers: List[PlayerCard]) -> Optional[PlayerCard]:
        """Find a receiver card matching the given letter (A-E)."""
        for rec in receivers:
            if rec.receiver_letter == letter:
                return rec
        # If not found, fall back to positional order
        letter_index = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}
        idx = letter_index.get(letter, 0)
        if idx < len(receivers):
            return receivers[idx]
        return receivers[0] if receivers else None

    def _resolve_receiver_target(self, fac_card: FACCard,
                                 pass_type: str,
                                 default_receiver: PlayerCard,
                                 receivers: List[PlayerCard]) -> PlayerCard:
        """Determine which receiver is targeted based on FAC card field."""
        target = fac_card.get_receiver_target(pass_type)
        if target in ("Orig", "Z"):
            return default_receiver
        if target == "P.Rush":
            return default_receiver  # caller handles P.Rush as sack
        # Target is a position code: FL, LE, RE, BK1, BK2, etc.
        target_map = {"FL": 0, "LE": 1, "RE": 2, "BK1": 3, "BK2": 4}
        idx = target_map.get(target, 0)
        if idx < len(receivers):
            return receivers[idx]
        return default_receiver

    def resolve_pass_5e(self, fac_card: FACCard, deck: FACDeck,
                        qb: PlayerCard, receiver: PlayerCard,
                        receivers: List[PlayerCard],
                        pass_type: str = "SHORT",
                        defense_coverage: int = 50,
                        defense_pass_rush: int = 50,
                        defense_formation: str = "4_3",
                        is_blitz_tendency: bool = False) -> PlayResult:
        """Resolve a pass play using 5th-edition FAC card mechanics.

        Parameters
        ----------
        fac_card : FACCard
            The drawn FAC card for this play.
        deck : FACDeck
            The deck (needed for Z-card resolution).
        qb : PlayerCard
            Quarterback's card.
        receiver : PlayerCard
            Default receiver for this play.
        receivers : List[PlayerCard]
            All available receivers (WRs + TEs).
        pass_type : str
            "SHORT", "LONG", "QUICK", or "SCREEN".
        """
        # ── Handle Z card ────────────────────────────────────────────
        if fac_card.is_z_card:
            z_event = self._resolve_z_card(deck)
            # On a Z card, draw the next card and use it for the play
            fac_card = deck.draw_non_z()
            return self._resolve_pass_inner_5e(
                fac_card, deck, qb, receiver, receivers, pass_type,
                defense_coverage, defense_pass_rush, defense_formation,
                is_blitz_tendency, z_event,
            )

        return self._resolve_pass_inner_5e(
            fac_card, deck, qb, receiver, receivers, pass_type,
            defense_coverage, defense_pass_rush, defense_formation,
            is_blitz_tendency, None,
        )

    def _resolve_pass_inner_5e(self, fac_card: FACCard, deck: FACDeck,
                               qb: PlayerCard, receiver: PlayerCard,
                               receivers: List[PlayerCard],
                               pass_type: str,
                               defense_coverage: int,
                               defense_pass_rush: int,
                               defense_formation: str,
                               is_blitz_tendency: bool,
                               z_event: Optional[Dict[str, Any]]) -> PlayResult:
        """Inner pass resolution after Z-card handling.

        Authentic resolution:
          1. Check ER (sack) on FAC card
          2. Check receiver target on FAC card
          3. Screen passes use FAC SC field directly
          4. PN → QB card passing ranges → COM / INC / INT
          5. If COM → RUN NUMBER → receiver's pass-gain Q/S/L → yards
        """

        # ── Step 1: Check ER (pass rush / sack) ─────────────────────
        sack_yards = fac_card.sack_yards
        if sack_yards is not None:
            return PlayResult(
                play_type="PASS", yards_gained=sack_yards,
                result="SACK",
                description=f"{qb.player_name} is sacked for {abs(sack_yards)} yard loss!",
                passer=qb.player_name, z_card_event=z_event,
            )

        # ── Step 1b: Check receiver target for P.Rush ────────────────
        target_field = fac_card.get_receiver_target(pass_type)
        if target_field == "P.Rush":
            # Pass rush result → check QB's pass_rush ranges
            if qb.pass_rush:
                pn = fac_card.pass_num_int or random.randint(1, 48)
                pr_result = qb.pass_rush.resolve(pn)
                if pr_result == "SACK":
                    loss = -(pn // 3 + 1)  # Sack yards from PN
                    loss = max(loss, -8)
                    return PlayResult(
                        play_type="PASS", yards_gained=loss,
                        result="SACK",
                        description=f"{qb.player_name} sacked on pass rush! {abs(loss)} yard loss.",
                        passer=qb.player_name, z_card_event=z_event,
                    )
                elif pr_result == "RUNS":
                    # QB scramble — use rushing column
                    run_num = fac_card.run_num_int or random.randint(1, 12)
                    if qb.rushing:
                        row = qb.get_rushing_row(run_num)
                        yards = row.v1 if isinstance(row.v1, int) else random.randint(1, 8)
                    else:
                        yards = random.randint(-2, 5)
                    is_td = random.random() < 0.03
                    return PlayResult(
                        play_type="PASS", yards_gained=yards,
                        result="TD" if is_td else "GAIN",
                        is_touchdown=is_td,
                        description=f"{qb.player_name} scrambles for {yards} yards",
                        passer=qb.player_name, z_card_event=z_event,
                    )
                elif pr_result == "INC":
                    return PlayResult(
                        play_type="PASS", yards_gained=0, result="INCOMPLETE",
                        description=f"{qb.player_name} hurried, pass incomplete",
                        passer=qb.player_name, z_card_event=z_event,
                    )
                # pr_result == "COM" → pass completed despite rush, continue
            else:
                loss = random.choice([-3, -4, -5, -6])
                return PlayResult(
                    play_type="PASS", yards_gained=loss,
                    result="SACK",
                    description=f"{qb.player_name} sacked on pass rush! {abs(loss)} yard loss.",
                    passer=qb.player_name, z_card_event=z_event,
                )

        # ── Step 2: Screen pass — use FAC SC field directly ──────────
        if pass_type == "SCREEN":
            return self._resolve_screen_5e(fac_card, qb, receiver, z_event)

        # ── Step 3: Determine actual receiver target ─────────────────
        actual_receiver = self._resolve_receiver_target(
            fac_card, pass_type, receiver, receivers,
        )

        # ── Step 4: PN → QB card passing ranges → COM/INC/INT ────────
        pn = fac_card.pass_num_int
        if pn is None:
            pn = random.randint(1, 48)

        # Check authentic range-based passing first
        if qb.passing_short or qb.passing_long or qb.passing_quick:
            qb_result = qb.resolve_passing(pass_type, pn)
        else:
            # Legacy: fall back to old slot-based columns
            if pass_type == "LONG":
                qb_column = qb.long_pass
            elif pass_type == "QUICK":
                qb_column = qb.quick_pass if qb.quick_pass else qb.short_pass
            else:
                qb_column = qb.short_pass

            if not qb_column:
                comp = random.random() < 0.62
                if comp:
                    yards = random.randint(5, 15)
                    return PlayResult(
                        play_type="PASS", yards_gained=yards, result="COMPLETE",
                        description=f"{qb.player_name} completes to {actual_receiver.player_name} for {yards} yards",
                        passer=qb.player_name, receiver=actual_receiver.player_name,
                        z_card_event=z_event,
                    )
                return PlayResult(
                    play_type="PASS", yards_gained=0, result="INCOMPLETE",
                    description=f"{qb.player_name} pass incomplete to {actual_receiver.player_name}",
                    passer=qb.player_name, receiver=actual_receiver.player_name,
                    z_card_event=z_event,
                )

            pn_str = str(pn)
            qb_data = qb_column.get(pn_str, {"result": "INC", "yards": 0, "td": False})
            qb_result_raw = qb_data.get("result", "INC")
            # Map old results to COM/INC/INT
            if qb_result_raw in ("INT",):
                qb_result = "INT"
            elif qb_result_raw in ("INC", "INCOMPLETE"):
                qb_result = "INC"
            else:
                qb_result = "COM"  # Any receiver letter or COMPLETE = completion

        # ── INT result ───────────────────────────────────────────────
        if qb_result == "INT":
            int_yards, int_td = Charts.roll_int_return()
            return PlayResult(
                play_type="PASS", yards_gained=0,
                result="INT", turnover=True, turnover_type="INT",
                description=(
                    f"{qb.player_name} pass intercepted!"
                    f"{'Returned for TD!' if int_td else f' Returned {int_yards} yards.'}"
                ),
                passer=qb.player_name, receiver=actual_receiver.player_name,
                z_card_event=z_event,
            )

        # ── INC result ───────────────────────────────────────────────
        if qb_result == "INC":
            return PlayResult(
                play_type="PASS", yards_gained=0, result="INCOMPLETE",
                description=f"{qb.player_name} pass incomplete to {actual_receiver.player_name}",
                passer=qb.player_name, receiver=actual_receiver.player_name,
                z_card_event=z_event,
            )

        # ── COM result — Stage 2: RUN NUMBER → receiver pass gain ────
        # Use the RUN NUMBER from the FAC card to look up yards on receiver's card
        run_num = fac_card.run_num_int
        if run_num is None:
            run_num = random.randint(1, 12)

        target_receiver = actual_receiver
        # If old-style QB card had receiver letters, look up that receiver
        if not (qb.passing_short or qb.passing_long or qb.passing_quick):
            # Legacy path: receiver might be encoded in qb_result_raw
            if qb_result_raw in RECEIVER_LETTERS:
                found = self._find_receiver_by_letter(qb_result_raw, receivers)
                if found:
                    target_receiver = found

        # Look up pass gain on receiver's card (Q/S/L columns)
        if target_receiver.pass_gain:
            row = target_receiver.get_pass_gain_row(run_num)
            if pass_type == "QUICK":
                yards = row.v1
            elif pass_type == "LONG":
                yards = row.v3
            else:
                yards = row.v2  # Short pass

            # Handle string values like "Lg" (long gain / big play)
            if isinstance(yards, str):
                if yards == "Lg":
                    yards = random.randint(25, 60)
                else:
                    try:
                        yards = int(yards)
                    except (ValueError, TypeError):
                        yards = random.randint(5, 15)
            is_td = random.random() < (0.06 if pass_type == "LONG" else 0.04)
        elif target_receiver.short_reception or target_receiver.long_reception:
            # Legacy fallback: use old reception columns
            pn_str = str(pn)
            if pass_type == "LONG":
                rec_column = target_receiver.long_reception
            else:
                rec_column = target_receiver.short_reception

            if rec_column:
                rec_data = rec_column.get(pn_str, {"result": "CATCH", "yards": 8, "td": False})
                if rec_data.get("result") in ("INC", "INCOMPLETE"):
                    return PlayResult(
                        play_type="PASS", yards_gained=0, result="INCOMPLETE",
                        description=f"{qb.player_name} pass dropped by {target_receiver.player_name}",
                        passer=qb.player_name, receiver=target_receiver.player_name,
                        z_card_event=z_event,
                    )
                yards = rec_data.get("yards", 8)
                is_td = rec_data.get("td", False)
            else:
                yards = random.randint(5, 15) if pass_type != "LONG" else random.randint(15, 30)
                is_td = random.random() < 0.05
        else:
            # No receiver card data at all
            yards = random.randint(5, 15) if pass_type != "LONG" else random.randint(15, 30)
            is_td = random.random() < 0.05

        # Coverage modifier
        eff_cov = effective_coverage(defense_coverage, defense_formation, is_blitz_tendency)
        cov_modifier = (eff_cov - 50) / 200.0
        if cov_modifier > 0 and isinstance(yards, int):
            yards = max(0, int(yards * (1 - cov_modifier)))

        if is_td:
            desc = f"{qb.player_name} completes to {target_receiver.player_name} for a TOUCHDOWN!"
        else:
            desc = f"{qb.player_name} completes to {target_receiver.player_name} for {yards} yard{'s' if yards != 1 else ''}"

        return PlayResult(
            play_type="PASS", yards_gained=yards,
            result="TD" if is_td else "COMPLETE",
            is_touchdown=is_td,
            description=desc,
            passer=qb.player_name, receiver=target_receiver.player_name,
            z_card_event=z_event,
        )

    def _resolve_screen_5e(self, fac_card: FACCard, qb: PlayerCard,
                           receiver: PlayerCard,
                           z_event: Optional[Dict[str, Any]]) -> PlayResult:
        """Resolve a screen pass using the FAC card's SC field."""
        sc_result = fac_card.screen_result

        if sc_result == "Inc":
            return PlayResult(
                play_type="PASS", yards_gained=0, result="INCOMPLETE",
                description=f"{qb.player_name} screen pass to {receiver.player_name} - incomplete",
                passer=qb.player_name, receiver=receiver.player_name,
                z_card_event=z_event,
            )

        if sc_result == "Int":
            int_yards, int_td = Charts.roll_int_return()
            return PlayResult(
                play_type="PASS", yards_gained=0,
                result="INT", turnover=True, turnover_type="INT",
                description=f"{qb.player_name} screen pass intercepted!",
                passer=qb.player_name, receiver=receiver.player_name,
                z_card_event=z_event,
            )

        # Screen complete — base yards
        base_yards = random.randint(3, 10)
        multiplier = 1.0

        if sc_result.startswith("Com x"):
            try:
                mult_str = sc_result.split("x")[-1].strip()
                if "½" in mult_str:
                    multiplier = 0.5
                elif "/" in mult_str:
                    # Handle fractions like "1/2"
                    num, den = mult_str.split("/")
                    multiplier = float(num) / float(den)
                else:
                    multiplier = float(mult_str)
            except (ValueError, ZeroDivisionError):
                multiplier = 1.0
        elif sc_result == "Dropped Int":
            # Dropped interception → treat as incomplete
            return PlayResult(
                play_type="PASS", yards_gained=0, result="INCOMPLETE",
                description=f"{qb.player_name} screen pass nearly intercepted - dropped!",
                passer=qb.player_name, receiver=receiver.player_name,
                z_card_event=z_event,
            )

        yards = max(0, int(base_yards * multiplier))
        is_td = random.random() < 0.03

        if is_td:
            desc = f"{qb.player_name} screen pass to {receiver.player_name} for a TOUCHDOWN!"
        else:
            desc = f"{qb.player_name} screen pass to {receiver.player_name} for {yards} yards"

        return PlayResult(
            play_type="PASS", yards_gained=yards,
            result="TD" if is_td else "COMPLETE",
            is_touchdown=is_td,
            description=desc,
            passer=qb.player_name, receiver=receiver.player_name,
            z_card_event=z_event,
        )

    def resolve_run_5e(self, fac_card: FACCard, deck: FACDeck,
                       rusher: PlayerCard,
                       play_direction: str = "IL",
                       defense_run_stop: int = 50,
                       defense_formation: str = "4_3") -> PlayResult:
        """Resolve a run play using 5th-edition FAC card mechanics.

        Authentic resolution:
          1. Draw FAC → get RUN NUMBER (1-12)
          2. Look up rusher's Rushing column row → N/SG/LG values
          3. Use N (Normal) column as base yards
          4. Modify by blocking matchups

        Parameters
        ----------
        fac_card : FACCard
            The drawn FAC card.
        deck : FACDeck
            The deck (for Z-card resolution).
        rusher : PlayerCard
            The ball carrier's card.
        play_direction : str
            "SL" (sweep left), "IL" (inside left),
            "SR" (sweep right), "IR" (inside right).
        """
        z_event = None

        # ── Handle Z card ────────────────────────────────────────────
        if fac_card.is_z_card:
            z_event = self._resolve_z_card(deck)
            fac_card = deck.draw_non_z()

        # ── Determine run number and OOB ─────────────────────────────
        run_num = fac_card.run_num_int
        is_oob = fac_card.is_out_of_bounds
        rn_str = str(run_num) if run_num is not None else "1"

        # Effective run-stop
        eff_run_stop = effective_run_stop(defense_run_stop, defense_formation)

        # ── Try authentic 12-row rushing first ───────────────────────
        if rusher.rushing and rusher.has_rushing():
            rn = run_num if run_num is not None else 1
            row = rusher.get_rushing_row(rn)

            # Use N (normal) column as base yards
            yards = row.v1
            if isinstance(yards, str):
                if yards == "Sg":
                    # Special gain (breakaway)
                    yards = row.v3 if isinstance(row.v3, int) else random.randint(15, 40)
                    is_td = random.random() < 0.2
                    desc = f"{rusher.player_name} breaks free for {yards} yards!"
                    if is_td:
                        desc += " TOUCHDOWN!"
                    return PlayResult(
                        play_type="RUN", yards_gained=yards,
                        result="TD" if is_td else "GAIN",
                        is_touchdown=is_td,
                        description=desc,
                        rusher=rusher.player_name, z_card_event=z_event,
                    )
                else:
                    try:
                        yards = int(yards)
                    except (ValueError, TypeError):
                        yards = random.randint(1, 5)

            # Defense run-stop modifier
            def_modifier = (eff_run_stop - 50) / 100.0
            yards = max(-5, int(yards - def_modifier * 2))
            if eff_run_stop >= 80 and random.random() < (eff_run_stop - 75) / 100.0:
                yards = min(yards, random.choice([-2, -1, 0]))
            if eff_run_stop >= 85 and random.random() < 0.03:
                recovery = Charts.roll_fumble_recovery()
                fumble_yards, fumble_td = Charts.roll_fumble_return()
                is_turnover = recovery == "DEFENSE"
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

            # Out of bounds
            if is_oob:
                desc = f"{rusher.player_name} runs {play_direction} for {yards} yards, out of bounds"
                return PlayResult(
                    play_type="RUN", yards_gained=yards,
                    result="OOB", out_of_bounds=True,
                    description=desc, rusher=rusher.player_name,
                    z_card_event=z_event,
                )

            is_td = random.random() < 0.03
            desc = f"{rusher.player_name} runs {play_direction}"
            if is_td:
                desc += " for a TOUCHDOWN!"
            else:
                desc += f" for {yards} yard{'s' if yards != 1 else ''}"

            return PlayResult(
                play_type="RUN", yards_gained=yards,
                result="TD" if is_td else "GAIN",
                is_touchdown=is_td,
                description=desc,
                rusher=rusher.player_name, z_card_event=z_event,
            )

        # ── Legacy: fall back to old slot-based columns ──────────────
        if play_direction in ("SL", "SR"):
            column = rusher.sweep if rusher.sweep else rusher.outside_run
        elif play_direction in ("IL", "IR"):
            column = rusher.inside_run
        elif play_direction in ("LEFT", "MIDDLE"):
            column = rusher.inside_run
        else:
            column = rusher.outside_run

        if not column:
            yards = random.choices([-2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8],
                                   weights=[2, 3, 5, 8, 10, 12, 12, 10, 8, 5, 3])[0]
            return PlayResult(
                play_type="RUN", yards_gained=yards, result="GAIN",
                description=f"{rusher.player_name} runs for {yards} yards",
                rusher=rusher.player_name, z_card_event=z_event,
            )

        play_data = column.get(rn_str, {"result": "GAIN", "yards": 2, "td": False})
        result_type = play_data.get("result", "GAIN")
        yards = play_data.get("yards", 0)
        is_td = play_data.get("td", False)

        # Defense run-stop modifier
        def_modifier = (eff_run_stop - 50) / 100.0
        if result_type in ("GAIN", "BREAKAWAY"):
            yards = max(-5, int(yards - def_modifier * 2))
            if eff_run_stop >= 80 and random.random() < (eff_run_stop - 75) / 100.0:
                yards = min(yards, random.choice([-2, -1, 0]))
            if eff_run_stop >= 85 and result_type == "GAIN" and random.random() < 0.03:
                result_type = "FUMBLE"

        # ── Out of bounds ────────────────────────────────────────────
        if is_oob:
            desc = f"{rusher.player_name} runs {play_direction} for {yards} yards, out of bounds"
            return PlayResult(
                play_type="RUN", yards_gained=yards,
                result="OOB", out_of_bounds=True,
                description=desc, rusher=rusher.player_name,
                z_card_event=z_event,
            )

        # ── Fumble ───────────────────────────────────────────────────
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

        # ── Breakaway ────────────────────────────────────────────────
        if result_type == "BREAKAWAY":
            is_td = is_td or random.random() < 0.2
            desc = f"{rusher.player_name} breaks free for {yards} yards!"
            if is_td:
                desc += " TOUCHDOWN!"
            return PlayResult(
                play_type="RUN", yards_gained=yards,
                result="TD" if is_td else "GAIN",
                is_touchdown=is_td,
                description=desc,
                rusher=rusher.player_name, z_card_event=z_event,
            )

        # ── Normal gain ──────────────────────────────────────────────
        # Check Z RES on the card for additional effects
        z_res_info = fac_card.parse_z_result()
        if z_res_info["type"] == "FUMBLE" and random.random() < 0.5:
            recovery = Charts.roll_fumble_recovery()
            is_turnover = recovery == "DEFENSE"
            return PlayResult(
                play_type="RUN", yards_gained=yards,
                result="FUMBLE", turnover=is_turnover,
                turnover_type="FUMBLE" if is_turnover else None,
                description=(
                    f"{rusher.player_name} fumbles at the end of the run! "
                    f"{'Defense recovers!' if is_turnover else 'Offense recovers.'}"
                ),
                rusher=rusher.player_name, z_card_event=z_event,
            )

        desc = f"{rusher.player_name} runs {play_direction}"
        if is_td:
            desc += " for a TOUCHDOWN!"
        else:
            desc += f" for {yards} yard{'s' if yards != 1 else ''}"

        return PlayResult(
            play_type="RUN", yards_gained=yards,
            result="TD" if is_td else "GAIN",
            is_touchdown=is_td,
            description=desc,
            rusher=rusher.player_name,
            z_card_event=z_event,
        )
