# Creating Custom Players

This guide shows you how to create custom player cards, build custom teams, and add new seasons to Statis Pro Football.

## Creating Individual Player Cards

### Using the CardGenerator

The `CardGenerator` class creates player cards from real-world statistics:

```python
from engine.card_generator import CardGenerator

gen = CardGenerator(seed=42)  # Use a seed for reproducible cards

# Create a QB card
qb = gen.generate_qb_card(
    name="Custom QB",
    team="CUS",         # Team abbreviation
    number=7,
    comp_pct=0.65,      # Completion percentage (0.0–1.0)
    ypa=7.5,            # Yards per attempt
    int_rate=0.025,     # Interception rate (0.0–1.0)
    sack_rate=0.07,     # Sack rate (0.0–1.0)
    grade="B",          # A+, A, B, C, or D
)

# Create a RB card
rb = gen.generate_rb_card(
    name="Custom RB",
    team="CUS",
    number=22,
    ypc=4.5,            # Yards per carry
    fumble_rate=0.012,  # Fumble rate (0.0–1.0)
    grade="A",
)

# Create a WR card
wr = gen.generate_wr_card(
    name="Custom WR",
    team="CUS",
    number=81,
    catch_rate=0.68,    # Catch percentage (0.0–1.0)
    avg_yards=13.0,     # Average yards per reception
    grade="A",
)

# Create a TE card
te = gen.generate_te_card(
    name="Custom TE",
    team="CUS",
    number=86,
    catch_rate=0.65,    # Catch percentage
    avg_yards=9.5,      # Average yards per reception
    grade="B",
)

# Create a Kicker card
k = gen.generate_k_card(
    name="Custom K",
    team="CUS",
    number=3,
    accuracy=0.85,      # FG accuracy (0.0–1.0)
    xp_rate=0.985,      # Extra point success rate
    grade="B",
)

# Create a Punter card
p = gen.generate_p_card(
    name="Custom P",
    team="CUS",
    number=4,
    avg_distance=46.0,  # Average punt distance in yards
    inside_20_rate=0.40,# Percentage of punts inside the 20
    grade="B",
)

# Create a Defender card
de = gen.generate_def_card(
    name="Custom DE",
    team="CUS",
    number=99,
    position="DE",      # DE, DT, LB, CB, S, etc.
    pass_rush=85,       # 0–99 scale
    coverage=45,        # 0–99 scale
    run_stop=75,        # 0–99 scale
    grade="A",
)
```

### Stat Ranges for Realistic Cards

Use these ranges to create realistic player cards:

#### QB Stats

| Stat | Elite (A+/A) | Good (B) | Average (C) | Below (D) |
|------|-------------|----------|-------------|-----------|
| Comp % | .660–.700 | .620–.660 | .580–.620 | .540–.580 |
| YPA | 7.8–9.0 | 7.0–7.8 | 6.4–7.0 | 5.8–6.4 |
| INT Rate | .014–.020 | .020–.026 | .026–.032 | .032–.040 |
| Sack Rate | .048–.065 | .065–.080 | .080–.095 | .095–.110 |

#### RB Stats

| Stat | Elite (A+/A) | Good (B) | Average (C) | Below (D) |
|------|-------------|----------|-------------|-----------|
| YPC | 4.8–5.5 | 4.2–4.8 | 3.6–4.2 | 3.0–3.6 |
| Fumble Rate | .006–.010 | .010–.014 | .014–.018 | .018–.024 |

#### WR/TE Stats

| Stat | Elite (A+/A) | Good (B) | Average (C) | Below (D) |
|------|-------------|----------|-------------|-----------|
| Catch Rate | .700–.760 | .640–.700 | .580–.640 | .540–.580 |
| Avg Yards | 13.0–16.0 | 11.0–13.0 | 9.5–11.0 | 8.0–9.5 |

#### Kicker Stats

| Stat | Elite (A+/A) | Good (B) | Average (C) | Below (D) |
|------|-------------|----------|-------------|-----------|
| Accuracy | .885–.940 | .840–.885 | .790–.840 | .740–.790 |
| XP Rate | .990–.998 | .975–.990 | .955–.975 | .940–.955 |

#### Punter Stats

| Stat | Elite (A+/A) | Good (B) | Average (C) | Below (D) |
|------|-------------|----------|-------------|-----------|
| Avg Distance | 48–51 yds | 45–48 yds | 43–45 yds | 40–43 yds |
| Inside 20 % | .42–.46 | .38–.42 | .34–.38 | .28–.34 |

#### Defender Ratings

| Rating | Elite (A+/A) | Good (B) | Average (C) | Below (D) |
|--------|-------------|----------|-------------|-----------|
| Pass Rush | 84–99 | 72–84 | 56–72 | 40–56 |
| Coverage | 84–99 | 72–84 | 56–72 | 40–56 |
| Run Stop | 80–99 | 68–80 | 56–68 | 40–56 |

## Building a Custom Team

### Method 1: Programmatic

