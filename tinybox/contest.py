"""CR122: the TinyBox as the opponent in the CQ contest (prcore/contest.py).

A TBClient in client mode with cap CT invites the box:

    //CT NEW h=1           -> //CT OK c=<locator of the box> h=1
                              //CT READY <hash>        (the box places at once)
    //CT CQ <loc>          -> //CT R <loc> ...         and right away the box's own
                              //CT CQ <loc>            call (the client invited: it starts)
    //CT R <loc> ...       the client's answer to the box's call
    //CT END ... / RESIGN  as between two clients; the box lays its stations open too
    //CT PAUSE / RESUME    the client takes a break (the box only calls after the client)

One game per call (without SSID), any number at the same time, kept in memory
for a day - a game goes on after a new connect, not after a restart of the box.
Without a locator in [station] the box does not play (//CT ERR no_locator).

Two clients of the box play each other through it (cap CTR): the box hands
the //CT lines on, from the logged-in call - nobody can play in another's name:

    //CTR <to> <line>      client -> box: a //CT line for <to> (NEW, OK, CQ ...)
    //CTR <from> <line>    box -> client: the line of <from>
    //CTR <to> ERR offline|no_game|no_locator|bad     the box could not hand it on

The center is the square of the box (it adds c= to the NEW). Only NEW opens a
pair; the other lines go only between two calls with a game (a day, NO ends it).
Each line goes over the air twice (to the box, to the other) - about 3 kB a game.
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
_pairs: dict[frozenset, float] = {}     # CTR: two base calls with a game -> last line
RELAY_WORDS = ("NEW", "OK", "NO", "READY", "CQ", "R", "END", "RESIGN", "PAUSE", "RESUME")


def _prune(now: float) -> None:
    for call in [c for c, g in _games.items() if now - g.get("touch", 0) > KEEP_SEC]:
        del _games[call]
    while len(_games) > MAX_GAMES:
        del _games[min(_games, key=lambda c: _games[c].get("touch", 0))]


def _clients_of(s: "Session", base: str) -> list:
    app = getattr(s.service, "app", None)
    return [x for x in (list(app.registry) if app is not None else [])
            if base_call(x.call) == base and not getattr(x, "closed", False)
            and x.client is not None and "CTR" in x.client.caps]


def relay(s: "Session", rest: str) -> None:
    """//CTR <to> <line>: hand a //CT line on to another client of this box."""
    p = rest.split()
    if len(p) < 2:
        return
    me, to, word, now = base_call(s.call), base_call(p[0].upper())[:9], p[1].upper(), time.time()
    for pair in [k for k, t in _pairs.items() if now - t > KEEP_SEC]:
        del _pairs[pair]
    if word not in RELAY_WORDS or to == me or len(rest) > 200:
        s.out(f"//CTR {to} ERR bad")
        return
    pair = frozenset((me, to))
    line = " ".join(p[1:])
    if word == "NEW":
        center = s.cfg.station.locator[:4].upper()
        if not contest.valid_center(center):
            s.out(f"//CTR {to} ERR no_locator")
            return
        line = " ".join([x for x in p[1:] if not x.lower().startswith("c=")] + [f"c={center}"])
    elif pair not in _pairs:
        s.out(f"//CTR {to} ERR no_game")
        return
    targets = _clients_of(s, to)
    if not targets:
        s.out(f"//CTR {to} ERR offline")
        _pairs.pop(pair, None)
        return
    targets[-1].out(f"//CTR {me} {line}")             # the newest session of that call
    if word == "NO":
        _pairs.pop(pair, None)
    else:
        _pairs[pair] = now
        while len(_pairs) > MAX_GAMES:
            del _pairs[min(_pairs, key=_pairs.get)]
    if word == "NEW":
        log.info("%s: CQ contest with %s through the box", s.call, to)


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
