"""Tests for new FAC distribution system, two-stage resolution, Z-cards, OOB, and defense integration."""
import sys
import os
import pytest
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.fac_distributions import (
    all_slots, SLOT_COUNT,
    qb_short_pass_distribution, qb_long_pass_distribution,
    qb_screen_pass_distribution, qb_rush_distribution,
    rb_run_distribution, reception_distribution,
    punter_distribution,
    get_yards_pool,
    SHORT_PASS_YARDS, LONG_PASS_YARDS, INSIDE_RUN_YARDS,
    OUTSIDE_RUN_YARDS, QB_RUSH_YARDS, OOB_RUN_YARDS,
    PUNT_YARDS, SACK_YARDS,
    FORMATION_MODIFIERS,
    effective_pass_rush, effective_coverage, effective_run_stop,
    pass_number, run_number,
)
from engine.card_generator import (
    CardGenerator, _make_qb_short_pass, _make_rb_inside_run,
    _make_rb_outside_run, _make_wr_reception, _make_qb_rush,
    _make_punter_column,
)
from engine.play_resolver import PlayResolver, PlayResult
from engine.player_card import PlayerCard
from engine.team import Team


# ─── FAC Distribution Tables ────────────────────────────────────────

class TestFACDistributions:
    def test_all_slots_returns_64(self):
        assert len(all_slots()) == 64

    def test_slot_count_constant(self):
        assert SLOT_COUNT == 64

    def test_qb_short_pass_distribution_sums_to_64(self):
        dist = qb_short_pass_distribution(0.64, 0.025, 0.07, "B")
        assert sum(dist.values()) == 64

    def test_qb_short_pass_has_all_result_types(self):
        dist = qb_short_pass_distribution(0.64, 0.025, 0.07, "B")
        assert set(dist.keys()) == {"COMPLETE", "INCOMPLETE", "INT", "SACK"}
        assert all(v >= 0 for v in dist.values())

    def test_qb_long_pass_distribution_sums_to_64(self):
        dist = qb_long_pass_distribution(0.65, 0.02, "A")
        assert sum(dist.values()) == 64

    def test_qb_screen_pass_distribution_sums_to_64(self):
        dist = qb_screen_pass_distribution("B")
        assert sum(dist.values()) == 64

    def test_qb_rush_distribution_sums_to_64(self):
        dist = qb_rush_distribution(4.0, 0.015, "B")
        assert sum(dist.values()) == 64

    def test_qb_rush_has_oob(self):
        dist = qb_rush_distribution(4.0, 0.015, "B")
        assert "OOB" in dist
        assert dist["OOB"] >= 1

    def test_rb_run_distribution_sums_to_64(self):
        dist = rb_run_distribution(0.012, "B", is_outside=False)
        assert sum(dist.values()) == 64

    def test_rb_outside_run_has_more_oob(self):
        inside = rb_run_distribution(0.012, "B", is_outside=False)
        outside = rb_run_distribution(0.012, "B", is_outside=True)
        assert outside["OOB"] >= inside["OOB"]

    def test_reception_distribution_sums_to_64(self):
        dist = reception_distribution(0.68, is_long=False)
        assert sum(dist.values()) == 64

    def test_punter_distribution_sums_to_64(self):
        dist = punter_distribution(45.0, 0.38)
        assert sum(dist.values()) == 64

    def test_punter_distribution_has_inside_20(self):
        dist = punter_distribution(45.0, 0.38)
        assert "INSIDE_20" in dist
        assert dist["INSIDE_20"] >= 1