```python
from engine.card_generator import CardGenerator
from engine.team import Team, Roster
from engine.player_card import PlayerCard

gen = CardGenerator(seed=42)

# Create all player cards
qb = gen.generate_qb_card("Star QB", "ALL", 12, 0.68, 8.2, 0.018, 0.058, "A")
rb1 = gen.generate_rb_card("Power RB", "ALL", 28, 5.0, 0.009, "A")
rb2 = gen.generate_rb_card("Speed RB", "ALL", 22, 4.4, 0.013, "B")
wr1 = gen.generate_wr_card("Deep Threat", "ALL", 81, 0.72, 15.5, "A")
wr2 = gen.generate_wr_card("Possession WR", "ALL", 14, 0.74, 11.5, "A")
wr3 = gen.generate_wr_card("Slot WR", "ALL", 10, 0.66, 10.0, "B")
te = gen.generate_te_card("Receiving TE", "ALL", 86, 0.70, 11.0, "A")
k = gen.generate_k_card("Clutch K", "ALL", 3, 0.90, 0.995, "A")
p = gen.generate_p_card("Booming P", "ALL", 7, 48.0, 0.42, "A")
de = gen.generate_def_card("Edge Rusher", "ALL", 99, "DE", 94, 50, 78, "A")
dt = gen.generate_def_card("Interior DL", "ALL", 97, "DT", 84, 44, 86, "A")
cb = gen.generate_def_card("Shutdown CB", "ALL", 24, "CB", 48, 92, 72, "A")

# Build the roster
roster = Roster(
    qbs=[qb],
    rbs=[rb1, rb2],
    wrs=[wr1, wr2, wr3],
    tes=[te],
    kickers=[k],
    punters=[p],
    defenders=[de, dt, cb],
)

# Build the team
team = Team(
    abbreviation="ALL",
    city="All-Star",
    name="Legends",
    conference="AFC",
    division="East",
    roster=roster,
    offense_rating=95,
    defense_rating=90,
)

# Save it
team.save(season=2025)
print(f"Saved team to engine/data/2025/ALL.json")

# Now use it in a game!
from engine.game import Game
from engine.team import Team as TeamLoad

my_team = TeamLoad.load("ALL", 2025)
opponent = TeamLoad.load("KC", 2025)
game = Game(my_team, opponent)
state = game.simulate_game()
print(f"Score: {state.home_team} {state.score.home} - {state.away_team} {state.score.away}")
```

### Method 2: JSON File

Create a JSON file directly in `engine/data/2025/`:

```json
{
  "abbreviation": "ALL",
  "city": "All-Star",
  "name": "Legends",
  "conference": "NFC",
  "division": "West",
  "record": {"wins": 0, "losses": 0, "ties": 0},
  "offense_rating": 95,
  "defense_rating": 90,
  "players": [
    {
      "name": "Star QB",
      "position": "QB",
      "number": 12,
      "team": "ALL",
      "overall_grade": "A",
      "short_pass": { "...64 entries..." },
      "long_pass": { "...64 entries..." },
      "screen_pass": { "...64 entries..." },
      "stats_summary": {"comp_pct": 0.68, "ypa": 8.2, "int_rate": 0.018, "sack_rate": 0.058}
    }
  ]
}
```

> **Tip**: Generate the card data programmatically first (see Method 1), then call `team.to_dict()` to get the complete JSON structure.

## Adding a New Season

To add a new season (e.g., 2026), create a data generator script:

### 1. Create the Generator

Create `engine/data/generate_2026_data.py`:

