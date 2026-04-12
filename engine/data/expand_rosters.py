"""Expand 2025 team rosters from 25 to 45+ players per the 5th Edition guide.

Target roster sizes (from player-card-creation.md):
  QB: 3, RB: 6, WR: 5, TE: 3, OL: 8, DL: 6, LB: 8, DB: 7
  Plus K: 1, P: 1 (not counted in the 45)

This script reads existing 2025 data, adds depth players with realistic
backup-level stats, then writes expanded data to both 2025/ and 2025_5e/.
"""
import sys
import os
import json
import random
import copy

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from engine.card_generator import CardGenerator
from engine.player_card import RECEIVER_LETTERS

random.seed(42)
gen = CardGenerator(seed=42)

DATA_DIR = os.path.join(os.path.dirname(__file__))
INPUT_DIR = os.path.join(DATA_DIR, "2025")
OUTPUT_5E_DIR = os.path.join(DATA_DIR, "2025_5e")

DEFENDER_LETTERS = list("ABCDEFGHIJKLMNOPQRSTU")

# ── Real 2024 NFL depth-chart backup names by team ──────────────────────────
# Keys: team abbrev → position group → list of {name, number, ...}
# Only the ADDITIONAL players beyond the existing 25 are listed here.

BACKUP_NAMES = {
    "ARI": {
        "qb": ["Clayton Tune", "Desmond Ridder"],
        "rb": ["Emari Demercado", "Trey Benson", "DeeJay Dallas", "Michael Carter"],
        "wr": ["Greg Dortch", "Zay Jones"],
        "te": ["Elijah Higgins", "Geoff Swaim"],
        "ol": ["Evan Brown", "Kelvin Beachum", "Josh Jones"],
        "dl": ["Bilal Nichols", "Dante Stills"],
        "lb": ["Dennis Gardeck", "Owen Pappoe", "Jesse Luketa", "Victor Dimukeje", "Cameron Thomas"],
        "db": ["Starling Thomas V", "Garrett Williams", "Jalen Thompson"],
    },
    "ATL": {
        "qb": ["Taylor Heinicke", "Logan Woodside"],
        "rb": ["Avery Williams", "Carlos Washington Jr.", "Jase McClellan", "Caleb Huntley"],
        "wr": ["Ray-Ray McCloud", "KhaDarel Hodge"],
        "te": ["MyCole Pruitt", "Ross Dwelley"],
        "ol": ["Ryan Neuzil", "Matt Hennessy", "John Leglue"],
        "dl": ["Ta'Quon Graham", "LaCale London"],
        "lb": ["Nate Landman", "Troy Andersen", "Mykal Walker", "JD Bertrand", "Rashaan Evans"],
        "db": ["Mike Hughes", "Dee Alford", "Richie Grant"],
    },
    "BAL": {
        "qb": ["Josh Johnson", "Devin Leary"],
        "rb": ["Gus Edwards", "Justice Hill", "Keaton Mitchell", "Chris Collier"],
        "wr": ["Nelson Agholor", "Tylan Wallace"],
        "te": ["Charlie Kolar", "Josh Oliver"],
        "ol": ["Ben Cleveland", "Andrew Vorhees", "Sam Mustipher"],
        "dl": ["Broderick Washington", "Travis Jones"],
        "lb": ["Malik Harrison", "Del'Shawn Phillips", "Kristian Welch", "David Ojabo", "Tavius Robinson"],
        "db": ["Arthur Maulet", "Brandon Stephens", "Ar'Darius Washington"],
    },
    "BUF": {
        "qb": ["Mitchell Trubisky", "Shane Buechele"],
        "rb": ["Latavius Murray", "Ty Johnson", "Frank Gore Jr.", "Darrynton Evans"],
        "wr": ["Curtis Samuel", "Mack Hollins"],
        "te": ["Quintin Morris", "Reggie Gilliam"],
        "ol": ["David Edwards", "Alec Anderson", "Greg Van Roten"],
        "dl": ["Shaq Lawson", "Tim Settle"],
        "lb": ["Baylon Spector", "Tyler Matakevich", "Joe Andreessen", "Nicholas Morrow", "Tyrel Dodson"],
        "db": ["Taron Johnson", "Christian Benford", "Micah Hyde"],
    },
    "CAR": {
        "qb": ["Andy Dalton", "Jake Luton"],
        "rb": ["Miles Sanders", "Raheem Blackshear", "Spencer Brown", "Velus Jones Jr."],
        "wr": ["Terrace Marshall Jr.", "Shi Smith"],
        "te": ["Ian Thomas", "Stephen Sullivan"],
        "ol": ["Brady Christensen", "Cade Mays", "Pat Elflein"],
        "dl": ["DeShawn Williams", "Shy Tuttle"],
        "lb": ["Josey Jewell", "DJ Johnson", "Amaré Barno", "Yetur Gross-Matos", "Trevin Wallace"],
        "db": ["Troy Hill", "Dane Jackson", "Sam Franklin Jr."],
    },
    "CHI": {
        "qb": ["Tyson Bagent", "Brett Rypien"],
        "rb": ["Roschon Johnson", "Travis Homer", "Velus Jones Jr.", "Darrynton Evans"],
        "wr": ["Tyler Scott", "Velus Jones Jr."],
        "te": ["Marcedes Lewis", "Robert Tonyan"],
        "ol": ["Matt Pryor", "Cody Whitehair", "Nate Davis"],
        "dl": ["Andrew Billings", "Zacch Pickens"],
        "lb": ["Noah Sewell", "Jack Sanborn", "Joe Thomas", "Matt Adams", "Nicholas Morrow"],
        "db": ["Kyler Gordon", "Josh Blackwell", "Elijah Hicks"],
    },
    "CIN": {
        "qb": ["Jake Browning", "AJ McCarron"],
        "rb": ["Chris Evans", "Trayveon Williams", "Chase Brown", "Samaje Perine"],
        "wr": ["Trenton Irwin", "Andrei Iosivas"],
        "te": ["Drew Sample", "Tanner Hudson"],
        "ol": ["Cordell Volson", "Max Scharping", "Hakeem Adeniji"],
        "dl": ["Jay Tufele", "Myles Murphy"],
        "lb": ["Markus Bailey", "Joe Bachie", "Maema Njongmeta", "Akeem Davis-Gaither", "Clay Johnston"],
        "db": ["Dax Hill", "DJ Turner", "Jordan Battle"],
    },
    "CLE": {
        "qb": ["Joe Flacco", "Dorian Thompson-Robinson"],
        "rb": ["Pierre Strong Jr.", "D'Onta Foreman", "Demetric Felton Jr.", "John Kelly"],
        "wr": ["Cedric Tillman", "David Bell"],
        "te": ["Jordan Akins", "Pharaoh Brown"],
        "ol": ["Michael Dunn", "Blake Hance", "Nick Harris"],
        "dl": ["Dalvin Tomlinson", "Shelby Harris"],
        "lb": ["Tony Fields II", "Jacob Phillips", "Mohamoud Diabate", "Siaki Ika", "Isaiah Thomas"],
        "db": ["Ronnie Hickman", "Cameron Mitchell", "Juan Thornhill"],
    },
    "DAL": {
        "qb": ["Cooper Rush", "Trey Lance"],
        "rb": ["Deuce Vaughn", "Hunter Luepke", "Malik Davis", "Snoop Conner"],
        "wr": ["Jalen Tolbert", "KaVontae Turpin"],
        "te": ["Peyton Hendershot", "Luke Schoonmaker"],
        "ol": ["Chuma Edoga", "Brock Hoffman", "Matt Waletzko"],
        "dl": ["Neville Gallimore", "Osa Odighizuwa"],
        "lb": ["Damone Clark", "Markquese Bell", "Jabril Cox", "Devin Harper", "Luke Gifford"],
        "db": ["Nahshon Wright", "Israel Mukuamu", "Donovan Wilson"],
    },
    "DEN": {
        "qb": ["Jarrett Stidham", "Ben DiNucci"],
        "rb": ["Samaje Perine", "Tyler Badie", "Jaleel McLaughlin", "Blake Watson"],
        "wr": ["Lil'Jordan Humphrey", "Brandon Johnson"],
        "te": ["Chris Manhertz", "Greg Dulcich"],
        "ol": ["Quinn Bailey", "Luke Wattenberg", "Alex Palczewski"],
        "dl": ["D.J. Jones", "Matt Henningsen"],
        "lb": ["Josey Jewell", "Justin Strnad", "Drew Sanders", "Nik Bonitto", "Frank Clark"],
        "db": ["Damarri Mathis", "Tremon Smith", "Caden Sterns"],
    },
    "DET": {
        "qb": ["Hendon Hooker", "Nate Sudfeld"],
        "rb": ["Craig Reynolds", "Zonovan Knight", "Jermar Jefferson", "Jason Cabinda"],
        "wr": ["Kalif Raymond", "Donovan Peoples-Jones"],
        "te": ["Brock Wright", "Shane Zylstra"],
        "ol": ["Dan Skipper", "Evan Brown", "Colby Sorsdal"],
        "dl": ["Isaiah Buggs", "Levi Onwuzurike"],
        "lb": ["Derrick Barnes", "Malcolm Rodriguez", "James Houston", "Josh Paschal", "Jalen Reeves-Maybin"],
        "db": ["Emmanuel Moseley", "Steven Gilmore", "C.J. Moore"],
    },
    "GB": {
        "qb": ["Sean Clifford", "Danny Etling"],
        "rb": ["Emanuel Wilson", "Patrick Taylor", "Jarveon Howard", "Chris Brooks"],
        "wr": ["Bo Melton", "Samori Toure"],
        "te": ["Ben Sims", "Tyler Davis"],
        "ol": ["Sean Rhyan", "Jake Hanson", "Caleb Jones"],
        "dl": ["T.J. Slaton", "Jonathan Ford"],
        "lb": ["Isaiah McDuffie", "Krys Barnes", "Quay Walker", "Kingsley Enagbare", "Colby Wooden"],
        "db": ["Carrington Valentine", "Corey Ballentine", "Jonathan Owens"],
    },
    "HOU": {
        "qb": ["Davis Mills", "Case Keenum"],
        "rb": ["Dare Ogunbowale", "Mike Boone", "J.J. Taylor", "Dameon Pierce"],
        "wr": ["Robert Woods", "John Metchie III"],
        "te": ["Brevin Jordan", "Teagan Quitoriano"],
        "ol": ["Jarrett Patterson", "Blake Fisher", "Jimmy Morrissey"],
        "dl": ["Foley Fatukasi", "Kurt Hinish"],
        "lb": ["Christian Harris", "Henry To'oTo'o", "Jake Hansen", "Neville Hewitt", "Blake Cashman"],
        "db": ["Tavierre Thomas", "Desmond King II", "Jalen Pitre"],
    },
    "IND": {
        "qb": ["Gardner Minshew", "Sam Ehlinger"],
        "rb": ["Trey Sermon", "Evan Hull", "Deon Jackson", "Jake Funk"],
        "wr": ["Josh Downs", "Adonai Mitchell"],
        "te": ["Kylen Granson", "Drew Ogletree"],
        "ol": ["Josh Sills", "Danny Pinter", "Will Fries"],
        "dl": ["Tyquan Lewis", "Raimon Jeffery"],
        "lb": ["E.J. Speed", "Grant Stuard", "Segun Olubi", "Cameron McGrone", "Jeremiah Owusu-Koramoah"],
        "db": ["Darren Hall", "JuJu Brents", "Rodney Thomas II"],
    },
    "JAX": {
        "qb": ["C.J. Beathard", "Nathan Rourke"],
        "rb": ["D'Ernest Johnson", "JaMycal Hasty", "Snoop Conner", "Qadree Ollison"],
        "wr": ["Tim Jones", "Parker Washington"],
        "te": ["Luke Farrell", "Brenton Strange"],
        "ol": ["Tyler Shatley", "Cole Van Lanen", "Blake Hance"],
        "dl": ["Roy Robertson-Harris", "Angelo Blackson"],
        "lb": ["Yasir Abdullah", "Ventrell Miller", "Chad Muma", "Caleb Johnson", "Shaquille Quarterman"],
        "db": ["Gregory Junior", "Montaric Brown", "Andre Cisco"],
    },
    "KC": {
        "qb": ["Carson Wentz", "Chris Oladokun"],
        "rb": ["Jerick McKinnon", "La'Mical Perine", "Deneric Prince", "Emani Bailey"],
        "wr": ["Skyy Moore", "Justyn Ross"],
        "te": ["Noah Gray", "Jody Fortson"],
        "ol": ["Mike Caliendo", "Nick Allegretti", "Andrew Wylie"],
        "dl": ["Derrick Nnadi", "Tershawn Wharton"],
        "lb": ["Drue Tranquill", "Willie Gay Jr.", "Leo Chenal", "Jack Cochrane", "Curtis Bolton"],
        "db": ["L'Jarius Sneed", "Joshua Williams", "Bryan Cook"],
    },
    "LAC": {
        "qb": ["Easton Stick", "Max Duggan"],
        "rb": ["Joshua Kelley", "Elijah Dotson", "Hassan Haskins", "Isaiah Spiller"],
        "wr": ["Joshua Palmer", "Derius Davis"],
        "te": ["Donald Parham Jr.", "Tre' McKitty"],
        "ol": ["Brenden Jaimes", "Will Clapp", "Foster Sarell"],
        "dl": ["Morgan Fox", "Scott Matlock"],
        "lb": ["Daiyan Henley", "Amen Ogbongbemiga", "Chris Rumph II", "Troy Dye", "Nick Niemann"],
        "db": ["Alohi Gilman", "Ja'Sir Taylor", "Raheem Layne"],
    },
    "LAR": {
        "qb": ["Jimmy Garoppolo", "Stetson Bennett"],
        "rb": ["Ronnie Rivers", "Zach Evans", "Royce Freeman", "Boston Scott"],
        "wr": ["Tyler Johnson", "Tutu Atwell"],
        "te": ["Hunter Long", "Davis Allen"],
        "ol": ["Alaric Jackson", "Coleman Shelton", "Conor McDermott"],
        "dl": ["Marquise Copeland", "Bobby Brown III"],
        "lb": ["Christian Rozeboom", "Jake Hummel", "Ochaun Mathis", "Keir Thomas", "Derion Kendrick"],
        "db": ["Robert Rochell", "Cobie Durant", "Quentin Lake"],
    },
    "LV": {
        "qb": ["Aidan O'Connell", "Brian Hoyer"],
        "rb": ["Ameer Abdullah", "Sincere McCormick", "Zamir White", "Brandon Bolden"],
        "wr": ["Tre Tucker", "Michael Gallup"],
        "te": ["Michael Mayer", "Harrison Bryant"],
        "ol": ["Jermaine Eluemunor", "Jordan Meredith", "Andrus Peat"],
        "dl": ["Bilal Nichols", "Jerry Tillery"],
        "lb": ["Luke Masterson", "Curtis Bolton", "Darien Butler", "Divine Deablo", "Amari Burney"],
        "db": ["Amik Robertson", "Sam Webb", "Tre'von Moehrig"],
    },
    "MIA": {
        "qb": ["Mike White", "Skylar Thompson"],
        "rb": ["Salvon Ahmed", "Chris Brooks", "Jeff Wilson Jr.", "Myles Gaskin"],
        "wr": ["Cedric Wilson Jr.", "Erik Ezukanma"],
        "te": ["Julian Hill", "Tanner Conner"],
        "ol": ["Liam Eichenberg", "Robert Hunt", "Michael Deiter"],
        "dl": ["Raekwon Davis", "Brandon Pili"],
        "lb": ["Duke Riley", "Calvin Munson", "Channing Tindall", "Sam Eguavoen", "Cameron Goode"],
        "db": ["Kader Kohou", "Ethan Bonner", "Jevon Holland"],
    },
    "MIN": {
        "qb": ["Nick Mullens", "Jaren Hall"],
        "rb": ["Ty Chandler", "Kene Nwangwu", "DeWayne McBride", "Myles Gaskin"],
        "wr": ["Brandon Powell", "Jalen Nailor"],
        "te": ["Johnny Mundt", "Nick Muse"],
        "ol": ["Dalton Risner", "Austin Schlottmann", "David Quessenberry"],
        "dl": ["Dean Lowry", "Jalen Redmond"],
        "lb": ["Troy Reeder", "Ivan Pace Jr.", "Abraham Beauplan", "Brian Asamoah II", "Wilson Huber"],
        "db": ["Akayleb Evans", "Mekhi Blackmon", "Josh Metellus"],
    },
    "NE": {
        "qb": ["Bailey Zappe", "Will Grier"],
        "rb": ["Ezekiel Elliott", "Kevin Harris", "Pierre Strong Jr.", "J.J. Taylor"],
        "wr": ["Demario Douglas", "Tyquan Thornton"],
        "te": ["Pharaoh Brown", "Matt Sokol"],
        "ol": ["Atonio Mafi", "Jake Andrews", "Sidy Sow"],
        "dl": ["Lawrence Guy", "Jeremiah Pharms Jr."],
        "lb": ["Jahlani Tavai", "Marte Mapu", "Raekwon McMillan", "Diego Fagot", "Chris Board"],
        "db": ["Myles Bryant", "Marcus Jones", "Jabrill Peppers"],
    },
    "NO": {
        "qb": ["Jameis Winston", "Jake Haener"],
        "rb": ["Jamaal Williams", "Kendre Miller", "Jordan Mims", "Tony Jones Jr."],
        "wr": ["Rashid Shaheed", "A.T. Perry"],
        "te": ["Foster Moreau", "Lucas Krull"],
        "ol": ["Landon Young", "Lewis Kidd", "Cesar Ruiz"],
        "dl": ["Nathan Shepherd", "Khalen Saunders"],
        "lb": ["Zack Baun", "D'Marco Jackson", "Isaiah Foskey", "Nephi Sewell", "Pete Werner"],
        "db": ["Alontae Taylor", "Isaac Yiadom", "Jordan Howden"],
    },
    "NYG": {
        "qb": ["Tommy DeVito", "Matt Barkley"],
        "rb": ["Eric Gray", "Matt Breida", "Gary Brightwell", "Chris Rodriguez Jr."],
        "wr": ["Isaiah Hodgins", "Gunner Olszewski"],
        "te": ["Lawrence Cager", "Chris Myarick"],
        "ol": ["Ben Bredeson", "Marcus McKethan", "Shane Lemieux"],
        "dl": ["Rakeem Nunez-Roches", "D.J. Davidson"],
        "lb": ["Micah McFadden", "Carter Coughlin", "Tae Crowder", "Cam Brown", "Jihad Ward"],
        "db": ["Nick McCloud", "Tre Hawkins", "Jason Pinnock"],
    },
    "NYJ": {
        "qb": ["Zach Wilson", "Tim Boyle"],
        "rb": ["Israel Abanikanda", "Zonovan Knight", "Travis Dye", "Izzy Abanikanda"],
        "wr": ["Randall Cobb", "Jason Brownlee"],
        "te": ["Jeremy Ruckert", "Kenny Yeboah"],
        "ol": ["Max Mitchell", "Wes Schweitzer", "Jake Hanson"],
        "dl": ["Solomon Thomas", "Leki Fotu"],
        "lb": ["Jamien Sherwood", "Del'Shawn Phillips", "Chazz Surratt", "Hamsah Nasirildeen", "Claudin Cherelus"],
        "db": ["Brandin Echols", "Craig James", "Tony Adams"],
    },
    "PHI": {
        "qb": ["Kenny Pickett", "Tanner McKee"],
        "rb": ["Kenneth Gainwell", "Boston Scott", "Tyrion Davis-Price", "Lew Nichols III"],
        "wr": ["Quez Watkins", "Britain Covey"],
        "te": ["Grant Calcaterra", "Albert Okwuegbunam"],
        "ol": ["Mekhi Becton", "Tyler Steen", "Brett Toth"],
        "dl": ["Milton Williams", "Marlon Tuipulotu"],
        "lb": ["Nicholas Morrow", "Ben VanSumeren", "Oren Burks", "Patrick Johnson", "Christian Elliss"],
        "db": ["Kelee Ringo", "Mario Goodrich", "Tristin McCollum"],
    },
    "PIT": {
        "qb": ["Mason Rudolph", "Kyle Allen"],
        "rb": ["Jaylen Warren", "Benny Snell Jr.", "Connor Heyward", "Anthony McFarland Jr."],
        "wr": ["Calvin Austin III", "Van Jefferson"],
        "te": ["Connor Heyward", "Zach Gentry"],
        "ol": ["Nate Herbig", "Mason Cole", "Jesse Davis"],
        "dl": ["DeMarvin Leal", "Montravius Adams"],
        "lb": ["Mark Robinson", "Myles Jack", "Cole Holcomb", "Robert Spillane", "Buddy Johnson"],
        "db": ["James Pierre", "Chandon Sullivan", "Damontae Kazee"],
    },
    "SF": {
        "qb": ["Sam Darnold", "Brandon Allen"],
        "rb": ["Elijah Mitchell", "Jordan Mason", "Tyrion Davis-Price", "Ke'Shawn Vaughn"],
        "wr": ["Jauan Jennings", "Ray-Ray McCloud"],
        "te": ["Charlie Woerner", "Cameron Latu"],
        "ol": ["Spencer Burford", "Matt Pryor", "Jon Feliciano"],
        "dl": ["Javon Hargrave", "Kevin Givens"],
        "lb": ["Oren Burks", "Curtis Robinson", "Demetrius Flannigan-Fowles", "Dee Winters", "Jalen Graham"],
        "db": ["Ambry Thomas", "Samuel Womack", "Tashaun Gipson Sr."],
    },
    "SEA": {
        "qb": ["Drew Lock", "Holton Ahlers"],
        "rb": ["Zach Charbonnet", "DeeJay Dallas", "SaRodorick Thompson", "Godwin Igwebuike"],
        "wr": ["Jake Bobo", "Dareke Young"],
        "te": ["Will Dissly", "Colby Parkinson"],
        "ol": ["Stone Forsythe", "Phil Haynes", "Jake Curhan"],
        "dl": ["Mario Edwards Jr.", "Myles Adams"],
        "lb": ["Jordyn Brooks", "Jon Rhattigan", "Tanner Muse", "Vi Jones", "Devin Bush"],
        "db": ["Artie Burns", "Coby Bryant", "Quandre Diggs"],
    },
    "TB": {
        "qb": ["Kyle Trask", "John Wolford"],
        "rb": ["Chase Edmonds", "Ke'Shawn Vaughn", "Patrick Laird", "Sean Tucker"],
        "wr": ["Trey Palmer", "Jalen McMillan"],
        "te": ["Payne Durham", "Ko Kieft"],
        "ol": ["Nick Leverett", "Matt Feiler", "Robert Hainsey"],
        "dl": ["Greg Gaines", "William Gholston"],
        "lb": ["K.J. Britt", "SirVocea Dennis", "Olakunle Fatukasi", "JJ Russell", "Vi Jones"],
        "db": ["Christian Izien", "Josh Hayes", "Ryan Neal"],
    },
    "TEN": {
        "qb": ["Malik Willis", "Matt Barkley"],
        "rb": ["Julius Chestnut", "Hassan Haskins", "Jabari Small", "Tyjae Spears"],
        "wr": ["Kyle Philips", "Nick Westbrook-Ikhine"],
        "te": ["Josh Whyle", "Thomas Odukoya"],
        "ol": ["Andrew Rupcich", "Dillon Radunz", "Jaelyn Duncan"],
        "dl": ["Keondre Coburn", "Teair Tart"],
        "lb": ["Azeez Al-Shaair", "Jack Gibbens", "Chance Campbell", "Monty Rice", "Dylan Cole"],
        "db": ["Sean Murphy-Bunting", "Tre Avery", "Amani Hooker"],
    },
    "WSH": {
        "qb": ["Sam Howell", "Jeff Driskel"],
        "rb": ["Chris Rodriguez Jr.", "Jonathan Williams", "Reggie Bonnafon", "Craig Reynolds"],
        "wr": ["Dyami Brown", "Olamide Zaccheaus"],
        "te": ["Cole Turner", "Armani Rogers"],
        "ol": ["Tyler Larsen", "Saahdiq Charles", "Trai Turner"],
        "dl": ["John Ridgeway", "Phidarian Mathis"],
        "lb": ["Cody Barton", "David Mayo", "De'Jon Harris", "Milo Eifler", "Khaleke Hudson"],
        "db": ["Christian Holmes", "Percy Butler", "Bobby McCain"],
    },
}

