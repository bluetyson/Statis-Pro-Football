import { useState } from 'react';
import type { GameState, HumanPlayCall, PersonnelData } from '../types/game';
import { OFFENSIVE_STRATEGIES } from '../types/game';

interface HumanPlayCallerProps {
  state: GameState;
  personnel: PersonnelData | null;
  loading: boolean;
  onCallPlay: (call: HumanPlayCall) => void;
  onSimulateDrive: () => void;
  onSimulateGame: () => void;
  onExecuteAIPlay: () => void;
}

const PLAY_TYPES = [
  { value: 'RUN', label: '🏃 Run', color: '#22c55e' },
  { value: 'SHORT_PASS', label: '📫 Short Pass', color: '#3b82f6' },
  { value: 'LONG_PASS', label: '🎯 Long Pass', color: '#8b5cf6' },
  { value: 'QUICK_PASS', label: '⚡ Quick Pass', color: '#06b6d4' },
  { value: 'SCREEN', label: '🖥️ Screen', color: '#f59e0b' },
  { value: 'PUNT', label: '🦵 Punt', color: '#6b7280' },
  { value: 'FG', label: '🥅 Field Goal', color: '#ef4444' },
  { value: 'KNEEL', label: '🧎 Kneel', color: '#374151' },
];

const KICKOFF_TYPES = [
  { value: 'NORMAL', label: 'Normal Kickoff' },
  { value: 'ONSIDE', label: 'Onside Kick' },
  { value: 'SQUIB', label: 'Squib Kick' },
];

const RUN_DIRECTIONS = [
  { value: 'IL', label: 'Inside Left' },
  { value: 'IR', label: 'Inside Right' },
  { value: 'SL', label: 'Sweep Left' },
  { value: 'SR', label: 'Sweep Right' },
  { value: 'MIDDLE', label: 'Middle' },
];

const PASS_DIRECTIONS = [
  { value: 'LEFT', label: 'Left' },
  { value: 'RIGHT', label: 'Right' },
  { value: 'MIDDLE', label: 'Middle' },
  { value: 'DEEP_LEFT', label: 'Deep Left' },
  { value: 'DEEP_RIGHT', label: 'Deep Right' },
];

const FORMATIONS = [
  { value: 'SHOTGUN', label: 'Shotgun' },
  { value: 'UNDER_CENTER', label: 'Under Center' },
  { value: 'I_FORM', label: 'I-Formation' },
  { value: 'TRIPS', label: 'Trips' },
  { value: 'SPREAD', label: 'Spread' },
];

function ordinal(n: number) {
  return ['', '1st', '2nd', '3rd', '4th'][n] ?? `${n}th`;
}

