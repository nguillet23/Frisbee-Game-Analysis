import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchPlayer } from "../api.js";
import GradeBadge from "../components/GradeBadge.jsx";
import ContributorBar from "../components/ContributorBar.jsx";

const STAT_LABELS = {
  completion_pct: "Completion %",
  turnovers_per_point: "Turnovers / point",
  blocks_per_point: "Blocks / point",
  goals_per_point: "Goals / point",
  assists_per_point: "Assists / point",
};

export default function PlayerProfile() {
  const { id } = useParams();
  const [player, setPlayer] = useState(null);
  const [error, setError] = useState(null);
  const [expandedGame, setExpandedGame] = useState(null);

  useEffect(() => {
    setPlayer(null);
    setError(null);
    fetchPlayer(id).then(setPlayer).catch((err) => setError(err.message));
  }, [id]);

  if (error) return <p className="error">Couldn't load this player: {error}</p>;
  if (!player) return <p>Loading…</p>;

  return (
    <div>
      <Link to="/">&larr; Back to leaderboard</Link>

      <div className="profile-header">
        <div>
          <h1>{player.name}</h1>
          <p className="subtitle">
            {player.team} · {player.archetype} · {player.games_played} games ({player.season})
          </p>
        </div>
        <div className="profile-rating">
          <GradeBadge grade={player.grade} tier={player.tier} />
          <span className="rating-value">{player.composite_rating} rating</span>
        </div>
      </div>

      <h2>Season stats</h2>
      <table className="stat-table">
        <tbody>
          {Object.entries(STAT_LABELS).map(([key, label]) => (
            <tr key={key}>
              <th>{label}</th>
              <td>{player.season_stats[key]}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>Game log</h2>
      <p className="subtitle">
        "Predicted" is what the model expected before the game, from role/prior form/opponent only (see{" "}
        <code>Plans/UFA_Analysis.md</code> Phase 5) — blank for a player's first games of the season, before
        there's any prior form to predict from. Click a row with a prediction to see what drove it.
      </p>
      <table className="game-log">
        <thead>
          <tr>
            <th>Date</th>
            <th>Opp</th>
            <th>Pts</th>
            <th>Actual</th>
            <th>Predicted</th>
          </tr>
        </thead>
        <tbody>
          {player.games.map((g) => (
            <GameRow
              key={g.game_id}
              game={g}
              expanded={expandedGame === g.game_id}
              onToggle={() => setExpandedGame(expandedGame === g.game_id ? null : g.game_id)}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function GameRow({ game, expanded, onToggle }) {
  const canExpand = game.top_contributors.length > 0;
  const maxAbs = Math.max(...game.top_contributors.map((c) => Math.abs(c.value)), 0);

  return (
    <>
      <tr className={canExpand ? "clickable" : ""} onClick={canExpand ? onToggle : undefined}>
        <td>{game.date}</td>
        <td>
          {game.is_home ? "vs" : "@"} {game.opponent}
        </td>
        <td>{game.points_played}</td>
        <td>{game.actual_rating}</td>
        <td>{game.predicted_rating ?? "—"}</td>
      </tr>
      {expanded && (
        <tr className="contrib-details">
          <td colSpan={5}>
            {game.top_contributors.map((c) => (
              <ContributorBar key={c.feature} feature={c.feature} value={c.value} maxAbs={maxAbs} />
            ))}
          </td>
        </tr>
      )}
    </>
  );
}
