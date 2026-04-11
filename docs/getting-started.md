# Getting Started

This guide walks you through installing, configuring, and running Statis Pro Football.

## Prerequisites

- **Python 3.9+** — The game engine is written in Python
- **Node.js 18+** — Required only if you want to run the web GUI
- **pip** — Python package manager

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/RichardScottOZ/Statis-Pro-Football.git
cd Statis-Pro-Football
```

### 2. Install Python Dependencies

```bash
pip install -r scripts/requirements.txt
```

This installs:
- `fastapi` — REST API framework
- `uvicorn` — ASGI server for the API
- `pydantic` — Data validation
- `pytest` — Testing framework
- `httpx` — HTTP client for testing

### 3. Install GUI Dependencies (Optional)

If you want the web interface:

```bash
cd gui
npm install
cd ..
```

## Running the Game

### Option 1: Python Script (Quickest)

Run a game directly in Python:

```python
from engine.team import Team
from engine.game import Game

# Load teams (use 2024 or 2025 season)
home = Team.load("KC", 2025)
away = Team.load("SF", 2025)

# Simulate a complete game
game = Game(home, away)
state = game.simulate_game()

# Print results
print(f"Final: {state.away_team} {state.score.away} - {state.home_team} {state.score.home}")
print(f"\nPlay-by-play (last 20):")
for play in state.play_log[-20:]:
    print(f"  {play}")
```

### Option 2: Play-by-Play Mode

Execute one play at a time:

```python
from engine.team import Team
from engine.game import Game

home = Team.load("DAL", 2025)
away = Team.load("PHI", 2025)
game = Game(home, away)

# Execute plays one at a time
for i in range(10):
    if not game.state.is_over:
        result = game.execute_play()
        print(f"Play {i+1}: {result.description}")
        print(f"  Score: Away {game.state.score.away} - Home {game.state.score.home}")
        print(f"  Ball: {'Home' if game.state.possession == 'home' else 'Away'} "
              f"{game.state.down}{'st' if game.state.down==1 else 'nd' if game.state.down==2 else 'rd' if game.state.down==3 else 'th'} "
              f"& {game.state.distance} at own {game.state.yard_line}")
```

### Option 3: Drive-by-Drive Mode

Simulate entire drives:

```python
from engine.team import Team
from engine.game import Game

home = Team.load("BUF", 2025)
away = Team.load("MIA", 2025)
game = Game(home, away)

# Simulate drives until the game ends
while not game.state.is_over:
    drive = game.simulate_drive()
    print(f"\n{'Home' if drive.team == 'home' else 'Away'} drive: "
          f"{drive.plays} plays, {drive.yards} yards → {drive.result} ({drive.points_scored} pts)")
    for play in drive.drive_log:
        print(f"  {play}")
```

### Option 4: Web GUI

Start both the API server and GUI dev server:

```bash
# Terminal 1: Start the API backend
python -m engine.api_server
# Runs on http://localhost:8000

# Terminal 2: Start the GUI frontend
cd gui
npm run dev
# Opens at http://localhost:3000
```

The web GUI provides:
- **Team Selector** — Pick home and away teams from any season
- **Game Board** — Visual display of score, quarter, clock, down & distance
- **Play Caller** — Buttons to run plays, simulate drives, or simulate the entire game
- **Game Log** — Real-time play-by-play updates
- **Dice Roller** — See each dice roll and its play tendency
- **Card Viewer** — Browse any team's roster and view individual player cards

### Option 5: API Only

Use the REST API directly with curl or any HTTP client:

```bash
# Start the server
python -m engine.api_server

# List available teams
curl http://localhost:8000/teams

# Start a new game
curl -X POST http://localhost:8000/games/new \
  -H "Content-Type: application/json" \
  -d '{"home_team": "KC", "away_team": "BUF", "season": 2025}'

# Execute a play (replace GAME_ID with the ID from above)
curl -X POST http://localhost:8000/games/GAME_ID/play

# Simulate the entire game
curl -X POST http://localhost:8000/games/GAME_ID/simulate
```

## Available Seasons

| Season | Based On | Teams |
|--------|----------|-------|
| 2024 | 2023 NFL regular season stats | All 32 NFL teams |
| 2025 | 2024 NFL regular season stats | All 32 NFL teams |

## Available Teams

All 32 NFL teams are available in both seasons:

| AFC East | AFC North | AFC South | AFC West |
|----------|-----------|-----------|----------|
| BUF Bills | BAL Ravens | HOU Texans | DEN Broncos |
| MIA Dolphins | CIN Bengals | IND Colts | KC Chiefs |
| NE Patriots | CLE Browns | JAX Jaguars | LAC Chargers |
| NYJ Jets | PIT Steelers | TEN Titans | LV Raiders |

| NFC East | NFC North | NFC South | NFC West |
|----------|-----------|-----------|----------|
| DAL Cowboys | CHI Bears | ATL Falcons | ARI Cardinals |
| NYG Giants | DET Lions | CAR Panthers | LAR Rams |
| PHI Eagles | GB Packers | NO Saints | SEA Seahawks |
| WSH Commanders | MIN Vikings | TB Buccaneers | SF 49ers |

## Regenerating Player Cards

To regenerate player card data:

```bash
# Regenerate 2025 cards
python scripts/generate_cards.py --season 2025

# Regenerate 2024 cards
python scripts/generate_cards.py --season 2024
```

Card generation uses a fixed random seed (42) for reproducibility. The same seed always produces the same card distributions.

## Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_engine.py -v

# Run with coverage (requires pytest-cov)
python -m pytest tests/ --cov=engine
```

## Troubleshooting

### "Team data not found" error

Make sure the team data JSON files exist:
```bash
ls engine/data/2025/  # Should show 32 .json files
ls engine/data/2024/  # Should show 32 .json files
```

If missing, regenerate them:
```bash
python scripts/generate_cards.py --season 2025
python scripts/generate_cards.py --season 2024
```

### API server won't start

Ensure FastAPI and uvicorn are installed:
```bash
pip install fastapi uvicorn[standard]
```

### GUI shows connection errors

Make sure the API server is running on port 8000 before starting the GUI. The Vite dev server proxies `/api` calls to `http://localhost:8000`.
