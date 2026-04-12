# Statis Pro Football GUI Implementation Audit

This document tracks the implementation status of 5E rules and features in the React/TypeScript GUI.

## Game Setup & Configuration

- [x] **Team Selection** — `TeamSelector.tsx` allows selecting home/away teams from all 32 teams
- [x] **Season Selection** — Can select 2024, 2025, or 2025_5e data
- [x] **Game Mode Selection** — Human vs AI, AI vs AI, or solitaire mode
- [ ] **5E vs Legacy Mode Toggle** — No UI to choose between 5E (FAC deck) and legacy (dice) modes
- [ ] **Seed Configuration** — No way to set random seed for reproducible games

## Play Calling (Offense)

- [x] **Basic Play Types** — Run, Short Pass, Long Pass, Quick Pass, Screen, Punt, FG, Kneel
- [x] **Run Directions** — Inside Left/Right, Sweep Left/Right, Middle
- [x] **Pass Directions** — Left, Right, Middle, Deep Left, Deep Right
- [x] **Formations** — Shotgun, Under Center, I-Form, Trips, Spread
- [x] **Offensive Strategies (5E)** — Flop, Sneak, Draw, Play-Action selector added
- [x] **Player Selection** — Dropdown to choose specific QB/RB/WR for the play
- [ ] **End-Around** — No UI to call end-around plays
- [x] **Two-Point Conversion** — Two-point conversion prompt after TD with Run/Short Pass/Quick Pass options

## Play Calling (Defense)

- [x] **Defensive Formations** — 4-3, 3-4, Cover 2, Zone, Blitz, Nickel, Goal Line
- [x] **Defensive Strategies (5E)** — Double Coverage, Triple Coverage, Alt Double selector added
- [ ] **Big Play Defense** — No UI to declare Big Play Defense usage
- [ ] **Blitz Player Selection** — Cannot choose which LBs/DBs to blitz
- [ ] **Coverage Assignments** — No box-based defensive positioning

## Special Teams

- [x] **Punt** — Basic punt play type available
- [x] **Field Goal** — Basic FG play type available
- [x] **Onside Kick** — UI button to attempt onside kick via API
- [x] **Squib Kick** — UI button for squib kick via API
- [ ] **Onside Kick Defense** — No UI to declare onside defense (API supports it)
- [x] **Fake Punt** — UI button (once per game) via API endpoint
- [x] **Fake Field Goal** — UI button (once per game) via API endpoint
- [x] **All-Out Punt Rush** — API endpoint implemented, available via special teams
- [x] **Coffin Corner Punt** — UI with slider to declare yardage deduction (10-25)

## Roster Management

- [ ] **Starting Lineup** — No UI to set starting 11 on offense/defense
- [x] **Substitutions** — `SubstitutionPanel.tsx` supports QB/RB/WR/TE/K/P + DL/LB/DB substitutions
- [ ] **Depth Chart** — No depth chart management
- [x] **Injury Tracking** — Visual injury tracker banner shows injured players and plays remaining
- [x] **Endurance Tracking** — Endurance values shown on expanded player cards in LetterBoards
- [ ] **Position Flexibility** — Cannot move players to different positions

## Game State Display

- [x] **Scoreboard** — Shows score, quarter, time, timeouts
- [x] **Down & Distance** — Displayed in situation bar
- [x] **Field Position** — Yard line shown
- [x] **Possession** — Current team with ball shown
- [x] **Play Log** — Recent plays displayed in GameLog component
- [x] **Timeout Display** — Shows remaining timeouts for both teams with call buttons
- [x] **Drive Summary** — Basic stats displayed (quarter, time, plays, timeouts)
- [x] **Team Stats** — Basic game stats displayed in GameStats component
- [ ] **Player Stats** — No individual player stats tracking
- [ ] **Penalty Summary** — No penalty tracking display
- [ ] **Turnover Summary** — No turnover count display

## 5E-Specific Features

- [x] **Offensive Strategies** — UI added for Flop, Sneak, Draw, Play-Action
- [x] **Defensive Strategies** — UI added for Double/Triple Coverage
- [x] **FAC Card Display** — Shows RUN#/PASS# and Z-card indicator after each play
- [x] **Run Number / Pass Number** — Displayed in FAC card after each play
- [x] **Z-Card Events** — Z-card indicator shown in FAC card display with warning icon
- [ ] **BV vs TV Battle** — No display of blocking/tackling matchup (backend fully implements BV vs TV)
- [ ] **Point of Interception** — Not calculated/displayed (backend implements via `calculate_point_of_interception()`)
- [ ] **Two-Minute Offense** — No UI to declare two-minute offense (backend auto-detects)
- [x] **Two-Minute Warning** — Visual indication with pulsing badge at 2:00 mark
- [x] **Authentic 5E Rating Scale** — Backend now uses authentic small-number ratings (PR 0-3, Pass Def -2 to +4, Tackle -5 to +4, OL blocking -1 to +4)
- [x] **Timeout Restriction** — Backend enforces 5E timeout rule (only after plays > 10 seconds)
- [x] **Half-End Defensive Penalty** — Backend prevents half from ending on defensive penalty

