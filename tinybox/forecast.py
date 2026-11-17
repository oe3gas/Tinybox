"""CR72: the weather forecast for one's own locator - on request (GETFC).

    GETFC [locator]       terminal: the forecast as text (48 h in 3-h steps), only to
                          the asker; without a locator the one of the profile (MYLOC)
    //GETFC [locator]     client (cap FC): the same values, compact in one line -
                          the client draws the table itself:
        //FC <loc> <run> <lat> <lon> <step>;<step>;...
             step = <unix>,<eighths>,<temp*10>,<wdir>,<wspd*10>,<gust*10>,<rain*10>
             (an empty field: no value)
        //FC - <reason>      no forecast (error text, English)

The values come from GeoSphere Austria (geosphere_prognose.py next to the box, the
same as the forecast bulletins - PLANUNG 20). Not every installation has these
scripts (they are not in the release package): then GETFC says so and the client
gets no FC cap. The box asks the API in a worker thread with a timeout, so a slow
answer never blocks a radio link.

Decisions (OE3GAS, 17.11.2026): everybody may ask; 48 h; no answer becomes a
bulletin or a brocast page; often asked locators are NOT taken into the bulletins
automatically. A cache per locator saves the API (the model runs every 3 h), a
limit per station and hour stops abuse.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from prcore.calls import base_call

from . import profiles

if TYPE_CHECKING:
    from .session import Session

log = logging.getLogger("tinybox.forecast")

HOURS, STEP = 48, 3
CACHE_SEC = 3600              # one answer per locator for an hour (model: every 3 h)
PER_HOUR = 6                  # requests per station and hour
TIMEOUT = 25                  # s for the API

try:                          # next to the box, not in the release package (PLANUNG 17.4)
    import geosphere_prognose as gp
except ImportError:           # pragma: no cover - depends on the installation
    gp = None

_cache: dict[str, tuple[float, dict, list]] = {}       # locator -> (time, data, rows)
_asked: dict[str, list[float]] = {}                    # base call -> times of requests


def available() -> bool:
    return gp is not None


def _fetch(loc: str) -> tuple[dict, list]:
    """In a worker thread: API -> (data of the cell, rows of 3 h)."""
    point = gp.locator_mitte(loc)
    d = gp.zuordnen(gp.api_get([point], timeout=TIMEOUT), [point])[0]
    rows = gp.schritte(d, HOURS, STEP)
    if not rows:
        raise ValueError("no forecast values")
    return d, rows


async def get(loc: str) -> tuple[dict, list]:
    now = time.monotonic()
    hit = _cache.get(loc)
    if hit is not None and now - hit[0] < CACHE_SEC:
        return hit[1], hit[2]
    d, rows = await asyncio.get_running_loop().run_in_executor(None, _fetch, loc)
    _cache[loc] = (time.monotonic(), d, rows)
    for k in [k for k, v in _cache.items() if time.monotonic() - v[0] > CACHE_SEC]:
        del _cache[k]
    return d, rows


def _allowed(call: str) -> bool:
    now = time.monotonic()
    times = [t for t in _asked.get(base_call(call), []) if now - t < 3600]
    if len(times) >= PER_HOUR:
        _asked[base_call(call)] = times
        return False
    _asked[base_call(call)] = times + [now]
    return True


def _locator(s: Session, arg: str) -> str:
    """The locator asked for, else the one of the profile. ValueError with the reason."""
    arg = arg.strip()
    if not arg:
        p = profiles.get(s.service.store, s.call) or {}
        arg = p.get("loc") or ""
        if not arg:
            raise ValueError("no locator - GETFC JN88BN, or set yours with MYLOC")
    try:
        loc = gp.locator_norm(arg)
        gp.locator_mitte(loc)                 # inside the model area?
    except ValueError as exc:
        raise ValueError(_english(str(exc), arg)) from None
    return loc


def _english(text: str, arg: str) -> str:
    if "zu grob" in text:
        return f"locator {arg.upper()} too coarse - 6 characters, e.g. {arg.upper()[:4]}BN"
    if "ausserhalb" in text:
        return f"{arg.upper()} is outside the model area (Austria and around)"
    return f"invalid locator {arg.upper()} - 6 or 8 characters, e.g. JN88BN"


def compact(loc: str, d: dict, rows: list) -> str:
    """The client line: //FC <loc> <run> <lat> <lon> <steps>."""
    def n(x, scale=10):
        return "" if x is None else str(round(x * scale))
    steps = ";".join(",".join((str(int(z["zeit"].timestamp())), n(z["achtel"], 1), n(z["temp"]),
                               n(z["wdir"], 1) if z["wspd"] is not None else "", n(z["wspd"]),
                               n(z["boe"]), n(z["regen"])))
                     for z in rows)
    lat, lon = d["zelle"]
    return f"//FC {loc} {d.get('lauf') or '-'} {lat:.3f} {lon:.3f} {steps}"


def cmd_getfc(s: Session, arg: str) -> None:
    """Terminal: GETFC [locator]."""
    _start(s, arg, client=False)


def client_getfc(s: Session, arg: str) -> None:
    """Client: //GETFC [locator]."""
    _start(s, arg, client=True)


def _start(s: Session, arg: str, client: bool) -> None:
    def fail(reason: str) -> None:
        s.out(f"//FC - {reason}" if client else f"No forecast: {reason}")
    if not available():
        fail("this box has no forecast (GeoSphere scripts missing)")
        return
    try:
        loc = _locator(s, arg)
    except ValueError as exc:
        fail(str(exc))
        return
    if not _allowed(s.call):
        fail(f"at most {PER_HOUR} forecasts per hour")
        return
    if not client:
        s.out(f"Forecast for {loc} is fetched ...")
    asyncio.get_running_loop().create_task(_answer(s, loc, client))


async def _answer(s: Session, loc: str, client: bool) -> None:
    try:
        d, rows = await get(loc)
    except Exception as exc:                  # API, network, TLS: one line, no traceback
        log.warning("%s: forecast %s failed: %s", s.call, loc, exc)
        if not s.closed:
            s.out("//FC - forecast service not reachable" if client
                  else "No forecast: the forecast service is not reachable - try later.")
            if not client:
                s.prompt()
        return
    if s.closed:
        return
    log.info("%s: forecast %s (%d steps)", s.call, loc, len(rows))
    if client:
        s.out(compact(loc, d, rows))
    else:
        s.out(*gp.bericht(loc, d, rows, STEP))
        s.prompt()
