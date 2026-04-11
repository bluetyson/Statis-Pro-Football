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

export interface GameSession {
  game_id: string;
  state: GameState;
}