# ── Generic stat ranges for backup players ──────────────────────────────────

def _backup_qb_stats(tier):
    """tier 0 = QB2, 1 = QB3"""
    if tier == 0:
        return {"comp_pct": round(random.uniform(0.57, 0.62), 3),
                "ypa": round(random.uniform(6.0, 6.8), 1),
                "int_rate": round(random.uniform(0.028, 0.035), 3),
                "sack_rate": round(random.uniform(0.075, 0.090), 3)}
    return {"comp_pct": round(random.uniform(0.52, 0.58), 3),
            "ypa": round(random.uniform(5.5, 6.2), 1),
            "int_rate": round(random.uniform(0.032, 0.042), 3),
            "sack_rate": round(random.uniform(0.085, 0.100), 3)}

def _backup_rb_stats(tier):
    ypc = round(random.uniform(2.8 + 0.3*(3-tier), 3.6 + 0.3*(3-tier)), 1)
    return {"ypc": ypc, "fumble_rate": round(random.uniform(0.012, 0.022), 3)}

def _backup_wr_stats(tier):
    cr = round(random.uniform(0.52 + 0.03*(2-tier), 0.62 + 0.02*(2-tier)), 2)
    ay = round(random.uniform(8.5 + 0.5*(2-tier), 11.5 + 0.5*(2-tier)), 1)
    return {"catch_rate": cr, "avg_yards": ay}

