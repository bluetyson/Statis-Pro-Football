"""Tests for 5th-edition rules implementation.

Covers:
  - Timing constants (40s/10s per 5E Timing Table)
  - Offensive strategies (Flop, Sneak, Draw, Play-Action)
  - Play restrictions (long pass within 20, screen within 5, inside run max loss)
  - BV vs TV blocking battle
  - Onside kick / Squib kick
  - Interception improvements (Point of Interception, INC-range, PN 48 check)
  - Endurance tracking
  - Injury duration tracking
  - Half-distance penalty
  - Inside runs never OOB
  - 45-player rosters
"""

import random
import pytest
from engine.team import Team
from engine.game import Game
from engine.play_resolver import PlayResolver, PlayResult
from engine.fac_deck import FACDeck
from engine.solitaire import PlayCall


class TestRosterExpansion:
    """Verify all 32 teams now have 45+ players with proper positional breakdown."""

    TEAMS = [
        "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
        "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
        "LAC", "LAR", "LV", "MIA", "MIN", "NE", "NO", "NYG",
        "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WSH",
    ]

    def test_all_teams_have_45_plus_players(self):
        for abbr in self.TEAMS:
            team = Team.load(abbr, "2025_5e")
            roster = team.roster
            total = len(roster.all_players())
            assert total >= 47, f"{abbr} has only {total} players (need 47+)"

    def test_position_counts(self):
        """Spot-check KC roster has correct position breakdown."""
        team = Team.load("KC", "2025_5e")
        roster = team.roster
        assert len(roster.qbs) >= 3, f"KC QBs: {len(roster.qbs)}"
        assert len(roster.rbs) >= 6, f"KC RBs: {len(roster.rbs)}"
        assert len(roster.wrs) >= 5, f"KC WRs: {len(roster.wrs)}"
        assert len(roster.tes) >= 3, f"KC TEs: {len(roster.tes)}"
        assert len(roster.offensive_line) >= 8, f"KC OL: {len(roster.offensive_line)}"
        # DL + LB + DB = 21+
        dl_lb_db = [p for p in roster.defenders]
        assert len(dl_lb_db) >= 21, f"KC DEF: {len(dl_lb_db)}"


class TestTimingConstants:
    """Verify timing matches 5E Timing Table (Page 4)."""

    def setup_method(self):
        random.seed(42)
        home = Team.load("KC", "2025_5e")
        away = Team.load("BUF", "2025_5e")
        self.game = Game(home, away, use_5e=True, seed=42)

    def test_run_is_40_seconds(self):
        result = PlayResult(play_type="RUN", yards_gained=5, result="GAIN")
        assert self.game._calculate_time(result) == 40

    def test_complete_pass_is_40_seconds(self):
        result = PlayResult(play_type="PASS", yards_gained=12, result="COMPLETE")
        assert self.game._calculate_time(result) == 40

    def test_sack_is_40_seconds(self):
        result = PlayResult(play_type="PASS", yards_gained=-5, result="SACK")
        assert self.game._calculate_time(result) == 40

    def test_incomplete_is_10_seconds(self):
        result = PlayResult(play_type="PASS", yards_gained=0, result="INCOMPLETE")
        assert self.game._calculate_time(result) == 10

    def test_oob_is_10_seconds(self):
        result = PlayResult(play_type="RUN", yards_gained=5, result="OOB",
                            out_of_bounds=True)
        assert self.game._calculate_time(result) == 10

    def test_penalty_is_10_seconds(self):
        result = PlayResult(play_type="RUN", yards_gained=0, result="PENALTY",
                            penalty={"type": "HOLDING_OFF", "yards": 10})
        assert self.game._calculate_time(result) == 10

    def test_touchdown_is_10_seconds(self):
        result = PlayResult(play_type="RUN", yards_gained=65, result="TD",
                            is_touchdown=True)
        assert self.game._calculate_time(result) == 10

    def test_kneel_is_40_seconds(self):
        result = PlayResult(play_type="KNEEL", yards_gained=-1, result="KNEEL")
        assert self.game._calculate_time(result) == 40

    def test_punt_is_10_seconds(self):
        result = PlayResult(play_type="PUNT", yards_gained=45, result="PUNT")
        assert self.game._calculate_time(result) == 10

    def test_field_goal_is_5_seconds(self):
        result = PlayResult(play_type="FG", yards_gained=0, result="FG_GOOD")
        assert self.game._calculate_time(result) == 5


