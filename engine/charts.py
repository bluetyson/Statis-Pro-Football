"""Game charts for Statis Pro Football using 5th-edition rules."""
import random
from typing import Dict, Any, Tuple, List


class Charts:
    """All game charts for Statis Pro Football."""

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

    # ── 5E Column A/B Kickoff Table ─────────────────────────────────
    # Column A: dice 11-48 (first column)
    # Column B: dice 51-88 (second column)
    # Values represent the yard-line where the KR starts. "TB" = touchback at 25.
    KICKOFF_COLUMN_A: Dict[str, Any] = {
        "11": "TB", "12": "TB", "13": "TB", "14": "TB",
        "15": "TB", "16": "TB", "17": "TB", "18": "TB",
        "21": "TB", "22": "TB", "23": "TB", "24": "TB",
        "25": "TB", "26": "TB", "27": "TB", "28": "TB",
        "31": "TB", "32": "TB", "33": "TB", "34": "TB",
        "35": "TB", "36": "TB", "37": "KR", "38": "KR",
        "41": "TB", "42": "TB", "43": "TB", "44": "KR",
        "45": "KR", "46": "KR", "47": "KR", "48": "KR",
    }

    KICKOFF_COLUMN_B: Dict[str, Any] = {
        "51": "KR", "52": "KR", "53": "KR", "54": "KR",
        "55": "KR", "56": "KR", "57": "KR", "58": "KR",
        "61": "KR", "62": "KR", "63": "KR", "64": "KR",
        "65": "KR", "66": "KR", "67": "KR", "68": "KR",
        "71": "KR", "72": "KR", "73": "KR", "74": "KR",
        "75": "KR", "76": "KR", "77": "KR", "78": "KR",
        "81": "KR", "82": "KR", "83": "KR", "84": "KR",
        "85": "KR", "86": "KR", "87": "KR", "88": "KR",
    }

    @staticmethod
    def resolve_kickoff_5e() -> Tuple[str, int]:
        """Resolve a kickoff using the 5E Column A/B table.

        Returns (result_type, yard_line):
          - ("TB", 25) for touchback
          - ("KR", start_yard_line) for kick return, with start yard from KICK_RETURN_CHART
        """
        tens = random.randint(1, 8)
        ones = random.randint(1, 8)
        key = f"{tens}{ones}"

        # Column A = dice 1x-4x, Column B = dice 5x-8x
        if tens <= 4:
            result = Charts.KICKOFF_COLUMN_A.get(key, "TB")
        else:
            result = Charts.KICKOFF_COLUMN_B.get(key, "KR")

        if result == "TB":
            return ("TB", 25)
        else:
            return_yards = Charts.roll_kick_return()
            return ("KR", max(1, min(99, return_yards)))

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

    # ── 5th-Edition Interception Return Table (Rule 25) ──────────────

    INT_RETURN_TABLE_5E: Dict[int, Dict[str, Any]] = {
        1:  {"line": 5,  "lb": 30, "db": "TD"},
        2:  {"line": 10, "lb": 20, "db": 50},
        3:  {"line": 5,  "lb": 15, "db": 40},
        4:  {"line": 0,  "lb": 10, "db": 30},
        5:  {"line": 0,  "lb": 5,  "db": 25},
        6:  {"line": 0,  "lb": 5,  "db": 20},
        7:  {"line": 0,  "lb": 0,  "db": 15},
        8:  {"line": 0,  "lb": 0,  "db": 10},
        9:  {"line": 0,  "lb": 0,  "db": 5},
        10: {"line": 0,  "lb": 0,  "db": 0},
        11: {"line": 0,  "lb": 0,  "db": 0},
        12: {"line": 0,  "lb": 0,  "db": 0},
    }

    @staticmethod
    def roll_int_return_5e(run_number: int, defender_position: str) -> Tuple[int, bool]:
        """Return (return_yards, is_td) using the 5E 12-entry INT return table.

        Parameters
        ----------
        run_number : int
            The run number drawn (1-12).
        defender_position : str
            Position of the intercepting defender: 'DL', 'LB', 'CB', 'S',
            or any other.  DL uses the 'line' column, LB uses 'lb',
            and all DBs (CB, S, DB) use 'db'.
        """
        rn = max(1, min(12, run_number))
        entry = Charts.INT_RETURN_TABLE_5E[rn]

        pos_upper = defender_position.upper() if defender_position else "DB"
        if pos_upper in ("DL", "DE", "DT", "NT"):
            val = entry["line"]
        elif pos_upper == "LB":
            val = entry["lb"]
        else:
            val = entry["db"]

        if val == "TD":
            return 99, True
        return int(val), False

    @staticmethod
    def roll_fumble_return() -> Tuple[int, bool]:
        yards = random.choices(
            [0, 5, 10, 15, 20, 25, 30, 99],
            weights=[25, 15, 15, 12, 10, 8, 8, 7],
        )[0]
        return yards, yards == 99

    # ── 5E Punt Distance Tables (35-50 yard averages) ────────────────
    # Each key is the punter's average distance. The value is a 12-row
    # list of distances corresponding to Run Numbers 1-12.

    PUNT_DISTANCE_TABLES: Dict[int, List[int]] = {
        35: [25, 28, 30, 32, 34, 35, 36, 38, 40, 42, 45, 50],
        36: [26, 29, 31, 33, 35, 36, 37, 39, 41, 43, 46, 51],
        37: [27, 30, 32, 34, 36, 37, 38, 40, 42, 44, 47, 52],
        38: [28, 31, 33, 35, 37, 38, 39, 41, 43, 45, 48, 53],
        39: [29, 32, 34, 36, 38, 39, 40, 42, 44, 46, 49, 54],
        40: [30, 33, 35, 37, 39, 40, 41, 43, 45, 47, 50, 55],
        41: [31, 34, 36, 38, 40, 41, 42, 44, 46, 48, 51, 56],
        42: [32, 35, 37, 39, 41, 42, 43, 45, 47, 49, 52, 57],
        43: [33, 36, 38, 40, 42, 43, 44, 46, 48, 50, 53, 58],
        44: [34, 37, 39, 41, 43, 44, 45, 47, 49, 51, 54, 59],
        45: [35, 38, 40, 42, 44, 45, 46, 48, 50, 52, 55, 60],
        46: [36, 39, 41, 43, 45, 46, 47, 49, 51, 53, 56, 61],
        47: [37, 40, 42, 44, 46, 47, 48, 50, 52, 54, 57, 62],
        48: [38, 41, 43, 45, 47, 48, 49, 51, 53, 55, 58, 63],
        49: [39, 42, 44, 46, 48, 49, 50, 52, 54, 56, 59, 64],
        50: [40, 43, 45, 47, 49, 50, 51, 53, 55, 57, 60, 65],
    }

    @staticmethod
    def get_punt_distance_5e(avg_distance: float, run_number: int) -> int:
        """Look up punt distance from the 5E 12-row punt distance table.

        Parameters
        ----------
        avg_distance : float
            Punter's average punt distance (35-50 range for table lookup).
        run_number : int
            Run Number drawn (1-12).

        Returns the punt distance in yards. Falls back to avg ± variance
        if the punter's average is outside the tabled range.
        """
        rn = max(1, min(12, run_number))
        avg_int = round(avg_distance)
        avg_int = max(35, min(50, avg_int))

        if avg_int in Charts.PUNT_DISTANCE_TABLES:
            return Charts.PUNT_DISTANCE_TABLES[avg_int][rn - 1]

        # Fallback: interpolate from nearest
        lower = max(35, avg_int)
        upper = min(50, avg_int)
        return Charts.PUNT_DISTANCE_TABLES.get(
            lower, Charts.PUNT_DISTANCE_TABLES[44]
        )[rn - 1]

    # ── 5E Over-51 Yards FG Table ────────────────────────────────────
    # Based on kicker's longest field goal. Maps (longest_kick, attempt_distance)
    # to success/miss thresholds. The table gives a "Good Range" out of 48.

    OVER_51_FG_TABLE: Dict[int, Dict[int, int]] = {
        # longest_kick: {attempt_distance: good_range_out_of_48}
        50: {51: 6, 52: 4, 53: 2, 54: 0, 55: 0},
        51: {51: 8, 52: 6, 53: 4, 54: 2, 55: 0},
        52: {51: 10, 52: 8, 53: 6, 54: 4, 55: 2},
        53: {51: 12, 52: 10, 53: 8, 54: 6, 55: 4},
        54: {51: 14, 52: 12, 53: 10, 54: 8, 55: 6},
        55: {51: 16, 52: 14, 53: 12, 54: 10, 55: 8},
        56: {51: 18, 52: 16, 53: 14, 54: 12, 55: 10},
        57: {51: 20, 52: 18, 53: 16, 54: 14, 55: 12},
        58: {51: 22, 52: 20, 53: 18, 54: 16, 55: 14},
        59: {51: 24, 52: 22, 53: 20, 54: 18, 55: 16},
        60: {51: 26, 52: 24, 53: 22, 54: 20, 55: 18},
    }

    @staticmethod
    def resolve_over_51_fg(attempt_distance: int, longest_kick: int) -> bool:
        """Resolve a field goal over 51 yards using the 5E longest-boot table.

        Parameters
        ----------
        attempt_distance : int
            The distance of the FG attempt (51-55).
        longest_kick : int
            The kicker's longest made field goal in the season.

        Returns True if the kick is good.
        """
        if attempt_distance > 55:
            return False

        longest = max(50, min(60, longest_kick))
        dist = max(51, min(55, attempt_distance))

        if longest in Charts.OVER_51_FG_TABLE:
            good_range = Charts.OVER_51_FG_TABLE[longest].get(dist, 0)
        else:
            # Interpolate
            good_range = max(0, (longest - 50) * 2 - (dist - 51) * 2)

        # Roll 1-48 (PN), if ≤ good_range → made
        roll = random.randint(1, 48)
        return roll <= good_range

    # ── Punt Return Percentage / Fair Catch ───────────────────────────

    @staticmethod
    def check_fair_catch(punt_return_pct: float) -> bool:
        """Determine if the returner calls a fair catch.

        punt_return_pct: fraction of punts that are returned (0.0-1.0).
        If random roll > punt_return_pct, it's a fair catch.
        """
        return random.random() > punt_return_pct

    # ── Blocked Punt Check ────────────────────────────────────────────

    @staticmethod
    def check_blocked_punt(blocked_punt_number: int, run_number: int) -> bool:
        """Check if a punt is blocked based on the punter's blocked punt number.

        blocked_punt_number: The RN assigned to the punter card for blocks (0 = none).
        run_number: The Run Number drawn on the play.

        Returns True if the punt is blocked.
        """
        if blocked_punt_number <= 0:
            return False
        return run_number == blocked_punt_number
