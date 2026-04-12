"""Fast Action Card (FAC) distribution tables for Statis Pro Football.

5th-Edition card structure
==========================
  * QB cards:  48 rows (Pass Numbers 1–48).
    Each cell → receiver letter (A–E) / INC / INT.
  * RB cards:  12 rows (Run Numbers 1–12).
    Each cell → yardage / FUMBLE / BREAKAWAY / TD.
  * WR/TE cards: 48 rows (Pass Numbers 1–48).
    Each cell → yards gained / INC.

Legacy 64-slot helpers are kept for backward compatibility with
pre-5th-edition team data files.

This module also provides:
  * Yardage pools by grade (used during card generation)
  * Z-card event tables (now primarily triggered by FACDeck Z cards)
  * Defence formation modifiers
"""

from typing import Dict, List, Tuple, Any


# ──────────────────────────────────────────────────────────────────────
#  Slot helpers
# ──────────────────────────────────────────────────────────────────────

PASS_SLOT_COUNT = 48    # 5th-edition pass numbers 1–48
RUN_SLOT_COUNT = 12     # 5th-edition run numbers 1–12
SLOT_COUNT = 64         # Legacy 8×8 dice grid


def all_slots() -> List[str]:
    """Return all 64 legacy slot keys from 11 to 88."""
    return [f"{t}{o}" for t in range(1, 9) for o in range(1, 9)]


def pass_slots() -> List[str]:
    """Return all 48 pass-number slot keys ("1" through "48")."""
    return [str(n) for n in range(1, PASS_SLOT_COUNT + 1)]


def run_slots() -> List[str]:
    """Return all 12 run-number slot keys ("1" through "12")."""
    return [str(n) for n in range(1, RUN_SLOT_COUNT + 1)]


# ──────────────────────────────────────────────────────────────────────
#  5th-Edition QB Pass distribution (48 slots, receiver-letter results)
# ──────────────────────────────────────────────────────────────────────

RECEIVER_LETTERS = ["A", "B", "C", "D", "E"]


def qb_pass_distribution_5e(
    comp_pct: float,
    int_pct: float,
    grade: str,
    n_receivers: int = 5,
) -> Dict[str, int]:
    """Return {result_type: slot_count} for a 5th-ed QB pass column (48 slots).

    Results are receiver letters (A-E), INC, or INT.
    On COMPLETE results the QB card returns the receiver letter rather than
    yardage — yardage comes from the receiver's own card in the 2nd stage.

    Parameters
    ----------
    comp_pct : float
        Overall completion percentage (0-1).
    int_pct : float
        Interception rate per attempt (0-1).
    grade : str
        Player grade (A+/A/B/C/D).
    n_receivers : int
        Number of receiver letters to distribute completions across (1-5).
    """
    n_int = max(1, round(int_pct * PASS_SLOT_COUNT))
    n_complete = max(0, round(comp_pct * PASS_SLOT_COUNT))
    n_incomplete = PASS_SLOT_COUNT - n_complete - n_int

    if n_incomplete < 0:
        n_complete = PASS_SLOT_COUNT - n_int
        n_incomplete = 0

    # Distribute completions among receiver letters
    # Primary receiver gets more targets; distribution tapers off
    n_receivers = max(1, min(n_receivers, 5))
    result: Dict[str, int] = {}
    remaining_comp = n_complete
    weights = [30, 25, 20, 15, 10][:n_receivers]
    total_w = sum(weights)
    for i in range(n_receivers):
        letter = RECEIVER_LETTERS[i]
        if i < n_receivers - 1:
            count = round(n_complete * weights[i] / total_w)
        else:
            count = remaining_comp  # last receiver gets the remainder
        count = max(0, count)
        result[letter] = count
        remaining_comp -= count

    result["INC"] = n_incomplete
    result["INT"] = n_int
    return result


def qb_long_pass_distribution_5e(
    comp_pct: float,
    int_pct: float,
    grade: str,
    n_receivers: int = 5,
) -> Dict[str, int]:
    """Return slot counts for a 5th-ed QB long-pass column (48 slots).

    Long passes have lower completion and higher interception rates.
    """
    long_comp_pct = comp_pct * 0.55
    long_int_pct = int_pct * 1.5
    return qb_pass_distribution_5e(long_comp_pct, long_int_pct, grade, n_receivers)


