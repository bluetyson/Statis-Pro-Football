# Getting Started

This guide walks you through installing, configuring, and running Statis Pro Football.

The primary game mode is **5th Edition (5E)**, which uses a 109-card FAC (Fast Action Card) deck. Player data is stored in `engine/data/2025_5e/` using the season string `"2025_5e"`.

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

Run a game directly in Python using 5th Edition mode:

```python
from engine.team import Team
from engine.game import Game

# Load teams — use "2025_5e" for the primary 5th-edition format
home = Team.load("KC", "2025_5e")   # Kansas City Chiefs
away = Team.load("SF", "2025_5e")   # San Francisco 49ers

# Simulate a complete game (5th Edition FAC deck, default)
game = Game(home, away, seed=42)
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

home = Team.load("DAL", "2025_5e")
away = Team.load("PHI", "2025_5e")
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

home = Team.load("BUF", "2025_5e")
away = Team.load("MIA", "2025_5e")
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
- **Human Play Caller** — Full offensive play calling (run directions IL/IR/SL/SR, pass types QK/SH/LG/SC, strategies Flop/Sneak/Draw/Play-Action)
- **Defensive Play Caller** — Formation (4-3/3-4/Nickel/Goal Line), play card (Pass Defense/Run Defense/Blitz/Prevent), strategy (Double/Triple Coverage), blitz player selection
- **Formation Grid** — Visual display board with player assignments (A-O boxes)
- **Depth Chart & Substitutions** — Manage rosters, backups, and injuries
- **FAC Card Display** — Shows the drawn Fast Action Card fields
- **Player Stats Panel** — Cumulative rushing/passing/receiving stats per player
- **Game Log** — Real-time play-by-play updates

### Option 5: API Only

Use the REST API directly with curl or any HTTP client:

```bash
# Start the server
python -m engine.api_server

# List available teams (5E season)
curl http://localhost:8000/teams?season=2025_5e

# Start a new game (5E mode is default)
curl -X POST http://localhost:8000/games/new \
  -H "Content-Type: application/json" \
  -d '{"home_team": "KC", "away_team": "BUF", "season": "2025_5e"}'

# Execute a play (replace GAME_ID with the ID from above)
curl -X POST http://localhost:8000/games/GAME_ID/play

# Simulate the entire game
curl -X POST http://localhost:8000/games/GAME_ID/simulate
```

## Available Seasons

| Season Key | Based On | Format | Teams |
|------------|----------|--------|-------|
| `2025_5e` | 2024 NFL regular season stats | 5th Edition (48/12-slot) | All 32 NFL teams |
| `2026_5e` | 2025 NFL regular season stats | 5th Edition (48/12-slot) | All 32 NFL teams |

> **Recommended**: Use `2025_5e` or `2026_5e` for the fully-featured Avalon Hill formula simulation.

## Available Teams

All 32 NFL teams are available in all seasons:

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
# Regenerate 2025 5E cards
python engine/data/generate_2025_5e_data.py

# Regenerate 2026 5E cards
python engine/data/generate_2026_5e_data.py
```

Card generation uses a fixed random seed (42) for reproducibility. The same seed always produces the same card distributions.

## Running Tests

```bash
# Run all tests (standard, excluding API server and out-of-bounds tests)
python3 -m pytest tests/ -x -q --ignore=tests/test_api_server.py -k "not test_oob"

# Run all tests including API server (requires fastapi + uvicorn installed)
python3 -m pytest tests/ -x -q

# Run specific test file
python3 -m pytest tests/test_5e_system.py -v

# Run with coverage (requires pytest-cov)
python3 -m pytest tests/ --cov=engine
```

## Troubleshooting

### "Team data not found" error

Make sure the team data JSON files exist:
```bash
ls engine/data/2025_5e/  # Should show 32 .json files
```

If missing, regenerate them:
```bash
python engine/data/generate_2025_5e_data.py
```

### API server won't start

Ensure FastAPI and uvicorn are installed:
```bash
pip install fastapi uvicorn[standard]
```

### GUI shows connection errors

Make sure the API server is running on port 8000 before starting the GUI. The Vite dev server proxies `/api` calls to `http://localhost:8000`.

### Updating an Existing Local Clone

Because the project is moving quickly, use this sequence whenever you pull new changes:

```bash
# From the repo root
git pull

# Refresh Python dependencies
pip install -r scripts/requirements.txt

# Refresh GUI dependencies and rebuild
cd gui
rm -rf node_modules
npm install
npx vite build
cd ..

# Re-run backend tests
python3 -m pytest tests/ -x -q --ignore=tests/test_api_server.py -k "not test_oob"
```

If you are actively developing with the GUI open, restart both the API server and the Vite dev server after pulling updates.
