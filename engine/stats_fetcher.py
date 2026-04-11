"""Stats fetcher with graceful fallback for Statis Pro Football."""
import json
import os
import random
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class PlayerStats:
    name: str
    team: str
    position: str
    stats: Dict[str, Any]


# 2024 NFL Season Reference Data (fallback)
NFL_2024_STATS = {
    "QB": {
        "elite": {"comp_pct": 0.672, "ypa": 8.2, "td_int": 3.8, "sack_rate": 0.058},
        "good":  {"comp_pct": 0.640, "ypa": 7.4, "td_int": 2.8, "sack_rate": 0.070},
        "avg":   {"comp_pct": 0.610, "ypa": 6.8, "td_int": 2.0, "sack_rate": 0.082},
        "below": {"comp_pct": 0.570, "ypa": 6.2, "td_int": 1.5, "sack_rate": 0.095},
    },
    "RB": {
        "elite": {"ypc": 5.2, "fumble_rate": 0.008},
        "good":  {"ypc": 4.5, "fumble_rate": 0.012},
        "avg":   {"ypc": 3.9, "fumble_rate": 0.016},
        "below": {"ypc": 3.4, "fumble_rate": 0.022},
    },
    "WR": {
        "elite": {"catch_rate": 0.720, "avg_yards": 14.2},
        "good":  {"catch_rate": 0.660, "avg_yards": 12.5},
        "avg":   {"catch_rate": 0.620, "avg_yards": 11.0},
        "below": {"catch_rate": 0.560, "avg_yards": 9.5},
    },
    "TE": {
        "elite": {"catch_rate": 0.700, "avg_yards": 11.5},
        "good":  {"catch_rate": 0.650, "avg_yards": 9.8},
        "avg":   {"catch_rate": 0.610, "avg_yards": 8.8},
        "below": {"catch_rate": 0.560, "avg_yards": 7.5},
    },
    "K": {
        "elite": {"accuracy": 0.895, "xp_rate": 0.990},
        "good":  {"accuracy": 0.855, "xp_rate": 0.980},
        "avg":   {"accuracy": 0.810, "xp_rate": 0.970},
        "below": {"accuracy": 0.750, "xp_rate": 0.950},
    },
    "P": {
        "elite": {"avg_distance": 48.5, "inside_20_rate": 0.44},
        "good":  {"avg_distance": 46.0, "inside_20_rate": 0.40},
        "avg":   {"avg_distance": 44.0, "inside_20_rate": 0.36},
        "below": {"avg_distance": 41.0, "inside_20_rate": 0.30},
    },
}

GRADE_TO_TIER = {
    "A+": "elite", "A": "elite",
    "B": "good",
    "C": "avg",
    "D": "below",
}


class StatsFetcher:
    """Fetches player stats with graceful fallback to built-in data."""

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or os.path.join(os.path.dirname(__file__), "data")
        self._cache: Dict[str, Any] = {}

    def get_qb_stats(self, name: str, grade: str) -> Dict[str, Any]:
        tier = GRADE_TO_TIER.get(grade, "avg")
        base = NFL_2024_STATS["QB"][tier].copy()
        base["comp_pct"] += random.uniform(-0.02, 0.02)
        base["ypa"] += random.uniform(-0.3, 0.3)
        return base

    def get_rb_stats(self, name: str, grade: str) -> Dict[str, Any]:
        tier = GRADE_TO_TIER.get(grade, "avg")
        base = NFL_2024_STATS["RB"][tier].copy()
        base["ypc"] += random.uniform(-0.2, 0.2)
        return base

    def get_wr_stats(self, name: str, grade: str) -> Dict[str, Any]:
        tier = GRADE_TO_TIER.get(grade, "avg")
        base = NFL_2024_STATS["WR"][tier].copy()
        base["catch_rate"] += random.uniform(-0.02, 0.02)
        base["avg_yards"] += random.uniform(-0.5, 0.5)
        return base

    def get_te_stats(self, name: str, grade: str) -> Dict[str, Any]:
        tier = GRADE_TO_TIER.get(grade, "avg")
        return NFL_2024_STATS["TE"][tier].copy()

    def get_k_stats(self, name: str, grade: str) -> Dict[str, Any]:
        tier = GRADE_TO_TIER.get(grade, "avg")
        return NFL_2024_STATS["K"][tier].copy()

    def get_p_stats(self, name: str, grade: str) -> Dict[str, Any]:
        tier = GRADE_TO_TIER.get(grade, "avg")
        return NFL_2024_STATS["P"][tier].copy()

    def get_def_ratings(self, position: str, grade: str) -> Dict[str, int]:
        tier = GRADE_TO_TIER.get(grade, "avg")
        base_ratings = {
            "elite": {"pass_rush": 90, "coverage": 85, "run_stop": 85},
            "good":  {"pass_rush": 75, "coverage": 72, "run_stop": 72},
            "avg":   {"pass_rush": 60, "coverage": 60, "run_stop": 60},
            "below": {"pass_rush": 45, "coverage": 45, "run_stop": 45},
        }

        ratings = base_ratings[tier].copy()

        if position in ("DE", "DT", "EDGE", "DL"):
            ratings["pass_rush"] = min(99, ratings["pass_rush"] + 10)
            ratings["coverage"] = max(30, ratings["coverage"] - 15)
        elif position in ("CB", "S", "FS", "SS"):
            ratings["coverage"] = min(99, ratings["coverage"] + 10)
            ratings["pass_rush"] = max(30, ratings["pass_rush"] - 10)
        elif position in ("MLB", "ILB", "OLB", "LB"):
            ratings["run_stop"] = min(99, ratings["run_stop"] + 10)

        return ratings

    def load_team_data(self, team_abbr: str, season: int = 2025) -> Optional[Dict]:
        """Load team data from JSON file."""
        filepath = os.path.join(self.data_dir, str(season), f"{team_abbr}.json")
        if os.path.exists(filepath):
            with open(filepath) as f:
                return json.load(f)
        return None
