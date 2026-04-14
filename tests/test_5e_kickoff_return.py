"""Tests for 5E authentic kickoff and return resolution.

Covers:
  - Team kickoff table lookup (TB, TB(-X), return start, OB, special/RN12)
  - KR selection via FAC Pass Number
  - KR return table lookup (normal and breakaway columns)
  - Fumble on return (f suffix) with team card recovery
  - Kick return TD
  - Default table generation when no explicit card data
  - Punt return 5E table lookup
  - _parse_return_value edge cases
  - _kickoff_yard_line helper
"""

import random
import pytest
from engine.play_resolver import PlayResolver, PlayResult
from engine.fac_deck import FACDeck, FACCard
from engine.team import Team


# ── Helpers ─────────────────────────────────────────────────────────────


def _make_fac_card(card_number=1, run_number="6", pass_number="24", **kwargs):
    """Create a FACCard with controllable RN and PN."""
    return FACCard(
        card_number=card_number,
        run_number=run_number,
        pass_number=pass_number,
        sweep_left=kwargs.get("sweep_left", "A"),
        inside_left=kwargs.get("inside_left", "C"),
        sweep_right=kwargs.get("sweep_right", "E"),
        inside_right=kwargs.get("inside_right", "D"),
        end_run=kwargs.get("end_run", "OK"),
        quick_kick=kwargs.get("quick_kick", "A"),
        short_pass=kwargs.get("short_pass", "B"),
        long_pass=kwargs.get("long_pass", "C"),
        screen=kwargs.get("screen", "Com"),
        z_result=kwargs.get("z_result", ""),
        solo=kwargs.get("solo", ""),
    )


class FixedDeck:
    """A FACDeck stub that returns a pre-set sequence of cards."""

    def __init__(self, cards):
        self._cards = list(cards)
        self._idx = 0

    def draw(self):
        card = self._cards[self._idx % len(self._cards)]
        self._idx += 1
        return card

    def draw_non_z(self):
        return self.draw()


# ── CHI-style test data (from 2011 CHICAGO team card) ──────────────

CHI_KICKOFF_TABLE = [
    "TB", "TB", "TB", "TB", "TB",   # RN 1-5
    "TB(-5)",                         # RN 6
    "TB(-3)", "TB(-3)",               # RN 7-8
    "1", "1",                         # RN 9-10
    "3",                              # RN 11
    "special",                        # RN 12
]

CHI_KR_RETURNERS = [
    {"name": "D. Hester", "pn_min": 1, "pn_max": 33},
    {"name": "J. Knox", "pn_min": 34, "pn_max": 48},
]

CHI_KR_TABLE = [
    # KR1: D. Hester
    [
        ["*35", "TD"],    # RN 1: breakaway
        [32, 73],         # RN 2
        [27, 35],         # RN 3
        [26, 35],         # RN 4
        [23, 35],         # RN 5
        [22, 35],         # RN 6
        [21, 35],         # RN 7
        [20, 35],         # RN 8
        [17, 35],         # RN 9
        [15, 35],         # RN 10
        [13, 35],         # RN 11
        ["12f", 35],      # RN 12: fumble
    ],
    # KR2: J. Knox
    [
        ["*42", 56],      # RN 1: breakaway
        [39, 53],         # RN 2
        [33, 42],         # RN 3
        [31, 42],         # RN 4
        [29, 42],         # RN 5
        [28, 42],         # RN 6
        [27, 42],         # RN 7
        [25, 42],         # RN 8
        [21, 42],         # RN 9
        [19, 42],         # RN 10
        [17, 42],         # RN 11
        ["15f", 42],      # RN 12: fumble
    ],
]


# ── _parse_return_value tests ────────────────────────────────────────

