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
table, explored in Phase 2 EDA (player archetypes via clustering), Phase 3
has defined a composite player-efficiency target with weights learned by
regression against team scoring outcomes, Phase 4 built the player-game
feature table (rates, archetype, rolling form, opponent strength), and
Phase 5 has trained and compared a baseline regression, an XGBoost model
(with built-in Tree SHAP explainability), and a PyTorch comparison model
that predict a player's rating for a game *before it happens*, and Phase 6
has built a React/Vite leaderboard/profile/comparison site reading a static
JSON export, with a GitHub Actions workflow to deploy it to GitHub Pages.
**The site has been built and tested locally only — its data export is
gitignored and deploys are manual-only, so it is not published** (see
"Publishing the site" below for why). See `Plans/UFA_Analysis.md` for the full plan and findings
per phase — note Phase 5's R² ≈ 0.35 and lack of confirmed All-Star ground
truth mean the model is a directional signal, not an authoritative grade,
at this stage.

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
  src/ufa_modeling/        target definition, feature engineering, models (OLS/XGBoost/PyTorch)
  notebooks/               phase3_target_definition.ipynb, phase4_features.ipynb, phase5_modeling.ipynb
data/
  raw/<season>/            raw per-game JSON + schedule.json (gitignored)
  processed/                player_game.parquet, game_score.parquet, player_ratings.parquet, etc. (gitignored)
Site/                     React (Vite) app — leaderboard, player profile, comparison tool
  public/data/              leaderboard.json + players/*.json (written by export_site_data.py)
  src/                      pages/, components/, api.js (fetches the static JSON)
Plans/                    planning docs (gitignored, local only)
.github/workflows/        deploy-site.yml — builds Site/ on every branch push (smoke test), deploys to GitHub Pages only from main
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

Re-execute the Phase 2-5 notebooks in place after changing the upstream
data or the relevant package (Phase 5 also rewrites
`data/processed/player_ratings.parquet`):

```bash
jupyter nbconvert --to notebook --execute --inplace EDA/notebooks/phase2_eda.ipynb
jupyter nbconvert --to notebook --execute --inplace Modeling/notebooks/phase3_target_definition.ipynb
jupyter nbconvert --to notebook --execute --inplace Modeling/notebooks/phase4_features.ipynb
jupyter nbconvert --to notebook --execute --inplace Modeling/notebooks/phase5_modeling.ipynb
```

## The site (Phase 6)

Export the static JSON the site reads (writes `Site/public/data/`):

```bash
python Modeling/scripts/export_site_data.py
```

Run it locally:

```bash
cd Site
npm install
npm run dev
```

Or build the static output that GitHub Pages would serve:

```bash
cd Site
npm run build      # writes Site/dist
npm run preview    # serve that build locally to sanity-check it
```

`.github/workflows/deploy-site.yml` builds `Site/` on **every branch push**
that touches it — a build-only smoke test, so a broken site is caught on a
feature branch, not just when it lands on `main`. Pushes never deploy: it
only produces a Pages artifact and deploys via `actions/deploy-pages` when
run **manually** on `main` (Actions → "Deploy site to GitHub Pages" → Run
workflow). It builds from whatever `Site/public/data/*.json` is committed;
it does not rerun the Python pipeline. It needs GitHub Pages enabled
(Settings → Pages → source "GitHub Actions") before it can deploy anything.

## Publishing the site

The repo is public, but UFA's stats terms of use for redistributing raw
*or derived* data haven't been confirmed yet — see open questions in
`Plans/UFA_Analysis.md`. So `Site/public/data/` is **gitignored** (the
export stays local) and the deploy workflow is **manual-only**: merging
code to `main` can't publish UFA-derived player stats by accident. Once the
ToS question is resolved (or the risk is consciously accepted):

1. Remove `/Site/public/data/` from `.gitignore`, then regenerate and commit
   the export (`python Modeling/scripts/export_site_data.py`).
2. Enable GitHub Pages (Settings → Pages → source "GitHub Actions").
3. Run the deploy workflow manually on `main`.