def _backup_te_stats(tier):
    cr = round(random.uniform(0.48 + 0.03*(2-tier), 0.60 + 0.02*(2-tier)), 2)
    ay = round(random.uniform(6.0 + 0.5*(2-tier), 9.0 + 0.5*(2-tier)), 1)
    return {"catch_rate": cr, "avg_yards": ay}

def _backup_ol_stats():
    return {"run_block": random.randint(58, 70), "pass_block": random.randint(56, 68)}

def _backup_def_stats(pos):
    if pos in ("DE", "DT"):
        return {"pass_rush": random.randint(48, 70), "coverage": random.randint(35, 48), "run_stop": random.randint(55, 72)}
    elif pos == "LB":
        return {"pass_rush": random.randint(42, 62), "coverage": random.randint(45, 65), "run_stop": random.randint(55, 72)}
    else:  # CB, S
        return {"pass_rush": random.randint(35, 50), "coverage": random.randint(55, 75), "run_stop": random.randint(48, 65)}


OL_POSITIONS = ["LT", "LG", "C", "RG", "RT", "LT", "LG", "C"]  # cycle for backups


def expand_team_players(team_data: dict, abbr: str) -> dict:
    """Expand a team's player list from ~25 to 45+ (plus K+P)."""
    players = team_data.get("players", [])
    new_players = list(players)  # keep all existing

    # Count existing by rough position group
    existing = {"QB": [], "RB": [], "WR": [], "TE": [], "K": [], "P": [],
                "OL": [], "DL": [], "LB": [], "DB": []}
    for p in players:
        pos = p.get("position", "")
        if pos == "QB": existing["QB"].append(p)
        elif pos == "RB": existing["RB"].append(p)
        elif pos == "WR": existing["WR"].append(p)
        elif pos == "TE": existing["TE"].append(p)
        elif pos == "K": existing["K"].append(p)
        elif pos == "P": existing["P"].append(p)
        elif pos in ("LT", "LG", "C", "RG", "RT", "OL"): existing["OL"].append(p)
        elif pos in ("DE", "DT", "DL", "NT"): existing["DL"].append(p)
        elif pos in ("LB", "ILB", "OLB", "MLB"): existing["LB"].append(p)
        elif pos in ("CB", "S", "SS", "FS", "DB"): existing["DB"].append(p)

    targets = {"QB": 3, "RB": 6, "WR": 5, "TE": 3, "OL": 8, "DL": 6, "LB": 8, "DB": 7}
    backups = BACKUP_NAMES.get(abbr, {})

    used_numbers = {p.get("number", 0) for p in players}

    def next_number(start=50):
        n = start
        while n in used_numbers:
            n += 1
        used_numbers.add(n)
        return n

    # Add QBs
    need = targets["QB"] - len(existing["QB"])
    names = backups.get("qb", [])
    for i in range(need):
        nm = names[i] if i < len(names) else f"QB{len(existing['QB'])+i+1} {abbr}"
        grade = "C" if i == 0 else "D"
        stats = _backup_qb_stats(i)
        p = _make_player(nm, "QB", next_number(2), abbr, grade, stats)
        new_players.append(p)

    # Add RBs
    need = targets["RB"] - len(existing["RB"])
    names = backups.get("rb", [])
    for i in range(need):
        nm = names[i] if i < len(names) else f"RB{len(existing['RB'])+i+1} {abbr}"
        grade = "C" if i < 2 else "D"
        stats = _backup_rb_stats(i)
        p = _make_player(nm, "RB", next_number(20), abbr, grade, stats)
        new_players.append(p)

    # Add WRs
    need = targets["WR"] - len(existing["WR"])
    names = backups.get("wr", [])
    for i in range(need):
        nm = names[i] if i < len(names) else f"WR{len(existing['WR'])+i+1} {abbr}"
        grade = "C" if i == 0 else "D"
        stats = _backup_wr_stats(i)
        p = _make_player(nm, "WR", next_number(80), abbr, grade, stats)
        new_players.append(p)

    # Add TEs
    need = targets["TE"] - len(existing["TE"])
    names = backups.get("te", [])
    for i in range(need):
        nm = names[i] if i < len(names) else f"TE{len(existing['TE'])+i+1} {abbr}"
        grade = "C" if i == 0 else "D"
        stats = _backup_te_stats(i)
        p = _make_player(nm, "TE", next_number(80), abbr, grade, stats)
        new_players.append(p)

    # Add OL
    need = targets["OL"] - len(existing["OL"])
    names = backups.get("ol", [])
    ol_pos_cycle = ["LT", "LG", "C", "RG", "RT"]
    for i in range(need):
        nm = names[i] if i < len(names) else f"OL{len(existing['OL'])+i+1} {abbr}"
        pos = ol_pos_cycle[i % len(ol_pos_cycle)]
        grade = "C" if i == 0 else "D"
        stats = _backup_ol_stats()
        p = _make_ol_player(nm, pos, next_number(60), abbr, grade, stats)
        new_players.append(p)

    # Add DL
    need = targets["DL"] - len(existing["DL"])
    names = backups.get("dl", [])
    dl_pos_cycle = ["DE", "DT"]
    for i in range(need):
        nm = names[i] if i < len(names) else f"DL{len(existing['DL'])+i+1} {abbr}"
        pos = dl_pos_cycle[i % 2]
        grade = "C" if i == 0 else "D"
        stats = _backup_def_stats(pos)
        p = _make_def_player(nm, pos, next_number(90), abbr, grade, stats)
        new_players.append(p)

    # Add LBs
    need = targets["LB"] - len(existing["LB"])
    names = backups.get("lb", [])
    for i in range(need):
        nm = names[i] if i < len(names) else f"LB{len(existing['LB'])+i+1} {abbr}"
        grade = "C" if i < 2 else "D"
        stats = _backup_def_stats("LB")
        p = _make_def_player(nm, "LB", next_number(40), abbr, grade, stats)
        new_players.append(p)

    # Add DBs
    need = targets["DB"] - len(existing["DB"])
    names = backups.get("db", [])
    db_pos_cycle = ["CB", "CB", "S"]
    for i in range(need):
        nm = names[i] if i < len(names) else f"DB{len(existing['DB'])+i+1} {abbr}"
        pos = db_pos_cycle[i % 3]
        grade = "C" if i < 1 else "D"
        stats = _backup_def_stats(pos)
        p = _make_def_player(nm, pos, next_number(20), abbr, grade, stats)
        new_players.append(p)

    result = dict(team_data)
    result["players"] = new_players
    return result