class TestParseReturnValue:
    def test_td_value(self):
        r = PlayResolver._parse_return_value("TD")
        assert r["is_td"] is True
        assert r["yard_line"] == 0

    def test_normal_int(self):
        r = PlayResolver._parse_return_value(27)
        assert r["yard_line"] == 27
        assert r["is_td"] is False
        assert r["is_fumble"] is False
        assert r["is_breakaway"] is False

    def test_fumble_suffix(self):
        r = PlayResolver._parse_return_value("12f")
        assert r["yard_line"] == 12
        assert r["is_fumble"] is True
        assert r["is_breakaway"] is False

    def test_breakaway_prefix(self):
        r = PlayResolver._parse_return_value("*35")
        assert r["yard_line"] == 35
        assert r["is_breakaway"] is True
        assert r["is_fumble"] is False

    def test_breakaway_fumble(self):
        r = PlayResolver._parse_return_value("*8f")
        assert r["yard_line"] == 8
        assert r["is_breakaway"] is True
        assert r["is_fumble"] is True

    def test_string_number(self):
        r = PlayResolver._parse_return_value("42")
        assert r["yard_line"] == 42


# ── Kickoff Table Lookup ──────────────────────────────────────────────

class TestKickoffTableLookup:
    """Test the kickoff table portion of resolve_kickoff_5e."""

    def test_touchback_rn1(self):
        """RN 1 on CHI table → TB at 20."""
        resolver = PlayResolver()
        # Card with RN=1, PN doesn't matter for TB
        cards = [_make_fac_card(run_number="1", pass_number="10")]
        deck = FixedDeck(cards)
        result = resolver.resolve_kickoff_5e(
            deck, CHI_KICKOFF_TABLE, CHI_KR_RETURNERS, CHI_KR_TABLE,
        )
        assert result.result == "TOUCHBACK"
        assert result.yards_gained == 20
        log_text = " ".join(result.debug_log)
        assert "[KO]" in log_text
        assert "RN=1" in log_text
        assert "Touchback" in log_text

    def test_touchback_with_modifier_rn6(self):
        """RN 6 → TB(-5) = touchback at 15 (20 - 5)."""
        resolver = PlayResolver()
        cards = [_make_fac_card(run_number="6")]
        deck = FixedDeck(cards)
        result = resolver.resolve_kickoff_5e(
            deck, CHI_KICKOFF_TABLE, CHI_KR_RETURNERS, CHI_KR_TABLE,
        )
        assert result.result == "TOUCHBACK"
        assert result.yards_gained == 15
        log_text = " ".join(result.debug_log)
        assert "adj -5" in log_text

    def test_touchback_minus_3_rn7(self):
        """RN 7 → TB(-3) = touchback at 17 (20 - 3)."""
        resolver = PlayResolver()
        cards = [_make_fac_card(run_number="7")]
        deck = FixedDeck(cards)
        result = resolver.resolve_kickoff_5e(
            deck, CHI_KICKOFF_TABLE, CHI_KR_RETURNERS, CHI_KR_TABLE,
        )
        assert result.result == "TOUCHBACK"
        assert result.yards_gained == 17

    def test_return_starts_at_1_rn9(self):
        """RN 9 → return starts at 1-yard line."""
        resolver = PlayResolver()
        # Need 3 FAC cards: kickoff (RN=9), KR selection (PN), return (RN)
        cards = [
            _make_fac_card(run_number="9", pass_number="10"),   # kickoff
            _make_fac_card(run_number="5", pass_number="10"),   # KR selection PN=10 → KR1
            _make_fac_card(run_number="5", pass_number="20"),   # return RN=5
        ]
        deck = FixedDeck(cards)
        result = resolver.resolve_kickoff_5e(
            deck, CHI_KICKOFF_TABLE, CHI_KR_RETURNERS, CHI_KR_TABLE,
        )
        assert result.result == "RETURN"
        log_text = " ".join(result.debug_log)
        assert "Return starts at 1" in log_text

    def test_return_at_3_rn11(self):
        """RN 11 → return starts at 3-yard line."""
        resolver = PlayResolver()
        cards = [
            _make_fac_card(run_number="11"),  # kickoff
            _make_fac_card(pass_number="10"),  # KR selection
            _make_fac_card(run_number="5"),    # return
        ]
        deck = FixedDeck(cards)
        result = resolver.resolve_kickoff_5e(
            deck, CHI_KICKOFF_TABLE, CHI_KR_RETURNERS, CHI_KR_TABLE,
        )
        assert result.result == "RETURN"
        log_text = " ".join(result.debug_log)
        assert "Return starts at 3" in log_text

    def test_special_rn12_sub1_starts_at_gl(self):
        """RN 12 → special: draw new RN. Sub-RN 1-4 → goal line."""
        resolver = PlayResolver()
        cards = [
            _make_fac_card(run_number="12"),   # kickoff → special
            _make_fac_card(run_number="3"),     # sub-table RN=3 → GL
            _make_fac_card(pass_number="10"),   # KR selection
            _make_fac_card(run_number="5"),     # return RN
        ]
        deck = FixedDeck(cards)
        result = resolver.resolve_kickoff_5e(
            deck, CHI_KICKOFF_TABLE, CHI_KR_RETURNERS, CHI_KR_TABLE,
        )
        assert result.result == "RETURN"
        log_text = " ".join(result.debug_log)
        assert "Special" in log_text
        assert "goal line" in log_text

    def test_special_rn12_sub7_uses_sub_rn_as_yard(self):
        """RN 12 → special: sub-RN 5-9 → use sub-RN as yard line."""
        resolver = PlayResolver()
        cards = [
            _make_fac_card(run_number="12"),   # kickoff → special
            _make_fac_card(run_number="7"),     # sub-table RN=7 → return at 7
            _make_fac_card(pass_number="10"),   # KR selection
            _make_fac_card(run_number="4"),     # return RN
        ]
        deck = FixedDeck(cards)
        result = resolver.resolve_kickoff_5e(
            deck, CHI_KICKOFF_TABLE, CHI_KR_RETURNERS, CHI_KR_TABLE,
        )
        assert result.result == "RETURN"
        log_text = " ".join(result.debug_log)
        assert "return starts at 7" in log_text

    def test_special_rn12_sub10_oob(self):
        """RN 12 → special: sub-RN 10-12 → out of bounds."""
        resolver = PlayResolver()
        cards = [
            _make_fac_card(run_number="12"),   # kickoff → special
            _make_fac_card(run_number="11"),    # sub-table RN=11 → OB
        ]
        deck = FixedDeck(cards)
        result = resolver.resolve_kickoff_5e(
            deck, CHI_KICKOFF_TABLE, CHI_KR_RETURNERS, CHI_KR_TABLE,
        )
        assert result.result == "OOB"
        assert result.yards_gained == 40
        log_text = " ".join(result.debug_log)
        assert "out of bounds" in log_text


