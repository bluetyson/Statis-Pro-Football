# Game Mechanics

This document explains how Statis Pro Football simulates an NFL game, from dice rolling to scoring.

## The Fast Action Dice System

At the heart of every play is the **Fast Action Dice** — a system using two 8-sided dice (d8), each producing values from 1 to 8. Together they create a two-digit number ranging from 11 to 88, giving 64 possible outcomes.

### Dice Components

Each roll produces three pieces of information:

| Component | Range | Purpose |
|-----------|-------|---------|
| Two-digit number | 11–88 | Indexes into player card columns |
| Play Tendency | RUN, SHORT_PASS, LONG_PASS, BLITZ | Suggests the type of play |
| Penalty Check | ~8% chance (5 specific combos) | Triggers penalty chart lookup |
| Turnover Modifier | 1–8 | Additional random factor for turnovers |

### Play Tendency Distribution

The 64 dice combinations are mapped to play tendencies:

- **RUN** — ~34% of outcomes (most common)
- **SHORT_PASS** — ~28% of outcomes
- **LONG_PASS** — ~25% of outcomes
- **BLITZ** — ~13% of outcomes (least common)

### Penalty Triggers

Five specific dice combinations trigger a penalty check:
- (1,7), (3,7), (5,8), (7,1), (8,2)

When a penalty is triggered, the full 64-entry penalty chart is consulted with a second dice roll to determine the specific penalty type and yardage.

## Game Flow

### 1. Coin Flip & Kickoff

The game begins with a random coin flip to determine which team receives. The receiving team gets a kickoff:
- **75% chance** of a touchback (ball at the 25-yard line)
- **25% chance** of a return (18–30 yards typically)

### 2. Drive Structure

Each drive follows this cycle until it ends:

```
Roll Dice → Determine Tendency → AI Calls Play → Resolve Play → Update State
     ↓                                                    ↓
  Penalty? ──────── Yes ──→ Apply Penalty ─────────→ Next Play
     ↓ No                                               ↑
  Turnover? ─────── Yes ──→ Change Possession ──────→ New Drive
     ↓ No                                               ↑
  Touchdown? ────── Yes ──→ Score + XP + Kickoff ───→ New Drive
     ↓ No                                               ↑
  4th Down? ─────── Punt/FG/Go For It ─────────────→ ...
     ↓ No
  Advance Down ──→ Next Play
```

### 3. Play Resolution

#### Running Plays

1. Roll dice → get slot number (e.g., "45")
2. Consult the RB's Inside Run or Outside Run card column
3. The slot returns: result type (GAIN/FUMBLE), yards, and touchdown flag
4. Apply defense modifier: `yards = yards - (defense_run_stop - 50) / 50`
5. If FUMBLE: roll fumble recovery (50/50 offense/defense)

#### Passing Plays

1. Roll dice → get slot number
2. Consult the QB's Short Pass, Long Pass, or Screen Pass column
3. Check the slot: COMPLETE, INCOMPLETE, INT, or SACK
4. If COMPLETE: also check receiver's reception column (may downgrade to INCOMPLETE)
5. Apply defense modifier: `yards = yards × (1 - (defense_coverage - 50) / 200)`
6. If INT: roll interception return chart
7. If SACK: negative yardage applied

#### Field Goals

1. Calculate distance: `(100 - yard_line) + 17` yards
2. Look up success rate from kicker's FG chart by distance range
3. Random roll against that rate

#### Punts

1. Calculate distance from punter's average ± random variance
2. Check inside-20 rate for downed punt
3. If not inside-20: roll punt return chart

### 4. Down Management

- **1st & 10**: Standard start
- Gaining 10+ yards from the line of scrimmage resets to 1st & 10
- If all 4 downs are used without a first down: turnover on downs (or punt/FG)

### 5. Clock Management

Each play consumes time from the 15-minute (900-second) quarter clock:

| Play Type | Time Used |
|-----------|-----------|
| Run | 25–45 seconds |
| Complete Pass | 20–40 seconds |
| Incomplete Pass | 5–10 seconds |
| Kneel | 40 seconds |
| Default | 30 seconds |

When the clock expires:
- **End of Q1/Q3**: Switch sides, continue
- **End of Q2 (Halftime)**: Second half kickoff with possession change
- **End of Q4**: Game over (or overtime if tied)

### 6. Overtime

If the score is tied after Q4, a 10-minute overtime period begins. The first team to score wins (simplified sudden death).

## Scoring

| Event | Points |
|-------|--------|
| Touchdown | 6 |
| Extra Point (kick) | 1 |
| Two-Point Conversion | 2 |
| Field Goal | 3 |
| Safety | 2 |

After a touchdown, the kicker attempts an extra point based on their XP rate (typically 95–99%).

## AI Play Calling (Solitaire Mode)

The AI evaluates the game situation and calls plays accordingly:

### Situational Logic

| Situation | AI Decision |
|-----------|------------|
| 4th down, deep in own territory | PUNT |
| 4th down, within FG range | FIELD GOAL |
| 4th down, short yardage in opponent territory | GO FOR IT (run) |
| Trailing with < 2 minutes left | TWO-MINUTE DRILL (aggressive passing) |
| Leading with < 1 minute left | KNEEL |
| 1st down | Follow dice tendency |
| 2nd and short (≤3 yards) | Run or short pass |
| 2nd and long (>7 yards) | Pass (short or long) |
| 3rd and short (≤2 yards) | Run sneak or quick pass |
| 3rd and long (>10 yards) | Long pass |

### Defensive Formations

The AI also calls defensive formations:

| Situation | Formation |
|-----------|-----------|
| 3rd and long | NICKEL_BLITZ or NICKEL_ZONE |
| 3rd and short | NICKEL_COVER2 |
| Short yardage | GOAL_LINE |
| Normal | 4_3, 3_4, 4_3_COVER2, 3_4_ZONE |
| Blitz tendency | 4_3_BLITZ |

## Penalty System

When a penalty is triggered (~8% of plays), a second dice roll consults the 64-entry penalty chart:

### Common Penalties

| Penalty | Yards | Auto First Down? |
|---------|-------|-------------------|
| Holding (Offense) | 10 | No |
| False Start | 5 | No |
| Pass Interference (Defense) | Spot | Yes |
| Roughing the Passer | 15 | Yes |
| Holding (Defense) | 5 | Yes |
| Face Mask | 15 | Yes |
| Encroachment | 5 | No |
| Delay of Game | 5 | No |

### Penalty Application

- **Offensive penalties**: Move the offense backward, add to distance needed
- **Defensive penalties**: Move the offense forward, may grant automatic first down
- **Loss of down**: Some penalties (e.g., Ineligible Receiver) cost a down

## Turnover System

### Interceptions

When a QB card slot shows INT:
1. The pass is intercepted
2. Roll the interception return chart for return yardage
3. 5% chance of a pick-six (99-yard return = touchdown)
4. Possession changes

### Fumbles

When a card slot shows FUMBLE:
1. Roll fumble recovery: OFFENSE (4/8 chance) vs DEFENSE (4/8 chance)
2. If defense recovers: possession changes
3. Roll fumble return chart for potential return yardage
4. 7% chance of fumble return touchdown

## Team Ratings

Each team has two ratings that modify play outcomes:

- **Offense Rating** (60–95): Higher = better offensive plays, used as context for play resolution
- **Defense Rating** (60–90): Applied as a modifier to opponent's offensive plays
  - Defense Run Stop modifies rushing yards
  - Defense Coverage modifies passing yards
