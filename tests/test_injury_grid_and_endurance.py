"""Tests for the injury replacement grid fix and endurance enforcement."""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.player_card import PlayerCard
from engine.team import Team, Roster
from engine.game import Game, GameState
from engine.play_resolver import PlayResolver


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_rb(name, number=20, endurance=0):
    return PlayerCard(
        player_name=name, team="TST", position="RB", number=number,
        overall_grade="C", endurance_rushing=endurance,
    )


def _make_wr(name, number=80, endurance=0):
    return PlayerCard(
        player_name=name, team="TST", position="WR", number=number,
        overall_grade="C", endurance_rushing=endurance,
    )


def _make_qb(name="TestQB", number=7):
    return PlayerCard(
        player_name=name, team="TST", position="QB", number=number,
        overall_grade="B",
    )


def _make_te(name="TestTE", number=85, endurance=0):
    return PlayerCard(
        player_name=name, team="TST", position="TE", number=number,
        overall_grade="C", endurance_rushing=endurance,
    )


def _make_ol(name, position, number):
    return PlayerCard(
        player_name=name, team="TST", position=position, number=number,
        overall_grade="C",
    )


def _make_def(name, position, number):
    return PlayerCard(
        player_name=name, team="TST", position=position, number=number,
        overall_grade="C",
    )


def _build_roster(rbs=None, qbs=None, wrs=None, tes=None):
    """Build a minimal roster for testing."""
    rbs = rbs or [_make_rb("RB1", 20), _make_rb("RB2", 22)]
    qbs = qbs or [_make_qb()]
    wrs = wrs or [_make_wr("WR1", 80), _make_wr("WR2", 81)]
    tes = tes or [_make_te("TE1", 85)]
    ol = [
        _make_ol("LT", "LT", 70),
        _make_ol("LG", "LG", 71),
        _make_ol("C", "C", 72),
        _make_ol("RG", "RG", 73),
        _make_ol("RT", "RT", 74),
    ]
    defenders = [_make_def(f"DEF{i}", pos, 50 + i)
                 for i, pos in enumerate(["DE", "DT", "DT", "DE",
                                          "LB", "LB", "LB",
                                          "CB", "CB", "SS", "FS"])]
    return Roster(
        qbs=qbs, rbs=rbs, wrs=wrs, tes=tes,
        kickers=[], punters=[],
        offensive_line=ol, defenders=defenders,
    )


def _build_game():
    """Build a minimal Game with two teams."""
    home_roster = _build_roster()
    away_roster = _build_roster(
        rbs=[_make_rb("AwayRB1", 30), _make_rb("AwayRB2", 32)],
        qbs=[_make_qb("AwayQB", 12)],
        wrs=[_make_wr("AwayWR1", 83), _make_wr("AwayWR2", 84)],
        tes=[_make_te("AwayTE1", 86)],
    )
    home = Team(abbreviation="HOM", city="Home", name="Tester",
                conference="AFC", division="North", roster=home_roster)
    away = Team(abbreviation="AWY", city="Away", name="Visitor",
                conference="NFC", division="South", roster=away_roster)
    return Game(home, away)


# ═════════════════════════════════════════════════════════════════════════════
#  Part 1 — Injury Replacement Grid Fix
# ═════════════════════════════════════════════════════════════════════════════