# ── KR Selection via PN ────────────────────────────────────────────────

class TestKRSelection:
    """Test that FAC Pass Number selects the correct KR."""

    def test_pn_in_kr1_range(self):
        """PN 10 → KR1 D. Hester (range 1-33)."""
        resolver = PlayResolver()
        cards = [
            _make_fac_card(run_number="9"),     # kickoff → return at 1
            _make_fac_card(pass_number="10"),    # KR selection: PN=10 → KR1
            _make_fac_card(run_number="5"),      # return
        ]
        deck = FixedDeck(cards)
        result = resolver.resolve_kickoff_5e(
            deck, CHI_KICKOFF_TABLE, CHI_KR_RETURNERS, CHI_KR_TABLE,
        )
        log_text = " ".join(result.debug_log)
        assert "KR1 D. Hester" in log_text
        assert "range 1-33" in log_text

    def test_pn_in_kr2_range(self):
        """PN 40 → KR2 J. Knox (range 34-48)."""
        resolver = PlayResolver()
        cards = [
            _make_fac_card(run_number="9"),     # kickoff → return at 1
            _make_fac_card(pass_number="40"),    # KR selection: PN=40 → KR2
            _make_fac_card(run_number="5"),      # return
        ]
        deck = FixedDeck(cards)
        result = resolver.resolve_kickoff_5e(
            deck, CHI_KICKOFF_TABLE, CHI_KR_RETURNERS, CHI_KR_TABLE,
        )
        log_text = " ".join(result.debug_log)
        assert "KR2 J. Knox" in log_text
        assert "range 34-48" in log_text


