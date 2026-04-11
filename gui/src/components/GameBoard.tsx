import type { GameState, PlayResult, DriveResult } from '../types/game';
import { Scoreboard } from './Scoreboard';
import { PlayCaller } from './PlayCaller';
import { GameLog } from './GameLog';
import { DiceRoller } from './DiceRoller';
import type { DiceRollResult } from '../types/game';

interface GameBoardProps {
  gameId: string;
  state: GameState;
  lastPlay: PlayResult | null;
  lastDrive: DriveResult | null;
  lastDice: DiceRollResult | null;
  loading: boolean;
  onExecutePlay: () => void;
  onSimulateDrive: () => void;
  onSimulateGame: () => void;
  onRollDice: () => void;
  onNewGame: () => void;
}

export function GameBoard({
  gameId,
  state,
  lastPlay,
  lastDrive,
  lastDice,
  loading,
  onExecutePlay,
  onSimulateDrive,
  onSimulateGame,
  onRollDice,
  onNewGame,
}: GameBoardProps) {
  return (
    <div className="game-board">
      <div className="board-header">
        <h1 className="board-title">🏈 Statis Pro Football</h1>
        <button className="btn btn-outline btn-sm" onClick={onNewGame}>
          New Game
        </button>
      </div>

      <Scoreboard state={state} />

      <div className="board-content">
        <div className="board-left">
          <PlayCaller
            state={state}
            loading={loading}
            onExecutePlay={onExecutePlay}
            onSimulateDrive={onSimulateDrive}
            onSimulateGame={onSimulateGame}
          />

          {lastPlay && (
            <div className={`last-play-card ${lastPlay.is_touchdown ? 'play-td' : lastPlay.turnover ? 'play-turnover' : ''}`}>
              <div className="last-play-label">Last Play</div>
              <div className="last-play-desc">{lastPlay.description}</div>
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

          <DiceRoller lastDice={lastDice} loading={loading} onRoll={onRollDice} />
        </div>

        <div className="board-right">
          <GameLog plays={state.last_plays} />
        </div>
      </div>

      <div className="game-id-footer">Game ID: {gameId}</div>
    </div>
  );
}
