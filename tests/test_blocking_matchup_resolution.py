"""Tests for 5E blocking matchup resolution.

Covers the 3 blocking matchup categories:
  1. OFFENSE ONLY (OL_ONLY / TWO_OL): Add offensive blocking values
  2. DEFENSE ONLY (SINGLE_DEF_BOX / TWO_DEF_BOX): Subtract defender TV
  3. CONTEST (BK_VS_BOX / OL_VS_BOX): Compare BV vs TV

Plus:
  - Empty box rule (+2)
  - Inside run max loss (-3)
  - classify_blocking_matchup / extract_ol_abbreviations / get_player_blocking_value
"""

import random
import pytest
from engine.play_resolver import PlayResolver, PlayResult
from engine.player_card import PlayerCard, ThreeValueRow
from engine.fac_deck import FACDeck, FACCard


# ── Helper factories ──────────────────────────────────────────────────

def _make_rusher(name="Test RB", rushing_yards=4):
    """Create a PlayerCard with 12-row rushing data, all returning rushing_yards."""
    card = PlayerCard(player_name=name, team="TST", position="RB", number=22)
    card.rushing = [
        ThreeValueRow(v1=rushing_yards, v2=rushing_yards + 5, v3=rushing_yards + 15)
        for _ in range(12)
    ]
    card.blocks = 1
    return card


def _make_ol(name, position, run_block_rating=2):
    """Create an OL PlayerCard with run_block_rating."""
    card = PlayerCard(player_name=name, team="TST", position=position, number=60)
    card.run_block_rating = run_block_rating
    card.blocks = 0
    return card


def _make_te(name, blocks=3):
    """Create a TE PlayerCard with blocks value."""
    card = PlayerCard(player_name=name, team="TST", position="TE", number=80)
    card.blocks = blocks
    return card


def _make_rb(name, blocks=1):
    """Create an RB PlayerCard used as blocking back."""
    card = PlayerCard(player_name=name, team="TST", position="RB", number=33)
    card.blocks = blocks
    return card


def _make_defender(name, tackle_rating=2, position="DL"):
    """Create a defensive PlayerCard with tackle_rating."""
    card = PlayerCard(player_name=name, team="TST", position=position, number=90)
    card.tackle_rating = tackle_rating
    return card


def _make_fac_card(matchup_il="LG", run_number=6):
    """Create a minimal FACCard with a specific inside_left matchup."""
    return FACCard(
        card_number=1,
        run_number=str(run_number),
        pass_number="24",
        sweep_left=matchup_il,
        inside_left=matchup_il,
        sweep_right=matchup_il,
        inside_right=matchup_il,
        end_run="OK",
        quick_kick="Orig",
        short_pass="Orig",
        long_pass="Orig",
        screen="Com",
        z_result="",
        solo="",
    )


# ── classify_blocking_matchup tests ──────────────────────────────────

class TestClassifyBlockingMatchup:
    def test_single_ol(self):
        assert PlayResolver.classify_blocking_matchup("LG") == "OL_ONLY"

    def test_single_bk(self):
        assert PlayResolver.classify_blocking_matchup("BK") == "OL_ONLY"

    def test_two_ol(self):
        assert PlayResolver.classify_blocking_matchup("CN + LG") == "TWO_OL"

    def test_single_def_box(self):
        assert PlayResolver.classify_blocking_matchup("A") == "SINGLE_DEF_BOX"

    def test_single_def_box_c(self):
        assert PlayResolver.classify_blocking_matchup("C") == "SINGLE_DEF_BOX"

    def test_two_def_box(self):
        assert PlayResolver.classify_blocking_matchup("A + F") == "TWO_DEF_BOX"

    def test_bk_vs_box(self):
        assert PlayResolver.classify_blocking_matchup("BK vs G") == "BK_VS_BOX"

    def test_ol_vs_box(self):
        assert PlayResolver.classify_blocking_matchup("LG vs B") == "OL_VS_BOX"

    def test_break(self):
        assert PlayResolver.classify_blocking_matchup("Break") == "BREAK"


# ── extract_ol_abbreviations tests ───────────────────────────────────

class TestExtractOLAbbreviations:
    def test_single_ol(self):
        assert PlayResolver.extract_ol_abbreviations("LG") == ["LG"]

    def test_single_bk(self):
        assert PlayResolver.extract_ol_abbreviations("BK") == ["BK"]

    def test_two_ol(self):
        assert PlayResolver.extract_ol_abbreviations("CN + LG") == ["CN", "LG"]

    def test_vs_matchup(self):
        assert PlayResolver.extract_ol_abbreviations("LG vs B") == ["LG"]

    def test_bk_vs_matchup(self):
        assert PlayResolver.extract_ol_abbreviations("BK vs G") == ["BK"]

    def test_single_def_box(self):
        assert PlayResolver.extract_ol_abbreviations("A") == []

    def test_two_def_boxes(self):
        assert PlayResolver.extract_ol_abbreviations("A + F") == []


