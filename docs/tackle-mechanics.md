# Tackle Assignment Mechanics

## Overview

After every play that results in a tackle (runs, completed passes, screen passes, etc.), the engine assigns individual tackle credit to one or more defenders.  The goal is realistic stat distribution: DTs and ILBs rack up tackles on inside runs, edge players dominate sweeps, DBs lead on pass plays.

---

## Defensive Box Layout

The 15 defensive boxes are arranged in three rows:

| Row | Boxes | Typical Occupants |
|-----|-------|-------------------|
| Row 1 — DL | A, B, C, D, E | DE (A/E), DT/NT (B/C/D) |
| Row 2 — LB | F, G, H, I, J | OLB (F/J), ILB/MLB (G/H/I) |
| Row 3 — DB | K, L, M, N, O | CB (K/O), SS (L/N), FS (M) |

---

## Algorithm

### Step 1 — Direct Box Assignment (Blocking Matchup)

If the blocking-matchup resolution identified a specific contested box (or boxes), the player(s) occupying those boxes receive tackle credit directly.

| Scenario | Credit |
|----------|--------|
| 1 box, 1 player | Full tackle (1.0) |
| 1 box, 2 players | Half tackle each (0.5) |
| 2 boxes, 1 player each | Half tackle each (0.5) |

### Step 2 — RN Table Lookup (primary random path)

When no direct box assignment applies, a **fresh Run Number (RN) is drawn from the deck** specifically for tackle resolution (1–12).  This draw is intentionally **independent** of the FAC card used to determine the play result (yards, outcome), so tackle credit is never tied to or correlated with the play's own RN.

The fresh RN is looked up in the table below:

- **Single box entry** — the occupant(s) of that box get the tackle.
- **Two-box entry** (e.g. `K O`) — flip a FAC card for its PN:
  - PN 1–24 → first box; PN 25–48 → second box.
- **Three-box entry** (e.g. `G H I`) — flip a FAC card for its PN:
  - PN 1–16 → first; PN 17–32 → second; PN 33–48 → third.
- **DEF entry** — the covering defender's box is used (pass plays); M (FS) is the intended default for Quick RN 4.

**If the resolved box is unoccupied:**
- *Run play* — nearest occupied box by grid distance; among ties, the player with the highest tackle_rating wins; if still tied, half a tackle each.
- *Pass play* — use the covering defender; if none, fall back to weighted-random draw.

**Multiple players in the resolved box** — all share equally (half a tackle each for 2 players; a third each for 3 players, etc.).

### Step 3 — Play-Type Weighted Random Draw (Fallback)

Only used when the RN table produces no result (unknown play type, no defenders in resolved box and no valid fallback).  A **weighted random draw** over all occupied boxes is performed.  Weights vary by play type (see tables below).

---

## RN Tackle Table

| RN | Inside | Sweep | Screen | Quick | Short | Long |
|----|--------|-------|--------|-------|-------|------|
| 1  | E | E | E | N | N | N |
| 2  | N | B | B | K | G H I | L |
| 3  | M | C | C | O | F J | L |
| 4  | J | D | D | DEF | L | M |
| 5  | H | J | J | DEF | DEF | DEF |
| 6  | I | F | F | DEF | DEF | DEF |
| 7  | G | H | H | DEF | DEF | DEF |
| 8  | F | K O | K O | H | M | M |
| 9  | B | I | I | G | O | O |
| 10 | C | J | J | I | O | O |
| 11 | D | N M | N M | F | K | K |
| 12 | A | A | A | J | K | K |

> **Note:** The original design chart had "S" for Quick RN 4; this is implemented as "DEF" (the covering defender).

---

## Weight Tables by Play Type (Weighted-Random Fallback)

These weights are used only when no RN is available.  A higher weight means that box's defender is more likely to make the tackle.

### INSIDE_RUN (IL / IR / Sneak / End-Around)

DTs (B/D) and MLB/ILB (G/H/I) are the primary tacklers.

| Box | Weight | Typical Position |
|-----|--------|-----------------|
| A   | 4      | DE |
| B   | 10     | DT |
| C   | 8      | NT/DT |
| D   | 10     | DT |
| E   | 4      | DE |
| F   | 5      | OLB |
| G   | 12     | ILB |
| H   | 15     | MLB ← highest |
| I   | 12     | ILB |
| J   | 5      | OLB |
| K   | 2      | CB |
| L   | 1      | SS |
| M   | 1      | FS |
| N   | 2      | SS |
| O   | 2      | CB |

### SWEEP (SL / SR)

Edge players — DEs (A/E) and OLBs (F/J) — dominate.

| Box | Weight | Typical Position |
|-----|--------|-----------------|
| A   | 14     | DE ← very high |
| B   | 4      | DT |
| C   | 2      | NT |
| D   | 4      | DT |
| E   | 14     | DE ← very high |
| F   | 12     | OLB |
| G   | 3      | ILB |
| H   | 3      | MLB |
| I   | 3      | ILB |
| J   | 12     | OLB |
| K   | 6      | CB |
| L   | 2      | SS |
| M   | 1      | FS |
| N   | 2      | SS |
| O   | 6      | CB |

### QUICK_PASS

More balanced across all three rows — quick throws can be caught in any zone.

