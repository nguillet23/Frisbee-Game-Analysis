// Data access layer: fetches the static JSON exported by
// Modeling/scripts/export_site_data.py (see Plans/UFA_Analysis.md Phase 6)
// — no backend, just plain fetch() against files under public/data.
//
// `import.meta.env.BASE_URL` matches vite.config.js's `base` option, so
// this resolves correctly both in dev (served at "/") and in a built site
// deployed under a GitHub Pages project subpath.

const DATA_URL = `${import.meta.env.BASE_URL}data`;

export async function fetchLeaderboard() {
  const res = await fetch(`${DATA_URL}/leaderboard.json`);
  if (!res.ok) throw new Error(`Failed to load leaderboard.json (${res.status})`);
  return res.json();
}

export async function fetchPlayer(id) {
  const res = await fetch(`${DATA_URL}/players/${id}.json`);
  if (!res.ok) throw new Error(`Failed to load player "${id}" (${res.status})`);
  return res.json();
}