# ── KR Return Table Lookup ─────────────────────────────────────────────

class TestKRReturnTable:
    """Test the return table lookup."""

    def test_normal_return_rn5(self):
        """RN 5 on KR1 Hester → 23-yard line (normal column)."""
        resolver = PlayResolver()
        cards = [
            _make_fac_card(run_number="9"),     # kickoff → return at 1
            _make_fac_card(pass_number="10"),    # KR1
            _make_fac_card(run_number="5"),      # return RN=5 → row 5: [23, 35]
        ]
        deck = FixedDeck(cards)
        result = resolver.resolve_kickoff_5e(
            deck, CHI_KICKOFF_TABLE, CHI_KR_RETURNERS, CHI_KR_TABLE,
        )
        assert result.result == "RETURN"
        assert result.yards_gained == 23
        log_text = " ".join(result.debug_log)
        assert "Normal column: 23" in log_text
        assert "D. Hester" in log_text

    def test_breakaway_rn1_td(self):
        """RN 1 on KR1 Hester → breakaway column → TD."""
        resolver = PlayResolver()
        cards = [
            _make_fac_card(run_number="9"),     # kickoff → return at 1
            _make_fac_card(pass_number="10"),    # KR1 Hester
            _make_fac_card(run_number="1"),      # return RN=1 → breakaway: TD
        ]
        deck = FixedDeck(cards)
        result = resolver.resolve_kickoff_5e(
            deck, CHI_KICKOFF_TABLE, CHI_KR_RETURNERS, CHI_KR_TABLE,
        )
        assert result.result == "KR_TD"
        assert result.is_touchdown is True
        log_text = " ".join(result.debug_log)
        assert "BREAKAWAY" in log_text
        assert "TOUCHDOWN" in log_text

    def test_breakaway_rn1_knox(self):
        """RN 1 on KR2 Knox → breakaway column → 56-yard line."""
        resolver = PlayResolver()
        cards = [
            _make_fac_card(run_number="9"),     # kickoff → return at 1
            _make_fac_card(pass_number="40"),    # KR2 Knox
            _make_fac_card(run_number="1"),      # return RN=1 → breakaway: 56
        ]
        deck = FixedDeck(cards)
        result = resolver.resolve_kickoff_5e(
            deck, CHI_KICKOFF_TABLE, CHI_KR_RETURNERS, CHI_KR_TABLE,
        )
        assert result.result == "RETURN"
        assert result.yards_gained == 56
        log_text = " ".join(result.debug_log)
        assert "BREAKAWAY" in log_text

    def test_fumble_rn12_hester(self):
        """RN 12 on KR1 Hester → 12f → fumble at the 12-yard line."""
        resolver = PlayResolver()
        cards = [
            _make_fac_card(run_number="9"),      # kickoff → return at 1
            _make_fac_card(pass_number="10"),     # KR1 Hester
            _make_fac_card(run_number="12"),      # return RN=12 → 12f (fumble)
            _make_fac_card(pass_number="10"),     # fumble recovery FAC
        ]
        deck = FixedDeck(cards)
        result = resolver.resolve_kickoff_5e(
            deck, CHI_KICKOFF_TABLE, CHI_KR_RETURNERS, CHI_KR_TABLE,
            fumbles_lost_max=25,
        )
        assert result.result == "FUMBLE"
        assert result.yards_gained == 12
        log_text = " ".join(result.debug_log)
        assert "FUMBLE" in log_text
        assert "D. Hester" in log_text
        assert "fumbles_lost_max=25" in log_text

    def test_fumble_rn12_knox(self):
        """RN 12 on KR2 Knox → 15f → fumble at the 15-yard line."""
        resolver = PlayResolver()
        cards = [
            _make_fac_card(run_number="9"),      # kickoff → return at 1
            _make_fac_card(pass_number="40"),     # KR2 Knox
            _make_fac_card(run_number="12"),      # return RN=12 → 15f (fumble)
            _make_fac_card(pass_number="10"),     # fumble recovery FAC
        ]
        deck = FixedDeck(cards)
        result = resolver.resolve_kickoff_5e(
            deck, CHI_KICKOFF_TABLE, CHI_KR_RETURNERS, CHI_KR_TABLE,
            fumbles_lost_max=25,
        )
        assert result.result == "FUMBLE"
        assert result.yards_gained == 15


