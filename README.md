# Statis Pro Football

A digital implementation of the classic Statis Pro Football tabletop game, featuring a Python game engine with AI play calling, a React/TypeScript web GUI, and complete player cards for all 32 NFL teams across multiple seasons.

**Status:** Feature-complete. Core 5E engine is fully implemented, the GUI includes complete human play calling with all 5E features, and 598+ tests are passing.

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
- **Web GUI** — React/TypeScript frontend with human offensive/defensive play calling, formation grid, player substitutions, depth chart, display box assignments, injury tracking, endurance display, player stats panel, FAC card display, BV vs TV battles, and real-time game state
- **REST API** — FastAPI backend with 30+ endpoints for game management, human play calling, special teams, roster management, and card browsing
- **Comprehensive Tests** — 598+ tests covering dice/deck distribution, card generation, game mechanics, GUI-facing API behavior, kickoff returns, fumble logging, injury/endurance, blitz/pass-rush, blocking matchups, and 5E rules

## Implementation Status

- **Engine**: 146/146 5E rules (100%) implemented
- **GUI**: 88/88 audited features (100%) implemented
- **Tests**: 598+ tests passing
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

# Load two teams (primary: 5th-edition format)
home = Team.load("KC", "2025_5e")   # Kansas City Chiefs
away = Team.load("BUF", "2025_5e")  # Buffalo Bills

# 5th Edition mode (109-card FAC deck) — default and recommended
game = Game(home, away, use_5e=True, seed=42)
state = game.simulate_game()
print(f"Final Score: {state.away_team} {state.score.away} - {state.home_team} {state.score.home}")

# Legacy mode (d8×d8 dice) — also supported
home_legacy = Team.load("KC", "2025")
away_legacy = Team.load("BUF", "2025")
game = Game(home_legacy, away_legacy, use_5e=False)
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
# Generate 2025 season cards (5th-edition 48/12-slot format) — primary
python engine/data/generate_2025_5e_data.py

# Generate 2025 season cards (legacy 64-slot format)
python engine/data/generate_2025_data.py
```

### Run Tests

```bash
# Run all tests (excluding API server tests which require fastapi installed)
python3 -m pytest tests/ -x -q --ignore=tests/test_api_server.py -k "not test_oob"

# Run all tests including API server tests
python3 -m pytest tests/ -x -q
```

## Project Structure

```
Statis-Pro-Football/
├── engine/                     # Python game engine
│   ├── api_server.py           # FastAPI REST server (30+ endpoints)
│   ├── card_generator.py       # Generate player cards (legacy + 5th-ed)
│   ├── charts.py               # Penalty, return, and recovery charts
│   ├── fac_deck.py             # 109-card FAC deck (5th Edition)
│   ├── fac_distributions.py    # Card distribution tables (48/12/64-slot)
│   ├── fast_action_dice.py     # 11-88 dice system (legacy)
│   ├── game.py                 # Core game state and logic
│   ├── play_resolver.py        # Play outcome resolution (legacy + 5th-ed)
│   ├── play_types.py           # 5E defensive/offensive play type enums
│   ├── player_card.py          # Player card data model
│   ├── solitaire.py            # AI play calling (legacy + SOLO-based)
│   ├── stats_fetcher.py        # Stats lookup with fallback data
│   ├── team.py                 # Team and roster management
│   └── data/
│       ├── 2024/               # 2024 season team JSON files (32 teams, legacy)
│       ├── 2025/               # 2025 season team JSON files (legacy, 32 teams)
│       ├── 2025_5e/            # 2025 season team JSON files (5th-ed, 32 teams) ← primary
│       ├── generate_2024_data.py
│       ├── generate_2025_data.py
│       └── generate_2025_5e_data.py
├── gui/                        # React/TypeScript web frontend
│   ├── src/
│   │   ├── components/         # UI components (20+ components)
│   │   │   ├── BlitzPlayerSelector.tsx   # Blitz player selection
│   │   │   ├── DefensivePlayCaller.tsx   # Human defensive play calling
│   │   │   ├── DepthChart.tsx            # Depth chart management
│   │   │   ├── DisplayBoxes.tsx          # 5E defensive display (A-O boxes)
│   │   │   ├── FACCardDisplay.tsx        # FAC card visual
│   │   │   ├── GameBoard.tsx             # Main game board
│   │   │   ├── HumanPlayCaller.tsx       # Human offensive play calling
│   │   │   ├── LetterBoards.tsx          # Formation grid
│   │   │   ├── StartingLineup.tsx        # Lineup management
│   │   │   ├── SubstitutionPanel.tsx     # Player substitutions
│   │   │   └── ...
│   │   ├── hooks/              # React hooks (API integration)
│   │   ├── types/              # TypeScript type definitions
│   │   └── styles/             # CSS styling
│   └── ...
├── scripts/
│   ├── generate_cards.py       # CLI for card generation
│   └── requirements.txt        # Python dependencies
├── tests/                      # Test suite (598+ tests)
│   ├── test_5e_kickoff_return.py
│   ├── test_5e_rules.py
│   ├── test_5e_system.py
│   ├── test_api_server.py
│   ├── test_blitz_pass_rush_and_receivers.py
│   ├── test_blocking_matchup_resolution.py
│   ├── test_card_generator.py
│   ├── test_engine.py
│   ├── test_fac_system.py
│   ├── test_fg_kickoff_and_run_middle.py
│   ├── test_fumble_return_logging.py
│   ├── test_human_defense_override.py
│   ├── test_injury_grid_and_endurance.py
│   └── test_kickoff_td_and_play_sync.py
└── docs/                       # Documentation
    ├── getting-started.md      # Setup and installation guide
    ├── game-mechanics.md       # How the game works
    ├── player-cards.md         # Player card explanation and examples
    ├── creating-custom-players.md  # Custom player creation guide
    ├── api-reference.md        # REST API documentation
    ├── 5e-rules-audit.md       # Complete 5E rules implementation tracking
    └── gui-audit.md            # GUI feature implementation tracking
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
- **[Game Mechanics](docs/game-mechanics.md)** — Detailed explanation of how the 5E game works
- **[Player Cards](docs/player-cards.md)** — Understanding 5E player cards with examples
- **[Creating Custom Players](docs/creating-custom-players.md)** — How to create your own player cards
- **[API Reference](docs/api-reference.md)** — REST API endpoint documentation
- **[5E Rules Audit](docs/5e-rules-audit.md)** — Complete mapping of all 146 5E rules to implementation
- **[GUI Audit](docs/gui-audit.md)** — Tracking of 88 GUI features across 11 categories

