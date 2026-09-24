# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A pipeline that pulls UFA (Ultimate Frisbee Association, formerly AUDL)
play-by-play data and turns it into a player-game dataset, with the
eventual goal of a trained player-performance model and a public
leaderboard site. Full plan: `Plans/UFA_Analysis.md` (gitignored, local
only — read it directly for scope/sequencing rather than relying on any
summary).

## Repo layout: one package per pipeline phase

Each phase of the pipeline (scraping, cleaning, later modeling) is its own
top-level folder with its own installable Python package — not one shared
package for the whole repo:

```
Scraping/
  pyproject.toml        # package "ufa-scraping"
  src/ufa_scraping/      # reusable fetch logic
  scripts/                # CLI entry points
Cleaning/
  pyproject.toml        # package "ufa-cleaning"
  src/ufa_cleaning/      # reusable parsing logic
  scripts/                # CLI entry points
  DATA_DICTIONARY.md    # column-by-column docs for player_game.parquet
EDA/
  pyproject.toml        # package "ufa-eda"
  src/ufa_eda/            # reusable aggregation/clustering logic
  notebooks/              # exploratory notebooks (no scripts/ — not CLI tools)
Modeling/
  pyproject.toml        # package "ufa-modeling"
  src/ufa_modeling/       # target definition, features, models, site data export
  scripts/                # CLI entry points, incl. export_site_data.py
  notebooks/              # phase3/4/5 notebooks
Site/                   # React (Vite) app — not a Python package
  public/data/            # leaderboard.json + players/*.json (written by export_site_data.py)
  src/                    # pages/, components/, api.js
data/
  raw/<season>/          # raw per-game JSON + schedule.json (gitignored)
  processed/              # player_game.parquet etc. (gitignored)
```

Each phase gets its own `pyproject.toml` (src layout, `where = ["src"]`)
and is installed editable independently (`pip install -e ./Scraping`).
When adding a new phase (e.g. modeling), follow the same pattern: its own
folder, its own `pyproject.toml`, its own `src/<package>/` + `scripts/`.

**Code convention: scripts only contain a `main()` (plus argparse setup) and
call into the phase's `src/` package for everything else.** All real logic —
parsing, fetching, stats computation — belongs in `src/<package>/`, not in
`scripts/`. This keeps logic importable (by other scripts, or later by
notebooks) instead of locked inside a CLI entry point.

`data/` is gitignored entirely — UFA's stats terms of use for redistributing
raw data haven't been confirmed, so raw and processed data stay local only.
`Site/public/data/` (the Phase 6 derived-data export) is gitignored too, for
the same open ToS question — don't force-add it or un-ignore it without
checking with the user first. `.github/workflows/deploy-site.yml` only
deploys on a manual `workflow_dispatch` run on `main` (pushes are
build-only), so don't loosen that trigger or trigger a deploy without the
user either.

## Environment

Python **3.13**, not 3.14 — pandas' prebuilt wheel for 3.14 gets blocked by
a Windows Application Control policy on this machine, and no source build
works either (missing MSVC toolchain). Python 3.13 has no such issue.

**`scipy` (and therefore `scikit-learn`) is unusable on this machine** — the
same Application Control policy blocks scipy's compiled LAPACK/BLAS
binaries specifically, tried across two scipy versions, even on Python
3.13 where numpy/pandas/matplotlib/seaborn are fine. Don't add
`scikit-learn`/`scipy` as a dependency; hand-roll the numpy equivalent
instead (e.g. `EDA/src/ufa_eda/archetypes.py`'s from-scratch k-means,
`Modeling/src/ufa_modeling/{target,model}.py`'s from-scratch OLS). The
block has also shown flaky behavior — the same import failed once, then
succeeded moments later with no code change — so retry once before
concluding a *new* compiled dependency is blocked, but don't expect scipy
itself to start working.

**`xgboost` and `torch` DO work on this machine** (checked in Phase 5) —
the block doesn't extend to them. **`shap` does not** — it imports
`scipy._lib._uarray` internally and hits the same failure as scipy itself.
Use XGBoost's own built-in Tree SHAP (`booster.predict(x, pred_contribs=True)`)
for explainability instead of the `shap` package.

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows
pip install -e ./Scraping -e ./Cleaning -e ./EDA -e ./Modeling
```

Re-run the relevant `pip install -e ./<Phase>` after adding a new phase
folder or changing its `pyproject.toml`.

## Common commands

Fetch raw game data for a season (idempotent — skips already-downloaded games):

```bash
python Scraping/scripts/fetch_games.py --seasons 2026
```

Build the clean player-game table from fetched raw data:

```bash
python Cleaning/scripts/build_player_game_table.py --seasons 2026
```

This also validates itself: it rolls player rows back up to team level and
diffs against the pre-aggregated totals already present in the raw JSON,
printing a mean-absolute-error summary per stat and writing any mismatches
to `data/processed/validation_discrepancies.csv`. It also writes
`data/processed/game_score.parquet` (one row per team per game with its
final score, taken straight off the raw JSON rather than summed from
events — see `Cleaning/DATA_DICTIONARY.md`).

Re-execute the Phase 2-5 notebooks in place after changing
`player_game.parquet`, `ufa_eda`, or `ufa_modeling` (Phase 5 also rewrites
`data/processed/player_ratings.parquet`):

```bash
jupyter nbconvert --to notebook --execute --inplace EDA/notebooks/phase2_eda.ipynb
jupyter nbconvert --to notebook --execute --inplace Modeling/notebooks/phase3_target_definition.ipynb
jupyter nbconvert --to notebook --execute --inplace Modeling/notebooks/phase4_features.ipynb
jupyter nbconvert --to notebook --execute --inplace Modeling/notebooks/phase5_modeling.ipynb
```

Export the static JSON the `Site/` React app reads, then run/build it:

```bash
python Modeling/scripts/export_site_data.py    # writes Site/public/data/
cd Site && npm install && npm run dev          # or: npm run build && npm run preview
```

See "Publishing the site" in `README.md` before committing `Site/public/data/`
or pushing `Site/` changes — the UFA ToS open question applies to the
derived per-player export too, not just raw data.

There is no test suite or linter yet; `Site/`'s build step (`npm run build`) is the only build step in the repo.

## Data source and its quirks

UFA's stats backend at `backend.ufastats.com` exposes an undocumented but
stable JSON API. `Scraping` uses the [`audl`](https://github.com/yukikongju/audl)
package as a client for schedule/roster endpoints, plus a direct request
against the per-game endpoint (`stats-pages/game/<game_id>`) for full
play-by-play — every disc touch, with thrower/receiver IDs and coordinates,
not just aggregate box scores.

The play-by-play event stream uses integer type codes (`t` field) that are
**not reliably documented** — the `audl` package's own two internal
reference tables contradict each other on several codes. `Cleaning/src/ufa_cleaning/events.py`
resolves them empirically by cross-checking parsed counts against the
pre-aggregated team totals shipped in the same JSON, and documents that
process and its residual error rate. When adding support for a new stat
derived from the event stream, follow the same approach: verify against the
known aggregate fields before trusting a code's assumed meaning.

Known data gaps (see `Cleaning/DATA_DICTIONARY.md` for the full list): no
stable cross-game player ID (full name used as the key for now), Callahans
aren't distinguished from an ordinary block + goal, at least one game per
season may have no play-by-play at all despite a final score existing
(handled as a skip, not a crash), and the `reg_season` field is `True` for
every 2026 game including the championship — it does **not** actually
distinguish regular season from playoffs despite the name.
