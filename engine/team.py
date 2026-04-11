"""Team and roster management for Statis Pro Football."""
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from .player_card import PlayerCard


@dataclass
class Roster:
    """Team roster containing player cards."""
    qbs: List[PlayerCard] = field(default_factory=list)
    rbs: List[PlayerCard] = field(default_factory=list)
    wrs: List[PlayerCard] = field(default_factory=list)
    tes: List[PlayerCard] = field(default_factory=list)
    kickers: List[PlayerCard] = field(default_factory=list)
    punters: List[PlayerCard] = field(default_factory=list)
    defenders: List[PlayerCard] = field(default_factory=list)

    def get_starter(self, position: str) -> Optional[PlayerCard]:
        pos_map = {
            "QB": self.qbs, "RB": self.rbs, "WR": self.wrs,
            "TE": self.tes, "K": self.kickers, "P": self.punters,
        }
        players = pos_map.get(position, [])
        return players[0] if players else None

    def all_players(self) -> List[PlayerCard]:
        return (self.qbs + self.rbs + self.wrs + self.tes +
                self.kickers + self.punters + self.defenders)


@dataclass
class Team:
    """Represents an NFL team with roster and stats."""
    abbreviation: str
    city: str
    name: str
    conference: str  # AFC/NFC
    division: str    # North/South/East/West
    roster: Roster = field(default_factory=Roster)

    wins: int = 0
    losses: int = 0
    ties: int = 0

    offense_rating: int = 75
    defense_rating: int = 75

    def to_dict(self) -> dict:
        return {
            "abbreviation": self.abbreviation,
            "city": self.city,
            "name": self.name,
            "conference": self.conference,
            "division": self.division,
            "record": {"wins": self.wins, "losses": self.losses, "ties": self.ties},
            "offense_rating": self.offense_rating,
            "defense_rating": self.defense_rating,
            "players": [p.to_dict() for p in self.roster.all_players()],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Team":
        team = cls(
            abbreviation=data.get("abbreviation", ""),
            city=data.get("city", ""),
            name=data.get("name", ""),
            conference=data.get("conference", "AFC"),
            division=data.get("division", "East"),
        )
        team.offense_rating = data.get("offense_rating", 75)
        team.defense_rating = data.get("defense_rating", 75)
        record = data.get("record", {})
        team.wins = record.get("wins", 0)
        team.losses = record.get("losses", 0)
        team.ties = record.get("ties", 0)

        roster = Roster()
        for p_data in data.get("players", []):
            card = PlayerCard.from_dict(p_data)
            pos = card.position.upper()
            if pos == "QB":
                roster.qbs.append(card)
            elif pos == "RB":
                roster.rbs.append(card)
            elif pos == "WR":
                roster.wrs.append(card)
            elif pos == "TE":
                roster.tes.append(card)
            elif pos == "K":
                roster.kickers.append(card)
            elif pos == "P":
                roster.punters.append(card)
            else:
                roster.defenders.append(card)
        team.roster = roster
        return team

    @classmethod
    def load(cls, team_abbr: str, season: int = 2025) -> "Team":
        """Load team from JSON data file."""
        data_dir = os.path.join(os.path.dirname(__file__), "data", str(season))
        filepath = os.path.join(data_dir, f"{team_abbr}.json")
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Team data not found: {filepath}")
        with open(filepath, "r") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def save(self, season: int = 2025) -> None:
        """Save team to JSON data file."""
        data_dir = os.path.join(os.path.dirname(__file__), "data", str(season))
        os.makedirs(data_dir, exist_ok=True)
        filepath = os.path.join(data_dir, f"{self.abbreviation}.json")
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)


def list_available_teams(season: int = 2025) -> List[str]:
    """List all available team abbreviations."""
    data_dir = os.path.join(os.path.dirname(__file__), "data", str(season))
    if not os.path.exists(data_dir):
        return []
    return [f.replace(".json", "") for f in os.listdir(data_dir) if f.endswith(".json")]
