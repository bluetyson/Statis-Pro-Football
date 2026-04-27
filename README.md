# Statis Pro Football

A digital implementation of the classic Statis Pro Football tabletop game, featuring a Python game engine with AI play calling, a React/TypeScript web GUI, and complete player cards for all 32 NFL teams.

The primary mode is **5th Edition (5E)**, which uses a 109-card FAC deck faithfully reproducing the Statis Pro Football 5th Edition mechanics with Avalon Hill formulae.

## Features

- **Complete Game Engine** — Full football simulation with drives, scoring, penalties, turnovers, clock management, and overtime
- **Human Play Calling** — Call offensive plays, defensive formations, and special teams from the web GUI
- **AI Solitaire Mode** — Let the AI control both sides using the 5E SOLO field
- **Player Card System** — 5E (48/12-slot) cards generated from real NFL statistics, all 32 teams
- **Two Seasons of Data** — 2024 (2023 NFL stats) and 2025 (2024 NFL stats)
- **Web GUI** — React/TypeScript frontend with real-time game state, FAC card display, player stats, roster management, and depth chart
- **REST API** — FastAPI backend for all game management and play calling

## Quick Start

### Prerequisites

- Python 3.9+
- Node.js 18+ (for the GUI)

### Installation

```bash
# Clone the repository
git clone https://github.com/bluetyson/Statis-Pro-Football.git
cd Statis-Pro-Football

# Install Python dependencies
pip install -r scripts/requirements.txt

# Install GUI dependencies (optional, for web interface)
cd gui
npm install
cd ..
```

### Run a Quick Game (Python)

```python
from engine.team import Team
from engine.game import Game

# Load two teams (primary: 5th-edition format)
home = Team.load("KC", "2025_5e")   # Kansas City Chiefs
away = Team.load("BUF", "2025_5e")  # Buffalo Bills

# Simulate a complete game (5th Edition FAC deck)
game = Game(home, away, seed=42)
state = game.simulate_game()
print(f"Final Score: {state.away_team} {state.score.away} - {state.home_team} {state.score.home}")
```

### Run the API Server

```bash
python -m engine.api_server
# Server starts at http://localhost:8000
# API docs at http://localhost:8000/docs
```

### Run the Web GUI

```bash
# Terminal 1: Start the API server
python -m engine.api_server

# Terminal 2: Start the GUI dev server
cd gui
npm run dev
# Opens at http://localhost:3000
```

### Generate Player Cards

```bash
# Generate 2025 season cards (5th-edition 48/12-slot format) — primary
python engine/data/generate_2025_5e_data.py
```

### Simulate a Full Season

A built-in schedule for 2025 is included. To simulate:

```bash
# Simulate all 17 weeks and print final standings + stat leaders
python scripts/simulate_season.py --standings --leaders

# Simulate only the first 4 weeks with a fixed random seed
python scripts/simulate_season.py --weeks 1-4 --seed 42 --standings

# Simulate without writing per-game JSON logs
python scripts/simulate_season.py --no-logs
```

Or from Python:

```python
from engine.season import Season

season = Season.load(year=2025)       # uses bundled 2025 schedule
stats = season.simulate(progress=True)
print(stats.standings_text())
print(stats.player_stats_text(stat_key="passing_yards", label="Passing Yards"))
```

Per-game replay logs are written to `season_logs/2025/weekNN_AWAY_at_HOME.json`.

#### Downloading Real NFL Schedules

