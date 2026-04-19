import { useState, useCallback, useRef } from 'react';
import axios from 'axios';
import type {
  GameState,
  PlayResult,
  DriveResult,
  PersonnelData,
  HumanPlayCall,
  DefensivePlayCall,
  GameMode,
} from '../types/game';

const API_BASE = '/api';

const MAX_SIGNIFICANT_EVENTS = 20;

export interface SignificantEvent {
  id: number;
  icon: string;
  text: string;
  kind: 'injury' | 'touchdown' | 'turnover' | 'first_down' | 'score';
}

interface UseGameEngineReturn {
  gameId: string | null;
  gameState: GameState | null;
  gameMode: GameMode;
  lastPlay: PlayResult | null;
  lastDrive: DriveResult | null;
  lastDice: null;
  personnel: PersonnelData | null;
  significantEvents: SignificantEvent[];
  loading: boolean;
  error: string | null;
  startGame: (homeTeam: string, awayTeam: string, mode: GameMode, seed?: number) => Promise<void>;
  executePlay: () => Promise<void>;
  executeHumanPlay: (call: HumanPlayCall) => Promise<void>;
  executeHumanDefense: (call: DefensivePlayCall) => Promise<void>;
  simulateDrive: () => Promise<void>;
  simulateGame: () => Promise<void>;
  fetchPersonnel: () => Promise<void>;
  substitutePlayer: (position: string, playerOut: string, playerIn: string) => Promise<void>;
  callTimeout: (team?: string) => Promise<void>;
  executeFakePunt: () => Promise<void>;
  executeFakeFG: () => Promise<void>;
  executeCoffinCorner: (deduction: number) => Promise<void>;
  executeOnsideKick: (onsideDefense?: boolean) => Promise<void>;
  executeSquibKick: () => Promise<void>;
  executeTwoPointConversion: (playType: string) => Promise<void>;
  activateBigPlayDefense: () => Promise<void>;
  declareTwoMinuteOffense: () => Promise<void>;
  downloadGameLog: () => void;
  resetError: () => void;
  isHumanTurn: () => boolean;
  isHumanOnDefense: () => boolean;
}

