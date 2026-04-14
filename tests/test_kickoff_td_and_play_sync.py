"""Tests for kickoff return TD scoring, follow-up kickoff, and play direction sync.

Covers:
  - Opening kickoff return TD updates score (Issue 1)
  - Opening kickoff return TD triggers a follow-up kickoff (Issue 2)
  - Offensive play direction synced with 5E OffensivePlay display (Issue 3)
"""

import random
import pytest
from unittest.mock import patch, MagicMock

from engine.game import Game
from engine.play_resolver import PlayResolver, PlayResult
from engine.fac_deck import FACDeck, FACCard
from engine.team import Team
from engine.solitaire import SolitaireAI, PlayCall
from engine.play_types import OffensivePlay


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_td_kickoff_result():
    """Create a PlayResult simulating a kickoff return touchdown."""
    return PlayResult(
        play_type="KICKOFF",
        yards_gained=100,
        result="KR_TD",
        is_touchdown=True,
        description="Kickoff to Test Player — returned for a TOUCHDOWN!",
        rusher="Test Player",
    )


def _make_normal_kickoff_result(yard_line=25):
    """Create a PlayResult simulating a normal kickoff return."""
    return PlayResult(
        play_type="KICKOFF",
        yards_gained=yard_line,
        result="RETURN",
        is_touchdown=False,
        description=f"Kickoff returned to the {yard_line}-yard line.",
    )


# ── Issue 1 & 2: Kickoff return TD scoring and follow-up kickoff ────────


class TestOpeningKickoffReturnTD:
    """Verify that a kickoff return TD on the opening kick updates score and
    triggers a follow-up kickoff with possession change."""

    def setup_method(self):
        random.seed(42)
        self.home = Team.load("KC", 2025)
        self.away = Team.load("BUF", 2025)

    def test_opening_kickoff_td_updates_score(self):
        """When opening kickoff is returned for a TD, score should increase."""
        td_result = _make_td_kickoff_result()
        normal_result = _make_normal_kickoff_result(25)

        # Patch _do_kickoff: first call returns TD, second returns normal
        call_count = [0]

        def mock_do_kickoff(self_game, kicking_team, receiving_team):
            call_count[0] += 1
            if call_count[0] == 1:
                return td_result
            return normal_result

        with patch.object(Game, '_do_kickoff', mock_do_kickoff):
            game = Game(self.home, self.away)

        # The receiving team scored a TD (6) + automatic XP (1) = 7
        receiving = game.state.possession  # After TD+kickoff, possession changes
        total_score = game.state.score.home + game.state.score.away
        assert total_score >= 6, (
            f"Score should be at least 6 after kickoff return TD, "
            f"got home={game.state.score.home} away={game.state.score.away}"
        )

    def test_opening_kickoff_td_triggers_followup_kickoff(self):
        """After opening kickoff TD, a follow-up kickoff should occur."""
        td_result = _make_td_kickoff_result()
        normal_result = _make_normal_kickoff_result(30)

        kickoff_calls = []

        def mock_do_kickoff(self_game, kicking_team, receiving_team):
            kickoff_calls.append({
                'kicking': kicking_team.abbreviation,
                'receiving': receiving_team.abbreviation,
            })
            if len(kickoff_calls) == 1:
                return td_result
            return normal_result

        with patch.object(Game, '_do_kickoff', mock_do_kickoff):
            game = Game(self.home, self.away)

        # Should have been called twice: opening kickoff + follow-up after TD
        assert len(kickoff_calls) == 2, (
            f"Expected 2 kickoff calls (opening + follow-up), got {len(kickoff_calls)}"
        )

    def test_opening_kickoff_td_changes_possession(self):
        """After opening kickoff TD + follow-up kickoff, possession should flip."""
        td_result = _make_td_kickoff_result()
        normal_result = _make_normal_kickoff_result(25)

        kickoff_calls = []

        def mock_do_kickoff(self_game, kicking_team, receiving_team):
            kickoff_calls.append({
                'kicking': kicking_team.abbreviation,
                'receiving': receiving_team.abbreviation,
            })
            if len(kickoff_calls) == 1:
                return td_result
            return normal_result

        with patch.object(Game, '_do_kickoff', mock_do_kickoff):
            game = Game(self.home, self.away)

        # The follow-up kickoff's kicking team should be the TD-scoring team
        # (i.e., the receiving team from the first kickoff)
        assert kickoff_calls[0]['receiving'] == kickoff_calls[1]['kicking'], (
            f"Follow-up kickoff should be kicked by the TD-scoring team. "
            f"First receiving: {kickoff_calls[0]['receiving']}, "
            f"Second kicking: {kickoff_calls[1]['kicking']}"
        )

    def test_opening_kickoff_td_play_log_mentions_touchdown(self):
        """Play log should mention the touchdown after kickoff return TD."""
        td_result = _make_td_kickoff_result()
        normal_result = _make_normal_kickoff_result(25)

        call_count = [0]

        def mock_do_kickoff(self_game, kicking_team, receiving_team):
            call_count[0] += 1
            if call_count[0] == 1:
                return td_result
            return normal_result

        with patch.object(Game, '_do_kickoff', mock_do_kickoff):
            game = Game(self.home, self.away)

        log = "\n".join(game.state.play_log)
        assert "TOUCHDOWN" in log, f"Play log should mention TOUCHDOWN:\n{log}"

    def test_normal_opening_kickoff_no_extra_kickoff(self):
        """A normal opening kickoff should NOT trigger a follow-up."""
        normal_result = _make_normal_kickoff_result(25)
        call_count = [0]

        def mock_do_kickoff(self_game, kicking_team, receiving_team):
            call_count[0] += 1
            return normal_result

        with patch.object(Game, '_do_kickoff', mock_do_kickoff):
            game = Game(self.home, self.away)

        assert call_count[0] == 1, (
            f"Normal kickoff should only call _do_kickoff once, got {call_count[0]}"
        )
        # Score should be 0-0
        assert game.state.score.home == 0
        assert game.state.score.away == 0


