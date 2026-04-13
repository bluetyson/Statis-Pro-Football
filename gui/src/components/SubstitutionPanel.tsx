import { useState } from 'react';
import axios from 'axios';
import type { PersonnelData, PlayerBrief } from '../types/game';

const API_BASE = '/api';

interface SubstitutionPanelProps {
  gameId: string;
  personnel: PersonnelData | null;
  loading: boolean;
  onSubstitute: (position: string, playerOut: string, playerIn: string) => void;
}

const POSITIONS = ['QB', 'RB', 'WR', 'TE', 'K', 'P', 'DL', 'LB', 'DB'];

const COMPATIBLE_POSITIONS: Record<string, string[]> = {
  DE: ['DT', 'DL', 'NT', 'LB', 'OLB'],
  DT: ['DE', 'DL', 'NT'],
  DL: ['DE', 'DT', 'NT'],
  NT: ['DT', 'DL', 'DE'],
  LB: ['OLB', 'ILB', 'MLB', 'DE'],
  OLB: ['LB', 'ILB', 'MLB', 'DE'],
  ILB: ['LB', 'OLB', 'MLB'],
  MLB: ['LB', 'OLB', 'ILB'],
  CB: ['S', 'SS', 'FS', 'DB'],
  S: ['SS', 'FS', 'CB', 'DB'],
  SS: ['S', 'FS', 'CB', 'DB'],
  FS: ['S', 'SS', 'CB', 'DB'],
  DB: ['CB', 'S', 'SS', 'FS'],
  RB: ['WR', 'TE'],
  WR: ['RB', 'TE'],
  TE: ['WR', 'RB'],
};