class TestPlayRestrictions:
    """Test play restriction enforcement per 5E rules."""

    def test_long_pass_blocked_inside_20(self):
        """No long pass when scrimmage is within opponent's 20."""
        assert PlayResolver.check_long_pass_restriction(80) is True
        assert PlayResolver.check_long_pass_restriction(90) is True
        assert PlayResolver.check_long_pass_restriction(79) is False
        assert PlayResolver.check_long_pass_restriction(50) is False

    def test_screen_blocked_inside_5(self):
        """No screen pass within 5-yard line."""
        assert PlayResolver.check_screen_pass_restriction(95) is True
        assert PlayResolver.check_screen_pass_restriction(99) is True
        assert PlayResolver.check_screen_pass_restriction(94) is False

    def test_inside_run_max_loss_3(self):
        """Inside runs have max loss of 3 yards."""
        assert PlayResolver.apply_inside_run_max_loss(-5, "IL") == -3
        assert PlayResolver.apply_inside_run_max_loss(-4, "IR") == -3
        assert PlayResolver.apply_inside_run_max_loss(-3, "IL") == -3
        assert PlayResolver.apply_inside_run_max_loss(-2, "IL") == -2
        assert PlayResolver.apply_inside_run_max_loss(5, "IL") == 5

    def test_sweep_no_loss_limit(self):
        """Sweeps have no loss limit."""
        assert PlayResolver.apply_inside_run_max_loss(-7, "SL") == -7
        assert PlayResolver.apply_inside_run_max_loss(-10, "SR") == -10


class TestOffensiveStrategies:
    """Test 5E offensive strategy implementations."""

    def setup_method(self):
        random.seed(42)
        self.resolver = PlayResolver()
        from engine.card_generator import CardGenerator
        gen = CardGenerator(seed=42)
        self.qb = gen.generate_qb_card_authentic(
            name="TestQB", team="TST", number=12,
            comp_pct=0.65, ypa=7.5, int_rate=0.025,
            sack_rate=0.07, grade="A",
        )

    def test_flop_gives_minus_1(self):
        """Flop (QB Dive) gives -1 yard, no fumble risk."""
        result = self.resolver.resolve_flop(self.qb)
        assert result.yards_gained == -1
        assert result.strategy == "FLOP"
        assert result.play_type == "RUN"
        assert result.result == "GAIN"

    def test_sneak_gives_0_or_1(self):
        """Sneak gives 0 (odd PN) or 1 (even PN) yard."""
        deck = FACDeck(seed=42)
        result = self.resolver.resolve_sneak(self.qb, deck)
        assert result.yards_gained in (0, 1)
        assert result.strategy == "SNEAK"
        assert result.play_type == "RUN"

    def test_draw_modifies_yards(self):
        """Draw play applies RN modifier based on defensive formation."""
        deck = FACDeck(seed=42)
        from engine.card_generator import CardGenerator
        gen = CardGenerator(seed=42)
        rb = gen.generate_rb_card_authentic(
            name="TestRB", team="TST", number=26,
            ypc=4.5, fumble_rate=0.015, grade="B",
        )
        fac_card = deck.draw()
        result = self.resolver.resolve_draw(
            fac_card, deck, rb, "4_3",
            defense_run_stop=50,
        )
        assert result.strategy == "DRAW"
        assert "Draw play" in result.description


class TestBVTVBattle:
    """Test BV vs TV blocking battle per 5E rules."""

    def test_empty_box_plus_2(self):
        """Empty defensive box gives +2 yards."""
        mod = PlayResolver.resolve_bv_tv_battle(0, 0, empty_box=True)
        assert mod == 2

    def test_empty_box_with_blocker(self):
        """Empty box with blocker: add BV only, no +2."""
        mod = PlayResolver.resolve_bv_tv_battle(3, 0, empty_box=True)
        assert mod == 3

    def test_two_defenders_minus_4(self):
        """Two defenders in box: TV = -4 regardless of printed values."""
        mod = PlayResolver.resolve_bv_tv_battle(2, 1, two_defenders=True)
        # diff = 2 - (-4) = 6 > 0 → add BV
        assert mod == 2

    def test_offense_wins(self):
        """When BV > TV, add BV."""
        mod = PlayResolver.resolve_bv_tv_battle(3, 1)
        assert mod == 3

    def test_defense_wins(self):
        """When TV > BV, subtract TV."""
        mod = PlayResolver.resolve_bv_tv_battle(1, 3)
        assert mod == -3

    def test_tied(self):
        """When BV == TV, no modification."""
        mod = PlayResolver.resolve_bv_tv_battle(2, 2)
        assert mod == 0


