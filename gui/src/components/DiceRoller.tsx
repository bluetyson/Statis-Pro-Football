import type { DiceRollResult } from '../types/game';

interface DiceRollerProps {
  lastDice: DiceRollResult | null;
  loading: boolean;
  onRoll: () => void;
}

const TENDENCY_COLORS: Record<string, string> = {
  RUN: '#22c55e',
  SHORT_PASS: '#3b82f6',
  LONG_PASS: '#8b5cf6',
  BLITZ: '#ef4444',
};

export function DiceRoller({ lastDice, loading, onRoll }: DiceRollerProps) {
  return (
    <div className="dice-roller">
      <h3 className="dice-title">🎲 Fast Action Dice</h3>
      <button className="btn btn-dice" onClick={onRoll} disabled={loading}>
        {loading ? '...' : 'Roll Dice'}
      </button>

      {lastDice && (
        <div className="dice-result">
          <div className="dice-display">
            <div className="die die-tens">{lastDice.tens}</div>
            <div className="die die-ones">{lastDice.ones}</div>
          </div>
          <div className="dice-info">
            <div
              className="tendency-badge"
              style={{ backgroundColor: TENDENCY_COLORS[lastDice.play_tendency] ?? '#6b7280' }}
            >
              {lastDice.play_tendency.replace('_', ' ')}
            </div>
            <div className="dice-meta">
              <span>2-digit: <strong>{lastDice.two_digit}</strong></span>
              <span>TO mod: <strong>{lastDice.turnover_modifier}</strong></span>
              {lastDice.penalty_check && (
                <span className="penalty-flag">⚠ Penalty Check!</span>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
