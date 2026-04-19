"""Statis-Pro Football 5th Edition play and strategy card types.

Based on the original Avalon Hill strategy cards:
  DEFENSE SELECTION CARDS: Pass Defense, Prevent Defense, Run Defense variants, Blitz
  OFFENSE PLAY SELECTION CARDS: 9 offensive plays
  OFFENSE STRATEGY CARDS: Flop, Draw, Play-Action
  DEFENSE STRATEGY CARDS: Double/Triple Coverage
"""
from enum import Enum
from typing import Optional


class DefensivePlay(str, Enum):
    """5E Defensive Play Selection Cards - the actual defensive PLAY call.

    These are separate from formations (4-3, 3-4, etc.) which determine
    who is on the field. The defensive play determines how they play.
    """
    PASS_DEFENSE = "PASS_DEFENSE"
    PREVENT_DEFENSE = "PREVENT_DEFENSE"
    RUN_DEFENSE_NO_KEY = "RUN_DEFENSE_NO_KEY"
    RUN_DEFENSE_KEY_BACK_1 = "RUN_DEFENSE_KEY_BACK_1"
    RUN_DEFENSE_KEY_BACK_2 = "RUN_DEFENSE_KEY_BACK_2"
    RUN_DEFENSE_KEY_BACK_3 = "RUN_DEFENSE_KEY_BACK_3"
    BLITZ = "BLITZ"


class DefensiveFormation(str, Enum):
    """Defensive formations - determines which players are on the field."""
    FOUR_THREE = "4_3"
    THREE_FOUR = "3_4"
    NICKEL = "NICKEL"
    GOAL_LINE = "GOAL_LINE"


class DefensiveStrategy(str, Enum):
    """5E Defensive Strategy Cards - optional additional coverage."""
    NONE = "NONE"
    DOUBLE_COVERAGE = "DOUBLE_COVERAGE"
    TRIPLE_COVERAGE = "TRIPLE_COVERAGE"
    ALT_DOUBLE_COVERAGE = "ALT_DOUBLE_COVERAGE"  # Double cover TWO receivers


class OffensivePlay(str, Enum):
    """5E Offensive Play Selection Cards - the 9 offensive plays."""
    LONG_PASS = "LONG_PASS"
    SHORT_PASS = "SHORT_PASS"
    QUICK_PASS = "QUICK_PASS"
    SCREEN_PASS = "SCREEN_PASS"
    RUNNING_INSIDE_LEFT = "RUNNING_INSIDE_LEFT"
    RUNNING_INSIDE_RIGHT = "RUNNING_INSIDE_RIGHT"
    RUNNING_SWEEP_LEFT = "RUNNING_SWEEP_LEFT"
    RUNNING_SWEEP_RIGHT = "RUNNING_SWEEP_RIGHT"
    END_AROUND_QB_SNEAK = "END_AROUND_QB_SNEAK"


class OffensiveStrategy(str, Enum):
    """5E Offensive Strategy Cards."""
    NONE = "NONE"
    FLOP = "FLOP"                # QB Flop/Dive
    DRAW = "DRAW"                # Draw Play
    PLAY_ACTION = "PLAY_ACTION"  # Play-Action Pass


class PlayerInvolved(str, Enum):
    """5E Offensive Player Involved cards - who the play is directed to."""
    QB_RUNNING = "QB_RUNNING"
    RB_1 = "RB_1"                    # Running Back Number 1
    RB_2 = "RB_2"                    # Running Back Number 2
    FLANKER_OR_BACK_3 = "FLANKER_OR_BACK_3"  # Flanker or Back Number 3
    LEFT_END = "LEFT_END"            # Left End (TE or WR)
    RIGHT_END = "RIGHT_END"          # Right End (TE or WR)


# ── Display names for logging ────────────────────────────────────────

DEFENSIVE_PLAY_NAMES = {
    DefensivePlay.PASS_DEFENSE: "Pass Defense",
    DefensivePlay.PREVENT_DEFENSE: "Prevent Defense",
    DefensivePlay.RUN_DEFENSE_NO_KEY: "Run Defense / No Key On",
    DefensivePlay.RUN_DEFENSE_KEY_BACK_1: "Run Defense / Key on Back 1",
    DefensivePlay.RUN_DEFENSE_KEY_BACK_2: "Run Defense / Key on Back 2",
    DefensivePlay.RUN_DEFENSE_KEY_BACK_3: "Run Defense / Key on Back 3",
    DefensivePlay.BLITZ: "Pass Blitz Defense",
}

