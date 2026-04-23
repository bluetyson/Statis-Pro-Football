"""Play resolution engine for Statis Pro Football (5th Edition).

Implements the FAC-card-driven resolution system:

  Pass plays (5th edition):
    1. Draw FAC card
    2. Check QK/SH/LG receiver target field — "P.Rush" triggers sack check
       (ER field is for run plays only, NOT pass plays)
    3. PN → QB card → receiver letter / INC / INT
    4. If receiver letter → same PN → Receiver card → yards
    5. Screen uses FAC card SC field directly

  Run plays (5th edition):
    1. Draw FAC card
    2. RUN# → RB card → yards / FUMBLE / BREAKAWAY
    3. FAC blocking matchup fields determine context
    4. OB suffix on RUN# means out-of-bounds

  Penalties (5th edition):
    Triggered via Z cards in the FAC deck.  When a Z card fires,
    the Z-result field encodes penalty info as ``"Pen: 1.D2 /2.O7 /3.R11 /4.K9"``.
    Category is selected by play type; the team letter (O/D/K/R) and
    penalty number (1-15) index into the 5E Penalty Table.

  Out-of-Position:
    OL playing wrong position: −1 blocking/pass-blocking value.
    DB playing wrong position: −1 pass defense value.
    DL/LB may play any Row 1 position without modification.
    All DBs may play Box L without modification.

Defence ratings (pass_rush, coverage, run_stop) are wired into
resolution via effective_* helpers from ``fac_distributions``.
"""
import random
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from .player_card import PlayerCard, RECEIVER_LETTERS
from .fac_deck import FACCard, FACDeck
from .charts import Charts
from .fac_distributions import (
    effective_pass_rush, effective_run_stop,
)


@dataclass
class PlayResult:
    """Result of a resolved play."""
    play_type: str
    yards_gained: int
    result: str  # GAIN, INCOMPLETE, INT, FUMBLE, SACK, TD, OOB, etc.
    is_touchdown: bool = False
    is_first_down: bool = False
    turnover: bool = False
    turnover_type: Optional[str] = None
    penalty: Optional[Dict[str, Any]] = None
    description: str = ""
    out_of_bounds: bool = False
    z_card_event: Optional[Dict[str, Any]] = None

    passer: Optional[str] = None
    rusher: Optional[str] = None
    receiver: Optional[str] = None
    run_number_used: Optional[int] = None
    pass_number_used: Optional[int] = None
    defense_formation: Optional[str] = None
    strategy: Optional[str] = None  # Offensive strategy used (FLOP, SNEAK, DRAW, PLAY_ACTION)
    injury_player: Optional[str] = None  # Player injured this play
    injury_duration: Optional[int] = None  # Injury duration in plays
    offensive_play_call: Optional[str] = None   # Display string for offensive call
    defensive_play_call: Optional[str] = None   # Display string for defensive call
    defensive_play: Optional[str] = None        # DefensivePlay value used
    bv_tv_result: Optional[Dict[str, Any]] = None  # BV vs TV battle details
    interception_point: Optional[int] = None    # Yard line where INT occurred
    personnel_note: Optional[str] = None        # Auto-substitution / availability note
    box_assignments: Optional[Dict[str, str]] = None  # Box letter → player name for this play
    debug_log: List[str] = field(default_factory=list)  # Step-by-step resolution log


# ──────────────────────────────────────────────────────────────────────
#  5E Penalty Table  (page 5 of the 5th-edition rules)
# ──────────────────────────────────────────────────────────────────────
#
# Penalty numbers 1-15 from the Z-card "Pen:" field.
# Each entry: type, yards, no_option, is_spot_foul, loss_of_down, auto_first,
#             notes.
#
# "team" is determined by the letter on the Z card (O/D/K/R), not here.
# "no_option" means the penalty MUST be accepted (cannot be declined).
#
# From the rules document (lines 339-355):
#  1. Offside: 5y (Option)
#  2. Movement: 5y (No Option)
#  3. Illegal Procedure: 5y (Option)
#  4. Motion: 5y (Option)
#  5. Personal Foul: 15y (No Option if DEF/K/R, Option if OFF; from spot
#     where play ended if DEF, from scrimmage if OFF)
#  6. Non-Flagrant Facemask: 5y (same conditions as #5)
#  7. Holding: 10y OFF (Option); 5y DEF + auto first down (Option)
#  8. Pass Interference: 15y OFF down counts (Option);
#     First Down at spot if DEF (Option).  Spot = same as POI.
#     If in end zone → 1st and goal at 1.
#  9. Personal Foul: 15y (same as #5)
# 10. Intentional Grounding: 15y, down counts (No Option).
#     Only on incomplete pass, otherwise ignore.
# 11. Clipping: 15y from spot of foul (No Option).
#     Spot via new FAC: odd RN = halfway point of return,
#     even RN = where return ended.
# 12. Roughing Kicker: 15y from scrimmage, auto first (No Option)
# 13. Running into Kicker: 5y, auto first (same as 12 but 5y)
# 14. Delay of Game: 5y (No Option)
# 15. Kickoff Out of Bounds: 5y (No Option). Re-kick + 5y added to return spot.

PENALTY_TABLE_5E: Dict[int, Dict[str, Any]] = {
    1:  {"name": "Offside",              "yards": 5,  "no_option": False, "spot_foul": False, "loss_of_down": False, "auto_first": False},
    2:  {"name": "Movement",             "yards": 5,  "no_option": True,  "spot_foul": False, "loss_of_down": False, "auto_first": False},
    3:  {"name": "Illegal Procedure",    "yards": 5,  "no_option": False, "spot_foul": False, "loss_of_down": False, "auto_first": False},
    4:  {"name": "Motion",               "yards": 5,  "no_option": False, "spot_foul": False, "loss_of_down": False, "auto_first": False},
    5:  {"name": "Personal Foul",        "yards": 15, "no_option": "DEF", "spot_foul": "DEF", "loss_of_down": False, "auto_first": False},
    6:  {"name": "Non-Flagrant Facemask", "yards": 5,  "no_option": "DEF", "spot_foul": "DEF", "loss_of_down": False, "auto_first": False},
    7:  {"name": "Holding",              "yards": 10, "no_option": False, "spot_foul": False, "loss_of_down": False, "auto_first": "DEF",
         "yards_def": 5},
    8:  {"name": "Pass Interference",    "yards": 15, "no_option": False, "spot_foul": "DEF", "loss_of_down": True,  "auto_first": "DEF"},
    9:  {"name": "Personal Foul",        "yards": 15, "no_option": "DEF", "spot_foul": "DEF", "loss_of_down": False, "auto_first": False},
    10: {"name": "Intentional Grounding", "yards": 15, "no_option": True,  "spot_foul": False, "loss_of_down": True,  "auto_first": False,
         "only_incomplete": True},
    11: {"name": "Clipping",             "yards": 15, "no_option": True,  "spot_foul": True,  "loss_of_down": False, "auto_first": False},
    12: {"name": "Roughing Kicker",      "yards": 15, "no_option": True,  "spot_foul": False, "loss_of_down": False, "auto_first": True},
    13: {"name": "Running into Kicker",  "yards": 5,  "no_option": True,  "spot_foul": False, "loss_of_down": False, "auto_first": True},
    14: {"name": "Delay of Game",        "yards": 5,  "no_option": True,  "spot_foul": False, "loss_of_down": False, "auto_first": False},
    15: {"name": "Kickoff Out of Bounds", "yards": 5,  "no_option": True,  "spot_foul": False, "loss_of_down": False, "auto_first": False,
         "rekick": True},
}


def resolve_z_penalty(pen_detail: str, play_type: str) -> Optional[Dict[str, Any]]:
    """Resolve a 5E Z-card penalty from the FAC card's Pen: field.

    Parameters
    ----------
    pen_detail : str
        The raw penalty string from the Z card, e.g.
        ``"1.D2 /2.D2 /3.R1 /4.R11"``
    play_type : str
        The current play type. Used to select the penalty category:
        - Category 1: RUN, SCREEN, QUICK_PASS, FG
        - Category 2: SHORT_PASS, LONG_PASS
        - Category 3: PUNT (and punt returns)
        - Category 4: KICKOFF (kickoff returns)

    Returns
    -------
    dict or None
        Penalty info dict with keys: type, name, yards, team (O/D/K/R),
        no_option, spot_foul, loss_of_down, auto_first, penalty_number.
        Returns None if the penalty string cannot be parsed.
    """
    # Determine category from play type
    play_upper = play_type.upper()
    if play_upper in ("RUN", "SCREEN", "QUICK_PASS", "FG"):
        category = 1
    elif play_upper in ("SHORT_PASS", "LONG_PASS", "PASS"):
        category = 2
    elif play_upper == "PUNT":
        category = 3
    elif play_upper == "KICKOFF":
        category = 4
    else:
        # Default: treat as category 1
        category = 1

    # Parse "1.D2 /2.D2 /3.R1 /4.R11" into {1: "D2", 2: "D2", 3: "R1", 4: "R11"}
    parts = pen_detail.split("/")
    pen_entries: Dict[int, str] = {}
    for part in parts:
        part = part.strip()
        if "." not in part:
            continue
        cat_str, code = part.split(".", 1)
        try:
            cat_num = int(cat_str)
        except ValueError:
            continue
        pen_entries[cat_num] = code.strip()

    if category not in pen_entries:
        return None

    code = pen_entries[category]
    if len(code) < 2:
        return None

    # Parse team letter and penalty number
    team_letter = code[0].upper()  # O, D, K, R
    try:
        penalty_number = int(code[1:])
    except ValueError:
        return None

    if penalty_number not in PENALTY_TABLE_5E:
        return None

    pen_info = PENALTY_TABLE_5E[penalty_number]

    # Map team letter to descriptive team
    team_map = {"O": "offense", "D": "defense", "K": "kicking", "R": "receiving"}
    team = team_map.get(team_letter, "offense")

    # Determine if this is an "against defense" penalty for conditional fields
    is_against_defense = team in ("defense", "receiving")

    # Resolve conditional fields
    no_option = pen_info["no_option"]
    if no_option == "DEF":
        no_option = is_against_defense

    spot_foul = pen_info["spot_foul"]
    if spot_foul == "DEF":
        spot_foul = is_against_defense

    auto_first = pen_info["auto_first"]
    if auto_first == "DEF":
        auto_first = is_against_defense

    # Holding: 10y vs offense, 5y + auto first vs defense
    yards = pen_info["yards"]
    if pen_info.get("yards_def") and is_against_defense:
        yards = pen_info["yards_def"]

    return {
        "type": pen_info["name"].upper().replace(" ", "_"),
        "name": pen_info["name"],
        "yards": yards,
        "team": team,
        "team_letter": team_letter,
        "no_option": no_option,
        "spot_foul": spot_foul,
        "loss_of_down": pen_info["loss_of_down"],
        "auto_first": auto_first,
        "penalty_number": penalty_number,
        "only_incomplete": pen_info.get("only_incomplete", False),
        "rekick": pen_info.get("rekick", False),
    }


class BigPlayDefense:
    """Big Play Defense card per 5E rules (Rule 14).

    Eligible teams (9+ wins) may use this card once per defensive series.
    """

    def __init__(self):
        self._used_this_series: bool = False

    @staticmethod
    def is_eligible(team_wins: int) -> bool:
        """Return True if the team qualifies for big play defense (9+ wins)."""
        return team_wins >= 9

    @staticmethod
    def get_rating(team_wins: int, is_home: bool) -> int:
        """Return the big play defense rating based on wins and home/road.

        Higher wins yield a higher rating; home teams get a small bonus.
        """
        base = max(0, team_wins - 8)  # 1 per win above 8
        return base + (1 if is_home else 0)

    @staticmethod
    def resolve_vs_rush(run_number: int) -> Optional[int]:
        """Resolve big play defense vs a rush.

        Returns yards (negative = loss), or None if the card fails.
        RN 1=-4y, 2=-3y, 3=-2y, 4=-1y, 5-7=no gain, 8-12=card fails.
        """
        rn = max(1, min(12, run_number))
        if rn == 1:
            return -4
        if rn == 2:
            return -3
        if rn == 3:
            return -2
        if rn == 4:
            return -1
        if 5 <= rn <= 7:
            return 0
        return None  # 8-12: card fails

    @staticmethod
    def resolve_vs_pass(run_number: int) -> Optional[Dict[str, Any]]:
        """Resolve big play defense vs a pass.

        Returns dict with result info, or None if the card fails.
        RN 1-3=sack -7y, 4-7=incomplete, 8-12=card fails.
        """
        rn = max(1, min(12, run_number))
        if 1 <= rn <= 3:
            return {"result": "SACK", "yards": -7}
        if 4 <= rn <= 7:
            return {"result": "INCOMPLETE", "yards": 0}
        return None  # 8-12: card fails

    def use(self) -> bool:
        """Attempt to use the big play card. Returns False if already used this series."""
        if self._used_this_series:
            return False
        self._used_this_series = True
        return True

    def reset_series(self) -> None:
        """Reset for a new defensive series."""
        self._used_this_series = False

    @property
    def used_this_series(self) -> bool:
        """Whether the big play card has been used this series."""
        return self._used_this_series