def qb_quick_pass_distribution_5e(
    comp_pct: float,
    int_pct: float,
    grade: str,
    n_receivers: int = 5,
) -> Dict[str, int]:
    """Return slot counts for a 5th-ed QB quick-pass column (48 slots).

    Quick passes have higher completion but mostly short-yardage results.
    """
    quick_comp_pct = min(0.95, comp_pct * 1.1)
    quick_int_pct = max(0.01, int_pct * 0.5)
    return qb_pass_distribution_5e(quick_comp_pct, quick_int_pct, grade, n_receivers)


# ──────────────────────────────────────────────────────────────────────
#  5th-Edition RB Run distribution (12 slots)
# ──────────────────────────────────────────────────────────────────────

def rb_run_distribution_5e(
    fumble_rate: float,
    grade: str,
    is_outside: bool = False,
    is_sweep: bool = False,
) -> Dict[str, int]:
    """Return {result_type: slot_count} for a 5th-ed RB run column (12 slots)."""
    n_fumble = max(0, round(fumble_rate * RUN_SLOT_COUNT))
    # Breakaway chance depends on grade
    breakaway_map = {"A+": 1, "A": 1, "B": 1, "C": 0, "D": 0}
    n_breakaway = breakaway_map.get(grade, 0)
    if is_sweep or is_outside:
        n_breakaway = min(n_breakaway + 1, 2)  # sweeps/outside have more big-play potential

    n_gain = RUN_SLOT_COUNT - n_fumble - n_breakaway
    if n_gain < 0:
        n_gain = RUN_SLOT_COUNT - n_fumble
        n_breakaway = 0

    return {
        "GAIN": n_gain,
        "FUMBLE": n_fumble,
        "BREAKAWAY": n_breakaway,
    }


# ──────────────────────────────────────────────────────────────────────
#  5th-Edition WR/TE Reception distribution (48 slots)
# ──────────────────────────────────────────────────────────────────────

def reception_distribution_5e(
    catch_rate: float,
    is_long: bool = False,
) -> Dict[str, int]:
    """Return {result_type: slot_count} for a 5th-ed receiver column (48 slots)."""
    n_catch = round(catch_rate * PASS_SLOT_COUNT)
    n_incomplete = PASS_SLOT_COUNT - n_catch
    return {
        "CATCH": n_catch,
        "INCOMPLETE": n_incomplete,
    }


# ──────────────────────────────────────────────────────────────────────
#  Legacy 64-slot distributions  (kept for backward compatibility)
# ──────────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────
#  QB Short-Pass distribution  (Pass Number → result)
# ──────────────────────────────────────────────────────────────────────

def qb_short_pass_distribution(
    comp_pct: float,
    int_pct: float,
    sack_pct: float,
    grade: str,
) -> Dict[str, int]:
    """Return a dict of {result_type: slot_count} for a QB short-pass column.

    The slot counts are deterministic given the inputs — no randomness.
    """
    n_sack = max(1, round(sack_pct * SLOT_COUNT))
    n_int = max(1, round(int_pct * SLOT_COUNT))
    n_complete = max(0, round(comp_pct * SLOT_COUNT))
    n_incomplete = SLOT_COUNT - n_complete - n_int - n_sack

    if n_incomplete < 0:
        n_complete = SLOT_COUNT - n_int - n_sack
        n_incomplete = 0

    return {
        "COMPLETE": n_complete,
        "INCOMPLETE": n_incomplete,
        "INT": n_int,
        "SACK": n_sack,
    }


# ──────────────────────────────────────────────────────────────────────
#  QB Long-Pass distribution
# ──────────────────────────────────────────────────────────────────────

def qb_long_pass_distribution(
    comp_pct: float,
    int_pct: float,
    grade: str,
) -> Dict[str, int]:
    """Return slot counts for a QB long-pass column."""
    long_comp_pct = comp_pct * 0.55
    n_complete = max(0, round(long_comp_pct * SLOT_COUNT))
    n_int = max(1, round(int_pct * 1.5 * SLOT_COUNT))
    n_incomplete = SLOT_COUNT - n_complete - n_int

    if n_incomplete < 0:
        n_complete = SLOT_COUNT - n_int
        n_incomplete = 0

    return {
        "COMPLETE": n_complete,
        "INCOMPLETE": n_incomplete,
        "INT": n_int,
    }