OFFENSIVE_PLAY_NAMES = {
    OffensivePlay.LONG_PASS: "Long Pass Play",
    OffensivePlay.SHORT_PASS: "Short Pass Play",
    OffensivePlay.QUICK_PASS: "Quick Pass / No Strategy",
    OffensivePlay.SCREEN_PASS: "Screen Pass Play",
    OffensivePlay.RUNNING_INSIDE_LEFT: "Running Inside Left",
    OffensivePlay.RUNNING_INSIDE_RIGHT: "Running Inside Right",
    OffensivePlay.RUNNING_SWEEP_LEFT: "Running Sweep Left",
    OffensivePlay.RUNNING_SWEEP_RIGHT: "Running Sweep Right",
    OffensivePlay.END_AROUND_QB_SNEAK: "End Around / QB Sneak",
}

OFFENSIVE_STRATEGY_NAMES = {
    OffensiveStrategy.NONE: "No Strategy",
    OffensiveStrategy.FLOP: "Quarterback Flop",
    OffensiveStrategy.DRAW: "Draw Play",
    OffensiveStrategy.PLAY_ACTION: "Play-Action Pass",
}

DEFENSIVE_STRATEGY_NAMES = {
    DefensiveStrategy.NONE: "No Strategy",
    DefensiveStrategy.DOUBLE_COVERAGE: "Double Coverage",
    DefensiveStrategy.TRIPLE_COVERAGE: "Triple Coverage",
    DefensiveStrategy.ALT_DOUBLE_COVERAGE: "Double Coverage (Two Receivers)",
}

PLAYER_INVOLVED_NAMES = {
    PlayerInvolved.QB_RUNNING: "Quarterback Running",
    PlayerInvolved.RB_1: "Running Back #1",
    PlayerInvolved.RB_2: "Running Back #2",
    PlayerInvolved.FLANKER_OR_BACK_3: "Flanker or Back #3",
    PlayerInvolved.LEFT_END: "Left End",
    PlayerInvolved.RIGHT_END: "Right End",
}


# ── Helpers ──────────────────────────────────────────────────────────

def is_run_defense(play: DefensivePlay) -> bool:
    """Return True if this is any run defense variant."""
    return play in (
        DefensivePlay.RUN_DEFENSE_NO_KEY,
        DefensivePlay.RUN_DEFENSE_KEY_BACK_1,
        DefensivePlay.RUN_DEFENSE_KEY_BACK_2,
        DefensivePlay.RUN_DEFENSE_KEY_BACK_3,
    )


def is_pass_defense(play: DefensivePlay) -> bool:
    """Return True if this is pass or prevent defense."""
    return play in (DefensivePlay.PASS_DEFENSE, DefensivePlay.PREVENT_DEFENSE)


def is_run_play(play: OffensivePlay) -> bool:
    """Return True if this is a running play."""
    return play in (
        OffensivePlay.RUNNING_INSIDE_LEFT,
        OffensivePlay.RUNNING_INSIDE_RIGHT,
        OffensivePlay.RUNNING_SWEEP_LEFT,
        OffensivePlay.RUNNING_SWEEP_RIGHT,
        OffensivePlay.END_AROUND_QB_SNEAK,
    )


def is_pass_play(play: OffensivePlay) -> bool:
    """Return True if this is a passing play."""
    return play in (
        OffensivePlay.LONG_PASS,
        OffensivePlay.SHORT_PASS,
        OffensivePlay.QUICK_PASS,
        OffensivePlay.SCREEN_PASS,
    )


def get_run_number_modifier_5e(defensive_play: DefensivePlay,
                                ball_carrier_number: int = 1) -> int:
    """Return run number modifier based on defensive play per 5E rules.

    Run Defense / Key on Ball Carrier: +4
    Run Defense / No Key:              +2
    Run Defense / Wrong Key:            0
    Pass/Prevent Defense:               0
    Blitz Defense:                      0
    """
    if defensive_play == DefensivePlay.BLITZ:
        return 0
    if is_pass_defense(defensive_play):
        return 0
    # Run defense variants
    if defensive_play == DefensivePlay.RUN_DEFENSE_NO_KEY:
        return 2
    # Check if keying on the correct back
    key_map = {
        DefensivePlay.RUN_DEFENSE_KEY_BACK_1: 1,
        DefensivePlay.RUN_DEFENSE_KEY_BACK_2: 2,
        DefensivePlay.RUN_DEFENSE_KEY_BACK_3: 3,
    }
    keyed_back = key_map.get(defensive_play, 0)
    if keyed_back == ball_carrier_number:
        return 4  # Correct key
    return 0  # Wrong key


