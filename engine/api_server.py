"""FastAPI server for Statis Pro Football engine."""
import os
import random
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .game import Game, GameState
from .team import Team, list_available_teams
from .fast_action_dice import FastActionDice, roll as dice_roll
from .solitaire import SolitaireAI, GameSituation
from .card_generator import CardGenerator

app = FastAPI(
    title="Statis Pro Football API",
    description="Digital game engine for Statis Pro Football",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_active_games: Dict[str, Game] = {}
_dice = FastActionDice()
_ai = SolitaireAI()
_gen = CardGenerator()


# ─── Request / Response Models ──────────────────────────────────────────────

class NewGameRequest(BaseModel):
    home_team: str
    away_team: str
    season: int = 2025
    solitaire_home: bool = True
    solitaire_away: bool = True


class PlayCallRequest(BaseModel):
    game_id: str
    play_type: Optional[str] = None


# ─── Endpoints ───────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "Statis Pro Football API", "version": "1.0.0"}


@app.get("/teams")
def get_teams(season: int = 2025):
    """List all available teams."""
    teams = list_available_teams(season)
    return {"teams": sorted(teams), "season": season}


@app.get("/teams/{team_abbr}")
def get_team(team_abbr: str, season: int = 2025):
    """Get team data."""
    try:
        team = Team.load(team_abbr.upper(), season)
        return team.to_dict()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Team {team_abbr} not found")


@app.get("/teams/{team_abbr}/roster")
def get_roster(team_abbr: str, season: int = 2025):
    """Get team roster."""
    try:
        team = Team.load(team_abbr.upper(), season)
        return {
            "team": team.abbreviation,
            "players": [p.to_dict() for p in team.roster.all_players()],
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Team {team_abbr} not found")


@app.post("/games/new")
def new_game(request: NewGameRequest):
    """Start a new game."""
    try:
        home = Team.load(request.home_team.upper(), request.season)
        away = Team.load(request.away_team.upper(), request.season)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    game = Game(home, away, request.solitaire_home, request.solitaire_away)
    game_id = f"{request.away_team}@{request.home_team}_{random.randint(1000, 9999)}"
    _active_games[game_id] = game

    return {
        "game_id": game_id,
        "state": _serialize_state(game.state),
    }


@app.get("/games/{game_id}")
def get_game(game_id: str):
    """Get current game state."""
    game = _get_game(game_id)
    return {"game_id": game_id, "state": _serialize_state(game.state)}


@app.post("/games/{game_id}/play")
def execute_play(game_id: str):
    """Execute a single play."""
    game = _get_game(game_id)

    if game.state.is_over:
        raise HTTPException(status_code=400, detail="Game is over")

    result = game.execute_play()

    return {
        "game_id": game_id,
        "play_result": {
            "play_type": result.play_type,
            "yards": result.yards_gained,
            "result": result.result,
            "description": result.description,
            "is_touchdown": result.is_touchdown,
            "turnover": result.turnover,
        },
        "state": _serialize_state(game.state),
    }


@app.post("/games/{game_id}/simulate-drive")
def simulate_drive(game_id: str):
    """Simulate an entire drive."""
    game = _get_game(game_id)

    if game.state.is_over:
        raise HTTPException(status_code=400, detail="Game is over")

    drive = game.simulate_drive()

    return {
        "game_id": game_id,
        "drive": {
            "team": drive.team,
            "plays": drive.plays,
            "yards": drive.yards,
            "result": drive.result,
            "points_scored": drive.points_scored,
            "drive_log": drive.drive_log,
        },
        "state": _serialize_state(game.state),
    }


@app.post("/games/{game_id}/simulate")
def simulate_game(game_id: str):
    """Simulate the entire game."""
    game = _get_game(game_id)

    if game.state.is_over:
        raise HTTPException(status_code=400, detail="Game is already over")

    state = game.simulate_game()

    return {
        "game_id": game_id,
        "final_score": {
            "home": state.score.home,
            "away": state.score.away,
        },
        "state": _serialize_state(state),
    }


@app.post("/dice/roll")
def roll_dice():
    """Roll the fast action dice."""
    result = dice_roll()
    return {
        "two_digit": result.two_digit,
        "tens": result.tens,
        "ones": result.ones,
        "play_tendency": result.play_tendency.value,
        "penalty_check": result.penalty_check,
        "turnover_modifier": result.turnover_modifier,
    }


@app.get("/cards/{team_abbr}/{player_name}")
def get_player_card(team_abbr: str, player_name: str, season: int = 2025):
    """Get a player's card."""
    try:
        team = Team.load(team_abbr.upper(), season)
        for p in team.roster.all_players():
            if p.player_name.lower() == player_name.lower():
                return p.to_dict()
        raise HTTPException(status_code=404, detail=f"Player {player_name} not found")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Team {team_abbr} not found")


@app.get("/health")
def health():
    return {"status": "ok", "active_games": len(_active_games)}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_game(game_id: str) -> Game:
    game = _active_games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    return game


def _serialize_state(state: GameState) -> dict:
    return {
        "home_team": state.home_team,
        "away_team": state.away_team,
        "quarter": state.quarter,
        "time_remaining": state.time_remaining,
        "possession": state.possession,
        "yard_line": state.yard_line,
        "down": state.down,
        "distance": state.distance,
        "score": {"home": state.score.home, "away": state.score.away},
        "is_over": state.is_over,
        "last_plays": state.play_log[-10:] if state.play_log else [],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