class TestImmediateInjurySwap:
    """Verify _immediate_injury_swap promotes backup into starter slot."""

    def test_rb_injury_swaps_starter_slot(self):
        game = _build_game()
        team = game.get_offense_team()
        rb1_name = team.roster.rbs[0].player_name
        rb2_name = team.roster.rbs[1].player_name

        # Mark RB1 as injured
        game.state.injuries[rb1_name] = 4

        # Trigger the swap
        game._immediate_injury_swap(rb1_name)

        # After swap, rbs[0] should be the backup
        assert team.roster.rbs[0].player_name == rb2_name
        # The injured player should now be in rbs[1]
        assert team.roster.rbs[1].player_name == rb1_name

    def test_wr_injury_swaps_starter_slot(self):
        game = _build_game()
        team = game.get_offense_team()
        wr1_name = team.roster.wrs[0].player_name
        wr2_name = team.roster.wrs[1].player_name

        game.state.injuries[wr1_name] = 4
        game._immediate_injury_swap(wr1_name)

        assert team.roster.wrs[0].player_name == wr2_name

    def test_swap_only_happens_for_starter(self):
        """No swap if the injured player isn't in the starter slot."""
        game = _build_game()
        team = game.get_offense_team()
        rb1_name = team.roster.rbs[0].player_name
        rb2_name = team.roster.rbs[1].player_name

        # Injure the backup (rbs[1])
        game.state.injuries[rb2_name] = 4
        game._immediate_injury_swap(rb2_name)

        # Starter slot unchanged
        assert team.roster.rbs[0].player_name == rb1_name

    def test_swap_generates_personnel_note(self):
        game = _build_game()
        game._current_play_personnel_note = None
        team = game.get_offense_team()
        rb1_name = team.roster.rbs[0].player_name

        game.state.injuries[rb1_name] = 4
        game._immediate_injury_swap(rb1_name)

        # Personnel note should mention the auto-sub
        assert game._current_play_personnel_note is not None
        assert "Auto-sub" in game._current_play_personnel_note
        assert rb1_name in game._current_play_personnel_note

    def test_get_rb_returns_healthy_after_swap(self):
        """After immediate swap, get_rb() should return the backup."""
        game = _build_game()
        team = game.get_offense_team()
        rb1_name = team.roster.rbs[0].player_name
        rb2_name = team.roster.rbs[1].player_name

        game.state.injuries[rb1_name] = 4
        game._immediate_injury_swap(rb1_name)

        # get_rb() should now return the backup without further swapping
        rb = game.get_rb()
        assert rb.player_name == rb2_name


# ═════════════════════════════════════════════════════════════════════════════
#  Part 2 — Endurance Enforcement
# ═════════════════════════════════════════════════════════════════════════════

class TestGameEnduranceCheck:
    """Test the game-level _check_endurance_violation method."""

    def test_endurance_0_never_violates(self):
        game = _build_game()
        rb = _make_rb("Workhorse", endurance=0)
        # Even if used on last play
        game.state.last_ball_carrier = "Workhorse"
        game.state.prev_ball_carrier = "Workhorse"
        game.state.endurance_used_this_drive.add("Workhorse")
        game.state.endurance_used_this_quarter.add("Workhorse")
        assert game._check_endurance_violation(rb) is None

    def test_endurance_1_violation_consecutive(self):
        game = _build_game()
        rb = _make_rb("SpeedBack", endurance=1)
        game.state.last_ball_carrier = "SpeedBack"
        assert game._check_endurance_violation(rb) == "endurance_1"

    def test_endurance_1_ok_after_rest(self):
        game = _build_game()
        rb = _make_rb("SpeedBack", endurance=1)
        game.state.last_ball_carrier = "OtherPlayer"
        game.state.prev_ball_carrier = "SpeedBack"
        # Only last_ball_carrier matters for endurance 1
        assert game._check_endurance_violation(rb) is None

    def test_endurance_2_violation_one_play_ago(self):
        game = _build_game()
        rb = _make_rb("MediumBack", endurance=2)
        game.state.last_ball_carrier = "MediumBack"
        assert game._check_endurance_violation(rb) == "endurance_2"

    def test_endurance_2_violation_two_plays_ago(self):
        game = _build_game()
        rb = _make_rb("MediumBack", endurance=2)
        game.state.last_ball_carrier = "OtherPlayer"
        game.state.prev_ball_carrier = "MediumBack"
        assert game._check_endurance_violation(rb) == "endurance_2"

    def test_endurance_2_ok_after_two_rest(self):
        game = _build_game()
        rb = _make_rb("MediumBack", endurance=2)
        game.state.last_ball_carrier = "Other1"
        game.state.prev_ball_carrier = "Other2"
        assert game._check_endurance_violation(rb) is None

    def test_endurance_3_violation_same_drive(self):
        game = _build_game()
        rb = _make_rb("LimitedBack", endurance=3)
        game.state.endurance_used_this_drive.add("LimitedBack")
        assert game._check_endurance_violation(rb) == "endurance_3"

    def test_endurance_3_ok_new_drive(self):
        game = _build_game()
        rb = _make_rb("LimitedBack", endurance=3)
        # Not in the set → OK
        assert game._check_endurance_violation(rb) is None

    def test_endurance_4_violation_same_quarter(self):
        game = _build_game()
        rb = _make_rb("RareBack", endurance=4)
        game.state.endurance_used_this_quarter.add("RareBack")
        assert game._check_endurance_violation(rb) == "endurance_4"

    def test_endurance_4_ok_new_quarter(self):
        game = _build_game()
        rb = _make_rb("RareBack", endurance=4)
        assert game._check_endurance_violation(rb) is None


