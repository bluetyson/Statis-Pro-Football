import type { PersonnelData, PlayerBrief } from '../types/game';

interface LetterBoardsProps {
  personnel: PersonnelData | null;
  possession: string;
}

function PlayerChip({ player, highlight }: { player: PlayerBrief; highlight?: boolean }) {
  const gradeClass =
    player.overall_grade === 'A' ? 'grade-a' :
    player.overall_grade === 'B' ? 'grade-b' :
    player.overall_grade === 'D' ? 'grade-d' : 'grade-c';

  return (
    <div className={`player-chip ${highlight ? 'chip-highlight' : ''}`}>
      <span className="chip-pos">{player.position}</span>
      <span className="chip-number">#{player.number}</span>
      <span className="chip-name">{player.name}</span>
      {player.receiver_letter && (
        <span className="chip-letter">{player.receiver_letter}</span>
      )}
      <span className={`chip-grade ${gradeClass}`}>{player.overall_grade}</span>
    </div>
  );
}

export function LetterBoards({ personnel, possession }: LetterBoardsProps) {
  if (!personnel) {
    return (
      <div className="letter-boards">
        <div className="board-placeholder">Loading personnel...</div>
      </div>
    );
  }

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
            <PlayerChip player={personnel.offense_starters.QB} highlight />
          )}
          {/* RB */}
          {personnel.offense_starters.RB && (
            <PlayerChip player={personnel.offense_starters.RB} />
          )}
          {/* Receivers (WR + TE) with letter designations */}
          {personnel.offense_receivers.map((r, i) => (
            <PlayerChip key={i} player={r} />
          ))}
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
                <PlayerChip key={i} player={p} />
              ))
            : <span className="board-empty">No defensive personnel data</span>
          }
        </div>
      </div>
    </div>
  );
}
