# Game Mechanics

This document explains how Statis Pro Football simulates an NFL game using the **5th Edition (5E) FAC deck system** with Avalon Hill formulae.

---

## 5th Edition: The FAC Deck System

### 109-Card Deck

The 5E system uses a physical deck of **109 Fast Action Cards** (FAC):

| Card Type | Count | Description |
|-----------|-------|-------------|
| Standard | 96 | Numbers 1–48 (each appearing twice: normal + out-of-bounds variant) |
| Z Cards | 13 | Special event cards (injuries, penalties, fumbles) |

Cards are drawn **without replacement**. When the deck is exhausted it is automatically reshuffled.

### FAC Card Fields

Each FAC card contains fields that drive all game mechanics:

| Field | Used For |
|-------|----------|
| RUN# (1–12) | RB card lookup (inside/outside/sweep) |
| PASS# (1–48) | QB/receiver card lookup |
| SL/IL/SR/IR | Defensive blocking matchups (BV vs TV) |
| ER | End-around resolution |
| QK/SH/LG | Receiver targeting override / P.Rush trigger |
| SC | Screen pass result |
| Z RES | Special events (penalty, injury, fumble) |
| SOLO | AI solitaire play calling |

### Pass Play Resolution (5E)

1. Draw FAC card
2. Check **QK/SH/LG target field** — may override the called receiver or trigger **P.Rush** (pass rush by defender in that box)
3. Look up **PASS#** on QB card → receiver letter (A–E), INC, or INT
4. If receiver letter → look up same **PASS#** on receiver's pass-gain card → yards
5. Apply **BV vs TV** blocking matchup using SL/IL/SR/IR field
6. Apply endurance penalties if applicable

### Run Play Resolution (5E)

1. Draw FAC card
2. Check **SL/IL/SR/IR** field → BV vs TV blocking matchup
3. Look up **RUN#** on RB card (inside/outside/sweep) → yards
4. If `(OB)` suffix on card → out of bounds (clock stops)
5. Check **Z RES** for fumbles/injuries

### End-Around (ER)

1. Look up **ER field** on FAC card on receiving player's rush column
2. Only usable once per game per player

---

## Game Flow

### 1. Coin Flip & Kickoff

The game begins with a random coin flip to determine which team receives. The receiving team gets a kickoff resolved from the kicking team's **kickoff table** (a 12-entry table derived from real NFL kickoff statistics). Outcomes include:

