"""Player card data model for Statis Pro Football.

Authentic card structure (matches original Avalon Hill / SI game):

  * **QB cards** have three sections:
    - *Passing*: Range-based columns for Quick, Short, and Long passes.
      Each column specifies a completion range (Com: 1-X), incomplete range
      (Inc: X+1-Y), and interception range (Int: Y+1-48) within Pass
      Numbers 1-48.
    - *Pass Rush*: Range-based column (Sack: 1-A, Runs: A+1-30,
      Com: 31-B, Inc: B+1-48) within PNs 1-48.
    - *Rushing*: 12 rows (Run Numbers 1-12), each with three values
      N/SG/LG (Normal yards / Short-Gain cutoff / Long-Gain cutoff).

  * **RB / WR / TE cards** share the **same layout**:
    - *Rushing*: 12 rows (Run Numbers 1-12), each with N/SG/LG yards.
      WRs usually have blank rushing columns; RBs have strong values.
    - *Pass Gain*: 12 rows (Run Numbers 1-12), each with Q/S/L yards
      (Quick / Short / Long pass types).  RBs with high pass-endurance
      numbers (3-4) have weaker pass columns; WRs are strong.
    - *Blocks*: A single blocking-value modifier (plus or minus).
    - *Endurance*: A number (0-4) controlling consecutive-play limits.

  * K, P, and DEF cards are unchanged from earlier implementations.

Legacy 64-slot (11-88) columns are preserved for backward compatibility.
"""
from dataclasses import dataclass, field
from typing import Dict, Optional, Any, List
from enum import Enum


class Position(str, Enum):
    QB = "QB"
    RB = "RB"
    WR = "WR"
    TE = "TE"
    K = "K"
    P = "P"
    DEF = "DEF"
    OL = "OL"
    DL = "DL"
    LB = "LB"
    CB = "CB"
    S = "S"


class Grade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


# Pass numbers run 1-48 on FAC cards
PASS_NUMBER_MAX = 48

# Run numbers run 1-12 on FAC cards
RUN_NUMBER_MAX = 12
RUN_SLOTS = [str(n) for n in range(1, RUN_NUMBER_MAX + 1)]
RUN_SLOT_COUNT = 12

# Legacy constants kept for backward compatibility
PASS_SLOTS = [str(n) for n in range(1, 49)]
PASS_SLOT_COUNT = 48
ALL_SLOTS = [f"{t}{o}" for t in range(1, 9) for o in range(1, 9)]
LEGACY_SLOT_COUNT = 64

# Receiver letters used on QB cards
RECEIVER_LETTERS = ["A", "B", "C", "D", "E"]

ResultDict = Dict[str, Any]
CardColumn = Dict[str, ResultDict]


# ── Range-based QB passing column ────────────────────────────────────

@dataclass
class PassRanges:
    """Range boundaries for a single QB pass column (Quick, Short, or Long).

    The Pass Number (1-48) falls into one of:
      Complete  if 1 <= PN <= com_max
      Incomplete if com_max < PN <= inc_max
      Intercepted if inc_max < PN <= 48

    The PN drawn from the FAC card never changes.  Coverage and defensive
    play modifiers shift the completion boundary (com_max) only — the INT
    threshold (inc_max) is a fixed property of the QB card.
    """
    com_max: int = 30     # PNs 1 through com_max → complete
    inc_max: int = 47     # PNs com_max+1 through inc_max → incomplete
    # PNs inc_max+1 through 48 → interception (may be empty if inc_max == 48)

    def resolve(self, pn: int, completion_modifier: int = 0) -> str:
        """Return 'COM', 'INC', or 'INT' for the given pass number.

        completion_modifier shifts the completion boundary only.
        Positive = wider COM range (easier to complete).
        Negative = narrower COM range (harder to complete).
        The INT threshold (inc_max) is never affected.
        """
        effective_com_max = self.com_max + completion_modifier
        if pn <= effective_com_max:
            return "COM"
        if pn <= self.inc_max:
            return "INC"
        return "INT"

    def to_dict(self) -> dict:
        return {"com_max": self.com_max, "inc_max": self.inc_max}

    @classmethod
    def from_dict(cls, data) -> "PassRanges":
        if isinstance(data, dict):
            return cls(
                com_max=data.get("com_max", 30),
                inc_max=data.get("inc_max", 47),
            )
        return cls()


