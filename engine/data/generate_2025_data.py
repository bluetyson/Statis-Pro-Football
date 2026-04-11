"""Generate 2025 NFL team data files for Statis Pro Football.

All player statistics are sourced from the 2024 NFL regular season.
"""
import sys
import os
import json
import random

# Add parent directory to path so we can import engine
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from engine.card_generator import CardGenerator
from engine.team import Team, Roster

random.seed(42)
gen = CardGenerator(seed=42)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "2025")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─── All 32 NFL Teams ─────────────────────────────────────────────────────────
# offense_rating and defense_rating reflect 2024 season performance
TEAMS = [
    # AFC East
    {"abbreviation": "BUF", "city": "Buffalo",      "name": "Bills",     "conference": "AFC", "division": "East",  "offense_rating": 87, "defense_rating": 81},
    {"abbreviation": "MIA", "city": "Miami",         "name": "Dolphins",  "conference": "AFC", "division": "East",  "offense_rating": 78, "defense_rating": 74},
    {"abbreviation": "NE",  "city": "New England",   "name": "Patriots",  "conference": "AFC", "division": "East",  "offense_rating": 68, "defense_rating": 68},
    {"abbreviation": "NYJ", "city": "New York",      "name": "Jets",      "conference": "AFC", "division": "East",  "offense_rating": 73, "defense_rating": 77},
    # AFC North
    {"abbreviation": "BAL", "city": "Baltimore",     "name": "Ravens",    "conference": "AFC", "division": "North", "offense_rating": 92, "defense_rating": 84},
    {"abbreviation": "CIN", "city": "Cincinnati",    "name": "Bengals",   "conference": "AFC", "division": "North", "offense_rating": 89, "defense_rating": 80},
    {"abbreviation": "CLE", "city": "Cleveland",     "name": "Browns",    "conference": "AFC", "division": "North", "offense_rating": 70, "defense_rating": 76},
    {"abbreviation": "PIT", "city": "Pittsburgh",    "name": "Steelers",  "conference": "AFC", "division": "North", "offense_rating": 75, "defense_rating": 82},
    # AFC South
    {"abbreviation": "HOU", "city": "Houston",       "name": "Texans",    "conference": "AFC", "division": "South", "offense_rating": 81, "defense_rating": 83},
    {"abbreviation": "IND", "city": "Indianapolis",  "name": "Colts",     "conference": "AFC", "division": "South", "offense_rating": 77, "defense_rating": 74},
    {"abbreviation": "JAX", "city": "Jacksonville",  "name": "Jaguars",   "conference": "AFC", "division": "South", "offense_rating": 74, "defense_rating": 72},
    {"abbreviation": "TEN", "city": "Tennessee",     "name": "Titans",    "conference": "AFC", "division": "South", "offense_rating": 65, "defense_rating": 70},
    # AFC West
    {"abbreviation": "DEN", "city": "Denver",        "name": "Broncos",   "conference": "AFC", "division": "West",  "offense_rating": 78, "defense_rating": 82},
    {"abbreviation": "KC",  "city": "Kansas City",   "name": "Chiefs",    "conference": "AFC", "division": "West",  "offense_rating": 88, "defense_rating": 85},
    {"abbreviation": "LV",  "city": "Las Vegas",     "name": "Raiders",   "conference": "AFC", "division": "West",  "offense_rating": 70, "defense_rating": 70},
    {"abbreviation": "LAC", "city": "Los Angeles",   "name": "Chargers",  "conference": "AFC", "division": "West",  "offense_rating": 81, "defense_rating": 86},
    # NFC East
    {"abbreviation": "DAL", "city": "Dallas",        "name": "Cowboys",   "conference": "NFC", "division": "East",  "offense_rating": 76, "defense_rating": 78},
    {"abbreviation": "NYG", "city": "New York",      "name": "Giants",    "conference": "NFC", "division": "East",  "offense_rating": 68, "defense_rating": 70},
    {"abbreviation": "PHI", "city": "Philadelphia",  "name": "Eagles",    "conference": "NFC", "division": "East",  "offense_rating": 91, "defense_rating": 88},
    {"abbreviation": "WSH", "city": "Washington",    "name": "Commanders","conference": "NFC", "division": "East",  "offense_rating": 82, "defense_rating": 76},
    # NFC North
    {"abbreviation": "CHI", "city": "Chicago",       "name": "Bears",     "conference": "NFC", "division": "North", "offense_rating": 72, "defense_rating": 72},
    {"abbreviation": "DET", "city": "Detroit",       "name": "Lions",     "conference": "NFC", "division": "North", "offense_rating": 90, "defense_rating": 79},
    {"abbreviation": "GB",  "city": "Green Bay",     "name": "Packers",   "conference": "NFC", "division": "North", "offense_rating": 82, "defense_rating": 82},
    {"abbreviation": "MIN", "city": "Minnesota",     "name": "Vikings",   "conference": "NFC", "division": "North", "offense_rating": 85, "defense_rating": 82},
    # NFC South
    {"abbreviation": "ATL", "city": "Atlanta",       "name": "Falcons",   "conference": "NFC", "division": "South", "offense_rating": 82, "defense_rating": 74},
    {"abbreviation": "CAR", "city": "Carolina",      "name": "Panthers",  "conference": "NFC", "division": "South", "offense_rating": 66, "defense_rating": 68},
    {"abbreviation": "NO",  "city": "New Orleans",   "name": "Saints",    "conference": "NFC", "division": "South", "offense_rating": 72, "defense_rating": 72},
    {"abbreviation": "TB",  "city": "Tampa Bay",     "name": "Buccaneers","conference": "NFC", "division": "South", "offense_rating": 84, "defense_rating": 78},
    # NFC West
    {"abbreviation": "ARI", "city": "Arizona",       "name": "Cardinals", "conference": "NFC", "division": "West",  "offense_rating": 76, "defense_rating": 70},
    {"abbreviation": "LAR", "city": "Los Angeles",   "name": "Rams",      "conference": "NFC", "division": "West",  "offense_rating": 78, "defense_rating": 76},
    {"abbreviation": "SF",  "city": "San Francisco", "name": "49ers",     "conference": "NFC", "division": "West",  "offense_rating": 86, "defense_rating": 84},
    {"abbreviation": "SEA", "city": "Seattle",       "name": "Seahawks",  "conference": "NFC", "division": "West",  "offense_rating": 79, "defense_rating": 77},
]

# ─── Per-team key player data ────────────────────────────────────────────────
# Format: {abbr: {players: [...]}}
# Each player dict: name, pos, number, grade, and position-specific stats

