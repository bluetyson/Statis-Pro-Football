"""Fast Action Card (FAC) deck for Statis Pro Football 5th Edition.

The 5th-edition FAC deck consists of **109 cards**:
  * 96 standard cards — numbers 1-48 each appearing twice
    (once "normal", once "OB" — out-of-bounds on the run)
  * 13 Z cards — special-event cards

Each card carries several fields used by different subsystems:

  RUN#   — Run Number (1-12, or n(OB), or Z)
  PASS#  — Pass Number (1-48, or Z)
  SL/IL/SR/IR — Defensive matchups for four run directions
  ER     — End-run / pass-rush result ("OK" or sack yards)
  QK/SH/LG — Receiver target override for quick/short/long pass
  SC     — Screen pass result (Com/Inc/Int/etc.)
  Z_RES  — Z-result field (penalty, injury, fumble, etc.)
  SOLO   — Solitaire play-calling sequence

Card data is sourced from the BJY (Brian Yonushonis) FAC flipper data
which faithfully reproduces the 5th-edition deck.
"""
import random
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


# ──────────────────────────────────────────────────────────────────────
#  FACCard data class
# ──────────────────────────────────────────────────────────────────────

@dataclass
class FACCard:
    """One Fast Action Card from the 109-card deck."""
    card_number: int          # 1-109 (deck index)
    run_number: str           # "1"-"12", "1(OB)"-"12(OB)", or "Z"
    pass_number: str          # "1"-"48" or "Z"
    sweep_left: str           # Defensive matchup for sweep left
    inside_left: str          # Defensive matchup for inside left
    sweep_right: str          # Defensive matchup for sweep right
    inside_right: str         # Defensive matchup for inside right
    end_run: str              # "OK" or sack yards ("-1" to "-6"), or "Z"
    quick_kick: str           # Receiver target for quick pass, or "Z"
    short_pass: str           # Receiver target for short pass, or "Z"
    long_pass: str            # Receiver target for long pass, or "Z"
    screen: str               # Screen result: "Com", "Inc", "Int", "Com x 2", etc.
    z_result: str             # Z-result: "Inj: BC", "Pen: ...", "Fumble", etc.
    solo: str                 # Solitaire play sequence

    @property
    def is_z_card(self) -> bool:
        """True if this is one of the 13 Z cards."""
        return self.run_number == "Z"

    @property
    def is_out_of_bounds(self) -> bool:
        """True if the run result puts the runner out of bounds."""
        return "(OB)" in self.run_number

    @property
    def run_num_int(self) -> Optional[int]:
        """The numeric run number (1-12), or None for Z cards."""
        if self.is_z_card:
            return None
        # Strip "(OB)" suffix to get the base number
        base = self.run_number.replace("(OB)", "").strip()
        try:
            return int(base)
        except ValueError:
            return None

    @property
    def pass_num_int(self) -> Optional[int]:
        """The numeric pass number (1-48), or None for Z cards."""
        if self.pass_number == "Z":
            return None
        try:
            return int(self.pass_number)
        except ValueError:
            return None

    @property
    def sack_yards(self) -> Optional[int]:
        """If ER indicates a sack, return negative yards; else None."""
        if self.end_run == "Z":
            return None
        if self.end_run == "OK":
            return None
        try:
            val = int(self.end_run)
            if val < 0:
                return val
        except ValueError:
            pass
        return None

    @property
    def screen_result(self) -> str:
        """Normalized screen pass result."""
        sc = self.screen.strip()
        if sc.startswith("Com x"):
            return sc  # "Com x 2", "Com x ½", "Com x 3"
        if sc == "Com":
            return "Com"
        if sc == "Inc":
            return "Inc"
        if sc == "Int":
            return "Int"
        if sc.startswith("Dropped"):
            return "Inc"  # "Dropped Int" → treat as incomplete
        return sc

    def get_receiver_target(self, pass_type: str) -> str:
        """Return the receiver target field for the given pass type.

        pass_type should be one of: "QUICK", "SHORT", "LONG"
        """
        if pass_type == "QUICK":
            return self.quick_kick
        elif pass_type == "SHORT":
            return self.short_pass
        elif pass_type == "LONG":
            return self.long_pass
        return self.short_pass  # default

    def get_blocking_matchup(self, direction: str) -> str:
        """Return the blocking matchup for the given run direction.

        direction should be one of: "SL", "IL", "SR", "IR"
        """
        mapping = {
            "SL": self.sweep_left,
            "IL": self.inside_left,
            "SR": self.sweep_right,
            "IR": self.inside_right,
        }
        return mapping.get(direction, self.inside_left)

    def parse_solo(self) -> Dict[int, str]:
        """Parse the solitaire field into a dict of {situation_number: play_code}.

        Format: "1.R(BC)/2.P/3.BLZ/4.PR(x2)/5.R(NK)"
        Returns: {1: "R(BC)", 2: "P", 3: "BLZ", 4: "PR(x2)", 5: "R(NK)"}
        """
        result = {}
        if not self.solo or self.solo == "Z":
            return result
        parts = self.solo.split("/")
        for part in parts:
            part = part.strip()
            if "." in part:
                num_str, code = part.split(".", 1)
                try:
                    result[int(num_str)] = code
                except ValueError:
                    pass
        return result

    def parse_z_result(self) -> Dict[str, Any]:
        """Parse the Z result field into a structured dict.

        Returns dict with:
          - "type": "INJURY", "PENALTY", "FUMBLE", "DOWN_BY_CONTACT",
                    "NO_INJURY", "NONE"
          - "detail": the raw text or parsed detail
        """
        z = self.z_result.strip()
        if z == "Z":
            return {"type": "Z_CARD", "detail": "Draw next card for Z resolution"}
        if z.startswith("Inj:"):
            return {"type": "INJURY", "detail": z[4:].strip()}
        if z.startswith("No Inj:"):
            return {"type": "NO_INJURY", "detail": z[7:].strip()}
        if z.startswith("Pen:"):
            return {"type": "PENALTY", "detail": z[4:].strip()}
        if z == "Fumble":
            return {"type": "FUMBLE", "detail": "Fumble"}
        if z.startswith("Fumble"):
            return {"type": "FUMBLE", "detail": z}
        if z == "Down By Contact":
            return {"type": "DOWN_BY_CONTACT", "detail": "Down by contact"}
        if z.startswith("Dropped"):
            return {"type": "DROPPED_INT", "detail": z}
        return {"type": "NONE", "detail": z}