class TestYardagePools:
    def test_short_pass_grades_exist(self):
        for grade in ("A+", "A", "B", "C", "D"):
            pool, weights = get_yards_pool(SHORT_PASS_YARDS, grade)
            assert len(pool) == len(weights)
            assert len(pool) > 0

    def test_long_pass_minimum_15_yards(self):
        for grade in ("A+", "A", "B", "C", "D"):
            pool, _ = get_yards_pool(LONG_PASS_YARDS, grade)
            assert min(pool) >= 15

    def test_inside_run_can_go_negative(self):
        for grade in ("A+", "A", "B", "C", "D"):
            pool, _ = get_yards_pool(INSIDE_RUN_YARDS, grade)
            assert min(pool) < 1

    def test_oob_run_yards_positive_for_good_grade(self):
        pool, _ = get_yards_pool(OOB_RUN_YARDS, "A")
        assert min(pool) >= 1

    def test_sack_yards_all_negative(self):
        pool, weights = SACK_YARDS
        assert all(y < 0 for y in pool)
        assert len(pool) == len(weights)

    def test_punt_yards_reasonable_range(self):
        for grade in ("A", "B", "C", "D"):
            pool, _ = get_yards_pool(PUNT_YARDS, grade)
            assert min(pool) >= 30
            assert max(pool) <= 65


# ─── Pass Number / Run Number ───────────────────────────────────────

class TestPassRunNumber:
    def test_pass_number(self):
        assert pass_number(3, 7) == 37

    def test_run_number(self):
        assert run_number(5, 2) == 52


# ─── Formation Modifiers ────────────────────────────────────────────

class TestFormationModifiers:
    def test_all_formations_have_three_keys(self):
        for name, mods in FORMATION_MODIFIERS.items():
            assert "pass_rush" in mods
            assert "coverage" in mods
            assert "run_stop" in mods

    def test_blitz_formations_boost_pass_rush(self):
        # In 5E, blitz is a defensive play, not a formation.
        # The BLITZ defensive play modifier should boost pass rush.
        from engine.fac_distributions import DEFENSIVE_PLAY_MODIFIERS
        assert DEFENSIVE_PLAY_MODIFIERS["BLITZ"]["pass_rush"] > 0

    def test_effective_pass_rush_clamped(self):
        assert effective_pass_rush(95, "4_3", is_blitz_tendency=True) <= 99
        assert effective_pass_rush(5, "NICKEL", is_blitz_tendency=False) >= 0

    def test_blitz_tendency_boosts_pass_rush(self):
        without = effective_pass_rush(70, "4_3", is_blitz_tendency=False)
        with_blitz = effective_pass_rush(70, "4_3", is_blitz_tendency=True)
        assert with_blitz > without

    def test_blitz_tendency_weakens_coverage(self):
        without = effective_coverage(70, "4_3", is_blitz_tendency=False)
        with_blitz = effective_coverage(70, "4_3", is_blitz_tendency=True)
        assert with_blitz < without

    def test_effective_run_stop_with_goal_line(self):
        base = effective_run_stop(70, "4_3")
        goal = effective_run_stop(70, "GOAL_LINE")
        assert goal > base  # Goal-line defense boosts run stop


# ─── New Card Generator Features ────────────────────────────────────

