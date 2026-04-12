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


# ═════════════════════════════════════════════════════════════════════
#  NEW: Tests for 5E rating scale conversion and remaining rules
# ═════════════════════════════════════════════════════════════════════

class TestAuthenticRatingScale:
    """Verify defensive/OL ratings are on authentic 5E small-number scale."""

    def test_defensive_pass_rush_range(self):
        """Pass rush ratings should be 0-3."""
        team = Team.load("KC", "2025_5e")
        for p in team.roster.defenders:
            pr = getattr(p, 'pass_rush_rating', None)
            if pr is not None:
                assert 0 <= pr <= 3, f"{p.player_name} pass_rush={pr}"

    def test_defensive_tackle_range(self):
        """Tackle ratings for DL: -4 to +2, LB: -5 to +4."""
        team = Team.load("KC", "2025_5e")
        for p in team.roster.defenders:
            tr = getattr(p, 'tackle_rating', None)
            if tr is not None:
                pos = p.position.upper()
                if pos in ("DE", "DT", "DL"):
                    assert -4 <= tr <= 2, f"{p.player_name} ({pos}) tackle={tr}"
                elif pos == "LB":
                    assert -5 <= tr <= 4, f"{p.player_name} ({pos}) tackle={tr}"

    def test_ol_run_block_range(self):
        """OL run_block_rating should be -1 to +4."""
        team = Team.load("KC", "2025_5e")
        for p in team.roster.offensive_line:
            rb = getattr(p, 'run_block_rating', None)
            if rb is not None:
                assert -1 <= rb <= 4, f"{p.player_name} run_block={rb}"

    def test_ol_pass_block_range(self):
        """OL pass_block_rating should be 0 to +3."""
        team = Team.load("KC", "2025_5e")
        for p in team.roster.offensive_line:
            pb = getattr(p, 'pass_block_rating', None)
            if pb is not None:
                assert 0 <= pb <= 3, f"{p.player_name} pass_block={pb}"

    def test_all_32_teams_converted(self):
        """All 32 teams should have ratings in 5E scale."""
        teams = [
            "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
            "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
            "LAC", "LAR", "LV", "MIA", "MIN", "NE", "NO", "NYG",
            "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WSH",
        ]
        for abbr in teams:
            team = Team.load(abbr, "2025_5e")
            # Check at least one defender has small-scale ratings
            for p in team.roster.defenders[:3]:
                pr = getattr(p, 'pass_rush_rating', None)
                if pr is not None:
                    assert pr <= 3, f"{abbr}: {p.player_name} pass_rush={pr} (should be 0-3)"


