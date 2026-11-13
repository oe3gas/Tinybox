"""CR127: results of client games (chess, CQ contest), signed, into the scores.

Chess and the CQ contest run between two TBClients; the box does not see them.
Each client reports its result, signed with its released key (CR93, like
//SEND). A game counts only when both players reported it and the reports match:
same game and id, the calls crosswise, win against loss or draw against draw,
the same hash over the course of the game, the same number of moves, the ends at
most MATCH_SEC apart. Then both go into game_stats (games.py).

    //GAME RES g=<chess|contest> id=<16 hex> vs=<call> r=<win|loss|draw> h=<16 hex> n=<moves> t=<end unix> c=.. sig=..
    -> //GAME OK <id> pending|counted
    -> //GAME ERR <id> nokey|mismatch|dup|old|self|limit|bad
    //GAME ST <id>       how is my report?  -> //GAME OK <id> pending|counted, //GAME ERR <id> mismatch|limit|expired|unknown

Reports with no answer of the opponent in KEEP_DAYS expire; reports older than
KEEP_DAYS are not taken. At most PAIR_DAY counted games per pair and day (UTC).
Both must report to the same box (OE3GAS, 13.11.2026).
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from prcore import auth

from . import games

if TYPE_CHECKING:
    from .session import Session

log = logging.getLogger(__name__)

GAMES = ("chess", "contest")
KEEP_DAYS = 7
MATCH_SEC = 600
PAIR_DAY = 50
HEX16 = re.compile(r"^[0-9a-f]{16}$")
CALL = re.compile(r"^(?=[A-Z0-9]*[0-9])(?=[A-Z0-9]*[A-Z])[A-Z0-9]{3,6}$")
OTHER = {"win": "loss", "loss": "win", "draw": "draw"}


def _ts(t: float) -> str:
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def command(s: "Session", rest: str) -> None:
    """//GAME ... of a client (RES already checked for its signature)."""
    p = rest.split()
    word = p[0].upper() if p else ""
    if word == "ST" and len(p) == 2:
        _status(s, p[1].lower())
    elif word == "RES":
        _report(s, p[1:])
    else:
        s.out("//GAME ERR - bad")


def _status(s: "Session", gid: str) -> None:
    r = s.service.store.report_get(gid, auth.base(s.call.upper()))
    if r is None:
        s.out(f"//GAME ERR {gid} unknown")
    elif r["status"] in ("pending", "counted"):
        s.out(f"//GAME OK {gid} {r['status']}")
    else:
        s.out(f"//GAME ERR {gid} {r['status']}")


def _report(s: "Session", args: list[str]) -> None:
    store = s.service.store
    kv = {k.lower(): v for k, sep, v in (a.partition("=") for a in args) if sep}
    gid = kv.get("id", "").lower()
    if not HEX16.match(gid):
        s.out("//GAME ERR - bad")
        return
    if not s.auth or s.auth_pub is None:            # only with a released key
        s.out(f"//GAME ERR {gid} nokey")
        return
    me = auth.base(s.call.upper())
    vs = auth.base(kv.get("vs", "").upper())
    try:
        game, res, h = kv["g"], kv["r"], kv["h"].lower()
        moves, ended = int(kv["n"]), int(kv["t"])
    except (KeyError, ValueError):
        s.out(f"//GAME ERR {gid} bad")
        return
    if game not in GAMES or res not in OTHER or not HEX16.match(h) or moves < 0 \
            or not CALL.match(vs):
        s.out(f"//GAME ERR {gid} bad")
        return
    if vs == me:
        s.out(f"//GAME ERR {gid} self")
        return
    now = time.time()
    if ended < now - KEEP_DAYS * 86400 or ended > now + 600:
        s.out(f"//GAME ERR {gid} old")
        return
    store.report_expire(_ts(now - KEEP_DAYS * 86400))
    mine = {"id": gid, "call": me, "game": game, "vs": vs, "result": res, "hash": h,
            "moves": moves, "ended": ended, "received": _ts(now), "status": "pending"}
    old = store.report_get(gid, me)
    if old is not None:
        same = all(old[k] == mine[k] for k in ("game", "vs", "result", "hash", "moves", "ended"))
        if not same:
            s.out(f"//GAME ERR {gid} dup")
        else:                                      # sent again (the answer got lost)
            _status(s, gid)
        return
    other = store.report_get(gid, vs)
    if other is not None and other["status"] != "pending":
        s.out(f"//GAME ERR {gid} dup")
        return
    store.report_put(mine)
    if other is None:
        log.info("%s: %s result %s vs %s reported, waits for the opponent", s.call, game, res, vs)
        s.out(f"//GAME OK {gid} pending")
        return
    if not (other["game"] == game and other["vs"] == me and other["result"] == OTHER[res]
            and other["hash"] == h and other["moves"] == moves
            and abs(other["ended"] - ended) <= MATCH_SEC):
        store.report_status(gid, "mismatch")
        log.warning("%s: %s result %s vs %s does not match the report of %s - not counted",
                    s.call, game, res, vs, vs)
        s.out(f"//GAME ERR {gid} mismatch")
        return
    day = datetime.fromtimestamp(ended, timezone.utc).strftime("%Y-%m-%d")
    if store.report_pair_day(me, vs, day) >= PAIR_DAY:
        store.report_status(gid, "limit")
        s.out(f"//GAME ERR {gid} limit")
        return
    rows = [{"call": me, "wins": int(res == "win"), "draws": int(res == "draw")},
            {"call": vs, "wins": int(res == "loss"), "draws": int(res == "draw")}]
    games.record(store, game, rows)
    store.report_status(gid, "counted")
    log.info("%s: %s %s vs %s counted (both reported)", s.call, game, res, vs)
    s.out(f"//GAME OK {gid} counted")


def disputed(store) -> list[str]:
    """For the sysop (GAMES): results that did not match."""
    return [f"  not counted: {r['game']} {r['call']} vs {r['vs']} ({r['received'][:10]})"
            for r in store.report_list("mismatch")]
