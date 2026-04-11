import type { GameState } from '../types/game';

interface PlayCallerProps {
  state: GameState;
  loading: boolean;
  onExecutePlay: () => void;
  onSimulateDrive: () => void;
  onSimulateGame: () => void;
}

function ordinal(n: number) {
  return ['', '1st', '2nd', '3rd', '4th'][n] ?? `${n}th`;
}

export function PlayCaller({
  state,
  loading,
  onExecutePlay,
  onSimulateDrive,
  onSimulateGame,
}: PlayCallerProps) {
  const disabled = loading || state.is_over;

  return (
    <div className="play-caller">
      <div className="field-situation">
        <div className="situation-chip">
          <span className="chip-label">Down & Distance</span>
          <span className="chip-value">
            {ordinal(state.down)} & {state.distance}
          </span>
        </div>
        <div className="situation-chip">
          <span className="chip-label">Field Position</span>
          <span className="chip-value">
            {state.possession.charAt(0).toUpperCase() + state.possession.slice(1)}{' '}
            {state.yard_line}
          </span>
        </div>
        <div className="situation-chip">
          <span className="chip-label">Possession</span>
          <span className="chip-value">
            {state.possession === 'home' ? state.home_team : state.away_team}
          </span>
        </div>
      </div>

      <div className="action-buttons">
        <button
          className="btn btn-primary"
          onClick={onExecutePlay}
          disabled={disabled}
        >
          {loading ? '⏳ Running...' : '▶ Run Play'}
        </button>
        <button
          className="btn btn-secondary"
          onClick={onSimulateDrive}
          disabled={disabled}
        >
          🏃 Simulate Drive
        </button>
        <button
          className="btn btn-accent"
          onClick={onSimulateGame}
          disabled={disabled}
        >
          🏆 Simulate Game
        </button>
      </div>

      {state.is_over && (
        <div className="game-over-banner">
          🏆 GAME OVER —{' '}
          {state.score.home > state.score.away
            ? `${state.home_team} wins!`
            : state.score.away > state.score.home
            ? `${state.away_team} wins!`
            : 'TIE GAME!'}
        </div>
      )}
    </div>
  );
}
