"""Tests for the card generator."""
import sys
import os
import pytest
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.card_generator import (
    CardGenerator,
    _all_slots,
    _distribute_results,
    _make_qb_short_pass,
    _make_qb_long_pass,
    _make_rb_inside_run,
    _make_wr_reception,
    _make_kicker_fg_chart,
)


class TestAllSlots:
    def test_64_slots(self):
        slots = _all_slots()
        assert len(slots) == 64

    def test_slots_format(self):
        slots = _all_slots()
        for slot in slots:
            assert len(slot) == 2
            t = int(slot[0])
            o = int(slot[1])
            assert 1 <= t <= 8
            assert 1 <= o <= 8

    def test_no_duplicate_slots(self):
        slots = _all_slots()
        assert len(set(slots)) == 64


class TestDistributeResults:
    def test_returns_64_entries(self):
        results = [{"result": "GAIN", "yards": i % 10, "td": False} for i in range(64)]
        distributed = _distribute_results(results)
        assert len(distributed) == 64

    def test_keys_are_valid_slots(self):
        results = [{"result": "GAIN", "yards": 5, "td": False} for _ in range(64)]
        distributed = _distribute_results(results)
        valid_slots = set(_all_slots())
        for key in distributed.keys():
            assert key in valid_slots

    def test_wrong_count_raises(self):
        results = [{"result": "GAIN", "yards": 5, "td": False} for _ in range(10)]
        with pytest.raises(AssertionError):
            _distribute_results(results)


class TestQBShortPass:
    def setup_method(self):
        random.seed(42)

    def test_returns_64_slots(self):
        col = _make_qb_short_pass(0.64, 0.025, 0.07, "B")
        assert len(col) == 64

    def test_contains_completions(self):
        col = _make_qb_short_pass(0.64, 0.025, 0.07, "B")
        results = [v["result"] for v in col.values()]
        assert "COMPLETE" in results

    def test_contains_ints(self):
        col = _make_qb_short_pass(0.64, 0.025, 0.07, "B")
        results = [v["result"] for v in col.values()]
        assert "INT" in results

    def test_contains_sacks(self):
        col = _make_qb_short_pass(0.64, 0.025, 0.07, "B")
        results = [v["result"] for v in col.values()]
        assert "SACK" in results

    def test_elite_grade_higher_completion_rate(self):
        random.seed(42)
        col_a = _make_qb_short_pass(0.70, 0.015, 0.05, "A")
        random.seed(42)
        col_d = _make_qb_short_pass(0.55, 0.040, 0.10, "D")
        complete_a = sum(1 for v in col_a.values() if v["result"] == "COMPLETE")
        complete_d = sum(1 for v in col_d.values() if v["result"] == "COMPLETE")
        assert complete_a > complete_d

    def test_sack_yards_are_negative(self):
        col = _make_qb_short_pass(0.64, 0.025, 0.07, "B")
        sack_yards = [v["yards"] for v in col.values() if v["result"] == "SACK"]
        assert all(y < 0 for y in sack_yards)

    def test_completion_yards_positive(self):
        col = _make_qb_short_pass(0.64, 0.025, 0.07, "B")
        comp_yards = [v["yards"] for v in col.values() if v["result"] == "COMPLETE"]
        assert all(y >= 0 for y in comp_yards)


class TestQBLongPass:
    def setup_method(self):
        random.seed(42)

    def test_returns_64_slots(self):
        col = _make_qb_long_pass(0.64, 0.025, "B")
        assert len(col) == 64

    def test_long_completions_more_yards(self):
        col = _make_qb_long_pass(0.70, 0.015, "A")
        comp_yards = [v["yards"] for v in col.values() if v["result"] == "COMPLETE"]
        if comp_yards:
            assert min(comp_yards) >= 15


class TestRBInsideRun:
    def setup_method(self):
        random.seed(42)

    def test_returns_64_slots(self):
        col = _make_rb_inside_run(4.5, 0.012, "B")
        assert len(col) == 64

    def test_has_fumbles(self):
        col = _make_rb_inside_run(4.5, 0.020, "C")
        results = [v["result"] for v in col.values()]
        assert "FUMBLE" in results

    def test_fumble_count_scales_with_rate(self):
        random.seed(42)
        col_low = _make_rb_inside_run(4.5, 0.010, "B")
        random.seed(42)
        col_high = _make_rb_inside_run(4.5, 0.030, "B")
        f_low = sum(1 for v in col_low.values() if v["result"] == "FUMBLE")
        f_high = sum(1 for v in col_high.values() if v["result"] == "FUMBLE")
        assert f_high >= f_low


class TestWRReception:
    def setup_method(self):
        random.seed(42)

    def test_returns_64_slots(self):
        col = _make_wr_reception(0.68, 13.0, "A", is_long=False)
        assert len(col) == 64

    def test_has_catches(self):
        col = _make_wr_reception(0.68, 13.0, "A", is_long=False)
        results = [v["result"] for v in col.values()]
        assert "CATCH" in results

    def test_has_drops(self):
        col = _make_wr_reception(0.68, 13.0, "A", is_long=False)
        results = [v["result"] for v in col.values()]
        assert "INCOMPLETE" in results

    def test_long_reception_more_yards(self):
        col_short = _make_wr_reception(0.70, 12.0, "A", is_long=False)
        col_long = _make_wr_reception(0.50, 20.0, "A", is_long=True)
        short_yards = [v["yards"] for v in col_short.values() if v["result"] == "CATCH"]
        long_yards = [v["yards"] for v in col_long.values() if v["result"] == "CATCH"]
        if short_yards and long_yards:
            assert max(long_yards) >= max(short_yards)


class TestKickerFGChart:
    def test_returns_all_ranges(self):
        chart = _make_kicker_fg_chart(0.85, "A")
        assert "0-19" in chart
        assert "20-29" in chart
        assert "30-39" in chart
        assert "40-49" in chart
        assert "50-59" in chart
        assert "60+" in chart

    def test_rates_decrease_with_distance(self):
        chart = _make_kicker_fg_chart(0.85, "B")
        assert chart["0-19"] > chart["20-29"] or chart["0-19"] >= chart["20-29"]
        assert chart["40-49"] > chart["50-59"]
        assert chart["50-59"] >= chart["60+"]

    def test_rates_clamped_0_to_1(self):
        chart = _make_kicker_fg_chart(0.95, "A")
        for rate in chart.values():
            assert 0.0 <= rate <= 1.0


class TestCardGeneratorIntegration:
    def setup_method(self):
        self.gen = CardGenerator(seed=99)

    def test_all_positions_generate_cards(self):
        positions = [
            ("QB", lambda: self.gen.generate_qb_card("QB", "T", 1, 0.64, 7.5, 0.025, 0.07, "B")),
            ("RB", lambda: self.gen.generate_rb_card("RB", "T", 22, 4.5, 0.012, "B")),
            ("WR", lambda: self.gen.generate_wr_card("WR", "T", 80, 0.68, 13.0, "A")),
            ("TE", lambda: self.gen.generate_te_card("TE", "T", 86, 0.65, 9.5, "B")),
            ("K",  lambda: self.gen.generate_k_card("K", "T", 7, 0.85, 0.99, "A")),
            ("P",  lambda: self.gen.generate_p_card("P", "T", 4, 46.0, 0.40, "B")),
            ("DE", lambda: self.gen.generate_def_card("DE", "T", 99, "DE", 85, 45, 75, "A")),
        ]
        for pos, gen_fn in positions:
            card = gen_fn()
            assert card.position == pos
            assert card.player_name != ""
