"""Event-type codes used in the ``tsgHome.events`` / ``tsgAway.events``
arrays returned by ``https://www.backend.ufastats.com/stats-pages/game/<id>``.

The upstream ``audl`` package's own reference tables (``HerokuPlay`` vs
``game_event_dict`` in its ``library/parameters.py``) disagree with each
other on what a few codes mean. The codes below were instead confirmed by
cross-checking counts against the pre-aggregated team totals that ship in
the same JSON (``tsgHome.turnovers``, ``.blocks``, ``.completionsNumer``):

- Code 8 carries ``x``/``y`` (a disc landing spot) and no ``r`` — an
  unforced throwaway, charged to whoever is currently "holding" the disc
  in the event chain.
- Code 9 carries neither coordinates nor a receiver (just an ``h`` flag) —
  it is NOT a turnover event despite one upstream reference table's label;
  it appears to annotate the preceding event (observed immediately after a
  throwaway) rather than represent an action of its own. Excluded from
  parsing here.
- Code 17 carries no fields beyond ``t``/``n`` — a stall violation. Its
  count matches (reported turnovers - computed throwaway+drop count)
  exactly in 86% of a full-season spot check, which is why it's treated as
  the stall code despite not appearing in either upstream reference table.
- Code 5 carries ``r`` (the blocking player) and its count is close to (but
  not always exactly) the team's reported ``blocks`` — Callahans (a block
  that also directly scores) aren't distinguished from a plain block here,
  which is a plausible source of the residual gap.

Known gap: after accounting for stalls, per-team-game validation against
the reported turnovers/blocks/completions aggregates still shows
discrepancies in a residual ~15% of team-games (see
``Cleaning/scripts/build_player_game_table.py``'s validation output) —
Callahans are counted as an ordinary block + goal rather than a distinct
stat, and there may be further rare, unidentified event codes.
"""


class EventType:
    OFFENSE_POINT = 1
    DEFENSE_POINT = 2
    PULL = 3
    BLOCK = 5
    THROWAWAY = 8
    STALL = 17
    PASS_DROPPED = 19
    PASS_COMPLETED = 20
    GOAL = 22


LINEUP_EVENTS = {EventType.OFFENSE_POINT, EventType.DEFENSE_POINT}