| Box | Weight | Typical Position |
|-----|--------|-----------------|
| A   | 6      | DE |
| B   | 4      | DT |
| C   | 4      | NT |
| D   | 4      | DT |
| E   | 6      | DE |
| F   | 9      | OLB |
| G   | 7      | ILB |
| H   | 7      | MLB |
| I   | 7      | ILB |
| J   | 9      | OLB |
| K   | 12     | CB |
| L   | 3      | SS |
| M   | 8      | FS |
| N   | 8      | SS/NB |
| O   | 12     | CB |

> **Note for adjustment:** Quick passes currently give DL boxes A/B/D/E weights of 4–6, which is the same order of magnitude as LBs. If a DT (e.g. in box B/C/D) is accumulating too many tackles on quick passes, reduce those weights to 1–2 and redistribute to LB/DB rows.

### SHORT_PASS

DBs and CBs lead; LBs secondary; DL rarely involved.

| Box | Weight | Typical Position |
|-----|--------|-----------------|
| A   | 2      | DE |
| B   | 1      | DT |
| C   | 1      | NT |
| D   | 1      | DT |
| E   | 2      | DE |
| F   | 7      | OLB |
| G   | 5      | ILB |
| H   | 5      | MLB |
| I   | 5      | ILB |
| J   | 7      | OLB |
| K   | 18     | CB ← high |
| L   | 5      | SS |
| M   | 10     | FS |
| N   | 10     | SS/NB |
| O   | 18     | CB ← high |

### LONG_PASS

Overwhelmingly DBs — CBs (K/O) and FS (M) are the primary tacklers/defenders.

| Box | Weight | Typical Position |
|-----|--------|-----------------|
| A   | 1      | DE |
| B   | 0      | DT (not involved) |
| C   | 0      | NT (not involved) |
| D   | 0      | DT (not involved) |
| E   | 1      | DE |
| F   | 3      | OLB |
| G   | 2      | ILB |
| H   | 2      | MLB |
| I   | 2      | ILB |
| J   | 3      | OLB |
| K   | 22     | CB ← very high |
| L   | 4      | SS |
| M   | 18     | FS ← high |
| N   | 8      | SS/NB |
| O   | 22     | CB ← very high |

> **Note:** Boxes with weight 0 use a minimum floor of 0.1 in the engine to keep them eligible in degenerate situations (e.g., only DTs on the field).

### SCREEN_PASS

Outside containment — OLBs (F/J) and DEs (A/E) are first; DBs second; interior DL rarely involved.

| Box | Weight | Typical Position |
|-----|--------|-----------------|
| A   | 12     | DE |
| B   | 3      | DT |
| C   | 1      | NT |
| D   | 3      | DT |
| E   | 12     | DE |
| F   | 14     | OLB ← highest |
| G   | 3      | ILB |
| H   | 2      | MLB |
| I   | 3      | ILB |
| J   | 14     | OLB ← highest |
| K   | 10     | CB |
| L   | 3      | SS |
| M   | 4      | FS |
| N   | 4      | SS/NB |
| O   | 10     | CB |

---

## Play-Type Mapping

| Offensive Play | Weight Key |
|----------------|-----------|
| Running Inside Left / Right | INSIDE_RUN |
| End Around / QB Sneak | INSIDE_RUN |
| Running Sweep Left / Right | SWEEP |
| Quick Pass | QUICK_PASS |
| Short Pass | SHORT_PASS |
| Long Pass | LONG_PASS |
| Screen Pass | SCREEN_PASS |
| All other / unknown | SHORT_PASS (default) |

---

## Fumble Recovery

When the defense recovers a fumble, `assign_fumble_recovery()` picks the specific defender who scoops up the ball.

### Algorithm

1. **RN table lookup** — a **fresh** RN is drawn from the deck (independent of all earlier draws) and looked up in `_RN_TACKLE_TABLE` for the current play type, exactly as tackle credit is resolved.  Multi-box entries use an additional PN flip; `DEF` entries fall through to the weighted-random fallback.
2. **Weighted-random fallback** — if the resolved box is unoccupied, or the play type is not in the RN table, the engine uses the `_TACKLE_WEIGHTS` weighted-random draw.  If a tackler was already identified for this play, their box weight is doubled (they're already in contact with the ball).

### Design rationale

Using the same RN table for both tackle credit and fumble recovery is intentional.  The position that was most likely to make the tackle is also the most likely position to be near a loose ball.  The two draws are always independent (separate card draws from the deck) so neither result is correlated with the play's yardage outcome.



**Primary table (RN-based):** edit `PlayResolver._RN_TACKLE_TABLE` in `engine/play_resolver.py`.  Each inner list has 12 entries (index 0 = RN 1, index 11 = RN 12).  Change a single box letter, swap two-box entries for single-box entries, or add "DEF" to alter who typically makes the tackle for each RN value.

**Fallback table (weighted-random):** edit `PlayResolver._TACKLE_WEIGHTS`.  This is only used when no RN is available (Z-card draws, special teams, etc.).  Increase a box's weight to make that position more likely; decrease (or set to 0) to make them less likely.

**Example — swapping Inside RN 1 from E (DE) to H (MLB):**
Change `_RN_TACKLE_TABLE["INSIDE_RUN"][0]` from `'E'` to `'H'`.