To simulate a real past or current season (e.g. 2024) with authentic matchups,
download the schedule from the free [nflverse](https://github.com/nflverse) dataset:

```bash
# Download the 2024 regular-season schedule (no extra dependencies needed)
python scripts/download_schedule.py --year 2024

# Preview without saving
python scripts/download_schedule.py --year 2024 --dry-run

# Save to a custom directory
python scripts/download_schedule.py --year 2024 --outdir /path/to/schedules
```

Optionally install [nfl-data-py](https://pypi.org/project/nfl-data-py/) for an
alternative fetch path:

```bash
pip install nfl-data-py
python scripts/download_schedule.py --year 2024 --use-nfl-data-py
```

The downloaded file is saved as `engine/data/schedules/2024_schedule.json` and is
immediately available to `Season.load(year=2024)`. nflverse covers all seasons
from 1999 onward, including future scheduled games.

Team abbreviation differences between nflverse and this project are handled
automatically (e.g. `JAC→JAX`, `WAS→WSH`).

### Run Tests

```bash
# Run all tests (excluding API server tests which require fastapi installed)
python3 -m pytest tests/ -x -q --ignore=tests/test_api_server.py -k "not test_oob"

# Run all tests including API server tests
python3 -m pytest tests/ -x -q
```

## How to Play

### Game Modes

When you start the web GUI (`npm run dev` + API server), you select a game mode on the setup screen:

| Mode | Description |
|------|-------------|
| **Solitaire** | AI controls both teams. Good for watching a game play out automatically. |
| **Human Offense** | You call all offensive plays; AI handles the defense. |
| **Human Defense** | You call all defensive plays; AI handles the offense. |

You also select home and away teams, and the season (`2025_5e` is recommended).

---

### Calling Offensive Plays (Human Offense Mode)

The **Offensive Play Caller** panel appears on your turn. Each section controls part of your play call:

#### 1. Select Play Type

| Play | Description |
|------|-------------|
| 🏃 **Run** | Standard rushing play |
| 📫 **Short Pass** | Medium-range pass (SH column) |
| 🎯 **Long Pass** | Deep pass — blocked inside the opponent's 20-yard line |
| ⚡ **Quick Pass** | Fast release, fewer receiver options (QK column) |
| 🖥️ **Screen** | Screen pass — blocked within 5 yards of the goal line |
| 🔄 **End-Around** | WR/TE carries the ball — limited to once per player per game |
| 🦵 **Punt** | Kick the ball away on 4th down |
| 🥅 **Field Goal** | Attempt a field goal |
| 🧎 **Kneel** | QB kneels to run out the clock |
| ⚡ **Spike** | Stop the clock — use before it expires |

#### 2. Select Direction

For **run plays**: Inside Left (IL), Inside Right (IR), Sweep Left (SL), Sweep Right (SR)

For **pass plays**: Left, Right, Middle

#### 3. Select Strategy (optional)

Strategies add wrinkles to the play. Available options depend on the play type:

| Strategy | Valid For | Effect |
|----------|-----------|--------|
| **QB Flop** | Runs | QB fakes a pass; small negative gain |
| **QB Sneak** | Runs | QB sneaks — 0 or +1 yard |
| **Draw Play** | Runs | RB draw; fakes out the pass rush |
| **Play-Action Pass** | Passes | Fake run before passing; boosts completion |

#### 4. Select Ball Carrier or Receiver Target

- **Run / End-Around**: Choose an RB or QB from the dropdown, or leave on Auto (picks best healthy RB).
- **Pass plays**: Choose the receiver you want to target. The best healthy receiver is auto-selected, but you can override it.

#### 5. Backs in to Block (pass plays)

On any pass play you can optionally keep one or more RBs in to pass-block. Each blocking back:
- Adds **+2 to the QB's completion range**
- **Cannot be targeted** on that play — if the FAC card redirects to a blocking back, the pass falls incomplete

#### 6. Call the Play

Click **▶ Call Play** to execute. The play log updates immediately with the result.

#### Automation Options

If you don't want to call every play manually, three buttons let the AI take over temporarily:

| Button | What it does |
|--------|-------------|
| 🤖 **AI Play** | AI calls a single play for your team |
| 🏃 **Sim Drive** | AI runs the current drive to completion |
| 🏆 **Sim Game** | AI simulates the rest of the game |

#### Special Teams Options

Expand **🏈 Special Teams Options** for:

| Option | When to Use |
|--------|-------------|
| **Fake Punt** | 4th down — resolves as a run from punt formation (once per game) |
| **Fake FG** | 4th down — resolves as a pass or run from FG formation (once per game, not in final 2 min) |
| **Coffin Corner** | Punt aimed at the sideline; use the slider to set the yardage deduction (-10 to -25 yds) |
| **Onside Kick** | After a score — attempt to recover your own kickoff |
| **Squib Kick** | Low bouncing kick to avoid a deep returner |

---

### Calling Defensive Plays (Human Defense Mode)

The **Defensive Play Caller** panel appears when the opponent has the ball.

#### 1. Defensive Formation (cosmetic)

Choose the personnel grouping you want displayed. **Note:** formation labels are display-only in 5E — they do not modify play resolution. All play modifiers come from the Play Card and individual player ratings.

| Formation | Personnel |
|-----------|-----------|
| **4-3 Base** | 4 DL, 3 LB, 4 DB |
| **3-4 Base** | 3 DL, 4 LB, 4 DB |
| **Nickel** | 4 DL, 2 LB, 5 DB — extra DB for passing situations |
| **Goal Line** | 5+ DL, LB — heavy run stop package |

#### 2. Defensive Play Card

This is the main defensive decision and does affect play resolution:

| Play Card | Effect |
|-----------|--------|
| 🎯 **Pass Defense** | Standard pass coverage (Quick -10 \| Short 0 \| Long 0) |
| 🔒 **Prevent Defense** | Concede short gains, protect against big plays (Quick -10 \| Short -5 \| Long -7) |
| 🏃 **Run Defense (No Key)** | Commit to stopping the run (+2 RUN# modifier) |
| 1️⃣ **Run D / Key Back 1** | Key on the #1 back — +4 modifier if correct, 0 if wrong |
| 2️⃣ **Run D / Key Back 2** | Key on the #2 back |
| 3️⃣ **Run D / Key Back 3** | Key on the #3 back |
| ⚡ **Blitz** | Send extra pass rushers (Short -5 \| Long passes trigger P.Rush) |

#### 3. Defensive Strategy (optional)

| Strategy | Effect |
|----------|--------|
| **Double Coverage (-7)** | Remove one receiver from available targets; -7 to completion range |
| **Triple Coverage (-15)** | Remove two receivers; -15 to completion range |
| **Alt Double Coverage** | Variation removing two receivers without the range penalty |

#### 4. Blitz Player Selection

If you choose the **Blitz** play card, a panel appears to select which LBs and/or DBs blitz. You must pick **2–5 players**. Selected players are removed from their coverage boxes and rush the QB.

#### 5. Set Defense

Click **🛡️ Set Defense** to commit your defensive call. The offensive AI then calls its play and the outcome is resolved.

---

### Display Boxes (A–O)

The **Display Boxes** panel shows the 15 defensive position slots filled by your defenders:

| Row | Boxes | Players |
|-----|-------|---------|
| Row 1 | A–E | DL (DE/DT) |
| Row 2 | F–J | LBs |
| Row 3 | K–O | DBs (CB in K/O, FS in M, SS in N) |

The FAC card's SL/IL/SR/IR field triggers BV vs TV blocking matchups using these box assignments. You can reassign players to boxes from the **Starting Lineup** and **Substitutions** panels.

---

### Roster Management

Three panels on the right sidebar let you manage your roster mid-game:

- **Starting Lineup** — View and change the players assigned to each position slot
- **Substitutions** — Swap in backup players from the depth chart
- **Depth Chart** — View the full roster sorted by position; includes injured status

Injuries are tracked automatically. When a player is injured, their backup is promoted immediately.

---

## The 5th Edition FAC Deck

Statis Pro Football 5E uses a deck of **109 Fast Action Cards** drawn without replacement:

- **96 standard cards** — numbers 1–48, each appearing twice (normal + out-of-bounds variant)
- **13 Z-cards** — special event cards (penalties, injuries, fumbles)

Each card carries fields that drive every aspect of play resolution:

| Field | Used For |
|-------|----------|
| RUN# (1–12) | RB card lookup for rushing plays |
| PASS# (1–48) | QB and receiver card lookup for passing plays |
| SL / IL / SR / IR | Blocking matchup (BV vs TV) for run and pass plays |
| QK / SH / LG | Receiver targeting override or pass-rush trigger |
| ER | End-around resolution |
| SC | Screen pass result |
| Z RES | Z-card event (penalty / injury / fumble) |
| SOLO | AI solitaire play calling |

When the deck is exhausted it is automatically reshuffled.

### Player Grades

Players are graded **A+, A, B, C, or D** based on real NFL performance. Higher grades produce better card distributions — more completions, longer gains, fewer turnovers.

---

## Project Structure

```
Statis-Pro-Football/
├── engine/              # Python game engine
│   ├── api_server.py    # FastAPI REST server
│   ├── game.py          # Core game state and logic
│   ├── play_resolver.py # Play outcome resolution
│   ├── fac_deck.py      # 109-card FAC deck
│   ├── solitaire.py     # AI play calling
│   ├── team.py          # Team and roster management
│   └── data/
│       ├── 2025_5e/     # 2025 season (5th-ed, 32 teams) ← primary
│       └── 2026_5e/     # 2026 season (5th-ed, 32 teams)
├── gui/                 # React/TypeScript web frontend
│   └── src/
│       └── components/  # HumanPlayCaller, DefensivePlayCaller, DisplayBoxes, …
├── scripts/
│   └── requirements.txt # Python dependencies
├── tests/               # Test suite (600+ tests)
└── docs/                # Detailed documentation
```

## Documentation

- **[Getting Started](docs/getting-started.md)** — Detailed installation, all run options, troubleshooting
- **[Game Mechanics](docs/game-mechanics.md)** — Full explanation of 5E rules, FAC deck, clock, scoring
- **[Player Cards](docs/player-cards.md)** — Understanding player card formats with examples
- **[Creating Custom Players](docs/creating-custom-players.md)** — How to create your own player cards
- **[API Reference](docs/api-reference.md)** — REST API endpoint documentation

## License

This project is for educational and entertainment purposes.
