"""Solitaire AI play calling for Statis Pro Football (5th Edition).

Uses FAC SOLO field parsing from the drawn FAC card for play selection.
"""
import random
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple
from .fac_deck import FACCard
from .play_types import (
    DefensivePlay, DefensiveFormation, DefensiveStrategy,
    OffensivePlay, OffensiveStrategy, PlayerInvolved,
    OFFENSIVE_PLAY_NAMES, DEFENSIVE_PLAY_NAMES, OFFENSIVE_STRATEGY_NAMES,
    DEFENSIVE_STRATEGY_NAMES, PLAYER_INVOLVED_NAMES,
)


@dataclass
class GameSituation:
    """Encapsulates the current game situation."""
    down: int
    distance: int
    yard_line: int
    score_diff: int
    quarter: int
    time_remaining: int
    timeouts_offense: int = 3
    timeouts_defense: int = 3


@dataclass
class PlayCall:
    """A called play."""
    play_type: str   # RUN, SHORT_PASS, LONG_PASS, QUICK_PASS, SCREEN, PUNT, FG, KICKOFF, KNEEL
    formation: str   # SHOTGUN, UNDER_CENTER, I_FORM, TRIPS, etc.
    direction: str   # LEFT, RIGHT, MIDDLE, IL, IR, SL, SR, DEEP_LEFT, DEEP_RIGHT, etc.
    reasoning: str
    strategy: Optional[str] = None  # FLOP, SNEAK, DRAW, PLAY_ACTION (5E offensive strategies)
    offensive_play: Optional[str] = None      # OffensivePlay value
    player_involved: Optional[str] = None     # PlayerInvolved value


# ── SOLO field code → PlayCall mapping ───────────────────────────────

def _solo_code_to_play(code: str) -> PlayCall:
    """Convert a SOLO field code to a PlayCall.

    Codes from 5th-edition FAC cards:
      R(BC)  = Run (Ball Carrier)
      R(NK)  = Run (No Key — non-featured back)
      P      = Pass (short)
      P(x2)  = Long Pass
      PR     = Play-action pass (short)
      PR(x2) = Play-action long pass
      BLZ    = Blitz defense (used as defensive call)
    """
    code = code.strip()

    if code.startswith("R(BC)"):
        direction = random.choice(["IL", "IR"])
        return PlayCall("RUN", "I_FORM", direction, f"SOLO: {code}")
    if code.startswith("R(NK)"):
        direction = random.choice(["IL", "IR", "SL", "SR"])
        return PlayCall("RUN", "UNDER_CENTER", direction, f"SOLO: {code}")
    if code == "P(x2)":
        direction = random.choice(["DEEP_LEFT", "DEEP_RIGHT"])
        return PlayCall("LONG_PASS", "SHOTGUN", direction, f"SOLO: {code}")
    if code == "PR(x2)":
        direction = random.choice(["DEEP_LEFT", "DEEP_RIGHT"])
        return PlayCall("LONG_PASS", "I_FORM", direction, f"SOLO: play-action deep")
    if code == "PR":
        direction = random.choice(["LEFT", "RIGHT", "MIDDLE"])
        return PlayCall("SHORT_PASS", "I_FORM", direction, f"SOLO: play-action")
    if code == "P":
        direction = random.choice(["LEFT", "RIGHT", "MIDDLE"])
        return PlayCall("SHORT_PASS", "SHOTGUN", direction, f"SOLO: {code}")
    if code == "BLZ":
        return PlayCall("RUN", "UNDER_CENTER", "IL", f"SOLO: blitz")

    # Fallback — treat unknown codes as a run
    return PlayCall("RUN", "I_FORM", random.choice(["IL", "IR"]), f"SOLO: unknown code {code}")


def _situation_number(situation: GameSituation) -> int:
    """Map the current game situation to a SOLO situation number (1-5).

    Numbers from 5th-edition:
      1 = 1st down / standard
      2 = 2nd down and short (≤5)
      3 = 2nd/3rd down and long (>5)
      4 = 3rd down / critical
      5 = 4th down / special
    """
    if situation.down == 1:
        return 1
    if situation.down == 2:
        return 2 if situation.distance <= 5 else 3
    if situation.down == 3:
        return 3 if situation.distance > 5 else 4
    return 5  # 4th down


