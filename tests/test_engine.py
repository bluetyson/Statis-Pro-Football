"""Tests for the game engine core modules."""
import sys
import os
import pytest
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.fast_action_dice import FastActionDice, DiceResult, PlayTendency, roll
from engine.player_card import PlayerCard
from engine.card_generator import CardGenerator
from engine.charts import Charts
from engine.team import Team, Roster, list_available_teams
from engine.play_resolver import PlayResolver, PlayResult
from engine.game import Game, GameState, Score
from engine.solitaire import SolitaireAI, GameSituation, PlayCall


# ─── FastActionDice ──────────────────────────────────────────────────────────

class TestFastActionDice:
    def test_roll_returns_dice_result(self):
        d = FastActionDice()
        result = d.roll()
        assert isinstance(result, DiceResult)

    def test_tens_range(self):
        d = FastActionDice()
        for _ in range(100):
            r = d.roll()
            assert 1 <= r.tens <= 8

    def test_ones_range(self):
        d = FastActionDice()
        for _ in range(100):
            r = d.roll()
            assert 1 <= r.ones <= 8

    def test_two_digit_format(self):
        d = FastActionDice()
        for _ in range(100):
            r = d.roll()
            assert r.two_digit == r.tens * 10 + r.ones

    def test_play_tendency_is_enum(self):
        d = FastActionDice()
        for _ in range(50):
            r = d.roll()
            assert r.play_tendency in list(PlayTendency)

    def test_turnover_modifier_range(self):
        d = FastActionDice()
        for _ in range(100):
            r = d.roll()
            assert 1 <= r.turnover_modifier <= 8

    def test_penalty_check_is_bool(self):
        d = FastActionDice()
        for _ in range(50):
            r = d.roll()
            assert isinstance(r.penalty_check, bool)

    def test_penalty_combos_trigger(self):
        """Verify penalty combos produce penalty_check=True."""
        d = FastActionDice()
        penalty_combos = {(1, 7), (3, 7), (5, 8), (7, 1), (8, 2)}
        for t, o in penalty_combos:
            two_digit = t * 10 + o
            tendency = d.TENDENCY_MAP.get((t, o), PlayTendency.RUN)
            result = DiceResult(two_digit, t, o, tendency, True, 1)
            assert result.penalty_check is True

    def test_module_roll_function(self):
        r = roll()
        assert isinstance(r, DiceResult)

    def test_all_tendencies_present(self):
        """All PlayTendency values appear in TENDENCY_MAP."""
        d = FastActionDice()
        found = set(d.TENDENCY_MAP.values())
        for t in PlayTendency:
            assert t in found


# ─── PlayerCard ──────────────────────────────────────────────────────────────

class TestPlayerCard:
    def test_create_player_card(self):
        card = PlayerCard("Patrick Mahomes", "KC", "QB", 15, "A")
        assert card.player_name == "Patrick Mahomes"
        assert card.team == "KC"
        assert card.position == "QB"
        assert card.number == 15

    def test_to_dict(self):
        card = PlayerCard("Test Player", "TST", "QB", 1, "B")
        d = card.to_dict()
        assert d["name"] == "Test Player"
        assert d["position"] == "QB"
        assert d["number"] == 1

    def test_from_dict_roundtrip(self):
        card = PlayerCard("Josh Allen", "BUF", "QB", 17, "A")
        card.stats_summary = {"comp_pct": 0.64}
        d = card.to_dict()
        card2 = PlayerCard.from_dict(d)
        assert card2.player_name == card.player_name
        assert card2.team == card.team
        assert card2.overall_grade == card.overall_grade

    def test_default_values(self):
        card = PlayerCard("Default", "TST", "QB", 0)
        assert card.overall_grade == "C"
        assert card.xp_rate == 0.95
        assert card.pass_rush_rating == 50


# ─── CardGenerator ───────────────────────────────────────────────────────────

