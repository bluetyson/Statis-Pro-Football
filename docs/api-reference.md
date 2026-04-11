# API Reference

The Statis Pro Football API is built with FastAPI and provides endpoints for managing games, browsing teams, and viewing player cards.

## Starting the Server

```bash
python -m engine.api_server
```

The server starts at `http://localhost:8000`. Interactive API documentation is available at `http://localhost:8000/docs` (Swagger UI).

## Endpoints

### Health Check

```
GET /
```

Returns API status and version.

**Response:**
```json
{
  "message": "Statis Pro Football API",
  "version": "1.0.0"
}
```

---

```
GET /health
```

Returns server health and active game count.

**Response:**
```json
{
  "status": "ok",
  "active_games": 2
}
```

---

### Teams

#### List Teams

```
GET /teams?season=2025
```

Lists all available team abbreviations for a season.

**Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| season | int | 2025 | Season year (2024 or 2025) |

**Response:**
```json
{
  "teams": ["ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC", "LAC", "LAR", "LV", "MIA", "MIN", "NE", "NO", "NYG", "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WSH"],
  "season": 2025
}
```

---

#### Get Team Details

```
GET /teams/{team_abbr}?season=2025
```

Returns full team data including roster.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| team_abbr | string | Team abbreviation (e.g., "KC", "BUF") |
| season | int | Season year (default: 2025) |

**Response:**
```json
{
  "abbreviation": "KC",
  "city": "Kansas City",
  "name": "Chiefs",
  "conference": "AFC",
  "division": "West",
  "record": {"wins": 0, "losses": 0, "ties": 0},
  "offense_rating": 88,
  "defense_rating": 85,
  "players": [
    {
      "name": "Patrick Mahomes",
      "position": "QB",
      "number": 15,
      "team": "KC",
      "overall_grade": "A",
      "short_pass": {"11": {"result": "SACK", "yards": -4, "td": false}, "...": "..."},
      "long_pass": {"11": {"result": "COMPLETE", "yards": 22, "td": false}, "...": "..."},
      "screen_pass": {"...": "..."},
      "stats_summary": {"comp_pct": 0.672, "ypa": 8.8, "int_rate": 0.016, "sack_rate": 0.055}
    }
  ]
}
```

**Errors:**
- `404`: Team not found

---

#### Get Team Roster

```
GET /teams/{team_abbr}/roster?season=2025
```

Returns just the roster (all player cards) for a team.

**Response:**
```json
{
  "team": "KC",
  "players": [
    {"name": "Patrick Mahomes", "position": "QB", "number": 15, "...": "..."},
    {"name": "Isiah Pacheco", "position": "RB", "number": 10, "...": "..."}
  ]
}
```

---

### Player Cards

#### Get Player Card

```
GET /cards/{team_abbr}/{player_name}?season=2025
```

Returns a specific player's card. Player name matching is case-insensitive.

**Example:**
```
GET /cards/KC/patrick mahomes
```

**Response:**
```json
{
  "name": "Patrick Mahomes",
  "position": "QB",
  "number": 15,
  "team": "KC",
  "overall_grade": "A",
  "short_pass": {
    "11": {"result": "SACK", "yards": -4, "td": false},
    "12": {"result": "INCOMPLETE", "yards": 0, "td": false},
    "...": "..."
  },
  "long_pass": {"...": "..."},
  "screen_pass": {"...": "..."},
  "inside_run": {},
  "outside_run": {},
  "short_reception": {},
  "long_reception": {},
  "fg_chart": {},
  "xp_rate": 0.95,
  "avg_distance": 44.0,
  "inside_20_rate": 0.35,
  "pass_rush_rating": 50,
  "coverage_rating": 50,
  "run_stop_rating": 50,
  "stats_summary": {"comp_pct": 0.672, "ypa": 8.8, "int_rate": 0.016, "sack_rate": 0.055}
}
```

**Errors:**
- `404`: Team or player not found

---

### Games

#### Create New Game

```
POST /games/new
```

Starts a new game between two teams.

