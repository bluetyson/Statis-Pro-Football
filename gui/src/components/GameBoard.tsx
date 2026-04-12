import { useState } from 'react';
import type { GameState, PlayResult, DriveResult, PersonnelData, HumanPlayCall, DefensivePlayCall, GameMode } from '../types/game';
import { Scoreboard } from './Scoreboard';
import { PlayCaller } from './PlayCaller';
import { HumanPlayCaller } from './HumanPlayCaller';
import { DefensivePlayCaller } from './DefensivePlayCaller';
import { GameLog } from './GameLog';
import { Gridiron } from './Gridiron';
import { LetterBoards } from './LetterBoards';
import { SubstitutionPanel } from './SubstitutionPanel';
import { DiceRoller } from './DiceRoller';
import { FACCardDisplay } from './FACCardDisplay';
import { GameStats } from './GameStats';
import type { DiceRollResult } from '../types/game';

function formatDefenseFormation(formation?: string | null): string {
  if (!formation) return '';
  return formation.replace(/_/g, ' ');
}

function DebugLogPanel({ log }: { log: string[] }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="debug-log-panel">
      <button className="debug-toggle" onClick={() => setExpanded(!expanded)}>
        🔍 {expanded ? 'Hide' : 'Show'} Resolution Details ({log.length} steps)
      </button>
      {expanded && (
        <div className="debug-log-entries">
          {log.map((entry, i) => (
            <div key={i} className={`debug-entry ${
              entry.includes('[SACK]') || entry.includes('[P.RUSH]') ? 'debug-sack' :
              entry.includes('[INT]') ? 'debug-int' :
              entry.includes('[COM]') ? 'debug-com' :
              entry.includes('[INC]') ? 'debug-inc' :
              ''
            }`}>
              {entry}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

interface GameBoardProps {
  gameId: string;
  state: GameState;
  gameMode: GameMode;
  lastPlay: PlayResult | null;
  lastDrive: DriveResult | null;
  lastDice: DiceRollResult | null;
  personnel: PersonnelData | null;
  loading: boolean;
  isHumanTurn: boolean;
  isHumanOnDefense: boolean;
  onExecutePlay: () => void;
  onExecuteHumanPlay: (call: HumanPlayCall) => void;
  onExecuteHumanDefense: (call: DefensivePlayCall) => void;
  onSimulateDrive: () => void;
  onSimulateGame: () => void;
  onRollDice: () => void;
  onSubstitute: (position: string, playerOut: string, playerIn: string) => void;
  onCallTimeout: (team?: string) => void;
  onFakePunt: () => void;
  onFakeFG: () => void;
  onCoffinCorner: (deduction: number) => void;
  onOnsideKick: (onsideDefense?: boolean) => void;
  onSquibKick: () => void;
  onTwoPointConversion: (playType: string) => void;
  onDownloadGameLog: () => void;
  onNewGame: () => void;
}

export function GameBoard({
  gameId,
  state,
  gameMode,
  lastPlay,
  lastDrive,
  lastDice,
  personnel,
  loading,
  isHumanTurn,
  isHumanOnDefense,
  onExecutePlay,
  onExecuteHumanPlay,
  onExecuteHumanDefense,
  onSimulateDrive,
  onSimulateGame,
  onRollDice,
  onSubstitute,
  onCallTimeout,
  onFakePunt,
  onFakeFG,
  onCoffinCorner,
  onOnsideKick,
  onSquibKick,
  onTwoPointConversion,
  onDownloadGameLog,
  onNewGame,
}: GameBoardProps) {
  const isInteractive = gameMode !== 'solitaire';
  const [showTwoPoint, setShowTwoPoint] = useState(false);
  const [coffinDeduction, setCoffinDeduction] = useState(15);

  // Detect touchdown for two-point conversion option
  const isTouchdown = lastPlay?.is_touchdown === true;

  // Halftime / Quarter break detection
  const isHalftime = state.quarter === 2 && state.time_remaining === 0 && !state.is_over;
  const isQuarterBreak = !isHalftime && state.time_remaining === 0 && state.quarter < 5 && !state.is_over;
  const isOvertime = state.quarter > 4;

  return (
    <div className="game-board">
      <div className="board-header">
        <h1 className="board-title">🏈 Statis Pro Football</h1>
        <div className="board-header-actions">
          <span className="mode-badge">
            {gameMode === 'human_home' ? '🏠 Home' :
             gameMode === 'human_away' ? '✈️ Away' : '🤖 Sim'}
          </span>
          <button className="btn btn-outline btn-sm" onClick={onDownloadGameLog}>
            📥 Save Log
          </button>
          <button className="btn btn-outline btn-sm" onClick={onNewGame}>
            New Game
          </button>
        </div>
      </div>

      <Scoreboard state={state} />

      {/* Halftime / Quarter break / Overtime indicators */}
      {isHalftime && (
        <div className="game-break-banner halftime-banner">
          🏟️ HALFTIME — {state.home_team} {state.score.home} - {state.away_team} {state.score.away}
        </div>
      )}
      {isQuarterBreak && (
        <div className="game-break-banner quarter-banner">
          📋 End of Q{state.quarter} — {state.home_team} {state.score.home} - {state.away_team} {state.score.away}
        </div>
      )}
      {isOvertime && (
        <div className="game-break-banner overtime-banner">
          ⏰ OVERTIME
        </div>
      )}

      {/* Gridiron field display */}
      <Gridiron state={state} />

      {/* Timeout buttons */}
      {isInteractive && !state.is_over && (
        <div className="timeout-actions">
          <button
            className="btn btn-outline btn-sm timeout-btn"
            onClick={() => onCallTimeout('home')}
            disabled={loading || state.timeouts_home <= 0}
            title={`${state.home_team} timeouts: ${state.timeouts_home}`}
          >
            ⏱️ {state.home_team} TO ({state.timeouts_home})
          </button>
          <button
            className="btn btn-outline btn-sm timeout-btn"
            onClick={() => onCallTimeout('away')}
            disabled={loading || state.timeouts_away <= 0}
            title={`${state.away_team} timeouts: ${state.timeouts_away}`}
          >
            ⏱️ {state.away_team} TO ({state.timeouts_away})
          </button>
        </div>
      )}

      {/* Two-point conversion prompt after TD */}
      {isTouchdown && isInteractive && (
        <div className="two-point-prompt">
          <span className="two-point-label">🎉 TOUCHDOWN! Extra point attempt:</span>
          <div className="two-point-buttons">
            <button className="btn btn-secondary btn-sm" onClick={() => setShowTwoPoint(false)} disabled={loading}>
              ✅ PAT (kick)
            </button>
            <button className="btn btn-accent btn-sm" onClick={() => setShowTwoPoint(true)} disabled={loading}>
              2️⃣ Two-Point Conversion
            </button>
          </div>
          {showTwoPoint && (
            <div className="two-point-options">
              <button className="btn btn-primary btn-sm" onClick={() => { onTwoPointConversion('RUN'); setShowTwoPoint(false); }} disabled={loading}>
                🏃 Run
              </button>
              <button className="btn btn-primary btn-sm" onClick={() => { onTwoPointConversion('SHORT_PASS'); setShowTwoPoint(false); }} disabled={loading}>
                📫 Short Pass
              </button>
              <button className="btn btn-primary btn-sm" onClick={() => { onTwoPointConversion('QUICK_PASS'); setShowTwoPoint(false); }} disabled={loading}>
                ⚡ Quick Pass
              </button>
            </div>
          )}
        </div>
      )}

      {/* Injury tracker */}
      {state.injuries && Object.keys(state.injuries).length > 0 && (
        <div className="injury-tracker">
          <span className="injury-header">🏥 Active Injuries:</span>
          <div className="injury-list">
            {Object.entries(state.injuries).map(([name, plays]) => (
              <span key={name} className="injury-chip">
                {name} ({plays} plays)
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="board-content">
        <div className="board-left">
          {/* Play caller: human offense, human defense, or AI mode */}
          {isInteractive && isHumanTurn ? (
            <HumanPlayCaller
              state={state}
              personnel={personnel}
              loading={loading}
              onCallPlay={onExecuteHumanPlay}
              onSimulateDrive={onSimulateDrive}
              onSimulateGame={onSimulateGame}
              onExecuteAIPlay={onExecutePlay}
              onFakePunt={onFakePunt}
              onFakeFG={onFakeFG}
              onCoffinCorner={onCoffinCorner}
              coffinDeduction={coffinDeduction}
              onCoffinDeductionChange={setCoffinDeduction}
              onOnsideKick={onOnsideKick}
              onSquibKick={onSquibKick}
            />
          ) : isInteractive && isHumanOnDefense ? (
            <DefensivePlayCaller
              state={state}
              loading={loading}
              onCallDefense={onExecuteHumanDefense}
              onSimulateDrive={onSimulateDrive}
              onSimulateGame={onSimulateGame}
              onExecuteAIPlay={onExecutePlay}
            />
          ) : (
            <PlayCaller
              state={state}
              loading={loading}
              onExecutePlay={onExecutePlay}
              onSimulateDrive={onSimulateDrive}
              onSimulateGame={onSimulateGame}
            />
          )}

          {/* Turn indicator for interactive mode */}
          {isInteractive && !state.is_over && (
            <div className={`turn-indicator ${isHumanTurn ? 'your-turn' : isHumanOnDefense ? 'your-defense' : 'ai-turn'}`}>
              {isHumanTurn
                ? '🎮 YOUR TURN — Call an offensive play!'
                : isHumanOnDefense
                ? '🛡️ YOUR DEFENSE — Call a defensive formation!'
                : '🤖 AI\'s turn — Run AI Play or Sim Drive'}
            </div>
          )}

          {lastPlay && (
            <div className={`last-play-card ${lastPlay.is_touchdown ? 'play-td' : lastPlay.turnover ? 'play-turnover' : ''}`}>
              <div className="last-play-label">Last Play</div>
              <div className="last-play-desc">{lastPlay.description}</div>
              {(lastPlay.run_number != null || lastPlay.pass_number != null || lastPlay.defense_formation) && (
                <div className="last-play-resolution">
                  {lastPlay.run_number != null && <span>RN {lastPlay.run_number}</span>}
                  {lastPlay.pass_number != null && <span>PN {lastPlay.pass_number}</span>}
                  {lastPlay.defense_formation && <span>{formatDefenseFormation(lastPlay.defense_formation)}</span>}
                </div>
              )}
              {(lastPlay.offensive_play_call || lastPlay.defensive_play_call) && (
                <div className="last-play-calls">
                  {lastPlay.offensive_play_call && <span className="play-call-badge off-call">OFF: {lastPlay.offensive_play_call}</span>}
                  {lastPlay.defensive_play_call && <span className="play-call-badge def-call">DEF: {lastPlay.defensive_play_call}</span>}
                </div>
              )}
              <div className="last-play-meta">
                <span>{lastPlay.play_type}</span>
                <span>{lastPlay.yards >= 0 ? '+' : ''}{lastPlay.yards} yds</span>
                <span className="play-result-badge">{lastPlay.result}</span>
                {lastPlay.passer && <span>QB: {lastPlay.passer}</span>}
                {lastPlay.receiver && <span>→ {lastPlay.receiver}</span>}
                {lastPlay.rusher && <span>🏃 {lastPlay.rusher}</span>}
              </div>
              {/* Debug log (collapsible) */}
              {lastPlay.debug_log && lastPlay.debug_log.length > 0 && (
                <DebugLogPanel log={lastPlay.debug_log} />
              )}
            </div>
          )}

          {lastDrive && (
            <div className="last-drive-card">
              <div className="last-play-label">Last Drive</div>
              <div className="drive-summary">
                <span>{lastDrive.plays} plays</span>
                <span>{lastDrive.yards} yards</span>
                <span className="drive-result-badge">{lastDrive.result}</span>
                {lastDrive.points_scored > 0 && (
                  <span className="drive-pts">+{lastDrive.points_scored} pts</span>
                )}
              </div>
            </div>
          )}

          {/* Substitution panel (interactive modes, on offense or defense) */}
          {isInteractive && (isHumanTurn || isHumanOnDefense) && (
            <SubstitutionPanel
              personnel={personnel}
              loading={loading}
              onSubstitute={onSubstitute}
            />
          )}

          <DiceRoller lastDice={lastDice} loading={loading} onRoll={onRollDice} />
          
          {/* FAC Card Display (5E mode) */}
          <FACCardDisplay lastPlay={lastPlay} />
          
          {/* Game Stats */}
          <GameStats state={state} />
        </div>

        <div className="board-right">
          {/* Letter boards for offense/defense — always visible */}
          <LetterBoards
            personnel={personnel}
            possession={state.possession}
            defenseFormation={lastPlay?.defense_formation ?? undefined}
          />

          <GameLog plays={state.last_plays} />
        </div>
      </div>

      <div className="game-id-footer">Game ID: {gameId}</div>
    </div>
  );
}
