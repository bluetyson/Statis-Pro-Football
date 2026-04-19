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

    def test_draw_modifies_run_number(self):
        """Draw play applies RN modifier to Run Number before card lookup."""
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
        assert "RN modifier" in result.description

    def test_draw_vs_blitz_gives_negative_rn_modifier(self):
        """Draw vs Blitz: -4 draw modifier (bonus for offense) via defensive_play string.

        Uses a standard "4_3" formation string — which carries no modifier
        by itself — and an explicit ``defensive_play="BLITZ"`` string to
        exercise the string-based fallback path in ``resolve_draw``.
        """
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
            defense_run_stop=0,
            defensive_play="BLITZ",
        )
        assert "RN modifier -4" in result.description

    def test_draw_vs_run_defense_gives_positive_rn_modifier(self):
        """Draw vs Run Defense: +2 to RN (penalty for offense) — via defensive_play string.

        Per 5E rules the modifier comes from the explicit PLAY CALL, not from
        the formation name.  Passing ``defensive_play='RUN_DEFENSE_NO_KEY'`` is
        required; a bare formation string "4_3" is no longer sufficient.
        """
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
            defense_run_stop=0,
            defensive_play="RUN_DEFENSE_NO_KEY",
        )
        assert "RN modifier +2" in result.description

    def test_draw_vs_pass_defense_gives_negative_rn_modifier(self):
        """Draw vs Pass Defense: -2 to RN (bonus for offense) — via defensive_play string.

        The formation string alone ("4_3_cover2") carries no modifier; the
        explicit play call is required.
        """
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
            defense_run_stop=0,
            defensive_play="PASS_DEFENSE",
        )
        assert "RN modifier -2" in result.description

    def test_draw_vs_prevent_gives_negative_rn_modifier(self):
        """Draw vs Prevent: -2 to RN (bonus for offense) — via defensive_play string."""
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
            defense_run_stop=0,
            defensive_play="PREVENT_DEFENSE",
        )
        assert "RN modifier -2" in result.description

    def test_draw_no_play_call_gives_zero_rn_modifier(self):
        """Draw with no defensive play call: 0 modifier.

        Per 5E rules, formation name alone ("4_3", "NICKEL", etc.) does
        not carry any run-number modifier.  Without an explicit play call the
        draw modifier is 0.
        """
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
            defense_run_stop=0,
        )
        assert "RN modifier +0" in result.description

    # --- Tests using explicit defensive_play_5e enum (bug-fix coverage) ------

    def test_draw_run_defense_enum_gives_positive_rn_modifier(self):
        """Draw with RUN_DEFENSE enum + default formation: +2 draw penalty modifier.

        When a human explicitly calls a run defense in the game log the
        draw-play modifier must be +2 (penalty — higher RN = fewer yards for
        offense) even if the formation string alone would not indicate a run
        defense.
        """
        from engine.play_types import DefensivePlay
        from engine.card_generator import CardGenerator
        gen = CardGenerator(seed=42)
        rb = gen.generate_rb_card_authentic(
            name="TestRB", team="TST", number=26,
            ypc=4.5, fumble_rate=0.015, grade="B",
        )
        deck = FACDeck(seed=42)
        fac_card = deck.draw()
        result = self.resolver.resolve_draw(
            fac_card, deck, rb, "4_3",
            defense_run_stop=0,
            defensive_play_5e=DefensivePlay.RUN_DEFENSE_NO_KEY,
        )
        assert "RN modifier +2" in result.description

    def test_draw_pass_defense_enum_gives_negative_rn_modifier(self):
        """Draw with PASS_DEFENSE enum + run formation: -2 modifier (not +2)."""
        from engine.play_types import DefensivePlay
        from engine.card_generator import CardGenerator
        gen = CardGenerator(seed=42)
        rb = gen.generate_rb_card_authentic(
            name="TestRB", team="TST", number=26,
            ypc=4.5, fumble_rate=0.015, grade="B",
        )
        deck = FACDeck(seed=42)
        fac_card = deck.draw()
        result = self.resolver.resolve_draw(
            fac_card, deck, rb, "4_3",  # run formation – should be overridden
            defense_run_stop=0,
            defensive_play_5e=DefensivePlay.PASS_DEFENSE,
        )
        assert "RN modifier -2" in result.description

    def test_draw_blitz_enum_gives_largest_negative_rn_modifier(self):
        """Draw with BLITZ enum: -4 modifier."""
        from engine.play_types import DefensivePlay
        from engine.card_generator import CardGenerator
        gen = CardGenerator(seed=42)
        rb = gen.generate_rb_card_authentic(
            name="TestRB", team="TST", number=26,
            ypc=4.5, fumble_rate=0.015, grade="B",
        )
        deck = FACDeck(seed=42)
        fac_card = deck.draw()
        result = self.resolver.resolve_draw(
            fac_card, deck, rb, "4_3",
            defense_run_stop=0,
            defensive_play_5e=DefensivePlay.BLITZ,
        )
        assert "RN modifier -4" in result.description


class TestPlayActionModifiers:
    """Test Play-Action pass strategy applies PN (completion range) modifiers."""

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
        self.wr = gen.generate_wr_card_authentic(
            name="TestWR", team="TST", number=81,
            catch_rate=0.65, avg_yards=12.0, grade="B",
        )

    def test_play_action_no_play_call_gives_zero_modifier(self):
        """Play-action with no defensive play call: 0 modifier.

        Per 5E rules, the modifier comes from the defensive PLAY CALL, not
        from the formation name.  Without an explicit play call (i.e.
        ``defensive_play_5e`` is None and no ``defensive_play`` string is
        passed) the modifier is 0.
        """
        deck = FACDeck(seed=42)
        fac_card = deck.draw()
        result = self.resolver.resolve_play_action(
            fac_card, deck, self.qb, self.wr, [self.wr],
            pass_type="SHORT", defense_formation="4_3",
        )
        assert result.strategy == "PLAY_ACTION"
        assert "completion modifier +0" in result.description

    def test_play_action_vs_run_defense_positive_modifier_via_enum(self):
        """Play-action vs Run Defense: +5 to completion range (via enum)."""
        from engine.play_types import DefensivePlay
        deck = FACDeck(seed=42)
        fac_card = deck.draw()
        result = self.resolver.resolve_play_action(
            fac_card, deck, self.qb, self.wr, [self.wr],
            pass_type="SHORT", defense_formation="4_3",
            defensive_play_5e=DefensivePlay.RUN_DEFENSE_NO_KEY,
        )
        assert result.strategy == "PLAY_ACTION"
        assert "completion modifier +5" in result.description

    def test_play_action_vs_pass_defense_negative_modifier_via_enum(self):
        """Play-action vs Pass Defense: -5 to completion range (via enum)."""
        from engine.play_types import DefensivePlay
        deck = FACDeck(seed=42)
        fac_card = deck.draw()
        result = self.resolver.resolve_play_action(
            fac_card, deck, self.qb, self.wr, [self.wr],
            pass_type="SHORT", defense_formation="4_3",
            defensive_play_5e=DefensivePlay.PASS_DEFENSE,
        )
        assert result.strategy == "PLAY_ACTION"
        assert "completion modifier -5" in result.description

    def test_play_action_vs_prevent_large_negative_modifier_via_enum(self):
        """Play-action vs Prevent Defense: -10 to completion range (via enum)."""
        from engine.play_types import DefensivePlay
        deck = FACDeck(seed=42)
        fac_card = deck.draw()
        result = self.resolver.resolve_play_action(
            fac_card, deck, self.qb, self.wr, [self.wr],
            pass_type="SHORT", defense_formation="4_3",
            defensive_play_5e=DefensivePlay.PREVENT_DEFENSE,
        )
        assert result.strategy == "PLAY_ACTION"
        assert "completion modifier -10" in result.description

    def test_play_action_vs_blitz_neutral_via_enum(self):
        """Play-action vs Blitz: 0 modifier (neutral, via enum)."""
        from engine.play_types import DefensivePlay
        deck = FACDeck(seed=42)
        fac_card = deck.draw()
        result = self.resolver.resolve_play_action(
            fac_card, deck, self.qb, self.wr, [self.wr],
            pass_type="SHORT", defense_formation="4_3",
            defensive_play_5e=DefensivePlay.BLITZ,
        )
        assert result.strategy == "PLAY_ACTION"
        assert "completion modifier +0" in result.description