def should_force_pass_rush(defensive_play: DefensivePlay,
                           pass_type: str) -> bool:
    """Return True if this defense/pass combination always triggers Pass Rush.

    Per the 5E Defense/Pass Table:
      Blitz vs Short pass → P.Rush (always)
      Blitz vs Long pass  → P.Rush (always)
    """
    return (defensive_play == DefensivePlay.BLITZ
            and pass_type in ("SHORT", "LONG"))


def get_completion_modifier_5e(defensive_play: DefensivePlay,
                                pass_type: str,
                                within_20: bool = False) -> int:
    """Return completion range modifier based on defensive play and pass type.

    5E Defense/Pass Table (from rules PDF page 5):

                     Quick    Short   Long
    Run Defense:      0(-10)  +5(0)   +7
    Pass Defense:   -10(-15)  -5       0
    Prevent Def:      0       -5      -7
    Blitz Def:      +10      P.Rush  P.Rush

    Values in parentheses apply when scrimmage line is within 20 yards
    of the defense's goal line.  Blitz vs Short/Long always triggers
    Pass Rush (see ``should_force_pass_rush``); this function returns 0
    for those cells — the caller must check ``should_force_pass_rush``
    first and bypass completion-range logic entirely.

    Screen pass modifiers are Run Number modifiers, not completion
    modifiers — see ``get_screen_rn_modifier_5e``.
    """
    if defensive_play == DefensivePlay.BLITZ:
        if pass_type == "QUICK":
            return 10
        # SHORT / LONG → pass rush; return 0 as placeholder
        return 0

    if is_run_defense(defensive_play):
        if pass_type == "QUICK":
            return -10 if within_20 else 0
        elif pass_type == "SHORT":
            return 0 if within_20 else 5
        else:  # LONG
            return 7

    if defensive_play == DefensivePlay.PASS_DEFENSE:
        if pass_type == "QUICK":
            return -15 if within_20 else -10
        elif pass_type == "SHORT":
            return -5
        else:  # LONG
            return 0

    if defensive_play == DefensivePlay.PREVENT_DEFENSE:
        if pass_type == "QUICK":
            return 0
        elif pass_type == "SHORT":
            return -5
        else:  # LONG
            return -7

    return 0


def get_screen_rn_modifier_5e(defensive_play: DefensivePlay,
                               ball_carrier_number: int = 1) -> int:
    """Return Run Number modifier for a completed screen pass.

    5E Defense/Pass Table — Screen row:
      Run Def:     0 / +2 / +4  (wrong key / no key / keyed on BC)
      Pass Def:    0
      Prevent Def: -2
      Blitz Def:   -4

    Negative values favour the offence (lower RN = more yards).
    """
    if is_run_defense(defensive_play):
        return get_run_number_modifier_5e(defensive_play, ball_carrier_number)
    if defensive_play == DefensivePlay.PREVENT_DEFENSE:
        return -2
    if defensive_play == DefensivePlay.BLITZ:
        return -4
    return 0  # Pass Defense


# Map formation strings to defensive play for backward compatibility.
# Only the four canonical 5E formation names are retained here; the old
# combo names (4_3_BLITZ, NICKEL_ZONE, etc.) have been removed.
LEGACY_FORMATION_TO_PLAY = {
    "4_3":       DefensivePlay.RUN_DEFENSE_NO_KEY,
    "3_4":       DefensivePlay.RUN_DEFENSE_NO_KEY,
    "NICKEL":    DefensivePlay.PASS_DEFENSE,
    "GOAL_LINE": DefensivePlay.RUN_DEFENSE_NO_KEY,
}

LEGACY_FORMATION_TO_FORMATION = {
    "4_3":       DefensiveFormation.FOUR_THREE,
    "3_4":       DefensiveFormation.THREE_FOUR,
    "NICKEL":    DefensiveFormation.NICKEL,
    "GOAL_LINE": DefensiveFormation.GOAL_LINE,
}
