import { useState } from 'react';
import type { PersonnelData, PlayerBrief } from '../types/game';

interface SubstitutionPanelProps {
  personnel: PersonnelData | null;
  loading: boolean;
  onSubstitute: (position: string, playerOut: string, playerIn: string) => void;
}

const POSITIONS = ['QB', 'RB', 'WR', 'TE', 'K', 'P', 'DL', 'LB', 'DB'];

export function SubstitutionPanel({ personnel, loading, onSubstitute }: SubstitutionPanelProps) {
  const [selectedPos, setSelectedPos] = useState<string>('QB');
  const [isOpen, setIsOpen] = useState(false);

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

  return (
    <div className="substitution-panel">
      <button
        className="sub-toggle-btn"
        onClick={() => setIsOpen(!isOpen)}
      >
        🔄 {isOpen ? 'Hide' : 'Show'} Substitutions
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
        </div>
      )}
    </div>
  );
}
