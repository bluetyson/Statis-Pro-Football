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

### Step 2 — Covering Defender Priority (Pass Plays)

When the covering defender's box is known (the defender matched to the targeted receiver), that box receives **double weight** in the random draw pool.

### Step 3 — Play-Type Weighted Random Draw (Fallback)

When no direct box is available (no matchup, empty boxes, special teams, etc.), a **weighted random draw** over all occupied boxes is used.  One box is drawn; the player in it gets a full tackle (1.0).

Weights vary by play type (see tables below).  A higher weight means that box's defender is more likely to make the tackle.

---

## Weight Tables by Play Type

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

## Adjusting the Tables

To change who makes tackles, edit `PlayResolver._TACKLE_WEIGHTS` in `engine/play_resolver.py`.  Each key corresponds to the play-type categories above.  Increase a box's weight to make that position more likely to make the tackle; decrease (or set to 0) to make them less likely.

**Example — reducing DL tackles on quick passes:**  
Change QUICK_PASS weights for B/C/D from 4 to 1–2 and add the difference to G/H/I (ILBs).
