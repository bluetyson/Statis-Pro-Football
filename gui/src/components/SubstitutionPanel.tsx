import { useState } from 'react';
import axios from 'axios';
import type { PersonnelData, PlayerBrief } from '../types/game';

const API_BASE = '/api';

interface SubstitutionPanelProps {
  gameId: string;
  personnel: PersonnelData | null;
  loading: boolean;
  onSubstitute: (position: string, playerOut: string, playerIn: string) => void;
  onRefreshPersonnel?: () => void;
}

const POSITIONS = ['QB', 'RB', 'WR', 'TE', 'OL', 'K', 'P', 'DL', 'LB', 'DB'];

const COMPATIBLE_POSITIONS: Record<string, string[]> = {
  // Defensive
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
  // Offensive skill
  RB: ['WR', 'TE'],
  WR: ['RB', 'TE'],
  TE: ['WR', 'RB'],
  // Offensive line
  LT: ['LG', 'OL'],
  LG: ['LT', 'C', 'OL'],
  C: ['LG', 'RG', 'OL'],
  RG: ['LG', 'C', 'RT', 'OL'],
  RT: ['RG', 'OL'],
  OL: ['LT', 'LG', 'C', 'RG', 'RT'],
};

// Skill formation slots and their display labels
const SKILL_SLOTS = ['FL', 'LE', 'RE', 'BK1', 'BK2', 'BK3'] as const;
const SKILL_SLOT_LABELS: Record<string, string> = {
  FL: 'FL (Flanker / FL#2)',
  LE: 'LE (Left End / FL#1)',
  RE: 'RE (Right End / TE)',
  BK1: 'BK1 (Back 1 / B1)',
  BK2: 'BK2 (Back 2 / B2)',
  BK3: 'BK3 (Back 3 / B3 — 3RB set)',
};

// Formation packages
const PACKAGES = [
  { key: 'STANDARD', label: 'Standard', desc: 'Auto-select from roster' },
  { key: '2TE_1WR', label: '2-TE', desc: 'WR1→LE, WR2→FL, TE1→RE' },
  { key: '3TE', label: '3-TE', desc: 'TE1→RE, TE2→LE, TE3→FL' },
  { key: 'JUMBO', label: 'Jumbo', desc: 'Heavy 3-TE blocking set' },
  { key: '4WR', label: '4-WR', desc: 'WR1→LE, WR2→FL, WR3→RE' },
  { key: '3RB', label: '3-RB', desc: 'WR1→LE (split end on line), TE1→RE (tight end on line), RB1→BK1, RB2→BK2, RB3→BK3 — no flanker (7-man line: OL×5 + LE + RE)' },
] as const;

// Defensive packages
const DEF_PACKAGES = [
  { key: 'STANDARD', label: 'Base (4-3)', desc: '4 DL / 3 LB / 4 DB — base formation' },
  { key: 'NICKEL',   label: 'Nickel (4-2-5)', desc: '4 DL, 2 LB, 5 DB — drop 1 LB, add 1 DB' },
  { key: 'DIME',     label: 'Dime (4-1-6)', desc: '4 DL, 1 LB, 6 DB — drop 2 LBs, add 2 DBs' },
  { key: '335',      label: '3-3-5', desc: '3 DL, 3 LB, 5 DB — 3-4 nickel look' },
  { key: 'PREVENT',  label: 'Prevent', desc: '2 DL, 2 LB, 7 DB — deep coverage' },
] as const;

// Small shared styles
const selectStyle: React.CSSProperties = {
  background: '#111827', color: '#ddd', border: '1px solid #374151',
  borderRadius: '4px', padding: '2px 4px', fontSize: '0.7em',
};
const btnStyle: React.CSSProperties = {
  background: '#1e293b', border: '1px solid #3b82f6', color: '#93c5fd',
  padding: '2px 8px', borderRadius: '4px', fontSize: '0.7em', cursor: 'pointer',
};
const sectionStyle: React.CSSProperties = {
  marginTop: '8px', padding: '6px 8px', background: '#1a1a2e',
  borderRadius: '6px', border: '1px solid #2d2d4e',
};
const sectionTitleStyle: React.CSSProperties = {
  fontSize: '0.75em', color: '#93c5fd', fontWeight: 'bold', marginBottom: '4px',
};