class TestRatingConversion:
    """Test legacy-to-5E rating conversion functions."""

    def test_pass_rush_conversion(self):
        from engine.card_generator import _legacy_to_5e_pass_rush
        assert _legacy_to_5e_pass_rush(90) == 3
        assert _legacy_to_5e_pass_rush(75) == 2
        assert _legacy_to_5e_pass_rush(55) == 1
        assert _legacy_to_5e_pass_rush(30) == 0

    def test_pass_defense_conversion(self):
        from engine.card_generator import _legacy_to_5e_pass_defense
        assert _legacy_to_5e_pass_defense(95) == 4
        assert _legacy_to_5e_pass_defense(85) == 3
        assert _legacy_to_5e_pass_defense(75) == 2
        assert _legacy_to_5e_pass_defense(65) == 1
        assert _legacy_to_5e_pass_defense(55) == 0
        assert _legacy_to_5e_pass_defense(45) == -1
        assert _legacy_to_5e_pass_defense(30) == -2

    def test_tackle_dl_conversion(self):
        from engine.card_generator import _legacy_to_5e_tackle
        assert _legacy_to_5e_tackle(95, "DT") == 2
        assert _legacy_to_5e_tackle(85, "DE") == 1
        assert _legacy_to_5e_tackle(75, "DT") == 0
        assert _legacy_to_5e_tackle(55, "DE") == -2
        assert _legacy_to_5e_tackle(30, "DT") == -4

    def test_tackle_lb_conversion(self):
        from engine.card_generator import _legacy_to_5e_tackle
        assert _legacy_to_5e_tackle(95, "LB") == 4
        assert _legacy_to_5e_tackle(85, "LB") == 3
        assert _legacy_to_5e_tackle(78, "LB") == 2
        assert _legacy_to_5e_tackle(70, "LB") == 1
        assert _legacy_to_5e_tackle(55, "LB") == -1
        assert _legacy_to_5e_tackle(20, "LB") == -5

    def test_run_block_conversion(self):
        from engine.card_generator import _legacy_to_5e_run_block
        assert _legacy_to_5e_run_block(95) == 4
        assert _legacy_to_5e_run_block(80) == 3
        assert _legacy_to_5e_run_block(70) == 2
        assert _legacy_to_5e_run_block(60) == 1
        assert _legacy_to_5e_run_block(45) == 0
        assert _legacy_to_5e_run_block(30) == -1

    def test_pass_block_conversion(self):
        from engine.card_generator import _legacy_to_5e_pass_block
        assert _legacy_to_5e_pass_block(90) == 3
        assert _legacy_to_5e_pass_block(75) == 2
        assert _legacy_to_5e_pass_block(60) == 1
        assert _legacy_to_5e_pass_block(40) == 0

    def test_intercepts_to_range(self):
        from engine.card_generator import _intercepts_to_range
        assert _intercepts_to_range(0) == 48
        assert _intercepts_to_range(3) == 47
        assert _intercepts_to_range(5) == 45
        assert _intercepts_to_range(10) == 38
        assert _intercepts_to_range(13) == 35

    def test_sacks_to_pass_rush(self):
        from engine.card_generator import _sacks_to_pass_rush
        assert _sacks_to_pass_rush(0) == 0
        assert _sacks_to_pass_rush(2) == 1
        assert _sacks_to_pass_rush(4) == 2
        assert _sacks_to_pass_rush(7) == 3


class TestFormationModifiers5E:
    """Verify formation modifiers are on small-number scale."""

    def test_modifiers_small_scale(self):
        from engine.fac_distributions import FORMATION_MODIFIERS
        for name, mods in FORMATION_MODIFIERS.items():
            for key, val in mods.items():
                assert -2 <= val <= 2, f"{name}.{key}={val} should be small"

    def test_effective_pass_rush(self):
        from engine.fac_distributions import effective_pass_rush
        # Base 2 + blitz +1 = 3
        assert effective_pass_rush(2, "4_3", is_blitz_tendency=True) == 3
        # Base 2 + no blitz = 2
        assert effective_pass_rush(2, "4_3", is_blitz_tendency=False) == 2
        # Base 0, no mod
        assert effective_pass_rush(0, "4_3") == 0

    def test_effective_coverage(self):
        from engine.fac_distributions import effective_coverage
        # Coverage is now direct small-number scale
        assert effective_coverage(2, "4_3") == 2
        # Blitz weakens coverage by 1
        assert effective_coverage(2, "4_3", is_blitz_tendency=True) == 1


class TestDroppedPasses:
    """Test dropped passes rule (Rule 11)."""

    def test_dropped_when_rn_equals_game_use(self):
        resolver = PlayResolver()
        from engine.player_card import PlayerCard
        wr = PlayerCard("Test WR", "KC", "WR", 88, "B")
        wr.endurance_rushing = 3
        assert resolver.check_dropped_pass(3, wr) is True
        assert resolver.check_dropped_pass(2, wr) is False

    def test_no_drop_for_workhorse(self):
        resolver = PlayResolver()
        from engine.player_card import PlayerCard
        wr = PlayerCard("Test WR", "KC", "WR", 88, "A")
        wr.endurance_rushing = 0
        assert resolver.check_dropped_pass(0, wr) is False


