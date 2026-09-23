# UFA Advanced Stats & Player Performance Model

Advanced-stats pipeline for the Ultimate Frisbee Association (UFA, formerly
AUDL) that goes beyond box-score counting stats (goals, assists, blocks) to
answer: **which players are actually playing well, and why?**

The end goal is a reusable player-game dataset, a trained model that
produces a per-player performance rating with SHAP-based explainability, and
a public leaderboard/profile site built on top of it.

## Status

Raw play-by-play data for the full 2026 UFA season (144 games, regular
season + playoffs) has been fetched and parsed into a clean player-game
table, explored in Phase 2 EDA (player archetypes via clustering), and
Phase 3 has defined a composite player-efficiency target with weights
learned by regression against team scoring outcomes. Feature engineering
and modeling (Phases 4-5) haven't started yet. See `Plans/UFA_Analysis.md`
for the full plan and findings per phase.

## Data source

UFA's stats backend at `backend.ufastats.com` exposes an undocumented but
stable JSON API (used by the official `watchufa.com` stats pages). Rather
than scraping HTML, this project pulls from that API directly, using the
[`audl`](https://github.com/yukikongju/audl) Python package as a client for
schedule/roster endpoints, plus a direct request against the per-game
endpoint for full play-by-play (every disc touch, with thrower/receiver IDs
and coordinates — not just aggregate box scores). The play-by-play event
codes aren't reliably documented anywhere, so they were resolved empirically
by cross-checking against the pre-aggregated team totals that ship in the
same JSON — see `Cleaning/src/ufa_cleaning/events.py`.

## Project structure

Each pipeline phase is its own installable Python package, not one shared
package for the whole repo:

```
Scraping/
  pyproject.toml        package "ufa-scraping"
  src/ufa_scraping/       reusable fetch logic
  scripts/                 CLI entry points, e.g. fetch_games.py
Cleaning/
  pyproject.toml        package "ufa-cleaning"
  src/ufa_cleaning/       reusable parsing/validation logic
  scripts/                 CLI entry points, e.g. build_player_game_table.py
  DATA_DICTIONARY.md      column-by-column docs for player_game.parquet
EDA/
  pyproject.toml        package "ufa-eda"
  src/ufa_eda/             player-season aggregation, rate features, archetype clustering
  notebooks/               phase2_eda.ipynb
Modeling/
  pyproject.toml        package "ufa-modeling"
  src/ufa_modeling/        target definition (composite rating regression), later: models
  notebooks/               phase3_target_definition.ipynb
data/
  raw/<season>/            raw per-game JSON + schedule.json (gitignored)
  processed/                player_game.parquet, game_score.parquet, etc. (gitignored)
Plans/                    planning docs (gitignored, local only)
```

Scripts only contain a `main()`; all reusable logic lives in each phase's
`src/` package. See `CLAUDE.md` for the full set of repo conventions.

## Setup

Requires **Python 3.13** (3.14's pandas wheel hits a Windows Application
Control policy block on at least one dev machine used on this project).

```bash
python -m venv .venv
.venv/Scripts/activate      # Windows
pip install -e ./Scraping -e ./Cleaning -e ./EDA -e ./Modeling
```

## Running the pipeline

Fetch raw game data for a season (idempotent — safe to re-run,
already-downloaded games are skipped):

```bash
python Scraping/scripts/fetch_games.py --seasons 2026
```

Parse the raw JSON into the clean player-game table
(`data/processed/player_game.parquet`), with built-in validation against
each game's own reported team totals:

```bash
python Cleaning/scripts/build_player_game_table.py --seasons 2026
```

This also writes `data/processed/game_score.parquet` (each team's final
score per game) and validates itself against the raw JSON's own reported
team totals.

Re-execute the Phase 2 EDA or Phase 3 target-definition notebooks in place
after changing the upstream data or the relevant package:

```bash
jupyter nbconvert --to notebook --execute --inplace EDA/notebooks/phase2_eda.ipynb
jupyter nbconvert --to notebook --execute --inplace Modeling/notebooks/phase3_target_definition.ipynb
```

## Why not just republish raw stats?

The repo is public, but UFA's stats terms of use for redistributing raw
data haven't been confirmed yet — see open questions before any public
data export ships.
