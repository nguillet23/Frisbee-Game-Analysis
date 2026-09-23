"""CLI to export the static JSON data the React site (Site/) reads.

Reads data/processed/{player_game,game_score,player_ratings}.parquet and
writes Site/public/data/leaderboard.json + Site/public/data/players/*.json.

Usage:
    python Modeling/scripts/export_site_data.py
"""

import argparse
from pathlib import Path

import pandas as pd

from ufa_modeling.export import SITE_DATA_DIR, write_site_data

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=SITE_DATA_DIR)
    args = parser.parse_args()

    player_game = pd.read_parquet(DATA_DIR / "player_game.parquet")
    game_score = pd.read_parquet(DATA_DIR / "game_score.parquet")
    player_ratings = pd.read_parquet(DATA_DIR / "player_ratings.parquet")

    n_players = write_site_data(player_game, game_score, player_ratings, out_dir=args.out_dir)
    print(f"Wrote leaderboard.json + {n_players} player profiles to {args.out_dir}")


if __name__ == "__main__":
    main()