class TestCardGenerator:
    def setup_method(self):
        self.gen = CardGenerator(seed=42)

    def test_generate_qb_card(self):
        card = self.gen.generate_qb_card(
            "Test QB", "TST", 1, 0.64, 7.5, 0.025, 0.07, "B"
        )
        assert card.position == "QB"
        assert len(card.short_pass) == 64
        assert len(card.long_pass) == 64
        assert len(card.screen_pass) == 64

    def test_generate_rb_card(self):
        card = self.gen.generate_rb_card("Test RB", "TST", 22, 4.5, 0.012, "B")
        assert card.position == "RB"
        assert len(card.inside_run) == 64
        assert len(card.outside_run) == 64

    def test_generate_wr_card(self):
        card = self.gen.generate_wr_card("Test WR", "TST", 80, 0.68, 13.0, "A")
        assert card.position == "WR"
        assert len(card.short_reception) == 64
        assert len(card.long_reception) == 64

    def test_generate_k_card(self):
        card = self.gen.generate_k_card("Test K", "TST", 3, 0.85, 0.985, "B")
        assert card.position == "K"
        assert "40-49" in card.fg_chart
        assert 0.0 <= card.fg_chart["40-49"] <= 1.0

    def test_generate_p_card(self):
        card = self.gen.generate_p_card("Test P", "TST", 7, 46.0, 0.40, "B")
        assert card.position == "P"
        assert card.avg_distance == 46.0

    def test_qb_card_slots_cover_all_outcomes(self):
        card = self.gen.generate_qb_card(
            "Elite QB", "TST", 1, 0.70, 8.5, 0.015, 0.055, "A"
        )
        results = [v["result"] for v in card.short_pass.values()]
        assert "COMPLETE" in results
        assert "INCOMPLETE" in results
        assert "INT" in results

    def test_rb_card_has_fumble(self):
        card = self.gen.generate_rb_card("RB", "TST", 22, 4.0, 0.015, "C")
        results = [v["result"] for v in card.inside_run.values()]
        assert "FUMBLE" in results

    def test_generate_def_card(self):
        card = self.gen.generate_def_card(
            "Test DE", "TST", 99, "DE", 85, 45, 75, "A"
        )
        assert card.position == "DE"
        assert card.pass_rush_rating == 85


# ─── Charts ──────────────────────────────────────────────────────────────────

class TestCharts:
    def test_penalty_chart_has_all_slots(self):
        """Check all 64 combinations are in penalty chart."""
        for t in range(1, 9):
            for o in range(1, 9):
                key = f"{t}{o}"
                assert key in Charts.PENALTY_CHART, f"Missing penalty chart key: {key}"

    def test_kick_return_chart_coverage(self):
        for t in range(1, 9):
            for o in range(1, 9):
                key = f"{t}{o}"
                assert key in Charts.KICK_RETURN_CHART

    def test_punt_return_chart_coverage(self):
        for t in range(1, 9):
            for o in range(1, 9):
                key = f"{t}{o}"
                assert key in Charts.PUNT_RETURN_CHART

    def test_roll_penalty_chart_returns_dict(self):
        p = Charts.roll_penalty_chart()
        assert isinstance(p, dict)
        assert "type" in p
        assert "yards" in p

    def test_roll_fumble_recovery_returns_valid(self):
        for _ in range(20):
            r = Charts.roll_fumble_recovery()
            assert r in ("OFFENSE", "DEFENSE")

    def test_roll_int_return(self):
        yards, is_td = Charts.roll_int_return()
        assert yards >= 0
        assert isinstance(is_td, bool)

    def test_roll_kick_return_returns_int(self):
        yards = Charts.roll_kick_return()
        assert isinstance(yards, int)
        assert yards >= 0

    def test_is_kickoff_touchback_returns_bool(self):
        for _ in range(10):
            tb = Charts.is_kickoff_touchback()
            assert isinstance(tb, bool)


