import { useState } from 'react';
import type { PersonnelData, PlayerBrief } from '../types/game';

interface LetterBoardsProps {
  personnel: PersonnelData | null;
  possession: string;
}

/** Compact table for 12-row rushing or pass-gain data. */
function ThreeColumnTable({
  rows,
  headers,
  label,
}: {
  rows: (number[] | null)[];
  headers: [string, string, string];
  label: string;
}) {
  if (!rows || rows.length === 0) return null;
  return (
    <div className="card-table">
      <div className="card-table-label">{label}</div>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>{headers[0]}</th>
            <th>{headers[1]}</th>
            <th>{headers[2]}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              <td className="row-num">{i + 1}</td>
              <td>{row ? row[0] : '—'}</td>
              <td>{row ? row[1] : '—'}</td>
              <td>{row ? row[2] : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** QB passing ranges display */
function PassRangesDisplay({ player }: { player: PlayerBrief }) {
  if (!player.passing_quick && !player.passing_short && !player.passing_long) return null;

  const ranges = [
    { label: 'Quick', data: player.passing_quick },
    { label: 'Short', data: player.passing_short },
    { label: 'Long', data: player.passing_long },
  ];

  return (
    <div className="card-table">
      <div className="card-table-label">Passing Ranges (1-48)</div>
      <table>
        <thead>
          <tr>
            <th>Type</th>
            <th>COM</th>
            <th>INC</th>
            <th>INT</th>
          </tr>
        </thead>
        <tbody>
          {ranges.map((r) => {
            if (!r.data) return null;
            const com = r.data.com_max;
            const inc = r.data.inc_max - r.data.com_max;
            const int_ = 48 - r.data.inc_max;
            return (
              <tr key={r.label}>
                <td className="row-label">{r.label}</td>
                <td className="pass-com">1-{com}</td>
                <td className="pass-inc">{com + 1}-{r.data.inc_max}</td>
                <td className="pass-int">{int_ > 0 ? `${r.data.inc_max + 1}-48` : '—'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {player.pass_rush && (
        <div className="pass-rush-info">
          Pass Rush: Sack 1-{player.pass_rush.sack_max} |
          Runs {player.pass_rush.sack_max + 1}-{player.pass_rush.runs_max} |
          Com {player.pass_rush.runs_max + 1}-{player.pass_rush.com_max} |
          Inc {player.pass_rush.com_max + 1}-48
        </div>
      )}
    </div>
  );
}

/** Defensive ratings display */
function DefenseRatings({ player }: { player: PlayerBrief }) {
  const hasRatings =
    player.pass_rush_rating > 0 ||
    player.coverage_rating > 0 ||
    player.run_stop_rating > 0;
  if (!hasRatings) return null;

  return (
    <div className="defense-ratings">
      <div className="rating-bar">
        <span className="rating-label">Rush</span>
        <div className="rating-fill" style={{ width: `${player.pass_rush_rating}%` }} />
        <span className="rating-value">{player.pass_rush_rating}</span>
      </div>
      <div className="rating-bar">
        <span className="rating-label">Cov</span>
        <div className="rating-fill coverage" style={{ width: `${player.coverage_rating}%` }} />
        <span className="rating-value">{player.coverage_rating}</span>
      </div>
      <div className="rating-bar">
        <span className="rating-label">Stop</span>
        <div className="rating-fill run-stop" style={{ width: `${player.run_stop_rating}%` }} />
        <span className="rating-value">{player.run_stop_rating}</span>
      </div>
    </div>
  );
}

function PlayerChip({
  player,
  highlight,
  expanded,
  onToggle,
}: {
  player: PlayerBrief;
  highlight?: boolean;
  expanded: boolean;
  onToggle: () => void;
}) {
  const gradeClass =
    player.overall_grade === 'A' ? 'grade-a' :
    player.overall_grade === 'B' ? 'grade-b' :
    player.overall_grade === 'D' ? 'grade-d' : 'grade-c';

  const isDefender = ['DEF', 'DL', 'LB', 'CB', 'S'].includes(player.position);

  return (
    <div className={`player-chip-wrap ${expanded ? 'expanded' : ''}`}>
      <div
        className={`player-chip ${highlight ? 'chip-highlight' : ''}`}
        onClick={onToggle}
        role="button"
        tabIndex={0}
      >
        <span className="chip-pos">{player.position}</span>
        <span className="chip-number">#{player.number}</span>
        <span className="chip-name">{player.name}</span>
        {player.receiver_letter && (
          <span className="chip-letter">{player.receiver_letter}</span>
        )}
        {player.defender_letter && (
          <span className="chip-letter def-letter">{player.defender_letter}</span>
        )}
        <span className={`chip-grade ${gradeClass}`}>{player.overall_grade}</span>
        <span className="chip-expand">{expanded ? '▼' : '▶'}</span>
      </div>
      {expanded && (
        <div className="chip-card-detail">
          {/* QB passing ranges */}
          {player.position === 'QB' && <PassRangesDisplay player={player} />}
          {/* QB endurance */}
          {player.position === 'QB' && player.qb_endurance && (
            <div className="endurance-badge">Endurance: {player.qb_endurance}</div>
          )}
          {/* Rushing rows */}
          {player.rushing && player.rushing.length > 0 && (
            <ThreeColumnTable
              rows={player.rushing}
              headers={['N', 'SG', 'LG']}
              label={`Rushing (End: ${player.endurance_rushing})`}
            />
          )}
          {/* Pass gain rows */}
          {player.pass_gain && player.pass_gain.length > 0 && (
            <ThreeColumnTable
              rows={player.pass_gain}
              headers={['Q', 'S', 'L']}
              label={`Pass Gain (End: ${player.endurance_pass})`}
            />
          )}
          {/* Blocks */}
          {player.blocks !== 0 && (
            <div className="blocks-badge">Blocks: {player.blocks > 0 ? '+' : ''}{player.blocks}</div>
          )}
          {/* Defense ratings */}
          {isDefender && <DefenseRatings player={player} />}
          {/* Kicker FG chart */}
          {player.fg_chart && Object.keys(player.fg_chart).length > 0 && (
            <div className="card-table">
              <div className="card-table-label">FG Chart (XP: {((player.xp_rate || 0.95) * 100).toFixed(0)}%)</div>
              <table>
                <thead>
                  <tr>
                    <th>Range</th>
                    <th>Rate</th>
                  </tr>
                </thead>
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
            <div className="punter-info">
              Avg: {player.avg_distance.toFixed(1)} yds | Inside 20: {((player.inside_20_rate || 0) * 100).toFixed(0)}%
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function LetterBoards({ personnel, possession }: LetterBoardsProps) {
  const [expandedPlayer, setExpandedPlayer] = useState<string | null>(null);

  if (!personnel) {
    return (
      <div className="letter-boards">
        <div className="board-placeholder">Loading personnel...</div>
      </div>
    );
  }

  const togglePlayer = (key: string) => {
    setExpandedPlayer(expandedPlayer === key ? null : key);
  };

  return (
    <div className="letter-boards">
      {/* Offense Board */}
      <div className="letter-board offense-board">
        <div className="board-header-bar">
          <span className="board-icon">⚔️</span>
          <h4>OFFENSE — {personnel.offense_team}</h4>
          <span className="ball-badge">🏈</span>
        </div>
        <div className="board-grid">
          {/* QB */}
          {personnel.offense_starters.QB && (
            <PlayerChip
              player={personnel.offense_starters.QB}
              highlight
              expanded={expandedPlayer === 'off-QB'}
              onToggle={() => togglePlayer('off-QB')}
            />
          )}
          {/* RB */}
          {personnel.offense_starters.RB && (
            <PlayerChip
              player={personnel.offense_starters.RB}
              expanded={expandedPlayer === 'off-RB'}
              onToggle={() => togglePlayer('off-RB')}
            />
          )}
          {/* Receivers (WR + TE) with letter designations */}
          {personnel.offense_receivers.map((r, i) => (
            <PlayerChip
              key={i}
              player={r}
              expanded={expandedPlayer === `off-rec-${i}`}
              onToggle={() => togglePlayer(`off-rec-${i}`)}
            />
          ))}
          {/* Kicker */}
          {personnel.offense_starters.K && (
            <PlayerChip
              player={personnel.offense_starters.K}
              expanded={expandedPlayer === 'off-K'}
              onToggle={() => togglePlayer('off-K')}
            />
          )}
          {/* Punter */}
          {personnel.offense_starters.P && (
            <PlayerChip
              player={personnel.offense_starters.P}
              expanded={expandedPlayer === 'off-P'}
              onToggle={() => togglePlayer('off-P')}
            />
          )}
        </div>
      </div>

      {/* Defense Board */}
      <div className="letter-board defense-board">
        <div className="board-header-bar">
          <span className="board-icon">🛡️</span>
          <h4>DEFENSE — {personnel.defense_team}</h4>
        </div>
        <div className="board-grid">
          {personnel.defense_players.length > 0
            ? personnel.defense_players.map((p, i) => (
                <PlayerChip
                  key={i}
                  player={p}
                  expanded={expandedPlayer === `def-${i}`}
                  onToggle={() => togglePlayer(`def-${i}`)}
                />
              ))
            : <span className="board-empty">No defensive personnel data</span>
          }
        </div>
      </div>
    </div>
  );
}