# ──────────────────────────────────────────────────────────────────────
#  Full 109-card deck data  (from BJY FAC flipper)
# ──────────────────────────────────────────────────────────────────────
#
# Each tuple: (card#, RUN#, PASS#, SL, IL, SR, IR, ER, QK, SH, LG, SC, Z_RES, SOLO)
#

_RAW_DECK = [
    # --- Standard cards (1-72): numbers 1-48, first appearance -----------
    (1, "1", "1", "LG + LT", "LG", "RG + RT", "RG", "OK", "Orig", "Orig", "Orig", "Com", "Inj: BC", "1.R(BC)/2.R(BC)/3.P/4.PR(x2)/5.R(BC)"),
    (2, "1", "1", "LG + LT", "LG", "RG + RT", "RG", "-6", "FL", "FL", "FL", "Com", "Pen: 1.D2 /2.D2 /3.R1 /4.R11", "1.R(NK)/2.P/3.BLZ/4.P(x2)/5.R(NK)"),
    (3, "1", "2", "LG + LT", "LG", "RG + RT", "RG", "-6", "FL", "FL", "FL", "Com", "Pen: 1.O2 /2.O2 /3.K1 /4.R11", "1.R(NK)/2.PR(x2)/3.BLZ/4.P(x2)/5.R(NK)"),
    (4, "1", "2", "LG + LT", "LG", "RG + RT", "RG", "OK", "RE", "RE", "RE", "Com", "Inj: RT", "1.R(NK)/2.P/3.P/4.P/5.R(NK)"),
    (5, "1", "3", "LG + LT", "LG", "RG + RT", "RG", "OK", "RE", "RE", "RE", "Com", "Inj: RE", "1.R(NK)/2.BLZ/3.BLZ/4.P(x2)/5.R(NK)"),
    (6, "1", "3", "LG + LT", "LG", "RG + RT", "RG", "OK", "Orig", "Orig", "Orig", "Com", "Inj: BC", "1.R(BC)/2.R(BC)/3.P/4.PR(x2)/5.R(NK)"),
    (7, "1", "4", "LG + LT", "LG", "RG + RT", "RG", "OK", "RE", "RE", "RE", "Com", "Inj: CN", "1.R(NK)/2.PR/3.PR(x2)/4.PR(x2)/5.R(NK)"),
    (8, "2", "5", "LG + LE", "LG", "RG + RE", "RG", "-5", "BK2", "BK2", "BK2", "Com", "Pen: 1.D5 /2.D1 /3.K1 /4.K1", "1.R(NK)/2.P/3.P(x2)/4.PR(x2)/5.R(NK)"),
    (9, "2", "5", "LG + LE", "LG", "RG + RE", "RG", "-6", "FL", "FL", "FL", "Com", "Pen: 1.O5 /2.O1 /3.R12 /4.R5", "1.R(NK)/2.P(x2)/3.PR/4.P/5.R(NK)"),
    (10, "2", "7", "LG + LE", "CN + LG", "RG + RE", "CN + RG", "-6", "FL", "FL", "FL", "Com", "Pen: 1.O2 /2.D1 /3.R1 /4.R11", "1.R(NK)/2.PR(x2)/3.BLZ/4.P(x2)/5.R(NK)"),
    (11, "3", "8", "BK vs F", "BK vs G", "BK vs J", "BK vs I", "OK", "RE", "RE", "RE", "Dropped Int", "Inj: D", "1.R(NK)/2.PR(x2)/3.BLZ/4.P(x2)/5.R(NK)"),
    (12, "3", "8", "LG vs F", "CN vs H", "RG vs J", "CN vs H", "OK", "LE", "LE", "LE", "Com", "Inj: BC", "1.R(BC)/2.R(NK)/3.R(NK)/4.PR/5.R(NK)"),
    (13, "3", "9", "LG vs F", "CN vs H", "RG vs J", "CN vs H", "OK", "LE", "LE", "LE", "Com", "Inj: BC", "1.R(BC)/2.R(NK)/3.R(NK)/4.PR/5.R(NK)"),
    (14, "4", "12", "BK vs G", "BK vs H", "BK vs I", "BK vs H", "OK", "FL", "FL", "FL", "Com", "Inj: N", "1.R(NK)/2.P(x2)/3.P/4.P/5.R(NK)"),
    (15, "4", "13", "LE vs F", "CN vs C", "RE vs J", "CN vs C", "OK", "LE", "LE", "LE", "Com", "Inj: BC", "1.R(NK)/2.PR/3.PR(x2)/4.PR(x2)/5.R(NK)"),
    (16, "4", "14", "LT", "CN", "RT", "CN", "-5", "BK2", "BK2", "BK2", "Com", "Pen: 1.O1 /2.O7 /3.R11 /4.R11", "1.R(NK)/2.P/3.P(x2)/4.PR(x2)/5.R(NK)"),
    (17, "4", "14", "LT", "CN", "RT", "CN", "OK", "LE", "LE", "LE", "Com", "Inj: LT", "1.R(BC)/2.R(NK)/3.R(NK)/4.PR/5.R(NK)"),
    (18, "5", "15", "LE vs F", "CN vs C", "RE vs J", "CN vs C", "OK", "BK2", "BK2", "BK2", "Com", "Inj: BC", "1.R(NK)/2.P(x2)/3.PR/4.P/5.R(NK)"),
    (19, "5", "15", "LT", "CN", "RT", "CN", "-6", "FL", "FL", "FL", "Com", "Pen: 1.O3 /2.O7 /3.R11 /4.R11", "1.R(NK)/2.P(x2)/3.PR/4.P/5.R(NK)"),
    (20, "5", "16", "LE vs F", "CN vs C", "RE vs J", "CN vs C", "OK", "LE", "LE", "LE", "Com", "Inj: BC", "1.R(BC)/2.R(NK)/3.R(NK)/4.PR/5.R(NK)"),
    (21, "5", "16", "LT", "CN", "RT", "CN", "-5", "BK2", "BK2", "BK2", "Com", "Pen: 1.O7 /2.D8 /3.R13 /4.K9", "1.R(NK)/2.P(x2)/3.PR/4.P/5.R(NK)"),
    (22, "5", "17", "LT vs B", "LG vs G", "RT vs D", "RG vs I", "OK", "FL", "FL", "FL", "Com", "Inj: O", "1.R(NK)/2.P(x2)/3.PR/4.P/5.R(NK)"),
    (23, "5", "17", "LT", "CN", "RT", "CN", "OK", "RE", "RE", "RE", "Com", "Inj: RG", "1.R(NK)/2.PR/3.PR(x2)/4.PR(x2)/5.R(NK)"),
    (24, "5", "18", "BK", "CN", "BK", "CN", "OK", "Orig", "Orig", "Orig", "Com", "No Inj: BC", "1.R(BC)/2.R(BC)/3.P(x2)/4.PR(x2)/5.R(NK)"),
    (25, "5", "18", "LE vs F", "CN vs C", "RE vs J", "CN vs C", "OK", "Orig", "Orig", "Orig", "Com", "Pen: 1.D1 /2.O7 /3.R11 /4.R11", "1.P/2.R(NK)/3.R(NK)/4.PR/5.R(BC)"),
    (26, "5", "19", "LT vs A", "LG vs B", "RT vs E", "RG vs D", "OK", "LE", "LE", "LE", "Com", "Inj: QB", "1.R(BC)/2.R(NK)/3.R(NK)/4.PR/5.R(NK)"),
    (27, "6", "10", "LT vs G", "BK vs I", "RT vs I", "BK vs G", "OK", "Orig", "Orig", "Orig", "Com", "Pen: 1.D1 /2.O7 /3.R11 /4.R11", "1.P/2.R(NK)/3.R(NK)/4.PR/5.R(BC)"),
    (28, "6", "11", "LT vs B", "LG vs B", "RT vs D", "RG vs I", "OK", "BK1", "BK1", "BK1", "Com", "Pen: 1.D1 /2.D7 /3.R11 /4.R11", "1.P/2.R(NK)/3.R(NK)/4.P/5.R(BC)"),
    (29, "6", "26", "A", "B", "D", "C", "-3", "Orig", "Orig", "Orig", "Inc", "Pen: 1.O3 /2.O3 /3.R11 /4.R11", "1.PR/2.R(NK)/3.R(BC)/4.BLZ/5.R(NK)"),
    (30, "6", "26", "A", "B", "D", "C", "-4", "Orig", "Orig", "Orig", "Inc", "Pen: 1.D7 /2.O8 /3.R13 /4.K5", "1.P(x2)/2.R(NK)/3.R(NK)/4.PR/5.P"),
    (31, "6", "27", "BK vs G", "BK vs H", "BK vs I", "BK vs H", "-2", "Orig", "Orig", "Orig", "Com x 2", "Down By Contact", "1.PR/2.R(NK)/3.R(BC)/4.BLZ/5.R(NK)"),
    (32, "6", "27", "A", "B", "D", "C", "-2", "Orig", "Orig", "Orig", "Inc", "Fumble", "1.PR/2.R(NK)/3.R(BC)/4.BLZ/5.R(NK)"),
    (33, "6", "28", "LG vs F", "CN vs H", "RG vs J", "CN vs H", "-5", "Orig", "Orig", "Orig", "Com x 2", "Pen: 1.O1 /2.O7 /3.R5 /4.R11", "1.P/2.R(NK)/3.R(NK)/4.PR/5.R(NK)"),
    (34, "6", "28", "LE vs H", "LT vs G", "RE vs H", "RT vs I", "-2", "Orig", "Orig", "Orig", "Com x 2", "Fumble", "1.P/2.R(NK)/3.P/4.BLZ/5.R(NK)"),
    (35, "6", "29", "BK vs F", "BK vs G", "BK vs J", "BK vs J", "OK", "Orig", "Orig", "Orig", "Com x 2", "Inj: LE", "1.P/2.R(NK)/3.R(NK)/4.PR/5.R(BC)"),
    (36, "7", "21", "LE", "BK", "RE", "BK", "OK", "LE", "LE", "LE", "Com", "Inj: LG", "1.R(BC)/2.R(BC)/3.P(x2)/4.PR(x2)/5.R(NK)"),
    (37, "7", "21", "LE", "BK", "RE", "BK", "OK", "LE", "LE", "LE", "Com", "Inj: LG", "1.R(BC)/2.R(BC)/3.P(x2)/4.PR(x2)/5.R(NK)"),
    (38, "7", "22", "LT vs A", "LG vs B", "RT vs E", "RG vs D", "OK", "LE", "LE", "LE", "Com", "Inj: BC", "1.R(BC)/2.R(NK)/3.R(NK)/4.PR/5.R(NK)"),
    (39, "7", "23", "Break", "Break", "Break", "Break", "OK", "RE", "RE", "RE", "Com", "Inj: CN", "1.R(NK)/2.PR/3.PR(x2)/4.PR(x2)/5.R(NK)"),
    (40, "7", "23", "LE", "BK", "RE", "BK", "OK", "RE", "RE", "RE", "Com", "Inj: RT", "1.R(NK)/2.PR/3.BLZ/4.P/5.R(NK)"),
    (41, "7", "24", "Break", "Break", "Break", "Break", "OK", "RE", "RE", "RE", "Com", "Inj: RG", "1.R(NK)/2.PR/3.PR(x2)/4.PR(x2)/5.R(NK)"),
    (42, "7", "25", "A", "B", "D", "C", "-3", "Orig", "Orig", "Orig", "Inc", "Pen: 1.O7 /2.D8 /3.R13 /4.K9", "1.PR/2.R(NK)/3.R(BC)/4.BLZ/5.R(NK)"),
    (43, "7", "25", "A", "B", "D", "C", "-1", "Orig", "Orig", "Orig", "Inc", "Fumble", "1.BLZ/2.R(NK)/3.R(BC)/4.BLZ/5.R(NK)"),
    (44, "8", "29", "LT vs A", "LG vs B", "RT vs E", "RG vs D", "-2", "Orig", "Orig", "Orig", "Com x 2", "Pen: 1.O1 /2.O1 /3.R11 /4.R11", "1.PR/2.R(NK)/3.P/4.BLZ/5.R(NK)"),
    (45, "8", "30", "LT vs A", "LG vs B", "RT vs E", "RG vs D", "-1", "Orig", "Orig", "Orig", "Com x 2", "Down By Contact", "1.BLZ/2.R(NK)/3.R(BC)/4.BLZ/5.R(NK)"),
    (46, "8", "31", "LT vs A", "LG vs B", "RT vs E", "RG vs D", "-5", "Orig", "Orig", "Orig", "Com x 2", "Pen: 1.O1 /2.D5 /3.K5 /4.R11", "1.P/2.R(NK)/3.R(NK)/4.PR/5.R(NK)"),
    (47, "8", "32", "A", "B", "D", "C", "OK", "Orig", "Orig", "Orig", "Int", "Inj: E", "1.P/2.R(NK)/3.R(NK)/4.PR/5.R(NK)"),
    (48, "8", "32", "LE vs H", "LT vs G", "RE vs H", "RT vs I", "-4", "Orig", "Orig", "Orig", "Com x 2", "Pen: 1.D2 /2.O5 /3.K5 /4.R11", "1.P(x2)/2.R(NK)/3.R(NK)/4.PR/5.R(BC)"),
    (49, "9", "33", "LE vs F", "CN vs C", "RE vs J", "CN vs C", "-1", "Orig", "Orig", "Orig", "Com x 2", "Down By Contact", "1.P/2.R(NK)/3.R(NK)/4.P/5.P"),
    (50, "9", "33", "LE vs F", "CN vs C", "RE vs J", "CN vs C", "-4", "Orig", "Orig", "Orig", "Com x 2", "Pen: 1.D1 /2.D7 /3.R11 /4.R11", "1.P(x2)/2.R(NK)/3.R(NK)/4.PR/5.PR(x2)"),
    (51, "9", "34", "B", "C", "E", "D", "OK", "Orig", "Orig", "Orig", "Inc", "Inj: G", "1.P/2.R(NK)/3.R(NK)/4.PR/5.R(BC)"),
    (52, "9", "35", "B", "C", "E", "D", "OK", "Orig", "Orig", "Orig", "Inc", "Inj: F", "1.P/2.R(NK)/3.R(NK)/4.PR/5.R(BC)"),
    (53, "9", "36", "B", "C", "E", "D", "-2", "Orig", "Orig", "Orig", "Inc", "Fumble(s)", "1.PR/2.R(NK)/3.P/4.BLZ/5.R(NK)"),
    (54, "9", "36", "LG vs F", "CN vs H", "RG vs J", "CN vs H", "-3", "Orig", "Orig", "Orig", "Com x 2", "Pen: 1.O1 /2.O1 /3.R11 /4.R11", "1.PR(x2)/2.R(NK)/3.R(BC)/4.PR/5.PR"),
    (55, "10", "37", "B", "C", "E", "D", "-2", "Orig", "Orig", "Orig", "Inc", "Fumble(s)", "1.PR/2.R(NK)/3.P/4.BLZ/5.R(NK)"),
    (56, "10", "37", "LE vs F", "CN vs C", "RE vs J", "CN vs C", "-4", "Orig", "Orig", "Orig", "Com x 2", "Pen: 1.O1 /2.O1 /3.K1 /4.K15", "1.P(x2)/2.R(NK)/3.R(NK)/4.PR/5.R(BC)"),
    (57, "10", "38", "B", "C", "E", "D", "-1", "Orig", "Orig", "Orig", "Inc", "Fumble", "1.BLZ/2.R(NK)/3.R(BC)/4.BLZ/5.R(NK)"),
    (58, "10", "39", "B", "C", "E", "D", "-3", "Orig", "Orig", "Orig", "Inc", "Pen: 1.O1 /2.O1 /3.R11 /4.R11", "1.PR(x2)/2.R(NK)/3.R(NK)/4.PR/5.R(BC)"),
    (59, "10", "39", "B", "C", "E", "D", "-2", "Orig", "Orig", "Orig", "Inc", "Fumble(s)", "1.PR/2.R(NK)/3.P/4.BLZ/5.R(NK)"),
    (60, "10", "40", "LT vs B", "LG vs G", "RT vs D", "RG vs I", "-2", "Orig", "Orig", "Orig", "Com x 2", "Fumble(s)", "1.PR/2.R(NK)/3.P/4.BLZ/5.R(NK)"),
    (61, "11", "41", "A + F", "B + G", "D + I", "C + H", "OK", "Orig", "Orig", "Orig", "Com x 2", "Inj: B", "1.P/2.R(NK)/3.R(NK)/4.PR/5.R(BC)"),
    (62, "11", "42", "A + F", "B + G", "D + I", "C + H", "OK", "LE", "LE", "P.Rush", "Com x 2", "Inj: B", "1.P/2.R(NK)/3.R(NK)/4.PR/5.R(BC)"),
    (63, "11", "43", "A + F", "B + G", "D + I", "C + H", "OK", "FL", "FL", "P.Rush", "Com x 2", "Inj: A", "1.P/2.R(NK)/3.R(NK)/4.PR/5.R(BC)"),
    (64, "11", "43", "A + F", "B + G", "D + I", "C + H", "-3", "LE", "LE", "P.Rush", "Inc", "Pen: 1.D9 /2.D9 /3.K9 /4.K15", "1.PR/2.R(NK)/3.R(BC)/4.BLZ/5.R(NK)"),
    (65, "11", "44", "A + F", "B + G", "D + I", "C + H", "-4", "FL", "FL", "P.Rush", "Inc", "Pen: 1.D1 /2.D1 /3.R1 /4.K15", "1.P/2.R(NK)/3.R(NK)/4.PR/5.P(x2)"),
    (66, "12", "45", "B + G", "C + H", "E + J", "D + I", "OK", "FL", "P.Rush", "P.Rush", "Inc", "Inj: J", "1.P/2.R(NK)/3.R(NK)/4.PR/5.R(BC)"),
    (67, "12", "45", "B + G", "C + H", "E + J", "D + I", "OK", "P.Rush", "P.Rush", "P.Rush", "Inc", "Inj: H", "1.P/2.R(NK)/3.R(NK)/4.PR/5.R(BC)"),
    (68, "12", "46", "B + G", "C + H", "E + J", "D + I", "OK", "LE", "P.Rush", "P.Rush", "Inc", "Inj: E", "1.P/2.R(NK)/3.R(NK)/4.PR/5.R(BC)"),
    (69, "12", "46", "B + G", "C + H", "E + J", "D + I", "-1", "RE", "P.Rush", "P.Rush", "Com x 2", "Down By Contact", "1.PR(x2)/2.R(NK)/3.R(NK)/4.PR/5.P"),
    (70, "12", "47", "B + G", "C + H", "E + J", "D + I", "-4", "RE", "P.Rush", "P.Rush", "Com x 3", "Pen: 1.O1 /2.O7 /3.R5 /4.R11", "1.P(x2)/2.R(NK)/3.R(NK)/4.PR/5.R(BC)"),
    (71, "12", "47", "B + G", "C + H", "E + J", "D + I", "OK", "RE", "P.Rush", "P.Rush", "Inc", "Inj: L", "1.P/2.R(NK)/3.R(NK)/4.PR/5.R(BC)"),
    (72, "12", "48", "B + G", "C + H", "E + J", "D + I", "-4", "LE", "P.Rush", "P.Rush", "Com x 3", "Pen: 1.O14 /2.O14 /3.K14 /4.R1", "1.P/2.R(NK)/3.R(NK)/4.PR/5.R(NK)"),
    # --- OB (Out of Bounds) variants (73-96) ----------------------------
    (73, "1(OB)", "4", "LG + LT", "LG", "RG + RT", "RG", "-6", "FL", "FL", "FL", "Com", "Pen: 1.D5 /2.D1 /3.R1 /4.K1", "1.R(NK)/2.P/3.P(x2)/4.PR(x2)/5.R(NK)"),
    (74, "10(OB)", "38", "B", "C", "E", "D", "OK", "Orig", "Orig", "Orig", "Inc", "Inj: I", "1.R(NK)/2.R(BC)/3.P/4.BLZ/5.R(NK)"),
    (75, "10(OB)", "40", "LE vs F", "CN vs C", "RE vs J", "CN vs C", "OK", "Orig", "Orig", "Orig", "Com x 2", "Inj: C", "1.R(NK)/2.R(BC)/3.P/4.BLZ/5.R(NK)"),
    (76, "11(OB)", "41", "A + F", "B + G", "D + I", "C + H", "OK", "Orig", "Orig", "Orig", "Com", "Inj: LT", "1.R(NK)/2.R(BC)/3.P/4.PR(x2)/5.R(NK)"),
    (77, "11(OB)", "42", "A + F", "B + G", "D + I", "C + H", "-4", "RE", "RE", "P.Rush", "Com x 3", "Pen: 1.D2 /2.D2 /3.R1 /4.R11", "1.P(x2)/2.R(NK)/3.R(NK)/4.PR/5.R(BC)"),
    (78, "11(OB)", "44", "A + F", "B + G", "D + I", "C + H", "OK", "FL", "FL", "P.Rush", "Com x 3", "Inj: D", "1.R(NK)/2.R(BC)/3.P/4.PR(x2)/5.R(NK)"),
    (79, "12(OB)", "48", "B + G", "C + H", "E + J", "D + I", "OK", "P.Rush", "P.Rush", "P.Rush", "Inc", "Inj: M", "1.R(NK)/2.PR/3.PR(x2)/4.PR(x2)/5.R(NK)"),
    (80, "2(OB)", "6", "LG + LE", "CN + LG", "RG + RE", "CN + RG", "-3", "BK1", "BK1", "BK1", "Com", "Pen: 1.O1 /2.O1 /3.R11 /4.R11", "1.R(NK)/2.P/3.PR/4.R(NK)/5.R(NK)"),
    (81, "2(OB)", "6", "LG + LE", "CN + LG", "RG + RE", "CN + RG", "-5", "BK2", "BK2", "BK2", "Com", "Pen: 1.O5 /2.O1 /3.K1 /4.R5", "1.R(NK)/2.P/3.P(x2)/4.PR(x2)/5.R(NK)"),
    (82, "3(OB)", "7", "LG", "CN + LG", "CN + RG", "RG", "-6", "FL", "FL", "FL", "Com", "Pen: 1.O2 /2.O2 /3.K1 /4.R11", "1.R(NK)/2.P/3.PR/4.R(NK)/5.R(NK)"),
    (83, "3(OB)", "9", "LT vs G", "BK vs I", "RT vs I", "BK vs G", "-1", "BK1", "BK1", "BK1", "Com", "Down By Contact", "1.R(NK)/2.P/3.PR/4.R(NK)/5.R(NK)"),
    (84, "4(OB)", "12", "LG", "LT", "RG", "RT", "-6", "BK2", "BK2", "BK2", "Com", "Pen: 1.D1 /2.O7 /3.R11 /4.R11", "1.R(NK)/2.P/3.PR/4.R(NK)/5.R(NK)"),
    (85, "4(OB)", "13", "LT", "LT", "RT", "RT", "-1", "BK1", "BK1", "BK1", "Com", "Fumble", "1.R(NK)/2.P/3.PR/4.R(NK)/5.R(NK)"),
    (86, "5(OB)", "19", "LT vs A", "LG vs B", "RT vs E", "RG vs D", "OK", "Orig", "Orig", "Orig", "Com", "Pen: 1.O4 /2.O4 /3.R11 /4.R11", "1.P/2.R(NK)/3.R(NK)/4.PR/5.R(BC)"),
    (87, "5(OB)", "20", "LT vs A", "LG vs B", "RT vs E", "RG vs D", "-1", "BK1", "BK1", "BK1", "Com", "Fumble", "1.R(NK)/2.P/3.PR/4.P/5.R(NK)"),
    (88, "5(OB)", "20", "BK", "BK", "BK", "BK", "-5", "BK1", "BK1", "BK1", "Com", "Pen: 1.D7 /2.D8 /3.R13 /4.K5", "1.R(NK)/2.P/3.PR/4.R(BC)/5.R(NK)"),
    (89, "6(OB)", "10", "LG", "LT", "RG", "RT", "-3", "BK1", "BK1", "BK1", "Com", "Pen: 1.D1 /2.D1 /3.K9 /4.K9", "1.R(NK)/2.P/3.PR/4.P/5.R(NK)"),
    (90, "6(OB)", "11", "LG", "LT", "RG", "RT", "-3", "BK1", "BK1", "BK1", "Com", "Pen: 1.D1 /2.D1 /3.K9 /4.K9", "1.R(NK)/2.P/3.PR/4.P/5.R(NK)"),
    (91, "7(OB)", "22", "LE", "BK", "RE", "BK", "OK", "RE", "RE", "RE", "Com", "Inj: RE", "1.R(NK)/2.P/3.P/4.P/5.R(NK)"),
    (92, "7(OB)", "24", "Break", "Break", "Break", "Break", "-5", "BK2", "BK2", "BK2", "Com", "Pen: 1.O6 /2.O10 /3.K9 /4.K9", "1.R(NK)/2.P/3.PR/4.P/5.R(NK)"),
    (93, "8(OB)", "30", "A", "B", "D", "C", "OK", "Orig", "Orig", "Orig", "Inc", "Inj: K", "1.R(NK)/2.R(BC)/3.P/4.BLZ/5.R(NK)"),
    (94, "8(OB)", "31", "A", "B", "D", "C", "OK", "Orig", "Orig", "Orig", "Com", "Inj: LE", "1.R(NK)/2.R(BC)/3.P/4.BLZ/5.R(NK)"),
    (95, "9(OB)", "34", "LT vs B", "LG vs G", "RT vs D", "RG vs I", "OK", "Orig", "Orig", "Orig", "Com x 2", "Inj: A", "1.R(NK)/2.R(BC)/3.P/4.BLZ/5.R(NK)"),
    (96, "9(OB)", "35", "LT vs A", "LG vs B", "RT vs E", "RG vs D", "OK", "Orig", "Orig", "Orig", "Com x 2", "Inj: C", "1.R(NK)/2.R(BC)/3.P/4.BLZ/5.R(NK)"),
    # --- Z cards (97-109) ------------------------------------------------
    (97, "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Follow 3-rules for Z", "Z"),
    (98, "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Follow 3-rules for Z", "Z"),
    (99, "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Follow 3-rules for Z", "Z"),
    (100, "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Follow 3-rules for Z", "Z"),
    (101, "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Follow 3-rules for Z", "Z"),
    (102, "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Follow 3-rules for Z", "Z"),
    (103, "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Follow 3-rules for Z", "Z"),
    (104, "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Follow 3-rules for Z", "Z"),
    (105, "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Follow 3-rules for Z", "Z"),
    (106, "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Follow 3-rules for Z", "Z"),
    (107, "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Follow 3-rules for Z", "Z"),
    (108, "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Follow 3-rules for Z", "Z"),
    (109, "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Z", "Follow 3-rules for Z", "Z"),
]


