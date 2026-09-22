"""Validation of parsed player-game rows against the pre-aggregated team
totals that ship in each game's raw JSON.
"""

import pandas as pd


def validate_game(game_json: dict, player_df: pd.DataFrame) -> list[dict]:
    """Compare player-row rollups against the game's reported team totals.

    Returns a list of discrepancy dicts (empty if everything reconciles).
    """
    discrepancies = []
    game_id = game_json["game"]["id"]

    for side, team_key in [("tsgHome", "team_season_home"), ("tsgAway", "team_season_away")]:
        tsg = game_json[side]
        team_ext_id = game_json["game"][team_key]["team"]["ext_team_id"]
        team_rows = player_df[player_df["team_ext_id"] == team_ext_id]

        checks = {
            "turnovers": (team_rows["turnovers"].sum(), tsg["turnovers"]),
            "blocks": (team_rows["blocks"].sum(), tsg["blocks"]),
            "completions": (team_rows["completions"].sum(), tsg["completionsNumer"]),
        }
        for stat, (computed, reported) in checks.items():
            if computed != reported:
                discrepancies.append(
                    {
                        "game_id": game_id,
                        "team_ext_id": team_ext_id,
                        "stat": stat,
                        "computed": computed,
                        "reported": reported,
                    }
                )
    return discrepancies


def summarize_discrepancies(all_discrepancies: list[dict], n_team_games: int) -> pd.DataFrame | None:
    """Turn raw discrepancy dicts into a DataFrame with diff/error columns.

    Returns None if there are no discrepancies to summarize.
    """
    if not all_discrepancies:
        return None
    disc_df = pd.DataFrame(all_discrepancies)
    disc_df["diff"] = disc_df["computed"] - disc_df["reported"]
    disc_df["abs_pct_err"] = (disc_df["diff"].abs() / disc_df["reported"].replace(0, pd.NA)) * 100
    return disc_df


def mean_abs_pct_error(disc_df: pd.DataFrame, stat: str, n_team_games: int) -> float:
    """Mean absolute percent error for one stat, averaged over all
    team-games (exact matches, which aren't in disc_df, count as 0 error).
    """
    stat_disc = disc_df[disc_df["stat"] == stat]
    return stat_disc["abs_pct_err"].sum() / n_team_games
