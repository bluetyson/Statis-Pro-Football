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
import type { DiceRollResult } from '../types/game';

function formatDefenseFormation(formation?: string | null): string {
  if (!formation) return '';
  return formation.replace(/_/g, ' ');
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
  onDownloadGameLog,
  onNewGame,
}: GameBoardProps) {
  const isInteractive = gameMode !== 'solitaire';

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

      {/* Gridiron field display */}
      <Gridiron state={state} />

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
              <div className="last-play-meta">
                <span>{lastPlay.play_type}</span>
                <span>{lastPlay.yards >= 0 ? '+' : ''}{lastPlay.yards} yds</span>
                <span className="play-result-badge">{lastPlay.result}</span>
              </div>
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