# ── Issue 3: Play direction synchronization ──────────────────────────────


class TestPlayDirectionSync:
    """Verify that the offensive play direction used for resolution matches
    the 5E OffensivePlay display string."""

    def setup_method(self):
        random.seed(42)
        self.home = Team.load("KC", 2025)
        self.away = Team.load("BUF", 2025)

    def test_sweep_left_uses_sl_direction(self):
        """When OffensivePlay is RUNNING_SWEEP_LEFT, direction should be SL."""
        game = Game(self.home, self.away)

        # Mock call_offense_play_5e to return RUNNING_SWEEP_LEFT
        from engine.play_types import OffensiveStrategy, PlayerInvolved

        with patch.object(game.ai, 'call_offense_play_5e',
                         return_value=(OffensivePlay.RUNNING_SWEEP_LEFT,
                                       OffensiveStrategy.NONE,
                                       PlayerInvolved.RB_1)):
            # Also ensure the legacy play_call returns a RUN
            with patch.object(game.ai, 'call_play_5e',
                             return_value=PlayCall("RUN", "I_FORM", "LEFT",
                                                   "test")):
                result = game.execute_play()

        # Check that the play log contains "SL" direction, not "IL"
        log = "\n".join(game.state.play_log)
        # The result description should reference the sweep direction
        if result.play_type == "RUN":
            assert "SL" in log or "Sweep Left" in log, (
                f"Expected SL/Sweep Left in log for RUNNING_SWEEP_LEFT:\n{log}"
            )

    def test_sweep_right_uses_sr_direction(self):
        """When OffensivePlay is RUNNING_SWEEP_RIGHT, direction should be SR."""
        game = Game(self.home, self.away)

        from engine.play_types import OffensiveStrategy, PlayerInvolved

        with patch.object(game.ai, 'call_offense_play_5e',
                         return_value=(OffensivePlay.RUNNING_SWEEP_RIGHT,
                                       OffensiveStrategy.NONE,
                                       PlayerInvolved.RB_1)):
            with patch.object(game.ai, 'call_play_5e',
                             return_value=PlayCall("RUN", "I_FORM", "RIGHT",
                                                   "test")):
                result = game.execute_play()

        if result.play_type == "RUN":
            log = "\n".join(game.state.play_log)
            assert "SR" in log or "Sweep Right" in log, (
                f"Expected SR/Sweep Right in log for RUNNING_SWEEP_RIGHT:\n{log}"
            )

    def test_inside_left_uses_il_direction(self):
        """When OffensivePlay is RUNNING_INSIDE_LEFT, direction should be IL."""
        game = Game(self.home, self.away)

        from engine.play_types import OffensiveStrategy, PlayerInvolved

        with patch.object(game.ai, 'call_offense_play_5e',
                         return_value=(OffensivePlay.RUNNING_INSIDE_LEFT,
                                       OffensiveStrategy.NONE,
                                       PlayerInvolved.RB_1)):
            with patch.object(game.ai, 'call_play_5e',
                             return_value=PlayCall("RUN", "I_FORM", "LEFT",
                                                   "test")):
                result = game.execute_play()

        if result.play_type == "RUN":
            log = "\n".join(game.state.play_log)
            assert "IL" in log or "Inside Left" in log, (
                f"Expected IL/Inside Left in log for RUNNING_INSIDE_LEFT:\n{log}"
            )

    def test_inside_right_uses_ir_direction(self):
        """When OffensivePlay is RUNNING_INSIDE_RIGHT, direction should be IR."""
        game = Game(self.home, self.away)

        from engine.play_types import OffensiveStrategy, PlayerInvolved

        with patch.object(game.ai, 'call_offense_play_5e',
                         return_value=(OffensivePlay.RUNNING_INSIDE_RIGHT,
                                       OffensiveStrategy.NONE,
                                       PlayerInvolved.RB_1)):
            with patch.object(game.ai, 'call_play_5e',
                             return_value=PlayCall("RUN", "I_FORM", "RIGHT",
                                                   "test")):
                result = game.execute_play()

        if result.play_type == "RUN":
            log = "\n".join(game.state.play_log)
            assert "IR" in log or "Inside Right" in log, (
                f"Expected IR/Inside Right in log for RUNNING_INSIDE_RIGHT:\n{log}"
            )

    def test_pass_play_not_affected_by_direction_sync(self):
        """Pass plays should not be altered by run direction synchronization."""
        game = Game(self.home, self.away)

        from engine.play_types import OffensiveStrategy, PlayerInvolved

        with patch.object(game.ai, 'call_offense_play_5e',
                         return_value=(OffensivePlay.SHORT_PASS,
                                       OffensiveStrategy.NONE,
                                       PlayerInvolved.LEFT_END)):
            with patch.object(game.ai, 'call_play_5e',
                             return_value=PlayCall("SHORT_PASS", "SHOTGUN",
                                                   "LEFT", "test")):
                result = game.execute_play()

        # Just verify no crash — pass plays should work normally
        assert result is not None
