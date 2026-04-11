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
