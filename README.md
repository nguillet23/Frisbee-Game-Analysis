# UFA Advanced Stats & Player Performance Model

Advanced-stats pipeline for the Ultimate Frisbee Association (UFA, formerly
AUDL) that goes beyond box-score counting stats (goals, assists, blocks) to
answer: **which players are actually playing well, and why?**

The end goal is a reusable player-game dataset, a trained model that
produces a per-player performance rating with SHAP-based explainability, and
a public leaderboard/profile site built on top of it.

## Status

Early — data acquisition is in progress. Raw play-by-play data for the full
2026 UFA season (144 games, regular season + playoffs) has been pulled
locally. Cleaning, EDA, target definition, and modeling haven't started yet.

## Data source

UFA's stats backend at `backend.ufastats.com` exposes an undocumented but
stable JSON API (used by the official `watchufa.com` stats pages). Rather
than scraping HTML, this project pulls from that API directly, using the
[`audl`](https://github.com/yukikongju/audl) Python package as a client for
schedule/roster endpoints, plus a direct request against the per-game
endpoint for full play-by-play (every disc touch, with thrower/receiver IDs
and coordinates — not just aggregate box scores).

## Project structure

```
Scraping/
  src/ufa_analysis/    reusable data-fetching code (importable package)
  scripts/              CLI entry points, e.g. fetch_games.py
data/raw/<season>/      raw per-game JSON + schedule.json (gitignored)
Plans/                  planning docs (gitignored, local only)
```

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate      # Windows
pip install -e .
```

## Fetching data

```bash
python Scraping/scripts/fetch_games.py --seasons 2026
```

Idempotent — safe to re-run; already-downloaded games are skipped.

## Why not just republish raw stats?

The repo is public, but UFA's stats terms of use for redistributing raw
data haven't been confirmed yet — see open questions before any public
data export ships.
