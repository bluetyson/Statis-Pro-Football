import { useState, useCallback } from 'react';
import axios from 'axios';
import type { GameState, PlayResult, DriveResult, DiceRollResult } from '../types/game';

const API_BASE = '/api';

interface UseGameEngineReturn {
  gameId: string | null;
  gameState: GameState | null;
  lastPlay: PlayResult | null;
  lastDrive: DriveResult | null;
  lastDice: DiceRollResult | null;
  loading: boolean;
  error: string | null;
  startGame: (homeTeam: string, awayTeam: string) => Promise<void>;
  executePlay: () => Promise<void>;
  simulateDrive: () => Promise<void>;
  simulateGame: () => Promise<void>;
  rollDice: () => Promise<void>;
  resetError: () => void;
}

export function useGameEngine(): UseGameEngineReturn {
  const [gameId, setGameId] = useState<string | null>(null);
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [lastPlay, setLastPlay] = useState<PlayResult | null>(null);
  const [lastDrive, setLastDrive] = useState<DriveResult | null>(null);
  const [lastDice, setLastDice] = useState<DiceRollResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleError = (err: unknown) => {
    if (axios.isAxiosError(err)) {
      setError(err.response?.data?.detail ?? err.message);
    } else if (err instanceof Error) {
      setError(err.message);
    } else {
      setError('An unknown error occurred');
    }
  };

  const startGame = useCallback(async (homeTeam: string, awayTeam: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post(`${API_BASE}/games/new`, {
        home_team: homeTeam,
        away_team: awayTeam,
        solitaire_home: true,
        solitaire_away: true,
      });
      setGameId(res.data.game_id);
      setGameState(res.data.state);
      setLastPlay(null);
      setLastDrive(null);
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  const executePlay = useCallback(async () => {
    if (!gameId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post(`${API_BASE}/games/${gameId}/play`);
      setLastPlay(res.data.play_result);
      setGameState(res.data.state);
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }, [gameId]);

  const simulateDrive = useCallback(async () => {
    if (!gameId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post(`${API_BASE}/games/${gameId}/simulate-drive`);
      setLastDrive(res.data.drive);
      setGameState(res.data.state);
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }, [gameId]);

  const simulateGame = useCallback(async () => {
    if (!gameId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post(`${API_BASE}/games/${gameId}/simulate`);
      setGameState(res.data.state);
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }, [gameId]);

  const rollDice = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post(`${API_BASE}/dice/roll`);
      setLastDice(res.data);
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  const resetError = useCallback(() => setError(null), []);

  return {
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
  };
}
