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

    def test_wr1_injury_with_3wrs_keeps_wr2_at_fl_puts_wr3_at_le(self):
        """Regression: WR1 (LE) injury should bring WR3 (backup) onto the field,
        NOT displace WR2 (FL) into the LE slot and pull WR3 into FL.

        Before fix: injuring WR1 promoted WR2 to WR1-slot, leaving WR3 to
        auto-fill FL — a bench player appeared on the field as the flanker.

        After fix: WR3 fills the vacated LE slot; WR2 stays at FL.
        """
        wr1 = _make_wr("Starter_LE", 80)  # depth-chart WR1 → LE
        wr2 = _make_wr("Starter_FL", 81)  # depth-chart WR2 → FL
        wr3 = _make_wr("Backup_WR", 82)   # bench player, must NOT auto-appear

        roster = _build_roster(wrs=[wr1, wr2, wr3])
        home = Team(abbreviation="HOM", city="Home", name="Tester",
                    conference="AFC", division="North", roster=roster)
        away_roster = _build_roster(
            rbs=[_make_rb("AwayRB1", 30), _make_rb("AwayRB2", 32)],
            qbs=[_make_qb("AwayQB", 12)],
            wrs=[_make_wr("AwayWR1", 83), _make_wr("AwayWR2", 84)],
            tes=[_make_te("AwayTE1", 86)],
        )
        away = Team(abbreviation="AWY", city="Away", name="Visitor",
                    conference="NFC", division="South", roster=away_roster)
        game = Game(home, away)
        game.state.possession = "home"

        # Injure WR1 (the LE starter) and trigger auto-sub
        game.state.injuries[wr1.player_name] = 4
        game._immediate_injury_swap(wr1.player_name)

        # Verify the roster swap used WR3 (true backup), not WR2 (the other starter)
        assert game.get_offense_team().roster.wrs[0].player_name == wr3.player_name, \
            "WR3 (backup) should now occupy the WR1 depth-chart slot"
        assert game.get_offense_team().roster.wrs[1].player_name == wr2.player_name, \
            "WR2 (Starter_FL) should remain unchanged in the depth chart"

        # Verify _get_all_receivers assigns the correct slots:
        # LE = WR3 (replaced WR1), FL = WR2 (unchanged)
        receivers = game._get_all_receivers()
        slots = {getattr(r, "_formation_slot", None): r.player_name for r in receivers}
        assert slots.get("LE") == wr3.player_name, \
            f"LE slot should be {wr3.player_name!r} (backup), got {slots.get('LE')!r}"
        assert slots.get("FL") == wr2.player_name, \
            f"FL slot should remain {wr2.player_name!r}, got {slots.get('FL')!r}"
        # The backup is already in LE; they must NOT also appear as FL
        fl_player = slots.get("FL")
        assert fl_player != wr3.player_name, \
            "Backup WR must not appear at both LE and FL"

    def test_rb1_injury_with_3rbs_keeps_rb2_at_bk2_puts_rb3_at_bk1(self):
        """Regression: RB1 (BK1) injury should bring RB3 (backup) onto the field,
        NOT displace RB2 (BK2) into the BK1 slot and pull RB3 into BK2.

        Mirrors the WR LE/FL fix: RB has two default starters (BK1 + BK2), so
        the same search_start = max(injured_idx+1, n_starters) protection applies.

        Before fix: injuring RB1 promoted RB2 to RB1-slot, leaving RB3 to
        auto-fill BK2 — a bench player appeared on the field as a second back.

        After fix: RB3 fills the vacated BK1 slot; RB2 stays at BK2.
        """
        rb1 = _make_rb("Starter_BK1", 20)  # depth-chart RB1 → BK1
        rb2 = _make_rb("Starter_BK2", 21)  # depth-chart RB2 → BK2
        rb3 = _make_rb("Backup_RB", 22)    # bench player, must NOT auto-appear

        roster = _build_roster(rbs=[rb1, rb2, rb3])
        home = Team(abbreviation="HOM", city="Home", name="Tester",
                    conference="AFC", division="North", roster=roster)
        away_roster = _build_roster(
            rbs=[_make_rb("AwayRB1", 30), _make_rb("AwayRB2", 32)],
            qbs=[_make_qb("AwayQB", 12)],
            wrs=[_make_wr("AwayWR1", 83), _make_wr("AwayWR2", 84)],
            tes=[_make_te("AwayTE1", 86)],
        )
        away = Team(abbreviation="AWY", city="Away", name="Visitor",
                    conference="NFC", division="South", roster=away_roster)
        game = Game(home, away)
        game.state.possession = "home"

        # Injure RB1 (the BK1 starter) and trigger auto-sub
        game.state.injuries[rb1.player_name] = 4
        game._immediate_injury_swap(rb1.player_name)

        # Verify the roster swap used RB3 (true backup), not RB2 (the other starter)
        assert game.get_offense_team().roster.rbs[0].player_name == rb3.player_name, \
            "RB3 (backup) should now occupy the RB1 depth-chart slot"
        assert game.get_offense_team().roster.rbs[1].player_name == rb2.player_name, \
            "RB2 (Starter_BK2) should remain unchanged in the depth chart"

        # Verify _get_all_receivers assigns the correct slots:
        # BK1 = RB3 (replaced RB1), BK2 = RB2 (unchanged)
        receivers = game._get_all_receivers()
        slots = {getattr(r, "_formation_slot", None): r.player_name for r in receivers}
        assert slots.get("BK1") == rb3.player_name, \
            f"BK1 slot should be {rb3.player_name!r} (backup), got {slots.get('BK1')!r}"
        assert slots.get("BK2") == rb2.player_name, \
            f"BK2 slot should remain {rb2.player_name!r}, got {slots.get('BK2')!r}"
        # The backup is already in BK1; they must NOT also appear as BK2
        assert slots.get("BK2") != rb3.player_name, \
            "Backup RB must not appear at both BK1 and BK2"

    def test_rb2_injury_with_3rbs_keeps_rb1_at_bk1_puts_rb3_at_bk2(self):
        """RB2 (BK2) injury should bring RB3 (backup) into BK2; RB1 stays at BK1."""
        rb1 = _make_rb("Starter_BK1", 20)
        rb2 = _make_rb("Starter_BK2", 21)
        rb3 = _make_rb("Backup_RB", 22)

        roster = _build_roster(rbs=[rb1, rb2, rb3])
        home = Team(abbreviation="HOM", city="Home", name="Tester",
                    conference="AFC", division="North", roster=roster)
        away_roster = _build_roster(
            rbs=[_make_rb("AwayRB1", 30), _make_rb("AwayRB2", 32)],
            qbs=[_make_qb("AwayQB", 12)],
            wrs=[_make_wr("AwayWR1", 83), _make_wr("AwayWR2", 84)],
            tes=[_make_te("AwayTE1", 86)],
        )
        away = Team(abbreviation="AWY", city="Away", name="Visitor",
                    conference="NFC", division="South", roster=away_roster)
        game = Game(home, away)
        game.state.possession = "home"

        game.state.injuries[rb2.player_name] = 4
        game._immediate_injury_swap(rb2.player_name)

        # RB1 must remain at index 0 (BK1 untouched); RB3 fills RB2's slot
        assert game.get_offense_team().roster.rbs[0].player_name == rb1.player_name, \
            "RB1 (Starter_BK1) should remain at index 0"
        assert game.get_offense_team().roster.rbs[1].player_name == rb3.player_name, \
            "RB3 (backup) should fill RB2's vacated slot"

        receivers = game._get_all_receivers()
        slots = {getattr(r, "_formation_slot", None): r.player_name for r in receivers}
        assert slots.get("BK1") == rb1.player_name, \
            f"BK1 should still be {rb1.player_name!r}"
        assert slots.get("BK2") == rb3.player_name, \
            f"BK2 should now be {rb3.player_name!r} (backup)"

    def test_qb_injury_swaps_to_backup_no_bench_player_on_field(self):
        """QB injury promotes QB2; no other position is displaced."""
        qb1 = _make_qb("Starter_QB", 1)
        qb2 = _make_qb("Backup_QB", 2)

        roster = _build_roster(qbs=[qb1, qb2])
        home = Team(abbreviation="HOM", city="Home", name="Tester",
                    conference="AFC", division="North", roster=roster)
        away_roster = _build_roster(
            rbs=[_make_rb("AwayRB1", 30), _make_rb("AwayRB2", 32)],
            qbs=[_make_qb("AwayQB", 12)],
            wrs=[_make_wr("AwayWR1", 83), _make_wr("AwayWR2", 84)],
            tes=[_make_te("AwayTE1", 86)],
        )
        away = Team(abbreviation="AWY", city="Away", name="Visitor",
                    conference="NFC", division="South", roster=away_roster)
        game = Game(home, away)
        game.state.possession = "home"

        game.state.injuries[qb1.player_name] = 4
        game._immediate_injury_swap(qb1.player_name)

        # QB2 should now be at index 0
        assert game.get_offense_team().roster.qbs[0].player_name == qb2.player_name, \
            "QB2 (backup) should now occupy the QB1 depth-chart slot"
        assert game.get_offense_team().roster.qbs[1].player_name == qb1.player_name, \
            "QB1 (injured) should be at index 1"

        # get_qb() should return QB2
        qb = game.get_qb()
        assert qb.player_name == qb2.player_name

    def test_te_injury_promotes_backup_te_to_re_slot(self):
        """TE1 injury promotes TE2 to the RE slot; LE/FL receivers unchanged."""
        te1 = _make_te("Starter_TE", 85)
        te2 = _make_te("Backup_TE", 86)
        wr1 = _make_wr("WR1", 80)
        wr2 = _make_wr("WR2", 81)

        roster = _build_roster(tes=[te1, te2], wrs=[wr1, wr2])
        home = Team(abbreviation="HOM", city="Home", name="Tester",
                    conference="AFC", division="North", roster=roster)
        away_roster = _build_roster(
            rbs=[_make_rb("AwayRB1", 30), _make_rb("AwayRB2", 32)],
            qbs=[_make_qb("AwayQB", 12)],
            wrs=[_make_wr("AwayWR1", 83), _make_wr("AwayWR2", 84)],
            tes=[_make_te("AwayTE1", 87)],
        )
        away = Team(abbreviation="AWY", city="Away", name="Visitor",
                    conference="NFC", division="South", roster=away_roster)
        game = Game(home, away)
        game.state.possession = "home"

        game.state.injuries[te1.player_name] = 4
        game._immediate_injury_swap(te1.player_name)

        # TE2 should now be at index 0 (RE slot)
        assert game.get_offense_team().roster.tes[0].player_name == te2.player_name, \
            "TE2 (backup) should now occupy the TE1 depth-chart slot"

        # WR slots (LE, FL) must be unaffected
        receivers = game._get_all_receivers()
        slots = {getattr(r, "_formation_slot", None): r.player_name for r in receivers}
        assert slots.get("LE") == wr1.player_name, "LE (WR1) should be unchanged"
        assert slots.get("FL") == wr2.player_name, "FL (WR2) should be unchanged"
        assert slots.get("RE") == te2.player_name, "RE should now be TE2 (backup)"