## Player Cards

- [x] **Card Viewer** — `CardViewer.tsx` and `PlayerCard.tsx` exist
- [x] **Basic Card Display** — Shows player name, position, grade
- [x] **5E Card Format** — Display of 48-slot passing / 12-slot rushing tables in PlayerCard
- [x] **Passing Ranges** — QB completion/INT ranges shown with COM/INC/INT columns + Pass Rush ranges + Endurance
- [x] **Rushing Tables** — N/SG/LG columns displayed with endurance info
- [x] **Pass Gain Tables** — Receiver Q/S/L columns shown with endurance info
- [x] **Defensive Ratings** — Pass rush, coverage, tackle, pass defense, intercept range displayed for 5E positions
- [x] **Endurance Rating** — Shown on rushing and pass gain table sections
- [x] **Blocking Values** — BV displayed on player cards
- [x] **OL Blocking Ratings** — Run Block and Pass Block ratings shown for offensive linemen

## AI Behavior

- [x] **AI Play Calling** — Solitaire AI makes play calls
- [x] **AI Defense Calling** — AI selects defensive formations
- [ ] **AI Strategy Usage** — Unknown if AI uses offensive/defensive strategies
- [ ] **AI Big Play Defense** — Unknown if AI uses Big Play Defense
- [ ] **AI Fake Plays** — Unknown if AI attempts fake punts/FGs
- [ ] **AI Two-Minute Drill** — Unknown if AI properly manages clock
- [ ] **AI Timeout Management** — Unknown if AI uses timeouts strategically

## Game Flow

- [x] **Play-by-Play** — Individual plays execute
- [x] **Drive Simulation** — Can simulate entire drive
- [x] **Game Simulation** — Can simulate entire game
- [x] **Game Over Detection** — Shows winner when game ends
- [x] **Overtime** — Overtime indicator banner when quarter > 4
- [x] **Halftime** — Halftime break banner with score display
- [x] **Quarter Breaks** — End of quarter indicator between quarters
- [x] **Timeout Calls** — UI buttons to call timeout for either team
- [ ] **Challenge System** — Not applicable (not in 5E rules)

## Visual Enhancements

- [x] **Gridiron Display** — `Gridiron.tsx` shows field
- [x] **Animated Field Position** — CSS transitions on ball marker, first-down marker, scrimmage line
- [ ] **Play Animation** — No visual play execution
- [ ] **Score Animation** — No celebration on TD/FG
- [ ] **Penalty Flags** — No visual penalty indication
- [x] **Injury Indicator** — Injury tracker banner with player names and plays remaining
- [x] **Timeout Indicator** — Timeout buttons show remaining count, disabled when depleted

## Summary

### Implementation Status

| Category | Implemented | Partial | Not Implemented | Total |
|----------|-------------|---------|-----------------|-------|
| Game Setup | 3 | 0 | 2 | 5 |
| Offense Play Calling | 7 | 0 | 1 | 8 |
| Defense Play Calling | 2 | 0 | 3 | 5 |
| Special Teams | 8 | 0 | 1 | 9 |
| Roster Management | 3 | 0 | 3 | 6 |
| Game State Display | 8 | 0 | 3 | 11 |
| 5E Features | 8 | 0 | 3 | 11 |
| Player Cards | 10 | 0 | 0 | 10 |
| AI Behavior | 2 | 0 | 5 | 7 |
| Game Flow | 8 | 0 | 1 | 9 |
| Visual Enhancements | 4 | 0 | 3 | 7 |
| **TOTAL** | **63** | **0** | **25** | **88** |

**Completion: 72% (63/88)** ← up from 47% (41/88)

### Priority Improvements

1. ~~**Player Selection**~~ ✅ COMPLETE — Allow choosing specific players for plays
2. ~~**Roster/Substitution Management**~~ ✅ COMPLETE — Functional lineup and substitution system
3. ~~**Special Teams Options**~~ ✅ COMPLETE — Onside kick, squib kick, fake plays, coffin corner
4. ~~**5E Card Display**~~ ✅ COMPLETE — Show FAC card details and player card tables
5. **Player Stats Tracking** — Display cumulative stats for teams and players
6. **AI Strategy Verification** — Ensure AI uses all available 5E features
7. ~~**Timeout Management**~~ ✅ COMPLETE — UI to call timeouts
8. **Two-Minute Offense** — UI to declare and visual indication
9. **Big Play Defense** — UI to declare big play defense usage
10. **BV vs TV Display** — Show blocking/tackling matchup results