- **Touchback** — ball placed at the **20-yard line** (5E rule; safety touchbacks at the 15)
- **Return** — yards determined by the kickoff return table
- **OOB** — ball placed at the 25-yard line (kicking team's penalty)
- **TD** — return touchdown

### 2. Drive Structure

Each drive follows this cycle until it ends:

```
Draw FAC / Roll Dice → Offense + Defense call plays → Resolve Play → Update State
         |                                                  |
       Z-Card? --- Yes ---> Injury/Penalty/Fumble -------> Next Play
         | No                                               ^
       Turnover? -- Yes ---> Change Possession -----------> New Drive
         | No                                               ^
       Touchdown? - Yes ---> Score + PAT/2PC + Kickoff ---> New Drive
         | No                                               ^
       4th Down? -- Punt/FG/Go For It -------------------> ...
         | No
       Advance Down ---> Next Play
```

### 3. Offensive Play Types

| Play | Code | Description |
|------|------|-------------|
| Inside Left / Inside Right | IL / IR | Run between the tackles |
| Sweep Left / Sweep Right | SL / SR | Run to the outside |
| End-Around | ER | WR/TE rushes — only once per player per game |
| Quick Pass | QK | Short, fast release (1–2 receiver letters) |
| Short Pass | SH | Medium pass (up to 3 receiver letters) |
| Long Pass | LG | Deep pass — not allowed within the opponent's 20 |
| Screen Pass | SC | Screen — not allowed within 5 yards of the goal line |
| Punt | — | Special teams |
| Field Goal | — | Special teams |

### 4. Offensive Strategies

| Strategy | Effect |
|----------|--------|
| **Flop** | Motion play that shifts the formation |
| **Sneak** | QB sneaks — uses QB rush column |
| **Draw** | Draws in the pass rush; uses run resolution |
| **Play-Action** | Fakes a run before passing |

### 5. Defensive Formations & Plays

**Personnel (Formation):**

| Formation | Personnel |
|-----------|-----------|
| 4-3 | 4 DL, 3 LB, 4 DB |
| 3-4 | 3 DL, 4 LB, 4 DB |
| Nickel | 3 DL, 2 LB, 6 DB |
| Goal Line | 5 DL, 4 LB, 2 DB |

> **Note:** In the 5th-edition rules, the formation name (4-3, 3-4, Nickel, etc.) is **cosmetic and display-only**. It has no effect on play resolution, run-number modifiers, or completion ranges. All gameplay modifiers come exclusively from the **Play Card** selection (Pass Defense, Run Defense, Blitz, etc.) and individual player ratings. The formation label is tracked to support a future auto-formation convenience feature that will auto-populate the defensive display boxes based on the named personnel grouping, but selecting a different formation name than your actual on-field personnel does not change any card results.

**Play Card:**

| Play | Usage |
|------|-------|
| Pass Defense | Standard pass coverage |
| Prevent Defense | Late-game, concedes short gains |
| Run Defense (No Key / Key Back 1/2/3) | Stop the run, optionally keying a specific back |
| Blitz | 2–5 LBs/DBs declared before offense reveals play |

**Strategy:**

| Strategy | Effect |
|----------|--------|
| Double Coverage | One receiver removed from targets |
| Triple Coverage | Two receivers removed from targets |
| Alternate Double Coverage | Variation of double coverage |

### 6. Blocking Matchups (BV vs TV)

The SL/IL/SR/IR field on the FAC card drives a **blocker vs tackler** matchup for both runs and passes. Results: **Offense Only** (offense wins), **Defense Only** (defense wins), or **Contest** (both matter).

### 7. Down Management

- **1st & 10**: Standard start
- Gaining 10+ yards from the line of scrimmage resets to 1st & 10
- If all 4 downs are used without a first down: turnover on downs (or punt/FG/go-for-it decision)

### 8. Clock Management

Each play consumes time from the 15-minute (900-second) quarter clock:

| Play Type | Time Used |
|-----------|-----------|
| Run (in bounds) | 35–45 seconds |
| Run (out of bounds) | 5–10 seconds |
| Complete Pass (in bounds) | 30–40 seconds |
| Incomplete Pass | 5–10 seconds |
| Kneel | 40 seconds |
| Default | 30 seconds |

When the clock expires:
- **End of Q1/Q3**: Switch sides, continue
- **End of Q2 (Halftime)**: Second half kickoff with possession change
- **End of Q4**: Game over (or overtime if tied)

### 9. Two-Minute Offense

When the offense declares two-minute offense (time <= 2:00 in Q4 or OT):
- All incomplete passes stop the clock
- Running plays out of bounds stop the clock
- **Yardage halving**: rush yards are halved
- **Completion penalty**: -4 to pass completion range
- AI uses two-minute drill automatically when trailing with under 2 minutes

### 10. Timeouts

Each team starts with 3 timeouts per half. Timeouts stop the clock and are tracked by the game state. The API endpoint `POST /games/{game_id}/timeout` calls a timeout for the team in possession or a specified team.

### 11. Overtime

If the score is tied after Q4, a 10-minute overtime period begins. The first team to score wins (sudden death). The overtime kickoff follows standard kickoff rules.

---

## Special Teams

### Field Goals

1. Calculate distance: `(100 - yard_line) + 17` yards
2. Look up success rate from kicker's FG chart by distance range
3. Random roll against that rate
4. On success: kicking team kicks off to opponent
5. On miss: possession changes, no kickoff

### Punts

1. Calculate distance from punter's average +/- random variance
2. Check inside-20 rate for downed punt
3. If not inside-20: resolve punt return
4. **Coffin Corner**: attempt to pin inside 5-yard line
5. **All-Out Punt Rush**: defense declares max rushers

### Kickoffs

- **Standard kickoff**: resolved from team's kickoff table
- **Onside kick**: kicking team attempts recovery; receiving team may declare onside defense
- **Squib kick**: low bouncing kick to avoid a returner
- **Safety free kick**: from the 20-yard line after a safety; touchback at the 15

### Fake Plays

- **Fake punt**: resolve as a run play from the punt formation
- **Fake field goal**: resolve as a pass or run from the FG formation

### Two-Point Conversion

After a touchdown, offense may declare a two-point conversion instead of kicking the PAT. Resolved as a regular play from the 3-yard line.

---

## Scoring

| Event | Points |
|-------|--------|
| Touchdown | 6 |
| Extra Point (kick) | 1 |
| Two-Point Conversion | 2 |
| Field Goal | 3 |
| Safety | 2 |

**Safety mechanics**: The defense scores 2 points. The team that conceded then kicks off from their own 20-yard line (a **safety free kick**). The receiving team's touchback is placed at the 15 (5 yards closer than a normal touchback).

---

## The Endurance System

Players have endurance ratings that limit how many consecutive plays they can carry the ball (or be targeted):

| Level | Rule |
|-------|------|
| RB-0 | Unlimited — no restriction |
| RB-1 | Must rest 1 play after carrying |
| RB-2 | Must rest 2 plays after carrying |
| RB-3 | Once per drive |
| RB-4 | Once per quarter |

**Violation penalty (runs)**: +2 added to RUN# (effectively reduces gains).
**Violation penalty (passes)**: -5 to completion range.

QB endurance is rated A/B/C and limits how many passes per drive before a penalty applies.

On **FAC check-off passes** (receiver is not the intended target), endurance penalty for the actual receiver is ignored.

---

## The Injury System

When a Z-card or injury roll occurs:

1. The injured player is identified
2. Their backup is immediately promoted to the starter slot
3. The injury duration (plays) is tracked in `GameState.injuries`
4. Players return automatically after their injury duration expires
5. If a player's backup is also injured, the next available depth chart player fills in

---

## The Display Box System

Defenders are assigned to 15 boxes on the defensive display (A-O):

| Row | Boxes | Positions |
|-----|-------|-----------|
| Row 1 | A-E | DL (DE/DT) — 0-2 players per box |
| Row 2 | F-J | LB only — one per box |
| Row 3 | K-O | DB — CB in K/O, FS in M, SS in N, any DB in L |

Blitz players are removed from Row 2/3 before the play. Pass coverage assignments link defenders to receiver letters (A-O) for pass defense.

---

## Big Play Defense

Teams that won 9+ games in the prior season may activate **Big Play Defense** once per game. When active:
- Run defense is significantly strengthened
- Pass defense is enhanced

---

## Turnover System

### Interceptions

1. QB card PASS# lookup returns INT
2. Interception return resolved from the interception table (12 entries, position columns)
3. Possession changes

### Fumbles

1. Card slot shows FUMBLE
2. Roll fumble recovery: offense or defense recovers
3. If defense recovers: possession changes
4. Roll fumble return chart for potential return yardage

---

## Team Ratings

Each team has ratings that modify play outcomes:

- **Offense Rating** (60–95): Used for context in play resolution
- **Defense Rating** (60–90): Applied as a modifier to opponent's offensive plays
  - Run Stop modifies rushing yards
  - Coverage modifies passing yards

**5E Authentic Defensive Ratings (per player card):**
- **Pass Rush (PR)**: 0–3 scale
- **Pass Defense**: -2 to +4 scale
- **Tackle**: -5 to +4 scale
- **Intercept Range**: column-based interception threshold
