"""Phase 4 feature engineering: builds a player-game feature table from
``player_game.parquet`` + ``game_score.parquet`` for Phase 5 modeling.

Per Plans/UFA_Analysis.md Phase 4, this covers:
- per-point rate stats (not raw totals), at player-game grain
- role/archetype (Phase 2 clustering) as a categorical feature
- rolling/season-to-date form vs. season-long averages
- opponent-adjusted stats (opponent strength, leave-one-out prior games only)
- team context (O-line share, team pace)

All "prior form" features (rolling form, season-to-date form, opponent
strength) are computed using only games strictly before the current one,
ordered by ``start_timestamp`` — never the current or a future game — so
they can be used to predict an outcome for the current game without
leaking information from it.
"""

import numpy as np
import pandas as pd

from ufa_eda.archetypes import aggregate_player_season, cluster_archetypes, compute_rate_features

PER_POINT_RATE_COLS = [
    "completion_pct",
    "turnovers_per_point",
    "blocks_per_point",
    "goals_per_point",
    "assists_per_point",
    "throws_per_point",
    "receptions_per_point",
]

ROLLING_WINDOW_GAMES = 3


def add_game_level_rates(player_game: pd.DataFrame) -> pd.DataFrame:
    """Add per-*game* per-point rate columns (same formulas/names as
    ``ufa_eda.archetypes.compute_rate_features``, but per game rather than
    summed to player-season — no usage floor is applied here since Phase 4
    features are meant to cover every player-game row; low-usage rows are
    just noisier, not dropped).
    """
    df = player_game.copy()
    df["throws_per_point"] = df["throw_attempts"] / df["points_played"]
    df["completions_per_point"] = df["completions"] / df["points_played"]
    df["receptions_per_point"] = df["receptions"] / df["points_played"]
    df["goals_per_point"] = df["goals"] / df["points_played"]
    df["assists_per_point"] = df["assists"] / df["points_played"]
    df["blocks_per_point"] = df["blocks"] / df["points_played"]
    df["turnovers_per_point"] = df["turnovers"] / df["points_played"]
    df["o_line_share"] = df["o_points_played"] / df["points_played"]
    df["completion_pct"] = df["completions"] / df["throw_attempts"].replace(0, np.nan)
    return df


def add_opponent(player_game: pd.DataFrame, game_score: pd.DataFrame) -> pd.DataFrame:
    """Attach ``opponent_team_ext_id`` and ``start_timestamp`` to each
    player-game row, by looking up the other team in the same
    (season, game_id) from ``game_score``.
    """
    teams = game_score[["season", "game_id", "team_ext_id", "start_timestamp"]]
    pairs = teams.merge(teams, on=["season", "game_id"], suffixes=("", "_opp"))
    pairs = pairs[pairs["team_ext_id"] != pairs["team_ext_id_opp"]]
    pairs = pairs.rename(columns={"team_ext_id_opp": "opponent_team_ext_id"}).drop(
        columns="start_timestamp_opp"
    )

    df = player_game.merge(pairs, on=["season", "game_id", "team_ext_id"], how="inner")
    df["start_timestamp"] = pd.to_datetime(df["start_timestamp"])
    return df


def add_team_context(df: pd.DataFrame, game_score: pd.DataFrame) -> pd.DataFrame:
    """Attach team-context columns: O-line share (already per-row from
    ``add_game_level_rates``) and team pace (total points played in the
    game, from the authoritative final score — higher pace means more
    total possessions for both teams to accumulate stats in).
    """
    pace = game_score[["season", "game_id", "team_ext_id"]].copy()
    pace["team_pace"] = game_score["team_score"] + game_score["opponent_score"]
    return df.merge(pace, on=["season", "game_id", "team_ext_id"], how="left")


def _label_archetype(center: pd.Series, all_centers: pd.DataFrame) -> str:
    """Heuristic human-readable label for a k-means cluster center, based on
    which discovered feature stands out most relative to the other
    clusters — see EDA/notebooks/phase2_eda.ipynb for the eyeballed version
    this codifies. Not a rigorous taxonomy, just a readability aid.
    """
    if center["blocks_per_point"] == all_centers["blocks_per_point"].max():
        return "D-line specialist"
    if center["throws_per_point"] == all_centers["throws_per_point"].max():
        return "Handler"
    if center["goals_per_point"] == all_centers["goals_per_point"].max():
        return "Cutter"
    return "Hybrid"


