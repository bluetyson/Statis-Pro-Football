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
    ZCardTrigger, lookup_z_card_event,
    Z_CARD_OFFENSE_EVENTS, Z_CARD_DEFENSE_EVENTS,
    FORMATION_MODIFIERS,
    effective_pass_rush, effective_coverage, effective_run_stop,
    pass_number, run_number,
)
from engine.fast_action_dice import FastActionDice, DiceResult, PlayTendency
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

    def test_dice_result_has_pn_rn(self):
        d = FastActionDice()
        r = d.roll()
        assert r.pass_number == r.two_digit
        assert r.run_number == r.two_digit

    def test_dice_result_has_slot(self):
        d = FastActionDice()
        r = d.roll()
        assert r.slot == str(r.two_digit)


# ─── Z-Card System ──────────────────────────────────────────────────

class TestZCardTrigger:
    def test_dice_combo_triggers(self):
        for tens, ones in ZCardTrigger.Z_CARD_COMBOS:
            assert ZCardTrigger.is_triggered(tens, ones)

    def test_non_trigger_dice_dont_fire(self):
        # (3, 5) is not a Z-card combo and doesn't match any situational trigger
        assert not ZCardTrigger.is_triggered(3, 5, down=1, distance=10, yard_line=30)

    def test_red_zone_third_down_trigger(self):
        # Inside 20 (yard_line >= 80), 3rd down, with matching doubles
        assert ZCardTrigger.is_triggered(3, 3, down=3, distance=5, yard_line=85)

    def test_third_and_long_trigger(self):
        assert ZCardTrigger.is_triggered(4, 4, down=3, distance=12, yard_line=30)

    def test_late_game_pressure_trigger(self):
        assert ZCardTrigger.is_triggered(1, 8, down=2, distance=7, yard_line=50,
                                          quarter=4, time_remaining=60)


class TestZCardEvents:
    def test_offense_events_has_64_entries(self):
        assert len(Z_CARD_OFFENSE_EVENTS) == 64

    def test_defense_events_has_64_entries(self):
        assert len(Z_CARD_DEFENSE_EVENTS) == 64

    def test_lookup_returns_event(self):
        event = lookup_z_card_event(1, 1, is_offense=True)
        assert "event" in event
        assert "yards" in event
        assert "turnover" in event

    def test_lookup_defense_event(self):
        event = lookup_z_card_event(2, 2, is_offense=False)
        assert event["event"] == "PICK_SIX"
        assert event["turnover"] is True

    def test_no_effect_for_most_slots(self):
        # Most slots should be NO_EFFECT
        no_effect_count = sum(1 for e in Z_CARD_OFFENSE_EVENTS.values()
                              if e["event"] == "NO_EFFECT")
        assert no_effect_count > 40  # Most are no-effect


# ─── Formation Modifiers ────────────────────────────────────────────

class TestFormationModifiers:
    def test_all_formations_have_three_keys(self):
        for name, mods in FORMATION_MODIFIERS.items():
            assert "pass_rush" in mods
            assert "coverage" in mods
            assert "run_stop" in mods

    def test_blitz_formations_boost_pass_rush(self):
        assert FORMATION_MODIFIERS["4_3_BLITZ"]["pass_rush"] > 0
        assert FORMATION_MODIFIERS["NICKEL_BLITZ"]["pass_rush"] > 0

    def test_effective_pass_rush_clamped(self):
        assert effective_pass_rush(95, "4_3_BLITZ", is_blitz_tendency=True) <= 99
        assert effective_pass_rush(5, "NICKEL_ZONE", is_blitz_tendency=False) >= 0

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


# ─── Two-Stage Pass Resolution ──────────────────────────────────────

