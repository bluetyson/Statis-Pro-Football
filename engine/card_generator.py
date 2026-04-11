"""Card generator for Statis Pro Football player cards."""
import random
from typing import Dict, Any, List
from .player_card import PlayerCard


def _all_slots() -> List[str]:
    return [f"{t}{o}" for t in range(1, 9) for o in range(1, 9)]


def _distribute_results(slot_assignments: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Map a list of 64 result dicts to slot keys."""
    slots = _all_slots()
    assert len(slot_assignments) == 64, f"Expected 64 slots, got {len(slot_assignments)}"
    return {slot: result for slot, result in zip(slots, slot_assignments)}


def _make_qb_short_pass(comp_pct: float, int_pct: float, sack_pct: float, grade: str) -> Dict[str, Any]:
    n_complete = round(comp_pct * 64)
    n_int = max(1, round(int_pct * 64))
    n_sack = max(1, round(sack_pct * 64))
    n_incomplete = 64 - n_complete - n_int - n_sack
    if n_incomplete < 0:
        n_complete = 64 - n_int - n_sack
        n_incomplete = 0

    if grade in ("A+", "A"):
        yards_pool = [4, 5, 6, 7, 8, 9, 10, 12, 14, 16, 18, 20]
        weights = [5, 8, 10, 12, 12, 10, 8, 6, 5, 5, 4, 3]
    elif grade == "B":
        yards_pool = [3, 4, 5, 6, 7, 8, 9, 10, 12, 14]
        weights = [5, 8, 12, 12, 10, 10, 8, 6, 5, 4]
    elif grade == "C":
        yards_pool = [2, 3, 4, 5, 6, 7, 8, 10, 12]
        weights = [6, 8, 12, 12, 12, 10, 8, 5, 3]
    else:
        yards_pool = [1, 2, 3, 4, 5, 6, 7, 8]
        weights = [8, 10, 12, 12, 10, 8, 6, 4]

    results = []
    for _ in range(n_complete):
        yds = random.choices(yards_pool, weights=weights)[0]
        td = random.random() < 0.04
        results.append({"result": "COMPLETE", "yards": yds, "td": td})
    for _ in range(n_incomplete):
        results.append({"result": "INCOMPLETE", "yards": 0, "td": False})
    for _ in range(n_int):
        results.append({"result": "INT", "yards": 0, "td": False})
    for _ in range(n_sack):
        loss = random.choice([-3, -4, -5, -6, -7, -8])
        results.append({"result": "SACK", "yards": loss, "td": False})

    random.shuffle(results)
    return _distribute_results(results)


def _make_qb_long_pass(comp_pct: float, int_pct: float, grade: str) -> Dict[str, Any]:
    long_comp = comp_pct * 0.55
    n_complete = round(long_comp * 64)
    n_int = max(1, round(int_pct * 1.5 * 64))
    n_incomplete = 64 - n_complete - n_int
    if n_incomplete < 0:
        n_complete = 64 - n_int
        n_incomplete = 0

    if grade in ("A+", "A"):
        yards_pool = [15, 18, 20, 22, 25, 28, 30, 35, 40, 45, 50]
        weights = [8, 10, 12, 12, 10, 8, 8, 6, 5, 3, 2]
    elif grade == "B":
        yards_pool = [15, 18, 20, 22, 25, 28, 30, 35, 40]
        weights = [10, 12, 12, 12, 10, 8, 6, 4, 2]
    else:
        yards_pool = [15, 18, 20, 22, 25, 28, 30]
        weights = [12, 14, 14, 12, 10, 8, 6]

    results = []
    for _ in range(n_complete):
        yds = random.choices(yards_pool, weights=weights)[0]
        td = random.random() < 0.08
        results.append({"result": "COMPLETE", "yards": yds, "td": td})
    for _ in range(n_incomplete):
        results.append({"result": "INCOMPLETE", "yards": 0, "td": False})
    for _ in range(n_int):
        results.append({"result": "INT", "yards": 0, "td": False})

    random.shuffle(results)
    return _distribute_results(results)


def _make_qb_screen_pass(grade: str) -> Dict[str, Any]:
    n_complete = 42
    n_incomplete = 16
    n_fumble = 3
    n_int = 3

    if grade in ("A+", "A"):
        yards_pool = [3, 4, 5, 6, 7, 8, 10, 12, 15]
        weights = [8, 12, 14, 14, 12, 10, 8, 5, 3]
    else:
        yards_pool = [1, 2, 3, 4, 5, 6, 7, 8, 10]
        weights = [8, 10, 14, 14, 12, 10, 8, 5, 3]

    results = []
    for _ in range(n_complete):
        yds = random.choices(yards_pool, weights=weights)[0]
        td = random.random() < 0.03
        results.append({"result": "COMPLETE", "yards": yds, "td": td})
    for _ in range(n_incomplete):
        results.append({"result": "INCOMPLETE", "yards": 0, "td": False})
    for _ in range(n_fumble):
        results.append({"result": "FUMBLE", "yards": 0, "td": False})
    for _ in range(n_int):
        results.append({"result": "INT", "yards": 0, "td": False})

    random.shuffle(results)
    return _distribute_results(results)


def _make_rb_inside_run(ypc: float, fumble_rate: float, grade: str) -> Dict[str, Any]:
    n_fumble = max(1, round(fumble_rate * 64))

    if grade in ("A+", "A"):
        yards_pool = [-1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 15]
        weights = [2, 3, 5, 8, 12, 14, 12, 10, 8, 6, 5, 3, 2]
    elif grade == "B":
        yards_pool = [-1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 10]
        weights = [3, 5, 7, 10, 12, 12, 10, 8, 6, 5, 4]
    elif grade == "C":
        yards_pool = [-2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8]
        weights = [3, 5, 8, 10, 12, 12, 10, 8, 6, 4, 3]
    else:
        yards_pool = [-3, -2, -1, 0, 1, 2, 3, 4, 5, 6]
        weights = [4, 6, 8, 10, 12, 12, 10, 8, 6, 4]

    n_regular = 64 - n_fumble
    results = []
    for _ in range(n_regular):
        yds = random.choices(yards_pool, weights=weights)[0]
        td = random.random() < 0.03
        results.append({"result": "GAIN", "yards": yds, "td": td})
    for _ in range(n_fumble):
        results.append({"result": "FUMBLE", "yards": 0, "td": False})

    random.shuffle(results)
    return _distribute_results(results)


def _make_rb_outside_run(ypc: float, fumble_rate: float, grade: str) -> Dict[str, Any]:
    n_fumble = max(1, round(fumble_rate * 64))

    if grade in ("A+", "A"):
        yards_pool = [-2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 15, 20]
        weights = [2, 2, 3, 4, 6, 8, 10, 12, 12, 8, 6, 5, 4, 3, 2]
    elif grade == "B":
        yards_pool = [-2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12]
        weights = [3, 3, 5, 6, 8, 10, 12, 10, 8, 6, 5, 4, 3]
    elif grade == "C":
        yards_pool = [-2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8]
        weights = [4, 5, 7, 8, 10, 12, 12, 10, 8, 5, 4]
    else:
        yards_pool = [-3, -2, -1, 0, 1, 2, 3, 4, 5, 6]
        weights = [5, 7, 8, 10, 12, 12, 10, 8, 5, 3]

    n_regular = 64 - n_fumble
    results = []
    for _ in range(n_regular):
        yds = random.choices(yards_pool, weights=weights)[0]
        td = random.random() < 0.04
        results.append({"result": "GAIN", "yards": yds, "td": td})
    for _ in range(n_fumble):
        results.append({"result": "FUMBLE", "yards": 0, "td": False})

    random.shuffle(results)
    return _distribute_results(results)


def _make_wr_reception(catch_rate: float, avg_yards: float, grade: str, is_long: bool = False) -> Dict[str, Any]:
    n_catch = round(catch_rate * 64)
    n_drop = 64 - n_catch

    if is_long:
        if grade in ("A+", "A"):
            yards_pool = [15, 18, 20, 22, 25, 28, 30, 35, 40, 45]
            weights = [8, 10, 12, 12, 10, 8, 8, 6, 4, 2]
        elif grade == "B":
            yards_pool = [15, 18, 20, 22, 25, 28, 30, 35]
            weights = [10, 12, 14, 14, 12, 10, 6, 4]
        else:
            yards_pool = [15, 18, 20, 22, 25, 28]
            weights = [14, 16, 16, 14, 12, 8]
    else:
        if grade in ("A+", "A"):
            yards_pool = [4, 5, 6, 7, 8, 9, 10, 12, 14]
            weights = [5, 8, 12, 14, 14, 12, 10, 8, 5]
        elif grade == "B":
            yards_pool = [3, 4, 5, 6, 7, 8, 9, 10, 12]
            weights = [5, 8, 12, 14, 14, 12, 10, 8, 4]
        elif grade == "C":
            yards_pool = [2, 3, 4, 5, 6, 7, 8, 9, 10]
            weights = [6, 8, 12, 14, 14, 12, 10, 7, 4]
        else:
            yards_pool = [1, 2, 3, 4, 5, 6, 7, 8]
            weights = [8, 10, 14, 14, 14, 12, 8, 4]

    results = []
    for _ in range(n_catch):
        yds = random.choices(yards_pool, weights=weights)[0]
        td = random.random() < (0.06 if is_long else 0.04)
        results.append({"result": "CATCH", "yards": yds, "td": td})
    for _ in range(n_drop):
        results.append({"result": "INCOMPLETE", "yards": 0, "td": False})

    random.shuffle(results)
    return _distribute_results(results)


def _make_kicker_fg_chart(accuracy: float, grade: str) -> Dict[str, float]:
    return {
        "0-19": min(1.0, accuracy + 0.15),
        "20-29": min(1.0, accuracy + 0.10),
        "30-39": min(1.0, accuracy + 0.05),
        "40-49": accuracy,
        "50-59": max(0.0, accuracy - 0.15),
        "60+": max(0.0, accuracy - 0.30),
    }


class CardGenerator:
    """Generates player cards from raw stats."""

    def __init__(self, seed: int = None):
        if seed is not None:
            random.seed(seed)

    def generate_qb_card(self, name: str, team: str, number: int,
                         comp_pct: float, ypa: float, int_rate: float,
                         sack_rate: float, grade: str) -> PlayerCard:
        card = PlayerCard(
            player_name=name, team=team, position="QB",
            number=number, overall_grade=grade
        )
        card.short_pass = _make_qb_short_pass(comp_pct, int_rate, sack_rate, grade)
        card.long_pass = _make_qb_long_pass(comp_pct, int_rate, grade)
        card.screen_pass = _make_qb_screen_pass(grade)
        card.stats_summary = {
            "comp_pct": comp_pct, "ypa": ypa,
            "int_rate": int_rate, "sack_rate": sack_rate
        }
        return card

    def generate_rb_card(self, name: str, team: str, number: int,
                         ypc: float, fumble_rate: float, grade: str) -> PlayerCard:
        card = PlayerCard(
            player_name=name, team=team, position="RB",
            number=number, overall_grade=grade
        )
        card.inside_run = _make_rb_inside_run(ypc, fumble_rate, grade)
        card.outside_run = _make_rb_outside_run(ypc, fumble_rate, grade)
        card.stats_summary = {"ypc": ypc, "fumble_rate": fumble_rate}
        return card

    def generate_wr_card(self, name: str, team: str, number: int,
                         catch_rate: float, avg_yards: float, grade: str) -> PlayerCard:
        card = PlayerCard(
            player_name=name, team=team, position="WR",
            number=number, overall_grade=grade
        )
        card.short_reception = _make_wr_reception(catch_rate, avg_yards, grade, is_long=False)
        card.long_reception = _make_wr_reception(catch_rate * 0.7, avg_yards, grade, is_long=True)
        card.stats_summary = {"catch_rate": catch_rate, "avg_yards": avg_yards}
        return card

    def generate_te_card(self, name: str, team: str, number: int,
                         catch_rate: float, avg_yards: float, grade: str) -> PlayerCard:
        card = PlayerCard(
            player_name=name, team=team, position="TE",
            number=number, overall_grade=grade
        )
        card.short_reception = _make_wr_reception(catch_rate, avg_yards, grade, is_long=False)
        card.long_reception = _make_wr_reception(catch_rate * 0.6, avg_yards, grade, is_long=True)
        card.stats_summary = {"catch_rate": catch_rate, "avg_yards": avg_yards}
        return card

    def generate_k_card(self, name: str, team: str, number: int,
                        accuracy: float, xp_rate: float, grade: str) -> PlayerCard:
        card = PlayerCard(
            player_name=name, team=team, position="K",
            number=number, overall_grade=grade
        )
        card.fg_chart = _make_kicker_fg_chart(accuracy, grade)
        card.xp_rate = xp_rate
        card.stats_summary = {"accuracy": accuracy, "xp_rate": xp_rate}
        return card

    def generate_p_card(self, name: str, team: str, number: int,
                        avg_distance: float, inside_20_rate: float, grade: str) -> PlayerCard:
        card = PlayerCard(
            player_name=name, team=team, position="P",
            number=number, overall_grade=grade
        )
        card.avg_distance = avg_distance
        card.inside_20_rate = inside_20_rate
        card.stats_summary = {"avg_distance": avg_distance, "inside_20_rate": inside_20_rate}
        return card

    def generate_def_card(self, name: str, team: str, number: int, position: str,
                          pass_rush: int, coverage: int, run_stop: int, grade: str) -> PlayerCard:
        card = PlayerCard(
            player_name=name, team=team, position=position,
            number=number, overall_grade=grade
        )
        card.pass_rush_rating = pass_rush
        card.coverage_rating = coverage
        card.run_stop_rating = run_stop
        card.stats_summary = {
            "pass_rush_rating": pass_rush,
            "coverage_rating": coverage,
            "run_stop_rating": run_stop,
        }
        return card
