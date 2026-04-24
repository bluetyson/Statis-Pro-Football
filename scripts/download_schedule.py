#!/usr/bin/env python3
"""Download a real NFL schedule from the nflverse public dataset and convert it
to the JSON format used by engine/season.py.

Saved file:  engine/data/schedules/<YEAR>_schedule.json

Usage
-----
# Download the 2024 NFL season schedule (default)
python scripts/download_schedule.py

# Download 2025 season
python scripts/download_schedule.py --year 2025

# Download 2024, save to a custom directory
python scripts/download_schedule.py --year 2024 --outdir /tmp/schedules

# Preview without saving
python scripts/download_schedule.py --year 2024 --dry-run

# Use nfl-data-py (pip install nfl-data-py) instead of the CSV fallback
python scripts/download_schedule.py --year 2024 --use-nfl-data-py

Data source
-----------
The script fetches game data from the nflverse GitHub release:
  https://github.com/nflverse/nflverse-data/releases/download/schedules/schedules.csv

This CSV covers all NFL seasons from 1999 onward, including future (scheduled)
games.  No API key or authentication is required.

Alternatively, if `nfl-data-py` is installed, pass --use-nfl-data-py to
use ``nfl_data_py.import_schedules([year])`` instead.

Output format
-------------
The produced JSON matches the schema expected by engine/season.py::Season.load():

    {
      "season": 2024,
      "data_season": "2024_5e",
      "weeks": 18,
      "source": "nflverse",
      "games": [
        {"week": 1, "home": "KC", "away": "BAL", "date": "2024-09-05"},
        ...
      ]
    }

Team abbreviation mapping
-------------------------
nflverse uses a slightly different set of abbreviations for some franchises.
The mapping below converts them to match the filenames used by this project's
player card data (engine/data/<season>/<ABBREV>.json).

Known differences:
  nflverse → project
  JAC      → JAX
  WAS      → WSH
  LA       → LAR   (fallback for older data)
  OAK      → LV    (Raiders moved to Las Vegas after 2019)
  SD       → LAC   (Chargers moved to Los Angeles after 2016)
  STL      → LAR   (Rams moved to Los Angeles after 2015)
"""

import argparse
import csv
import io
import json
import os
import sys
import urllib.request
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NFLVERSE_SCHEDULES_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "schedules/schedules.csv"
)

# nflverse abbreviation → project abbreviation
ABBREV_MAP: Dict[str, str] = {
    "JAC": "JAX",
    "WAS": "WSH",
    "LA":  "LAR",  # legacy pre-2020 usage
    "OAK": "LV",   # Raiders moved to Las Vegas (2020)
    "SD":  "LAC",  # Chargers moved to Los Angeles (2017)
    "STL": "LAR",  # Rams moved to Los Angeles (2016)
}

# Game types to include.  "REG" = regular season.  Remove "POST" to skip
# playoff games.  Change to {"REG", "POST"} to include playoffs.
INCLUDED_GAME_TYPES = {"REG"}

# Which data_season suffix to use for each NFL season year.
# "YYYY_5e" cards are the primary format used by this project.
def _data_season(year: int) -> str:
    return f"{year}_5e"


# ---------------------------------------------------------------------------
# Team normalisation
# ---------------------------------------------------------------------------

def normalise_abbrev(abbrev: str) -> str:
    """Convert a nflverse team abbreviation to the project's abbreviation."""
    return ABBREV_MAP.get(abbrev.upper(), abbrev.upper())


# ---------------------------------------------------------------------------
# Data fetchers
# ---------------------------------------------------------------------------

def _fetch_via_nfl_data_py(year: int) -> List[dict]:
    """Download schedule via the nfl-data-py library."""
    try:
        import nfl_data_py as nfl  # type: ignore
    except ImportError:
        print(
            "ERROR: nfl-data-py is not installed.\n"
            "       Run:  pip install nfl-data-py\n"
            "       Or omit --use-nfl-data-py to use the CSV fallback.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Fetching {year} schedule via nfl-data-py …")
    df = nfl.import_schedules([year])
    rows = df.to_dict("records")
    return rows


