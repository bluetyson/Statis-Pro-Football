# Fumble Recovery Mechanics

## Overview

Fumble resolution happens in two stages:

1. **Team-level** — did the offense *lose* the fumble (defense recovers)?  Resolved via FAC Pass Number and the team's Fumbles Lost rating.
2. **Player-level** — *which* defender picks up the loose ball?  Resolved by a weighted random draw that favours the tackler.

---

## Stage 1 — Team-Level Fumble Resolution

### When a Fumble Is Triggered

A fumble can occur on:
- **Running plays** — the ball-carrier's RUN# result on his player card shows `FUMBLE`.
- **Kickoff / punt returns** — the return table value ends with `f`.

Once a fumble is flagged, a second FAC card is drawn (Z cards are re-drawn as non-Z) and its **Pass Number (PN)** is used to determine recovery.

### Resolution Formula

```
adjusted_max = fumbles_lost_max + def_fumble_adj
if is_home:  adjusted_max -= 1        # home team is harder to strip
adjusted_max = clamp(adjusted_max, 0, 48)

if 1 ≤ PN ≤ adjusted_max:  DEFENSE recovers (turnover)
else:                        OFFENSE recovers (no turnover)
```

### Parameters

| Parameter | Source | Description |
|-----------|--------|-------------|
| `fumbles_lost_max` | Offensive team card | Upper end of the "fumbles lost" range, e.g. 21 means PN 1–21 = defense recovers |
| `def_fumble_adj` | Defensive team card | Added to the range; a positive value means the defence recovers fumbles more easily |
| `is_home` | Game state | The home team gets a –1 adjustment (slight home-field advantage in loose-ball situations) |

### Example

- Offensive team `fumbles_lost_max = 21`, defensive `def_fumble_adj = 2`, home game:
- `adjusted_max = 21 + 2 – 1 = 22`
- PN 1–22 → defense recovers; PN 23–48 → offense recovers.

---

## Stage 2 — Player-Level Recovery Assignment

Called only when `fumble_lost = True` (the defense has already been determined to recover the ball).

### Algorithm

1. **Identify the tackler** — the player(s) assigned tackle credit for the same play are the primary recovery candidates.  If there are multiple tacklers, the one with the highest credit share is chosen as the primary.

2. **Build a weighted pool** — all occupied defensive boxes enter the pool with weights drawn from the same play-type tables used for tackle assignment (see [tackle-mechanics.md](tackle-mechanics.md)).

3. **Double the tackler's weight** — the primary tackler's weight is multiplied by ×2 because they are already in contact with the ball carrier.

4. **Single weighted random draw** — one defender is selected; they receive the fumble recovery credit.

### Pseudocode

```
weight_key = normalise_play_type(play_type)   # e.g., "INSIDE_RUN", "SWEEP", …
base_weights = TACKLE_WEIGHTS[weight_key]

for each occupied box:
    w = base_weights[box]
    if box.player == tackler:
        w *= 2
    pool.add(box.player, weight=max(w, 0.1))

recoverer = random.choices(pool)[0]
```

### Recovery Weight Tables

The same 15-box weight tables from [tackle-mechanics.md](tackle-mechanics.md) are used here.  The tackler boost means:

- On an inside run where the MLB (H) made the tackle, the MLB has roughly double the chance of recovering the fumble versus a raw play-type draw.
- On a sweep where the OLB (F or J) made the tackle, that OLB leads recovery probability.

---

## Special Cases

### Kickoff Return Fumbles

Kickoff-return fumbles use the same team-level formula but with the kicking team as the "defense."  Player-level recovery for kick-return fumbles is logged but follows the same weighted-draw logic applied to the return coverage personnel.

### Punt Return Fumbles

Identical to kickoff return — second FAC is drawn, team formula applied, then player-level draw from the coverage unit.

### No Defenders Available

If `defenders_by_box` is empty (unusual formation edge case), recovery credit is not assigned (returns `None`).  The fumble turnover is still recorded at the team level.

---

## Adjusting Recovery Behaviour

| What you want | How to change it |
|---------------|-----------------|
| Defense recovers fumbles more often | Increase `def_fumble_adj` on the defensive team card |
| Offense retains fumbles more often | Decrease `fumbles_lost_max` on the offensive team card |
| A specific player recovers more fumbles | The only lever is the underlying play-type weight for their box — see [tackle-mechanics.md](tackle-mechanics.md) |
| Tackler advantage on recovery | Edit the `w *= 2.0` multiplier in `assign_fumble_recovery` in `engine/play_resolver.py` |
