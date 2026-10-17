"""KISS link of the client (CR46): kisshub instead of Direwolf - the client runs
its own AX.25 layer 2 (TinyBox's tinybox/ax25, v2.2 with fallback to v2.0).
With a KISS TNC behind kisshub the client is a complete packet radio program
of its own: no Direwolf, no TinyBox needed.

    TNC --serial-- kisshub --KISS-TCP 127.0.0.1:8101-- KissPort --+-- KissLink channel 1
                                                                  +-- KissLink channel 2 ...

KissPort  the KISS-TCP connection, the router (frame -> link of that station),
          the timers of all links and the monitor (every frame heard and sent)
KissLink  one AX.25 connection, the same interface as AgwLink for the channels

Incoming connects (somebody connects to us) open a free channel as a terminal;
with no free channel the station gets DM.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

from prcore.ax25 import frame as ax
from prcore.ax25.frame import AX25Error, Frame
from prcore.kiss import KissTcpClient
from prcore.ax25.link import Ax25Link, LinkCfg

from . import radio
from .config import Config
from .links import BaseLink

log = logging.getLogger(__name__)

HUB_POLL_SEC = 30

# why a link went down -> the reason the channel shows ("disconnected" = normal,
# while connecting the GUI makes "no answer from ..." of it)
REASONS = {"local": "disconnected", "remote": "disconnected", "timeout": "disconnected",
           "refused": "refused (DM)", "dm": "refused (DM)",
           "retryout": "link lost (no answer)", "protocol": "protocol error"}


def norm(call: str) -> str:
    call = call.upper()
    return call[:-2] if call.endswith("-0") else call


def link_cfg(cfg: Config) -> LinkCfg:
    return LinkCfg(paclen=cfg.ax25_paclen, maxframe=cfg.ax25_maxframe,
                   maxframe_ext=cfg.ax25_maxframe_ext, srej=cfg.ax25_srej, n2=cfg.ax25_n2,
                   version=cfg.ax25_version, t1_min_sec=cfg.ax25_t1_min,
                   t1_max_sec=cfg.ax25_t1_max, t2_sec=cfg.ax25_t2, t3_sec=cfg.ax25_t3,
                   air_baud=cfg.kiss_air_baud, txdelay_sec=cfg.kiss_txdelay_ms / 1000,
                   max_rx_info=max(512, cfg.ax25_paclen))


class KissPort:
    def __init__(self, cfg: Config, on_frame, on_incoming=None) -> None:
        self.cfg = cfg
        self.mycall = norm(cfg.mycall)
        self.on_frame = on_frame                  # monitor: radio.RawFrame
        self.on_incoming = on_incoming            # remote -> KissLink of a free channel, or None
        self.link_cfg = link_cfg(cfg)
        self.kiss = KissTcpClient(cfg.kiss_host, cfg.kiss_port, self._on_kiss,
                                  reconnect_sec=5, kiss_port=cfg.kiss_channel)
        self.agw_up = self.kiss.connected         # same name as AgwPort: "the radio is there"
        self.links: dict[str, KissLink] = {}      # remote -> its connection
        self.v20: set[str] = set()                # answered SABME with DM: call with SABM
        self.hub: dict | None = None              # kisshub's /status: the TNC behind it
        self._kick = asyncio.Event()

    @staticmethod
    def now() -> float:
        return time.monotonic()

    async def run(self) -> None:
        log.info("KISS %s:%d, own AX.25 layer 2 (version %s), %s",
                 self.cfg.kiss_host, self.cfg.kiss_port, self.link_cfg.version, self.mycall)
        tasks = [asyncio.ensure_future(self._timer_loop()), asyncio.ensure_future(self._hub_poll())]
        try:
            await self.kiss.run()
        finally:
            for t in tasks:
                t.cancel()

    async def _timer_loop(self) -> None:
        """Run the link timers (T1/T2/T3/XID) when they are due."""
        while True:
            due = [d for d in (k.ax.next_deadline() for k in self.links.values() if k.ax)
                   if d is not None]
            self._kick.clear()
            timeout = max(0.0, min(due) - self.now()) if due else None
            try:
                await asyncio.wait_for(self._kick.wait(), timeout)
            except asyncio.TimeoutError:
                pass
            now = self.now()
            for k in list(self.links.values()):
                d = k.ax.next_deadline() if k.ax else None
                if d is not None and d <= now:
                    try:
                        k.ax.tick(now)
                        self.service(k)
                    except Exception:
                        log.exception("%s: timer handling failed", k.target)

    # --- sending -----------------------------------------------------------------

    def _airtime(self, nbytes: int) -> float:
        c = self.link_cfg
        return c.txdelay_sec + (nbytes + 4) * 8 / c.air_baud

    def transmit(self, f: Frame, source: "KissLink | None") -> None:
        raw = f.encode()
        if not self.kiss.send(raw):
            log.debug("KISS down, frame lost: %s", f)
        rf = radio.decode(raw)
        if rf is not None:
            self.on_frame(rf)                     # the own frames belong into the monitor
        air, now = self._airtime(len(raw)), self.now()
        for k in self.links.values():             # one transmitter: the others had to wait
            if k is not source and k.ax:
                k.ax.channel_busy(air, now)

    def service(self, k: "KissLink") -> None:
        """Send what the link produced and hand its events on."""
        if k.ax is None:
            return
        for f in k.ax.pop_output():
            self.transmit(f, k)
        for name, arg in k.ax.pop_events():
            try:
                k.on_event(name, arg)
            except Exception:
                log.exception("%s: error handling link event %s", k.target, name)
        self._kick.set()

    # --- receiving -----------------------------------------------------------------

    def _on_kiss(self, port: int, data: bytes) -> None:
        rf = radio.decode(data)
        if rf is not None:
            self.on_frame(rf)
        now = self.now()
        try:
            dest, src, path, repeated = ax.peek(data)
        except AX25Error:
            return
        dest, src = norm(dest), norm(src)
        target = self.links.get(src) if dest == self.mycall else None
        air = self._airtime(len(data))
        for k in self.links.values():
            if k is not target and k.ax:
                k.ax.channel_busy(air, now)       # half duplex: nobody else got through
        if dest != self.mycall or (path and not all(repeated)):
            return
        try:
            f = Frame.decode(data, target.ax.modulo if target and target.ax else 8)
        except AX25Error:
            return
        if f.kind == "UI":
            return
        if target is None or target.ax is None:
            self._unknown(f, src, now)
            return
        target.ax.receive(f, now)
        self.service(target)

    def _unknown(self, f: Frame, src: str, now: float) -> None:
        """A frame from a station without a link: a connect to us opens a free
        channel; anything else (or no channel free) gets DM."""
        if f.kind in ("SABM", "SABME") and f.command and self.on_incoming is not None:
            k = self.on_incoming(src)
            if k is not None:
                k.ax = Ax25Link(self.mycall, src, path=f.reply_path(), cfg=self.link_cfg,
                                now=now)
                self.links[src] = k
                k.ax.receive(f, now)
                self.service(k)
                return
        tmp = Ax25Link(self.mycall, src, path=f.reply_path(), cfg=self.link_cfg, now=now)
        tmp.receive(f, now)
        for out in tmp.pop_output():
            self.transmit(out, None)

    # --- kisshub status -------------------------------------------------------------

    async def _hub_poll(self) -> None:
        """Which TNC, and is it in KISS? (kisshub GET /status, loopback only)."""
        if self.cfg.kiss_status_port <= 0:
            return
        while True:
            try:
                st = await fetch_hub_status(self.cfg.kiss_host, self.cfg.kiss_status_port)
                tnc = st.get("tnc") or {}
                self.hub = {"tnc": tnc.get("name"), "state": tnc.get("state"),
                            "error": tnc.get("last_error")}
            except (OSError, asyncio.TimeoutError, ValueError):
                self.hub = None
            await asyncio.sleep(HUB_POLL_SEC)

    def radio_state(self) -> dict:
        h = self.hub or {}
        return {"via": "kiss", "up": self.kiss.connected.is_set(), "tnc": h.get("tnc"),
                "tnc_state": h.get("state"), "error": h.get("error")}


async def fetch_hub_status(host: str, port: int, timeout: float = 3.0) -> dict:
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


class KissLink(BaseLink):
    """One AX.25 connection over the KissPort, for one channel."""
    kind = "kiss"

    def __init__(self, port: KissPort, cfg: Config, on_state, on_line) -> None:
        super().__init__(cfg, on_state, on_line)
        self.port = port
        self.agw_up = port.agw_up
        self.ax: Ax25Link | None = None

    def _forget(self) -> None:
        if self.port.links.get(self.target) is self:
            del self.port.links[self.target]
        self.ax = None

    def on_event(self, name: str, arg) -> None:
        if name == "connected":
            if self.ax and self.ax.peer_version == "2.0":
                self.port.v20.add(self.target)
            if arg == "incoming":
                self._fresh()
            self._set("online")
        elif name == "data":
            self.rx_bytes += len(arg)
            self.splitter.feed(arg)
        elif name == "disconnected":
            if self.ax is not None and self.ax.peer_v20:
                self.port.v20.add(self.target)
            self._forget()
            if self.active:
                self._set("offline", REASONS.get(arg, str(arg)))

    async def connect(self) -> None:
        if not self.agw_up.is_set():
            self._set("offline", "kisshub not reachable")
            return
        if self.target in self.port.links:
            self._set("offline", f"already connected to {self.target}")
            return
        now = self.port.now()
        self._fresh()
        self.ax = Ax25Link(self.port.mycall, self.target, cfg=self.port.link_cfg, now=now,
                           peer_v20=self.target in self.port.v20)
        self.port.links[self.target] = self
        self._set("connecting")
        self.ax.connect(now)
        self.port.service(self)

    def send_line(self, text: str) -> None:
        self.send_bytes((text + "\r").encode("utf-8"))

    def send_bytes(self, data: bytes) -> None:
        if self.ax is None:
            return
        self.tx_bytes += len(data)
        self.ax.send(data, self.port.now())
        self.port.service(self)

    async def outstanding(self) -> int:
        """Frames not yet acknowledged or not yet sent."""
        return (len(self.ax.queue) + self.ax.unacked) if self.ax else 0

    def disconnect(self) -> None:
        if not self.active or self.ax is None:
            return
        if self.online:
            self._set("disconnecting")
        self.ax.disconnect(self.port.now())       # connecting: gone at once ("local")
        self.port.service(self)

    def drop(self, reason: str) -> None:
        self._forget()
        super().drop(reason)
