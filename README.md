# Statis Pro Football

A digital implementation of the classic Statis Pro Football tabletop game, featuring a Python game engine with AI play calling, a React/TypeScript web GUI, and complete player cards for all 32 NFL teams across multiple seasons.

**Status:** Active rapid development. Core 5E engine is largely implemented, the GUI now includes human offensive and defensive play calling, and 388 tests are passing.

## Overview

Statis Pro Football supports two game modes:

### 5th Edition Mode (Primary)

The **5th-edition FAC deck system** uses a physical deck of **109 Fast Action Cards** that faithfully reproduce the Statis Pro Football 5th Edition mechanics:

- **109-card deck** — 96 standard cards (numbers 1–48 appearing twice, with out-of-bounds variants) + 13 Z-cards (special events)
- **Draw-without-replacement** — Cards are drawn one at a time until the deck is exhausted, then reshuffled
- **48-slot QB pass columns** — Pass Numbers 1–48 produce receiver letters (A–E), INC, or INT
- **12-slot RB run columns** — Run Numbers 1–12 with inside, outside, and sweep directions
- **Two-stage pass resolution** — QB card determines receiver letter → receiver card determines yards
- **FAC-driven mechanics** — End-around checks (ER field), receiver targeting / pass-rush triggers (QK/SH/LG), screen results (SC), blocking matchups (SL/IL/SR/IR), and solitaire play calling (SOLO field)
- **Z-card system** — 13 Z-cards trigger special events (injuries, penalties, fumbles)
- **Offensive Strategies** — Flop, Sneak, Draw, Play-Action (all implemented)
- **Defensive Strategies** — Double Coverage, Triple Coverage (all implemented)
- **Big Play Defense** — Full system for teams with 9+ wins
- **Two-Minute Offense** — Complete restrictions (yardage halving, -4 completion)

### Legacy Mode

The original **d8×d8 dice-based system** (64 slots, range 11–88) remains fully supported for backward compatibility.

### Features

- **Complete Game Engine** — Full football simulation with drives, scoring, penalties, turnovers, clock management, and overtime
- **AI Play Calling** — Solitaire mode with both legacy dice-based and 5th-edition SOLO field-based play selection
- **Player Card System** — 5th-edition (48/12-slot) and legacy (64-slot) cards generated from real NFL statistics
- **Two Seasons of Data** — 2024 (2023 NFL stats) and 2025 (2024 NFL stats) with all 32 teams
- **Web GUI** — React/TypeScript frontend with human offensive play calling, human defensive play calling, defensive run/play cards, player selection, special teams controls, and real-time game state
- **REST API** — FastAPI backend with endpoints for game management, dice rolling, and card browsing
- **Comprehensive Tests** — 388 tests covering dice/deck distribution, card generation, game mechanics, GUI-facing API behavior, and 5E rules

## Implementation Status

- **Engine**: 140/146 5E rules (96%) implemented
- **GUI**: 63/88 audited features (72%) implemented
- **Tests**: 388 tests passing
- **Documentation**: Complete audit documents and API reference

See [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) for detailed status.

## Quick Start

### Prerequisites

- Python 3.9+
- Node.js 18+ (for the GUI)

### Installation

```bash
# Clone the repository
git clone https://github.com/RichardScottOZ/Statis-Pro-Football.git
cd Statis-Pro-Football

# Install Python dependencies
pip install -r scripts/requirements.txt

# Install GUI dependencies (optional, for web interface)
cd gui
npm install
cd ..
```

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
python3 -m pytest tests/ -x -q
```

If you are actively developing with the GUI open, restart both the API server and the Vite dev server after pulling updates.

### Run a Quick Game (Python)

```python
from engine.team import Team
from engine.game import Game

# Load two teams
home = Team.load("KC", "2025_5e")   # Kansas City Chiefs
away = Team.load("BUF", "2025_5e")  # Buffalo Bills

# 5th Edition mode (109-card FAC deck)
game = Game(home, away, use_5e=True, seed=42)
state = game.simulate_game()
print(f"Final Score: {state.away_team} {state.score.away} - {state.home_team} {state.score.home}")

# Legacy mode (d8×d8 dice)
game = Game(home, away, use_5e=False)
state = game.simulate_game()
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
# Generate 2025 season cards (legacy 64-slot format)
python engine/data/generate_2025_data.py