# ═════════════════════════════════════════════════════════════════════════════
#  Part 1b — 2TE / 3TE (JUMBO) Formation Injury Swap
# ═════════════════════════════════════════════════════════════════════════════

def _build_game_multi_te(wrs, tes, extra_te_backup=None):
    """Build a Game configured for multi-TE formation testing."""
    all_tes = list(tes)
    if extra_te_backup:
        all_tes.append(extra_te_backup)
    roster = _build_roster(wrs=wrs, tes=all_tes)
    home = Team(abbreviation="HOM", city="Home", name="Tester",
                conference="AFC", division="North", roster=roster)
    away_roster = _build_roster(
        rbs=[_make_rb("AwayRB1", 30), _make_rb("AwayRB2", 32)],
        qbs=[_make_qb("AwayQB", 12)],
        wrs=[_make_wr("AwayWR1", 83), _make_wr("AwayWR2", 84)],
        tes=[_make_te("AwayTE1", 90)],
    )
    away = Team(abbreviation="AWY", city="Away", name="Visitor",
                conference="NFC", division="South", roster=away_roster)
    game = Game(home, away)
    game.state.possession = "home"
    return game


class TestMultiTEFormationInjurySwap:
    """Verify _immediate_injury_swap is correct for 2TE and 3TE/JUMBO packages.

    Root cause of the bug: when a formation package puts N TEs on the field
    via explicit overrides and one of them is injured, the old code searched
    from injured_idx+1 — finding another on-field TE — and redirected the
    injured player's override slot to that on-field TE.  The on-field TE's own
    slot override was still in place, so _get_all_receivers assigned it to two
    slots simultaneously (double-assignment).

    Fix: when has_slot_override=True and multiple players of the same position
    are in on_field_offense, skip ALL of them and pull the first healthy bench
    player instead.
    """

    # ── 2TE_1WR package ──────────────────────────────────────────────

    def test_2te_package_te1_injury_keeps_te2_at_fl_puts_te3_at_re(self):
        """2TE_1WR: TE1 (RE) injury brings TE3 (backup) to RE; TE2 stays at FL."""
        wr1 = _make_wr("WR1", 80)
        te1 = _make_te("TE1_RE", 85)   # RE starter
        te2 = _make_te("TE2_FL", 86)   # FL starter (on field)
        te3 = _make_te("TE3_bench", 87)  # bench — should fill

        game = _build_game_multi_te([wr1], [te1, te2], extra_te_backup=te3)
        # Apply 2TE_1WR: WR1→LE, TE1→RE, TE2→FL
        game.apply_formation_package("home", "2TE_1WR")

        # Confirm package is set correctly
        overrides = game._on_field_offense["home"]
        assert overrides.get("LE") == wr1.player_name
        assert overrides.get("RE") == te1.player_name
        assert overrides.get("FL") == te2.player_name

        # Injure TE1 (RE)
        game.state.injuries[te1.player_name] = 4
        game._immediate_injury_swap(te1.player_name)

        # TE3 should be promoted into TE1's depth-chart slot
        tes_roster = game.get_offense_team().roster.tes
        assert tes_roster[0].player_name == te3.player_name, \
            "TE3 (backup) should be at index 0 after swap"
        assert tes_roster[1].player_name == te2.player_name, \
            "TE2 should remain at index 1 (unchanged)"

        # Override for RE should now point to TE3; FL stays TE2
        overrides = game._on_field_offense["home"]
        assert overrides.get("RE") == te3.player_name, \
            f"RE override should be TE3 (backup), got {overrides.get('RE')!r}"
        assert overrides.get("FL") == te2.player_name, \
            f"FL override must remain TE2 (on-field starter), got {overrides.get('FL')!r}"

        # _get_all_receivers must not double-assign TE2
        receivers = game._get_all_receivers()
        slots = {getattr(r, "_formation_slot", None): r.player_name for r in receivers}
        assert slots.get("RE") == te3.player_name, \
            f"RE slot should be TE3, got {slots.get('RE')!r}"
        assert slots.get("FL") == te2.player_name, \
            f"FL slot should still be TE2, got {slots.get('FL')!r}"
        # Exactly one slot per player — TE2 must NOT appear twice
        player_names = [n for n in slots.values()]
        assert player_names.count(te2.player_name) == 1, \
            "TE2 must not be assigned to two slots"

    def test_2te_package_te2_injury_keeps_te1_at_re_puts_te3_at_fl(self):
        """2TE_1WR: TE2 (FL) injury brings TE3 (backup) to FL; TE1 stays at RE."""
        wr1 = _make_wr("WR1", 80)
        te1 = _make_te("TE1_RE", 85)
        te2 = _make_te("TE2_FL", 86)
        te3 = _make_te("TE3_bench", 87)

        game = _build_game_multi_te([wr1], [te1, te2], extra_te_backup=te3)
        game.apply_formation_package("home", "2TE_1WR")

        game.state.injuries[te2.player_name] = 4
        game._immediate_injury_swap(te2.player_name)

        tes_roster = game.get_offense_team().roster.tes
        assert tes_roster[0].player_name == te1.player_name, \
            "TE1 should remain at index 0"
        assert tes_roster[1].player_name == te3.player_name, \
            "TE3 (backup) should fill TE2's vacated slot"

        overrides = game._on_field_offense["home"]
        assert overrides.get("RE") == te1.player_name, "RE stays TE1"
        assert overrides.get("FL") == te3.player_name, "FL updated to TE3"

        receivers = game._get_all_receivers()
        slots = {getattr(r, "_formation_slot", None): r.player_name for r in receivers}
        assert slots.get("RE") == te1.player_name
        assert slots.get("FL") == te3.player_name
        assert slots.get("LE") == wr1.player_name

    def test_2te_package_wr_injury_only_affects_le_slot(self):
        """2TE_1WR: WR1 (LE) injury should not disturb TE1/TE2 assignments."""
        wr1 = _make_wr("WR1_LE", 80)
        wr2 = _make_wr("WR2_bench", 81)   # backup WR for LE
        te1 = _make_te("TE1_RE", 85)
        te2 = _make_te("TE2_FL", 86)

        roster = _build_roster(wrs=[wr1, wr2], tes=[te1, te2])
        home = Team(abbreviation="HOM", city="Home", name="Tester",
                    conference="AFC", division="North", roster=roster)
        away_roster = _build_roster(
            rbs=[_make_rb("AwayRB1", 30), _make_rb("AwayRB2", 32)],
            qbs=[_make_qb("AwayQB", 12)],
            wrs=[_make_wr("AwayWR1", 83), _make_wr("AwayWR2", 84)],
            tes=[_make_te("AwayTE1", 90)],
        )
        away = Team(abbreviation="AWY", city="Away", name="Visitor",
                    conference="NFC", division="South", roster=away_roster)
        game = Game(home, away)
        game.state.possession = "home"
        game.apply_formation_package("home", "2TE_1WR")

        game.state.injuries[wr1.player_name] = 4
        game._immediate_injury_swap(wr1.player_name)

        overrides = game._on_field_offense["home"]
        # LE override redirected to WR2; TE slots unchanged
        assert overrides.get("LE") == wr2.player_name, "LE should now be WR2"
        assert overrides.get("RE") == te1.player_name, "RE unchanged"
        assert overrides.get("FL") == te2.player_name, "FL unchanged"

    # ── 3TE / JUMBO package ──────────────────────────────────────────

    def test_3te_te1_injury_keeps_te2_le_te3_fl_puts_te4_at_re(self):
        """3TE: TE1 (RE) injury brings TE4 (backup) to RE; TE2/TE3 stay at LE/FL.

        This is the core bug scenario — without the fix, TE2 would be moved
        into RE and double-assigned (both RE and LE overrides pointing to TE2).
        """
        te1 = _make_te("TE1_RE", 85)
        te2 = _make_te("TE2_LE", 86)
        te3 = _make_te("TE3_FL", 87)
        te4 = _make_te("TE4_bench", 88)   # true backup, must fill

        game = _build_game_multi_te([], [te1, te2, te3], extra_te_backup=te4)
        game.apply_formation_package("home", "3TE")

        overrides = game._on_field_offense["home"]
        assert overrides.get("RE") == te1.player_name
        assert overrides.get("LE") == te2.player_name
        assert overrides.get("FL") == te3.player_name

        game.state.injuries[te1.player_name] = 4
        game._immediate_injury_swap(te1.player_name)

        tes_roster = game.get_offense_team().roster.tes
        assert tes_roster[0].player_name == te4.player_name, \
            "TE4 (backup) should move to index 0"

        overrides = game._on_field_offense["home"]
        assert overrides.get("RE") == te4.player_name, \
            f"RE must point to TE4 (backup), got {overrides.get('RE')!r}"
        assert overrides.get("LE") == te2.player_name, "LE must remain TE2"
        assert overrides.get("FL") == te3.player_name, "FL must remain TE3"

        receivers = game._get_all_receivers()
        slots = {getattr(r, "_formation_slot", None): r.player_name for r in receivers}
        assert slots.get("RE") == te4.player_name
        assert slots.get("LE") == te2.player_name
        assert slots.get("FL") == te3.player_name
        # No player appears in two slots
        names = list(slots.values())
        assert len(names) == len(set(names)), \
            "Each player must appear in exactly one slot"

    def test_3te_te2_injury_keeps_te1_re_te3_fl_puts_te4_at_le(self):
        """3TE: TE2 (LE) injury brings TE4 (backup) to LE; TE1/TE3 stay."""
        te1 = _make_te("TE1_RE", 85)
        te2 = _make_te("TE2_LE", 86)
        te3 = _make_te("TE3_FL", 87)
        te4 = _make_te("TE4_bench", 88)

        game = _build_game_multi_te([], [te1, te2, te3], extra_te_backup=te4)
        game.apply_formation_package("home", "3TE")

        game.state.injuries[te2.player_name] = 4
        game._immediate_injury_swap(te2.player_name)

        overrides = game._on_field_offense["home"]
        assert overrides.get("RE") == te1.player_name, "RE must remain TE1"
        assert overrides.get("LE") == te4.player_name, \
            f"LE must be TE4 (backup), got {overrides.get('LE')!r}"
        assert overrides.get("FL") == te3.player_name, "FL must remain TE3"

        receivers = game._get_all_receivers()
        slots = {getattr(r, "_formation_slot", None): r.player_name for r in receivers}
        assert slots.get("RE") == te1.player_name
        assert slots.get("LE") == te4.player_name
        assert slots.get("FL") == te3.player_name
        names = list(slots.values())
        assert len(names) == len(set(names)), "No player double-assigned"

    def test_3te_te3_injury_keeps_te1_re_te2_le_puts_te4_at_fl(self):
        """3TE: TE3 (FL) injury brings TE4 (backup) to FL; TE1/TE2 stay."""
        te1 = _make_te("TE1_RE", 85)
        te2 = _make_te("TE2_LE", 86)
        te3 = _make_te("TE3_FL", 87)
        te4 = _make_te("TE4_bench", 88)

        game = _build_game_multi_te([], [te1, te2, te3], extra_te_backup=te4)
        game.apply_formation_package("home", "3TE")

        game.state.injuries[te3.player_name] = 4
        game._immediate_injury_swap(te3.player_name)

        overrides = game._on_field_offense["home"]
        assert overrides.get("RE") == te1.player_name, "RE must remain TE1"
        assert overrides.get("LE") == te2.player_name, "LE must remain TE2"
        assert overrides.get("FL") == te4.player_name, \
            f"FL must be TE4 (backup), got {overrides.get('FL')!r}"

        receivers = game._get_all_receivers()
        slots = {getattr(r, "_formation_slot", None): r.player_name for r in receivers}
        assert slots.get("FL") == te4.player_name
        names = list(slots.values())
        assert len(names) == len(set(names)), "No player double-assigned"

    def test_jumbo_te1_injury_is_equivalent_to_3te(self):
        """JUMBO package uses same slot logic as 3TE — same fix applies."""
        te1 = _make_te("TE1_RE", 85)
        te2 = _make_te("TE2_LE", 86)
        te3 = _make_te("TE3_FL", 87)
        te4 = _make_te("TE4_bench", 88)

        game = _build_game_multi_te([], [te1, te2, te3], extra_te_backup=te4)
        game.apply_formation_package("home", "JUMBO")

        game.state.injuries[te1.player_name] = 4
        game._immediate_injury_swap(te1.player_name)

        overrides = game._on_field_offense["home"]
        assert overrides.get("RE") == te4.player_name, \
            f"RE must be TE4 (backup) after JUMBO TE1 injury, got {overrides.get('RE')!r}"
        assert overrides.get("LE") == te2.player_name, "LE must remain TE2"
        assert overrides.get("FL") == te3.player_name, "FL must remain TE3"

        receivers = game._get_all_receivers()
        slots = {getattr(r, "_formation_slot", None): r.player_name for r in receivers}
        names = list(slots.values())
        assert len(names) == len(set(names)), "No player double-assigned in JUMBO"

    def test_3te_no_backup_falls_back_to_next_healthy_te(self):
        """3TE with only 3 TEs (no bench): emergency fallback when backup pool is empty.

        The fix skips all on-field TEs when searching for a replacement.  If
        there are no TEs beyond index 2, the existing fallback loop (which
        retries from injured_idx+1) picks the next healthy on-field TE as a
        last resort.  This means one TE will momentarily hold two override
        slots — which is unavoidable when the roster is exhausted.  The key
        guarantee is: (1) no crash, (2) the injured player is removed from
        the RE override so play logic doesn't try to call plays for them.
        """
        te1 = _make_te("TE1_RE", 85)
        te2 = _make_te("TE2_LE", 86)
        te3 = _make_te("TE3_FL", 87)  # no TE4; roster is exhausted

        game = _build_game_multi_te([], [te1, te2, te3])
        game.apply_formation_package("home", "3TE")

        game.state.injuries[te1.player_name] = 4
        # Should not raise; fallback picks te2 (next healthy TE)
        game._immediate_injury_swap(te1.player_name)

        # The injured player must be removed from the RE override
        overrides = game._on_field_offense["home"]
        assert overrides.get("RE") is not None, \
            "RE override must be set even when no true backup exists"
        assert overrides.get("RE") != te1.player_name, \
            "Injured TE1 must not remain in the RE override"
        # In the no-backup case the emergency fallback reuses an on-field TE,
        # so double-assignment is acceptable and intentional.
        assert overrides.get("RE") in (te2.player_name, te3.player_name), \
            "Emergency fill must be one of the remaining healthy on-field TEs"


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

        # Snapshot scores before the play — the opening kickoff in __init__
        # may have already produced scoring (e.g. a kick-return TD), so we
        # compare deltas rather than absolute values.
        away_before = game.state.score.away
        home_before = game.state.score.home

        # Advance -5 yards (loss), pushing below goal line
        game._advance_down(-5)

        # Defense (away team) should gain exactly 2 points; home unchanged.
        assert game.state.score.away == away_before + 2
        assert game.state.score.home == home_before

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

        home_before = game.state.score.home
        game._advance_down(-3)

        # Home team (defense) gets exactly 2 more points
        assert game.state.score.home == home_before + 2
        assert any("SAFETY" in entry for entry in game.state.play_log)

    def test_no_safety_at_1(self):
        """Ball at 1, loss of 0 = no safety."""
        game = _build_game()
        game.state.possession = "home"
        game.state.yard_line = 1
        game.state.distance = 10
        game.state.down = 1

        away_before = game.state.score.away
        result = game._advance_down(0)
        # No safety: away score must not have increased
        assert game.state.score.away == away_before
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