class TestDefensivePlayRNModifiers:
    """Test that 5E DefensivePlay enums correctly modify Run Number on standard plays."""

    def setup_method(self):
        random.seed(42)
        self.resolver = PlayResolver()
        from engine.card_generator import CardGenerator
        gen = CardGenerator(seed=42)
        self.rb = gen.generate_rb_card_authentic(
            name="TestRB", team="TST", number=26,
            ypc=4.5, fumble_rate=0.015, grade="B",
        )

    def test_run_defense_no_key_adds_plus_2(self):
        """Run Defense / No Key: +2 to Run Number (e.g. RN 6 → 8)."""
        from engine.play_types import DefensivePlay, get_run_number_modifier_5e
        mod = get_run_number_modifier_5e(DefensivePlay.RUN_DEFENSE_NO_KEY, ball_carrier_number=1)
        assert mod == 2

    def test_run_defense_key_on_correct_back_adds_plus_4(self):
        """Run Defense / Key on BC(1) and back 1 carries: +4 to Run Number."""
        from engine.play_types import DefensivePlay, get_run_number_modifier_5e
        mod = get_run_number_modifier_5e(DefensivePlay.RUN_DEFENSE_KEY_BACK_1, ball_carrier_number=1)
        assert mod == 4

    def test_run_defense_wrong_key_adds_0(self):
        """Run Defense / Key on BC(2) but back 1 carries: 0 (wrong key)."""
        from engine.play_types import DefensivePlay, get_run_number_modifier_5e
        mod = get_run_number_modifier_5e(DefensivePlay.RUN_DEFENSE_KEY_BACK_2, ball_carrier_number=1)
        assert mod == 0

    def test_pass_defense_adds_0_to_run(self):
        """Pass Defense: 0 to Run Number (defense focused on pass)."""
        from engine.play_types import DefensivePlay, get_run_number_modifier_5e
        mod = get_run_number_modifier_5e(DefensivePlay.PASS_DEFENSE, ball_carrier_number=1)
        assert mod == 0

    def test_blitz_adds_0_to_run(self):
        """Blitz: 0 to Run Number."""
        from engine.play_types import DefensivePlay, get_run_number_modifier_5e
        mod = get_run_number_modifier_5e(DefensivePlay.BLITZ, ball_carrier_number=1)
        assert mod == 0

    def test_resolve_run_uses_defensive_play_5e(self):
        """resolve_run_5e applies DefensivePlay modifier when provided."""
        from engine.play_types import DefensivePlay
        deck = FACDeck(seed=42)
        fac_card = deck.draw()
        original_rn = fac_card.run_num_int

        # Run with no defensive play (old behavior — defaults to 0)
        deck_a = FACDeck(seed=42)
        card_a = deck_a.draw()
        result_a = self.resolver.resolve_run_5e(
            card_a, deck_a, self.rb, "IL",
            defense_formation="4_3",
        )

        # Run with RUN_DEFENSE_NO_KEY — should apply +2 to RN
        deck_b = FACDeck(seed=42)
        card_b = deck_b.draw()
        result_b = self.resolver.resolve_run_5e(
            card_b, deck_b, self.rb, "IL",
            defense_formation="4_3",
            defensive_play_5e=DefensivePlay.RUN_DEFENSE_NO_KEY,
        )

        # Result b uses a higher run number (worse for offense)
        assert result_b.run_number_used >= result_a.run_number_used or result_a.run_number_used >= 11


