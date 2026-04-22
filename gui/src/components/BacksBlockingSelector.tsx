import { useState, useEffect } from 'react';
import type { PlayerBrief } from '../types/game';

interface BacksBlockingSelectorProps {
  /** All on-field receivers; only RBs in BK slots are shown. */
  backs: PlayerBrief[];
  isPassPlay: boolean;
  disabled: boolean;
  onSelectionChange: (players: string[]) => void;
}

/**
 * 5E Backs-in-to-Block Selector.
 *
 * Per 5E rules (Extra Pass Blocking):
 *   - Any or all backs may be declared as blockers before the snap.
 *   - Each blocking back adds +2 to the QB's Completion Range.
 *   - The pass may NOT be directed at a blocking back.
 *   - If the FAC redirects the pass to a blocking back, the pass is INCOMPLETE.
 */
export function BacksBlockingSelector({
  backs,
  isPassPlay,
  disabled,
  onSelectionChange,
}: BacksBlockingSelectorProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set());

  // Reset when switching away from pass plays
  useEffect(() => {
    if (!isPassPlay) {
      setSelected(new Set());
      onSelectionChange([]);
    }
  }, [isPassPlay, onSelectionChange]);

  if (!isPassPlay || backs.length === 0) return null;

  const toggle = (name: string) => {
    const next = new Set(selected);
    if (next.has(name)) {
      next.delete(name);
    } else {
      next.add(name);
    }
    setSelected(next);
    onSelectionChange(Array.from(next));
  };

  const bonus = selected.size * 2;

  return (
    <div
      style={{
        background: '#1a2e1a',
        borderRadius: '8px',
        padding: '8px 12px',
        margin: '8px 0',
        border: '1px solid #22c55e',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '6px',
        }}
      >
        <span style={{ color: '#22c55e', fontWeight: 'bold', fontSize: '0.85em' }}>
          🛡️ Backs in to Block (Optional)
        </span>
        {selected.size > 0 && (
          <span style={{ fontSize: '0.75em', color: '#22c55e', fontWeight: 'bold' }}>
            +{bonus} completion range ✅
          </span>
        )}
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
        {backs.map((p) => (
          <button
            key={p.name}
            onClick={() => toggle(p.name)}
            disabled={disabled || p.injured}
            style={{
              padding: '3px 8px',
              fontSize: '0.75em',
              borderRadius: '4px',
              border: selected.has(p.name) ? '2px solid #22c55e' : '1px solid #444',
              background: selected.has(p.name) ? '#22c55e33' : '#222',
              color: p.injured ? '#666' : '#ddd',
              cursor: p.injured ? 'not-allowed' : 'pointer',
            }}
          >
            #{p.number} {p.name} ({p.position})
            {p.injured && ' 🏥'}
          </button>
        ))}
      </div>

      <div style={{ fontSize: '0.65em', color: '#888', marginTop: '6px' }}>
        💡 Per 5E rules: +2 completion range per blocking back. Blocking backs
        cannot be targeted — if FAC redirects to a blocker, the pass is{' '}
        <strong>INCOMPLETE</strong>.
      </div>
    </div>
  );
}
