import { useEffect, useMemo, useState } from 'react';
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
  onFakePunt: () => void;
  onFakeFG: () => void;
  onCoffinCorner: (deduction: number) => void;
  coffinDeduction: number;
  onCoffinDeductionChange: (d: number) => void;
  onOnsideKick: (onsideDefense?: boolean) => void;
  onSquibKick: () => void;
}

const PLAY_TYPES = [
  { value: 'RUN', label: '🏃 Run', color: '#22c55e' },
  { value: 'SHORT_PASS', label: '📫 Short Pass', color: '#3b82f6' },
  { value: 'LONG_PASS', label: '🎯 Long Pass', color: '#8b5cf6' },
  { value: 'QUICK_PASS', label: '⚡ Quick Pass', color: '#06b6d4' },
  { value: 'SCREEN', label: '🖥️ Screen', color: '#f59e0b' },
  { value: 'END_AROUND', label: '🔄 End-Around', color: '#10b981' },
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
  onFakePunt,
  onFakeFG,
  onCoffinCorner,
  coffinDeduction,
  onCoffinDeductionChange,
  onOnsideKick,
  onSquibKick,
}: HumanPlayCallerProps) {
  const [selectedPlay, setSelectedPlay] = useState<string>('RUN');
  const [selectedDirection, setSelectedDirection] = useState<string>('MIDDLE');
  const [selectedFormation, setSelectedFormation] = useState<string>('UNDER_CENTER');
  const [selectedStrategy, setSelectedStrategy] = useState<string>('NONE');
  const [selectedPlayer, setSelectedPlayer] = useState<string>('');

  const disabled = loading || state.is_over;

  const isRunPlay = selectedPlay === 'RUN' || selectedPlay === 'END_AROUND';
  const isPassPlay = ['SHORT_PASS', 'LONG_PASS', 'QUICK_PASS', 'SCREEN'].includes(selectedPlay);
  const isSpecialPlay = ['PUNT', 'FG', 'KNEEL'].includes(selectedPlay);

  const directions = isRunPlay ? RUN_DIRECTIONS : PASS_DIRECTIONS;

  // Get available players based on play type
  const ballCarriers = useMemo(() => (
    personnel ? personnel.offense_all.filter(p =>
      p.position === 'RB' || p.position === 'QB' || p.position === 'WR'
    ) : []
  ), [personnel]);
  const availableBallCarriers = useMemo(
    () => ballCarriers.filter((p) => !p.injured),
    [ballCarriers],
  );

  const receiverTargets = useMemo(
    () => personnel ? personnel.offense_receivers : [],
    [personnel],
  );
  const availableReceiverTargets = useMemo(
    () => receiverTargets.filter((p) => !p.injured),
    [receiverTargets],
  );
  const autoBallCarrier = useMemo(
    () => availableBallCarriers.find((p) => p.position === 'RB') ?? availableBallCarriers[0] ?? null,
    [availableBallCarriers],
  );
  const noEligiblePlayer = useMemo(
    () => ((selectedPlay === 'RUN' || selectedPlay === 'END_AROUND') && availableBallCarriers.length === 0) ||
      (['SHORT_PASS', 'LONG_PASS', 'QUICK_PASS', 'SCREEN'].includes(selectedPlay) && availableReceiverTargets.length === 0),
    [availableBallCarriers.length, availableReceiverTargets.length, selectedPlay],
  );

  useEffect(() => {
    const pool = isRunPlay ? availableBallCarriers : availableReceiverTargets;
    if (selectedPlayer && !pool.some((p) => p.name === selectedPlayer)) {
      setSelectedPlayer('');
    }
  }, [availableBallCarriers, availableReceiverTargets, isRunPlay, selectedPlayer]);

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

      {/* Player selection — Ball Carrier for runs, Receiver Target for passes */}
      {!isSpecialPlay && isRunPlay && ballCarriers.length > 0 && (
        <div className="play-option">
          <label className="section-label">Ball Carrier</label>
          <select
            className="player-select"
            value={selectedPlayer}
            onChange={(e) => setSelectedPlayer(e.target.value)}
            disabled={disabled}
          >
            <option value="">{autoBallCarrier ? `Auto (${autoBallCarrier.name})` : 'Auto (No healthy ball carrier)'}</option>
            {ballCarriers.map((p) => (
              <option key={p.name} value={p.name} disabled={p.injured}>
                {p.name} ({p.position}) - {p.overall_grade}{p.injured ? ' [INJ]' : ''}
              </option>
            ))}
          </select>
        </div>
      )}
      {!isSpecialPlay && isPassPlay && receiverTargets.length > 0 && (
        <div className="play-option">
          <label className="section-label">Receiver Target</label>
          <select
            className="player-select"
            value={selectedPlayer}
            onChange={(e) => setSelectedPlayer(e.target.value)}
            disabled={disabled}
          >
            <option value="">Auto (FAC card determines)</option>
            {receiverTargets.map((p) => (
              <option key={p.name} value={p.name} disabled={p.injured}>
                {p.name} ({p.position}{p.receiver_letter ? ` [${p.receiver_letter}]` : ''}) - {p.overall_grade}{p.injured ? ' [INJ]' : ''}
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
          disabled={disabled || noEligiblePlayer}
        >
          {loading ? '⏳ Running...' : '▶ Call Play'}
        </button>
      </div>

      {isRunPlay && (
        <div className="timeout-info">
          <span>
            {autoBallCarrier
              ? `🔄 Auto ball carrier: ${autoBallCarrier.name}`
              : '⚠ No healthy ball carrier available'}
          </span>
        </div>
      )}
      {isPassPlay && availableReceiverTargets.length === 0 && (
        <div className="timeout-info">
          <span>⚠ No healthy eligible receiver available</span>
        </div>
      )}

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

      {/* Special Teams Options */}
      <div className="special-teams-section">
        <details className="special-teams-details">
          <summary className="section-label special-teams-toggle">🏈 Special Teams Options</summary>
          <div className="special-teams-grid">
            <button className="btn btn-outline btn-sm" onClick={onFakePunt} disabled={disabled} title="Once per game">
              🎭 Fake Punt
            </button>
            <button className="btn btn-outline btn-sm" onClick={onFakeFG} disabled={disabled} title="Once per game, not in final 2 min">
              🎭 Fake FG
            </button>
            <div className="coffin-corner-group">
              <button
                className="btn btn-outline btn-sm"
                onClick={() => onCoffinCorner(coffinDeduction)}
                disabled={disabled}
                title={`Punt with ${coffinDeduction}yd deduction`}
              >
                ⚰️ Coffin Corner
              </button>
              <input
                type="range"
                min={10}
                max={25}
                value={coffinDeduction}
                onChange={(e) => onCoffinDeductionChange(Number(e.target.value))}
                className="coffin-slider"
                disabled={disabled}
              />
              <span className="coffin-value">-{coffinDeduction}yd</span>
            </div>
            <button className="btn btn-outline btn-sm" onClick={() => onOnsideKick()} disabled={disabled}>
              🏈 Onside Kick
            </button>
            <button className="btn btn-outline btn-sm" onClick={onSquibKick} disabled={disabled}>
              🏈 Squib Kick
            </button>
          </div>
        </details>
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
