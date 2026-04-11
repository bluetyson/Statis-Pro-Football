"""Player card data model for Statis Pro Football."""
from dataclasses import dataclass, field
from typing import Dict, Optional, Any, List
from enum import Enum


class Position(str, Enum):
    QB = "QB"
    RB = "RB"
    WR = "WR"
    TE = "TE"
    K = "K"
    P = "P"
    DEF = "DEF"
    OL = "OL"
    DL = "DL"
    LB = "LB"
    CB = "CB"
    S = "S"


class Grade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


ResultDict = Dict[str, Any]
CardColumn = Dict[str, ResultDict]


@dataclass
class PlayerCard:
    player_name: str
    team: str
    position: str
    number: int
    overall_grade: str = "C"

    short_pass: CardColumn = field(default_factory=dict)
    long_pass: CardColumn = field(default_factory=dict)
    screen_pass: CardColumn = field(default_factory=dict)

    inside_run: CardColumn = field(default_factory=dict)
    outside_run: CardColumn = field(default_factory=dict)

    short_reception: CardColumn = field(default_factory=dict)
    long_reception: CardColumn = field(default_factory=dict)

    fg_chart: Dict[str, float] = field(default_factory=dict)
    xp_rate: float = 0.95

    avg_distance: float = 44.0
    inside_20_rate: float = 0.35

    pass_rush_rating: int = 50
    coverage_rating: int = 50
    run_stop_rating: int = 50

    stats_summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.player_name,
            "position": self.position,
            "number": self.number,
            "team": self.team,
            "overall_grade": self.overall_grade,
            "short_pass": self.short_pass,
            "long_pass": self.long_pass,
            "screen_pass": self.screen_pass,
            "inside_run": self.inside_run,
            "outside_run": self.outside_run,
            "short_reception": self.short_reception,
            "long_reception": self.long_reception,
            "fg_chart": self.fg_chart,
            "xp_rate": self.xp_rate,
            "avg_distance": self.avg_distance,
            "inside_20_rate": self.inside_20_rate,
            "pass_rush_rating": self.pass_rush_rating,
            "coverage_rating": self.coverage_rating,
            "run_stop_rating": self.run_stop_rating,
            "stats_summary": self.stats_summary,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlayerCard":
        card = cls(
            player_name=data.get("name", "Unknown"),
            team=data.get("team", ""),
            position=data.get("position", ""),
            number=data.get("number", 0),
            overall_grade=data.get("overall_grade", "C"),
        )
        card.short_pass = data.get("short_pass", {})
        card.long_pass = data.get("long_pass", {})
        card.screen_pass = data.get("screen_pass", {})
        card.inside_run = data.get("inside_run", {})
        card.outside_run = data.get("outside_run", {})
        card.short_reception = data.get("short_reception", {})
        card.long_reception = data.get("long_reception", {})
        card.fg_chart = data.get("fg_chart", {})
        card.xp_rate = data.get("xp_rate", 0.95)
        card.avg_distance = data.get("avg_distance", 44.0)
        card.inside_20_rate = data.get("inside_20_rate", 0.35)
        card.pass_rush_rating = data.get("pass_rush_rating", 50)
        card.coverage_rating = data.get("coverage_rating", 50)
        card.run_stop_rating = data.get("run_stop_rating", 50)
        card.stats_summary = data.get("stats_summary", {})
        return card


ALL_SLOTS = [f"{t}{o}" for t in range(1, 9) for o in range(1, 9)]
