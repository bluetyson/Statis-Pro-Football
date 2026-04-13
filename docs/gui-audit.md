# Statis Pro Football GUI Implementation Audit

This document tracks the implementation status of 5E rules and features in the React/TypeScript GUI.

## Game Setup & Configuration

- [x] **Team Selection** — `TeamSelector.tsx` allows selecting home/away teams from all 32 teams
- [x] **Season Selection** — Can select 2024, 2025, or 2025_5e data
- [x] **Game Mode Selection** — Human vs AI, AI vs AI, or solitaire mode
- [x] **5E vs Legacy Mode Toggle** — Added checkbox in TeamSelector to choose between 5E (FAC deck) and legacy (dice) modes
- [x] **Seed Configuration** — Added seed input in TeamSelector for reproducible games

## Play Calling (Offense)

- [x] **Basic Play Types** — Run, Short Pass, Long Pass, Quick Pass, Screen, Punt, FG, Kneel
- [x] **Run Directions** — Inside Left/Right, Sweep Left/Right, Middle
- [x] **Pass Directions** — Left, Right, Middle, Deep Left, Deep Right
- [x] **Formations** — Shotgun, Under Center, I-Form, Trips, Spread
- [x] **Offensive Strategies (5E)** — Flop, Sneak, Draw, Play-Action selector added
- [x] **Player Selection** — Dropdown to choose specific QB/RB/WR for the play
- [x] **End-Around** — End-Around play type available in HumanPlayCaller (🔄 End-Around button), backed by `resolve_end_around()` in play_resolver.py
- [x] **Two-Point Conversion** — Two-point conversion prompt after TD with Run/Short Pass/Quick Pass options

## Play Calling (Defense)

- [x] **Defensive Formations** — 4-3, 3-4, Cover 2, Zone, Blitz, Nickel, Goal Line
- [x] **Defensive Strategies (5E)** — Double Coverage, Triple Coverage, Alt Double selector added
- [x] **Big Play Defense** — Added Big Play Defense button in GameBoard tactical actions, calls `/big-play-defense` API
- [x] **Blitz Player Selection** — BlitzPlayerSelector component allows choosing 2-5 LBs/DBs to blitz, integrated into DefensivePlayCaller with API `blitz_players` parameter
- [x] **Coverage Assignments** — DisplayBoxes component shows 5E A-O defensive box assignments (Row 1 DL, Row 2 LB, Row 3 DB) with pass defense mappings via `/display-boxes` endpoint

## Special Teams

- [x] **Punt** — Basic punt play type available
- [x] **Field Goal** — Basic FG play type available
- [x] **Onside Kick** — UI button to attempt onside kick via API
- [x] **Squib Kick** — UI button for squib kick via API
- [x] **Onside Kick Defense** — Added Onside Defense button in GameBoard tactical actions for defensive team
- [x] **Fake Punt** — UI button (once per game) via API endpoint
- [x] **Fake Field Goal** — UI button (once per game) via API endpoint
- [x] **All-Out Punt Rush** — API endpoint implemented, available via special teams
- [x] **Coffin Corner Punt** — UI with slider to declare yardage deduction (10-25)

## Roster Management

- [x] **Starting Lineup** — StartingLineup component shows full starting 11 offense/defense with team card format, backed by `/starting-lineup` GET/POST endpoints
- [x] **Substitutions** — `SubstitutionPanel.tsx` supports QB/RB/WR/TE/K/P + DL/LB/DB substitutions with defensive substitution via `/substitute-defense`
- [x] **Depth Chart** — DepthChart component shows full positional depth for all positions (QB/RB/WR/TE/OL/K/P/DL/LB/DB) via `/depth-chart` endpoint
- [x] **Injury Tracking** — Visual injury tracker banner shows injured players and plays remaining
- [x] **Endurance Tracking** — Endurance values shown on expanded player cards in LetterBoards
- [x] **Position Flexibility** — SubstitutionPanel includes position change section with compatible position validation via `/position-change` endpoint (5E penalty rules applied)

## Game State Display

- [x] **Scoreboard** — Shows score, quarter, time, timeouts
- [x] **Down & Distance** — Displayed in situation bar
- [x] **Field Position** — Yard line shown
- [x] **Possession** — Current team with ball shown
- [x] **Play Log** — Recent plays displayed in GameLog component
- [x] **Timeout Display** — Shows remaining timeouts for both teams with call buttons
- [x] **Drive Summary** — Basic stats displayed (quarter, time, plays, timeouts)
- [x] **Team Stats** — Basic game stats displayed in GameStats component
- [x] **Player Stats** — Added collapsible PlayerStatsPanel with rushing/passing/receiving stats table
- [x] **Penalty Summary** — Added penalty/turnover bar showing penalty count and yardage per team
- [x] **Turnover Summary** — Added turnover count per team in penalty/turnover bar

## 5E-Specific Features