**Request Body:**
```json
{
  "home_team": "KC",
  "away_team": "BUF",
  "season": 2025,
  "solitaire_home": true,
  "solitaire_away": true
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| home_team | string | required | Home team abbreviation |
| away_team | string | required | Away team abbreviation |
| season | int | 2025 | Season year |
| solitaire_home | bool | true | AI controls home team |
| solitaire_away | bool | true | AI controls away team |

**Response:**
```json
{
  "game_id": "BUF@KC_1234",
  "state": {
    "home_team": "KC",
    "away_team": "BUF",
    "quarter": 1,
    "time_remaining": 900,
    "possession": "away",
    "yard_line": 25,
    "down": 1,
    "distance": 10,
    "score": {"home": 0, "away": 0},
    "is_over": false,
    "last_plays": ["Coin flip: away team receives", "Kickoff - touchback, ball at 25-yard line"]
  }
}
```

**Errors:**
- `404`: Team not found

---

#### Get Game State

```
GET /games/{game_id}
```

Returns the current state of an active game.

**Response:**
```json
{
  "game_id": "BUF@KC_1234",
  "state": {
    "home_team": "KC",
    "away_team": "BUF",
    "quarter": 2,
    "time_remaining": 450,
    "possession": "home",
    "yard_line": 35,
    "down": 2,
    "distance": 7,
    "score": {"home": 7, "away": 3},
    "is_over": false,
    "last_plays": ["...last 10 plays..."]
  }
}
```

**Errors:**
- `404`: Game not found

---

#### Execute Single Play

```
POST /games/{game_id}/play
```

Executes one play in the game. The AI calls the play based on the game situation.

**Response:**
```json
{
  "game_id": "BUF@KC_1234",
  "play_result": {
    "play_type": "PASS",
    "yards": 12,
    "result": "COMPLETE",
    "description": "Patrick Mahomes completes to Travis Kelce for 12 yards",
    "is_touchdown": false,
    "turnover": false
  },
  "state": {"...current game state..."}
}
```

**Errors:**
- `400`: Game is over
- `404`: Game not found

---

#### Simulate Drive

```
POST /games/{game_id}/simulate-drive
```

Simulates an entire drive (multiple plays until score, punt, turnover, or possession change).

**Response:**
```json
{
  "game_id": "BUF@KC_1234",
  "drive": {
    "team": "home",
    "plays": 8,
    "yards": 75,
    "result": "TD",
    "points_scored": 7,
    "drive_log": [
      "Isiah Pacheco runs middle for 4 yards",
      "Patrick Mahomes completes to Rashee Rice for 12 yards",
      "..."
    ]
  },
  "state": {"...current game state..."}
}
```

Drive result values: `TD`, `FG`, `PUNT`, `TURNOVER`, `DOWNS`, `MISSED_FG`, `END_HALF`, `CHANGE`

---

#### Simulate Entire Game

```
POST /games/{game_id}/simulate
```

Simulates the entire remaining game.

**Response:**
```json
{
  "game_id": "BUF@KC_1234",
  "final_score": {
    "home": 27,
    "away": 24
  },
  "state": {
    "...final game state...",
    "is_over": true
  }
}
```

**Errors:**
- `400`: Game is already over
- `404`: Game not found

---

### Dice

#### Roll Dice

```
POST /dice/roll
```

Rolls the Fast Action Dice independently (not tied to a game).

**Response:**
```json
{
  "two_digit": 37,
  "tens": 3,
  "ones": 7,
  "play_tendency": "LONG_PASS",
  "penalty_check": true,
  "turnover_modifier": 5
}
```

---

## Game State Object

The game state returned by all game endpoints has this structure:

| Field | Type | Description |
|-------|------|-------------|
| home_team | string | Home team abbreviation |
| away_team | string | Away team abbreviation |
| quarter | int | Current quarter (1–4, 5 for OT) |
| time_remaining | int | Seconds remaining in the quarter |
| possession | string | "home" or "away" |
| yard_line | int | Distance from own end zone (1–99) |
| down | int | Current down (1–4) |
| distance | int | Yards needed for first down |
| score | object | `{"home": int, "away": int}` |
| is_over | bool | Whether the game has ended |
| last_plays | array | Last 10 play descriptions |

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

| Status Code | Meaning |
|-------------|---------|
| 400 | Bad request (e.g., game already over) |
| 404 | Resource not found (team, player, or game) |
| 422 | Validation error (invalid request body) |
| 500 | Internal server error |

## CORS

The API allows all origins (`*`) for development. In production, you should restrict this to your frontend's domain.

## Example: Full Game via API

```bash
# 1. Start a game
GAME=$(curl -s -X POST http://localhost:8000/games/new \
  -H "Content-Type: application/json" \
  -d '{"home_team": "KC", "away_team": "SF"}')
GAME_ID=$(echo $GAME | python -c "import sys,json; print(json.load(sys.stdin)['game_id'])")

# 2. Execute plays one at a time
curl -s -X POST http://localhost:8000/games/$GAME_ID/play | python -m json.tool

# 3. Or simulate a whole drive
curl -s -X POST http://localhost:8000/games/$GAME_ID/simulate-drive | python -m json.tool

# 4. Or simulate the rest of the game
curl -s -X POST http://localhost:8000/games/$GAME_ID/simulate | python -m json.tool
```