def _fetch_via_csv(year: int) -> List[dict]:
    """Download the nflverse schedules CSV and filter to the requested year."""
    url = NFLVERSE_SCHEDULES_URL
    print(f"Fetching nflverse schedules CSV from:\n  {url}")
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "statis-pro-football/1.0 (+github.com/bluetyson)"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        print(f"ERROR: HTTP {exc.code} downloading schedule CSV: {exc.reason}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"ERROR: Network error downloading schedule CSV: {exc.reason}", file=sys.stderr)
        sys.exit(1)

    reader = csv.DictReader(io.StringIO(raw))
    rows = [r for r in reader if str(r.get("season", "")) == str(year)]
    print(f"  Downloaded {len(rows)} rows for season {year}.")
    return rows


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------

def convert_rows(rows: List[dict], year: int) -> dict:
    """Convert raw schedule rows to the project JSON format."""
    games: List[dict] = []
    weeks_seen = set()

    for row in rows:
        game_type = str(row.get("game_type", "REG")).upper()
        if game_type not in INCLUDED_GAME_TYPES:
            continue

        week_raw = row.get("week")
        try:
            week = int(week_raw)
        except (TypeError, ValueError):
            continue

        home = normalise_abbrev(str(row.get("home_team", "")))
        away = normalise_abbrev(str(row.get("away_team", "")))
        if not home or not away:
            continue

        # Date: nflverse uses "gameday" (YYYY-MM-DD) or "game_date"
        date = str(row.get("gameday", row.get("game_date", ""))).strip()
        if not date or date.lower() in ("nan", "none", ""):
            date = f"{year}-09-07"  # placeholder

        games.append({"week": week, "home": home, "away": away, "date": date})
        weeks_seen.add(week)

    if not games:
        print(
            f"WARNING: No regular-season games found for {year}.\n"
            "         Check that the year is valid (1999–present).",
            file=sys.stderr,
        )

    games.sort(key=lambda g: (g["week"], g["date"], g["home"]))
    n_weeks = max(weeks_seen) if weeks_seen else 0

    return {
        "season": year,
        "data_season": _data_season(year),
        "weeks": n_weeks,
        "source": "nflverse",
        "games": games,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download a real NFL schedule and save it for season simulation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--year", type=int, default=2024,
        help="NFL season year to download (default: 2024)",
    )
    parser.add_argument(
        "--outdir",
        default=os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "engine", "data", "schedules",
        ),
        help="Directory to save the JSON file (default: engine/data/schedules/)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print summary and first 5 games without saving",
    )
    parser.add_argument(
        "--use-nfl-data-py", action="store_true",
        help="Use nfl-data-py library instead of direct CSV download",
    )
    args = parser.parse_args()

    # Fetch rows
    if args.use_nfl_data_py:
        rows = _fetch_via_nfl_data_py(args.year)
    else:
        rows = _fetch_via_csv(args.year)

    # Convert
    schedule = convert_rows(rows, args.year)
    n_games = len(schedule["games"])
    print(
        f"Season {args.year}: {n_games} regular-season games across "
        f"{schedule['weeks']} weeks."
    )

    if args.dry_run:
        print("\nFirst 5 games:")
        for g in schedule["games"][:5]:
            print(f"  Week {g['week']:2d}  {g['away']} @ {g['home']}  ({g['date']})")
        print("(dry-run: file not saved)")
        return

    # Save
    os.makedirs(args.outdir, exist_ok=True)
    out_path = os.path.join(args.outdir, f"{args.year}_schedule.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(schedule, fh, indent=2)
    print(f"Saved → {out_path}")
    print("\nUsage in season simulation:")
    print(f"  from engine.season import Season")
    print(f"  season = Season.load(year={args.year})")
    print(f"  stats = season.simulate()")


if __name__ == "__main__":
    main()
