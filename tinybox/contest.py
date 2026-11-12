"""CR122: the TinyBox as the opponent in the CQ contest (prcore/contest.py).

A TBClient in client mode with cap CT invites the box:

    //CT NEW h=1           -> //CT OK c=<locator of the box> h=1
                              //CT READY <hash>        (the box places at once)
    //CT CQ <loc>          -> //CT R <loc> ...         and right away the box's own
                              //CT CQ <loc>            call (the client invited: it starts)
    //CT R <loc> ...       the client's answer to the box's call
    //CT END ... / RESIGN  as between two clients; the box lays its stations open too

One game per call (without SSID), any number at the same time, kept in memory
for a day - a game goes on after a new connect, not after a restart of the box.
Without a locator in [station] the box does not play (//CT ERR no_locator).
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from prcore import contest

from .addressing import base_call

if TYPE_CHECKING:
    from .session import Session

log = logging.getLogger(__name__)

KEEP_SEC = 24 * 3600
MAX_GAMES = 200

_games: dict[str, dict] = {}            # base call -> game state


def _prune(now: float) -> None:
    for call in [c for c, g in _games.items() if now - g.get("touch", 0) > KEEP_SEC]:
        del _games[call]
    while len(_games) > MAX_GAMES:
        del _games[min(_games, key=lambda c: _games[c].get("touch", 0))]


def game_of(call: str) -> dict | None:
    return _games.get(base_call(call))


def handle(s: "Session", rest: str) -> None:
    """One //CT line of a client session."""
    p = rest.split()
    if not p:
        return
    call, now = base_call(s.call), time.time()
    _prune(now)
    word = p[0].upper()
    out: list[str] = []
    if word == "NEW":
        center = s.cfg.station.locator[:4].upper()
        if not contest.valid_center(center):
            s.out("//CT ERR no_locator")
            return
        hints = dict(x.partition("=")[::2] for x in p[1:] if "=" in x).get("h", "1") != "0"
        state = contest.new_state(center, hints, first=False, opp=call)
        g = contest.Game(state)
        g.random_place()
        out = [f"OK c={center} h={1 if hints else 0}"] + g.set_ready()
        _games[call] = state
        log.info("%s: CQ contest started (center %s)", s.call, center)
    else:
        state = _games.get(call)
        if state is None:
            if word not in ("END", "RESIGN"):
                s.out("//CT ERR no_game")
            return
        g = contest.Game(state)
        out = g.take(rest)
        if word == "CQ" and g.my_turn():             # the box calls right after its answer
            out += g.cq(g.pick())
        if state["st"] == "end" and state.get("reveal") is not None:
            log.info("%s: CQ contest over - box %s, %s:%s", s.call, state["res"],
                     g.worked(), g.lost())
            del _games[call]                         # both sides laid open: done
    if call in _games:
        _games[call]["touch"] = now
    if out:
        s.out(*[f"//CT {line}" for line in out])