# ──────────────────────────────────────────────────────────────────────
#  QB Screen-Pass distribution
# ──────────────────────────────────────────────────────────────────────

def qb_screen_pass_distribution(grade: str) -> Dict[str, int]:
    """Return slot counts for a QB screen-pass column."""
    return {
        "COMPLETE": 42,
        "INCOMPLETE": 16,
        "FUMBLE": 3,
        "INT": 3,
    }


# ──────────────────────────────────────────────────────────────────────
#  QB Rush distribution  (Run Number → result)
# ──────────────────────────────────────────────────────────────────────

def qb_rush_distribution(
    rush_ypc: float,
    fumble_rate: float,
    grade: str,
) -> Dict[str, int]:
    """Return slot counts for a QB rush column (new column type)."""
    n_fumble = max(1, round(fumble_rate * SLOT_COUNT))
    n_oob = max(1, round(0.08 * SLOT_COUNT))  # ~5 slots: QB scrambles often OOB
    n_gain = SLOT_COUNT - n_fumble - n_oob

    if n_gain < 0:
        n_gain = SLOT_COUNT - n_fumble
        n_oob = 0

    return {
        "GAIN": n_gain,
        "FUMBLE": n_fumble,
        "OOB": n_oob,
    }


# ──────────────────────────────────────────────────────────────────────
#  RB Run distribution  (Run Number → result, with OOB)
# ──────────────────────────────────────────────────────────────────────

def rb_run_distribution(
    fumble_rate: float,
    grade: str,
    is_outside: bool = False,
) -> Dict[str, int]:
    """Return slot counts for an RB run column with OOB support."""
    n_fumble = max(1, round(fumble_rate * SLOT_COUNT))
    # Outside runs have more OOB potential (sweep, edge)
    oob_rate = 0.06 if is_outside else 0.03
    n_oob = max(1, round(oob_rate * SLOT_COUNT))
    n_gain = SLOT_COUNT - n_fumble - n_oob

    if n_gain < 0:
        n_gain = SLOT_COUNT - n_fumble
        n_oob = 0

    return {
        "GAIN": n_gain,
        "FUMBLE": n_fumble,
        "OOB": n_oob,
    }


# ──────────────────────────────────────────────────────────────────────
#  WR / TE Reception distribution  (Pass Number → result)
# ──────────────────────────────────────────────────────────────────────

def reception_distribution(
    catch_rate: float,
    is_long: bool = False,
) -> Dict[str, int]:
    """Return slot counts for a receiver card column."""
    n_catch = round(catch_rate * SLOT_COUNT)
    n_incomplete = SLOT_COUNT - n_catch
    return {
        "CATCH": n_catch,
        "INCOMPLETE": n_incomplete,
    }


# ──────────────────────────────────────────────────────────────────────
#  Punter distribution  (Run Number → distance slot)
# ──────────────────────────────────────────────────────────────────────

def punter_distribution(avg_distance: float, inside_20_rate: float) -> Dict[str, int]:
    """Return slot counts for a punter slot-based card column."""
    n_inside_20 = max(1, round(inside_20_rate * SLOT_COUNT))
    n_touchback = max(1, round(0.08 * SLOT_COUNT))  # ~5 slots
    n_normal = SLOT_COUNT - n_inside_20 - n_touchback

    if n_normal < 0:
        n_normal = SLOT_COUNT - n_inside_20
        n_touchback = 0

    return {
        "NORMAL": n_normal,
        "INSIDE_20": n_inside_20,
        "TOUCHBACK": n_touchback,
    }


# ──────────────────────────────────────────────────────────────────────
#  Yardage pools by grade  (deterministic tables, no randomness)
# ──────────────────────────────────────────────────────────────────────