# ── Team Default Tables ──────────────────────────────────────────────

class TestTeamDefaultTables:
    """Test that Team generates sensible defaults when no explicit card data."""

    def test_default_kickoff_table_has_12_entries(self):
        assert len(Team.DEFAULT_KICKOFF_TABLE) == 12

    def test_default_kr_return_table_has_12_rows(self):
        assert len(Team.DEFAULT_KR_RETURN_TABLE) == 12

    def test_default_pr_return_table_has_12_rows(self):
        assert len(Team.DEFAULT_PR_RETURN_TABLE) == 12

    def test_get_kickoff_table_returns_default(self):
        team = Team(abbreviation="TST", city="Test", name="Team",
                    conference="NFC", division="North")
        table = team.get_kickoff_table()
        assert len(table) == 12
        assert table[0] == "TB"

    def test_get_kickoff_table_returns_custom(self):
        team = Team(abbreviation="TST", city="Test", name="Team",
                    conference="NFC", division="North")
        team.kickoff_table = CHI_KICKOFF_TABLE
        assert team.get_kickoff_table() == CHI_KICKOFF_TABLE

    def test_get_kickoff_returners_auto_selects(self):
        """With no explicit KR data, auto-selects from roster."""
        team = Team.from_dict({
            "abbreviation": "TST", "city": "Test", "name": "Team",
            "conference": "NFC", "division": "North",
            "players": [
                {"name": "Fast Guy", "number": 1, "position": "WR",
                 "overall_grade": "A"},
                {"name": "Other Guy", "number": 2, "position": "RB",
                 "overall_grade": "B"},
            ],
        })
        krs = team.get_kickoff_returners()
        assert len(krs) >= 1
        assert krs[0]["pn_min"] == 1
        # First player should be one of the two
        assert krs[0]["name"] in ("Fast Guy", "Other Guy")

    def test_get_kickoff_returners_uses_explicit(self):
        team = Team(abbreviation="TST", city="Test", name="Team",
                    conference="NFC", division="North")
        team.kickoff_returners = CHI_KR_RETURNERS
        assert team.get_kickoff_returners() == CHI_KR_RETURNERS


# ── Team to_dict / from_dict round-trip ──────────────────────────────

class TestTeamCardRoundTrip:
    def test_kickoff_table_round_trip(self):
        team = Team(abbreviation="CHI", city="Chicago", name="Bears",
                    conference="NFC", division="North")
        team.kickoff_table = CHI_KICKOFF_TABLE
        team.kickoff_returners = CHI_KR_RETURNERS
        team.kickoff_return_table = CHI_KR_TABLE

        d = team.to_dict()
        assert d["kickoff_table"] == CHI_KICKOFF_TABLE
        assert d["kickoff_returners"] == CHI_KR_RETURNERS
        assert d["kickoff_return_table"] == CHI_KR_TABLE

        team2 = Team.from_dict(d)
        assert team2.kickoff_table == CHI_KICKOFF_TABLE
        assert team2.kickoff_returners == CHI_KR_RETURNERS
        assert team2.kickoff_return_table == CHI_KR_TABLE