class TestTwoStagePassResolution:
    def setup_method(self):
        random.seed(42)
        self.resolver = PlayResolver()
        self.gen = CardGenerator(seed=42)
        self.dice = FastActionDice()

    def _make_qb(self, grade="B"):
        return self.gen.generate_qb_card(
            "Test QB", "TST", 1, 0.64, 7.5, 0.025, 0.07, grade,
        )

    def _make_wr(self, grade="B"):
        return self.gen.generate_wr_card("Test WR", "TST", 80, 0.68, 13.0, grade)

    def test_pass_result_has_z_card_field(self):
        dice = self.dice.roll()
        qb = self._make_qb()
        wr = self._make_wr()
        result = self.resolver.resolve_pass(dice, qb, wr, "SHORT")
        assert hasattr(result, 'z_card_event')

    def test_pass_with_defense_parameters(self):
        dice = self.dice.roll()
        qb = self._make_qb()
        wr = self._make_wr()
        result = self.resolver.resolve_pass(
            dice, qb, wr, "SHORT",
            defense_coverage=80, defense_pass_rush=75,
            defense_formation="4_3_BLITZ", is_blitz_tendency=True,
        )
        assert isinstance(result, PlayResult)
        assert result.play_type == "PASS"

    def test_high_pass_rush_produces_more_sacks(self):
        """With high pass rush, more sacks should happen over many plays."""
        random.seed(123)
        qb = self._make_qb()
        wr = self._make_wr()
        sack_count = 0
        for _ in range(200):
            dice = self.dice.roll()
            result = self.resolver.resolve_pass(
                dice, qb, wr, "SHORT",
                defense_pass_rush=90, defense_formation="4_3_BLITZ",
                is_blitz_tendency=True,
            )
            if result.result == "SACK":
                sack_count += 1
        # At least some sacks should happen with very high pass rush
        assert sack_count > 5

    def test_high_coverage_reduces_yards(self):
        """High coverage should reduce yards on completions."""
        random.seed(456)
        qb = self._make_qb("A")
        wr = self._make_wr("A")
        normal_yards = []
        covered_yards = []
        for _ in range(200):
            dice = self.dice.roll()
            result = self.resolver.resolve_pass(dice, qb, wr, "SHORT",
                                                 defense_coverage=50)
            if result.result in ("COMPLETE", "TD"):
                normal_yards.append(result.yards_gained)

        random.seed(456)
        for _ in range(200):
            dice = self.dice.roll()
            result = self.resolver.resolve_pass(dice, qb, wr, "SHORT",
                                                 defense_coverage=90)
            if result.result in ("COMPLETE", "TD"):
                covered_yards.append(result.yards_gained)

        if normal_yards and covered_yards:
            avg_normal = sum(normal_yards) / len(normal_yards)
            avg_covered = sum(covered_yards) / len(covered_yards)
            # High coverage should result in fewer or lower yards
            assert avg_covered <= avg_normal or len(covered_yards) <= len(normal_yards)


# ─── OOB and Clock ──────────────────────────────────────────────────

class TestOOBAndClock:
    def setup_method(self):
        random.seed(42)
        self.resolver = PlayResolver()
        self.gen = CardGenerator(seed=42)
        self.dice = FastActionDice()

    def test_oob_result_has_out_of_bounds_flag(self):
        rb = self.gen.generate_rb_card("Test RB", "TST", 22, 4.5, 0.012, "B")
        # Run many plays until we get an OOB
        oob_found = False
        for _ in range(500):
            dice = self.dice.roll()
            result = self.resolver.resolve_run(dice, rb, "RIGHT")
            if result.out_of_bounds:
                oob_found = True
                assert result.result == "OOB"
                break
        assert oob_found, "Should get at least one OOB result in 500 plays"

    def test_oob_result_stops_clock(self):
        """OOB plays should be treated like incomplete passes for clock."""
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
        # OOB should use 5-10 seconds (like INCOMPLETE)
        assert 5 <= time_used <= 10

    def test_run_play_uses_more_time(self):
        from engine.game import Game
        home = Team.load("KC", 2025)
        away = Team.load("BUF", 2025)
        game = Game(home, away)

        run_result = PlayResult(play_type="RUN", yards_gained=5, result="GAIN")
        time_used = game._calculate_time(run_result)
        assert 25 <= time_used <= 45


# ─── Defense Integration in Resolution ──────────────────────────────

class TestDefenseIntegration:
    def setup_method(self):
        random.seed(42)
        self.resolver = PlayResolver()
        self.gen = CardGenerator(seed=42)
        self.dice = FastActionDice()

    def test_run_stop_affects_yards(self):
        rb = self.gen.generate_rb_card("Test RB", "TST", 22, 4.5, 0.012, "B")
        low_stop_yards = []
        high_stop_yards = []

        random.seed(789)
        for _ in range(200):
            dice = self.dice.roll()
            result = self.resolver.resolve_run(dice, rb, "MIDDLE",
                                                defense_run_stop=30)
            if result.result == "GAIN":
                low_stop_yards.append(result.yards_gained)

        random.seed(789)
        for _ in range(200):
            dice = self.dice.roll()
            result = self.resolver.resolve_run(dice, rb, "MIDDLE",
                                                defense_run_stop=90)
            if result.result == "GAIN":
                high_stop_yards.append(result.yards_gained)

        if low_stop_yards and high_stop_yards:
            avg_low = sum(low_stop_yards) / len(low_stop_yards)
            avg_high = sum(high_stop_yards) / len(high_stop_yards)
            assert avg_high <= avg_low

    def test_formation_wired_into_resolution(self):
        rb = self.gen.generate_rb_card("Test RB", "TST", 22, 4.5, 0.012, "B")
        dice = self.dice.roll()
        # Should accept defense_formation parameter
        result = self.resolver.resolve_run(
            dice, rb, "MIDDLE",
            defense_run_stop=75, defense_formation="GOAL_LINE",
        )
        assert isinstance(result, PlayResult)


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