# ── get_player_blocking_value tests ──────────────────────────────────

class TestGetPlayerBlockingValue:
    def test_ol_uses_run_block_rating(self):
        ol = _make_ol("LG Test", "LG", run_block_rating=3)
        assert PlayResolver.get_player_blocking_value(ol) == 3

    def test_rb_uses_blocks(self):
        rb = _make_rb("RB Test", blocks=2)
        assert PlayResolver.get_player_blocking_value(rb) == 2

    def test_te_uses_blocks(self):
        te = _make_te("TE Test", blocks=4)
        assert PlayResolver.get_player_blocking_value(te) == 4


# ── Offense Only (OL_ONLY / TWO_OL) ─────────────────────────────────

class TestOffenseOnlyMatchup:
    """Offense-only matchups ADD the blocker's BV to rushing yards."""

    def test_ol_only_adds_bv(self):
        """Single OL matchup 'LG' adds LG's blocking value."""
        resolver = PlayResolver()
        rusher = _make_rusher(rushing_yards=3)
        fac = _make_fac_card("LG", run_number=6)
        deck = FACDeck(seed=42)

        lg = _make_ol("Left Guard", "LG", run_block_rating=3)
        offensive_blockers = {"LG": lg}

        result = resolver.resolve_run_5e(
            fac, deck, rusher, "IL",
            offensive_blockers_by_pos=offensive_blockers,
        )
        # base_yards=3 (from row), + BV=3 = 6
        assert result.yards_gained == 6
        assert any("Offense only" in e for e in result.debug_log)

    def test_bk_only_adds_bv(self):
        """Single BK matchup adds blocking back's value."""
        resolver = PlayResolver()
        rusher = _make_rusher(rushing_yards=4)
        fac = _make_fac_card("BK", run_number=6)
        deck = FACDeck(seed=42)

        bk = _make_rb("Blocking Back", blocks=2)
        offensive_blockers = {"BK": bk}

        result = resolver.resolve_run_5e(
            fac, deck, rusher, "IL",
            offensive_blockers_by_pos=offensive_blockers,
        )
        # base_yards=4 + BV=2 = 6
        assert result.yards_gained == 6

    def test_two_ol_adds_both_bv(self):
        """TWO_OL matchup 'CN + LG' adds both blocking values."""
        resolver = PlayResolver()
        rusher = _make_rusher(rushing_yards=2)
        fac = _make_fac_card("CN + LG", run_number=6)
        deck = FACDeck(seed=42)

        cn = _make_ol("Center", "C", run_block_rating=2)
        lg = _make_ol("Left Guard", "LG", run_block_rating=3)
        offensive_blockers = {"CN": cn, "LG": lg}

        result = resolver.resolve_run_5e(
            fac, deck, rusher, "IL",
            offensive_blockers_by_pos=offensive_blockers,
        )
        # base_yards=2 + CN(2) + LG(3) = 7
        assert result.yards_gained == 7

    def test_ol_only_no_personnel_zero_bv(self):
        """OL_ONLY without offensive_blockers_by_pos adds 0."""
        resolver = PlayResolver()
        rusher = _make_rusher(rushing_yards=5)
        fac = _make_fac_card("LG", run_number=6)
        deck = FACDeck(seed=42)

        result = resolver.resolve_run_5e(
            fac, deck, rusher, "IL",
        )
        # base_yards=5 + BV=0 (no blockers provided)
        assert result.yards_gained == 5


# ── Defense Only (SINGLE_DEF_BOX / TWO_DEF_BOX) ─────────────────────

