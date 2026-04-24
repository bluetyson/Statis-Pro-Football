# Sack Assignment Mechanics

## Overview

When a pass rush results in a sack, the engine assigns sack credit to the defender(s) most responsible.  Credit is weighted by each player's `pass_rush_rating` and their position in the defensive box layout.

---

## Defensive Box Layout (Pass Rush)

| Row | Boxes | Typical Occupants |
|-----|-------|-------------------|
| Row 1 — Pass Rush Line | A, B, C, D, E | DE (A/E), DT/NT (B/C/D) |
| Row 2/3 — Blitzers | F–J (LB), K–O (DB) | LBs and DBs who blitz |

---

## Algorithm

### Step 1 — Build the Candidate Pool

Two sources contribute to the sack candidate pool:

**Row 1 (A–E) — Regular Pass Rushers:**  
Each occupied box in Row 1 contributes the player there with weight equal to their `pass_rush_rating`.

| `pass_rush_rating` | Meaning |
|--------------------|---------|
| 0 | No pass rush threat |
| 1 | Below average |
| 2 | Average / minimum worthwhile value |
| 3–4 | Above average |
| 5+ | Elite pass rusher |

**Blitzers (Row 2/3) — LBs and DBs:**  
Each blitzing player (moved from Row 2/3 into the pass-rush rush) contributes their box with **fixed weight 2**, regardless of their `pass_rush_rating`.

### Step 2 — Weighted Random Draw

`random.choices` draws one box from the pool, weighted as described above.  Each box has a minimum weight of 1 to prevent zero-weight exclusion.

### Step 3 — Assign Credit

| Players in Drawn Box | Credit |
|----------------------|--------|
| 1 player | Full sack (1.0) |
| 2 players (shared box) | Half sack each (0.5) |

### Fallback — No Row 1 / No Blitzers

If the candidate pool is empty (e.g., unusual formation with no one in A–E and no blitzers), the engine falls back to the player with the highest `pass_rush_rating` across the entire defense.

| Situation | Credit |
|-----------|--------|
| 1 player with highest rating | Full sack (1.0) |
| Tied top rating (2+ players) | Split equally (e.g., 0.5 for a tie of 2) |

---

## Blitz Box Removals

When a Blitz defense is called, players are removed from these boxes before the play based on the Pass Number (PN) drawn from the FAC:

| PN Range | Boxes Emptied |
|----------|--------------|
| 1 – 26   | F, J |
| 27 – 35  | F, J, M |
| 36 – 48  | F, G, H, I, J |

These removed players become the blitzers and contribute weight 2 each to the sack pool.

---

## Relationship to Pass Rush Adjustment (5E Rules)

Per 5E rules the blitz also applies a **+10 completion modifier** to quick passes (defender advantage on deeper drops) and triggers automatic **Pass Rush** resolution on short and long passes instead of a completion check.  The sack-credit algorithm above operates *after* the pass-rush check has determined a sack occurred.

---

## Adjusting Pass Rush Weights

To change who gets sack credit:

1. **Increase a DL player's `pass_rush_rating`** on their player card — this directly increases their weight in the sack pool and makes it more likely they are assigned credit.
2. **Decrease `pass_rush_rating` to 0 or 1** for players you do not want accumulating sacks (e.g., interior linemen who are gap-setters rather than pass rushers).
3. The blitz weight (2) is fixed by 5E rules; to adjust it, edit the constant in `assign_sack_credit` in `engine/play_resolver.py`.
