import { useState } from 'react';
import type { GameState, DefensivePlayCall } from '../types/game';
import { DEFENSIVE_FORMATIONS, DEFENSIVE_STRATEGIES } from '../types/game';

interface DefensivePlayCallerProps {
  state: GameState;
  loading: boolean;
  onCallDefense: (call: DefensivePlayCall) => void;
  onSimulateDrive: () => void;
  onSimulateGame: () => void;
  onExecuteAIPlay: () => void;
}

function ordinal(n: number) {
  return ['', '1st', '2nd', '3rd', '4th'][n] ?? `${n}th`;
}

export function DefensivePlayCaller({
  state,
  loading,
  onCallDefense,
  onSimulateDrive,
  onSimulateGame,
  onExecuteAIPlay,
}: DefensivePlayCallerProps) {
  const [selectedFormation, setSelectedFormation] = useState<string>('4_3');
  const [selectedStrategy, setSelectedStrategy] = useState<string>('NONE');

  const disabled = loading || state.is_over;

  const handleCallDefense = () => {
    onCallDefense({ 
      formation: selectedFormation,
      defensive_strategy: selectedStrategy !== 'NONE' ? selectedStrategy : undefined,
    });
  };

  return (
    <div className="human-play-caller defense-caller">
      {/* Situation bar */}
      <div className="field-situation">
        <div className="situation-chip defense-chip">
          <span className="chip-label">🛡️ Defense</span>
          <span className="chip-value">Your Defense</span>
        </div>
        <div className="situation-chip">
          <span className="chip-label">Down &amp; Distance</span>
          <span className="chip-value">
            {ordinal(state.down)} &amp; {state.distance}
          </span>
        </div>
        <div className="situation-chip">
          <span className="chip-label">Field Position</span>
          <span className="chip-value">
            {state.yard_line > 50
              ? `OPP ${100 - state.yard_line}`
              : state.yard_line === 50
              ? 'MIDFIELD'
              : `OWN ${state.yard_line}`}
          </span>
        </div>
        <div className="situation-chip">
          <span className="chip-label">Offense</span>
          <span className="chip-value">
            {state.possession === 'home' ? state.home_team : state.away_team} (AI)
          </span>
        </div>
      </div>

      {/* Defensive formation selection */}
      <div className="play-type-section">
        <label className="section-label">Select Defensive Formation</label>
        <div className="play-type-grid defense-grid">
          {DEFENSIVE_FORMATIONS.map((f) => (
            <button
              key={f.value}
              className={`play-type-btn defense-btn ${selectedFormation === f.value ? 'selected' : ''}`}
              style={
                selectedFormation === f.value
                  ? { borderColor: '#ef4444', backgroundColor: '#ef444422' }
                  : {}
              }
              onClick={() => setSelectedFormation(f.value)}
              disabled={disabled}
            >
              {f.icon} {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Formation description */}
      <div className="formation-info">
        <FormationDescription formation={selectedFormation} />
      </div>

      {/* Defensive strategy selection (5E rules) */}
      <div className="play-option">
        <label className="section-label">Defensive Strategy (5E)</label>
        <div className="option-pills">
          {DEFENSIVE_STRATEGIES.map((s) => (
            <button
              key={s.value}
              className={`option-pill ${selectedStrategy === s.value ? 'selected' : ''}`}
              onClick={() => setSelectedStrategy(s.value)}
              disabled={disabled}
              title={s.label}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Execute button */}
      <div className="action-buttons">
        <button
          className="btn btn-danger btn-lg"
          onClick={handleCallDefense}
          disabled={disabled}
        >
          {loading ? '⏳ Running...' : '🛡️ Set Defense'}
        </button>
      </div>

      {/* Simulate options */}
      <div className="sim-buttons">
        <button className="btn btn-secondary btn-sm" onClick={onExecuteAIPlay} disabled={disabled}>
          🤖 AI Play
        </button>
        <button className="btn btn-secondary btn-sm" onClick={onSimulateDrive} disabled={disabled}>
          🏃 Sim Drive
        </button>
        <button className="btn btn-accent btn-sm" onClick={onSimulateGame} disabled={disabled}>
          🏆 Sim Game
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

function FormationDescription({ formation }: { formation: string }) {
  const descriptions: Record<string, string> = {
    '4_3': '4 DL, 3 LB — Balanced base defense. Good all-around.',
    '3_4': '3 DL, 4 LB — Extra LB for coverage and run support.',
    '4_3_COVER2': '4 DL, 3 LB, Cover 2 — Strong pass coverage, weaker run stop.',
    '3_4_ZONE': '3 DL, 4 LB, Zone — Good coverage, solid run stop.',
    '4_3_BLITZ': '4 DL, 3 LB, Blitz — Heavy pass rush (+15), weak coverage (-10).',
    'NICKEL_ZONE': '4 DL, 2 LB, 5 DB — Great coverage (+15), weak run stop (-10).',
    'NICKEL_BLITZ': '4 DL, 2 LB, 5 DB, Blitz — Strong rush (+15), decent coverage.',
    'NICKEL_COVER2': '4 DL, 2 LB, 5 DB, Cover 2 — Good coverage, weak run stop.',
    'GOAL_LINE': '5+ DL, LB — Massive run stop (+20), no pass coverage (-15).',
  };

  return (
    <div className="formation-desc">
      {descriptions[formation] ?? 'Select a formation'}
    </div>
  );
}