# ═════════════════════════════════════════════════════════════════════════════
#  Part 6 — Defensive injury swap priority
# ═════════════════════════════════════════════════════════════════════════════

def _make_def_rated(name, position, number,
                    pass_rush=0, tackle=0, pass_defense=0):
    """Create a defender with explicit ability ratings."""
    card = PlayerCard(
        player_name=name, team="TST", position=position, number=number,
        overall_grade="C",
    )
    card.pass_rush_rating = pass_rush
    card.tackle_rating = tackle
    card.pass_defense_rating = pass_defense
    return card


def _build_game_with_defense(defenders_home):
    """Build a game where the home team uses a custom defenders list."""
    home_roster = _build_roster()
    home_roster.defenders = defenders_home
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


class TestDefensiveInjurySwapPriority:
    """Verify _immediate_injury_swap cross-position rules for defenders."""

    def _defenders_43(self):
        """Standard 4-3: 4 DL + 3 LB + 4 DB = 11 starters + 4 backups."""
        return [
            # starters
            _make_def_rated("DE1",  "DE",  91, pass_rush=3),
            _make_def_rated("DT1",  "DT",  92, tackle=3),
            _make_def_rated("DT2",  "DT",  93, tackle=2),
            _make_def_rated("DE2",  "DE",  94, pass_rush=2),
            _make_def_rated("OLB1", "OLB", 55, pass_rush=2),
            _make_def_rated("MLB1", "MLB", 56, tackle=3),
            _make_def_rated("OLB2", "OLB", 57, pass_rush=1),
            _make_def_rated("CB1",  "CB",  21, pass_defense=3),
            _make_def_rated("CB2",  "CB",  22, pass_defense=2),
            _make_def_rated("SS1",  "SS",  31, pass_defense=2),
            _make_def_rated("FS1",  "FS",  32, pass_defense=3),
            # backups
            _make_def_rated("ILB_back", "ILB", 58, tackle=2, pass_rush=1),
            _make_def_rated("OLB_back", "OLB", 59, pass_rush=3),
            _make_def_rated("CB_back",  "CB",  23, pass_defense=1),
            _make_def_rated("SS_back",  "SS",  33, pass_defense=1),
        ]

    def test_dt_injury_promotes_ilb(self):
        """DT injured → ILB/MLB promoted (interior gap role)."""
        defs = self._defenders_43()
        game = _build_game_with_defense(defs)
        game._immediate_injury_swap("DT1")
        # The slot formerly occupied by DT1 should now hold an interior LB
        promoted = game.home_team.roster.defenders[1]
        assert promoted.position.upper() in ("ILB", "MLB"), \
            f"Expected ILB/MLB replacement for DT, got {promoted.position}"

    def test_de_injury_promotes_olb(self):
        """DE injured → OLB promoted (edge-rusher role)."""
        defs = self._defenders_43()
        game = _build_game_with_defense(defs)
        game._immediate_injury_swap("DE1")
        promoted = game.home_team.roster.defenders[0]
        assert promoted.position.upper() == "OLB", \
            f"Expected OLB replacement for DE, got {promoted.position}"

    def test_de_injury_prefers_olb_over_ilb(self):
        """DE injured → OLB_back is preferred over ILB_back (edge role)."""
        defs = self._defenders_43()
        # Remove OLB1 and OLB2 from starters so OLB_back is the best OLB bench
        game = _build_game_with_defense(defs)
        # Injure DE1 — OLB_back (pass_rush=3) should win over ILB_back (tackle=2)
        game._immediate_injury_swap("DE1")
        promoted = game.home_team.roster.defenders[0]
        assert promoted.player_name == "OLB_back", \
            f"Expected OLB_back, got {promoted.player_name}"

    def test_dt_injury_prefers_ilb_over_olb(self):
        """DT injured → ILB_back is preferred over OLB (interior role)."""
        defs = self._defenders_43()
        game = _build_game_with_defense(defs)
        # ILB_back (tackle=2, pass_rush=1) vs OLB_back (pass_rush=3)
        # DT → prefers ILB/MLB first
        game._immediate_injury_swap("DT1")
        promoted = game.home_team.roster.defenders[1]
        assert promoted.player_name == "ILB_back", \
            f"Expected ILB_back, got {promoted.player_name}"

    def test_cb_injury_promotes_backup_cb(self):
        """CB injured → backup CB fills in (same group first)."""
        defs = self._defenders_43()
        game = _build_game_with_defense(defs)
        game._immediate_injury_swap("CB1")
        promoted = game.home_team.roster.defenders[7]
        assert promoted.position.upper() in ("CB", "S", "SS", "FS", "DB"), \
            f"Expected a DB replacement, got {promoted.position}"

    def test_cb_injury_no_olb_when_enough_dbs(self):
        """CB injured but 3+ DBs remain — OLB not called up as emergency."""
        defs = self._defenders_43()
        game = _build_game_with_defense(defs)
        game._immediate_injury_swap("CB1")
        promoted = game.home_team.roster.defenders[7]
        # With CB_back and SS_back available, result should be a real DB, not OLB
        assert promoted.position.upper() in ("CB", "S", "SS", "FS", "DB")

    def test_db_emergency_olb_when_few_dbs(self):
        """When only 2 healthy DBs remain, OLB may be called as emergency fill."""
        # Build a defense where only 2 DBs are available (2 CBs, one injured)
        defs = [
            _make_def_rated("DE1",  "DE",  91, pass_rush=2),
            _make_def_rated("DT1",  "DT",  92, tackle=2),
            _make_def_rated("DT2",  "DT",  93, tackle=2),
            _make_def_rated("DE2",  "DE",  94, pass_rush=2),
            _make_def_rated("OLB1", "OLB", 55, pass_rush=2, pass_defense=2),
            _make_def_rated("MLB1", "MLB", 56, tackle=2),
            _make_def_rated("OLB2", "OLB", 57, pass_rush=1, pass_defense=1),
            # Only 3 DBs total: CB1 (to be injured) + CB2 + SS1
            _make_def_rated("CB1",  "CB",  21, pass_defense=3),
            _make_def_rated("CB2",  "CB",  22, pass_defense=2),
            _make_def_rated("SS1",  "SS",  31, pass_defense=2),
            _make_def_rated("OLB_emerg", "OLB", 59, pass_defense=3),  # bench OLB
        ]
        game = _build_game_with_defense(defs)
        # Mark CB2 and SS1 as injured (injuries dict maps name -> duration > 0)
        game.state.injuries["CB2"] = 99
        game.state.injuries["SS1"] = 99
        game._immediate_injury_swap("CB1")
        promoted = game.home_team.roster.defenders[7]
        # OLB_emerg is the only healthy non-DL non-LB left
        assert promoted.position.upper() == "OLB", \
            f"Expected emergency OLB, got {promoted.position} ({promoted.player_name})"

    def test_defensive_sub_logged(self):
        """Auto defensive sub must appear in play log."""
        defs = self._defenders_43()
        game = _build_game_with_defense(defs)
        game._immediate_injury_swap("DT1")
        log = " ".join(game.state.play_log)
        assert "DEF SUB" in log or "EMERGENCY" in log, \
            "Defensive substitution was not logged"


