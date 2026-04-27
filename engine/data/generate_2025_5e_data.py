"""Regenerate 2025 team data using authentic Avalon Hill card formats.

This script reads the existing team data (from generate_2025_data.py) and
re-generates the player cards using authentic Statis Pro Football card layout:
  * QB: range-based passing (Com/Inc/Int boundaries for Quick/Short/Long),
        pass-rush ranges, 12-row rushing (N/SG/LG)
  * RB: 12-row rushing (N/SG/LG) + 12-row pass gain (Q/S/L) + blocks
  * WR: 12-row pass gain (Q/S/L), mostly blank rushing + blocks
  * TE: 12-row pass gain (Q/S/L), blank rushing + higher blocks
  * DEF: defender letters (A-M) for FAC blocking-matchup resolution

The output overwrites existing files in engine/data/2025_5e/.
"""
import sys
import os
import json
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from engine.card_generator import CardGenerator
from engine.team import Team, Roster
from engine.player_card import RECEIVER_LETTERS

random.seed(42)
gen = CardGenerator(seed=42)

INPUT_DIR = os.path.join(os.path.dirname(__file__), "2025")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "2025_5e")
os.makedirs(OUTPUT_DIR, exist_ok=True)

DEFENDER_LETTERS = list("ABCDEFGHIJKLM")


def upgrade_team(team_data: dict) -> dict:
    """Upgrade a team's player cards to authentic card format."""
    players = team_data.get("players", [])
    new_players = []

    abbr = team_data["abbreviation"]

    # Track receiver letter assignments
    receiver_idx = 0
    defender_idx = 0

    for p in players:
        pos = p.get("position", "")
        grade = p.get("overall_grade", "C")
        stats = p.get("stats_summary", {})

        if pos == "QB":
            card = gen.generate_qb_card_authentic(
                name=p["name"], team=abbr, number=p["number"],
                comp_pct=stats.get("comp_pct", 0.62),
                ypa=stats.get("ypa", 7.0),
                int_rate=stats.get("int_rate", 0.025),
                sack_rate=stats.get("sack_rate", 0.07),
                grade=grade,
                rush_ypc=stats.get("rush_ypc", 3.0),
                rush_fumble_rate=stats.get("rush_fumble_rate", 0.015),
            )
            new_players.append(card.to_dict())

        elif pos == "RB":
            # RBs get receiver letters if they're good pass catchers
            letter = ""
            if receiver_idx < 5:
                letter = RECEIVER_LETTERS[receiver_idx]
                receiver_idx += 1
            endurance_pass = 2  # Default moderate
            if stats.get("catch_rate", 0.3) >= 0.5:
                endurance_pass = 0  # Great pass-catching back
            elif stats.get("catch_rate", 0.3) >= 0.35:
                endurance_pass = 1
            elif stats.get("catch_rate", 0.3) < 0.2:
                endurance_pass = 4  # Rarely catches

            card = gen.generate_rb_card_authentic(
                name=p["name"], team=abbr, number=p["number"],
                ypc=stats.get("ypc", 4.0),
                fumble_rate=stats.get("fumble_rate", 0.015),
                grade=grade,
                catch_rate=stats.get("catch_rate", 0.3),
                avg_rec_yards=stats.get("avg_yards", 7.0),
                endurance_pass=endurance_pass,
                blocks=1,
                receiver_letter=letter,
            )
            new_players.append(card.to_dict())

        elif pos == "WR":
            letter = RECEIVER_LETTERS[receiver_idx] if receiver_idx < 5 else "E"
            receiver_idx += 1
            card = gen.generate_wr_card_authentic(
                name=p["name"], team=abbr, number=p["number"],
                catch_rate=stats.get("catch_rate", 0.65),
                avg_yards=stats.get("avg_yards", 11.0),
                grade=grade,
                receiver_letter=letter,
                blocks=-2,
            )
            new_players.append(card.to_dict())

        elif pos == "TE":
            letter = RECEIVER_LETTERS[receiver_idx] if receiver_idx < 5 else "E"
            receiver_idx += 1
            card = gen.generate_te_card_authentic(
                name=p["name"], team=abbr, number=p["number"],
                catch_rate=stats.get("catch_rate", 0.60),
                avg_yards=stats.get("avg_yards", 9.0),
                grade=grade,
                receiver_letter=letter,
                blocks=3,
            )
            new_players.append(card.to_dict())

        elif pos in ("K",):
            # Kicker — unchanged, copy as-is
            new_players.append(p)

        elif pos in ("P",):
            # Punter — unchanged, copy as-is
            new_players.append(p)

        elif pos in ("LT", "LG", "C", "RG", "RT", "OL"):
            # Offensive lineman — copy with OL ratings
            card = gen.generate_ol_card(
                name=p["name"], team=abbr, number=p["number"],
                position=pos, grade=grade,
                run_block=stats.get("run_block_rating", p.get("run_block_rating", 70)),
                pass_block=stats.get("pass_block_rating", p.get("pass_block_rating", 70)),
            )
            new_players.append(card.to_dict())

        elif pos in ("DL", "DE", "DT", "LB", "CB", "S", "DEF"):
            letter = DEFENDER_LETTERS[defender_idx] if defender_idx < 13 else ""
            defender_idx += 1
            card = gen.generate_def_card_5e(
                name=p["name"], team=abbr, number=p["number"],
                position=pos, grade=grade,
                pass_rush=stats.get("pass_rush_rating", p.get("pass_rush_rating", 50)),
                coverage=stats.get("coverage_rating", p.get("coverage_rating", 50)),
                run_stop=stats.get("run_stop_rating", p.get("run_stop_rating", 50)),
                defender_letter=letter,
            )
            new_players.append(card.to_dict())

        else:
            # Unknown position — copy as-is
            new_players.append(p)

    result = dict(team_data)
    result["players"] = new_players
    result["edition"] = "5e"
    return result


def main():
    if not os.path.exists(INPUT_DIR):
        print(f"Input directory {INPUT_DIR} does not exist. Run generate_2025_data.py first.")
        return

    team_files = sorted(f for f in os.listdir(INPUT_DIR) if f.endswith(".json"))
    print(f"Upgrading {len(team_files)} teams from {INPUT_DIR} → {OUTPUT_DIR}")

    for fname in team_files:
        input_path = os.path.join(INPUT_DIR, fname)
        output_path = os.path.join(OUTPUT_DIR, fname)

        with open(input_path) as f:
            team_data = json.load(f)

        upgraded = upgrade_team(team_data)

        with open(output_path, "w") as f:
            json.dump(upgraded, f, indent=2)

        abbr = team_data.get("abbreviation", fname)
        n_players = len(upgraded["players"])
        print(f"  {abbr}: {n_players} players → {output_path}")

    print(f"Done! Generated {len(team_files)} authentic-format team files.")


if __name__ == "__main__":
    main()
