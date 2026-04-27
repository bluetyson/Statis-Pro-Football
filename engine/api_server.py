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
from .solitaire import SolitaireAI, GameSituation, PlayCall
from .card_generator import CardGenerator
from .play_resolver import PlayResolver

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
        "box_assignments": getattr(result, "box_assignments", None),
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
        # Authentic Avalon Hill defensive ratings
        "pass_rush_rating": getattr(p, "pass_rush_rating", 0),
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
        # Human-readable endurance label — for WR/TE show pass endurance
        # (the one that matters when they're targeted), for RB/FB/HB show
        # rushing endurance.
        "endurance_label": (
            f"{p.position}-{getattr(p, 'endurance_pass', 0)}"
            if p.position in ("WR", "TE")
            else f"{p.position}-{getattr(p, 'endurance_rushing', 0)}"
            if p.position in ("RB", "FB", "HB")
            else ""
        ),
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


class HumanPlayCallRequest(BaseModel):
    play_type: str  # RUN, SHORT_PASS, LONG_PASS, QUICK_PASS, SCREEN, PUNT, FG, KNEEL, SPIKE
    direction: str = "MIDDLE"  # LEFT, RIGHT, MIDDLE, IL, IR, SL, SR, DEEP_LEFT, DEEP_RIGHT
    formation: str = "UNDER_CENTER"  # UNDER_CENTER, SHOTGUN, I_FORM, TRIPS, etc.
    strategy: Optional[str] = None  # FLOP, SNEAK, DRAW, PLAY_ACTION (5E strategies)
    player_name: Optional[str] = None  # Specific player to use (QB/RB/WR name)
    backs_blocking: Optional[List[str]] = None  # RB names kept in to pass-block (+2 comp range each)


class DefensivePlayCallRequest(BaseModel):
    formation: str = "4_3"  # 4_3, 3_4, NICKEL, GOAL_LINE
    defensive_play: str = "PASS_DEFENSE"  # PASS_DEFENSE, PREVENT_DEFENSE, RUN_DEFENSE_NO_KEY, etc.
    defensive_strategy: str = "NONE"  # NONE, DOUBLE_COVERAGE, TRIPLE_COVERAGE
    blitz_players: Optional[List[str]] = None  # Names of LBs/DBs to blitz (2-5 players)


class SubstitutionRequest(BaseModel):
    position: str  # QB, RB, WR, TE, OL, LT, LG, C, RG, RT, K, P, DL, LB, DB
    player_out: str  # player name to remove from starters
    player_in: str  # player name to put in as starter


class PositionChangeRequest(BaseModel):
    player_name: str  # player to move
    new_position: str  # new position (compatible positions only)


class SetFieldSlotRequest(BaseModel):
    """Assign a specific player to an on-field formation slot."""
    slot: str        # FL, LE, RE, BK1, BK2, BK3  or  LT, LG, C, RG, RT
    player_name: Optional[str] = None  # None / empty to clear the slot
    team: str = "possession"  # 'home', 'away', or 'possession' (auto-detect)


class ApplyPackageRequest(BaseModel):
    """Apply a named formation package to an offense."""
    package: str   # STANDARD, 2TE_1WR, 3TE, JUMBO, 4WR, 3RB
    team: str = "possession"  # 'home', 'away', or 'possession' (auto-detect)


class ApplyDefensePackageRequest(BaseModel):
    """Apply a named coverage/rush package to a defense."""
    package: str   # STANDARD, NICKEL, DIME, 335, PREVENT
    team: str = "defense"  # 'defense', 'home', or 'away'


class StartingLineupRequest(BaseModel):
    """Set starting lineup for a team."""
    team: str  # 'home' or 'away'
    offense: Optional[Dict[str, str]] = None  # {position: player_name} e.g. {"QB": "Patrick Mahomes"}
    defense: Optional[List[str]] = None  # List of 11 defender names in order


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

    game = Game(home, away, request.solitaire_home, request.solitaire_away,
                seed=request.seed)
    game_id = f"{request.away_team}@{request.home_team}_{random.randint(1000, 9999)}"
    _active_games[game_id] = game

    return {
        "game_id": game_id,
        "state": _serialize_state(game.state, game),
    }


