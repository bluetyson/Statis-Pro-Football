"""Tests for the Fast Action Dice system."""
import sys
import os
import pytest
import random
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.fast_action_dice import FastActionDice, DiceResult, PlayTendency, roll


class TestDiceDistribution:
    """Statistical tests for dice distribution."""

    def test_thousands_of_rolls_cover_all_slots(self):
        d = FastActionDice()
        seen = set()
        for _ in range(5000):
            r = d.roll()
            seen.add(r.two_digit)
        assert len(seen) == 64, f"Only saw {len(seen)} of 64 possible slots"

    def test_tendency_distribution_is_reasonable(self):
        d = FastActionDice()
        counts = Counter()
        n = 6400
        for _ in range(n):
            counts[d.roll().play_tendency] += 1
        for tendency in PlayTendency:
            pct = counts[tendency] / n
            assert 0.05 < pct < 0.50, f"{tendency}: {pct:.2%} out of expected range"

    def test_run_tendency_most_common(self):
        """RUN should be most common tendency."""
        d = FastActionDice()
        counts = Counter(d.roll().play_tendency for _ in range(6400))
        # RUN appears most in the tendency map
        assert counts[PlayTendency.RUN] >= counts[PlayTendency.BLITZ]

    def test_penalty_rate_approximately_8_percent(self):
        d = FastActionDice()
        n = 10000
        penalty_count = sum(1 for _ in range(n) if d.roll().penalty_check)
        penalty_rate = penalty_count / n
        assert 0.03 <= penalty_rate <= 0.15, f"Penalty rate {penalty_rate:.2%} out of expected range"

    def test_tens_uniform_distribution(self):
        d = FastActionDice()
        counts = Counter(d.roll().tens for _ in range(8000))
        for val in range(1, 9):
            # Each should appear ~12.5%, allow 5-20% range
            pct = counts[val] / 8000
            assert 0.05 <= pct <= 0.20, f"Tens={val}: {pct:.2%}"

    def test_ones_uniform_distribution(self):
        d = FastActionDice()
        counts = Counter(d.roll().ones for _ in range(8000))
        for val in range(1, 9):
            pct = counts[val] / 8000
            assert 0.05 <= pct <= 0.20, f"Ones={val}: {pct:.2%}"

    def test_turnover_modifier_uniform(self):
        d = FastActionDice()
        counts = Counter(d.roll().turnover_modifier for _ in range(8000))
        for val in range(1, 9):
            pct = counts[val] / 8000
            assert 0.05 <= pct <= 0.20, f"Turnover={val}: {pct:.2%}"


class TestTendencyMap:
    def test_map_has_64_entries(self):
        d = FastActionDice()
        assert len(d.TENDENCY_MAP) == 64

    def test_all_combinations_present(self):
        d = FastActionDice()
        for t in range(1, 9):
            for o in range(1, 9):
                assert (t, o) in d.TENDENCY_MAP, f"Missing ({t},{o})"

    def test_penalty_combos_subset_of_all(self):
        d = FastActionDice()
        for combo in d.PENALTY_COMBOS:
            assert combo in d.TENDENCY_MAP


class TestDiceResultDataclass:
    def test_dice_result_fields(self):
        r = DiceResult(
            two_digit=47,
            tens=4,
            ones=7,
            play_tendency=PlayTendency.BLITZ,
            penalty_check=False,
            turnover_modifier=3,
        )
        assert r.two_digit == 47
        assert r.tens == 4
        assert r.ones == 7
        assert r.play_tendency == PlayTendency.BLITZ
        assert r.penalty_check is False
        assert r.turnover_modifier == 3

    def test_play_tendency_enum_values(self):
        assert PlayTendency.RUN == "RUN"
        assert PlayTendency.SHORT_PASS == "SHORT_PASS"
        assert PlayTendency.LONG_PASS == "LONG_PASS"
        assert PlayTendency.BLITZ == "BLITZ"


class TestReproducibility:
    def test_seeded_rolls_reproducible(self):
        random.seed(12345)
        d = FastActionDice()
        results1 = [d.roll() for _ in range(20)]

        random.seed(12345)
        d2 = FastActionDice()
        results2 = [d2.roll() for _ in range(20)]

        for r1, r2 in zip(results1, results2):
            assert r1.two_digit == r2.two_digit
            assert r1.play_tendency == r2.play_tendency


class TestPenaltyFrequency:
    def test_penalty_combos_count(self):
        d = FastActionDice()
        assert len(d.PENALTY_COMBOS) == 5

    def test_specific_penalty_combos(self):
        d = FastActionDice()
        expected = {(1, 7), (3, 7), (5, 8), (7, 1), (8, 2)}
        assert d.PENALTY_COMBOS == expected