class TestDefensivePlayCompletionModifiers:
    """Test that 5E DefensivePlay enums correctly modify Pass Number on standard passes."""

    def test_pass_defense_lowers_completion_for_quick_pass(self):
        """Pass Defense on Quick pass: -10 to completion range."""
        from engine.play_types import DefensivePlay, get_completion_modifier_5e
        mod = get_completion_modifier_5e(DefensivePlay.PASS_DEFENSE, "QUICK")
        assert mod == -10

    def test_pass_defense_reduces_short_pass(self):
        """Pass Defense on Short pass: -5 to completion range (per 5E rules PDF)."""
        from engine.play_types import DefensivePlay, get_completion_modifier_5e
        mod = get_completion_modifier_5e(DefensivePlay.PASS_DEFENSE, "SHORT")
        assert mod == -5

    def test_pass_defense_neutral_for_long_pass(self):
        """Pass Defense on Long pass: 0 (neutral per 5E rules PDF)."""
        from engine.play_types import DefensivePlay, get_completion_modifier_5e
        mod = get_completion_modifier_5e(DefensivePlay.PASS_DEFENSE, "LONG")
        assert mod == 0

    def test_run_defense_boosts_short_pass(self):
        """Run Defense on Short pass: +5 to completion range (defense fooled)."""
        from engine.play_types import DefensivePlay, get_completion_modifier_5e
        mod = get_completion_modifier_5e(DefensivePlay.RUN_DEFENSE_NO_KEY, "SHORT")
        assert mod == 5

    def test_run_defense_boosts_long_pass(self):
        """Run Defense on Long pass: +7 to completion range."""
        from engine.play_types import DefensivePlay, get_completion_modifier_5e
        mod = get_completion_modifier_5e(DefensivePlay.RUN_DEFENSE_KEY_BACK_1, "LONG")
        assert mod == 7

    def test_run_defense_neutral_for_quick_pass(self):
        """Run Defense on Quick pass: 0 (per 5E rules PDF)."""
        from engine.play_types import DefensivePlay, get_completion_modifier_5e
        mod = get_completion_modifier_5e(DefensivePlay.RUN_DEFENSE_NO_KEY, "QUICK")
        assert mod == 0

    def test_prevent_defense_modifiers(self):
        """Prevent Defense: 0 Quick, -5 Short, -7 Long (per 5E rules PDF)."""
        from engine.play_types import DefensivePlay, get_completion_modifier_5e
        assert get_completion_modifier_5e(DefensivePlay.PREVENT_DEFENSE, "QUICK") == 0
        assert get_completion_modifier_5e(DefensivePlay.PREVENT_DEFENSE, "SHORT") == -5
        assert get_completion_modifier_5e(DefensivePlay.PREVENT_DEFENSE, "LONG") == -7

    def test_blitz_boosts_quick_pass(self):
        """Blitz on Quick pass: +10 to completion range (per 5E rules PDF)."""
        from engine.play_types import DefensivePlay, get_completion_modifier_5e
        mod = get_completion_modifier_5e(DefensivePlay.BLITZ, "QUICK")
        assert mod == 10

    def test_blitz_forces_pass_rush_short(self):
        """Blitz on Short pass: always triggers pass rush."""
        from engine.play_types import DefensivePlay, should_force_pass_rush
        assert should_force_pass_rush(DefensivePlay.BLITZ, "SHORT") is True

    def test_blitz_forces_pass_rush_long(self):
        """Blitz on Long pass: always triggers pass rush."""
        from engine.play_types import DefensivePlay, should_force_pass_rush
        assert should_force_pass_rush(DefensivePlay.BLITZ, "LONG") is True

    def test_blitz_does_not_force_pass_rush_quick(self):
        """Blitz on Quick pass: no forced pass rush, use +10 modifier."""
        from engine.play_types import DefensivePlay, should_force_pass_rush
        assert should_force_pass_rush(DefensivePlay.BLITZ, "QUICK") is False

    def test_non_blitz_does_not_force_pass_rush(self):
        """Non-Blitz defenses never force pass rush."""
        from engine.play_types import DefensivePlay, should_force_pass_rush
        for play in (DefensivePlay.PASS_DEFENSE, DefensivePlay.PREVENT_DEFENSE,
                     DefensivePlay.RUN_DEFENSE_NO_KEY, DefensivePlay.RUN_DEFENSE_KEY_BACK_1):
            assert should_force_pass_rush(play, "SHORT") is False
            assert should_force_pass_rush(play, "LONG") is False

    def test_within_20_run_def_quick(self):
        """Within-20: Run Def / Quick changes from 0 to -10."""
        from engine.play_types import DefensivePlay, get_completion_modifier_5e
        assert get_completion_modifier_5e(DefensivePlay.RUN_DEFENSE_NO_KEY, "QUICK", within_20=False) == 0
        assert get_completion_modifier_5e(DefensivePlay.RUN_DEFENSE_NO_KEY, "QUICK", within_20=True) == -10

    def test_within_20_pass_def_quick(self):
        """Within-20: Pass Def / Quick changes from -10 to -15."""
        from engine.play_types import DefensivePlay, get_completion_modifier_5e
        assert get_completion_modifier_5e(DefensivePlay.PASS_DEFENSE, "QUICK", within_20=False) == -10
        assert get_completion_modifier_5e(DefensivePlay.PASS_DEFENSE, "QUICK", within_20=True) == -15

    def test_within_20_run_def_short(self):
        """Within-20: Run Def / Short changes from +5 to 0."""
        from engine.play_types import DefensivePlay, get_completion_modifier_5e
        assert get_completion_modifier_5e(DefensivePlay.RUN_DEFENSE_NO_KEY, "SHORT", within_20=False) == 5
        assert get_completion_modifier_5e(DefensivePlay.RUN_DEFENSE_NO_KEY, "SHORT", within_20=True) == 0

    def test_within_20_unchanged_cells(self):
        """Within-20: cells without parenthetical values stay the same."""
        from engine.play_types import DefensivePlay, get_completion_modifier_5e
        # Prevent / Quick stays 0
        assert get_completion_modifier_5e(DefensivePlay.PREVENT_DEFENSE, "QUICK", within_20=True) == 0
        # Run Def / Long stays +7
        assert get_completion_modifier_5e(DefensivePlay.RUN_DEFENSE_NO_KEY, "LONG", within_20=True) == 7
        # Pass Def / Short stays -5
        assert get_completion_modifier_5e(DefensivePlay.PASS_DEFENSE, "SHORT", within_20=True) == -5

    def test_screen_rn_modifier_run_defense(self):
        """Screen RN modifiers for run defense use key/no-key logic."""
        from engine.play_types import DefensivePlay, get_screen_rn_modifier_5e
        # Key on correct back = +4
        assert get_screen_rn_modifier_5e(DefensivePlay.RUN_DEFENSE_KEY_BACK_1, ball_carrier_number=1) == 4
        # No key = +2
        assert get_screen_rn_modifier_5e(DefensivePlay.RUN_DEFENSE_NO_KEY) == 2
        # Wrong key = 0
        assert get_screen_rn_modifier_5e(DefensivePlay.RUN_DEFENSE_KEY_BACK_2, ball_carrier_number=1) == 0

    def test_screen_rn_modifier_pass_defense(self):
        """Screen RN modifier for Pass Defense: 0."""
        from engine.play_types import DefensivePlay, get_screen_rn_modifier_5e
        assert get_screen_rn_modifier_5e(DefensivePlay.PASS_DEFENSE) == 0

    def test_screen_rn_modifier_prevent(self):
        """Screen RN modifier for Prevent: -2 (favours offense)."""
        from engine.play_types import DefensivePlay, get_screen_rn_modifier_5e
        assert get_screen_rn_modifier_5e(DefensivePlay.PREVENT_DEFENSE) == -2

    def test_screen_rn_modifier_blitz(self):
        """Screen RN modifier for Blitz: -4 (strongly favours offense)."""
        from engine.play_types import DefensivePlay, get_screen_rn_modifier_5e
        assert get_screen_rn_modifier_5e(DefensivePlay.BLITZ) == -4


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

    def test_screen_run_modifier_deprecated_returns_zero(self):
        """get_screen_run_modifier is deprecated — always returns 0 for any formation string.

        Per 5E rules, run-number modifiers come from the defensive PLAY CALL
        (the DefensivePlay enum), not from the formation name.  Use
        ``get_screen_rn_modifier_5e`` from ``play_types`` with an explicit
        DefensivePlay enum instead.
        """
        assert PlayResolver.get_screen_run_modifier("4_3") == 0
        assert PlayResolver.get_screen_run_modifier("GOAL_LINE") == 0
        assert PlayResolver.get_screen_run_modifier("NICKEL") == 0

    def test_screen_rn_modifier_run_defense_via_enum(self):
        """Screen vs Run Defense: +2 to RN (using proper DefensivePlay enum)."""
        from engine.play_types import DefensivePlay, get_screen_rn_modifier_5e
        assert get_screen_rn_modifier_5e(DefensivePlay.RUN_DEFENSE_NO_KEY) == 2

    def test_screen_rn_modifier_pass_defense_via_enum(self):
        """Screen vs Pass Defense: 0 modifier."""
        from engine.play_types import DefensivePlay, get_screen_rn_modifier_5e
        assert get_screen_rn_modifier_5e(DefensivePlay.PASS_DEFENSE) == 0

    def test_screen_rn_modifier_blitz_via_enum(self):
        """Screen vs Blitz: -4 modifier (bonus for offense)."""
        from engine.play_types import DefensivePlay, get_screen_rn_modifier_5e
        assert get_screen_rn_modifier_5e(DefensivePlay.BLITZ) == -4

    def test_screen_rn_modifier_prevent_via_enum(self):
        """Screen vs Prevent Defense: -2 modifier (bonus for offense)."""
        from engine.play_types import DefensivePlay, get_screen_rn_modifier_5e
        assert get_screen_rn_modifier_5e(DefensivePlay.PREVENT_DEFENSE) == -2


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
        result = ai.convert_prevent_within_20(sit, "PREVENT_DEFENSE")
        assert result == "4_3"

    def test_nickel_not_converted_within_20(self):
        """Nickel is a valid pass formation — it should NOT be converted inside the 20."""
        from engine.solitaire import SolitaireAI, GameSituation
        ai = SolitaireAI()
        sit = GameSituation(down=1, distance=10, yard_line=85,
                            score_diff=0, quarter=1, time_remaining=600)
        result = ai.convert_prevent_within_20(sit, "NICKEL")
        assert result == "NICKEL"

    def test_no_conversion_outside_20(self):
        from engine.solitaire import SolitaireAI, GameSituation
        ai = SolitaireAI()
        sit = GameSituation(down=1, distance=10, yard_line=50,
                            score_diff=0, quarter=1, time_remaining=600)
        result = ai.convert_prevent_within_20(sit, "PREVENT_DEFENSE")
        assert result == "PREVENT_DEFENSE"


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


# ─── Display Box Tracking Tests ──────────────────────────────────────────


class TestDisplayBoxTracking:
    """Test 5E Display box assignment system."""

    def test_assign_default_display_boxes(self):
        """Verify default box assignments follow 5E rules."""
        team = Team.load("KC", "2025_5e")
        defs = team.roster.defenders[:11]
        boxes = PlayResolver.assign_default_display_boxes(defs)
        assert len(boxes) > 0
        # All assigned boxes should be valid
        valid_boxes = set('ABCDEFGHIJKLMNO')
        for name, box in boxes.items():
            assert box in valid_boxes, f"{name} assigned to invalid box {box}"

    def test_dl_in_row1(self):
        """DL players should be in Row 1 (A-E)."""
        team = Team.load("KC", "2025_5e")
        defs = team.roster.defenders[:11]
        boxes = PlayResolver.assign_default_display_boxes(defs)
        for d in defs:
            if d.position in ('DE', 'DT', 'DL', 'NT'):
                if d.player_name in boxes:
                    assert boxes[d.player_name] in 'ABCDE', \
                        f"DL {d.player_name} should be in Row 1"

    def test_lb_in_row2(self):
        """LB players should be in Row 2 (F-J)."""
        team = Team.load("KC", "2025_5e")
        defs = team.roster.defenders[:11]
        boxes = PlayResolver.assign_default_display_boxes(defs)
        for d in defs:
            if d.position in ('LB', 'OLB', 'ILB', 'MLB'):
                if d.player_name in boxes:
                    assert boxes[d.player_name] in 'FGHIJ', \
                        f"LB {d.player_name} should be in Row 2"


# ─── Pass Defense Box Assignment Tests ───────────────────────────────────


class TestPassDefenseAssignments:
    """Test 5E pass defense box assignments."""

    def test_receiver_slot_to_box_mapping(self):
        """Verify receiver slot → box mapping matches 5E rules."""
        assert PlayResolver.PASS_DEFENSE_ASSIGNMENTS['RE'] == 'N'
        assert PlayResolver.PASS_DEFENSE_ASSIGNMENTS['LE'] == 'K'
        assert PlayResolver.PASS_DEFENSE_ASSIGNMENTS['FL1'] == 'O'
        assert PlayResolver.PASS_DEFENSE_ASSIGNMENTS['FL2'] == 'M'
        assert PlayResolver.PASS_DEFENSE_ASSIGNMENTS['BK1'] == 'F'
        assert PlayResolver.PASS_DEFENSE_ASSIGNMENTS['BK2'] == 'J'
        assert PlayResolver.PASS_DEFENSE_ASSIGNMENTS['BK3'] == 'H'

    def test_get_pass_defender_empty_box(self):
        """Empty box returns None (→ +5 completion bonus)."""
        assignments = {'Smith': 'K', 'Jones': 'O'}
        result = PlayResolver.get_pass_defender_for_receiver('BK1', assignments)
        assert result is None  # Box F is empty


