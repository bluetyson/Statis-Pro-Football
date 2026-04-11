"""Fast Action Dice system for Statis Pro Football."""
import random
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class PlayTendency(str, Enum):
    RUN = "RUN"
    SHORT_PASS = "SHORT_PASS"
    LONG_PASS = "LONG_PASS"
    BLITZ = "BLITZ"


@dataclass
class DiceResult:
    two_digit: int          # 11-88 (tens 1-8, ones 1-8)
    tens: int               # 1-8
    ones: int               # 1-8
    play_tendency: PlayTendency
    penalty_check: bool     # ~8% chance
    turnover_modifier: int  # 1-8


class FastActionDice:
    """Simulates the Fast Action Dice from Statis Pro Football."""

    TENDENCY_MAP = {
        (1, 1): PlayTendency.RUN, (1, 2): PlayTendency.RUN, (1, 3): PlayTendency.SHORT_PASS,
        (1, 4): PlayTendency.SHORT_PASS, (1, 5): PlayTendency.LONG_PASS, (1, 6): PlayTendency.LONG_PASS,
        (1, 7): PlayTendency.BLITZ, (1, 8): PlayTendency.RUN,
        (2, 1): PlayTendency.SHORT_PASS, (2, 2): PlayTendency.RUN, (2, 3): PlayTendency.RUN,
        (2, 4): PlayTendency.SHORT_PASS, (2, 5): PlayTendency.SHORT_PASS, (2, 6): PlayTendency.LONG_PASS,
        (2, 7): PlayTendency.RUN, (2, 8): PlayTendency.BLITZ,
        (3, 1): PlayTendency.LONG_PASS, (3, 2): PlayTendency.SHORT_PASS, (3, 3): PlayTendency.RUN,
        (3, 4): PlayTendency.RUN, (3, 5): PlayTendency.SHORT_PASS, (3, 6): PlayTendency.SHORT_PASS,
        (3, 7): PlayTendency.LONG_PASS, (3, 8): PlayTendency.RUN,
        (4, 1): PlayTendency.RUN, (4, 2): PlayTendency.LONG_PASS, (4, 3): PlayTendency.SHORT_PASS,
        (4, 4): PlayTendency.RUN, (4, 5): PlayTendency.RUN, (4, 6): PlayTendency.SHORT_PASS,
        (4, 7): PlayTendency.BLITZ, (4, 8): PlayTendency.LONG_PASS,
        (5, 1): PlayTendency.SHORT_PASS, (5, 2): PlayTendency.RUN, (5, 3): PlayTendency.LONG_PASS,
        (5, 4): PlayTendency.SHORT_PASS, (5, 5): PlayTendency.RUN, (5, 6): PlayTendency.RUN,
        (5, 7): PlayTendency.SHORT_PASS, (5, 8): PlayTendency.BLITZ,
        (6, 1): PlayTendency.LONG_PASS, (6, 2): PlayTendency.SHORT_PASS, (6, 3): PlayTendency.RUN,
        (6, 4): PlayTendency.LONG_PASS, (6, 5): PlayTendency.SHORT_PASS, (6, 6): PlayTendency.RUN,
        (6, 7): PlayTendency.RUN, (6, 8): PlayTendency.SHORT_PASS,
        (7, 1): PlayTendency.BLITZ, (7, 2): PlayTendency.LONG_PASS, (7, 3): PlayTendency.SHORT_PASS,
        (7, 4): PlayTendency.RUN, (7, 5): PlayTendency.LONG_PASS, (7, 6): PlayTendency.SHORT_PASS,
        (7, 7): PlayTendency.RUN, (7, 8): PlayTendency.LONG_PASS,
        (8, 1): PlayTendency.RUN, (8, 2): PlayTendency.BLITZ, (8, 3): PlayTendency.LONG_PASS,
        (8, 4): PlayTendency.SHORT_PASS, (8, 5): PlayTendency.BLITZ, (8, 6): PlayTendency.LONG_PASS,
        (8, 7): PlayTendency.SHORT_PASS, (8, 8): PlayTendency.RUN,
    }

    PENALTY_COMBOS = {(1, 7), (3, 7), (5, 8), (7, 1), (8, 2)}

    def roll(self) -> DiceResult:
        tens = random.randint(1, 8)
        ones = random.randint(1, 8)
        two_digit = tens * 10 + ones
        tendency = self.TENDENCY_MAP.get((tens, ones), PlayTendency.RUN)
        penalty_check = (tens, ones) in self.PENALTY_COMBOS
        turnover_modifier = random.randint(1, 8)
        return DiceResult(
            two_digit=two_digit,
            tens=tens,
            ones=ones,
            play_tendency=tendency,
            penalty_check=penalty_check,
            turnover_modifier=turnover_modifier,
        )


def roll() -> DiceResult:
    return FastActionDice().roll()