class TestEnduranceResets:
    """Verify endurance tracking resets on possession/quarter changes."""

    def test_drive_endurance_resets_on_possession_change(self):
        game = _build_game()
        game.state.endurance_used_this_drive.add("SomePlayer")
        game.state.last_ball_carrier = "SomePlayer"
        game.state.prev_ball_carrier = "SomePlayer"

        game._change_possession(25)

        assert len(game.state.endurance_used_this_drive) == 0
        assert game.state.last_ball_carrier is None
        assert game.state.prev_ball_carrier is None

    def test_quarter_endurance_resets_on_quarter_change(self):
        game = _build_game()
        game.state.endurance_used_this_quarter.add("SomePlayer")
        game.state.time_remaining = 0  # Force quarter change

        game._advance_time(0)  # Trigger the check

        assert len(game.state.endurance_used_this_quarter) == 0

    def test_endurance_usage_recorded(self):
        game = _build_game()
        game._record_endurance_usage("TestRB")

        assert "TestRB" in game.state.endurance_used_this_drive
        assert "TestRB" in game.state.endurance_used_this_quarter

    def test_endurance_usage_not_recorded_for_none(self):
        game = _build_game()
        game._record_endurance_usage(None)

        assert len(game.state.endurance_used_this_drive) == 0
        assert len(game.state.endurance_used_this_quarter) == 0


class TestEndurancePenaltyRun:
    """Verify +2 RN penalty is applied for run endurance violations."""

    def test_penalty_applied(self):
        game = _build_game()
        rb = _make_rb("TiredRB", endurance=1)
        game.state.last_ball_carrier = "TiredRB"

        rn, violation = game._apply_endurance_penalty_to_run(rb, 5)
        assert rn == 7
        assert violation == "endurance_1"

    def test_no_penalty_when_rested(self):
        game = _build_game()
        rb = _make_rb("FreshRB", endurance=1)
        game.state.last_ball_carrier = "OtherPlayer"

        rn, violation = game._apply_endurance_penalty_to_run(rb, 5)
        assert rn == 5
        assert violation is None

    def test_no_penalty_for_endurance_0(self):
        game = _build_game()
        rb = _make_rb("Workhorse", endurance=0)
        game.state.last_ball_carrier = "Workhorse"

        rn, violation = game._apply_endurance_penalty_to_run(rb, 5)
        assert rn == 5
        assert violation is None


# ═════════════════════════════════════════════════════════════════════════════
#  Part 3 — WR/TE Endurance on Pass Plays
# ═════════════════════════════════════════════════════════════════════════════

class TestPassEnduranceCheck:
    """Verify endurance check works for WR and TE as pass targets."""

    def test_wr_endurance_pass_violation(self):
        """WR with endurance_pass=1 targeted on consecutive play → violation."""
        game = _build_game()
        wr = _make_wr("SpeedWR", endurance=1)
        wr.endurance_pass = 1
        game.state.last_ball_carrier = "SpeedWR"
        assert game._check_endurance_violation(wr, for_pass=True) == "endurance_1"

    def test_wr_endurance_pass_ok(self):
        """WR with endurance_pass=1 rested one play → no violation."""
        game = _build_game()
        wr = _make_wr("SpeedWR", endurance=1)
        wr.endurance_pass = 1
        game.state.last_ball_carrier = "OtherPlayer"
        assert game._check_endurance_violation(wr, for_pass=True) is None

    def test_wr_endurance_0_unlimited(self):
        """WR with endurance_pass=0 can be targeted every play."""
        game = _build_game()
        wr = _make_wr("StarWR", endurance=0)
        wr.endurance_pass = 0
        game.state.last_ball_carrier = "StarWR"
        game.state.endurance_used_this_drive.add("StarWR")
        game.state.endurance_used_this_quarter.add("StarWR")
        assert game._check_endurance_violation(wr, for_pass=True) is None

    def test_te_endurance_3_drive_violation(self):
        """TE with endurance_pass=3 used already this drive → violation."""
        game = _build_game()
        te = _make_te("BlockTE", endurance=3)
        te.endurance_pass = 3
        game.state.endurance_used_this_drive.add("BlockTE")
        assert game._check_endurance_violation(te, for_pass=True) == "endurance_3"

    def test_te_endurance_3_new_drive_ok(self):
        """TE with endurance_pass=3 not yet used this drive → ok."""
        game = _build_game()
        te = _make_te("BlockTE", endurance=3)
        te.endurance_pass = 3
        assert game._check_endurance_violation(te, for_pass=True) is None

    def test_rushing_endurance_used_for_runs(self):
        """Run play should use endurance_rushing (not endurance_pass)."""
        game = _build_game()
        rb = _make_rb("DualRB", endurance=0)
        rb.endurance_pass = 2  # More restrictive for passes
        # RB used last play
        game.state.last_ball_carrier = "DualRB"
        # For runs: endurance_rushing=0 → unlimited
        assert game._check_endurance_violation(rb, for_pass=False) is None
        # For passes: endurance_pass=2 → violation (used 1 play ago)
        assert game._check_endurance_violation(rb, for_pass=True) == "endurance_2"


