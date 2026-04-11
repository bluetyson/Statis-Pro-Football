import type { GameState } from '../types/game';

interface ScoreboardProps {
  state: GameState;
}

export function Scoreboard({ state }: ScoreboardProps) {
  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const quarterLabel = state.quarter <= 4 ? `Q${state.quarter}` : 'OT';

  return (
    <div className="scoreboard">
      <div className="scoreboard-teams">
        <div className={`team-score ${state.possession === 'away' ? 'has-ball' : ''}`}>
          <span className="team-abbr">{state.away_team}</span>
          <span className="team-pts">{state.score.away}</span>
          {state.possession === 'away' && <span className="ball-indicator">🏈</span>}
        </div>
        <div className="scoreboard-center">
          <div className="quarter-time">
            <span className="quarter">{quarterLabel}</span>
            <span className="time">{formatTime(state.time_remaining)}</span>
          </div>
          {state.is_over && <div className="final-badge">FINAL</div>}
        </div>
        <div className={`team-score ${state.possession === 'home' ? 'has-ball' : ''}`}>
          {state.possession === 'home' && <span className="ball-indicator">🏈</span>}
          <span className="team-abbr">{state.home_team}</span>
          <span className="team-pts">{state.score.home}</span>
        </div>
      </div>
    </div>
  );
}