@app.get("/games/{game_id}")
def get_game(game_id: str):
    """Get current game state."""
    game = _get_game(game_id)
    return {"game_id": game_id, "state": _serialize_state(game.state, game)}


@app.post("/games/{game_id}/play")
def execute_play(game_id: str):
    """Execute a single play (AI-controlled)."""
    game = _get_game(game_id)

    if game.state.is_over:
        raise HTTPException(status_code=400, detail="Game is over")
    if game.state.pending_extra_point:
        raise HTTPException(
            status_code=400,
            detail="A touchdown was just scored — choose PAT (kick) or 2-point conversion before calling a new play.",
        )

    result = game.execute_play()

    return {
        "game_id": game_id,
        "play_result": _serialize_play_result(result),
        "state": _serialize_state(game.state, game),
    }


@app.post("/games/{game_id}/human-play")
def execute_human_play(game_id: str, request: HumanPlayCallRequest):
    """Execute a play with a human-specified play call."""
    game = _get_game(game_id)

    if game.state.is_over:
        raise HTTPException(status_code=400, detail="Game is over")
    if game.state.pending_extra_point:
        raise HTTPException(
            status_code=400,
            detail="A touchdown was just scored — choose PAT (kick) or 2-point conversion before calling a new play.",
        )

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
        player_name=request.player_name,
        backs_blocking=request.backs_blocking or None,
    )

    return {
        "game_id": game_id,
        "play_result": _serialize_play_result(result),
        "state": _serialize_state(game.state, game),
    }