# ═════════════════════════════════════════════════════════════════════════════
#  Part 7 — Offensive emergency fill grade priority
# ═════════════════════════════════════════════════════════════════════════════

class TestOffensiveEmergencyFillPriority:
    """Verify _get_all_receivers grade-sorts RBs used as emergency fills."""

    def _make_rb_graded(self, name, number, blocks=0, n_pass_gain_rows=0):
        rb = _make_rb(name, number)
        rb.blocks = blocks
        # Populate the requested number of pass_gain rows with a token value
        from engine.player_card import ThreeValueRow
        rb.pass_gain = [ThreeValueRow(v1=5, v2=8, v3=10)] * n_pass_gain_rows
        return rb

    def _build_game_no_wrs_no_tes(self, rbs):
        """Build a game whose home offense has only RBs (no WRs, no TEs)."""
        home_roster = Roster(
            qbs=[_make_qb()],
            rbs=rbs,
            wrs=[],
            tes=[],
            kickers=[],
            punters=[],
            offensive_line=[
                _make_ol("LT", "LT", 70), _make_ol("LG", "LG", 71),
                _make_ol("C", "C", 72),  _make_ol("RG", "RG", 73),
                _make_ol("RT", "RT", 74),
            ],
            defenders=[_make_def(f"DEF{i}", pos, 50 + i)
                        for i, pos in enumerate(["DE", "DT", "DT", "DE",
                                                 "LB", "LB", "LB",
                                                 "CB", "CB", "SS", "FS"])],
        )
        home = Team(abbreviation="HOM", city="Home", name="Tester",
                    conference="AFC", division="North", roster=home_roster)
        away_roster = _build_roster(
            rbs=[_make_rb("AwayRB1", 30)],
            qbs=[_make_qb("AwayQB", 12)],
            wrs=[_make_wr("AwayWR1", 83)],
            tes=[_make_te("AwayTE1", 86)],
        )
        away = Team(abbreviation="AWY", city="Away", name="Visitor",
                    conference="NFC", division="South", roster=away_roster)
        return Game(home, away)

    def test_re_emergency_fill_prefers_best_blocker(self):
        """RE (TE slot) emergency fill: RB with highest blocks wins."""
        blocker_rb = self._make_rb_graded("BlockerRB", 30, blocks=5, n_pass_gain_rows=0)
        receiver_rb = self._make_rb_graded("ReceiverRB", 31, blocks=-1, n_pass_gain_rows=8)
        rbs = [blocker_rb, receiver_rb]
        game = self._build_game_no_wrs_no_tes(rbs)
        game.state.possession = "home"
        receivers = game._get_all_receivers()
        # Find whichever RB was placed in the RE slot
        re_player = next((r for r in receivers if r._formation_slot == "RE"), None)
        assert re_player is not None, "RE slot was not filled"
        assert re_player.player_name == "BlockerRB", \
            f"Expected BlockerRB in RE, got {re_player.player_name}"

    def test_le_emergency_fill_prefers_best_receiver(self):
        """LE (WR slot) emergency fill: RB with most pass_gain rows wins."""
        blocker_rb = self._make_rb_graded("BlockerRB", 30, blocks=5, n_pass_gain_rows=0)
        receiver_rb = self._make_rb_graded("ReceiverRB", 31, blocks=-1, n_pass_gain_rows=8)
        rbs = [blocker_rb, receiver_rb]
        game = self._build_game_no_wrs_no_tes(rbs)
        game.state.possession = "home"
        receivers = game._get_all_receivers()
        le_player = next((r for r in receivers if r._formation_slot == "LE"), None)
        assert le_player is not None, "LE slot was not filled"
        assert le_player.player_name == "ReceiverRB", \
            f"Expected ReceiverRB in LE, got {le_player.player_name}"


