"""Parse one raw game JSON (as saved by ``Scraping/scripts/fetch_games.py``)
into a per-player-game row: one row per player who appeared in the game,
with counting stats derived from the play-by-play event stream.
"""

import json
from collections import defaultdict

import pandas as pd

from ufa_cleaning.events import EventType, LINEUP_EVENTS

PLAYER_STAT_FIELDS = [
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
]


def _empty_stats():
    return {field: 0 for field in PLAYER_STAT_FIELDS}


def _split_points(events):
    """Split a team's flat event list into points, each keyed by the
    Offense/Defense-Point lineup event that opens it.
    """
    points = []
    current = None
    for event in events:
        if event["t"] in LINEUP_EVENTS:
            if current is not None:
                points.append(current)
            current = {
                "is_offense": event["t"] == EventType.OFFENSE_POINT,
                "lineup": event["l"],
                "events": [],
            }
        elif current is not None:
            current["events"].append(event)
    if current is not None:
        points.append(current)
    return points


def _parse_team_events(raw_events_json: str) -> dict:
    """Return ``{player_game_id: stats_dict}`` for one team in one game."""
    events = json.loads(raw_events_json)
    stats = defaultdict(_empty_stats)

    for point in _split_points(events):
        for player_id in point["lineup"]:
            stats[player_id]["points_played"] += 1
            key = "o_points_played" if point["is_offense"] else "d_points_played"
            stats[player_id][key] += 1

        thrower = None
        # chain of throwers this possession, for hockey-assist attribution
        chain = []

        for event in point["events"]:
            t = event["t"]

            if t == EventType.PULL:
                puller = event.get("r")
                if puller is not None:
                    stats[puller]["pulls"] += 1

            elif t == EventType.BLOCK:
                blocker = event.get("r")
                if blocker is not None:
                    stats[blocker]["blocks"] += 1

            elif t == EventType.THROWAWAY:
                if thrower is not None:
                    stats[thrower]["throw_attempts"] += 1
                    stats[thrower]["throwaways"] += 1
                thrower = None
                chain = []

            elif t == EventType.STALL:
                if thrower is not None:
                    stats[thrower]["stalls"] += 1
                thrower = None
                chain = []

            elif t == EventType.PASS_DROPPED:
                receiver = event.get("r")
                if thrower is not None:
                    stats[thrower]["throw_attempts"] += 1
                if receiver is not None:
                    stats[receiver]["drops"] += 1
                thrower = None
                chain = []

            elif t == EventType.PASS_COMPLETED:
                receiver = event.get("r")
                if thrower is not None and receiver is not None:
                    stats[thrower]["throw_attempts"] += 1
                    stats[thrower]["completions"] += 1
                    stats[receiver]["receptions"] += 1
                    chain.append(thrower)
                thrower = receiver

            elif t == EventType.GOAL:
                scorer = event.get("r")
                if scorer is not None:
                    stats[scorer]["goals"] += 1
                    stats[scorer]["receptions"] += 1
                if thrower is not None:
                    stats[thrower]["throw_attempts"] += 1
                    stats[thrower]["completions"] += 1
                    stats[thrower]["assists"] += 1
                    if chain:
                        stats[chain[-1]]["hockey_assists"] += 1
                thrower = None
                chain = []

    return stats


def parse_game(game_json: dict) -> pd.DataFrame:
    """Parse a single game's raw JSON into a player-game DataFrame.

    Returns one row per player who appeared in at least one lineup, with
    game/team metadata joined on from rosters + game info.
    """
    game_id = game_json["game"]["id"]
    reg_season = game_json["game"].get("reg_season")

    rows = []
    for side, roster_key, team_key in [
        ("tsgHome", "rostersHome", "team_season_home"),
        ("tsgAway", "rostersAway", "team_season_away"),
    ]:
        tsg = game_json[side]
        if tsg.get("events") is None:
            # A handful of games (so far: one 2026 regular-season game) have
            # no play-by-play tracked at all, despite a final score existing.
            # Skip this team's rows rather than crash; the caller can tell
            # from the empty result plus the game_id that this game has no
            # player-game rows.
            continue
        team_ext_id = game_json["game"][team_key]["team"]["ext_team_id"]
        stats_by_player = _parse_team_events(tsg["events"])

        roster_df = pd.json_normalize(game_json[roster_key])
        roster_lookup = roster_df.set_index("id")

        for player_game_id, stats in stats_by_player.items():
            if stats["points_played"] == 0:
                continue  # appeared in raw events but never actually took the field
            player_row = {
                "game_id": game_id,
                "reg_season": reg_season,
                "is_home": side == "tsgHome",
                "team_ext_id": team_ext_id,
                "player_game_id": player_game_id,
                **stats,
            }
            if player_game_id in roster_lookup.index:
                meta = roster_lookup.loc[player_game_id]
                first_name = meta.get("player.first_name")
                last_name = meta.get("player.last_name")
                player_row["first_name"] = first_name
                player_row["last_name"] = last_name
                # No stable cross-game external player ID ships in the
                # roster payload (the audl package assumes one that isn't
                # actually present in current API responses) — full name is
                # used as the player key for now. Known limitation: name
                # collisions across players/seasons aren't resolved yet.
                player_row["player_name"] = f"{first_name} {last_name}"
            rows.append(player_row)

    df = pd.DataFrame(rows)
    if not df.empty:
        df["turnovers"] = df["throwaways"] + df["stalls"] + df["drops"]
        df["completion_pct"] = df["completions"] / df["throw_attempts"].replace(0, pd.NA)
    return df