SHORT_PASS_YARDS: Dict[str, Tuple[List[int], List[int]]] = {
    "A+": ([4, 5, 6, 7, 8, 9, 10, 12, 14, 16, 18, 20],
           [5, 8, 10, 12, 12, 10, 8, 6, 5, 5, 4, 3]),
    "A":  ([4, 5, 6, 7, 8, 9, 10, 12, 14, 16, 18, 20],
           [5, 8, 10, 12, 12, 10, 8, 6, 5, 5, 4, 3]),
    "B":  ([3, 4, 5, 6, 7, 8, 9, 10, 12, 14],
           [5, 8, 12, 12, 10, 10, 8, 6, 5, 4]),
    "C":  ([2, 3, 4, 5, 6, 7, 8, 10, 12],
           [6, 8, 12, 12, 12, 10, 8, 5, 3]),
    "D":  ([1, 2, 3, 4, 5, 6, 7, 8],
           [8, 10, 12, 12, 10, 8, 6, 4]),
}

LONG_PASS_YARDS: Dict[str, Tuple[List[int], List[int]]] = {
    "A+": ([15, 18, 20, 22, 25, 28, 30, 35, 40, 45, 50],
           [8, 10, 12, 12, 10, 8, 8, 6, 5, 3, 2]),
    "A":  ([15, 18, 20, 22, 25, 28, 30, 35, 40, 45, 50],
           [8, 10, 12, 12, 10, 8, 8, 6, 5, 3, 2]),
    "B":  ([15, 18, 20, 22, 25, 28, 30, 35, 40],
           [10, 12, 12, 12, 10, 8, 6, 4, 2]),
    "C":  ([15, 18, 20, 22, 25, 28, 30],
           [12, 14, 14, 12, 10, 8, 6]),
    "D":  ([15, 18, 20, 22, 25, 28, 30],
           [12, 14, 14, 12, 10, 8, 6]),
}

SCREEN_PASS_YARDS: Dict[str, Tuple[List[int], List[int]]] = {
    "A+": ([3, 4, 5, 6, 7, 8, 10, 12, 15],
           [8, 12, 14, 14, 12, 10, 8, 5, 3]),
    "A":  ([3, 4, 5, 6, 7, 8, 10, 12, 15],
           [8, 12, 14, 14, 12, 10, 8, 5, 3]),
    "B":  ([1, 2, 3, 4, 5, 6, 7, 8, 10],
           [8, 10, 14, 14, 12, 10, 8, 5, 3]),
    "C":  ([1, 2, 3, 4, 5, 6, 7, 8, 10],
           [8, 10, 14, 14, 12, 10, 8, 5, 3]),
    "D":  ([1, 2, 3, 4, 5, 6, 7, 8, 10],
           [8, 10, 14, 14, 12, 10, 8, 5, 3]),
}

# RB Inside-Run yardage pools
INSIDE_RUN_YARDS: Dict[str, Tuple[List[int], List[int]]] = {
    "A+": ([-1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 15],
           [2, 3, 5, 8, 12, 14, 12, 10, 8, 6, 5, 3, 2]),
    "A":  ([-1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 15],
           [2, 3, 5, 8, 12, 14, 12, 10, 8, 6, 5, 3, 2]),
    "B":  ([-1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 10],
           [3, 5, 7, 10, 12, 12, 10, 8, 6, 5, 4]),
    "C":  ([-2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8],
           [3, 5, 8, 10, 12, 12, 10, 8, 6, 4, 3]),
    "D":  ([-3, -2, -1, 0, 1, 2, 3, 4, 5, 6],
           [4, 6, 8, 10, 12, 12, 10, 8, 6, 4]),
}

# RB Outside-Run yardage pools
OUTSIDE_RUN_YARDS: Dict[str, Tuple[List[int], List[int]]] = {
    "A+": ([-2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 15, 20],
           [2, 2, 3, 4, 6, 8, 10, 12, 12, 8, 6, 5, 4, 3, 2]),
    "A":  ([-2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 15, 20],
           [2, 2, 3, 4, 6, 8, 10, 12, 12, 8, 6, 5, 4, 3, 2]),
    "B":  ([-2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12],
           [3, 3, 5, 6, 8, 10, 12, 10, 8, 6, 5, 4, 3]),
    "C":  ([-2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8],
           [4, 5, 7, 8, 10, 12, 12, 10, 8, 5, 4]),
    "D":  ([-3, -2, -1, 0, 1, 2, 3, 4, 5, 6],
           [5, 7, 8, 10, 12, 12, 10, 8, 5, 3]),
}