def _build_deck_template() -> List[FACCard]:
    """Build the canonical 109-card deck from raw data."""
    cards = []
    for row in _RAW_DECK:
        (num, run, pn, sl, il, sr, ir, er, qk, sh, lg, sc, zres, solo) = row
        cards.append(FACCard(
            card_number=num,
            run_number=run,
            pass_number=pn,
            sweep_left=sl,
            inside_left=il,
            sweep_right=sr,
            inside_right=ir,
            end_run=er,
            quick_kick=qk,
            short_pass=sh,
            long_pass=lg,
            screen=sc,
            z_result=zres,
            solo=solo,
        ))
    return cards


# Singleton template — built once at import time
_DECK_TEMPLATE: List[FACCard] = _build_deck_template()

DECK_SIZE = 109
Z_CARD_COUNT = 13
STANDARD_CARD_COUNT = 96
PASS_NUMBER_RANGE = 48  # 1-48
RUN_NUMBER_RANGE = 12   # 1-12


# ──────────────────────────────────────────────────────────────────────
#  FACDeck — the shuffleable deck
# ──────────────────────────────────────────────────────────────────────

class FACDeck:
    """A shuffleable 109-card Fast Action Card deck.

    Usage::

        deck = FACDeck(seed=42)
        card = deck.draw()   # draws and removes one card
        if deck.cards_remaining == 0:
            deck.reshuffle()  # or auto-reshuffles on next draw
    """

    def __init__(self, seed: Optional[int] = None, solitaire: bool = False):
        self._rng = random.Random(seed)
        self._draw_pile: List[FACCard] = []
        self._discard_pile: List[FACCard] = []
        # 5E Solitaire Rule: remove 1 Z card from the deck
        self._remove_z_count = 1 if solitaire else 0
        self.reshuffle()

    @property
    def cards_remaining(self) -> int:
        return len(self._draw_pile)

    @property
    def cards_used(self) -> int:
        return len(self._discard_pile)

    def reshuffle(self) -> None:
        """Restore all 109 cards and shuffle."""
        self._draw_pile = list(_DECK_TEMPLATE)
        self._discard_pile = []
        # Remove Z cards for solitaire mode
        if self._remove_z_count > 0:
            z_removed = 0
            new_pile = []
            for card in self._draw_pile:
                if card.is_z_card and z_removed < self._remove_z_count:
                    z_removed += 1
                else:
                    new_pile.append(card)
            self._draw_pile = new_pile
        self._rng.shuffle(self._draw_pile)

    def draw(self) -> FACCard:
        """Draw the top card from the deck.

        Auto-reshuffles if deck is exhausted.
        """
        if not self._draw_pile:
            self.reshuffle()
        card = self._draw_pile.pop()
        self._discard_pile.append(card)
        return card

    def draw_non_z(self) -> FACCard:
        """Draw cards until a non-Z card is found.

        Used when a Z card triggers the "draw next card" rule.
        Any Z cards drawn in the process are discarded normally.
        """
        for _ in range(DECK_SIZE):  # safety limit
            card = self.draw()
            if not card.is_z_card:
                return card
        # Extremely unlikely: all remaining cards are Z
        # Force a reshuffle and try once more
        self.reshuffle()
        return self.draw()

    def peek(self) -> Optional[FACCard]:
        """Look at the top card without removing it."""
        if not self._draw_pile:
            return None
        return self._draw_pile[-1]


# ──────────────────────────────────────────────────────────────────────
#  Convenience: module-level draw
# ──────────────────────────────────────────────────────────────────────

_default_deck: Optional[FACDeck] = None


def get_default_deck() -> FACDeck:
    """Return (and lazily create) a module-level default deck."""
    global _default_deck
    if _default_deck is None:
        _default_deck = FACDeck()
    return _default_deck


def draw() -> FACCard:
    """Draw a card from the default deck."""
    return get_default_deck().draw()
