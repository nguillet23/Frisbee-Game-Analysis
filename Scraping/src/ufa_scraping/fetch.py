"""Reusable functions for pulling raw UFA game data from the ufastats.com
backend API and caching it locally under ``data/raw/<season>/``.

Kept import-safe (no side effects, no argument parsing) so both
``Scraping/scripts/fetch_games.py`` and future notebooks can call into it
directly.
"""

import json
from pathlib import Path

import requests
from audl.stats.endpoints.seasonschedule import SeasonSchedule

GAME_JSON_URL = "https://www.backend.ufastats.com/stats-pages/game/{game_id}"
RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"


def fetch_season_schedule(season: int) -> list[str]:
    """Fetch a season's schedule, cache it, and return its game IDs."""
    df = SeasonSchedule(season).get_schedule()
    season_dir = RAW_DIR / str(season)
    season_dir.mkdir(parents=True, exist_ok=True)
    df.to_json(season_dir / "schedule.json", orient="records", indent=2)
    return df["gameID"].tolist()


def fetch_game(game_id: str, season_dir: Path) -> bool:
    """Fetch and save one game's full JSON (box score + play-by-play).

    Returns False without making a request if the game is already cached.
    """
    games_dir = season_dir / "games"
    games_dir.mkdir(parents=True, exist_ok=True)
    out_path = games_dir / f"{game_id}.json"
    if out_path.exists():
        return False

    resp = requests.get(GAME_JSON_URL.format(game_id=game_id), timeout=30)
    resp.raise_for_status()
    out_path.write_text(json.dumps(resp.json()), encoding="utf-8")
    return True
