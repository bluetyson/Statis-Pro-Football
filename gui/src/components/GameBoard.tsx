import { useState } from 'react';
import type { GameState, PlayResult, DriveResult, PersonnelData, HumanPlayCall, DefensivePlayCall, GameMode } from '../types/game';
import type { SignificantEvent } from '../hooks/useGameEngine';
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
import { DisplayBoxes } from './DisplayBoxes';
import { StartingLineup } from './StartingLineup';
import { DepthChart } from './DepthChart';
import { CardViewer } from './CardViewer';
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
              entry.includes('[RUSH]') || entry.includes('[RN]') ? 'debug-run' :
              entry.includes('[FAC]') ? 'debug-fac' :
              entry.includes('[YARDS]') || entry.includes('[RESULT]') ? 'debug-result' :
              entry.includes('[FUMBLE]') ? 'debug-int' :
              entry.includes('[TACKLE]') || entry.includes('[DEF]') ? 'debug-def' :
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

function PlayerStatsPanel({ stats }: { stats: Record<string, Record<string, number>> }) {
  const [expanded, setExpanded] = useState(false);
  const players = Object.entries(stats).filter(
    ([, s]) => (s.rushing_attempts || 0) > 0 || (s.pass_attempts || 0) > 0 || (s.receptions || 0) > 0
  );
  if (players.length === 0) return null;

  return (
    <div className="player-stats-panel" style={{ background: '#1a1a2e', borderRadius: '8px', padding: '8px', margin: '8px 0' }}>
      <button
        className="debug-toggle"
        onClick={() => setExpanded(!expanded)}
        style={{ width: '100%', textAlign: 'left', padding: '4px 8px' }}
      >
        📊 {expanded ? 'Hide' : 'Show'} Player Stats ({players.length} players)
      </button>
      {expanded && (
        <div style={{ fontSize: '0.75em', overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #333', color: '#aaa' }}>
                <th style={{ textAlign: 'left', padding: '4px' }}>Player</th>
                <th>Rush</th><th>RuYds</th><th>RuTD</th>
                <th>Att</th><th>Cmp</th><th>PaYds</th><th>PaTD</th><th>INT</th>
                <th>Rec</th><th>ReYds</th><th>ReTD</th>
              </tr>
            </thead>
            <tbody>
              {players.map(([name, s]) => (
                <tr key={name} style={{ borderBottom: '1px solid #222' }}>
                  <td style={{ padding: '2px 4px', color: '#ddd' }}>{name}</td>
                  <td style={{ textAlign: 'center' }}>{s.rushing_attempts || 0}</td>
                  <td style={{ textAlign: 'center' }}>{s.rushing_yards || 0}</td>
                  <td style={{ textAlign: 'center' }}>{s.rushing_tds || 0}</td>
                  <td style={{ textAlign: 'center' }}>{s.pass_attempts || 0}</td>
                  <td style={{ textAlign: 'center' }}>{s.completions || 0}</td>
                  <td style={{ textAlign: 'center' }}>{s.passing_yards || 0}</td>
                  <td style={{ textAlign: 'center' }}>{s.passing_tds || 0}</td>
                  <td style={{ textAlign: 'center' }}>{s.interceptions || 0}</td>
                  <td style={{ textAlign: 'center' }}>{s.receptions || 0}</td>
                  <td style={{ textAlign: 'center' }}>{s.receiving_yards || 0}</td>
                  <td style={{ textAlign: 'center' }}>{s.receiving_tds || 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
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
  significantEvents: SignificantEvent[];
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
  onBigPlayDefense: () => void;
  onTwoMinuteOffense: () => void;
  onDownloadGameLog: () => void;
  onNewGame: () => void;
  onRefreshPersonnel?: () => void;
}

export function GameBoard({
  gameId,
  state,
  gameMode,
  lastPlay,
  lastDrive,
  lastDice,
  personnel,
  significantEvents,
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
  onBigPlayDefense,
  onTwoMinuteOffense,
  onDownloadGameLog,
  onNewGame,
  onRefreshPersonnel,
}: GameBoardProps) {
  const isInteractive = gameMode !== 'solitaire';
  const [showTwoPoint, setShowTwoPoint] = useState(false);
  const [coffinDeduction, setCoffinDeduction] = useState(15);
  const [showCardViewer, setShowCardViewer] = useState<string | null>(null);
  /** Name of the ball carrier selected in the HumanPlayCaller dropdown ('' = auto). */
  const [selectedBallCarrier, setSelectedBallCarrier] = useState<string>('');

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

      {/* Significant Events ticker — injuries, TDs, turnovers, first downs */}
      {significantEvents.length > 0 && (
        <div className="significant-events-panel">
          <span className="significant-events-header">⚡ Key Events</span>
          <div className="significant-events-list">
            {significantEvents.map((ev) => (
              <div
                key={ev.id}
                className={`significant-event significant-event-${ev.kind}`}
              >
                <span className="se-icon">{ev.icon}</span>
                <span className="se-text">{ev.text}</span>
              </div>
            ))}
          </div>
        </div>
      )}

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

      {/* Two-Minute Offense & Big Play Defense buttons */}
      {isInteractive && !state.is_over && (
        <div className="tactical-actions" style={{ display: 'flex', gap: '8px', padding: '4px 12px' }}>
          {isHumanTurn && state.quarter >= 2 && state.time_remaining <= 180 && (
            <button
              className="btn btn-accent btn-sm"
              onClick={onTwoMinuteOffense}
              disabled={loading}
              title="Declare two-minute offense: halved time, halved run yardage"
            >
              ⏱️ Two-Minute Offense
            </button>
          )}
          {isHumanOnDefense && (
            <button
              className="btn btn-accent btn-sm"
              onClick={onBigPlayDefense}
              disabled={loading}
              title="Activate Big Play Defense (once per series, 9+ wins required)"
            >
              🛡️ Big Play Defense
            </button>
          )}
          {isHumanOnDefense && (
            <button
              className="btn btn-outline btn-sm"
              onClick={() => onOnsideKick(true)}
              disabled={loading}
              title="Declare onside kick defense (reduces recovery chance for kicker)"
            >
              🏈 Onside Defense
            </button>
          )}
        </div>
      )}

      {/* Penalty & Turnover Summary */}
      {(state.penalties || state.turnovers) && (
        <div className="penalty-turnover-bar" style={{ display: 'flex', gap: '16px', padding: '4px 12px', fontSize: '0.8em', color: '#aaa' }}>
          {state.penalties && (
            <span>
              🚩 Penalties: {state.home_team} {state.penalties.home || 0} ({state.penalty_yards?.home || 0} yds)
              {' / '}{state.away_team} {state.penalties.away || 0} ({state.penalty_yards?.away || 0} yds)
            </span>
          )}
          {state.turnovers && (
            <span>
              🔄 Turnovers: {state.home_team} {state.turnovers.home || 0}
              {' / '}{state.away_team} {state.turnovers.away || 0}
            </span>
          )}
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
              onBallCarrierChange={setSelectedBallCarrier}
            />
          ) : isInteractive && isHumanOnDefense ? (
            <DefensivePlayCaller
              state={state}
              loading={loading}
              personnel={personnel}
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
              {lastPlay.personnel_note && (
                <div className="last-play-note">{lastPlay.personnel_note}</div>
              )}
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
                  {/* Don't reveal AI's offensive play call to the human defender */}
                  {lastPlay.offensive_play_call && !isHumanOnDefense && <span className="play-call-badge off-call">OFF: {lastPlay.offensive_play_call}</span>}
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
              {/* BV vs TV battle display */}
              {lastPlay.bv_tv_result && (
                <div className="bv-tv-display" style={{ fontSize: '0.8em', padding: '4px 8px', background: '#1a2a1a', borderRadius: '4px', margin: '4px 0' }}>
                  ⚔️ BV vs TV: Blocker {lastPlay.bv_tv_result.blocker_bv} vs Defender {lastPlay.bv_tv_result.defender_tv}
                  {' → '}{lastPlay.bv_tv_result.modifier >= 0 ? '+' : ''}{lastPlay.bv_tv_result.modifier} yds
                </div>
              )}
              {/* Point of Interception display */}
              {lastPlay.interception_point != null && (
                <div className="int-point-display" style={{ fontSize: '0.8em', padding: '4px 8px', background: '#2a1a1a', borderRadius: '4px', margin: '4px 0' }}>
                  📍 Interception at the {lastPlay.interception_point}-yard line
                </div>
              )}
              {/* TD/Score animation */}
              {lastPlay.is_touchdown && (
                <div className="td-animation" style={{
                  textAlign: 'center', fontSize: '1.5em', padding: '8px',
                  background: 'linear-gradient(135deg, #2d5a2d, #1a3a1a)',
                  borderRadius: '8px', margin: '4px 0',
                  animation: 'pulse 1s ease-in-out infinite',
                }}>
                  🎉🏈 TOUCHDOWN! 🏈🎉
                </div>
              )}
              {/* Penalty flag visual */}
              {lastPlay.result === 'PENALTY' && (
                <div className="penalty-flag" style={{
                  textAlign: 'center', fontSize: '1.2em', padding: '6px',
                  background: 'linear-gradient(135deg, #5a5a1a, #3a3a0a)',
                  borderRadius: '8px', margin: '4px 0',
                }}>
                  🟡 FLAG ON THE PLAY 🟡
                </div>
              )}
              {/* Debug log (collapsible) */}
              {lastPlay.debug_log && lastPlay.debug_log.length > 0 && (
                <DebugLogPanel log={lastPlay.debug_log} />
              )}
              {/* Box assignments for this play */}
              {lastPlay.box_assignments && Object.keys(lastPlay.box_assignments).length > 0 && (
                <div style={{
                  fontSize: '0.7em', padding: '4px 8px', margin: '4px 0',
                  background: '#0f172a', borderRadius: '4px', border: '1px solid #1e3a5f',
                }}>
                  <span style={{ color: '#93c5fd', fontWeight: 'bold' }}>📦 Box Assignments: </span>
                  {Object.entries(lastPlay.box_assignments)
                    .sort(([a], [b]) => a.localeCompare(b))
                    .map(([box, name]) => (
                      <span key={box} style={{ color: '#ddd', marginRight: '8px' }}>
                        {box}={name as string}
                      </span>
                    ))}
                </div>
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
              gameId={gameId}
              personnel={personnel}
              loading={loading}
              onSubstitute={onSubstitute}
              onRefreshPersonnel={onRefreshPersonnel}
            />
          )}

          <DiceRoller lastDice={lastDice} loading={loading} onRoll={onRollDice} />
          
          {/* FAC Card Display (5E mode) */}
          <FACCardDisplay lastPlay={lastPlay} />
          
          {/* Game Stats */}
          <GameStats state={state} />

          {/* Player Stats Panel */}
          {state.player_stats && Object.keys(state.player_stats).length > 0 && (
            <PlayerStatsPanel stats={state.player_stats} />
          )}
        </div>

        <div className="board-right">
          {/* Team Card Viewers — access all player cards, KR, PR, team lineup */}
          <div style={{
            display: 'flex', gap: '4px', padding: '4px 0',
            borderBottom: '1px solid #1e3a5f', marginBottom: '4px',
          }}>
            <button
              className={`btn btn-sm ${showCardViewer === state.home_team ? 'btn-primary' : 'btn-outline'}`}
              onClick={() => setShowCardViewer(showCardViewer === state.home_team ? null : state.home_team)}
              style={{ fontSize: '0.75em', padding: '2px 8px' }}
            >
              🃏 {state.home_team} Cards
            </button>
            <button
              className={`btn btn-sm ${showCardViewer === state.away_team ? 'btn-primary' : 'btn-outline'}`}
              onClick={() => setShowCardViewer(showCardViewer === state.away_team ? null : state.away_team)}
              style={{ fontSize: '0.75em', padding: '2px 8px' }}
            >
              🃏 {state.away_team} Cards
            </button>
          </div>

          {showCardViewer && <CardViewer teamAbbr={showCardViewer} />}

          {/* Letter boards for offense/defense — always visible */}
          <LetterBoards
            personnel={personnel}
            possession={state.possession}
            defenseFormation={lastPlay?.defense_formation ?? undefined}
            selectedBallCarrier={selectedBallCarrier}
            onSubstitute={onSubstitute}
          />

          {/* 5E Defensive Display Boxes (A-O) */}
          <DisplayBoxes gameId={gameId} />

          {/* Starting Lineup Cards */}
          <StartingLineup gameId={gameId} team="home" teamAbbr={state.home_team} />
          <StartingLineup gameId={gameId} team="away" teamAbbr={state.away_team} />

          {/* Depth Charts */}
          <DepthChart gameId={gameId} team="home" teamAbbr={state.home_team} />
          <DepthChart gameId={gameId} team="away" teamAbbr={state.away_team} />

          <GameLog plays={state.last_plays} />
        </div>
      </div>

      <div className="game-id-footer">Game ID: {gameId}</div>
    </div>
  );
}
