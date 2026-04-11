# Statis Pro Football

A digital implementation of the classic Statis Pro Football tabletop game, featuring a Python game engine with AI play calling, a React/TypeScript web GUI, and complete player cards for all 32 NFL teams across multiple seasons.

## Overview

Statis Pro Football is a dice-based football simulation where play outcomes are determined by rolling Fast Action Dice (an 11–88 system using two 8-sided dice) and consulting player cards. Each player's card reflects their real-world NFL statistics, translating them into 64-slot lookup tables that drive realistic game outcomes.

### Features

- **Complete Game Engine** — Full football simulation with drives, scoring, penalties, turnovers, clock management, and overtime
- **AI Play Calling** — Solitaire mode with intelligent play selection based on game situation, down/distance, and score
- **Player Card System** — 64-slot cards generated from real NFL statistics for QBs, RBs, WRs, TEs, kickers, punters, and defenders
- **Two Seasons of Data** — 2024 (2023 NFL stats) and 2025 (2024 NFL stats) with all 32 teams
- **Web GUI** — React/TypeScript frontend with game board, play-by-play log, dice roller, and card viewer
- **REST API** — FastAPI backend with endpoints for game management, dice rolling, and card browsing
- **Comprehensive Tests** — 100+ tests covering dice distribution, card generation, game mechanics, and team loading

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

### Run a Quick Game (Python)

```python
from engine.team import Team
from engine.game import Game

# Load two teams
home = Team.load("KC", 2025)   # Kansas City Chiefs
away = Team.load("BUF", 2025)  # Buffalo Bills

# Simulate a full game
game = Game(home, away)
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
# Generate 2025 season cards (2024 NFL stats)
python scripts/generate_cards.py --season 2025

# Generate 2024 season cards (2023 NFL stats)
python scripts/generate_cards.py --season 2024
```

### Run Tests

```bash
python -m pytest tests/ -v
```

## Project Structure

```
Statis-Pro-Football/
├── engine/                     # Python game engine
│   ├── api_server.py           # FastAPI REST server
│   ├── card_generator.py       # Generate player cards from stats
│   ├── charts.py               # Penalty, return, and recovery charts
│   ├── fast_action_dice.py     # 11-88 dice system
│   ├── game.py                 # Core game state and logic
│   ├── play_resolver.py        # Play outcome resolution
│   ├── player_card.py          # Player card data model
│   ├── solitaire.py            # AI play calling
│   ├── stats_fetcher.py        # Stats lookup with fallback data
│   ├── team.py                 # Team and roster management
│   └── data/
│       ├── 2024/               # 2024 season team JSON files (32 teams)
│       ├── 2025/               # 2025 season team JSON files (32 teams)
│       ├── generate_2024_data.py
│       └── generate_2025_data.py
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

### The Fast Action Dice

Two 8-sided dice (values 1–8) produce a two-digit number from 11 to 88, giving 64 possible outcomes. Each roll determines:

1. **Play Tendency** — RUN, SHORT_PASS, LONG_PASS, or BLITZ (mapped from the dice combination)
2. **Penalty Check** — 5 specific combinations (~8% chance) trigger a penalty roll
3. **Turnover Modifier** — A separate d8 roll for turnover-related effects

### Player Cards

Every player has a card with 64 slots (matching the dice outcomes). When a play is called:

1. Roll the Fast Action Dice → get a slot number (e.g., "37")
2. Look up that slot on the relevant player's card column
3. The slot tells you the result: COMPLETE for 12 yards, FUMBLE, SACK for -5, etc.

Different positions use different card columns:

| Position | Card Columns |
|----------|-------------|
| QB | Short Pass, Long Pass, Screen Pass |
| RB | Inside Run, Outside Run |
| WR/TE | Short Reception, Long Reception |
| K | FG Chart (by distance), XP Rate |
| P | Avg Distance, Inside-20 Rate |
| DEF | Pass Rush, Coverage, Run Stop ratings |

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
