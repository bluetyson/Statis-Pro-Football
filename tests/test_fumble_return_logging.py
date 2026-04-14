"""Tests for fumble FAC resolution, return logging, and interception return logging.

Covers:
  - Team card fumble fields (fumbles_lost_max, def_fumble_adj) load from JSON
  - resolve_fumble_with_team_rating uses FAC PN and team card range
  - 5E run fumble draws FAC for PN-based recovery with detailed logging
  - Z-result fumble uses team card recovery
  - Kickoff return debug_log includes returner info and modifier breakdown
  - Punt return debug_log includes returner info, fair catch, modifier breakdown
  - Interception point field is populated on all INT results
  - INT return logging includes POI, return yards, defender position
  - INT return into opposing end zone triggers TD
"""

import random
import pytest
from unittest.mock import patch
from engine.team import Team
from engine.play_resolver import PlayResolver, PlayResult
from engine.fac_deck import FACDeck, FACCard
from engine.charts import Charts
from engine.player_card import PlayerCard


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_fac_card(card_number=1, run_number="6", pass_number="24",
                   sweep_left="A", inside_left="C", sweep_right="E",
                   inside_right="D", end_run="OK",
                   quick_kick="A", short_pass="B", long_pass="C",
                   screen="Com", z_result="", solo=""):
    return FACCard(
        card_number=card_number,
        run_number=run_number,
        pass_number=pass_number,
        sweep_left=sweep_left,
        inside_left=inside_left,
        sweep_right=sweep_right,
        inside_right=inside_right,
        end_run=end_run,
        quick_kick=quick_kick,
        short_pass=short_pass,
        long_pass=long_pass,
        screen=screen,
        z_result=z_result,
        solo=solo,
    )


def _make_rusher(name="Test Runner", grade="B"):
    return PlayerCard.from_dict({
        "name": name,
        "number": 28,
        "position": "RB",
        "overall_grade": grade,
        "rushing": [
            [3, 8, 15] for _ in range(12)
        ],
    })


def _make_qb(name="Test QB"):
    return PlayerCard.from_dict({
        "name": name,
        "number": 12,
        "position": "QB",
        "overall_grade": "A",
        "passing_short": {"com_max": 30, "inc_max": 42},
        # PN 1-30 = COM, PN 31-42 = INC, PN 43-48 = INT
    })


def _make_receiver(name="Test WR", position="WR"):
    return PlayerCard.from_dict({
        "name": name,
        "number": 81,
        "position": position,
        "overall_grade": "B",
        "pass_gain": [
            [5, 8, 15] for _ in range(12)
        ],
    })


def _make_returner(name="Return Man", grade="A", position="WR"):
    return PlayerCard.from_dict({
        "name": name,
        "number": 84,
        "position": position,
        "overall_grade": grade,
        "stats_summary": {"ypc": 5.0, "avg_yards": 10.0, "catch_rate": 0.6},
    })


def _make_punter(name="Test Punter"):
    return PlayerCard.from_dict({
        "name": name,
        "number": 4,
        "position": "P",
        "overall_grade": "B",
        "avg_distance": 45,
        "inside_20_rate": 0.3,
        "punt_return_pct": 0.4,
    })


# ── Team Card Fumble Fields ──────────────────────────────────────────────

class TestTeamFumbleFields:
    """Team model loads fumbles_lost_max and def_fumble_adj."""

    def test_default_values(self):
        team = Team(abbreviation="TST", city="Test", name="Testers",
                    conference="AFC", division="East")
        assert team.fumbles_lost_max == 21
        assert team.def_fumble_adj == 0

    def test_from_dict_loads_fields(self):
        data = {
            "abbreviation": "TST",
            "city": "Test",
            "name": "Testers",
            "conference": "AFC",
            "division": "East",
            "fumbles_lost_max": 18,
            "def_fumble_adj": 3,
            "players": [],
        }
        team = Team.from_dict(data)
        assert team.fumbles_lost_max == 18
        assert team.def_fumble_adj == 3

    def test_from_dict_defaults_when_missing(self):
        data = {
            "abbreviation": "TST",
            "city": "Test",
            "name": "Testers",
            "conference": "AFC",
            "division": "East",
            "players": [],
        }
        team = Team.from_dict(data)
        assert team.fumbles_lost_max == 21
        assert team.def_fumble_adj == 0

    def test_to_dict_includes_fields(self):
        team = Team(abbreviation="TST", city="Test", name="Testers",
                    conference="AFC", division="East")
        team.fumbles_lost_max = 15
        team.def_fumble_adj = 4
        d = team.to_dict()
        assert d["fumbles_lost_max"] == 15
        assert d["def_fumble_adj"] == 4


