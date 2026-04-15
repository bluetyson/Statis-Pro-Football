# Player Cards

Player cards are the core of Statis Pro Football. In **5th Edition (5E)** mode, QB cards have 48 pass rows and RB cards have 12 run rows. The legacy mode uses 64-slot (dice-indexed) cards.

---

## 5th Edition Card System

### 5E Card Overview

In 5E, every play uses:
- A **PASS# (1–48)** drawn from the FAC deck to index QB and receiver cards
- A **RUN# (1–12)** drawn from the FAC deck to index RB run cards

Cards do not use the 11–88 dice range from legacy mode.

---

## Card Columns by Position

### Quarterback (QB)

QBs have three **passing range** columns. Each column is a two-value threshold:

| Column | Used When | Values |
|--------|-----------|--------|
| **passing_quick** | Quick Pass (QK) | `com_max` and `inc_max` (PASS# thresholds) |
| **passing_short** | Short Pass (SH) | `com_max` and `inc_max` |
| **passing_long** | Long Pass (LG) | `com_max` and `inc_max` |

**How it works**: A PASS# (1–48) is drawn. If it is ≤ `com_max`, the pass is **complete**; if ≤ `inc_max`, it is **incomplete**; otherwise it is **INT**.

**Additional QB fields:**

| Field | Description |
|-------|-------------|
| `pass_rush` | `{sack_max, runs_max, com_max}` — determines sack/run/completion from the pass-rush table |
| `qb_endurance` | A/B/C — limits passes per drive before endurance penalty |
| `rushing` | 12-row table for QB scrambles (same format as RB) |
| `long_pass_com_adj` | Adjustment to completion range for long passes |

**Example: Patrick Mahomes (A grade)**

```json
{
  "name": "Patrick Mahomes",
  "position": "QB",
  "number": 15,
  "team": "KC",
  "overall_grade": "A",
  "passing_quick": {"com_max": 34, "inc_max": 48},
  "passing_short": {"com_max": 32, "inc_max": 47},
  "passing_long":  {"com_max": 28, "inc_max": 47},
  "pass_rush":     {"sack_max": 7, "runs_max": 30, "com_max": 37},
  "qb_endurance": "A",
  "long_pass_com_adj": 0,
  "stats_summary": {"comp_pct": 0.672, "ypa": 8.8, "int_rate": 0.016, "sack_rate": 0.055}
}
```

---

### Running Back (RB)

RBs have a **12-row rushing table** (one row per RUN# 1–12). Each row is a `ThreeValueRow`:

| Column Index | Meaning |
|-------------|---------|
| v1 | **Normal gain** yards |
| v2 | **Sweep/Outside** gain yards |
| v3 | **BREAKAWAY** threshold (RUN# ≥ v3 → big gain) |

Special row values: `"Sg"` = Short Gain, `"Lg"` = Long Gain (mapped to specific yardage at runtime).

**Additional RB fields:**

| Field | Description |
|-------|-------------|
| `pass_gain` | 12-row table for receptions (same ThreeValueRow format) |
| `endurance_rushing` | 0–4 — how many consecutive carries before rest required |
| `endurance_pass` | 0–4 — same for pass targets |
| `receiver_letter` | A–E — the letter used for QB card pass targeting |

**Example: Isiah Pacheco (B grade)**

```json
{
  "name": "Isiah Pacheco",
  "position": "RB",
  "number": 10,
  "team": "KC",
  "overall_grade": "B",
  "rushing": [
    ["Sg", 14, 30],
    [10, 12, 24],
    [9, 11, 23],
    ...12 rows total...
  ],
  "endurance_rushing": 1,
  "pass_gain": [
    [5, 7, 20],
    [4, 7, 20],
    ...12 rows total...
  ],
  "receiver_letter": "E",
  "stats_summary": {"ypc": 4.6, "fumble_rate": 0.011}
}
```

---

### Wide Receiver / Tight End (WR/TE)

WRs and TEs have a **12-row pass_gain table** matching the same ThreeValueRow format as RB receiving.

| Field | Description |
|-------|-------------|
| `pass_gain` | 12-row table — yards on each row (v1=short, v2=long, v3=breakaway) |
| `receiver_letter` | A–E — letter used in QB pass targeting |
| `endurance_pass` | 0–4 — pass target endurance rating |

**Example: Rashee Rice (A grade)**

```json
{
  "name": "Rashee Rice",
  "position": "WR",
  "number": 4,
  "team": "KC",
  "overall_grade": "A",
  "receiver_letter": "C",
  "pass_gain": [
    ["Lg", "Lg", 60],
    [13, 18, 40],
    [12, 18, 39],
    ...12 rows total...
  ],
  "endurance_pass": 0
}
```

---

### Kicker (K)

Kickers have a distance-based FG chart and an extra point rate:

| Attribute | Description |
|-----------|------------|
| **fg_chart** | Success rates by distance range |
| **xp_rate** | Extra point success percentage |
| **longest_kick** | Maximum FG distance attempted |

**FG Chart Example: Harrison Butker (A grade, 90.0% accuracy)**

| Distance | Success Rate |
|----------|-------------|
| 0–19 yards | 100% |
| 20–29 yards | 100% |
| 30–39 yards | 95% |
| 40–49 yards | 90% |
| 50–59 yards | 75% |
| 60+ yards | 60% |

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
  "longest_kick": 62,
  "stats_summary": {"accuracy": 0.90, "xp_rate": 0.995}
}
```

---

### Punter (P)

Punters have two attributes:

| Attribute | Description | Range |
|-----------|------------|-------|
| **avg_distance** | Average punt distance | 41–51 yards |
| **inside_20_rate** | Chance of pinning inside 20 | 30–46% |
| **blocked_punt_number** | FAC threshold for blocked punt | 1–3 |

---

### Defenders (DEF)

5E uses **authentic 5E defensive ratings** on a different scale than legacy:

| Rating | Description | Range |
|--------|-------------|-------|
| **Pass Rush (PR)** | Pass rush effectiveness | 0–3 |
| **Pass Defense** | Coverage / pass defense modifier | -2 to +4 |
| **Tackle** | Run stop / tackle modifier | -5 to +4 |
| **Intercept Range** | Interception chance threshold | 0–99 |
| **defender_letter** | A–O — box assignment on the defensive display | A–O |

Additionally, legacy ratings are retained for backward compatibility:
- `pass_rush_rating` (0–99), `coverage_rating` (0–99), `run_stop_rating` (0–99)

**Example: Chris Jones (A grade)**

```json
{
  "name": "Chris Jones",
  "position": "DT",
  "number": 95,
  "team": "KC",
  "overall_grade": "A",
  "pass_rush_rating": 3,
  "tackle_rating": 1,
  "pass_defense_rating": 0,
  "intercept_range": 0,
  "defender_letter": "A"
}
```

---

### Offensive Linemen (OL)

OL players have blocking ratings used in BV vs TV matchups:

| Rating | Description | Range |
|--------|-------------|-------|
| **run_block_rating** | Effectiveness run blocking | -1 to +4 |
| **pass_block_rating** | Effectiveness pass blocking | -1 to +4 |

---

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
1. The yard value distribution (higher grades = more big plays, `"Lg"` values)
2. The QB passing completion thresholds (`com_max`)
3. The overall catch/gain rates

---

## How Cards Interact During a Play (5E)

### Passing Play Example

1. **FAC Draw**: PASS# = 23, QK field = "B"
2. **Check QK field**: Forces pass to receiver letter B (or triggers P.Rush)
3. **QB Card Lookup**: `passing_short.com_max = 32` — PASS# 23 ≤ 32 → **COMPLETE**, receiver = B
4. **Receiver Card Lookup**: Receiver B's `pass_gain` row 23 → `[12, 18, 40]` → 12 yards short, 18 yards long
5. **Defense Modifier**: Apply pass defense rating
6. **Final Result**: Complete pass for 12–18 yards (depending on pass type)

### Running Play Example

1. **FAC Draw**: RUN# = 7, direction = IL (inside left)
2. **BV vs TV**: Check IL field → blocking matchup
3. **RB Card Lookup**: RB's `rushing` row 7 → `[5, 8, 24]` — 5 yards inside
4. **Endurance Check**: If RB violated endurance: +2 to RUN# (effectively row 9 → fewer yards)
5. **Final Result**: 5-yard gain (or less if defense wins the blocking matchup)

---

## Legacy Card System (64-Slot)

The legacy format uses slots 11–88 (64 outcomes from d8×d8 dice):

| Position | Columns | Slot Contents |
|----------|---------|---------------|
| QB | Short Pass, Long Pass, Screen Pass | COMPLETE/INCOMPLETE/INT/SACK + yards |
| RB | Inside Run, Outside Run | GAIN/FUMBLE + yards |
| WR/TE | Short Reception, Long Reception | CATCH/INCOMPLETE + yards |
| K | FG Chart (by distance), XP Rate | Success probability |
| P | Avg Distance, Inside-20 Rate | Distance/placement |

Legacy teams are stored in `engine/data/2025/` and `engine/data/2024/`.