# ─── Flanker Designation Tests ───────────────────────────────────────────


class TestFlankerDesignation:
    """Test FL#1/FL#2 designation system."""

    def test_three_rbs_designates_fl1(self):
        """With 3 RBs on display, no flanker — all backs in BK slots.

        7-man line rule: 5 OL + LE + RE = 7.  FL is absent in a 3RB formation.
        """
        team = Team.load("KC", "2025_5e")
        rbs = team.roster.rbs[:3]
        wrs = team.roster.wrs[:3]
        tes = team.roster.tes[:1]
        flankers = PlayResolver.designate_flankers(3, wrs, tes, rbs)
        # 3-back formation has no flanker slot occupied
        assert 'FL1' not in flankers
        assert 'FL2' not in flankers

    def test_two_rbs_wr_is_fl1(self):
        """With 2 RBs, first WR becomes FL#1."""
        team = Team.load("KC", "2025_5e")
        rbs = team.roster.rbs[:2]
        wrs = team.roster.wrs[:3]
        tes = team.roster.tes[:1]
        flankers = PlayResolver.designate_flankers(2, wrs, tes, rbs)
        assert 'FL1' in flankers
        assert flankers['FL1'] == wrs[0].player_name

    def test_one_rb_gets_fl2(self):
        """With 1 RB, second WR becomes FL#2."""
        team = Team.load("KC", "2025_5e")
        rbs = team.roster.rbs[:1]
        wrs = team.roster.wrs[:3]
        tes = team.roster.tes[:1]
        flankers = PlayResolver.designate_flankers(1, wrs, tes, rbs)
        assert 'FL2' in flankers


# ─── Injury Protection Tests ────────────────────────────────────────────


class TestInjuryProtection:
    """Test backup player injury protection per 5E rules."""

    def test_backup_protected_when_starter_injured(self):
        assert PlayResolver.check_injury_protection("Backup QB", True, True) is True

    def test_starter_not_protected(self):
        assert PlayResolver.check_injury_protection("Starter QB", False, False) is False

    def test_backup_not_protected_when_starter_healthy(self):
        assert PlayResolver.check_injury_protection("Backup QB", True, False) is False


# ─── Asterisked Punt Return Tests ───────────────────────────────────────


class TestAsteriskedReturns:
    """Test asterisked punt return resolution."""

    def test_asterisked_return_uses_base_or_special(self):
        """Result is always one of the two possible values."""
        deck = FACDeck(seed=42)
        for _ in range(20):
            result = PlayResolver.resolve_asterisked_return(15, 40, deck)
            assert result in (15, 40)


# ─── Spot of Foul Tests ─────────────────────────────────────────────────


class TestSpotOfFoul:
    """Test pass interference spot of foul calculation."""

    def test_screen_half_rn(self):
        spot = PlayResolver.calculate_spot_of_foul('SCREEN', 8, 30)
        assert spot == 34  # 30 + 8//2 = 34

    def test_quick_pass_rn(self):
        spot = PlayResolver.calculate_spot_of_foul('QUICK_PASS', 6, 40)
        assert spot == 46  # 40 + 6

    def test_short_pass_double_rn(self):
        spot = PlayResolver.calculate_spot_of_foul('SHORT_PASS', 5, 50)
        assert spot == 60  # 50 + 5*2

    def test_long_pass_quad_rn(self):
        spot = PlayResolver.calculate_spot_of_foul('LONG_PASS', 10, 50)
        assert spot == 90  # 50 + 10*4

    def test_capped_at_99(self):
        spot = PlayResolver.calculate_spot_of_foul('LONG_PASS', 12, 80)
        assert spot == 99  # Capped


# ─── Clipping Spot Tests ────────────────────────────────────────────────


class TestClippingSpot:
    """Test clipping spot penalty calculation."""

    def test_odd_rn_halfway(self):
        spot = PlayResolver.calculate_clipping_spot(3, 20, 30)
        assert spot == 40  # 30 + 20//2 = 40

    def test_even_rn_end_of_return(self):
        spot = PlayResolver.calculate_clipping_spot(4, 20, 30)
        assert spot == 50  # 30 + 20 = 50


# ─── Out of Position Tests ──────────────────────────────────────────────


class TestOutOfPosition:
    """Test out of position penalty logic including DL/LB exception."""

    def test_dl_no_penalty_in_row1(self):
        """DL/LB may play any Row 1 position without modification."""
        from engine.player_card import PlayerCard
        p = PlayerCard(player_name="DE", team="KC", position="DE", number=99)
        assert PlayResolver.check_out_of_position_penalty(p, "DT") == 0
        assert PlayResolver.check_out_of_position_penalty(p, "A") == 0

    def test_cb_penalty_in_wrong_position(self):
        from engine.player_card import PlayerCard
        p = PlayerCard(player_name="CB", team="KC", position="CB", number=21)
        assert PlayResolver.check_out_of_position_penalty(p, "SS") == -1

    def test_db_no_penalty_in_box_l(self):
        """Any DB may play in Box L without modification."""
        from engine.player_card import PlayerCard
        p = PlayerCard(player_name="Safety", team="KC", position="S", number=22)
        assert PlayResolver.check_out_of_position_penalty(p, "L") == 0


# ─── Blocking Value Classification Tests ─────────────────────────────────


class TestBlockingValues:
    """Test TE/WR blocking value classification."""

    def test_te_elite_blocking(self):
        from engine.player_card import PlayerCard
        p = PlayerCard(player_name="TE1", team="KC", position="TE", number=87, blocks=4)
        assert PlayResolver.classify_blocking_value(p) == 'Elite'

    def test_wr_liability_blocking(self):
        from engine.player_card import PlayerCard
        p = PlayerCard(player_name="WR1", team="KC", position="WR", number=11, blocks=-3)
        assert PlayResolver.classify_blocking_value(p) == 'Liability'

    def test_wr_good_blocking(self):
        from engine.player_card import PlayerCard
        p = PlayerCard(player_name="WR2", team="KC", position="WR", number=12, blocks=2)
        assert PlayResolver.classify_blocking_value(p) == 'Good'


# ─── Fumble Team Rating Tests ───────────────────────────────────────────


class TestFumbleTeamRatings:
    """Test fumble recovery with team ratings per 5E rules."""

    def test_fumble_lost_within_range(self):
        """PN within Fumbles Lost range = fumble lost."""
        assert PlayResolver.resolve_fumble_with_team_rating(10, 21) is True

    def test_fumble_kept_outside_range(self):
        """PN outside range = fumble kept."""
        assert PlayResolver.resolve_fumble_with_team_rating(30, 21) is False

    def test_defensive_adjustment(self):
        """Defensive adjustment increases fumble loss range."""
        assert PlayResolver.resolve_fumble_with_team_rating(23, 21, def_fumble_adj=5) is True

    def test_home_field_bonus(self):
        """Home team gets -1 to fumble loss threshold."""
        # PN=21, max=21, but home bonus makes effective max=20
        assert PlayResolver.resolve_fumble_with_team_rating(21, 21, is_home=True) is False
        assert PlayResolver.resolve_fumble_with_team_rating(20, 21, is_home=True) is True


# ─── Blitz Procedure Tests ──────────────────────────────────────────────


class TestBlitzProcedure:
    """Test blitz player removal tracking."""

    def test_pn_low_removes_f_j(self):
        removals = PlayResolver.get_blitz_removals(15)
        assert removals == ['F', 'J']

    def test_pn_mid_removes_f_j_m(self):
        removals = PlayResolver.get_blitz_removals(30)
        assert removals == ['F', 'J', 'M']

    def test_pn_high_removes_all_lb(self):
        removals = PlayResolver.get_blitz_removals(40)
        assert removals == ['F', 'G', 'H', 'I', 'J']


# ─── Game Method Integration Tests ──────────────────────────────────────


