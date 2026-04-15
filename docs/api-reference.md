# API Reference

The Statis Pro Football API is built with FastAPI and provides 30+ endpoints for managing games, human play calling, special teams, roster management, and player card browsing.

## Starting the Server

```bash
python -m engine.api_server
```

The server starts at `http://localhost:8000`. Interactive API documentation is available at `http://localhost:8000/docs` (Swagger UI).

---

## Health & Root

### Root

```
GET /
```

Returns API status and version.

**Response:**
```json
{"message": "Statis Pro Football API", "version": "1.0.0"}
```

### Health Check

```
GET /health
```

Returns server health and active game count.

**Response:**
```json
{"status": "ok", "active_games": 2}
```

---

## Teams

### List Teams

```
GET /teams?season=2025_5e
```

Lists all available team abbreviations for a season.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| season | string | `2025_5e` | Season key: `2025_5e`, `2025`, or `2024` |

**Response:**
```json
{
  "teams": ["ARI", "ATL", "BAL", "BUF", "..."],
  "season": "2025_5e"
}
```

### Get Team Details

```
GET /teams/{team_abbr}?season=2025_5e
```

Returns full team data including roster and team card.

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
  "players": [...],
  "team_card": {...}
}
```

### Get Team Roster

```
GET /teams/{team_abbr}/roster?season=2025_5e
```

Returns the full roster (all player cards) for a team.

---

## Player Cards

### Get Player Card

```
GET /cards/{team_abbr}/{player_name}?season=2025_5e
```

Returns a specific player's card. Player name matching is case-insensitive.

**Example:**
```
GET /cards/KC/patrick mahomes
```

**Errors:** `404` Team or player not found

---

## Games

### Create New Game

```
POST /games/new
```

Starts a new game between two teams.

**Request Body:**
```json
{
  "home_team": "KC",
  "away_team": "BUF",
  "season": "2025_5e",
  "solitaire_home": true,
  "solitaire_away": true,
  "seed": 42
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| home_team | string | required | Home team abbreviation |
| away_team | string | required | Away team abbreviation |
| season | string | `2025_5e` | Season key |
| solitaire_home | bool | true | AI controls home team |
| solitaire_away | bool | true | AI controls away team |
| seed | int | null | Random seed for reproducible games |

**Response:**
```json
{
  "game_id": "BUF@KC_1234",
  "state": {... game state ...}
}
```

### Get Game State

```
GET /games/{game_id}
```

Returns the current state of an active game.

### Execute Single Play (AI)

```
POST /games/{game_id}/play
```

Executes one play with AI controlling both sides.

**Response:**
```json
{
  "game_id": "BUF@KC_1234",
  "play_result": {
    "play_type": "RUN",
    "yards": 5,
    "result": "GAIN",
    "description": "Isiah Pacheco runs IL for 5 yards",
    "is_touchdown": false,
    "turnover": false,
    "run_number": 7,
    "pass_number": null,
    "defense_formation": "4_3",
    "rusher": "Isiah Pacheco",
    "passer": null,
    "receiver": null,
    "bv_tv_result": "contest",
    "debug_log": [...]
  },
  "state": {... game state ...}
}
```

### Execute Human Offensive Play

```
POST /games/{game_id}/human-play
```

Executes a play with a human-specified offensive call. Defense is AI-controlled.

**Request Body:**
```json
{
  "play_type": "RUN",
  "direction": "IL",
  "formation": "UNDER_CENTER",
  "strategy": null,
  "player_name": "Isiah Pacheco"
}
```

| Field | Values |
|-------|--------|
| play_type | `RUN`, `SHORT_PASS`, `LONG_PASS`, `QUICK_PASS`, `SCREEN`, `PUNT`, `FG`, `KNEEL` |
| direction | `IL`, `IR`, `SL`, `SR` (runs); `DEEP_LEFT`, `DEEP_RIGHT` (deep pass) |
| formation | `UNDER_CENTER`, `SHOTGUN`, `I_FORM`, `TRIPS`, etc. |
| strategy | `FLOP`, `SNEAK`, `DRAW`, `PLAY_ACTION` (or null) |
| player_name | Specific QB/RB/WR name (or null for default) |

### Execute Human Defensive Play

```
POST /games/{game_id}/human-defense
```

Executes a play with a human-specified defensive call. Offense is AI-controlled.

**Request Body:**
```json
{
  "formation": "4_3",
  "defensive_play": "PASS_DEFENSE",
  "defensive_strategy": "NONE",
  "blitz_players": ["Patrick Queen", "Roquan Smith"]
}
```

| Field | Values |
|-------|--------|
| formation | `4_3`, `3_4`, `NICKEL`, `GOAL_LINE` |
| defensive_play | `PASS_DEFENSE`, `PREVENT_DEFENSE`, `RUN_DEFENSE_NO_KEY`, `RUN_DEFENSE_KEY_BACK_1/2/3`, `BLITZ` |
| defensive_strategy | `NONE`, `DOUBLE_COVERAGE`, `TRIPLE_COVERAGE`, `ALT_DOUBLE_COVERAGE` |
| blitz_players | List of 2–5 LB/DB player names (required for BLITZ) |

### Simulate Drive

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
    "drive_log": ["...", "..."]
  },
  "state": {... game state ...}
}
```

Drive result values: `TD`, `FG`, `PUNT`, `TURNOVER`, `DOWNS`, `MISSED_FG`, `END_HALF`, `CHANGE`

### Simulate Entire Game

```
POST /games/{game_id}/simulate
```

Simulates the entire remaining game.

---

## Personnel & Roster Management

### Get Personnel

```
GET /games/{game_id}/personnel
```

Returns the current personnel for both teams, including starter positions, injury status, and player card fields.

**Response:**
```json
{
  "home": {
    "offense": {
      "QB": {...player brief...},
      "RB1": {...},
      "WR1": {...},
      ...
    },
    "offensive_line": [...],
    "defense": [...],
    "returners": {"kick": {...}, "punt": {...}},
    "kick_returners": [...],
    "punt_returners": [...]
  },
  "away": {...}
}
```

### Get Starting Lineup

```
GET /games/{game_id}/starting-lineup?team=home
```

Returns the current starting lineup for the specified team (home or away).

### Set Starting Lineup

```
POST /games/{game_id}/starting-lineup
```

Set the starting lineup for a team before or during the game.

**Request Body:**
```json
{
  "team": "home",
  "offense": {
    "QB": "Patrick Mahomes",
    "RB": "Isiah Pacheco"
  },
  "defense": ["Chris Jones", "George Karlaftis", "...]
}
```

### Substitute Player (Offense)

```
POST /games/{game_id}/substitute
```

Substitute a player on the current possession team.

**Request Body:**
```json
{
  "position": "RB",
  "player_out": "Isiah Pacheco",
  "player_in": "Clyde Edwards-Helaire"
}
```

### Substitute Player (Defense)

```
POST /games/{game_id}/substitute-defense
```

Same format as `/substitute` but for the defending team.

### Get Depth Chart

```
GET /games/{game_id}/depth-chart?team=home
```

Returns the full depth chart for a team, grouped by position (QB, RB, WR, TE, OL, K, P, DL, LB, DB).

### Change Player Position

```
POST /games/{game_id}/position-change
```

Move a player to a compatible position (e.g., WR to TE).

**Request Body:**
```json
{
  "player_name": "Noah Gray",
  "new_position": "TE"
}
```

### Get Display Boxes

```
GET /games/{game_id}/display-boxes
```

Returns the current defensive display box assignments (A–O boxes) for both teams, reflecting the 5E defensive display layout.

**Response:**
```json
{
  "home": {
    "A": {...player...}, "B": null, "C": {...}, ..., "O": {...}
  },
  "away": {...}
}
```

---

## Game Log

### Get Game Log

```
GET /games/{game_id}/gamelog
```

Returns the full game log as structured data, including play-by-play and drive summaries.

**Response:**
```json
{
  "game_id": "BUF@KC_1234",
  "log": ["Q1 - 15:00 - Coin flip: away team receives", "..."],
  "drives": [
    {
      "team": "away",
      "plays": 6,
      "yards": 45,
      "result": "FG",
      "points_scored": 3,
      "drive_log": [...]
    }
  ]
}
```

### Download Game Log

```
GET /games/{game_id}/gamelog/download
```

Downloads the full game log as a plain text file, including boxscore (passing/rushing/receiving stats, penalties, turnovers).

---

## Special Teams

### Timeout

```
POST /games/{game_id}/timeout?team=possession
```

Call a timeout for the specified team.

| Parameter | Values | Description |
|-----------|--------|-------------|
| team | `home`, `away`, `possession` | Which team calls the timeout (default: team in possession) |

**Errors:** `400` No timeouts remaining

### Onside Kick

```
POST /games/{game_id}/onside-kick
```

**Request Body:**
```json
{
  "onside_defense": false
}
```

`onside_defense`: Set to `true` if the receiving team declared onside defense.

### Squib Kick

```
POST /games/{game_id}/squib-kick
```

Execute a squib kick (low bouncer to avoid returner).

### Fake Punt

```
POST /games/{game_id}/fake-punt
```

Execute a fake punt (once per game).

### Fake Field Goal

```
POST /games/{game_id}/fake-fg
```

Execute a fake field goal (once per game; not available in final 2 minutes).

### Coffin Corner Punt

```
POST /games/{game_id}/coffin-corner
```

Execute a coffin corner punt attempt.

**Request Body:**
```json
{
  "deduction": 15
}
```

`deduction`: Yardage deduction from normal punt distance (10–25 yards).

### All-Out Punt Rush

```
POST /games/{game_id}/all-out-punt-rush
```

Defensive call to rush all players at the punt.

### Two-Point Conversion

```
POST /games/{game_id}/two-point-conversion
```

Execute a two-point conversion attempt after a touchdown.

**Request Body:**
```json
{
  "play_type": "SHORT_PASS",
  "direction": "MIDDLE",
  "player_name": ""
}
```

---

## Advanced 5E Features

### Declare Two-Minute Offense

```
POST /games/{game_id}/two-minute-offense
```

Manually declare two-minute offense mode (also triggered automatically when trailing with ≤ 2 minutes remaining).

### Activate Big Play Defense

```
POST /games/{game_id}/big-play-defense
```

Activate Big Play Defense for eligible teams (9+ wins in prior season). Can be used once per defensive series.

**Request Body:**
```json
{
  "team": "defense"
}
```

`team`: `home`, `away`, or `defense` (auto-detect).

**Errors:** `400` Team not eligible or already used

---

## Game State Object

The game state returned by all game endpoints:

| Field | Type | Description |
|-------|------|-------------|
| home_team | string | Home team abbreviation |
| away_team | string | Away team abbreviation |
| quarter | int | Current quarter (1–4, 5 = OT) |
| time_remaining | int | Seconds remaining in the quarter |
| possession | string | `"home"` or `"away"` |
| yard_line | int | Distance from own end zone (1–99) |
| down | int | Current down (1–4) |
| distance | int | Yards needed for first down |
| score | object | `{"home": int, "away": int}` |
| is_over | bool | Whether the game has ended |
| timeouts_home | int | Timeouts remaining for home team (0–3) |
| timeouts_away | int | Timeouts remaining for away team (0–3) |
| last_plays | array | Last 20 play descriptions |
| injuries | object | `{player_name: plays_remaining}` |
| penalties | object | `{"home": count, "away": count}` |
| penalty_yards | object | `{"home": yards, "away": yards}` |
| turnovers | object | `{"home": count, "away": count}` |
| player_stats | object | `{player_name: {stat_type: value}}` |

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

| Status Code | Meaning |
|-------------|---------|
| 400 | Bad request (e.g., game already over, timeout not available) |
| 404 | Resource not found (team, player, or game) |
| 422 | Validation error (invalid request body) |
| 500 | Internal server error |

---

## CORS

The API allows all origins (`*`) for development. In production, restrict this to your frontend's domain.

---

## Example: Full Game via API

```bash
# 1. Start a game
GAME=$(curl -s -X POST http://localhost:8000/games/new \
  -H "Content-Type: application/json" \
  -d '{"home_team": "KC", "away_team": "SF", "season": "2025_5e"}')
GAME_ID=$(echo $GAME | python -c "import sys,json; print(json.load(sys.stdin)['game_id'])")

# 2. Execute plays one at a time (AI)
curl -s -X POST http://localhost:8000/games/$GAME_ID/play | python -m json.tool

# 3. Execute a human offensive play
curl -s -X POST http://localhost:8000/games/$GAME_ID/human-play \
  -H "Content-Type: application/json" \
  -d '{"play_type": "RUN", "direction": "IL", "formation": "UNDER_CENTER", "player_name": "Isiah Pacheco"}' \
  | python -m json.tool

# 4. Execute a human defensive play
curl -s -X POST http://localhost:8000/games/$GAME_ID/human-defense \
  -H "Content-Type: application/json" \
  -d '{"formation": "NICKEL", "defensive_play": "PASS_DEFENSE", "defensive_strategy": "DOUBLE_COVERAGE"}' \
  | python -m json.tool

# 5. Call a timeout
curl -s -X POST "http://localhost:8000/games/$GAME_ID/timeout?team=possession" | python -m json.tool

# 6. Or simulate a whole drive
curl -s -X POST http://localhost:8000/games/$GAME_ID/simulate-drive | python -m json.tool

# 7. Or simulate the rest of the game
curl -s -X POST http://localhost:8000/games/$GAME_ID/simulate | python -m json.tool

# 8. Download the game log with boxscore
curl -s http://localhost:8000/games/$GAME_ID/gamelog/download -o game_log.txt
```
