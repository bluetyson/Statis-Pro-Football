"""Season simulation engine for Statis Pro Football.

Provides:
  - ``SeasonGame``    — result of one simulated game stored in the season log.
  - ``SeasonRoster``  — per-team injury tracker that persists across games.
  - ``SeasonStats``   — accumulates player stats and standings across a season.
  - ``Season``        — orchestrates loading, simulating, and logging a full season.

Usage (minimal)::

    season = Season.load(year=2025)
    season.simulate(progress=True)
    print(season.stats.standings_text())

Season logs are written to ``season_logs/<year>/week<NN>_<AWAY>_at_<HOME>.json``
relative to the current working directory (or the ``log_dir`` argument).
"""

from __future__ import annotations

import json
import os
import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .game import Game
from .team import Team


# ── SeasonGame ────────────────────────────────────────────────────────────────


@dataclass
class SeasonGame:
    """Summary of a single completed game stored in the season log."""

    week: int
    home: str
    away: str
    date: str
    home_score: int
    away_score: int
    player_stats: Dict[str, Dict[str, Any]]
    play_log: List[str]

    @property
    def winner(self) -> Optional[str]:
        if self.home_score > self.away_score:
            return self.home
        if self.away_score > self.home_score:
            return self.away
        return None  # tie

    @property
    def loser(self) -> Optional[str]:
        if self.home_score > self.away_score:
            return self.away
        if self.away_score > self.home_score:
            return self.home
        return None

    def to_dict(self) -> dict:
        return {
            "week": self.week,
            "home": self.home,
            "away": self.away,
            "date": self.date,
            "home_score": self.home_score,
            "away_score": self.away_score,
            "player_stats": self.player_stats,
            "play_log": self.play_log,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SeasonGame":
        return cls(
            week=d["week"],
            home=d["home"],
            away=d["away"],
            date=d.get("date", ""),
            home_score=d["home_score"],
            away_score=d["away_score"],
            player_stats=d.get("player_stats", {}),
            play_log=d.get("play_log", []),
        )


# ── SeasonRoster ──────────────────────────────────────────────────────────────


class SeasonRoster:
    """Wraps a team's :class:`~engine.team.Team` and carries multi-game injury status.

    Each game, the season simulation calls :meth:`apply_pre_game_injuries` to
    mark players that are still out, then :meth:`record_post_game_injuries`
    after the game to persist new injuries discovered during play.

    Injury durations are stored in *games* (not plays).  Each game a player
    misses decrements their remaining games by one.  When it reaches zero they
    are healthy.
    """

    def __init__(self, team: Team) -> None:
        self.team = team
        # {player_name: games_remaining} — tracks season-level injury carry-over
        self._injuries: Dict[str, int] = {}

    # ── Public API ────────────────────────────────────────────────────────

    @property
    def injuries(self) -> Dict[str, int]:
        """Read-only view of current season injury ledger."""
        return dict(self._injuries)

    def is_injured(self, player_name: str) -> bool:
        return self._injuries.get(player_name, 0) > 0

    def apply_pre_game_injuries(self, game_state_injuries: Dict[str, int]) -> None:
        """Seed the game's injury dict with players still out from prior games.

        This is called before a new ``Game`` is constructed so the in-game
        injury tracker starts with carried-over injuries.
        """
        game_state_injuries.clear()
        for name, games_remaining in self._injuries.items():
            if games_remaining > 0:
                # Represent as a large play count so the in-game counter
                # keeps them out for the entire game.
                game_state_injuries[name] = 9999

    def record_post_game_injuries(
        self, game_state_injuries: Dict[str, int], new_injuries: Dict[str, int]
    ) -> None:
        """Update the season injury ledger after a game completes.

        Parameters
        ----------
        game_state_injuries:
            The ``GameState.injuries`` dict after the game (players still out
            at game end — already carried-over from the season ledger).
        new_injuries:
            {player_name: game_duration} for players newly injured *this* game
            (duration in games, not plays).  Typically derived from
            ``result.injury_duration`` values collected during simulation.
        """
        # Decrement carried-over injuries (they sat out this game)
        to_remove = []
        for name in list(self._injuries):
            self._injuries[name] -= 1
            if self._injuries[name] <= 0:
                to_remove.append(name)
        for name in to_remove:
            del self._injuries[name]

        # Add brand-new injuries
        for name, duration in new_injuries.items():
            if duration > 0:
                current = self._injuries.get(name, 0)
                self._injuries[name] = max(current, duration)


# ── SeasonStats ───────────────────────────────────────────────────────────────

# Division memberships (used for standings display).
_CONF_DIVS: Dict[str, Dict[str, List[str]]] = {
    "AFC": {
        "East":  ["BUF", "MIA", "NE",  "NYJ"],
        "North": ["BAL", "CIN", "CLE", "PIT"],
        "South": ["HOU", "IND", "JAX", "TEN"],
        "West":  ["DEN", "KC",  "LAC", "LV"],
    },
    "NFC": {
        "East":  ["DAL", "NYG", "PHI", "WSH"],
        "North": ["CHI", "DET", "GB",  "MIN"],
        "South": ["ATL", "CAR", "NO",  "TB"],
        "West":  ["ARI", "LAR", "SEA", "SF"],
    },
}


@dataclass
class TeamRecord:
    wins: int = 0
    losses: int = 0
    ties: int = 0
    points_for: int = 0
    points_against: int = 0

    @property
    def win_pct(self) -> float:
        g = self.wins + self.losses + self.ties
        if g == 0:
            return 0.0
        return (self.wins + 0.5 * self.ties) / g

    def __str__(self) -> str:
        return f"{self.wins}-{self.losses}" + (f"-{self.ties}" if self.ties else "")


class SeasonStats:
    """Accumulates standings and player stats across all completed games.

    Standings are updated by calling :meth:`record_game`.  Player totals are
    merged via :meth:`merge_player_stats`.
    """

    def __init__(self) -> None:
        self.records: Dict[str, TeamRecord] = {}
        self.player_stats: Dict[str, Dict[str, Any]] = {}
        self.weekly_scores: List[Dict[str, Any]] = []

    # ── Recording ─────────────────────────────────────────────────────────

    def record_game(self, game: SeasonGame) -> None:
        """Update standings and player stats from a completed game."""
        home = game.home
        away = game.away
        for abbr in (home, away):
            if abbr not in self.records:
                self.records[abbr] = TeamRecord()

        home_rec = self.records[home]
        away_rec = self.records[away]
        home_rec.points_for += game.home_score
        home_rec.points_against += game.away_score
        away_rec.points_for += game.away_score
        away_rec.points_against += game.home_score

        if game.home_score > game.away_score:
            home_rec.wins += 1
            away_rec.losses += 1
        elif game.away_score > game.home_score:
            away_rec.wins += 1
            home_rec.losses += 1
        else:
            home_rec.ties += 1
            away_rec.ties += 1

        self.merge_player_stats(game.player_stats)

        self.weekly_scores.append({
            "week": game.week,
            "home": home,
            "away": away,
            "home_score": game.home_score,
            "away_score": game.away_score,
        })

    def merge_player_stats(self, game_stats: Dict[str, Dict[str, Any]]) -> None:
        """Add per-game player stats to season totals."""
        for player, stats in game_stats.items():
            if player not in self.player_stats:
                self.player_stats[player] = {}
            season = self.player_stats[player]
            for stat, value in stats.items():
                if isinstance(value, (int, float)):
                    season[stat] = season.get(stat, 0) + value

    # ── Display ───────────────────────────────────────────────────────────

    def standings_text(self) -> str:
        """Return a multi-line standings string (conference/division format)."""
        lines: List[str] = []
        for conf in ("AFC", "NFC"):
            lines.append("")
            lines.append(f"{'─'*50}")
            lines.append(f" {conf}")
            lines.append(f"{'─'*50}")
            for div_name, div_teams in _CONF_DIVS[conf].items():
                lines.append(f"  {div_name}")
                ranked = sorted(
                    div_teams,
                    key=lambda t: -(self.records.get(t, TeamRecord()).win_pct),
                )
                for abbr in ranked:
                    rec = self.records.get(abbr, TeamRecord())
                    pf = rec.points_for
                    pa = rec.points_against
                    lines.append(f"    {abbr:<4s}  {rec!s:<8s}  PF {pf:>4d}  PA {pa:>4d}")
        return "\n".join(lines)

    def player_stats_text(
        self,
        top_n: int = 10,
        stat_key: str = "passing_yards",
        label: str = "Passing Yards",
    ) -> str:
        """Return top-N players for a given stat as a formatted string."""
        ranked = sorted(
            self.player_stats.items(),
            key=lambda kv: -kv[1].get(stat_key, 0),
        )[:top_n]
        lines = [f"\n{'─'*50}", f" Top {top_n} — {label}", "─"*50]
        for i, (name, stats) in enumerate(ranked, 1):
            val = stats.get(stat_key, 0)
            if isinstance(val, float):
                val_str = f"{val:.1f}"
            else:
                val_str = str(val)
            lines.append(f"  {i:>2d}. {name:<26s} {val_str}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "records": {
                abbr: {
                    "wins": r.wins,
                    "losses": r.losses,
                    "ties": r.ties,
                    "points_for": r.points_for,
                    "points_against": r.points_against,
                }
                for abbr, r in self.records.items()
            },
            "player_stats": self.player_stats,
            "weekly_scores": self.weekly_scores,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SeasonStats":
        obj = cls()
        for abbr, rd in d.get("records", {}).items():
            obj.records[abbr] = TeamRecord(
                wins=rd.get("wins", 0),
                losses=rd.get("losses", 0),
                ties=rd.get("ties", 0),
                points_for=rd.get("points_for", 0),
                points_against=rd.get("points_against", 0),
            )
        obj.player_stats = d.get("player_stats", {})
        obj.weekly_scores = d.get("weekly_scores", [])
        return obj


# ── Season ────────────────────────────────────────────────────────────────────


class Season:
    """Orchestrates a complete NFL season simulation.

    Parameters
    ----------
    schedule:
        List of game entries ``{"week": int, "home": str, "away": str, "date": str}``.
    data_season:
        The Statis-Pro data season key (e.g. ``"2025_5e"``) used to load team files.
    year:
        Calendar year label (used for log directory naming).
    log_dir:
        Root directory for game logs.  Season logs are saved under
        ``<log_dir>/<year>/``.  Pass ``None`` to suppress all file I/O.
    seed:
        Optional master RNG seed for reproducible seasons.
    """

    _SCHEDULE_DIR = os.path.join(os.path.dirname(__file__), "data", "schedules")

    def __init__(
        self,
        schedule: List[Dict[str, Any]],
        data_season: str = "2025_5e",
        year: int = 2025,
        log_dir: Optional[str] = "season_logs",
        seed: Optional[int] = None,
    ) -> None:
        self.schedule = schedule
        self.data_season = data_season
        self.year = year
        self.log_dir = log_dir
        self.seed = seed

        self.stats = SeasonStats()
        self.completed_games: List[SeasonGame] = []

        # Cache loaded teams to avoid re-reading JSON on every game
        self._team_cache: Dict[str, Team] = {}
        # Per-team season roster (injury carry-over)
        self._season_rosters: Dict[str, SeasonRoster] = {}

    # ── Class methods ─────────────────────────────────────────────────────

    @classmethod
    def load(
        cls,
        year: int = 2025,
        log_dir: Optional[str] = "season_logs",
        seed: Optional[int] = None,
    ) -> "Season":
        """Load a season from the bundled schedule JSON file.

        Parameters
        ----------
        year:
            Season year (e.g. 2025).  Looks for
            ``engine/data/schedules/<year>_schedule.json``.
        log_dir:
            Root directory for game logs (``None`` to skip logging).
        seed:
            Master RNG seed for reproducibility.
        """
        sched_file = os.path.join(
            cls._SCHEDULE_DIR, f"{year}_schedule.json"
        )
        if not os.path.exists(sched_file):
            raise FileNotFoundError(
                f"Schedule file not found: {sched_file}. "
                f"Available: {os.listdir(cls._SCHEDULE_DIR) if os.path.isdir(cls._SCHEDULE_DIR) else 'directory missing'}"
            )
        with open(sched_file) as f:
            data = json.load(f)

        return cls(
            schedule=data["games"],
            data_season=data.get("data_season", "2025_5e"),
            year=year,
            log_dir=log_dir,
            seed=seed,
        )

    # ── Simulation ────────────────────────────────────────────────────────

    def simulate(
        self,
        weeks: Optional[List[int]] = None,
        progress: bool = False,
    ) -> SeasonStats:
        """Simulate the season (or a subset of weeks).

        Parameters
        ----------
        weeks:
            Limit to specific week numbers (e.g. ``[1, 2]``).
            ``None`` simulates all weeks in the schedule.
        progress:
            If ``True``, print a one-line summary for each game as it completes.

        Returns
        -------
        SeasonStats
            Accumulated standings and player totals.
        """
        # Group games by week for ordered processing
        schedule_by_week: Dict[int, List[Dict]] = {}
        for entry in self.schedule:
            w = entry["week"]
            schedule_by_week.setdefault(w, []).append(entry)

        target_weeks = sorted(schedule_by_week.keys())
        if weeks is not None:
            target_weeks = [w for w in target_weeks if w in weeks]

        game_seed = self.seed
        for week in target_weeks:
            if progress:
                print(f"\n── Week {week} {'─'*42}")
            for entry in schedule_by_week[week]:
                sg = self._simulate_game(entry, seed=game_seed)
                self.completed_games.append(sg)
                self.stats.record_game(sg)
                if self.log_dir:
                    self._save_game_log(sg)
                if progress:
                    w_label = sg.winner or "TIE"
                    print(
                        f"  {sg.away:>3s} @ {sg.home:<3s}  "
                        f"{sg.away_score:>2d}-{sg.home_score:<2d}  "
                        f"({w_label})"
                    )
                if game_seed is not None:
                    game_seed += 1

        return self.stats

    def simulate_week(self, week: int, progress: bool = False) -> List[SeasonGame]:
        """Simulate a single week and return its game results."""
        results = self.simulate(weeks=[week], progress=progress)
        return [g for g in self.completed_games if g.week == week]

    # ── Internal ──────────────────────────────────────────────────────────

    def _get_team(self, abbr: str) -> Team:
        """Load (and cache) a team's data, returning a fresh deep-copy each call.

        Each game must start from a clean roster (no injury-state bleed), so we
        always return a deep copy of the cached base team.  Season-level injury
        carry-over is handled by :class:`SeasonRoster` separately.
        """
        if abbr not in self._team_cache:
            self._team_cache[abbr] = Team.load(abbr, self.data_season)
        return copy.deepcopy(self._team_cache[abbr])

    def _get_season_roster(self, abbr: str) -> SeasonRoster:
        if abbr not in self._season_rosters:
            self._season_rosters[abbr] = SeasonRoster(self._get_team(abbr))
        return self._season_rosters[abbr]

    def _simulate_game(
        self, entry: Dict[str, Any], seed: Optional[int] = None
    ) -> SeasonGame:
        """Simulate one game and return a :class:`SeasonGame`."""
        home_abbr = entry["home"]
        away_abbr = entry["away"]
        week = entry["week"]
        date = entry.get("date", "")

        home_team = self._get_team(home_abbr)
        away_team = self._get_team(away_abbr)

        home_sr = self._get_season_roster(home_abbr)
        away_sr = self._get_season_roster(away_abbr)

        game = Game(home_team, away_team, seed=seed)

        # Inject carried-over season injuries into the game's injury state
        home_sr.apply_pre_game_injuries(game.state.injuries)
        away_sr.apply_pre_game_injuries(game.state.injuries)

        # Collect new injuries during simulation (play-by-play)
        new_injuries: Dict[str, int] = {}

        # Simulate the full game
        final_state = game.simulate_game()

        # Collect any new injuries that occurred this game.
        # injury_duration in the game is in *plays*, convert to *games*:
        # roughly 2-3 game days per injury duration value in the board game.
        # We use a simple rule: game injury_duration (plays) → games remaining.
        # The play log records injuries; we parse it minimally here.
        for line in final_state.play_log:
            if "injured! Out for" in line and "plays." in line:
                # "  ⚕ PlayerName injured! Out for N plays."
                try:
                    parts = line.strip().split()
                    # Find "Out" then "for" then number
                    out_idx = parts.index("Out")
                    plays = int(parts[out_idx + 2])
                    # Convert plays to games: ≤4 plays → 0 games (just this game),
                    # 5-16 → 1 game, 17-32 → 2 games, etc.
                    game_duration = max(0, (plays - 4) // 8)
                    # Find player name: ⚕ PlayerName injured!
                    oc_idx = next(i for i, p in enumerate(parts) if "injured!" in p)
                    player_name = " ".join(
                        p.strip("⚕") for p in parts[1:oc_idx]
                    ).strip()
                    if player_name and game_duration > 0:
                        new_injuries[player_name] = max(
                            new_injuries.get(player_name, 0), game_duration
                        )
                except (ValueError, IndexError, StopIteration):
                    pass

        # Update season rosters with post-game injury status
        home_sr.record_post_game_injuries(final_state.injuries, new_injuries)
        away_sr.record_post_game_injuries(final_state.injuries, new_injuries)

        return SeasonGame(
            week=week,
            home=home_abbr,
            away=away_abbr,
            date=date,
            home_score=final_state.score.home,
            away_score=final_state.score.away,
            player_stats=dict(final_state.player_stats),
            play_log=list(final_state.play_log),
        )

    def _save_game_log(self, game: SeasonGame) -> None:
        """Write a game's result and play log to a JSON file."""
        if not self.log_dir:
            return
        year_dir = os.path.join(self.log_dir, str(self.year))
        os.makedirs(year_dir, exist_ok=True)
        filename = f"week{game.week:02d}_{game.away}_at_{game.home}.json"
        filepath = os.path.join(year_dir, filename)
        with open(filepath, "w") as f:
            json.dump(game.to_dict(), f, indent=2)

    # ── Summary helpers ───────────────────────────────────────────────────

    def save_season_summary(self, path: Optional[str] = None) -> str:
        """Save the full season stats summary to a JSON file.

        Returns the file path written.
        """
        if path is None:
            if self.log_dir:
                path = os.path.join(self.log_dir, str(self.year), "season_summary.json")
            else:
                path = f"season_summary_{self.year}.json"
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.stats.to_dict(), f, indent=2)
        return path