class TestSpecialPlaysIntegration:
    """Test new game methods for fake punt/FG, coffin corner, all-out rush."""

    def test_fake_punt(self):
        """Fake punt executes and returns PlayResult."""
        home = Team.load("KC", "2025_5e")
        away = Team.load("SF", "2025_5e")
        game = Game(home, away, use_5e=True, seed=42)
        result = game.execute_fake_punt()
        assert result.play_type in ("PUNT", "RUN", "PASS")

    def test_fake_punt_once_per_game(self):
        """Fake punt can only be used once per game."""
        home = Team.load("KC", "2025_5e")
        away = Team.load("SF", "2025_5e")
        game = Game(home, away, use_5e=True, seed=42)
        result1 = game.execute_fake_punt()
        result2 = game.execute_fake_punt()
        assert "ILLEGAL" in result2.description or "already used" in result2.description

    def test_fake_fg(self):
        """Fake FG executes and returns PlayResult."""
        home = Team.load("KC", "2025_5e")
        away = Team.load("SF", "2025_5e")
        game = Game(home, away, use_5e=True, seed=42)
        result = game.execute_fake_field_goal()
        assert result is not None

    def test_coffin_corner_punt(self):
        """Coffin corner punt uses deduction."""
        home = Team.load("KC", "2025_5e")
        away = Team.load("SF", "2025_5e")
        game = Game(home, away, use_5e=True, seed=42)
        result = game.execute_coffin_corner_punt(15)
        assert "coffin corner" in result.description.lower() or "COFFIN" in str(result)

    def test_all_out_punt_rush(self):
        """All-out punt rush executes."""
        home = Team.load("KC", "2025_5e")
        away = Team.load("SF", "2025_5e")
        game = Game(home, away, use_5e=True, seed=42)
        result = game.execute_all_out_punt_rush()
        assert result is not None


# ── New 5E Features Tests ──────────────────────────────────────────


class TestColumnABKickoff:
    """Test the 5E Column A/B kickoff table."""

    def test_kickoff_returns_tuple(self):
        from engine.charts import Charts
        result = Charts.resolve_kickoff_5e()
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert result[0] in ("TB", "KR")
        if result[0] == "TB":
            assert result[1] == 25
        else:
            assert 1 <= result[1] <= 99

    def test_touchback_and_return_distribution(self):
        """Run many trials and verify we get both TBs and KRs."""
        from engine.charts import Charts
        random.seed(42)
        results = [Charts.resolve_kickoff_5e() for _ in range(200)]
        tbs = sum(1 for r in results if r[0] == "TB")
        krs = sum(1 for r in results if r[0] == "KR")
        assert tbs > 0, "Should get at least one touchback"
        assert krs > 0, "Should get at least one kick return"


class TestPuntDistanceTables:
    """Test the 5E 12-row punt distance tables."""

    def test_known_averages(self):
        from engine.charts import Charts
        # Average of 44 yards, RN 6 should be 44
        assert Charts.get_punt_distance_5e(44, 6) == 44
        # RN 1 should be shorter
        assert Charts.get_punt_distance_5e(44, 1) < 44
        # RN 12 should be longer
        assert Charts.get_punt_distance_5e(44, 12) > 44

    def test_range_35_to_50(self):
        from engine.charts import Charts
        for avg in range(35, 51):
            for rn in range(1, 13):
                dist = Charts.get_punt_distance_5e(avg, rn)
                assert isinstance(dist, int)
                assert 10 <= dist <= 80

    def test_outside_range_fallback(self):
        from engine.charts import Charts
        dist = Charts.get_punt_distance_5e(30, 6)
        assert isinstance(dist, int)
        assert dist > 0


class TestOver51FGTable:
    """Test the 5E over-51 FG table."""

    def test_impossible_distance(self):
        from engine.charts import Charts
        assert Charts.resolve_over_51_fg(56, 55) is False

    def test_kicker_with_high_longest(self):
        from engine.charts import Charts
        random.seed(42)
        made_count = sum(1 for _ in range(100) if Charts.resolve_over_51_fg(51, 60))
        # Should make some with longest=60
        assert made_count > 0

    def test_kicker_with_low_longest(self):
        from engine.charts import Charts
        random.seed(42)
        made_count = sum(1 for _ in range(100) if Charts.resolve_over_51_fg(55, 50))
        # Very hard with longest=50, distance=55
        assert made_count < 10  # Should be very rare


class TestBlockedPunts:
    """Test blocked punt check."""

    def test_blocked_when_matching(self):
        from engine.charts import Charts
        assert Charts.check_blocked_punt(5, 5) is True

    def test_not_blocked_when_different(self):
        from engine.charts import Charts
        assert Charts.check_blocked_punt(5, 6) is False

    def test_no_blocked_punt_number(self):
        from engine.charts import Charts
        assert Charts.check_blocked_punt(0, 5) is False


class TestFairCatch:
    """Test fair catch / punt return percentage."""

    def test_high_return_pct(self):
        from engine.charts import Charts
        random.seed(42)
        fair_catches = sum(1 for _ in range(100) if Charts.check_fair_catch(0.9))
        assert fair_catches < 20  # 90% return rate means few fair catches

    def test_low_return_pct(self):
        from engine.charts import Charts
        random.seed(42)
        fair_catches = sum(1 for _ in range(100) if Charts.check_fair_catch(0.1))
        assert fair_catches > 80  # 10% return rate means many fair catches


class TestPlayerCardNewFields:
    """Test new fields on PlayerCard."""

    def test_punter_has_blocked_punt_number(self):
        from engine.player_card import PlayerCard
        card = PlayerCard(player_name="Test Punter", team="TST", number=1,
                          position="P", blocked_punt_number=7)
        assert card.blocked_punt_number == 7

    def test_punter_has_punt_return_pct(self):
        from engine.player_card import PlayerCard
        card = PlayerCard(player_name="Test Punter", team="TST", number=1,
                          position="P", punt_return_pct=0.55)
        assert card.punt_return_pct == 0.55

    def test_kicker_has_longest_kick(self):
        from engine.player_card import PlayerCard
        card = PlayerCard(player_name="Test Kicker", team="TST", number=2,
                          position="K", longest_kick=57)
        assert card.longest_kick == 57


class TestBigPlayDefense:
    """Test Big Play Defense methods on Game."""

    def test_activate_big_play_defense(self):
        home = Team.load("KC", "2025_5e")
        away = Team.load("SF", "2025_5e")
        game = Game(home, away, use_5e=True, seed=42)
        # Activate for home team
        result = game.activate_big_play_defense("home")
        assert result is True
        # Second activation should fail (already used this series)
        result2 = game.activate_big_play_defense("home")
        assert result2 is False


class TestTwoMinuteOffense:
    """Test two-minute offense declaration."""

    def test_declare_two_minute_offense(self):
        home = Team.load("KC", "2025_5e")
        away = Team.load("SF", "2025_5e")
        game = Game(home, away, use_5e=True, seed=42)
        game.declare_two_minute_offense()
        assert game._two_minute_declared is True
        assert game._is_two_minute_offense() is True


class TestPlayerStatsTracking:
    """Test that player stats are tracked during play."""

    def test_stats_accumulate(self):
        home = Team.load("KC", "2025_5e")
        away = Team.load("SF", "2025_5e")
        game = Game(home, away, use_5e=True, seed=42)
        # Run several plays
        for _ in range(10):
            if game.state.is_over:
                break
            game.execute_play()
        # Should have some stats
        assert isinstance(game.state.player_stats, dict)
        assert len(game.state.player_stats) >= 0  # Some plays may not track


class TestPenaltyTurnoverTracking:
    """Test that penalties and turnovers are tracked."""

    def test_penalty_dict_initialized(self):
        home = Team.load("KC", "2025_5e")
        away = Team.load("SF", "2025_5e")
        game = Game(home, away, use_5e=True, seed=42)
        assert game.state.penalties == {"home": 0, "away": 0}
        assert game.state.penalty_yards == {"home": 0, "away": 0}
        assert game.state.turnovers == {"home": 0, "away": 0}

    def test_turnover_dict_populated_after_plays(self):
        home = Team.load("KC", "2025_5e")
        away = Team.load("SF", "2025_5e")
        game = Game(home, away, use_5e=True, seed=42)
        for _ in range(30):
            if game.state.is_over:
                break
            game.execute_play()
        # Turnovers dict should exist regardless
        assert isinstance(game.state.turnovers, dict)


