"""API coverage for play metadata exposed to the GUI."""

import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.api_server import app, _active_games


client = TestClient(app)


def setup_function():
    _active_games.clear()


def _new_game() -> str:
    response = client.post(
        "/games/new",
        json={
            "home_team": "CHI",
            "away_team": "GB",
            "season": "2025_5e",
            "solitaire_home": False,
            "solitaire_away": False,
        },
    )
    assert response.status_code == 200
    return response.json()["game_id"]


def test_run_play_response_includes_resolution_numbers():
    game_id = _new_game()

    response = client.post(
        f"/games/{game_id}/human-play",
        json={
            "play_type": "RUN",
            "direction": "MIDDLE",
            "formation": "UNDER_CENTER",
        },
    )

    assert response.status_code == 200
    play_result = response.json()["play_result"]
    assert 1 <= play_result["run_number"] <= 12
    assert play_result["pass_number"] is None
    assert play_result["defense_formation"] in {
        "4_3", "3_4", "NICKEL", "GOAL_LINE",
    }


def test_pass_play_response_includes_pass_number_and_optional_run_number():
    game_id = _new_game()

    response = client.post(
        f"/games/{game_id}/human-play",
        json={
            "play_type": "SHORT_PASS",
            "direction": "MIDDLE",
            "formation": "UNDER_CENTER",
        },
    )

    assert response.status_code == 200
    play_result = response.json()["play_result"]
    if play_result["pass_number"] is not None:
        assert 1 <= play_result["pass_number"] <= 48
    else:
        assert play_result["result"] == "SACK"
    if play_result["run_number"] is not None:
        assert 1 <= play_result["run_number"] <= 12
    assert play_result["defense_formation"] in {
        "4_3", "3_4", "NICKEL", "GOAL_LINE",
    }


def test_human_defense_response_keeps_called_formation():
    game_id = _new_game()

    response = client.post(
        f"/games/{game_id}/human-defense",
        json={"formation": "NICKEL", "defensive_play": "BLITZ"},
    )

    assert response.status_code == 200
    play_result = response.json()["play_result"]
    assert play_result["defense_formation"] == "NICKEL"


def test_team_endpoint_includes_team_card_and_returners():
    response = client.get("/teams/CHI?season=2025_5e")

    assert response.status_code == 200
    body = response.json()
    assert "team_card" in body
    assert body["team_card"]["offense"]["QB"]["position"] == "QB"
    assert len(body["team_card"]["kick_returners"]) >= 1
    assert len(body["team_card"]["punt_returners"]) >= 1


def test_human_play_rejects_explicit_injured_player():
    game_id = _new_game()
    game = _active_games[game_id]
    injured_rb = game.get_offense_team().roster.rbs[0].player_name
    game.state.injuries[injured_rb] = 4

    response = client.post(
        f"/games/{game_id}/human-play",
        json={
            "play_type": "RUN",
            "direction": "MIDDLE",
            "formation": "UNDER_CENTER",
            "player_name": injured_rb,
        },
    )

    assert response.status_code == 400
    assert "injured and unavailable" in response.json()["detail"]


def test_human_play_auto_subs_injured_starter():
    game_id = _new_game()
    game = _active_games[game_id]
    injured_rb = game.get_offense_team().roster.rbs[0].player_name
    backup_rb = game.get_offense_team().roster.rbs[1].player_name
    game.state.injuries[injured_rb] = 4

    response = client.post(
        f"/games/{game_id}/human-play",
        json={
            "play_type": "RUN",
            "direction": "MIDDLE",
            "formation": "UNDER_CENTER",
        },
    )

    assert response.status_code == 200
    play_result = response.json()["play_result"]
    assert play_result["personnel_note"] is not None
    assert backup_rb in play_result["personnel_note"]
    assert injured_rb not in {play_result.get("rusher"), play_result.get("receiver")}