class TestOnsideKick:
    """Test onside kick mechanics per 5E rules."""

    def test_onside_kick_recoverable(self):
        """PN 1-11 = kicking team recovers."""
        resolver = PlayResolver()
        random.seed(1)  # Set seed so we get deterministic results
        deck = FACDeck(seed=1)
        # Run multiple times and verify outcomes follow rules
        recovered = 0
        for _ in range(100):
            result = resolver.resolve_onside_kick(deck)
            if result.result == "ONSIDE_RECOVERED":
                recovered += 1
        # Probability of recovery = 11/48 ≈ 22.9%
        assert 5 <= recovered <= 50  # Reasonable range

    def test_onside_defense_reduces_recovery(self):
        """With onside defense, recovery threshold is lower (PN 1-7)."""
        resolver = PlayResolver()
        deck = FACDeck(seed=42)
        recovered = 0
        for _ in range(100):
            result = resolver.resolve_onside_kick(deck, onside_defense=True)
            if result.result == "ONSIDE_RECOVERED":
                recovered += 1
        # Probability = 7/48 ≈ 14.6%, should be less than normal
        assert recovered < 30


class TestSquibKick:
    """Test squib kick mechanics per 5E rules."""

    def test_squib_kick_returns_better_position(self):
        resolver = PlayResolver()
        deck = FACDeck(seed=42)
        result = resolver.resolve_squib_kick(deck)
        assert result.play_type == "KICKOFF"
        # Squib kicks generally give better field position to returner
        assert result.yards_gained >= 15  # Should be well past the 15


class TestInterceptionImprovements:
    """Test interception improvements per 5E rules."""

    def test_point_of_interception_screen(self):
        """Screen: POI = RN / 2."""
        poi = PlayResolver.calculate_point_of_interception("SCREEN", 8, 50)
        # POI yards = 8/2 = 4; INT at YL 54 → defense gets at YL 46
        assert poi == 46

    def test_point_of_interception_quick(self):
        """Quick: POI = RN."""
        poi = PlayResolver.calculate_point_of_interception("QUICK", 6, 50)
        # POI yards = 6; INT at YL 56 → defense gets at YL 44
        assert poi == 44

    def test_point_of_interception_short(self):
        """Short: POI = RN × 2."""
        poi = PlayResolver.calculate_point_of_interception("SHORT", 6, 50)
        # POI yards = 12; INT at YL 62 → defense gets at YL 38
        assert poi == 38

    def test_point_of_interception_long(self):
        """Long: POI = RN × 4."""
        poi = PlayResolver.calculate_point_of_interception("LONG", 6, 50)
        # POI yards = 24; INT at YL 74 → defense gets at YL 26
        assert poi == 26

    def test_poi_past_goal_line_touchback(self):
        """If POI goes past goal line → touchback at 20."""
        poi = PlayResolver.calculate_point_of_interception("LONG", 12, 80)
        # POI yards = 48; YL 80+48 = 128 >= 100 → touchback at 20
        assert poi == 20


class TestEnduranceTracking:
    """Test endurance system per 5E rules."""

    def test_track_endurance(self):
        resolver = PlayResolver()
        resolver.track_endurance("TestPlayer")
        assert resolver._endurance_tracker["TestPlayer"] == 1
        resolver.track_endurance("TestPlayer")
        assert resolver._endurance_tracker["TestPlayer"] == 2

    def test_reset_endurance(self):
        resolver = PlayResolver()
        resolver.track_endurance("TestPlayer")
        resolver.track_endurance("TestPlayer")
        resolver.reset_endurance("TestPlayer")
        assert resolver._endurance_tracker["TestPlayer"] == 0

    def test_endurance_0_no_violation(self):
        """Endurance 0 (workhorse) has no restriction."""
        resolver = PlayResolver()
        from engine.player_card import PlayerCard
        player = PlayerCard(player_name="Test", team="TST", number=26,
                            position="RB", overall_grade="A", endurance_rushing=0)
        resolver.track_endurance(player.player_name)
        resolver.track_endurance(player.player_name)
        assert resolver.check_endurance_violation(player) is None

    def test_endurance_1_violation(self):
        """Endurance 1: violated if used on consecutive play."""
        resolver = PlayResolver()
        from engine.player_card import PlayerCard
        player = PlayerCard(player_name="Test", team="TST", number=26,
                            position="RB", overall_grade="C", endurance_rushing=1)
        resolver.track_endurance(player.player_name)
        assert resolver.check_endurance_violation(player) == "endurance_1"


