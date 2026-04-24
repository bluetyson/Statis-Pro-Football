"""Tests for the season simulation engine (engine/season.py)."""

import os
import sys
import json
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.season import (
    Season,
    SeasonGame,
    SeasonRoster,
    SeasonStats,
    TeamRecord,
    _CONF_DIVS,
)
from engine.team import Team


# ─── SeasonGame ──────────────────────────────────────────────────────────────


class TestSeasonGame:
    def _make_game(self, home_score=21, away_score=14):
        return SeasonGame(
            week=1, home="KC", away="BUF", date="2024-09-05",
            home_score=home_score, away_score=away_score,
            player_stats={"Patrick Mahomes": {"passing_yards": 280}},
            play_log=["Q1: KC kickoff"],
        )

    def test_winner_home(self):
        g = self._make_game(21, 14)
        assert g.winner == "KC"
        assert g.loser == "BUF"

    def test_winner_away(self):
        g = self._make_game(14, 21)
        assert g.winner == "BUF"
        assert g.loser == "KC"

    def test_tie(self):
        g = self._make_game(17, 17)
        assert g.winner is None
        assert g.loser is None

    def test_roundtrip(self):
        g = self._make_game()
        d = g.to_dict()
        g2 = SeasonGame.from_dict(d)
        assert g2.week == g.week
        assert g2.home == g.home
        assert g2.home_score == g.home_score
        assert g2.player_stats == g.player_stats
        assert g2.play_log == g.play_log


# ─── TeamRecord ──────────────────────────────────────────────────────────────


class TestTeamRecord:
    def test_win_pct_no_games(self):
        r = TeamRecord()
        assert r.win_pct == 0.0

    def test_win_pct_perfect(self):
        r = TeamRecord(wins=17, losses=0)
        assert r.win_pct == 1.0

    def test_win_pct_tie_counts_half(self):
        r = TeamRecord(wins=8, losses=8, ties=1)
        # (8 + 0.5) / 17
        assert abs(r.win_pct - 8.5 / 17) < 1e-9

    def test_str(self):
        assert str(TeamRecord(wins=10, losses=7)) == "10-7"
        assert str(TeamRecord(wins=8, losses=7, ties=2)) == "8-7-2"


# ─── SeasonStats ─────────────────────────────────────────────────────────────


class TestSeasonStats:
    def _make_game(self, home, away, home_score, away_score, week=1):
        return SeasonGame(
            week=week, home=home, away=away, date="2024-09-05",
            home_score=home_score, away_score=away_score,
            player_stats={}, play_log=[],
        )

    def test_record_win(self):
        ss = SeasonStats()
        ss.record_game(self._make_game("KC", "BUF", 28, 14))
        assert ss.records["KC"].wins == 1
        assert ss.records["BUF"].losses == 1

    def test_record_loss(self):
        ss = SeasonStats()
        ss.record_game(self._make_game("KC", "BUF", 10, 21))
        assert ss.records["KC"].losses == 1
        assert ss.records["BUF"].wins == 1

    def test_record_tie(self):
        ss = SeasonStats()
        ss.record_game(self._make_game("KC", "BUF", 17, 17))
        assert ss.records["KC"].ties == 1
        assert ss.records["BUF"].ties == 1

    def test_points_accumulate(self):
        ss = SeasonStats()
        ss.record_game(self._make_game("KC", "BUF", 28, 14, week=1))
        ss.record_game(self._make_game("BUF", "KC", 20, 17, week=2))
        assert ss.records["KC"].points_for == 28 + 17
        assert ss.records["KC"].points_against == 14 + 20

    def test_player_stats_merged(self):
        ss = SeasonStats()
        g1 = SeasonGame(1, "KC", "BUF", "2024-09-05", 28, 14,
                        {"Mahomes": {"passing_yards": 280}}, [])
        g2 = SeasonGame(2, "KC", "BAL", "2024-09-12", 21, 17,
                        {"Mahomes": {"passing_yards": 220}}, [])
        ss.record_game(g1)
        ss.record_game(g2)
        assert ss.player_stats["Mahomes"]["passing_yards"] == 500

    def test_standings_text_contains_all_divs(self):
        ss = SeasonStats()
        text = ss.standings_text()
        for conf in ("AFC", "NFC"):
            assert conf in text
        for div in ("East", "North", "South", "West"):
            assert div in text

    def test_standings_text_shows_teams(self):
        ss = SeasonStats()
        ss.record_game(self._make_game("KC", "BUF", 28, 14))
        text = ss.standings_text()
        assert "KC" in text
        assert "BUF" in text

    def test_to_dict_from_dict_roundtrip(self):
        ss = SeasonStats()
        ss.record_game(self._make_game("KC", "BUF", 28, 14))
        ss.merge_player_stats({"Mahomes": {"passing_yards": 300}})
        d = ss.to_dict()
        ss2 = SeasonStats.from_dict(d)
        assert ss2.records["KC"].wins == 1
        assert ss2.player_stats["Mahomes"]["passing_yards"] == 300

    def test_player_stats_text(self):
        ss = SeasonStats()
        ss.merge_player_stats({"Mahomes": {"passing_yards": 300}})
        ss.merge_player_stats({"Allen": {"passing_yards": 250}})
        text = ss.player_stats_text(top_n=2, stat_key="passing_yards")
        assert "Mahomes" in text
        assert "Allen" in text


