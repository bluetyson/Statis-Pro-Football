import { useState, useEffect } from 'react';
import axios from 'axios';
import type { PlayerBrief } from '../types/game';

const API_BASE = '/api';

interface DepthChartProps {
  gameId: string;
  team: 'home' | 'away';
  teamAbbr: string;
}

interface DepthChartData {
  team: string;
  team_name: string;
  depth_chart: Record<string, PlayerBrief[]>;
}

const POSITION_ORDER = ['QB', 'RB', 'WR', 'TE', 'OL', 'K', 'P', 'DL', 'LB', 'DB'];
const POSITION_COLORS: Record<string, string> = {
  QB: '#3b82f6',
  RB: '#22c55e',
  WR: '#8b5cf6',
  TE: '#06b6d4',
  OL: '#6b7280',
  K: '#f59e0b',
  P: '#f59e0b',
  DL: '#ef4444',
  LB: '#f97316',
  DB: '#ec4899',
};

/**
 * Depth Chart component — shows full positional depth for a team.
 * Displays starters (index 0) and all backups with their ratings.
 */
export function DepthChart({ gameId, team, teamAbbr }: DepthChartProps) {
  const [data, setData] = useState<DepthChartData | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const fetchData = () => {
    if (!gameId) return;
    setLoading(true);
    axios
      .get(`${API_BASE}/games/${gameId}/depth-chart?team=${team}`)
      .then((res) => setData(res.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (isOpen && gameId) fetchData();
  }, [isOpen, gameId]);

  return (
    <div style={{
      background: '#0f172a',
      borderRadius: '8px',
      padding: '6px 10px',
      margin: '4px 0',
      border: '1px solid #1e3a5f',
    }}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          background: 'none',
          border: 'none',
          color: '#93c5fd',
          cursor: 'pointer',
          fontSize: '0.85em',
          fontWeight: 'bold',
          padding: '2px 0',
          width: '100%',
          textAlign: 'left',
        }}
      >
        📊 {isOpen ? 'Hide' : 'Show'} {teamAbbr} Depth Chart ({team === 'home' ? '🏠' : '✈️'})
      </button>

      {isOpen && loading && (
        <div style={{ fontSize: '0.75em', color: '#888', padding: '8px' }}>Loading...</div>
      )}

      {isOpen && data && (
        <div style={{ padding: '4px 0' }}>
          <div style={{ fontSize: '0.8em', color: '#fff', fontWeight: 'bold', marginBottom: '6px' }}>
            {data.team_name} — Full Depth Chart
          </div>

          {POSITION_ORDER.map((pos) => {
            const players = data.depth_chart[pos];
            if (!players || players.length === 0) return null;

            return (
              <div key={pos} style={{ marginBottom: '6px' }}>
                <div style={{
                  fontSize: '0.7em',
                  color: POSITION_COLORS[pos] ?? '#888',
                  fontWeight: 'bold',
                  textTransform: 'uppercase',
                  marginBottom: '1px',
                  borderBottom: `1px solid ${POSITION_COLORS[pos] ?? '#333'}33`,
                  paddingBottom: '1px',
                }}>
                  {pos} ({players.length})
                </div>
                {players.map((p, i) => (
                  <div
                    key={p.name}
                    style={{
                      display: 'flex',
                      gap: '6px',
                      alignItems: 'center',
                      padding: '1px 4px',
                      background: i === 0 ? '#1e293b' : 'transparent',
                      borderRadius: '3px',
                      borderLeft: i === 0 ? `2px solid ${POSITION_COLORS[pos] ?? '#888'}` : '2px solid transparent',
                    }}
                  >
                    <span style={{
                      fontSize: '0.6em',
                      color: i === 0 ? '#22c55e' : '#4b5563',
                      minWidth: '14px',
                      fontWeight: 'bold',
                    }}>
                      {i === 0 ? '★' : `${i + 1}`}
                    </span>
                    <span style={{ fontSize: '0.6em', color: '#6b7280' }}>#{p.number}</span>
                    <span style={{ fontSize: '0.7em', color: i === 0 ? '#fff' : '#9ca3af', flex: 1 }}>
                      {p.name}
                    </span>
                    <span style={{ fontSize: '0.6em', color: '#6b7280' }}>{p.position}</span>
                    <span style={{
                      fontSize: '0.6em',
                      fontWeight: 'bold',
                      color: p.overall_grade.startsWith('A') ? '#22c55e' :
                             p.overall_grade === 'B' ? '#3b82f6' :
                             p.overall_grade === 'C' ? '#f59e0b' : '#ef4444',
                    }}>
                      {p.overall_grade}
                    </span>
                    {p.injured && <span style={{ fontSize: '0.6em' }}>🏥</span>}
                  </div>
                ))}
              </div>
            );
          })}

          <button
            onClick={fetchData}
            disabled={loading}
            style={{
              marginTop: '4px',
              background: '#1e293b',
              border: '1px solid #374151',
              color: '#93c5fd',
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '0.7em',
              cursor: 'pointer',
            }}
          >
            🔄 Refresh
          </button>
        </div>
      )}
    </div>
  );
}