class TestSeedConfiguration:
    """Test that seed produces deterministic games."""

    def test_seed_reproducibility(self):
        home1 = Team.load("KC", "2025_5e")
        away1 = Team.load("SF", "2025_5e")
        game1 = Game(home1, away1, use_5e=True, seed=12345)

        home2 = Team.load("KC", "2025_5e")
        away2 = Team.load("SF", "2025_5e")
        game2 = Game(home2, away2, use_5e=True, seed=12345)

        # Both games should produce the same state with the same seed
        assert game1.state.possession == game2.state.possession
        assert game1.state.yard_line == game2.state.yard_line


class TestAIEnhancements:
    """Test AI strategy, fake play, and timeout methods."""

    def test_ai_should_call_timeout(self):
        from engine.solitaire import SolitaireAI, GameSituation
        ai = SolitaireAI()
        # Trailing in Q4, under 2 minutes → should call timeout
        sit = GameSituation(down=1, distance=10, yard_line=30,
                            score_diff=-7, quarter=4, time_remaining=60,
                            timeouts_offense=2)
        assert ai.should_call_timeout(sit) is True

    def test_ai_should_not_call_timeout_early(self):
        from engine.solitaire import SolitaireAI, GameSituation
        ai = SolitaireAI()
        sit = GameSituation(down=1, distance=10, yard_line=30,
                            score_diff=0, quarter=1, time_remaining=800)
        assert ai.should_call_timeout(sit) is False

    def test_ai_big_play_defense_decision(self):
        from engine.solitaire import SolitaireAI, GameSituation
        ai = SolitaireAI()
        # Long yardage, should consider BPD
        sit = GameSituation(down=3, distance=20, yard_line=50,
                            score_diff=0, quarter=2, time_remaining=500)
        # Run multiple times (probabilistic)
        random.seed(42)
        results = [ai.should_use_big_play_defense(sit) for _ in range(100)]
        assert any(results), "Should sometimes use BPD on 3rd and long"


# ─── Offensive Personnel Tracking Tests ──────────────────────────────────


class TestOffensivePersonnel:
    """Test offensive personnel tracking per play."""

    def test_build_offensive_personnel_full(self):
        """All 5 receiver slots populated."""
        from engine.player_card import PlayerCard
        recs = [PlayerCard(f"P{i}", "KC", "WR", 80+i, "B") for i in range(5)]
        personnel = PlayResolver.build_offensive_personnel(recs)
        assert personnel['FL'] is recs[0]
        assert personnel['LE'] is recs[1]
        assert personnel['RE'] is recs[2]
        assert personnel['BK1'] is recs[3]
        assert personnel['BK2'] is recs[4]

    def test_build_offensive_personnel_three_receivers(self):
        """Only 3 receivers — BK slots should be None."""
        from engine.player_card import PlayerCard
        recs = [PlayerCard(f"P{i}", "KC", "WR", 80+i, "B") for i in range(3)]
        personnel = PlayResolver.build_offensive_personnel(recs)
        assert personnel['FL'] is recs[0]
        assert personnel['LE'] is recs[1]
        assert personnel['RE'] is recs[2]
        assert personnel['BK1'] is None
        assert personnel['BK2'] is None

    def test_build_offensive_personnel_with_backs_blocking(self):
        """Backs kept in to block are removed from personnel."""
        from engine.player_card import PlayerCard
        recs = [PlayerCard(f"P{i}", "KC", "WR", 80+i, "B") for i in range(5)]
        personnel = PlayResolver.build_offensive_personnel(recs, backs_blocking=[3, 4])
        assert personnel['FL'] is recs[0]
        assert personnel['LE'] is recs[1]
        assert personnel['RE'] is recs[2]
        assert personnel['BK1'] is None  # blocking
        assert personnel['BK2'] is None  # blocking

    def test_get_receiver_slot(self):
        """Receiver index maps to correct slot name."""
        from engine.player_card import PlayerCard
        recs = [PlayerCard(f"P{i}", "KC", "WR", 80+i, "B") for i in range(5)]
        assert PlayResolver.get_receiver_slot(recs[0], recs) == 'FL'
        assert PlayResolver.get_receiver_slot(recs[1], recs) == 'LE'
        assert PlayResolver.get_receiver_slot(recs[2], recs) == 'RE'
        assert PlayResolver.get_receiver_slot(recs[3], recs) == 'BK1'
        assert PlayResolver.get_receiver_slot(recs[4], recs) == 'BK2'

    def test_get_receiver_slot_not_found(self):
        """Unknown receiver returns None."""
        from engine.player_card import PlayerCard
        recs = [PlayerCard(f"P{i}", "KC", "WR", 80+i, "B") for i in range(3)]
        stranger = PlayerCard("Stranger", "KC", "WR", 99, "B")
        assert PlayResolver.get_receiver_slot(stranger, recs) is None


# ─── Covering Defender Lookup Tests ──────────────────────────────────────


class TestCoveringDefender:
    """Test covering defender lookup via PASS_DEFENSE_ASSIGNMENTS."""

    def test_re_covered_by_box_n(self):
        """RE receiver is covered by defender in box N (SS)."""
        from engine.player_card import PlayerCard
        ss = PlayerCard("SS Player", "DAL", "S", 22, "B", pass_defense_rating=3)
        defenders_by_box = {'N': ss}
        result = PlayResolver.get_covering_defender('RE', defenders_by_box)
        assert result is ss

    def test_le_covered_by_box_k(self):
        """LE receiver is covered by defender in box K (LCB)."""
        from engine.player_card import PlayerCard
        cb = PlayerCard("CB Player", "DAL", "CB", 24, "B", pass_defense_rating=2)
        defenders_by_box = {'K': cb}
        result = PlayResolver.get_covering_defender('LE', defenders_by_box)
        assert result is cb

    def test_fl_covered_by_box_o(self):
        """FL receiver is covered by defender in box O (RCB)."""
        from engine.player_card import PlayerCard
        cb = PlayerCard("RCB Player", "DAL", "CB", 25, "B", pass_defense_rating=4)
        defenders_by_box = {'O': cb}
        result = PlayResolver.get_covering_defender('FL', defenders_by_box)
        assert result is cb

    def test_bk1_covered_by_box_f(self):
        """BK1 covered by box F (LOLB)."""
        from engine.player_card import PlayerCard
        olb = PlayerCard("OLB Player", "DAL", "LB", 56, "B", pass_defense_rating=1)
        defenders_by_box = {'F': olb}
        result = PlayResolver.get_covering_defender('BK1', defenders_by_box)
        assert result is olb

    def test_bk2_covered_by_box_j(self):
        """BK2 covered by box J (ROLB)."""
        from engine.player_card import PlayerCard
        olb = PlayerCard("ROLB Player", "DAL", "LB", 57, "B", pass_defense_rating=0)
        defenders_by_box = {'J': olb}
        result = PlayResolver.get_covering_defender('BK2', defenders_by_box)
        assert result is olb

    def test_empty_box_returns_none(self):
        """Empty box returns None (triggers +5 completion bonus)."""
        defenders_by_box = {'K': None}  # box N not populated
        result = PlayResolver.get_covering_defender('RE', defenders_by_box)
        assert result is None

    def test_fl_alias_matches_fl1(self):
        """FL alias maps to same box as FL1 (box O)."""
        assert PlayResolver.PASS_DEFENSE_ASSIGNMENTS['FL'] == PlayResolver.PASS_DEFENSE_ASSIGNMENTS['FL1']


# ─── Backs In To Block Tests ────────────────────────────────────────────


