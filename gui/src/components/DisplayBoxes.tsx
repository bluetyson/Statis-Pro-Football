import { useState, useEffect } from 'react';
import axios from 'axios';
import type { PlayerBrief } from '../types/game';

const API_BASE = '/api';

interface DisplayBoxesProps {
  gameId: string;
}

interface BoxData {
  defense_team: string;
  boxes: Record<string, PlayerBrief | null>;
  rows: {
    row1_dl: Record<string, PlayerBrief | null>;
    row2_lb: Record<string, PlayerBrief | null>;
    row3_db: Record<string, PlayerBrief | null>;
  };
}

const ROW_LABELS: Record<string, string> = {
  A: 'A', B: 'B', C: 'C', D: 'D', E: 'E',
  F: 'F', G: 'G', H: 'H', I: 'I', J: 'J',
  K: 'K', L: 'L', M: 'M', N: 'N', O: 'O',
};

const PASS_DEFENSE_MAP: Record<string, string> = {
  N: 'RE (Right End)',
  K: 'LE (Left End)',
  O: 'FL#1',
  M: 'FL#2',
  F: 'BK#1',
  J: 'BK#2',
  H: 'BK#3',
};

function BoxCell({ box, player }: { box: string; player: PlayerBrief | null }) {
  const passAssignment = PASS_DEFENSE_MAP[box];
  return (
    <div
      className="display-box-cell"
      style={{
        background: player ? '#1e293b' : '#111827',
        border: player ? '1px solid #3b82f6' : '1px dashed #374151',
        borderRadius: '6px',
        padding: '4px 6px',
        textAlign: 'center',
        minWidth: '80px',
        position: 'relative',
      }}
      title={passAssignment ? `Covers: ${passAssignment}` : undefined}
    >
      <div style={{
        position: 'absolute',
        top: '1px',
        left: '4px',
        fontSize: '0.6em',
        color: '#6b7280',
        fontWeight: 'bold',
      }}>
        {ROW_LABELS[box]}
      </div>
      {player ? (
        <>
          <div style={{ fontSize: '0.7em', color: '#93c5fd', fontWeight: 'bold' }}>
            #{player.number} {player.position}
          </div>
          <div style={{ fontSize: '0.65em', color: '#ddd', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {player.name}
          </div>
          <div style={{ fontSize: '0.55em', color: '#888' }}>
            PR:{player.pass_rush_rating} PD:{player.pass_defense_rating} TK:{player.tackle_rating}
          </div>
        </>
      ) : (
        <div style={{ fontSize: '0.65em', color: '#4b5563' }}>Empty</div>
      )}
      {passAssignment && (
        <div style={{
          position: 'absolute',
          bottom: '1px',
          right: '3px',
          fontSize: '0.5em',
          color: '#f59e0b',
        }}>
          ↔{passAssignment.split(' ')[0]}
        </div>
      )}
    </div>
  );
}

/**
 * 5E Defensive Display Boxes — shows the 15-box (A-O) defensive arrangement
 * per 5E rules: Row 1 (DL: A-E), Row 2 (LB: F-J), Row 3 (DB: K-O)
 */
export function DisplayBoxes({ gameId }: DisplayBoxesProps) {
  const [boxData, setBoxData] = useState<BoxData | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const fetchBoxes = () => {
    if (!gameId) return;
    setLoading(true);
    axios
      .get(`${API_BASE}/games/${gameId}/display-boxes`)
      .then((res) => setBoxData(res.data))
      .catch(() => setBoxData(null))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (isOpen && gameId) fetchBoxes();
  }, [isOpen, gameId]);

  return (
    <div style={{
      background: '#0f172a',
      borderRadius: '8px',
      padding: '6px 10px',
      margin: '8px 0',
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
        🛡️ {isOpen ? 'Hide' : 'Show'} Defensive Display Boxes (5E A-O)
        {boxData && ` — ${boxData.defense_team}`}
      </button>

      {isOpen && loading && (
        <div style={{ fontSize: '0.75em', color: '#888', padding: '8px' }}>Loading...</div>
      )}

      {isOpen && boxData && (
        <div style={{ padding: '6px 0' }}>
          {/* Row 3: DB (K-O) — top of display */}
          <div style={{ marginBottom: '2px' }}>
            <span style={{ fontSize: '0.6em', color: '#666', textTransform: 'uppercase' }}>
              Row 3 — Defensive Backs (K-O)
            </span>
            <div style={{ display: 'flex', gap: '4px', marginTop: '2px' }}>
              {Object.entries(boxData.rows.row3_db).map(([box, player]) => (
                <BoxCell key={box} box={box} player={player} />
              ))}
            </div>
          </div>

          {/* Row 2: LB (F-J) */}
          <div style={{ marginBottom: '2px' }}>
            <span style={{ fontSize: '0.6em', color: '#666', textTransform: 'uppercase' }}>
              Row 2 — Linebackers (F-J)
            </span>
            <div style={{ display: 'flex', gap: '4px', marginTop: '2px' }}>
              {Object.entries(boxData.rows.row2_lb).map(([box, player]) => (
                <BoxCell key={box} box={box} player={player} />
              ))}
            </div>
          </div>

          {/* Row 1: DL (A-E) — bottom of display */}
          <div>
            <span style={{ fontSize: '0.6em', color: '#666', textTransform: 'uppercase' }}>
              Row 1 — Defensive Line (A-E)
            </span>
            <div style={{ display: 'flex', gap: '4px', marginTop: '2px' }}>
              {Object.entries(boxData.rows.row1_dl).map(([box, player]) => (
                <BoxCell key={box} box={box} player={player} />
              ))}
            </div>
          </div>

          {/* Refresh button */}
          <button
            onClick={fetchBoxes}
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
            🔄 Refresh Boxes
          </button>

          {/* Legend */}
          <div style={{ fontSize: '0.55em', color: '#666', marginTop: '4px' }}>
            📋 Pass Defense Assignments: RE→N, LE→K, FL#1→O, FL#2→M, BK#1→F, BK#2→J, BK#3→H
          </div>
        </div>
      )}
    </div>
  );
}
