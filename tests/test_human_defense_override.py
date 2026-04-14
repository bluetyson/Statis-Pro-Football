"""Tests for human defensive play call override and run-stop fixes."""
import json
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.fac_deck import FACDeck
from engine.play_resolver import PlayResolver
from engine.play_types import DefensivePlay
from engine.game import Game
from engine.team import Team
from engine.solitaire import PlayCall


def _load_team(abbr):
    """Load a 5E team from JSON."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "engine", "data", "2025_5e", f"{abbr}.json"
    )
    with open(path) as f:
        return Team.from_dict(json.load(f))


def _find_rusher(team, name_substr):
    for p in team.roster.rbs:
        if name_substr in p.player_name:
            return p
    return None


class TestHumanDefenseOverride:
    """Verify that human defensive play call is used, not an AI-generated one."""

    def test_pass_defense_shown_in_result(self):
        """When human selects PASS_DEFENSE, the result should reflect it."""
        buf = _load_team("BUF")
        kc = _load_team("KC")
        game = Game(buf, kc, seed=42)
        game.state.down = 1
        game.state.distance = 10
        game.state.yard_line = 30

        play_call = PlayCall(
            play_type="RUN", direction="IL",
            formation="UNDER_CENTER", reasoning="test"
        )
        result = game.execute_play(
            play_call=play_call,
            defense_formation="4_3",
            defensive_play="PASS_DEFENSE",
        )
        assert result.defensive_play == "PASS_DEFENSE"
        assert "Pass Defense" in result.defensive_play_call

    def test_run_defense_key_back_1_shown_in_result(self):
        """When human selects RUN_DEFENSE_KEY_BACK_1, the result should reflect it."""
        buf = _load_team("BUF")
        kc = _load_team("KC")
        game = Game(buf, kc, seed=42)
        game.state.down = 1
        game.state.distance = 10
        game.state.yard_line = 30

        play_call = PlayCall(
            play_type="RUN", direction="IL",
            formation="UNDER_CENTER", reasoning="test"
        )
        result = game.execute_play(
            play_call=play_call,
            defense_formation="4_3",
            defensive_play="RUN_DEFENSE_KEY_BACK_1",
        )
        assert result.defensive_play == "RUN_DEFENSE_KEY_BACK_1"
        assert "Key on Back 1" in result.defensive_play_call

    def test_pass_defense_zero_rn_modifier(self):
        """PASS_DEFENSE should produce +0 RN modifier for runs."""
        buf = _load_team("BUF")
        rusher = _find_rusher(buf, "Cook")
        assert rusher is not None

        deck = FACDeck(seed=42)
        resolver = PlayResolver()
        card = deck.draw_non_z()

        result = resolver.resolve_run_5e(
            card, deck, rusher, "IL",
            defense_run_stop=85,
            defense_formation="4_3",
            defensive_play_5e=DefensivePlay.PASS_DEFENSE,
        )
        # Check log contains def_modifier=+0
        mod_entries = [e for e in result.debug_log if "[RN MOD]" in e]
        assert any("def_modifier=+0" in e for e in mod_entries)

    def test_run_defense_key_back_plus4_modifier(self):
        """RUN_DEFENSE_KEY_BACK_1 should produce +4 RN modifier."""
        buf = _load_team("BUF")
        rusher = _find_rusher(buf, "Cook")

        deck = FACDeck(seed=42)
        resolver = PlayResolver()
        card = deck.draw_non_z()

        result = resolver.resolve_run_5e(
            card, deck, rusher, "IL",
            defense_run_stop=85,
            defense_formation="4_3",
            defensive_play_5e=DefensivePlay.RUN_DEFENSE_KEY_BACK_1,
        )
        mod_entries = [e for e in result.debug_log if "[RN MOD]" in e]
        assert any("def_modifier=+4" in e for e in mod_entries)


class TestOLOnlyNoLegacyRunStop:
    """OL_ONLY and TWO_OL matchups should not subtract legacy team run-stop."""

    def test_ol_only_bk_matchup_no_subtraction(self):
        """When FAC matchup is 'BK' (OL_ONLY), yards include BK blocking value,
        no legacy run-stop subtraction."""
        buf = _load_team("BUF")
        rusher = _find_rusher(buf, "Cook")
        resolver = PlayResolver()

        # Find a card with 'BK' IL matchup
        deck = FACDeck(seed=1)
        bk_card = None
        for _ in range(300):
            card = deck.draw_non_z()
            if card.inside_left and card.inside_left.strip() == "BK":
                bk_card = card
                break
        assert bk_card is not None, "No BK matchup card found in 300 draws"

        result = resolver.resolve_run_5e(
            bk_card, deck, rusher, "IL",
            defense_run_stop=85,
            defense_formation="4_3",
            defensive_play_5e=DefensivePlay.PASS_DEFENSE,
        )
        # Should not produce absurdly negative yards from legacy run-stop
        assert result.yards_gained >= -3, (
            f"Got {result.yards_gained} yards; legacy run-stop should not apply"
        )
        # Check that no defensive box is in the matchup
        def_entries = [e for e in result.debug_log if "[DEF]" in e]
        assert any("No defensive box" in e for e in def_entries), (
            f"Expected 'No defensive box' log, got: {def_entries}"
        )

    def test_two_ol_matchup_no_subtraction(self):
        """When FAC matchup is 'CN + LG' (TWO_OL), adds BV, no run-stop subtraction."""
        buf = _load_team("BUF")
        rusher = _find_rusher(buf, "Cook")
        resolver = PlayResolver()

        deck = FACDeck(seed=1)
        ol_card = None
        for _ in range(300):
            card = deck.draw_non_z()
            il = card.inside_left or ""
            if " + " in il and not all(
                len(p.strip()) == 1 and p.strip().isupper()
                for p in il.split(" + ")
            ):
                ol_card = card
                break
        assert ol_card is not None, "No TWO_OL matchup card found"

        result = resolver.resolve_run_5e(
            ol_card, deck, rusher, "IL",
            defense_run_stop=85,
            defense_formation="4_3",
            defensive_play_5e=DefensivePlay.PASS_DEFENSE,
        )
        # The yards should be reasonable (base yards + blocking values, no subtraction)
        assert result.yards_gained >= -3


class TestBlockingBackBVLogging:
    """Blocking back BV should be logged when BK is in the matchup."""

    def test_bk_matchup_logs_bv(self):
        """BK matchup should log blocking back BV via offensive_blockers_by_pos."""
        buf = _load_team("BUF")
        rusher = _find_rusher(buf, "Cook")
        resolver = PlayResolver()

        deck = FACDeck(seed=1)
        bk_card = None
        for _ in range(300):
            card = deck.draw_non_z()
            if card.inside_left and card.inside_left.strip() == "BK":
                bk_card = card
                break
        assert bk_card is not None

        result = resolver.resolve_run_5e(
            bk_card, deck, rusher, "IL",
            defense_run_stop=85,
            defense_formation="4_3",
            defensive_play_5e=DefensivePlay.PASS_DEFENSE,
            blocking_back_bv=2,
        )
        # Should log BK blocking back BV via fallback
        bv_entries = [e for e in result.debug_log if "BK" in e and "BV" in e]
        assert len(bv_entries) >= 1, (
            f"Expected BK BV log entry, got: {[e for e in result.debug_log if 'OFF' in e or 'BK' in e]}"
        )
