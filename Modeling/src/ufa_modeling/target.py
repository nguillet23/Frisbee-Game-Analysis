"""Phase 3 target definition: a composite player efficiency rating whose
per-stat weights are *learned* (regression against team scoring outcomes),
not hand-set, per Plans/UFA_Analysis.md Phase 3.

The regression is fit at team-game level: team-level per-point process
stats (turnover/block/goal rate) predicting that team's point differential
in the game. ``completion_pct`` and ``assist_rate`` were tried and dropped —
see ``REGRESSION_FEATURE_COLS`` — because they're near-duplicates of
``turnover_rate`` and ``goal_rate`` respectively at the team-game level,
which made their regression coefficients unstable and sign-flipped. The
fitted weights are then applied to individual players' per-point rates to
produce a composite rating — each player is scored on how much their own
rates, expressed in team-level standard deviations, historically moved
team scoring margin.

No scikit-learn/statsmodels available on this dev machine (see CLAUDE.md),
so the regression is hand-rolled OLS via ``numpy.linalg.lstsq``.
"""

import numpy as np
import pandas as pd

TEAM_COUNT_COLS = [
    "points_played",
    "completions",
    "throw_attempts",
    "turnovers",
    "blocks",
    "assists",
    "goals",
]

REGRESSION_FEATURE_COLS = ["turnover_rate", "block_rate", "goal_rate"]


def aggregate_team_game(player_game: pd.DataFrame, game_score: pd.DataFrame) -> pd.DataFrame:
    """Roll player_game rows up to one row per team per game, joined to the
    authoritative point differential, with per-point rate features attached.

    Rate features all divide by the team's summed ``points_played`` (across
    every player on that team-game) — the *same* denominator basis
    ``ufa_eda.archetypes.compute_rate_features`` uses per player. That
    makes a team-game rate literally a points-played-weighted average of
    its players' individual rates, so team- and player-level rates end up
    in the same units and scale — required for ``composite_rating`` to
    apply team-fitted weights to player-level rates correctly. (An earlier
    version divided by total game points instead, which put team rates
    ~7x larger than player rates — one event per point, but ~7 players on
    the field each point — and silently broke every player's composite
    score.) Point differential itself still comes from ``game_score``
    (the authoritative final score) rather than summed goals, which carry
    ~1% parsing noise (see Cleaning/DATA_DICTIONARY.md).
    """
    grouped = player_game.groupby(["season", "game_id", "team_ext_id"])
    team = grouped[TEAM_COUNT_COLS].sum().reset_index()

    team = team.merge(
        game_score[["season", "game_id", "team_ext_id", "point_differential"]],
        on=["season", "game_id", "team_ext_id"],
        how="inner",
    )

    team["completion_pct"] = team["completions"] / team["throw_attempts"]
    team["turnover_rate"] = team["turnovers"] / team["points_played"]
    team["block_rate"] = team["blocks"] / team["points_played"]
    team["assist_rate"] = team["assists"] / team["points_played"]
    team["goal_rate"] = team["goals"] / team["points_played"]

    return team


def fit_ols(
    df: pd.DataFrame,
    feature_cols: list[str] = REGRESSION_FEATURE_COLS,
    target_col: str = "point_differential",
) -> dict:
    """Standardized OLS: z-score the features, solve with an intercept via
    ``np.linalg.lstsq``, so coefficients read as "point-differential impact
    per SD of that stat" and are comparable to each other despite the
    features living on different natural scales.

    Returns a dict with the fitted weights, intercept, R^2, and the feature
    means/stds needed to standardize new data (e.g. player-level rates) the
    same way before applying the weights — see ``composite_rating``.
    """
    clean = df.dropna(subset=feature_cols + [target_col])
    x_raw = clean[feature_cols].to_numpy(dtype=float)
    y = clean[target_col].to_numpy(dtype=float)

    mean = x_raw.mean(axis=0)
    std = x_raw.std(axis=0)
    x = (x_raw - mean) / std

    design = np.column_stack([np.ones(len(x)), x])
    coefs, *_ = np.linalg.lstsq(design, y, rcond=None)
    intercept, weights = coefs[0], coefs[1:]

    y_pred = design @ coefs
    ss_res = float(((y - y_pred) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())

    return {
        "feature_cols": list(feature_cols),
        "weights": dict(zip(feature_cols, weights.tolist())),
        "intercept": float(intercept),
        "feature_mean": dict(zip(feature_cols, mean.tolist())),
        "feature_std": dict(zip(feature_cols, std.tolist())),
        "r_squared": 1.0 - ss_res / ss_tot,
        "n_obs": int(len(clean)),
    }


def composite_rating(
    rate_df: pd.DataFrame, fit: dict, feature_map: dict[str, str] | None = None
) -> pd.Series:
    """Apply a fitted ``fit_ols`` result to a rate table (team- or
    player-level) to produce a composite rating.

    Each feature is standardized using the *team-level regression's*
    mean/std (not re-fit on ``rate_df``), so a player's rate is expressed in
    the same units as the team-level regression ("how many team-level SDs
    above/below average"), then combined with the fitted weights.

    ``feature_map`` lets the caller's column names differ from the
    regression's ``feature_cols`` (e.g. player-level tables from
    ``ufa_eda.archetypes.compute_rate_features`` name things
    ``*_per_point`` instead of ``*_rate``) — maps each fitted feature name
    to the column to read from ``rate_df``. Defaults to identity.
    """
    feature_map = feature_map or {f: f for f in fit["feature_cols"]}
    total = pd.Series(0.0, index=rate_df.index)
    for feature in fit["feature_cols"]:
        col = feature_map[feature]
        z = (rate_df[col] - fit["feature_mean"][feature]) / fit["feature_std"][feature]
        total = total + fit["weights"][feature] * z
    return total