- [x] **Offensive Strategies** — UI added for Flop, Sneak, Draw, Play-Action
- [x] **Defensive Strategies** — UI added for Double/Triple Coverage
- [x] **FAC Card Display** — Shows RUN#/PASS# and Z-card indicator after each play
- [x] **Run Number / Pass Number** — Displayed in FAC card after each play
- [x] **Z-Card Events** — Z-card indicator shown in FAC card display with warning icon
- [x] **BV vs TV Battle** — Added BV vs TV display in last play card showing blocker/defender values and modifier
- [x] **Point of Interception** — Added interception point display in last play card showing yard line
- [x] **Two-Minute Offense** — Added Two-Minute Offense declaration button in GameBoard tactical actions
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
- [x] **AI Strategy Usage** — AI now uses Double/Triple Coverage strategies on 3rd/4th and long
- [x] **AI Big Play Defense** — AI has `should_use_big_play_defense()` method for BPD decisions
- [x] **AI Fake Plays** — AI considers fake punt (6%) and fake FG (8%) on 4th down in appropriate situations
- [x] **AI Two-Minute Drill** — AI uses QUICK_PASS/SCREEN in two-minute drill with clock awareness
- [x] **AI Timeout Management** — AI has `should_call_timeout()` method for strategic timeout decisions

## Game Flow

- [x] **Play-by-Play** — Individual plays execute
- [x] **Drive Simulation** — Can simulate entire drive
- [x] **Game Simulation** — Can simulate entire game
- [x] **Game Over Detection** — Shows winner when game ends
- [x] **Overtime** — Overtime indicator banner when quarter > 4
- [x] **Halftime** — Halftime break banner with score display
- [x] **Quarter Breaks** — End of quarter indicator between quarters
- [x] **Timeout Calls** — UI buttons to call timeout for either team
- [x] **Challenge System** — N/A: Not in 5E rules

## Visual Enhancements

- [x] **Gridiron Display** — `Gridiron.tsx` shows field
- [x] **Animated Field Position** — CSS transitions on ball marker, first-down marker, scrimmage line
- [x] **Play Animation** — Added slideIn CSS animation for TD/turnover play cards
- [x] **Score Animation** — Added pulse animation on TD with celebration banner
- [x] **Penalty Flags** — Added yellow flag visual indicator on penalty plays
- [x] **Injury Indicator** — Injury tracker banner with player names and plays remaining
- [x] **Timeout Indicator** — Timeout buttons show remaining count, disabled when depleted

## Summary

### Implementation Status

| Category | Implemented | Partial | Not Implemented | Total |
|----------|-------------|---------|-----------------|-------|
| Game Setup | 5 | 0 | 0 | 5 |
| Offense Play Calling | 8 | 0 | 0 | 8 |
| Defense Play Calling | 5 | 0 | 0 | 5 |
| Special Teams | 9 | 0 | 0 | 9 |
| Roster Management | 6 | 0 | 0 | 6 |
| Game State Display | 11 | 0 | 0 | 11 |
| 5E Features | 11 | 0 | 0 | 11 |
| Player Cards | 10 | 0 | 0 | 10 |
| AI Behavior | 7 | 0 | 0 | 7 |
| Game Flow | 9 | 0 | 0 | 9 |
| Visual Enhancements | 7 | 0 | 0 | 7 |
| **TOTAL** | **88** | **0** | **0** | **88** |

**Completion: 100% (88/88)** ← up from 72% (63/88)

### Priority Improvements

1. ~~**Player Selection**~~ ✅ COMPLETE — Allow choosing specific players for plays
2. ~~**Roster/Substitution Management**~~ ✅ COMPLETE — Functional lineup and substitution system
3. ~~**Special Teams Options**~~ ✅ COMPLETE — Onside kick, squib kick, fake plays, coffin corner
4. ~~**5E Card Display**~~ ✅ COMPLETE — Show FAC card details and player card tables
5. ~~**Player Stats Tracking**~~ ✅ COMPLETE — Cumulative player stats panel
6. ~~**AI Strategy Verification**~~ ✅ COMPLETE — AI uses all 5E features
7. ~~**Timeout Management**~~ ✅ COMPLETE — UI to call timeouts
8. ~~**Two-Minute Offense**~~ ✅ COMPLETE — Declaration button and visual indication
9. ~~**Big Play Defense**~~ ✅ COMPLETE — Declaration button in tactical actions
10. ~~**BV vs TV Display**~~ ✅ COMPLETE — Blocker/tackler matchup results shown
11. ~~**Blitz Player Selection**~~ ✅ COMPLETE — BlitzPlayerSelector component with 2-5 player selection
12. ~~**Coverage Assignments**~~ ✅ COMPLETE — DisplayBoxes with 5E A-O box visualization
13. ~~**Starting Lineup**~~ ✅ COMPLETE — StartingLineup component with full team card display
14. ~~**Depth Chart**~~ ✅ COMPLETE — DepthChart component with full positional depth
15. ~~**Position Flexibility**~~ ✅ COMPLETE — Position change in SubstitutionPanel with compatible positions