export function SubstitutionPanel({
  gameId, personnel, loading, onSubstitute, onRefreshPersonnel,
}: SubstitutionPanelProps) {
  const [selectedPos, setSelectedPos] = useState<string>('QB');
  const [isOpen, setIsOpen] = useState(false);

  // Position change state
  const [posChangePlayer, setPosChangePlayer] = useState<string>('');
  const [posChangeTarget, setPosChangeTarget] = useState<string>('');
  const [posChangeMsg, setPosChangeMsg] = useState<string>('');

  // On-field slot state — per slot dropdown selection
  const [slotSelections, setSlotSelections] = useState<Record<string, string>>({});
  const [slotMsg, setSlotMsg] = useState<string>('');

  // Package state
  const [packageMsg, setPackageMsg] = useState<string>('');
  const [activePackage, setActivePackage] = useState<string>('');

  // Defense package state
  const [defPackageMsg, setDefPackageMsg] = useState<string>('');
  const [activeDefPackage, setActiveDefPackage] = useState<string>('');

  if (!personnel) return null;

  const DEF_POSITIONS = new Set(['DL', 'LB', 'DB', 'DE', 'DT', 'NT', 'CB', 'S', 'SS', 'FS', 'OLB', 'ILB', 'MLB']);
  const isDefPos = DEF_POSITIONS.has(selectedPos);
  const isOLPos = selectedPos === 'OL';
  const allPlayers = isDefPos ? personnel.defense_all : personnel.offense_all;
  // Skill players eligible for on-field slot assignments
  const skillPlayers = personnel.offense_all.filter(
    p => ['WR', 'TE', 'RB', 'FB', 'HB'].includes(p.position.toUpperCase()),
  );
  const olPlayers = personnel.offense_all.filter(
    p => ['LT', 'LG', 'C', 'RG', 'RT', 'OL'].includes(p.position.toUpperCase()),
  );

  // Map the UI position groups to actual position values
  const posGroupMap: Record<string, string[]> = {
    DL: ['DE', 'DT', 'DL', 'NT'],
    LB: ['LB', 'OLB', 'ILB', 'MLB'],
    DB: ['CB', 'S', 'SS', 'FS', 'DB'],
    OL: ['LT', 'LG', 'C', 'RG', 'RT', 'OL'],
  };
  const posMatch = posGroupMap[selectedPos] ?? [selectedPos];
  const posPlayers = allPlayers.filter(
    (p) => posMatch.includes(p.position.toUpperCase()),
  );

  const starter = isDefPos || isOLPos
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

  const handleSetSlot = async (slot: string) => {
    const playerName = slotSelections[slot];
    setSlotMsg('');
    try {
      const res = await axios.post(`${API_BASE}/games/${gameId}/set-field-slot`, {
        slot,
        player_name: playerName || null,
        team: 'possession',
      });
      setSlotMsg(`✅ ${res.data.message}`);
      onRefreshPersonnel?.();
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        setSlotMsg(`❌ ${err.response?.data?.detail ?? err.message}`);
      } else {
        setSlotMsg(`❌ ${err instanceof Error ? err.message : 'An unknown error occurred'}`);
      }
    }
  };

  const handleClearSlot = async (slot: string) => {
    setSlotMsg('');
    setSlotSelections(prev => ({ ...prev, [slot]: '' }));
    try {
      const res = await axios.post(`${API_BASE}/games/${gameId}/set-field-slot`, {
        slot,
        player_name: null,
        team: 'possession',
      });
      setSlotMsg(`✅ ${res.data.message}`);
      onRefreshPersonnel?.();
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        setSlotMsg(`❌ ${err.response?.data?.detail ?? err.message}`);
      } else {
        setSlotMsg(`❌ ${err instanceof Error ? err.message : 'An unknown error occurred'}`);
      }
    }
  };

  const handleApplyPackage = async (pkg: string) => {
    setPackageMsg('');
    try {
      const res = await axios.post(`${API_BASE}/games/${gameId}/apply-package`, {
        package: pkg,
        team: 'possession',
      });
      setPackageMsg(`✅ ${res.data.message}`);
      setActivePackage(pkg);
      onRefreshPersonnel?.();
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        setPackageMsg(`❌ ${err.response?.data?.detail ?? err.message}`);
      } else {
        setPackageMsg(`❌ ${err instanceof Error ? err.message : 'An unknown error occurred'}`);
      }
    }
  };

  const handleApplyDefensePackage = async (pkg: string) => {
    setDefPackageMsg('');
    try {
      const res = await axios.post(`${API_BASE}/games/${gameId}/apply-defense-package`, {
        package: pkg,
        team: 'defense',
      });
      setDefPackageMsg(`✅ ${res.data.message}`);
      setActiveDefPackage(pkg);
      onRefreshPersonnel?.();
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        setDefPackageMsg(`❌ ${err.response?.data?.detail ?? err.message}`);
      } else {
        setDefPackageMsg(`❌ ${err instanceof Error ? err.message : 'An unknown error occurred'}`);
      }
    }
  };

  // Get compatible positions for the selected player
  const selectedPlayerPos = allPlayers.find(p => p.name === posChangePlayer)?.position?.toUpperCase() ?? '';
  const compatiblePositions = COMPATIBLE_POSITIONS[selectedPlayerPos] ?? [];

  const onFieldAssignments = personnel.on_field_assignments ?? {};

  return (
    <div className="substitution-panel">
      <button className="sub-toggle-btn" onClick={() => setIsOpen(!isOpen)}>
        🔄 {isOpen ? 'Hide' : 'Show'} Substitutions & Formation
      </button>

      {isOpen && (
        <div className="sub-content">
          {/* ── Position tabs ── */}
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

          {/* ── Starter row ── */}
          <div className="sub-starter">
            <span className="sub-label">Starter:</span>
            {starter ? (
              <span className="sub-player-name">
                #{starter.number} {starter.name} ({starter.position} {starter.overall_grade})
                {isOLPos && starter.run_block_rating != null && (
                  <span style={{ fontSize: '0.8em', color: '#6b7280', marginLeft: '4px' }}>
                    RB:{starter.run_block_rating} PB:{starter.pass_block_rating}
                  </span>
                )}
              </span>
            ) : (
              <span className="sub-empty">None</span>
            )}
          </div>

          {/* ── Bench / available list ── */}
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
                    {isOLPos && (
                      <span style={{ fontSize: '0.65em', color: '#6b7280', marginLeft: '2px' }}>
                        RB:{p.run_block_rating} PB:{p.pass_block_rating}
                      </span>
                    )}
                    <span className="sub-arrow">↑</span>
                  </button>
                ))}
              {posPlayers.filter((p) => p.name !== starter?.name).length === 0 && (
                <span className="sub-empty">No backup at {selectedPos}</span>
              )}
            </div>
          </div>

          {/* ── Formation Packages (offense) ── */}
          {!isDefPos && (
          <div style={sectionStyle}>
            <div style={sectionTitleStyle}>🏈 Formation Packages</div>
            <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginBottom: '4px' }}>
              {PACKAGES.map(({ key, label, desc }) => (
                <button
                  key={key}
                  onClick={() => handleApplyPackage(key)}
                  disabled={loading}
                  title={desc}
                  style={{
                    ...btnStyle,
                    background: activePackage === key ? '#1e3a5f' : '#1e293b',
                    border: activePackage === key ? '1px solid #60a5fa' : '1px solid #374151',
                    color: activePackage === key ? '#bfdbfe' : '#93c5fd',
                    fontWeight: activePackage === key ? 'bold' : 'normal',
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
            {packageMsg && (
              <div style={{ fontSize: '0.65em', color: packageMsg.startsWith('✅') ? '#22c55e' : '#ef4444', marginTop: '2px' }}>
                {packageMsg}
              </div>
            )}
            <div style={{ fontSize: '0.55em', color: '#666', marginTop: '2px' }}>
              Packages set which players fill each receiver slot (FL/LE/RE/BK1/BK2/BK3).
            </div>
          </div>
          )}

          {/* ── Defensive Packages ── */}
          {isDefPos && (
          <div style={sectionStyle}>
            <div style={sectionTitleStyle}>🛡️ Defensive Packages</div>
            <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginBottom: '4px' }}>
              {DEF_PACKAGES.map(({ key, label, desc }) => (
                <button
                  key={key}
                  onClick={() => handleApplyDefensePackage(key)}
                  disabled={loading}
                  title={desc}
                  style={{
                    ...btnStyle,
                    background: activeDefPackage === key ? '#1a3a2a' : '#1e293b',
                    border: activeDefPackage === key ? '1px solid #4ade80' : '1px solid #374151',
                    color: activeDefPackage === key ? '#bbf7d0' : '#6ee7b7',
                    fontWeight: activeDefPackage === key ? 'bold' : 'normal',
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
            {defPackageMsg && (
              <div style={{ fontSize: '0.65em', color: defPackageMsg.startsWith('✅') ? '#22c55e' : '#ef4444', marginTop: '2px' }}>
                {defPackageMsg}
              </div>
            )}
            <div style={{ fontSize: '0.55em', color: '#666', marginTop: '2px' }}>
              Reorders the defensive roster so the chosen DL/LB/DB mix starts.
            </div>
          </div>
          )}

          {/* ── On-Field Skill Slots (offense only) ── */}
          {!isDefPos && (
          <div style={sectionStyle}>
            <div style={sectionTitleStyle}>🎯 On-Field Slot Assignments</div>
            <div style={{ fontSize: '0.6em', color: '#888', marginBottom: '4px' }}>
              Current overrides (blank = auto from roster order)
            </div>
            {SKILL_SLOTS.map((slot) => {
              const assigned = onFieldAssignments[slot] ?? '';
              return (
                <div key={slot} style={{ display: 'flex', gap: '4px', alignItems: 'center', marginBottom: '3px' }}>
                  <span style={{ fontSize: '0.65em', color: '#6b7280', minWidth: '36px', fontWeight: 'bold' }}>
                    {slot}
                  </span>
                  {assigned && (
                    <span style={{ fontSize: '0.65em', color: '#22c55e', minWidth: '80px' }}>
                      ✓ {assigned}
                    </span>
                  )}
                  <select
                    value={slotSelections[slot] ?? ''}
                    onChange={e => setSlotSelections(prev => ({ ...prev, [slot]: e.target.value }))}
                    style={{ ...selectStyle, flex: 1, minWidth: '0' }}
                    title={SKILL_SLOT_LABELS[slot]}
                  >
                    <option value="">— select player —</option>
                    {skillPlayers.map(p => (
                      <option key={p.name} value={p.name}>
                        {p.name} ({p.position} {p.overall_grade})
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={() => handleSetSlot(slot)}
                    disabled={!slotSelections[slot] || loading}
                    style={btnStyle}
                  >
                    Set
                  </button>
                  {assigned && (
                    <button
                      onClick={() => handleClearSlot(slot)}
                      disabled={loading}
                      style={{ ...btnStyle, border: '1px solid #6b7280', color: '#9ca3af' }}
                      title="Clear — revert to auto"
                    >
                      ✕
                    </button>
                  )}
                </div>
              );
            })}
            {slotMsg && (
              <div style={{ fontSize: '0.65em', color: slotMsg.startsWith('✅') ? '#22c55e' : '#ef4444', marginTop: '2px' }}>
                {slotMsg}
              </div>
            )}
          </div>
          )}

          {/* ── OL Slot Assignments (shown when OL tab active) ── */}
          {isOLPos && (
            <div style={sectionStyle}>
              <div style={sectionTitleStyle}>🛡️ OL Slot Assignments</div>
              {(['LT', 'LG', 'C', 'RG', 'RT'] as const).map((olSlot) => {
                const assigned = onFieldAssignments[olSlot] ?? '';
                return (
                  <div key={olSlot} style={{ display: 'flex', gap: '4px', alignItems: 'center', marginBottom: '3px' }}>
                    <span style={{ fontSize: '0.65em', color: '#6b7280', minWidth: '28px', fontWeight: 'bold' }}>
                      {olSlot}
                    </span>
                    {assigned && (
                      <span style={{ fontSize: '0.65em', color: '#22c55e', minWidth: '80px' }}>
                        ✓ {assigned}
                      </span>
                    )}
                    <select
                      value={slotSelections[olSlot] ?? ''}
                      onChange={e => setSlotSelections(prev => ({ ...prev, [olSlot]: e.target.value }))}
                      style={{ ...selectStyle, flex: 1, minWidth: '0' }}
                    >
                      <option value="">— select OL —</option>
                      {olPlayers.map(p => (
                        <option key={p.name} value={p.name}>
                          {p.name} ({p.position}) RB:{p.run_block_rating} PB:{p.pass_block_rating}
                        </option>
                      ))}
                    </select>
                    <button
                      onClick={() => handleSetSlot(olSlot)}
                      disabled={!slotSelections[olSlot] || loading}
                      style={btnStyle}
                    >
                      Set
                    </button>
                    {assigned && (
                      <button
                        onClick={() => handleClearSlot(olSlot)}
                        disabled={loading}
                        style={{ ...btnStyle, border: '1px solid #6b7280', color: '#9ca3af' }}
                        title="Clear — revert to auto"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* ── Position Change (5E rules) ── */}
          <div style={sectionStyle}>
            <div style={sectionTitleStyle}>🔀 Position Change (5E rules)</div>
            <div style={{ display: 'flex', gap: '4px', alignItems: 'center', flexWrap: 'wrap' }}>
              <select
                value={posChangePlayer}
                onChange={(e) => { setPosChangePlayer(e.target.value); setPosChangeTarget(''); setPosChangeMsg(''); }}
                style={selectStyle}
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
                style={selectStyle}
              >
                <option value="">New position...</option>
                {compatiblePositions.map((pos) => (
                  <option key={pos} value={pos}>{pos}</option>
                ))}
              </select>
              <button
                onClick={handlePositionChange}
                disabled={!posChangePlayer || !posChangeTarget || loading}
                style={btnStyle}
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