export function HumanPlayCaller({
  state,
  personnel,
  loading,
  onCallPlay,
  onSimulateDrive,
  onSimulateGame,
  onExecuteAIPlay,
}: HumanPlayCallerProps) {
  const [selectedPlay, setSelectedPlay] = useState<string>('RUN');
  const [selectedDirection, setSelectedDirection] = useState<string>('MIDDLE');
  const [selectedFormation, setSelectedFormation] = useState<string>('UNDER_CENTER');
  const [selectedStrategy, setSelectedStrategy] = useState<string>('NONE');
  const [selectedPlayer, setSelectedPlayer] = useState<string>('');

  const disabled = loading || state.is_over;

  const isRunPlay = selectedPlay === 'RUN';
  const isPassPlay = ['SHORT_PASS', 'LONG_PASS', 'QUICK_PASS', 'SCREEN'].includes(selectedPlay);
  const isSpecialPlay = ['PUNT', 'FG', 'KNEEL'].includes(selectedPlay);

  const directions = isRunPlay ? RUN_DIRECTIONS : PASS_DIRECTIONS;

  // Get available players based on play type
  const availablePlayers = personnel ? (
    isRunPlay ? [
      ...(personnel.offense_starters['QB'] ? [personnel.offense_starters['QB']] : []),
      ...personnel.offense_all.filter(p => p.position === 'RB')
    ] :
    isPassPlay ? [
      ...(personnel.offense_starters['QB'] ? [personnel.offense_starters['QB']] : []),
      ...personnel.offense_receivers
    ] :
    []
  ) : [];

  const handleCallPlay = () => {
    onCallPlay({
      play_type: selectedPlay,
      direction: isSpecialPlay ? 'MIDDLE' : selectedDirection,
      formation: isSpecialPlay ? 'SHOTGUN' : selectedFormation,
      strategy: selectedStrategy !== 'NONE' ? selectedStrategy : undefined,
      player_name: selectedPlayer || undefined,
    });
  };

  return (
    <div className="human-play-caller">
      {/* Situation bar */}
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
            {state.yard_line > 50
              ? `OPP ${100 - state.yard_line}`
              : state.yard_line === 50
              ? 'MIDFIELD'
              : `OWN ${state.yard_line}`}
          </span>
        </div>
        <div className="situation-chip">
          <span className="chip-label">Possession</span>
          <span className="chip-value">
            {state.possession === 'home' ? state.home_team : state.away_team}
          </span>
        </div>
      </div>

      {/* Play type selection */}
      <div className="play-type-section">
        <label className="section-label">Select Play</label>
        <div className="play-type-grid">
          {PLAY_TYPES.map((pt) => (
            <button
              key={pt.value}
              className={`play-type-btn ${selectedPlay === pt.value ? 'selected' : ''}`}
              style={
                selectedPlay === pt.value
                  ? { borderColor: pt.color, backgroundColor: `${pt.color}22` }
                  : {}
              }
              onClick={() => setSelectedPlay(pt.value)}
              disabled={disabled}
            >
              {pt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Direction & Formation (not for special plays) */}
      {!isSpecialPlay && (
        <div className="play-options-row">
          <div className="play-option">
            <label className="section-label">Direction</label>
            <div className="option-pills">
              {directions.map((d) => (
                <button
                  key={d.value}
                  className={`option-pill ${selectedDirection === d.value ? 'selected' : ''}`}
                  onClick={() => setSelectedDirection(d.value)}
                  disabled={disabled}
                >
                  {d.label}
                </button>
              ))}
            </div>
          </div>
          <div className="play-option">
            <label className="section-label">Formation</label>
            <div className="option-pills">
              {FORMATIONS.map((f) => (
                <button
                  key={f.value}
                  className={`option-pill ${selectedFormation === f.value ? 'selected' : ''}`}
                  onClick={() => setSelectedFormation(f.value)}
                  disabled={disabled}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Strategy selection (5E rules) */}
      {!isSpecialPlay && (
        <div className="play-option">
          <label className="section-label">Strategy (5E)</label>
          <div className="option-pills">
            {OFFENSIVE_STRATEGIES.map((s) => (
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
      )}

      {/* Player selection */}
      {!isSpecialPlay && availablePlayers.length > 0 && (
        <div className="play-option">
          <label className="section-label">
            {isRunPlay ? 'Ball Carrier' : 'Quarterback'}
          </label>
          <select
            className="player-select"
            value={selectedPlayer}
            onChange={(e) => setSelectedPlayer(e.target.value)}
            disabled={disabled}
          >
            <option value="">Auto (Starter)</option>
            {availablePlayers.map((p) => (
              <option key={p.name} value={p.name}>
                {p.name} ({p.position}) - {p.grade}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Execute button */}
      <div className="action-buttons">
        <button
          className="btn btn-primary btn-lg"
          onClick={handleCallPlay}
          disabled={disabled}
        >
          {loading ? '⏳ Running...' : '▶ Call Play'}
        </button>
      </div>

      {/* Timeout info */}
      <div className="timeout-info">
        <span>⏱️ Timeouts: {state.possession === 'home' ? state.timeouts_home : state.timeouts_away} remaining</span>
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
