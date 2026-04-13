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


def _serialize_play_result(result) -> dict:
    """Serialize a play result for API responses."""
    return {
        "play_type": result.play_type,
        "yards": result.yards_gained,
        "result": result.result,
        "description": result.description,
        "is_touchdown": result.is_touchdown,
        "turnover": result.turnover,
        "run_number": result.run_number_used,
        "pass_number": result.pass_number_used,
        "defense_formation": result.defense_formation,
        "strategy": result.strategy,
        "injury_player": result.injury_player,
        "injury_duration": result.injury_duration,
        "offensive_play_call": result.offensive_play_call,
        "defensive_play_call": result.defensive_play_call,
        "defensive_play": result.defensive_play,
        "passer": result.passer,
        "rusher": result.rusher,
        "receiver": result.receiver,
        "bv_tv_result": result.bv_tv_result,
        "interception_point": result.interception_point,
        "personnel_note": getattr(result, "personnel_note", None),
        "debug_log": getattr(result, 'debug_log', []),
    }


def _player_brief(p, unavailable_names: Optional[set[str]] = None):
    if p is None:
        raise ValueError("_player_brief requires a player")
    unavailable = unavailable_names or set()
    return {
        "name": p.player_name,
        "position": p.position,
        "number": p.number,
        "overall_grade": p.overall_grade,
        "receiver_letter": getattr(p, "receiver_letter", ""),
        "defender_letter": getattr(p, "defender_letter", ""),
        "injured": p.player_name in unavailable,
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
        "longest_kick": getattr(p, "longest_kick", 0),
        # Punter
        "avg_distance": getattr(p, "avg_distance", 0),
        "inside_20_rate": getattr(p, "inside_20_rate", 0),
        "blocked_punt_number": getattr(p, "blocked_punt_number", 0),
        "punt_return_pct": getattr(p, "punt_return_pct", 0),
    }


def _build_team_card(team: Team, unavailable_names: Optional[set[str]] = None) -> dict:
    lineup = team.get_standard_lineup()
    kr_depth = team.get_return_candidates("KR")[:3]
    pr_depth = team.get_return_candidates("PR")[:4]
    return {
        "team": team.abbreviation,
        "city": team.city,
        "name": team.name,
        "record": {"wins": team.wins, "losses": team.losses, "ties": team.ties},
        "offense": {
            pos: _player_brief(player, unavailable_names) if player else None
            for pos, player in lineup["offense"].items()
        },
        "offensive_line": [_player_brief(player, unavailable_names) for player in lineup["offensive_line"]],
        "defense": [_player_brief(player, unavailable_names) for player in lineup["defense"]],
        "returners": {
            kind: _player_brief(player, unavailable_names) if player else None
            for kind, player in lineup["returners"].items()
        },
        "kick_returners": [_player_brief(player, unavailable_names) for player in kr_depth],
        "punt_returners": [_player_brief(player, unavailable_names) for player in pr_depth],
    }


# ─── Request / Response Models ──────────────────────────────────────────────

class NewGameRequest(BaseModel):
    home_team: str
    away_team: str
    season: str = "2025_5e"
    solitaire_home: bool = True
    solitaire_away: bool = True
    seed: Optional[int] = None  # Random seed for reproducible games
    use_5e: Optional[bool] = None  # Explicit 5E mode toggle (auto-detected from season if None)


class HumanPlayCallRequest(BaseModel):
    play_type: str  # RUN, SHORT_PASS, LONG_PASS, QUICK_PASS, SCREEN, PUNT, FG, KNEEL
    direction: str = "MIDDLE"  # LEFT, RIGHT, MIDDLE, IL, IR, SL, SR, DEEP_LEFT, DEEP_RIGHT
    formation: str = "UNDER_CENTER"  # UNDER_CENTER, SHOTGUN, I_FORM, TRIPS, etc.
    strategy: Optional[str] = None  # FLOP, SNEAK, DRAW, PLAY_ACTION (5E strategies)
    player_name: Optional[str] = None  # Specific player to use (QB/RB/WR name)