def _make_player(name, position, number, team, grade, stats):
    """Create a basic player dict in the same format as existing data."""
    base = {
        "name": name, "position": position, "number": number, "team": team,
        "overall_grade": grade, "receiver_letter": "",
        "passing_quick": None, "passing_short": None, "passing_long": None,
        "pass_rush": None, "long_pass_com_adj": 0, "qb_endurance": "C",
        "rushing": [], "endurance_rushing": 3, "pass_gain": [],
        "endurance_pass": 0, "blocks": 0,
        "fg_chart": {}, "xp_rate": 0.95,
        "avg_distance": 44.0, "inside_20_rate": 0.35,
        "run_block_rating": 0, "pass_block_rating": 0,
        "pass_rush_rating": 50, "coverage_rating": 50, "run_stop_rating": 50,
        "tackle_rating": 0, "pass_defense_rating": 0, "intercept_range": 0,
        "defender_letter": "",
        "stats_summary": stats,
        "short_pass": {}, "long_pass": {}, "quick_pass": {}, "screen_pass": {},
        "qb_rush": {}, "inside_run": {}, "outside_run": {}, "sweep": {},
        "short_reception": {}, "long_reception": {}, "punt_column": {},
    }
    return base


def _make_ol_player(name, position, number, team, grade, stats):
    p = _make_player(name, position, number, team, grade, stats)
    p["run_block_rating"] = stats["run_block"]
    p["pass_block_rating"] = stats["pass_block"]
    return p