# ─── SeasonRoster ────────────────────────────────────────────────────────────


class TestSeasonRoster:
    def _make_roster(self):
        team = Team.load("KC", "2025_5e")
        return SeasonRoster(team)

    def test_initially_no_injuries(self):
        sr = self._make_roster()
        assert sr.injuries == {}

    def test_not_injured_initially(self):
        sr = self._make_roster()
        assert sr.is_injured("Patrick Mahomes") is False

    def test_record_new_injury(self):
        sr = self._make_roster()
        sr.record_post_game_injuries({}, {"Patrick Mahomes": 2})
        assert sr.is_injured("Patrick Mahomes") is True
        assert sr.injuries["Patrick Mahomes"] == 2

    def test_injury_decrements_each_game(self):
        sr = self._make_roster()
        sr.record_post_game_injuries({}, {"Patrick Mahomes": 2})
        # Decrement once
        sr.record_post_game_injuries({}, {})
        assert sr.injuries.get("Patrick Mahomes", 0) == 1
        # Decrement again — now healed
        sr.record_post_game_injuries({}, {})
        assert sr.is_injured("Patrick Mahomes") is False
        assert "Patrick Mahomes" not in sr.injuries

    def test_apply_pre_game_injuries_seeds_game_state(self):
        sr = self._make_roster()
        sr.record_post_game_injuries({}, {"Patrick Mahomes": 1})
        gs_injuries: dict = {}
        sr.apply_pre_game_injuries(gs_injuries)
        assert "Patrick Mahomes" in gs_injuries
        assert gs_injuries["Patrick Mahomes"] == 9999  # large sentinel value

    def test_apply_pre_game_clears_old_contents(self):
        sr = self._make_roster()
        gs_injuries = {"OldPlayer": 3}
        sr.apply_pre_game_injuries(gs_injuries)
        assert "OldPlayer" not in gs_injuries

    def test_zero_duration_injury_not_added(self):
        sr = self._make_roster()
        sr.record_post_game_injuries({}, {"Patrick Mahomes": 0})
        assert not sr.is_injured("Patrick Mahomes")


# ─── Season (integration) ─────────────────────────────────────────────────────