class SolitaireAI:
    """AI play caller for solitaire / computer-controlled teams."""

    def __init__(self):
        # 5E Solitaire rules tracking
        self._last_play_type: str = ""      # Track last play type
        self._z_card_removed: bool = False  # Whether one Z card removed for solitaire

    def _call_fourth_down(self, situation: GameSituation) -> PlayCall:
        fg_range = situation.yard_line >= 55

        if situation.distance <= 1 and situation.yard_line > 60:
            return PlayCall("RUN", "UNDER_CENTER", random.choice(["IL", "IR"]),
                            "Short yardage in opponent territory, going for it")

        if fg_range and situation.yard_line >= 45:
            # AI considers fake FG on 4th down if score is close and not in final 2 min
            if (situation.time_remaining > 120
                    and abs(situation.score_diff) <= 7
                    and random.random() < 0.08):
                return PlayCall("FG", "SHOTGUN", "MIDDLE",
                                "Fake FG attempt (AI surprise play)",
                                strategy="FAKE_FG")
            return PlayCall("FG", "SHOTGUN", "MIDDLE",
                            f"Field goal attempt from ~{100 - situation.yard_line} yards")

        if situation.yard_line <= 45:
            # AI considers fake punt if behind and in opponent's half
            if (situation.score_diff < 0
                    and situation.yard_line >= 35
                    and random.random() < 0.06):
                return PlayCall("PUNT", "PUNT_FORMATION", "MIDDLE",
                                "Fake punt attempt (AI surprise play)",
                                strategy="FAKE_PUNT")
            return PlayCall("PUNT", "PUNT_FORMATION", "MIDDLE",
                            "Deep in own territory, punting")

        if situation.distance <= 3 and situation.yard_line > 70:
            return PlayCall("SHORT_PASS", "SHOTGUN", "MIDDLE",
                            "Short yardage 4th down attempt")

        return PlayCall("PUNT", "PUNT_FORMATION", "MIDDLE", "Punting on 4th down")

    def should_call_timeout(self, situation: GameSituation) -> bool:
        """AI timeout management: determine if AI should call a timeout.

        Returns True if the AI should call a timeout this play.
        """
        # Don't waste timeouts early
        if situation.quarter <= 2 and situation.time_remaining > 120:
            return False

        # Trailing in Q4 with under 2 minutes, call timeout to save clock
        if (situation.quarter == 4
                and situation.time_remaining <= 120
                and situation.score_diff < 0
                and situation.timeouts_offense > 0):
            return True

        # End of half, defense wants to save time
        if (situation.quarter == 2
                and situation.time_remaining <= 60
                and situation.score_diff >= 0
                and situation.timeouts_defense > 0):
            return random.random() < 0.5

        return False

    def should_use_big_play_defense(self, situation: GameSituation) -> bool:
        """AI decides whether to activate Big Play Defense.

        Returns True if conditions favor using BPD.
        """
        # Use BPD when trailing team has big-play opportunity
        if situation.down >= 3 and situation.distance >= 15:
            return random.random() < 0.6
        if situation.yard_line >= 50 and situation.down == 1:
            return random.random() < 0.15
        return False

    # ── 5th-Edition SOLO-based play calling ──────────────────────────

    def call_play_5e(self, situation: GameSituation,
                     fac_card: Optional[FACCard] = None) -> PlayCall:
        """Call a play using the FAC card's SOLO field (5th-edition mode).

        Falls back to situation-based AI if the card has no SOLO data.
        """
        # Use SOLO field if available
        if fac_card is not None and not fac_card.is_z_card:
            solo_dict = fac_card.parse_solo()
            if solo_dict:
                sit_num = _situation_number(situation)
                if sit_num in solo_dict:
                    play_call = _solo_code_to_play(solo_dict[sit_num])
                    # Override with special situations
                    if situation.down == 4:
                        return self._call_fourth_down(situation)
                    if situation.time_remaining <= 120 and situation.score_diff < 0:
                        # Two-minute drill: pass-heavy
                        if situation.distance > 10:
                            return PlayCall("LONG_PASS", "SHOTGUN",
                                            random.choice(["DEEP_LEFT", "DEEP_RIGHT"]),
                                            "Need big play in 2-minute drill")
                        return PlayCall("SHORT_PASS", "SHOTGUN",
                                        random.choice(["LEFT", "RIGHT", "MIDDLE"]),
                                        "Moving chains in 2-minute drill")
                    if situation.time_remaining <= 60 and situation.score_diff > 0:
                        return PlayCall("KNEEL", "UNDER_CENTER", "MIDDLE",
                                        "Running out the clock")
                    return play_call

        # Fallback: situation-based play calling
        if situation.down == 4:
            return self._call_fourth_down(situation)
        if situation.time_remaining <= 60 and situation.score_diff > 0:
            return PlayCall("KNEEL", "UNDER_CENTER", "MIDDLE", "Running out the clock")
        # Default run play
        direction = random.choice(["IL", "IR", "SL", "SR"])
        return PlayCall("RUN", "I_FORM", direction, "Default play")

    def call_defense_5e(self, situation: GameSituation,
                        fac_card: Optional[FACCard] = None) -> str:
        """Call a defensive formation using 5th-edition SOLO field.

        If the SOLO field indicates BLZ, use a blitz formation.
        Falls back to situation-based defense calling otherwise.

        Returns one of the four clean formation names: "4_3", "3_4",
        "NICKEL", "GOAL_LINE".  Blitz calls are signalled via the
        DefensivePlay enum (call_defense_play_5e); this method only
        returns the personnel/formation on the field.

        Nickel (4-2-5) is selected on 3rd down with 5+ yards to go:
        this covers both 3rd-and-medium (5-6 yds) and 3rd-and-long
        (7+ yds) passing situations where an extra DB replaces a LB.
        """
        if fac_card is not None and not fac_card.is_z_card:
            solo_dict = fac_card.parse_solo()
            if solo_dict:
                sit_num = _situation_number(situation)
                code = solo_dict.get(sit_num, "")
                if code == "BLZ":
                    # Formation is chosen situationally; blitz play handled separately
                    if situation.down == 3 and situation.distance >= 5:
                        return "NICKEL"
                    return random.choice(["4_3", "3_4"])

        # Situation-based defense.
        # 3rd-and-5+ covers both medium and long passing downs where an extra
        # DB replacing a LB (Nickel / 4-2-5) provides better pass coverage.
        if situation.down == 3 and situation.distance >= 5:
            return "NICKEL"
        elif situation.distance <= 2:
            return "GOAL_LINE"
        else:
            return random.choice(["4_3", "3_4"])

    # ── 5th-Edition proper play / strategy calling ───────────────────

    def call_defense_play_5e(self, situation: GameSituation,
                              fac_card: Optional[FACCard] = None
                              ) -> Tuple[DefensiveFormation, DefensivePlay, DefensiveStrategy]:
        """Call a defensive play using 5E rules.

        Returns (DefensiveFormation, DefensivePlay, DefensiveStrategy).
        """
        # Formation based on personnel
        if situation.distance <= 2 and situation.yard_line >= 95:
            formation = DefensiveFormation.GOAL_LINE
        elif situation.down == 3 and situation.distance >= 5:
            formation = DefensiveFormation.NICKEL
        else:
            formation = random.choice([DefensiveFormation.FOUR_THREE, DefensiveFormation.THREE_FOUR])

        # Defensive play based on FAC SOLO field
        if fac_card is not None and not fac_card.is_z_card:
            solo_dict = fac_card.parse_solo()
            if solo_dict:
                sit_num = _situation_number(situation)
                code = solo_dict.get(sit_num, "")
                if code == "BLZ":
                    return (formation, DefensivePlay.BLITZ, DefensiveStrategy.NONE)
                # Pass-oriented defense codes
                if code.startswith("P"):
                    play = random.choice([DefensivePlay.PASS_DEFENSE, DefensivePlay.PREVENT_DEFENSE])
                    # AI uses Double Coverage on 3rd/4th and long
                    strategy = DefensiveStrategy.NONE
                    if situation.down >= 3 and situation.distance >= 10:
                        strategy = random.choice([DefensiveStrategy.DOUBLE_COVERAGE,
                                                  DefensiveStrategy.NONE])
                    return (formation, play, strategy)

        # Situational play calling
        if situation.down == 3 and situation.distance >= 10:
            play = DefensivePlay.PREVENT_DEFENSE
            # AI uses coverage strategies on long-yardage situations
            strategy = random.choice([DefensiveStrategy.DOUBLE_COVERAGE,
                                      DefensiveStrategy.TRIPLE_COVERAGE,
                                      DefensiveStrategy.NONE])
        elif situation.down == 3 and situation.distance >= 5:
            play = DefensivePlay.PASS_DEFENSE
            strategy = random.choice([DefensiveStrategy.DOUBLE_COVERAGE,
                                      DefensiveStrategy.NONE])
        elif situation.down <= 2 and situation.distance <= 3:
            play = random.choice([
                DefensivePlay.RUN_DEFENSE_KEY_BACK_1,
                DefensivePlay.RUN_DEFENSE_KEY_BACK_2,
            ])
            strategy = DefensiveStrategy.NONE
        else:
            play = random.choice([
                DefensivePlay.RUN_DEFENSE_NO_KEY,
                DefensivePlay.PASS_DEFENSE,
                DefensivePlay.RUN_DEFENSE_KEY_BACK_1,
            ])
            strategy = DefensiveStrategy.NONE

        return (formation, play, strategy)

    def call_offense_play_5e(self, situation: GameSituation,
                              fac_card: Optional[FACCard] = None
                              ) -> Tuple[OffensivePlay, OffensiveStrategy, PlayerInvolved]:
        """Call an offensive play using 5E rules.

        Returns (OffensivePlay, OffensiveStrategy, PlayerInvolved).
        """
        # Use SOLO field if available
        if fac_card is not None and not fac_card.is_z_card:
            solo_dict = fac_card.parse_solo()
            if solo_dict:
                sit_num = _situation_number(situation)
                code = solo_dict.get(sit_num, "")
                return _solo_code_to_5e_play(code, situation)

        # Situational play calling without SOLO
        if situation.down == 4:
            # Special teams handled elsewhere; default to short pass
            return (OffensivePlay.SHORT_PASS, OffensiveStrategy.NONE, PlayerInvolved.LEFT_END)

        if situation.time_remaining <= 120 and situation.score_diff < 0:
            play = random.choice([OffensivePlay.SHORT_PASS, OffensivePlay.LONG_PASS])
            player = random.choice([PlayerInvolved.LEFT_END, PlayerInvolved.RIGHT_END,
                                    PlayerInvolved.FLANKER_OR_BACK_3])
            return (play, OffensiveStrategy.NONE, player)

        if situation.down <= 2 and situation.distance <= 3:
            play = random.choice([OffensivePlay.RUNNING_INSIDE_LEFT,
                                  OffensivePlay.RUNNING_INSIDE_RIGHT])
            return (play, OffensiveStrategy.NONE, PlayerInvolved.RB_1)

        if situation.down == 3 and situation.distance >= 7:
            play = random.choice([OffensivePlay.SHORT_PASS, OffensivePlay.LONG_PASS])
            player = random.choice([PlayerInvolved.LEFT_END, PlayerInvolved.RIGHT_END])
            return (play, OffensiveStrategy.NONE, player)

        # Normal play calling
        play = random.choice(list(OffensivePlay))
        if play in (OffensivePlay.RUNNING_INSIDE_LEFT, OffensivePlay.RUNNING_INSIDE_RIGHT,
                    OffensivePlay.RUNNING_SWEEP_LEFT, OffensivePlay.RUNNING_SWEEP_RIGHT):
            player = random.choice([PlayerInvolved.RB_1, PlayerInvolved.RB_2])
            strategy = random.choice([OffensiveStrategy.NONE, OffensiveStrategy.DRAW])
        elif play == OffensivePlay.END_AROUND_QB_SNEAK:
            player = random.choice([PlayerInvolved.QB_RUNNING, PlayerInvolved.FLANKER_OR_BACK_3])
            strategy = OffensiveStrategy.NONE
        else:
            player = random.choice([PlayerInvolved.LEFT_END, PlayerInvolved.RIGHT_END,
                                    PlayerInvolved.FLANKER_OR_BACK_3, PlayerInvolved.RB_1])
            strategy = random.choice([OffensiveStrategy.NONE, OffensiveStrategy.PLAY_ACTION])

        return (play, strategy, player)

    # ── 5th-Edition Solitaire Specific Rules ─────────────────────────

    def enforce_no_consecutive_screen_quick(self, play_call: PlayCall) -> PlayCall:
        """5E Solitaire Rule: No two screen/quick passes in succession.

        If the last play was SCREEN or QUICK_PASS and this play is also
        SCREEN or QUICK_PASS, convert it to SHORT_PASS.
        """
        screen_quick = ("SCREEN", "QUICK_PASS")
        if self._last_play_type in screen_quick and play_call.play_type in screen_quick:
            play_call = PlayCall(
                play_type="SHORT_PASS",
                formation=play_call.formation,
                direction=play_call.direction,
                reasoning=f"Converted from {play_call.play_type} (no consecutive screen/quick)",
                strategy=play_call.strategy,
            )
        self._last_play_type = play_call.play_type
        return play_call

    @staticmethod
    def convert_prevent_within_20(situation: GameSituation,
                                  defense_formation: str) -> str:
        """5E Solitaire Rule: Within 20, convert Prevent Defense to Pass Defense.

        When the offense is inside the opponent's 20-yard line, Prevent
        Defense is ineffective and should be converted to Pass Defense.

        Only the legacy string "PREVENT_DEFENSE" triggers the conversion.
        All other strings (including valid canonical formations) are returned
        unchanged.

        .. note::
            In the 5E play-call flow the relevant conversion is performed on
            the ``DefensivePlay`` enum directly inside
            ``call_defense_play_5e``; this helper is only kept for legacy
            callers that still pass formation strings.
        """
        if situation.yard_line >= 80 and defense_formation == "PREVENT_DEFENSE":
            return "4_3"  # Convert prevent to base pass defense formation
        return defense_formation


