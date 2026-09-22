# `player_game` data dictionary

Built by `Cleaning/scripts/build_player_game_table.py` from raw game JSON
in `data/raw/<season>/games/*.json`. One row per player who took the field
in a given game (players on the roster but who never entered a lineup are
excluded).

## Identity / context columns

| Column | Type | Description |
|---|---|---|
| `season` | int | Season year |
| `game_id` | int | UFA's internal numeric game id |
| `reg_season` | bool | Regular season vs. playoffs (from the raw `game.reg_season` field) |
| `is_home` | bool | Whether the player's team was home |
| `team_ext_id` | str | Team external id (e.g. `'havoc'`) |
| `player_game_id` | int | Roster-entry id local to this game (not stable across games) |
| `player_name` | str | `"First Last"`, used as the player key. **Known limitation**: no stable cross-game player id ships in the roster payload (the upstream `audl` package assumes one that isn't actually present in current API responses), so name collisions across players aren't resolved yet — see `Cleaning/src/ufa_cleaning/parse_game.py`. |

## Counting stats

| Column | Description |
|---|---|
| `points_played` | Points the player was on the field for |
| `o_points_played` / `d_points_played` | Split by starting on offense vs. defense. **Known limitation**: mid-point substitutions via timeout aren't reflected — only the lineup announced at the start of the point is counted. |
| `pulls` | Pulls thrown |
| `blocks` | Blocks (Ds) |
| `throw_attempts` | Throws attempted (completions + throwaways + drops thrown into) |
| `completions` | Throws completed, including the scoring throw |
| `receptions` | Catches, including goals |
| `throwaways` | Unforced turnovers thrown away |
| `stalls` | Stall-violation turnovers |
| `drops` | Passes dropped (charged to the receiver, not the thrower) |
| `turnovers` | `throwaways + stalls + drops` |
| `goals` | Goals scored |
| `assists` | Goals directly assisted |
| `hockey_assists` | Secondary assists (the pass before the assist) |
| `completion_pct` | `completions / throw_attempts` |

## Known limitations (as of the 2026-season build)

Validated by rolling player rows back up to the team level and comparing
against the pre-aggregated `tsgHome`/`tsgAway` totals in the same raw JSON.
Mean absolute error across all 2026 team-games (exact matches counted as
0%): **completions ~1.5%, turnovers ~0.8%, blocks ~0.9%**. Residual gaps
are believed to come from:

- **Callahans** not being distinguished from an ordinary block + goal.
- A handful of rare, unidentified event codes (the event-type mapping was
  reverse-engineered against real data since the upstream `audl` package's
  own two reference tables contradict each other on several codes — see
  `Cleaning/src/ufa_cleaning/events.py` for the resolution process).
- One 2026 regular-season game (`game_id` 3818, PIT @ CHI) has no
  play-by-play at all despite a final score existing, and is skipped
  entirely — it will have zero rows in `player_game`.

`touches` (times a player had the disc) was in the original plan's field
list but isn't included yet: the API doesn't log a separate event for
catching the opening pull of a possession, so it can't be counted the same
way as a normal reception without a documented gap.

Yardage (`TY`/`RY` in the official box score) also isn't computed yet —
it's derivable from the `x`/`y` coordinates already being parsed, and is
deferred to Phase 4 feature engineering rather than blocking this table.