def _make_def_player(name, position, number, team, grade, stats):
    p = _make_player(name, position, number, team, grade, stats)
    p["pass_rush_rating"] = stats["pass_rush"]
    p["coverage_rating"] = stats["coverage"]
    p["run_stop_rating"] = stats["run_stop"]
    return p


def upgrade_to_5e(team_data: dict) -> dict:
    """Apply 5E card generation to all players."""
    players = team_data.get("players", [])
    new_players = []
    abbr = team_data["abbreviation"]
    receiver_idx = 0
    defender_idx = 0

    for p in players:
        pos = p.get("position", "")
        grade = p.get("overall_grade", "C")
        stats = p.get("stats_summary", {})

        if pos == "QB":
            card = gen.generate_qb_card_authentic(
                name=p["name"], team=abbr, number=p["number"],
                comp_pct=stats.get("comp_pct", 0.58),
                ypa=stats.get("ypa", 6.5),
                int_rate=stats.get("int_rate", 0.030),
                sack_rate=stats.get("sack_rate", 0.080),
                grade=grade,
                rush_ypc=stats.get("rush_ypc", 2.5),
                rush_fumble_rate=stats.get("rush_fumble_rate", 0.015),
            )
            new_players.append(card.to_dict())
        elif pos == "RB":
            letter = ""
            if receiver_idx < 8:
                letter = RECEIVER_LETTERS[receiver_idx] if receiver_idx < len(RECEIVER_LETTERS) else ""
                receiver_idx += 1
            endurance_pass = 2
            cr = stats.get("catch_rate", 0.3)
            if cr >= 0.5: endurance_pass = 0
            elif cr >= 0.35: endurance_pass = 1
            elif cr < 0.2: endurance_pass = 4
            card = gen.generate_rb_card_authentic(
                name=p["name"], team=abbr, number=p["number"],
                ypc=stats.get("ypc", 3.5), fumble_rate=stats.get("fumble_rate", 0.015),
                grade=grade, catch_rate=stats.get("catch_rate", 0.25),
                avg_rec_yards=stats.get("avg_yards", 6.0),
                endurance_pass=endurance_pass, blocks=1 if grade in ("A","B") else 0,
                receiver_letter=letter,
            )
            new_players.append(card.to_dict())
        elif pos == "WR":
            letter = RECEIVER_LETTERS[receiver_idx] if receiver_idx < len(RECEIVER_LETTERS) else ""
            receiver_idx += 1
            card = gen.generate_wr_card_authentic(
                name=p["name"], team=abbr, number=p["number"],
                catch_rate=stats.get("catch_rate", 0.58),
                avg_yards=stats.get("avg_yards", 10.0),
                grade=grade, receiver_letter=letter,
                blocks=-2 if grade in ("C","D") else -1,
            )
            new_players.append(card.to_dict())
        elif pos == "TE":
            letter = RECEIVER_LETTERS[receiver_idx] if receiver_idx < len(RECEIVER_LETTERS) else ""
            receiver_idx += 1
            card = gen.generate_te_card_authentic(
                name=p["name"], team=abbr, number=p["number"],
                catch_rate=stats.get("catch_rate", 0.55),
                avg_yards=stats.get("avg_yards", 8.0),
                grade=grade, receiver_letter=letter,
                blocks=3 if grade in ("A","B") else 2,
            )
            new_players.append(card.to_dict())
        elif pos in ("K",):
            new_players.append(p)
        elif pos in ("P",):
            new_players.append(p)
        elif pos in ("LT", "LG", "C", "RG", "RT", "OL"):
            card = gen.generate_ol_card(
                name=p["name"], team=abbr, number=p["number"],
                position=pos, grade=grade,
                run_block=stats.get("run_block_rating", p.get("run_block_rating", 65)),
                pass_block=stats.get("pass_block_rating", p.get("pass_block_rating", 63)),
            )
            new_players.append(card.to_dict())
        elif pos in ("DL", "DE", "DT", "NT", "LB", "CB", "S", "SS", "FS", "DEF"):
            letter = DEFENDER_LETTERS[defender_idx] if defender_idx < len(DEFENDER_LETTERS) else ""
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
            new_players.append(p)

    result = dict(team_data)
    result["players"] = new_players
    result["edition"] = "5e"
    return result


