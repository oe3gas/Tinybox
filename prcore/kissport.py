"""KISS port: the own AX.25 layer 2 over KISS-TCP (kisshub or Direwolf's KISS
port), shared by the TinyBox (tinybox/adapters/kiss.py) and the client
(tbclient/kisslink.py). PLANUNG.md section 17.1, step 2c.

    KISS-TCP  ->  _on_kiss  ->  Ax25Link per station  ->  on_link_event()
                                     |
                 transmit()  <-  service()

What it does for both:
    - one Ax25Link per remote station (links), their timers (T1/T2/T3/XID)
    - routing: frames not to us or not fully repeated only pause T1 of all
      links (half duplex); frames to us go to the link of that station
    - strangers: SABM/SABME opens a link if accept_incoming() says so and
      gets DM otherwise; anything else gets DM from a throw-away link
    - one transmitter for all links: every frame sent or heard pauses the
      other links for its airtime
    - stations that answered SABME with DM are remembered (v20) and called
      with SABM the next time
    - kisshub's status page (fetch_hub_status, poll_hub)

What each side adds, by overriding the hooks:
    on_heard(data, peeked, target)   every frame heard (monitor, statistics)
    on_transmit(f, raw)              every frame sent (monitor, counters)
    received(f, target, now)         a frame for us, before it is routed
    accept_incoming(link)            a station connects to us: take it?
    on_link_event(link, name, arg)   connected / data / reset / disconnected
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import time
from typing import Awaitable, Callable

from .ax25 import frame as ax
from .ax25.frame import AX25Error, Frame
from .ax25.link import Ax25Link, LinkCfg
from .kiss import KissTcpClient

log = logging.getLogger(__name__)


def norm_call(call: str) -> str:
    """'oe3gas-0 ' -> 'OE3GAS': the form links are keyed by."""
    call = call.strip().upper()
    return call[:-2] if call.endswith("-0") else call


class KissPort:
    def __init__(self, mycall: str, host: str, port: int, link_cfg: LinkCfg, *,
                 channel: int = 0, reconnect_sec: float = 5) -> None:
        self.mycall = norm_call(mycall)
        self.link_cfg = link_cfg
        self.kiss = KissTcpClient(host, port, self._on_kiss, reconnect_sec=reconnect_sec,
                                  kiss_port=channel)
        self.connected = self.kiss.connected      # set while KISS-TCP is up
        self.links: dict[str, Ax25Link] = {}      # remote call -> its link
        self.v20: set[str] = set()                # answered SABME with DM: call with SABM
        self._kick = asyncio.Event()

    @staticmethod
    def now() -> float:
        return time.monotonic()

    # --- hooks ---------------------------------------------------------------------

    def apply_hub_status(self, status: dict | None,
                         fixed: frozenset[str] | set[str] = frozenset()) -> dict:
        """CR70: take kisshub's radio values for links opened from now on.
        Returns the fields that changed ({} = nothing new)."""
        self.link_cfg, changed = hub_link_cfg(self.link_cfg, status, fixed)
        return changed

    def on_heard(self, data: bytes, peeked: tuple | None, target: Ax25Link | None) -> None:
        """Every frame heard. peeked: (dest, src, path, repeated) or None if the
        address field is garbage; target: our link it belongs to, if any."""

    def on_transmit(self, f: Frame, raw: bytes) -> None:
        """Every frame sent (already handed to KISS)."""

    def received(self, f: Frame, target: Ax25Link | None, now: float) -> None:
        """A frame for us. Override to add context, then call super()."""
        self.route(f, target, now)

    def accept_incoming(self, link: Ax25Link) -> bool:
        """A station connects to us (link is new, not yet registered)."""
        return True

    def on_link_event(self, link: Ax25Link, name: str, arg) -> None:
        """connected (arg incoming/outgoing), data (bytes), reset, disconnected (reason)."""

    # --- main loop -------------------------------------------------------------------

    async def run(self, *extra: Awaitable) -> None:
        """Keep KISS-TCP up and run the link timers; extra coroutines run alongside
        and are cancelled with it."""
        tasks = [asyncio.ensure_future(self._timer_loop())]
        tasks += [asyncio.ensure_future(c) for c in extra]
        try:
            await self.kiss.run()
        finally:
            for t in tasks:
                t.cancel()

    async def _timer_loop(self) -> None:
        """Run the link timers (T1/T2/T3/XID) when they are due."""
        while True:
            due = [d for d in (link.next_deadline() for link in self.links.values())
                   if d is not None]
            self._kick.clear()
            timeout = max(0.0, min(due) - self.now()) if due else None
            try:
                await asyncio.wait_for(self._kick.wait(), timeout)
            except asyncio.TimeoutError:
                pass
            now = self.now()
            for link in list(self.links.values()):
                deadline = link.next_deadline()
                if deadline is not None and deadline <= now:
                    try:
                        link.tick(now)
                        self.service(link)
                    except Exception:
                        log.exception("%s: timer handling failed", link.remote)

    # --- links -------------------------------------------------------------------------

    def open_link(self, remote: str, via: list[str] | None = None) -> Ax25Link:
        """A new link for an outgoing connect (registered; call link.connect())."""
        remote = norm_call(remote)
        link = Ax25Link(self.mycall, remote, path=[norm_call(v) for v in via or []],
                        cfg=self.link_cfg, now=self.now(), peer_v20=remote in self.v20)
        self.links[remote] = link
        return link

    def service(self, link: Ax25Link) -> None:
        """Send what the link produced and hand its events on. Call after every
        call into a link."""
        for f in link.pop_output():
            self.transmit(f, link)
        for name, arg in link.pop_events():
            try:
                self._event(link, name, arg)
            except Exception:
                log.exception("%s: error handling link event %s", link.remote, name)
        self._kick.set()

    def _event(self, link: Ax25Link, name: str, arg) -> None:
        if name == "connected":
            if link.peer_version == "2.0":
                self.v20.add(link.remote)
            else:
                self.v20.discard(link.remote)
        elif name == "disconnected":
            if self.links.get(link.remote) is link:
                del self.links[link.remote]
            if link.peer_v20:
                self.v20.add(link.remote)
        self.on_link_event(link, name, arg)

    # --- sending -------------------------------------------------------------------------

    def airtime(self, nbytes: int) -> float:
        c = self.link_cfg
        return c.txdelay_sec + (nbytes + 4) * 8 / c.air_baud

    def transmit(self, f: Frame, source: Ax25Link | None) -> None:
        raw = f.encode()
        if not self.kiss.send(raw):
            log.debug("KISS down, frame lost: %s", f)
        log.debug(">> %s", f)
        self.on_transmit(f, raw)
        # one transmitter for all: our other links could not be answered meanwhile
        air, now = self.airtime(len(raw)), self.now()
        for link in self.links.values():
            if link is not source:
                link.channel_busy(air, now)

    # --- receiving -----------------------------------------------------------------------

    def _on_kiss(self, port: int, data: bytes) -> None:
        now = self.now()
        try:
            dest, src, path, repeated = ax.peek(data)
        except AX25Error as exc:
            log.debug("undecodable frame ignored: %s", exc)
            self.on_heard(data, None, None)
            return
        dest, src = norm_call(dest), norm_call(src)
        target = self.links.get(src) if dest == self.mycall else None
        self.on_heard(data, (dest, src, path, repeated), target)
        air = self.airtime(len(data))
        for link in self.links.values():
            if link is not target:
                link.channel_busy(air, now)       # half duplex: nobody else got through
        if dest != self.mycall or (path and not all(repeated)):
            return
        try:
            f = Frame.decode(data, target.modulo if target else 8)
        except AX25Error as exc:
            log.debug("frame from %s ignored: %s", src, exc)
            return
        self.received(f, target, now)

    def route(self, f: Frame, link: Ax25Link | None, now: float) -> None:
        if f.kind == "UI":
            return                                 # nothing for our call itself
        if link is None:
            link = Ax25Link(self.mycall, f.src, path=f.reply_path(), cfg=self.link_cfg,
                            now=now)
            if f.kind in ("SABM", "SABME") and f.command:
                if self.accept_incoming(link):
                    self.links[link.remote] = link
                else:                              # refused (e.g. no free channel): DM
                    self.transmit(ax.u_frame("DM", link.remote, self.mycall, command=False,
                                             pf=f.pf, path=f.reply_path()), None)
                    return
            else:                                  # a stranger: DM and forget
                link.receive(f, now)
                for out in link.pop_output():
                    self.transmit(out, None)
                return
        link.receive(f, now)
        self.service(link)


# --- kisshub's status page -----------------------------------------------------------------

# CR70: kisshub owns the radio values; its status ("radio" block) gives them to
# the stations. LinkCfg field <- key in the radio block / its "ax25" part.
HUB_AX25_KEYS = ("paclen", "maxframe", "maxframe_ext", "n2", "t1_min_sec", "t1_max_sec",
                 "t2_sec", "t3_sec")


def hub_link_cfg(base: LinkCfg, status: dict | None,
                 fixed: frozenset[str] | set[str] = frozenset()) -> tuple[LinkCfg, dict]:
    """The link values with kisshub's radio block applied. `fixed`: LinkCfg fields
    set in the station's own conf - they stay. Returns (cfg, {field: new value})
    with only the fields that changed."""
    radio = (status or {}).get("radio")
    if not isinstance(radio, dict):
        return base, {}
    new: dict = {}
    if isinstance(radio.get("air_baud"), int) and radio["air_baud"] >= 300:
        new["air_baud"] = radio["air_baud"]
    if isinstance(radio.get("txdelay_ms"), (int, float)) and 0 <= radio["txdelay_ms"] <= 10000:
        new["txdelay_sec"] = radio["txdelay_ms"] / 1000
    ax25 = radio.get("ax25") if isinstance(radio.get("ax25"), dict) else {}
    for key in HUB_AX25_KEYS:
        v = ax25.get(key)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0:
            new[key] = type(getattr(base, key))(v)
    if "maxframe" in new:
        new["maxframe"] = min(7, new["maxframe"])
    changed = {k: v for k, v in new.items() if k not in fixed and getattr(base, k) != v}
    if not changed:
        return base, {}
    cfg = dataclasses.replace(base, **changed)
    if cfg.t1_min_sec > cfg.t1_max_sec:                # a recommendation with T1 18 s
        cfg = dataclasses.replace(cfg, t1_max_sec=cfg.t1_min_sec)
    if "paclen" in changed:
        cfg = dataclasses.replace(cfg, max_rx_info=max(cfg.max_rx_info, cfg.paclen))
    return cfg, changed


def describe_changes(changed: dict) -> str:
    def show(k, v):
        return f"txdelay {round(v * 1000)} ms" if k == "txdelay_sec" else f"{k} {v}"
    return ", ".join(show(k, v) for k, v in changed.items())

async def fetch_hub_status(host: str, port: int, timeout: float = 3.0) -> dict:
    """GET /status from kisshub (tiny HTTP/1.0, loopback only)."""
    async def _get() -> bytes:
        reader, writer = await asyncio.open_connection(host, port)
        try:
            writer.write(f"GET /status HTTP/1.0\r\nHost: {host}:{port}\r\n\r\n".encode())
            await writer.drain()
            return await reader.read(256 * 1024)
        finally:
            writer.close()
    raw = await asyncio.wait_for(_get(), timeout)
    head, _, body = raw.partition(b"\r\n\r\n")
    if not head.startswith(b"HTTP/1.") or b" 200 " not in head.split(b"\r\n", 1)[0]:
        raise ValueError("unexpected answer from kisshub")
    data = json.loads(body.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("unexpected answer from kisshub")
    return data


async def poll_hub(host: str, port: int, every: float,
                   on_result: Callable[[dict | None, Exception | None], None]) -> None:
    """Ask kisshub for its status every `every` seconds; on_result(status, None)
    or on_result(None, error). Returns at once if port <= 0 (no status port)."""
    if port <= 0:
        return
    while True:
        try:
            status = await fetch_hub_status(host, port)
        except (OSError, asyncio.TimeoutError, ValueError) as exc:
            on_result(None, exc)
        else:
            on_result(status, None)
        await asyncio.sleep(every)