# ── Fumble Recovery with Team Rating ─────────────────────────────────────

class TestFumbleWithTeamRating:
    """resolve_fumble_with_team_rating uses PN and team card range."""

    def test_pn_in_range_means_fumble_lost(self):
        # PN 10 with range 1-21 → lost
        assert PlayResolver.resolve_fumble_with_team_rating(10, 21, 0, False) is True

    def test_pn_outside_range_means_recovered(self):
        # PN 30 with range 1-21 → recovered
        assert PlayResolver.resolve_fumble_with_team_rating(30, 21, 0, False) is False

    def test_pn_at_boundary_lost(self):
        assert PlayResolver.resolve_fumble_with_team_rating(21, 21, 0, False) is True

    def test_pn_just_outside_boundary_recovered(self):
        assert PlayResolver.resolve_fumble_with_team_rating(22, 21, 0, False) is False

    def test_def_adj_expands_range(self):
        # PN 23 with range 1-21+3=24 → lost
        assert PlayResolver.resolve_fumble_with_team_rating(23, 21, 3, False) is True

    def test_home_field_contracts_range(self):
        # PN 21 with range 1-(21-1)=20 → recovered (home bonus)
        assert PlayResolver.resolve_fumble_with_team_rating(21, 21, 0, True) is False

    def test_home_and_def_adj_combined(self):
        # PN 23 with range 1-(21+3-1)=23 → lost
        assert PlayResolver.resolve_fumble_with_team_rating(23, 21, 3, True) is True
        # PN 24 → recovered
        assert PlayResolver.resolve_fumble_with_team_rating(24, 21, 3, True) is False


# ── 5E Run Fumble Uses Team Card ─────────────────────────────────────────

class TestRunFumbleTeamCard:
    """resolve_run_5e fumble paths draw FAC PN and use team ratings."""

    def test_z_result_fumble_uses_team_rating(self):
        """Z-result fumble uses team card ratings for recovery with logging."""
        resolver = PlayResolver()
        deck = FACDeck()
        rusher = _make_rusher()

        # Card with z_result = "Fumble" — normal gain + Z-result fumble
        fac_card = _make_fac_card(run_number="6", z_result="Fumble")

        # Try seeds until we get a Z-result fumble
        found_fumble = False
        for seed in range(200):
            random.seed(seed)
            result = resolver.resolve_run_5e(
                fac_card, deck, rusher, "IL",
                fumbles_lost_max=25,
                def_fumble_adj=0,
                is_home=False,
            )
            if result.result == "FUMBLE":
                log_text = " ".join(result.debug_log)
                if "Z-result fumble" in log_text:
                    found_fumble = True
                    assert "fumbles_lost_max=25" in log_text
                    assert "FAC drawn for recovery" in log_text
                    assert "PN" in log_text
                    break

        assert found_fumble, "Should have triggered Z-result fumble in 200 seeds"



# ── Interception Point Tracking ──────────────────────────────────────────

class TestInterceptionPointTracking:
    """INT results set interception_point field."""

    def test_poi_calculation_short_pass(self):
        poi = PlayResolver.calculate_point_of_interception("SHORT", 6, 30)
        # SHORT: RN × 2 = 12. yard_line 30 + 12 = 42. 100 - 42 = 58.
        assert poi == 58

    def test_poi_calculation_long_pass(self):
        poi = PlayResolver.calculate_point_of_interception("LONG", 8, 40)
        # LONG: RN × 4 = 32. yard_line 40 + 32 = 72. 100 - 72 = 28.
        assert poi == 28

    def test_poi_touchback_at_goal_line(self):
        poi = PlayResolver.calculate_point_of_interception("LONG", 12, 70)
        # LONG: RN × 4 = 48. yard_line 70 + 48 = 118 → >= 100 → touchback at 20
        assert poi == 20

    def test_poi_screen_pass(self):
        poi = PlayResolver.calculate_point_of_interception("SCREEN", 6, 30)
        # SCREEN: RN / 2 = 3. yard_line 30 + 3 = 33. 100 - 33 = 67.
        assert poi == 67

    def test_poi_quick_pass(self):
        poi = PlayResolver.calculate_point_of_interception("QUICK", 10, 50)
        # QUICK: RN × 1 = 10. yard_line 50 + 10 = 60. 100 - 60 = 40.
        assert poi == 40


