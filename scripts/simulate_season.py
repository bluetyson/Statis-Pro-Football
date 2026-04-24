#!/usr/bin/env python3
"""CLI script to simulate a full Statis-Pro Football season.

Usage examples::

    # Simulate the full 2025 season (all 272 games)
    python scripts/simulate_season.py

    # Simulate only weeks 1-4 with verbose game output
    python scripts/simulate_season.py --weeks 1-4 --verbose

    # Reproducible run with a fixed seed; don't save logs
    python scripts/simulate_season.py --seed 42 --no-logs

    # Show standings and top stat leaders after the run
    python scripts/simulate_season.py --standings --leaders
"""

import argparse
import os
import sys
import time

# Allow running from the project root without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.season import Season


def parse_weeks(weeks_str: str):
    """Parse a weeks specification like '1-4' or '1,3,5' into a list of ints."""
    result = []
    for part in weeks_str.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-", 1)
            result.extend(range(int(lo), int(hi) + 1))
        else:
            result.append(int(part))
    return sorted(set(result))


def main():
    parser = argparse.ArgumentParser(
        description="Simulate a Statis-Pro Football season.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--year", type=int, default=2025,
        help="Season year (default: 2025)",
    )
    parser.add_argument(
        "--weeks", type=str, default=None,
        help="Week range to simulate, e.g. '1-4' or '1,3,5' (default: all)",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Master RNG seed for reproducibility",
    )
    parser.add_argument(
        "--log-dir", type=str, default="season_logs",
        help="Root directory for game logs (default: season_logs/)",
    )
    parser.add_argument(
        "--no-logs", action="store_true",
        help="Do not write per-game JSON logs",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print each game score as it completes",
    )
    parser.add_argument(
        "--standings", action="store_true",
        help="Print conference/division standings after simulation",
    )
    parser.add_argument(
        "--leaders", action="store_true",
        help="Print statistical leaders after simulation",
    )
    parser.add_argument(
        "--summary", action="store_true",
        help="Save a season_summary.json file after simulation",
    )
    args = parser.parse_args()

    # Build season
    try:
        season = Season.load(
            year=args.year,
            log_dir=None if args.no_logs else args.log_dir,
            seed=args.seed,
        )
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    target_weeks = parse_weeks(args.weeks) if args.weeks else None
    total_games = sum(
        1 for g in season.schedule
        if target_weeks is None or g["week"] in target_weeks
    )

    print(f"Statis-Pro Football — {args.year} Season Simulation")
    print(f"Simulating {total_games} game(s)…")
    if args.seed is not None:
        print(f"  (seed={args.seed})")
    if not args.no_logs:
        print(f"  Logs → {args.log_dir}/{args.year}/")
    print()

    t0 = time.monotonic()
    stats = season.simulate(weeks=target_weeks, progress=args.verbose)
    elapsed = time.monotonic() - t0

    completed = len(season.completed_games)
    print(f"\nCompleted {completed} game(s) in {elapsed:.1f}s.")

    if args.standings:
        print(stats.standings_text())

    if args.leaders:
        LEADER_STATS = [
            ("passing_yards",   "Passing Yards"),
            ("rushing_yards",   "Rushing Yards"),
            ("receiving_yards", "Receiving Yards"),
            ("passing_tds",     "Passing TDs"),
            ("rushing_tds",     "Rushing TDs"),
            ("receiving_tds",   "Receiving TDs"),
            ("sacks_given",     "Sacks (Defense)"),
            ("tackles",         "Tackles"),
            ("passes_defensed", "Passes Defensed"),
        ]
        for stat_key, label in LEADER_STATS:
            print(stats.player_stats_text(top_n=5, stat_key=stat_key, label=label))

    if args.summary:
        path = season.save_season_summary()
        print(f"\nSeason summary saved to: {path}")


if __name__ == "__main__":
    main()