@dataclass
class PassRushRanges:
    """Range boundaries for QB pass-rush resolution.

    On a Pass Rush result, the PN (1-48) maps to:
      Sack       if 1 <= PN <= sack_max
      QB Runs    if sack_max < PN <= runs_max
      Complete   if runs_max < PN <= com_max
      Incomplete if com_max < PN <= 48
    """
    sack_max: int = 12
    runs_max: int = 30
    com_max: int = 40  # PNs runs_max+1 through com_max → completion
    # PNs com_max+1 through 48 → incomplete

    def resolve(self, pn: int) -> str:
        """Return 'SACK', 'RUNS', 'COM', or 'INC'."""
        if pn <= self.sack_max:
            return "SACK"
        if pn <= self.runs_max:
            return "RUNS"
        if pn <= self.com_max:
            return "COM"
        return "INC"

    def to_dict(self) -> dict:
        return {
            "sack_max": self.sack_max,
            "runs_max": self.runs_max,
            "com_max": self.com_max,
        }

    @classmethod
    def from_dict(cls, data) -> "PassRushRanges":
        if isinstance(data, dict):
            return cls(
                sack_max=data.get("sack_max", 12),
                runs_max=data.get("runs_max", 30),
                com_max=data.get("com_max", 40),
            )
        return cls()


# ── 12-row table entry (N/SG/LG or Q/S/L) ───────────────────────────

@dataclass
class ThreeValueRow:
    """One row of a 12-row card table with three values.

    For Rushing columns the three values are:
      n  = Normal yards (base run result)
      sg = Short-Gain cutoff (yards gained on SG result)
      lg = Long-Gain cutoff (yards gained on LG result)

    For Pass Gain columns the three values are:
      q = Quick pass yards gained
      s = Short pass yards gained
      l = Long pass yards gained

    Row 1 may use special markers: "Sg" (short gain — draw a new FAC,
    use SG column) or "Lg" (long gain / big play).
    """
    v1: Any = 0  # N or Q
    v2: Any = 0  # SG or S
    v3: Any = 0  # LG or L

    def to_list(self) -> list:
        return [self.v1, self.v2, self.v3]

    @classmethod
    def from_list(cls, data) -> "ThreeValueRow":
        if isinstance(data, (list, tuple)) and len(data) >= 3:
            return cls(v1=data[0], v2=data[1], v3=data[2])
        if isinstance(data, (list, tuple)) and len(data) == 2:
            return cls(v1=data[0], v2=data[1], v3=data[1])
        if isinstance(data, (list, tuple)) and len(data) == 1:
            return cls(v1=data[0], v2=data[0], v3=data[0])
        if isinstance(data, (int, float, str)):
            return cls(v1=data, v2=data, v3=data)
        return cls()


