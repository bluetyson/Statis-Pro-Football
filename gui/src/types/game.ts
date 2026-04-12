/** Type definitions for the Statis Pro Football game engine. */

export interface Score {
  home: number;
  away: number;
}

export interface GameState {
  home_team: string;
  away_team: string;
  quarter: number;
  time_remaining: number;
  possession: string;
  yard_line: number;
  down: number;
  distance: number;
  score: Score;
  is_over: boolean;
  timeouts_home: number;
  timeouts_away: number;
  last_plays: string[];
}

export interface PlayResult {
  play_type: string;
  yards: number;
  result: string;
  description: string;
  is_touchdown: boolean;
  turnover: boolean;
}

export interface DriveResult {
  team: string;
  plays: number;
  yards: number;
  result: string;
  points_scored: number;
  drive_log: string[];
}

export interface DiceRollResult {
  two_digit: number;
  tens: number;
  ones: number;
  play_tendency: string;
  penalty_check: boolean;
  turnover_modifier: number;
}

export interface FGChart {
  '0-19': number;
  '20-29': number;
  '30-39': number;
  '40-49': number;
  '50-59': number;
  '60+': number;
}

export interface PlayerCard {
  name: string;
  position: string;
  number: number;
  team: string;
  overall_grade: string;
  receiver_letter?: string;
  fg_chart?: FGChart;
  xp_rate?: number;
  avg_distance?: number;
  inside_20_rate?: number;
  pass_rush_rating?: number;
  coverage_rating?: number;
  run_stop_rating?: number;
  stats_summary?: Record<string, number | string>;
}

export interface TeamData {
  abbreviation: string;
  city: string;
  name: string;
  conference: string;
  division: string;
  record: { wins: number; losses: number; ties: number };
  offense_rating: number;
  defense_rating: number;
  players: PlayerCard[];
}

export type GamePhase = 'setup' | 'playing' | 'gameover';

export type GameMode = 'human_home' | 'human_away' | 'solitaire';

export interface GameSession {
  game_id: string;
  state: GameState;
}

export interface PlayerBrief {
  name: string;
  position: string;
  number: number;
  overall_grade: string;
  receiver_letter: string;
  defender_letter: string;
  // Offensive Line ratings
  run_block_rating: number;
  pass_block_rating: number;
  // Legacy defensive ratings
  pass_rush_rating: number;
  coverage_rating: number;
  run_stop_rating: number;
  // Authentic 5E defensive ratings
  tackle_rating: number;
  pass_defense_rating: number;
  intercept_range: number;
  // QB passing ranges
  passing_quick: { com_max: number; inc_max: number } | null;
  passing_short: { com_max: number; inc_max: number } | null;
  passing_long: { com_max: number; inc_max: number } | null;
  pass_rush: { sack_max: number; runs_max: number; com_max: number } | null;
  qb_endurance: string;
  // Rushing (12-row N/SG/LG)
  rushing: (number[] | null)[];
  endurance_rushing: number;
  // Pass gain (12-row Q/S/L)
  pass_gain: (number[] | null)[];
  endurance_pass: number;
  blocks: number;
  // Kicker
  fg_chart: FGChart | null;
  xp_rate: number;
  // Punter
  avg_distance: number;
  inside_20_rate: number;
}

export interface PersonnelData {
  possession: string;
  offense_team: string;
  defense_team: string;
  offense_starters: Record<string, PlayerBrief>;
  offense_receivers: PlayerBrief[];
  offense_line: PlayerBrief[];
  defense_players: PlayerBrief[];
  defense_line: PlayerBrief[];
  linebackers: PlayerBrief[];
  defensive_backs: PlayerBrief[];
  offense_all: PlayerBrief[];
  defense_all: PlayerBrief[];
}

export interface HumanPlayCall {
  play_type: string;
  direction: string;
  formation: string;
}

export interface DefensivePlayCall {
  formation: string;
}

export const DEFENSIVE_FORMATIONS = [
  { value: '4_3', label: '4-3 Base', icon: '🛡️' },
  { value: '3_4', label: '3-4 Base', icon: '🛡️' },
  { value: '4_3_COVER2', label: '4-3 Cover 2', icon: '👁️' },
  { value: '3_4_ZONE', label: '3-4 Zone', icon: '🌐' },
  { value: '4_3_BLITZ', label: '4-3 Blitz', icon: '⚡' },
  { value: 'NICKEL_ZONE', label: 'Nickel Zone', icon: '🪙' },
  { value: 'NICKEL_BLITZ', label: 'Nickel Blitz', icon: '💥' },
  { value: 'NICKEL_COVER2', label: 'Nickel Cover 2', icon: '🪙' },
  { value: 'GOAL_LINE', label: 'Goal Line', icon: '🧱' },
] as const;