# QB Rush yardage pools
QB_RUSH_YARDS: Dict[str, Tuple[List[int], List[int]]] = {
    "A+": ([-1, 0, 1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20],
           [2, 3, 4, 6, 8, 10, 12, 12, 10, 8, 6, 3, 2]),
    "A":  ([-1, 0, 1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20],
           [2, 3, 4, 6, 8, 10, 12, 12, 10, 8, 6, 3, 2]),
    "B":  ([-1, 0, 1, 2, 3, 4, 5, 6, 7, 8],
           [4, 6, 8, 10, 12, 14, 12, 10, 6, 4]),
    "C":  ([-2, -1, 0, 1, 2, 3, 4, 5, 6],
           [5, 8, 10, 12, 14, 14, 12, 8, 5]),
    "D":  ([-3, -2, -1, 0, 1, 2, 3, 4],
           [6, 8, 12, 14, 14, 12, 8, 6]),
}

# Short reception yardage pools
SHORT_RECEPTION_YARDS: Dict[str, Tuple[List[int], List[int]]] = {
    "A+": ([4, 5, 6, 7, 8, 9, 10, 12, 14],
           [5, 8, 12, 14, 14, 12, 10, 8, 5]),
    "A":  ([4, 5, 6, 7, 8, 9, 10, 12, 14],
           [5, 8, 12, 14, 14, 12, 10, 8, 5]),
    "B":  ([3, 4, 5, 6, 7, 8, 9, 10, 12],
           [5, 8, 12, 14, 14, 12, 10, 8, 4]),
    "C":  ([2, 3, 4, 5, 6, 7, 8, 9, 10],
           [6, 8, 12, 14, 14, 12, 10, 7, 4]),
    "D":  ([1, 2, 3, 4, 5, 6, 7, 8],
           [8, 10, 14, 14, 14, 12, 8, 4]),
}

# Long reception yardage pools
LONG_RECEPTION_YARDS: Dict[str, Tuple[List[int], List[int]]] = {
    "A+": ([15, 18, 20, 22, 25, 28, 30, 35, 40, 45],
           [8, 10, 12, 12, 10, 8, 8, 6, 4, 2]),
    "A":  ([15, 18, 20, 22, 25, 28, 30, 35, 40, 45],
           [8, 10, 12, 12, 10, 8, 8, 6, 4, 2]),
    "B":  ([15, 18, 20, 22, 25, 28, 30, 35],
           [10, 12, 14, 14, 12, 10, 6, 4]),
    "C":  ([15, 18, 20, 22, 25, 28],
           [14, 16, 16, 14, 12, 8]),
    "D":  ([15, 18, 20, 22, 25, 28],
           [14, 16, 16, 14, 12, 8]),
}

# OOB yardage pools — used when a run result is OOB
OOB_RUN_YARDS: Dict[str, Tuple[List[int], List[int]]] = {
    "A+": ([1, 2, 3, 4, 5, 6, 7, 8],
           [5, 8, 12, 14, 14, 12, 8, 5]),
    "A":  ([1, 2, 3, 4, 5, 6, 7, 8],
           [5, 8, 12, 14, 14, 12, 8, 5]),
    "B":  ([0, 1, 2, 3, 4, 5, 6],
           [6, 10, 14, 16, 14, 10, 6]),
    "C":  ([0, 1, 2, 3, 4, 5],
           [8, 12, 16, 16, 12, 8]),
    "D":  ([-1, 0, 1, 2, 3, 4],
           [8, 14, 18, 18, 14, 8]),
}

