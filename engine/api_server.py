"""FastAPI server for Statis Pro Football engine."""
import os
import random
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from .game import Game, GameState
from .team import Team, list_available_teams
from .fast_action_dice import FastActionDice, roll as dice_roll
from .solitaire import SolitaireAI, GameSituation, PlayCall
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

MAX_LAST_PLAYS = 20  # Number of recent plays to include in state responses


# ─── Request / Response Models ──────────────────────────────────────────────

class NewGameRequest(BaseModel):
    home_team: str
    away_team: str
    season: str = "2025_5e"
    solitaire_home: bool = True
    solitaire_away: bool = True


class HumanPlayCallRequest(BaseModel):
    play_type: str  # RUN, SHORT_PASS, LONG_PASS, QUICK_PASS, SCREEN, PUNT, FG, KNEEL
    direction: str = "MIDDLE"  # LEFT, RIGHT, MIDDLE, IL, IR, SL, SR, DEEP_LEFT, DEEP_RIGHT
    formation: str = "UNDER_CENTER"  # UNDER_CENTER, SHOTGUN, I_FORM, TRIPS, etc.


class DefensivePlayCallRequest(BaseModel):
    formation: str = "4_3"  # 4_3, 3_4, 4_3_BLITZ, 3_4_ZONE, NICKEL_BLITZ, NICKEL_ZONE, NICKEL_COVER2, GOAL_LINE, 4_3_COVER2


class SubstitutionRequest(BaseModel):
    position: str  # QB, RB, WR, TE, K, P
    player_out: str  # player name to remove from starters
    player_in: str  # player name to put in as starter


class PlayCallRequest(BaseModel):
    game_id: str
    play_type: Optional[str] = None


# ─── Endpoints ───────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "Statis Pro Football API", "version": "1.0.0"}


@app.get("/teams")
def get_teams(season: str = "2025_5e"):
    """List all available teams."""
    teams = list_available_teams(season)
    return {"teams": sorted(teams), "season": season}


@app.get("/teams/{team_abbr}")
def get_team(team_abbr: str, season: str = "2025_5e"):
    """Get team data."""
    try:
        team = Team.load(team_abbr.upper(), season)
        return team.to_dict()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Team {team_abbr} not found")


@app.get("/teams/{team_abbr}/roster")
def get_roster(team_abbr: str, season: str = "2025_5e"):
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

    use_5e = "5e" in str(request.season)
    game = Game(home, away, request.solitaire_home, request.solitaire_away, use_5e=use_5e)
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
    """Execute a single play (AI-controlled)."""
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


@app.post("/games/{game_id}/human-play")
def execute_human_play(game_id: str, request: HumanPlayCallRequest):
    """Execute a play with a human-specified play call."""
    game = _get_game(game_id)

    if game.state.is_over:
        raise HTTPException(status_code=400, detail="Game is over")

    play_call = PlayCall(
        play_type=request.play_type.upper(),
        formation=request.formation.upper(),
        direction=request.direction.upper(),
        reasoning="Human play call",
    )

    result = game.execute_play(play_call=play_call)

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


VALID_FORMATIONS = {
    "4_3", "3_4", "4_3_BLITZ", "3_4_ZONE", "4_3_COVER2",
    "NICKEL_BLITZ", "NICKEL_ZONE", "NICKEL_COVER2", "GOAL_LINE",
}