class DefensivePlayCallRequest(BaseModel):
    formation: str = "4_3"  # 4_3, 3_4, 4_3_BLITZ, 3_4_ZONE, NICKEL_BLITZ, NICKEL_ZONE, NICKEL_COVER2, GOAL_LINE, 4_3_COVER2
    defensive_play: str = "PASS_DEFENSE"  # PASS_DEFENSE, PREVENT_DEFENSE, RUN_DEFENSE_NO_KEY, etc.
    defensive_strategy: str = "NONE"  # NONE, DOUBLE_COVERAGE, TRIPLE_COVERAGE


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
        data = team.to_dict()
        data["team_card"] = _build_team_card(team)
        return data
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

    use_5e = request.use_5e if request.use_5e is not None else ("5e" in str(request.season))
    game = Game(home, away, request.solitaire_home, request.solitaire_away,
                use_5e=use_5e, seed=request.seed)
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
        "play_result": _serialize_play_result(result),
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
        strategy=request.strategy.upper() if request.strategy else None,
    )

    if request.player_name:
        try:
            game.validate_player_availability(request.player_name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    result = game.execute_play(
        play_call=play_call,
        player_name=request.player_name
    )

    return {
        "game_id": game_id,
        "play_result": _serialize_play_result(result),
        "state": _serialize_state(game.state),
    }


VALID_FORMATIONS = {
    "4_3", "3_4", "4_3_BLITZ", "3_4_ZONE", "4_3_COVER2",
    "NICKEL_BLITZ", "NICKEL_ZONE", "NICKEL_COVER2", "GOAL_LINE",
}

VALID_DEFENSIVE_PLAYS = {
    "PASS_DEFENSE", "PREVENT_DEFENSE", "RUN_DEFENSE_NO_KEY",
    "RUN_DEFENSE_KEY_BACK_1", "RUN_DEFENSE_KEY_BACK_2",
    "RUN_DEFENSE_KEY_BACK_3", "BLITZ",
}

VALID_DEFENSIVE_STRATEGIES = {
    "NONE", "DOUBLE_COVERAGE", "TRIPLE_COVERAGE", "ALT_DOUBLE_COVERAGE",
}


@app.post("/games/{game_id}/human-defense")
def execute_human_defense(game_id: str, request: DefensivePlayCallRequest):
    """Execute a play where the human calls the defensive formation.

    The offense is AI-controlled while the human picks the defense.
    Accepts both legacy formation strings and new 5E defensive play types.
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

    defensive_play = request.defensive_play.upper()
    if defensive_play not in VALID_DEFENSIVE_PLAYS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid defensive play: {defensive_play}. Valid: {sorted(VALID_DEFENSIVE_PLAYS)}",
        )

    defensive_strategy = request.defensive_strategy.upper()
    if defensive_strategy not in VALID_DEFENSIVE_STRATEGIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid defensive strategy: {defensive_strategy}. Valid: {sorted(VALID_DEFENSIVE_STRATEGIES)}",
        )

    result = game.execute_play(
        defense_formation=formation,
        defensive_strategy=defensive_strategy if defensive_strategy != "NONE" else None,
    )

    return {
        "game_id": game_id,
        "play_result": _serialize_play_result(result),
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
    unavailable = set(game.state.injuries)

    offense_starters = {}
    for pos in ["QB", "RB", "WR", "TE", "K", "P"]:
        starter = offense_team.roster.get_starter(pos)
        if starter:
            offense_starters[pos] = _player_brief(starter, unavailable)

    # Include WR2, WR3, TE if available
    offense_receivers = []
    for wr in offense_team.roster.wrs[:3]:
        offense_receivers.append(_player_brief(wr, unavailable))
    for te in offense_team.roster.tes[:1]:
        offense_receivers.append(_player_brief(te, unavailable))

    # Offensive line
    offense_line = [_player_brief(p, unavailable) for p in offense_team.roster.offensive_line[:5]]

    defense_players = [_player_brief(p, unavailable) for p in defense_team.roster.defenders[:11]]

    # Group defenders by position for board layout (DL/LB/DB rows)
    defense_line = []
    linebackers = []
    defensive_backs = []
    for p in defense_team.roster.defenders[:11]:
        brief = _player_brief(p, unavailable)
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
        "offense_all": [_player_brief(p, unavailable) for p in offense_team.roster.all_players()],
        "defense_all": [_player_brief(p, unavailable) for p in defense_team.roster.all_players()],
        "return_specialists": {
            "KR": _player_brief(game.get_returner(offense_team, "KR"), unavailable)
            if game.get_returner(offense_team, "KR") else None,
            "PR": _player_brief(game.get_returner(offense_team, "PR"), unavailable)
            if game.get_returner(offense_team, "PR") else None,
        },
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
        "injuries": state.injuries,
        "penalties": state.penalties,
        "penalty_yards": state.penalty_yards,
        "turnovers": state.turnovers,
        "player_stats": state.player_stats,
    }


# ─── Onside / Squib Kick Endpoints ─────────────────────────────────────────

class OnsideKickRequest(BaseModel):
    onside_defense: bool = False  # Receiving team declared onside defense


@app.post("/games/{game_id}/onside-kick")
def execute_onside_kick(game_id: str, request: OnsideKickRequest):
    """Execute an onside kick per 5E rules."""
    game = _get_game(game_id)
    if game.state.is_over:
        raise HTTPException(status_code=400, detail="Game is over")
    result = game.execute_onside_kick(onside_defense=request.onside_defense)
    return {
        "game_id": game_id,
        "play_result": _serialize_play_result(result),
        "state": _serialize_state(game.state),
    }


@app.post("/games/{game_id}/squib-kick")
def execute_squib_kick(game_id: str):
    """Execute a squib kick per 5E rules."""
    game = _get_game(game_id)
    if game.state.is_over:
        raise HTTPException(status_code=400, detail="Game is over")
    result = game.execute_squib_kick()
    return {
        "game_id": game_id,
        "play_result": _serialize_play_result(result),
        "state": _serialize_state(game.state),
    }


@app.post("/games/{game_id}/timeout")
def call_timeout(game_id: str, team: str = "possession"):
    """Call a timeout for the specified team.

    team: 'home', 'away', or 'possession' (default).
    """
    game = _get_game(game_id)
    if game.state.is_over:
        raise HTTPException(status_code=400, detail="Game is over")

    if team == "possession":
        team = game.state.possession

    success = game.call_timeout(team)
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot call timeout for {team} (no timeouts left or 5E restriction)",
        )
    return {
        "game_id": game_id,
        "message": f"Timeout called by {team}",
        "state": _serialize_state(game.state),
    }


class TwoPointConversionRequest(BaseModel):
    play_type: str = "SHORT_PASS"  # RUN, SHORT_PASS, QUICK_PASS
    direction: str = "MIDDLE"
    player_name: str = ""


class CoffinCornerRequest(BaseModel):
    deduction: int = 15  # 10-25 yard deduction from normal punt distance


@app.post("/games/{game_id}/fake-punt")
def execute_fake_punt(game_id: str):
    """Execute a fake punt per 5E rules (once per game)."""
    game = _get_game(game_id)
    if game.state.is_over:
        raise HTTPException(status_code=400, detail="Game is over")
    result = game.execute_fake_punt()
    return {
        "game_id": game_id,
        "play_result": _serialize_play_result(result),
        "state": _serialize_state(game.state),
    }


@app.post("/games/{game_id}/fake-fg")
def execute_fake_fg(game_id: str):
    """Execute a fake field goal per 5E rules (once per game, not in final 2 min)."""
    game = _get_game(game_id)
    if game.state.is_over:
        raise HTTPException(status_code=400, detail="Game is over")
    result = game.execute_fake_field_goal()
    return {
        "game_id": game_id,
        "play_result": _serialize_play_result(result),
        "state": _serialize_state(game.state),
    }


@app.post("/games/{game_id}/coffin-corner")
def execute_coffin_corner(game_id: str, request: CoffinCornerRequest):
    """Execute a coffin corner punt with declared yardage deduction."""
    game = _get_game(game_id)
    if game.state.is_over:
        raise HTTPException(status_code=400, detail="Game is over")
    deduction = max(10, min(25, request.deduction))
    result = game.execute_coffin_corner_punt(deduction)
    return {
        "game_id": game_id,
        "play_result": _serialize_play_result(result),
        "state": _serialize_state(game.state),
    }


@app.post("/games/{game_id}/all-out-punt-rush")
def execute_all_out_punt_rush(game_id: str):
    """Execute an all-out punt rush (defensive call)."""
    game = _get_game(game_id)
    if game.state.is_over:
        raise HTTPException(status_code=400, detail="Game is over")
    result = game.execute_all_out_punt_rush()
    return {
        "game_id": game_id,
        "play_result": _serialize_play_result(result),
        "state": _serialize_state(game.state),
    }


@app.post("/games/{game_id}/two-point-conversion")
def execute_two_point_conversion(game_id: str, request: TwoPointConversionRequest):
    """Execute a two-point conversion attempt after a touchdown."""
    game = _get_game(game_id)
    if game.state.is_over:
        raise HTTPException(status_code=400, detail="Game is over")

    # Create a play call for the 2-point conversion
    play_call = PlayCall(
        play_type=request.play_type.upper(),
        formation="SHOTGUN",
        direction=request.direction.upper(),
        reasoning="Two-point conversion attempt",
    )

    # Set field position to 2-yard line
    original_yl = game.state.yard_line
    game.state.yard_line = 98  # 2 yards from opponent's end zone

    result = game.execute_play(
        play_call=play_call,
        player_name=request.player_name if request.player_name else None,
    )

    # Check if the play gained at least 2 yards
    if result.yards_gained >= 2 or result.is_touchdown:
        # Two-point conversion successful
        if game.state.possession == "home":
            game.state.score.home += 2
        else:
            game.state.score.away += 2
        game.state.play_log.append("✅ Two-point conversion GOOD!")
        result_desc = "Two-point conversion successful!"
    else:
        game.state.play_log.append("❌ Two-point conversion FAILED")
        result_desc = "Two-point conversion failed"

    # Restore state for kickoff
    game.state.yard_line = original_yl

    return {
        "game_id": game_id,
        "result": result_desc,
        "play_result": _serialize_play_result(result),
        "state": _serialize_state(game.state),
    }


# ─── Big Play Defense Endpoint ──────────────────────────────────────────────

class BigPlayDefenseRequest(BaseModel):
    team: str = "defense"  # 'home' or 'away' or 'defense' (auto-detect defending team)


@app.post("/games/{game_id}/big-play-defense")
def activate_big_play_defense(game_id: str, request: BigPlayDefenseRequest):
    """Activate Big Play Defense for the specified team this defensive series."""
    game = _get_game(game_id)
    if game.state.is_over:
        raise HTTPException(status_code=400, detail="Game is over")

    team = request.team
    if team == "defense":
        team = "away" if game.state.possession == "home" else "home"

    result = game.activate_big_play_defense(team)
    if not result:
        raise HTTPException(
            status_code=400,
            detail="Big Play Defense not available (already used this series, or team not eligible)",
        )
    return {
        "game_id": game_id,
        "message": f"Big Play Defense activated for {team}",
        "state": _serialize_state(game.state),
    }


# ─── Two-Minute Offense Endpoint ───────────────────────────────────────────

@app.post("/games/{game_id}/two-minute-offense")
def declare_two_minute_offense(game_id: str):
    """Declare two-minute offense mode (manual toggle)."""
    game = _get_game(game_id)
    if game.state.is_over:
        raise HTTPException(status_code=400, detail="Game is over")

    game.declare_two_minute_offense()
    return {
        "game_id": game_id,
        "message": "Two-minute offense declared",
        "two_minute_offense": True,
        "state": _serialize_state(game.state),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