# Punter yardage pools for NORMAL results
PUNT_YARDS: Dict[str, Tuple[List[int], List[int]]] = {
    "A+": ([40, 42, 44, 46, 48, 50, 52, 55, 58, 60],
           [4, 6, 10, 14, 16, 14, 12, 8, 4, 2]),
    "A":  ([40, 42, 44, 46, 48, 50, 52, 55, 58, 60],
           [4, 6, 10, 14, 16, 14, 12, 8, 4, 2]),
    "B":  ([38, 40, 42, 44, 46, 48, 50, 52],
           [5, 8, 12, 16, 16, 14, 10, 6]),
    "C":  ([36, 38, 40, 42, 44, 46, 48],
           [6, 10, 14, 18, 18, 14, 8]),
    "D":  ([34, 36, 38, 40, 42, 44],
           [8, 12, 18, 22, 18, 10]),
}

# Sack yards (negative) — same for all grades
SACK_YARDS: Tuple[List[int], List[int]] = (
    [-3, -4, -5, -6, -7, -8],
    [15, 20, 25, 20, 12, 8],
)


def get_yards_pool(table: Dict[str, Tuple[List[int], List[int]]],
                   grade: str) -> Tuple[List[int], List[int]]:
    """Look up a (values, weights) tuple from a yardage table by grade.

    Falls back through grade tiers if the exact grade isn't present.
    """
    if grade in table:
        return table[grade]
    # Fallback chain
    fallbacks = {"A+": "A", "A": "B", "B": "C", "C": "D", "D": "D"}
    return table.get(fallbacks.get(grade, "C"), list(table.values())[-1])


# ──────────────────────────────────────────────────────────────────────
#  Z-Card System
# ──────────────────────────────────────────────────────────────────────

class ZCardTrigger:
    """Determines when a Z-card event should fire."""

    # Dice combos that trigger Z-card check
    Z_CARD_COMBOS = {(1, 1), (2, 8), (4, 7), (6, 1), (8, 5)}

    # Situational triggers: certain game situations also activate Z-cards
    @staticmethod
    def is_triggered(tens: int, ones: int,
                     down: int = 0, distance: int = 0,
                     yard_line: int = 0, quarter: int = 0,
                     time_remaining: int = 900) -> bool:
        """Return True if a Z-card event should be checked."""
        # Dice-based trigger
        if (tens, ones) in ZCardTrigger.Z_CARD_COMBOS:
            return True
        # Red zone trigger (inside opponent 20)
        if yard_line >= 80 and down >= 3:
            return (tens, ones) in {(3, 3), (5, 5), (7, 7)}
        # 3rd-and-long trigger
        if down == 3 and distance >= 10:
            return (tens, ones) in {(2, 2), (4, 4), (6, 6), (8, 8)}
        # Late-game pressure (Q4, under 2 min)
        if quarter == 4 and time_remaining <= 120:
            return (tens, ones) in {(1, 8), (8, 1)}
        return False


# Z-card event tables — keyed by a second dice roll (11-88)
# Each event is: {"event": str, "effect": str, "yards": int, "turnover": bool}
Z_CARD_OFFENSE_EVENTS = {
    "11": {"event": "BREAKAWAY_RUN",     "effect": "Big gain on run play",        "yards": 25, "turnover": False},
    "12": {"event": "SCREEN_BUST",       "effect": "Screen play goes for big yds", "yards": 20, "turnover": False},
    "13": {"event": "QB_DRAW",           "effect": "QB keeper for nice gain",      "yards": 12, "turnover": False},
    "14": {"event": "TIPPED_PASS_CATCH", "effect": "Tipped ball caught anyway",    "yards": 15, "turnover": False},
    "15": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "16": {"event": "PENALTY_BOOST",     "effect": "Defensive penalty adds yards", "yards": 15, "turnover": False},
    "17": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "18": {"event": "FUMBLE_SNAP",       "effect": "Bad snap, fumble",             "yards": -5, "turnover": True},
    "21": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "22": {"event": "REVERSE_PLAY",      "effect": "Reverse for big gain",         "yards": 18, "turnover": False},
    "23": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "24": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "25": {"event": "STRIP_SACK",        "effect": "QB stripped, fumble",          "yards": -8, "turnover": True},
    "26": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "27": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "28": {"event": "PLAY_ACTION_BOMB",  "effect": "Play action deep completion",  "yards": 35, "turnover": False},
    "31": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "32": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "33": {"event": "QB_SCRAMBLE",       "effect": "QB scrambles for first down",  "yards": 10, "turnover": False},
    "34": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "35": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "36": {"event": "HOLDING_NEGATED",   "effect": "Big play negated by hold",     "yards": -10, "turnover": False},
    "37": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "38": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "41": {"event": "SHOVEL_PASS",       "effect": "Shovel pass for gain",         "yards": 8,  "turnover": False},
    "42": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "43": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "44": {"event": "END_AROUND",        "effect": "WR end around",               "yards": 14, "turnover": False},
    "45": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "46": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "47": {"event": "TIPPED_INT",        "effect": "Tipped pass intercepted",      "yards": 0,  "turnover": True},
    "48": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "51": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "52": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "53": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "54": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "55": {"event": "BROKEN_PLAY_TD",    "effect": "Broken play turns into TD",    "yards": 50, "turnover": False},
    "56": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "57": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "58": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "61": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "62": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "63": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "64": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "65": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "66": {"event": "HAIL_MARY",         "effect": "Hail Mary caught!",            "yards": 45, "turnover": False},
    "67": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "68": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "71": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "72": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "73": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "74": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "75": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "76": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "77": {"event": "SAFETY",            "effect": "Safety! Ball in end zone",     "yards": 0,  "turnover": False},
    "78": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "81": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "82": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "83": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "84": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "85": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "86": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "87": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "88": {"event": "BLOCKED_PUNT_TD",   "effect": "Blocked punt returned for TD", "yards": 0,  "turnover": True},
}