class TestNewCardGeneration:
    def setup_method(self):
        random.seed(42)
        self.gen = CardGenerator(seed=42)

    def test_qb_rush_column_generated(self):
        card = self.gen.generate_qb_card(
            "Test QB", "TST", 1, 0.64, 7.5, 0.025, 0.07, "B",
            rush_ypc=4.0, rush_fumble_rate=0.015,
        )
        assert len(card.qb_rush) == 64

    def test_qb_rush_has_oob_results(self):
        card = self.gen.generate_qb_card(
            "Mobile QB", "TST", 1, 0.64, 7.5, 0.025, 0.07, "A",
            rush_ypc=5.0, rush_fumble_rate=0.01,
        )
        results = [v["result"] for v in card.qb_rush.values()]
        assert "OOB" in results

    def test_qb_rush_has_gain_and_fumble(self):
        card = self.gen.generate_qb_card(
            "Test QB", "TST", 1, 0.64, 7.5, 0.025, 0.07, "B",
        )
        results = [v["result"] for v in card.qb_rush.values()]
        assert "GAIN" in results
        assert "FUMBLE" in results

    def test_rb_inside_run_has_oob(self):
        card = self.gen.generate_rb_card("Test RB", "TST", 22, 4.5, 0.012, "B")
        results = [v["result"] for v in card.inside_run.values()]
        assert "OOB" in results

    def test_rb_outside_run_has_oob(self):
        card = self.gen.generate_rb_card("Test RB", "TST", 22, 4.5, 0.012, "B")
        results = [v["result"] for v in card.outside_run.values()]
        assert "OOB" in results

    def test_punter_has_punt_column(self):
        card = self.gen.generate_p_card("Test P", "TST", 7, 46.0, 0.40, "B")
        assert len(card.punt_column) == 64

    def test_punter_column_has_inside_20(self):
        card = self.gen.generate_p_card("Test P", "TST", 7, 46.0, 0.40, "B")
        results = [v["result"] for v in card.punt_column.values()]
        assert "INSIDE_20" in results

    def test_punter_column_has_touchback(self):
        card = self.gen.generate_p_card("Test P", "TST", 7, 46.0, 0.40, "B")
        results = [v["result"] for v in card.punt_column.values()]
        assert "TOUCHBACK" in results

    def test_card_to_dict_includes_new_fields(self):
        card = self.gen.generate_qb_card(
            "Test QB", "TST", 1, 0.64, 7.5, 0.025, 0.07, "B",
        )
        d = card.to_dict()
        assert "qb_rush" in d
        assert len(d["qb_rush"]) == 64

    def test_card_from_dict_preserves_new_fields(self):
        card = self.gen.generate_qb_card(
            "Test QB", "TST", 1, 0.64, 7.5, 0.025, 0.07, "B",
        )
        d = card.to_dict()
        card2 = PlayerCard.from_dict(d)
        assert len(card2.qb_rush) == 64

    def test_punter_from_dict_preserves_punt_column(self):
        card = self.gen.generate_p_card("Test P", "TST", 7, 46.0, 0.40, "B")
        d = card.to_dict()
        card2 = PlayerCard.from_dict(d)
        assert len(card2.punt_column) == 64



# ─── OOB and Clock ──────────────────────────────────────────────────

class TestOOBAndClock:
    def setup_method(self):
        random.seed(42)
        self.resolver = PlayResolver()
        self.gen = CardGenerator(seed=42)


    def test_oob_result_stops_clock(self):
        """OOB plays should use clock-stop time (10 seconds per 5E rules)."""
        from engine.game import Game
        home = Team.load("KC", 2025)
        away = Team.load("BUF", 2025)
        game = Game(home, away)

        # Create an OOB play result
        oob_result = PlayResult(
            play_type="RUN", yards_gained=5, result="OOB",
            out_of_bounds=True, description="Run OOB",
        )
        time_used = game._calculate_time(oob_result)
        # 5th-edition Timing Table: OOB → 10 seconds
        assert time_used == 10

    def test_run_play_uses_more_time(self):
        from engine.game import Game
        home = Team.load("KC", 2025)
        away = Team.load("BUF", 2025)
        game = Game(home, away)

        run_result = PlayResult(play_type="RUN", yards_gained=5, result="GAIN")
        time_used = game._calculate_time(run_result)
        # 5th-edition Timing Table: Run → 40 seconds
        assert time_used == 40

    def test_incomplete_pass_uses_clock_stop_time(self):
        from engine.game import Game
        home = Team.load("KC", 2025)
        away = Team.load("BUF", 2025)
        game = Game(home, away)

        inc_result = PlayResult(play_type="PASS", yards_gained=0, result="INCOMPLETE")
        time_used = game._calculate_time(inc_result)
        # 5th-edition Timing Table: Incomplete → 10 seconds
        assert time_used == 10

    def test_complete_pass_uses_standard_time(self):
        from engine.game import Game
        home = Team.load("KC", 2025)
        away = Team.load("BUF", 2025)
        game = Game(home, away)

        com_result = PlayResult(play_type="PASS", yards_gained=12, result="COMPLETE")
        time_used = game._calculate_time(com_result)
        # 5th-edition Timing Table: Complete pass → 40 seconds
        assert time_used == 40

    def test_kneel_uses_maximum_time(self):
        from engine.game import Game
        home = Team.load("KC", 2025)
        away = Team.load("BUF", 2025)
        game = Game(home, away)

        kneel_result = PlayResult(play_type="KNEEL", yards_gained=-1, result="KNEEL")
        time_used = game._calculate_time(kneel_result)
        # 5th-edition: kneel → 40 seconds
        assert time_used == 40

    def test_penalty_uses_no_time(self):
        from engine.game import Game
        home = Team.load("KC", 2025)
        away = Team.load("BUF", 2025)
        game = Game(home, away)

        pen_result = PlayResult(
            play_type="RUN", yards_gained=0, result="PENALTY",
            penalty={"type": "HOLDING_OFF", "yards": 10},
        )
        time_used = game._calculate_time(pen_result)
        # 5th-edition Timing Table: Penalty → 10 seconds
        assert time_used == 10