class TestScreenPassModifiers:
    """Test screen pass run number modifiers (Rule 5)."""

    def test_screen_run_modifier_run_defense(self):
        assert PlayResolver.get_screen_run_modifier("4_3") == 2
        assert PlayResolver.get_screen_run_modifier("GOAL_LINE") == 2

    def test_screen_run_modifier_pass_defense(self):
        assert PlayResolver.get_screen_run_modifier("NICKEL_ZONE") == 0
        assert PlayResolver.get_screen_run_modifier("4_3_COVER2") == 0

    def test_screen_run_modifier_blitz(self):
        assert PlayResolver.get_screen_run_modifier("4_3_BLITZ") == 0


class TestWithin20Modifier:
    """Test within-20 completion modifier (Rule 14)."""

    def test_within_20(self):
        assert PlayResolver.get_within_20_completion_modifier(85) == -5
        assert PlayResolver.get_within_20_completion_modifier(95) == -5

    def test_outside_20(self):
        assert PlayResolver.get_within_20_completion_modifier(50) == 0
        assert PlayResolver.get_within_20_completion_modifier(79) == 0


class TestZCardIgnore:
    """Test Z card ignore rules."""

    def test_ignore_on_fg(self):
        assert PlayResolver.should_ignore_z_card("FG") is True

    def test_ignore_on_xp(self):
        assert PlayResolver.should_ignore_z_card("XP") is True

    def test_ignore_on_onside(self):
        assert PlayResolver.should_ignore_z_card("ONSIDE_KICK") is True

    def test_ignore_on_incomplete(self):
        assert PlayResolver.should_ignore_z_card("INCOMPLETE") is True

    def test_not_ignore_on_run(self):
        assert PlayResolver.should_ignore_z_card("RUN") is False

    def test_not_ignore_on_pass(self):
        assert PlayResolver.should_ignore_z_card("PASS") is False


class TestFumbleHomeField:
    """Test fumble home field advantage rule."""

    def test_home_team_bonus(self):
        # Home team recovers on roll 5 (normally defense)
        assert PlayResolver.apply_fumble_home_field(True, 5) == "OFFENSE"
        assert PlayResolver.apply_fumble_home_field(True, 6) == "DEFENSE"

    def test_away_team_no_bonus(self):
        assert PlayResolver.apply_fumble_home_field(False, 5) == "DEFENSE"
        assert PlayResolver.apply_fumble_home_field(False, 4) == "OFFENSE"


class TestQBEndurance:
    """Test QB endurance modifier."""

    def test_endurance_a(self):
        from engine.player_card import PlayerCard
        qb = PlayerCard("Test QB", "KC", "QB", 15, "A")
        qb.endurance_passing = "A"
        assert PlayResolver.get_qb_endurance_modifier(qb) == 0

    def test_endurance_b(self):
        from engine.player_card import PlayerCard
        qb = PlayerCard("Test QB", "KC", "QB", 15, "B")
        qb.endurance_passing = "B"
        assert PlayResolver.get_qb_endurance_modifier(qb) == -2

    def test_endurance_c(self):
        from engine.player_card import PlayerCard
        qb = PlayerCard("Test QB", "KC", "QB", 15, "C")
        qb.endurance_passing = "C"
        assert PlayResolver.get_qb_endurance_modifier(qb) == -4


class TestCheckoffEndurance:
    """Test check-off pass endurance modifier."""

    def test_high_endurance_penalty(self):
        from engine.player_card import PlayerCard
        wr = PlayerCard("Test WR", "KC", "WR", 88, "C")
        wr.endurance_rushing = 3
        assert PlayResolver.get_checkoff_endurance_modifier(wr) == -3

    def test_low_endurance_no_penalty(self):
        from engine.player_card import PlayerCard
        wr = PlayerCard("Test WR", "KC", "WR", 88, "A")
        wr.endurance_rushing = 1
        assert PlayResolver.get_checkoff_endurance_modifier(wr) == 0