export function useGameEngine(): UseGameEngineReturn {
  const [gameId, setGameId] = useState<string | null>(null);
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [gameMode, setGameMode] = useState<GameMode>('solitaire');
  const [lastPlay, setLastPlay] = useState<PlayResult | null>(null);
  const [lastDrive, setLastDrive] = useState<DriveResult | null>(null);
  const [personnel, setPersonnel] = useState<PersonnelData | null>(null);
  const [significantEvents, setSignificantEvents] = useState<SignificantEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const eventIdRef = useRef(0);

  const addSignificantEvents = useCallback(
    (play: PlayResult, state: GameState) => {
      const newEvents: SignificantEvent[] = [];
      const nextId = () => ++eventIdRef.current;

      if (play.injury_player) {
        newEvents.push({
          id: nextId(),
          icon: '🏥',
          kind: 'injury',
          text: `${play.injury_player} INJURED — out for ${play.injury_duration ?? '?'} plays (auto-subbed)`,
        });
      }
      if (play.is_touchdown) {
        const scorer = play.rusher ?? play.receiver ?? play.passer ?? '?';
        newEvents.push({
          id: nextId(),
          icon: '🎉',
          kind: 'touchdown',
          text: `TOUCHDOWN by ${scorer}! ${state.home_team} ${state.score.home} – ${state.away_team} ${state.score.away}`,
        });
      } else if (play.result === 'FG_GOOD') {
        newEvents.push({
          id: nextId(),
          icon: '🥅',
          kind: 'score',
          text: `FIELD GOAL! ${state.home_team} ${state.score.home} – ${state.away_team} ${state.score.away}`,
        });
      }
      if (play.turnover) {
        const type = play.result === 'INT' ? 'Interception' : 'Fumble';
        newEvents.push({
          id: nextId(),
          icon: '🔄',
          kind: 'turnover',
          text: `TURNOVER — ${type}!`,
        });
      }
      // First down: yards >= distance means the play achieved a first down
      // We detect it indirectly via the state (down reset to 1 on a new series).
      // Instead, flag if a run/pass resulted in a gain that wasn't a TD/turnover.
      if (
        !play.is_touchdown &&
        !play.turnover &&
        play.result === 'FIRST_DOWN'
      ) {
        const carrier = play.rusher ?? play.receiver ?? '?';
        newEvents.push({
          id: nextId(),
          icon: '📋',
          kind: 'first_down',
          text: `FIRST DOWN — ${carrier} (${play.yards >= 0 ? '+' : ''}${play.yards} yds)`,
        });
      }

      if (newEvents.length > 0) {
        setSignificantEvents((prev) =>
          [...newEvents, ...prev].slice(0, MAX_SIGNIFICANT_EVENTS)
        );
      }
    },
    [],
  );

  const handleError = (err: unknown) => {
    if (axios.isAxiosError(err)) {
      setError(err.response?.data?.detail ?? err.message);
    } else if (err instanceof Error) {
      setError(err.message);
    } else {
      setError('An unknown error occurred');
    }
  };

  const startGame = useCallback(async (homeTeam: string, awayTeam: string, mode: GameMode, seed?: number) => {
    setLoading(true);
    setError(null);
    try {
      const solHome = mode !== 'human_home';
      const solAway = mode !== 'human_away';
      const payload: Record<string, unknown> = {
        home_team: homeTeam,
        away_team: awayTeam,
        solitaire_home: solHome,
        solitaire_away: solAway,
      };
      if (seed !== undefined) payload.seed = seed;
      const res = await axios.post(`${API_BASE}/games/new`, payload);
      setGameId(res.data.game_id);
      setGameState(res.data.state);
      setGameMode(mode);
      setLastPlay(null);
      setLastDrive(null);
      setPersonnel(null);
      setSignificantEvents([]);

      // Fetch initial personnel
      try {
        const pRes = await axios.get(`${API_BASE}/games/${res.data.game_id}/personnel`);
        setPersonnel(pRes.data);
      } catch { /* personnel fetch is optional */ }
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
      addSignificantEvents(res.data.play_result, res.data.state);
      // Refresh personnel after play
      try {
        const pRes = await axios.get(`${API_BASE}/games/${gameId}/personnel`);
        setPersonnel(pRes.data);
      } catch { /* ok */ }
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }, [gameId, gameMode, addSignificantEvents]);

  const executeHumanPlay = useCallback(async (call: HumanPlayCall) => {
    if (!gameId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post(`${API_BASE}/games/${gameId}/human-play`, call);
      setLastPlay(res.data.play_result);
      setGameState(res.data.state);
      addSignificantEvents(res.data.play_result, res.data.state);
      // Refresh personnel after play
      try {
        const pRes = await axios.get(`${API_BASE}/games/${gameId}/personnel`);
        setPersonnel(pRes.data);
      } catch { /* ok */ }
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }, [gameId, addSignificantEvents]);

  const executeHumanDefense = useCallback(async (call: DefensivePlayCall) => {
    if (!gameId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post(`${API_BASE}/games/${gameId}/human-defense`, call);
      setLastPlay(res.data.play_result);
      setGameState(res.data.state);
      addSignificantEvents(res.data.play_result, res.data.state);
      // Refresh personnel after play
      try {
        const pRes = await axios.get(`${API_BASE}/games/${gameId}/personnel`);
        setPersonnel(pRes.data);
      } catch { /* ok */ }
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }, [gameId, addSignificantEvents]);

  const simulateDrive = useCallback(async () => {
    if (!gameId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post(`${API_BASE}/games/${gameId}/simulate-drive`);
      setLastDrive(res.data.drive);
      setGameState(res.data.state);
      try {
        const pRes = await axios.get(`${API_BASE}/games/${gameId}/personnel`);
        setPersonnel(pRes.data);
      } catch { /* ok */ }
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }, [gameId, gameMode]);

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

  const fetchPersonnel = useCallback(async () => {
    if (!gameId) return;
    try {
      const res = await axios.get(`${API_BASE}/games/${gameId}/personnel`);
      setPersonnel(res.data);
    } catch (err) {
      handleError(err);
    }
  }, [gameId]);

  const substitutePlayer = useCallback(async (position: string, playerOut: string, playerIn: string) => {
    if (!gameId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post(`${API_BASE}/games/${gameId}/substitute`, {
        position,
        player_out: playerOut,
        player_in: playerIn,
      });
      setGameState(res.data.state);
      // Refresh personnel
      try {
        const pRes = await axios.get(`${API_BASE}/games/${gameId}/personnel`);
        setPersonnel(pRes.data);
      } catch { /* ok */ }
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }, [gameId]);

  const downloadGameLog = useCallback(() => {
    if (!gameId) return;
    window.open(`${API_BASE}/games/${gameId}/gamelog/download`, '_blank');
  }, [gameId]);

  const isHumanTurn = useCallback(() => {
    if (!gameState || gameMode === 'solitaire') return false;
    if (gameMode === 'human_home') return gameState.possession === 'home';
    if (gameMode === 'human_away') return gameState.possession === 'away';
    return false;
  }, [gameState, gameMode]);

  const isHumanOnDefense = useCallback(() => {
    if (!gameState || gameMode === 'solitaire') return false;
    if (gameMode === 'human_home') return gameState.possession === 'away';
    if (gameMode === 'human_away') return gameState.possession === 'home';
    return false;
  }, [gameState, gameMode]);

  const resetError = useCallback(() => setError(null), []);

  const callTimeout = useCallback(async (team?: string) => {
    if (!gameId) return;
    setLoading(true);
    setError(null);
    try {
      const params = team ? `?team=${team}` : '';
      const res = await axios.post(`${API_BASE}/games/${gameId}/timeout${params}`);
      setGameState(res.data.state);
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }, [gameId]);

  const executeFakePunt = useCallback(async () => {
    if (!gameId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post(`${API_BASE}/games/${gameId}/fake-punt`);
      setLastPlay(res.data.play_result);
      setGameState(res.data.state);
      addSignificantEvents(res.data.play_result, res.data.state);
      try {
        const pRes = await axios.get(`${API_BASE}/games/${gameId}/personnel`);
        setPersonnel(pRes.data);
      } catch { /* ok */ }
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }, [gameId, addSignificantEvents]);

  const executeFakeFG = useCallback(async () => {
    if (!gameId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post(`${API_BASE}/games/${gameId}/fake-fg`);
      setLastPlay(res.data.play_result);
      setGameState(res.data.state);
      addSignificantEvents(res.data.play_result, res.data.state);
      try {
        const pRes = await axios.get(`${API_BASE}/games/${gameId}/personnel`);
        setPersonnel(pRes.data);
      } catch { /* ok */ }
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }, [gameId, addSignificantEvents]);

  const executeCoffinCorner = useCallback(async (deduction: number) => {
    if (!gameId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post(`${API_BASE}/games/${gameId}/coffin-corner`, { deduction });
      setLastPlay(res.data.play_result);
      setGameState(res.data.state);
      addSignificantEvents(res.data.play_result, res.data.state);
      try {
        const pRes = await axios.get(`${API_BASE}/games/${gameId}/personnel`);
        setPersonnel(pRes.data);
      } catch { /* ok */ }
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }, [gameId, addSignificantEvents]);

  const executeOnsideKick = useCallback(async (onsideDefense: boolean = false) => {
    if (!gameId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post(`${API_BASE}/games/${gameId}/onside-kick`, { onside_defense: onsideDefense });
      setLastPlay(res.data.play_result);
      setGameState(res.data.state);
      addSignificantEvents(res.data.play_result, res.data.state);
      try {
        const pRes = await axios.get(`${API_BASE}/games/${gameId}/personnel`);
        setPersonnel(pRes.data);
      } catch { /* ok */ }
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }, [gameId, addSignificantEvents]);

  const executeSquibKick = useCallback(async () => {
    if (!gameId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post(`${API_BASE}/games/${gameId}/squib-kick`);
      setLastPlay(res.data.play_result);
      setGameState(res.data.state);
      addSignificantEvents(res.data.play_result, res.data.state);
      try {
        const pRes = await axios.get(`${API_BASE}/games/${gameId}/personnel`);
        setPersonnel(pRes.data);
      } catch { /* ok */ }
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }, [gameId, addSignificantEvents]);

  const executeTwoPointConversion = useCallback(async (playType: string) => {
    if (!gameId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post(`${API_BASE}/games/${gameId}/two-point-conversion`, {
        play_type: playType,
        direction: 'MIDDLE',
      });
      setLastPlay(res.data.play_result);
      setGameState(res.data.state);
      addSignificantEvents(res.data.play_result, res.data.state);
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }, [gameId, addSignificantEvents]);

  const activateBigPlayDefense = useCallback(async () => {
    if (!gameId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post(`${API_BASE}/games/${gameId}/big-play-defense`, {
        team: 'defense',
      });
      setGameState(res.data.state);
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }, [gameId]);

  const declareTwoMinuteOffense = useCallback(async () => {
    if (!gameId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post(`${API_BASE}/games/${gameId}/two-minute-offense`);
      setGameState(res.data.state);
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }, [gameId]);

  return {
    gameId,
    gameState,
    gameMode,
    lastPlay,
    lastDrive,
    lastDice: null,
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
    fetchPersonnel,
    substitutePlayer,
    callTimeout,
    executeFakePunt,
    executeFakeFG,
    executeCoffinCorner,
    executeOnsideKick,
    executeSquibKick,
    executeTwoPointConversion,
    activateBigPlayDefense,
    declareTwoMinuteOffense,
    downloadGameLog,
    resetError,
    isHumanTurn,
    isHumanOnDefense,
  };
}