# ═════════════════════════════════════════════════════════════════════════════
#  Part 8 — 5E Position-injury protection flag
# ═════════════════════════════════════════════════════════════════════════════

def _inject_injury_event(game, player_name: str, duration: int = 3):
    """Directly inject an INJURY z-card event into game state, bypassing FAC.

    This lets tests exercise the injury-processing block in _run_play by
    simulating `result.z_card_event = {"type": "INJURY", ...}` on a
    play-result that is then fed through the same code path.
    """
    # We call the processing fragment directly rather than going through
    # _run_play to keep tests simple and free of FAC randomness.
    side_pos = game._find_player_side_and_pos(player_name)
    if side_pos is None:
        return False  # player not found

    p_side, p_pos = side_pos
    already = p_pos in game.state.position_injury_flags.get(p_side, set())
    if already:
        game.state.play_log.append(
            f"  ⚕ Injury to {player_name} ignored "
            f"(position {p_pos} already injured this game)."
        )
        return False  # injury blocked

    game.state.injuries[player_name] = duration
    game.state.position_injury_flags[p_side].add(p_pos)
    game.state._injured_starter_positions[player_name] = (p_side, p_pos)
    game.state.play_log.append(
        f"  ⚕ {player_name} injured! Out for {duration} plays."
    )
    return True  # injury applied