class TestDefenseOnlyMatchup:
    """Defense-only matchups SUBTRACT defender TV from rushing yards."""

    def test_single_def_box_subtracts_tv(self):
        """Single defense box 'A' subtracts that defender's TV."""
        resolver = PlayResolver()
        rusher = _make_rusher(rushing_yards=5)
        fac = _make_fac_card("A", run_number=6)
        deck = FACDeck(seed=42)

        defender_a = _make_defender("DE Guy", tackle_rating=3)
        defenders = {"A": defender_a}

        result = resolver.resolve_run_5e(
            fac, deck, rusher, "IL",
            defenders_by_box=defenders,
        )
        # base_yards=5 - TV=3 = 2
        assert result.yards_gained == 2
        assert any("Defense box" in e for e in result.debug_log)

    def test_two_def_box_subtracts_both_tvs(self):
        """TWO_DEF_BOX 'C + H' subtracts sum of both TVs."""
        resolver = PlayResolver()
        rusher = _make_rusher(rushing_yards=5)
        fac = _make_fac_card("C + H", run_number=6)
        deck = FACDeck(seed=42)

        defender_c = _make_defender("NT", tackle_rating=2, position="DL")
        defender_h = _make_defender("MLB", tackle_rating=4, position="LB")
        defenders = {"C": defender_c, "H": defender_h}

        result = resolver.resolve_run_5e(
            fac, deck, rusher, "IL",
            defenders_by_box=defenders,
        )
        # base_yards=5 - (TV=2 + TV=4) = 5 - 6 = -1
        # But inside run max loss = -3, so -1 is fine
        assert result.yards_gained == -1

    def test_two_def_box_inside_run_max_loss(self):
        """TWO_DEF_BOX with high TVs respects inside run max loss of -3."""
        resolver = PlayResolver()
        rusher = _make_rusher(rushing_yards=2)
        fac = _make_fac_card("C + H", run_number=6)
        deck = FACDeck(seed=42)

        defender_c = _make_defender("NT", tackle_rating=4)
        defender_h = _make_defender("MLB", tackle_rating=5)
        defenders = {"C": defender_c, "H": defender_h}

        result = resolver.resolve_run_5e(
            fac, deck, rusher, "IL",
            defenders_by_box=defenders,
        )
        # base_yards=2 - (4+5) = -7 → capped at -3 for inside run
        assert result.yards_gained == -3

    def test_single_def_box_empty_plus_2(self):
        """Empty single defense box gives +2."""
        resolver = PlayResolver()
        rusher = _make_rusher(rushing_yards=4)
        fac = _make_fac_card("A", run_number=6)
        deck = FACDeck(seed=42)

        # No defender in box A
        defenders = {"B": _make_defender("Other", tackle_rating=3)}

        result = resolver.resolve_run_5e(
            fac, deck, rusher, "IL",
            defenders_by_box=defenders,
        )
        # base_yards=4 + 2 (empty box) = 6
        assert result.yards_gained == 6

    def test_two_def_box_both_empty_plus_2(self):
        """Both defense boxes empty gives +2."""
        resolver = PlayResolver()
        rusher = _make_rusher(rushing_yards=3)
        fac = _make_fac_card("A + F", run_number=6)
        deck = FACDeck(seed=42)

        # Neither A nor F is occupied
        defenders = {"B": _make_defender("Other", tackle_rating=3)}

        result = resolver.resolve_run_5e(
            fac, deck, rusher, "IL",
            defenders_by_box=defenders,
        )
        # base_yards=3 + 2 (empty box) = 5
        assert result.yards_gained == 5

    def test_two_def_box_one_empty_subtracts_occupied(self):
        """TWO_DEF_BOX with one empty box subtracts only the occupied TV."""
        resolver = PlayResolver()
        rusher = _make_rusher(rushing_yards=6)
        fac = _make_fac_card("A + F", run_number=6)
        deck = FACDeck(seed=42)

        # Only A is occupied, F is empty
        defenders = {"A": _make_defender("DE", tackle_rating=3)}

        result = resolver.resolve_run_5e(
            fac, deck, rusher, "IL",
            defenders_by_box=defenders,
        )
        # base_yards=6 - TV=3 (only occupied box counts) = 3
        assert result.yards_gained == 3


# ── Contest (BK_VS_BOX / OL_VS_BOX) ─────────────────────────────────