def main():
    team_files = sorted(f for f in os.listdir(INPUT_DIR) if f.endswith(".json"))
    print(f"Expanding {len(team_files)} teams")

    for fname in team_files:
        input_path = os.path.join(INPUT_DIR, fname)
        with open(input_path) as f:
            team_data = json.load(f)

        abbr = team_data.get("abbreviation", fname.replace(".json", ""))

        # Step 1: Expand roster in 2025/ format (raw stats)
        expanded = expand_team_players(team_data, abbr)

        # Save expanded to 2025/
        with open(input_path, "w") as f:
            json.dump(expanded, f, indent=2)

        # Step 2: Generate 5E cards
        upgraded = upgrade_to_5e(expanded)

        output_5e_path = os.path.join(OUTPUT_5E_DIR, fname)
        with open(output_5e_path, "w") as f:
            json.dump(upgraded, f, indent=2)

        # Count positions
        positions = {}
        for p in upgraded["players"]:
            pos = p["position"]
            if pos in ("DE", "DT", "NT"): pos = "DL"
            elif pos in ("CB", "S", "SS", "FS"): pos = "DB"
            elif pos in ("LT", "LG", "C", "RG", "RT"): pos = "OL"
            positions[pos] = positions.get(pos, 0) + 1

        total_45 = sum(v for k, v in positions.items() if k not in ("K", "P"))
        print(f"  {abbr}: {len(upgraded['players'])} total ({total_45} rated) — {positions}")

    print("Done!")


if __name__ == "__main__":
    main()
