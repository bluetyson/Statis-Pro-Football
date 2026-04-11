import { useState, useEffect } from 'react';
import axios from 'axios';
import { PlayerCardView } from './PlayerCard';
import type { PlayerCard, TeamData } from '../types/game';

const API_BASE = '/api';

interface CardViewerProps {
  teamAbbr: string;
}

export function CardViewer({ teamAbbr }: CardViewerProps) {
  const [team, setTeam] = useState<TeamData | null>(null);
  const [selectedCard, setSelectedCard] = useState<PlayerCard | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!teamAbbr) return;
    setLoading(true);
    axios
      .get(`${API_BASE}/teams/${teamAbbr}/roster`)
      .then((res) => {
        const fakeTeam: TeamData = {
          abbreviation: teamAbbr,
          city: '',
          name: teamAbbr,
          conference: '',
          division: '',
          record: { wins: 0, losses: 0, ties: 0 },
          offense_rating: 75,
          defense_rating: 75,
          players: res.data.players,
        };
        setTeam(fakeTeam);
        setSelectedCard(null);
      })
      .catch(() => setTeam(null))
      .finally(() => setLoading(false));
  }, [teamAbbr]);

  if (loading) return <div className="card-viewer-loading">Loading roster...</div>;
  if (!team) return <div className="card-viewer-empty">Select a team to view cards</div>;

  return (
    <div className="card-viewer">
      <h3 className="card-viewer-title">{teamAbbr} Roster</h3>
      <div className="roster-list">
        {team.players.map((p, i) => (
          <button
            key={i}
            className={`roster-btn ${selectedCard?.name === p.name ? 'active' : ''}`}
            onClick={() => setSelectedCard(selectedCard?.name === p.name ? null : p)}
          >
            <span className="roster-pos">{p.position}</span>
            <span className="roster-name">{p.name}</span>
            <span className="roster-grade">{p.overall_grade}</span>
          </button>
        ))}
      </div>
      {selectedCard && (
        <div className="selected-card-view">
          <PlayerCardView card={selectedCard} />
        </div>
      )}
    </div>
  );
}