# ─── Defense Play Call Override ─────────────────────────────────────

class TestDefenseFormationOverride:
    def setup_method(self):
        random.seed(42)

    def test_execute_play_with_defense_formation(self):
        """Human-specified defense formation should be used instead of AI."""
        from engine.game import Game
        home = Team.load("KC", 2025)
        away = Team.load("BUF", 2025)
        game = Game(home, away, seed=42)

        # Execute play with a specific defense formation
        result = game.execute_play(defense_formation="GOAL_LINE")
        assert result is not None
        assert hasattr(result, "play_type")

    def test_execute_play_with_both_play_call_and_defense(self):
        """Both offense play call and defense formation can be specified."""
        from engine.game import Game
        from engine.solitaire import PlayCall
        home = Team.load("KC", 2025)
        away = Team.load("BUF", 2025)
        game = Game(home, away, seed=42)

        play_call = PlayCall("RUN", "I_FORM", "MIDDLE", "Test")
        result = game.execute_play(
            play_call=play_call, defense_formation="4_3"
        )
        assert result is not None


# ─── Defense Integration in Resolution ──────────────────────────────



# ─── Loaded Team Data Validation ────────────────────────────────────

class TestRegeneratedTeamData:
    def test_all_32_teams_loadable(self):
        from engine.team import list_available_teams
        teams = list_available_teams(2025)
        assert len(teams) == 32

    def test_qb_has_qb_rush_column(self):
        team = Team.load("KC", 2025)
        qb = team.roster.get_starter("QB")
        assert qb is not None
        assert len(qb.qb_rush) == 64

    def test_rb_has_oob_in_run_columns(self):
        team = Team.load("BAL", 2025)
        rb = team.roster.get_starter("RB")
        assert rb is not None
        inside_results = [v["result"] for v in rb.inside_run.values()]
        assert "OOB" in inside_results

    def test_punter_has_punt_column(self):
        team = Team.load("NE", 2025)
        punter = team.roster.get_starter("P")
        assert punter is not None
        assert len(punter.punt_column) == 64

    def test_punt_column_has_expected_results(self):
        team = Team.load("NE", 2025)
        punter = team.roster.get_starter("P")
        results = set(v["result"] for v in punter.punt_column.values())
        assert "NORMAL" in results
        assert "INSIDE_20" in results

    def test_loaded_team_simulates_full_game(self):
        """Ensure regenerated data works in full game simulation."""
        random.seed(42)
        from engine.game import Game
        home = Team.load("PHI", 2025)
        away = Team.load("SF", 2025)
        game = Game(home, away)
        state = game.simulate_game()
        assert state.is_over
        assert state.score.home >= 0
        assert state.score.away >= 0
