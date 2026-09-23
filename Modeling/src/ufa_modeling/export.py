"""Phase 6 data export: builds the static JSON files the React site reads.

Per Plans/UFA_Analysis.md Phase 6, there's no live backend — GitHub Pages
only serves static files — so the pipeline writes plain JSON that the site
``fetch()``s at runtime: ``Site/public/data/leaderboard.json`` (season
leaderboard) and ``Site/public/data/players/{id}.json`` (one per player,
game log + explainability).

Also makes the Phase 3 grading note's presentation decision, deferred
until now: composite ratings are converted to a **role-relative percentile
grade** (0-100, within archetype), not shown on an absolute scale — a
D-line specialist's raw composite ceiling is structurally lower than a
handler's (see Phase 3/5 findings), so an absolute scale would present
that role gap as if it were a skill gap.
"""

import json
import re
from pathlib import Path

import pandas as pd

from ufa_eda.archetypes import aggregate_player_season, cluster_archetypes, compute_rate_features, label_archetypes
from ufa_modeling.features import build_player_game_features
from ufa_modeling.target import aggregate_team_game, composite_rating, fit_ols

SITE_DATA_DIR = Path(__file__).resolve().parents[3] / "Site" / "public" / "data"

# Percentile-within-archetype cutoffs -> a readable tier label, purely a
# presentation convenience alongside the numeric grade. Cutoffs are
# unvalidated round numbers (no ground truth to calibrate against yet, see
# the plan's open questions) — revisit once more seasons/validation exist.
GRADE_TIERS = [
    (90, "Elite"),
    (70, "Above Average"),
    (40, "Average"),
    (20, "Below Average"),
    (0, "Limited"),
]

FEATURE_MAP = {
    "turnover_rate": "turnovers_per_point",
    "block_rate": "blocks_per_point",
    "goal_rate": "scoring_involvement_per_point",
}


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _tier_for_grade(grade: float) -> str:
    for threshold, label in GRADE_TIERS:
        if grade >= threshold:
            return label
    return GRADE_TIERS[-1][1]