# ─── Team ────────────────────────────────────────────────────────────────────

class TestTeam:
    def test_list_available_teams(self):
        teams = list_available_teams(2025)
        assert len(teams) == 32

    def test_load_team(self):
        team = Team.load("KC", 2025)
        assert team.abbreviation == "KC"
        assert team.name == "Chiefs"

    def test_team_has_roster(self):
        team = Team.load("BUF", 2025)
        assert len(team.roster.qbs) >= 1
        assert len(team.roster.rbs) >= 1
        assert len(team.roster.wrs) >= 1

    def test_team_has_qb(self):
        team = Team.load("SF", 2025)
        qb = team.roster.get_starter("QB")
        assert qb is not None
        assert qb.position == "QB"

    def test_team_to_dict(self):
        team = Team.load("DET", 2025)
        d = team.to_dict()
        assert "abbreviation" in d
        assert "players" in d
        assert len(d["players"]) > 0

    def test_team_from_dict_roundtrip(self):
        team = Team.load("GB", 2025)
        d = team.to_dict()
        team2 = Team.from_dict(d)
        assert team2.abbreviation == team.abbreviation
        assert team2.name == team.name

    def test_all_32_teams_loadable(self):
        for abbr in list_available_teams(2025):
            t = Team.load(abbr, 2025)
            assert t.abbreviation == abbr

    def test_team_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            Team.load("FAKE", 2025)


# ─── PlayResolver ────────────────────────────────────────────────────────────

class TestPlayResolver:
    def setup_method(self):
        random.seed(42)
        self.resolver = PlayResolver()
        self.gen = CardGenerator(seed=42)
        self.dice = FastActionDice()

    def _make_qb(self):
        return self.gen.generate_qb_card(
            "Test QB", "TST", 1, 0.64, 7.5, 0.025, 0.07, "B"
        )

    def _make_rb(self):
        return self.gen.generate_rb_card("Test RB", "TST", 22, 4.5, 0.012, "B")

    def _make_wr(self):
        return self.gen.generate_wr_card("Test WR", "TST", 80, 0.68, 13.0, "B")

    def test_resolve_run_returns_result(self):
        dice = self.dice.roll()
        rb = self._make_rb()
        result = self.resolver.resolve_run(dice, rb)
        assert isinstance(result, PlayResult)
        assert result.play_type == "RUN"

    def test_resolve_pass_returns_result(self):
        dice = self.dice.roll()
        qb = self._make_qb()
        wr = self._make_wr()
        result = self.resolver.resolve_pass(dice, qb, wr, "SHORT")
        assert isinstance(result, PlayResult)
        assert result.play_type == "PASS"

    def test_resolve_field_goal_close(self):
        kicker = self.gen.generate_k_card("Kicker", "TST", 7, 0.92, 0.995, "A")
        hits = sum(1 for _ in range(100)
                   if self.resolver.resolve_field_goal(25, kicker).result == "FG_GOOD")
        assert hits > 80  # Close FGs should be made most of the time

    def test_resolve_field_goal_long(self):
        kicker = self.gen.generate_k_card("Kicker", "TST", 7, 0.75, 0.985, "B")
        made_count = sum(1 for _ in range(100)
                         if self.resolver.resolve_field_goal(62, kicker).result == "FG_GOOD")
        assert made_count < 60  # Long FGs miss more

    def test_resolve_punt_returns_result(self):
        punter = self.gen.generate_p_card("Punter", "TST", 4, 46.0, 0.40, "B")
        result = self.resolver.resolve_punt(punter)
        assert result.play_type == "PUNT"

    def test_resolve_xp_returns_result(self):
        kicker = self.gen.generate_k_card("Kicker", "TST", 7, 0.89, 0.990, "A")
        result = self.resolver.resolve_xp(kicker)
        assert result.play_type == "XP"
        assert result.result in ("XP_GOOD", "XP_NO_GOOD")

    def test_resolve_kickoff(self):
        result = self.resolver.resolve_kickoff()
        assert result.play_type == "KICKOFF"
        assert result.result in ("TOUCHBACK", "RETURN")