@app.post("/games/{game_id}/human-defense")
def execute_human_defense(game_id: str, request: DefensivePlayCallRequest):
    """Execute a play where the human calls the defensive formation.

    The offense is AI-controlled while the human picks the defense.
    """
    game = _get_game(game_id)

    if game.state.is_over:
        raise HTTPException(status_code=400, detail="Game is over")

    formation = request.formation.upper()
    if formation not in VALID_FORMATIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid formation: {formation}. Valid: {sorted(VALID_FORMATIONS)}",
        )

    result = game.execute_play(defense_formation=formation)

    return {
        "game_id": game_id,
        "play_result": {
            "play_type": result.play_type,
            "yards": result.yards_gained,
            "result": result.result,
            "description": result.description,
            "is_touchdown": result.is_touchdown,
            "turnover": result.turnover,
            "defense_formation": formation,
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
def get_player_card(team_abbr: str, player_name: str, season: str = "2025_5e"):
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


@app.get("/games/{game_id}/personnel")
def get_personnel(game_id: str):
    """Get current offensive and defensive personnel on the field."""
    game = _get_game(game_id)

    offense_team = game.get_offense_team()
    defense_team = game.get_defense_team()

    def _player_brief(p):
        """Build a player summary including card data for board display."""
        brief = {
            "name": p.player_name,
            "position": p.position,
            "number": p.number,
            "overall_grade": p.overall_grade,
            "receiver_letter": getattr(p, "receiver_letter", ""),
            "defender_letter": getattr(p, "defender_letter", ""),
            # Offensive Line ratings
            "run_block_rating": getattr(p, "run_block_rating", 0),
            "pass_block_rating": getattr(p, "pass_block_rating", 0),
            # Defensive ratings (legacy)
            "pass_rush_rating": getattr(p, "pass_rush_rating", 0),
            "coverage_rating": getattr(p, "coverage_rating", 0),
            "run_stop_rating": getattr(p, "run_stop_rating", 0),
            # Authentic 5E defensive ratings
            "tackle_rating": getattr(p, "tackle_rating", 0),
            "pass_defense_rating": getattr(p, "pass_defense_rating", 0),
            "intercept_range": getattr(p, "intercept_range", 0),
            # QB passing ranges
            "passing_quick": p.passing_quick.to_dict() if getattr(p, "passing_quick", None) else None,
            "passing_short": p.passing_short.to_dict() if getattr(p, "passing_short", None) else None,
            "passing_long": p.passing_long.to_dict() if getattr(p, "passing_long", None) else None,
            "pass_rush": p.pass_rush.to_dict() if getattr(p, "pass_rush", None) else None,
            "qb_endurance": getattr(p, "qb_endurance", ""),
            # Rushing (12-row N/SG/LG)
            "rushing": [r.to_list() if r else None for r in getattr(p, "rushing", [])],
            "endurance_rushing": getattr(p, "endurance_rushing", 0),
            # Pass gain (12-row Q/S/L)
            "pass_gain": [r.to_list() if r else None for r in getattr(p, "pass_gain", [])],
            "endurance_pass": getattr(p, "endurance_pass", 0),
            "blocks": getattr(p, "blocks", 0),
            # Kicker
            "fg_chart": getattr(p, "fg_chart", None) or None,
            "xp_rate": getattr(p, "xp_rate", 0),
            # Punter
            "avg_distance": getattr(p, "avg_distance", 0),
            "inside_20_rate": getattr(p, "inside_20_rate", 0),
        }
        return brief

    offense_starters = {}
    for pos in ["QB", "RB", "WR", "TE", "K", "P"]:
        starter = offense_team.roster.get_starter(pos)
        if starter:
            offense_starters[pos] = _player_brief(starter)

    # Include WR2, WR3, TE if available
    offense_receivers = []
    for wr in offense_team.roster.wrs[:3]:
        offense_receivers.append(_player_brief(wr))
    for te in offense_team.roster.tes[:1]:
        offense_receivers.append(_player_brief(te))

    # Offensive line
    offense_line = [_player_brief(p) for p in offense_team.roster.offensive_line[:5]]

    defense_players = [_player_brief(p) for p in defense_team.roster.defenders[:11]]

    # Group defenders by position for board layout (DL/LB/DB rows)
    defense_line = []
    linebackers = []
    defensive_backs = []
    for p in defense_team.roster.defenders[:11]:
        brief = _player_brief(p)
        pos = p.position.upper()
        if pos in ("DE", "DT", "DL", "NT"):
            defense_line.append(brief)
        elif pos in ("LB", "OLB", "ILB", "MLB"):
            linebackers.append(brief)
        elif pos in ("CB", "S", "SS", "FS", "DB"):
            defensive_backs.append(brief)
        else:
            # Default: put unknown defensive positions in DL
            defense_line.append(brief)

    return {
        "possession": game.state.possession,
        "offense_team": offense_team.abbreviation,
        "defense_team": defense_team.abbreviation,
        "offense_starters": offense_starters,
        "offense_receivers": offense_receivers,
        "offense_line": offense_line,
        "defense_players": defense_players,
        "defense_line": defense_line,
        "linebackers": linebackers,
        "defensive_backs": defensive_backs,
        "offense_all": [_player_brief(p) for p in offense_team.roster.all_players()],
        "defense_all": [_player_brief(p) for p in defense_team.roster.all_players()],
    }


@app.post("/games/{game_id}/substitute")
def substitute_player(game_id: str, request: SubstitutionRequest):
    """Substitute a player on the current possession team."""
    game = _get_game(game_id)

    pos = request.position.upper()
    team = game.get_offense_team()

    pos_map = {
        "QB": team.roster.qbs,
        "RB": team.roster.rbs,
        "WR": team.roster.wrs,
        "TE": team.roster.tes,
        "K": team.roster.kickers,
        "P": team.roster.punters,
    }

    player_list = pos_map.get(pos)
    if player_list is None:
        raise HTTPException(status_code=400, detail=f"Invalid position: {pos}")

    # Find player_in in the list
    player_in_obj = None
    player_in_idx = None
    for i, p in enumerate(player_list):
        if p.player_name.lower() == request.player_in.lower():
            player_in_obj = p
            player_in_idx = i
            break

    if player_in_obj is None:
        raise HTTPException(
            status_code=404,
            detail=f"Player '{request.player_in}' not found at {pos}",
        )

    # Find player_out (should be the starter at index 0)
    player_out_idx = None
    for i, p in enumerate(player_list):
        if p.player_name.lower() == request.player_out.lower():
            player_out_idx = i
            break

    if player_out_idx is None:
        raise HTTPException(
            status_code=404,
            detail=f"Player '{request.player_out}' not found at {pos}",
        )

    # Swap positions in the list so player_in becomes the starter
    player_list[player_out_idx], player_list[player_in_idx] = (
        player_list[player_in_idx],
        player_list[player_out_idx],
    )

    game.state.play_log.append(
        f"SUB: {request.player_in} replaces {request.player_out} at {pos}"
    )

    return {
        "message": f"{request.player_in} now starting at {pos}",
        "state": _serialize_state(game.state),
    }


@app.get("/games/{game_id}/gamelog")
def get_game_log(game_id: str):
    """Get the full game log as structured data."""
    game = _get_game(game_id)
    return {
        "game_id": game_id,
        "log": game.state.play_log,
        "drives": [
            {
                "team": d.team,
                "plays": d.plays,
                "yards": d.yards,
                "result": d.result,
                "points_scored": d.points_scored,
                "drive_log": d.drive_log,
            }
            for d in game.state.drives
        ],
    }


@app.get("/games/{game_id}/gamelog/download")
def download_game_log(game_id: str):
    """Download the full game log as a plain text file."""
    game = _get_game(game_id)

    lines = [
        f"Statis Pro Football - Game Log",
        f"{'=' * 50}",
        f"{game.state.away_team} @ {game.state.home_team}",
        f"Final Score: {game.state.away_team} {game.state.score.away} - "
        f"{game.state.home_team} {game.state.score.home}",
        f"{'=' * 50}",
        "",
    ]
    for entry in game.state.play_log:
        lines.append(entry)

    if game.state.drives:
        lines.append("")
        lines.append(f"{'=' * 50}")
        lines.append("DRIVE SUMMARY")
        lines.append(f"{'=' * 50}")
        for i, d in enumerate(game.state.drives, 1):
            lines.append(
                f"Drive {i}: {d.team} - {d.plays} plays, {d.yards} yds - "
                f"{d.result} ({d.points_scored} pts)"
            )

    content = "\n".join(lines)
    return PlainTextResponse(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{game_id}_gamelog.txt"'},
    )


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
        "timeouts_home": state.timeouts_home,
        "timeouts_away": state.timeouts_away,
        "last_plays": state.play_log[-MAX_LAST_PLAYS:] if state.play_log else [],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
