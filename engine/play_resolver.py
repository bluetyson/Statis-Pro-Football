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

  Legacy (pre-5th-ed) resolution still supported via the old resolve_*
  methods when DiceResult objects are passed.

Defence ratings (pass_rush, coverage, run_stop) are wired into
resolution via effective_* helpers from ``fac_distributions``.
"""
import random
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from .player_card import PlayerCard, RECEIVER_LETTERS
from .fast_action_dice import DiceResult, PlayTendency
from .fac_deck import FACCard, FACDeck
from .charts import Charts
from .fac_distributions import (
    effective_pass_rush, effective_coverage, effective_run_stop,
    ZCardTrigger, lookup_z_card_event,
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
    debug_log: List[str] = field(default_factory=list)  # Step-by-step resolution log


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

    def resolve_sneak(self, qb: PlayerCard, deck: FACDeck) -> PlayResult:
        """Resolve a QB Sneak strategy.

        5E Rules: Inside run to QB; flip FAC; even PN = +1 yard, odd PN = 0.
        """
        fac_card = deck.draw()
        pn = fac_card.pass_num_int or random.randint(1, 48)
        yards = 1 if pn % 2 == 0 else 0
        return PlayResult(
            play_type="RUN", yards_gained=yards, result="GAIN",
            description=f"{qb.player_name} sneaks for {yards} yard{'s' if yards != 1 else ''} (Sneak)",
            rusher=qb.player_name, strategy="SNEAK",
            pass_number_used=pn,
        )

    def resolve_draw(self, fac_card: FACCard, deck: FACDeck,
                     rusher: PlayerCard, defense_formation: str,
                     defense_run_stop: int = 0) -> PlayResult:
        """Resolve a Draw Play strategy.

        5E Rules: Inside run to any back/QB.
          vs Run Defense: +2 to Run Number (in addition to normal modifiers)
          vs Pass/Prevent: -2 to Run Number
          vs Blitz: -4 to Run Number
        """
        # Draw play modifier
        draw_mod = 0
        form_lower = defense_formation.lower()
        if "blitz" in form_lower or form_lower == "blz":
            draw_mod = -4
        elif form_lower in ("pass", "4_3_cover2", "nickel_zone", "nickel_cover2",
                            "prevent", "3_4_zone"):
            draw_mod = -2
        else:
            draw_mod = 2  # vs Run Defense

        # Resolve as inside run with draw modifier applied to RN
        result = self.resolve_run_5e(
            fac_card, deck, rusher, "IL",
            defense_run_stop=defense_run_stop,
            defense_formation=defense_formation,
        )
        # Apply draw RN modifier to yards (approximation: each RN point ≈ 1 yard)
        result.yards_gained += draw_mod
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
                            defenders: Optional[List[PlayerCard]] = None) -> PlayResult:
        """Resolve a Play-Action pass strategy.

        5E Rules: Short/Long pass only.
          vs Run Defense: +5 to completion range
          vs Pass Defense: -5 to completion range
          vs Prevent: -10 to completion range
        """
        # Play-action modifier to completion range
        pa_mod = 0
        form_lower = defense_formation.lower()
        if "blitz" in form_lower:
            pa_mod = 0
        elif form_lower in ("4_3", "3_4"):
            pa_mod = 5  # vs Run Defense
        elif form_lower in ("4_3_cover2", "nickel_zone", "nickel_cover2"):
            pa_mod = -5  # vs Pass Defense
        elif "prevent" in form_lower or form_lower == "3_4_zone":
            pa_mod = -10  # vs Prevent Defense
        else:
            pa_mod = 5  # default vs Run

        # Adjust defense coverage for play-action effect
        adjusted_coverage = max(0, defense_coverage - pa_mod)

        result = self.resolve_pass_5e(
            fac_card, deck, qb, receiver, receivers,
            pass_type=pass_type,
            defense_coverage=adjusted_coverage,
            defense_pass_rush=defense_pass_rush,
            defense_formation=defense_formation,
            defensive_strategy=defensive_strategy,
            defenders=defenders,
            two_minute_offense=False,  # Play-action not affected by two-minute restrictions
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

    def resolve_squib_kick(self, deck: FACDeck) -> PlayResult:
        """Resolve a squib kick per 5E rules.

        Normal kickoff + 15 yards to return start + 1 to return Run Number (12 stays 12).
        """
        result = self.resolve_kickoff()
        if result.result == "TOUCHBACK":
            # Squib kicks are less likely to reach end zone
            result.result = "GAIN"
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
        """Return run-number modifier based on defensive formation (Rule 1).

        Run Defense / Key on Ball Carrier: +4
        Run Defense / No Key:              +2
        Run Defense / Wrong Key:            0
        Pass/Prevent Defense:               0
        Blitz Defense:                      0

        Callers must explicitly set is_key_on_bc or is_no_key to activate
        the run-defense keying modifiers.  Without either flag the default
        is 'wrong key' (0).
        """
        form = defense_formation.lower() if defense_formation else ""
        pass_forms = ("pass", "4_3_cover2", "nickel_zone", "nickel_cover2",
                      "prevent", "3_4_zone")
        if "blitz" in form or form == "blz":
            return 0
        if form in pass_forms or "prevent" in form:
            return 0
        # Run defense formations (4_3, 3_4, goal_line, etc.)
        if is_key_on_bc:
            return 4
        if is_no_key:
            return 2
        # Default: wrong key → 0
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

    # ── Z-card helper ────────────────────────────────────────────────

    def _check_z_card(self, dice: DiceResult,
                      down: int = 0, distance: int = 0,
                      yard_line: int = 0, quarter: int = 0,
                      time_remaining: int = 900,
                      is_offense: bool = True) -> Optional[Dict[str, Any]]:
        """Check for a Z-card event and return it if triggered."""
        if ZCardTrigger.is_triggered(
            dice.tens, dice.ones,
            down=down, distance=distance,
            yard_line=yard_line, quarter=quarter,
            time_remaining=time_remaining,
        ):
            z_dice_tens = random.randint(1, 8)
            z_dice_ones = random.randint(1, 8)
            event = lookup_z_card_event(z_dice_tens, z_dice_ones, is_offense)
            if event["event"] != "NO_EFFECT":
                return event
        return None

    # ── Run resolution ───────────────────────────────────────────────

    def resolve_run(self, dice: DiceResult, rusher: PlayerCard,
                    play_direction: str = "MIDDLE",
                    defense_run_stop: int = 0,
                    defense_formation: str = "4_3",
                    down: int = 0, distance: int = 0,
                    yard_line: int = 0, quarter: int = 0,
                    time_remaining: int = 900) -> PlayResult:
        slot = dice.slot

        # Effective run-stop with formation modifier
        eff_run_stop = effective_run_stop(defense_run_stop, defense_formation)

        if play_direction in ("LEFT", "MIDDLE"):
            column = rusher.inside_run
        else:
            column = rusher.outside_run

        if not column:
            yards = random.choices([-2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8],
                                   weights=[2, 3, 5, 8, 10, 12, 12, 10, 8, 5, 3])[0]
            result_type = "GAIN"
            is_td = random.random() < 0.03
        else:
            play_data = column.get(slot, {"result": "GAIN", "yards": 2, "td": False})
            result_type = play_data.get("result", "GAIN")
            yards = play_data.get("yards", 0)
            is_td = play_data.get("td", False)

        # Defense run-stop modifier: authentic 5E small-number scale
        if result_type in ("GAIN", "OOB"):
            yards = max(-5, int(yards - eff_run_stop))
            # High tackle rating can force TFL
            if eff_run_stop >= 3 and random.random() < 0.15:
                yards = min(yards, random.choice([-2, -1, 0]))
            # High tackle rating can force fumble
            if eff_run_stop >= 3 and result_type == "GAIN" and random.random() < 0.03:
                result_type = "FUMBLE"

        # Z-card check
        z_event = self._check_z_card(
            dice, down=down, distance=distance,
            yard_line=yard_line, quarter=quarter,
            time_remaining=time_remaining, is_offense=True,
        )

        # OOB result
        if result_type == "OOB":
            desc = f"{rusher.player_name} runs {play_direction.lower()} for {yards} yards, out of bounds"
            return PlayResult(
                play_type="RUN", yards_gained=yards,
                result="OOB", out_of_bounds=True,
                description=desc, rusher=rusher.player_name,
                z_card_event=z_event,
            )

        if result_type == "FUMBLE":
            recovery = Charts.roll_fumble_recovery()
            fumble_yards, fumble_td = Charts.roll_fumble_return()
            is_turnover = recovery == "DEFENSE"
            if is_turnover and fumble_td:
                return PlayResult(
                    play_type="RUN", yards_gained=-fumble_yards,
                    result="FUMBLE_TD", is_touchdown=False,
                    turnover=True, turnover_type="FUMBLE",
                    description=f"{rusher.player_name} fumbles! Returned for TD!",
                    rusher=rusher.player_name, z_card_event=z_event,
                )
            return PlayResult(
                play_type="RUN", yards_gained=yards,
                result="FUMBLE", turnover=is_turnover,
                turnover_type="FUMBLE" if is_turnover else None,
                description=(
                    f"{rusher.player_name} fumbles! "
                    f"{'Defense recovers!' if is_turnover else 'Offense recovers.'}"
                ),
                rusher=rusher.player_name, z_card_event=z_event,
            )

        penalty_info = None
        if dice.penalty_check:
            penalty_info = Charts.roll_penalty_chart()

        desc = f"{rusher.player_name} runs {play_direction.lower()}"
        if is_td:
            desc += " for a TOUCHDOWN!"
        elif result_type == "GAIN":
            desc += f" for {yards} yard{'s' if yards != 1 else ''}"

        return PlayResult(
            play_type="RUN",
            yards_gained=yards,
            result="TD" if is_td else result_type,
            is_touchdown=is_td,
            penalty=penalty_info,
            description=desc,
            rusher=rusher.player_name,
            z_card_event=z_event,
        )

    # ── Two-stage pass resolution ────────────────────────────────────

    def resolve_pass(self, dice: DiceResult, qb: PlayerCard,
                     receiver: PlayerCard, pass_length: str = "SHORT",
                     defense_coverage: int = 0,
                     defense_pass_rush: int = 0,
                     defense_formation: str = "4_3",
                     is_blitz_tendency: bool = False,
                     down: int = 0, distance: int = 0,
                     yard_line: int = 0, quarter: int = 0,
                     time_remaining: int = 900) -> PlayResult:
        slot = dice.slot

        # Effective ratings with formation + blitz
        eff_pass_rush = effective_pass_rush(
            defense_pass_rush, defense_formation, is_blitz_tendency,
        )
        eff_coverage = effective_coverage(
            defense_coverage, defense_formation, is_blitz_tendency,
        )

        # ── Stage 0: Pass-rush check (before QB card lookup) ────────
        # Authentic 5E: pass rush value 0-3, higher = more dangerous
        sack_chance = eff_pass_rush * 0.08  # 0→0%, 1→8%, 2→16%, 3→24%
        if sack_chance > 0 and random.random() < sack_chance:
            loss = random.choice([-3, -4, -5, -6, -7, -8])
            z_event = self._check_z_card(
                dice, down=down, distance=distance,
                yard_line=yard_line, quarter=quarter,
                time_remaining=time_remaining, is_offense=False,
            )
            return PlayResult(
                play_type="PASS", yards_gained=loss,
                result="SACK",
                description=f"{qb.player_name} is sacked for {abs(loss)} yard loss! (Pass rush pressure)",
                passer=qb.player_name, z_card_event=z_event,
            )

        # ── Stage 1: PN → QB card → pass result ─────────────────────
        if pass_length == "SHORT":
            qb_column = qb.short_pass
            rec_column = receiver.short_reception
        elif pass_length == "SCREEN":
            qb_column = qb.screen_pass
            rec_column = receiver.short_reception
        else:
            qb_column = qb.long_pass
            rec_column = receiver.long_reception

        if not qb_column:
            comp = random.random() < 0.62
            yards = random.randint(5, 15) if comp else 0
            result_type = "COMPLETE" if comp else "INCOMPLETE"
            is_td = comp and random.random() < 0.05
        else:
            qb_data = qb_column.get(slot, {"result": "INCOMPLETE", "yards": 0, "td": False})
            result_type = qb_data.get("result", "INCOMPLETE")
            yards = qb_data.get("yards", 0)
            is_td = qb_data.get("td", False)

        # ── Stage 2: If COMPLETE → RN → Receiver card → yards/catch ─
        if result_type == "COMPLETE" and rec_column:
            rec_data = rec_column.get(slot, {"result": "CATCH", "yards": yards, "td": is_td})
            if rec_data.get("result") == "INCOMPLETE":
                result_type = "INCOMPLETE"
                yards = 0
                is_td = False
            else:
                # Receiver card provides yardage (use max of QB/WR for realism)
                rec_yards = rec_data.get("yards", yards)
                if rec_yards > 0:
                    yards = max(yards, rec_yards)
                rec_td = rec_data.get("td", False)
                is_td = is_td or rec_td

        # ── Coverage modifier (authentic 5E: pass_defense −2 to +4) ──
        # Positive coverage reduces yards, negative increases them
        if result_type == "COMPLETE":
            cov_shift = eff_coverage  # Direct yard shift
            yards = max(0, yards - cov_shift)
            # High coverage can convert completion → incompletion
            if eff_coverage >= 3 and random.random() < 0.10:
                result_type = "INCOMPLETE"
                yards = 0
                is_td = False
            # Very high coverage can convert completion → INT (tipped ball)
            elif eff_coverage >= 4 and random.random() < 0.03:
                result_type = "INT"
                yards = 0
                is_td = False

        # Z-card check
        z_event = self._check_z_card(
            dice, down=down, distance=distance,
            yard_line=yard_line, quarter=quarter,
            time_remaining=time_remaining,
            is_offense=(result_type != "INT"),
        )

        if result_type == "INT":
            int_yards, int_td = Charts.roll_int_return()
            return PlayResult(
                play_type="PASS", yards_gained=0,
                result="INT", turnover=True, turnover_type="INT",
                description=(
                    f"{qb.player_name} pass intercepted!"
                    f"{'Returned for TD!' if int_td else f' Returned {int_yards} yards.'}"
                ),
                passer=qb.player_name, receiver=receiver.player_name,
                z_card_event=z_event,
            )

        if result_type == "SACK":
            return PlayResult(
                play_type="PASS", yards_gained=yards,
                result="SACK",
                description=f"{qb.player_name} is sacked for {abs(yards)} yard loss!",
                passer=qb.player_name, z_card_event=z_event,
            )

        penalty_info = None
        if dice.penalty_check:
            penalty_info = Charts.roll_penalty_chart()

        if result_type == "COMPLETE":
            desc = f"{qb.player_name} completes to {receiver.player_name}"
            if is_td:
                desc += " for a TOUCHDOWN!"
            else:
                desc += f" for {yards} yard{'s' if yards != 1 else ''}"
        else:
            desc = f"{qb.player_name} pass intended for {receiver.player_name} - INCOMPLETE"

        return PlayResult(
            play_type="PASS",
            yards_gained=yards,
            result="TD" if is_td else result_type,
            is_touchdown=is_td,
            penalty=penalty_info,
            description=desc,
            passer=qb.player_name,
            receiver=receiver.player_name,
            z_card_event=z_event,
        )

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

    # ── Punt (slot-based) ────────────────────────────────────────────

    @staticmethod
    def _returner_modifier(returner: Optional[PlayerCard], kind: str) -> int:
        if returner is None:
            return 0
        stats = returner.stats_summary or {}
        grade_bonus = {"A+": 2, "A": 2, "B": 1, "C": 0, "D": -1}.get(returner.overall_grade, 0)
        # Use rushing efficiency and receiving explosiveness as lightweight return proxies.
        ypc_bonus = round(
            (float(stats.get("ypc", PlayResolver.RETURN_BASE_YPC)) - PlayResolver.RETURN_BASE_YPC)
            * (PlayResolver.PUNT_RETURN_YPC_WEIGHT if kind == "PR" else PlayResolver.KICK_RETURN_YPC_WEIGHT)
        )
        rec_bonus = round(
            (float(stats.get("avg_yards", PlayResolver.RETURN_BASE_REC_YARDS)) - PlayResolver.RETURN_BASE_REC_YARDS)
            / (PlayResolver.PUNT_RETURN_REC_DIVISOR if kind == "PR" else PlayResolver.KICK_RETURN_REC_DIVISOR)
        )
        position_bonus = 1 if returner.position.upper() in ("RB", "WR", "CB", "S", "SS", "FS", "DB") else 0
        modifier = grade_bonus + ypc_bonus + rec_bonus + position_bonus
        return max(-2, min(6, modifier))

    def resolve_punt(self, punter: PlayerCard,
                     dice: Optional[DiceResult] = None,
                     returner: Optional[PlayerCard] = None) -> PlayResult:
        # Use slot-based punt column if available
        if punter.punt_column and dice is not None:
            slot = dice.slot
            punt_data = punter.punt_column.get(
                slot, {"result": "NORMAL", "yards": int(punter.avg_distance), "td": False},
            )
            punt_result = punt_data.get("result", "NORMAL")

            if punt_result == "INSIDE_20":
                distance = random.randint(
                    max(30, int(punter.avg_distance - 5)),
                    int(punter.avg_distance + 5),
                )
                return PlayResult(
                    play_type="PUNT",
                    yards_gained=distance,
                    result="PUNT",
                    description=f"{punter.player_name} punts {distance} yards, downed inside the 20",
                )
            elif punt_result == "TOUCHBACK":
                distance = random.randint(
                    int(punter.avg_distance + 5),
                    int(punter.avg_distance + 15),
                )
                return PlayResult(
                    play_type="PUNT",
                    yards_gained=distance,
                    result="PUNT",
                    description=f"{punter.player_name} punts {distance} yards, touchback",
                )
            else:
                distance = punt_data.get("yards", int(punter.avg_distance))
                fair_catch = Charts.check_fair_catch(punter.punt_return_pct)
                return_yards = 0 if fair_catch else max(
                    0, Charts.roll_punt_return() + self._returner_modifier(returner, "PR")
                )
                desc = f"{punter.player_name} punts {distance} yards"
                if fair_catch:
                    desc += f", fair catch by {returner.player_name}" if returner else ", fair catch"
                elif return_yards > 0:
                    desc += (
                        f", {returner.player_name} returns it {return_yards} yards"
                        if returner else f", returned {return_yards} yards"
                    )
                return PlayResult(
                    play_type="PUNT",
                    yards_gained=distance - return_yards,
                    result="PUNT",
                    description=desc,
                )

        # Legacy fallback for punters without a punt_column
        avg = punter.avg_distance
        variance = random.gauss(0, 5)
        distance = max(20, int(avg + variance))

        inside_20 = random.random() < punter.inside_20_rate
        fair_catch = Charts.check_fair_catch(punter.punt_return_pct)
        return_yards = 0 if fair_catch else max(
            0, Charts.roll_punt_return() + self._returner_modifier(returner, "PR")
        )

        desc = f"{punter.player_name} punts {distance} yards"
        if inside_20:
            desc += ", downed inside the 20"
            return_yards = 0
        elif fair_catch:
            desc += f", fair catch by {returner.player_name}" if returner else ", fair catch"
        elif return_yards > 0 and returner:
            desc += f", {returner.player_name} returns it {return_yards} yards"

        return PlayResult(
            play_type="PUNT",
            yards_gained=distance - return_yards,
            result="PUNT",
            description=desc,
        )

    # ── XP / 2PT / Kickoff ──────────────────────────────────────────

    def resolve_xp(self, kicker: PlayerCard) -> PlayResult:
        made = random.random() < kicker.xp_rate
        return PlayResult(
            play_type="XP",
            yards_gained=0,
            result="XP_GOOD" if made else "XP_NO_GOOD",
            description=f"Extra point {'good' if made else 'no good'}!",
        )

    def resolve_two_point(self, dice: DiceResult, qb: PlayerCard,
                          receiver: PlayerCard) -> PlayResult:
        success = random.random() < 0.48
        return PlayResult(
            play_type="2PT",
            yards_gained=0,
            result="2PT_GOOD" if success else "2PT_NO_GOOD",
            description=f"2-point conversion {'successful!' if success else 'fails.'}",
        )

    def resolve_kickoff(self, returner: Optional[PlayerCard] = None) -> PlayResult:
        if Charts.is_kickoff_touchback():
            return PlayResult(
                play_type="KICKOFF",
                yards_gained=0,
                result="TOUCHBACK",
                description="Kickoff - touchback, ball at 25-yard line",
            )
        final_position = Charts.roll_kick_return() + self._returner_modifier(returner, "KR")
        final_position = max(1, min(99, final_position))
        return PlayResult(
            play_type="KICKOFF",
            yards_gained=final_position,
            result="RETURN",
            description=(
                f"Kickoff to {returner.player_name}, returned to the {final_position}-yard line"
                if returner else f"Kickoff returned to the {final_position}-yard line"
            ),
        )

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
        """
        target = fac_card.get_receiver_target(pass_type)
        if target in ("Orig", "Z"):
            return default_receiver
        if target == "P.Rush":
            return default_receiver  # caller handles P.Rush as sack
        # Target is a position code: FL, LE, RE, BK1, BK2, etc.
        target_map = {"FL": 0, "LE": 1, "RE": 2, "BK1": 3, "BK2": 4}
        idx = target_map.get(target)
        if idx is not None and idx < len(receivers):
            return receivers[idx]
        # Rule 8: Position unoccupied → return None (thrown away)
        if idx is not None and idx >= len(receivers):
            return None
        return default_receiver

    def resolve_pass_5e(self, fac_card: FACCard, deck: FACDeck,
                        qb: PlayerCard, receiver: PlayerCard,
                        receivers: List[PlayerCard],
                        pass_type: str = "SHORT",
                        defense_coverage: int = 0,
                        defense_pass_rush: int = 0,
                        defense_formation: str = "4_3",
                        is_blitz_tendency: bool = False,
                        defensive_strategy: str = "NONE",
                        defenders: Optional[List[PlayerCard]] = None,
                        two_minute_offense: bool = False) -> PlayResult:
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
        """
        # ── Handle Z card ────────────────────────────────────────────
        if fac_card.is_z_card:
            z_event = self._resolve_z_card(deck)
            # On a Z card, draw the next card and use it for the play
            fac_card = deck.draw_non_z()
            return self._resolve_pass_inner_5e(
                fac_card, deck, qb, receiver, receivers, pass_type,
                defense_coverage, defense_pass_rush, defense_formation,
                is_blitz_tendency, z_event, defensive_strategy, defenders,
                two_minute_offense,
            )

        return self._resolve_pass_inner_5e(
            fac_card, deck, qb, receiver, receivers, pass_type,
            defense_coverage, defense_pass_rush, defense_formation,
            is_blitz_tendency, None, defensive_strategy, defenders,
            two_minute_offense,
        )

    def _resolve_pass_inner_5e(self, fac_card: FACCard, deck: FACDeck,
                               qb: PlayerCard, receiver: PlayerCard,
                               receivers: List[PlayerCard],
                               pass_type: str,
                               defense_coverage: int,
                               defense_pass_rush: int,
                               defense_formation: str,
                               is_blitz_tendency: bool,
                               z_event: Optional[Dict[str, Any]],
                               defensive_strategy: str = "NONE",
                               defenders: Optional[List[PlayerCard]] = None,
                               two_minute_offense: bool = False) -> PlayResult:
        """Inner pass resolution after Z-card handling.

        Authentic 5E resolution:
          1. Check QK/SH/LG receiver target field on FAC card
          2. If "P.Rush" → check QB pass rush ranges for sack/scramble/INC/COM
          3. Screen passes use FAC SC field directly
          4. PN → QB card passing ranges → COM / INC / INT
          5. If COM → RUN NUMBER → receiver's pass-gain Q/S/L → yards

        NOTE: The ER (End Run) field is for run plays only; it does NOT
        cause sacks on pass plays.  Pass-play sacks come exclusively
        from the "P.Rush" code in the QK/SH/LG receiver-target field.
        """
        log: List[str] = []
        log.append(f"[FAC] Card #{fac_card.card_number}: RN={fac_card.run_number} PN={fac_card.pass_number} ER={fac_card.end_run}")
        log.append(f"[PASS] Type={pass_type}, QB={qb.player_name}, Target={receiver.player_name}")
        log.append(f"[DEF] Formation={defense_formation}, Coverage={defense_coverage}, PassRush={defense_pass_rush}, Strategy={defensive_strategy}")

        # ── Step 1: Check receiver target for P.Rush ─────────────────
        target_field = fac_card.get_receiver_target(pass_type)
        log.append(f"[TARGET] FAC {pass_type} target field = '{target_field}'")
        if target_field == "P.Rush":
            log.append("[P.RUSH] Pass rush triggered by FAC card")
            # Pass rush result → check QB's pass_rush ranges
            if qb.pass_rush:
                pn = fac_card.pass_num_int or random.randint(1, 48)
                log.append(f"[P.RUSH] PN={pn}, QB pass_rush ranges: sack_max={qb.pass_rush.sack_max}, runs_max={qb.pass_rush.runs_max}, com_max={qb.pass_rush.com_max}")

                # Rule 2: Apply pass rush modifier to sack range
                pr_modifier = self.calculate_pass_rush_modifier(
                    defense_pass_rush, getattr(qb, 'pass_block_rating', 0)
                )
                adjusted_pn = pn
                if pr_modifier != 0:
                    adjusted_pn = max(1, min(48, pn - pr_modifier))
                    log.append(f"[P.RUSH] PR modifier={pr_modifier}, adjusted PN={adjusted_pn}")

                # Rule 3: Blitz pass rush override
                if is_blitz_tendency:
                    blitz_pr = self.get_blitz_pass_rush_value()
                    blitz_mod = self.calculate_pass_rush_modifier(
                        blitz_pr * 2, getattr(qb, 'pass_block_rating', 0)
                    )
                    adjusted_pn = max(1, min(48, pn - blitz_mod))
                    log.append(f"[P.RUSH] Blitz override: blitz_mod={blitz_mod}, adjusted PN={adjusted_pn}")

                pr_result = qb.pass_rush.resolve(adjusted_pn)
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
                    is_td = random.random() < 0.03
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
                elif pr_result == "INC":
                    r = PlayResult(
                        play_type="PASS", yards_gained=0, result="INCOMPLETE",
                        description=f"{qb.player_name} hurried, pass incomplete",
                        passer=qb.player_name, z_card_event=z_event,
                        pass_number_used=pn,
                    )
                    r.debug_log = log
                    return r
                log.append(f"[P.RUSH] COM despite rush — continue to pass resolution")
                # pr_result == "COM" → pass completed despite rush, continue
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
        
        if strategy_modifier != 0:
            log.append(f"[QB CARD] Strategy modifier={strategy_modifier}, PN adjusted from {pn} to {min(48, pn + abs(strategy_modifier)) if strategy_modifier < 0 else pn}")
        if strategy_modifier < 0:
            pn = min(48, pn + abs(strategy_modifier))

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
            int_yards, int_td = Charts.roll_int_return()
            log.append(f"[INT] Interception! Return yards={int_yards}, TD={int_td}")
            r = PlayResult(
                play_type="PASS", yards_gained=0,
                result="INT", turnover=True, turnover_type="INT",
                description=(
                    f"{qb.player_name} pass intercepted!"
                    f"{'Returned for TD!' if int_td else f' Returned {int_yards} yards.'}"
                ),
                passer=qb.player_name, receiver=actual_receiver.player_name,
                z_card_event=z_event,
                pass_number_used=pn,
                run_number_used=rn_for_poi,
            )
            r.debug_log = log
            return r

        # ── INC result — check for INC-range interception ────────────
        if qb_result == "INC":
            log.append(f"[INC] Incomplete pass, checking defender intercept ranges")
            if hasattr(actual_receiver, 'intercept_range') and actual_receiver.intercept_range:
                int_range = actual_receiver.intercept_range
                log.append(f"[INC] Defender intercept range = {int_range}")
                if isinstance(int_range, int) and int_range <= 48:
                    if int_range <= pn <= 48:
                        rn_for_ret = fac_card.run_num_int or random.randint(1, 12)
                        defender_pos = getattr(actual_receiver, 'position', 'DB')
                        int_yards, int_td = Charts.roll_int_return_5e(rn_for_ret, defender_pos)
                        log.append(f"[INC→INT] PN {pn} in intercept range [{int_range}-48]! INT!")
                        r = PlayResult(
                            play_type="PASS", yards_gained=0,
                            result="INT", turnover=True, turnover_type="INT",
                            description=(
                                f"{qb.player_name} pass intercepted by defender in coverage!"
                                f"{'Returned for TD!' if int_td else f' Returned {int_yards} yards.'}"
                            ),
                            passer=qb.player_name, receiver=actual_receiver.player_name,
                            z_card_event=z_event,
                            pass_number_used=pn,
                            run_number_used=rn_for_ret,
                        )
                        r.debug_log = log
                        return r
                elif isinstance(int_range, (list, tuple)) and len(int_range) == 2:
                    if int_range[0] <= pn <= int_range[1]:
                        int_yards, int_td = Charts.roll_int_return()
                        log.append(f"[INC→INT] PN {pn} in legacy range [{int_range[0]}-{int_range[1]}]! INT!")
                        r = PlayResult(
                            play_type="PASS", yards_gained=0,
                            result="INT", turnover=True, turnover_type="INT",
                            description=(
                                f"{qb.player_name} pass intercepted by defender in coverage!"
                                f"{'Returned for TD!' if int_td else f' Returned {int_yards} yards.'}"
                            ),
                            passer=qb.player_name, receiver=actual_receiver.player_name,
                            z_card_event=z_event,
                            pass_number_used=pn,
                        )
                        r.debug_log = log
                        return r
            if pn == 48:
                new_pn = random.randint(1, 48)
                log.append(f"[INC] PN=48 special check: new PN={new_pn}")
                if new_pn <= 24:
                    int_yards, int_td = Charts.roll_int_return()
                    r = PlayResult(
                        play_type="PASS", yards_gained=0,
                        result="INT", turnover=True, turnover_type="INT",
                        description=(
                            f"{qb.player_name} pass intercepted on PN 48 check! (new PN {new_pn})"
                            f"{'Returned for TD!' if int_td else f' Returned {int_yards} yards.'}"
                        ),
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
            is_td = random.random() < (0.06 if pass_type == "LONG" else 0.04)
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
                is_td = random.random() < 0.05
        else:
            yards = random.randint(5, 15) if pass_type != "LONG" else random.randint(15, 30)
            is_td = random.random() < 0.05
            log.append(f"[REC CARD] No receiver data, random yards={yards}")

        # Coverage modifier
        eff_cov = effective_coverage(defense_coverage, defense_formation, is_blitz_tendency)
        if eff_cov > 0 and isinstance(yards, int):
            old_yards = yards
            yards = max(0, yards - eff_cov)
            log.append(f"[COVERAGE] eff_cov={eff_cov}: {old_yards} → {yards} yards")

        if isinstance(yards, int) and yards >= 99:
            is_td = True

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
                           defense_formation: str = "4_3") -> PlayResult:
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
            int_yards, int_td = Charts.roll_int_return()
            return PlayResult(
                play_type="PASS", yards_gained=0,
                result="INT", turnover=True, turnover_type="INT",
                description=f"{qb.player_name} screen pass intercepted!",
                passer=qb.player_name, receiver=actual_receiver.player_name,
                z_card_event=z_event,
            )

        # Screen complete — Rule 4: use RB's rushing N column for yards
        run_num = fac_card.run_num_int or random.randint(1, 12)
        # Apply defense run number modifiers for screen
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
        is_td = random.random() < 0.03

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
                       defense_formation: str = "4_3") -> PlayResult:
        """Resolve a run play using 5th-edition FAC card mechanics.

        Authentic resolution:
          1. Draw FAC → get RUN NUMBER (1-12)
          2. Look up rusher's Rushing column row → N/SG/LG values
          3. Use N (Normal) column as base yards
          4. Modify by blocking matchups

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
        """
        z_event = None

        # ── Handle Z card ────────────────────────────────────────────
        if fac_card.is_z_card:
            z_event = self._resolve_z_card(deck)
            fac_card = deck.draw_non_z()

        # ── Determine run number and OOB ─────────────────────────────
        run_num = fac_card.run_num_int
        is_oob = fac_card.is_out_of_bounds

        # Rule 1: Apply run number modifier based on defense formation
        rn_modifier = self.get_run_number_modifier(defense_formation)
        if run_num is not None:
            run_num = max(1, min(12, run_num + rn_modifier))

        rn_str = str(run_num) if run_num is not None else "1"
        used_run_num = run_num if run_num is not None else 1

        # Effective run-stop
        eff_run_stop = effective_run_stop(defense_run_stop, defense_formation)

        # ── Try authentic 12-row rushing first ───────────────────────
        if rusher.rushing and rusher.has_rushing():
            rn = run_num if run_num is not None else 1
            row = rusher.get_rushing_row(rn)

            # Use N (normal) column as base yards
            yards = row.v1
            if isinstance(yards, str):
                if yards == "Sg":
                    # Special gain (breakaway)
                    yards = row.v3 if isinstance(row.v3, int) else random.randint(15, 40)
                    is_td = random.random() < 0.2
                    desc = f"{rusher.player_name} breaks free for {yards} yards!"
                    if is_td:
                        desc += " TOUCHDOWN!"
                    return PlayResult(
                        play_type="RUN", yards_gained=yards,
                        result="TD" if is_td else "GAIN",
                        is_touchdown=is_td,
                        description=desc,
                        rusher=rusher.player_name, z_card_event=z_event,
                        run_number_used=used_run_num,
                    )
                else:
                    try:
                        yards = int(yards)
                    except (ValueError, TypeError):
                        yards = random.randint(1, 5)

            # Defense run-stop modifier (authentic 5E: tackle rating −5 to +4)
            # Positive tackle = defense is better at stopping, reduces yards
            yards = max(-5, int(yards - eff_run_stop))
            if eff_run_stop >= 3 and random.random() < 0.15:
                yards = min(yards, random.choice([-2, -1, 0]))

            # 5E Rule: Inside run max loss = 3 yards; no limit on sweep
            yards = self.apply_inside_run_max_loss(yards, play_direction)

            if eff_run_stop >= 3 and random.random() < 0.03:
                recovery = Charts.roll_fumble_recovery()
                fumble_yards, fumble_td = Charts.roll_fumble_return()
                is_turnover = recovery == "DEFENSE"
                return PlayResult(
                    play_type="RUN", yards_gained=yards,
                    result="FUMBLE", turnover=is_turnover,
                    turnover_type="FUMBLE" if is_turnover else None,
                    description=(
                        f"{rusher.player_name} fumbles! "
                        f"{'Defense recovers!' if is_turnover else 'Offense recovers.'}"
                    ),
                    rusher=rusher.player_name, z_card_event=z_event,
                    run_number_used=used_run_num,
                )

            # Out of bounds — 5E Rule: inside runs may never end out of bounds
            if is_oob and play_direction not in ("IL", "IR", "INSIDE", "MIDDLE", "LEFT"):
                desc = f"{rusher.player_name} runs {play_direction} for {yards} yards, out of bounds"
                return PlayResult(
                    play_type="RUN", yards_gained=yards,
                    result="OOB", out_of_bounds=True,
                    description=desc, rusher=rusher.player_name,
                    z_card_event=z_event,
                    run_number_used=used_run_num,
                )

            is_td = random.random() < 0.03
            desc = f"{rusher.player_name} runs {play_direction}"
            if is_td:
                desc += " for a TOUCHDOWN!"
            else:
                desc += f" for {yards} yard{'s' if yards != 1 else ''}"

            return PlayResult(
                play_type="RUN", yards_gained=yards,
                result="TD" if is_td else "GAIN",
                is_touchdown=is_td,
                description=desc,
                rusher=rusher.player_name, z_card_event=z_event,
                run_number_used=used_run_num,
            )

        # ── Legacy: fall back to old slot-based columns ──────────────
        if play_direction in ("SL", "SR"):
            column = rusher.sweep if rusher.sweep else rusher.outside_run
        elif play_direction in ("IL", "IR"):
            column = rusher.inside_run
        elif play_direction in ("LEFT", "MIDDLE"):
            column = rusher.inside_run
        else:
            column = rusher.outside_run

        if not column:
            yards = random.choices([-2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8],
                                   weights=[2, 3, 5, 8, 10, 12, 12, 10, 8, 5, 3])[0]
            return PlayResult(
                play_type="RUN", yards_gained=yards, result="GAIN",
                description=f"{rusher.player_name} runs for {yards} yards",
                rusher=rusher.player_name, z_card_event=z_event,
                run_number_used=used_run_num,
            )

        play_data = column.get(rn_str, {"result": "GAIN", "yards": 2, "td": False})
        result_type = play_data.get("result", "GAIN")
        yards = play_data.get("yards", 0)
        is_td = play_data.get("td", False)

        # Defense run-stop modifier (authentic 5E small-number scale)
        if result_type in ("GAIN", "BREAKAWAY"):
            yards = max(-5, int(yards - eff_run_stop))
            if eff_run_stop >= 3 and random.random() < 0.15:
                yards = min(yards, random.choice([-2, -1, 0]))
            if eff_run_stop >= 3 and result_type == "GAIN" and random.random() < 0.03:
                result_type = "FUMBLE"

        # ── Out of bounds ────────────────────────────────────────────
        if is_oob:
            desc = f"{rusher.player_name} runs {play_direction} for {yards} yards, out of bounds"
            return PlayResult(
                play_type="RUN", yards_gained=yards,
                result="OOB", out_of_bounds=True,
                description=desc, rusher=rusher.player_name,
                z_card_event=z_event,
                run_number_used=used_run_num,
            )

        # ── Fumble ───────────────────────────────────────────────────
        if result_type == "FUMBLE":
            recovery = Charts.roll_fumble_recovery()
            fumble_yards, fumble_td = Charts.roll_fumble_return()
            is_turnover = recovery == "DEFENSE"
            if is_turnover and fumble_td:
                return PlayResult(
                    play_type="RUN", yards_gained=-fumble_yards,
                    result="FUMBLE_TD", is_touchdown=False,
                    turnover=True, turnover_type="FUMBLE",
                    description=f"{rusher.player_name} fumbles! Returned for TD!",
                    rusher=rusher.player_name, z_card_event=z_event,
                    run_number_used=used_run_num,
                )
            return PlayResult(
                play_type="RUN", yards_gained=yards,
                result="FUMBLE", turnover=is_turnover,
                turnover_type="FUMBLE" if is_turnover else None,
                description=(
                    f"{rusher.player_name} fumbles! "
                    f"{'Defense recovers!' if is_turnover else 'Offense recovers.'}"
                ),
                rusher=rusher.player_name, z_card_event=z_event,
                run_number_used=used_run_num,
            )

        # ── Breakaway ────────────────────────────────────────────────
        if result_type == "BREAKAWAY":
            is_td = is_td or random.random() < 0.2
            desc = f"{rusher.player_name} breaks free for {yards} yards!"
            if is_td:
                desc += " TOUCHDOWN!"
            return PlayResult(
                play_type="RUN", yards_gained=yards,
                result="TD" if is_td else "GAIN",
                is_touchdown=is_td,
                description=desc,
                rusher=rusher.player_name, z_card_event=z_event,
                run_number_used=used_run_num,
            )

        # ── Normal gain ──────────────────────────────────────────────
        # Check Z RES on the card for additional effects
        z_res_info = fac_card.parse_z_result()
        if z_res_info["type"] == "FUMBLE" and random.random() < 0.5:
            recovery = Charts.roll_fumble_recovery()
            is_turnover = recovery == "DEFENSE"
            return PlayResult(
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

        desc = f"{rusher.player_name} runs {play_direction}"
        if is_td:
            desc += " for a TOUCHDOWN!"
        else:
            desc += f" for {yards} yard{'s' if yards != 1 else ''}"

        return PlayResult(
            play_type="RUN", yards_gained=yards,
            result="TD" if is_td else "GAIN",
            is_touchdown=is_td,
            description=desc,
            rusher=rusher.player_name,
            z_card_event=z_event,
            run_number_used=used_run_num,
        )

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
                                minutes_remaining: float = 3.0) -> PlayResult:
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
            is_td = random.random() < 0.08
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
                          punter: PlayerCard) -> PlayResult:
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
            is_td = random.random() < 0.05
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
            is_td = random.random() < 0.15
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
            is_td = random.random() < 0.03
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

        Screen passes use the same modifiers as running plays:
          Run Defense: +2 (no key), +4 (key on back)
          Pass/Prevent: 0
          Blitz: 0
        """
        form = defense_formation.lower() if defense_formation else ""
        if "blitz" in form:
            return 0
        pass_forms = ("pass", "4_3_cover2", "nickel_zone", "nickel_cover2",
                      "prevent", "3_4_zone")
        if form in pass_forms or "prevent" in form:
            return 0
        # Run defense formations
        return 2

    # ── Rule 14: Within-20 Completion Modifier ───────────────────────

    @staticmethod
    def get_within_20_completion_modifier(yard_line: int) -> int:
        """Return completion range modifier when inside opponent's 20 (Rule 14).

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

    # ── OL/CB/S Out of Position (Optional Rule) ─────────────────────

    @staticmethod
    def check_out_of_position_penalty(player: PlayerCard,
                                       assigned_position: str) -> int:
        """Return penalty for playing out of position (Optional Rule).

        OL playing wrong slot: -1 to blocking value
        CB/S playing wrong position: -1 to pass defense
        DL/LB may play any Row 1 position without modification.
        Any DB may play in Box L without modification.
        """
        natural_pos = getattr(player, 'position', '')
        if natural_pos == assigned_position:
            return 0

        # DL/LB can play any Row 1 position without penalty
        if natural_pos in ('DE', 'DT', 'DL', 'NT', 'LB', 'OLB', 'ILB', 'MLB'):
            if assigned_position in ('A', 'B', 'C', 'D', 'E',
                                     'DE', 'DT', 'DL', 'NT', 'LB', 'OLB', 'ILB', 'MLB'):
                return 0

        # Any DB may play in Box L without modification
        if natural_pos in ('CB', 'S', 'SS', 'FS', 'DB') and assigned_position == 'L':
            return 0

        if natural_pos in ('LT', 'LG', 'C', 'RG', 'RT'):
            return -1  # OL out of position
        if natural_pos in ('CB', 'S', 'SS', 'FS'):
            return -1  # DB out of position
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
        """
        assignments: Dict[str, str] = {}
        dl_players = [d for d in defenders if getattr(d, 'position', '') in
                      ('DE', 'DT', 'DL', 'NT')]
        lb_players = [d for d in defenders if getattr(d, 'position', '') in
                      ('LB', 'OLB', 'ILB', 'MLB')]
        db_players = [d for d in defenders if getattr(d, 'position', '') in
                      ('CB', 'S', 'SS', 'FS', 'DB')]

        # Row 1: DL players to boxes A-E (0-2 per box)
        row1_boxes = ['A', 'B', 'C', 'D', 'E']
        for i, p in enumerate(dl_players[:5]):
            box = row1_boxes[i % len(row1_boxes)]
            assignments[p.player_name] = box

        # Row 2: LBs to boxes F-J (one per box)
        row2_boxes = ['F', 'G', 'H', 'I', 'J']
        for i, p in enumerate(lb_players[:5]):
            assignments[p.player_name] = row2_boxes[i]

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
            if pos in ('FS', 'S') and 'M' not in assignments.values():
                assignments[s.player_name] = 'M'
            elif pos == 'SS' and 'N' not in assignments.values():
                assignments[s.player_name] = 'N'
            elif 'L' not in assignments.values():
                assignments[s.player_name] = 'L'
        for db in other_dbs:
            for box in ['L', 'M', 'N']:
                if box not in assignments.values():
                    assignments[db.player_name] = box
                    break

        return assignments

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
        'RE': 'N',    # Right End → Box N
        'LE': 'K',    # Left End → Box K
        'FL1': 'O',   # Flanker #1 → Box O
        'FL2': 'M',   # Flanker #2 → Box M
        'BK1': 'F',   # Back #1 → Box F
        'BK2': 'J',   # Back #2 → Box J
        'BK3': 'H',   # Back #3 → Box H
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

    # ── FL#1/FL#2 Flanker Designation System (5E) ────────────────────

    # Per 5E rules:
    #   If 3 RBs on display → 1 back is in flanker position (FL#1)
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

        if rbs_on_display >= 3 and len(rbs) >= 3:
            # 3 RBs: one back becomes FL#1
            result['FL1'] = rbs[2].player_name
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
