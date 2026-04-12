import type { PlayResult } from '../types/game';

interface FACCardDisplayProps {
  lastPlay: PlayResult | null;
}

export function FACCardDisplay({ lastPlay }: FACCardDisplayProps) {
  if (!lastPlay) {
    return (
      <div className="fac-card-display">
        <div className="fac-card-placeholder">
          <span>No play yet</span>
        </div>
      </div>
    );
  }

  const hasCardInfo = lastPlay.run_number || lastPlay.pass_number;

  if (!hasCardInfo) {
    return null;
  }

  return (
    <div className="fac-card-display">
      <div className="fac-card">
        <div className="fac-card-header">
          <span className="fac-label">FAC Card</span>
          {lastPlay.z_card && <span className="z-badge">Z-CARD</span>}
        </div>
        <div className="fac-card-body">
          {lastPlay.run_number && (
            <div className="fac-field">
              <span className="fac-field-label">RUN #</span>
              <span className="fac-field-value">{lastPlay.run_number}</span>
            </div>
          )}
          {lastPlay.pass_number && (
            <div className="fac-field">
              <span className="fac-field-label">PASS #</span>
              <span className="fac-field-value">{lastPlay.pass_number}</span>
            </div>
          )}
        </div>
        <div className="fac-card-footer">
          <span className="fac-result">{lastPlay.result}</span>
          <span className="fac-yards">{lastPlay.yards > 0 ? '+' : ''}{lastPlay.yards} yds</span>
        </div>
        {lastPlay.description && (
          <div className="fac-description">
            {lastPlay.z_card && <span className="z-indicator">⚠️ Z-CARD EVENT: </span>}
            {lastPlay.description}
          </div>
        )}
      </div>
    </div>
  );
}