class TestInjuryDuration:
    """Test injury duration tracking per 5E Injury Table."""

    def test_injury_table_ranges(self):
        resolver = PlayResolver()
        assert resolver.resolve_injury_duration(5) == 2    # PN 1-10 → 2 plays
        assert resolver.resolve_injury_duration(15) == 4   # PN 11-20 → 4 plays
        assert resolver.resolve_injury_duration(25) == 6   # PN 21-30 → 6 plays
        assert resolver.resolve_injury_duration(33) == 15  # PN 31-35 → rest of Q
        assert resolver.resolve_injury_duration(40) == 60  # PN 36-43 → rest of game
        assert resolver.resolve_injury_duration(45) == 99  # PN 44-48 → rest of game+

    def test_injure_and_check(self):
        resolver = PlayResolver()
        resolver.injure_player("TestPlayer", 5)
        assert resolver.is_injured("TestPlayer") is True
        for _ in range(5):
            resolver.tick_injuries()
        assert resolver.is_injured("TestPlayer") is False


class TestHalfDistancePenalty:
    """Test half-distance-to-goal rule for penalties."""

    def test_offense_penalty_inside_own_15(self):
        """15y penalty at own 10 → half distance = 5."""
        actual = PlayResolver.apply_half_distance_penalty(15, 10, True)
        assert actual == 5

    def test_defense_penalty_near_goal(self):
        """15y defensive penalty at opponent's 8 → half distance = 4."""
        actual = PlayResolver.apply_half_distance_penalty(15, 92, False)
        assert actual == 4

    def test_normal_penalty_no_reduction(self):
        """Penalty at midfield → no reduction."""
        actual = PlayResolver.apply_half_distance_penalty(10, 50, True)
        assert actual == 10


class TestGameWithExpandedRosters:
    """Test that games play correctly with 45-player rosters."""

    def test_game_runs_to_completion(self):
        """Simulate a full 5E game with expanded rosters."""
        random.seed(42)
        home = Team.load("KC", "2025_5e")
        away = Team.load("BUF", "2025_5e")
        game = Game(home, away, use_5e=True, seed=42)
        state = game.simulate_game()
        assert state.is_over is True
        assert state.quarter >= 4

    def test_all_32_teams_can_load(self):
        """All 32 teams load correctly with expanded rosters."""
        teams = [
            "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
            "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
            "LAC", "LAR", "LV", "MIA", "MIN", "NE", "NO", "NYG",
            "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WSH",
        ]
        for abbr in teams:
            team = Team.load(abbr, "2025_5e")
            assert team is not None
            assert team.abbreviation == abbr

    def test_multiple_games_different_teams(self):
        """Multiple games with different team matchups work."""
        matchups = [("SF", "DAL"), ("BAL", "KC"), ("DET", "PHI")]
        for home_abbr, away_abbr in matchups:
            random.seed(99)
            home = Team.load(home_abbr, "2025_5e")
            away = Team.load(away_abbr, "2025_5e")
            game = Game(home, away, use_5e=True, seed=99)
            state = game.simulate_game()
            assert state.is_over is True


class TestPlayCallStrategy:
    """Test PlayCall strategy field works correctly."""

    def test_play_call_with_strategy(self):
        pc = PlayCall(
            play_type="SHORT_PASS", formation="SHOTGUN",
            direction="RIGHT", reasoning="test", strategy="PLAY_ACTION",
        )
        assert pc.strategy == "PLAY_ACTION"

    def test_play_call_without_strategy(self):
        pc = PlayCall(
            play_type="RUN", formation="I_FORM",
            direction="LEFT", reasoning="test",
        )
        assert pc.strategy is None
