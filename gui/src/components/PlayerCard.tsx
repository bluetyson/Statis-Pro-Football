import type { PlayerCard } from '../types/game';

interface PlayerCardProps {
  card: PlayerCard;
}

const GRADE_COLORS: Record<string, string> = {
  'A+': '#fbbf24',
  A: '#f59e0b',
  B: '#3b82f6',
  C: '#6b7280',
  D: '#ef4444',
};

export function PlayerCardView({ card }: PlayerCardProps) {
  const gradeColor = GRADE_COLORS[card.overall_grade] ?? '#6b7280';
  const extCard = card as Record<string, unknown>;

  return (
    <div className="player-card">
      <div className="card-header" style={{ borderLeftColor: gradeColor }}>
        <div className="card-number">#{card.number}</div>
        <div className="card-identity">
          <span className="card-name">{card.name}</span>
          <span className="card-pos-team">{card.position} · {card.team}</span>
        </div>
        <div className="card-grade" style={{ color: gradeColor }}>
          {card.overall_grade}
        </div>
      </div>

      {/* QB Passing Ranges */}
      {card.position === 'QB' && extCard.passing_quick && (
        <div className="card-section">
          <div className="section-title">Passing Ranges (1-48)</div>
          <table className="card-data-table">
            <thead>
              <tr><th>Type</th><th>COM</th><th>INC</th><th>INT</th></tr>
            </thead>
            <tbody>
              {['Quick', 'Short', 'Long'].map((label) => {
                const key = `passing_${label.toLowerCase()}` as keyof typeof card;
                const ranges = extCard[key] as { com_max: number; inc_max: number } | null;
                if (!ranges) return null;
                return (
                  <tr key={label}>
                    <td>{label}</td>
                    <td>1-{ranges.com_max}</td>
                    <td>{ranges.com_max + 1}-{ranges.inc_max}</td>
                    <td>{ranges.inc_max < 48 ? `${ranges.inc_max + 1}-48` : '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {extCard.pass_rush && (
            <div className="card-sub-info">
              PR: Sack 1-{(extCard.pass_rush as { sack_max: number }).sack_max} |
              Runs {(extCard.pass_rush as { sack_max: number; runs_max: number }).sack_max + 1}-{(extCard.pass_rush as { runs_max: number }).runs_max} |
              COM {(extCard.pass_rush as { runs_max: number; com_max: number }).runs_max + 1}-{(extCard.pass_rush as { com_max: number }).com_max}
            </div>
          )}
          {extCard.qb_endurance && (
            <div className="card-sub-info">QB Endurance: {extCard.qb_endurance as string}</div>
          )}
        </div>
      )}

      {/* Rushing Table */}
      {extCard.rushing && Array.isArray(extCard.rushing) &&
       (extCard.rushing as unknown[]).length > 0 && (
        <div className="card-section">
          <div className="section-title">Rushing (N/SG/LG)</div>
          {typeof extCard.endurance_rushing === 'number' && (
            <div className="card-sub-info">Endurance: {extCard.endurance_rushing as number}</div>
          )}
          <table className="card-data-table">
            <thead>
              <tr><th>#</th><th>N</th><th>SG</th><th>LG</th></tr>
            </thead>
            <tbody>
              {(extCard.rushing as (number[] | null)[]).map((row, i) => (
                <tr key={i}>
                  <td>{i + 1}</td>
                  <td>{row ? row[0] : '—'}</td>
                  <td>{row ? row[1] : '—'}</td>
                  <td>{row ? row[2] : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pass Gain Table */}
      {extCard.pass_gain && Array.isArray(extCard.pass_gain) &&
       (extCard.pass_gain as unknown[]).length > 0 && (
        <div className="card-section">
          <div className="section-title">Pass Gain (Q/S/L)</div>
          {typeof extCard.endurance_pass === 'number' && extCard.endurance_pass !== 0 && (
            <div className="card-sub-info">Endurance: {extCard.endurance_pass as number}</div>
          )}
          <table className="card-data-table">
            <thead>
              <tr><th>#</th><th>Q</th><th>S</th><th>L</th></tr>
            </thead>
            <tbody>
              {(extCard.pass_gain as (number[] | null)[]).map((row, i) => (
                <tr key={i}>
                  <td>{i + 1}</td>
                  <td>{row ? row[0] : '—'}</td>
                  <td>{row ? row[1] : '—'}</td>
                  <td>{row ? row[2] : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Blocking Value */}
      {typeof extCard.blocks === 'number' && extCard.blocks !== 0 && (
        <div className="card-section">
          <div className="card-sub-info">
            Blocking Value: {(extCard.blocks as number) > 0 ? '+' : ''}{extCard.blocks as number}
          </div>
        </div>
      )}

      {/* Defensive Ratings (5E) */}
      {card.pass_rush_rating !== undefined && card.position !== 'QB' &&
       ['DE', 'DT', 'DL', 'NT', 'LB', 'OLB', 'ILB', 'MLB', 'CB', 'S', 'SS', 'FS', 'DB'].includes(card.position) && (
        <div className="card-section">
          <div className="section-title">Defensive Ratings (5E)</div>
          <div className="def-rating-grid">
            {typeof extCard.tackle_rating === 'number' && (
              <div className="def-rating-item">
                <span className="def-label">Tackle</span>
                <span className="def-value">{extCard.tackle_rating as number}</span>
              </div>
            )}
            <div className="def-rating-item">
              <span className="def-label">Pass Rush</span>
              <span className="def-value">{card.pass_rush_rating}</span>
            </div>
            {typeof extCard.pass_defense_rating === 'number' && (extCard.pass_defense_rating as number) !== 0 && (
              <div className="def-rating-item">
                <span className="def-label">Pass Defense</span>
                <span className="def-value">{extCard.pass_defense_rating as number}</span>
              </div>
            )}
            {typeof extCard.intercept_range === 'number' && (extCard.intercept_range as number) !== 0 && (
              <div className="def-rating-item">
                <span className="def-label">Intercept Range</span>
                <span className="def-value">{extCard.intercept_range as number}-48</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* OL Blocking Ratings */}
      {['LT', 'LG', 'C', 'RG', 'RT', 'OL'].includes(card.position) && (
        <div className="card-section">
          <div className="section-title">Blocking Ratings</div>
          <div className="def-rating-grid">
            {typeof extCard.run_block_rating === 'number' && (
              <div className="def-rating-item">
                <span className="def-label">Run Block</span>
                <span className="def-value">{extCard.run_block_rating as number}</span>
              </div>
            )}
            {typeof extCard.pass_block_rating === 'number' && (
              <div className="def-rating-item">
                <span className="def-label">Pass Block</span>
                <span className="def-value">{extCard.pass_block_rating as number}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {card.stats_summary && Object.keys(card.stats_summary).length > 0 && (
        <div className="card-stats">
          {Object.entries(card.stats_summary).map(([key, val]) => (
            <div key={key} className="stat-row">
              <span className="stat-key">{key.replace(/_/g, ' ')}</span>
              <span className="stat-val">
                {typeof val === 'number'
                  ? val < 1 && val > 0
                    ? `${(val * 100).toFixed(1)}%`
                    : val.toFixed(1)
                  : val}
              </span>
            </div>
          ))}
        </div>
      )}

      {card.fg_chart && (
        <div className="fg-chart">
          <div className="fg-chart-title">Field Goal Chart</div>
          {typeof card.longest_kick === 'number' && card.longest_kick > 0 && (
            <div className="card-sub-info">Longest Field Goal: {card.longest_kick} yds</div>
          )}
          {Object.entries(card.fg_chart).map(([range, rate]) => (
            <div key={range} className="fg-row">
              <span className="fg-range">{range} yds</span>
              <div className="fg-bar-container">
                <div
                  className="fg-bar"
                  style={{ width: `${(rate as number) * 100}%` }}
                />
              </div>
              <span className="fg-pct">{((rate as number) * 100).toFixed(0)}%</span>
            </div>
          ))}
        </div>
      )}

      {card.position === 'P' && (
        <div className="card-section">
          <div className="section-title">Punting</div>
          <div className="def-rating-grid">
            {typeof card.avg_distance === 'number' && (
              <div className="def-rating-item">
                <span className="def-label">Average</span>
                <span className="def-value">{card.avg_distance.toFixed(1)}</span>
              </div>
            )}
            {typeof card.inside_20_rate === 'number' && (
              <div className="def-rating-item">
                <span className="def-label">Inside 20</span>
                <span className="def-value">{(card.inside_20_rate * 100).toFixed(0)}%</span>
              </div>
            )}
            {typeof card.blocked_punt_number === 'number' && card.blocked_punt_number > 0 && (
              <div className="def-rating-item">
                <span className="def-label">Blocked</span>
                <span className="def-value">1-{card.blocked_punt_number}</span>
              </div>
            )}
            {typeof card.punt_return_pct === 'number' && (
              <div className="def-rating-item">
                <span className="def-label">Returned</span>
                <span className="def-value">{(card.punt_return_pct * 100).toFixed(0)}%</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
