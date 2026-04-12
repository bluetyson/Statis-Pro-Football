import type { GameState } from '../types/game';

interface GameStatsProps {
  state: GameState;
}

export function GameStats({ state }: GameStatsProps) {
  // Calculate basic stats from play log
  const totalPlays = state.last_plays?.length || 0;
  const isTwoMinuteWarning = (state.quarter === 2 || state.quarter === 4) && state.time_remaining <= 120;
  
  return (
    <div className="game-stats">
      <div className="stats-header">
        Game Stats
        {isTwoMinuteWarning && <span className="two-minute-badge">⏰ 2:00 WARNING</span>}
      </div>
      <div className="stats-grid">
        <div className="stat-item">
          <span className="stat-label">Quarter</span>
          <span className="stat-value">{state.quarter}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Time</span>
          <span className="stat-value">
            {Math.floor(state.time_remaining / 60)}:{String(state.time_remaining % 60).padStart(2, '0')}
          </span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Plays</span>
          <span className="stat-value">{totalPlays}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Timeouts {state.possession === 'home' ? state.home_team : state.away_team}</span>
          <span className="stat-value">{state.possession === 'home' ? state.timeouts_home : state.timeouts_away}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Timeouts {state.possession === 'home' ? state.away_team : state.home_team}</span>
          <span className="stat-value">{state.possession === 'home' ? state.timeouts_away : state.timeouts_home}</span>
        </div>
      </div>
    </div>
  );
}
