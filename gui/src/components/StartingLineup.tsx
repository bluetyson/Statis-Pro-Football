import { useState, useEffect } from 'react';
import axios from 'axios';
import type { PlayerBrief } from '../types/game';

const API_BASE = '/api';

interface StartingLineupProps {
  gameId: string;
  team: 'home' | 'away';
  teamAbbr: string;
}

interface LineupData {
  team: string;
  team_name: string;
  record: { wins: number; losses: number; ties: number };
  offense: Record<string, PlayerBrief | null>;
  offensive_line: PlayerBrief[];
  defense: PlayerBrief[];
  returners: { KR: PlayerBrief | null; PR: PlayerBrief | null };
}

function formatRecord(r: { wins: number; losses: number; ties: number }) {
  return `${r.wins}-${r.losses}${r.ties ? `-${r.ties}` : ''}`;
}

function PlayerSlot({ label, player }: { label: string; player: PlayerBrief | null }) {
  if (!player) return (
    <div style={{ display: 'flex', gap: '6px', alignItems: 'center', padding: '2px 0', opacity: 0.5 }}>
      <span style={{ fontSize: '0.7em', color: '#888', minWidth: '30px' }}>{label}</span>
      <span style={{ fontSize: '0.7em', color: '#666' }}>—</span>
    </div>
  );

  return (
    <div style={{
      display: 'flex', gap: '6px', alignItems: 'center', padding: '2px 0',
      borderBottom: '1px solid #1e293b',
    }}>
      <span style={{ fontSize: '0.7em', color: '#93c5fd', minWidth: '30px', fontWeight: 'bold' }}>
        {label}
      </span>
      <span style={{ fontSize: '0.65em', color: '#888' }}>#{player.number}</span>
      <span style={{ fontSize: '0.75em', color: '#ddd', flex: 1 }}>{player.name}</span>
      <span style={{
        fontSize: '0.65em',
        color: player.overall_grade.startsWith('A') ? '#22c55e' :
               player.overall_grade === 'B' ? '#3b82f6' :
               player.overall_grade === 'C' ? '#f59e0b' : '#ef4444',
        fontWeight: 'bold',
      }}>
        {player.overall_grade}
      </span>
      {player.injured && <span style={{ fontSize: '0.7em' }}>🏥</span>}
    </div>
  );
}

/**
 * Starting Lineup component — shows the full starting 11 on offense/defense
 * with team card format per 5E rules.
 */
export function StartingLineup({ gameId, team, teamAbbr }: StartingLineupProps) {
  const [lineup, setLineup] = useState<LineupData | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const fetchLineup = () => {
    if (!gameId) return;
    setLoading(true);
    axios
      .get(`${API_BASE}/games/${gameId}/starting-lineup?team=${team}`)
      .then((res) => setLineup(res.data))
      .catch(() => setLineup(null))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (isOpen && gameId) fetchLineup();
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
        📋 {isOpen ? 'Hide' : 'Show'} {teamAbbr} Starting Lineup ({team === 'home' ? '🏠' : '✈️'})
      </button>

      {isOpen && loading && (
        <div style={{ fontSize: '0.75em', color: '#888', padding: '8px' }}>Loading...</div>
      )}

      {isOpen && lineup && (
        <div style={{ padding: '4px 0' }}>
          {/* Team header */}
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '4px 0', borderBottom: '1px solid #1e3a5f', marginBottom: '6px',
          }}>
            <span style={{ fontSize: '0.9em', color: '#fff', fontWeight: 'bold' }}>
              {lineup.team_name}
            </span>
            <span style={{ fontSize: '0.75em', color: '#93c5fd' }}>
              {formatRecord(lineup.record)}
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
            {/* Offense */}
            <div>
              <div style={{ fontSize: '0.7em', color: '#22c55e', fontWeight: 'bold', marginBottom: '2px', textTransform: 'uppercase' }}>
                🏈 Offense
              </div>
              {Object.entries(lineup.offense).map(([pos, player]) => (
                <PlayerSlot key={pos} label={pos} player={player} />
              ))}
              <div style={{ fontSize: '0.65em', color: '#888', margin: '4px 0 2px', textTransform: 'uppercase' }}>
                Offensive Line
              </div>
              {lineup.offensive_line.map((p, i) => (
                <PlayerSlot key={i} label={p.position} player={p} />
              ))}
            </div>

            {/* Defense */}
            <div>
              <div style={{ fontSize: '0.7em', color: '#ef4444', fontWeight: 'bold', marginBottom: '2px', textTransform: 'uppercase' }}>
                🛡️ Defense (11 Starters)
              </div>
              {lineup.defense.map((p, i) => (
                <PlayerSlot key={i} label={`${p.position}${i + 1}`} player={p} />
              ))}
            </div>
          </div>

          {/* Returners */}
          {lineup.returners && (lineup.returners.KR || lineup.returners.PR) && (
            <div style={{ marginTop: '6px', borderTop: '1px solid #1e3a5f', paddingTop: '4px' }}>
              <div style={{ fontSize: '0.65em', color: '#888', textTransform: 'uppercase', marginBottom: '2px' }}>
                🏈 Return Specialists
              </div>
              {lineup.returners.KR && <PlayerSlot label="KR" player={lineup.returners.KR} />}
              {lineup.returners.PR && <PlayerSlot label="PR" player={lineup.returners.PR} />}
            </div>
          )}

          {/* Refresh */}
          <button
            onClick={fetchLineup}
            disabled={loading}
            style={{
              marginTop: '6px',
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
