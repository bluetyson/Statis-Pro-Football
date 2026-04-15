"""Tests for human-provided run direction being preserved (not overridden by AI)."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.game import Game
from engine.solitaire import PlayCall
from engine.team import Team


def _load_team(abbr):
    """Load a 5E team from JSON."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "engine", "data", "2025_5e", f"{abbr}.json"
    )
    with open(path) as f:
        return Team.from_dict(json.load(f))


class TestHumanRunDirectionPreserved:
    """Verify that a human-selected run direction is never overwritten by the AI."""

    @pytest.mark.parametrize("direction", ["IR", "IL", "SR", "SL"])
    def test_direction_preserved_across_seeds(self, direction):
        """Run 20 plays with a fixed direction; every result must use that direction."""
        buf = _load_team("BUF")
        kc = _load_team("KC")

        for seed in range(20):
            game = Game(buf, kc, seed=seed)
            game.state.down = 1
            game.state.distance = 10
            game.state.yard_line = 30

            play_call = PlayCall(
                play_type="RUN",
                formation="UNDER_CENTER",
                direction=direction,
                reasoning="Human play call",
            )

            result = game.execute_play(play_call=play_call)

            # The offensive_play_call logged in the result must contain the
            # human-selected direction name (e.g. "Inside Right" for IR).
            direction_names = {
                "IR": "Inside Right",
                "IL": "Inside Left",
                "SR": "Sweep Right",
                "SL": "Sweep Left",
            }
            expected_name = direction_names[direction]
            assert expected_name in result.offensive_play_call, (
                f"seed={seed}: expected '{expected_name}' in offensive_play_call "
                f"but got '{result.offensive_play_call}'"
            )

            # Also verify via the play log that the correct direction appears
            offense_lines = [
                line for line in game.state.play_log if "OFFENSE:" in line
            ]
            assert any(expected_name in line for line in offense_lines), (
                f"seed={seed}: expected '{expected_name}' in play log OFFENSE line"
            )
