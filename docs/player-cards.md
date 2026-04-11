# Player Cards

Player cards are the core of Statis Pro Football. Each player has a card with 64 slots that determine the outcome of plays involving that player.

## Card Overview

A player card is a lookup table with 64 entries, one for each possible dice roll (11 through 88). When the dice show "37", you look up slot "37" on the relevant player's card column to find the result.

### Card Structure

```
Player: Patrick Mahomes (QB #15, KC)
Grade: A
──────────────────────────────────────
SHORT PASS COLUMN:
  Slot 11: SACK, -4 yards
  Slot 12: INCOMPLETE
  Slot 13: INT
  Slot 14: INCOMPLETE
  Slot 15: COMPLETE, 10 yards
  Slot 16: COMPLETE, 7 yards
  Slot 17: COMPLETE, 12 yards, TD
  Slot 18: COMPLETE, 6 yards
  ...
  Slot 88: COMPLETE, 8 yards
──────────────────────────────────────
LONG PASS COLUMN:
  Slot 11: COMPLETE, 22 yards
  Slot 12: COMPLETE, 25 yards
  ...
  Slot 88: INCOMPLETE
```

## Card Columns by Position

### Quarterback (QB)

QBs have three card columns:

| Column | Used When | Typical Outcomes |
|--------|-----------|-----------------|
| **Short Pass** | Short/medium passes | COMPLETE (4–20 yds), INCOMPLETE, INT, SACK |
| **Long Pass** | Deep passes | COMPLETE (15–50 yds), INCOMPLETE, INT |
| **Screen Pass** | Screen plays | COMPLETE (1–15 yds), INCOMPLETE, FUMBLE, INT |

**How QB stats translate to cards:**

| Real Stat | Card Effect |
|-----------|------------|
| Completion % | More COMPLETE slots (e.g., 67% → ~43/64 completions) |
| Yards per attempt | Higher yard values on COMPLETE slots |
| Interception rate | More INT slots (e.g., 2.5% → 2/64 INTs) |
| Sack rate | More SACK slots with negative yardage |

**Grade effects on Short Pass:**

| Grade | Completion Yards Pool | Notes |
|-------|----------------------|-------|
| A+/A | 4, 5, 6, 7, 8, 9, 10, 12, 14, 16, 18, 20 | Weighted toward 6–10 |
| B | 3, 4, 5, 6, 7, 8, 9, 10, 12, 14 | Weighted toward 5–7 |
| C | 2, 3, 4, 5, 6, 7, 8, 10, 12 | Weighted toward 4–6 |
| D | 1, 2, 3, 4, 5, 6, 7, 8 | Weighted toward 3–5 |

**Example: Patrick Mahomes (A grade, 67.2% comp, 1.6% INT, 5.5% sack)**
- Short Pass: ~43 COMPLETE, ~14 INCOMPLETE, ~1 INT, ~4 SACK, ~2 with TD flag
- Long Pass: ~24 COMPLETE (15–50 yds), ~37 INCOMPLETE, ~2 INT
- Screen Pass: ~42 COMPLETE, ~16 INCOMPLETE, ~3 FUMBLE, ~3 INT

### Running Back (RB)

RBs have two card columns:

| Column | Used When | Typical Outcomes |
|--------|-----------|-----------------|
| **Inside Run** | Runs up the middle/left | GAIN (-3 to +15 yds), FUMBLE |
| **Outside Run** | Runs to the outside/right | GAIN (-3 to +20 yds), FUMBLE |

**How RB stats translate to cards:**

| Real Stat | Card Effect |
|-----------|------------|
| Yards per carry | Higher yard values on GAIN slots |
| Fumble rate | More FUMBLE slots (e.g., 1.2% → 1/64 fumbles) |

**Grade effects on Inside Run:**

| Grade | Yards Pool | Notes |
|-------|-----------|-------|
| A+/A | -1 to 15 | Weighted toward 3–5, rare big gains |
| B | -1 to 10 | Weighted toward 3–5 |
| C | -2 to 8 | Weighted toward 2–4 |
| D | -3 to 6 | Weighted toward 1–3 |

Outside runs have slightly more variance (bigger gains possible, but also more negative plays).

