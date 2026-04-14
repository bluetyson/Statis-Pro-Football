"""Tests for blitz pass rush procedure and receiver formation ordering.

Covers:
  - Pass rush uses actual OL pass-blocking / DL pass-rush sums (not team rating)
  - Blitz forces pass rush on Short/Long passes
  - Blitzing players add PR=2 each to DL sum
  - Receiver list built in formation order [FL, LE, RE, BK1, BK2]
  - RBs included at BK1/BK2 positions
  - Depth WRs (e.g. Curtis Samuel) excluded from on-field list
"""

import json
import random
import pytest

from engine.team import Team
from engine.game import Game
from engine.play_resolver import PlayResolver, PlayResult
from engine.fac_deck import FACDeck, FACCard
from engine.player_card import PlayerCard, PassRushRanges
from engine.solitaire import PlayCall
from engine.card_generator import CardGenerator
from engine.play_types import DefensivePlay


# ── Helpers ──────────────────────────────────────────────────────────────

def _load_team(abbrev: str) -> Team:
    path = f"engine/data/2025_5e/{abbrev}.json"
    with open(path) as f:
        return Team.from_dict(json.load(f))


def _make_ol(name: str, pass_block: int = 2, run_block: int = 2,
             position: str = "OL") -> PlayerCard:
    card = PlayerCard(player_name=name, position=position)
    card.pass_block_rating = pass_block
    card.run_block_rating = run_block
    return card


def _make_dl(name: str, pass_rush: int = 2, position: str = "DE") -> PlayerCard:
    card = PlayerCard(player_name=name, position=position)
    card.pass_rush_rating = pass_rush
    card.defender_letter = ""
    return card


def _make_lb(name: str, pass_rush: int = 1, position: str = "LB") -> PlayerCard:
    card = PlayerCard(player_name=name, position=position)
    card.pass_rush_rating = pass_rush
    return card


# ── Receiver Formation Ordering Tests ────────────────────────────────────

class TestReceiverFormationOrdering:
    """Verify _get_all_receivers builds list in formation position order."""

    def setup_method(self):
        self.buf = _load_team("BUF")
        self.kc = _load_team("KC")

    def test_receivers_include_rbs_at_bk_positions(self):
        """BK1/BK2 positions should be filled by RBs, not WR/TE depth."""
        game = Game(self.kc, self.buf)
        # BUF is away team — set possession to away so BUF is offense
        game.state.possession = "away"
        receivers = game._get_all_receivers()
        # Should have 5 receivers: FL, LE, RE, BK1, BK2
        assert len(receivers) == 5
        # BK1 and BK2 (indices 3 and 4) should be RBs
        bk1 = receivers[3]
        bk2 = receivers[4]
        assert bk1.position == "RB", f"BK1 should be RB, got {bk1.position} ({bk1.player_name})"
        assert bk2.position == "RB", f"BK2 should be RB, got {bk2.position} ({bk2.player_name})"

    def test_receivers_exclude_depth_wrs(self):
        """Curtis Samuel (depth WR) should NOT be in the 5-receiver on-field list."""
        game = Game(self.kc, self.buf)
        game.state.possession = "away"
        receivers = game._get_all_receivers()
        names = [r.player_name for r in receivers]
        # Curtis Samuel is a depth WR on BUF, should not be on field
        assert "Curtis Samuel" not in names, (
            f"Curtis Samuel (depth WR) should not be on field. Receivers: {names}"
        )

    def test_receivers_have_wr_at_fl_and_le(self):
        """FL and LE positions should have WRs (for BUF: Shakir at FL, Diggs at LE)."""
        game = Game(self.kc, self.buf)
        game.state.possession = "away"
        receivers = game._get_all_receivers()
        fl = receivers[0]  # FL = index 0
        le = receivers[1]  # LE = index 1
        assert fl.position == "WR", f"FL should be WR, got {fl.position} ({fl.player_name})"
        assert le.position == "WR", f"LE should be WR, got {le.position} ({le.player_name})"

    def test_receivers_have_te_at_re(self):
        """RE position should have a TE (for BUF: Kincaid)."""
        game = Game(self.kc, self.buf)
        game.state.possession = "away"
        receivers = game._get_all_receivers()
        re = receivers[2]  # RE = index 2
        assert re.position == "TE", f"RE should be TE, got {re.position} ({re.player_name})"

    def test_buf_formation_matches_team_card(self):
        """BUF on-field receivers should match the team card layout."""
        game = Game(self.kc, self.buf)
        game.state.possession = "away"
        receivers = game._get_all_receivers()
        names = [r.player_name for r in receivers]
        # Expected: FL=Shakir, LE=Diggs, RE=Kincaid, BK1=Cook, BK2=Davis
        assert "Khalil Shakir" in names, f"Shakir should be on field: {names}"
        assert "Stefon Diggs" in names, f"Diggs should be on field: {names}"
        assert "Dalton Kincaid" in names, f"Kincaid should be on field: {names}"
        assert "James Cook" in names, f"Cook should be on field: {names}"
        assert "Ray Davis" in names, f"Davis should be on field: {names}"

    def test_no_duplicate_receivers(self):
        """Each receiver should appear exactly once in the list."""
        game = Game(self.kc, self.buf)
        game.state.possession = "away"
        receivers = game._get_all_receivers()
        names = [r.player_name for r in receivers]
        assert len(names) == len(set(names)), f"Duplicate receivers found: {names}"

    def test_all_32_teams_have_valid_receivers(self):
        """Every team should produce a valid receivers list with RBs."""
        teams = [
            "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
            "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
            "LAC", "LAR", "LV", "MIA", "MIN", "NE", "NO", "NYG",
            "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WSH",
        ]
        for abbrev in teams:
            team1 = _load_team(abbrev)
            team2 = _load_team("KC" if abbrev != "KC" else "BUF")
            game = Game(team1, team2)
            receivers = game._get_all_receivers()
            assert len(receivers) >= 3, (
                f"{abbrev} has only {len(receivers)} receivers"
            )
            # Should not have any duplicate names
            names = [r.player_name for r in receivers]
            assert len(names) == len(set(names)), (
                f"{abbrev} has duplicate receivers: {names}"
            )


