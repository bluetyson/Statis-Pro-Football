import { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { PlayerCardView } from './PlayerCard';
import type { PlayerBrief, PlayerCard, TeamCardData, TeamData } from '../types/game';

const API_BASE = '/api';

interface CardViewerProps {
  teamAbbr: string;
}

type CardSelection = 'TEAM' | 'KR' | 'PR' | string;

function formatRecord(record: TeamData['record']) {
  return `${record.wins}-${record.losses}${record.ties ? `-${record.ties}` : ''}`;
}

function lineupEntries(lineup: Record<string, PlayerBrief | null>) {
  return Object.entries(lineup).filter(([, player]) => player);
}

export function CardViewer({ teamAbbr }: CardViewerProps) {
  const [team, setTeam] = useState<TeamData | null>(null);
  const [selectedView, setSelectedView] = useState<CardSelection>('TEAM');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!teamAbbr) return;
    setLoading(true);
    axios
      .get(`${API_BASE}/teams/${teamAbbr}`)
      .then((res) => {
        setTeam(res.data);
        setSelectedView('TEAM');
      })
      .catch(() => setTeam(null))
      .finally(() => setLoading(false));
  }, [teamAbbr]);

  const playerLookup = useMemo(() => {
    const map = new Map<string, PlayerCard>();
    team?.players.forEach((player) => map.set(player.name, player));
    return map;
  }, [team?.players]);

  const teamCard = team?.team_card;
  const selectedCard =
    selectedView === 'KR'
      ? teamCard?.returners.KR ? playerLookup.get(teamCard.returners.KR.name) ?? null : null
      : selectedView === 'PR'
      ? teamCard?.returners.PR ? playerLookup.get(teamCard.returners.PR.name) ?? null : null
      : playerLookup.get(selectedView) ?? null;

  const renderPlayerLink = (label: string, player: PlayerBrief | null | undefined) => {
    if (!player) return null;
    return (
      <button
        key={`${label}-${player.name}`}
        className="team-card-player"
        onClick={() => setSelectedView(player.name)}
      >
        <span className="team-card-label">{label}</span>
        <span className="team-card-name">#{player.number} {player.name}</span>
        <span className="team-card-grade">{player.overall_grade}</span>
      </button>
    );
  };

  const renderTeamCard = (card: TeamCardData) => (
    <div className="team-card-view">
      <div className="team-card-header">
        <div>
          <div className="team-card-title">{card.city} {card.name}</div>
          <div className="team-card-subtitle">
            {card.team} • {formatRecord(card.record)}
          </div>
        </div>
        <div className="team-card-meta">
          <span>{team?.conference}</span>
          <span>{team?.division}</span>
        </div>
      </div>

      <div className="team-card-grid">
        <section className="team-card-section">
          <h4>Offense</h4>
          <div className="team-card-stack">
            {lineupEntries(card.offense).map(([label, player]) => renderPlayerLink(label, player))}
          </div>
        </section>

        <section className="team-card-section">
          <h4>Offensive Line</h4>
          <div className="team-card-stack">
            {card.offensive_line.map((player) => renderPlayerLink(player.position, player))}
          </div>
        </section>

        <section className="team-card-section">
          <h4>Defense</h4>
          <div className="team-card-stack">
            {card.defense.map((player, index) => renderPlayerLink(`${player.position}${index + 1}`, player))}
          </div>
        </section>

        <section className="team-card-section">
          <h4>Kick Return Depth (KR1-KR3)</h4>
          <div className="team-card-stack">
            {card.kick_returners.map((player, index) => renderPlayerLink(`KR${index + 1}`, player))}
          </div>
        </section>

        <section className="team-card-section">
          <h4>Punt Return Depth (PR1-PR4)</h4>
          <div className="team-card-stack">
            {card.punt_returners.map((player, index) => renderPlayerLink(`PR${index + 1}`, player))}
          </div>
        </section>

        <section className="team-card-section">
          <h4>Specialists</h4>
          <div className="team-card-stack">
            {renderPlayerLink('K', card.offense.K)}
            {renderPlayerLink('P', card.offense.P)}
          </div>
        </section>
      </div>
    </div>
  );

  if (loading) return <div className="card-viewer-loading">Loading team cards...</div>;
  if (!team) return <div className="card-viewer-empty">Select a team to view cards</div>;

  return (
    <div className="card-viewer">
      <h3 className="card-viewer-title">{team.city} {team.name} Cards</h3>

      <div className="card-viewer-actions">
        <button
          className={`roster-btn ${selectedView === 'TEAM' ? 'active' : ''}`}
          onClick={() => setSelectedView('TEAM')}
        >
          <span className="roster-pos">TEAM</span>
          <span className="roster-name">Team Card</span>
          <span className="roster-grade">{formatRecord(team.record)}</span>
        </button>
        {teamCard?.returners.KR && (
          <button
            className={`roster-btn ${selectedView === 'KR' ? 'active' : ''}`}
            onClick={() => setSelectedView('KR')}
          >
            <span className="roster-pos">KR</span>
            <span className="roster-name">{teamCard.returners.KR.name}</span>
            <span className="roster-grade">{teamCard.returners.KR.overall_grade}</span>
          </button>
        )}
        {teamCard?.returners.PR && (
          <button
            className={`roster-btn ${selectedView === 'PR' ? 'active' : ''}`}
            onClick={() => setSelectedView('PR')}
          >
            <span className="roster-pos">PR</span>
            <span className="roster-name">{teamCard.returners.PR.name}</span>
            <span className="roster-grade">{teamCard.returners.PR.overall_grade}</span>
          </button>
        )}
      </div>

      <div className="roster-list">
        {team.players.map((player) => (
          <button
            key={player.name}
            className={`roster-btn ${selectedView === player.name ? 'active' : ''}`}
            onClick={() => setSelectedView(player.name)}
          >
            <span className="roster-pos">{player.position}</span>
            <span className="roster-name">{player.name}</span>
            <span className="roster-grade">{player.overall_grade}</span>
          </button>
        ))}
      </div>

      <div className="selected-card-view">
        {selectedView === 'TEAM' && teamCard ? renderTeamCard(teamCard) : null}
        {selectedView !== 'TEAM' && selectedCard ? <PlayerCardView card={selectedCard} /> : null}
      </div>
    </div>
  );
}