Z_CARD_DEFENSE_EVENTS = {
    "11": {"event": "FORCED_FUMBLE",     "effect": "Big hit forces fumble",        "yards": 0,  "turnover": True},
    "12": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "13": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "14": {"event": "COVERAGE_SACK",     "effect": "Coverage sack",               "yards": -7, "turnover": False},
    "15": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "16": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "17": {"event": "TIPPED_BALL_INT",   "effect": "Tipped ball intercepted",      "yards": 0,  "turnover": True},
    "18": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "21": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "22": {"event": "PICK_SIX",          "effect": "Interception returned for TD", "yards": -40, "turnover": True},
    "23": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "24": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "25": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "26": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "27": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "28": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "31": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "32": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "33": {"event": "FUMBLE_RECOVERY_TD","effect": "Fumble recovery returned TD",  "yards": 0,  "turnover": True},
    "34": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "35": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "36": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "37": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "38": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "41": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "42": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "43": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "44": {"event": "SAFETY",            "effect": "Safety! Defense scores",       "yards": 0,  "turnover": False},
    "45": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "46": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "47": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "48": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "51": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "52": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "53": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "54": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "55": {"event": "BLOCKED_FG",        "effect": "Field goal blocked!",          "yards": 0,  "turnover": True},
    "56": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "57": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "58": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "61": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "62": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "63": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "64": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "65": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "66": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "67": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "68": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "71": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "72": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "73": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "74": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "75": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "76": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "77": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "78": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "81": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "82": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "83": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "84": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "85": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "86": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "87": {"event": "NO_EFFECT",         "effect": "No special event",             "yards": 0,  "turnover": False},
    "88": {"event": "BLOCKED_PUNT",      "effect": "Punt blocked!",               "yards": 0,  "turnover": True},
}


def lookup_z_card_event(tens: int, ones: int, is_offense: bool = True) -> Dict[str, Any]:
    """Look up a Z-card event from the appropriate table."""
    key = f"{tens}{ones}"
    table = Z_CARD_OFFENSE_EVENTS if is_offense else Z_CARD_DEFENSE_EVENTS
    return table.get(key, {"event": "NO_EFFECT", "effect": "No special event",
                           "yards": 0, "turnover": False})


# ──────────────────────────────────────────────────────────────────────
#  Pass Number / Run Number concepts
# ──────────────────────────────────────────────────────────────────────

def pass_number(tens: int, ones: int) -> int:
    """Derive the Pass Number from a dice roll.

    In the FAC system the PN is the same two-digit number used for
    QB card column lookups.
    """
    return tens * 10 + ones


def run_number(tens: int, ones: int) -> int:
    """Derive the Run Number from a dice roll.

    The RN is used for rusher card lookups and for the second-stage
    receiver yardage lookup on completions.
    """
    return tens * 10 + ones