# ═════════════════════════════════════════════════════════════════════════════
#  Part 4 — Safety Scoring
# ═════════════════════════════════════════════════════════════════════════════

class TestSafety:
    """Verify safety scoring when ball carrier is in own end zone."""

    def test_safety_awards_2_points_to_defense(self):
        game = _build_game()
        game.state.possession = "home"
        game.state.yard_line = 2
        game.state.down = 1
        game.state.distance = 10

        # Advance -5 yards (loss), pushing below goal line
        game._advance_down(-5)

        # Defense (away team) should get 2 points
        assert game.state.score.away == 2
        assert game.state.score.home == 0

    def test_safety_changes_possession(self):
        """After safety, possession must switch: the scoring team receives."""
        game = _build_game()
        game.state.possession = "home"  # home gets tackled in own endzone
        game.state.yard_line = 2

        game._advance_down(-5)

        # Scoring team (away) now has the ball
        assert game.state.possession == "away"

    def test_safety_logged(self):
        game = _build_game()
        game.state.possession = "away"
        game.state.yard_line = 1

        game._advance_down(-3)

        # Home team (defense) gets 2 points
        assert game.state.score.home == 2
        assert any("SAFETY" in entry for entry in game.state.play_log)

    def test_no_safety_at_1(self):
        """Ball at 1, loss of 0 = no safety."""
        game = _build_game()
        game.state.possession = "home"
        game.state.yard_line = 1
        game.state.distance = 10
        game.state.down = 1

        result = game._advance_down(0)
        # No safety, normal play
        assert game.state.score.away == 0
        assert game.state.yard_line == 1


class TestSafetyKickoffYardLine:
    """Verify the yard-line helper for safety free kicks."""

    def test_plain_touchback_at_15(self):
        """Safety kickoff plain touchback (no modifier) → 15."""
        from engine.play_resolver import PlayResult
        game = _build_game()
        tb = PlayResult("KICKOFF", 0, "TOUCHBACK", description="Touchback")
        assert game._safety_kickoff_yard_line(tb) == 15

    def test_touchback_with_modifier(self):
        """Safety kickoff TB already at 17 (20-3 modifier) → 17-5=12."""
        from engine.play_resolver import PlayResult
        game = _build_game()
        tb = PlayResult("KICKOFF", 17, "TOUCHBACK",
                        description="Kickoff — touchback, ball at the 17-yard line")
        assert game._safety_kickoff_yard_line(tb) == 12

    def test_oob_safety_kickoff(self):
        """OOB safety kickoff → 40-15 = 25."""
        from engine.play_resolver import PlayResult
        game = _build_game()
        oob = PlayResult("KICKOFF", 0, "OOB", description="Kickoff OOB")
        assert game._safety_kickoff_yard_line(oob) == 25

    def test_return_uses_yards_gained(self):
        """Returned kick uses yards_gained as-is (field position from return)."""
        from engine.play_resolver import PlayResult
        game = _build_game()
        ret = PlayResult("KICKOFF", 33, "RETURN", description="Return to 33")
        assert game._safety_kickoff_yard_line(ret) == 33


# ═════════════════════════════════════════════════════════════════════════════
#  Part 5 — Touchback Yard Line Fix
# ═════════════════════════════════════════════════════════════════════════════

class TestTouchbackYardLine:
    """Verify touchbacks use 20-yard line per 5E rules."""

    def test_kickoff_touchback_at_20(self):
        game = _build_game()
        from engine.play_resolver import PlayResult
        touchback = PlayResult("KICKOFF", 0, "TOUCHBACK",
                               description="Touchback")
        yl = game._kickoff_yard_line(touchback)
        assert yl == 20