class TestContestMatchup:
    """Contest matchups compare total BV vs total TV."""

    def test_offense_wins_adds_bv(self):
        """When BV > TV, add BV to yardage."""
        resolver = PlayResolver()
        rusher = _make_rusher(rushing_yards=4)
        fac = _make_fac_card("LG vs B", run_number=6)
        deck = FACDeck(seed=42)

        lg = _make_ol("Left Guard", "LG", run_block_rating=4)
        defender_b = _make_defender("LDT", tackle_rating=2)

        result = resolver.resolve_run_5e(
            fac, deck, rusher, "IL",
            defenders_by_box={"B": defender_b},
            offensive_blockers_by_pos={"LG": lg},
        )
        # BV=4 > TV=2 → base=4 + 4 = 8
        assert result.yards_gained == 8
        assert any("offense wins" in e for e in result.debug_log)

    def test_defense_wins_subtracts_tv(self):
        """When TV > BV, subtract TV from yardage."""
        resolver = PlayResolver()
        rusher = _make_rusher(rushing_yards=5)
        fac = _make_fac_card("LG vs B", run_number=6)
        deck = FACDeck(seed=42)

        lg = _make_ol("Left Guard", "LG", run_block_rating=1)
        defender_b = _make_defender("LDT", tackle_rating=4)

        result = resolver.resolve_run_5e(
            fac, deck, rusher, "IL",
            defenders_by_box={"B": defender_b},
            offensive_blockers_by_pos={"LG": lg},
        )
        # TV=4 > BV=1 → base=5 - 4 = 1
        assert result.yards_gained == 1
        assert any("defense wins" in e for e in result.debug_log)

    def test_tie_no_modification(self):
        """When BV == TV, no modification."""
        resolver = PlayResolver()
        rusher = _make_rusher(rushing_yards=4)
        fac = _make_fac_card("LG vs B", run_number=6)
        deck = FACDeck(seed=42)

        lg = _make_ol("Left Guard", "LG", run_block_rating=3)
        defender_b = _make_defender("LDT", tackle_rating=3)

        result = resolver.resolve_run_5e(
            fac, deck, rusher, "IL",
            defenders_by_box={"B": defender_b},
            offensive_blockers_by_pos={"LG": lg},
        )
        # BV=3 == TV=3 → base=4 + 0 = 4
        assert result.yards_gained == 4
        assert any("tie" in e for e in result.debug_log)

    def test_bk_vs_box_offense_wins(self):
        """BK vs box: BK BV > defender TV → add BV."""
        resolver = PlayResolver()
        rusher = _make_rusher(rushing_yards=3)
        fac = _make_fac_card("BK vs G", run_number=6)
        deck = FACDeck(seed=42)

        bk = _make_rb("Blocking Back", blocks=3)
        defender_g = _make_defender("LILB", tackle_rating=2, position="LB")

        result = resolver.resolve_run_5e(
            fac, deck, rusher, "IL",
            defenders_by_box={"G": defender_g},
            offensive_blockers_by_pos={"BK": bk},
        )
        # BV=3 > TV=2 → base=3 + 3 = 6
        assert result.yards_gained == 6

    def test_contest_empty_box_plus_2(self):
        """Contest with empty defense box gives +2."""
        resolver = PlayResolver()
        rusher = _make_rusher(rushing_yards=4)
        fac = _make_fac_card("LG vs B", run_number=6)
        deck = FACDeck(seed=42)

        lg = _make_ol("Left Guard", "LG", run_block_rating=2)
        # Box B is empty
        defenders = {"A": _make_defender("Other", tackle_rating=3)}

        result = resolver.resolve_run_5e(
            fac, deck, rusher, "IL",
            defenders_by_box=defenders,
            offensive_blockers_by_pos={"LG": lg},
        )
        # Empty box → base=4 + 2 = 6
        assert result.yards_gained == 6
        assert any("empty box" in e.lower() for e in result.debug_log)

    def test_contest_defense_wins_inside_run_cap(self):
        """Contest defense wins, but inside run max loss caps at -3."""
        resolver = PlayResolver()
        rusher = _make_rusher(rushing_yards=1)
        fac = _make_fac_card("LG vs B", run_number=6)
        deck = FACDeck(seed=42)

        lg = _make_ol("Left Guard", "LG", run_block_rating=0)
        defender_b = _make_defender("LDT", tackle_rating=6)

        result = resolver.resolve_run_5e(
            fac, deck, rusher, "IL",
            defenders_by_box={"B": defender_b},
            offensive_blockers_by_pos={"LG": lg},
        )
        # TV=6 > BV=0 → base=1 - 6 = -5 → capped at -3
        assert result.yards_gained == -3

    def test_sweep_no_loss_cap(self):
        """On sweep, defense wins with no max loss cap."""
        resolver = PlayResolver()
        rusher = _make_rusher(rushing_yards=1)
        fac = _make_fac_card("LG vs B", run_number=6)
        deck = FACDeck(seed=42)

        lg = _make_ol("Left Guard", "LG", run_block_rating=0)
        defender_b = _make_defender("LDT", tackle_rating=6)

        result = resolver.resolve_run_5e(
            fac, deck, rusher, "SL",
            defenders_by_box={"B": defender_b},
            offensive_blockers_by_pos={"LG": lg},
        )
        # TV=6 > BV=0 → base=1 - 6 = -5 (no cap on sweep)
        assert result.yards_gained == -5
