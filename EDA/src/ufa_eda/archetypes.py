"""Player-season aggregation, per-point rate features, and archetype
clustering (handler / cutter / hybrid / D-line specialist).

Extracted into an importable package (rather than left inline in the Phase
2 notebook) because Phase 4 feature engineering is expected to reuse the
discovered archetype as a model feature — see Plans/UFA_Analysis.md.
"""

import numpy as np
import pandas as pd

RATE_FEATURE_COLS = [
    "throws_per_point",
    "completions_per_point",
    "receptions_per_point",
    "goals_per_point",
    "assists_per_point",
    "blocks_per_point",
    "turnovers_per_point",
    "o_line_share",
]


def aggregate_player_season(player_game: pd.DataFrame) -> pd.DataFrame:
    """Roll player_game rows up to one row per player per season.

    A player's ``team_ext_id`` is taken as their most common team that
    season (handles mid-season trades without dropping stats from either
    team). Counting stats are summed; ``games_played`` is a row count.
    """
    count_cols = [
        "points_played",
        "o_points_played",
        "d_points_played",
        "pulls",
        "blocks",
        "throw_attempts",
        "completions",
        "receptions",
        "throwaways",
        "stalls",
        "drops",
        "goals",
        "assists",
        "hockey_assists",
        "turnovers",
    ]

    grouped = player_game.groupby(["player_name", "season"])
    season_df = grouped[count_cols].sum()
    season_df["games_played"] = grouped.size()
    season_df["team_ext_id"] = grouped["team_ext_id"].agg(lambda s: s.mode().iat[0])
    return season_df.reset_index()


def compute_rate_features(player_season: pd.DataFrame, min_points_played: int = 50) -> pd.DataFrame:
    """Add per-point rate columns and drop low-usage players (noisy rates).

    ``min_points_played`` defaults to 50 (roughly a third of a full 2026
    season's points for a regular rotation player) purely to keep small
    samples from dominating the rate distributions and cluster fit; revisit
    once more seasons are pulled.
    """
    df = player_season[player_season["points_played"] >= min_points_played].copy()

    df["throws_per_point"] = df["throw_attempts"] / df["points_played"]
    df["completions_per_point"] = df["completions"] / df["points_played"]
    df["receptions_per_point"] = df["receptions"] / df["points_played"]
    df["goals_per_point"] = df["goals"] / df["points_played"]
    df["assists_per_point"] = df["assists"] / df["points_played"]
    df["blocks_per_point"] = df["blocks"] / df["points_played"]
    df["turnovers_per_point"] = df["turnovers"] / df["points_played"]
    df["o_line_share"] = df["o_points_played"] / df["points_played"]
    df["completion_pct"] = df["completions"] / df["throw_attempts"].replace(0, pd.NA)

    return df


def _kmeans_plusplus_init(x: np.ndarray, n_clusters: int, rng: np.random.Generator) -> np.ndarray:
    """k-means++ seeding: pick centers spread out relative to each other."""
    n_samples = x.shape[0]
    centers = np.empty((n_clusters, x.shape[1]))
    centers[0] = x[rng.integers(n_samples)]

    closest_sq_dist = np.sum((x - centers[0]) ** 2, axis=1)
    for i in range(1, n_clusters):
        probs = closest_sq_dist / closest_sq_dist.sum()
        centers[i] = x[rng.choice(n_samples, p=probs)]
        new_sq_dist = np.sum((x - centers[i]) ** 2, axis=1)
        closest_sq_dist = np.minimum(closest_sq_dist, new_sq_dist)

    return centers


def _kmeans_once(x: np.ndarray, n_clusters: int, rng: np.random.Generator, max_iter: int = 300):
    """A single k-means run (Lloyd's algorithm) from a k-means++ seed.

    Returns (labels, centers, inertia).
    """
    centers = _kmeans_plusplus_init(x, n_clusters, rng)

    for _ in range(max_iter):
        dists = ((x[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        labels = dists.argmin(axis=1)

        new_centers = centers.copy()
        for k in range(n_clusters):
            members = x[labels == k]
            if len(members) > 0:
                new_centers[k] = members.mean(axis=0)

        if np.allclose(new_centers, centers):
            centers = new_centers
            break
        centers = new_centers

    dists = ((x[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
    labels = dists.argmin(axis=1)
    inertia = dists[np.arange(len(x)), labels].sum()
    return labels, centers, inertia


def cluster_archetypes(
    rate_df: pd.DataFrame,
    feature_cols: list[str] = RATE_FEATURE_COLS,
    n_clusters: int = 4,
    n_init: int = 10,
    random_state: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """K-means cluster players on standardized per-point rate features.

    Implemented from scratch with numpy (k-means++ init, ``n_init`` random
    restarts keeping the lowest-inertia run) rather than scikit-learn:
    scipy's compiled LAPACK/BLAS binaries are blocked by a Windows
    Application Control policy on at least one dev machine used on this
    project, across every scipy version tried — see ``EDA/pyproject.toml``.

    Returns ``(rate_df with an added 'archetype_cluster' column, cluster
    centers as a DataFrame in the original feature units)`` — centers are
    de-standardized so they're directly interpretable (e.g. "this cluster
    averages 0.6 throws per point"), left for the caller (or the notebook)
    to name based on which stats stand out.
    """
    values = rate_df[feature_cols].to_numpy(dtype=float)
    mean = values.mean(axis=0)
    std = values.std(axis=0)
    x = (values - mean) / std

    rng = np.random.default_rng(random_state)
    best = None
    for _ in range(n_init):
        labels, centers, inertia = _kmeans_once(x, n_clusters, rng)
        if best is None or inertia < best[2]:
            best = (labels, centers, inertia)
    labels, centers, _ = best

    result = rate_df.copy()
    result["archetype_cluster"] = labels

    centers_df = pd.DataFrame(centers * std + mean, columns=feature_cols)
    centers_df.index.name = "archetype_cluster"

    return result, centers_df