def add_archetype(player_game: pd.DataFrame, min_points_played: int = 50) -> pd.DataFrame:
    """Attach a per-player-season archetype (Phase 2 clustering) to every
    game row for that player-season. Players below ``min_points_played``
    for the season (same floor Phase 2 used) get ``NaN`` archetype columns
    — there isn't enough season signal to cluster them reliably.
    """
    season = aggregate_player_season(player_game)
    rates = compute_rate_features(season, min_points_played=min_points_played)
    clustered, centers = cluster_archetypes(rates, random_state=0)
    centers["archetype_label"] = [_label_archetype(centers.loc[i], centers) for i in centers.index]

    archetype_lookup = clustered[["player_name", "season", "archetype_cluster"]].merge(
        centers[["archetype_label"]], left_on="archetype_cluster", right_index=True
    )
    return player_game.merge(archetype_lookup, on=["player_name", "season"], how="left")


def _prior_only(group: pd.DataFrame, cols: list[str], window: int) -> pd.DataFrame:
    """For one player/team's games (already sorted by ``start_timestamp``),
    compute rolling and season-to-date means using only strictly earlier
    games — ``shift(1)`` before rolling/expanding excludes the current row.
    """
    shifted = group[cols].shift(1)
    rolling = shifted.rolling(window, min_periods=1).mean()
    rolling.columns = [f"{c}_last{window}" for c in cols]
    season_to_date = shifted.expanding(min_periods=1).mean()
    season_to_date.columns = [f"{c}_season_to_date" for c in cols]
    return pd.concat([rolling, season_to_date], axis=1)


def add_rolling_form(
    df: pd.DataFrame, rate_cols: list[str] = PER_POINT_RATE_COLS, window: int = ROLLING_WINDOW_GAMES
) -> pd.DataFrame:
    """Add trailing-``window``-game and season-to-date average rate
    features per player, computed from games strictly before the current
    one (see ``_prior_only``). A player's first game of a season has no
    prior data and gets ``NaN`` for all of these — expected, not a bug.
    """
    df = df.sort_values(["player_name", "season", "start_timestamp"])
    form = df.groupby(["player_name", "season"], group_keys=False).apply(
        lambda g: _prior_only(g, rate_cols, window)
    )
    return pd.concat([df, form], axis=1)


def add_opponent_strength(df: pd.DataFrame, game_score: pd.DataFrame) -> pd.DataFrame:
    """Add ``opponent_strength``: the opponent's average point differential
    over their games strictly before this one this season (prior-only, same
    leakage-safety rule as ``add_rolling_form``). A team's own first game(s)
    of the season leave their opponents with less (or no) prior history, so
    early-season rows have more ``NaN``/noisy values here — expected.
    """
    gs = game_score.sort_values(["team_ext_id", "season", "start_timestamp"]).copy()
    gs["prior_avg_differential"] = gs.groupby(["team_ext_id", "season"])["point_differential"].transform(
        lambda s: s.shift(1).expanding(min_periods=1).mean()
    )
    strength = gs[["season", "game_id", "team_ext_id", "prior_avg_differential"]].rename(
        columns={"team_ext_id": "opponent_team_ext_id", "prior_avg_differential": "opponent_strength"}
    )
    return df.merge(strength, on=["season", "game_id", "opponent_team_ext_id"], how="left")


def build_player_game_features(
    player_game: pd.DataFrame, game_score: pd.DataFrame, min_points_played: int = 50
) -> pd.DataFrame:
    """Orchestrate the full Phase 4 feature pipeline into one player-game
    feature table. See module docstring for what each piece covers.
    """
    df = add_game_level_rates(player_game)
    df = add_opponent(df, game_score)
    df = add_team_context(df, game_score)
    df = add_archetype(df, min_points_played=min_points_played)
    df = add_rolling_form(df)
    df = add_opponent_strength(df, game_score)
    return df
