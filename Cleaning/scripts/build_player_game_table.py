"""CLI to build the clean player_game table from raw fetched game JSON.

Reads every ``data/raw/<season>/games/*.json`` file, parses it into
per-player-game rows, and writes the combined table to
``data/processed/player_game.parquet``.

Also validates each game by rolling player rows back up to the team level
and comparing against the pre-computed ``tsgHome``/``tsgAway`` aggregates
that ship in the raw JSON (turnovers, blocks, completions) — a direct check
on whether the event-parsing logic in ufa_cleaning.parse_game is correct,
and a way to surface incomplete/inconsistent stat tracking per game.

Usage:
    python Cleaning/scripts/build_player_game_table.py --seasons 2026
"""

import argparse

from ufa_cleaning.build import build_player_game_table, format_summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seasons", type=int, nargs="+", required=True)
    args = parser.parse_args()

    result = build_player_game_table(args.seasons)
    print(format_summary(result))


if __name__ == "__main__":
    main()
