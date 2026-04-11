"""Solitaire AI play calling for Statis Pro Football."""
import random
from dataclasses import dataclass
from typing import Optional
from .fast_action_dice import FastActionDice, DiceResult, PlayTendency


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
    play_type: str   # RUN, SHORT_PASS, LONG_PASS, SCREEN, PUNT, FG, KICKOFF, KNEEL
    formation: str   # SHOTGUN, UNDER_CENTER, I_FORM, TRIPS, etc.
    direction: str   # LEFT, RIGHT, MIDDLE, DEEP_LEFT, DEEP_RIGHT, etc.
    reasoning: str


class SolitaireAI:
    """AI play caller for solitaire / computer-controlled teams."""

    def __init__(self):
        self.dice = FastActionDice()

    def call_play(self, situation: GameSituation,
                  dice_result: Optional[DiceResult] = None) -> PlayCall:
        """Call a play based on the game situation."""
        if dice_result is None:
            dice_result = self.dice.roll()

        if situation.down == 4:
            return self._call_fourth_down(situation)

        if situation.time_remaining <= 120 and situation.score_diff < 0:
            return self._call_two_minute_drill(situation, dice_result)

        if situation.time_remaining <= 60 and situation.score_diff > 0:
            return PlayCall("KNEEL", "UNDER_CENTER", "MIDDLE", "Running out the clock")

        return self._call_normal_play(situation, dice_result)

    def _call_fourth_down(self, situation: GameSituation) -> PlayCall:
        fg_range = situation.yard_line >= 55

        if situation.distance <= 1 and situation.yard_line > 60:
            return PlayCall("RUN", "UNDER_CENTER", "MIDDLE",
                            "Short yardage in opponent territory, going for it")

        if fg_range and situation.yard_line >= 45:
            return PlayCall("FG", "SHOTGUN", "MIDDLE",
                            f"Field goal attempt from ~{100 - situation.yard_line} yards")

        if situation.yard_line <= 45:
            return PlayCall("PUNT", "PUNT_FORMATION", "MIDDLE",
                            "Deep in own territory, punting")

        if situation.distance <= 3 and situation.yard_line > 70:
            return PlayCall("SHORT_PASS", "SHOTGUN", "MIDDLE",
                            "Short yardage 4th down attempt")

        return PlayCall("PUNT", "PUNT_FORMATION", "MIDDLE", "Punting on 4th down")

    def _call_two_minute_drill(self, situation: GameSituation,
                               dice_result: DiceResult) -> PlayCall:
        if situation.distance > 10:
            return PlayCall("LONG_PASS", "SHOTGUN",
                            random.choice(["DEEP_LEFT", "DEEP_RIGHT"]),
                            "Need big play in 2-minute drill")
        elif situation.distance > 5:
            return PlayCall("SHORT_PASS", "SHOTGUN",
                            random.choice(["LEFT", "RIGHT", "MIDDLE"]),
                            "Moving chains in 2-minute drill")
        else:
            return PlayCall("SHORT_PASS", "SHOTGUN",
                            random.choice(["LEFT", "RIGHT"]),
                            "Short pass to get out of bounds")

    def _call_normal_play(self, situation: GameSituation,
                          dice_result: DiceResult) -> PlayCall:
        tendency = dice_result.play_tendency

        if situation.down == 1:
            return self._first_down_play(situation, tendency)
        elif situation.down == 2:
            return self._second_down_play(situation, tendency)
        else:
            return self._third_down_play(situation, tendency)

    def _first_down_play(self, situation: GameSituation,
                         tendency: PlayTendency) -> PlayCall:
        if tendency == PlayTendency.RUN:
            direction = random.choice(["LEFT", "RIGHT", "MIDDLE"])
            return PlayCall("RUN", "I_FORM", direction, "1st and 10 run")
        elif tendency == PlayTendency.SHORT_PASS:
            direction = random.choice(["LEFT", "RIGHT", "MIDDLE"])
            return PlayCall("SHORT_PASS", "SHOTGUN", direction, "1st down short pass")
        elif tendency == PlayTendency.LONG_PASS:
            direction = random.choice(["DEEP_LEFT", "DEEP_RIGHT"])
            return PlayCall("LONG_PASS", "SHOTGUN", direction, "1st down shot downfield")
        else:
            return PlayCall("SCREEN", "SHOTGUN", "MIDDLE", "Screen to counter blitz")

    def _second_down_play(self, situation: GameSituation,
                          tendency: PlayTendency) -> PlayCall:
        if situation.distance <= 3:
            if tendency in (PlayTendency.RUN, PlayTendency.BLITZ):
                return PlayCall("RUN", "UNDER_CENTER", "MIDDLE", "Short yardage run")
            else:
                return PlayCall("SHORT_PASS", "SHOTGUN", "MIDDLE", "Short yardage pass")
        elif situation.distance <= 7:
            if tendency == PlayTendency.RUN:
                return PlayCall("RUN", "I_FORM", random.choice(["LEFT", "RIGHT"]),
                                "2nd and medium run")
            else:
                direction = random.choice(["LEFT", "RIGHT", "MIDDLE"])
                return PlayCall("SHORT_PASS", "SHOTGUN", direction, "2nd and medium pass")
        else:
            if tendency == PlayTendency.LONG_PASS:
                return PlayCall("LONG_PASS", "SHOTGUN",
                                random.choice(["DEEP_LEFT", "DEEP_RIGHT"]),
                                "2nd and long, shot downfield")
            direction = random.choice(["LEFT", "RIGHT", "MIDDLE"])
            return PlayCall("SHORT_PASS", "SHOTGUN", direction, "2nd and long pass")

    def _third_down_play(self, situation: GameSituation,
                         tendency: PlayTendency) -> PlayCall:
        if situation.distance <= 2:
            if tendency in (PlayTendency.RUN, PlayTendency.BLITZ):
                return PlayCall("RUN", "UNDER_CENTER", "MIDDLE", "3rd and short run sneak")
            return PlayCall("SHORT_PASS", "SHOTGUN", "MIDDLE", "Quick 3rd and short pass")
        elif situation.distance <= 5:
            direction = random.choice(["LEFT", "RIGHT", "MIDDLE"])
            return PlayCall("SHORT_PASS", "SHOTGUN", direction, "3rd down conversion pass")
        elif situation.distance <= 10:
            direction = random.choice(["LEFT", "RIGHT", "MIDDLE"])
            return PlayCall("SHORT_PASS", "SHOTGUN", direction, "3rd down pass")
        else:
            direction = random.choice(["DEEP_LEFT", "DEEP_RIGHT", "MIDDLE"])
            return PlayCall("LONG_PASS", "SHOTGUN", direction, "3rd and long shot")

    def call_defense(self, situation: GameSituation,
                     dice_result: Optional[DiceResult] = None) -> str:
        """Call a defensive formation."""
        if dice_result is None:
            dice_result = self.dice.roll()

        tendency = dice_result.play_tendency

        if situation.down == 3 and situation.distance >= 7:
            return "NICKEL_BLITZ" if tendency == PlayTendency.BLITZ else "NICKEL_ZONE"
        elif situation.down == 3:
            return "NICKEL_COVER2"
        elif tendency == PlayTendency.BLITZ:
            return "4_3_BLITZ"
        elif situation.distance <= 2:
            return "GOAL_LINE"
        else:
            return random.choice(["4_3", "3_4", "4_3_COVER2", "3_4_ZONE"])