def _tick_injuries(game, plays: int = 1):
    """Advance injury counters by *plays* ticks (mirroring the _run_play loop)."""
    for _ in range(plays):
        to_remove = []
        for name in list(game.state.injuries):
            game.state.injuries[name] -= 1
            if game.state.injuries[name] <= 0:
                to_remove.append(name)
                game.state.play_log.append(f"  ⚕ {name} returns from injury.")
        for name in to_remove:
            del game.state.injuries[name]
            if name in game.state._injured_starter_positions:
                clr_side, clr_pos = game.state._injured_starter_positions.pop(name)
                game.state.position_injury_flags[clr_side].discard(clr_pos)


class TestPositionInjuryProtectionFlag:
    """5E rule: a second injury to the same position is ignored while the
    first player is still injured; protection lifts when they return."""

    def _game_with_two_rbs(self):
        roster = _build_roster(
            rbs=[_make_rb("RB1", 20), _make_rb("RB2", 22)],
            qbs=[_make_qb()],
            wrs=[_make_wr("WR1", 80), _make_wr("WR2", 81)],
            tes=[_make_te("TE1", 85)],
        )
        home = Team(abbreviation="HOM", city="Home", name="Tester",
                    conference="AFC", division="North", roster=roster)
        away_roster = _build_roster(
            rbs=[_make_rb("AwayRB1", 30)],
            qbs=[_make_qb("AwayQB", 12)],
            wrs=[_make_wr("AwayWR1", 83)],
            tes=[_make_te("AwayTE1", 86)],
        )
        away = Team(abbreviation="AWY", city="Away", name="Visitor",
                    conference="NFC", division="South", roster=away_roster)
        return Game(home, away)

    # ── find_player_side_and_pos ─────────────────────────────────────

    def test_find_player_side_and_pos_home(self):
        game = self._game_with_two_rbs()
        result = game._find_player_side_and_pos("RB1")
        assert result == ("home", "RB")

    def test_find_player_side_and_pos_away(self):
        game = self._game_with_two_rbs()
        result = game._find_player_side_and_pos("AwayRB1")
        assert result == ("away", "RB")

    def test_find_player_side_and_pos_unknown(self):
        game = self._game_with_two_rbs()
        assert game._find_player_side_and_pos("NoSuchPlayer") is None

    # ── flag set when first injury fires ─────────────────────────────

    def test_flag_set_on_first_injury(self):
        game = self._game_with_two_rbs()
        applied = _inject_injury_event(game, "RB1", duration=3)
        assert applied is True
        assert "RB" in game.state.position_injury_flags["home"]

    def test_player_in_injuries_dict(self):
        game = self._game_with_two_rbs()
        _inject_injury_event(game, "RB1", duration=3)
        assert game.state.injuries.get("RB1", 0) == 3

    # ── second injury to same position is blocked ─────────────────────

    def test_second_injury_same_position_blocked(self):
        game = self._game_with_two_rbs()
        _inject_injury_event(game, "RB1", duration=99)  # sets flag
        applied = _inject_injury_event(game, "RB2", duration=3)
        assert applied is False, "Second RB injury should be blocked"
        assert "RB2" not in game.state.injuries

    def test_second_injury_logged_as_ignored(self):
        game = self._game_with_two_rbs()
        _inject_injury_event(game, "RB1", duration=99)
        _inject_injury_event(game, "RB2", duration=3)
        ignored = any(
            "ignored" in line and "RB2" in line
            for line in game.state.play_log
        )
        assert ignored, "Blocked injury should be logged as ignored"

    # ── flag lifted when original player returns ─────────────────────

    def test_flag_cleared_on_return(self):
        game = self._game_with_two_rbs()
        _inject_injury_event(game, "RB1", duration=2)
        assert "RB" in game.state.position_injury_flags["home"]

        _tick_injuries(game, plays=2)   # RB1 returns

        assert "RB" not in game.state.position_injury_flags["home"], \
            "Position flag should be cleared when RB1 returns"
        assert "RB1" not in game.state._injured_starter_positions

    def test_second_injury_fires_after_first_returns(self):
        game = self._game_with_two_rbs()
        _inject_injury_event(game, "RB1", duration=1)
        _tick_injuries(game, plays=1)   # RB1 returns, flag cleared

        applied = _inject_injury_event(game, "RB2", duration=2)
        assert applied is True, "Second RB injury should be allowed after flag cleared"
        assert "RB2" in game.state.injuries

    # ── different positions are independent ──────────────────────────

    def test_qb_and_rb_flags_independent(self):
        """QB flag does not protect RB and vice-versa."""
        game = self._game_with_two_rbs()
        qb_card = game.home_team.roster.qbs[0]
        _inject_injury_event(game, qb_card.player_name, duration=99)

        applied = _inject_injury_event(game, "RB1", duration=3)
        assert applied is True, "RB injury should fire even though QB is injured"
        assert "RB1" in game.state.injuries

    def test_away_team_flag_independent_of_home(self):
        """Away team's position flag does not protect home team's same position."""
        game = self._game_with_two_rbs()
        _inject_injury_event(game, "AwayRB1", duration=99)  # away RB flagged
        applied = _inject_injury_event(game, "RB1", duration=3)  # home RB
        assert applied is True, "Home RB injury should fire regardless of away flag"

    # ── injured_starter_positions bookkeeping ────────────────────────

    def test_injured_starter_positions_populated(self):
        game = self._game_with_two_rbs()
        _inject_injury_event(game, "RB1", duration=5)
        entry = game.state._injured_starter_positions.get("RB1")
        assert entry == ("home", "RB")

    def test_injured_starter_positions_cleared_on_return(self):
        game = self._game_with_two_rbs()
        _inject_injury_event(game, "RB1", duration=1)
        _tick_injuries(game, plays=1)
        assert "RB1" not in game.state._injured_starter_positions