# ── Full Integration: resolve_kickoff_5e logging ──────────────────────

class TestKickoffReturnLogging:
    """Full logging chain for a kickoff return."""

    def test_full_return_logging(self):
        """A return play should have complete [KO] and [KR] logging."""
        resolver = PlayResolver()
        cards = [
            _make_fac_card(run_number="9", pass_number="10"),   # kickoff
            _make_fac_card(run_number="5", pass_number="10"),   # KR selection
            _make_fac_card(run_number="5", pass_number="20"),   # return
        ]
        deck = FixedDeck(cards)
        result = resolver.resolve_kickoff_5e(
            deck, CHI_KICKOFF_TABLE, CHI_KR_RETURNERS, CHI_KR_TABLE,
        )
        log_text = " ".join(result.debug_log)

        # Kickoff table logging
        assert "[KO] FAC Card #1: RN=9" in log_text
        assert "Kickoff table RN 9" in log_text
        assert "Return starts at 1" in log_text

        # KR selection logging
        assert "[KR]" in log_text
        assert "KR1 D. Hester" in log_text
        assert "range 1-33" in log_text

        # Return table logging
        assert "return RN=5" in log_text
        assert "Normal column" in log_text

    def test_oob_result_has_direct_kickoff_table(self):
        """Make an OB kickoff table and verify result."""
        resolver = PlayResolver()
        oob_table = ["OB"] * 12
        cards = [_make_fac_card(run_number="1")]
        deck = FixedDeck(cards)
        result = resolver.resolve_kickoff_5e(
            deck, oob_table, CHI_KR_RETURNERS, CHI_KR_TABLE,
        )
        assert result.result == "OOB"
        assert result.yards_gained == 40


# ── Punt Return 5E ────────────────────────────────────────────────────

class TestPuntReturn5E:
    """Test resolve_punt_return_5e."""

    def test_normal_return(self):
        resolver = PlayResolver()
        pr_returners = [{"name": "D. Hester", "pn_min": 1, "pn_max": 48}]
        pr_table = [Team.DEFAULT_PR_RETURN_TABLE]
        cards = [
            _make_fac_card(pass_number="10"),   # PR selection
            _make_fac_card(run_number="5"),      # return RN=5
        ]
        deck = FixedDeck(cards)
        info = resolver.resolve_punt_return_5e(
            deck, pr_returners, pr_table,
            punt_distance=45, yard_line=30,
        )
        assert info["returner_name"] == "D. Hester"
        assert info["is_fair_catch"] is False
        assert len(info["log_entries"]) >= 2

    def test_breakaway_rn1(self):
        resolver = PlayResolver()
        pr_returners = [{"name": "Tyreek Hill", "pn_min": 1, "pn_max": 48}]
        pr_table = [Team.DEFAULT_PR_RETURN_TABLE]
        cards = [
            _make_fac_card(pass_number="10"),   # PR selection
            _make_fac_card(run_number="1"),      # RN=1 → breakaway
        ]
        deck = FixedDeck(cards)
        info = resolver.resolve_punt_return_5e(
            deck, pr_returners, pr_table,
            punt_distance=45, yard_line=30,
        )
        log_text = " ".join(info["log_entries"])
        assert "BREAKAWAY" in log_text


# ── OB table entry ──────────────────────────────────────────────────

class TestDirectOBEntry:
    """Kickoff tables can have direct OB entries (not just via special)."""

    def test_direct_ob_entry(self):
        resolver = PlayResolver()
        table = ["OB", "TB", "TB", "TB", "TB", "TB",
                 "TB", "TB", "TB", "TB", "TB", "TB"]
        cards = [_make_fac_card(run_number="1")]
        deck = FixedDeck(cards)
        result = resolver.resolve_kickoff_5e(
            deck, table, CHI_KR_RETURNERS, CHI_KR_TABLE,
        )
        assert result.result == "OOB"
        assert result.yards_gained == 40