# Generate 2025 season cards (5th-edition 48/12-slot format)
python engine/data/generate_2025_5e_data.py
```

### Run Tests

```bash
python3 -m pytest tests/ -x -q
```

## Project Structure

```
Statis-Pro-Football/
├── engine/                     # Python game engine
│   ├── api_server.py           # FastAPI REST server
│   ├── card_generator.py       # Generate player cards (legacy + 5th-ed)
│   ├── charts.py               # Penalty, return, and recovery charts
│   ├── fac_deck.py             # 109-card FAC deck (5th Edition)
│   ├── fac_distributions.py    # Card distribution tables (48/12/64-slot)
│   ├── fast_action_dice.py     # 11-88 dice system (legacy)
│   ├── game.py                 # Core game state and logic
│   ├── play_resolver.py        # Play outcome resolution (legacy + 5th-ed)
│   ├── player_card.py          # Player card data model
│   ├── solitaire.py            # AI play calling (legacy + SOLO-based)
│   ├── stats_fetcher.py        # Stats lookup with fallback data
│   ├── team.py                 # Team and roster management
│   └── data/
│       ├── 2024/               # 2024 season team JSON files (32 teams)
│       ├── 2025/               # 2025 season team JSON files (legacy, 32 teams)
│       ├── 2025_5e/            # 2025 season team JSON files (5th-ed, 32 teams)
│       ├── generate_2024_data.py
│       ├── generate_2025_data.py
│       └── generate_2025_5e_data.py
├── gui/                        # React/TypeScript web frontend
│   ├── src/
│   │   ├── components/         # UI components
│   │   ├── hooks/              # React hooks (API integration)
│   │   ├── types/              # TypeScript type definitions
│   │   └── styles/             # CSS styling
│   └── ...
├── scripts/
│   ├── generate_cards.py       # CLI for card generation
│   └── requirements.txt        # Python dependencies
├── tests/                      # Test suite
│   ├── test_engine.py          # Integration tests
│   ├── test_5e_system.py       # 5th-edition system tests
│   ├── test_fac_system.py      # FAC system tests
│   ├── test_card_generator.py  # Card generation tests
│   └── test_fast_action_dice.py # Dice system tests
└── docs/                       # Documentation
    ├── getting-started.md      # Setup and installation guide
    ├── game-mechanics.md       # How the game works
    ├── player-cards.md         # Player card explanation and examples
    ├── creating-custom-players.md  # Custom player creation guide
    └── api-reference.md        # REST API documentation
```

## How It Works

### 5th Edition: The FAC Deck

The 5th-edition system uses a deck of **109 Fast Action Cards**:

| Card Type | Count | Description |
|-----------|-------|-------------|
| Standard | 96 | Numbers 1–48 (each twice: normal + out-of-bounds variant) |
| Z Cards | 13 | Special event cards (injuries, penalties, fumbles) |

Each FAC card contains 13 fields that drive all game mechanics:

| Field | Used For |
|-------|----------|
| RUN# (1–12) | RB card lookup |
| PASS# (1–48) | QB/receiver card lookup |
| SL/IL/SR/IR | Defensive blocking matchups |
| ER | End-around resolution |
| QK/SH/LG | Receiver targeting override / P.Rush trigger |
| SC | Screen pass result |
| Z RES | Special events (penalty, injury, fumble) |
| SOLO | Solitaire play calling |

**Pass Play Resolution (5th Edition):**
1. Draw FAC card
2. Check QK/SH/LG target field → may override receiver or trigger **P.Rush**
3. ER is used for end-around resolution, not normal pass sacks
4. Look up PASS# on QB card → receiver letter (A–E) / INC / INT
5. If receiver letter → look up same PASS# on receiver card → yards

**Run Play Resolution (5th Edition):**
1. Draw FAC card
2. Look up RUN# on RB card (inside/outside/sweep) → yards
3. If "(OB)" suffix → out of bounds (clock stops)
4. Check Z RES for fumbles/injuries

### Legacy: The Fast Action Dice

Two 8-sided dice (values 1–8) produce a two-digit number from 11 to 88, giving 64 possible outcomes. Each roll determines:

1. **Play Tendency** — RUN, SHORT_PASS, LONG_PASS, or BLITZ
2. **Penalty Check** — 5 specific combinations (~8% chance) trigger a penalty roll
3. **Turnover Modifier** — A separate d8 roll for turnover-related effects

### Player Cards

**5th Edition cards:**

| Position | Rows | Columns | Cell Contents |
|----------|------|---------|---------------|
| QB | 48 (Pass#) | Short, Long, Quick Pass | Receiver letter (A–E), INC, INT |
| RB | 12 (Run#) | Inside, Outside, Sweep | Yards, FUMBLE, BREAKAWAY |
| WR/TE | 48 (Pass#) | Short/Long Reception | Yards, INC |
| K | — | FG Chart (by distance), XP Rate | Success probability |
| P | — | Avg Distance, Inside-20 Rate | Distance/placement |
| DEF | — | Pass Rush, Coverage, Run Stop + letter | Ratings (0–99) |

### Grades

Players are graded A+, A, B, C, or D based on their real NFL performance. Higher grades produce better distributions on their cards — more completions, longer gains, fewer turnovers.

## Documentation

For detailed documentation, see the [docs/](docs/) directory:

- **[Getting Started](docs/getting-started.md)** — Installation, setup, running the game
- **[Game Mechanics](docs/game-mechanics.md)** — Detailed explanation of how the game works
- **[Player Cards](docs/player-cards.md)** — Understanding player cards with examples
- **[Creating Custom Players](docs/creating-custom-players.md)** — How to create your own player cards
- **[API Reference](docs/api-reference.md)** — REST API endpoint documentation

## License

This project is for educational and entertainment purposes.
