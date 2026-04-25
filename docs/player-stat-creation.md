# Player Stat Creation Guide

This document explains, position by position, how player cards are created from real NFL statistics. It covers the data sources used, how closely the implementation follows the original Avalon Hill formulae, and how **era normalization** works for generating cards from any decade of NFL history.

---

## Data Sources

Player statistics for the bundled seasons come from:

| Season File | NFL Season | Primary Source |
|-------------|-----------|----------------|
| `engine/data/2025_5e/` | 2024 NFL regular season | [Pro Football Reference](https://www.pro-football-reference.com) |
| `engine/data/2025/` | 2024 NFL regular season | [Pro Football Reference](https://www.pro-football-reference.com) |
| `engine/data/2024/` | 2023 NFL regular season | [Pro Football Reference](https://www.pro-football-reference.com) |

Schedule data (for season simulation) is downloaded from [nflverse](https://github.com/nflverse), which covers all seasons back to 1999. The `scripts/download_schedule.py` script automates this.

**Stats used per position:**

| Position | Key Stats Used |
|----------|---------------|
| QB | Completions, attempts, yards, TDs, INTs, sacks |
| RB | Carries, rush yards, receptions, receiving yards |
| WR/TE | Targets, receptions, receiving yards |
| K | FG made/attempted by distance range, XP made/attempted |
| P | Punts, yards, inside-20 count |
| OL | Team sacks allowed (for pass blocking), team rush yards (for run blocking) |
| DL | Team rush yards allowed, individual sacks |
| LB | Team rush yards allowed, team pass yards allowed, individual sacks, interceptions |
| DB | Team pass yards per attempt allowed, individual interceptions, sacks |

---

## Avalon Hill Formula Usage

The original Statis Pro Football **5th Edition Player Card Method** (an internal Avalon Hill document dated ~1988) describes position-specific formulae for deriving ratings from real NFL statistics. The document in `docs/player-card-creation.md` is the source of record.

The table below summarises what was faithfully reproduced versus what was adapted:

| Aspect | AH Original | This Implementation | Notes |
|--------|-------------|---------------------|-------|
| DB Pass Defense points (team YPA table) | ✅ Used | ✅ Faithfully reproduced | `_AH_PASS_DEFENSE_POINTS` table |
| DB/LB individual pass defense distribution | ✅ Used | ✅ Reproduced | `_AH_DB_DISTRIBUTIONS` |
| DL Tackle ratings (team rush ypg table) | ✅ Used | ✅ Reproduced | `_AH_DL_TACKLE_TABLE` |
| LB Tackle ratings (team rush ypg table) | ✅ Used | ✅ Reproduced | `_AH_LB_TACKLE_TABLE` |
| Pass Rush (sacks → 0–3) | ✅ Used | ✅ Faithfully reproduced | `_sacks_to_pass_rush()` |
| Intercept Range (INTs → low end) | ✅ Used | ✅ Faithfully reproduced | `_intercepts_to_range()` |
| OL Run Block (team off rush ypg) | ✅ Used | ✅ Reproduced | `_AH_OL_RUN_BLOCK_TABLE` |
| OL Pass Block (sacks allowed) | ✅ Used | ✅ Reproduced | `_AH_OL_PASS_BLOCK_TABLE` |
| QB Completion ranges (Quick/Short/Long) | AH uses completion % table | ✅ Derived from comp_pct + ypa | Formula produces equivalent ranges |
| RB Rushing gain tables (N/SG/LG) | AH uses YPC lookup table | ✅ Derived from YPC | Algorithmically equivalent |
| WR/TE Receiving gain tables (Q/S/L) | AH uses avg yards lookup | ✅ Derived from avg catch yards | Algorithmically equivalent |
| Kicker FG chart (by distance range) | ✅ Used | ✅ Faithfully reproduced | `_make_kicker_fg_chart()` |
| Punter (avg distance + inside-20 rate) | ✅ Used | ✅ Reproduced | Direct mapping |
| Big Play defense rating | AH uses win-count judgment | ⚠️ Not yet implemented | Optional enhancement |
| Era normalization | ❌ Not in AH doc (1988-only) | ✅ Added (see below) | New feature for historical seasons |

---

## Position-by-Position Card Creation

### Quarterback (QB)

**Stats needed:** completions, attempts, yards, TDs, interceptions, sacks taken, rush attempts, rush yards.

**Derived inputs:**
- `comp_pct` = completions / attempts
- `ypa` = pass yards / attempts
- `int_rate` = interceptions / attempts
- `sack_rate` = sacks / (sacks + attempts)
- `rush_ypc` = rush yards / rush attempts

**Card values generated:**
- **Passing ranges (Quick / Short / Long):** The QB's completion percentage determines how many of the 48 PASS# slots result in completions. Quick passes add ~+4% completion; Long passes subtract ~−8%.  Interception rate fills in the INT tail from PASS# 48 downward.
- **Pass Rush ranges (Sack / Runs / Complete):** Sack rate sets the sack window. A small QB rush window follows. The remaining slots are completions.
- **Rushing table (12 rows):** Derived from rush YPC using the standard RB rushing formula at a ~70% scale (QBs are weaker runners).

**Notes:** AH uses separate lookup tables (one row per integer completion %) to assign the exact passing range values. This implementation uses the same formula: `com_max = round(comp_pct × 48)` which produces equivalent results.

---

### Running Back (RB)

**Stats needed:** carries, rush yards, fumbles, receptions, receiving yards.

**Derived inputs:**
- `ypc` = rush yards / carries
- `fumble_rate` = fumbles / carries
- `catch_rate` = receptions / targets (or receptions / (carries + receptions) as a proxy)
- `avg_yards` = receiving yards / receptions

**Card values generated:**
- **Rushing table (12 rows, N/SG/LG):** Row 1 is always "Sg" (Short Gain — consult SG column). Rows 2–12 descend based on YPC. The LG column (Long Gain, triggered by blocking BREAK result) is always larger. Elite RBs (A/A+ grade) get a boost to all values.
- **Pass Gain table (12 rows, Q/S/L):** Derived from `avg_yards` and `catch_rate`. Row 1 is "Lg" for high-quality pass-catching backs. `endurance_pass` (0–4) scales the pass game: 0 = three-down back, 4 = rarely targeted.
- **Blocks rating:** Fullbacks receive 2–3; speed backs 0–1; pass-catching specialists −1 to −2.
- **Receiver letter (A–E):** Assigned in order of pass-catching usage on the team.

**About the rushing table:** The original AH document has complete YPC lookup tables from 1.0 to 10.0+. This implementation algorithmically approximates the same distribution. An RB averaging 4.5 YPC gets roughly the same range of outcomes as the AH lookup would produce.

---

### Wide Receiver (WR)

**Stats needed:** targets, receptions, receiving yards.

**Derived inputs:**
- `catch_rate` = receptions / targets
- `avg_yards` = receiving yards / receptions

**Card values generated:**
- **Rushing table:** All `None` (blank) by default. WRs used on end-arounds can have a rushing table generated at ~4 YPC.
- **Pass Gain table (12 rows, Q/S/L):** Strong values for quality WRs. Row 1 is "Lg" for A/A+ receivers. `endurance_pass` is 0 for starters (unlimited targeting), 1 for quality backups.
- **Blocks rating:** −2 (standard WR blocking); adjusted if the WR is a notable blocker.
- **Receiver letter (A–E):** Assigned in order. The team's #1 WR gets letter A.

**About WR ranking:** The original AH document groups WRs with TEs as "Receivers," rated by receptions and average catch. Each team's WRs are ordered by usage (catches + yards) for letter assignment. The best WR on the team should get letter A and `endurance_pass=0`.

---

### Tight End (TE)

Same formula as WR but with:
- Higher default blocking rating (1–4; elite blocking TEs get 4)
- Lower average yards (TEs typically catch shorter routes, avg 8–11 yards)
- `endurance_pass` = 0 for receiving TEs, 2 for blocking-first TEs

---

### Kicker (K)

**Stats needed:** FG made/attempted by distance range (18–25, 26–35, 36–45, 46–50, 51+), XP made/attempted, longest successful FG.

**Card values generated (following AH formulae exactly):**
- **FG chart:** A success probability per distance range derived from the season's made/attempt percentage in each range.
- **XP rate:** Made / attempted as a percentage.
- **Longest kick:** Determines eligibility for 50+ yard attempts.

The AH tables provide exact threshold mappings (e.g., 75% success in the 36–45 range → success on PASS# 1–41). This implementation uses the same percentage-to-threshold formula.

---

### Punter (P)

**Stats needed:** punts, total yards, inside-20 count, blocked punts.

**Card values generated (following AH formulae exactly):**
- **avg_distance:** Season average yards per punt (41–51 typical range).
- **inside_20_rate:** Inside-20 punts / total punts.
- **blocked_punt_number:** 0 (none), 1 (one blocked), 2 (two blocked).

AH has detailed distance tables for each average from 35 to 50 yards. This implementation stores the average and inside-20 rate directly; the game engine maps these to outcomes at runtime.

---

### Offensive Linemen (OL)

**Stats needed:** Team-level — offensive rush yards per game, total sacks allowed for the season.

OL players do **not** have individual pass-catching or rushing stats. Their ratings are derived entirely from team-level performance, distributed across the 8 OL slots (LT, LG, C, RG, RT + 3 backups).

**Card values generated (following AH formulae):**

**Run Block (`run_block_rating`, -1 to +4):**

| Team Offensive Rush Yards/Game | Distribution (8 OL, best to worst) |
|-------------------------------|-------------------------------------|
| 150+ | 4, 4, 3, 3, 3, 1, 1, 2 |
| 140–149 | 4, 4, 3, 3, 2, 2, 1, 1 |
| 130–139 | 3, 3, 2, 2, 2, 1, 1, 1 |
| 120–129 | 3, 2, 2, 2, 1, 1, 0, 0 |
| 110–119 | 2, 2, 2, 1, 1, 0, 0, 0 |
| 100–109 | 2, 1, 1, 1, 0, 0, -1, -1 |
| Below 100 | 2, 1, 1, 0, 0, 0, -1, -1 |

**Pass Block (`pass_block_rating`, 0 to +3):**

| Team Sacks Allowed | Distribution (8 OL) |
|--------------------|----------------------|
| 10–15 | 3, 3, 2, 2, 1, 1, 0, 0 |
| 16–22 | 3, 2, 2, 1, 1, 0, 0, 0 |
| 23–30 | 2, 2, 1, 1, 0, 0, 0, 0 |
| 31–40 | 2, 1, 1, 0, 0, 0, 0, 0 |
| 41–55 | 1, 1, 0, 0, 0, 0, 0, 0 |
| 56–75 | 1, 0, 0, 0, 0, 0, 0, 0 |
| 76+ | 0, 0, 0, 0, 0, 0, 0, 0 |

**Era normalization applies here** — see the [Era Normalization](#era-normalization) section below.

---

### Defensive Linemen (DL: DE, DT, NT)

**Stats needed:** Team-level — defensive rush yards allowed per game. Individual — sacks.

DL players have **two** ratings in 5th Edition:
- **Tackle rating** (`tackle_rating`, -4 to +2): Derived from team defensive rush yards/game
- **Pass Rush rating** (`pass_rush_rating`, 0–3): Derived from individual sack count

**Important:** All DL on the same team share the same team-level tackle distribution. This is why DL ratings can seem "odd" if you look at individuals in isolation — a DT might have a negative tackle rating not because he's bad, but because his team allowed a lot of rush yards overall, and he drew the lower end of the distribution.

**Why DL Tackle Ratings Can Seem Strange:**

The AH methodology intentionally distributes tackles across position groups. The 6 DL slots get ratings from the team rush defense table, with one player typically getting the worst rating. This mirrors how real defensive performance is diluted across a unit — even great DTs play on bad run defenses.

**Tackle rating distribution (6 DL slots, best to worst):**

| Team Defensive Rush Yards/Game | DL Ratings (sorted best→worst) |
|-------------------------------|--------------------------------|
| ≤ 85 | -3, -3, -4, -2, -2, -2 |
| 86–95 | -3, -2, -3, -2, -2, -1 |
| 96–105 | -3, -2, -2, -2, -1, -1 |
| 106–115 | -2, -2, -2, -1, -1, 0 |
| 116–125 | -2, -2, -1, -1, 0, 0 |
| 126–135 | -2, -1, -1, 0, 0, 1 |
| 136–145 | -1, -1, 0, 0, 1, 1 |
| 146–155 | -1, 0, 0, 1, 1, 2 |
| 156–165 | 0, 0, 1, 1, 2, 2 |
| 166–180 | 0, 1, 1, 2, 2, 2 |
| 180+ | 1, 1, 2, -3, 2, 2 |

**Pass Rush rating (individual sacks):**

| Season Sacks | Pass Rush Rating |
|-------------|-----------------|
| 6+ | 3 |
| 4–5 | 2 |
| 2–3 | 1 |
| 0–1 | 0 |

**Era normalization applies to the team rush yards table** — see below.

---

### Linebackers (LB)

**Stats needed:** Team-level — defensive rush yards/game (for tackle), defensive pass yards per attempt (for pass defense). Individual — sacks (for pass rush), interceptions (for intercept range).

LBs have **four** ratings:
- **Tackle rating** (`tackle_rating`, -5 to +4): Team rush yards/game (same principle as DL but wider range)
- **Pass Defense** (`pass_defense_rating`, -2 to +4): Team pass YPA allowed, distributed among LBs
- **Pass Rush** (`pass_rush_rating`, 0–3): Individual sack count
- **Intercept Range** (`intercept_range`, 35–48): Individual interceptions

The LB pass defense is assigned from the same team YPA table as DBs, but the pool of available points is split between DBs and LBs based on position-group strength.

**Era normalization applies to both the rush and pass tables** — see below.

---

### Defensive Backs (DB: CB, S, FS, SS)

**Stats needed:** Team-level — defensive pass yards per attempt allowed. Individual — interceptions, sacks.

DBs have **three** ratings:
- **Pass Defense** (`pass_defense_rating`, -2 to +4): From team YPA allowed
- **Pass Rush** (`pass_rush_rating`, 0–3): From individual sacks
- **Intercept Range** (`intercept_range`, 35–48): From individual interceptions

DBs **do not** have a tackle rating in 5E.

**Team YPA → Pass Defense point table (4 DB starters):**

| Team Defensive YPA | Total Points | Example DB Distribution |
|--------------------|-------------|------------------------|
| ≤ 5.2 | -10 (elite) | -4, -3, -2, -1 |
| 5.3–5.4 | -9 | -4, -3, -1, -1 |
| 5.5–5.6 | -8 | -4, -2, -1, -1 |
| 5.7–5.8 | -7 | -3, -2, -1, -1 |
| 5.9–6.0 | -6 | -3, -2, -1, 0 |
| 6.1–6.2 | -5 | -3, -1, -1, 0 |
| 6.3–6.4 | -4 | -3, -1, 0, 0 |
| 6.5–6.6 | -3 | -2, -1, 0, 0 |
| 6.7–6.8 | -2 | -2, 0, 0, 0 |
| 6.9–7.0 | -1 | -1, 0, 0, 0 |
| 7.1–7.2 | 0 | 0, 0, 0, 0 |
| 7.3–7.4 | +1 | +1, 0, 0, 0 |
| 7.5–7.6 | +2 | +1, +1, 0, 0 |
| 7.7–7.8 | +3 | +2, +1, 0, 0 |
| 7.9–8.0 | +4 | +2, +1, +1, 0 |
| 8.0+ | +5 | +2, +2, +1, 0 |

**Intercept Range:**

| Season Interceptions | Range (low end–48) |
|---------------------|---------------------|
| 0–2 | 48 (no range) |
| 3 | 47–48 |
| 4 | 46–48 |
| 5 | 45–48 |
| 6 | 44–48 |
| 7 | 43–48 |
| 8 | 42–48 |
| 9 | 41–48 |
| 10 | 38–48 |
| 11 | 37–48 |
| 12 | 36–48 |
| 13+ | 35–48 |

---

## Era Normalization

### Why It Matters

The Avalon Hill player card tables were calibrated for **late-1980s NFL football**. In that era:
- The average pass YPA allowed by a defense was approximately **6.7**.
- Teams averaged approximately **125 rush yards/game** on offence.

The AH pass defense table treats 7.1–7.2 YPA as "0 points" (average). In 1988, that was above average, making it a reasonable midpoint. In modern football (2024), **the league average is closer to 7.1–7.2 YPA**, meaning every defense looks slightly above average by the raw AH table.

Similarly, the AH OL run-blocking and DL/LB tackle tables were set at a time when teams gained more rush yards per game. A 2024 team gaining 110 rush yards/game on offense is actually near the league average, but the AH table might rate those OL as merely average or below.

**Without normalization:** Cards generated from historical or modern raw stats can be systematically skewed — modern passing teams look poor on run defense, and 1970s teams look like powerhouse rushers even when they were average.

### How Era Normalization Works

The `engine/card_generator.py` file provides `ERA_BASELINES` and helper functions that shift raw team statistics to be equivalent to the 1980s calibration point before applying AH tables.

```python
from engine.card_generator import (
    ERA_BASELINES,
    era_normalized_pass_ypa,
    era_normalized_rush_ypg,
    compute_db_pass_defense_ratings,
    compute_dl_tackle_ratings,
    compute_lb_tackle_ratings,
)
```

**Available era keys:**

| Key | Period | Notes |
|-----|--------|-------|
| `"1970s"` | 1970–1979 | Run-heavy; low YPA, high rush yards |
| `"1980s"` | 1980–1989 | AH calibration era (default baseline) |
| `"1990s"` | 1990–1999 | Transition to more passing |
| `"2000s"` | 2000–2009 | Pass-oriented era begins |
| `"2010s"` | 2010–2019 | High-volume passing |
| `"2020s"` | 2020–present | Modern NFL; highest pass YPA |

### Example: Generating DL Cards for a Modern Team

```python
from engine.card_generator import compute_dl_tackle_ratings, compute_lb_tackle_ratings

# 2024 Kansas City Chiefs: allowed ~107 rush yards/game
dl_tackle_ratings = compute_dl_tackle_ratings(team_rush_ypg=107.0, era="2020s")
lb_tackle_ratings = compute_lb_tackle_ratings(team_rush_ypg=107.0, era="2020s")
# → DL: [-2, -2, -1, -1, 0, 0] (solid run defense for the era)
# → LB: [-4, -3, -2, -1, 0, 0, 1, 1]
```

Without normalization, 107 rush yards/game would map to approximately the 106–115 band in the AH table and produce the same result. **But for a 1970s team:**

```python
# 1975 Pittsburgh Steelers: allowed ~98 rush yards/game (genuinely elite)
dl_tackle_ratings = compute_dl_tackle_ratings(team_rush_ypg=98.0, era="1970s")
# → normalized to ~84 ypg equivalent → DL: [-3, -3, -4, -2, -2, -2] (dominant)
# Without normalization, 98 ypg would produce a merely above-average result
```

### Example: Generating DB Cards for a Modern Team

```python
from engine.card_generator import compute_db_pass_defense_ratings

# 2024 Los Angeles Rams: allowed 6.8 YPA (below modern league average of 7.1)
db_ratings = compute_db_pass_defense_ratings(team_ypa=6.8, era="2020s")
# → normalized to 6.4 equivalent → total -4 points → DB ratings: [-3, -1, 0, 0, 0, 0, 0]
```

### Era Baselines Reference

| Era | Avg Pass YPA Allowed | Avg Rush Ypg Allowed | Avg Off Rush Ypg | Avg Sacks/Game |
|-----|---------------------|---------------------|-----------------|---------------|
| 1970s | 5.8 | 150 | 148 | 4.0 |
| **1980s** | **6.7** | **128** | **125** | **3.8** |
| 1990s | 6.9 | 118 | 115 | 3.5 |
| 2000s | 6.8 | 115 | 113 | 3.4 |
| 2010s | 7.0 | 111 | 110 | 3.2 |
| 2020s | 7.1 | 112 | 110 | 3.1 |

The 1980s row (bold) is the AH calibration era. Normalization shifts stats so that the era's average maps to the 1980s average before table lookup.

---

## Assigning Individual 0–100 Ratings

The `generate_2025_data.py` and `generate_2025_5e_data.py` scripts use a **0–100 intermediate scale** for defenders. These values are manually assigned based on the player's real 2024 performance and get converted to authentic 5E ratings via the conversion functions.

The mapping is:

| 0–100 Rating | Description | 5E Pass Rush | 5E Tackle (DL) | 5E Pass Def |
|-------------|-------------|-------------|----------------|-------------|
| 85–100 | Elite | 3 | +2 | +4 |
| 70–84 | Good starter | 2 | +1 | +3 |
| 50–69 | Average | 1 | 0 | +1–+2 |
| 30–49 | Below average | 0 | -2 to -1 | -1–0 |
| Below 30 | Poor | 0 | -4 to -3 | -2 |

For **team-based ratings** (DL/LB tackle, DB/LB pass defense), the `compute_*_ratings()` functions described above are the preferred approach for new seasons, as they anchor individual ratings to real team performance data and correct for era.

---

## Common Questions

**Q: Why do some DL have negative tackle ratings?**

Tackle rating on DL reflects the whole unit's run-stopping success. The table distributes ratings from the team's defensive rush yards/game total, and one slot always gets the bottom of the distribution. A DT with tackle -3 simply means his team allowed a lot of rush yards — it does not mean he personally was bad.

**Q: Why doesn't the pass defense YPA table change between seasons?**

The raw AH table is calibrated for 1980s football. For modern seasons (2020s), use `compute_db_pass_defense_ratings(team_ypa, era="2020s")` which normalises the YPA before table lookup. The bundled 2024/2025 season data uses the 0–100 intermediate scale, which was manually calibrated to modern standards and does not require additional normalisation.

**Q: How were 1970s or 1990s rosters rated?**

If you create historical rosters, use the appropriate `era` parameter in all `compute_*_ratings()` calls. For individual offensive players (QB, RB, WR), the per-play stats (comp_pct, ypc, avg_yards) are already relative measures and do not need era adjustment — a QB completing 62% passes in 1970 was just as elite relative to his era as a QB completing 66% in 2024.

**Q: Where can I get historical stats?**

- **Pro Football Reference** (pro-football-reference.com) — comprehensive individual and team stats from 1920 onward
- **nflverse** (github.com/nflverse) — machine-readable datasets from 1999 onward, used by this project for schedules
- **Football Outsiders** (footballoutsiders.com) — advanced metrics (DVOA, etc.) useful for grading

---

## See Also

- [Player Cards](player-cards.md) — Card format reference with JSON examples
- [Creating Custom Players](creating-custom-players.md) — Step-by-step guide for new teams
- `docs/player-card-creation.md` — Full text of the original Avalon Hill player card creation document
- `engine/card_generator.py` — Source code for all card generation logic