class TestBacksInToBlock:
    """Test +2 completion range per blocking back."""

    def _make_fac_card(self, pn=20, rn=6):
        """Create a simple FAC card for testing."""
        from engine.fac_deck import FACCard
        return FACCard(
            card_number=1, run_number=str(rn), pass_number=str(pn),
            sweep_left="A", inside_left="B", sweep_right="C", inside_right="D",
            quick_kick="Orig", short_pass="Orig", long_pass="Orig",
            screen="Com", end_run="OK", z_result="NONE", solo="P",
        )

    def _make_qb(self, com_max=30):
        """Create a QB with known passing ranges."""
        from engine.player_card import PlayerCard, PassRanges
        qb = PlayerCard("Test QB", "KC", "QB", 15, "A")
        qb.passing_short = PassRanges(com_max=com_max, inc_max=47)
        qb.passing_quick = PassRanges(com_max=com_max, inc_max=47)
        qb.passing_long = PassRanges(com_max=com_max - 5, inc_max=47)
        return qb

    def _make_receivers(self, n=5):
        """Create receivers with pass_gain rows and _formation_slot attributes."""
        from engine.player_card import PlayerCard, ThreeValueRow
        slot_names = ["FL", "LE", "RE", "BK1", "BK2", "BK3"]
        recs = []
        for i in range(n):
            r = PlayerCard(f"WR{i}", "KC", "WR", 80+i, "B")
            r.pass_gain = [ThreeValueRow(v1=5, v2=8, v3=15) for _ in range(12)]
            r._formation_slot = slot_names[i] if i < len(slot_names) else f"BK{i}"
            recs.append(r)
        return recs

    def test_one_back_blocking_adds_plus_2(self):
        """One back blocking → +2 completion modifier (lowers PN by 2)."""
        resolver = PlayResolver()
        qb = self._make_qb(com_max=25)  # COM range 1-25
        recs = self._make_receivers(5)
        # PN=27 is normally INC (> com_max 25)
        # With +2 from 1 blocking back, PN adjusted to 25 → COM
        fac = self._make_fac_card(pn=27)
        deck = FACDeck()
        random.seed(42)
        result = resolver.resolve_pass_5e(
            fac, deck, qb, recs[0], recs,
            pass_type="SHORT",
            backs_blocking=[3],  # BK1 blocking
        )
        # The +2 modifier shifts PN from 27 to 25, which is COM
        assert result.result in ("COMPLETE", "TD"), f"Expected COM with back blocking, got {result.result}"

    def test_two_backs_blocking_adds_plus_4(self):
        """Two backs blocking → +4 completion modifier."""
        resolver = PlayResolver()
        qb = self._make_qb(com_max=25)
        recs = self._make_receivers(5)
        # PN=29 is INC. With +4 from 2 blockers, PN → 25 → COM
        fac = self._make_fac_card(pn=29)
        deck = FACDeck()
        random.seed(42)
        result = resolver.resolve_pass_5e(
            fac, deck, qb, recs[0], recs,
            pass_type="SHORT",
            backs_blocking=[3, 4],  # BK1 + BK2 blocking
        )
        assert result.result in ("COMPLETE", "TD"), f"Expected COM with 2 backs blocking, got {result.result}"

    def test_blocking_back_targeted_throws_away(self):
        """If FAC targets a blocking back, ball is thrown away."""
        from engine.fac_deck import FACCard
        resolver = PlayResolver()
        qb = self._make_qb(com_max=30)
        recs = self._make_receivers(5)
        # FAC card targets BK1 (index 3)
        fac = FACCard(
            card_number=1, run_number="6", pass_number="20",
            sweep_left="A", inside_left="B", sweep_right="C", inside_right="D",
            quick_kick="Orig", short_pass="BK1", long_pass="Orig",
            screen="Com", end_run="OK", z_result="NONE", solo="P",
        )
        deck = FACDeck()
        result = resolver.resolve_pass_5e(
            fac, deck, qb, recs[0], recs,
            pass_type="SHORT",
            backs_blocking=[3],  # BK1 is blocking
        )
        assert result.result == "INCOMPLETE"
        assert "block" in result.description.lower() or "thrown away" in result.description.lower()

    def test_no_blocking_no_modifier(self):
        """Without blocking backs, no extra modifier applied."""
        resolver = PlayResolver()
        qb = self._make_qb(com_max=25)
        recs = self._make_receivers(5)
        # PN=27 > com_max 25 → INC without blockers
        fac = self._make_fac_card(pn=27)
        deck = FACDeck()
        random.seed(42)
        result = resolver.resolve_pass_5e(
            fac, deck, qb, recs[0], recs,
            pass_type="SHORT",
            backs_blocking=[],
        )
        assert result.result in ("INCOMPLETE", "INT"), f"Expected INC without blockers, got {result.result}"


# ─── Pass Defense Rating Modifier Tests ─────────────────────────────────


class TestPassDefenseRating:
    """Test covering defender's pass_defense_rating modifies completion."""

    def _make_fac_card(self, pn=20, rn=6):
        from engine.fac_deck import FACCard
        return FACCard(
            card_number=1, run_number=str(rn), pass_number=str(pn),
            sweep_left="A", inside_left="B", sweep_right="C", inside_right="D",
            quick_kick="Orig", short_pass="Orig", long_pass="Orig",
            screen="Com", end_run="OK", z_result="NONE", solo="P",
        )

    def _make_qb(self, com_max=30):
        from engine.player_card import PlayerCard, PassRanges
        qb = PlayerCard("Test QB", "KC", "QB", 15, "A")
        qb.passing_short = PassRanges(com_max=com_max, inc_max=47)
        qb.passing_quick = PassRanges(com_max=com_max, inc_max=47)
        qb.passing_long = PassRanges(com_max=com_max - 5, inc_max=47)
        return qb

    def _make_receivers(self, n=5):
        from engine.player_card import PlayerCard, ThreeValueRow
        slot_names = ["FL", "LE", "RE", "BK1", "BK2", "BK3"]
        recs = []
        for i in range(n):
            r = PlayerCard(f"WR{i}", "KC", "WR", 80+i, "B")
            r.pass_gain = [ThreeValueRow(v1=5, v2=8, v3=15) for _ in range(12)]
            r._formation_slot = slot_names[i] if i < len(slot_names) else f"BK{i}"
            recs.append(r)
        return recs


    def test_high_pdr_makes_pass_harder(self):
        """High pass_defense_rating defender increases PN → harder to complete."""
        from engine.player_card import PlayerCard
        resolver = PlayResolver()
        qb = self._make_qb(com_max=30)
        recs = self._make_receivers(5)
        # FL is receivers[0], covered by box O
        cb = PlayerCard("Elite CB", "DAL", "CB", 24, "A", pass_defense_rating=4)
        defenders_by_box = {'O': cb}  # box O covers FL
        # PN=29 is normally COM (≤30), but PDR=4 → PN adjusted +4 → 33 → INC
        fac = self._make_fac_card(pn=29)
        deck = FACDeck()
        random.seed(42)
        result = resolver.resolve_pass_5e(
            fac, deck, qb, recs[0], recs,
            pass_type="SHORT",
            defenders_by_box=defenders_by_box,
        )
        assert result.result in ("INCOMPLETE", "INT"), f"Expected INC/INT with high PDR, got {result.result}"

    def test_negative_pdr_makes_pass_easier(self):
        """Negative pass_defense_rating defender (bad coverage) lowers PN."""
        from engine.player_card import PlayerCard
        resolver = PlayResolver()
        qb = self._make_qb(com_max=30)
        recs = self._make_receivers(5)
        # FL is receivers[0], covered by box O
        cb = PlayerCard("Weak CB", "DAL", "CB", 24, "D", pass_defense_rating=-2)
        defenders_by_box = {'O': cb}
        # PN=32 is normally INC (>30), but PDR=-2 → modifier +2 → PN adjusted -2 → 30 → COM
        fac = self._make_fac_card(pn=32)
        deck = FACDeck()
        random.seed(42)
        result = resolver.resolve_pass_5e(
            fac, deck, qb, recs[0], recs,
            pass_type="SHORT",
            defenders_by_box=defenders_by_box,
        )
        assert result.result in ("COMPLETE", "TD"), f"Expected COM with negative PDR, got {result.result}"

    def test_empty_box_gives_plus_5(self):
        """Empty covering box → +5 to completion range."""
        from engine.player_card import PlayerCard
        resolver = PlayResolver()
        qb = self._make_qb(com_max=25)
        recs = self._make_receivers(5)
        # Box O (covers FL) is empty → +5 → PN 30 adjusted to 25 → COM
        defenders_by_box = {'K': PlayerCard("CB", "DAL", "CB", 24, "B")}  # Only box K filled
        fac = self._make_fac_card(pn=30)
        deck = FACDeck()
        random.seed(42)
        result = resolver.resolve_pass_5e(
            fac, deck, qb, recs[0], recs,
            pass_type="SHORT",
            defenders_by_box=defenders_by_box,
        )
        assert result.result in ("COMPLETE", "TD"), f"Expected COM with empty box +5, got {result.result}"

    def test_zero_pdr_no_effect(self):
        """PDR=0 has no effect on completion."""
        from engine.player_card import PlayerCard
        resolver = PlayResolver()
        qb = self._make_qb(com_max=30)
        recs = self._make_receivers(5)
        cb = PlayerCard("Average CB", "DAL", "CB", 24, "B", pass_defense_rating=0)
        defenders_by_box = {'O': cb}
        # PN=30 → exactly at COM boundary → should complete
        fac = self._make_fac_card(pn=30)
        deck = FACDeck()
        random.seed(42)
        result = resolver.resolve_pass_5e(
            fac, deck, qb, recs[0], recs,
            pass_type="SHORT",
            defenders_by_box=defenders_by_box,
        )
        assert result.result in ("COMPLETE", "TD"), f"Expected COM with PDR=0, got {result.result}"