VALID_FORMATIONS = {
    "4_3", "3_4", "NICKEL", "GOAL_LINE",
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
    Formations: 4_3, 3_4, NICKEL, GOAL_LINE.
    Defensive plays: PASS_DEFENSE, PREVENT_DEFENSE, RUN_DEFENSE_NO_KEY, etc.
    """
    game = _get_game(game_id)

    if game.state.is_over:
        raise HTTPException(status_code=400, detail="Game is over")
    if game.state.pending_extra_point:
        raise HTTPException(
            status_code=400,
            detail="A touchdown was just scored — choose PAT (kick) or 2-point conversion before calling a new play.",
        )

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

    # Validate blitz players if provided
    blitz_players = None
    if request.blitz_players:
        if defensive_play != "BLITZ":
            raise HTTPException(
                status_code=400,
                detail="Blitz players can only be specified with BLITZ defense",
            )
        if len(request.blitz_players) < 2 or len(request.blitz_players) > 5:
            raise HTTPException(
                status_code=400,
                detail="Must specify 2-5 blitz players (LBs/DBs)",
            )
        blitz_players = request.blitz_players

    result = game.execute_play(
        defense_formation=formation,
        defensive_play=defensive_play,
        defensive_strategy=defensive_strategy if defensive_strategy != "NONE" else None,
        blitz_players=blitz_players,
    )

    return {
        "game_id": game_id,
        "play_result": _serialize_play_result(result),
        "state": _serialize_state(game.state, game),
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
        "state": _serialize_state(game.state, game),
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
        "state": _serialize_state(state, game),
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

    def _first_healthy(players):
        """Return first non-injured player, falling back to index 0."""
        for p in players:
            if p.player_name not in unavailable:
                return p
        return players[0] if players else None

    offense_starters = {}
    for pos in ["QB", "RB", "WR", "TE", "K", "P"]:
        pos_map = {
            "QB": offense_team.roster.qbs, "RB": offense_team.roster.rbs,
            "WR": offense_team.roster.wrs, "TE": offense_team.roster.tes,
            "K": offense_team.roster.kickers, "P": offense_team.roster.punters,
        }
        starter = _first_healthy(pos_map[pos])
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

    # Compute dynamic box assignments (A-O) from current on-field order so
    # that the letter badges shown on the board match actual box positions.
    # This overrides the static defender_letter stored on the player card,
    # which was assigned by roster-slot order in the JSON file and therefore
    # doesn't match the position-based (DE=A/E, DT=B/D, NT=C, …) layout.
    _dynamic_boxes = PlayResolver.assign_default_display_boxes(
        list(defense_team.roster.defenders[:11])
    )
    for group in (defense_line, linebackers, defensive_backs):
        for brief in group:
            box = _dynamic_boxes.get(brief["name"])
            if box:
                brief["defender_letter"] = box

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
        "on_field_assignments": game.get_field_assignments(game.state.possession),
    }


@app.post("/games/{game_id}/substitute")
def substitute_player(game_id: str, request: SubstitutionRequest):
    """Substitute a player on the current possession team.

    Supports all offensive positions including OL (offensive linemen).
    For OL subs, the player_out/player_in are matched across the full
    offensive_line roster and the list order is swapped so the new player
    becomes first (starter) at that position.
    """
    game = _get_game(game_id)

    pos = request.position.upper()
    team = game.get_offense_team()

    # OL substitution — search the entire offensive_line list regardless of
    # the specific OL position label (LT/LG/C/RG/RT/OL).
    if pos in ("OL", "LT", "LG", "C", "RG", "RT"):
        player_list = team.roster.offensive_line
        player_in_idx = next(
            (i for i, p in enumerate(player_list)
             if p.player_name.lower() == request.player_in.lower()),
            None,
        )
        player_out_idx = next(
            (i for i, p in enumerate(player_list)
             if p.player_name.lower() == request.player_out.lower()),
            None,
        )
        if player_in_idx is None:
            raise HTTPException(
                status_code=404,
                detail=f"Player '{request.player_in}' not found in OL",
            )
        if player_out_idx is None:
            raise HTTPException(
                status_code=404,
                detail=f"Player '{request.player_out}' not found in OL",
            )
    # Determine which OL slot the outgoing player held (look at on_field_ol first,
    # then fall back to the OL position from their player card).
    off_side = game.state.possession
    ol_assignments = game._on_field_ol.get(off_side, {})
    out_slot = next(
        (slot for slot, name in ol_assignments.items()
         if name.lower() == request.player_out.lower()),
        None,
    )
    if not out_slot:
        # Find the player's card position (LT/LG/C/RG/RT) from the list
        out_card = next(
            (p for p in player_list if p.player_name.lower() == request.player_out.lower()),
            None,
        )
        out_slot = out_card.position if out_card else pos

    player_list[player_out_idx], player_list[player_in_idx] = (
        player_list[player_in_idx], player_list[player_out_idx]
    )
    game.state.play_log.append(
        f"OL SUB: {request.player_in} replaces {request.player_out} at {out_slot}"
    )
    # 5E: substitution rescinds no-huddle offense
    game._rescind_no_huddle_offense(reason="substitution")
    return {
        "message": f"{request.player_in} now starting at {pos} (OL)",
        "state": _serialize_state(game.state, game),
    }

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

    # Determine which formation slot the outgoing player was in.
    # Priority: explicit on_field_assignments override → default by position+order.
    offense_side = game.state.possession
    field_assignments = game.get_field_assignments(offense_side)
    # Reverse lookup: which slot was the outgoing player explicitly assigned to?
    out_slot = next(
        (slot for slot, name in field_assignments.items()
         if name.lower() == request.player_out.lower()),
        None,
    )
    if not out_slot:
        # Default: first WR → LE, second WR → FL, third WR → RE;
        # first RB → BK1, second RB → BK2; first TE → RE.
        # After the swap player_out_idx holds the outgoing player's original roster index.
        slot_by_pos_idx: dict = {
            ("WR", 0): "LE",  ("WR", 1): "FL",  ("WR", 2): "RE",
            ("RB", 0): "BK1", ("RB", 1): "BK2",
            ("TE", 0): "RE",  ("TE", 1): "LE",
            ("QB", 0): "QB",
            ("K",  0): "K",   ("P", 0): "P",
        }
        out_slot = slot_by_pos_idx.get((pos, player_out_idx), pos)

    game.state.play_log.append(
        f"SUB: {request.player_in} replaces {request.player_out} at {pos} ({out_slot} slot)"
    )
    # 5E: substitution rescinds no-huddle offense
    game._rescind_no_huddle_offense(reason="substitution")

    return {
        "message": f"{request.player_in} now starting at {pos}",
        "state": _serialize_state(game.state, game),
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

    # Append player stats boxscore
    lines.extend(game.format_boxscore())

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


def _serialize_state(state: GameState, game=None) -> dict:
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
        "pending_extra_point": state.pending_extra_point,
        "two_minute_offense": bool(game._is_two_minute_offense()) if game else False,
        "no_huddle_offense": bool(getattr(game, '_no_huddle', False)) if game else False,
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
        "state": _serialize_state(game.state, game),
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
        "state": _serialize_state(game.state, game),
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
        "state": _serialize_state(game.state, game),
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
        "state": _serialize_state(game.state, game),
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
        "state": _serialize_state(game.state, game),
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
        "state": _serialize_state(game.state, game),
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
        "state": _serialize_state(game.state, game),
    }


@app.post("/games/{game_id}/two-point-conversion")
def execute_two_point_conversion(game_id: str, request: TwoPointConversionRequest):
    """Execute a two-point conversion attempt after a human-scored touchdown."""
    game = _get_game(game_id)
    if game.state.is_over:
        raise HTTPException(status_code=400, detail="Game is over")
    if not game.state.pending_extra_point:
        raise HTTPException(
            status_code=400,
            detail="No touchdown pending — cannot attempt a two-point conversion right now.",
        )

    try:
        result, success = game.execute_two_point_conversion_attempt(
            play_type=request.play_type,
            player_name=request.player_name if request.player_name else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    result_desc = "Two-point conversion successful!" if success else "Two-point conversion failed"

    return {
        "game_id": game_id,
        "result": result_desc,
        "play_result": _serialize_play_result(result),
        "state": _serialize_state(game.state, game),
    }


@app.post("/games/{game_id}/pat-kick")
def execute_pat_kick(game_id: str):
    """Execute the PAT (point-after-touchdown) kick after a human-scored touchdown."""
    game = _get_game(game_id)
    if game.state.is_over:
        raise HTTPException(status_code=400, detail="Game is over")
    if not game.state.pending_extra_point:
        raise HTTPException(
            status_code=400,
            detail="No touchdown pending — cannot attempt a PAT kick right now.",
        )

    try:
        result = game.execute_pat_kick()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "game_id": game_id,
        "play_result": _serialize_play_result(result),
        "state": _serialize_state(game.state, game),
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
        "state": _serialize_state(game.state, game),
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
        "state": _serialize_state(game.state, game),
    }


@app.post("/games/{game_id}/rescind-two-minute-offense")
def rescind_two_minute_offense(game_id: str):
    """Voluntarily rescind two-minute offense mode."""
    game = _get_game(game_id)
    if game.state.is_over:
        raise HTTPException(status_code=400, detail="Game is over")

    game.rescind_two_minute_offense()
    return {
        "game_id": game_id,
        "message": "Two-minute offense rescinded",
        "two_minute_offense": False,
        "state": _serialize_state(game.state, game),
    }


# ─── No-Huddle Offense Endpoints ────────────────────────────────────────────

@app.post("/games/{game_id}/no-huddle-offense")
def declare_no_huddle_offense(game_id: str):
    """Declare no-huddle offense mode.

    No-huddle may be used at any time.  It halves clock time for non-stopping
    plays only.  It is auto-rescinded when the clock stops, an injury occurs,
    a substitution is made, or possession changes.
    """
    game = _get_game(game_id)
    if game.state.is_over:
        raise HTTPException(status_code=400, detail="Game is over")

    game.declare_no_huddle_offense()
    return {
        "game_id": game_id,
        "message": "No-huddle offense declared",
        "no_huddle_offense": True,
        "state": _serialize_state(game.state, game),
    }


@app.post("/games/{game_id}/rescind-no-huddle-offense")
def rescind_no_huddle_offense(game_id: str):
    """Voluntarily rescind no-huddle offense mode."""
    game = _get_game(game_id)
    if game.state.is_over:
        raise HTTPException(status_code=400, detail="Game is over")

    game.rescind_no_huddle_offense()
    return {
        "game_id": game_id,
        "message": "No-huddle offense rescinded",
        "no_huddle_offense": False,
        "state": _serialize_state(game.state, game),
    }


# ─── Depth Chart Endpoint ──────────────────────────────────────────────────

@app.get("/games/{game_id}/depth-chart")
def get_depth_chart(game_id: str, team: str = "home"):
    """Get full depth chart for a team in the current game."""
    game = _get_game(game_id)
    t = game.home_team if team == "home" else game.away_team
    unavailable = set(game.state.injuries)

    depth_chart: Dict[str, List[dict]] = {}

    # Offense
    pos_groups = {
        "QB": t.roster.qbs,
        "RB": t.roster.rbs,
        "WR": t.roster.wrs,
        "TE": t.roster.tes,
        "OL": t.roster.offensive_line,
        "K": t.roster.kickers,
        "P": t.roster.punters,
    }
    for pos, players in pos_groups.items():
        depth_chart[pos] = [_player_brief(p, unavailable) for p in players]

    # Defense — group by position type
    dl_players = [d for d in t.roster.defenders if d.position.upper() in
                  ("DE", "DT", "DL", "NT")]
    lb_players = [d for d in t.roster.defenders if d.position.upper() in
                  ("LB", "OLB", "ILB", "MLB")]
    db_players = [d for d in t.roster.defenders if d.position.upper() in
                  ("CB", "S", "SS", "FS", "DB")]
    depth_chart["DL"] = [_player_brief(p, unavailable) for p in dl_players]
    depth_chart["LB"] = [_player_brief(p, unavailable) for p in lb_players]
    depth_chart["DB"] = [_player_brief(p, unavailable) for p in db_players]

    return {
        "team": t.abbreviation,
        "team_name": f"{t.city} {t.name}",
        "depth_chart": depth_chart,
    }


# ─── Starting Lineup Endpoint ──────────────────────────────────────────────

@app.get("/games/{game_id}/starting-lineup")
def get_starting_lineup(game_id: str, team: str = "home"):
    """Get the current starting lineup for a team."""
    game = _get_game(game_id)
    t = game.home_team if team == "home" else game.away_team
    unavailable = set(game.state.injuries)
    lineup = t.get_standard_lineup()

    return {
        "team": t.abbreviation,
        "team_name": f"{t.city} {t.name}",
        "record": {"wins": t.wins, "losses": t.losses, "ties": t.ties},
        "offense": {
            pos: _player_brief(player, unavailable) if player else None
            for pos, player in lineup["offense"].items()
        },
        "offensive_line": [_player_brief(p, unavailable) for p in lineup["offensive_line"]],
        "defense": [_player_brief(p, unavailable) for p in lineup["defense"]],
        "returners": {
            kind: _player_brief(player, unavailable) if player else None
            for kind, player in lineup["returners"].items()
        },
    }


@app.post("/games/{game_id}/starting-lineup")
def set_starting_lineup(game_id: str, request: StartingLineupRequest):
    """Set the starting lineup for a team before or during the game."""
    game = _get_game(game_id)
    t = game.home_team if request.team == "home" else game.away_team

    changes_made = []

    if request.offense:
        pos_map = {
            "QB": t.roster.qbs, "RB": t.roster.rbs, "WR": t.roster.wrs,
            "WR1": t.roster.wrs, "WR2": t.roster.wrs, "WR3": t.roster.wrs,
            "TE": t.roster.tes, "K": t.roster.kickers, "P": t.roster.punters,
        }
        for pos, player_name in request.offense.items():
            player_list = pos_map.get(pos.upper())
            if not player_list:
                continue
            for i, p in enumerate(player_list):
                if p.player_name.lower() == player_name.lower() and i != 0:
                    player_list[0], player_list[i] = player_list[i], player_list[0]
                    changes_made.append(f"{player_name} → starter at {pos}")
                    break

    if request.defense:
        defenders = t.roster.defenders
        new_order = []
        remaining = list(defenders)
        for name in request.defense:
            found = None
            for d in remaining:
                if d.player_name.lower() == name.lower():
                    found = d
                    break
            if found:
                new_order.append(found)
                remaining.remove(found)
        new_order.extend(remaining)
        t.roster.defenders = new_order
        changes_made.append(f"Defense reordered ({len(request.defense)} starters)")

    return {
        "message": f"Lineup updated: {'; '.join(changes_made)}" if changes_made else "No changes made",
        "changes": changes_made,
        "state": _serialize_state(game.state, game),
    }


# ─── Display Boxes Endpoint ────────────────────────────────────────────────

@app.get("/games/{game_id}/display-boxes")
def get_display_boxes(game_id: str):
    """Get current defensive display box assignments (5E A-O boxes)."""
    game = _get_game(game_id)
    from .play_resolver import PlayResolver

    defense_team = game.get_defense_team()
    defenders = defense_team.roster.defenders[:11]
    unavailable = set(game.state.injuries)

    boxes = PlayResolver.assign_default_display_boxes(defenders)

    # Build box-to-player mapping
    box_assignments: Dict[str, Optional[dict]] = {}
    for box in "ABCDEFGHIJKLMNO":
        box_assignments[box] = None

    for player in defenders:
        box = boxes.get(player.player_name)
        if box:
            box_assignments[box] = _player_brief(player, unavailable)

    return {
        "defense_team": defense_team.abbreviation,
        "boxes": box_assignments,
        "rows": {
            "row1_dl": {b: box_assignments[b] for b in "ABCDE"},
            "row2_lb": {b: box_assignments[b] for b in "FGHIJ"},
            "row3_db": {b: box_assignments[b] for b in "KLMNO"},
        },
    }


# ─── Position Flexibility Endpoint ─────────────────────────────────────────

COMPATIBLE_POSITIONS: Dict[str, set] = {
    # Defensive position compatibility
    "DE": {"DT", "DL", "NT", "LB", "OLB"},
    "DT": {"DE", "DL", "NT"},
    "DL": {"DE", "DT", "NT"},
    "NT": {"DT", "DL", "DE"},
    "LB": {"OLB", "ILB", "MLB", "DE"},
    "OLB": {"LB", "ILB", "MLB", "DE"},
    "ILB": {"LB", "OLB", "MLB"},
    "MLB": {"LB", "OLB", "ILB"},
    "CB": {"S", "SS", "FS", "DB"},
    "S": {"SS", "FS", "CB", "DB"},
    "SS": {"S", "FS", "CB", "DB"},
    "FS": {"S", "SS", "CB", "DB"},
    "DB": {"CB", "S", "SS", "FS"},
    # Offensive skill position compatibility
    "RB": {"WR", "TE"},
    "WR": {"RB", "TE"},
    "TE": {"WR", "RB"},
    # Offensive line position compatibility
    "LT": {"LG", "OL"},
    "LG": {"LT", "C", "OL"},
    "C": {"LG", "RG", "OL"},
    "RG": {"LG", "C", "RT", "OL"},
    "RT": {"RG", "OL"},
    "OL": {"LT", "LG", "C", "RG", "RT"},
}


@app.post("/games/{game_id}/position-change")
def change_player_position(game_id: str, request: PositionChangeRequest):
    """Change a player's position (within compatible positions per 5E rules).

    Note: Playing out of position incurs penalties per 5E rules:
    - OL out of position: -1 to Blocking and Pass Blocking Values
    - CB/S out of position: -1 to Pass Defense Values
    """
    game = _get_game(game_id)
    new_pos = request.new_position.upper()

    # Search all players on both teams
    for t in [game.home_team, game.away_team]:
        for player in t.roster.all_players():
            if player.player_name.lower() == request.player_name.lower():
                old_pos = player.position.upper()
                compatible = COMPATIBLE_POSITIONS.get(old_pos, set())
                if new_pos not in compatible:
                    raise HTTPException(
                        status_code=400,
                        detail=f"{old_pos} cannot move to {new_pos}. Compatible: {sorted(compatible)}",
                    )
                player.position = new_pos
                game.state.play_log.append(
                    f"POSITION CHANGE: {player.player_name} moved from {old_pos} to {new_pos}"
                )
                return {
                    "message": f"{player.player_name} moved from {old_pos} to {new_pos}",
                    "old_position": old_pos,
                    "new_position": new_pos,
                    "penalty_note": "Out-of-position penalty may apply (-1 to relevant ratings)",
                    "state": _serialize_state(game.state, game),
                }

    raise HTTPException(status_code=404, detail=f"Player '{request.player_name}' not found")


# ─── On-Field Slot Assignment Endpoints ────────────────────────────────────

def _resolve_side(game: Game, team_param: str) -> str:
    """Resolve 'possession', 'home', or 'away' to 'home' or 'away'."""
    if team_param == "possession":
        return game.state.possession
    if team_param in ("home", "away"):
        return team_param
    raise HTTPException(
        status_code=400,
        detail=f"Invalid team value '{team_param}'. Use 'home', 'away', or 'possession'.",
    )


@app.post("/games/{game_id}/set-field-slot")
def set_field_slot(game_id: str, request: SetFieldSlotRequest):
    """Assign (or clear) a player to an on-field formation slot.

    Skill slots: FL, LE, RE, BK1, BK2, BK3
    OL slots:    LT, LG, C, RG, RT

    Passing ``player_name`` as null or empty string clears the slot and
    reverts it to automatic roster-order selection.

    This does not restrict which position a player can fill — you can place
    a TE in the FL slot to run a 3-TE package.  The assignment takes effect
    on the very next play call.
    """
    game = _get_game(game_id)
    side = _resolve_side(game, request.team)
    try:
        msg = game.set_field_slot(side, request.slot, request.player_name or None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "message": msg,
        "on_field_assignments": game.get_field_assignments(side),
        "state": _serialize_state(game.state, game),
    }


@app.get("/games/{game_id}/on-field-assignments")
def get_on_field_assignments(game_id: str, team: str = "possession"):
    """Get the current on-field slot overrides for an offense."""
    game = _get_game(game_id)
    side = _resolve_side(game, team)
    return {
        "team": side,
        "on_field_assignments": game.get_field_assignments(side),
    }


@app.post("/games/{game_id}/apply-package")
def apply_formation_package(game_id: str, request: ApplyPackageRequest):
    """Apply a named formation package to the offense.

    Packages
    --------
    ``STANDARD``  — clear all overrides (roster-order auto-select).
    ``2TE_1WR``   — WR1→LE, TE1→RE, TE2→FL (two-TE set, one wide receiver).
    ``3TE``       — TE1→RE, TE2→LE, TE3→FL (three-TE set).
    ``JUMBO``     — same as 3TE, logged as Jumbo.
    ``4WR``       — WR1→LE, WR2→FL, WR3→RE (four-wide, no TE).
    ``3RB``       — WR1→LE (split end on line), TE1→RE (tight end on line),
                    RB1→BK1, RB2→BK2, RB3→BK3; FL absent.
                    7-man line: 5 OL + LE + RE ✓  (power run, no flanker).
    """
    game = _get_game(game_id)
    side = _resolve_side(game, request.team)
    try:
        msg = game.apply_formation_package(side, request.package)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "message": msg,
        "package": request.package.upper(),
        "on_field_assignments": game.get_field_assignments(side),
        "state": _serialize_state(game.state, game),
    }


@app.post("/games/{game_id}/apply-defense-package")
def apply_defense_package(game_id: str, request: ApplyDefensePackageRequest):
    """Apply a named coverage/rush package to the defense.

    Reorders the defensive roster so the desired mix of DL / LB / DB occupies
    the first 11 slots (the on-field unit).  Changes take effect on the next
    play.

    Packages
    --------
    ``STANDARD``  — 4-3 base: 4 DL + 3 LB + 4 DB.
    ``NICKEL``    — 4-2-5: 4 DL, 2 LB, 5 DB (drop 1 LB, add 1 DB).
    ``DIME``      — 4-1-6: 4 DL, 1 LB, 6 DB (drop 2 LBs, add 2 DBs).
    ``335``       — 3-3-5: 3 DL, 3 LB, 5 DB (nickel 3-4 look).
    ``PREVENT``   — 2-2-7: 2 DL, 2 LB, 7 DB (prevent/deep coverage).
    """
    game = _get_game(game_id)
    # Resolve which team is on defense
    team_param = request.team.lower()
    if team_param == "defense":
        side = game.state.get_defense_team()  # "home" or "away"
    else:
        side = _resolve_side(game, team_param)
    try:
        msg = game.apply_defense_package(side, request.package)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "message": msg,
        "package": request.package.upper(),
        "state": _serialize_state(game.state, game),
    }


# ─── Defensive Substitution Endpoint ───────────────────────────────────────

@app.post("/games/{game_id}/substitute-defense")
def substitute_defense_player(game_id: str, request: SubstitutionRequest):
    """Substitute a player on the defensive team."""
    game = _get_game(game_id)

    defense_team = game.get_defense_team()
    defenders = defense_team.roster.defenders

    pos = request.position.upper()
    DEF_POS_MAP = {
        "DL": ("DE", "DT", "DL", "NT"),
        "LB": ("LB", "OLB", "ILB", "MLB"),
        "DB": ("CB", "S", "SS", "FS", "DB"),
        "DE": ("DE",), "DT": ("DT",), "NT": ("NT",),
        "CB": ("CB",), "S": ("S",), "SS": ("SS",), "FS": ("FS",),
        "OLB": ("OLB",), "ILB": ("ILB",), "MLB": ("MLB",),
    }

    valid_positions = DEF_POS_MAP.get(pos)
    if not valid_positions:
        raise HTTPException(status_code=400, detail=f"Invalid defensive position: {pos}")

    player_in_obj = None
    player_in_idx = None
    player_out_idx = None
    for i, p in enumerate(defenders):
        if p.player_name.lower() == request.player_in.lower():
            player_in_obj = p
            player_in_idx = i
        if p.player_name.lower() == request.player_out.lower():
            player_out_idx = i

    if player_in_obj is None:
        raise HTTPException(status_code=404, detail=f"Player '{request.player_in}' not found on defense")
    if player_out_idx is None:
        raise HTTPException(status_code=404, detail=f"Player '{request.player_out}' not found on defense")

    # Compute box assignments BEFORE the swap so we can log the outgoing player's box.
    pre_boxes = PlayResolver.assign_default_display_boxes(list(defenders[:11]))
    out_box = pre_boxes.get(request.player_out, "?")

    defenders[player_out_idx], defenders[player_in_idx] = (
        defenders[player_in_idx], defenders[player_out_idx]
    )

    # Compute box assignments AFTER the swap to find the incoming player's new box.
    post_boxes = PlayResolver.assign_default_display_boxes(list(defenders[:11]))
    in_box = post_boxes.get(request.player_in, "?")

    game.state.play_log.append(
        f"DEF SUB: {request.player_in} ({pos}) — Box {in_box} "
        f"replaces {request.player_out} ({pos}) — Box {out_box}"
    )

    return {
        "message": f"{request.player_in} now starting at {pos} on defense",
        "state": _serialize_state(game.state, game),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
