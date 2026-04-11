import type { GameState } from '../types/game';

interface GridironProps {
  state: GameState;
}

/**
 * Visual gridiron (football field) display showing ball position,
 * down markers, and field position context.
 */
export function Gridiron({ state }: GridironProps) {
  // yard_line is distance from offense's own end zone (1-99)
  // We need to convert to absolute field position for display
  const isHome = state.possession === 'home';
  // Home team attacks left-to-right, away attacks right-to-left
  const absYardLine = isHome ? state.yard_line : 100 - state.yard_line;
  const ballPercent = absYardLine;

  // First down marker position
  const firstDownPercent = isHome
    ? Math.min(100, state.yard_line + state.distance)
    : Math.max(0, 100 - state.yard_line - state.distance);

  const yardMarkers = [10, 20, 30, 40, 50, 60, 70, 80, 90];

  function ordinal(n: number) {
    return ['', '1st', '2nd', '3rd', '4th'][n] ?? `${n}th`;
  }

  return (
    <div className="gridiron">
      {/* Down & Distance overlay */}
      <div className="gridiron-situation">
        <span className="gridiron-down">
          {ordinal(state.down)} &amp; {state.distance}
        </span>
        <span className="gridiron-pos">
          {state.possession === 'home' ? state.home_team : state.away_team} ball
          {' · '}
          {state.yard_line > 50
            ? `OPP ${100 - state.yard_line}`
            : state.yard_line === 50
            ? 'MIDFIELD'
            : `OWN ${state.yard_line}`}
        </span>
      </div>

      {/* The field */}
      <div className="field">
        {/* End zones */}
        <div className="endzone endzone-away">
          <span>{state.away_team}</span>
        </div>

        <div className="field-body">
          {/* Yard lines */}
          {yardMarkers.map((yd) => (
            <div
              key={yd}
              className="yard-line"
              style={{ left: `${yd}%` }}
            >
              <span className="yard-number">
                {yd <= 50 ? yd : 100 - yd}
              </span>
            </div>
          ))}

          {/* Hash marks (decorative) */}
          {Array.from({ length: 19 }, (_, i) => (i + 1) * 5).map((yd) => (
            <div
              key={`hash-${yd}`}
              className="hash-mark"
              style={{ left: `${yd}%` }}
            />
          ))}

          {/* First down marker */}
          {state.down <= 4 && !state.is_over && (
            <div
              className="first-down-marker"
              style={{ left: `${firstDownPercent}%` }}
              title={`1st down marker`}
            />
          )}

          {/* Ball position */}
          <div
            className="ball-marker"
            style={{ left: `${ballPercent}%` }}
            title={`Ball at own ${state.yard_line}`}
          >
            🏈
          </div>

          {/* Scrimmage line */}
          <div
            className="scrimmage-line"
            style={{ left: `${ballPercent}%` }}
          />
        </div>

        <div className="endzone endzone-home">
          <span>{state.home_team}</span>
        </div>
      </div>

      {/* Timeout indicators */}
      <div className="timeout-row">
        <div className="timeout-group">
          <span className="timeout-label">{state.away_team} TO:</span>
          {[1, 2, 3].map((t) => (
            <span
              key={t}
              className={`timeout-dot ${t <= (state.timeouts_away ?? 3) ? 'active' : ''}`}
            />
          ))}
        </div>
        <div className="timeout-group">
          <span className="timeout-label">{state.home_team} TO:</span>
          {[1, 2, 3].map((t) => (
            <span
              key={t}
              className={`timeout-dot ${t <= (state.timeouts_home ?? 3) ? 'active' : ''}`}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
