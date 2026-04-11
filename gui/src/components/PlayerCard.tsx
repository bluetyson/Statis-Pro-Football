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
      {card.position === 'QB' && (card as Record<string, unknown>).passing_quick && (
        <div className="card-section">
          <div className="section-title">Passing Ranges (1-48)</div>
          <table className="card-data-table">
            <thead>
              <tr><th>Type</th><th>COM</th><th>INC</th><th>INT</th></tr>
            </thead>
            <tbody>
              {['Quick', 'Short', 'Long'].map((label) => {
                const key = `passing_${label.toLowerCase()}` as keyof typeof card;
                const ranges = (card as Record<string, unknown>)[key] as { com_max: number; inc_max: number } | null;
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
        </div>
      )}

      {/* Rushing Table */}
      {(card as Record<string, unknown>).rushing && Array.isArray((card as Record<string, unknown>).rushing) &&
       ((card as Record<string, unknown>).rushing as unknown[]).length > 0 && (
        <div className="card-section">
          <div className="section-title">Rushing (N/SG/LG)</div>
          <table className="card-data-table">
            <thead>
              <tr><th>#</th><th>N</th><th>SG</th><th>LG</th></tr>
            </thead>
            <tbody>
              {((card as Record<string, unknown>).rushing as (number[] | null)[]).map((row, i) => (
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
      {(card as Record<string, unknown>).pass_gain && Array.isArray((card as Record<string, unknown>).pass_gain) &&
       ((card as Record<string, unknown>).pass_gain as unknown[]).length > 0 && (
        <div className="card-section">
          <div className="section-title">Pass Gain (Q/S/L)</div>
          <table className="card-data-table">
            <thead>
              <tr><th>#</th><th>Q</th><th>S</th><th>L</th></tr>
            </thead>
            <tbody>
              {((card as Record<string, unknown>).pass_gain as (number[] | null)[]).map((row, i) => (
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
    </div>
  );
}