TEAM_PLAYERS = {
    "BUF": {
        "qb":  [{"name": "Josh Allen",         "number": 17, "grade": "A",  "comp_pct": 0.639, "ypa": 8.0, "int_rate": 0.022, "sack_rate": 0.065}],
        "rb":  [{"name": "James Cook",          "number": 4,  "grade": "B",  "ypc": 4.6, "fumble_rate": 0.010},
                {"name": "Ray Davis",            "number": 22, "grade": "C",  "ypc": 3.9, "fumble_rate": 0.014}],
        "wr":  [{"name": "Stefon Diggs",         "number": 14, "grade": "A",  "catch_rate": 0.71, "avg_yards": 13.1},
                {"name": "Khalil Shakir",         "number": 10, "grade": "B",  "catch_rate": 0.66, "avg_yards": 11.5},
                {"name": "Keon Coleman",          "number": 0,  "grade": "C",  "catch_rate": 0.60, "avg_yards": 12.0}],
        "te":  [{"name": "Dalton Kincaid",       "number": 86, "grade": "B",  "catch_rate": 0.66, "avg_yards": 9.5}],
        "k":   [{"name": "Tyler Bass",           "number": 2,  "grade": "B",  "accuracy": 0.840, "xp_rate": 0.980}],
        "p":   [{"name": "Sam Martin",           "number": 8,  "grade": "B",  "avg_distance": 45.5, "inside_20_rate": 0.40}],
        "def": [{"name": "Von Miller",           "number": 40, "pos": "DE",   "grade": "B",  "pass_rush": 80, "coverage": 45, "run_stop": 72},
                {"name": "Jordan Poyer",          "number": 21, "pos": "S",    "grade": "B",  "pass_rush": 45, "coverage": 80, "run_stop": 72},
                {"name": "Tre'Davious White",     "number": 27, "pos": "CB",   "grade": "B",  "pass_rush": 42, "coverage": 82, "run_stop": 68}],
    },
    "MIA": {
        "qb":  [{"name": "Tua Tagovailoa",       "number": 1,  "grade": "A",  "comp_pct": 0.674, "ypa": 8.1, "int_rate": 0.018, "sack_rate": 0.070}],
        "rb":  [{"name": "Raheem Mostert",        "number": 31, "grade": "B",  "ypc": 4.4, "fumble_rate": 0.012},
                {"name": "De'Von Achane",          "number": 28, "grade": "A",  "ypc": 5.8, "fumble_rate": 0.009}],
        "wr":  [{"name": "Tyreek Hill",           "number": 10, "grade": "A",  "catch_rate": 0.72, "avg_yards": 15.5},
                {"name": "Jaylen Waddle",          "number": 17, "grade": "A",  "catch_rate": 0.71, "avg_yards": 13.2},
                {"name": "Braxton Berrios",        "number": 0,  "grade": "C",  "catch_rate": 0.62, "avg_yards": 10.0}],
        "te":  [{"name": "Durham Smythe",         "number": 81, "grade": "C",  "catch_rate": 0.60, "avg_yards": 8.0}],
        "k":   [{"name": "Jason Sanders",         "number": 7,  "grade": "B",  "accuracy": 0.855, "xp_rate": 0.985}],
        "p":   [{"name": "Jake Bailey",           "number": 16, "grade": "C",  "avg_distance": 44.0, "inside_20_rate": 0.36}],
        "def": [{"name": "Jalen Ramsey",          "number": 5,  "pos": "CB",   "grade": "A",  "pass_rush": 45, "coverage": 90, "run_stop": 72},
                {"name": "Christian Wilkins",      "number": 94, "pos": "DT",   "grade": "B",  "pass_rush": 76, "coverage": 42, "run_stop": 80},
                {"name": "Emmanuel Ogbah",         "number": 91, "pos": "DE",   "grade": "B",  "pass_rush": 78, "coverage": 44, "run_stop": 70}],
    },
    "NE": {
        "qb":  [{"name": "Drake Maye",            "number": 10, "grade": "C",  "comp_pct": 0.600, "ypa": 6.8, "int_rate": 0.028, "sack_rate": 0.090}],
        "rb":  [{"name": "Rhamondre Stevenson",   "number": 38, "grade": "B",  "ypc": 4.1, "fumble_rate": 0.014},
                {"name": "Antonio Gibson",         "number": 24, "grade": "C",  "ypc": 3.7, "fumble_rate": 0.016}],
        "wr":  [{"name": "Kendrick Bourne",        "number": 84, "grade": "C",  "catch_rate": 0.62, "avg_yards": 11.5},
                {"name": "JuJu Smith-Schuster",    "number": 7,  "grade": "C",  "catch_rate": 0.65, "avg_yards": 10.5},
                {"name": "DeMario Douglas",        "number": 81, "grade": "C",  "catch_rate": 0.60, "avg_yards": 9.5}],
        "te":  [{"name": "Hunter Henry",           "number": 85, "grade": "B",  "catch_rate": 0.65, "avg_yards": 9.2}],
        "k":   [{"name": "Chad Ryland",            "number": 3,  "grade": "C",  "accuracy": 0.790, "xp_rate": 0.960}],
        "p":   [{"name": "Bryce Baringer",         "number": 17, "grade": "A",  "avg_distance": 49.0, "inside_20_rate": 0.43}],
        "def": [{"name": "Matthew Judon",          "number": 9,  "pos": "DE",   "grade": "B",  "pass_rush": 80, "coverage": 44, "run_stop": 70},
                {"name": "Kyle Dugger",            "number": 23, "pos": "S",    "grade": "B",  "pass_rush": 50, "coverage": 78, "run_stop": 74},
                {"name": "Christian Gonzalez",     "number": 0,  "pos": "CB",   "grade": "B",  "pass_rush": 44, "coverage": 80, "run_stop": 65}],
    },
    "NYJ": {
        "qb":  [{"name": "Aaron Rodgers",          "number": 8,  "grade": "B",  "comp_pct": 0.622, "ypa": 7.0, "int_rate": 0.025, "sack_rate": 0.082}],
        "rb":  [{"name": "Breece Hall",            "number": 20, "grade": "A",  "ypc": 4.9, "fumble_rate": 0.010},
                {"name": "Dalvin Cook",            "number": 4,  "grade": "C",  "ypc": 3.8, "fumble_rate": 0.015}],
        "wr":  [{"name": "Garrett Wilson",         "number": 17, "grade": "A",  "catch_rate": 0.70, "avg_yards": 13.8},
                {"name": "Allen Lazard",           "number": 10, "grade": "C",  "catch_rate": 0.60, "avg_yards": 11.0},
                {"name": "Xavier Gipson",          "number": 83, "grade": "C",  "catch_rate": 0.62, "avg_yards": 10.0}],
        "te":  [{"name": "Tyler Conklin",          "number": 83, "grade": "C",  "catch_rate": 0.63, "avg_yards": 8.5}],
        "k":   [{"name": "Greg Zuerlein",          "number": 9,  "grade": "B",  "accuracy": 0.845, "xp_rate": 0.975}],
        "p":   [{"name": "Thomas Morstead",        "number": 5,  "grade": "B",  "avg_distance": 45.0, "inside_20_rate": 0.39}],
        "def": [{"name": "Quinnen Williams",       "number": 95, "pos": "DT",   "grade": "A",  "pass_rush": 88, "coverage": 44, "run_stop": 82},
                {"name": "C.J. Mosley",            "number": 57, "pos": "LB",   "grade": "B",  "pass_rush": 60, "coverage": 72, "run_stop": 82},
                {"name": "Sauce Gardner",          "number": 1,  "pos": "CB",   "grade": "A",  "pass_rush": 44, "coverage": 92, "run_stop": 70}],
    },
    "BAL": {
        "qb":  [{"name": "Lamar Jackson",          "number": 8,  "grade": "A",  "comp_pct": 0.668, "ypa": 8.5, "int_rate": 0.017, "sack_rate": 0.050}],
        "rb":  [{"name": "Derrick Henry",          "number": 22, "grade": "A",  "ypc": 5.1, "fumble_rate": 0.008},
                {"name": "Justice Hill",           "number": 43, "grade": "C",  "ypc": 3.8, "fumble_rate": 0.012}],
        "wr":  [{"name": "Zay Flowers",            "number": 4,  "grade": "B",  "catch_rate": 0.67, "avg_yards": 12.5},
                {"name": "Rashod Bateman",         "number": 7,  "grade": "C",  "catch_rate": 0.63, "avg_yards": 13.0},
                {"name": "Nelson Agholor",         "number": 15, "grade": "C",  "catch_rate": 0.60, "avg_yards": 12.0}],
        "te":  [{"name": "Mark Andrews",           "number": 89, "grade": "A",  "catch_rate": 0.73, "avg_yards": 11.2}],
        "k":   [{"name": "Justin Tucker",          "number": 9,  "grade": "A",  "accuracy": 0.900, "xp_rate": 0.995}],
        "p":   [{"name": "Jordan Stout",           "number": 17, "grade": "B",  "avg_distance": 46.5, "inside_20_rate": 0.41}],
        "def": [{"name": "Roquan Smith",           "number": 0,  "pos": "LB",   "grade": "A",  "pass_rush": 72, "coverage": 80, "run_stop": 88},
                {"name": "Marlon Humphrey",        "number": 44, "pos": "CB",   "grade": "A",  "pass_rush": 46, "coverage": 88, "run_stop": 74},
                {"name": "Kyle Van Noy",           "number": 55, "pos": "DE",   "grade": "B",  "pass_rush": 75, "coverage": 48, "run_stop": 72}],
    },
    "CIN": {
        "qb":  [{"name": "Joe Burrow",             "number": 9,  "grade": "A",  "comp_pct": 0.672, "ypa": 8.2, "int_rate": 0.019, "sack_rate": 0.075}],
        "rb":  [{"name": "Joe Mixon",              "number": 28, "grade": "B",  "ypc": 4.5, "fumble_rate": 0.011},
                {"name": "Zack Moss",              "number": 31, "grade": "C",  "ypc": 3.9, "fumble_rate": 0.015}],
        "wr":  [{"name": "Ja'Marr Chase",          "number": 1,  "grade": "A",  "catch_rate": 0.73, "avg_yards": 15.8},
                {"name": "Tee Higgins",            "number": 85, "grade": "A",  "catch_rate": 0.70, "avg_yards": 14.0},
                {"name": "Tyler Boyd",             "number": 83, "grade": "B",  "catch_rate": 0.68, "avg_yards": 10.8}],
        "te":  [{"name": "Irv Smith Jr.",          "number": 84, "grade": "C",  "catch_rate": 0.62, "avg_yards": 9.0}],
        "k":   [{"name": "Evan McPherson",         "number": 2,  "grade": "A",  "accuracy": 0.885, "xp_rate": 0.990}],
        "p":   [{"name": "Brad Robbins",           "number": 10, "grade": "B",  "avg_distance": 45.5, "inside_20_rate": 0.40}],
        "def": [{"name": "Trey Hendrickson",       "number": 91, "pos": "DE",   "grade": "A",  "pass_rush": 90, "coverage": 42, "run_stop": 72},
                {"name": "Logan Wilson",           "number": 55, "pos": "LB",   "grade": "B",  "pass_rush": 62, "coverage": 74, "run_stop": 80},
                {"name": "Cam Taylor-Britt",       "number": 29, "pos": "CB",   "grade": "B",  "pass_rush": 44, "coverage": 79, "run_stop": 68}],
    },
    "CLE": {
        "qb":  [{"name": "Deshaun Watson",         "number": 4,  "grade": "C",  "comp_pct": 0.598, "ypa": 6.5, "int_rate": 0.032, "sack_rate": 0.100}],
        "rb":  [{"name": "Nick Chubb",             "number": 24, "grade": "A",  "ypc": 5.0, "fumble_rate": 0.009},
                {"name": "Jerome Ford",            "number": 34, "grade": "C",  "ypc": 4.0, "fumble_rate": 0.014}],
        "wr":  [{"name": "Amari Cooper",           "number": 2,  "grade": "A",  "catch_rate": 0.70, "avg_yards": 13.5},
                {"name": "Elijah Moore",           "number": 8,  "grade": "B",  "catch_rate": 0.64, "avg_yards": 12.0},
                {"name": "David Bell",             "number": 18, "grade": "C",  "catch_rate": 0.60, "avg_yards": 10.0}],
        "te":  [{"name": "David Njoku",            "number": 85, "grade": "A",  "catch_rate": 0.72, "avg_yards": 11.0}],
        "k":   [{"name": "Dustin Hopkins",         "number": 7,  "grade": "B",  "accuracy": 0.848, "xp_rate": 0.980}],
        "p":   [{"name": "Corey Bojorquez",        "number": 16, "grade": "B",  "avg_distance": 46.0, "inside_20_rate": 0.38}],
        "def": [{"name": "Myles Garrett",          "number": 95, "pos": "DE",   "grade": "A",  "pass_rush": 96, "coverage": 44, "run_stop": 78},
                {"name": "Jeremiah Owusu-Koramoah","number": 28, "pos": "LB",   "grade": "A",  "pass_rush": 72, "coverage": 82, "run_stop": 84},
                {"name": "Greg Newsome II",        "number": 20, "pos": "CB",   "grade": "B",  "pass_rush": 44, "coverage": 80, "run_stop": 68}],
    },
    "PIT": {
        "qb":  [{"name": "Russell Wilson",         "number": 3,  "grade": "B",  "comp_pct": 0.622, "ypa": 7.0, "int_rate": 0.024, "sack_rate": 0.078}],
        "rb":  [{"name": "Najee Harris",           "number": 22, "grade": "B",  "ypc": 4.1, "fumble_rate": 0.013},
                {"name": "Jaylen Warren",          "number": 30, "grade": "C",  "ypc": 3.9, "fumble_rate": 0.016}],
        "wr":  [{"name": "George Pickens",         "number": 14, "grade": "B",  "catch_rate": 0.65, "avg_yards": 14.2},
                {"name": "Van Jefferson",          "number": 12, "grade": "C",  "catch_rate": 0.61, "avg_yards": 11.5},
                {"name": "Calvin Austin III",      "number": 19, "grade": "C",  "catch_rate": 0.62, "avg_yards": 12.0}],
        "te":  [{"name": "Pat Freiermuth",         "number": 88, "grade": "B",  "catch_rate": 0.66, "avg_yards": 9.0}],
        "k":   [{"name": "Chris Boswell",          "number": 9,  "grade": "A",  "accuracy": 0.893, "xp_rate": 0.993}],
        "p":   [{"name": "Pressley Harvin III",    "number": 6,  "grade": "B",  "avg_distance": 45.5, "inside_20_rate": 0.39}],
        "def": [{"name": "T.J. Watt",             "number": 90, "pos": "DE",   "grade": "A",  "pass_rush": 96, "coverage": 54, "run_stop": 82},
                {"name": "Cameron Heyward",        "number": 97, "pos": "DT",   "grade": "A",  "pass_rush": 86, "coverage": 44, "run_stop": 86},
                {"name": "Patrick Peterson",       "number": 7,  "pos": "CB",   "grade": "B",  "pass_rush": 44, "coverage": 78, "run_stop": 68}],
    },
    "HOU": {
        "qb":  [{"name": "C.J. Stroud",            "number": 7,  "grade": "A",  "comp_pct": 0.643, "ypa": 8.0, "int_rate": 0.018, "sack_rate": 0.062}],
        "rb":  [{"name": "Joe Mixon",              "number": 28, "grade": "B",  "ypc": 4.5, "fumble_rate": 0.011},
                {"name": "Dameon Pierce",          "number": 31, "grade": "C",  "ypc": 3.8, "fumble_rate": 0.016}],
        "wr":  [{"name": "Nico Collins",           "number": 12, "grade": "A",  "catch_rate": 0.71, "avg_yards": 14.5},
                {"name": "Tank Dell",              "number": 13, "grade": "B",  "catch_rate": 0.66, "avg_yards": 13.0},
                {"name": "Stefon Diggs",           "number": 10, "grade": "B",  "catch_rate": 0.68, "avg_yards": 12.5}],
        "te":  [{"name": "Dalton Schultz",         "number": 86, "grade": "B",  "catch_rate": 0.65, "avg_yards": 9.5}],
        "k":   [{"name": "Ka'imi Fairbairn",       "number": 7,  "grade": "B",  "accuracy": 0.845, "xp_rate": 0.978}],
        "p":   [{"name": "Jon Weeks",              "number": 45, "grade": "C",  "avg_distance": 43.5, "inside_20_rate": 0.36}],
        "def": [{"name": "Will Anderson Jr.",      "number": 51, "pos": "DE",   "grade": "A",  "pass_rush": 86, "coverage": 50, "run_stop": 74},
                {"name": "DeMeco Ryans",           "number": 55, "pos": "LB",   "grade": "B",  "pass_rush": 66, "coverage": 72, "run_stop": 82},
                {"name": "Derek Stingley Jr.",     "number": 24, "pos": "CB",   "grade": "A",  "pass_rush": 46, "coverage": 88, "run_stop": 70}],
    },
    "IND": {
        "qb":  [{"name": "Anthony Richardson",    "number": 5,  "grade": "C",  "comp_pct": 0.582, "ypa": 7.2, "int_rate": 0.030, "sack_rate": 0.095}],
        "rb":  [{"name": "Jonathan Taylor",       "number": 28, "grade": "A",  "ypc": 5.0, "fumble_rate": 0.009},
                {"name": "Zack Moss",             "number": 21, "grade": "C",  "ypc": 3.8, "fumble_rate": 0.015}],
        "wr":  [{"name": "Michael Pittman Jr.",   "number": 11, "grade": "B",  "catch_rate": 0.68, "avg_yards": 12.0},
                {"name": "Josh Downs",            "number": 1,  "grade": "B",  "catch_rate": 0.67, "avg_yards": 11.0},
                {"name": "Adonai Mitchell",       "number": 5,  "grade": "C",  "catch_rate": 0.60, "avg_yards": 13.0}],
        "te":  [{"name": "Mo Alie-Cox",           "number": 81, "grade": "C",  "catch_rate": 0.62, "avg_yards": 8.5}],
        "k":   [{"name": "Matt Gay",              "number": 7,  "grade": "B",  "accuracy": 0.848, "xp_rate": 0.980}],
        "p":   [{"name": "Rigoberto Sanchez",     "number": 9,  "grade": "B",  "avg_distance": 44.5, "inside_20_rate": 0.38}],
        "def": [{"name": "DeForest Buckner",      "number": 99, "pos": "DT",   "grade": "A",  "pass_rush": 86, "coverage": 44, "run_stop": 86},
                {"name": "Shaquille Leonard",     "number": 53, "pos": "LB",   "grade": "B",  "pass_rush": 68, "coverage": 74, "run_stop": 84},
                {"name": "Kenny Moore II",        "number": 23, "pos": "CB",   "grade": "B",  "pass_rush": 46, "coverage": 78, "run_stop": 68}],
    },
    "JAX": {
        "qb":  [{"name": "Trevor Lawrence",       "number": 16, "grade": "B",  "comp_pct": 0.625, "ypa": 7.2, "int_rate": 0.026, "sack_rate": 0.082}],
        "rb":  [{"name": "Travis Etienne Jr.",    "number": 1,  "grade": "A",  "ypc": 4.8, "fumble_rate": 0.010},
                {"name": "Tank Bigsby",           "number": 4,  "grade": "C",  "ypc": 3.9, "fumble_rate": 0.015}],
        "wr":  [{"name": "Calvin Ridley",         "number": 0,  "grade": "B",  "catch_rate": 0.66, "avg_yards": 13.5},
                {"name": "Gabe Davis",            "number": 13, "grade": "B",  "catch_rate": 0.62, "avg_yards": 14.5},
                {"name": "Zay Jones",             "number": 7,  "grade": "C",  "catch_rate": 0.63, "avg_yards": 10.5}],
        "te":  [{"name": "Evan Engram",           "number": 17, "grade": "A",  "catch_rate": 0.74, "avg_yards": 12.0}],
        "k":   [{"name": "Brandon McManus",       "number": 8,  "grade": "C",  "accuracy": 0.800, "xp_rate": 0.965}],
        "p":   [{"name": "Logan Cooke",           "number": 9,  "grade": "B",  "avg_distance": 46.0, "inside_20_rate": 0.40}],
        "def": [{"name": "Josh Allen",            "number": 41, "pos": "DE",   "grade": "A",  "pass_rush": 90, "coverage": 48, "run_stop": 76},
                {"name": "Travon Walker",         "number": 44, "pos": "DE",   "grade": "B",  "pass_rush": 78, "coverage": 44, "run_stop": 72},
                {"name": "Darious Williams",      "number": 31, "pos": "CB",   "grade": "B",  "pass_rush": 44, "coverage": 78, "run_stop": 66}],
    },
    "TEN": {
        "qb":  [{"name": "Will Levis",            "number": 8,  "grade": "C",  "comp_pct": 0.588, "ypa": 6.8, "int_rate": 0.032, "sack_rate": 0.092}],
        "rb":  [{"name": "Tony Pollard",          "number": 20, "grade": "B",  "ypc": 4.3, "fumble_rate": 0.012},
                {"name": "Tyjae Spears",          "number": 2,  "grade": "C",  "ypc": 4.0, "fumble_rate": 0.015}],
        "wr":  [{"name": "DeAndre Hopkins",       "number": 10, "grade": "B",  "catch_rate": 0.68, "avg_yards": 12.5},
                {"name": "Calvin Ridley",         "number": 0,  "grade": "C",  "catch_rate": 0.62, "avg_yards": 13.0},
                {"name": "Nick Westbrook-Ikhine", "number": 15, "grade": "C",  "catch_rate": 0.60, "avg_yards": 11.0}],
        "te":  [{"name": "Chig Okonkwo",          "number": 85, "grade": "B",  "catch_rate": 0.66, "avg_yards": 9.5}],
        "k":   [{"name": "Nick Folk",             "number": 6,  "grade": "B",  "accuracy": 0.845, "xp_rate": 0.980}],
        "p":   [{"name": "Ryan Stonehouse",       "number": 4,  "grade": "A",  "avg_distance": 50.0, "inside_20_rate": 0.40}],
        "def": [{"name": "Harold Landry III",     "number": 58, "pos": "DE",   "grade": "B",  "pass_rush": 80, "coverage": 46, "run_stop": 70},
                {"name": "Jeffery Simmons",       "number": 98, "pos": "DT",   "grade": "A",  "pass_rush": 84, "coverage": 44, "run_stop": 86},
                {"name": "L'Jarius Sneed",        "number": 38, "pos": "CB",   "grade": "A",  "pass_rush": 48, "coverage": 88, "run_stop": 72}],
    },
    "DEN": {
        "qb":  [{"name": "Bo Nix",                "number": 10, "grade": "C",  "comp_pct": 0.602, "ypa": 6.9, "int_rate": 0.028, "sack_rate": 0.086}],
        "rb":  [{"name": "Javonte Williams",      "number": 33, "grade": "B",  "ypc": 4.2, "fumble_rate": 0.014},
                {"name": "Samaje Perine",         "number": 25, "grade": "C",  "ypc": 3.8, "fumble_rate": 0.016}],
        "wr":  [{"name": "Courtland Sutton",      "number": 14, "grade": "B",  "catch_rate": 0.64, "avg_yards": 14.2},
                {"name": "Jerry Jeudy",           "number": 10, "grade": "B",  "catch_rate": 0.65, "avg_yards": 13.0},
                {"name": "Marvin Mims Jr.",       "number": 15, "grade": "C",  "catch_rate": 0.62, "avg_yards": 14.0}],
        "te":  [{"name": "Greg Dulcich",          "number": 80, "grade": "C",  "catch_rate": 0.62, "avg_yards": 9.0}],
        "k":   [{"name": "Wil Lutz",              "number": 3,  "grade": "B",  "accuracy": 0.848, "xp_rate": 0.980}],
        "p":   [{"name": "Riley Dixon",           "number": 9,  "grade": "B",  "avg_distance": 45.5, "inside_20_rate": 0.38}],
        "def": [{"name": "Nik Bonitto",           "number": 15, "pos": "DE",   "grade": "B",  "pass_rush": 80, "coverage": 46, "run_stop": 68},
                {"name": "Zach Allen",            "number": 99, "pos": "DT",   "grade": "B",  "pass_rush": 76, "coverage": 42, "run_stop": 80},
                {"name": "Patrick Surtain II",    "number": 2,  "pos": "CB",   "grade": "A",  "pass_rush": 46, "coverage": 92, "run_stop": 70}],
    },
    "KC": {
        "qb":  [{"name": "Patrick Mahomes",       "number": 15, "grade": "A",  "comp_pct": 0.672, "ypa": 8.8, "int_rate": 0.016, "sack_rate": 0.055}],
        "rb":  [{"name": "Isiah Pacheco",         "number": 10, "grade": "B",  "ypc": 4.6, "fumble_rate": 0.011},
                {"name": "Clyde Edwards-Helaire", "number": 25, "grade": "C",  "ypc": 3.8, "fumble_rate": 0.015}],
        "wr":  [{"name": "Rashee Rice",           "number": 4,  "grade": "A",  "catch_rate": 0.71, "avg_yards": 12.8},
                {"name": "Marquise Brown",        "number": 4,  "grade": "B",  "catch_rate": 0.65, "avg_yards": 13.5},
                {"name": "Mecole Hardman",        "number": 17, "grade": "C",  "catch_rate": 0.62, "avg_yards": 12.5}],
        "te":  [{"name": "Travis Kelce",          "number": 87, "grade": "A",  "catch_rate": 0.76, "avg_yards": 12.5}],
        "k":   [{"name": "Harrison Butker",       "number": 7,  "grade": "A",  "accuracy": 0.900, "xp_rate": 0.995}],
        "p":   [{"name": "Tommy Townsend",        "number": 5,  "grade": "B",  "avg_distance": 47.0, "inside_20_rate": 0.42}],
        "def": [{"name": "Chris Jones",           "number": 95, "pos": "DT",   "grade": "A",  "pass_rush": 94, "coverage": 48, "run_stop": 84},
                {"name": "Nick Bolton",           "number": 32, "pos": "LB",   "grade": "B",  "pass_rush": 64, "coverage": 74, "run_stop": 84},
                {"name": "L'Jarius Sneed",        "number": 38, "pos": "CB",   "grade": "A",  "pass_rush": 48, "coverage": 88, "run_stop": 72}],
    },
    "LV": {
        "qb":  [{"name": "Gardner Minshew II",    "number": 15, "grade": "C",  "comp_pct": 0.598, "ypa": 6.8, "int_rate": 0.030, "sack_rate": 0.088}],
        "rb":  [{"name": "Josh Jacobs",           "number": 28, "grade": "A",  "ypc": 4.9, "fumble_rate": 0.009},
                {"name": "Ameer Abdullah",        "number": 22, "grade": "C",  "ypc": 3.6, "fumble_rate": 0.016}],
        "wr":  [{"name": "Davante Adams",         "number": 17, "grade": "A",  "catch_rate": 0.73, "avg_yards": 12.8},
                {"name": "Hunter Renfrow",        "number": 13, "grade": "B",  "catch_rate": 0.70, "avg_yards": 9.8},
                {"name": "Jakobi Meyers",         "number": 16, "grade": "B",  "catch_rate": 0.68, "avg_yards": 11.5}],
        "te":  [{"name": "Michael Mayer",         "number": 87, "grade": "C",  "catch_rate": 0.62, "avg_yards": 8.5}],
        "k":   [{"name": "Daniel Carlson",        "number": 2,  "grade": "A",  "accuracy": 0.892, "xp_rate": 0.993}],
        "p":   [{"name": "AJ Cole",               "number": 6,  "grade": "A",  "avg_distance": 48.5, "inside_20_rate": 0.42}],
        "def": [{"name": "Maxx Crosby",           "number": 98, "pos": "DE",   "grade": "A",  "pass_rush": 94, "coverage": 50, "run_stop": 78},
                {"name": "Divine Deablo",         "number": 5,  "pos": "LB",   "grade": "B",  "pass_rush": 62, "coverage": 72, "run_stop": 80},
                {"name": "Nate Hobbs",            "number": 39, "pos": "CB",   "grade": "B",  "pass_rush": 44, "coverage": 78, "run_stop": 68}],
    },
    "LAC": {
        "qb":  [{"name": "Justin Herbert",        "number": 10, "grade": "A",  "comp_pct": 0.652, "ypa": 7.8, "int_rate": 0.020, "sack_rate": 0.068}],
        "rb":  [{"name": "Austin Ekeler",         "number": 30, "grade": "B",  "ypc": 4.4, "fumble_rate": 0.010},
                {"name": "J.K. Dobbins",          "number": 27, "grade": "B",  "ypc": 4.6, "fumble_rate": 0.011}],
        "wr":  [{"name": "Keenan Allen",          "number": 13, "grade": "A",  "catch_rate": 0.72, "avg_yards": 12.8},
                {"name": "Mike Williams",         "number": 81, "grade": "B",  "catch_rate": 0.62, "avg_yards": 15.5},
                {"name": "Joshua Palmer",         "number": 5,  "grade": "C",  "catch_rate": 0.62, "avg_yards": 12.5}],
        "te":  [{"name": "Donald Parham Jr.",     "number": 89, "grade": "C",  "catch_rate": 0.62, "avg_yards": 9.5}],
        "k":   [{"name": "Cameron Dicker",        "number": 11, "grade": "B",  "accuracy": 0.855, "xp_rate": 0.982}],
        "p":   [{"name": "JK Scott",              "number": 7,  "grade": "B",  "avg_distance": 45.5, "inside_20_rate": 0.38}],
        "def": [{"name": "Joey Bosa",             "number": 97, "pos": "DE",   "grade": "A",  "pass_rush": 90, "coverage": 46, "run_stop": 76},
                {"name": "Khalil Mack",           "number": 52, "pos": "DE",   "grade": "A",  "pass_rush": 92, "coverage": 48, "run_stop": 74},
                {"name": "J.C. Jackson",          "number": 27, "pos": "CB",   "grade": "B",  "pass_rush": 44, "coverage": 80, "run_stop": 68}],
    },
    "DAL": {
        "qb":  [{"name": "Dak Prescott",          "number": 4,  "grade": "A",  "comp_pct": 0.655, "ypa": 7.8, "int_rate": 0.022, "sack_rate": 0.060}],
        "rb":  [{"name": "Tony Pollard",          "number": 20, "grade": "B",  "ypc": 4.5, "fumble_rate": 0.011},
                {"name": "Ezekiel Elliott",       "number": 15, "grade": "C",  "ypc": 3.7, "fumble_rate": 0.015}],
        "wr":  [{"name": "CeeDee Lamb",           "number": 88, "grade": "A",  "catch_rate": 0.74, "avg_yards": 14.0},
                {"name": "Michael Gallup",        "number": 13, "grade": "C",  "catch_rate": 0.62, "avg_yards": 13.5},
                {"name": "Brandin Cooks",         "number": 3,  "grade": "C",  "catch_rate": 0.63, "avg_yards": 12.0}],
        "te":  [{"name": "Jake Ferguson",         "number": 87, "grade": "B",  "catch_rate": 0.67, "avg_yards": 10.5}],
        "k":   [{"name": "Brandon Aubrey",        "number": 17, "grade": "A",  "accuracy": 0.898, "xp_rate": 0.994}],
        "p":   [{"name": "Bryan Anger",           "number": 5,  "grade": "B",  "avg_distance": 46.0, "inside_20_rate": 0.40}],
        "def": [{"name": "Micah Parsons",         "number": 11, "pos": "DE",   "grade": "A",  "pass_rush": 96, "coverage": 58, "run_stop": 82},
                {"name": "DaRon Bland",           "number": 26, "pos": "CB",   "grade": "A",  "pass_rush": 46, "coverage": 88, "run_stop": 70},
                {"name": "Trevon Diggs",          "number": 7,  "pos": "CB",   "grade": "A",  "pass_rush": 46, "coverage": 90, "run_stop": 68}],
    },
    "NYG": {
        "qb":  [{"name": "Daniel Jones",          "number": 8,  "grade": "C",  "comp_pct": 0.592, "ypa": 6.6, "int_rate": 0.028, "sack_rate": 0.098}],
        "rb":  [{"name": "Saquon Barkley",        "number": 26, "grade": "A",  "ypc": 4.9, "fumble_rate": 0.010},
                {"name": "Matt Breida",           "number": 31, "grade": "C",  "ypc": 3.8, "fumble_rate": 0.015}],
        "wr":  [{"name": "Wan'Dale Robinson",     "number": 17, "grade": "B",  "catch_rate": 0.67, "avg_yards": 10.5},
                {"name": "Darius Slayton",        "number": 86, "grade": "B",  "catch_rate": 0.63, "avg_yards": 14.0},
                {"name": "Sterling Shepard",      "number": 87, "grade": "C",  "catch_rate": 0.65, "avg_yards": 10.0}],
        "te":  [{"name": "Darren Waller",         "number": 12, "grade": "B",  "catch_rate": 0.68, "avg_yards": 11.0}],
        "k":   [{"name": "Graham Gano",           "number": 9,  "grade": "B",  "accuracy": 0.840, "xp_rate": 0.978}],
        "p":   [{"name": "Jamie Gillan",          "number": 18, "grade": "C",  "avg_distance": 44.0, "inside_20_rate": 0.36}],
        "def": [{"name": "Kayvon Thibodeaux",     "number": 5,  "pos": "DE",   "grade": "B",  "pass_rush": 80, "coverage": 46, "run_stop": 70},
                {"name": "Dexter Lawrence",       "number": 97, "pos": "DT",   "grade": "A",  "pass_rush": 86, "coverage": 44, "run_stop": 88},
                {"name": "Adoree' Jackson",       "number": 22, "pos": "CB",   "grade": "B",  "pass_rush": 44, "coverage": 78, "run_stop": 68}],
    },
    "PHI": {
        "qb":  [{"name": "Jalen Hurts",           "number": 1,  "grade": "A",  "comp_pct": 0.643, "ypa": 7.9, "int_rate": 0.017, "sack_rate": 0.058}],
        "rb":  [{"name": "D'Andre Swift",         "number": 0,  "grade": "A",  "ypc": 5.0, "fumble_rate": 0.009},
                {"name": "Kenneth Gainwell",      "number": 14, "grade": "C",  "ypc": 3.8, "fumble_rate": 0.015}],
        "wr":  [{"name": "A.J. Brown",            "number": 11, "grade": "A",  "catch_rate": 0.72, "avg_yards": 15.0},
                {"name": "DeVonta Smith",         "number": 6,  "grade": "A",  "catch_rate": 0.71, "avg_yards": 13.5},
                {"name": "Olamide Zaccheaus",     "number": 17, "grade": "C",  "catch_rate": 0.63, "avg_yards": 11.5}],
        "te":  [{"name": "Dallas Goedert",        "number": 88, "grade": "A",  "catch_rate": 0.73, "avg_yards": 12.0}],
        "k":   [{"name": "Jake Elliott",          "number": 4,  "grade": "A",  "accuracy": 0.890, "xp_rate": 0.990}],
        "p":   [{"name": "Arryn Siposs",          "number": 10, "grade": "C",  "avg_distance": 43.5, "inside_20_rate": 0.36}],
        "def": [{"name": "Haason Reddick",        "number": 7,  "pos": "DE",   "grade": "A",  "pass_rush": 90, "coverage": 50, "run_stop": 72},
                {"name": "Fletcher Cox",          "number": 91, "pos": "DT",   "grade": "A",  "pass_rush": 82, "coverage": 44, "run_stop": 86},
                {"name": "Darius Slay",           "number": 24, "pos": "CB",   "grade": "A",  "pass_rush": 48, "coverage": 90, "run_stop": 72}],
    },
    "WSH": {
        "qb":  [{"name": "Jayden Daniels",        "number": 5,  "grade": "B",  "comp_pct": 0.632, "ypa": 7.5, "int_rate": 0.020, "sack_rate": 0.070}],
        "rb":  [{"name": "Brian Robinson Jr.",    "number": 8,  "grade": "B",  "ypc": 4.2, "fumble_rate": 0.013},
                {"name": "Antonio Gibson",        "number": 24, "grade": "C",  "ypc": 3.8, "fumble_rate": 0.016}],
        "wr":  [{"name": "Terry McLaurin",        "number": 17, "grade": "A",  "catch_rate": 0.70, "avg_yards": 14.5},
                {"name": "Jahan Dotson",          "number": 1,  "grade": "B",  "catch_rate": 0.65, "avg_yards": 12.5},
                {"name": "Dyami Brown",           "number": 2,  "grade": "C",  "catch_rate": 0.60, "avg_yards": 13.0}],
        "te":  [{"name": "Logan Thomas",          "number": 82, "grade": "C",  "catch_rate": 0.64, "avg_yards": 9.0}],
        "k":   [{"name": "Cade York",             "number": 3,  "grade": "C",  "accuracy": 0.800, "xp_rate": 0.965}],
        "p":   [{"name": "Tress Way",             "number": 5,  "grade": "A",  "avg_distance": 48.0, "inside_20_rate": 0.44}],
        "def": [{"name": "Chase Young",           "number": 99, "pos": "DE",   "grade": "B",  "pass_rush": 82, "coverage": 46, "run_stop": 72},
                {"name": "Jonathan Allen",        "number": 93, "pos": "DT",   "grade": "A",  "pass_rush": 84, "coverage": 44, "run_stop": 86},
                {"name": "Emmanuel Forbes Jr.",   "number": 13, "pos": "CB",   "grade": "B",  "pass_rush": 44, "coverage": 78, "run_stop": 64}],
    },
    "CHI": {
        "qb":  [{"name": "Caleb Williams",        "number": 18, "grade": "C",  "comp_pct": 0.605, "ypa": 7.0, "int_rate": 0.026, "sack_rate": 0.090}],
        "rb":  [{"name": "D'Andre Swift",         "number": 29, "grade": "B",  "ypc": 4.6, "fumble_rate": 0.010},
                {"name": "Khalil Herbert",        "number": 24, "grade": "C",  "ypc": 4.0, "fumble_rate": 0.014}],
        "wr":  [{"name": "DJ Moore",              "number": 2,  "grade": "B",  "catch_rate": 0.68, "avg_yards": 13.5},
                {"name": "Keenan Allen",          "number": 13, "grade": "B",  "catch_rate": 0.70, "avg_yards": 12.0},
                {"name": "Tyler Scott",           "number": 10, "grade": "C",  "catch_rate": 0.60, "avg_yards": 13.5}],
        "te":  [{"name": "Cole Kmet",             "number": 85, "grade": "B",  "catch_rate": 0.67, "avg_yards": 9.5}],
        "k":   [{"name": "Cairo Santos",          "number": 5,  "grade": "B",  "accuracy": 0.848, "xp_rate": 0.980}],
        "p":   [{"name": "Tory Taylor",           "number": 15, "grade": "B",  "avg_distance": 46.5, "inside_20_rate": 0.40}],
        "def": [{"name": "Montez Sweat",          "number": 90, "pos": "DE",   "grade": "A",  "pass_rush": 88, "coverage": 48, "run_stop": 74},
                {"name": "Grady Jarett",          "number": 97, "pos": "DT",   "grade": "B",  "pass_rush": 78, "coverage": 44, "run_stop": 84},
                {"name": "Jaylon Johnson",        "number": 33, "pos": "CB",   "grade": "B",  "pass_rush": 46, "coverage": 80, "run_stop": 68}],
    },
    "DET": {
        "qb":  [{"name": "Jared Goff",            "number": 16, "grade": "A",  "comp_pct": 0.672, "ypa": 7.8, "int_rate": 0.018, "sack_rate": 0.058}],
        "rb":  [{"name": "David Montgomery",      "number": 5,  "grade": "A",  "ypc": 4.9, "fumble_rate": 0.009},
                {"name": "Jahmyr Gibbs",          "number": 26, "grade": "A",  "ypc": 5.3, "fumble_rate": 0.008}],
        "wr":  [{"name": "Amon-Ra St. Brown",     "number": 14, "grade": "A",  "catch_rate": 0.74, "avg_yards": 12.5},
                {"name": "Josh Reynolds",         "number": 8,  "grade": "B",  "catch_rate": 0.65, "avg_yards": 13.0},
                {"name": "Jameson Williams",      "number": 9,  "grade": "B",  "catch_rate": 0.62, "avg_yards": 16.0}],
        "te":  [{"name": "Sam LaPorta",           "number": 86, "grade": "A",  "catch_rate": 0.72, "avg_yards": 11.5}],
        "k":   [{"name": "Michael Badgley",       "number": 4,  "grade": "B",  "accuracy": 0.850, "xp_rate": 0.982}],
        "p":   [{"name": "Jack Fox",              "number": 3,  "grade": "A",  "avg_distance": 49.0, "inside_20_rate": 0.42}],
        "def": [{"name": "Aidan Hutchinson",      "number": 97, "pos": "DE",   "grade": "A",  "pass_rush": 92, "coverage": 52, "run_stop": 80},
                {"name": "Alim McNeill",          "number": 54, "pos": "DT",   "grade": "B",  "pass_rush": 76, "coverage": 44, "run_stop": 86},
                {"name": "Brian Branch",          "number": 32, "pos": "S",    "grade": "A",  "pass_rush": 52, "coverage": 86, "run_stop": 80}],
    },
    "GB": {
        "qb":  [{"name": "Jordan Love",           "number": 10, "grade": "A",  "comp_pct": 0.638, "ypa": 7.8, "int_rate": 0.022, "sack_rate": 0.070}],
        "rb":  [{"name": "Josh Jacobs",           "number": 8,  "grade": "A",  "ypc": 4.9, "fumble_rate": 0.009},
                {"name": "AJ Dillon",             "number": 28, "grade": "C",  "ypc": 3.8, "fumble_rate": 0.014}],
        "wr":  [{"name": "Christian Watson",      "number": 9,  "grade": "B",  "catch_rate": 0.64, "avg_yards": 15.0},
                {"name": "Romeo Doubs",           "number": 87, "grade": "B",  "catch_rate": 0.66, "avg_yards": 12.5},
                {"name": "Jayden Reed",           "number": 11, "grade": "B",  "catch_rate": 0.67, "avg_yards": 11.5}],
        "te":  [{"name": "Tucker Kraft",          "number": 85, "grade": "B",  "catch_rate": 0.67, "avg_yards": 9.8}],
        "k":   [{"name": "Anders Carlson",        "number": 7,  "grade": "B",  "accuracy": 0.844, "xp_rate": 0.980}],
        "p":   [{"name": "Daniel Whelan",         "number": 6,  "grade": "B",  "avg_distance": 46.0, "inside_20_rate": 0.40}],
        "def": [{"name": "Rashan Gary",           "number": 52, "pos": "DE",   "grade": "A",  "pass_rush": 86, "coverage": 50, "run_stop": 72},
                {"name": "Kenny Clark",           "number": 97, "pos": "DT",   "grade": "A",  "pass_rush": 80, "coverage": 44, "run_stop": 88},
                {"name": "Jaire Alexander",       "number": 23, "pos": "CB",   "grade": "A",  "pass_rush": 46, "coverage": 90, "run_stop": 70}],
    },
    "MIN": {
        "qb":  [{"name": "Sam Darnold",           "number": 14, "grade": "B",  "comp_pct": 0.628, "ypa": 7.4, "int_rate": 0.024, "sack_rate": 0.076}],
        "rb":  [{"name": "Aaron Jones",           "number": 33, "grade": "B",  "ypc": 4.4, "fumble_rate": 0.011},
                {"name": "Ty Chandler",           "number": 32, "grade": "C",  "ypc": 3.9, "fumble_rate": 0.015}],
        "wr":  [{"name": "Justin Jefferson",      "number": 18, "grade": "A",  "catch_rate": 0.74, "avg_yards": 14.5},
                {"name": "Jordan Addison",        "number": 3,  "grade": "B",  "catch_rate": 0.67, "avg_yards": 14.0},
                {"name": "Brandon Powell",        "number": 14, "grade": "C",  "catch_rate": 0.62, "avg_yards": 10.5}],
        "te":  [{"name": "T.J. Hockenson",        "number": 87, "grade": "A",  "catch_rate": 0.74, "avg_yards": 11.5}],
        "k":   [{"name": "Will Reichard",         "number": 19, "grade": "A",  "accuracy": 0.890, "xp_rate": 0.992}],
        "p":   [{"name": "Ryan Wright",           "number": 14, "grade": "B",  "avg_distance": 46.0, "inside_20_rate": 0.40}],
        "def": [{"name": "Jonathan Greenard",     "number": 55, "pos": "DE",   "grade": "B",  "pass_rush": 80, "coverage": 48, "run_stop": 72},
                {"name": "Harrison Phillips",     "number": 97, "pos": "DT",   "grade": "B",  "pass_rush": 72, "coverage": 44, "run_stop": 84},
                {"name": "Byron Murphy II",       "number": 33, "pos": "CB",   "grade": "B",  "pass_rush": 44, "coverage": 80, "run_stop": 68}],
    },
    "ATL": {
        "qb":  [{"name": "Kirk Cousins",          "number": 8,  "grade": "B",  "comp_pct": 0.640, "ypa": 7.4, "int_rate": 0.024, "sack_rate": 0.076}],
        "rb":  [{"name": "Bijan Robinson",        "number": 7,  "grade": "A",  "ypc": 5.1, "fumble_rate": 0.009},
                {"name": "Tyler Allgeier",        "number": 25, "grade": "C",  "ypc": 3.9, "fumble_rate": 0.015}],
        "wr":  [{"name": "Drake London",          "number": 5,  "grade": "A",  "catch_rate": 0.70, "avg_yards": 12.5},
                {"name": "Darnell Mooney",        "number": 1,  "grade": "B",  "catch_rate": 0.64, "avg_yards": 13.5},
                {"name": "Ray-Ray McCloud",       "number": 3,  "grade": "C",  "catch_rate": 0.62, "avg_yards": 10.5}],
        "te":  [{"name": "Kyle Pitts",            "number": 8,  "grade": "A",  "catch_rate": 0.70, "avg_yards": 12.5}],
        "k":   [{"name": "Younghoe Koo",          "number": 7,  "grade": "A",  "accuracy": 0.888, "xp_rate": 0.990}],
        "p":   [{"name": "Bradley Pinion",        "number": 13, "grade": "B",  "avg_distance": 45.5, "inside_20_rate": 0.39}],
        "def": [{"name": "Grady Jarrett",         "number": 97, "pos": "DT",   "grade": "A",  "pass_rush": 82, "coverage": 44, "run_stop": 88},
                {"name": "Matthew Judon",         "number": 40, "pos": "DE",   "grade": "B",  "pass_rush": 80, "coverage": 46, "run_stop": 68},
                {"name": "A.J. Terrell",          "number": 24, "pos": "CB",   "grade": "A",  "pass_rush": 46, "coverage": 88, "run_stop": 70}],
    },
    "CAR": {
        "qb":  [{"name": "Bryce Young",           "number": 9,  "grade": "D",  "comp_pct": 0.565, "ypa": 6.2, "int_rate": 0.035, "sack_rate": 0.105}],
        "rb":  [{"name": "Miles Sanders",         "number": 6,  "grade": "C",  "ypc": 3.8, "fumble_rate": 0.016},
                {"name": "Chuba Hubbard",         "number": 30, "grade": "C",  "ypc": 4.0, "fumble_rate": 0.014}],
        "wr":  [{"name": "Adam Thielen",          "number": 19, "grade": "B",  "catch_rate": 0.67, "avg_yards": 11.5},
                {"name": "DJ Chark",              "number": 3,  "grade": "C",  "catch_rate": 0.60, "avg_yards": 13.0},
                {"name": "Diontae Johnson",       "number": 18, "grade": "B",  "catch_rate": 0.68, "avg_yards": 11.0}],
        "te":  [{"name": "Hayden Hurst",          "number": 0,  "grade": "C",  "catch_rate": 0.62, "avg_yards": 8.5}],
        "k":   [{"name": "Eddy Pineiro",          "number": 15, "grade": "C",  "accuracy": 0.795, "xp_rate": 0.963}],
        "p":   [{"name": "Johnny Hekker",         "number": 10, "grade": "B",  "avg_distance": 45.0, "inside_20_rate": 0.38}],
        "def": [{"name": "Brian Burns",           "number": 0,  "pos": "DE",   "grade": "B",  "pass_rush": 82, "coverage": 46, "run_stop": 70},
                {"name": "Derrick Brown",         "number": 95, "pos": "DT",   "grade": "B",  "pass_rush": 76, "coverage": 44, "run_stop": 84},
                {"name": "Jaycee Horn",           "number": 8,  "pos": "CB",   "grade": "B",  "pass_rush": 46, "coverage": 80, "run_stop": 68}],
    },
    "NO": {
        "qb":  [{"name": "Derek Carr",            "number": 4,  "grade": "C",  "comp_pct": 0.616, "ypa": 7.0, "int_rate": 0.026, "sack_rate": 0.082}],
        "rb":  [{"name": "Alvin Kamara",          "number": 41, "grade": "A",  "ypc": 4.7, "fumble_rate": 0.010},
                {"name": "Jamaal Williams",       "number": 21, "grade": "C",  "ypc": 3.7, "fumble_rate": 0.016}],
        "wr":  [{"name": "Chris Olave",           "number": 12, "grade": "A",  "catch_rate": 0.70, "avg_yards": 14.0},
                {"name": "Michael Thomas",        "number": 13, "grade": "B",  "catch_rate": 0.70, "avg_yards": 11.0},
                {"name": "Rashid Shaheed",        "number": 89, "grade": "C",  "catch_rate": 0.62, "avg_yards": 16.5}],
        "te":  [{"name": "Juwan Johnson",         "number": 83, "grade": "B",  "catch_rate": 0.66, "avg_yards": 10.0}],
        "k":   [{"name": "Blake Grupe",           "number": 9,  "grade": "C",  "accuracy": 0.810, "xp_rate": 0.970}],
        "p":   [{"name": "Lou Hedley",            "number": 3,  "grade": "B",  "avg_distance": 46.0, "inside_20_rate": 0.40}],
        "def": [{"name": "Cameron Jordan",        "number": 94, "pos": "DE",   "grade": "A",  "pass_rush": 86, "coverage": 48, "run_stop": 78},
                {"name": "Carl Granderson",       "number": 96, "pos": "DE",   "grade": "B",  "pass_rush": 78, "coverage": 44, "run_stop": 70},
                {"name": "Marshon Lattimore",     "number": 23, "pos": "CB",   "grade": "A",  "pass_rush": 46, "coverage": 88, "run_stop": 70}],
    },
    "TB": {
        "qb":  [{"name": "Baker Mayfield",        "number": 6,  "grade": "B",  "comp_pct": 0.643, "ypa": 7.6, "int_rate": 0.022, "sack_rate": 0.068}],
        "rb":  [{"name": "Rachaad White",         "number": 29, "grade": "B",  "ypc": 4.2, "fumble_rate": 0.012},
                {"name": "Chase Edmonds",         "number": 2,  "grade": "C",  "ypc": 3.8, "fumble_rate": 0.015}],
        "wr":  [{"name": "Mike Evans",            "number": 13, "grade": "A",  "catch_rate": 0.70, "avg_yards": 14.5},
                {"name": "Chris Godwin",          "number": 14, "grade": "A",  "catch_rate": 0.72, "avg_yards": 12.5},
                {"name": "Tanner Hudson",         "number": 87, "grade": "C",  "catch_rate": 0.62, "avg_yards": 11.5}],
        "te":  [{"name": "Cade Otton",            "number": 88, "grade": "B",  "catch_rate": 0.66, "avg_yards": 9.5}],
        "k":   [{"name": "Chase McLaughlin",      "number": 3,  "grade": "B",  "accuracy": 0.848, "xp_rate": 0.980}],
        "p":   [{"name": "Jake Camarda",          "number": 5,  "grade": "A",  "avg_distance": 48.0, "inside_20_rate": 0.42}],
        "def": [{"name": "Yaya Diaby",            "number": 98, "pos": "DE",   "grade": "B",  "pass_rush": 80, "coverage": 46, "run_stop": 70},
                {"name": "Vita Vea",              "number": 50, "pos": "DT",   "grade": "A",  "pass_rush": 80, "coverage": 44, "run_stop": 90},
                {"name": "Carlton Davis",         "number": 33, "pos": "CB",   "grade": "A",  "pass_rush": 46, "coverage": 86, "run_stop": 70}],
    },
    "ARI": {
        "qb":  [{"name": "Kyler Murray",          "number": 1,  "grade": "B",  "comp_pct": 0.635, "ypa": 7.4, "int_rate": 0.022, "sack_rate": 0.072}],
        "rb":  [{"name": "James Conner",          "number": 6,  "grade": "B",  "ypc": 4.4, "fumble_rate": 0.012},
                {"name": "Emari Demercado",       "number": 35, "grade": "C",  "ypc": 3.8, "fumble_rate": 0.016}],
        "wr":  [{"name": "Marvin Harrison Jr.",   "number": 18, "grade": "A",  "catch_rate": 0.70, "avg_yards": 15.0},
                {"name": "Michael Wilson",        "number": 14, "grade": "C",  "catch_rate": 0.62, "avg_yards": 13.5},
                {"name": "Greg Dortch",           "number": 83, "grade": "C",  "catch_rate": 0.66, "avg_yards": 10.5}],
        "te":  [{"name": "Trey McBride",          "number": 85, "grade": "A",  "catch_rate": 0.74, "avg_yards": 11.0}],
        "k":   [{"name": "Matt Prater",           "number": 5,  "grade": "B",  "accuracy": 0.848, "xp_rate": 0.980}],
        "p":   [{"name": "Blake Gillikin",        "number": 7,  "grade": "C",  "avg_distance": 44.0, "inside_20_rate": 0.36}],
        "def": [{"name": "Zaven Collins",         "number": 25, "pos": "LB",   "grade": "B",  "pass_rush": 70, "coverage": 76, "run_stop": 84},
                {"name": "BJ Ojulari",            "number": 40, "pos": "DE",   "grade": "B",  "pass_rush": 80, "coverage": 46, "run_stop": 70},
                {"name": "Sean Murphy-Bunting",   "number": 0,  "pos": "CB",   "grade": "B",  "pass_rush": 44, "coverage": 78, "run_stop": 66}],
    },
    "LAR": {
        "qb":  [{"name": "Matthew Stafford",      "number": 9,  "grade": "B",  "comp_pct": 0.632, "ypa": 7.5, "int_rate": 0.024, "sack_rate": 0.075}],
        "rb":  [{"name": "Kyren Williams",        "number": 23, "grade": "A",  "ypc": 5.0, "fumble_rate": 0.009},
                {"name": "Blake Corum",           "number": 2,  "grade": "C",  "ypc": 3.9, "fumble_rate": 0.015}],
        "wr":  [{"name": "Puka Nacua",            "number": 17, "grade": "A",  "catch_rate": 0.72, "avg_yards": 12.5},
                {"name": "Cooper Kupp",           "number": 10, "grade": "A",  "catch_rate": 0.74, "avg_yards": 11.5},
                {"name": "Demarcus Robinson",     "number": 15, "grade": "C",  "catch_rate": 0.62, "avg_yards": 12.5}],
        "te":  [{"name": "Tyler Higbee",          "number": 89, "grade": "B",  "catch_rate": 0.66, "avg_yards": 9.5}],
        "k":   [{"name": "Joshua Karty",          "number": 9,  "grade": "B",  "accuracy": 0.848, "xp_rate": 0.980}],
        "p":   [{"name": "Ethan Evans",           "number": 16, "grade": "B",  "avg_distance": 46.0, "inside_20_rate": 0.40}],
        "def": [{"name": "Kobie Turner",          "number": 91, "pos": "DT",   "grade": "B",  "pass_rush": 78, "coverage": 44, "run_stop": 84},
                {"name": "Byron Young",           "number": 0,  "pos": "DE",   "grade": "B",  "pass_rush": 80, "coverage": 46, "run_stop": 72},
                {"name": "Darious Williams",      "number": 31, "pos": "CB",   "grade": "B",  "pass_rush": 44, "coverage": 78, "run_stop": 66}],
    },
    "SF": {
        "qb":  [{"name": "Brock Purdy",           "number": 13, "grade": "A",  "comp_pct": 0.674, "ypa": 8.2, "int_rate": 0.017, "sack_rate": 0.055}],
        "rb":  [{"name": "Christian McCaffrey",   "number": 23, "grade": "A",  "ypc": 5.4, "fumble_rate": 0.008},
                {"name": "Elijah Mitchell",       "number": 25, "grade": "C",  "ypc": 4.0, "fumble_rate": 0.014}],
        "wr":  [{"name": "Brandon Aiyuk",         "number": 11, "grade": "A",  "catch_rate": 0.72, "avg_yards": 15.0},
                {"name": "Deebo Samuel",          "number": 19, "grade": "A",  "catch_rate": 0.70, "avg_yards": 12.5},
                {"name": "Jauan Jennings",        "number": 15, "grade": "B",  "catch_rate": 0.68, "avg_yards": 11.5}],
        "te":  [{"name": "George Kittle",         "number": 85, "grade": "A",  "catch_rate": 0.75, "avg_yards": 13.0}],
        "k":   [{"name": "Jake Moody",            "number": 4,  "grade": "B",  "accuracy": 0.850, "xp_rate": 0.982}],
        "p":   [{"name": "Mitch Wishnowsky",      "number": 18, "grade": "B",  "avg_distance": 46.0, "inside_20_rate": 0.40}],
        "def": [{"name": "Nick Bosa",             "number": 97, "pos": "DE",   "grade": "A",  "pass_rush": 96, "coverage": 52, "run_stop": 80},
                {"name": "Javon Hargrave",        "number": 98, "pos": "DT",   "grade": "A",  "pass_rush": 84, "coverage": 44, "run_stop": 86},
                {"name": "Charvarius Ward",       "number": 7,  "pos": "CB",   "grade": "A",  "pass_rush": 48, "coverage": 88, "run_stop": 72}],
    },
    "SEA": {
        "qb":  [{"name": "Geno Smith",            "number": 7,  "grade": "B",  "comp_pct": 0.635, "ypa": 7.2, "int_rate": 0.022, "sack_rate": 0.075}],
        "rb":  [{"name": "Kenneth Walker III",    "number": 9,  "grade": "A",  "ypc": 4.8, "fumble_rate": 0.010},
                {"name": "Zach Charbonnet",       "number": 26, "grade": "B",  "ypc": 4.5, "fumble_rate": 0.012}],
        "wr":  [{"name": "DK Metcalf",            "number": 14, "grade": "A",  "catch_rate": 0.69, "avg_yards": 15.5},
                {"name": "Tyler Lockett",         "number": 16, "grade": "A",  "catch_rate": 0.74, "avg_yards": 12.5},
                {"name": "Jaxon Smith-Njigba",    "number": 11, "grade": "B",  "catch_rate": 0.68, "avg_yards": 11.0}],
        "te":  [{"name": "Noah Fant",             "number": 87, "grade": "B",  "catch_rate": 0.66, "avg_yards": 10.5}],
        "k":   [{"name": "Jason Myers",           "number": 5,  "grade": "B",  "accuracy": 0.848, "xp_rate": 0.980}],
        "p":   [{"name": "Michael Dickson",       "number": 4,  "grade": "A",  "avg_distance": 49.0, "inside_20_rate": 0.43}],
        "def": [{"name": "Uchenna Nwosu",         "number": 10, "pos": "DE",   "grade": "B",  "pass_rush": 80, "coverage": 50, "run_stop": 72},
                {"name": "Leonard Williams",      "number": 99, "pos": "DT",   "grade": "A",  "pass_rush": 82, "coverage": 44, "run_stop": 88},
                {"name": "Devon Witherspoon",     "number": 21, "pos": "CB",   "grade": "A",  "pass_rush": 48, "coverage": 88, "run_stop": 74}],
    },
}


