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



class TestDiceResultDataclass:
    def test_dice_result_fields(self):
        r = DiceResult(
            two_digit=47,
            tens=4,
            ones=7,
            play_tendency=PlayTendency.BLITZ,
            turnover_modifier=3,
        )
        assert r.two_digit == 47
        assert r.tens == 4
        assert r.ones == 7
        assert r.play_tendency == PlayTendency.BLITZ
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
