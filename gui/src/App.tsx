import { useState } from 'react';
import { useGameEngine } from './hooks/useGameEngine';
import { TeamSelector } from './components/TeamSelector';
import { GameBoard } from './components/GameBoard';
import { CardViewer } from './components/CardViewer';
import type { GamePhase } from './types/game';
import './styles/index.css';

export default function App() {
  const {
    gameId,
    gameState,
    lastPlay,
    lastDrive,
    lastDice,
    loading,
    error,
    startGame,
    executePlay,
    simulateDrive,
    simulateGame,
    rollDice,
    resetError,
  } = useGameEngine();

  const [phase, setPhase] = useState<GamePhase>('setup');
  const [activeTab, setActiveTab] = useState<'game' | 'cards'>('game');
  const [cardTeam, setCardTeam] = useState('KC');

  const handleStartGame = async (homeTeam: string, awayTeam: string) => {
    await startGame(homeTeam, awayTeam);
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
                lastPlay={lastPlay}
                lastDrive={lastDrive}
                lastDice={lastDice}
                loading={loading}
                onExecutePlay={executePlay}
                onSimulateDrive={simulateDrive}
                onSimulateGame={simulateGame}
                onRollDice={rollDice}
                onNewGame={handleNewGame}
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
                  'NYJ','PHI','PIT','SF','SEA','TB','TEN','WAS'].map((t) => (
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
