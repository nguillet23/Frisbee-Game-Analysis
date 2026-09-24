import { useEffect, useState } from "react";
import { fetchLeaderboard, fetchPlayer } from "../api.js";
import GradeBadge from "../components/GradeBadge.jsx";

const STAT_LABELS = {
  completion_pct: "Completion %",
  turnovers_per_point: "Turnovers / point",
  blocks_per_point: "Blocks / point",
  goals_per_point: "Goals / point",
  assists_per_point: "Assists / point",
};

// Stats where a *lower* number is the better outcome (only turnovers here)
// — used to color the comparison correctly instead of always treating
// "higher" as better.
const LOWER_IS_BETTER = new Set(["turnovers_per_point"]);

export default function Compare() {
  const [roster, setRoster] = useState([]);
  const [leftId, setLeftId] = useState("");
  const [rightId, setRightId] = useState("");
  const [left, setLeft] = useState(null);
  const [right, setRight] = useState(null);

  useEffect(() => {
    fetchLeaderboard().then((data) => setRoster(data.players));
  }, []);

  useEffect(() => {
    if (leftId) fetchPlayer(leftId).then(setLeft);
    else setLeft(null);
  }, [leftId]);

  useEffect(() => {
    if (rightId) fetchPlayer(rightId).then(setRight);
    else setRight(null);
  }, [rightId]);

  return (
    <div>
      <h1>Compare players</h1>
      <div className="compare-pickers">
        <PlayerPicker roster={roster} value={leftId} onChange={setLeftId} label="Player A" />
        <PlayerPicker roster={roster} value={rightId} onChange={setRightId} label="Player B" />
      </div>

      {left && right ? (
        <table className="compare-table">
          <thead>
            <tr>
              <th></th>
              <th>{left.name}</th>
              <th>{right.name}</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th>Team</th>
              <td>{left.team}</td>
              <td>{right.team}</td>
            </tr>
            <tr>
              <th>Role</th>
              <td>{left.archetype}</td>
              <td>{right.archetype}</td>
            </tr>
            <tr>
              <th>Games played</th>
              <td>{left.games_played}</td>
              <td>{right.games_played}</td>
            </tr>
            <tr>
              <th>Rating</th>
              <td>{left.composite_rating}</td>
              <td>{right.composite_rating}</td>
            </tr>
            <tr>
              <th>Grade</th>
              <td>
                <GradeBadge grade={left.grade} tier={left.tier} />
              </td>
              <td>
                <GradeBadge grade={right.grade} tier={right.tier} />
              </td>
            </tr>
            {Object.entries(STAT_LABELS).map(([key, label]) => (
              <tr key={key}>
                <th>{label}</th>
                <td className={cellClass(left.season_stats[key], right.season_stats[key], key)}>
                  {left.season_stats[key]}
                </td>
                <td className={cellClass(right.season_stats[key], left.season_stats[key], key)}>
                  {right.season_stats[key]}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="subtitle">Pick two players to compare their season stats side by side.</p>
      )}
      {left && right && left.archetype !== right.archetype && (
        <p className="subtitle">
          Note: these two players have different roles ({left.archetype} vs. {right.archetype}) — grades are
          role-relative percentiles, so comparing them directly is comparing each to their own peer group, not
          to each other on an absolute scale.
        </p>
      )}
    </div>
  );
}

function cellClass(value, other, statKey) {
  if (value === other) return "";
  const better = LOWER_IS_BETTER.has(statKey) ? value < other : value > other;
  return better ? "compare-higher" : "compare-lower";
}

function PlayerPicker({ roster, value, onChange, label }) {
  return (
    <label className="compare-picker">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Select a player…</option>
        {roster.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name} ({p.team})
          </option>
        ))}
      </select>
    </label>
  );
}
