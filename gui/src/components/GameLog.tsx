interface GameLogProps {
  plays: string[];
}

export function GameLog({ plays }: GameLogProps) {
  const getPlayClass = (line: string) => {
    if (line.includes('TOUCHDOWN') || line.includes('TD')) return 'log-td';
    if (line.includes('GAME OVER') || line.includes('FINAL')) return 'log-final';
    if (line.includes('PENALTY') || line.includes('⚠')) return 'log-penalty';
    if (line.includes('intercept') || line.includes('INT') || line.includes('fumble') || line.includes('FUMBLE')) return 'log-turnover';
    if (line.includes('→') || line.startsWith('  ')) return 'log-result';
    if (line.startsWith('Q') || line.startsWith('End')) return 'log-situation';
    return 'log-normal';
  };

  return (
    <div className="game-log">
      <h3 className="log-title">📋 Play-by-Play</h3>
      <div className="log-entries">
        {plays.length === 0 ? (
          <p className="log-empty">No plays yet. Start a game and run some plays!</p>
        ) : (
          [...plays].reverse().map((line, i) => (
            <div key={i} className={`log-entry ${getPlayClass(line)}`}>
              {line}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
