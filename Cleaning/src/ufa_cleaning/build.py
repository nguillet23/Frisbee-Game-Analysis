"""Orchestration for building the player_game table from raw game JSON.

Kept import-safe (no argument parsing, no top-level side effects) so
``Cleaning/scripts/build_player_game_table.py`` stays a thin CLI wrapper.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from ufa_cleaning.parse_game import parse_game, parse_game_score
from ufa_cleaning.validate import mean_abs_pct_error, summarize_discrepancies, validate_game

RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"
PROCESSED_DIR = Path(__file__).resolve().parents[3] / "data" / "processed"


@dataclass
class BuildResult:
    player_game: pd.DataFrame
    out_path: Path
    game_score: pd.DataFrame
    game_score_path: Path
    n_games: int
    n_team_games: int
    skipped_games: list[int]
    discrepancies: pd.DataFrame | None
    discrepancies_path: Path | None


def build_player_game_table(seasons: list[int]) -> BuildResult:
    """Parse every raw game JSON for the given seasons into player-game
    rows, validate each game against its own reported team totals, and
    write both the combined table and the discrepancy list to disk.

    Also writes ``game_score.parquet`` (one row per team per game with its
    final score) alongside it — this comes straight off ``game_json["game"]``
    rather than being summed from parsed events, so it's available even for
    the one game with no play-by-play at all (see Cleaning/DATA_DICTIONARY.md).
    """
    all_rows = []
    all_score_rows = []
    all_discrepancies = []
    skipped_games = []

    for season in seasons:
        games_dir = RAW_DIR / str(season) / "games"
        game_files = sorted(games_dir.glob("*.json"))

        for path in tqdm(game_files, desc=f"{season} games"):
            game_json = json.loads(path.read_text(encoding="utf-8"))

            for score_row in parse_game_score(game_json):
                score_row["season"] = season
                all_score_rows.append(score_row)

            df = parse_game(game_json)
            if df.empty:
                skipped_games.append(game_json["game"]["id"])
                continue
            df["season"] = season
            all_rows.append(df)
            all_discrepancies.extend(validate_game(game_json, df))

    player_game = pd.concat(all_rows, ignore_index=True)
    game_score = pd.DataFrame(all_score_rows)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PROCESSED_DIR / "player_game.parquet"
    player_game.to_parquet(out_path, index=False)

    game_score_path = PROCESSED_DIR / "game_score.parquet"
    game_score.to_parquet(game_score_path, index=False)

    n_games = player_game["game_id"].nunique()
    n_team_games = n_games * 2

    disc_df = summarize_discrepancies(all_discrepancies, n_team_games)
    disc_path = None
    if disc_df is not None:
        disc_path = PROCESSED_DIR / "validation_discrepancies.csv"
        disc_df.to_csv(disc_path, index=False)

    return BuildResult(
        player_game=player_game,
        out_path=out_path,
        game_score=game_score,
        game_score_path=game_score_path,
        n_games=n_games,
        n_team_games=n_team_games,
        skipped_games=skipped_games,
        discrepancies=disc_df,
        discrepancies_path=disc_path,
    )


def format_summary(result: BuildResult) -> str:
    """Render a BuildResult as the human-readable CLI summary."""
    lines = []
    if result.skipped_games:
        lines.append(
            f"\nSkipped {len(result.skipped_games)} game(s) with no play-by-play data: "
            f"{result.skipped_games}"
        )

    lines.append(
        f"\nWrote {len(result.player_game)} player-game rows from {result.n_games} "
        f"games to {result.out_path}"
    )
    lines.append(
        f"Wrote {len(result.game_score)} team-game score rows to {result.game_score_path}"
    )

    if result.discrepancies is not None:
        lines.append(
            f"\nValidation: player-row rollups vs the game's own reported team "
            f"totals, across {result.n_team_games} team-games:"
        )
        for stat in ["completions", "turnovers", "blocks"]:
            stat_disc = result.discrepancies[result.discrepancies["stat"] == stat]
            err = mean_abs_pct_error(result.discrepancies, stat, result.n_team_games)
            lines.append(
                f"  {stat}: mismatched in {len(stat_disc)}/{result.n_team_games} team-games, "
                f"mean abs error {err:.2f}% (averaged over all team-games, exact matches "
                f"counted as 0)"
            )
        lines.append(f"Full discrepancy list written to {result.discrepancies_path}")
    else:
        lines.append("Validation: every team-game rollup matched its reported totals exactly.")

    return "\n".join(lines)