# ── Pass Rush Procedure Tests ────────────────────────────────────────────

class TestPassRushWithOLDLSums:
    """Verify pass rush uses actual OL/DL individual ratings."""

    def test_pass_rush_modifier_uses_sums(self):
        """calculate_pass_rush_modifier should compute (def_pr - off_pb) * 2."""
        resolver = PlayResolver()
        # DL total = 8, OL total = 10 → (8-10)*2 = -4 (offense wins)
        assert resolver.calculate_pass_rush_modifier(8, 10) == -4
        # DL total = 12, OL total = 10 → (12-10)*2 = 4 (defense wins)
        assert resolver.calculate_pass_rush_modifier(12, 10) == 4
        # Equal → 0
        assert resolver.calculate_pass_rush_modifier(10, 10) == 0

    def test_blitz_players_add_pr_2_each(self):
        """Per rules: blitzing players have PR=2 regardless of printed value."""
        resolver = PlayResolver()
        assert resolver.get_blitz_pass_rush_value() == 2

    def test_pass_rush_with_actual_ol_dl_sums_in_debug_log(self):
        """When pass rush triggers, debug log should show actual OL/DL sums."""
        resolver = PlayResolver()
        gen = CardGenerator(seed=42)
        deck = FACDeck(seed=42)

        qb = gen.generate_qb_card_authentic(
            "Test QB", "TST", 1, 0.65, 7.5, 0.03, 0.06, "B"
        )
        wr = gen.generate_wr_card_authentic(
            "Test WR", "TST", 80, 0.70, 12.0, "B", receiver_letter="A"
        )

        # Create a FAC card that targets P.Rush
        found_pr_card = None
        test_deck = FACDeck(seed=99)
        for _ in range(200):
            card = test_deck.draw()
            if not card.is_z_card:
                target = card.get_receiver_target("SHORT")
                if target == "P.Rush":
                    found_pr_card = card
                    break
        if found_pr_card is None:
            pytest.skip("No P.Rush FAC card found in deck")

        result = resolver._resolve_pass_inner_5e(
            found_pr_card, deck, qb, wr, [wr],
            pass_type="SHORT", defense_coverage=0,
            defense_pass_rush=8,  # DL sum
            offense_pass_block=10,  # OL sum
            defense_formation="4_3",
            is_blitz_tendency=False, z_event=None,
            yard_line=30,
        )
        log_text = " ".join(result.debug_log)
        assert "DL pass rush sum=8" in log_text
        assert "OL pass block sum=10" in log_text

    def test_blitz_forces_pass_rush_on_short_pass(self):
        """Blitz + short pass = forced pass rush per 5E rules."""
        resolver = PlayResolver()
        gen = CardGenerator(seed=42)
        deck = FACDeck(seed=42)

        qb = gen.generate_qb_card_authentic(
            "Test QB", "TST", 1, 0.65, 7.5, 0.03, 0.06, "B"
        )
        wr = gen.generate_wr_card_authentic(
            "Test WR", "TST", 80, 0.70, 12.0, "B", receiver_letter="A"
        )

        # Use any non-Z card — blitz forces pass rush regardless of FAC target
        fac_card = deck.draw_non_z()

        result = resolver.resolve_pass_5e(
            fac_card, deck, qb, wr, [wr],
            pass_type="SHORT",
            defense_pass_rush=6,  # DL sum with blitz PR=2 additions
            offense_pass_block=10,  # OL sum
            defensive_play_5e=DefensivePlay.BLITZ,
        )
        log_text = " ".join(result.debug_log)
        assert "Pass rush FORCED by Blitz" in log_text

    def test_blitz_forces_pass_rush_on_long_pass(self):
        """Blitz + long pass = forced pass rush per 5E rules."""
        resolver = PlayResolver()
        gen = CardGenerator(seed=42)
        deck = FACDeck(seed=42)

        qb = gen.generate_qb_card_authentic(
            "Test QB", "TST", 1, 0.65, 7.5, 0.03, 0.06, "B"
        )
        wr = gen.generate_wr_card_authentic(
            "Test WR", "TST", 80, 0.70, 12.0, "B", receiver_letter="A"
        )

        fac_card = deck.draw_non_z()

        result = resolver.resolve_pass_5e(
            fac_card, deck, qb, wr, [wr],
            pass_type="LONG",
            defense_pass_rush=6,
            offense_pass_block=10,
            defensive_play_5e=DefensivePlay.BLITZ,
        )
        log_text = " ".join(result.debug_log)
        assert "Pass rush FORCED by Blitz" in log_text

    def test_blitz_does_not_force_pass_rush_on_quick_pass(self):
        """Blitz + quick pass = no forced pass rush; uses normal resolution."""
        resolver = PlayResolver()
        gen = CardGenerator(seed=42)
        deck = FACDeck(seed=42)

        qb = gen.generate_qb_card_authentic(
            "Test QB", "TST", 1, 0.65, 7.5, 0.03, 0.06, "B"
        )
        wr = gen.generate_wr_card_authentic(
            "Test WR", "TST", 80, 0.70, 12.0, "B", receiver_letter="A"
        )

        fac_card = deck.draw_non_z()

        result = resolver.resolve_pass_5e(
            fac_card, deck, qb, wr, [wr],
            pass_type="QUICK",
            defense_pass_rush=6,
            offense_pass_block=10,
            defensive_play_5e=DefensivePlay.BLITZ,
        )
        log_text = " ".join(result.debug_log)
        # Should NOT say "forced by Blitz" for quick passes
        assert "Pass rush FORCED by Blitz" not in log_text


class TestBlitzPassRushIntegration:
    """Integration test: full game blitz with actual OL/DL ratings."""

    def setup_method(self):
        self.buf = _load_team("BUF")
        self.kc = _load_team("KC")

    def test_execute_pass_with_blitz_calculates_ol_dl_sums(self):
        """_execute_pass_5e should compute OL/DL sums from player ratings."""
        game = Game(self.kc, self.buf)
        # KC is home, BUF is away — set possession to home so KC is offense
        game.state.possession = "home"
        game.state.yard_line = 30

        fac_card = game.deck.draw()

        play_call = PlayCall(
            play_type="SHORT_PASS",
            formation="SHOTGUN",
            direction="LEFT",
            reasoning="test",
        )

        result = game._execute_pass_5e(
            fac_card, play_call,
            defensive_play_5e=DefensivePlay.BLITZ,
        )
        assert isinstance(result, PlayResult)
        assert result.play_type == "PASS"