class PlayResolver:
    """Resolves plays by consulting player cards with FAC distributions."""

    RETURN_BASE_YPC = 4.0
    RETURN_BASE_REC_YARDS = 10.0
    PUNT_RETURN_YPC_WEIGHT = 1.0
    KICK_RETURN_YPC_WEIGHT = 1.5
    PUNT_RETURN_REC_DIVISOR = 5.0
    KICK_RETURN_REC_DIVISOR = 6.0

    # Yard-line threshold for "within 20 of the defense's goal"
    # on the 0–100 scale (0 = own goal, 100 = opponent's goal).
    WITHIN_20_YARD_LINE = 80

    def __init__(self):
        self.charts = Charts()
        # Track endurance: {player_name: consecutive_plays_directed}
        self._endurance_tracker: Dict[str, int] = {}
        # Track injuries: {player_name: plays_remaining}
        self._injury_tracker: Dict[str, int] = {}
        # Track end-around usage: {player_name: bool}
        self._end_around_used: Dict[str, bool] = {}
        # Track fake FG / fake punt usage (once per game)
        self._fake_fg_used: bool = False
        self._fake_punt_used: bool = False

    # ── Endurance tracking ───────────────────────────────────────────

    def track_endurance(self, player_name: str) -> None:
        """Record that a play was directed at this player."""
        self._endurance_tracker[player_name] = (
            self._endurance_tracker.get(player_name, 0) + 1
        )

    def reset_endurance(self, player_name: str) -> None:
        """Reset consecutive-play count (play was NOT directed at player)."""
        self._endurance_tracker[player_name] = 0

    def check_endurance_violation(self, player: PlayerCard) -> Optional[str]:
        """Check if directing a play at this player violates endurance rules.

        5E Endurance Rules:
          0 = unlimited (workhorse)
          1 = cannot be directed on consecutive plays
          2 = two preceding plays must not be directed at him
          3 = once per current possession
          4 = once per quarter

        Returns description of penalty if violated, None if OK.
        """
        endurance = getattr(player, 'endurance_rushing', None)
        if endurance is None or endurance == 0:
            return None
        consecutive = self._endurance_tracker.get(player.player_name, 0)
        if endurance == 1 and consecutive >= 1:
            return "endurance_1"
        if endurance == 2 and consecutive >= 2:
            return "endurance_2"
        if endurance >= 3 and consecutive >= 1:
            return f"endurance_{endurance}"
        return None

    def apply_endurance_penalty(self, player: PlayerCard, play_type: str,
                                run_number: int = 0,
                                completion_range: int = 0) -> tuple:
        """Apply endurance violation penalty.

        Run: +2 to Run Number
        Pass: -5 to completion range

        Returns (modified_run_number, modified_completion_adj).
        """
        violation = self.check_endurance_violation(player)
        if violation is None:
            return run_number, completion_range
        if play_type == "RUN":
            return run_number + 2, completion_range
        return run_number, completion_range - 5

    # ── Injury tracking ──────────────────────────────────────────────

    def resolve_injury_duration(self, pn: int) -> int:
        """Determine injury duration from Pass Number per 5E Injury Table.

        PN 1-10  → 2 plays
        PN 11-20 → 4 plays
        PN 21-30 → 6 plays
        PN 31-35 → rest of quarter (~15 plays)
        PN 36-43 → rest of game (~60 plays)
        PN 44-48 → rest of game + more (~99 plays)
        """
        if pn <= 10:
            return 2
        elif pn <= 20:
            return 4
        elif pn <= 30:
            return 6
        elif pn <= 35:
            return 15  # rest of quarter approximation
        elif pn <= 43:
            return 60  # rest of game
        else:
            return 99  # rest of game + more

    def injure_player(self, player_name: str, duration: int) -> None:
        """Record an injury for a player."""
        self._injury_tracker[player_name] = duration

    def tick_injuries(self) -> None:
        """Decrement injury counters by 1 play."""
        to_remove = []
        for name in self._injury_tracker:
            self._injury_tracker[name] -= 1
            if self._injury_tracker[name] <= 0:
                to_remove.append(name)
        for name in to_remove:
            del self._injury_tracker[name]

    def is_injured(self, player_name: str) -> bool:
        """Check if a player is currently injured."""
        return self._injury_tracker.get(player_name, 0) > 0

    # ── Play restriction checks ──────────────────────────────────────

    @staticmethod
    def check_long_pass_restriction(yard_line: int) -> bool:
        """No long pass when scrimmage is within opponent's 20 (yard_line >= 80).

        Returns True if long pass is BLOCKED.
        """
        return yard_line >= 80

    @staticmethod
    def check_screen_pass_restriction(yard_line: int) -> bool:
        """No screen pass within 5-yard line (yard_line >= 95).

        Returns True if screen pass is BLOCKED.
        """
        return yard_line >= 95

    @staticmethod
    def apply_inside_run_max_loss(yards: int, play_direction: str) -> int:
        """Inside runs have a maximum loss of 3 yards per 5E rules.

        Sweeps have no loss limit.
        """
        if play_direction in ("IL", "IR", "INSIDE", "MIDDLE", "LEFT"):
            return max(yards, -3)
        return yards  # Sweeps have no limit

    # ── Offensive strategies ─────────────────────────────────────────

    def resolve_flop(self, qb: PlayerCard) -> PlayResult:
        """Resolve a QB Flop (QB Dive) strategy.

        5E Rules: Inside run to QB; automatic -1 yard; no FAC flip, no fumble.
        """
        return PlayResult(
            play_type="RUN", yards_gained=-1, result="GAIN",
            description=f"{qb.player_name} dives for -1 yard (Flop)",
            rusher=qb.player_name, strategy="FLOP",
        )

    def resolve_sneak(
        self,
        qb: PlayerCard,
        deck: FACDeck,
        ol_by_position: Optional[Dict[str, "PlayerCard"]] = None,
        defenders_list_by_box: Optional[Dict[str, List["PlayerCard"]]] = None,
    ) -> PlayResult:
        """Resolve a QB Sneak strategy.

        5E Rules: Inside run to QB; flip FAC.
        Baseline: 24 out of 48 pass numbers succeed (gain 1 yard).

        Interior blocking matchup rule:
          offense_block = LG.run_block_rating + C.run_block_rating
                          + RG.run_block_rating
          defense_tackle = effective_tackle(B) + effective_tackle(C)
                           + effective_tackle(D)
          adjustment = offense_block - defense_tackle
          success_count = clamp(24 + adjustment, 0, 48)
          gain = 1 if PN <= success_count else 0

        Double-box crowding bonus: when two defenders share an interior box
        (B, C, or D) the effective tackle value = sum of their tackle_ratings
        + 1 per additional player (e.g. DT[2] + LB[1] → 2+1+1 = 4).

        When OL or defender data is unavailable the baseline (24 ranges) is used.
        """
        fac_card = deck.draw()
        pn = fac_card.pass_num_int or random.randint(1, 48)

        log: List[str] = []

        # ── Interior blocking matchup ──────────────────────────────────
        lg = (ol_by_position or {}).get("LG")
        cn = (ol_by_position or {}).get("CN")
        rg = (ol_by_position or {}).get("RG")

        lg_val = getattr(lg, "run_block_rating", 0) if lg else 0
        cn_val = getattr(cn, "run_block_rating", 0) if cn else 0
        rg_val = getattr(rg, "run_block_rating", 0) if rg else 0
        offense_block = lg_val + cn_val + rg_val

        lg_name = lg.player_name if lg else "—"
        cn_name = cn.player_name if cn else "—"
        rg_name = rg.player_name if rg else "—"

        def _box_tackle(box_key: str):
            """Return (effective_tackle_value, display_string) for a box."""
            players = (defenders_list_by_box or {}).get(box_key, [])
            if not players:
                return 0, "—"
            base = sum(getattr(p, "tackle_rating", 0) for p in players)
            bonus = len(players) - 1  # +1 crowding bonus per extra player
            total = base + bonus
            label = " & ".join(
                f"{p.player_name}({getattr(p, 'tackle_rating', 0)})"
                for p in players
            )
            if bonus:
                label += f" +{bonus}crowd"
            return total, label

        b_val, b_label = _box_tackle("B")
        c_val, c_label = _box_tackle("C")
        d_val, d_label = _box_tackle("D")

        defense_tackle = b_val + c_val + d_val
        adjustment = offense_block - defense_tackle
        success_count = max(0, min(48, 24 + adjustment))

        log.append(
            f"[Sneak] OL block: LG {lg_name}({lg_val}) + C {cn_name}({cn_val})"
            f" + RG {rg_name}({rg_val}) = {offense_block}"
        )
        log.append(
            f"[Sneak] DL tackle: B {b_label}({b_val}) + C {c_label}({c_val})"
            f" + D {d_label}({d_val}) = {defense_tackle}"
        )
        if adjustment > 0:
            log.append(
                f"[Sneak] Offense +{adjustment} advantage → {success_count}/48 PNs gain 1 yd"
            )
        elif adjustment < 0:
            log.append(
                f"[Sneak] Defense +{-adjustment} advantage → {success_count}/48 PNs gain 1 yd"
            )
        else:
            log.append(f"[Sneak] Even matchup → {success_count}/48 PNs gain 1 yd")
        log.append(f"[Sneak] PN={pn} (success if PN ≤ {success_count})")

        yards = 1 if pn <= success_count else 0
        result = PlayResult(
            play_type="RUN", yards_gained=yards, result="GAIN",
            description=f"{qb.player_name} sneaks for {yards} yard{'s' if yards != 1 else ''} (Sneak)",
            rusher=qb.player_name, strategy="SNEAK",
            pass_number_used=pn,
        )
        result.debug_log = log
        return result

    def resolve_spike(self, qb: PlayerCard) -> PlayResult:
        """Resolve a QB Spike play (intentional grounding to stop the clock).

        5E Rules:
          - Counts as an incomplete pass attempt (QB loses a down, no yards).
          - Clock stops (10 seconds used, same as any incomplete pass).
          - The PREVIOUS play's time is retroactively halved (min 10 seconds);
            callers are responsible for applying the time refund before calling
            _advance_time.
        """
        return PlayResult(
            play_type="PASS",
            yards_gained=0,
            result="INCOMPLETE",
            description=f"{qb.player_name} spikes the ball — clock stopped (Spike)",
            passer=qb.player_name,
            strategy="SPIKE",
        )

    def resolve_draw(self, fac_card: FACCard, deck: FACDeck,
                     rusher: PlayerCard, defense_formation: str,
                     defense_run_stop: int = 0,
                     defensive_play: Optional[str] = None,
                     defenders_by_box: Optional[Dict[str, PlayerCard]] = None,
                     defensive_play_5e=None) -> PlayResult:
        """Resolve a Draw Play strategy.

        5E Rules: Inside run to any back/QB.
        Draw modifier is applied to the Run Number BEFORE the card lookup:
          vs Blitz:          -4 to Run Number (blitzers commit, draw exploits gaps)
          vs Pass Defense:   -2 to Run Number (defense in coverage, not keying run)
          vs Prevent Defense:-2 to Run Number (spread defense, easy to run through)
          vs Run Defense:    +2 to Run Number (defense set to stop the run)

        Negative RN modifier = lower run number = better rushing row = more yards.
        Positive RN modifier = higher run number = worse rushing row = fewer yards.

        Per 5E rules the modifier depends solely on the defensive PLAY CALL
        (Pass Defense, Run Defense, Blitz, etc.).  The formation name (4-3,
        Nickel, etc.) carries no modifier of its own.

        ``defensive_play_5e`` (a DefensivePlay enum) is the authoritative
        source.  ``defensive_play`` (a plain string) is accepted as a
        convenience fallback when the caller has not yet converted to the enum.
        When neither is supplied the draw modifier is 0.
        """
        # Draw play modifier — derive solely from the explicit play call,
        # never from the formation string.
        if defensive_play_5e is not None:
            from .play_types import DefensivePlay
            if defensive_play_5e == DefensivePlay.BLITZ:
                draw_mod = -4  # Bonus: blitzers commit hard, draw freezes them
            elif defensive_play_5e == DefensivePlay.PREVENT_DEFENSE:
                draw_mod = -2  # Bonus: spread/prevent defense is easy to run through
            elif defensive_play_5e == DefensivePlay.PASS_DEFENSE:
                draw_mod = -2  # Bonus: pass coverage, not keying on run
            else:
                # Penalty: covers all RUN_DEFENSE variants (no-key, keyed on back 1/2/3)
                draw_mod = 2
        elif defensive_play is not None:
            # Convenience: accept plain string when enum is not available yet
            dp = defensive_play.upper()
            if dp == "BLITZ":
                draw_mod = -4
            elif dp == "PREVENT_DEFENSE":
                draw_mod = -2
            elif dp == "PASS_DEFENSE":
                draw_mod = -2
            elif dp.startswith("RUN_DEFENSE"):
                draw_mod = 2
            else:
                # Unknown play string — no modifier
                draw_mod = 0
        else:
            # No defensive play call supplied — cannot determine modifier.
            # Per 5E rules, the formation name alone carries no modifier.
            draw_mod = 0

        # Resolve as inside run with draw modifier applied to RN before lookup.
        #
        # ``draw_mod`` is the draw-specific bonus/penalty.  ``defensive_play_5e``
        # is also forwarded to ``resolve_run_5e`` so that the *base* run-defense
        # Run Number modifier is applied on top of it, exactly as the 5E rules
        # state: "These modifiers are IN ADDITION TO normal Run Number modifiers
        # called for on each particular defense."
        #
        # Example — Draw vs Run Defense / No Key:
        #   draw_mod        = +2  (draw penalty: run defense is set to stop it)
        #   base def_rn_mod = +2  (normal Run Defense / No Key modifier)
        #   total RN change = +4  ← correct per 5E rules
        result = self.resolve_run_5e(
            fac_card, deck, rusher, "IL",
            defense_run_stop=defense_run_stop,
            defense_formation=defense_formation,
            extra_rn_modifier=draw_mod,
            defenders_by_box=defenders_by_box,
            defensive_play_5e=defensive_play_5e,
        )
        result.strategy = "DRAW"
        result.description += f" (Draw play, RN modifier {draw_mod:+d})"
        return result

    def resolve_play_action(self, fac_card: FACCard, deck: FACDeck,
                            qb: PlayerCard, receiver: PlayerCard,
                            receivers: list, pass_type: str,
                            defense_formation: str,
                            defense_coverage: int = 0,
                            defense_pass_rush: int = 0,
                            defensive_strategy: str = "NONE",
                            defenders: Optional[List[PlayerCard]] = None,
                            defensive_play_5e=None,
                            yard_line: int = 25) -> PlayResult:
        """Resolve a Play-Action pass strategy.

        5E Rules: Short/Long pass only.
        Play-action modifier is applied to the QB's completion range
        (adjusting the effective Pass Number before the card lookup):
          vs Run Defense:    +5 to completion range (fools run-keyed defense)
          vs Blitz:           0 (neutral)
          vs Pass Defense:   -5 to completion range (defense not fooled)
          vs Prevent Defense:-10 to completion range (deep zone not fooled at all)

        Positive completion modifier = wider COM range = more completions.
        Negative completion modifier = narrower COM range = fewer completions.
        """
        # Play-action modifier to completion range.
        # Per 5E rules, the modifier depends solely on the defensive PLAY CALL
        # (Run Defense, Pass Defense, Blitz, etc.), never on the formation name.
        # When the explicit DefensivePlay enum is available, use it.
        # When only a plain-string play call is available it is already encoded
        # in the DefensivePlay enum via the caller (from `_execute_play_5e`).
        # If neither is available, the modifier is 0.
        pa_mod = 0
        if defensive_play_5e is not None:
            from .play_types import is_run_defense, DefensivePlay
            if defensive_play_5e == DefensivePlay.BLITZ:
                pa_mod = 0  # Blitz: neutral for play-action
            elif is_run_defense(defensive_play_5e):
                pa_mod = 5   # vs Run Defense — fools them
            elif defensive_play_5e == DefensivePlay.PASS_DEFENSE:
                pa_mod = -5  # vs Pass Defense — not fooled
            elif defensive_play_5e == DefensivePlay.PREVENT_DEFENSE:
                pa_mod = -10  # vs Prevent Defense — deep zone, not fooled at all
            # else: unknown enum variant → neutral (0)

        result = self.resolve_pass_5e(
            fac_card, deck, qb, receiver, receivers,
            pass_type=pass_type,
            defense_coverage=defense_coverage,
            defense_pass_rush=defense_pass_rush,
            defense_formation=defense_formation,
            defensive_strategy=defensive_strategy,
            defenders=defenders,
            two_minute_offense=False,
            completion_modifier=pa_mod,
            defensive_play_5e=defensive_play_5e,
            yard_line=yard_line,
        )
        result.strategy = "PLAY_ACTION"
        result.description += f" (Play-action, completion modifier {pa_mod:+d})"
        return result

    # ── BV vs TV blocking battle ─────────────────────────────────────

    @staticmethod
    def resolve_bv_tv_battle(blocker_bv: int, defender_tv: int,
                             empty_box: bool = False,
                             two_defenders: bool = False) -> int:
        """Resolve Blocking Value vs Tackle Value battle per 5E rules.

        Returns yard modifier:
          - Positive = offense wins (add BV)
          - Negative = defense wins (subtract TV)
          - Zero = no modification

        Special cases:
          - Two defenders in box: TV = -4 regardless of printed values
          - Empty defensive box: +2 yards bonus
          - BV vs empty box: Add BV only, no +2 bonus
        """
        if empty_box:
            if blocker_bv != 0:
                return blocker_bv  # Add BV only, no +2
            return 2  # Empty box +2

        effective_tv = -4 if two_defenders else defender_tv
        diff = blocker_bv - effective_tv
        if diff > 0:
            return blocker_bv  # Offense wins: add BV
        elif diff < 0:
            return -effective_tv  # Defense wins: subtract TV
        return 0  # Tied: no modification

    @staticmethod
    def classify_blocking_matchup(matchup: str) -> str:
        """Classify a FAC blocking matchup string into a matchup type.

        Returns one of:
          "BK_VS_BOX"     — "BK vs F" style: blocking back vs. defensive box (contest)
          "OL_VS_BOX"     — "CN vs C" / "LG vs B" style: OL vs. defensive box (contest)
          "SINGLE_DEF_BOX" — "A" / "C" style: single defensive box letter (defense only)
          "TWO_DEF_BOX"   — "A + F" / "B + G" style: two defensive boxes (defense only)
          "TWO_OL"        — "LG + LT" / "CN + LG" style: two offensive players (offense only)
          "OL_ONLY"       — "LG" / "CN" / "BK" / "LT" etc.: single OL (offense only)
          "BREAK"         — breakaway run
          "OTHER"         — unrecognised pattern
        """
        m = matchup.strip()
        if m.upper() == "BREAK":
            return "BREAK"
        if " vs " in m:
            if m.startswith("BK"):
                return "BK_VS_BOX"
            return "OL_VS_BOX"
        if " + " in m:
            parts = [p.strip() for p in m.split(" + ")]
            if len(parts) == 2:
                # Single uppercase letter = defensive box (A-J)
                if all(len(p) == 1 and p.isupper() for p in parts):
                    return "TWO_DEF_BOX"
                return "TWO_OL"
        # Single uppercase letter = defensive box (A-O)
        if len(m) == 1 and m.isupper():
            return "SINGLE_DEF_BOX"
        return "OL_ONLY"

    @staticmethod
    def extract_ol_abbreviations(matchup: str) -> list:
        """Extract 2-letter offensive player abbreviations from a matchup string.

        Returns a list of offensive position abbreviations (e.g. CN, LG, BK).
        Examples:
          "BK"        → ["BK"]
          "LG"        → ["LG"]
          "CN + LG"   → ["CN", "LG"]
          "LG vs B"   → ["LG"]
          "BK vs G"   → ["BK"]
          "A"         → []      (defensive box only)
          "A + F"     → []      (defensive boxes only)
        """
        m = matchup.strip()
        if " vs " in m:
            off_part = m.split(" vs ")[0].strip()
            if len(off_part) >= 2:
                return [off_part]
            return []
        if " + " in m:
            parts = [p.strip() for p in m.split(" + ")]
            if len(parts) == 2:
                # If all parts are single letters, these are defensive boxes
                if all(len(p) == 1 and p.isupper() for p in parts):
                    return []
                return [p for p in parts if len(p) >= 2]
            return []
        # Single 2+ letter abbreviation = offensive player
        if len(m) >= 2:
            return [m]
        return []

    @staticmethod
    def get_player_blocking_value(player: 'PlayerCard') -> int:
        """Get the blocking value for a player in blocking matchups.

        For OL: uses run_block_rating (the small-integer blocking grade).
        For others (RB, TE, WR): uses blocks field.
        """
        rbr = getattr(player, 'run_block_rating', 0) or 0
        if rbr > 0:
            return rbr
        return getattr(player, 'blocks', 0) or 0

    @staticmethod
    def extract_box_letters(matchup: str) -> list:
        """Extract defensive box letter(s) from a FAC blocking matchup string.

        Returns a list of box letters (A-O) found in the matchup.
        Examples:
          "C"         → ["C"]
          "LT vs B"   → ["B"]
          "BK vs G"   → ["G"]
          "A + F"     → ["A", "F"]
          "LG"        → []      (no box letter)
          "CN + LG"   → []      (no box letter)
        """
        m = matchup.strip()
        if " vs " in m:
            # "OL vs X" or "BK vs X" — box is after "vs "
            box = m.split(" vs ")[-1].strip()
            if len(box) == 1 and box.isupper():
                return [box]
            return []
        if " + " in m:
            parts = [p.strip() for p in m.split(" + ")]
            if len(parts) == 2 and all(len(p) == 1 and p.isupper() for p in parts):
                return parts
            return []
        # Single letter = defensive box
        if len(m) == 1 and m.isupper():
            return [m]
        return []

    # ── Onside kick ──────────────────────────────────────────────────

    def resolve_onside_kick(self, deck: FACDeck,
                            onside_defense: bool = False) -> PlayResult:
        """Resolve an onside kick per 5E rules.

        Normal: PN 1-11 = kicking team recovers at 50; 12-48 = receiving at 50
        With onside defense: PN 1-7 kicking / 8-48 receiving
        """
        fac_card = deck.draw()
        pn = fac_card.pass_num_int or random.randint(1, 48)

        threshold = 7 if onside_defense else 11
        kicking_recovers = pn <= threshold

        if kicking_recovers:
            return PlayResult(
                play_type="KICKOFF", yards_gained=50, result="ONSIDE_RECOVERED",
                description=f"Onside kick recovered by kicking team at the 50! (PN {pn})",
                pass_number_used=pn,
            )
        return PlayResult(
            play_type="KICKOFF", yards_gained=50, result="ONSIDE_RECEIVING",
            description=f"Onside kick recovered by receiving team at the 50. (PN {pn})",
            pass_number_used=pn,
        )

    # ── Squib kick ───────────────────────────────────────────────────

    def resolve_squib_kick(self, deck: FACDeck,
                           kickoff_table: Optional[List[str]] = None,
                           kickoff_returners: Optional[List[Dict[str, Any]]] = None,
                           kickoff_return_table: Optional[List[List[Any]]] = None,
                           fumbles_lost_max: int = 21,
                           def_fumble_adj: int = 0,
                           is_home: bool = False) -> PlayResult:
        """Resolve a squib kick per 5E rules.

        Normal kickoff + 15 yards to return start + 1 to return Run Number (12 stays 12).
        """
        if kickoff_table and len(kickoff_table) == 12:
            result = self.resolve_kickoff_5e(
                deck, kickoff_table, kickoff_returners or [],
                kickoff_return_table or [], fumbles_lost_max,
                def_fumble_adj, is_home,
            )
        else:
            # No table data — default to touchback
            result = PlayResult(
                play_type="KICKOFF", yards_gained=0,
                result="TOUCHBACK",
                description="Kickoff - touchback, ball at 20-yard line",
            )
        if result.result == "TOUCHBACK":
            # Squib kicks are less likely to reach end zone
            result.result = "RETURN"
            result.yards_gained = 35  # ~35 yard line
            result.description = "Squib kick returned to the 35"
        else:
            # +15 yards to return start (better field position for returner)
            result.yards_gained = min(99, result.yards_gained + 15)
            result.description = f"Squib kick returned to the {result.yards_gained}"
        return result

    # ── Point of Interception calculation ────────────────────────────

    @staticmethod
    def calculate_point_of_interception(pass_type: str,
                                        run_number: int,
                                        yard_line: int) -> int:
        """Calculate Point of Interception per 5E rules.

        Screen: RN / 2
        Quick:  RN
        Short:  RN × 2
        Long:   RN × 4

        Returns the yard line where interception occurs.
        """
        if pass_type == "SCREEN":
            poi_yards = run_number // 2
        elif pass_type == "QUICK":
            poi_yards = run_number
        elif pass_type == "SHORT":
            poi_yards = run_number * 2
        else:  # LONG
            poi_yards = run_number * 4

        interception_yl = min(100, yard_line + poi_yards)
        # If past goal line, touchback at 20
        if interception_yl >= 100:
            return 20  # Touchback
        return 100 - interception_yl  # Convert to defensive yard line

    # ── Half-distance penalty ────────────────────────────────────────

    @staticmethod
    def apply_half_distance_penalty(penalty_yards: int,
                                    yard_line: int,
                                    is_offense_penalty: bool) -> int:
        """Apply half-distance-to-goal rule for penalties.

        15y penalty inside 20, or 10y penalty inside 10 = half distance.
        """
        if is_offense_penalty:
            # Penalty moves offense back toward own end zone
            if yard_line <= penalty_yards:
                return max(1, yard_line // 2)
        else:
            # Defensive penalty inside own 20
            distance_to_goal = 100 - yard_line
            if distance_to_goal <= penalty_yards:
                return max(1, distance_to_goal // 2)
        return penalty_yards

    # ── Rule 1: Run Number Modifiers ─────────────────────────────────

    @staticmethod
    def get_run_number_modifier(defense_formation: str,
                                is_key_on_bc: bool = False,
                                is_no_key: bool = False) -> int:
        """Return run-number modifier based on defensive PLAY CALL (Rule 1).

        .. deprecated::
            Callers should supply a ``DefensivePlay`` enum and use
            ``get_run_number_modifier_5e`` from ``play_types`` instead.

            Per 5E rules, run-number modifiers come exclusively from the
            defensive PLAY CALL (Pass Defense, Run Defense, Blitz, etc.), not
            from the formation name (4-3, Nickel, etc.).  A formation name
            like "4_3" merely describes the personnel on the field; it carries
            no inherent modifier.  Without an explicit defensive play call the
            modifier is always 0.

        This legacy overload is kept for backward compatibility only.  It
        always returns 0 regardless of the formation string because the
        formation name alone does not determine the play-call modifier.
        """
        return 0

    # ── Rule 2: Pass Rush Detailed Calculation ───────────────────────

    @staticmethod
    def calculate_pass_rush_modifier(defense_pr_sum: int,
                                     offense_pb_sum: int) -> int:
        """Return pass rush modifier: (defense PR sum - offense PB sum) * 2.

        Positive = defense wins, negative = offense wins.
        Applied to QB's sack range.
        """
        return (defense_pr_sum - offense_pb_sum) * 2

    # ── Rule 3: Blitz Pass Rush Value ────────────────────────────────

    @staticmethod
    def get_blitz_pass_rush_value() -> int:
        """Blitzing players have a pass rush value of 2 regardless of printed value."""
        return 2

    # ── Rule 9: Empty Box Completion Modifier ────────────────────────

    @staticmethod
    def get_empty_box_completion_modifier(defender_assigned: bool) -> int:
        """Return +5 to completion range when the guarding defensive box is empty."""
        return 0 if defender_assigned else 5

    # ── Rule 12: Double Coverage ─────────────────────────────────────

    @staticmethod
    def resolve_double_coverage(receiver: PlayerCard,
                                defenders: List[PlayerCard]) -> int:
        """Return completion range modifier for double coverage (Rule 12).

        Only usable with Pass/Prevent defense.
        Requires 4 in Row 2+3, or 3 in Row 2 + 5 in Row 3.
        Returns -7 completion range modifier, or 0 if not applicable.
        """
        if len(defenders) < 2:
            return 0
        # Count defenders by assignment row (approximate via list position)
        row2_count = 0
        row3_count = 0
        for i, d in enumerate(defenders):
            if i == 0:
                continue  # Row 1 is the primary
            if i <= 3:
                row2_count += 1
            else:
                row3_count += 1

        if (row2_count + row3_count >= 4) or (row2_count >= 3 and row3_count >= 5):
            return -7
        return 0

    # ── Rule 13: Triple Coverage ─────────────────────────────────────

    @staticmethod
    def resolve_triple_coverage(receiver: PlayerCard,
                                defenders: List[PlayerCard]) -> int:
        """Return completion range modifier for triple coverage (Rule 13).

        Only usable with Pass/Prevent defense.
        Requires 2 in Row 2 + 6 in Row 3.
        Returns -15 completion range modifier, or 0 if not applicable.
        """
        if len(defenders) < 3:
            return 0
        row2_count = 0
        row3_count = 0
        for i, d in enumerate(defenders):
            if i == 0:
                continue
            if i <= 3:
                row2_count += 1
            else:
                row3_count += 1

        if row2_count >= 2 and row3_count >= 6:
            return -15
        return 0

    # ── Rule 23: FG Distance Calculation ─────────────────────────────

    @staticmethod
    def calculate_fg_distance(yard_line: int) -> int:
        """Calculate field goal distance: (100 - yard_line) + 17."""
        return (100 - yard_line) + 17

    # ── Run resolution (5E) ──────────────────────────────────────────

    # ── Field goal ───────────────────────────────────────────────────

    def resolve_field_goal(self, distance: int, kicker: PlayerCard) -> PlayResult:
        fg_chart = kicker.fg_chart

        if distance < 20:
            rate = fg_chart.get("0-19", 0.99)
        elif distance < 30:
            rate = fg_chart.get("20-29", 0.95)
        elif distance < 40:
            rate = fg_chart.get("30-39", 0.88)
        elif distance < 50:
            rate = fg_chart.get("40-49", 0.78)
        elif distance < 60:
            rate = fg_chart.get("50-59", 0.62)
        else:
            rate = fg_chart.get("60+", 0.35)

        made = random.random() < rate
        return PlayResult(
            play_type="FG",
            yards_gained=0,
            result="FG_GOOD" if made else "FG_NO_GOOD",
            description=f"{kicker.player_name} {'makes' if made else 'misses'} {distance}-yard field goal",
        )

    # ── Punt (5E) ─────────────────────────────────────────────────────
    # Legacy slot-based punt resolution has been removed.
    # 5E punts use resolve_punt_return_5e() via game.py's _execute_punt_5e().

    # ── XP / Kickoff ────────────────────────────────────────────────

    def resolve_xp(self, kicker: PlayerCard) -> PlayResult:
        made = random.random() < kicker.xp_rate
        return PlayResult(
            play_type="XP",
            yards_gained=0,
            result="XP_GOOD" if made else "XP_NO_GOOD",
            description=f"Extra point {'good' if made else 'no good'}!",
        )

    # ── 5E Authentic Kickoff Resolution ────────────────────────────────

    @staticmethod
    def _parse_return_value(val: Any) -> Dict[str, Any]:
        """Parse a kickoff/punt return table value.

        Returns dict with keys:
          yard_line: int  — the final yard line (0 = goal line)
          is_td: bool     — touchdown return
          is_fumble: bool — fumble on the return
          is_breakaway: bool — breakaway marker (*)
        """
        if val == "TD":
            return {"yard_line": 0, "is_td": True, "is_fumble": False, "is_breakaway": False}
        s = str(val)
        is_breakaway = s.startswith("*")
        if is_breakaway:
            s = s[1:]
        is_fumble = s.endswith("f")
        if is_fumble:
            s = s[:-1]
        try:
            yl = int(s)
        except (ValueError, TypeError):
            yl = 20
        return {"yard_line": yl, "is_td": False, "is_fumble": is_fumble,
                "is_breakaway": is_breakaway}

    def resolve_kickoff_5e(
        self,
        deck: FACDeck,
        kickoff_table: List[str],
        kickoff_returners: List[Dict[str, Any]],
        kickoff_return_table: List[List[Any]],
        fumbles_lost_max: int = 21,
        def_fumble_adj: int = 0,
        is_home: bool = False,
    ) -> PlayResult:
        """Resolve a kickoff using authentic 5E team card mechanics.

        Flow:
          1. Draw FAC → RN → look up kicking team's kickoff table
          2. If return: Draw FAC → PN → select which KR from receiving team
          3. Draw FAC → RN → look up KR's return column on receiving team's card
        """
        log: List[str] = []

        # Step 1: Draw FAC for kickoff table lookup
        ko_fac = deck.draw()
        if ko_fac.is_z_card:
            ko_fac = deck.draw_non_z()
        ko_rn = ko_fac.run_num_int or random.randint(1, 12)
        ko_rn = max(1, min(12, ko_rn))

        log.append(f"[KO] FAC Card #{ko_fac.card_number}: RN={ko_rn}")

        # Look up the kickoff table (12 entries, index 0 = RN 1)
        if not kickoff_table or len(kickoff_table) < 12:
            # No table data — default to touchback
            log.append("[KO] No kickoff table data — default touchback")
            r = PlayResult(
                play_type="KICKOFF", yards_gained=0,
                result="TOUCHBACK",
                description="Kickoff - touchback, ball at 20-yard line",
            )
            r.debug_log = log
            return r

        ko_entry = kickoff_table[ko_rn - 1]
        log.append(f"[KO] Kickoff table RN {ko_rn} → {ko_entry}")

        # ── Handle "special" (RN 12 sub-table: draw new RN) ──────────
        if ko_entry.lower() == "special":
            sub_fac = deck.draw()
            if sub_fac.is_z_card:
                sub_fac = deck.draw_non_z()
            sub_rn = sub_fac.run_num_int or random.randint(1, 12)
            sub_rn = max(1, min(12, sub_rn))
            log.append(f"[KO] Special (RN 12): drew new RN={sub_rn}")

            if sub_rn <= 4:
                # Return starts at goal line
                ko_entry = "GL"
                log.append(f"[KO] Sub-RN {sub_rn} (1-4) → return starts at goal line")
            elif sub_rn <= 9:
                # Use the sub-RN itself as the starting yard line
                ko_entry = str(sub_rn)
                log.append(f"[KO] Sub-RN {sub_rn} (5-9) → return starts at {sub_rn}-yard line")
            else:
                # 10-12: Kick goes out of bounds
                ko_entry = "OB"
                log.append(f"[KO] Sub-RN {sub_rn} (10-12) → kick out of bounds")

        # ── Touchback results ────────────────────────────────────────
        ko_upper = ko_entry.upper()
        if ko_upper.startswith("TB"):
            yard_line = 20
            modifier_str = ""
            if "(" in ko_entry and ")" in ko_entry:
                inner = ko_entry[ko_entry.index("(") + 1:ko_entry.index(")")]
                try:
                    tb_adj = int(inner)
                    yard_line = max(1, 20 + tb_adj)
                    modifier_str = f" (adj {tb_adj:+d})"
                except ValueError:
                    pass
            log.append(f"[KO] Touchback{modifier_str}, ball at {yard_line}-yard line")
            r = PlayResult(
                play_type="KICKOFF",
                yards_gained=yard_line,
                result="TOUCHBACK",
                description=f"Kickoff — touchback, ball at the {yard_line}-yard line",
            )
            r.debug_log = log
            return r

        # ── Out of bounds ────────────────────────────────────────────
        if ko_upper == "OB":
            log.append("[KO] Kick goes out of bounds — penalty, ball at the 40-yard line")
            r = PlayResult(
                play_type="KICKOFF",
                yards_gained=40,
                result="OOB",
                description="Kickoff out of bounds — ball at the 40-yard line",
            )
            r.debug_log = log
            return r

        # ── Return: determine start yard line ────────────────────────
        if ko_upper == "GL":
            start_yl = 0
        else:
            try:
                start_yl = int(ko_entry)
            except (ValueError, TypeError):
                start_yl = 1
        log.append(f"[KO] Return starts at {start_yl}-yard line")

        # Step 2: Draw FAC → PN to select which KR
        kr_fac = deck.draw()
        if kr_fac.is_z_card:
            kr_fac = deck.draw_non_z()
        kr_pn = kr_fac.pass_num_int or random.randint(1, 48)
        kr_pn = max(1, min(48, kr_pn))

        kr_index = 0
        kr_name = "unknown"
        for i, kr in enumerate(kickoff_returners):
            pn_min = kr.get("pn_min", 1)
            pn_max = kr.get("pn_max", 48)
            if pn_min <= kr_pn <= pn_max:
                kr_index = i
                kr_name = kr.get("name", "unknown")
                break
        log.append(
            f"[KR] FAC Card #{kr_fac.card_number}: PN={kr_pn} → "
            f"KR{kr_index + 1} {kr_name} (range {kickoff_returners[kr_index].get('pn_min', '?')}-"
            f"{kickoff_returners[kr_index].get('pn_max', '?')})"
        )

        # Step 3: Draw FAC → RN for the return table
        ret_fac = deck.draw()
        if ret_fac.is_z_card:
            ret_fac = deck.draw_non_z()
        ret_rn = ret_fac.run_num_int or random.randint(1, 12)
        ret_rn = max(1, min(12, ret_rn))

        log.append(f"[KR] FAC Card #{ret_fac.card_number}: return RN={ret_rn}")

        # Look up the KR's return table
        kr_tables = kickoff_return_table
        if kr_index < len(kr_tables) and len(kr_tables[kr_index]) >= 12:
            row = kr_tables[kr_index][ret_rn - 1]
        else:
            # Fallback to default
            from .team import Team
            default_table = Team.DEFAULT_KR_RETURN_TABLE
            row = default_table[ret_rn - 1]

        # Each row is [normal, breakaway]
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            normal_val = row[0]
            breakaway_val = row[1]
        else:
            normal_val = row
            breakaway_val = row

        # RN 1 = breakaway (use breakaway/red column)
        if ret_rn == 1:
            parsed = self._parse_return_value(breakaway_val)
            column_used = "breakaway"
            log.append(f"[KR] RN=1 → BREAKAWAY! Using breakaway column: {breakaway_val}")
        else:
            parsed = self._parse_return_value(normal_val)
            column_used = "normal"
            log.append(f"[KR] Normal column: {normal_val}")

        final_yl = parsed["yard_line"]
        is_td = parsed["is_td"]
        is_fumble = parsed["is_fumble"]

        # Build description
        if is_td:
            log.append(f"[KR] {kr_name} returns the kickoff for a TOUCHDOWN!")
            r = PlayResult(
                play_type="KICKOFF",
                yards_gained=final_yl,
                result="KR_TD",
                is_touchdown=True,
                description=f"Kickoff to {kr_name} — returned for a TOUCHDOWN!",
                rusher=kr_name,
            )
            r.debug_log = log
            return r

        if is_fumble:
            # Draw FAC for fumble recovery using team card
            fumble_fac = deck.draw()
            if fumble_fac.is_z_card:
                fumble_fac = deck.draw_non_z()
            fumble_pn = fumble_fac.pass_num_int or random.randint(1, 48)
            fumble_lost = PlayResolver.resolve_fumble_with_team_rating(
                fumble_pn, fumbles_lost_max, def_fumble_adj, is_home,
            )
            recovery = "DEFENSE" if fumble_lost else "OFFENSE"
            adjusted_max = max(0, min(48, fumbles_lost_max + def_fumble_adj - (1 if is_home else 0)))
            log.append(f"[KR] {kr_name} FUMBLES at the {final_yl}-yard line!")
            log.append(f"[KR FUMBLE] FAC drawn: Card #{fumble_fac.card_number}, PN={fumble_pn}")
            log.append(f"[KR FUMBLE] fumbles_lost_max={fumbles_lost_max}, def_fumble_adj={def_fumble_adj}, "
                        f"home={is_home} → range 1-{adjusted_max}")
            log.append(f"[KR FUMBLE] PN {fumble_pn} {'in' if fumble_lost else 'outside'} range "
                        f"→ {recovery} recovers")

            desc = (f"Kickoff to {kr_name}, returned to the {final_yl}-yard line — FUMBLE! "
                    f"{'Defense recovers!' if fumble_lost else 'Offense recovers.'}")
            r = PlayResult(
                play_type="KICKOFF",
                yards_gained=final_yl,
                result="FUMBLE",
                turnover=fumble_lost,
                turnover_type="FUMBLE" if fumble_lost else None,
                description=desc,
                rusher=kr_name,
            )
            r.debug_log = log
            return r

        log.append(f"[KR] {kr_name} returns the kickoff to the {final_yl}-yard line "
                    f"(column={column_used})")
        r = PlayResult(
            play_type="KICKOFF",
            yards_gained=final_yl,
            result="RETURN",
            description=f"Kickoff to {kr_name}, returned to the {final_yl}-yard line",
            rusher=kr_name,
        )
        r.debug_log = log
        return r

    # ── 5E Authentic Punt Return Resolution ────────────────────────────

    def resolve_punt_return_5e(
        self,
        deck: FACDeck,
        punt_returners: List[Dict[str, Any]],
        punt_return_table: List[List[Any]],
        punt_distance: int,
        yard_line: int,
        fumbles_lost_max: int = 21,
        def_fumble_adj: int = 0,
        is_home: bool = False,
    ) -> Dict[str, Any]:
        """Resolve a punt return using 5E team card tables.

        Returns a dict with:
          returner_name, return_yards, final_yl, is_td, is_fumble,
          fumble_lost, is_fair_catch, log_entries
        """
        log: List[str] = []

        # Draw FAC → PN to select which PR
        pr_fac = deck.draw()
        if pr_fac.is_z_card:
            pr_fac = deck.draw_non_z()
        pr_pn = pr_fac.pass_num_int or random.randint(1, 48)
        pr_pn = max(1, min(48, pr_pn))

        pr_index = 0
        pr_name = "unknown"
        for i, pr in enumerate(punt_returners):
            pn_min = pr.get("pn_min", 1)
            pn_max = pr.get("pn_max", 48)
            if pn_min <= pr_pn <= pn_max:
                pr_index = i
                pr_name = pr.get("name", "unknown")
                break
        log.append(
            f"[PR] FAC Card #{pr_fac.card_number}: PN={pr_pn} → "
            f"PR{pr_index + 1} {pr_name}"
        )

        # Draw FAC → RN for return table
        ret_fac = deck.draw()
        if ret_fac.is_z_card:
            ret_fac = deck.draw_non_z()
        ret_rn = ret_fac.run_num_int or random.randint(1, 12)
        ret_rn = max(1, min(12, ret_rn))

        log.append(f"[PR] FAC Card #{ret_fac.card_number}: return RN={ret_rn}")

        # Look up the PR's return table
        pr_tables = punt_return_table
        if pr_index < len(pr_tables) and len(pr_tables[pr_index]) >= 12:
            row = pr_tables[pr_index][ret_rn - 1]
        else:
            from .team import Team
            row = Team.DEFAULT_PR_RETURN_TABLE[ret_rn - 1]

        if isinstance(row, (list, tuple)) and len(row) >= 2:
            normal_val = row[0]
            breakaway_val = row[1]
        else:
            normal_val = row
            breakaway_val = row

        # RN 1 = breakaway
        if ret_rn == 1:
            parsed = self._parse_return_value(breakaway_val)
            log.append(f"[PR] RN=1 → BREAKAWAY! Using breakaway column: {breakaway_val}")
        else:
            parsed = self._parse_return_value(normal_val)
            log.append(f"[PR] Normal column: {normal_val}")

        return_yl = parsed["yard_line"]
        is_td = parsed["is_td"]
        is_fumble = parsed["is_fumble"]

        # Calculate return yards from the punt landing spot
        # Punt lands at: yard_line + punt_distance (from punter's perspective)
        # Returner's yard line = 100 - (yard_line + punt_distance), capped at 1-99
        punt_landing = max(1, min(99, yard_line + punt_distance))
        returner_start_yl = max(1, 100 - punt_landing)

        # The return table value IS the final yard line the returner reaches
        return_yards = max(0, return_yl - returner_start_yl) if not is_td else return_yl

        if is_td:
            log.append(f"[PR] {pr_name} returns the punt for a TOUCHDOWN!")
        elif is_fumble:
            log.append(f"[PR] {pr_name} FUMBLES at the {return_yl}-yard line!")
        else:
            log.append(f"[PR] {pr_name} returns to the {return_yl}-yard line "
                        f"(started at ~{returner_start_yl})")

        fumble_lost = False
        if is_fumble:
            fumble_fac = deck.draw()
            if fumble_fac.is_z_card:
                fumble_fac = deck.draw_non_z()
            fumble_pn = fumble_fac.pass_num_int or random.randint(1, 48)
            fumble_lost = PlayResolver.resolve_fumble_with_team_rating(
                fumble_pn, fumbles_lost_max, def_fumble_adj, is_home,
            )
            recovery = "DEFENSE" if fumble_lost else "OFFENSE"
            adjusted_max = max(0, min(48, fumbles_lost_max + def_fumble_adj - (1 if is_home else 0)))
            log.append(f"[PR FUMBLE] FAC PN={fumble_pn}, range 1-{adjusted_max} → {recovery}")

        return {
            "returner_name": pr_name,
            "return_yards": return_yards,
            "final_yl": return_yl,
            "is_td": is_td,
            "is_fumble": is_fumble,
            "fumble_lost": fumble_lost,
            "is_fair_catch": False,
            "log_entries": log,
        }

    # ══════════════════════════════════════════════════════════════════
    #  5th-EDITION  FAC-CARD  RESOLUTION METHODS
    # ══════════════════════════════════════════════════════════════════

    def _resolve_z_card(self, deck: FACDeck) -> Optional[Dict[str, Any]]:
        """Resolve a Z-card event by drawing the next non-Z card.

        For injuries, also determines duration per the 5E Injury Table.
        """
        next_card = deck.draw_non_z()
        z_info = next_card.parse_z_result()
        if z_info["type"] == "NONE":
            return None
        # 5E Injury Table: Use the pass number to determine injury duration
        if z_info["type"] == "INJURY":
            inj_pn = next_card.pass_num_int or random.randint(1, 48)
            duration = self.resolve_injury_duration(inj_pn)
            z_info["injury_duration"] = duration
            z_info["injury_pn"] = inj_pn
        return z_info

    def _find_receiver_by_letter(self, letter: str,
                                 receivers: List[PlayerCard]) -> Optional[PlayerCard]:
        """Find a receiver card matching the given letter (A-E)."""
        for rec in receivers:
            if rec.receiver_letter == letter:
                return rec
        # If not found, fall back to positional order
        letter_index = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}
        idx = letter_index.get(letter, 0)
        if idx < len(receivers):
            return receivers[idx]
        return receivers[0] if receivers else None

    def _resolve_receiver_target(self, fac_card: FACCard,
                                 pass_type: str,
                                 default_receiver: PlayerCard,
                                 receivers: List[PlayerCard]) -> Optional[PlayerCard]:
        """Determine which receiver is targeted based on FAC card field.

        Rule 8: If the targeted position is unoccupied (no receiver matches),
        returns None so the caller treats it as a thrown-away pass (incomplete).

        Targeting uses the ``_formation_slot`` attribute set on each card by
        ``_get_all_receivers``, so it is robust to absent slots (e.g. FL absent
        in a 3RB formation — targeting "FL" correctly returns None instead of
        accidentally returning the player who happens to sit at index 0).
        """
        target = fac_card.get_receiver_target(pass_type)
        if target in ("Orig", "Z"):
            return default_receiver
        if target == "P.Rush":
            return default_receiver  # caller handles P.Rush as sack
        # Target is a position code: FL, LE, RE, BK1, BK2, BK3, etc.
        # Use slot-name lookup via _formation_slot attribute (set by _get_all_receivers).
        if target in ("FL", "LE", "RE", "BK1", "BK2", "BK3"):
            for rec in receivers:
                if getattr(rec, '_formation_slot', None) == target:
                    return rec
            # Rule 8: no receiver occupies the targeted slot → throw it away
            return None
        return default_receiver

    def resolve_pass_5e(self, fac_card: FACCard, deck: FACDeck,
                        qb: PlayerCard, receiver: PlayerCard,
                        receivers: List[PlayerCard],
                        pass_type: str = "SHORT",
                        defense_coverage: int = 0,
                        defense_pass_rush: int = 0,
                        offense_pass_block: int = 0,
                        defense_formation: str = "4_3",
                        is_blitz_tendency: bool = False,
                        defensive_strategy: str = "NONE",
                        defenders: Optional[List[PlayerCard]] = None,
                        two_minute_offense: bool = False,
                        completion_modifier: int = 0,
                        defensive_play_5e=None,
                        yard_line: int = 25,
                        defenders_by_box: Optional[Dict[str, PlayerCard]] = None,
                        backs_blocking: Optional[List[int]] = None,
                        double_coverage_defender_box: Optional[str] = None,
                        blitzer_names: Optional[List[str]] = None,
                        endurance_modifier: int = 0) -> PlayResult:
        """Resolve a pass play using 5th-edition FAC card mechanics.

        Parameters
        ----------
        fac_card : FACCard
            The drawn FAC card for this play.
        deck : FACDeck
            The deck (needed for Z-card resolution).
        qb : PlayerCard
            Quarterback's card.
        receiver : PlayerCard
            Default receiver for this play.
        receivers : List[PlayerCard]
            All available receivers (WRs + TEs).
        pass_type : str
            "SHORT", "LONG", "QUICK", or "SCREEN".
        defensive_strategy : str
            "NONE", "DOUBLE_COVERAGE", "TRIPLE_COVERAGE", or "ALT_DOUBLE_COVERAGE".
        defenders : Optional[List[PlayerCard]]
            Defensive players for coverage calculations.
        two_minute_offense : bool
            If True, apply two-minute offense restrictions (-4 to completion range for non-screen passes).
        completion_modifier : int
            Additional modifier to QB completion range (e.g. from play-action).
            Positive = wider COM range (more completions), negative = narrower.
        defensive_play_5e : Optional[DefensivePlay]
            The 5E defensive play call. When provided, uses proper
            get_completion_modifier_5e() for completion range modifiers.
        yard_line : int
            Offensive team's field position (0 = own goal, 100 = opponent's
            goal).  Used for within-20 completion modifiers.
        defenders_by_box : Optional[Dict[str, PlayerCard]]
            Box letter → PlayerCard mapping for the defense.  When provided,
            enables per-receiver pass-defense-rating modifiers and proper
            INC→INT checks using the covering defender.
        backs_blocking : Optional[List[int]]
            Indices into the ``receivers`` list for backs staying in to
            block instead of running routes.  Each blocking back adds +2
            to the QB's completion range but cannot be targeted.
        double_coverage_defender_box : Optional[str]
            The original box letter of the defender who moved to double
            cover a receiver.  If an INC→INT check fires in this box,
            the interception is suppressed because the defender is away.
        blitzer_names : Optional[List[str]]
            Names of blitzing players for debug logging.
        endurance_modifier : int
            Completion range modifier from receiver endurance violation.
            Only applied when the FAC's actual receiver matches the
            intended target; ignored on check-offs per 5E rules.
        """
        # ── Handle Z card ────────────────────────────────────────────
        if fac_card.is_z_card:
            z_event = self._resolve_z_card(deck)
            # On a Z card, draw the next card and use it for the play
            fac_card = deck.draw_non_z()
            return self._resolve_pass_inner_5e(
                fac_card, deck, qb, receiver, receivers, pass_type,
                defense_coverage, defense_pass_rush, offense_pass_block,
                defense_formation,
                is_blitz_tendency, z_event, defensive_strategy, defenders,
                two_minute_offense, completion_modifier, defensive_play_5e,
                yard_line, defenders_by_box, backs_blocking,
                double_coverage_defender_box, blitzer_names,
                endurance_modifier,
            )

        return self._resolve_pass_inner_5e(
            fac_card, deck, qb, receiver, receivers, pass_type,
            defense_coverage, defense_pass_rush, offense_pass_block,
            defense_formation,
            is_blitz_tendency, None, defensive_strategy, defenders,
            two_minute_offense, completion_modifier, defensive_play_5e,
            yard_line, defenders_by_box, backs_blocking,
            double_coverage_defender_box, blitzer_names,
            endurance_modifier,
        )

    def _resolve_pass_inner_5e(self, fac_card: FACCard, deck: FACDeck,
                               qb: PlayerCard, receiver: PlayerCard,
                               receivers: List[PlayerCard],
                               pass_type: str,
                               defense_coverage: int,
                               defense_pass_rush: int,
                               offense_pass_block: int,
                               defense_formation: str,
                               is_blitz_tendency: bool,
                               z_event: Optional[Dict[str, Any]],
                               defensive_strategy: str = "NONE",
                               defenders: Optional[List[PlayerCard]] = None,
                               two_minute_offense: bool = False,
                               completion_modifier: int = 0,
                               defensive_play_5e=None,
                               yard_line: int = 25,
                               defenders_by_box: Optional[Dict[str, PlayerCard]] = None,
                               backs_blocking: Optional[List[int]] = None,
                               double_coverage_defender_box: Optional[str] = None,
                               blitzer_names: Optional[List[str]] = None,
                               endurance_modifier: int = 0) -> PlayResult:
        """Inner pass resolution after Z-card handling.

        Authentic 5E resolution:
          1. If Blitz vs Short/Long → always trigger Pass Rush
          2. Check QK/SH/LG receiver target field on FAC card
          3. If "P.Rush" → check QB pass rush ranges for sack/scramble/COM
          4. Screen passes use FAC SC field directly
          5. PN → QB card passing ranges → COM / INC / INT
          6. If COM → RUN NUMBER → receiver's pass-gain Q/S/L → yards

        NOTE: The ER (End Run) field is for run plays only; it does NOT
        cause sacks on pass plays.  Pass-play sacks come exclusively
        from the "P.Rush" code in the QK/SH/LG receiver-target field,
        or from Blitz defense forcing Pass Rush on Short/Long passes.
        """
        log: List[str] = []
        log.append(f"[FAC] Card #{fac_card.card_number}: RN={fac_card.run_number} PN={fac_card.pass_number} ER={fac_card.end_run}")
        log.append(f"[PASS] Type={pass_type}, QB={qb.player_name}, Target={receiver.player_name}")
        log.append(f"[DEF] Formation={defense_formation}, Strategy={defensive_strategy}")

        # ── Step 0: Blitz always forces Pass Rush on Short/Long ──────
        force_pass_rush = False
        if defensive_play_5e is not None:
            from .play_types import should_force_pass_rush
            force_pass_rush = should_force_pass_rush(defensive_play_5e, pass_type)

        # ── Step 1: Check receiver target for P.Rush ─────────────────
        target_field = fac_card.get_receiver_target(pass_type)
        log.append(f"[TARGET] FAC {pass_type} target field = '{target_field}'")
        if force_pass_rush or target_field == "P.Rush":
            if force_pass_rush:
                log.append(f"[P.RUSH] Pass rush FORCED by Blitz defense vs {pass_type} pass (overrides FAC target)")
            else:
                log.append("[P.RUSH] Pass rush triggered by FAC card")
            # Pass rush result → check QB's pass_rush ranges
            if qb.pass_rush:
                # PN comes directly from the FAC card (1-48 per 5E rules).
                # The fallback random.randint(1, 48) covers unparseable cards.
                # PN is never modified — only the QB's sack range shifts.
                pn = min(fac_card.pass_num_int or random.randint(1, 48), 48)
                log.append(f"[P.RUSH] PN={pn}, QB pass_rush ranges: sack_max={qb.pass_rush.sack_max}, runs_max={qb.pass_rush.runs_max}, com_max={qb.pass_rush.com_max}")

                # Per 5E rules Steps 1-3:
                # defense_pass_rush = sum of DL Row 1 pass rush values
                #   (+ blitzing player PR=2 each, already included by caller)
                # offense_pass_block = sum of OL pass blocking values
                # Modifier = (def_sum - off_sum) * 2, applied to sack range
                pr_modifier = self.calculate_pass_rush_modifier(
                    defense_pass_rush, offense_pass_block
                )
                log.append(f"[P.RUSH] DL pass rush sum={defense_pass_rush}, OL pass block sum={offense_pass_block}")

                # Per 5E rules: modifier adjusts the QB's Sack Range on
                # his Pass Rush line — NOT the Pass Number.  The
                # Completion Range is never altered (Step 4 note).
                # When sack range shrinks, former sack numbers become
                # RUNS (Step 4 note).
                adjusted_sack_max = qb.pass_rush.sack_max + pr_modifier
                # Sack range can't go below 0 or above runs_max
                adjusted_sack_max = max(0, min(qb.pass_rush.runs_max, adjusted_sack_max))
                if pr_modifier != 0:
                    log.append(f"[P.RUSH] PR modifier={pr_modifier}, adjusted sack range: {qb.pass_rush.sack_max}→{adjusted_sack_max}")

                # Log blitzer info when blitz forced the pass rush
                if blitzer_names:
                    log.append(f"[P.RUSH] Blitzing ({len(blitzer_names)}): {', '.join(blitzer_names)}")

                # Resolve using adjusted sack range; runs_max and com_max
                # are unchanged per the rules.
                if pn <= adjusted_sack_max:
                    pr_result = "SACK"
                elif pn <= qb.pass_rush.runs_max:
                    pr_result = "RUNS"
                elif pn <= qb.pass_rush.com_max:
                    pr_result = "COM"
                else:
                    pr_result = "INC"
                log.append(f"[P.RUSH] Result = {pr_result}")
                if pr_result == "SACK":
                    loss = -(pn // 3 + 1)
                    loss = max(loss, -8)
                    r = PlayResult(
                        play_type="PASS", yards_gained=loss,
                        result="SACK",
                        description=f"{qb.player_name} sacked on pass rush! {abs(loss)} yard loss.",
                        passer=qb.player_name, z_card_event=z_event,
                        pass_number_used=pn,
                    )
                    r.debug_log = log
                    return r
                elif pr_result == "RUNS":
                    run_num = fac_card.run_num_int or random.randint(1, 12)
                    log.append(f"[SCRAMBLE] QB scrambles, RN={run_num}")
                    if qb.rushing:
                        row = qb.get_rushing_row(run_num)
                        yards = row.v1
                        if isinstance(yards, str) and yards == "Sg":
                            yards = row.v2
                            if isinstance(yards, str):
                                yards = row.v3
                                if isinstance(yards, str):
                                    try:
                                        yards = int(yards)
                                    except (ValueError, TypeError):
                                        yards = random.randint(15, 40)
                        elif not isinstance(yards, int):
                            try:
                                yards = int(yards)
                            except (ValueError, TypeError):
                                yards = random.randint(1, 8)
                    else:
                        yards = random.randint(-2, 5)
                    is_td = self.check_pass_td_at_goal(yard_line, yards)
                    if is_td:
                        yards = 100 - yard_line
                    log.append(f"[SCRAMBLE] Yards={yards}, TD={is_td}")
                    r = PlayResult(
                        play_type="PASS", yards_gained=yards,
                        result="TD" if is_td else "GAIN",
                        is_touchdown=is_td,
                        description=f"{qb.player_name} scrambles for {yards} yards",
                        passer=qb.player_name, z_card_event=z_event,
                        pass_number_used=pn,
                        run_number_used=run_num,
                    )
                    r.debug_log = log
                    return r
                log.append(f"[P.RUSH] Pass rush had no effect — continue to pass resolution")
                # pr_result == "COM" or "INC" (PN outside all rush ranges) →
                # pass rush failed; per 5E rules there is no "hurried" result,
                # so play continues to normal pass resolution.
            else:
                loss = random.choice([-3, -4, -5, -6])
                log.append(f"[P.RUSH] No QB pass_rush ranges, default sack {loss} yards")
                r = PlayResult(
                    play_type="PASS", yards_gained=loss,
                    result="SACK",
                    description=f"{qb.player_name} sacked on pass rush! {abs(loss)} yard loss.",
                    passer=qb.player_name, z_card_event=z_event,
                )
                r.debug_log = log
                return r

        # ── Step 2: Screen pass — use FAC SC field directly ──────────
        if pass_type == "SCREEN":
            log.append(f"[SCREEN] SC field = '{fac_card.screen}'")
            r = self._resolve_screen_5e(
                fac_card, qb, receiver, z_event,
                receivers=receivers,
                defense_formation=defense_formation,
                defensive_play_5e=defensive_play_5e,
                yard_line=yard_line,
            )
            r.debug_log = log
            return r

        # ── Step 3: Determine actual receiver target ─────────────────
        actual_receiver = self._resolve_receiver_target(
            fac_card, pass_type, receiver, receivers,
        )
        log.append(f"[RECEIVER] Resolved target: {actual_receiver.player_name if actual_receiver else 'NONE (thrown away)'}")

        # Rule 8: If targeted position is unoccupied, throw the ball away
        if actual_receiver is None:
            r = PlayResult(
                play_type="PASS", yards_gained=0, result="INCOMPLETE",
                description=f"{qb.player_name} throws the ball away - no receiver at targeted position",
                passer=qb.player_name, z_card_event=z_event,
            )
            r.debug_log = log
            return r

        # ── Step 3a: Look up covering defender for this receiver ──────
        receiver_slot = self.get_receiver_slot(actual_receiver, receivers)
        covering_defender: Optional[PlayerCard] = None
        covering_defender_box: Optional[str] = None
        if receiver_slot and defenders_by_box:
            covering_defender_box = self.PASS_DEFENSE_ASSIGNMENTS.get(receiver_slot)
            covering_defender = self.get_covering_defender(receiver_slot, defenders_by_box)
            if covering_defender:
                log.append(f"[COVERAGE] {actual_receiver.player_name} ({receiver_slot}) covered by "
                           f"{covering_defender.player_name} (box {covering_defender_box}, "
                           f"PDR={covering_defender.pass_defense_rating})")
            else:
                log.append(f"[COVERAGE] {actual_receiver.player_name} ({receiver_slot}) → "
                           f"box {covering_defender_box} is EMPTY (+5 completion bonus)")

        # ── Step 3b: Backs in to block → check target not blocking ────
        blocking_set = set(backs_blocking or [])
        if blocking_set and actual_receiver is not None:
            rec_idx = None
            for idx, rec in enumerate(receivers):
                if rec is actual_receiver or rec.player_name == actual_receiver.player_name:
                    rec_idx = idx
                    break
            if rec_idx is not None and rec_idx in blocking_set:
                log.append(f"[BLOCK] Target {actual_receiver.player_name} is blocking — ball thrown away")
                r = PlayResult(
                    play_type="PASS", yards_gained=0, result="INCOMPLETE",
                    description=f"{qb.player_name} throws the ball away - {actual_receiver.player_name} stayed in to block",
                    passer=qb.player_name, z_card_event=z_event,
                )
                r.debug_log = log
                return r

        # ── Step 4: PN → QB card passing ranges → COM/INC/INT ────────
        pn = fac_card.pass_num_int
        if pn is None:
            pn = random.randint(1, 48)
        log.append(f"[QB CARD] PN={pn}, pass_type={pass_type}")

        # Apply defensive strategy modifiers (5E Rule 12-13)
        strategy_modifier = 0
        if defensive_strategy == "DOUBLE_COVERAGE" and defenders:
            strategy_modifier = self.resolve_double_coverage(actual_receiver, defenders)
        elif defensive_strategy == "TRIPLE_COVERAGE" and defenders:
            strategy_modifier = self.resolve_triple_coverage(actual_receiver, defenders)
        elif defensive_strategy == "ALT_DOUBLE_COVERAGE" and defenders:
            strategy_modifier = self.resolve_double_coverage(actual_receiver, defenders)
        
        if two_minute_offense and pass_type != "SCREEN":
            strategy_modifier -= 4

        # Apply 5E Defense/Pass Table completion modifier from defensive play call.
        # This is the core modifier: Pass Defense lowers completion range,
        # Run Defense makes passing easier, etc.
        # Within-20 modifiers apply when scrimmage line is within 20 of
        # the defense's goal (i.e. yard_line >= 80 on our 0-100 scale).
        defense_play_comp_mod = 0
        if defensive_play_5e is not None:
            from .play_types import get_completion_modifier_5e
            is_within_20 = yard_line >= self.WITHIN_20_YARD_LINE
            defense_play_comp_mod = get_completion_modifier_5e(defensive_play_5e, pass_type, within_20=is_within_20)
            if defense_play_comp_mod != 0:
                w20_tag = " [within-20]" if is_within_20 else ""
                log.append(f"[QB CARD] 5E Defense/Pass modifier: {defense_play_comp_mod:+d} (play={defensive_play_5e}, type={pass_type}){w20_tag}")

        # ── Backs in to block: +2 completion range per blocking back ──
        backs_blocking_mod = 0
        if blocking_set:
            num_blocking = len(blocking_set)
            backs_blocking_mod = num_blocking * 2
            log.append(f"[BLOCK] {num_blocking} back(s) blocking → +{backs_blocking_mod} completion range")

        # ── Pass defense rating of covering defender ──────────────────
        pass_defense_mod = 0
        empty_box_mod = 0
        if defenders_by_box is not None and receiver_slot:
            if covering_defender:
                # Positive pass_defense_rating = good defender = harder to complete
                # Apply as negative completion modifier (raises PN)
                pdr = covering_defender.pass_defense_rating
                # Out-of-position penalty: DB in wrong box → −1 PDR
                if covering_defender_box:
                    oop = self.check_out_of_position_penalty(
                        covering_defender, covering_defender_box
                    )
                    if oop != 0:
                        pdr = max(0, pdr + oop)
                        log.append(
                            f"[OOP] {covering_defender.player_name} out of position "
                            f"in box {covering_defender_box}: PDR adjusted by {oop}"
                        )
                pass_defense_mod = -pdr
                if pass_defense_mod != 0:
                    log.append(f"[COVERAGE] Defender PDR {pdr} → "
                               f"completion modifier {pass_defense_mod:+d}")
            else:
                # Empty box → +5 to completion range per 5E rules
                empty_box_mod = self.get_empty_box_completion_modifier(False)
                log.append(f"[COVERAGE] Empty box → +{empty_box_mod} completion range")

        # Apply completion_modifier (e.g. from play-action strategy).
        # Positive = wider COM range = subtract from PN (more likely to complete).
        # Negative = narrower COM range = add to PN (less likely to complete).
        #
        # 5E Endurance rule: if the FAC redirected the pass to a different
        # receiver (check-off), ignore the endurance penalty for this play.
        applied_endurance_mod = 0
        if endurance_modifier != 0:
            is_checkoff = (actual_receiver is not None
                           and actual_receiver.player_name != receiver.player_name)
            if is_checkoff:
                log.append(f"[ENDURANCE] Check-off to {actual_receiver.player_name} — "
                           f"endurance penalty ignored per 5E rules")
            else:
                applied_endurance_mod = endurance_modifier
                log.append(f"[ENDURANCE] Receiver endurance penalty: "
                           f"{applied_endurance_mod:+d} to completion range")
        total_completion_mod = (completion_modifier + defense_play_comp_mod
                                + backs_blocking_mod + empty_box_mod
                                + pass_defense_mod + applied_endurance_mod)
        completion_adjustment = -total_completion_mod  # +5 completion → -5 to PN

        # Coverage penalties (double/triple/two-minute) are always <= 0.
        # Negative strategy_modifier → increase PN (harder to complete).
        coverage_penalty = -strategy_modifier if strategy_modifier < 0 else 0

        total_pn_adjustment = completion_adjustment + coverage_penalty
        
        if strategy_modifier != 0 or total_completion_mod != 0:
            log.append(f"[QB CARD] Strategy modifier={strategy_modifier}, completion modifier={total_completion_mod}")
        if total_pn_adjustment != 0:
            old_pn = pn
            pn = max(1, min(48, pn + total_pn_adjustment))
            log.append(f"[QB CARD] PN adjusted from {old_pn} to {pn} (total adjustment {total_pn_adjustment:+d})")

        # Check authentic range-based passing first
        if qb.passing_short or qb.passing_long or qb.passing_quick:
            qb_result = qb.resolve_passing(pass_type, pn)
            log.append(f"[QB CARD] Authentic passing ranges → result={qb_result}")
        else:
            # Legacy: fall back to old slot-based columns
            if pass_type == "LONG":
                qb_column = qb.long_pass
            elif pass_type == "QUICK":
                qb_column = qb.quick_pass if qb.quick_pass else qb.short_pass
            else:
                qb_column = qb.short_pass

            if not qb_column:
                comp = random.random() < 0.62
                log.append(f"[QB CARD] No QB column, random completion={comp}")
                if comp:
                    yards = random.randint(5, 15)
                    r = PlayResult(
                        play_type="PASS", yards_gained=yards, result="COMPLETE",
                        description=f"{qb.player_name} completes to {actual_receiver.player_name} for {yards} yards",
                        passer=qb.player_name, receiver=actual_receiver.player_name,
                        z_card_event=z_event,
                        pass_number_used=pn,
                    )
                    r.debug_log = log
                    return r
                r = PlayResult(
                    play_type="PASS", yards_gained=0, result="INCOMPLETE",
                    description=f"{qb.player_name} pass incomplete to {actual_receiver.player_name}",
                    passer=qb.player_name, receiver=actual_receiver.player_name,
                    z_card_event=z_event,
                    pass_number_used=pn,
                )
                r.debug_log = log
                return r

            pn_str = str(pn)
            qb_data = qb_column.get(pn_str, {"result": "INC", "yards": 0, "td": False})
            qb_result_raw = qb_data.get("result", "INC")
            if qb_result_raw in ("INT",):
                qb_result = "INT"
            elif qb_result_raw in ("INC", "INCOMPLETE"):
                qb_result = "INC"
            else:
                qb_result = "COM"
            log.append(f"[QB CARD] Legacy: raw={qb_result_raw}, mapped={qb_result}")

        # ── INT result ───────────────────────────────────────────────
        if qb_result == "INT":
            rn_for_poi = fac_card.run_num_int or random.randint(1, 12)
            poi = PlayResolver.calculate_point_of_interception(pass_type, rn_for_poi, yard_line)
            int_yards, int_td = Charts.roll_int_return()
            # Check if return goes into opposing end zone
            if not int_td and poi - int_yards <= 0:
                int_td = True
                int_yards = poi
            log.append(f"[INT] Interception! RN={rn_for_poi}, pass_type={pass_type}")
            log.append(f"[INT] Point of interception: {poi}-yard line (from yard_line={yard_line})")
            log.append(f"[INT] Return yards={int_yards}, TD={int_td}")
            r = PlayResult(
                play_type="PASS", yards_gained=0,
                result="INT", turnover=True, turnover_type="INT",
                is_touchdown=int_td,
                description=(
                    f"{qb.player_name} pass intercepted at the {poi}-yard line!"
                    f"{' Returned for TD!' if int_td else f' Returned {int_yards} yards.'}"
                ),
                passer=qb.player_name, receiver=actual_receiver.player_name,
                z_card_event=z_event,
                pass_number_used=pn,
                run_number_used=rn_for_poi,
                interception_point=poi,
            )
            r.debug_log = log
            return r

        # ── INC result — check for INC-range interception ────────────
        if qb_result == "INC":
            log.append(f"[INC] Incomplete pass, checking defender intercept ranges")

            # Use the covering defender's intercept_range (not the offensive receiver's).
            # If defenders_by_box is provided, use the covering defender looked up
            # in Step 3a.  Otherwise fall back to legacy check.
            int_check_defender = covering_defender
            int_check_defender_box = covering_defender_box

            # Double coverage INT suppression: if the covering defender's
            # original box matches the double_coverage_defender_box, that
            # defender has moved away to double-cover another receiver and
            # is not in position to intercept.
            if (int_check_defender and double_coverage_defender_box
                    and int_check_defender_box == double_coverage_defender_box):
                log.append(f"[INC] Defender {int_check_defender.player_name} (box {int_check_defender_box}) "
                           f"away on double coverage — INT suppressed")
                int_check_defender = None

            # Fall back to legacy: use actual_receiver (this may be an
            # offensive player with intercept_range 0, which is harmless).
            if int_check_defender is None and covering_defender is None:
                if hasattr(actual_receiver, 'intercept_range') and actual_receiver.intercept_range:
                    int_check_defender = actual_receiver

            if int_check_defender and getattr(int_check_defender, 'intercept_range', 0):
                int_range = int_check_defender.intercept_range
                log.append(f"[INC] Defender {int_check_defender.player_name} intercept range = {int_range}")
                if isinstance(int_range, int) and int_range <= 48:
                    if int_range <= pn <= 48:
                        rn_for_ret = fac_card.run_num_int or random.randint(1, 12)
                        defender_pos = getattr(int_check_defender, 'position', 'DB')
                        poi = PlayResolver.calculate_point_of_interception(pass_type, rn_for_ret, yard_line)
                        int_yards, int_td = Charts.roll_int_return_5e(rn_for_ret, defender_pos)
                        # Check if return goes into opposing end zone
                        if not int_td and poi - int_yards <= 0:
                            int_td = True
                            int_yards = poi
                        log.append(f"[INC→INT] PN {pn} in intercept range [{int_range}-48]! INT by {int_check_defender.player_name} ({defender_pos})!")
                        log.append(f"[INC→INT] Point of interception: {poi}-yard line (RN={rn_for_ret}, pass_type={pass_type})")
                        log.append(f"[INC→INT] Return: {int_yards} yards (5E table, position={defender_pos}), TD={int_td}")
                        r = PlayResult(
                            play_type="PASS", yards_gained=0,
                            result="INT", turnover=True, turnover_type="INT",
                            is_touchdown=int_td,
                            description=(
                                f"{qb.player_name} pass intercepted by {int_check_defender.player_name} at the {poi}-yard line!"
                                f"{' Returned for TD!' if int_td else f' Returned {int_yards} yards.'}"
                            ),
                            passer=qb.player_name, receiver=actual_receiver.player_name,
                            z_card_event=z_event,
                            pass_number_used=pn,
                            run_number_used=rn_for_ret,
                            interception_point=poi,
                        )
                        r.debug_log = log
                        return r
                elif isinstance(int_range, (list, tuple)) and len(int_range) == 2:
                    if int_range[0] <= pn <= int_range[1]:
                        rn_for_ret = fac_card.run_num_int or random.randint(1, 12)
                        poi = PlayResolver.calculate_point_of_interception(pass_type, rn_for_ret, yard_line)
                        int_yards, int_td = Charts.roll_int_return()
                        if not int_td and poi - int_yards <= 0:
                            int_td = True
                            int_yards = poi
                        log.append(f"[INC→INT] PN {pn} in legacy range [{int_range[0]}-{int_range[1]}]! INT by {int_check_defender.player_name}!")
                        log.append(f"[INC→INT] Point of interception: {poi}-yard line (RN={rn_for_ret}, pass_type={pass_type})")
                        log.append(f"[INC→INT] Return: {int_yards} yards, TD={int_td}")
                        r = PlayResult(
                            play_type="PASS", yards_gained=0,
                            result="INT", turnover=True, turnover_type="INT",
                            is_touchdown=int_td,
                            description=(
                                f"{qb.player_name} pass intercepted by {int_check_defender.player_name} at the {poi}-yard line!"
                                f"{' Returned for TD!' if int_td else f' Returned {int_yards} yards.'}"
                            ),
                            passer=qb.player_name, receiver=actual_receiver.player_name,
                            z_card_event=z_event,
                            pass_number_used=pn,
                            run_number_used=rn_for_ret,
                            interception_point=poi,
                        )
                        r.debug_log = log
                        return r
            if pn == 48:
                new_pn = random.randint(1, 48)
                log.append(f"[INC] PN=48 special check: new PN={new_pn}")
                if new_pn <= 24:
                    rn_for_ret = fac_card.run_num_int or random.randint(1, 12)
                    poi = PlayResolver.calculate_point_of_interception(pass_type, rn_for_ret, yard_line)
                    int_yards, int_td = Charts.roll_int_return()
                    if not int_td and poi - int_yards <= 0:
                        int_td = True
                        int_yards = poi
                    log.append(f"[INC→INT] PN 48 special: intercepted at {poi}-yard line")
                    log.append(f"[INC→INT] Return: {int_yards} yards, TD={int_td}")
                    r = PlayResult(
                        play_type="PASS", yards_gained=0,
                        result="INT", turnover=True, turnover_type="INT",
                        is_touchdown=int_td,
                        description=(
                            f"{qb.player_name} pass intercepted on PN 48 check at the {poi}-yard line! (new PN {new_pn})"
                            f"{' Returned for TD!' if int_td else f' Returned {int_yards} yards.'}"
                        ),
                        passer=qb.player_name, receiver=actual_receiver.player_name,
                        z_card_event=z_event,
                        pass_number_used=pn,
                        run_number_used=rn_for_ret,
                        interception_point=poi,
                    )
                    r.debug_log = log
                    return r
            r = PlayResult(
                play_type="PASS", yards_gained=0, result="INCOMPLETE",
                description=f"{qb.player_name} pass incomplete to {actual_receiver.player_name}",
                passer=qb.player_name, receiver=actual_receiver.player_name,
                z_card_event=z_event,
                pass_number_used=pn,
            )
            r.debug_log = log
            return r

        # ── COM result — Stage 2: RUN NUMBER → receiver pass gain ────
        run_num = fac_card.run_num_int
        if run_num is None:
            run_num = random.randint(1, 12)
        log.append(f"[COM] Completion! RN={run_num}, receiver={actual_receiver.player_name}")

        target_receiver = actual_receiver
        if not (qb.passing_short or qb.passing_long or qb.passing_quick):
            if qb_result_raw in RECEIVER_LETTERS:
                found = self._find_receiver_by_letter(qb_result_raw, receivers)
                if found:
                    target_receiver = found
                    log.append(f"[COM] Legacy receiver redirect → {target_receiver.player_name}")

        # Look up pass gain on receiver's card (Q/S/L columns)
        if target_receiver.pass_gain:
            row = target_receiver.get_pass_gain_row(run_num)
            if pass_type == "QUICK":
                yards = row.v1
            elif pass_type == "LONG":
                yards = row.v3
            else:
                yards = row.v2
            log.append(f"[REC CARD] Row {run_num}: Q={row.v1} S={row.v2} L={row.v3} → yards={yards}")

            if yards is None or yards == 0 or yards == "":
                log.append(f"[REC CARD] Dropped pass (blank/0)")
                r = PlayResult(
                    play_type="PASS", yards_gained=0, result="INCOMPLETE",
                    description=f"{qb.player_name} pass dropped by {target_receiver.player_name}",
                    passer=qb.player_name, receiver=target_receiver.player_name,
                    z_card_event=z_event,
                    pass_number_used=pn,
                    run_number_used=run_num,
                )
                r.debug_log = log
                return r

            if isinstance(yards, str):
                if yards == "Lg":
                    yards = random.randint(25, 60)
                    log.append(f"[REC CARD] 'Lg' → big play {yards} yards")
                else:
                    try:
                        yards = int(yards)
                    except (ValueError, TypeError):
                        yards = random.randint(5, 15)
            is_td = self.check_pass_td_at_goal(yard_line, yards) if isinstance(yards, int) else False
        elif target_receiver.short_reception or target_receiver.long_reception:
            pn_str = str(pn)
            if pass_type == "LONG":
                rec_column = target_receiver.long_reception
            else:
                rec_column = target_receiver.short_reception

            if rec_column:
                rec_data = rec_column.get(pn_str, {"result": "CATCH", "yards": 8, "td": False})
                log.append(f"[REC CARD] Legacy column: {rec_data}")
                if rec_data.get("result") in ("INC", "INCOMPLETE"):
                    r = PlayResult(
                        play_type="PASS", yards_gained=0, result="INCOMPLETE",
                        description=f"{qb.player_name} pass dropped by {target_receiver.player_name}",
                        passer=qb.player_name, receiver=target_receiver.player_name,
                        z_card_event=z_event,
                        pass_number_used=pn,
                        run_number_used=run_num,
                    )
                    r.debug_log = log
                    return r
                yards = rec_data.get("yards", 8)
                is_td = rec_data.get("td", False)
            else:
                yards = random.randint(5, 15) if pass_type != "LONG" else random.randint(15, 30)
                is_td = False
        else:
            yards = random.randint(5, 15) if pass_type != "LONG" else random.randint(15, 30)
            is_td = False
            log.append(f"[REC CARD] No receiver data, random yards={yards}")

        # NOTE: In authentic 5E rules, defense affects the Pass Number (PN)
        # via the covering defender's pass_defense_rating (already applied above),
        # NOT the reception yards.  The receiver card yards are used as-is.

        # Validate TD against field position — only score if ball reaches end zone
        if isinstance(yards, int):
            if self.check_pass_td_at_goal(yard_line, yards):
                is_td = True
                yards = 100 - yard_line  # cap at goal line
            else:
                is_td = False

        if is_td:
            desc = f"{qb.player_name} completes to {target_receiver.player_name} for a TOUCHDOWN!"
        else:
            desc = f"{qb.player_name} completes to {target_receiver.player_name} for {yards} yard{'s' if yards != 1 else ''}"
        log.append(f"[RESULT] {desc}")

        r = PlayResult(
            play_type="PASS", yards_gained=yards,
            result="TD" if is_td else "COMPLETE",
            is_touchdown=is_td,
            description=desc,
            passer=qb.player_name, receiver=target_receiver.player_name,
            z_card_event=z_event,
            pass_number_used=pn,
            run_number_used=run_num,
        )
        r.debug_log = log
        return r

    def _resolve_screen_5e(self, fac_card: FACCard, qb: PlayerCard,
                           receiver: PlayerCard,
                           z_event: Optional[Dict[str, Any]],
                           receivers: Optional[List[PlayerCard]] = None,
                           defense_formation: str = "4_3",
                           defensive_play_5e=None,
                           yard_line: int = 25) -> PlayResult:
        """Resolve a screen pass using the FAC card's SC field.

        Rule 4: Screen passes must go to a back (RB). If the receiver is a
        TE/WR, automatically redirect to the first available RB. When the
        screen is complete, use the RB's rushing N column for yards.
        Defense run number modifiers apply to screen plays.
        """
        # Rule 4: Redirect to first available RB if receiver is not a back
        actual_receiver = receiver
        if receiver.position not in ("RB", "QB"):
            # Find first available RB in receivers list
            if receivers:
                for r in receivers:
                    if r.position == "RB":
                        actual_receiver = r
                        break

        sc_result = fac_card.screen_result

        if sc_result == "Inc":
            return PlayResult(
                play_type="PASS", yards_gained=0, result="INCOMPLETE",
                description=f"{qb.player_name} screen pass to {actual_receiver.player_name} - incomplete",
                passer=qb.player_name, receiver=actual_receiver.player_name,
                z_card_event=z_event,
            )

        if sc_result == "Int":
            rn_for_ret = fac_card.run_num_int or random.randint(1, 12)
            poi = PlayResolver.calculate_point_of_interception("SCREEN", rn_for_ret, yard_line)
            int_yards, int_td = Charts.roll_int_return()
            if not int_td and poi - int_yards <= 0:
                int_td = True
                int_yards = poi
            return PlayResult(
                play_type="PASS", yards_gained=0,
                result="INT", turnover=True, turnover_type="INT",
                is_touchdown=int_td,
                description=(
                    f"{qb.player_name} screen pass intercepted at the {poi}-yard line!"
                    f"{' Returned for TD!' if int_td else f' Returned {int_yards} yards.'}"
                ),
                passer=qb.player_name, receiver=actual_receiver.player_name,
                z_card_event=z_event,
                interception_point=poi,
            )

        # Screen complete — Rule 4: use RB's rushing N column for yards
        run_num = fac_card.run_num_int or random.randint(1, 12)
        # Apply defense run number modifiers for screen (from Defense/Pass Table)
        if defensive_play_5e is not None:
            from .play_types import get_screen_rn_modifier_5e
            rn_modifier = get_screen_rn_modifier_5e(defensive_play_5e, ball_carrier_number=1)
        else:
            rn_modifier = self.get_run_number_modifier(defense_formation)
        run_num = max(1, min(12, run_num + rn_modifier))

        if actual_receiver.has_rushing():
            row = actual_receiver.get_rushing_row(run_num)
            base_yards = row.v1
            if isinstance(base_yards, str):
                if base_yards == "Sg":
                    base_yards = row.v2 if isinstance(row.v2, int) else random.randint(8, 15)
                else:
                    try:
                        base_yards = int(base_yards)
                    except (ValueError, TypeError):
                        base_yards = random.randint(3, 10)
        else:
            base_yards = random.randint(3, 10)

        multiplier = 1.0
        if sc_result.startswith("Com x"):
            try:
                mult_str = sc_result.split("x")[-1].strip()
                if "½" in mult_str:
                    multiplier = 0.5
                elif "/" in mult_str:
                    num, den = mult_str.split("/")
                    multiplier = float(num) / float(den)
                else:
                    multiplier = float(mult_str)
            except (ValueError, ZeroDivisionError):
                multiplier = 1.0
        elif sc_result == "Dropped Int":
            return PlayResult(
                play_type="PASS", yards_gained=0, result="INCOMPLETE",
                description=f"{qb.player_name} screen pass nearly intercepted - dropped!",
                passer=qb.player_name, receiver=actual_receiver.player_name,
                z_card_event=z_event,
            )

        yards = max(0, int(base_yards * multiplier))
        is_td = self.check_pass_td_at_goal(yard_line, yards)
        if is_td:
            yards = 100 - yard_line

        if is_td:
            desc = f"{qb.player_name} screen pass to {actual_receiver.player_name} for a TOUCHDOWN!"
        else:
            desc = f"{qb.player_name} screen pass to {actual_receiver.player_name} for {yards} yards"

        return PlayResult(
            play_type="PASS", yards_gained=yards,
            result="TD" if is_td else "COMPLETE",
            is_touchdown=is_td,
            description=desc,
            passer=qb.player_name, receiver=actual_receiver.player_name,
            z_card_event=z_event,
            run_number_used=run_num,
        )

    def resolve_run_5e(self, fac_card: FACCard, deck: FACDeck,
                       rusher: PlayerCard,
                       play_direction: str = "IL",
                       defense_run_stop: int = 0,
                       defense_formation: str = "4_3",
                       extra_rn_modifier: int = 0,
                       defensive_play_5e=None,
                       box_is_empty: bool = False,
                       both_boxes_empty: bool = False,
                       blocking_back_bv: int = 0,
                       defenders_by_box: Optional[Dict[str, PlayerCard]] = None,
                       offensive_blockers_by_pos: Optional[Dict[str, 'PlayerCard']] = None,
                       fumbles_lost_max: int = 21,
                       def_fumble_adj: int = 0,
                       is_home: bool = False,
                       yard_line: int = 25) -> PlayResult:
        """Resolve a run play using 5th-edition FAC card mechanics.

        Authentic resolution:
          1. Draw FAC → get RUN NUMBER (1-12)
          2. Apply Run Number modifiers (defense play + extra)
          3. Look up rusher's Rushing column row → N/SG/LG values
          4. Use N (Normal) column as base yards
          5. Apply blocking matchup modifier (3 categories):
             a. OFFENSE ONLY (OL_ONLY / TWO_OL): ADD offensive blocker(s)
                blocking value to yardage.
             b. DEFENSE ONLY (SINGLE_DEF_BOX / TWO_DEF_BOX): SUBTRACT
                defender(s) tackle value from yardage; +2 if box empty.
             c. CONTEST (BK_VS_BOX / OL_VS_BOX): Compare total BV vs TV.
                If BV > TV → add BV; tie → 0; TV > BV → subtract TV.
                Empty box → +2.

        Parameters
        ----------
        fac_card : FACCard
            The drawn FAC card.
        deck : FACDeck
            The deck (for Z-card resolution).
        rusher : PlayerCard
            The ball carrier's card.
        play_direction : str
            "SL" (sweep left), "IL" (inside left),
            "SR" (sweep right), "IR" (inside right).
        extra_rn_modifier : int
            Additional Run Number modifier (e.g. from Draw strategy).
            Positive = worse for offense (higher RN), negative = better.
        defensive_play_5e : Optional[DefensivePlay]
            The 5E defensive play call.
        defenders_by_box : dict
            Mapping of box letter (A-O) → defensive PlayerCard.
        offensive_blockers_by_pos : dict
            Mapping of position abbreviation (CN, LG, BK, etc.) → offensive
            PlayerCard.  Used to look up blocking values for OL_ONLY, TWO_OL,
            and contest matchups.
        blocking_back_bv : int
            Legacy blocking back BV (kept for backward compat; prefer
            offensive_blockers_by_pos["BK"]).
        fumbles_lost_max : int
            Team's Fumbles Lost upper range.
        def_fumble_adj : int
            Defensive team's Fumble Adjustment.
        is_home : bool
            Whether the ball carrier's team is the home team.
        """
        z_event = None
        log: List[str] = []

        # ── Handle Z card ────────────────────────────────────────────
        if fac_card.is_z_card:
            log.append(f"[FAC] Z card drawn — resolving Z event, redrawing")
            z_event = self._resolve_z_card(deck)
            fac_card = deck.draw_non_z()

        # ── Log FAC card details ─────────────────────────────────────
        blocking_matchup = fac_card.get_blocking_matchup(play_direction)
        log.append(
            f"[FAC] Card #{fac_card.card_number}: "
            f"RN={fac_card.run_number} PN={fac_card.pass_number} "
            f"ER={fac_card.end_run} OOB={'Yes' if fac_card.is_out_of_bounds else 'No'}"
        )
        log.append(
            f"[FAC] Blocking matchup for {play_direction}: "
            f"SL={fac_card.sweep_left} | IL={fac_card.inside_left} | "
            f"SR={fac_card.sweep_right} | IR={fac_card.inside_right}"
        )
        log.append(f"[FAC] Selected matchup ({play_direction}): {blocking_matchup}")

        # ── Determine run number and OOB ─────────────────────────────
        run_num = fac_card.run_num_int
        is_oob = fac_card.is_out_of_bounds
        original_rn = run_num

        # Rule 1: Apply run number modifier based on defensive play + extra
        if defensive_play_5e is not None:
            from .play_types import get_run_number_modifier_5e
            # TODO: ball_carrier_number should come from play call context
            def_rn_mod = get_run_number_modifier_5e(defensive_play_5e, ball_carrier_number=1)
            rn_modifier = def_rn_mod + extra_rn_modifier
            log.append(
                f"[RN MOD] Defensive play={defensive_play_5e.value}: "
                f"def_modifier={def_rn_mod:+d}, extra={extra_rn_modifier:+d}, "
                f"total RN modifier={rn_modifier:+d}"
            )
        else:
            def_rn_mod = self.get_run_number_modifier(defense_formation)
            rn_modifier = def_rn_mod + extra_rn_modifier
            log.append(
                f"[RN MOD] Formation={defense_formation}: "
                f"def_modifier={def_rn_mod:+d}, extra={extra_rn_modifier:+d}, "
                f"total RN modifier={rn_modifier:+d}"
            )
        if run_num is not None:
            run_num = max(1, min(12, run_num + rn_modifier))
            log.append(f"[RN] Original RN={original_rn}, adjusted RN={run_num}")
        else:
            log.append(f"[RN] No run number (Z card fallback)")

        rn_str = str(run_num) if run_num is not None else "1"
        used_run_num = run_num if run_num is not None else 1

        # ── Compute defensive TV and offensive BV from matchup ────────
        box_letters = self.extract_box_letters(blocking_matchup)
        ol_abbrevs = self.extract_ol_abbreviations(blocking_matchup)

        # Total defensive tackle value from targeted box(es)
        total_def_tv = 0
        def_names = []
        any_box_occupied = False
        all_boxes_empty = False

        if defenders_by_box and box_letters:
            occupied_count = 0
            for bl in box_letters:
                defender = defenders_by_box.get(bl)
                if defender is not None:
                    tv = getattr(defender, 'tackle_rating', 0) or 0
                    # Out-of-position penalty: DB in wrong box → −1 TV
                    oop_penalty = self.check_out_of_position_penalty(defender, bl)
                    if oop_penalty != 0:
                        tv = max(0, tv + oop_penalty)
                        log.append(
                            f"[OOP] {defender.player_name} playing out of position "
                            f"in box {bl}: TV adjusted by {oop_penalty}"
                        )
                    total_def_tv += tv
                    def_names.append(f"{defender.player_name}(box={bl},TV={tv})")
                    occupied_count += 1
            any_box_occupied = occupied_count > 0
            all_boxes_empty = occupied_count == 0
            if any_box_occupied:
                log.append(
                    f"[DEF] Defenders targeted: {', '.join(def_names)}, "
                    f"total TV={total_def_tv}"
                )
            else:
                log.append(
                    f"[DEF] All targeted boxes {box_letters} empty"
                )
        elif box_letters:
            all_boxes_empty = True
            log.append(f"[DEF] No defenders_by_box available, boxes {box_letters} treated as empty")
        else:
            log.append(f"[DEF] No defensive box in matchup")

        # Total offensive blocking value from OL/BK abbreviations
        total_off_bv = 0
        off_names = []
        if offensive_blockers_by_pos and ol_abbrevs:
            for abbrev in ol_abbrevs:
                blocker = offensive_blockers_by_pos.get(abbrev)
                if blocker is not None:
                    bv = self.get_player_blocking_value(blocker)
                    total_off_bv += bv
                    off_names.append(f"{blocker.player_name}({abbrev},BV={bv})")
            if off_names:
                log.append(
                    f"[OFF] Blockers: {', '.join(off_names)}, total BV={total_off_bv}"
                )
        elif ol_abbrevs:
            # Fallback: use blocking_back_bv for BK if no personnel dict
            if "BK" in ol_abbrevs and blocking_back_bv:
                total_off_bv = blocking_back_bv
                log.append(f"[OFF] BK blocking back BV={blocking_back_bv} (fallback)")

        # Update empty-box flags for backward compatibility
        if all_boxes_empty and box_letters:
            if len(box_letters) == 1:
                box_is_empty = True
            elif len(box_letters) == 2:
                both_boxes_empty = True

        # ── Try authentic 12-row rushing first ───────────────────────
        if rusher.rushing and rusher.has_rushing():
            rn = run_num if run_num is not None else 1
            row = rusher.get_rushing_row(rn)
            log.append(
                f"[RUSH] {rusher.player_name} card row {rn}: "
                f"N={row.v1}, SG={row.v2}, LG={row.v3}"
            )

            # ── Check blocking matchup FIRST to detect BREAKAWAY ─────
            matchup_type = self.classify_blocking_matchup(blocking_matchup)
            log.append(f"[BLOCK] Matchup type: {matchup_type} ({blocking_matchup!r}), "
                       f"total_off_bv={total_off_bv}, total_def_tv={total_def_tv}, "
                       f"box_empty={box_is_empty}, both_empty={both_boxes_empty}")

            if matchup_type == "BREAK":
                # BREAKAWAY: use the LG (Long Gain) column, no run-stop
                yards = row.v3
                if isinstance(yards, str):
                    try:
                        yards = int(yards)
                    except (ValueError, TypeError):
                        yards = random.randint(15, 40)
                is_td = (yard_line + yards) >= 100
                if is_td:
                    yards = 100 - yard_line
                log.append(
                    f"[BREAKAWAY] FAC blocking matchup is BREAK → "
                    f"using LG column={row.v3}, yards={yards}, TD={is_td}"
                )
                desc = f"{rusher.player_name} breaks free for {yards} yards!"
                if is_td:
                    desc += " TOUCHDOWN!"
                r = PlayResult(
                    play_type="RUN", yards_gained=yards,
                    result="TD" if is_td else "GAIN",
                    is_touchdown=is_td,
                    description=desc,
                    rusher=rusher.player_name, z_card_event=z_event,
                    run_number_used=used_run_num,
                )
                r.debug_log = log
                return r

            # Use N (normal) column as base yards
            yards = row.v1
            if isinstance(yards, str):
                if yards == "Sg":
                    # Short Gain: draw a new FAC to get a new run number,
                    # then look up the SG column (v2) at that row.
                    # Per 5th-edition rules, Long Gain is only earned via a
                    # BREAK blocking matchup — not from an SG result.
                    sg_fac = deck.draw()
                    if sg_fac.is_z_card:
                        sg_fac = deck.draw_non_z()
                    if sg_fac.run_num_int is not None:
                        sg_rn = sg_fac.run_num_int
                    else:
                        sg_rn = random.randint(1, 12)
                        log.append(f"[RUSH] SG FAC has no run number; using random RN={sg_rn}")
                    sg_row = rusher.get_rushing_row(sg_rn)
                    yards = sg_row.v2
                    if isinstance(yards, str):
                        try:
                            yards = int(yards)
                        except (ValueError, TypeError):
                            # SG column value unreadable — use a short-gain approximation
                            yards = random.randint(1, 8)
                    is_td = (yard_line + yards) >= 100
                    if is_td:
                        yards = 100 - yard_line
                    log.append(
                        f"[RUSH] Short Gain (SG)! New FAC RN={sg_rn}, "
                        f"SG column={sg_row.v2}, yards={yards}, TD={is_td}"
                    )
                    desc = f"{rusher.player_name} gains {yards} yards (short gain)"
                    if is_td:
                        desc += " TOUCHDOWN!"
                    r = PlayResult(
                        play_type="RUN", yards_gained=yards,
                        result="TD" if is_td else "GAIN",
                        is_touchdown=is_td,
                        description=desc,
                        rusher=rusher.player_name, z_card_event=z_event,
                        run_number_used=used_run_num,
                    )
                    r.debug_log = log
                    return r
                else:
                    try:
                        yards = int(yards)
                    except (ValueError, TypeError):
                        yards = random.randint(1, 5)

            base_yards = yards

            # ── Blocking matchup resolution (3 categories) ───────────
            if matchup_type in ("OL_ONLY", "TWO_OL"):
                # OFFENSE ONLY: add offensive blocker(s) blocking value
                yards = base_yards + total_off_bv
                log.append(
                    f"[BLOCK] Offense only ({blocking_matchup}): "
                    f"base={base_yards} + BV={total_off_bv} = {yards}"
                )

            elif matchup_type in ("SINGLE_DEF_BOX", "TWO_DEF_BOX"):
                # DEFENSE ONLY: subtract defender(s) tackle value
                if all_boxes_empty:
                    yards = base_yards + 2
                    log.append(
                        f"[BLOCK] Empty box ({blocking_matchup}): "
                        f"base={base_yards} + 2 = {yards}"
                    )
                else:
                    yards = base_yards - total_def_tv
                    log.append(
                        f"[BLOCK] Defense box ({blocking_matchup}): "
                        f"base={base_yards} - TV={total_def_tv} = {yards}"
                    )

            elif matchup_type in ("BK_VS_BOX", "OL_VS_BOX"):
                # CONTEST: compare offense BV vs defense TV
                if all_boxes_empty:
                    # Empty box rule: +2
                    yards = base_yards + 2
                    log.append(
                        f"[BLOCK] Contest empty box ({blocking_matchup}): "
                        f"base={base_yards} + 2 = {yards}"
                    )
                elif total_off_bv > total_def_tv:
                    # Offense wins: add BV
                    yards = base_yards + total_off_bv
                    log.append(
                        f"[BLOCK] Contest offense wins ({blocking_matchup}): "
                        f"BV={total_off_bv} > TV={total_def_tv}, "
                        f"base={base_yards} + {total_off_bv} = {yards}"
                    )
                elif total_off_bv == total_def_tv:
                    # Tie: no modification
                    yards = base_yards
                    log.append(
                        f"[BLOCK] Contest tie ({blocking_matchup}): "
                        f"BV={total_off_bv} == TV={total_def_tv}, "
                        f"base={base_yards} + 0 = {yards}"
                    )
                else:
                    # Defense wins: subtract TV
                    yards = base_yards - total_def_tv
                    log.append(
                        f"[BLOCK] Contest defense wins ({blocking_matchup}): "
                        f"TV={total_def_tv} > BV={total_off_bv}, "
                        f"base={base_yards} - {total_def_tv} = {yards}"
                    )
            else:
                # Unrecognised matchup: use base yards only
                log.append(
                    f"[BLOCK] Unrecognised matchup ({blocking_matchup}): "
                    f"using base yards={base_yards}"
                )

            # 5E Rule: Inside run max loss = 3 yards; no limit on sweep
            old_yards = yards
            yards = self.apply_inside_run_max_loss(yards, play_direction)
            if yards != old_yards:
                log.append(
                    f"[CAP] Inside run max loss applied ({play_direction}): "
                    f"{old_yards} → {yards}"
                )

            # Out of bounds — 5E Rule: inside runs may never end out of bounds
            if is_oob and play_direction not in ("IL", "IR", "INSIDE", "MIDDLE", "LEFT"):
                log.append(f"[OOB] Runner out of bounds ({play_direction})")
                desc = f"{rusher.player_name} runs {play_direction} for {yards} yards, out of bounds"
                r = PlayResult(
                    play_type="RUN", yards_gained=yards,
                    result="OOB", out_of_bounds=True,
                    description=desc, rusher=rusher.player_name,
                    z_card_event=z_event,
                    run_number_used=used_run_num,
                )
                r.debug_log = log
                return r

            is_td = (yard_line + yards) >= 100
            if is_td:
                yards = 100 - yard_line

            # Check Z RES on the card for additional effects (authentic path)
            z_res_info = fac_card.parse_z_result()
            if z_res_info["type"] == "FUMBLE" and random.random() < 0.5:
                fumble_fac = deck.draw()
                if fumble_fac.is_z_card:
                    fumble_fac = deck.draw_non_z()
                fumble_pn = fumble_fac.pass_num_int or random.randint(1, 48)
                fumble_lost = PlayResolver.resolve_fumble_with_team_rating(
                    fumble_pn, fumbles_lost_max, def_fumble_adj, is_home,
                )
                is_turnover = fumble_lost
                recovery = "DEFENSE" if fumble_lost else "OFFENSE"

                adjusted_max = max(0, min(48, fumbles_lost_max + def_fumble_adj - (1 if is_home else 0)))
                log.append(f"[FUMBLE] Z-result fumble triggered for {rusher.player_name}")
                log.append(f"[FUMBLE] FAC drawn for recovery: Card #{fumble_fac.card_number}, PN={fumble_pn}")
                log.append(f"[FUMBLE] Team fumbles_lost_max={fumbles_lost_max}, def_fumble_adj={def_fumble_adj}, "
                            f"home={is_home} → adjusted range 1-{adjusted_max}")
                log.append(f"[FUMBLE] PN {fumble_pn} {'in' if fumble_lost else 'outside'} range 1-{adjusted_max} "
                            f"→ Recovery={recovery}")

                r = PlayResult(
                    play_type="RUN", yards_gained=yards,
                    result="FUMBLE", turnover=is_turnover,
                    turnover_type="FUMBLE" if is_turnover else None,
                    description=(
                        f"{rusher.player_name} fumbles at the end of the run! "
                        f"{'Defense recovers!' if is_turnover else 'Offense recovers.'}"
                    ),
                    rusher=rusher.player_name, z_card_event=z_event,
                    run_number_used=used_run_num,
                )
                r.debug_log = log
                return r

            desc = f"{rusher.player_name} runs {play_direction}"
            if is_td:
                desc += " for a TOUCHDOWN!"
            else:
                desc += f" for {yards} yard{'s' if yards != 1 else ''}"
            log.append(f"[RESULT] Final: {yards} yards, TD={is_td}")

            r = PlayResult(
                play_type="RUN", yards_gained=yards,
                result="TD" if is_td else "GAIN",
                is_touchdown=is_td,
                description=desc,
                rusher=rusher.player_name, z_card_event=z_event,
                run_number_used=used_run_num,
            )
            r.debug_log = log
            return r

        # No 12-row rushing data — generic fallback
        yards = random.choices([-2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8],
                               weights=[2, 3, 5, 8, 10, 12, 12, 10, 8, 5, 3])[0]
        log.append(f"[RUN] No rushing card data for {rusher.player_name}; fallback yards={yards}")
        r = PlayResult(
            play_type="RUN", yards_gained=yards, result="GAIN",
            description=f"{rusher.player_name} runs for {yards} yards",
            rusher=rusher.player_name, z_card_event=z_event,
            run_number_used=used_run_num,
        )
        r.debug_log = log
        return r

    # ══════════════════════════════════════════════════════════════════
    #  ADDITIONAL 5E RULES — NEW METHODS
    # ══════════════════════════════════════════════════════════════════

    # ── Rule 6: End-Around Resolution ────────────────────────────────

    def resolve_end_around(self, fac_card: FACCard, deck: FACDeck,
                           receiver: PlayerCard,
                           defense_formation: str = "4_3",
                           defense_run_stop: int = 0) -> PlayResult:
        """Resolve an end-around play (Rule 6).

        - Check ER info on FAC card: 'OK' = resolve as run using receiver's
          Rush column; negative number = automatic loss of that many yards.
        - Only allowed if receiver has rushing data.
        - Only ONCE per game per player.
        """
        # Check if already used this game
        if self._end_around_used.get(receiver.player_name, False):
            return PlayResult(
                play_type="RUN", yards_gained=-5, result="GAIN",
                description=f"End-around to {receiver.player_name} ILLEGAL - already used! -5 yards",
                rusher=receiver.player_name,
            )

        # Check if receiver has rushing data
        if not receiver.has_rushing():
            return PlayResult(
                play_type="RUN", yards_gained=-5, result="GAIN",
                description=f"End-around to {receiver.player_name} fails - no rushing ability! -5 yards",
                rusher=receiver.player_name,
            )

        # Mark as used
        self._end_around_used[receiver.player_name] = True

        # Check ER field on FAC card
        er = fac_card.end_run.strip()
        if er != "OK":
            # Negative number = automatic loss
            try:
                loss = int(er)
                if loss < 0:
                    return PlayResult(
                        play_type="RUN", yards_gained=loss, result="GAIN",
                        description=f"End-around to {receiver.player_name} loses {abs(loss)} yards",
                        rusher=receiver.player_name,
                    )
            except (ValueError, TypeError):
                pass

        # ER is OK — resolve as a run using receiver's Rush column
        return self.resolve_run_5e(
            fac_card, deck, receiver, "SR",
            defense_run_stop=defense_run_stop,
            defense_formation=defense_formation,
        )

    # ── Rule 7: Blocking Backs ───────────────────────────────────────

    @staticmethod
    def resolve_blocking_back(fac_matchup: str,
                              backs: List[PlayerCard]) -> int:
        """Resolve blocking back yardage modifier (Rule 7).

        When FAC directs to 'BK', the non-carrying back's BV modifies yardage.
        If 2 extra backs, both BVs are summed (coupled).

        Returns the total blocking value modifier.
        """
        if not backs:
            return 0
        total_bv = 0
        for back in backs:
            total_bv += getattr(back, 'blocks', 0)
        return total_bv

    # ── Rule 10: Passes Past End Zone = TD ───────────────────────────

    @staticmethod
    def check_pass_td_at_goal(yard_line: int, pass_yards: int) -> bool:
        """Return True if pass yards reach or exceed the end zone (Rule 10).

        yard_line is distance from own end zone (0-100).
        """
        return (yard_line + pass_yards) >= 100

    # ── Rule 15: Coffin Corner Punts ─────────────────────────────────

    def resolve_coffin_corner_punt(self, punter: PlayerCard,
                                   deck: FACDeck,
                                   deduction: int) -> PlayResult:
        """Resolve a coffin corner punt (Rule 15).

        Parameters
        ----------
        punter : PlayerCard
            The punter's card.
        deck : FACDeck
            The FAC deck.
        deduction : int
            Declared deduction from normal punt distance (10-25 yards).
        """
        deduction = max(10, min(25, deduction))
        punt_distance = max(10, int(punter.avg_distance) - deduction)

        # Draw FAC for run number
        fac_card = deck.draw()
        rn = fac_card.run_num_int or random.randint(1, 12)

        if rn % 2 == 1:
            # Odd RN: out of bounds at calculated spot, no return
            return PlayResult(
                play_type="PUNT", yards_gained=punt_distance,
                result="PUNT", out_of_bounds=True,
                description=(
                    f"{punter.player_name} coffin corner punt {punt_distance} yards, "
                    f"out of bounds (RN {rn})"
                ),
                run_number_used=rn,
            )
        else:
            # Even RN: normal return from calculated spot
            return_yards = Charts.roll_punt_return()
            net = punt_distance - return_yards
            return PlayResult(
                play_type="PUNT", yards_gained=net,
                result="PUNT",
                description=(
                    f"{punter.player_name} coffin corner punt {punt_distance} yards, "
                    f"returned {return_yards} yards (RN {rn})"
                ),
                run_number_used=rn,
            )

    # ── Rule 16: All-Out Punt Rush ───────────────────────────────────

    def resolve_all_out_punt_rush(self, punter: PlayerCard,
                                  deck: FACDeck) -> PlayResult:
        """Resolve an all-out punt rush (Rule 16).

        - Ignore RN 12 results.
        - RN 1-4:  blocked punt (-5 yards behind scrimmage).
        - RN 5-9:  hurried punt (use RN 11 yardage from punter card).
        - RN 10-12: roughing the punter (15 yards + first down penalty).
        - Max return 3 yards.
        """
        fac_card = deck.draw()
        rn = fac_card.run_num_int or random.randint(1, 12)

        # Ignore RN 12 — redraw
        while rn == 12:
            fac_card = deck.draw()
            rn = fac_card.run_num_int or random.randint(1, 11)

        if 1 <= rn <= 4:
            # Blocked punt
            return PlayResult(
                play_type="PUNT", yards_gained=-5,
                result="BLOCKED_PUNT",
                description=f"{punter.player_name}'s punt is BLOCKED! -5 yards (RN {rn})",
                run_number_used=rn,
            )
        elif 5 <= rn <= 9:
            # Hurried punt — use RN 11 yardage (shorter kick)
            if punter.rushing and len(punter.rushing) >= 11:
                row = punter.get_rushing_row(11)
                punt_yards = row.v1 if isinstance(row.v1, int) else int(punter.avg_distance * 0.7)
            else:
                punt_yards = int(punter.avg_distance * 0.7)
            # Max return 3 yards
            return_yards = min(3, Charts.roll_punt_return())
            net = punt_yards - return_yards
            return PlayResult(
                play_type="PUNT", yards_gained=net,
                result="PUNT",
                description=(
                    f"{punter.player_name} hurried punt for {punt_yards} yards, "
                    f"returned {return_yards} yards (RN {rn})"
                ),
                run_number_used=rn,
            )
        else:
            # RN 10-11: Roughing the punter
            return PlayResult(
                play_type="PUNT", yards_gained=15,
                result="PENALTY",
                is_first_down=True,
                penalty={"type": "ROUGHING_PUNTER", "yards": 15,
                         "auto_first": True, "loss_of_down": False},
                description=f"Roughing the punter! 15 yards and automatic first down (RN {rn})",
                run_number_used=rn,
            )

    # ── Rule 17: Punt Number 12 Rules ────────────────────────────────

    def resolve_punt_rn12(self, punter: PlayerCard,
                          deck: FACDeck) -> PlayResult:
        """Handle punt when RN is 12 (Rule 17).

        When RN is 12, draw a new 1-12 number:
          1-4: longest kick (out of bounds, no return)
          5-8: blocked punt (-5 yards)
          9-12: 5-yard movement penalty against kicking team
        """
        fac_card = deck.draw()
        rn2 = fac_card.run_num_int or random.randint(1, 12)

        if 1 <= rn2 <= 4:
            # Longest kick, OOB
            long_dist = int(punter.avg_distance + 10)
            return PlayResult(
                play_type="PUNT", yards_gained=long_dist,
                result="PUNT", out_of_bounds=True,
                description=f"{punter.player_name} booms a {long_dist}-yard punt out of bounds (RN12→{rn2})",
                run_number_used=rn2,
            )
        elif 5 <= rn2 <= 8:
            # Blocked punt
            return PlayResult(
                play_type="PUNT", yards_gained=-5,
                result="BLOCKED_PUNT",
                description=f"{punter.player_name}'s punt is BLOCKED! (RN12→{rn2})",
                run_number_used=rn2,
            )
        else:
            # 5-yard movement penalty
            return PlayResult(
                play_type="PUNT", yards_gained=0,
                result="PENALTY",
                penalty={"type": "DELAY_OF_GAME", "yards": 5,
                         "auto_first": False, "loss_of_down": False},
                description=f"5-yard movement penalty against kicking team (RN12→{rn2})",
                run_number_used=rn2,
            )

    # ── Rule 18: Punt Penalties ──────────────────────────────────────

    @staticmethod
    def check_punt_penalty(run_number: int) -> Optional[Dict[str, Any]]:
        """Check for automatic punt penalty (Rule 18).

        Even RN = 5-yard penalty vs kicking team.
        Odd RN = 5-yard penalty vs return team.
        These are automatic and cannot be declined.
        """
        if run_number % 2 == 0:
            return {"team": "kicking", "yards": 5, "type": "PUNT_PENALTY",
                    "description": "5-yard penalty against kicking team"}
        return {"team": "returning", "yards": 5, "type": "PUNT_PENALTY",
                "description": "5-yard penalty against return team"}

    # ── Rule 19: Punt Inside 6 = Touchback ───────────────────────────

    @staticmethod
    def check_punt_touchback(landing_yard_line: int,
                             is_coffin_corner: bool = False) -> bool:
        """Return True if a non-coffin-corner punt landing inside the 6 is a touchback (Rule 19).

        landing_yard_line is the opponent's yard line where the punt lands
        (1 = very close to their end zone, 100 = our end zone).
        """
        if is_coffin_corner:
            return False
        return landing_yard_line <= 5

    # ── Rule 20: Fumbled Punt Returns ────────────────────────────────

    @staticmethod
    def check_fumbled_punt_return(return_result: str) -> bool:
        """Return True if the punt return result includes a fumble (Rule 20).

        When the return result contains 'f', the return is fumbled.
        """
        if isinstance(return_result, str) and "f" in return_result.lower():
            return True
        return False

    # ── Rule 21: Fake Field Goal ─────────────────────────────────────

    def resolve_fake_field_goal(self, deck: FACDeck,
                                qb_or_holder: PlayerCard,
                                minutes_remaining: float = 3.0,
                                yard_line: int = 25) -> PlayResult:
        """Resolve a fake field goal attempt (Rule 21).

        - Draw FAC for RN: 1-6 = pass/run result, 7-9 = incomplete,
          10 = INT returned for TD.
        - Once per game restriction.
        - Never in final 2 minutes.
        """
        if self._fake_fg_used:
            return PlayResult(
                play_type="FG", yards_gained=-10, result="GAIN",
                description="Fake FG ILLEGAL - already used this game! -10 yards",
            )
        if minutes_remaining <= 2.0:
            return PlayResult(
                play_type="FG", yards_gained=-10, result="GAIN",
                description="Fake FG ILLEGAL - cannot use in final 2 minutes! -10 yards",
            )

        self._fake_fg_used = True
        fac_card = deck.draw()
        rn = fac_card.run_num_int or random.randint(1, 12)

        if 1 <= rn <= 6:
            # Pass/run result — scramble for yards
            yards = random.randint(2, 15)
            is_td = (yard_line + yards) >= 100
            if is_td:
                yards = 100 - yard_line
            return PlayResult(
                play_type="PASS", yards_gained=yards,
                result="TD" if is_td else "COMPLETE",
                is_touchdown=is_td,
                description=f"Fake field goal! {qb_or_holder.player_name} gains {yards} yards! (RN {rn})",
                passer=qb_or_holder.player_name,
                run_number_used=rn,
            )
        elif 7 <= rn <= 9:
            return PlayResult(
                play_type="PASS", yards_gained=0, result="INCOMPLETE",
                description=f"Fake field goal! Pass incomplete (RN {rn})",
                passer=qb_or_holder.player_name,
                run_number_used=rn,
            )
        else:
            # RN 10-12: interception returned for TD
            return PlayResult(
                play_type="PASS", yards_gained=0,
                result="INT", turnover=True, turnover_type="INT",
                is_touchdown=True,
                description=f"Fake field goal! INTERCEPTED and returned for a TOUCHDOWN! (RN {rn})",
                passer=qb_or_holder.player_name,
                run_number_used=rn,
            )

    # ── Rule 22: Fake Punt ───────────────────────────────────────────

    def resolve_fake_punt(self, deck: FACDeck,
                          punter: PlayerCard,
                          yard_line: int = 25) -> PlayResult:
        """Resolve a fake punt attempt (Rule 22).

        - Draw FAC for RN: 1-5 = pass result, 6-12 = punter run results.
        - RN 12 = daylight run (PN × 2 yards).
        - Once per game restriction.
        """
        if self._fake_punt_used:
            return PlayResult(
                play_type="PUNT", yards_gained=-10, result="GAIN",
                description="Fake punt ILLEGAL - already used this game! -10 yards",
            )

        self._fake_punt_used = True
        fac_card = deck.draw()
        rn = fac_card.run_num_int or random.randint(1, 12)

        if 1 <= rn <= 5:
            # Pass result
            yards = random.randint(5, 20)
            is_td = (yard_line + yards) >= 100
            if is_td:
                yards = 100 - yard_line
            return PlayResult(
                play_type="PASS", yards_gained=yards,
                result="TD" if is_td else "COMPLETE",
                is_touchdown=is_td,
                description=f"Fake punt! {punter.player_name} throws for {yards} yards! (RN {rn})",
                passer=punter.player_name,
                run_number_used=rn,
            )
        elif rn == 12:
            # Daylight run: PN × 2 yards
            pn = fac_card.pass_num_int or random.randint(1, 48)
            yards = pn * 2
            is_td = (yard_line + yards) >= 100
            if is_td:
                yards = 100 - yard_line
            return PlayResult(
                play_type="RUN", yards_gained=yards,
                result="TD" if is_td else "GAIN",
                is_touchdown=is_td,
                description=f"Fake punt! {punter.player_name} daylight run for {yards} yards! (RN {rn}, PN {pn})",
                rusher=punter.player_name,
                run_number_used=rn,
                pass_number_used=pn,
            )
        else:
            # RN 6-11: punter run results
            yards = random.randint(-2, 8)
            is_td = (yard_line + yards) >= 100
            if is_td:
                yards = 100 - yard_line
            return PlayResult(
                play_type="RUN", yards_gained=yards,
                result="TD" if is_td else "GAIN",
                is_touchdown=is_td,
                description=f"Fake punt! {punter.player_name} runs for {yards} yards (RN {rn})",
                rusher=punter.player_name,
                run_number_used=rn,
            )

    # ── Rule 24: FG Over 50 ─────────────────────────────────────────

    def resolve_field_goal_5e(self, distance: int,
                              kicker: PlayerCard) -> PlayResult:
        """Resolve a field goal with 5E over-50 rules (Rule 24).

        When distance > 50 yards:
          - Subtract 2 from the Good Range per yard over 50.
          - Maximum attempt distance is 55 yards.
        """
        if distance > 55:
            return PlayResult(
                play_type="FG", yards_gained=0,
                result="FG_NO_GOOD",
                description=f"{kicker.player_name} {distance}-yard FG attempt too far (max 55)",
            )

        fg_chart = kicker.fg_chart
        if distance < 20:
            rate = fg_chart.get("0-19", 0.99)
        elif distance < 30:
            rate = fg_chart.get("20-29", 0.95)
        elif distance < 40:
            rate = fg_chart.get("30-39", 0.88)
        elif distance < 50:
            rate = fg_chart.get("40-49", 0.78)
        elif distance < 60:
            rate = fg_chart.get("50-59", 0.62)
        else:
            rate = fg_chart.get("60+", 0.35)

        # Rule 24: Subtract 2 from good range per yard over 50
        if distance > 50:
            penalty = (distance - 50) * 2
            # Convert rate reduction: each point is roughly 1/48 of range
            rate = max(0.0, rate - penalty / 48.0)

        made = random.random() < rate
        return PlayResult(
            play_type="FG", yards_gained=0,
            result="FG_GOOD" if made else "FG_NO_GOOD",
            description=f"{kicker.player_name} {'makes' if made else 'misses'} {distance}-yard field goal",
        )

    # ── Rule 11: Dropped Passes ──────────────────────────────────────

    @staticmethod
    def check_dropped_pass(run_number: int, receiver: PlayerCard) -> bool:
        """Check if a completed pass is dropped (Rule 11).

        In 5E, when the RN equals the receiver's game-use rating,
        the pass is dropped (becomes incomplete).
        """
        game_use = getattr(receiver, 'endurance_rushing', None)
        if game_use is not None and game_use >= 3 and run_number == game_use:
            return True
        return False

    # ── Rule 5: Screen Pass Run Number Modifiers ─────────────────────

    @staticmethod
    def get_screen_run_modifier(defense_formation: str) -> int:
        """Return run number modifier for screen passes (Rule 5).

        .. deprecated::
            Callers should supply a ``DefensivePlay`` enum and use
            ``get_screen_rn_modifier_5e`` from ``play_types`` instead.

            Per 5E rules, screen run-number modifiers come from the defensive
            PLAY CALL, not from the formation name.  Without an explicit
            defensive play call the modifier is always 0.

        This legacy overload is kept for backward compatibility only.
        It always returns 0 regardless of the formation string.
        """
        return 0

    # ── Rule 14: Within-20 Completion Modifier (legacy) ────────────────

    @staticmethod
    def get_within_20_completion_modifier(yard_line: int) -> int:
        """Return completion range modifier when inside opponent's 20 (Rule 14).

        .. deprecated::
            Superseded by ``get_completion_modifier_5e(within_20=True)`` in
            play_types.py which provides per-defense/per-pass-type within-20
            modifiers matching the 5E rules PDF table.  Kept for backward
            compatibility with legacy tests.

        5E Rule: When inside the 20, Long passes have their completion
        range reduced by -5 (compressed field).
        """
        if yard_line >= 80:
            return -5
        return 0

    # ── Z Card Ignore Rules ──────────────────────────────────────────

    @staticmethod
    def should_ignore_z_card(play_context: str) -> bool:
        """Return True if Z cards should be ignored in this context.

        5E Rule: Z cards are ignored on:
          - Onside kicks
          - Extra points (XP)
          - Fumble recovery plays
          - Field goal attempts
          - After touchdowns
          - Incomplete passes (no fumble possible)
        """
        ignore_contexts = (
            "ONSIDE_KICK", "XP", "EXTRA_POINT",
            "FUMBLE_RECOVERY", "FG", "FIELD_GOAL",
            "TOUCHDOWN", "TD", "INCOMPLETE",
        )
        return play_context.upper() in ignore_contexts

    # ── Fumble Home Field Rule ───────────────────────────────────────

    @staticmethod
    def apply_fumble_home_field(is_home_team: bool, fumble_roll: int) -> str:
        """Apply 5E home field advantage on fumble recovery.

        The home team gets a +1 bonus on fumble recovery rolls.
        Roll is 1-8: 1-4 = OFFENSE recovers, 5-8 = DEFENSE.
        Home team bonus shifts the threshold.
        """
        if is_home_team:
            # Home team (offense) recovers on 1-5 instead of 1-4
            return "OFFENSE" if fumble_roll <= 5 else "DEFENSE"
        return "OFFENSE" if fumble_roll <= 4 else "DEFENSE"

    # ── Extra Pass Blocking (Optional Rule) ──────────────────────────

    @staticmethod
    def resolve_extra_pass_blocking(ol_pass_block_sum: int,
                                     dl_pass_rush_sum: int,
                                     extra_blocker_bv: int = 0) -> int:
        """Resolve extra pass blocking (Optional Rule).

        When a RB stays in to block, add their BV to the OL pass block sum.
        Returns the net pass rush modifier.
        """
        total_block = ol_pass_block_sum + extra_blocker_bv
        return (dl_pass_rush_sum - total_block) * 2

    # ── Endurance 3 & 4 Rules ────────────────────────────────────────

    def check_endurance_3_possession(self, player_name: str,
                                      used_this_possession: set) -> bool:
        """Check if a player with endurance 3 can be used (once per possession)."""
        return player_name not in used_this_possession

    def check_endurance_4_quarter(self, player_name: str,
                                   used_this_quarter: set) -> bool:
        """Check if a player with endurance 4 can be used (once per quarter)."""
        return player_name not in used_this_quarter

    # ── QB Endurance (A/B/C) ─────────────────────────────────────────

    @staticmethod
    def get_qb_endurance_modifier(qb: PlayerCard) -> int:
        """Return completion range modifier for QB endurance.

        5E QB Endurance:
          A = no penalty (workhorse)
          B = -2 to completion in 4th quarter
          C = -4 to completion in 4th quarter
        """
        endurance = getattr(qb, 'endurance_passing', 'A')
        if endurance == 'B':
            return -2
        if endurance == 'C':
            return -4
        return 0

    # ── Endurance on Check-off Passes ────────────────────────────────

    @staticmethod
    def get_checkoff_endurance_modifier(receiver: PlayerCard) -> int:
        """Return modifier for check-off passes to a receiver.

        5E Rule: Endurance affects check-off passes — if receiver has
        endurance >= 3, -3 to completion range on check-off.
        """
        endurance = getattr(receiver, 'endurance_rushing', 0)
        if endurance >= 3:
            return -3
        return 0

    # ── OL/CB/S Out of Position (5E Rule) ──────────────────────────

    # Natural box assignments for defensive positions (from 5E Display Layout):
    #   Row 1 (DL): A=LE, B=LDT, C=NT, D=RDT, E=RE — any DL/LB can play here
    #   Row 2 (LB): F=LOLB, G=LILB, H=MLB, I=RILB, J=ROLB
    #   Row 3 (DB): K=LCB, L=extra DB, M=FS, N=SS, O=RCB
    DB_NATURAL_BOXES = {
        'CB':  {'K', 'O'},        # CBs play corner boxes
        'FS':  {'M'},             # Free Safety in box M
        'SS':  {'N'},             # Strong Safety in box N
        'S':   {'M', 'N'},       # Generic safety in either safety box
        'DB':  {'K', 'L', 'M', 'N', 'O'},  # Generic DB in any Row 3 box
    }
    ROW1_BOXES = {'A', 'B', 'C', 'D', 'E'}
    ROW2_BOXES = {'F', 'G', 'H', 'I', 'J'}
    ROW3_BOXES = {'K', 'L', 'M', 'N', 'O'}

    # Natural slot positions for offensive linemen
    OL_NATURAL_SLOTS = {
        'LT': {'LT'},
        'LG': {'LG'},
        'C':  {'C', 'CN'},
        'RG': {'RG'},
        'RT': {'RT'},
    }

    @staticmethod
    def check_out_of_position_penalty(player: PlayerCard,
                                       assigned_position: str) -> int:
        """Return penalty for playing out of position (5E Rule).

        OL playing wrong slot: −1 to blocking value (BV).
        DB playing wrong box: −1 to pass defense rating (PDR).
        DL/LB may play any Row 1 box without modification.
        Any DB may play in Box L without modification.

        ``assigned_position`` can be a box letter (A-O) or a position name
        (DE, DT, CB, SS, FS, LT, RG, etc.).
        """
        natural_pos = getattr(player, 'position', '')

        # Exact match — always in position
        if natural_pos == assigned_position:
            return 0

        # ── DL/LB: can play any Row 1 position without penalty ──
        DL_LB = ('DE', 'DT', 'DL', 'NT', 'LB', 'OLB', 'ILB', 'MLB', 'EDGE')
        if natural_pos in DL_LB:
            if assigned_position in PlayResolver.ROW1_BOXES:
                return 0
            if assigned_position in DL_LB:
                return 0
            if natural_pos in ('LB', 'OLB', 'ILB', 'MLB'):
                if assigned_position in PlayResolver.ROW2_BOXES:
                    return 0
            return 0  # DL/LB are never penalized

        # ── DBs ──────────────────────────────────────────────────────
        DB_POSITIONS = ('CB', 'S', 'SS', 'FS', 'DB')
        if natural_pos in DB_POSITIONS:
            # Any DB may play in Box L without modification
            if assigned_position == 'L':
                return 0
            # Check if position name assigned matches natural position type
            # (e.g. CB assigned to 'CB' → OK, CB assigned to 'SS' → penalty)
            if assigned_position in DB_POSITIONS:
                # Same position type → OK
                if assigned_position == natural_pos:
                    return 0
                # Generic safety/DB can play either S/SS/FS
                if natural_pos == 'S' and assigned_position in ('SS', 'FS', 'S', 'DB'):
                    return 0
                if natural_pos == 'DB':
                    return 0  # Generic DB can play anywhere
                return -1  # DB in wrong DB position
            # Check box letter assignments
            natural_boxes = PlayResolver.DB_NATURAL_BOXES.get(natural_pos, set())
            if assigned_position in natural_boxes:
                return 0
            if assigned_position in PlayResolver.ROW3_BOXES:
                return -1  # DB in wrong Row 3 box
            if assigned_position in PlayResolver.ROW1_BOXES | PlayResolver.ROW2_BOXES:
                return -1  # DB moved to front rows
            return 0

        # ── OL ────────────────────────────────────────────────────────
        OL_POSITIONS = ('LT', 'LG', 'C', 'RG', 'RT')
        if natural_pos in OL_POSITIONS:
            natural_slots = PlayResolver.OL_NATURAL_SLOTS.get(natural_pos, set())
            if assigned_position in natural_slots:
                return 0
            # Any OL position or slot that doesn't match
            if assigned_position in OL_POSITIONS or assigned_position in ('CN', 'LT', 'LG', 'RG', 'RT'):
                return -1
            return -1  # OL out of position

        return 0

    # ── Display Box Tracking (5E Defensive Spatial Arrangement) ──────

    # 5E Display Layout:
    #   Row 1 (Defensive Line): Boxes A, B, C, D, E
    #   Row 2 (Linebackers):    Boxes F, G, H, I, J
    #   Row 3 (Defensive Backs): Boxes K, L, M, N, O
    # Rules:
    #   Row 1: 3-10 cards, 0-2 per box, only DE/DT/LB
    #   Row 2: 0-5 LBs, one per box (F-J)
    #   Row 3: 0-6 DBs, CB in K/O, FS in M, SS in N, Box L any DB

    DISPLAY_BOXES_ROW1 = ['A', 'B', 'C', 'D', 'E']
    DISPLAY_BOXES_ROW2 = ['F', 'G', 'H', 'I', 'J']
    DISPLAY_BOXES_ROW3 = ['K', 'L', 'M', 'N', 'O']

    @staticmethod
    def assign_default_display_boxes(defenders: list) -> Dict[str, str]:
        """Assign defenders to default Display box positions.

        Returns a dict mapping player_name -> box_letter.
        Follows 5E rules for Row 1/2/3 placement.

        Row 1 (DL) layout mirrors the field:
          A=LE, B=LDT, C=NT/C, D=RDT, E=RE (EDGE treated as DE)
        Row 2 (LB) layout:
          F=LOLB, G=LILB, H=MLB, I=RILB, J=ROLB
        Row 3 (DB) layout:
          K=LCB, L=extra DB, M=FS, N=SS, O=RCB
        """
        assignments: Dict[str, str] = {}
        dl_players = [d for d in defenders if getattr(d, 'position', '') in
                      ('DE', 'DT', 'DL', 'NT', 'EDGE')]
        lb_players = [d for d in defenders if getattr(d, 'position', '') in
                      ('LB', 'OLB', 'ILB', 'MLB')]
        db_players = [d for d in defenders if getattr(d, 'position', '') in
                      ('CB', 'S', 'SS', 'FS', 'DB')]

        # Row 1: DL players by position — DEs on edges (A/E), DTs inside (B/D), NT center (C)
        des = [d for d in dl_players if getattr(d, 'position', '') in ('DE', 'EDGE')]
        dts = [d for d in dl_players if getattr(d, 'position', '') in ('DT', 'DL')]
        nts = [d for d in dl_players if getattr(d, 'position', '') == 'NT']

        # Assign DEs to edge boxes (A, E)
        if len(des) >= 1:
            assignments[des[0].player_name] = 'A'
        if len(des) >= 2:
            assignments[des[1].player_name] = 'E'

        # Assign NTs to center box (C)
        if nts:
            assignments[nts[0].player_name] = 'C'

        # Assign DTs to inside boxes (B, D)
        dt_boxes = ['B', 'D']
        dt_idx = 0
        for dt in dts:
            if dt.player_name not in assignments:
                while dt_idx < len(dt_boxes) and dt_boxes[dt_idx] in assignments.values():
                    dt_idx += 1
                if dt_idx < len(dt_boxes):
                    assignments[dt.player_name] = dt_boxes[dt_idx]
                    dt_idx += 1

        # Fill remaining DL to first empty Row 1 box
        for p in dl_players:
            if p.player_name not in assignments:
                for box in ['A', 'B', 'C', 'D', 'E']:
                    if box not in assignments.values():
                        assignments[p.player_name] = box
                        break

        # Row 2: LBs by position — OLBs on edges (F/J), ILBs inside (G/I), MLB center (H)
        olbs = [d for d in lb_players if getattr(d, 'position', '') == 'OLB']
        ilbs = [d for d in lb_players if getattr(d, 'position', '') == 'ILB']
        mlbs = [d for d in lb_players if getattr(d, 'position', '') == 'MLB']
        generic_lbs = [d for d in lb_players if getattr(d, 'position', '') == 'LB']

        if len(olbs) >= 1:
            assignments[olbs[0].player_name] = 'F'
        if len(olbs) >= 2:
            assignments[olbs[1].player_name] = 'J'
        if mlbs:
            assignments[mlbs[0].player_name] = 'H'
        lb_inner = ['G', 'I']
        lb_idx = 0
        for ilb in ilbs:
            if ilb.player_name not in assignments:
                while lb_idx < len(lb_inner) and lb_inner[lb_idx] in assignments.values():
                    lb_idx += 1
                if lb_idx < len(lb_inner):
                    assignments[ilb.player_name] = lb_inner[lb_idx]
                    lb_idx += 1

        # Fill generic LBs to first empty Row 2 box
        for p in generic_lbs + olbs[2:] + ilbs + mlbs[1:]:
            if p.player_name not in assignments:
                for box in ['F', 'G', 'H', 'I', 'J']:
                    if box not in assignments.values():
                        assignments[p.player_name] = box
                        break

        # Row 3: DBs to boxes K-O following position rules
        # CB→K/O, FS→M, SS→N, any DB→L
        cbs = [d for d in db_players if getattr(d, 'position', '') == 'CB']
        safeties = [d for d in db_players if getattr(d, 'position', '') in ('S', 'SS', 'FS')]
        other_dbs = [d for d in db_players if d not in cbs and d not in safeties]

        if len(cbs) >= 1:
            assignments[cbs[0].player_name] = 'K'
        if len(cbs) >= 2:
            assignments[cbs[1].player_name] = 'O'
        for s in safeties:
            pos = getattr(s, 'position', '')
            if pos == 'FS' and 'M' not in assignments.values():
                assignments[s.player_name] = 'M'
            elif pos == 'SS' and 'N' not in assignments.values():
                assignments[s.player_name] = 'N'
            elif pos == 'S':
                # Generic safety: try FS (M) first, then SS (N), then L
                if 'M' not in assignments.values():
                    assignments[s.player_name] = 'M'
                elif 'N' not in assignments.values():
                    assignments[s.player_name] = 'N'
                elif 'L' not in assignments.values():
                    assignments[s.player_name] = 'L'
            elif 'L' not in assignments.values():
                # FS/SS whose preferred box is taken — fall back to DB slot (L)
                assignments[s.player_name] = 'L'
        for db in (other_dbs + cbs[2:]):
            if db.player_name in assignments:
                continue
            for box in ['L', 'M', 'N']:
                if box not in assignments.values():
                    assignments[db.player_name] = box
                    break

        return assignments

    @staticmethod
    def assign_defenders_to_boxes_multi(defenders: list) -> Dict[str, List[str]]:
        """Like assign_default_display_boxes but returns box → list of player names.

        Extra DL beyond the five Row-1 slots (A-E) overflow into the interior
        boxes (B, D, C in that order), modelling a goal-line or short-yardage
        stack where a second defender is packed into a gap.
        """
        primary: Dict[str, str] = PlayResolver.assign_default_display_boxes(defenders)
        result: Dict[str, List[str]] = {}
        for name, box in primary.items():
            result.setdefault(box, []).append(name)

        # Identify DL players not assigned to any box (overflow)
        _DL_POSITIONS = {'DE', 'DT', 'DL', 'NT', 'EDGE'}
        assigned_names = set(primary.keys())
        overflow_dl = [
            d for d in defenders
            if getattr(d, 'position', '') in _DL_POSITIONS
            and d.player_name not in assigned_names
        ]
        # Overflow DL go into inner line boxes B, D, C (gap-stuffing priority)
        _OVERFLOW_BOXES = ['B', 'D', 'C']
        for i, dl in enumerate(overflow_dl):
            if i < len(_OVERFLOW_BOXES):
                result.setdefault(_OVERFLOW_BOXES[i], []).append(dl.player_name)

        return result

    # ── Pass Defense Box Assignments (5E) ────────────────────────────

    # Per 5E rules, pass defense assignments are:
    #   RE (Right End) → Box N
    #   LE (Left End) → Box K
    #   FL#1 → Box O
    #   FL#2 → Box M
    #   BK#1 → Box F
    #   BK#2 → Box J
    #   BK#3 → Box H

    PASS_DEFENSE_ASSIGNMENTS = {
        'RE': 'N',    # Right End → Box N (typically SS)
        'LE': 'K',    # Left End → Box K (typically LCB)
        'FL1': 'O',   # Flanker #1 → Box O (typically RCB)
        'FL2': 'M',   # Flanker #2 → Box M (typically FS)
        'FL': 'O',    # Alias: FL → same as FL1 (RCB)
        'BK1': 'F',   # Back #1 → Box F (typically LOLB)
        'BK2': 'J',   # Back #2 → Box J (typically ROLB)
        'BK3': 'H',   # Back #3 → Box H (typically MLB)
    }

    # Map from compacted receiver list index to receiver slot name.
    # Standard formation: [0]=FL, [1]=LE, [2]=RE, [3]=BK1, [4]=BK2
    # 3RB formation (FL absent): [0]=LE, [1]=RE, [2]=BK1, [3]=BK2, [4]=BK3
    # NOTE: index-based slot lookups are unreliable when slots are absent.
    # Always prefer the _formation_slot attribute on each PlayerCard (set by
    # _get_all_receivers) for slot-name based operations.
    RECEIVER_INDEX_TO_SLOT = {
        0: 'FL',
        1: 'LE',
        2: 'RE',
        3: 'BK1',
        4: 'BK2',
        5: 'BK3',
    }

    @staticmethod
    def get_pass_defender_for_receiver(receiver_slot: str,
                                       box_assignments: Dict[str, str]) -> Optional[str]:
        """Return the defender name guarding the given receiver slot.

        receiver_slot: 'RE', 'LE', 'FL1', 'FL2', 'BK1', 'BK2', 'BK3'
        box_assignments: dict mapping player_name → box_letter
        """
        target_box = PlayResolver.PASS_DEFENSE_ASSIGNMENTS.get(receiver_slot)
        if not target_box:
            return None
        # Find defender in that box
        for name, box in box_assignments.items():
            if box == target_box:
                return name
        return None  # Empty box → +5 to completion range per 5E rules

    @staticmethod
    def get_covering_defender(receiver_slot: str,
                              defenders_by_box: Dict[str, 'PlayerCard']) -> Optional['PlayerCard']:
        """Return the PlayerCard of the defender covering the given receiver slot.

        receiver_slot: 'RE', 'LE', 'FL', 'FL1', 'FL2', 'BK1', 'BK2', 'BK3'
        defenders_by_box: dict mapping box_letter → PlayerCard
        """
        target_box = PlayResolver.PASS_DEFENSE_ASSIGNMENTS.get(receiver_slot)
        if not target_box:
            return None
        return defenders_by_box.get(target_box)

    @staticmethod
    def build_offensive_personnel(receivers: List[PlayerCard],
                                  backs_blocking: Optional[List[int]] = None) -> Dict[str, Optional[PlayerCard]]:
        """Build a position slot → PlayerCard mapping for the current play.

        Uses the ``_formation_slot`` attribute set on each card by
        ``_get_all_receivers`` so that the mapping is correct even when FL is
        absent (e.g. 3RB formation where LE=WR1, RE=TE, BK1/BK2/BK3=RBs).

        backs_blocking: list of receiver indices (e.g. [3, 4]) for backs
                        staying in to block instead of running routes.

        Returns dict with keys: 'FL', 'LE', 'RE', 'BK1', 'BK2', 'BK3'
        → PlayerCard or None.
        """
        blocking = set(backs_blocking or [])
        # Initialise all known slots to None
        personnel: Dict[str, Optional[PlayerCard]] = {
            slot: None for slot in PlayResolver.RECEIVER_INDEX_TO_SLOT.values()
        }
        for i, rec in enumerate(receivers):
            if i not in blocking:
                slot = getattr(rec, '_formation_slot',
                               PlayResolver.RECEIVER_INDEX_TO_SLOT.get(i))
                if slot:
                    personnel[slot] = rec
        return personnel

    @staticmethod
    def get_receiver_slot(receiver: PlayerCard,
                          receivers: List[PlayerCard]) -> Optional[str]:
        """Return the slot name ('FL', 'LE', 'RE', 'BK1', 'BK2', 'BK3') for a receiver.

        Uses the ``_formation_slot`` attribute set on each card by
        ``_get_all_receivers`` so that the correct slot name is returned even
        when slots are absent (e.g. FL missing in a 3RB formation).
        """
        for rec in receivers:
            if rec is receiver or rec.player_name == receiver.player_name:
                # Prefer the authoritative slot attribute; fall back to index
                # mapping only when the attribute is absent (legacy callers).
                slot = getattr(rec, '_formation_slot', None)
                if slot:
                    return slot
                return PlayResolver.RECEIVER_INDEX_TO_SLOT.get(receivers.index(rec))
        return None

    # ── FL#1/FL#2 Flanker Designation System (5E) ────────────────────

    # Per 5E rules:
    #   If 3 RBs on display → no flanker (all 3 backs in BK slots, LE/RE on line)
    #   If 2 RBs → 1 WR is designated as flanker (FL#1)
    #   If 1 RB → WR or TE is designated as FL#2
    #   FAC "flanker" always means FL#1

    @staticmethod
    def designate_flankers(rbs_on_display: int,
                           wrs: list,
                           tes: list,
                           rbs: list) -> Dict[str, str]:
        """Designate FL#1 and FL#2 based on RBs on display.

        Returns dict: {'FL1': player_name, 'FL2': player_name}
        """
        result: Dict[str, str] = {}

        if rbs_on_display >= 3:
            # 3 RBs: all backs in BK1/BK2/BK3; no flanker (LE and RE are on
            # the line as the two ends).  7-man line = 5 OL + LE + RE. ✓
            pass
        elif rbs_on_display == 2:
            # 2 RBs: first available WR is FL#1
            if wrs:
                result['FL1'] = wrs[0].player_name
        elif rbs_on_display <= 1:
            # 1 RB: WR or TE is FL#2
            if len(wrs) >= 2:
                result['FL2'] = wrs[1].player_name
            elif tes:
                result['FL2'] = tes[0].player_name

        return result

    # ── Injury Protection for Backup Players (5E) ────────────────────

    @staticmethod
    def check_injury_protection(player_name: str,
                                 is_backup: bool,
                                 starter_injured: bool) -> bool:
        """Check if a backup player has injury protection.

        Per 5E rules: If starter lost to injury, backup plays injury-free
        until starter is eligible to return.

        Returns True if the backup is injury-protected.
        """
        return is_backup and starter_injured

    # ── Asterisked Punt Returns (5E) ─────────────────────────────────

    @staticmethod
    def resolve_asterisked_return(base_yards: int,
                                   asterisk_yards: int,
                                   deck: 'FACDeck') -> int:
        """Resolve asterisked punt return per 5E rules.

        Flip new FAC:
          RN 1-2 = use asterisked yardage
          RN 3-12 = use original (base) yardage
        """
        fac = deck.draw()
        rn = fac.run_num_int or random.randint(1, 12)
        if 1 <= rn <= 2:
            return asterisk_yards
        return base_yards

    # ── Spot of Foul for Pass Interference (5E) ──────────────────────

    @staticmethod
    def calculate_spot_of_foul(pass_type: str,
                                run_number: int,
                                yard_line: int) -> int:
        """Calculate spot of foul for pass interference.

        Per 5E rules: Determined same way as Point of Interception.
          Screen = RN ÷ 2
          Quick = RN
          Short = RN × 2
          Long = RN × 4

        Returns the yard line where the foul occurred.
        """
        rn = max(1, min(12, run_number))
        ptype = pass_type.upper()
        if ptype == 'SCREEN':
            distance = max(1, rn // 2)
        elif ptype in ('QUICK', 'QUICK_PASS'):
            distance = rn
        elif ptype in ('SHORT', 'SHORT_PASS'):
            distance = rn * 2
        elif ptype in ('LONG', 'LONG_PASS'):
            distance = rn * 4
        else:
            distance = rn * 2  # Default to short pass formula

        spot = min(99, yard_line + distance)
        return spot

    # ── Clipping Spot Penalty (5E) ───────────────────────────────────

    @staticmethod
    def calculate_clipping_spot(run_number: int,
                                 return_yards: int,
                                 yard_line: int) -> int:
        """Calculate spot of clipping penalty per 5E rules.

        New FAC drawn:
          Odd RN = halfway point of return
          Even RN = where return ended
        """
        if run_number % 2 == 1:
            # Odd: halfway point of the return
            clip_spot = yard_line + (return_yards // 2)
        else:
            # Even: where the return ended
            clip_spot = yard_line + return_yards
        return min(99, max(1, clip_spot))

    # ── TE/WR Blocking Value Differentiation (5E) ────────────────────

    # Per 5E player card creation rules:
    #   TE blocking: 4 (all-pro) to 1 (minimum)
    #   WR blocking: +2 to -3 (negative = bad blocker)
    # These are already stored in the `blocks` field on PlayerCard.
    # This method validates/classifies them for display purposes.

    @staticmethod
    def classify_blocking_value(player: PlayerCard) -> str:
        """Classify a player's blocking value for display.

        Returns a human-readable label: 'Elite', 'Good', 'Average', 'Poor', 'Liability'
        """
        bv = getattr(player, 'blocks', 0)
        pos = getattr(player, 'position', '').upper()

        if pos == 'TE':
            if bv >= 4:
                return 'Elite'
            elif bv >= 3:
                return 'Good'
            elif bv >= 2:
                return 'Average'
            else:
                return 'Below Average'
        elif pos == 'WR':
            if bv >= 2:
                return 'Good'
            elif bv >= 0:
                return 'Average'
            elif bv >= -1:
                return 'Poor'
            else:
                return 'Liability'
        else:
            if bv >= 3:
                return 'Good'
            elif bv >= 0:
                return 'Average'
            else:
                return 'Poor'

    # ── Fumble Team Ratings (5E) ─────────────────────────────────────

    # Per 5E rules, teams have a "Fumbles Lost" range (e.g., 1-21)
    # and a Defensive Fumble Adjustment. When a fumble occurs:
    #   - Draw FAC, get PN (1-48)
    #   - If PN falls within team's Fumbles Lost range → fumble lost
    #   - Defensive Fumble Adjustment modifies the range
    #   - Home field gives +1 bonus (already implemented)

    @staticmethod
    def resolve_fumble_with_team_rating(fumble_pn: int,
                                         fumbles_lost_max: int = 21,
                                         def_fumble_adj: int = 0,
                                         is_home: bool = False) -> bool:
        """Resolve fumble recovery using team ratings per 5E rules.

        Args:
            fumble_pn: Pass Number drawn from FAC (1-48)
            fumbles_lost_max: Team's Fumbles Lost upper range (e.g., 21 means 1-21)
            def_fumble_adj: Defensive Fumble Adjustment (positive = defense recovers more)
            is_home: Whether ball carrier is on home team (home gets +1)

        Returns True if fumble is LOST (defense recovers).
        """
        adjusted_max = fumbles_lost_max + def_fumble_adj
        if is_home:
            adjusted_max -= 1  # Home team bonus: harder to lose fumble

        adjusted_max = max(0, min(48, adjusted_max))
        return 1 <= fumble_pn <= adjusted_max

    # ── Blitz Procedure Tracking (5E) ────────────────────────────────

    # Per 5E rules, when blitz is announced:
    #   - Remove 2-5 LBs/DBs from Display before play
    #   - Blitzing players have Pass Rush Value of 2 (already implemented)
    #   - After play, restore removed players to Display

    @staticmethod
    def get_blitz_removals(pn: int) -> list:
        """Determine which defensive boxes to remove players from for blitz.

        Per 5E solitaire rules:
          PN 1-26:  Remove F + J
          PN 27-35: Remove F + J + M
          PN 36-48: Remove F + G + H + I + J
        """
        if 1 <= pn <= 26:
            return ['F', 'J']
        elif 27 <= pn <= 35:
            return ['F', 'J', 'M']
        elif 36 <= pn <= 48:
            return ['F', 'G', 'H', 'I', 'J']
        return ['F', 'J']  # Default
