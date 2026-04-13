import { useState, useEffect } from 'react';
import type { PlayerBrief } from '../types/game';

interface BlitzPlayerSelectorProps {
  linebackers: PlayerBrief[];
  defensiveBacks: PlayerBrief[];
  isBlitz: boolean;
  disabled: boolean;
  onSelectionChange: (players: string[]) => void;
}

/**
 * 5E Blitz Player Selection — allows choosing 2-5 LBs/DBs to blitz.
 * Per 5E rules, blitz removes 2-5 players from the defensive Display (Rows 2-3).
 */
export function BlitzPlayerSelector({
  linebackers,
  defensiveBacks,
  isBlitz,
  disabled,
  onSelectionChange,
}: BlitzPlayerSelectorProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!isBlitz) {
      setSelected(new Set());
      onSelectionChange([]);
    }
  }, [isBlitz, onSelectionChange]);

  if (!isBlitz) return null;

  const allEligible = [...linebackers, ...defensiveBacks];

  const toggle = (name: string) => {
    const next = new Set(selected);
    if (next.has(name)) {
      next.delete(name);
    } else {
      if (next.size >= 5) return; // Max 5 blitzers
      next.add(name);
    }
    setSelected(next);
    onSelectionChange(Array.from(next));
  };

  const validCount = selected.size >= 2 && selected.size <= 5;

  return (
    <div className="blitz-selector" style={{
      background: '#1a1a2e',
      borderRadius: '8px',
      padding: '8px 12px',
      margin: '8px 0',
      border: '1px solid #ef4444',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
        <span style={{ color: '#ef4444', fontWeight: 'bold', fontSize: '0.85em' }}>
          ⚡ Select Blitz Players (2-5)
        </span>
        <span style={{
          fontSize: '0.75em',
          color: validCount ? '#22c55e' : '#f59e0b',
          fontWeight: 'bold',
        }}>
          {selected.size} selected {validCount ? '✅' : '(need 2-5)'}
        </span>
      </div>

      {linebackers.length > 0 && (
        <div style={{ marginBottom: '4px' }}>
          <span style={{ fontSize: '0.7em', color: '#888', textTransform: 'uppercase' }}>
            Linebackers (Row 2)
          </span>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '2px' }}>
            {linebackers.map((p) => (
              <button
                key={p.name}
                onClick={() => toggle(p.name)}
                disabled={disabled || p.injured}
                className="blitz-player-btn"
                style={{
                  padding: '3px 8px',
                  fontSize: '0.75em',
                  borderRadius: '4px',
                  border: selected.has(p.name) ? '2px solid #ef4444' : '1px solid #444',
                  background: selected.has(p.name) ? '#ef444433' : '#222',
                  color: p.injured ? '#666' : '#ddd',
                  cursor: p.injured ? 'not-allowed' : 'pointer',
                }}
              >
                #{p.number} {p.name} ({p.position})
                {p.injured && ' 🏥'}
              </button>
            ))}
          </div>
        </div>
      )}

      {defensiveBacks.length > 0 && (
        <div>
          <span style={{ fontSize: '0.7em', color: '#888', textTransform: 'uppercase' }}>
            Defensive Backs (Row 3)
          </span>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '2px' }}>
            {defensiveBacks.map((p) => (
              <button
                key={p.name}
                onClick={() => toggle(p.name)}
                disabled={disabled || p.injured}
                className="blitz-player-btn"
                style={{
                  padding: '3px 8px',
                  fontSize: '0.75em',
                  borderRadius: '4px',
                  border: selected.has(p.name) ? '2px solid #ef4444' : '1px solid #444',
                  background: selected.has(p.name) ? '#ef444433' : '#222',
                  color: p.injured ? '#666' : '#ddd',
                  cursor: p.injured ? 'not-allowed' : 'pointer',
                }}
              >
                #{p.number} {p.name} ({p.position})
                {p.injured && ' 🏥'}
              </button>
            ))}
          </div>
        </div>
      )}

      <div style={{ fontSize: '0.65em', color: '#888', marginTop: '6px' }}>
        💡 Per 5E rules: Blitzing players get Pass Rush Value of 2 regardless of printed value.
        Selected players are removed from the Display for this play.
      </div>
    </div>
  );
}