# ──────────────────────────────────────────────────────────────────────
#  Defense modifiers
# ──────────────────────────────────────────────────────────────────────

# Formation modifiers: {formation: {pass_rush_mod, coverage_mod, run_stop_mod}}
FORMATION_MODIFIERS: Dict[str, Dict[str, int]] = {
    "4_3":          {"pass_rush": 0,  "coverage": 0,  "run_stop": 0},
    "3_4":          {"pass_rush": 0,  "coverage": 0,  "run_stop": 0},
    "4_3_COVER2":   {"pass_rush": 0,  "coverage": 1,  "run_stop": 0},
    "3_4_ZONE":     {"pass_rush": 0,  "coverage": 1,  "run_stop": 0},
    "4_3_BLITZ":    {"pass_rush": 1,  "coverage": -1, "run_stop": 0},
    "NICKEL_ZONE":  {"pass_rush": 0,  "coverage": 1,  "run_stop": -1},
    "NICKEL_BLITZ": {"pass_rush": 1,  "coverage": 0,  "run_stop": 0},
    "NICKEL_COVER2":{"pass_rush": 0,  "coverage": 1,  "run_stop": 0},
    "GOAL_LINE":    {"pass_rush": 0,  "coverage": -1, "run_stop": 1},
}

# 5E Defensive Play modifiers (keyed by DefensivePlay enum values)
DEFENSIVE_PLAY_MODIFIERS: Dict[str, Dict[str, int]] = {
    "PASS_DEFENSE":          {"pass_rush": 0,  "coverage": 1,  "run_stop": 0},
    "PREVENT_DEFENSE":       {"pass_rush": 0,  "coverage": 1,  "run_stop": -1},
    "RUN_DEFENSE_NO_KEY":    {"pass_rush": 0,  "coverage": 0,  "run_stop": 1},
    "RUN_DEFENSE_KEY_BACK_1":{"pass_rush": 0,  "coverage": 0,  "run_stop": 1},
    "RUN_DEFENSE_KEY_BACK_2":{"pass_rush": 0,  "coverage": 0,  "run_stop": 1},
    "RUN_DEFENSE_KEY_BACK_3":{"pass_rush": 0,  "coverage": 0,  "run_stop": 1},
    "BLITZ":                 {"pass_rush": 1,  "coverage": -1, "run_stop": 0},
}


def get_formation_modifier(formation: str) -> Dict[str, int]:
    """Return the {pass_rush, coverage, run_stop} modifier for a formation."""
    return FORMATION_MODIFIERS.get(formation, {"pass_rush": 0, "coverage": 0, "run_stop": 0})


def get_defensive_play_modifier(defensive_play: str) -> Dict[str, int]:
    """Return the {pass_rush, coverage, run_stop} modifier for a 5E defensive play."""
    return DEFENSIVE_PLAY_MODIFIERS.get(defensive_play, {"pass_rush": 0, "coverage": 0, "run_stop": 0})


def effective_pass_rush(base_rating: int, formation: str,
                        is_blitz_tendency: bool = False) -> int:
    """Compute effective pass-rush rating with formation + blitz bonus.

    Uses authentic 5E small-number scale (0-3 base + modifiers).
    """
    mod = get_formation_modifier(formation)
    rating = base_rating + mod["pass_rush"]
    if is_blitz_tendency:
        rating += 1  # Blitz tendency adds +1 pass rush
    return max(0, rating)


def effective_coverage(base_rating: int, formation: str,
                       is_blitz_tendency: bool = False) -> int:
    """Compute effective coverage (pass defense) rating with formation + blitz penalty.

    Uses authentic 5E small-number scale (−2 to +4 base + modifiers).
    """
    mod = get_formation_modifier(formation)
    rating = base_rating + mod["coverage"]
    if is_blitz_tendency:
        rating -= 1  # Blitzing weakens coverage by 1
    return rating


def effective_run_stop(base_rating: int, formation: str) -> int:
    """Compute effective run-stop (tackle) rating with formation modifier.

    Uses authentic 5E small-number scale (−5 to +4 base + modifiers).
    """
    mod = get_formation_modifier(formation)
    return base_rating + mod["run_stop"]
