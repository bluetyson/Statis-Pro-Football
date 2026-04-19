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
  injuries?: Record<string, number>;
  penalties?: Record<string, number>;
  penalty_yards?: Record<string, number>;
  turnovers?: Record<string, number>;
  player_stats?: Record<string, Record<string, number>>;
}

export interface PlayResult {
  play_type: string;
  yards: number;
  result: string;
  description: string;
  is_touchdown: boolean;
  turnover: boolean;
  run_number?: number | null;
  pass_number?: number | null;
  defense_formation?: string | null;
  fac_card_number?: number | null;
  z_card?: boolean;
  strategy?: string | null;
  offensive_play_call?: string | null;
  defensive_play_call?: string | null;
  defensive_play?: string | null;
  passer?: string | null;
  rusher?: string | null;
  receiver?: string | null;
  bv_tv_result?: { blocker_bv: number; defender_tv: number; modifier: number } | null;
  interception_point?: number | null;
  personnel_note?: string | null;
  box_assignments?: Record<string, string> | null;
  debug_log?: string[];
  injury_player?: string | null;
  injury_duration?: number | null;
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
  longest_kick?: number;
  avg_distance?: number;
  inside_20_rate?: number;
  blocked_punt_number?: number;
  punt_return_pct?: number;
  pass_rush_rating?: number;
  coverage_rating?: number;
  run_stop_rating?: number;
  stats_summary?: Record<string, number | string>;
}

export interface TeamCardData {
  team: string;
  city: string;
  name: string;
  record: { wins: number; losses: number; ties: number };
  offense: Record<string, PlayerBrief | null>;
  offensive_line: PlayerBrief[];
  defense: PlayerBrief[];
  returners: { KR: PlayerBrief | null; PR: PlayerBrief | null };
  kick_returners: PlayerBrief[];
  punt_returners: PlayerBrief[];
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
  team_card?: TeamCardData;
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
  injured: boolean;
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
  endurance_label: string;  // e.g. "RB-0", "WR-1", "TE-2"
  // Pass gain (12-row Q/S/L)
  pass_gain: (number[] | null)[];
  endurance_pass: number;
  blocks: number;
  // Kicker
  fg_chart: FGChart | null;
  xp_rate: number;
  longest_kick: number;
  // Punter
  avg_distance: number;
  inside_20_rate: number;
  blocked_punt_number: number;
  punt_return_pct: number;
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
  return_specialists?: { KR: PlayerBrief | null; PR: PlayerBrief | null };
  on_field_assignments?: Record<string, string>;
}

export interface HumanPlayCall {
  play_type: string;
  direction: string;
  formation: string;
  strategy?: string;
  player_name?: string;  // Specific player to use (QB/RB/WR name)
  call_timeout?: boolean;  // Call timeout before play
}

export interface DefensivePlayCall {
  formation: string;
  defensive_strategy?: string;
  defensive_play?: string;  // 5E defensive play card (PASS_DEFENSE, RUN_DEFENSE_KEY_BACK_1, etc.)
  blitz_players?: string[];  // Names of LBs/DBs to blitz (2-5 players)
}

export interface DepthChartData {
  team: string;
  team_name: string;
  depth_chart: Record<string, PlayerBrief[]>;
}

export interface DisplayBoxData {
  defense_team: string;
  boxes: Record<string, PlayerBrief | null>;
  rows: {
    row1_dl: Record<string, PlayerBrief | null>;
    row2_lb: Record<string, PlayerBrief | null>;
    row3_db: Record<string, PlayerBrief | null>;
  };
}

export interface StartingLineupData {
  team: string;
  team_name: string;
  record: { wins: number; losses: number; ties: number };
  offense: Record<string, PlayerBrief | null>;
  offensive_line: PlayerBrief[];
  defense: PlayerBrief[];
  returners: { KR: PlayerBrief | null; PR: PlayerBrief | null };
}

export const DEFENSIVE_FORMATIONS = [
  { value: '4_3', label: '4-3 Base', icon: '🛡️' },
  { value: '3_4', label: '3-4 Base', icon: '🛡️' },
  { value: 'NICKEL', label: 'Nickel', icon: '🪙' },
  { value: 'GOAL_LINE', label: 'Goal Line', icon: '🧱' },
] as const;

export const OFFENSIVE_STRATEGIES = [
  { value: 'NONE', label: 'None' },
  { value: 'FLOP', label: 'QB Flop (-1 yard)' },
  { value: 'SNEAK', label: 'QB Sneak (0 or +1)' },
  { value: 'DRAW', label: 'Draw Play' },
  { value: 'PLAY_ACTION', label: 'Play-Action Pass' },
] as const;

export const DEFENSIVE_STRATEGIES = [
  { value: 'NONE', label: 'None' },
  { value: 'DOUBLE_COVERAGE', label: 'Double Coverage (-7)' },
  { value: 'TRIPLE_COVERAGE', label: 'Triple Coverage (-15)' },
  { value: 'ALT_DOUBLE_COVERAGE', label: 'Alt Double (2 receivers)' },
] as const;

export const DEFENSIVE_PLAYS = [
  { value: 'PASS_DEFENSE', label: 'Pass Defense', icon: '🎯', desc: 'Quick -10 | Short 0 | Long 0' },
  { value: 'PREVENT_DEFENSE', label: 'Prevent Defense', icon: '🔒', desc: 'Quick -10 | Short -5 | Long -7' },
  { value: 'RUN_DEFENSE_NO_KEY', label: 'Run Defense (No Key)', icon: '🏃', desc: 'Run +2 modifier' },
  { value: 'RUN_DEFENSE_KEY_BACK_1', label: 'Run D / Key Back 1', icon: '1️⃣', desc: 'Run +4 if correct back' },
  { value: 'RUN_DEFENSE_KEY_BACK_2', label: 'Run D / Key Back 2', icon: '2️⃣', desc: 'Run +4 if correct back' },
  { value: 'RUN_DEFENSE_KEY_BACK_3', label: 'Run D / Key Back 3', icon: '3️⃣', desc: 'Run +4 if correct back' },
  { value: 'BLITZ', label: 'Blitz', icon: '⚡', desc: 'Short -5 | Long → P.Rush' },
] as const;