**Example: Derrick Henry (A grade, 5.1 ypc, 0.8% fumble)**
- Inside Run: ~63 GAIN (weighted toward 3–7 yards), ~1 FUMBLE, ~2% TD chance
- Outside Run: ~63 GAIN (wider range, -2 to 20), ~1 FUMBLE, ~4% TD chance

### Wide Receiver / Tight End (WR/TE)

WRs and TEs have two card columns:

| Column | Used When | Typical Outcomes |
|--------|-----------|-----------------|
| **Short Reception** | Short/medium targets | CATCH (2–14 yds), INCOMPLETE |
| **Long Reception** | Deep targets | CATCH (15–45 yds), INCOMPLETE |

**How WR stats translate to cards:**

| Real Stat | Card Effect |
|-----------|------------|
| Catch rate | More CATCH slots (e.g., 72% → ~46/64 catches) |
| Avg yards | Yard values on CATCH slots |

The long reception column uses `catch_rate × 0.7` for WRs and `catch_rate × 0.6` for TEs to reflect the difficulty of deep catches.

**Grade effects on Short Reception:**

| Grade | Yards Pool |
|-------|-----------|
| A+/A | 4, 5, 6, 7, 8, 9, 10, 12, 14 |
| B | 3, 4, 5, 6, 7, 8, 9, 10, 12 |
| C | 2, 3, 4, 5, 6, 7, 8, 9, 10 |
| D | 1, 2, 3, 4, 5, 6, 7, 8 |

**Example: CeeDee Lamb (A grade, 74% catch, 14.0 avg yards)**
- Short Reception: ~47 CATCH (4–14 yds), ~17 INCOMPLETE, ~4% TD chance
- Long Reception: ~33 CATCH (15–45 yds), ~31 INCOMPLETE, ~6% TD chance

### Kicker (K)

Kickers don't use the 64-slot system. Instead they have:

| Attribute | Description |
|-----------|------------|
| **FG Chart** | Success rates by distance range |
| **XP Rate** | Extra point success percentage |

**FG Chart Example: Harrison Butker (A grade, 90.0% accuracy)**

| Distance | Success Rate |
|----------|-------------|
| 0–19 yards | 100% |
| 20–29 yards | 100% |
| 30–39 yards | 95% |
| 40–49 yards | 90% |
| 50–59 yards | 75% |
| 60+ yards | 60% |

The chart is generated from the kicker's base accuracy:
- `0-19`: accuracy + 15% (capped at 100%)
- `20-29`: accuracy + 10% (capped at 100%)
- `30-39`: accuracy + 5%
- `40-49`: base accuracy
- `50-59`: accuracy - 15%
- `60+`: accuracy - 30%

### Punter (P)

Punters have two attributes:

| Attribute | Description | Range |
|-----------|------------|-------|
| **Avg Distance** | Average punt distance | 41–50 yards |
| **Inside-20 Rate** | Chance of pinning inside 20 | 30–45% |

Actual punt distance is: `avg_distance ± random_variance` (gaussian, σ=5).

### Defenders (DEF)

Defenders have three ratings (0–99 scale):

| Rating | Effect |
|--------|--------|
| **Pass Rush** | Modifies sack probability and pass rush effectiveness |
| **Coverage** | Reduces passing yards gained against their defense |
| **Run Stop** | Reduces rushing yards gained against their defense |

Defensive ratings are influenced by position:
- **DE/DT/DL**: Higher pass rush, lower coverage
- **CB/S**: Higher coverage, lower pass rush
- **LB**: Higher run stop, balanced otherwise

## Player Grades

Grades reflect overall player quality:

| Grade | Tier | Description |
|-------|------|-------------|
| A+ | Elite | Top 5 at position (e.g., Mahomes, McCaffrey) |
| A | Elite | Top 10–15 at position |
| B | Good | Above average starter |
| C | Average | Average starter or good backup |
| D | Below Average | Backup or struggling player |

Grades affect:
1. The yard value distribution (higher grades = more big plays)
2. The TD probability on each play
3. The overall completion/catch/gain rates

## Full Card Example

Here is a complete example of what a QB card looks like in JSON format:

