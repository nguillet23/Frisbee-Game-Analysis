"""CLI to fetch raw UFA game data for one or more seasons.

Idempotent: skips games already downloaded, so it's safe to re-run to pick
up new games or retry failures.

Usage:
    python Scraping/scripts/fetch_games.py --seasons 2026
    python Scraping/scripts/fetch_games.py --seasons 2012 2013 2014
"""

import argparse

import requests
from tqdm import tqdm

from ufa_scraping.fetch import RAW_DIR, fetch_game, fetch_season_schedule


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seasons", type=int, nargs="+", required=True)
    args = parser.parse_args()

    for season in args.seasons:
        print(f"Season {season}: fetching schedule...")
        game_ids = fetch_season_schedule(season)
        season_dir = RAW_DIR / str(season)

        fetched, skipped, failed = 0, 0, 0
        for game_id in tqdm(game_ids, desc=f"{season} games"):
            try:
                if fetch_game(game_id, season_dir):
                    fetched += 1
                else:
                    skipped += 1
            except requests.RequestException as e:
                failed += 1
                tqdm.write(f"  FAILED {game_id}: {e}")

        print(
            f"Season {season}: {fetched} fetched, {skipped} already cached, "
            f"{failed} failed (of {len(game_ids)} total games)"
        )


if __name__ == "__main__":
    main()
