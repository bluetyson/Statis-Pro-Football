"""Card generator for Statis Pro Football player cards.

Uses FAC distribution tables from ``fac_distributions`` to determine the
fixed number of slots per outcome type, then fills yardage values from
grade-appropriate pools.
"""
import random
from typing import Dict, Any, List, Tuple

from .player_card import PlayerCard
from .fac_distributions import (
    all_slots, SLOT_COUNT,
    qb_short_pass_distribution, qb_long_pass_distribution,
    qb_screen_pass_distribution, qb_rush_distribution,
    rb_run_distribution, reception_distribution,
    punter_distribution,
    get_yards_pool,
    SHORT_PASS_YARDS, LONG_PASS_YARDS, SCREEN_PASS_YARDS,
    INSIDE_RUN_YARDS, OUTSIDE_RUN_YARDS, QB_RUSH_YARDS,
    SHORT_RECEPTION_YARDS, LONG_RECEPTION_YARDS,
    OOB_RUN_YARDS, PUNT_YARDS, SACK_YARDS,
)


# ── helpers ──────────────────────────────────────────────────────────

def _all_slots() -> List[str]:
    return all_slots()


def _distribute_results(slot_assignments: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Map a list of 64 result dicts to slot keys."""
    slots = _all_slots()
    assert len(slot_assignments) == SLOT_COUNT, f"Expected {SLOT_COUNT} slots, got {len(slot_assignments)}"
    return {slot: result for slot, result in zip(slots, slot_assignments)}


def _pick_yards(pool: List[int], weights: List[int]) -> int:
    return random.choices(pool, weights=weights)[0]


# ── QB columns ───────────────────────────────────────────────────────

def _make_qb_short_pass(comp_pct: float, int_pct: float,
                         sack_pct: float, grade: str) -> Dict[str, Any]:
    dist = qb_short_pass_distribution(comp_pct, int_pct, sack_pct, grade)
    pool, weights = get_yards_pool(SHORT_PASS_YARDS, grade)
    sack_pool, sack_weights = SACK_YARDS

    results: List[Dict[str, Any]] = []
    for _ in range(dist["COMPLETE"]):
        yds = _pick_yards(pool, weights)
        results.append({"result": "COMPLETE", "yards": yds, "td": random.random() < 0.04})
    for _ in range(dist["INCOMPLETE"]):
        results.append({"result": "INCOMPLETE", "yards": 0, "td": False})
    for _ in range(dist["INT"]):
        results.append({"result": "INT", "yards": 0, "td": False})
    for _ in range(dist["SACK"]):
        results.append({"result": "SACK", "yards": _pick_yards(sack_pool, sack_weights), "td": False})

    random.shuffle(results)
    return _distribute_results(results)


def _make_qb_long_pass(comp_pct: float, int_pct: float,
                        grade: str) -> Dict[str, Any]:
    dist = qb_long_pass_distribution(comp_pct, int_pct, grade)
    pool, weights = get_yards_pool(LONG_PASS_YARDS, grade)

    results: List[Dict[str, Any]] = []
    for _ in range(dist["COMPLETE"]):
        yds = _pick_yards(pool, weights)
        results.append({"result": "COMPLETE", "yards": yds, "td": random.random() < 0.08})
    for _ in range(dist["INCOMPLETE"]):
        results.append({"result": "INCOMPLETE", "yards": 0, "td": False})
    for _ in range(dist["INT"]):
        results.append({"result": "INT", "yards": 0, "td": False})

    random.shuffle(results)
    return _distribute_results(results)


def _make_qb_screen_pass(grade: str) -> Dict[str, Any]:
    dist = qb_screen_pass_distribution(grade)
    pool, weights = get_yards_pool(SCREEN_PASS_YARDS, grade)

    results: List[Dict[str, Any]] = []
    for _ in range(dist["COMPLETE"]):
        yds = _pick_yards(pool, weights)
        results.append({"result": "COMPLETE", "yards": yds, "td": random.random() < 0.03})
    for _ in range(dist["INCOMPLETE"]):
        results.append({"result": "INCOMPLETE", "yards": 0, "td": False})
    for _ in range(dist["FUMBLE"]):
        results.append({"result": "FUMBLE", "yards": 0, "td": False})
    for _ in range(dist["INT"]):
        results.append({"result": "INT", "yards": 0, "td": False})

    random.shuffle(results)
    return _distribute_results(results)


def _make_qb_rush(rush_ypc: float, fumble_rate: float,
                   grade: str) -> Dict[str, Any]:
    """Generate a QB rush card column (Run Number → result)."""
    dist = qb_rush_distribution(rush_ypc, fumble_rate, grade)
    gain_pool, gain_weights = get_yards_pool(QB_RUSH_YARDS, grade)
    oob_pool, oob_weights = get_yards_pool(OOB_RUN_YARDS, grade)

    results: List[Dict[str, Any]] = []
    for _ in range(dist["GAIN"]):
        yds = _pick_yards(gain_pool, gain_weights)
        results.append({"result": "GAIN", "yards": yds, "td": random.random() < 0.04})
    for _ in range(dist["FUMBLE"]):
        results.append({"result": "FUMBLE", "yards": 0, "td": False})
    for _ in range(dist["OOB"]):
        yds = _pick_yards(oob_pool, oob_weights)
        results.append({"result": "OOB", "yards": yds, "td": False})

    random.shuffle(results)
    return _distribute_results(results)


# ── RB columns (with OOB) ───────────────────────────────────────────

def _make_rb_inside_run(ypc: float, fumble_rate: float,
                         grade: str) -> Dict[str, Any]:
    dist = rb_run_distribution(fumble_rate, grade, is_outside=False)
    gain_pool, gain_weights = get_yards_pool(INSIDE_RUN_YARDS, grade)
    oob_pool, oob_weights = get_yards_pool(OOB_RUN_YARDS, grade)

    results: List[Dict[str, Any]] = []
    for _ in range(dist["GAIN"]):
        yds = _pick_yards(gain_pool, gain_weights)
        results.append({"result": "GAIN", "yards": yds, "td": random.random() < 0.03})
    for _ in range(dist["FUMBLE"]):
        results.append({"result": "FUMBLE", "yards": 0, "td": False})
    for _ in range(dist["OOB"]):
        yds = _pick_yards(oob_pool, oob_weights)
        results.append({"result": "OOB", "yards": yds, "td": False})

    random.shuffle(results)
    return _distribute_results(results)


def _make_rb_outside_run(ypc: float, fumble_rate: float,
                          grade: str) -> Dict[str, Any]:
    dist = rb_run_distribution(fumble_rate, grade, is_outside=True)
    gain_pool, gain_weights = get_yards_pool(OUTSIDE_RUN_YARDS, grade)
    oob_pool, oob_weights = get_yards_pool(OOB_RUN_YARDS, grade)

    results: List[Dict[str, Any]] = []
    for _ in range(dist["GAIN"]):
        yds = _pick_yards(gain_pool, gain_weights)
        results.append({"result": "GAIN", "yards": yds, "td": random.random() < 0.04})
    for _ in range(dist["FUMBLE"]):
        results.append({"result": "FUMBLE", "yards": 0, "td": False})
    for _ in range(dist["OOB"]):
        yds = _pick_yards(oob_pool, oob_weights)
        results.append({"result": "OOB", "yards": yds, "td": False})

    random.shuffle(results)
    return _distribute_results(results)


# ── WR / TE columns ─────────────────────────────────────────────────

def _make_wr_reception(catch_rate: float, avg_yards: float,
                        grade: str, is_long: bool = False) -> Dict[str, Any]:
    dist = reception_distribution(catch_rate, is_long)
    if is_long:
        pool, weights = get_yards_pool(LONG_RECEPTION_YARDS, grade)
    else:
        pool, weights = get_yards_pool(SHORT_RECEPTION_YARDS, grade)

    results: List[Dict[str, Any]] = []
    for _ in range(dist["CATCH"]):
        yds = _pick_yards(pool, weights)
        td = random.random() < (0.06 if is_long else 0.04)
        results.append({"result": "CATCH", "yards": yds, "td": td})
    for _ in range(dist["INCOMPLETE"]):
        results.append({"result": "INCOMPLETE", "yards": 0, "td": False})

    random.shuffle(results)
    return _distribute_results(results)


# ── Kicker ───────────────────────────────────────────────────────────

def _make_kicker_fg_chart(accuracy: float, grade: str) -> Dict[str, float]:
    return {
        "0-19": min(1.0, accuracy + 0.15),
        "20-29": min(1.0, accuracy + 0.10),
        "30-39": min(1.0, accuracy + 0.05),
        "40-49": accuracy,
        "50-59": max(0.0, accuracy - 0.15),
        "60+": max(0.0, accuracy - 0.30),
    }


# ── Punter (slot-based column) ───────────────────────────────────────

def _make_punter_column(avg_distance: float, inside_20_rate: float,
                         grade: str) -> Dict[str, Any]:
    """Generate a 64-slot punter card column."""
    dist = punter_distribution(avg_distance, inside_20_rate)
    punt_pool, punt_weights = get_yards_pool(PUNT_YARDS, grade)

    results: List[Dict[str, Any]] = []
    for _ in range(dist["NORMAL"]):
        yds = _pick_yards(punt_pool, punt_weights)
        results.append({"result": "NORMAL", "yards": yds, "td": False})
    for _ in range(dist["INSIDE_20"]):
        results.append({"result": "INSIDE_20", "yards": 0, "td": False})
    for _ in range(dist["TOUCHBACK"]):
        results.append({"result": "TOUCHBACK", "yards": 0, "td": False})

    random.shuffle(results)
    return _distribute_results(results)


# ── Main generator class ─────────────────────────────────────────────

class CardGenerator:
    """Generates player cards from raw stats using FAC distribution tables."""

    def __init__(self, seed: int = None):
        if seed is not None:
            random.seed(seed)

    def generate_qb_card(self, name: str, team: str, number: int,
                         comp_pct: float, ypa: float, int_rate: float,
                         sack_rate: float, grade: str,
                         rush_ypc: float = 3.0,
                         rush_fumble_rate: float = 0.015) -> PlayerCard:
        card = PlayerCard(
            player_name=name, team=team, position="QB",
            number=number, overall_grade=grade,
        )
        card.short_pass = _make_qb_short_pass(comp_pct, int_rate, sack_rate, grade)
        card.long_pass = _make_qb_long_pass(comp_pct, int_rate, grade)
        card.screen_pass = _make_qb_screen_pass(grade)
        card.qb_rush = _make_qb_rush(rush_ypc, rush_fumble_rate, grade)
        card.stats_summary = {
            "comp_pct": comp_pct, "ypa": ypa,
            "int_rate": int_rate, "sack_rate": sack_rate,
            "rush_ypc": rush_ypc,
        }
        return card

    def generate_rb_card(self, name: str, team: str, number: int,
                         ypc: float, fumble_rate: float, grade: str) -> PlayerCard:
        card = PlayerCard(
            player_name=name, team=team, position="RB",
            number=number, overall_grade=grade,
        )
        card.inside_run = _make_rb_inside_run(ypc, fumble_rate, grade)
        card.outside_run = _make_rb_outside_run(ypc, fumble_rate, grade)
        card.stats_summary = {"ypc": ypc, "fumble_rate": fumble_rate}
        return card

    def generate_wr_card(self, name: str, team: str, number: int,
                         catch_rate: float, avg_yards: float, grade: str) -> PlayerCard:
        card = PlayerCard(
            player_name=name, team=team, position="WR",
            number=number, overall_grade=grade,
        )
        card.short_reception = _make_wr_reception(catch_rate, avg_yards, grade, is_long=False)
        card.long_reception = _make_wr_reception(catch_rate * 0.7, avg_yards, grade, is_long=True)
        card.stats_summary = {"catch_rate": catch_rate, "avg_yards": avg_yards}
        return card

    def generate_te_card(self, name: str, team: str, number: int,
                         catch_rate: float, avg_yards: float, grade: str) -> PlayerCard:
        card = PlayerCard(
            player_name=name, team=team, position="TE",
            number=number, overall_grade=grade,
        )
        card.short_reception = _make_wr_reception(catch_rate, avg_yards, grade, is_long=False)
        card.long_reception = _make_wr_reception(catch_rate * 0.6, avg_yards, grade, is_long=True)
        card.stats_summary = {"catch_rate": catch_rate, "avg_yards": avg_yards}
        return card

    def generate_k_card(self, name: str, team: str, number: int,
                        accuracy: float, xp_rate: float, grade: str) -> PlayerCard:
        card = PlayerCard(
            player_name=name, team=team, position="K",
            number=number, overall_grade=grade,
        )
        card.fg_chart = _make_kicker_fg_chart(accuracy, grade)
        card.xp_rate = xp_rate
        card.stats_summary = {"accuracy": accuracy, "xp_rate": xp_rate}
        return card

    def generate_p_card(self, name: str, team: str, number: int,
                        avg_distance: float, inside_20_rate: float, grade: str) -> PlayerCard:
        card = PlayerCard(
            player_name=name, team=team, position="P",
            number=number, overall_grade=grade,
        )
        card.punt_column = _make_punter_column(avg_distance, inside_20_rate, grade)
        card.avg_distance = avg_distance
        card.inside_20_rate = inside_20_rate
        card.stats_summary = {"avg_distance": avg_distance, "inside_20_rate": inside_20_rate}
        return card

    def generate_def_card(self, name: str, team: str, number: int, position: str,
                          pass_rush: int, coverage: int, run_stop: int, grade: str) -> PlayerCard:
        card = PlayerCard(
            player_name=name, team=team, position=position,
            number=number, overall_grade=grade,
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