```json
{
  "name": "Patrick Mahomes",
  "position": "QB",
  "number": 15,
  "team": "KC",
  "overall_grade": "A",
  "short_pass": {
    "11": {"result": "SACK", "yards": -4, "td": false},
    "12": {"result": "INCOMPLETE", "yards": 0, "td": false},
    "13": {"result": "INT", "yards": 0, "td": false},
    "14": {"result": "INCOMPLETE", "yards": 0, "td": false},
    "15": {"result": "COMPLETE", "yards": 10, "td": false},
    "16": {"result": "COMPLETE", "yards": 7, "td": false},
    "17": {"result": "COMPLETE", "yards": 12, "td": true},
    "18": {"result": "COMPLETE", "yards": 6, "td": false},
    "...": "... (64 total entries)"
  },
  "long_pass": {
    "11": {"result": "COMPLETE", "yards": 22, "td": false},
    "12": {"result": "COMPLETE", "yards": 25, "td": false},
    "13": {"result": "COMPLETE", "yards": 28, "td": false},
    "14": {"result": "INCOMPLETE", "yards": 0, "td": false},
    "...": "... (64 total entries)"
  },
  "screen_pass": {
    "11": {"result": "COMPLETE", "yards": 5, "td": false},
    "...": "... (64 total entries)"
  },
  "stats_summary": {
    "comp_pct": 0.672,
    "ypa": 8.8,
    "int_rate": 0.016,
    "sack_rate": 0.055
  }
}
```

### RB Card Example

```json
{
  "name": "Derrick Henry",
  "position": "RB",
  "number": 22,
  "team": "BAL",
  "overall_grade": "A",
  "inside_run": {
    "11": {"result": "GAIN", "yards": 5, "td": false},
    "12": {"result": "GAIN", "yards": 3, "td": false},
    "13": {"result": "GAIN", "yards": 7, "td": false},
    "14": {"result": "GAIN", "yards": -1, "td": false},
    "15": {"result": "FUMBLE", "yards": 0, "td": false},
    "16": {"result": "GAIN", "yards": 12, "td": true},
    "...": "... (64 total entries)"
  },
  "outside_run": {
    "11": {"result": "GAIN", "yards": 8, "td": false},
    "...": "... (64 total entries)"
  },
  "stats_summary": {
    "ypc": 5.1,
    "fumble_rate": 0.008
  }
}
```

### Kicker Card Example

```json
{
  "name": "Harrison Butker",
  "position": "K",
  "number": 7,
  "team": "KC",
  "overall_grade": "A",
  "fg_chart": {
    "0-19": 1.0,
    "20-29": 1.0,
    "30-39": 0.95,
    "40-49": 0.90,
    "50-59": 0.75,
    "60+": 0.60
  },
  "xp_rate": 0.995,
  "stats_summary": {
    "accuracy": 0.90,
    "xp_rate": 0.995
  }
}
```

## How Cards Interact During a Play

Here's the step-by-step flow for a passing play:

1. **Dice Roll**: 37 → play tendency = LONG_PASS
2. **AI Play Call**: Long pass to deep right
3. **QB Card Lookup**: Check QB's `long_pass` column at slot "37"
   - Result: `{"result": "COMPLETE", "yards": 28, "td": false}`
4. **Receiver Card Check**: Check WR's `long_reception` column at slot "37"
   - If `CATCH` → pass stays complete
   - If `INCOMPLETE` → overrides QB result, pass is now incomplete
5. **Defense Modifier**: Defense coverage rating adjusts yards
   - `yards = 28 × (1 - (80 - 50) / 200) = 28 × 0.85 = 23 yards`
6. **Final Result**: Complete pass for 23 yards

For a rushing play:

1. **Dice Roll**: 52 → play tendency = RUN
2. **AI Play Call**: Run to the left (inside)
3. **RB Card Lookup**: Check RB's `inside_run` column at slot "52"
   - Result: `{"result": "GAIN", "yards": 6, "td": false}`
4. **Defense Modifier**: Defense run stop rating adjusts yards
   - `yards = 6 - (82 - 50) / 50 = 6 - 0.64 ≈ 5 yards`
5. **Final Result**: 5-yard gain on the run