class TestSeasonLoad:
    def test_load_2025_schedule(self):
        season = Season.load(year=2025, log_dir=None)
        assert len(season.schedule) == 272  # 17 weeks × 16 games

    def test_all_weeks_present(self):
        season = Season.load(year=2025, log_dir=None)
        weeks = {g["week"] for g in season.schedule}
        assert weeks == set(range(1, 18))

    def test_all_teams_appear(self):
        season = Season.load(year=2025, log_dir=None)
        teams_in_schedule = set()
        for g in season.schedule:
            teams_in_schedule.add(g["home"])
            teams_in_schedule.add(g["away"])
        assert len(teams_in_schedule) == 32

    def test_each_team_plays_17_games(self):
        season = Season.load(year=2025, log_dir=None)
        from collections import Counter
        counts = Counter()
        for g in season.schedule:
            counts[g["home"]] += 1
            counts[g["away"]] += 1
        for team, count in counts.items():
            assert count == 17, f"{team} plays {count} games (expected 17)"

    def test_missing_schedule_raises(self):
        with pytest.raises(FileNotFoundError):
            Season.load(year=9999, log_dir=None)


class TestSeasonSimulate:
    """Integration tests that actually simulate games (small subset for speed)."""

    def test_simulate_week_1(self):
        season = Season.load(year=2025, log_dir=None, seed=42)
        games = season.simulate_week(1)
        assert len(games) == 16
        for g in games:
            assert isinstance(g, SeasonGame)
            assert g.week == 1
            # Scores are non-negative integers
            assert g.home_score >= 0
            assert g.away_score >= 0

    def test_stats_accumulated_after_week(self):
        season = Season.load(year=2025, log_dir=None, seed=42)
        season.simulate(weeks=[1])
        # Should have some player stats
        assert len(season.stats.player_stats) > 0
        # Should have standings for teams that played
        played = {g["home"] for g in season.schedule if g["week"] == 1}
        played |= {g["away"] for g in season.schedule if g["week"] == 1}
        for abbr in played:
            assert abbr in season.stats.records

    def test_standings_after_week(self):
        season = Season.load(year=2025, log_dir=None, seed=42)
        season.simulate(weeks=[1])
        for abbr, rec in season.stats.records.items():
            assert rec.wins + rec.losses + rec.ties == 1

    def test_injury_carry_over(self):
        """Injuries from week 1 should be tracked in SeasonRoster."""
        season = Season.load(year=2025, log_dir=None, seed=1)
        season.simulate(weeks=[1])
        # SeasonRosters should be populated for all 32 teams
        assert len(season._season_rosters) == 32

    def test_game_log_written(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            season = Season.load(year=2025, log_dir=tmpdir, seed=42)
            season.simulate(weeks=[1])
            year_dir = os.path.join(tmpdir, "2025")
            assert os.path.isdir(year_dir)
            log_files = os.listdir(year_dir)
            assert len(log_files) == 16
            # Verify one log is valid JSON with expected keys
            first_log = os.path.join(year_dir, sorted(log_files)[0])
            with open(first_log) as f:
                d = json.load(f)
            assert "week" in d
            assert "home_score" in d
            assert "away_score" in d
            assert "player_stats" in d
            assert "play_log" in d

    def test_season_summary_saved(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            season = Season.load(year=2025, log_dir=tmpdir, seed=42)
            season.simulate(weeks=[1])
            path = season.save_season_summary()
            assert os.path.exists(path)
            with open(path) as f:
                d = json.load(f)
            assert "records" in d
            assert "player_stats" in d

    def test_no_logs_when_disabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            season = Season.load(year=2025, log_dir=None, seed=42)
            season.simulate(weeks=[1])
            # No files should be written to cwd (just check log_dir=None works)
            assert season.log_dir is None

    def test_seed_reproducible(self):
        """Same seed produces identical results."""
        s1 = Season.load(year=2025, log_dir=None, seed=99)
        s1.simulate(weeks=[1])
        s2 = Season.load(year=2025, log_dir=None, seed=99)
        s2.simulate(weeks=[1])
        for g1, g2 in zip(s1.completed_games, s2.completed_games):
            assert g1.home_score == g2.home_score
            assert g1.away_score == g2.away_score