```python
"""Generate 2026 NFL team data files for Statis Pro Football.

All player statistics are sourced from the 2025 NFL regular season.
"""
import sys
import os
import json
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from engine.card_generator import CardGenerator
from engine.team import Team, Roster

random.seed(42)
gen = CardGenerator(seed=42)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "2026")
os.makedirs(OUTPUT_DIR, exist_ok=True)

TEAMS = [
    # Define all 32 teams with ratings
    {"abbreviation": "KC", "city": "Kansas City", "name": "Chiefs",
     "conference": "AFC", "division": "West",
     "offense_rating": 88, "defense_rating": 85},
    # ... all 32 teams
]

TEAM_PLAYERS = {
    "KC": {
        "qb":  [{"name": "Patrick Mahomes", "number": 15, "grade": "A",
                  "comp_pct": 0.670, "ypa": 8.5, "int_rate": 0.016, "sack_rate": 0.055}],
        "rb":  [{"name": "Isiah Pacheco", "number": 10, "grade": "B",
                  "ypc": 4.6, "fumble_rate": 0.011},
                {"name": "Backup RB", "number": 25, "grade": "C",
                  "ypc": 3.8, "fumble_rate": 0.015}],
        "wr":  [{"name": "WR1 Name", "number": 4, "grade": "A",
                  "catch_rate": 0.71, "avg_yards": 13.0},
                {"name": "WR2 Name", "number": 11, "grade": "B",
                  "catch_rate": 0.65, "avg_yards": 12.0},
                {"name": "WR3 Name", "number": 17, "grade": "C",
                  "catch_rate": 0.62, "avg_yards": 11.0}],
        "te":  [{"name": "Travis Kelce", "number": 87, "grade": "A",
                  "catch_rate": 0.75, "avg_yards": 12.5}],
        "k":   [{"name": "Harrison Butker", "number": 7, "grade": "A",
                  "accuracy": 0.90, "xp_rate": 0.995}],
        "p":   [{"name": "Tommy Townsend", "number": 5, "grade": "B",
                  "avg_distance": 47.0, "inside_20_rate": 0.42}],
        "def": [{"name": "Chris Jones", "number": 95, "pos": "DT", "grade": "A",
                  "pass_rush": 94, "coverage": 48, "run_stop": 84},
                {"name": "LB Name", "number": 32, "pos": "LB", "grade": "B",
                  "pass_rush": 64, "coverage": 74, "run_stop": 84},
                {"name": "CB Name", "number": 38, "pos": "CB", "grade": "A",
                  "pass_rush": 48, "coverage": 88, "run_stop": 72}],
    },
    # ... all 32 teams
}


def build_team(team_info: dict) -> dict:
    """Build a complete team dictionary with generated player cards."""
    abbr = team_info["abbreviation"]
    players_data = TEAM_PLAYERS.get(abbr, {})
    players = []

    for p in players_data.get("qb", []):
        card = gen.generate_qb_card(
            name=p["name"], team=abbr, number=p["number"],
            comp_pct=p["comp_pct"], ypa=p["ypa"],
            int_rate=p["int_rate"], sack_rate=p["sack_rate"],
            grade=p["grade"])
        players.append(card.to_dict())

    for p in players_data.get("rb", []):
        card = gen.generate_rb_card(
            name=p["name"], team=abbr, number=p["number"],
            ypc=p["ypc"], fumble_rate=p["fumble_rate"],
            grade=p["grade"])
        players.append(card.to_dict())

    for p in players_data.get("wr", []):
        card = gen.generate_wr_card(
            name=p["name"], team=abbr, number=p["number"],
            catch_rate=p["catch_rate"], avg_yards=p["avg_yards"],
            grade=p["grade"])
        players.append(card.to_dict())

    for p in players_data.get("te", []):
        card = gen.generate_te_card(
            name=p["name"], team=abbr, number=p["number"],
            catch_rate=p["catch_rate"], avg_yards=p["avg_yards"],
            grade=p["grade"])
        players.append(card.to_dict())

    for p in players_data.get("k", []):
        card = gen.generate_k_card(
            name=p["name"], team=abbr, number=p["number"],
            accuracy=p["accuracy"], xp_rate=p["xp_rate"],
            grade=p["grade"])
        players.append(card.to_dict())

    for p in players_data.get("p", []):
        card = gen.generate_p_card(
            name=p["name"], team=abbr, number=p["number"],
            avg_distance=p["avg_distance"],
            inside_20_rate=p["inside_20_rate"],
            grade=p["grade"])
        players.append(card.to_dict())

    for p in players_data.get("def", []):
        card = gen.generate_def_card(
            name=p["name"], team=abbr, number=p["number"],
            position=p["pos"], pass_rush=p["pass_rush"],
            coverage=p["coverage"], run_stop=p["run_stop"],
            grade=p["grade"])
        players.append(card.to_dict())

    return {
        "abbreviation": abbr,
        "city": team_info["city"],
        "name": team_info["name"],
        "conference": team_info["conference"],
        "division": team_info["division"],
        "record": {"wins": 0, "losses": 0, "ties": 0},
        "offense_rating": team_info["offense_rating"],
        "defense_rating": team_info["defense_rating"],
        "players": players,
    }


def main():
    print(f"Generating 2026 team data in {OUTPUT_DIR}")
    for team_info in TEAMS:
        abbr = team_info["abbreviation"]
        print(f"  Generating {abbr}...")
        team_data = build_team(team_info)
        filepath = os.path.join(OUTPUT_DIR, f"{abbr}.json")
        with open(filepath, "w") as f:
            json.dump(team_data, f, indent=2)
    print("Done!")


if __name__ == "__main__":
    main()
```

### 2. Register the Season

Add it to `scripts/generate_cards.py`:

```python
from engine.data.generate_2026_data import main as generate_2026

SUPPORTED_SEASONS = {
    2024: generate_2024,
    2025: generate_2025,
    2026: generate_2026,
}
```

### 3. Generate the Data

```bash
python scripts/generate_cards.py --season 2026
```

## Tips for Realistic Cards

1. **Use real stats**: Look up player statistics on sites like Pro Football Reference
2. **Grade carefully**: Reserve A+ for truly elite players (top 3–5 at their position)
3. **Balance the team**: Not every player should be grade A — most NFL rosters have a mix
4. **Team ratings matter**: offense_rating (60–95) and defense_rating (60–90) affect game outcomes
5. **Seed consistency**: Use `CardGenerator(seed=42)` for reproducible results, or omit the seed for random variation each time
