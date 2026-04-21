import { useState } from 'react';
import { useGameEngine } from './hooks/useGameEngine';
import { TeamSelector } from './components/TeamSelector';
import { GameBoard } from './components/GameBoard';
import { CardViewer } from './components/CardViewer';
import type { GamePhase, GameMode } from './types/game';
import './styles/index.css';

export default function App() {
  const {
    gameId,
    gameState,
    gameMode,
    lastPlay,
    lastDrive,
    personnel,
    significantEvents,
    loading,
    error,
    startGame,
    executePlay,
    executeHumanPlay,
    executeHumanDefense,
    simulateDrive,
    simulateGame,
    substitutePlayer,
    callTimeout,
    executeFakePunt,
    executeFakeFG,
    executeCoffinCorner,
    executeOnsideKick,
    executeSquibKick,
    executePATKick,
    executeTwoPointConversion,
    activateBigPlayDefense,
    declareTwoMinuteOffense,
    downloadGameLog,
    resetError,
    isHumanTurn,
    isHumanOnDefense,
    fetchPersonnel,
  } = useGameEngine();

  const [phase, setPhase] = useState<GamePhase>('setup');
  const [activeTab, setActiveTab] = useState<'game' | 'cards'>('game');
  const [cardTeam, setCardTeam] = useState('KC');

  const handleStartGame = async (homeTeam: string, awayTeam: string, mode: GameMode, seed?: number) => {
    await startGame(homeTeam, awayTeam, mode, seed);
    setPhase('playing');
    setCardTeam(homeTeam);
  };

  const handleNewGame = () => {
    setPhase('setup');
    resetError();
  };

  return (
    <div className="app">
      <nav className="app-nav">
        <span className="nav-logo">🏈 Statis Pro Football</span>
        <div className="nav-tabs">
          <button
            className={`nav-tab ${activeTab === 'game' ? 'active' : ''}`}
            onClick={() => setActiveTab('game')}
          >
            Game
          </button>
          <button
            className={`nav-tab ${activeTab === 'cards' ? 'active' : ''}`}
            onClick={() => setActiveTab('cards')}
          >
            Cards
          </button>
        </div>
      </nav>

      {error && (
        <div className="error-banner">
          <span>⚠ {error}</span>
          <button onClick={resetError} className="error-dismiss">✕</button>
        </div>
      )}

      <main className="app-main">
        {activeTab === 'game' && (
          <>
            {phase === 'setup' && (
              <TeamSelector onStartGame={handleStartGame} loading={loading} />
            )}
            {phase === 'playing' && gameId && gameState && (
              <GameBoard
                gameId={gameId}
                state={gameState}
                gameMode={gameMode}
                lastPlay={lastPlay}
                lastDrive={lastDrive}
                lastDice={null}
                personnel={personnel}
                significantEvents={significantEvents}
                loading={loading}
                isHumanTurn={isHumanTurn()}
                isHumanOnDefense={isHumanOnDefense()}
                onExecutePlay={executePlay}
                onExecuteHumanPlay={executeHumanPlay}
                onExecuteHumanDefense={executeHumanDefense}
                onSimulateDrive={simulateDrive}
                onSimulateGame={simulateGame}
                onRollDice={() => Promise.resolve()}
                onSubstitute={substitutePlayer}
                onCallTimeout={callTimeout}
                onFakePunt={executeFakePunt}
                onFakeFG={executeFakeFG}
                onCoffinCorner={executeCoffinCorner}
                onOnsideKick={executeOnsideKick}
                onSquibKick={executeSquibKick}
                onPATKick={executePATKick}
                onTwoPointConversion={executeTwoPointConversion}
                onBigPlayDefense={activateBigPlayDefense}
                onTwoMinuteOffense={declareTwoMinuteOffense}
                onDownloadGameLog={downloadGameLog}
                onNewGame={handleNewGame}
                onRefreshPersonnel={fetchPersonnel}
              />
            )}
          </>
        )}

        {activeTab === 'cards' && (
          <div className="cards-tab">
            <div className="cards-team-select">
              <label>Team: </label>
              <select value={cardTeam} onChange={(e) => setCardTeam(e.target.value)}>
                {['ARI','ATL','BAL','BUF','CAR','CHI','CIN','CLE',
                  'DAL','DEN','DET','GB','HOU','IND','JAX','KC',
                  'LAC','LAR','LV','MIA','MIN','NE','NO','NYG',
                  'NYJ','PHI','PIT','SF','SEA','TB','TEN','WSH'].map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
            <CardViewer teamAbbr={cardTeam} />
          </div>
        )}
      </main>
    </div>
  );
}