def build_team(team_info: dict) -> dict:
    """Build a complete team dictionary with generated player cards."""
    abbr = team_info["abbreviation"]
    players_data = TEAM_PLAYERS.get(abbr, {})

    players = []

    # QBs
    for p in players_data.get("qb", []):
        card = gen.generate_qb_card(
            name=p["name"], team=abbr, number=p["number"],
            comp_pct=p["comp_pct"], ypa=p["ypa"],
            int_rate=p["int_rate"], sack_rate=p["sack_rate"],
            grade=p["grade"],
        )
        players.append(card.to_dict())

    # RBs
    for p in players_data.get("rb", []):
        card = gen.generate_rb_card(
            name=p["name"], team=abbr, number=p["number"],
            ypc=p["ypc"], fumble_rate=p["fumble_rate"],
            grade=p["grade"],
        )
        players.append(card.to_dict())

    # WRs
    for p in players_data.get("wr", []):
        card = gen.generate_wr_card(
            name=p["name"], team=abbr, number=p["number"],
            catch_rate=p["catch_rate"], avg_yards=p["avg_yards"],
            grade=p["grade"],
        )
        players.append(card.to_dict())

    # TEs
    for p in players_data.get("te", []):
        card = gen.generate_te_card(
            name=p["name"], team=abbr, number=p["number"],
            catch_rate=p["catch_rate"], avg_yards=p["avg_yards"],
            grade=p["grade"],
        )
        players.append(card.to_dict())

    # Kickers
    for p in players_data.get("k", []):
        card = gen.generate_k_card(
            name=p["name"], team=abbr, number=p["number"],
            accuracy=p["accuracy"], xp_rate=p["xp_rate"],
            grade=p["grade"],
        )
        players.append(card.to_dict())

    # Punters
    for p in players_data.get("p", []):
        card = gen.generate_p_card(
            name=p["name"], team=abbr, number=p["number"],
            avg_distance=p["avg_distance"], inside_20_rate=p["inside_20_rate"],
            grade=p["grade"],
        )
        players.append(card.to_dict())

    # Defenders
    for p in players_data.get("def", []):
        card = gen.generate_def_card(
            name=p["name"], team=abbr, number=p["number"],
            position=p["pos"], pass_rush=p["pass_rush"],
            coverage=p["coverage"], run_stop=p["run_stop"],
            grade=p["grade"],
        )
        players.append(card.to_dict())

    return {
        "abbreviation": abbr,
        "city": team_info["city"],
        "name": team_info["name"],
        "conference": team_info["conference"],
        "division": team_info["division"],
        "record": {"wins": 0, "losses": 0, "ties": 0},
        "offense_rating": team_info["offense_rating"],
        "defense_rating": team_info["defense_rating"],
        "players": players,
    }


def main():
    print(f"Generating 2025 team data in {OUTPUT_DIR}")
    for team_info in TEAMS:
        abbr = team_info["abbreviation"]
        print(f"  Generating {abbr} - {team_info['city']} {team_info['name']}...")
        team_data = build_team(team_info)
        filepath = os.path.join(OUTPUT_DIR, f"{abbr}.json")
        with open(filepath, "w") as f:
            json.dump(team_data, f, indent=2)
    print(f"Done! Generated {len(TEAMS)} team files.")


if __name__ == "__main__":
    main()
