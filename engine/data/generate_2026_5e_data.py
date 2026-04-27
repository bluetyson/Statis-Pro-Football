"""Regenerate 2026 team data using authentic Avalon Hill card formats.

This script reads the existing team data (from generate_2026_data.py) and
re-generates the player cards using authentic Statis Pro Football card layout:
  * QB: range-based passing (Com/Inc/Int boundaries for Quick/Short/Long),
        pass-rush ranges, 12-row rushing (N/SG/LG)
  * RB: 12-row rushing (N/SG/LG) + 12-row pass gain (Q/S/L) + blocks
  * WR: 12-row pass gain (Q/S/L), mostly blank rushing + blocks
  * TE: 12-row pass gain (Q/S/L), blank rushing + higher blocks
  * DEF: Avalon Hill formula ratings derived from real 2024 team defensive stats
         (team YPA → DB/LB pass-defense ratings; rush yards → tackle ratings)
  * OL:  Avalon Hill formula ratings derived from real 2024 team offensive stats
         (rush yards/game → run-block ratings; sacks allowed → pass-block ratings)

All defensive and OL ratings use only Avalon Hill formulae — no legacy 0–100
scale values.  The output overwrites existing files in engine/data/2026_5e/.
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

INPUT_DIR = os.path.join(os.path.dirname(__file__), "2026")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "2026_5e")
os.makedirs(OUTPUT_DIR, exist_ok=True)

DEFENDER_LETTERS = list("ABCDEFGHIJKLM")

# ═══════════════════════════════════════════════════════════════════════════════
# REAL 2024 NFL TEAM DEFENSIVE STATS (used for Avalon Hill formula ratings)
# Source: footballdb.com 2024 regular season
# ═══════════════════════════════════════════════════════════════════════════════

TEAM_STATS_2024 = {
    # AFC East
    "BUF": {"def_ypa": 6.42, "def_rush_yds_game": 109.6, "off_rush_yds_game": 124.4, "sacks_allowed": 28, "pass_attempts": 542},
    "MIA": {"def_ypa": 7.18, "def_rush_yds_game": 101.8, "off_rush_yds_game": 115.8, "sacks_allowed": 32, "pass_attempts": 548},
    "NE":  {"def_ypa": 6.88, "def_rush_yds_game": 119.4, "off_rush_yds_game": 102.4, "sacks_allowed": 48, "pass_attempts": 518},
    "NYJ": {"def_ypa": 6.52, "def_rush_yds_game": 100.4, "off_rush_yds_game": 108.2, "sacks_allowed": 38, "pass_attempts": 496},
    # AFC North
    "BAL": {"def_ypa": 7.15, "def_rush_yds_game": 80.1, "off_rush_yds_game": 156.6, "sacks_allowed": 22, "pass_attempts": 498},
    "CIN": {"def_ypa": 7.42, "def_rush_yds_game": 112.8, "off_rush_yds_game": 102.5, "sacks_allowed": 35, "pass_attempts": 567},
    "CLE": {"def_ypa": 6.72, "def_rush_yds_game": 100.6, "off_rush_yds_game": 108.6, "sacks_allowed": 45, "pass_attempts": 512},
    "PIT": {"def_ypa": 6.38, "def_rush_yds_game": 98.7, "off_rush_yds_game": 118.2, "sacks_allowed": 40, "pass_attempts": 502},
    # AFC South
    "HOU": {"def_ypa": 6.58, "def_rush_yds_game": 100.4, "off_rush_yds_game": 112.4, "sacks_allowed": 30, "pass_attempts": 534},
    "IND": {"def_ypa": 7.28, "def_rush_yds_game": 126.5, "off_rush_yds_game": 104.2, "sacks_allowed": 36, "pass_attempts": 548},
    "JAX": {"def_ypa": 7.94, "def_rush_yds_game": 127.6, "off_rush_yds_game": 102.8, "sacks_allowed": 42, "pass_attempts": 580},
    "TEN": {"def_ypa": 6.80, "def_rush_yds_game": 133.5, "off_rush_yds_game": 108.4, "sacks_allowed": 52, "pass_attempts": 473},
    # AFC West
    "DEN": {"def_ypa": 6.22, "def_rush_yds_game": 96.4, "off_rush_yds_game": 98.6, "sacks_allowed": 38, "pass_attempts": 524},
    "KC":  {"def_ypa": 6.48, "def_rush_yds_game": 101.2, "off_rush_yds_game": 118.4, "sacks_allowed": 25, "pass_attempts": 534},
    "LV":  {"def_ypa": 7.62, "def_rush_yds_game": 79.8, "off_rush_yds_game": 92.4, "sacks_allowed": 48, "pass_attempts": 542},
    "LAC": {"def_ypa": 6.28, "def_rush_yds_game": 101.8, "off_rush_yds_game": 108.2, "sacks_allowed": 30, "pass_attempts": 518},
    # NFC East
    "DAL": {"def_ypa": 7.32, "def_rush_yds_game": 137.1, "off_rush_yds_game": 112.6, "sacks_allowed": 35, "pass_attempts": 548},
    "NYG": {"def_ypa": 7.48, "def_rush_yds_game": 131.2, "off_rush_yds_game": 108.4, "sacks_allowed": 50, "pass_attempts": 524},
    "PHI": {"def_ypa": 6.03, "def_rush_yds_game": 104.3, "off_rush_yds_game": 142.8, "sacks_allowed": 24, "pass_attempts": 542},
    "WSH": {"def_ypa": 7.04, "def_rush_yds_game": 137.5, "off_rush_yds_game": 108.6, "sacks_allowed": 38, "pass_attempts": 496},
    "WAS": {"def_ypa": 7.04, "def_rush_yds_game": 137.5, "off_rush_yds_game": 108.6, "sacks_allowed": 38, "pass_attempts": 496},
    # NFC North
    "CHI": {"def_ypa": 6.82, "def_rush_yds_game": 136.3, "off_rush_yds_game": 144.5, "sacks_allowed": 45, "pass_attempts": 485},
    "DET": {"def_ypa": 7.18, "def_rush_yds_game": 98.4, "off_rush_yds_game": 114.6, "sacks_allowed": 26, "pass_attempts": 567},
    "GB":  {"def_ypa": 6.58, "def_rush_yds_game": 100.4, "off_rush_yds_game": 112.4, "sacks_allowed": 32, "pass_attempts": 534},
    "MIN": {"def_ypa": 6.42, "def_rush_yds_game": 93.4, "off_rush_yds_game": 102.8, "sacks_allowed": 34, "pass_attempts": 518},
    # NFC South
    "ATL": {"def_ypa": 7.28, "def_rush_yds_game": 124.5, "off_rush_yds_game": 108.4, "sacks_allowed": 32, "pass_attempts": 548},
    "CAR": {"def_ypa": 7.82, "def_rush_yds_game": 179.8, "off_rush_yds_game": 92.6, "sacks_allowed": 55, "pass_attempts": 482},
    "NO":  {"def_ypa": 7.38, "def_rush_yds_game": 141.4, "off_rush_yds_game": 98.4, "sacks_allowed": 40, "pass_attempts": 524},
    "TB":  {"def_ypa": 6.88, "def_rush_yds_game": 97.8, "off_rush_yds_game": 108.2, "sacks_allowed": 30, "pass_attempts": 534},
    # NFC West
    "ARI": {"def_ypa": 7.52, "def_rush_yds_game": 125.4, "off_rush_yds_game": 98.6, "sacks_allowed": 42, "pass_attempts": 548},
    "LAR": {"def_ypa": 6.92, "def_rush_yds_game": 106.4, "off_rush_yds_game": 108.4, "sacks_allowed": 34, "pass_attempts": 534},
    "SF":  {"def_ypa": 6.18, "def_rush_yds_game": 100.6, "off_rush_yds_game": 142.4, "sacks_allowed": 28, "pass_attempts": 498},
    "SEA": {"def_ypa": 7.08, "def_rush_yds_game": 122.4, "off_rush_yds_game": 108.2, "sacks_allowed": 38, "pass_attempts": 534},
}


# ═══════════════════════════════════════════════════════════════════════════════
# AVALON HILL FORMULA FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def team_ypa_to_db_ratings(ypa: float) -> list:
    """Convert team defensive YPA to DB pass-defense ratings (7 values)."""
    ERA_1980S_AVG = 6.8
    ERA_2024_AVG = 7.1
    ypa = ypa * (ERA_1980S_AVG / ERA_2024_AVG)
    if ypa <= 5.2: return [-4, -3, -2, -1, 0, 0, 1]
    if ypa <= 5.4: return [-4, -3, -1, 0, 0, 1, 1]
    if ypa <= 5.6: return [-4, -2, -1, 0, 0, 1, 1]
    if ypa <= 5.8: return [-4, -2, -1, 0, 1, 1, 2]
    if ypa <= 6.0: return [-3, -2, -1, 0, 1, 1, 2]
    if ypa <= 6.2: return [-3, -2, -1, 1, 1, 2, 2]
    if ypa <= 6.4: return [-3, -2, 0, 1, 2, 2, 2]
    if ypa <= 6.6: return [-3, -1, 0, 1, 2, 2, 3]
    if ypa <= 6.8: return [-2, -1, 0, 1, 2, 3, 3]
    if ypa <= 7.0: return [-2, -1, 0, 2, 2, 3, 3]
    if ypa <= 7.2: return [-2, -1, 1, 2, 3, 3, 3]
    if ypa <= 7.4: return [-2, -1, 2, 2, 3, 3, 4]
    if ypa <= 7.6: return [-1, 0, 2, 2, 3, 4, 4]
    if ypa <= 7.8: return [-1, 0, 2, 3, 3, 4, 4]
    if ypa <= 8.0: return [0, -1, 2, 3, 4, 4, 4]
    return [0, 0, 2, 3, 4, 4, 4]


def team_ypa_to_lb_ratings(ypa: float) -> list:
    """Convert team defensive YPA to LB pass-defense ratings (8 values)."""
    ERA_1980S_AVG = 6.8
    ERA_2024_AVG = 7.1
    ypa = ypa * (ERA_1980S_AVG / ERA_2024_AVG)
    if ypa <= 5.2: return [-3, -2, -2, -1, 1, 0, 1, 2]
    if ypa <= 5.4: return [-3, -2, -1, 1, 1, 1, 2, 2]
    if ypa <= 5.6: return [-3, -1, -1, 0, 1, 2, 2, 3]
    if ypa <= 5.8: return [-3, -1, 0, 0, 1, 2, 3, 3]
    if ypa <= 6.0: return [-2, -1, 0, 0, 1, 2, 3, 3]
    if ypa <= 6.2: return [-2, -1, 0, 1, 1, 2, 3, 3]
    if ypa <= 6.4: return [-2, 0, 0, 1, 2, 2, 3, 3]
    if ypa <= 6.6: return [-2, 0, 0, 1, 2, 2, 3, 3]
    if ypa <= 6.8: return [-1, 0, 0, 1, 2, 2, 3, 3]
    if ypa <= 7.0: return [-1, 0, 0, 2, 2, 3, 3, 3]
    if ypa <= 7.2: return [-1, 0, 1, 2, 2, 3, 3, 3]
    if ypa <= 7.4: return [-1, 0, 2, 2, 2, 3, 3, 4]
    if ypa <= 7.6: return [0, 0, 2, 2, 3, 3, 3, 4]
    if ypa <= 7.8: return [0, 0, 2, 2, 3, 3, 4, 4]
    if ypa <= 8.0: return [0, 2, 0, 3, 2, 3, 4, 4]
    return [0, 0, 2, 3, 4, 4, 4, 4]


def team_rush_yds_to_tackle_ratings(rush_yds: float, is_dl: bool) -> list:
    """Convert team rushing yards allowed/game to tackle ratings."""
    if is_dl:
        if rush_yds <= 85: return [-3, -3, -4, -2, -2, -2]
        if rush_yds <= 92: return [-3, -3, -4, -2, -1, -1]
        if rush_yds <= 99: return [-3, -3, -4, -2, -1, -1]
        if rush_yds <= 105: return [-2, -2, -4, -2, -1, -1]
        if rush_yds <= 112: return [-2, -2, -3, -2, -1, -1]
        if rush_yds <= 119: return [-2, -2, -3, -1, -1, -1]
        if rush_yds <= 125: return [-3, -2, -1, -1, 0, 0]
        if rush_yds <= 132: return [-2, -1, -1, 0, 0, 1]
        if rush_yds <= 139: return [-2, -1, -1, 0, 0, 1]
        if rush_yds <= 145: return [-2, -1, 0, 0, 1, 2]
        if rush_yds <= 152: return [-1, -1, 0, 0, 1, 2]
        if rush_yds <= 159: return [-1, -1, 0, 0, 1, 2]
        if rush_yds <= 165: return [-1, 0, 0, 1, 2, 2]
        if rush_yds <= 172: return [-1, 0, 1, 1, 2, 3]
        if rush_yds <= 179: return [0, 0, 1, 2, 3, 3]
        return [0, 1, 1, 2, 3, 4]
    else:
        if rush_yds <= 85: return [-5, -4, -3, -2, -1, 0, 1, 2]
        if rush_yds <= 92: return [-5, -4, -3, -2, -1, 0, 1, 2]
        if rush_yds <= 99: return [-5, -4, -2, -1, 0, 1, 2, 3]
        if rush_yds <= 105: return [-4, -3, -2, -1, 0, 1, 2, 3]
        if rush_yds <= 112: return [-4, -3, -2, -1, 0, 1, 2, 3]
        if rush_yds <= 119: return [-4, -3, -2, -1, 0, 1, 2, 3]
        if rush_yds <= 125: return [-3, -2, -1, 0, 1, 2, 3, 3]
        if rush_yds <= 132: return [-3, -2, -1, 0, 1, 2, 3, 4]
        if rush_yds <= 139: return [-2, -1, 0, 1, 2, 3, 3, 4]
        if rush_yds <= 145: return [-2, -1, 0, 1, 2, 3, 4, 4]
        if rush_yds <= 152: return [-2, -1, 0, 1, 2, 3, 4, 4]
        if rush_yds <= 159: return [-1, 0, 1, 2, 3, 4, 4, 4]
        if rush_yds <= 165: return [-1, 0, 1, 2, 3, 4, 4, 4]
        if rush_yds <= 172: return [0, 1, 2, 3, 4, 4, 4, 4]
        if rush_yds <= 179: return [0, 1, 2, 3, 4, 4, 4, 4]
        return [1, 2, 3, 3, 4, 4, 4, 4]


def team_off_yds_to_run_block(rush_yds: float) -> list:
    """Convert team rushing yards/game to OL run-blocking ratings (8 values)."""
    if rush_yds >= 150: return [4, 4, 3, 3, 3, 1, 1, 2]
    if rush_yds >= 140: return [4, 4, 3, 3, 2, 2, 1, 1]
    if rush_yds >= 130: return [4, 3, 3, 3, 2, 2, 1, 1]
    if rush_yds >= 120: return [3, 4, 3, 2, 2, 1, 1, 0]
    if rush_yds >= 110: return [4, 3, 3, 2, 1, 1, 0, 0]
    if rush_yds >= 105: return [3, 3, 3, 2, 1, 0, 0, 0]
    if rush_yds >= 100: return [3, 3, 2, 2, 1, 0, 0, -1]
    if rush_yds >= 95:  return [3, 2, 2, 1, 1, 0, -1, -1]
    if rush_yds >= 90:  return [2, 2, 2, 1, 1, 0, -1, -1]
    if rush_yds >= 80:  return [2, 2, 2, 1, 0, -1, -1, -1]
    return [2, 2, 1, 1, 0, 0, -1, -1]


def team_sacks_to_pass_block(sacks: int, pass_attempts: int = None) -> list:
    """Convert team sacks allowed to OL pass-blocking ratings (8 values)."""
    if pass_attempts:
        sacks = sacks * (32 / 33) * (550 / pass_attempts)
    if sacks <= 15: return [3, 3, 2, 2, 1, 1, 1, 1]
    if sacks <= 22: return [3, 3, 2, 2, 1, 1, 1, 0]
    if sacks <= 29: return [3, 3, 2, 1, 0, 0, 0, 0]
    if sacks <= 35: return [3, 2, 2, 1, 1, 0, 0, 0]
    if sacks <= 42: return [3, 2, 1, 1, 1, 0, 0, -1]
    if sacks <= 49: return [2, 3, 1, 1, 0, 0, -1, -1]
    if sacks <= 55: return [2, 2, 1, 1, 0, -1, -1, -1]
    if sacks <= 62: return [2, 2, 1, 0, 0, -1, -1, -1]
    return [1, 1, 1, 0, 0, -1, -1, -1]


def upgrade_team(team_data: dict) -> dict:
    """Upgrade a team's player cards to authentic Avalon Hill card format."""
    players = team_data.get("players", [])
    new_players = []

    abbr = team_data["abbreviation"]

    # Compute Avalon Hill team-level ratings from real 2024 stats
    team_stats = TEAM_STATS_2024.get(abbr, {})
    def_ypa = team_stats.get("def_ypa", 7.0)
    def_rush_yds = team_stats.get("def_rush_yds_game", 110.0)
    off_rush_yds = team_stats.get("off_rush_yds_game", 110.0)
    sacks_allowed = team_stats.get("sacks_allowed", 35)
    pass_attempts = team_stats.get("pass_attempts", 530)

    db_pass_def = team_ypa_to_db_ratings(def_ypa)
    lb_pass_def = team_ypa_to_lb_ratings(def_ypa)
    dl_tackle = team_rush_yds_to_tackle_ratings(def_rush_yds, is_dl=True)
    lb_tackle = team_rush_yds_to_tackle_ratings(def_rush_yds, is_dl=False)
    ol_run = team_off_yds_to_run_block(off_rush_yds)
    ol_pass = team_sacks_to_pass_block(sacks_allowed, pass_attempts)

    # Track position-group indices
    receiver_idx = 0
    defender_idx = 0
    dl_idx = 0
    lb_idx = 0
    db_idx = 0
    ol_idx = 0

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
            # Offensive lineman — Avalon Hill team-level run/pass block ratings
            card = gen.generate_ol_card(
                name=p["name"], team=abbr, number=p["number"],
                position=pos, grade=grade,
                run_block=ol_run[ol_idx] if ol_idx < len(ol_run) else 0,
                pass_block=ol_pass[ol_idx] if ol_idx < len(ol_pass) else 0,
            )
            ol_idx += 1
            new_players.append(card.to_dict())

        elif pos in ("DL", "DE", "DT", "LB", "CB", "S", "DEF"):
            letter = DEFENDER_LETTERS[defender_idx] if defender_idx < 13 else ""
            defender_idx += 1

            # Individual pass-rush from player's own sack data (0-100 auto-converts);
            # team-level tackle and pass-defense come from Avalon Hill formulae.
            pos_upper = pos.upper()
            if pos_upper in ("DE", "DT", "DL", "NT", "EDGE"):
                tackle = dl_tackle[dl_idx] if dl_idx < len(dl_tackle) else 0
                coverage = 0
                dl_idx += 1
            elif pos_upper in ("LB", "OLB", "ILB", "MLB"):
                tackle = lb_tackle[lb_idx] if lb_idx < len(lb_tackle) else 0
                coverage = lb_pass_def[lb_idx] if lb_idx < len(lb_pass_def) else 0
                lb_idx += 1
            else:  # CB, S, DB
                tackle = 0
                coverage = db_pass_def[db_idx] if db_idx < len(db_pass_def) else 0
                db_idx += 1

            # pass_rush uses the individual rating (0-100 auto-converted to AH 0-4)
            pass_rush = stats.get("pass_rush_rating", p.get("pass_rush_rating", 50))

            card = gen.generate_def_card_5e(
                name=p["name"], team=abbr, number=p["number"],
                position=pos, grade=grade,
                pass_rush=pass_rush,
                coverage=coverage,
                run_stop=tackle,
                defender_letter=letter,
            )
            new_players.append(card.to_dict())

        else:
            # Unknown position — copy as-is
            new_players.append(p)

    result = dict(team_data)
    result["players"] = new_players
    result["edition"] = "5e"
    # Remove legacy 0-100 team-level ratings
    result.pop("offense_rating", None)
    result.pop("defense_rating", None)
    return result


def main():
    if not os.path.exists(INPUT_DIR):
        print(f"Input directory {INPUT_DIR} does not exist. Run generate_2026_data.py first.")
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