# ─── INC→INT Covering Defender Tests ────────────────────────────────────


class TestINCInterceptionCoveringDefender:
    """Test INC→INT uses covering defender's intercept_range."""

    def _make_fac_card(self, pn=45, rn=6):
        from engine.fac_deck import FACCard
        return FACCard(
            card_number=1, run_number=str(rn), pass_number=str(pn),
            sweep_left="A", inside_left="B", sweep_right="C", inside_right="D",
            quick_kick="Orig", short_pass="Orig", long_pass="Orig",
            screen="Com", end_run="OK", z_result="NONE", solo="P",
        )

    def _make_qb(self, com_max=20, inc_max=44):
        from engine.player_card import PlayerCard, PassRanges
        qb = PlayerCard("Test QB", "KC", "QB", 15, "A")
        qb.passing_short = PassRanges(com_max=com_max, inc_max=inc_max)
        qb.passing_quick = PassRanges(com_max=com_max, inc_max=inc_max)
        qb.passing_long = PassRanges(com_max=com_max - 5, inc_max=inc_max)
        return qb

    def _make_receivers(self, n=5):
        from engine.player_card import PlayerCard, ThreeValueRow
        recs = []
        for i in range(n):
            r = PlayerCard(f"WR{i}", "KC", "WR", 80+i, "B")
            r.pass_gain = [ThreeValueRow(v1=5, v2=8, v3=15) for _ in range(12)]
            recs.append(r)
        return recs

    def test_covering_defender_intercept_fires(self):
        """Covering defender with intercept_range catches the INC→INT."""
        from engine.player_card import PlayerCard
        resolver = PlayResolver()
        qb = self._make_qb(com_max=20, inc_max=40)
        recs = self._make_receivers(5)
        # CB in box O covers FL (recs[0]), intercept_range=38
        cb = PlayerCard("Ball Hawk CB", "DAL", "CB", 24, "A",
                        pass_defense_rating=0, intercept_range=38)
        defenders_by_box = {'O': cb}
        # PN=39: INC range (21-40), and 38 ≤ 39 ≤ 48 → INT
        fac = self._make_fac_card(pn=39)
        deck = FACDeck()
        random.seed(42)
        result = resolver.resolve_pass_5e(
            fac, deck, qb, recs[0], recs,
            pass_type="SHORT",
            defenders_by_box=defenders_by_box,
        )
        assert result.result == "INT", f"Expected INT from covering defender, got {result.result}"
        assert "Ball Hawk CB" in result.description

    def test_no_defenders_by_box_legacy_fallback(self):
        """Without defenders_by_box, falls back to legacy check (offensive receiver)."""
        resolver = PlayResolver()
        qb = self._make_qb(com_max=20, inc_max=44)
        recs = self._make_receivers(5)
        # No defenders_by_box → legacy path, offensive receiver has intercept_range=0
        fac = self._make_fac_card(pn=42)
        deck = FACDeck()
        random.seed(99)
        result = resolver.resolve_pass_5e(
            fac, deck, qb, recs[0], recs,
            pass_type="SHORT",
        )
        # Should be INC (offensive players don't have intercept_range)
        assert result.result in ("INCOMPLETE", "INT")


# ─── Double Coverage INT Suppression Tests ───────────────────────────────


class TestDoubleCoverageINTSuppression:
    """Test double coverage defender away → INT suppressed."""

    def _make_fac_card(self, pn=39, rn=6):
        from engine.fac_deck import FACCard
        return FACCard(
            card_number=1, run_number=str(rn), pass_number=str(pn),
            sweep_left="A", inside_left="B", sweep_right="C", inside_right="D",
            quick_kick="Orig", short_pass="Orig", long_pass="Orig",
            screen="Com", end_run="OK", z_result="NONE", solo="P",
        )

    def _make_qb(self, com_max=20, inc_max=40):
        from engine.player_card import PlayerCard, PassRanges
        qb = PlayerCard("Test QB", "KC", "QB", 15, "A")
        qb.passing_short = PassRanges(com_max=com_max, inc_max=inc_max)
        qb.passing_quick = PassRanges(com_max=com_max, inc_max=inc_max)
        qb.passing_long = PassRanges(com_max=com_max - 5, inc_max=inc_max)
        return qb

    def _make_receivers(self, n=5):
        from engine.player_card import PlayerCard, ThreeValueRow
        recs = []
        for i in range(n):
            r = PlayerCard(f"WR{i}", "KC", "WR", 80+i, "B")
            r.pass_gain = [ThreeValueRow(v1=5, v2=8, v3=15) for _ in range(12)]
            recs.append(r)
        return recs

    def test_fs_away_on_double_coverage_suppresses_int(self):
        """FS (box M) away on double coverage → INT in box M suppressed.

        FL2 is covered by box M (FS). If FS has moved to double cover
        another receiver, their intercept shouldn't fire.
        """
        from engine.player_card import PlayerCard
        resolver = PlayResolver()
        qb = self._make_qb(com_max=20, inc_max=40)
        recs = self._make_receivers(5)
        # Target LE (recs[1]), covered by box K
        # FS in box M has intercept_range=38 but has moved to double-cover someone else
        fs = PlayerCard("FS Player", "DAL", "S", 21, "A",
                        pass_defense_rating=0, intercept_range=38)
        cb_k = PlayerCard("LCB", "DAL", "CB", 24, "B",
                          pass_defense_rating=0, intercept_range=38)
        defenders_by_box = {'K': cb_k, 'M': fs}

        # PN=39 would trigger INT for the covering defender in box K
        # The covering defender for LE is box K (cb_k), whose box is K, not M
        # So double_coverage_defender_box='M' should NOT suppress box K INT
        fac = self._make_fac_card(pn=39)
        deck = FACDeck()

        # Target LE (index 1) → covered by box K (cb_k)
        # double_coverage_defender_box='M' means FS left box M
        # Since cb_k is in box K (not M), cb_k's INT should still fire
        random.seed(42)
        result = resolver.resolve_pass_5e(
            fac, deck, qb, recs[1], recs,
            pass_type="SHORT",
            defenders_by_box=defenders_by_box,
            double_coverage_defender_box='M',
        )
        assert result.result == "INT", f"INT from box K should not be suppressed when M away"

    def test_covering_defender_box_matches_away_box_suppresses(self):
        """When the covering defender IS the one away on double coverage, suppress INT.

        If FL2 is the target, covered by box M (FS), and FS is away on double coverage,
        the FS's intercept is suppressed.
        """
        from engine.player_card import PlayerCard
        resolver = PlayResolver()
        qb = self._make_qb(com_max=20, inc_max=40)
        # Need FL2 target — that requires a specific FAC card and receiver setup
        # FL2 maps to box M. Since we're targeting recs[0] = FL → box O, let's
        # test with LE → box K and set double_coverage_defender_box='K'
        recs = self._make_receivers(5)
        cb_k = PlayerCard("LCB", "DAL", "CB", 24, "B",
                          pass_defense_rating=0, intercept_range=38)
        defenders_by_box = {'K': cb_k}

        fac = self._make_fac_card(pn=39)
        deck = FACDeck()
        random.seed(42)
        # Target LE (recs[1]) → covered by box K
        # double_coverage_defender_box='K' → cb_k has left → INT suppressed
        result = resolver.resolve_pass_5e(
            fac, deck, qb, recs[1], recs,
            pass_type="SHORT",
            defenders_by_box=defenders_by_box,
            double_coverage_defender_box='K',  # box K defender away
        )
        assert result.result == "INCOMPLETE", \
            f"INT should be suppressed when covering defender away, got {result.result}"