## Advanced Rules (Optional / House Rules)

The following rules are implemented as optional extensions beyond the core 5th-edition rulebook:

- **Shotgun Formation (Offense)** — When the QB declares Shotgun, he receives +1 to all
  completion ranges and +1 to the offensive pass-block sum for all pass-rush checks on that
  play.  Play-Action passes are **not allowed** from Shotgun (the defense cannot be fooled
  by a run fake from an obvious passing formation).

- **Goal Line Defensive Package** — Activating the GOAL_LINE package selects the 5 players
  (from DL + LB combined) with the highest combined tackle + pass-rush ratings and places
  them on the defensive line.  Three additional LBs fill the second wave.  The remaining 3
  spots are filled by DBs, explicitly **excluding** any Free Safety (FS-position) players —
  they are removed from the field for this package.  The total on-field unit is 5 + 3 + 3 = 11.

- **Extra Pass Blocking (Backs in to Block)** — Before the snap on any pass play, the offense
  may declare any or all of its backs as blockers.  Each blocking back adds +2 to the QB's
  Completion Range but **cannot be targeted**; if the FAC redirects the pass to a blocking
  back, the pass is **incomplete**.  The AI applies this decision situationally (base ~30 %
  chance per pass play; rises to ~50 % on 3rd/4th & long or when protecting a late lead).
  All blocking-back decisions are logged in the play log.

- **Sack Credit Assignment** — When a sack results from a Pass Rush, individual credit is
  assigned to the defender most responsible using a weighted random draw:
  - **Pass-rush line** (Row 1, boxes A-E): each occupied DL box is a candidate weighted by
    the player's `pass_rush_rating`.  Players with high pass-rush ratings (> 2) are
    therefore the strongest contributors and are typically placed on the line.
  - **Blitzers** (Row 2/3 boxes): any blitzing player is also a candidate with fixed weight 2
    (their 5E blitz PR value).
  - `random.choices` draws one box from the weighted pool.  If two players occupy that
    box, each receives a **half sack** (0.5); otherwise the sole occupant gets a **full sack**.
  - **Fallback**: if no weighted candidates are found, credit goes to the highest-rated pass
    rusher in the whole defense.  Ties are split equally (half sack each, even if > 2 players).
  - The sacker's name appears in the play log (e.g. "Josh Allen sacked by Myles Garrett! 6 yard loss.")
    and in the end-of-game SACKS section of the boxscore.

- **Tackle Credit Assignment** — Individual tackle credit is assigned on every run play and
  completed pass.  The algorithm (house rule):
  - **Direct box assignment**: when the blocking matchup on the FAC card identified a
    specific defended box, that box's player(s) get the tackle.  Two players in a box →
    half tackle each (0.5); two boxes each with one player → half tackle each.
  - **Weighted random fallback**: when boxes are empty or the matchup is not box-based, a
    weighted draw over all occupied defensive boxes is used.  Weights vary by play type:
    - *Inside run*: DTs (B/C/D) and ILB/MLB (G/H/I) most likely.
    - *Sweep*: DEs (A/E) and OLBs (F/J) most likely.
    - *Long pass*: CBs (K/O) and FS (M) overwhelmingly likely; covering defender doubled.
    - *Short pass*: mostly DBs and LBs; covering defender doubled.
    - *Quick pass*: more even across all rows; covering defender doubled.
    - *Screen*: outside players (OLBs F/J and DEs A/E) most likely.
  - Tackle totals (whole and fractional) appear in the end-of-game TACKLES section of the
    boxscore and are logged in the play log.

- **Fumble Recovery Assignment** — When a fumble is recovered by the defense, a specific
  player is selected as the recoverer:
  - The identified tackler for that play is the most likely recoverer (their weight doubled).
  - All other defenders are secondary candidates weighted by play type (same distribution
    as tackle assignment — the nearest defenders are most likely to pick up the ball).
  - The recoverer's name appears in the play description ("... [Name] recovers for the defense!")
    and in the end-of-game FUMBLE RECOVERIES section of the boxscore.

## Future Rules / Potential Extensions

The following rules do not appear in the 5th-edition rulebook but may be added as optional house rules in a future release:

- ~~**Shotgun Formation (Offense)**~~ — Now implemented as an advanced rule (see above).

- ~~**Sack Credit Assignment**~~ — Now implemented as an advanced rule (see above).

- ~~**Tackle Credit Assignment**~~ — Now implemented as an advanced rule (see above).

- ~~**Fumble Recovery Assignment**~~ — Now implemented as an advanced rule (see above).

- **Special Teams Individual Credit** — Fumble recoveries, tackles, and blocks on kickoff/
  punt returns could be assigned to individual special-teams personnel (backup roster players).
  Currently special-teams fumble recoveries are team-level only; a future extension could
  draw from the depth chart to assign individual credit consistent with how game-play
  fumble recoveries are handled.

## License

This project is for educational and entertainment purposes.