export function SubstitutionPanel({ gameId, personnel, loading, onSubstitute }: SubstitutionPanelProps) {
  const [selectedPos, setSelectedPos] = useState<string>('QB');
  const [isOpen, setIsOpen] = useState(false);
  const [posChangePlayer, setPosChangePlayer] = useState<string>('');
  const [posChangeTarget, setPosChangeTarget] = useState<string>('');
  const [posChangeMsg, setPosChangeMsg] = useState<string>('');

  if (!personnel) return null;

  const DEF_POSITIONS = new Set(['DL', 'LB', 'DB', 'DE', 'DT', 'NT', 'CB', 'S', 'SS', 'FS', 'OLB', 'ILB', 'MLB']);
  const isDefPos = DEF_POSITIONS.has(selectedPos);
  const allPlayers = isDefPos ? personnel.defense_all : personnel.offense_all;

  // Map the UI position groups to actual position values
  const posGroupMap: Record<string, string[]> = {
    'DL': ['DE', 'DT', 'DL', 'NT'],
    'LB': ['LB', 'OLB', 'ILB', 'MLB'],
    'DB': ['CB', 'S', 'SS', 'FS', 'DB'],
  };
  const posMatch = posGroupMap[selectedPos] ?? [selectedPos];
  const posPlayers = allPlayers.filter(
    (p) => posMatch.includes(p.position.toUpperCase()),
  );

  const starter = isDefPos
    ? posPlayers.length > 0 ? posPlayers[0] : null
    : personnel.offense_starters[selectedPos] ?? null;

  const handleSub = (benchPlayer: PlayerBrief) => {
    if (!starter) return;
    onSubstitute(selectedPos, starter.name, benchPlayer.name);
  };

  const handlePositionChange = async () => {
    if (!posChangePlayer || !posChangeTarget || !gameId) return;
    setPosChangeMsg('');
    try {
      const res = await axios.post(`${API_BASE}/games/${gameId}/position-change`, {
        player_name: posChangePlayer,
        new_position: posChangeTarget,
      });
      setPosChangeMsg(`✅ ${res.data.message}`);
      setPosChangePlayer('');
      setPosChangeTarget('');
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        setPosChangeMsg(`❌ ${err.response?.data?.detail ?? err.message}`);
      } else {
        setPosChangeMsg(`❌ ${err instanceof Error ? err.message : 'An unknown error occurred'}`);
      }
    }
  };

  // Get compatible positions for the selected player
  const selectedPlayerPos = allPlayers.find(p => p.name === posChangePlayer)?.position?.toUpperCase() ?? '';
  const compatiblePositions = COMPATIBLE_POSITIONS[selectedPlayerPos] ?? [];

  return (
    <div className="substitution-panel">
      <button
        className="sub-toggle-btn"
        onClick={() => setIsOpen(!isOpen)}
      >
        🔄 {isOpen ? 'Hide' : 'Show'} Substitutions & Position Changes
      </button>

      {isOpen && (
        <div className="sub-content">
          <div className="sub-pos-tabs">
            {POSITIONS.map((pos) => (
              <button
                key={pos}
                className={`sub-pos-tab ${selectedPos === pos ? 'active' : ''}`}
                onClick={() => setSelectedPos(pos)}
              >
                {pos}
              </button>
            ))}
          </div>

          <div className="sub-starter">
            <span className="sub-label">Starter:</span>
            {starter ? (
              <span className="sub-player-name">
                #{starter.number} {starter.name} ({starter.overall_grade})
              </span>
            ) : (
              <span className="sub-empty">None</span>
            )}
          </div>

          <div className="sub-bench">
            <span className="sub-label">Available:</span>
            <div className="sub-bench-list">
              {posPlayers
                .filter((p) => p.name !== starter?.name)
                .map((p, i) => (
                  <button
                    key={i}
                    className="sub-bench-btn"
                    onClick={() => handleSub(p)}
                    disabled={loading}
                    title={`Sub in ${p.name}`}
                  >
                    <span className="sub-num">#{p.number}</span>
                    <span className="sub-name">{p.name}</span>
                    <span className="sub-grade">{p.overall_grade}</span>
                    <span className="sub-arrow">↑</span>
                  </button>
                ))}
              {posPlayers.filter((p) => p.name !== starter?.name).length === 0 && (
                <span className="sub-empty">No backup at {selectedPos}</span>
              )}
            </div>
          </div>

          {/* Position Flexibility Section */}
          <div style={{
            marginTop: '8px',
            padding: '6px 8px',
            background: '#1a1a2e',
            borderRadius: '6px',
            border: '1px solid #2d2d4e',
          }}>
            <div style={{ fontSize: '0.75em', color: '#93c5fd', fontWeight: 'bold', marginBottom: '4px' }}>
              🔀 Position Change (5E rules)
            </div>
            <div style={{ display: 'flex', gap: '4px', alignItems: 'center', flexWrap: 'wrap' }}>
              <select
                value={posChangePlayer}
                onChange={(e) => { setPosChangePlayer(e.target.value); setPosChangeTarget(''); setPosChangeMsg(''); }}
                style={{
                  background: '#111827',
                  color: '#ddd',
                  border: '1px solid #374151',
                  borderRadius: '4px',
                  padding: '2px 4px',
                  fontSize: '0.7em',
                }}
              >
                <option value="">Select player...</option>
                {allPlayers.map((p) => (
                  <option key={p.name} value={p.name}>
                    {p.name} ({p.position})
                  </option>
                ))}
              </select>
              <span style={{ fontSize: '0.7em', color: '#888' }}>→</span>
              <select
                value={posChangeTarget}
                onChange={(e) => setPosChangeTarget(e.target.value)}
                disabled={!posChangePlayer || compatiblePositions.length === 0}
                style={{
                  background: '#111827',
                  color: '#ddd',
                  border: '1px solid #374151',
                  borderRadius: '4px',
                  padding: '2px 4px',
                  fontSize: '0.7em',
                }}
              >
                <option value="">New position...</option>
                {compatiblePositions.map((pos) => (
                  <option key={pos} value={pos}>{pos}</option>
                ))}
              </select>
              <button
                onClick={handlePositionChange}
                disabled={!posChangePlayer || !posChangeTarget || loading}
                style={{
                  background: '#1e293b',
                  border: '1px solid #3b82f6',
                  color: '#93c5fd',
                  padding: '2px 8px',
                  borderRadius: '4px',
                  fontSize: '0.7em',
                  cursor: 'pointer',
                }}
              >
                Move
              </button>
            </div>
            {posChangeMsg && (
              <div style={{ fontSize: '0.65em', color: posChangeMsg.startsWith('✅') ? '#22c55e' : '#ef4444', marginTop: '2px' }}>
                {posChangeMsg}
              </div>
            )}
            <div style={{ fontSize: '0.55em', color: '#666', marginTop: '2px' }}>
              ⚠️ Out-of-position penalty: -1 to relevant ratings (OL blocking, CB/S pass defense)
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