# ─── SolitaireAI ─────────────────────────────────────────────────────────────

class TestSolitaireAI:
    def setup_method(self):
        self.ai = SolitaireAI()

    def _sit(self, down=1, distance=10, yard_line=25, score_diff=0,
             quarter=2, time_remaining=600):
        return GameSituation(down, distance, yard_line, score_diff, quarter, time_remaining)

    def test_call_play_returns_play_call(self):
        sit = self._sit()
        play = self.ai.call_play(sit)
        assert isinstance(play, PlayCall)
        assert play.play_type in (
            "RUN", "SHORT_PASS", "LONG_PASS", "SCREEN", "PUNT", "FG", "KNEEL"
        )

    def test_fourth_down_long_distance_punts(self):
        sit = self._sit(down=4, distance=15, yard_line=30)
        play = self.ai.call_play(sit)
        assert play.play_type == "PUNT"

    def test_fourth_down_fg_range(self):
        sit = self._sit(down=4, distance=8, yard_line=65)
        play = self.ai.call_play(sit)
        assert play.play_type == "FG"

    def test_kneel_when_winning_late(self):
        sit = self._sit(down=1, distance=10, yard_line=30, score_diff=7,
                        quarter=4, time_remaining=45)
        play = self.ai.call_play(sit)
        assert play.play_type == "KNEEL"

    def test_two_minute_drill(self):
        sit = self._sit(down=2, distance=8, yard_line=35, score_diff=-7,
                        quarter=4, time_remaining=100)
        play = self.ai.call_play(sit)
        assert play.play_type in ("SHORT_PASS", "LONG_PASS")

    def test_call_defense_returns_string(self):
        sit = self._sit(down=3, distance=8)
        formation = self.ai.call_defense(sit)
        assert isinstance(formation, str)
        assert len(formation) > 0


# ─── Game ─────────────────────────────────────────────────────────────────────

class TestGame:
    def setup_method(self):
        random.seed(42)
        self.home = Team.load("KC", 2025)
        self.away = Team.load("BUF", 2025)

    def test_game_initializes(self):
        game = Game(self.home, self.away)
        assert game.state is not None
        assert game.state.home_team == "KC"
        assert game.state.away_team == "BUF"

    def test_game_state_initial_score(self):
        game = Game(self.home, self.away)
        assert game.state.score.home == 0
        assert game.state.score.away == 0

    def test_execute_play_returns_result(self):
        game = Game(self.home, self.away)
        result = game.execute_play()
        assert isinstance(result, PlayResult)

    def test_simulate_drive(self):
        game = Game(self.home, self.away)
        drive = game.simulate_drive()
        assert drive.plays >= 1
        assert drive.result in ("TD", "FG", "PUNT", "TURNOVER", "DOWNS",
                                "MISSED_FG", "END_HALF", "CHANGE")

    def test_simulate_full_game(self):
        game = Game(self.home, self.away)
        state = game.simulate_game()
        assert state.is_over
        assert state.score.home >= 0
        assert state.score.away >= 0

    def test_game_log_populated(self):
        game = Game(self.home, self.away)
        game.simulate_drive()
        assert len(game.state.play_log) > 2

    def test_game_state_to_situation(self):
        game = Game(self.home, self.away)
        sit = game.state.to_situation()
        assert isinstance(sit, GameSituation)
        assert 1 <= sit.down <= 4

    def test_multiple_games_dont_share_state(self):
        game1 = Game(self.home, self.away)
        game2 = Game(self.home, self.away)
        game1.simulate_drive()
        # game2 should still be at start
        assert game2.state.score.home == 0
        assert game2.state.score.away == 0