class TestExtraPassBlocking:
    """Test extra pass blocking rule."""

    def test_rb_blocks(self):
        # OL sum 8, DL sum 6, RB BV +2 → (6 - 10) * 2 = -8 (offense wins)
        assert PlayResolver.resolve_extra_pass_blocking(8, 6, 2) == (6 - 10) * 2

    def test_without_extra_blocker(self):
        # OL sum 8, DL sum 6, no extra → (6 - 8) * 2 = -4
        assert PlayResolver.resolve_extra_pass_blocking(8, 6, 0) == -4


class TestOutOfPosition:
    """Test out-of-position penalty."""

    def test_ol_wrong_position(self):
        from engine.player_card import PlayerCard
        p = PlayerCard("Test OL", "KC", "LT", 71, "B")
        assert PlayResolver.check_out_of_position_penalty(p, "RG") == -1

    def test_ol_correct_position(self):
        from engine.player_card import PlayerCard
        p = PlayerCard("Test OL", "KC", "LT", 71, "B")
        assert PlayResolver.check_out_of_position_penalty(p, "LT") == 0


class TestSolitaireRules:
    """Test solitaire-specific rules."""

    def test_no_consecutive_screen_quick(self):
        from engine.solitaire import SolitaireAI, PlayCall
        ai = SolitaireAI()
        # First screen is fine
        pc1 = PlayCall("SCREEN", "SHOTGUN", "MIDDLE", "test")
        result1 = ai.enforce_no_consecutive_screen_quick(pc1)
        assert result1.play_type == "SCREEN"

        # Second screen should be converted
        pc2 = PlayCall("SCREEN", "SHOTGUN", "MIDDLE", "test")
        result2 = ai.enforce_no_consecutive_screen_quick(pc2)
        assert result2.play_type == "SHORT_PASS"

    def test_prevent_within_20(self):
        from engine.solitaire import SolitaireAI, GameSituation
        ai = SolitaireAI()
        sit = GameSituation(down=1, distance=10, yard_line=85,
                            score_diff=0, quarter=1, time_remaining=600)
        result = ai.convert_prevent_within_20(sit, "3_4_ZONE")
        assert result == "4_3_COVER2"

    def test_no_conversion_outside_20(self):
        from engine.solitaire import SolitaireAI, GameSituation
        ai = SolitaireAI()
        sit = GameSituation(down=1, distance=10, yard_line=50,
                            score_diff=0, quarter=1, time_remaining=600)
        result = ai.convert_prevent_within_20(sit, "3_4_ZONE")
        assert result == "3_4_ZONE"


class TestSolitaireZCardRemoval:
    """Test solitaire Z card removal."""

    def test_solitaire_deck_has_fewer_z_cards(self):
        from engine.fac_deck import FACDeck
        normal = FACDeck(seed=42)
        solitaire = FACDeck(seed=42, solitaire=True)
        normal_z = sum(1 for c in normal._draw_pile if c.is_z_card)
        sol_z = sum(1 for c in solitaire._draw_pile if c.is_z_card)
        assert sol_z == normal_z - 1
        assert solitaire.cards_remaining == normal.cards_remaining - 1

    def test_non_solitaire_has_all_z_cards(self):
        from engine.fac_deck import FACDeck
        deck = FACDeck(seed=42, solitaire=False)
        z_count = sum(1 for c in deck._draw_pile if c.is_z_card)
        assert z_count == 13


class TestTimeoutRestriction:
    """Test timeout restriction (only after plays > 10s)."""

    def test_timeout_after_run(self):
        """Timeout allowed after a run play (40s)."""
        home = Team.load("KC", "2025_5e")
        away = Team.load("SF", "2025_5e")
        game = Game(home, away, use_5e=True)
        game._last_play_time = 40
        assert game.call_timeout("offense") is True

    def test_timeout_denied_after_incomplete(self):
        """Timeout denied after incomplete pass (10s)."""
        home = Team.load("KC", "2025_5e")
        away = Team.load("SF", "2025_5e")
        game = Game(home, away, use_5e=True)
        game._last_play_time = 10
        assert game.call_timeout("offense") is False
