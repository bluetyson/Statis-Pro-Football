"""Game charts for Statis Pro Football using 11-88 dice system."""
import random
from typing import Dict, Any, Tuple


class Charts:
    """All game charts for Statis Pro Football."""

    PENALTY_CHART = {
        "11": {"type": "HOLDING_OFF", "yards": 10, "loss_of_down": False, "auto_first": False},
        "12": {"type": "FALSE_START", "yards": 5, "loss_of_down": False, "auto_first": False},
        "13": {"type": "HOLDING_OFF", "yards": 10, "loss_of_down": False, "auto_first": False},
        "14": {"type": "PASS_INTERFERENCE_OFF", "yards": 15, "loss_of_down": False, "auto_first": False},
        "15": {"type": "ILLEGAL_MOTION", "yards": 5, "loss_of_down": False, "auto_first": False},
        "16": {"type": "FALSE_START", "yards": 5, "loss_of_down": False, "auto_first": False},
        "17": {"type": "HOLDING_OFF", "yards": 10, "loss_of_down": False, "auto_first": False},
        "18": {"type": "INELIGIBLE_RECEIVER", "yards": 5, "loss_of_down": True, "auto_first": False},
        "21": {"type": "FALSE_START", "yards": 5, "loss_of_down": False, "auto_first": False},
        "22": {"type": "ROUGHING_PASSER", "yards": 15, "loss_of_down": False, "auto_first": True},
        "23": {"type": "HOLDING_DEF", "yards": 5, "loss_of_down": False, "auto_first": True},
        "24": {"type": "PASS_INTERFERENCE_DEF", "yards": 0, "loss_of_down": False, "auto_first": True, "spot": True},
        "25": {"type": "HOLDING_OFF", "yards": 10, "loss_of_down": False, "auto_first": False},
        "26": {"type": "ENCROACHMENT", "yards": 5, "loss_of_down": False, "auto_first": False},
        "27": {"type": "FACE_MASK", "yards": 15, "loss_of_down": False, "auto_first": True},
        "28": {"type": "HOLDING_OFF", "yards": 10, "loss_of_down": False, "auto_first": False},
        "31": {"type": "DELAY_OF_GAME", "yards": 5, "loss_of_down": False, "auto_first": False},
        "32": {"type": "HOLDING_DEF", "yards": 5, "loss_of_down": False, "auto_first": True},
        "33": {"type": "FALSE_START", "yards": 5, "loss_of_down": False, "auto_first": False},
        "34": {"type": "ROUGHING_PASSER", "yards": 15, "loss_of_down": False, "auto_first": True},
        "35": {"type": "PASS_INTERFERENCE_OFF", "yards": 10, "loss_of_down": False, "auto_first": False},
        "36": {"type": "HOLDING_OFF", "yards": 10, "loss_of_down": False, "auto_first": False},
        "37": {"type": "ILLEGAL_CONTACT", "yards": 5, "loss_of_down": False, "auto_first": True},
        "38": {"type": "OFFSIDE", "yards": 5, "loss_of_down": False, "auto_first": False},
        "41": {"type": "HOLDING_OFF", "yards": 10, "loss_of_down": False, "auto_first": False},
        "42": {"type": "CLIPPING", "yards": 15, "loss_of_down": False, "auto_first": False},
        "43": {"type": "UNNECESSARY_ROUGHNESS", "yards": 15, "loss_of_down": False, "auto_first": True},
        "44": {"type": "FALSE_START", "yards": 5, "loss_of_down": False, "auto_first": False},
        "45": {"type": "HOLDING_DEF", "yards": 5, "loss_of_down": False, "auto_first": True},
        "46": {"type": "HOLDING_OFF", "yards": 10, "loss_of_down": False, "auto_first": False},
        "47": {"type": "PASS_INTERFERENCE_DEF", "yards": 0, "loss_of_down": False, "auto_first": True, "spot": True},
        "48": {"type": "ENCROACHMENT", "yards": 5, "loss_of_down": False, "auto_first": False},
        "51": {"type": "ILLEGAL_MOTION", "yards": 5, "loss_of_down": False, "auto_first": False},
        "52": {"type": "HOLDING_OFF", "yards": 10, "loss_of_down": False, "auto_first": False},
        "53": {"type": "FALSE_START", "yards": 5, "loss_of_down": False, "auto_first": False},
        "54": {"type": "FACE_MASK", "yards": 15, "loss_of_down": False, "auto_first": True},
        "55": {"type": "HOLDING_OFF", "yards": 10, "loss_of_down": False, "auto_first": False},
        "56": {"type": "ROUGHING_KICKER", "yards": 15, "loss_of_down": False, "auto_first": True},
        "57": {"type": "HOLDING_DEF", "yards": 5, "loss_of_down": False, "auto_first": True},
        "58": {"type": "ILLEGAL_USE_HANDS", "yards": 10, "loss_of_down": False, "auto_first": False},
        "61": {"type": "HOLDING_OFF", "yards": 10, "loss_of_down": False, "auto_first": False},
        "62": {"type": "FALSE_START", "yards": 5, "loss_of_down": False, "auto_first": False},
        "63": {"type": "PASS_INTERFERENCE_DEF", "yards": 0, "loss_of_down": False, "auto_first": True, "spot": True},
        "64": {"type": "HOLDING_OFF", "yards": 10, "loss_of_down": False, "auto_first": False},
        "65": {"type": "OFFSIDE", "yards": 5, "loss_of_down": False, "auto_first": False},
        "66": {"type": "HOLDING_DEF", "yards": 5, "loss_of_down": False, "auto_first": True},
        "67": {"type": "UNNECESSARY_ROUGHNESS", "yards": 15, "loss_of_down": False, "auto_first": True},
        "68": {"type": "FALSE_START", "yards": 5, "loss_of_down": False, "auto_first": False},
        "71": {"type": "HOLDING_OFF", "yards": 10, "loss_of_down": False, "auto_first": False},
        "72": {"type": "DELAY_OF_GAME", "yards": 5, "loss_of_down": False, "auto_first": False},
        "73": {"type": "FACE_MASK", "yards": 15, "loss_of_down": False, "auto_first": True},
        "74": {"type": "HOLDING_OFF", "yards": 10, "loss_of_down": False, "auto_first": False},
        "75": {"type": "ENCROACHMENT", "yards": 5, "loss_of_down": False, "auto_first": False},
        "76": {"type": "PASS_INTERFERENCE_OFF", "yards": 10, "loss_of_down": False, "auto_first": False},
        "77": {"type": "ILLEGAL_CONTACT", "yards": 5, "loss_of_down": False, "auto_first": True},
        "78": {"type": "HOLDING_OFF", "yards": 10, "loss_of_down": False, "auto_first": False},
        "81": {"type": "FALSE_START", "yards": 5, "loss_of_down": False, "auto_first": False},
        "82": {"type": "HOLDING_OFF", "yards": 10, "loss_of_down": False, "auto_first": False},
        "83": {"type": "ROUGHING_PASSER", "yards": 15, "loss_of_down": False, "auto_first": True},
        "84": {"type": "HOLDING_DEF", "yards": 5, "loss_of_down": False, "auto_first": True},
        "85": {"type": "HOLDING_OFF", "yards": 10, "loss_of_down": False, "auto_first": False},
        "86": {"type": "FALSE_START", "yards": 5, "loss_of_down": False, "auto_first": False},
        "87": {"type": "PASS_INTERFERENCE_DEF", "yards": 0, "loss_of_down": False, "auto_first": True, "spot": True},
        "88": {"type": "CLIPPING", "yards": 15, "loss_of_down": False, "auto_first": False},
    }

    FUMBLE_RECOVERY = {
        1: "OFFENSE", 2: "OFFENSE", 3: "OFFENSE", 4: "DEFENSE",
        5: "DEFENSE", 6: "DEFENSE", 7: "DEFENSE", 8: "OFFENSE",
    }

    KICK_RETURN_CHART = {
        "11": 18, "12": 20, "13": 22, "14": 18, "15": 25, "16": 28, "17": 20, "18": 15,
        "21": 22, "22": 24, "23": 20, "24": 18, "25": 30, "26": 22, "27": 19, "28": 16,
        "31": 20, "32": 18, "33": 25, "34": 22, "35": 20, "36": 26, "37": 21, "38": 17,
        "41": 24, "42": 22, "43": 20, "44": 19, "45": 22, "46": 24, "47": 23, "48": 18,
        "51": 18, "52": 20, "53": 22, "54": 24, "55": 20, "56": 18, "57": 22, "58": 19,
        "61": 25, "62": 22, "63": 20, "64": 23, "65": 21, "66": 19, "67": 24, "68": 20,
        "71": 20, "72": 19, "73": 22, "74": 20, "75": 18, "76": 21, "77": 23, "78": 17,
        "81": 22, "82": 24, "83": 21, "84": 19, "85": 20, "86": 22, "87": 18, "88": 16,
    }

    PUNT_RETURN_CHART = {
        "11": 0, "12": 2, "13": 4, "14": 6, "15": 8, "16": 5, "17": 3, "18": 0,
        "21": 3, "22": 5, "23": 7, "24": 4, "25": 2, "26": 6, "27": 8, "28": 0,
        "31": 5, "32": 3, "33": 0, "34": 8, "35": 6, "36": 4, "37": 2, "38": 5,
        "41": 7, "42": 4, "43": 2, "44": 0, "45": 5, "46": 7, "47": 3, "48": 6,
        "51": 4, "52": 6, "53": 8, "54": 5, "55": 3, "56": 0, "57": 7, "58": 4,
        "61": 2, "62": 0, "63": 5, "64": 7, "65": 4, "66": 6, "67": 0, "68": 3,
        "71": 6, "72": 8, "73": 3, "74": 0, "75": 7, "76": 5, "77": 4, "78": 2,
        "81": 0, "82": 3, "83": 6, "84": 8, "85": 5, "86": 4, "87": 2, "88": 0,
    }

    @staticmethod
    def roll_penalty_chart() -> Dict[str, Any]:
        tens = random.randint(1, 8)
        ones = random.randint(1, 8)
        key = f"{tens}{ones}"
        return Charts.PENALTY_CHART.get(
            key, {"type": "HOLDING_OFF", "yards": 10, "loss_of_down": False, "auto_first": False}
        )

    @staticmethod
    def roll_fumble_recovery() -> str:
        return Charts.FUMBLE_RECOVERY[random.randint(1, 8)]

    @staticmethod
    def roll_kick_return() -> int:
        tens = random.randint(1, 8)
        ones = random.randint(1, 8)
        key = f"{tens}{ones}"
        return Charts.KICK_RETURN_CHART.get(key, 20)

    @staticmethod
    def roll_punt_return() -> int:
        tens = random.randint(1, 8)
        ones = random.randint(1, 8)
        key = f"{tens}{ones}"
        return Charts.PUNT_RETURN_CHART.get(key, 5)

    @staticmethod
    def is_kickoff_touchback() -> bool:
        """75% touchback rate for modern NFL."""
        return random.random() < 0.75

    @staticmethod
    def roll_int_return() -> Tuple[int, bool]:
        """Returns (return_yards, is_td)."""
        yards = random.choices(
            [0, 5, 10, 15, 20, 25, 30, 40, 99],
            weights=[20, 15, 15, 12, 10, 8, 8, 7, 5],
        )[0]
        return yards, yards == 99

    @staticmethod
    def roll_fumble_return() -> Tuple[int, bool]:
        yards = random.choices(
            [0, 5, 10, 15, 20, 25, 30, 99],
            weights=[25, 15, 15, 12, 10, 8, 8, 7],
        )[0]
        return yards, yards == 99