@dataclass
class PlayerCard:
    player_name: str
    team: str
    position: str
    number: int
    overall_grade: str = "C"

    # Receiver letter (A-E) — links receivers to QB card completions
    receiver_letter: str = ""

    # ── QB Passing (range-based, authentic format) ────────────────────
    passing_quick: Optional[PassRanges] = None
    passing_short: Optional[PassRanges] = None
    passing_long: Optional[PassRanges] = None
    pass_rush: Optional[PassRushRanges] = None
    long_pass_com_adj: int = 0  # Long-pass completion adjustment

    # ── QB Endurance ──────────────────────────────────────────────────
    qb_endurance: str = "C"  # "A", "B", or "C"

    # ── Rushing: 12 rows, each with N/SG/LG (shared by QB/RB/WR/TE) ─
    rushing: List[Optional[ThreeValueRow]] = field(default_factory=list)
    endurance_rushing: int = 3  # Consecutive-play endurance for rushing

    # ── Pass Gain: 12 rows, each with Q/S/L (shared by RB/WR/TE) ────
    pass_gain: List[Optional[ThreeValueRow]] = field(default_factory=list)
    endurance_pass: int = 0  # Endurance number for pass (0=unlimited)

    # ── Blocks (RB/WR/TE) ────────────────────────────────────────────
    blocks: int = 0  # Blocking value (positive = good, negative = bad)

    # ── Kicker ────────────────────────────────────────────────────────
    fg_chart: Dict[str, float] = field(default_factory=dict)
    xp_rate: float = 0.95

    # ── Punter ────────────────────────────────────────────────────────
    avg_distance: float = 44.0
    inside_20_rate: float = 0.35
    blocked_punt_number: int = 0  # RN that triggers a blocked punt (0 = none)
    punt_return_pct: float = 0.60  # Fraction of punts returned vs fair catch

    # ── Kicker (extended) ────────────────────────────────────────────
    longest_kick: int = 50  # Kicker's longest made FG (for over-51 table)

    # ── Offensive Line ────────────────────────────────────────────────
    run_block_rating: int = 0   # OL run-blocking grade (0-99)
    pass_block_rating: int = 0  # OL pass-blocking grade (0-99)

    # ── Defense ───────────────────────────────────────────────────────
    # Legacy generic ratings (kept for backward compat; use 5E fields below)
    pass_rush_rating: int = 0
    coverage_rating: int = 0
    run_stop_rating: int = 0
    # Authentic 5E defensive ratings (position-specific):
    #   DL:  tackle_rating, pass_rush_rating
    #   LB:  pass_defense_rating, tackle_rating, pass_rush_rating, intercept_range
    #   DB:  pass_defense_rating, pass_rush_rating, intercept_range (no tackle)
    tackle_rating: int = 0
    pass_defense_rating: int = 0
    intercept_range: int = 0  # 0 = no intercept ability
    defender_letter: str = ""  # A-M defensive player letter for FAC matchups

    stats_summary: Dict[str, Any] = field(default_factory=dict)

    # ── Legacy columns (backward compatibility with old data) ────────
    short_pass: CardColumn = field(default_factory=dict)
    long_pass: CardColumn = field(default_factory=dict)
    quick_pass: CardColumn = field(default_factory=dict)
    screen_pass: CardColumn = field(default_factory=dict)
    qb_rush: CardColumn = field(default_factory=dict)
    inside_run: CardColumn = field(default_factory=dict)
    outside_run: CardColumn = field(default_factory=dict)
    sweep: CardColumn = field(default_factory=dict)
    short_reception: CardColumn = field(default_factory=dict)
    long_reception: CardColumn = field(default_factory=dict)
    punt_column: CardColumn = field(default_factory=dict)

    # ── Helpers ───────────────────────────────────────────────────────

    def has_rushing(self) -> bool:
        """True if this card has any rushing rows with values."""
        return bool(self.rushing) and any(
            r is not None and r.v1 != 0 for r in self.rushing
        )

    def has_pass_gain(self) -> bool:
        """True if this card has any pass-gain rows with values."""
        return bool(self.pass_gain) and any(
            r is not None and r.v1 != 0 for r in self.pass_gain
        )

    def get_rushing_row(self, run_number: int) -> ThreeValueRow:
        """Get rushing N/SG/LG values for a run number (1-12)."""
        idx = max(0, min(run_number - 1, len(self.rushing) - 1))
        if idx < len(self.rushing) and self.rushing[idx] is not None:
            return self.rushing[idx]
        return ThreeValueRow()

    def get_pass_gain_row(self, run_number: int) -> ThreeValueRow:
        """Get pass-gain Q/S/L values for a run number (1-12)."""
        idx = max(0, min(run_number - 1, len(self.pass_gain) - 1))
        if idx < len(self.pass_gain) and self.pass_gain[idx] is not None:
            return self.pass_gain[idx]
        return ThreeValueRow()

    def resolve_passing(self, pass_type: str, pn: int, completion_modifier: int = 0) -> str:
        """Resolve a pass number against this QB's passing ranges.

        The PN is the raw FAC card value and is never modified.
        completion_modifier shifts the completion boundary (com_max) only;
        positive = easier to complete, negative = harder.

        Returns 'COM', 'INC', or 'INT'.
        """
        if pass_type == "QUICK" and self.passing_quick:
            return self.passing_quick.resolve(pn, completion_modifier)
        if pass_type == "SHORT" and self.passing_short:
            return self.passing_short.resolve(pn, completion_modifier)
        if pass_type == "LONG" and self.passing_long:
            return self.passing_long.resolve(pn, completion_modifier)
        # Fallback to short
        if self.passing_short:
            return self.passing_short.resolve(pn, completion_modifier)
        return "INC"

    def to_dict(self) -> dict:
        return {
            "name": self.player_name,
            "position": self.position,
            "number": self.number,
            "team": self.team,
            "overall_grade": self.overall_grade,
            "receiver_letter": self.receiver_letter,
            # QB passing (range-based)
            "passing_quick": self.passing_quick.to_dict() if self.passing_quick else None,
            "passing_short": self.passing_short.to_dict() if self.passing_short else None,
            "passing_long": self.passing_long.to_dict() if self.passing_long else None,
            "pass_rush": self.pass_rush.to_dict() if self.pass_rush else None,
            "long_pass_com_adj": self.long_pass_com_adj,
            "qb_endurance": self.qb_endurance,
            # Rushing (12-row N/SG/LG)
            "rushing": [r.to_list() if r else None for r in self.rushing],
            "endurance_rushing": self.endurance_rushing,
            # Pass gain (12-row Q/S/L)
            "pass_gain": [r.to_list() if r else None for r in self.pass_gain],
            "endurance_pass": self.endurance_pass,
            "blocks": self.blocks,
            # Kicker / Punter
            "fg_chart": self.fg_chart,
            "xp_rate": self.xp_rate,
            "avg_distance": self.avg_distance,
            "inside_20_rate": self.inside_20_rate,
            "blocked_punt_number": self.blocked_punt_number,
            "punt_return_pct": self.punt_return_pct,
            "longest_kick": self.longest_kick,
            # Offensive Line
            "run_block_rating": self.run_block_rating,
            "pass_block_rating": self.pass_block_rating,
            # Defense
            "pass_rush_rating": self.pass_rush_rating,
            "tackle_rating": self.tackle_rating,
            "pass_defense_rating": self.pass_defense_rating,
            "intercept_range": self.intercept_range,
            "defender_letter": self.defender_letter,
            "stats_summary": self.stats_summary,
            # Legacy columns
            "short_pass": self.short_pass,
            "long_pass": self.long_pass,
            "quick_pass": self.quick_pass,
            "screen_pass": self.screen_pass,
            "qb_rush": self.qb_rush,
            "inside_run": self.inside_run,
            "outside_run": self.outside_run,
            "sweep": self.sweep,
            "short_reception": self.short_reception,
            "long_reception": self.long_reception,
            "punt_column": self.punt_column,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlayerCard":
        card = cls(
            player_name=data.get("name", "Unknown"),
            team=data.get("team", ""),
            position=data.get("position", ""),
            number=data.get("number", 0),
            overall_grade=data.get("overall_grade", "C"),
        )
        card.receiver_letter = data.get("receiver_letter", "")

        # QB passing (range-based)
        pq = data.get("passing_quick")
        card.passing_quick = PassRanges.from_dict(pq) if pq else None
        ps = data.get("passing_short")
        card.passing_short = PassRanges.from_dict(ps) if ps else None
        pl = data.get("passing_long")
        card.passing_long = PassRanges.from_dict(pl) if pl else None
        pr = data.get("pass_rush")
        card.pass_rush = PassRushRanges.from_dict(pr) if pr else None
        card.long_pass_com_adj = data.get("long_pass_com_adj", 0)
        card.qb_endurance = data.get("qb_endurance", "C")

        # Rushing (12-row)
        rushing_data = data.get("rushing", [])
        card.rushing = [
            ThreeValueRow.from_list(r) if r is not None else None
            for r in rushing_data
        ]
        card.endurance_rushing = data.get("endurance_rushing", 3)

        # Pass gain (12-row)
        pg_data = data.get("pass_gain", [])
        card.pass_gain = [
            ThreeValueRow.from_list(r) if r is not None else None
            for r in pg_data
        ]
        card.endurance_pass = data.get("endurance_pass", 0)
        card.blocks = data.get("blocks", 0)

        # Kicker / Punter
        card.fg_chart = data.get("fg_chart", {})
        card.xp_rate = data.get("xp_rate", 0.95)
        card.avg_distance = data.get("avg_distance", 44.0)
        card.inside_20_rate = data.get("inside_20_rate", 0.35)
        card.blocked_punt_number = data.get("blocked_punt_number", 0)
        card.punt_return_pct = data.get("punt_return_pct", 0.60)
        card.longest_kick = data.get("longest_kick", 50)

        # Offensive Line
        card.run_block_rating = data.get("run_block_rating", 0)
        card.pass_block_rating = data.get("pass_block_rating", 0)

        # Defense
        card.pass_rush_rating = data.get("pass_rush_rating", 0)
        card.coverage_rating = data.get("coverage_rating", 0)
        card.run_stop_rating = data.get("run_stop_rating", 0)
        card.tackle_rating = data.get("tackle_rating", 0)
        card.pass_defense_rating = data.get("pass_defense_rating", 0)
        card.intercept_range = data.get("intercept_range", 0)
        card.defender_letter = data.get("defender_letter", "")

        card.stats_summary = data.get("stats_summary", {})

        # Legacy columns
        card.short_pass = data.get("short_pass", {})
        card.long_pass = data.get("long_pass", {})
        card.quick_pass = data.get("quick_pass", {})
        card.screen_pass = data.get("screen_pass", {})
        card.qb_rush = data.get("qb_rush", {})
        card.inside_run = data.get("inside_run", {})
        card.outside_run = data.get("outside_run", {})
        card.sweep = data.get("sweep", {})
        card.short_reception = data.get("short_reception", {})
        card.long_reception = data.get("long_reception", {})
        card.punt_column = data.get("punt_column", {})

        return card
