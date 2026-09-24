import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchLeaderboard } from "../api.js";
import GradeBadge from "../components/GradeBadge.jsx";

const ARCHETYPES = ["All", "Handler", "Cutter", "D-line specialist", "Hybrid"];

export default function Leaderboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [archetype, setArchetype] = useState("All");
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState("grade");
  const [sortDir, setSortDir] = useState("desc");

  useEffect(() => {
    fetchLeaderboard().then(setData).catch((err) => setError(err.message));
  }, []);

  const rows = useMemo(() => {
    if (!data) return [];
    let filtered = data.players;
    if (archetype !== "All") {
      filtered = filtered.filter((p) => p.archetype === archetype);
    }
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      filtered = filtered.filter((p) => p.name.toLowerCase().includes(q));
    }
    const sorted = [...filtered].sort((a, b) => {
      const diff = a[sortKey] > b[sortKey] ? 1 : a[sortKey] < b[sortKey] ? -1 : 0;
      return sortDir === "asc" ? diff : -diff;
    });
    return sorted;
  }, [data, archetype, search, sortKey, sortDir]);

  function toggleSort(key) {
    if (key === sortKey) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  if (error) return <p className="error">Couldn't load the leaderboard: {error}</p>;
  if (!data) return <p>Loading…</p>;

  return (
    <div>
      <h1>2026 Season Leaderboard</h1>
      <p className="subtitle">
        Grade is a <strong>role-relative percentile</strong> (0-100) within each player's archetype, not an
        absolute scale — see the profile page for the underlying composite rating and methodology notes.
      </p>

      <div className="controls">
        <input
          type="search"
          placeholder="Search player…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select value={archetype} onChange={(e) => setArchetype(e.target.value)}>
          {ARCHETYPES.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
      </div>

      <table className="leaderboard">
        <thead>
          <tr>
            <th onClick={() => toggleSort("name")}>Player</th>
            <th onClick={() => toggleSort("team")}>Team</th>
            <th onClick={() => toggleSort("archetype")}>Role</th>
            <th onClick={() => toggleSort("games_played")}>GP</th>
            <th onClick={() => toggleSort("composite_rating")}>Rating</th>
            <th onClick={() => toggleSort("grade")}>Grade</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => (
            <tr key={p.id}>
              <td>
                <Link to={`/players/${p.id}`}>{p.name}</Link>
              </td>
              <td>{p.team}</td>
              <td>{p.archetype}</td>
              <td>{p.games_played}</td>
              <td>{p.composite_rating}</td>
              <td>
                <GradeBadge grade={p.grade} tier={p.tier} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && <p>No players match those filters.</p>}
    </div>
  );
}
