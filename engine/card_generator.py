"""Card generator for Statis Pro Football player cards.

Supports both authentic card formats (range-based QB passing, 12-row
N/SG/LG rushing and Q/S/L pass gain shared by RB/WR/TE) and legacy
64-slot cards.

Uses FAC distribution tables from ``fac_distributions`` to determine the
fixed number of slots per outcome type, then fills yardage values from
grade-appropriate pools.
"""
import random
from typing import Dict, Any, List, Tuple, Optional

from .player_card import (
    PlayerCard, PASS_SLOTS, RUN_SLOTS, RECEIVER_LETTERS,
    PassRanges, PassRushRanges, ThreeValueRow,
    PASS_NUMBER_MAX, RUN_NUMBER_MAX,
)
from .fac_distributions import (
    all_slots, pass_slots, run_slots,
    SLOT_COUNT, PASS_SLOT_COUNT, RUN_SLOT_COUNT,
    qb_short_pass_distribution, qb_long_pass_distribution,
    qb_screen_pass_distribution, qb_rush_distribution,
    rb_run_distribution, reception_distribution,
    punter_distribution,
    qb_pass_distribution_5e, qb_long_pass_distribution_5e,
    qb_quick_pass_distribution_5e,
    rb_run_distribution_5e, reception_distribution_5e,
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

    # ── 5th-Edition card generators ──────────────────────────────────

    def generate_qb_card_5e(self, name: str, team: str, number: int,
                            comp_pct: float, ypa: float, int_rate: float,
                            sack_rate: float, grade: str,
                            n_receivers: int = 5) -> PlayerCard:
        """Generate a 5th-edition QB card with 48-slot receiver-letter columns."""
        card = PlayerCard(
            player_name=name, team=team, position="QB",
            number=number, overall_grade=grade,
        )
        card.short_pass = _make_qb_pass_5e(comp_pct, int_rate, grade, n_receivers)
        card.long_pass = _make_qb_long_pass_5e(comp_pct, int_rate, grade, n_receivers)
        card.quick_pass = _make_qb_quick_pass_5e(comp_pct, int_rate, grade, n_receivers)
        card.stats_summary = {
            "comp_pct": comp_pct, "ypa": ypa,
            "int_rate": int_rate, "sack_rate": sack_rate,
        }
        return card

    def generate_rb_card_5e(self, name: str, team: str, number: int,
                            ypc: float, fumble_rate: float, grade: str) -> PlayerCard:
        """Generate a 5th-edition RB card with 12-slot run columns."""
        card = PlayerCard(
            player_name=name, team=team, position="RB",
            number=number, overall_grade=grade,
        )
        card.inside_run = _make_rb_run_5e(ypc, fumble_rate, grade, is_outside=False)
        card.outside_run = _make_rb_run_5e(ypc, fumble_rate, grade, is_outside=True)
        card.sweep = _make_rb_run_5e(ypc, fumble_rate, grade, is_sweep=True)
        card.stats_summary = {"ypc": ypc, "fumble_rate": fumble_rate}
        return card

    def generate_wr_card_5e(self, name: str, team: str, number: int,
                            catch_rate: float, avg_yards: float, grade: str,
                            receiver_letter: str = "A") -> PlayerCard:
        """Generate a 5th-edition WR card with 48-slot reception columns."""
        card = PlayerCard(
            player_name=name, team=team, position="WR",
            number=number, overall_grade=grade,
        )
        card.receiver_letter = receiver_letter
        card.short_reception = _make_wr_reception_5e(catch_rate, avg_yards, grade, is_long=False)
        card.long_reception = _make_wr_reception_5e(catch_rate * 0.7, avg_yards, grade, is_long=True)
        card.stats_summary = {"catch_rate": catch_rate, "avg_yards": avg_yards}
        return card

    def generate_te_card_5e(self, name: str, team: str, number: int,
                            catch_rate: float, avg_yards: float, grade: str,
                            receiver_letter: str = "D") -> PlayerCard:
        """Generate a 5th-edition TE card with 48-slot reception columns."""
        card = PlayerCard(
            player_name=name, team=team, position="TE",
            number=number, overall_grade=grade,
        )
        card.receiver_letter = receiver_letter
        card.short_reception = _make_wr_reception_5e(catch_rate, avg_yards, grade, is_long=False)
        card.long_reception = _make_wr_reception_5e(catch_rate * 0.6, avg_yards, grade, is_long=True)
        card.stats_summary = {"catch_rate": catch_rate, "avg_yards": avg_yards}
        return card

    def generate_def_card_5e(self, name: str, team: str, number: int, position: str,
                             pass_rush: int, coverage: int, run_stop: int, grade: str,
                             defender_letter: str = "") -> PlayerCard:
        """Generate a 5th-edition defensive player card with authentic stats.

        Authentic 5E defensive ratings by position group:
          DL (DE/DT): tackle_rating, pass_rush_rating
          LB:         pass_defense_rating, tackle_rating, pass_rush_rating, intercept_range
          DB (CB/S):  pass_defense_rating, pass_rush_rating, intercept_range (no tackle)
        """
        card = PlayerCard(
            player_name=name, team=team, position=position,
            number=number, overall_grade=grade,
        )
        # Legacy fields (kept for backward compat)
        card.pass_rush_rating = pass_rush
        card.coverage_rating = coverage
        card.run_stop_rating = run_stop
        card.defender_letter = defender_letter

        # Authentic 5E position-specific ratings
        pos = position.upper()
        if pos in ("DE", "DT", "DL", "NT", "EDGE"):
            # DL: tackle + pass rush
            card.tackle_rating = run_stop
            card.pass_rush_rating = pass_rush
        elif pos in ("LB", "OLB", "ILB", "MLB"):
            # LB: pass defense, tackle, pass rush, intercept range
            card.pass_defense_rating = coverage
            card.tackle_rating = run_stop
            card.pass_rush_rating = pass_rush
            card.intercept_range = max(0, min(9, (coverage - 50) // 5))  # 0-9 scale
        elif pos in ("CB", "S", "SS", "FS", "DB"):
            # DB: pass defense, pass rush, intercept range (no tackle)
            card.pass_defense_rating = coverage
            card.pass_rush_rating = pass_rush
            card.intercept_range = max(0, min(14, (coverage - 40) // 4))  # 0-14 scale, DBs better

        card.stats_summary = {
            "pass_rush_rating": pass_rush,
            "coverage_rating": coverage,
            "run_stop_rating": run_stop,
            "tackle_rating": card.tackle_rating,
            "pass_defense_rating": card.pass_defense_rating,
            "intercept_range": card.intercept_range,
        }
        return card

    def generate_ol_card(self, name: str, team: str, number: int,
                         position: str, grade: str,
                         run_block: int = 70, pass_block: int = 70) -> PlayerCard:
        """Generate an offensive lineman card (LT, LG, C, RG, RT).

        OL cards have run_block_rating and pass_block_rating used for
        pass rush resolution and run blocking matchups.
        """
        card = PlayerCard(
            player_name=name, team=team, position=position,
            number=number, overall_grade=grade,
        )
        card.run_block_rating = run_block
        card.pass_block_rating = pass_block
        card.stats_summary = {
            "run_block_rating": run_block,
            "pass_block_rating": pass_block,
        }
        return card

    # ══════════════════════════════════════════════════════════════════
    #  AUTHENTIC CARD GENERATORS
    #  Match the real Statis Pro Football card format:
    #    QB: range-based passing + 12-row rushing
    #    RB/WR/TE: same layout - 12-row rushing + 12-row pass gain
    # ══════════════════════════════════════════════════════════════════

    def generate_qb_card_authentic(
        self, name: str, team: str, number: int,
        comp_pct: float, ypa: float, int_rate: float,
        sack_rate: float, grade: str,
        rush_ypc: float = 3.0,
        rush_fumble_rate: float = 0.015,
        qb_endurance: str = "A",
    ) -> PlayerCard:
        """Generate an authentic QB card with range-based passing columns.

        Passing columns use ranges within 1-48 (Com/Inc/Int boundaries),
        matching the original Avalon Hill card format.
        Rushing uses 12 rows with N/SG/LG values.
        """
        card = PlayerCard(
            player_name=name, team=team, position="QB",
            number=number, overall_grade=grade,
        )

        # Passing ranges (Quick is highest completion, Long is lowest)
        card.passing_quick = _make_qb_pass_ranges(
            comp_pct + 0.04, int_rate * 0.5, grade,
        )
        card.passing_short = _make_qb_pass_ranges(
            comp_pct, int_rate, grade,
        )
        card.passing_long = _make_qb_pass_ranges(
            comp_pct - 0.08, int_rate * 1.5, grade,
        )

        # Pass Rush ranges
        card.pass_rush = _make_pass_rush_ranges(sack_rate, comp_pct, grade)

        # QB Rushing: 12 rows with N/SG/LG
        card.rushing = _make_rushing_12rows(
            rush_ypc, grade, is_qb=True,
        )
        card.endurance_rushing = 3
        card.qb_endurance = qb_endurance

        card.stats_summary = {
            "comp_pct": comp_pct, "ypa": ypa,
            "int_rate": int_rate, "sack_rate": sack_rate,
            "rush_ypc": rush_ypc,
        }
        return card

    def generate_rb_card_authentic(
        self, name: str, team: str, number: int,
        ypc: float, fumble_rate: float, grade: str,
        catch_rate: float = 0.3,
        avg_rec_yards: float = 7.0,
        endurance_pass: int = 2,
        blocks: int = 1,
        receiver_letter: str = "",
    ) -> PlayerCard:
        """Generate an authentic RB card (same format as WR/TE).

        RBs have strong rushing columns and varying pass gain columns.
        endurance_pass: 0 = unlimited, 4 = very limited pass involvement.
        """
        card = PlayerCard(
            player_name=name, team=team, position="RB",
            number=number, overall_grade=grade,
        )
        card.receiver_letter = receiver_letter

        # Rushing: 12 rows N/SG/LG (strong for RBs)
        card.rushing = _make_rushing_12rows(ypc, grade, is_qb=False)
        card.endurance_rushing = 0 if grade in ("A", "A+") else 1

        # Pass Gain: 12 rows Q/S/L (varies based on endurance_pass)
        card.pass_gain = _make_pass_gain_12rows(
            catch_rate, avg_rec_yards, grade,
            pass_endurance=endurance_pass,
        )
        card.endurance_pass = endurance_pass
        card.blocks = blocks

        card.stats_summary = {
            "ypc": ypc, "fumble_rate": fumble_rate,
            "catch_rate": catch_rate, "avg_rec_yards": avg_rec_yards,
        }
        return card

    def generate_wr_card_authentic(
        self, name: str, team: str, number: int,
        catch_rate: float, avg_yards: float, grade: str,
        receiver_letter: str = "A",
        has_rushing: bool = False,
        rush_ypc: float = 4.0,
        endurance_rush: str = "No",
        blocks: int = -2,
    ) -> PlayerCard:
        """Generate an authentic WR card (same format as RB/TE).

        WRs have strong pass gain columns but usually blank rushing.
        """
        card = PlayerCard(
            player_name=name, team=team, position="WR",
            number=number, overall_grade=grade,
        )
        card.receiver_letter = receiver_letter

        # Rushing: usually blank for WRs, but some have end-around ability
        if has_rushing:
            card.rushing = _make_rushing_12rows(rush_ypc, grade, is_qb=False)
            card.endurance_rushing = 4  # Very limited
        else:
            card.rushing = [None] * RUN_NUMBER_MAX
            card.endurance_rushing = 0  # "No" rushing

        # Pass Gain: 12 rows Q/S/L (strong for WRs)
        card.pass_gain = _make_pass_gain_12rows(
            catch_rate, avg_yards, grade,
            pass_endurance=0,  # WRs have strong pass gain
        )
        card.endurance_pass = 0 if grade in ("A", "A+") else 1
        card.blocks = blocks

        card.stats_summary = {
            "catch_rate": catch_rate, "avg_yards": avg_yards,
        }
        return card

    def generate_te_card_authentic(
        self, name: str, team: str, number: int,
        catch_rate: float, avg_yards: float, grade: str,
        receiver_letter: str = "D",
        blocks: int = 3,
    ) -> PlayerCard:
        """Generate an authentic TE card (same format as RB/WR).

        TEs have blank rushing, good blocking, moderate pass gain.
        """
        card = PlayerCard(
            player_name=name, team=team, position="TE",
            number=number, overall_grade=grade,
        )
        card.receiver_letter = receiver_letter

        # Rushing: blank for TEs
        card.rushing = [None] * RUN_NUMBER_MAX
        card.endurance_rushing = 0  # "No" rushing

        # Pass Gain: 12 rows Q/S/L (moderate for TEs)
        card.pass_gain = _make_pass_gain_12rows(
            catch_rate, avg_yards, grade,
            pass_endurance=0,
        )
        card.endurance_pass = 0 if grade in ("A", "A+") else 2
        card.blocks = blocks

        card.stats_summary = {
            "catch_rate": catch_rate, "avg_yards": avg_yards,
        }
        return card


# ── 5th-edition column builders ──────────────────────────────────────

def _distribute_pass_results(slot_assignments: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Map a list of 48 result dicts to pass-number slot keys ("1"-"48")."""
    slots = pass_slots()
    assert len(slot_assignments) == PASS_SLOT_COUNT, \
        f"Expected {PASS_SLOT_COUNT} slots, got {len(slot_assignments)}"
    return {slot: result for slot, result in zip(slots, slot_assignments)}


def _distribute_run_results(slot_assignments: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Map a list of 12 result dicts to run-number slot keys ("1"-"12")."""
    slots = run_slots()
    assert len(slot_assignments) == RUN_SLOT_COUNT, \
        f"Expected {RUN_SLOT_COUNT} slots, got {len(slot_assignments)}"
    return {slot: result for slot, result in zip(slots, slot_assignments)}


def _make_qb_pass_5e(comp_pct: float, int_pct: float,
                     grade: str, n_receivers: int = 5) -> Dict[str, Any]:
    """Generate a 5th-edition QB short-pass column (48 rows, receiver letters)."""
    dist = qb_pass_distribution_5e(comp_pct, int_pct, grade, n_receivers)

    results: List[Dict[str, Any]] = []
    for letter in RECEIVER_LETTERS[:n_receivers]:
        for _ in range(dist.get(letter, 0)):
            results.append({"result": letter, "yards": 0, "td": False})
    for _ in range(dist["INC"]):
        results.append({"result": "INC", "yards": 0, "td": False})
    for _ in range(dist["INT"]):
        results.append({"result": "INT", "yards": 0, "td": False})

    random.shuffle(results)
    return _distribute_pass_results(results)


def _make_qb_long_pass_5e(comp_pct: float, int_pct: float,
                           grade: str, n_receivers: int = 5) -> Dict[str, Any]:
    """Generate a 5th-edition QB long-pass column (48 rows)."""
    dist = qb_long_pass_distribution_5e(comp_pct, int_pct, grade, n_receivers)

    results: List[Dict[str, Any]] = []
    for letter in RECEIVER_LETTERS[:n_receivers]:
        for _ in range(dist.get(letter, 0)):
            results.append({"result": letter, "yards": 0, "td": False})
    for _ in range(dist["INC"]):
        results.append({"result": "INC", "yards": 0, "td": False})
    for _ in range(dist["INT"]):
        results.append({"result": "INT", "yards": 0, "td": False})

    random.shuffle(results)
    return _distribute_pass_results(results)


def _make_qb_quick_pass_5e(comp_pct: float, int_pct: float,
                            grade: str, n_receivers: int = 5) -> Dict[str, Any]:
    """Generate a 5th-edition QB quick-pass column (48 rows)."""
    dist = qb_quick_pass_distribution_5e(comp_pct, int_pct, grade, n_receivers)

    results: List[Dict[str, Any]] = []
    for letter in RECEIVER_LETTERS[:n_receivers]:
        for _ in range(dist.get(letter, 0)):
            results.append({"result": letter, "yards": 0, "td": False})
    for _ in range(dist["INC"]):
        results.append({"result": "INC", "yards": 0, "td": False})
    for _ in range(dist["INT"]):
        results.append({"result": "INT", "yards": 0, "td": False})

    random.shuffle(results)
    return _distribute_pass_results(results)


def _make_rb_run_5e(ypc: float, fumble_rate: float, grade: str,
                    is_outside: bool = False, is_sweep: bool = False) -> Dict[str, Any]:
    """Generate a 5th-edition RB run column (12 rows)."""
    dist = rb_run_distribution_5e(fumble_rate, grade, is_outside=is_outside, is_sweep=is_sweep)
    if is_sweep:
        gain_pool, gain_weights = get_yards_pool(OUTSIDE_RUN_YARDS, grade)
    elif is_outside:
        gain_pool, gain_weights = get_yards_pool(OUTSIDE_RUN_YARDS, grade)
    else:
        gain_pool, gain_weights = get_yards_pool(INSIDE_RUN_YARDS, grade)

    results: List[Dict[str, Any]] = []
    for _ in range(dist["GAIN"]):
        yds = _pick_yards(gain_pool, gain_weights)
        results.append({"result": "GAIN", "yards": yds, "td": random.random() < 0.04})
    for _ in range(dist["FUMBLE"]):
        results.append({"result": "FUMBLE", "yards": 0, "td": False})
    for _ in range(dist["BREAKAWAY"]):
        breakaway_yards = random.choice([15, 20, 25, 30, 40, 50])
        results.append({"result": "BREAKAWAY", "yards": breakaway_yards, "td": random.random() < 0.3})

    random.shuffle(results)
    return _distribute_run_results(results)


def _make_wr_reception_5e(catch_rate: float, avg_yards: float,
                          grade: str, is_long: bool = False) -> Dict[str, Any]:
    """Generate a 5th-edition WR/TE reception column (48 rows)."""
    dist = reception_distribution_5e(catch_rate, is_long)
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
        results.append({"result": "INC", "yards": 0, "td": False})

    random.shuffle(results)
    return _distribute_pass_results(results)


# ══════════════════════════════════════════════════════════════════════
#  AUTHENTIC CARD BUILDER HELPERS
# ══════════════════════════════════════════════════════════════════════

# Grade-based adjustments
_GRADE_RUSH_BOOST = {"A+": 3, "A": 2, "B": 1, "C": 0, "D": -1}
_GRADE_PASS_BOOST = {"A+": 4, "A": 3, "B": 1, "C": 0, "D": -2}


def _make_qb_pass_ranges(
    comp_pct: float, int_rate: float, grade: str,
) -> PassRanges:
    """Build range boundaries for a QB pass column (Quick, Short, or Long).

    comp_pct: completion percentage 0-1.
    int_rate: interception rate per attempt 0-1.
    """
    # Com range: PN 1 through com_max
    com_max = max(1, min(PASS_NUMBER_MAX - 1, round(comp_pct * PASS_NUMBER_MAX)))

    # Int range: PN inc_max+1 through 48
    n_int = max(0, round(int_rate * PASS_NUMBER_MAX))
    inc_max = PASS_NUMBER_MAX - n_int
    if inc_max <= com_max:
        inc_max = com_max  # No incomplete zone

    return PassRanges(com_max=com_max, inc_max=inc_max)


def _make_pass_rush_ranges(
    sack_rate: float, comp_pct: float, grade: str,
) -> PassRushRanges:
    """Build range boundaries for QB pass rush resolution."""
    sack_max = max(1, min(30, round(sack_rate * PASS_NUMBER_MAX * 2.5)))
    runs_max = 30  # QB runs typically range from sack_max+1 to 30
    if sack_max >= runs_max:
        runs_max = sack_max + 1

    # On pass rush, some passes still get completed
    comp_slots = max(1, round(comp_pct * (PASS_NUMBER_MAX - runs_max) * 0.6))
    com_max = min(PASS_NUMBER_MAX - 1, runs_max + comp_slots)

    return PassRushRanges(sack_max=sack_max, runs_max=runs_max, com_max=com_max)


def _make_rushing_12rows(
    ypc: float, grade: str, is_qb: bool = False,
) -> List[Optional[ThreeValueRow]]:
    """Build 12 rows of N/SG/LG rushing values.

    Row 1 has the best values (including "Sg" breakaway potential).
    Row 12 has the worst.

    N  = Normal yards (base result)
    SG = Short-Gain yards (used on SG blocking result)
    LG = Long-Gain yards (used on LG blocking result)
    """
    boost = _GRADE_RUSH_BOOST.get(grade, 0)
    rows: List[ThreeValueRow] = []

    # Base values scale with ypc
    # Row 1 is the best, row 12 is the worst
    for i in range(RUN_NUMBER_MAX):
        # N column: descending from good to bad
        if i == 0:
            # Row 1: "Sg" (special gain) — represent as string or high value
            n_val = "Sg"
        else:
            base_n = round(ypc * 2.2 - i * ypc * 0.25 + boost)
            if is_qb:
                base_n = round(base_n * 0.7)  # QBs are weaker rushers
            n_val = max(-5, base_n)

        # SG column: moderate value
        sg_base = round(ypc * 2.5 + boost * 0.5 - i * 0.4)
        if is_qb:
            sg_base = max(6, round(sg_base * 0.65))
        sg_val = max(sg_base if i > 0 else sg_base + 2, 5 if not is_qb else 2)

        # LG column: highest value (long gain potential)
        lg_base = round(ypc * 5.0 + boost * 2 - i * 1.2)
        if is_qb:
            lg_base = round(lg_base * 0.5)
        lg_val = max(lg_base if i > 0 else lg_base + 5, 10)
        if is_qb:
            lg_val = max(lg_val, sg_val)

        rows.append(ThreeValueRow(v1=n_val, v2=sg_val, v3=lg_val))

    return rows


def _make_pass_gain_12rows(
    catch_rate: float, avg_yards: float, grade: str,
    pass_endurance: int = 0,
) -> List[Optional[ThreeValueRow]]:
    """Build 12 rows of Q/S/L pass gain values.

    Row 1 has the best values.  Row 12 has the worst.

    Q = Quick pass yards
    S = Short pass yards
    L = Long pass yards

    pass_endurance: 0 = best receiver (unlimited), 4 = worst.
    Players with endurance 3-4 get fewer columns / lower values.
    """
    boost = _GRADE_PASS_BOOST.get(grade, 0)
    rows: List[ThreeValueRow] = []

    # Scale factor: 0=great receiver, 4=barely catches
    scale = max(0.3, 1.0 - pass_endurance * 0.15)

    for i in range(RUN_NUMBER_MAX):
        if pass_endurance >= 4 and catch_rate < 0.3:
            # Very poor receiver — only single values (no Q/S/L split)
            base = round(avg_yards * scale * 0.6 - i * 0.8 + boost * 0.3)
            val = max(-3, base)
            rows.append(ThreeValueRow(v1=val, v2=val, v3=val))
            continue

        # Row 1 can be "Lg" (long gain) for top receivers
        if i == 0 and pass_endurance <= 1:
            q_val = "Lg"
            s_val = "Lg"
            l_val = round(avg_yards * 4.0 * scale + boost * 3)
            l_val = max(20, l_val)
        else:
            # Q column (Quick pass): shortest yards
            q_base = round(avg_yards * 0.8 * scale - i * 0.6 + boost)
            q_val = max(0 if i < 8 else -3, q_base)

            # S column (Short pass): moderate yards
            s_base = round(avg_yards * 1.2 * scale - i * 0.5 + boost * 1.2)
            s_val = max(5, s_base)

            # L column (Long pass): highest yards
            l_base = round(avg_yards * 2.8 * scale - i * 1.5 + boost * 2)
            l_val = max(20, l_base)

        # For RBs with high endurance_pass (3-4), Long column might be missing
        if pass_endurance >= 3 and i > 0:
            # Weak long-pass ability for non-receiving backs
            if isinstance(l_val, (int, float)):
                l_val = max(s_val if isinstance(s_val, int) else 10, l_val)
            # Some rows might only have S/L or just a single value
            if pass_endurance >= 4:
                q_val = s_val  # No quick-pass ability

        rows.append(ThreeValueRow(v1=q_val, v2=s_val, v3=l_val))

    return rows