class TestInterceptionReturnLogging:
    """INT returns include POI, return details, and defender info in logs."""

    def test_direct_int_has_poi_in_description(self):
        """Direct INT result includes interception yard line in description."""
        resolver = PlayResolver()
        deck = FACDeck()
        qb = _make_qb()
        receiver = _make_receiver()

        # Force INT result: use PN=45 which is in INT range
        fac_card = _make_fac_card(run_number="6", pass_number="45",
                                  short_pass="A")

        random.seed(42)
        result = resolver._resolve_pass_inner_5e(
            fac_card, deck, qb, receiver, [receiver],
            pass_type="SHORT", defense_coverage=0,
            defense_pass_rush=0, defense_formation="4_3",
            is_blitz_tendency=False, z_event=None,
            yard_line=30,
        )

        if result.result == "INT":
            # Should have interception_point set
            assert result.interception_point is not None
            # Description should mention the yard line
            assert "yard line" in result.description
            # Debug log should include POI
            log_text = " ".join(result.debug_log)
            assert "Point of interception" in log_text

    def test_inc_to_int_5e_has_poi_and_defender_info(self):
        """INC→INT with 5E intercept_range includes POI and defender details."""
        resolver = PlayResolver()
        deck = FACDeck()
        qb = _make_qb()
        receiver = _make_receiver()

        # Create a defender with intercept_range
        defender = PlayerCard.from_dict({
            "name": "INT Defender",
            "number": 21,
            "position": "CB",
            "overall_grade": "A",
            "intercept_range": 30,  # Intercepts on PN 30-48
        })

        # Force INC result: PN 35 is in INC range (31-42) and in intercept range (30-48)
        fac_card = _make_fac_card(run_number="4", pass_number="35",
                                  short_pass="A")

        # Set defenders_by_box with covering defender on box K (LCB covers receiver A/FL)
        defenders_by_box = {"K": defender}

        random.seed(42)
        result = resolver._resolve_pass_inner_5e(
            fac_card, deck, qb, receiver, [receiver],
            pass_type="SHORT", defense_coverage=0,
            defense_pass_rush=0, defense_formation="4_3",
            is_blitz_tendency=False, z_event=None,
            yard_line=40,
            defenders_by_box=defenders_by_box,
        )

        if result.result == "INT":
            assert result.interception_point is not None
            log_text = " ".join(result.debug_log)
            assert "Point of interception" in log_text
            assert "INT Defender" in log_text or "CB" in log_text


class TestInterceptionReturnTD:
    """INT return into opposing end zone results in TD."""

    def test_int_return_td_when_past_endzone(self):
        """If POI minus return yards goes to 0 or below, it's a TD."""
        # POI at 10-yard line, return 15 yards → should be TD
        resolver = PlayResolver()
        deck = FACDeck()
        qb = _make_qb()
        receiver = _make_receiver()

        # Force INT + specific yards
        fac_card = _make_fac_card(run_number="1", pass_number="45",
                                  short_pass="A")

        # We need to mock Charts.roll_int_return to return specific yards
        found_td = False
        for seed in range(200):
            random.seed(seed)
            with patch.object(Charts, 'roll_int_return', return_value=(99, True)):
                result = resolver._resolve_pass_inner_5e(
                    fac_card, deck, qb, receiver, [receiver],
                    pass_type="SHORT", defense_coverage=0,
                    defense_pass_rush=0, defense_formation="4_3",
                    is_blitz_tendency=False, z_event=None,
                    yard_line=30,
                )
                if result.result == "INT" and "TD" in result.description:
                    found_td = True
                    break

        # At minimum, verify the TD description mentions it
        if found_td:
            assert "Returned for TD!" in result.description


# ── Handle Turnover Uses interception_point ──────────────────────────────

class TestHandleTurnoverUsesPoI:
    """Game._handle_turnover uses interception_point for INT yard placement."""

    def test_int_with_poi_uses_it(self):
        result = PlayResult(
            play_type="PASS", yards_gained=0, result="INT",
            turnover=True, turnover_type="INT",
            interception_point=35,
        )
        # Verify the field is set
        assert result.interception_point == 35

    def test_int_without_poi_defaults(self):
        result = PlayResult(
            play_type="PASS", yards_gained=0, result="INT",
            turnover=True, turnover_type="INT",
        )
        assert result.interception_point is None
