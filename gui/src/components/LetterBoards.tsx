import { useState } from 'react';
import type { PersonnelData, PlayerBrief } from '../types/game';

interface LetterBoardsProps {
  personnel: PersonnelData | null;
  possession: string;
  defenseFormation?: string;
}

/** Scale intercept_range (0-14) to a 0-100% bar width. */
function intRangeBarWidth(ir: number): string {
  return `${Math.min(ir * 10, 100)}%`;
}

/* ─── Compact inline card for a single player ─────────────────── */

function MiniCard({ player, isDefender }: { player: PlayerBrief; isDefender?: boolean }) {
  const gradeClass =
    player.overall_grade === 'A' ? 'grade-a' :
    player.overall_grade === 'B' ? 'grade-b' :
    player.overall_grade === 'D' ? 'grade-d' : 'grade-c';

  return (
    <div className={`mini-card ${isDefender ? 'mini-card-def' : 'mini-card-off'}`}>
      {/* Header: position + name + grade */}
      <div className="mini-card-header">
        <span className="mc-pos">{player.position}</span>
        <span className="mc-num">#{player.number}</span>
        <span className={`mc-grade ${gradeClass}`}>{player.overall_grade}</span>
        {player.receiver_letter && (
          <span className="mc-letter mc-letter-off">{player.receiver_letter}</span>
        )}
        {player.defender_letter && (
          <span className="mc-letter mc-letter-def">{player.defender_letter}</span>
        )}
      </div>
      <div className="mc-name">{player.name}</div>

      {/* QB: passing ranges */}
      {player.position === 'QB' && player.passing_quick && (
        <div className="mc-data">
          <table className="mc-table">
            <thead>
              <tr><th></th><th>COM</th><th>INC</th><th>INT</th></tr>
            </thead>
            <tbody>
              {[
                { l: 'Q', d: player.passing_quick },
                { l: 'S', d: player.passing_short },
                { l: 'L', d: player.passing_long },
              ].map(r => r.d ? (
                <tr key={r.l}>
                  <td className="mc-row-label">{r.l}</td>
                  <td className="pass-com">1-{r.d.com_max}</td>
                  <td className="pass-inc">{r.d.com_max + 1}-{r.d.inc_max}</td>
                  <td className="pass-int">{r.d.inc_max < 48 ? `${r.d.inc_max + 1}-48` : '—'}</td>
                </tr>
              ) : null)}
            </tbody>
          </table>
          {player.pass_rush && (
            <div className="mc-sub">
              PR: Sk 1-{player.pass_rush.sack_max} | R {player.pass_rush.sack_max + 1}-{player.pass_rush.runs_max} | C {player.pass_rush.runs_max + 1}-{player.pass_rush.com_max}
            </div>
          )}
          {player.qb_endurance && <div className="mc-sub">End: {player.qb_endurance}</div>}
        </div>
      )}

      {/* RB/WR/TE/QB: rushing + pass gain tables */}
      {!isDefender && player.position !== 'K' && player.position !== 'P' && (
        <div className="mc-data">
          {player.rushing && player.rushing.length > 0 && player.rushing.some(r => r !== null) && (
            <table className="mc-table">
              <thead>
                <tr><th>#</th><th>N</th><th>SG</th><th>LG</th></tr>
              </thead>
              <tbody>
                {player.rushing.map((row, i) => (
                  <tr key={i}>
                    <td className="mc-row-label">{i + 1}</td>
                    <td>{row ? row[0] : '—'}</td>
                    <td>{row ? row[1] : '—'}</td>
                    <td>{row ? row[2] : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {player.pass_gain && player.pass_gain.length > 0 && player.pass_gain.some(r => r !== null) && (
            <table className="mc-table">
              <thead>
                <tr><th>#</th><th>Q</th><th>S</th><th>L</th></tr>
              </thead>
              <tbody>
                {player.pass_gain.map((row, i) => (
                  <tr key={i}>
                    <td className="mc-row-label">{i + 1}</td>
                    <td>{row ? row[0] : '—'}</td>
                    <td>{row ? row[1] : '—'}</td>
                    <td>{row ? row[2] : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {player.blocks !== 0 && <div className="mc-sub">Blocks: {player.blocks > 0 ? '+' : ''}{player.blocks}</div>}
        </div>
      )}

      {/* Kicker: FG chart */}
      {player.fg_chart && Object.keys(player.fg_chart).length > 0 && (
        <div className="mc-data">
          <div className="mc-sub">XP: {((player.xp_rate || 0.95) * 100).toFixed(0)}%</div>
          <table className="mc-table">
            <thead><tr><th>Range</th><th>Rate</th></tr></thead>
            <tbody>
              {Object.entries(player.fg_chart).map(([range, rate]) => (
                <tr key={range}>
                  <td>{range}</td>
                  <td>{((rate as number) * 100).toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Punter */}
      {player.position === 'P' && player.avg_distance > 0 && (
        <div className="mc-data">
          <div className="mc-sub">Avg: {player.avg_distance.toFixed(1)} | I20: {((player.inside_20_rate || 0) * 100).toFixed(0)}%</div>
        </div>
      )}

      {/* Defender: authentic 5E position-specific ratings */}
      {isDefender && (
        <div className="mc-data mc-def-ratings">
          {/* DL: tackle + pass rush */}
          {['DE', 'DT', 'DL', 'NT'].includes(player.position.toUpperCase()) && (
            <>
              <div className="mc-rating">
                <span className="mc-rl">Tackle</span>
                <div className="mc-bar"><div className="mc-fill mc-fill-stop" style={{ width: `${player.tackle_rating}%` }} /></div>
                <span className="mc-rv">{player.tackle_rating}</span>
              </div>
              <div className="mc-rating">
                <span className="mc-rl">P.Rush</span>
                <div className="mc-bar"><div className="mc-fill mc-fill-rush" style={{ width: `${player.pass_rush_rating}%` }} /></div>
                <span className="mc-rv">{player.pass_rush_rating}</span>
              </div>
            </>
          )}
          {/* LB: pass defense, tackle, pass rush, intercept range */}
          {['LB', 'OLB', 'ILB', 'MLB'].includes(player.position.toUpperCase()) && (
            <>
              <div className="mc-rating">
                <span className="mc-rl">P.Def</span>
                <div className="mc-bar"><div className="mc-fill mc-fill-cov" style={{ width: `${player.pass_defense_rating}%` }} /></div>
                <span className="mc-rv">{player.pass_defense_rating}</span>
              </div>
              <div className="mc-rating">
                <span className="mc-rl">Tackle</span>
                <div className="mc-bar"><div className="mc-fill mc-fill-stop" style={{ width: `${player.tackle_rating}%` }} /></div>
                <span className="mc-rv">{player.tackle_rating}</span>
              </div>
              <div className="mc-rating">
                <span className="mc-rl">P.Rush</span>
                <div className="mc-bar"><div className="mc-fill mc-fill-rush" style={{ width: `${player.pass_rush_rating}%` }} /></div>
                <span className="mc-rv">{player.pass_rush_rating}</span>
              </div>
              <div className="mc-rating">
                <span className="mc-rl">Int</span>
                <div className="mc-bar"><div className="mc-fill mc-fill-int" style={{ width: intRangeBarWidth(player.intercept_range) }} /></div>
                <span className="mc-rv">{player.intercept_range}</span>
              </div>
            </>
          )}
          {/* DB: pass defense, pass rush, intercept range (no tackle) */}
          {['CB', 'S', 'SS', 'FS', 'DB'].includes(player.position.toUpperCase()) && (
            <>
              <div className="mc-rating">
                <span className="mc-rl">P.Def</span>
                <div className="mc-bar"><div className="mc-fill mc-fill-cov" style={{ width: `${player.pass_defense_rating}%` }} /></div>
                <span className="mc-rv">{player.pass_defense_rating}</span>
              </div>
              <div className="mc-rating">
                <span className="mc-rl">P.Rush</span>
                <div className="mc-bar"><div className="mc-fill mc-fill-rush" style={{ width: `${player.pass_rush_rating}%` }} /></div>
                <span className="mc-rv">{player.pass_rush_rating}</span>
              </div>
              <div className="mc-rating">
                <span className="mc-rl">Int</span>
                <div className="mc-bar"><div className="mc-fill mc-fill-int" style={{ width: intRangeBarWidth(player.intercept_range) }} /></div>
                <span className="mc-rv">{player.intercept_range}</span>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

/* ─── Offensive Line card with block ratings ─────────────────── */

function OLCard({ player }: { player: PlayerBrief }) {
  const gradeClass =
    player.overall_grade === 'A' ? 'grade-a' :
    player.overall_grade === 'B' ? 'grade-b' :
    player.overall_grade === 'D' ? 'grade-d' : 'grade-c';

  return (
    <div className="mini-card mini-card-ol">
      <div className="mini-card-header">
        <span className="mc-pos">{player.position}</span>
        <span className="mc-num">#{player.number}</span>
        <span className={`mc-grade ${gradeClass}`}>{player.overall_grade}</span>
      </div>
      <div className="mc-name">{player.name}</div>
      <div className="mc-data mc-def-ratings">
        <div className="mc-rating">
          <span className="mc-rl">Run</span>
          <div className="mc-bar"><div className="mc-fill mc-fill-rush" style={{ width: `${player.run_block_rating}%` }} /></div>
          <span className="mc-rv">{player.run_block_rating}</span>
        </div>
        <div className="mc-rating">
          <span className="mc-rl">Pass</span>
          <div className="mc-bar"><div className="mc-fill mc-fill-cov" style={{ width: `${player.pass_block_rating}%` }} /></div>
          <span className="mc-rv">{player.pass_block_rating}</span>
        </div>
      </div>
    </div>
  );
}

function OLSlot({ label }: { label: string }) {
  return (
    <div className="mini-card mini-card-ol">
      <div className="mc-pos-only">{label}</div>
    </div>
  );
}

/* ─── Offense Formation (5E positional layout) ───────────────── */

function gradeColor(grade: string): string {
  if (grade.startsWith('A')) return '#22c55e';
  if (grade === 'B') return '#3b82f6';
  if (grade === 'C') return '#f59e0b';
  return '#ef4444';
}

function shortName(fullName: string): string {
  const parts = fullName.trim().split(/\s+/);
  return parts.length > 1 ? parts[parts.length - 1] : fullName;
}

interface FormationSlotProps {
  label: string;
  player: PlayerBrief | null;
  showBlocks?: boolean;
  ghost?: boolean;
}

function FormationSlot({ label, player, showBlocks = false, ghost = false }: FormationSlotProps) {
  if (ghost) return <div className="fmn-cell fmn-ghost" />;

  return (
    <div className="fmn-cell">
      <div className="fmn-pos">{label}</div>
      {player ? (
        <div className={`fmn-player${player.injured ? ' fmn-player-inj' : ''}`}>
          <div className="fmn-name" title={player.name}>{shortName(player.name)}</div>
          <div className="fmn-grade" style={{ color: gradeColor(player.overall_grade) }}>
            {player.overall_grade}
          </div>
          {player.receiver_letter && (
            <div className="fmn-letter">[{player.receiver_letter}]</div>
          )}
          {showBlocks && player.blocks !== 0 && (
            // Only show BV when non-zero; a zero BV means no blocking modifier
            <div className="fmn-bv" style={{ color: player.blocks > 0 ? '#22c55e' : '#ef4444' }}>
              BV{player.blocks > 0 ? '+' : ''}{player.blocks}
            </div>
          )}
          {player.injured && <span className="fmn-inj">🏥</span>}
        </div>
      ) : (
        <div className="fmn-player-empty">—</div>
      )}
    </div>
  );
}

function OffenseFormation({ personnel }: { personnel: PersonnelData }) {
  const line = personnel.offense_line; // [LT, LG, C, RG, RT]

  // Split receivers into WRs and TEs
  const wrs = personnel.offense_receivers.filter(r => r.position !== 'TE');
  const tes = personnel.offense_receivers.filter(r => r.position === 'TE');

  // LE = split end (first WR), RE = tight end (or second WR), FL = next WR
  const le: PlayerBrief | null = wrs[0] ?? null;
  const re: PlayerBrief | null = tes[0] ?? wrs[1] ?? null;
  const fl: PlayerBrief | null = tes.length > 0 ? (wrs[1] ?? null) : (wrs[2] ?? null);

  const qb: PlayerBrief | null = personnel.offense_starters['QB'] ?? null;
  const bk1: PlayerBrief | null = personnel.offense_starters['RB'] ?? null;

  // Find BK2: second RB/FB/HB in offense_all by position, skipping BK1's slot
  // Note: PlayerBrief has no unique ID, so we skip by name (sufficient for roster uniqueness)
  const bk2: PlayerBrief | null = personnel.offense_all.find(p =>
    (p.position === 'RB' || p.position === 'FB' || p.position === 'HB') &&
    p.name !== bk1?.name
  ) ?? null;

  return (
    <div className="offense-formation">
      {/* Row 1: Line of scrimmage — LE LT LG C RG RT RE */}
      <div className="fmn-row">
        <FormationSlot label="LE" player={le} />
        <FormationSlot label="LT" player={line[0] ?? null} />
        <FormationSlot label="LG" player={line[1] ?? null} />
        <FormationSlot label="C"  player={line[2] ?? null} />
        <FormationSlot label="RG" player={line[3] ?? null} />
        <FormationSlot label="RT" player={line[4] ?? null} />
        <FormationSlot label="RE" player={re} />
      </div>

      {/* Scrimmage line indicator */}
      <div className="fmn-los-line" />

      {/* Row 2: QB behind center */}
      <div className="fmn-row">
        <FormationSlot label="" player={null} ghost />
        <FormationSlot label="" player={null} ghost />
        <FormationSlot label="" player={null} ghost />
        <FormationSlot label="QB" player={qb} />
        <FormationSlot label="" player={null} ghost />
        <FormationSlot label="" player={null} ghost />
        <FormationSlot label="" player={null} ghost />
      </div>

      {/* Row 3: Backs + Flanker */}
      <div className="fmn-row">
        <FormationSlot label="" player={null} ghost />
        <FormationSlot label="BK1" player={bk1} showBlocks />
        <FormationSlot label="BK2" player={bk2} showBlocks />
        <FormationSlot label="" player={null} ghost />
        <FormationSlot label="" player={null} ghost />
        <FormationSlot label="" player={null} ghost />
        <FormationSlot label="FL" player={fl} />
      </div>
    </div>
  );
}

/* ─── Defensive slot type ─────────────────────────────────────── */

type DefensiveSlot = {
  key: string;
  label: string;
  player: PlayerBrief | null;
};

function takeFirst(group: PlayerBrief[][]): PlayerBrief | null {
  for (const queue of group) {
    if (queue.length > 0) return queue.shift() ?? null;
  }
  return null;
}

function defenseFamily(formation?: string): '4_3' | '3_4' | 'NICKEL' | 'GOAL_LINE' {
  if (!formation) return '4_3';
  if (formation.startsWith('3_4')) return '3_4';
  if (formation.startsWith('NICKEL')) return 'NICKEL';
  if (formation === 'GOAL_LINE') return 'GOAL_LINE';
  // Fall back to the base 4-3 shell so unknown values still render a stable board.
  return '4_3';
}

function buildDefensiveLineSlots(players: PlayerBrief[]): DefensiveSlot[] {
  const ends = players.filter(p => p.position.toUpperCase() === 'DE');
  const noses = players.filter(p => p.position.toUpperCase() === 'NT');
  const tackles = players.filter(p => ['DT', 'DL'].includes(p.position.toUpperCase()));
  const extras = players.filter(p => !['DE', 'DT', 'DL', 'NT'].includes(p.position.toUpperCase()));

  const assignments = [
    takeFirst([ends, extras]),
    takeFirst([tackles, extras]),
    takeFirst([noses, extras]),
    takeFirst([tackles, extras]),
    takeFirst([ends, extras]),
  ];

  return ['DE', 'DT', 'NT', 'DT', 'DE'].map((label, index) => ({
    key: `dl-${index}`,
    label,
    player: assignments[index],
  }));
}

function buildLinebackerSlots(players: PlayerBrief[], formation?: string): DefensiveSlot[] {
  const family = defenseFamily(formation);
  const activeByFamily: Record<typeof family, number[]> = {
    '4_3': [0, 2, 4],
    '3_4': [0, 1, 3, 4],
    'NICKEL': [1, 2, 3],
    'GOAL_LINE': [0, 1, 2, 3, 4],
  };
  const labels = ['OLB', 'ILB', 'MLB', 'ILB', 'OLB'];
  const olbs = players.filter(p => p.position.toUpperCase() === 'OLB');
  const ilbs = players.filter(p => p.position.toUpperCase() === 'ILB');
  const mlbs = players.filter(p => p.position.toUpperCase() === 'MLB');
  const extras = players.filter(p => !['OLB', 'ILB', 'MLB'].includes(p.position.toUpperCase()));
  const active = new Set(activeByFamily[family]);

  return labels.map((label, index) => {
    if (!active.has(index)) {
      return { key: `lb-${index}`, label, player: null };
    }

    const player =
      label === 'OLB' ? takeFirst([olbs, extras]) :
      label === 'ILB' ? takeFirst([ilbs, extras]) :
      takeFirst([mlbs, extras]);

    return { key: `lb-${index}`, label, player };
  });
}

function buildSecondarySlots(players: PlayerBrief[], formation?: string): DefensiveSlot[] {
  const family = defenseFamily(formation);
  const activeByFamily: Record<typeof family, number[]> = {
    '4_3': [0, 1, 2, 4],
    '3_4': [0, 1, 2, 4],
    'NICKEL': [0, 1, 2, 3, 4],
    'GOAL_LINE': [0, 1, 2, 4],
  };
  const labels = ['CB', 'SS', 'FS', 'OBOX', 'CB'];
  const cbs = players.filter(p => p.position.toUpperCase() === 'CB');
  const strongSafeties = players.filter(p => p.position.toUpperCase() === 'SS');
  const freeSafeties = players.filter(p => p.position.toUpperCase() === 'FS');
  const safeties = players.filter(p => ['S', 'DB'].includes(p.position.toUpperCase()));
  const extras = players.filter(p => !['CB', 'SS', 'FS', 'S', 'DB'].includes(p.position.toUpperCase()));
  const active = new Set(activeByFamily[family]);

  return labels.map((label, index) => {
    if (!active.has(index)) {
      return { key: `db-${index}`, label, player: null };
    }

    const player =
      label === 'CB' ? takeFirst([cbs, safeties, extras]) :
      label === 'SS' ? takeFirst([strongSafeties, safeties, extras]) :
      label === 'FS' ? takeFirst([freeSafeties, safeties, extras]) :
      takeFirst([safeties, cbs, extras]);

    return { key: `db-${index}`, label, player };
  });
}

function DefensiveSlotCard({ slot }: { slot: DefensiveSlot }) {
  return (
    <div className="board-slot">
      <div className="board-slot-label">{slot.label}</div>
      {slot.player ? (
        <MiniCard player={slot.player} isDefender />
      ) : (
        <div className="mini-card mini-card-slot">
          <div className="mc-pos-only">{slot.label}</div>
        </div>
      )}
    </div>
  );
}

/* ─── LetterBoards main component ─────────────────────────────── */

export function LetterBoards({ personnel, defenseFormation }: LetterBoardsProps) {
  const [collapsed, setCollapsed] = useState<{ off: boolean; def: boolean }>({ off: false, def: false });

  if (!personnel) {
    return (
      <div className="letter-boards">
        <div className="board-placeholder">Loading personnel...</div>
      </div>
    );
  }

  const defensiveLineSlots = buildDefensiveLineSlots(personnel.defense_line);
  const linebackerSlots = buildLinebackerSlots(personnel.linebackers, defenseFormation);
  const secondarySlots = buildSecondarySlots(personnel.defensive_backs, defenseFormation);

  return (
    <div className="letter-boards">
      {/* ── OFFENSE BOARD ── */}
      <div className="lineup-board offense-board-5e">
        <div className="board-header-bar" onClick={() => setCollapsed(c => ({ ...c, off: !c.off }))}>
          <span className="board-icon">⚔️</span>
          <h4>OFFENSE — {personnel.offense_team}</h4>
          <span className="ball-badge">🏈</span>
          <span className="collapse-toggle">{collapsed.off ? '▶' : '▼'}</span>
        </div>

        {!collapsed.off && (
          <>
            {/* Formation view: LE LT LG C RG RT RE / QB / BK1 BK2 FL */}
            <OffenseFormation personnel={personnel} />

            {/* Detailed cards: OL block ratings */}
            <div className="board-row board-row-label">
              <span className="row-label-text">LINE RATINGS</span>
            </div>
            <div className="board-row board-row-ol">
              {personnel.offense_line && personnel.offense_line.length > 0
                ? personnel.offense_line.map((p, i) => (
                    <OLCard key={`ol-${i}`} player={p} />
                  ))
                : <>
                    <OLSlot label="LT" />
                    <OLSlot label="LG" />
                    <OLSlot label="C" />
                    <OLSlot label="RG" />
                    <OLSlot label="RT" />
                  </>
              }
            </div>

            {/* Backfield + Receivers detail cards */}
            <div className="board-row board-row-label">
              <span className="row-label-text">SKILL PLAYER RATINGS</span>
            </div>
            <div className="board-row board-row-backfield">
              {personnel.offense_starters.QB && (
                <MiniCard player={personnel.offense_starters.QB} />
              )}
              {personnel.offense_starters.RB && (
                <MiniCard player={personnel.offense_starters.RB} />
              )}
              {/* Show on-field receivers matching the formation grid (LE, RE, FL) */}
              {(() => {
                const wrs = personnel.offense_receivers.filter(r => r.position !== 'TE');
                const tes = personnel.offense_receivers.filter(r => r.position === 'TE');
                const onField: PlayerBrief[] = [];
                const le = wrs[0] ?? null;
                const re = tes[0] ?? wrs[1] ?? null;
                const fl = tes.length > 0 ? (wrs[1] ?? null) : (wrs[2] ?? null);
                const seen = new Set<string>();
                for (const p of [le, re, fl]) {
                  if (p && !seen.has(p.name)) {
                    seen.add(p.name);
                    onField.push(p);
                  }
                }
                return onField.map((r, i) => (
                  <MiniCard key={`rec-${i}`} player={r} />
                ));
              })()}
              {/* Show BK2 (blocking back) to match formation grid */}
              {(() => {
                const bk1 = personnel.offense_starters['RB'] ?? null;
                const bk2 = personnel.offense_all.find(p =>
                  (p.position === 'RB' || p.position === 'FB' || p.position === 'HB') &&
                  p.name !== bk1?.name
                ) ?? null;
                return bk2 ? <MiniCard player={bk2} /> : null;
              })()}
            </div>

            {/* Special Teams row */}
            <div className="board-row board-row-label">
              <span className="row-label-text">SPECIAL TEAMS</span>
            </div>
            <div className="board-row board-row-st">
              {personnel.offense_starters.K && (
                <MiniCard player={personnel.offense_starters.K} />
              )}
              {personnel.offense_starters.P && (
                <MiniCard player={personnel.offense_starters.P} />
              )}
            </div>
          </>
        )}
      </div>

      {/* ── DEFENSE BOARD ── */}
      <div className="lineup-board defense-board-5e">
        <div className="board-header-bar" onClick={() => setCollapsed(c => ({ ...c, def: !c.def }))}>
          <span className="board-icon">🛡️</span>
          <h4>DEFENSE — {personnel.defense_team}</h4>
          <span className="collapse-toggle">{collapsed.def ? '▶' : '▼'}</span>
        </div>

        {!collapsed.def && (
          <>
            {/* Row 1: Defensive Line (a-f) */}
            <div className="board-row board-row-label">
              <span className="row-label-text">DEFENSIVE LINE</span>
              <span className="row-letters">A(LE) B(LT) C(NT) D(RT) E(RE)</span>
            </div>
            <div className="board-row board-row-dl">
              {defensiveLineSlots.map(slot => (
                <DefensiveSlotCard key={slot.key} slot={slot} />
              ))}
            </div>

            {/* Row 2: Linebackers (g-k) */}
            <div className="board-row board-row-label">
              <span className="row-label-text">LINEBACKERS</span>
              <span className="row-letters">F(LOLB) G(LILB) H(MLB) I(RILB) J(ROLB)</span>
            </div>
            <div className="board-row board-row-lb">
              {linebackerSlots.map(slot => (
                <DefensiveSlotCard key={slot.key} slot={slot} />
              ))}
            </div>

            {/* Row 3: Defensive Backs (l-p) */}
            <div className="board-row board-row-label">
              <span className="row-label-text">DEFENSIVE BACKS</span>
              <span className="row-letters">K(LCB) L(DB) M(FS) N(SS) O(RCB)</span>
            </div>
            <div className="board-row board-row-db">
              {secondarySlots.map(slot => (
                <DefensiveSlotCard key={slot.key} slot={slot} />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