def _solo_code_to_5e_play(code: str, situation: GameSituation
                           ) -> Tuple[OffensivePlay, OffensiveStrategy, PlayerInvolved]:
    """Convert a SOLO field code to 5E play/strategy/player triple."""
    code = code.strip()

    if code.startswith("R(BC)"):
        play = random.choice([OffensivePlay.RUNNING_INSIDE_LEFT,
                              OffensivePlay.RUNNING_INSIDE_RIGHT])
        return (play, OffensiveStrategy.NONE, PlayerInvolved.RB_1)

    if code.startswith("R(NK)"):
        play = random.choice([OffensivePlay.RUNNING_SWEEP_LEFT,
                              OffensivePlay.RUNNING_SWEEP_RIGHT,
                              OffensivePlay.RUNNING_INSIDE_LEFT,
                              OffensivePlay.RUNNING_INSIDE_RIGHT])
        return (play, OffensiveStrategy.NONE, PlayerInvolved.RB_2)

    if code == "P(x2)":
        player = random.choice([PlayerInvolved.LEFT_END, PlayerInvolved.RIGHT_END])
        return (OffensivePlay.LONG_PASS, OffensiveStrategy.NONE, player)

    if code == "PR(x2)":
        player = random.choice([PlayerInvolved.LEFT_END, PlayerInvolved.RIGHT_END])
        return (OffensivePlay.LONG_PASS, OffensiveStrategy.PLAY_ACTION, player)

    if code == "PR":
        player = random.choice([PlayerInvolved.LEFT_END, PlayerInvolved.RIGHT_END,
                                PlayerInvolved.FLANKER_OR_BACK_3])
        return (OffensivePlay.SHORT_PASS, OffensiveStrategy.PLAY_ACTION, player)

    if code == "P":
        player = random.choice([PlayerInvolved.LEFT_END, PlayerInvolved.RIGHT_END,
                                PlayerInvolved.FLANKER_OR_BACK_3])
        return (OffensivePlay.SHORT_PASS, OffensiveStrategy.NONE, player)

    # Fallback — treat unknown codes as a run
    return (OffensivePlay.RUNNING_INSIDE_LEFT, OffensiveStrategy.NONE, PlayerInvolved.RB_1)