def _with_scoring_involvement(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["scoring_involvement_per_point"] = df["goals_per_point"] + df["assists_per_point"]
    return df


def build_season_ratings(
    player_game: pd.DataFrame, game_score: pd.DataFrame, min_points_played: int = 50
) -> pd.DataFrame:
    """One row per player-season: Phase 3's composite rating, Phase 2's
    archetype, and the role-relative percentile grade/tier described in the
    module docstring. Same ``min_points_played`` floor as Phase 2/3 — the
    leaderboard only covers regular contributors, not every bench appearance.
    """
    season = aggregate_player_season(player_game)
    rates = compute_rate_features(season, min_points_played=min_points_played)
    clustered, centers = cluster_archetypes(rates, random_state=0)
    centers = label_archetypes(centers)
    clustered = clustered.merge(centers[["archetype_label"]], left_on="archetype_cluster", right_index=True)
    clustered = _with_scoring_involvement(clustered)

    team = aggregate_team_game(player_game, game_score)
    fit = fit_ols(team)
    clustered["composite_rating"] = composite_rating(clustered, fit, FEATURE_MAP)

    clustered["grade"] = clustered.groupby("archetype_label")["composite_rating"].rank(pct=True) * 100
    clustered["tier"] = clustered["grade"].apply(_tier_for_grade)
    return clustered


def build_game_log(
    player_game: pd.DataFrame, game_score: pd.DataFrame, player_ratings: pd.DataFrame
) -> pd.DataFrame:
    """Every player-game (not just the ones with a Phase 5 prediction),
    with Phase 3's actual per-game composite rating recomputed for all of
    them, plus Phase 5's ``predicted_rating``/``contrib_*`` columns left-
    joined on where available (``NaN`` for a player's/opponent's early-
    season games with no prior history — see Phase 4/5 findings).
    """
    feats = build_player_game_features(player_game, game_score)
    feats = _with_scoring_involvement(feats)

    team = aggregate_team_game(player_game, game_score)
    fit = fit_ols(team)
    feats["composite_rating_game"] = composite_rating(feats, fit, FEATURE_MAP)

    pred_cols = ["season", "game_id", "player_name", "predicted_rating"]
    pred_cols += [c for c in player_ratings.columns if c.startswith("contrib_") and c != "contrib_bias"]
    return feats.merge(player_ratings[pred_cols], on=["season", "game_id", "player_name"], how="left")


def top_contributors(row: pd.Series, n: int = 3) -> list[dict]:
    """Top ``n`` largest-magnitude ``contrib_*`` values for one game log
    row, as ``{"feature": ..., "value": ...}`` — empty if this game has no
    Phase 5 prediction (no prior history yet)."""
    contrib_cols = [c for c in row.index if c.startswith("contrib_")]
    values = row[contrib_cols].dropna()
    if values.empty:
        return []
    ranked = values.reindex(values.abs().sort_values(ascending=False).index)
    return [
        {"feature": col.removeprefix("contrib_"), "value": round(float(val), 2)}
        for col, val in ranked.head(n).items()
    ]


def write_site_data(
    player_game: pd.DataFrame,
    game_score: pd.DataFrame,
    player_ratings: pd.DataFrame,
    out_dir: Path = SITE_DATA_DIR,
) -> int:
    """Write ``leaderboard.json`` and one ``players/{id}.json`` per player
    to ``out_dir`` (default: the React site's ``public/data``). Returns the
    number of players written.
    """
    season_ratings = build_season_ratings(player_game, game_score)
    game_log = build_game_log(player_game, game_score, player_ratings)

    players_dir = out_dir / "players"
    players_dir.mkdir(parents=True, exist_ok=True)

    leaderboard_rows = []
    for _, row in season_ratings.sort_values("composite_rating", ascending=False).iterrows():
        player_id = f"{int(row['season'])}-{slugify(row['player_name'])}"
        leaderboard_rows.append(
            {
                "id": player_id,
                "name": row["player_name"],
                "season": int(row["season"]),
                "team": row["team_ext_id"],
                "archetype": row["archetype_label"],
                "games_played": int(row["games_played"]),
                "composite_rating": round(float(row["composite_rating"]), 1),
                "grade": round(float(row["grade"])),
                "tier": row["tier"],
            }
        )

    season = int(player_game["season"].max())
    with open(out_dir / "leaderboard.json", "w", encoding="utf-8") as f:
        json.dump({"season": season, "players": leaderboard_rows}, f, indent=2)

    for _, srow in season_ratings.iterrows():
        player_id = f"{int(srow['season'])}-{slugify(srow['player_name'])}"
        games = game_log[
            (game_log["player_name"] == srow["player_name"]) & (game_log["season"] == srow["season"])
        ].sort_values("start_timestamp")

        games_out = []
        for _, grow in games.iterrows():
            has_prediction = pd.notna(grow["predicted_rating"])
            games_out.append(
                {
                    "game_id": int(grow["game_id"]),
                    "date": grow["start_timestamp"].strftime("%Y-%m-%d"),
                    "opponent": grow["opponent_team_ext_id"],
                    "is_home": bool(grow["is_home"]),
                    "points_played": int(grow["points_played"]),
                    "actual_rating": round(float(grow["composite_rating_game"]), 1),
                    "predicted_rating": round(float(grow["predicted_rating"]), 1) if has_prediction else None,
                    "top_contributors": top_contributors(grow) if has_prediction else [],
                }
            )

        profile = {
            "id": player_id,
            "name": srow["player_name"],
            "season": int(srow["season"]),
            "team": srow["team_ext_id"],
            "archetype": srow["archetype_label"],
            "games_played": int(srow["games_played"]),
            "composite_rating": round(float(srow["composite_rating"]), 1),
            "grade": round(float(srow["grade"])),
            "tier": srow["tier"],
            "season_stats": {
                "completion_pct": round(float(srow["completion_pct"]), 3),
                "turnovers_per_point": round(float(srow["turnovers_per_point"]), 3),
                "blocks_per_point": round(float(srow["blocks_per_point"]), 3),
                "goals_per_point": round(float(srow["goals_per_point"]), 3),
                "assists_per_point": round(float(srow["assists_per_point"]), 3),
            },
            "games": games_out,
        }
        with open(players_dir / f"{player_id}.json", "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2)

    return len(leaderboard_rows)
