"""KISS adapter: TinyBox's own AX.25 layer 2 instead of Direwolf/AGW (KISS step K4).

docs/kiss-mode-konzept.md, PLANUNG.md section 15. Selected with

    [radio]
    interface = kiss

TinyBox talks KISS over TCP to kisshub (which owns the TNC) or to Direwolf's
KISS port. Everything above the connection - Session, chat, forwarding,
client sync, link quality - is the same as with AGW: KissAdapter is an
AgwAdapter with another way to the radio, KissConnection an AgwConnection
whose output goes into an Ax25Link instead of AGW 'D' frames.

    KISS-TCP  ->  frame router  ->  Ax25Link per station (tinybox/ax25/link.py)
                                        |  events: connected / data / disconnected
                                        v
                                  KissConnection -> Session / forward link

Router (no Direwolf 'X' registration any more, TinyBox sees every frame):
    not to the mailbox call                 -> only pauses T1 of all links
    digipeater path not fully repeated      -> ignored (still on its way)
    SABM / SABME to the mailbox call        -> new Ax25Link
    anything else for a known station       -> that link
    I / S / DISC from an unknown station    -> DM (a throw-away link answers)

Differences to AGW:
    - the link quality comes straight from the link (no Direwolf fork needed)
    - a lost KISS-TCP connection does not end the AX.25 links: frames sent
      meanwhile are lost and the links recover by their own timers
    - stations that answered SABME with DM are remembered (v2.0, next time SABM)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

from .. import chanmon, framemon, logsetup
from ..app import App
from prcore.ax25 import frame as ax
from prcore.ax25.frame import AX25Error, Frame
from prcore.kiss import KissTcpClient
from prcore.ax25.link import Ax25Link, LinkCfg
from ..config import Config, normalize_call
from .agw import DRAIN_TIMEOUT, AgwAdapter, AgwConnection

log = logging.getLogger(__name__)
monitor = logging.getLogger("tinybox.monitor.kiss")


def link_cfg(cfg: Config) -> LinkCfg:
    a, k = cfg.ax25, cfg.kiss
    return LinkCfg(paclen=a.paclen, maxframe=a.maxframe, maxframe_ext=a.maxframe_ext,
                   srej=a.srej, n2=a.n2, version=a.version, srt_init_sec=a.srt_init_sec,
                   t1_min_sec=a.t1_min_sec, t1_max_sec=a.t1_max_sec, t2_sec=a.t2_sec,
                   t3_sec=a.t3_sec, air_baud=k.air_baud, txdelay_sec=k.txdelay_ms / 1000,
                   max_rx_info=max(512, a.paclen))


def _call(call: str) -> str:
    call = normalize_call(call)
    return call[:-2] if call.endswith("-0") else call


class KissConnection(AgwConnection):
    """One AX.25 connection; output goes into the link, which cuts it into I frames."""

    def __init__(self, adapter: "KissAdapter", remote: str) -> None:
        super().__init__(adapter, remote)
        self.link: Ax25Link = adapter.links[remote]

    def write_bytes(self, data: bytes) -> None:
        if self.gone or not data:
            return
        self.tx_bytes += len(data)
        self.link.send(data, self.adapter.now())
        self.adapter.service(self.link)

    def abort_output(self) -> None:
        dropped = len(self.link.queue)
        self.link.queue.clear()
        log.debug("%s: output aborted, %d packets dropped", self.remote, dropped)

    async def pump(self) -> None:
        """No polling as with AGW 'Y': the link sends by itself. Only wait for close()."""
        try:
            while not self.gone:
                if self.closing:
                    await self._drain_and_disconnect()
                    return
                self._wakeup.clear()
                await self._wakeup.wait()
        except asyncio.CancelledError:
            pass

    async def _drain_and_disconnect(self) -> None:
        deadline = time.monotonic() + DRAIN_TIMEOUT
        while (not self.gone and self.link.connected and not self.link.is_idle
               and time.monotonic() < deadline):
            await asyncio.sleep(0.2)
        if not self.gone and self.link.connected:
            log.info("%s: disconnecting", self.remote)
            self.link.disconnect(self.adapter.now())
            self.adapter.service(self.link)


class KissAdapter(AgwAdapter):
    conn_class = KissConnection

    def __init__(self, app: App) -> None:
        super().__init__(app)
        k = self.cfg.kiss
        self.mycall = _call(self.cfg.station.mailbox_call)
        self.radio_port = k.channel
        self.link_cfg = link_cfg(self.cfg)
        self.links: dict[str, Ax25Link] = {}
        self.v20_calls: set[str] = set()       # answered SABME with DM: call with SABM
        self.q_supported = True                # quality comes from our own links
        self.kiss = KissTcpClient(k.host, k.port, self._on_kiss_frame,
                                  reconnect_sec=k.reconnect_sec, kiss_port=k.channel)
        self.connected = self.kiss.connected
        self._kick = asyncio.Event()
        # CR41: channel monitor (from the KISS stream) and kisshub's status
        self.channel = chanmon.ChannelMonitor(self.mycall, k.air_baud, k.txdelay_ms / 1000)
        self.hub_status: dict | None = None     # last answer of kisshub's /status
        self.hub_status_at: float | None = None  # time.monotonic() of that answer
        self.hub_error: str | None = None       # why the last query failed

    def describe(self) -> str:
        return f"KISS {self.cfg.kiss.host}:{self.cfg.kiss.port}"

    @staticmethod
    def now() -> float:
        return time.monotonic()

    # --- main loop --------------------------------------------------------------

    async def run(self) -> None:
        log.info("KISS mode: own AX.25 layer 2 (version %s), KISS %s:%d",
                 self.link_cfg.version, self.cfg.kiss.host, self.cfg.kiss.port)
        tasks = [asyncio.create_task(self._timer_loop()),
                 asyncio.create_task(self._idle_watchdog()),
                 asyncio.create_task(self._quality_poll()),
                 asyncio.create_task(self._hub_poll())]
        try:
            await self.kiss.run()
        finally:
            for t in tasks:
                t.cancel()
            self._drop_all()

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

    # --- sending -------------------------------------------------------------------

    def _airtime(self, nbytes: int) -> float:
        c = self.link_cfg
        return c.txdelay_sec + (nbytes + 4) * 8 / c.air_baud

    def _transmit(self, f: Frame, source: Ax25Link | None) -> None:
        raw = f.encode()
        if not self.kiss.send(raw):
            log.debug("KISS down, frame lost: %s", f)
        logsetup.counters.frames_out += 1
        log.debug(">> %s", f)
        self.channel.record(self.mycall, len(raw), path=f.path)
        framemon.emit(raw, tx=True, mycall=self.mycall, mod128=f.modulo == 128)   # CR52
        # one transmitter for all: our other links could not be answered meanwhile
        air = self._airtime(len(raw))
        now = self.now()
        for link in self.links.values():
            if link is not source:
                link.channel_busy(air, now)

    def service(self, link: Ax25Link) -> None:
        """Send what the link produced and hand its events on. Call after every
        call into a link."""
        for f in link.pop_output():
            self._transmit(f, link)
        for name, arg in link.pop_events():
            try:
                self._on_link_event(link, name, arg)
            except Exception:
                log.exception("%s: error handling link event %s", link.remote, name)
        self._kick.set()

    def send_ui(self, dest: str, text: str, path: list[str] | None = None) -> None:
        """One UI frame (unproto) from the mailbox call, e.g. to TBCHAT-1."""
        try:
            f = ax.ui_frame(dest, self.mycall, text.encode("utf-8"), path=path or None)
        except AX25Error as exc:
            log.warning("UI frame to %s not sent: %s", dest, exc)
            return
        self._transmit(f, None)
        monitor.info("UI %s > %s", dest, text)

    # --- receiving -------------------------------------------------------------------

    def _on_kiss_frame(self, port: int, data: bytes) -> None:
        now = self.now()
        try:
            dest, src, path, repeated = ax.peek(data)
        except AX25Error as exc:
            log.debug("undecodable frame ignored: %s", exc)
            return
        self.channel.record(src, len(data),
                            path=[c + ("*" if h else "") for c, h in zip(path, repeated)])
        target = self.links.get(src) if dest == self.mycall else None
        # CR52: every frame heard goes to the web monitor; a known link knows its modulo
        known = target or (self.links.get(dest) if src == self.mycall else None)
        framemon.emit(data, tx=False, mycall=self.mycall,
                      mod128=(known.modulo == 128) if known else None)
        air = self._airtime(len(data))
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
        logsetup.counters.frames_in += 1
        conn = self.conns.get(src)
        with logsetup.session_context(getattr(conn, "log_ctx", None) or logsetup.NO_SESSION):
            log.debug("<< %s", f)
            self._route(f, target, now)

    def _route(self, f: Frame, link: Ax25Link | None, now: float) -> None:
        if f.kind == "UI":
            return                                 # nothing for the mailbox call itself
        if link is None:
            if f.kind in ("SABM", "SABME") and f.command:
                link = Ax25Link(self.mycall, f.src, path=f.reply_path(), cfg=self.link_cfg,
                                now=now)
                self.links[f.src] = link
            else:                                  # a stranger: DM and forget
                tmp = Ax25Link(self.mycall, f.src, path=f.reply_path(), cfg=self.link_cfg,
                               now=now)
                tmp.receive(f, now)
                for out in tmp.pop_output():
                    self._transmit(out, None)
                return
        link.receive(f, now)
        self.service(link)

    def _on_link_event(self, link: Ax25Link, name: str, arg) -> None:
        remote = link.remote
        if name == "connected":
            if link.peer_version == "2.0":
                self.v20_calls.add(remote)
            else:
                self.v20_calls.discard(remote)
            log.info("%s: AX.25 %s link up (%s, modulo %d)", remote, arg,
                     link.peer_version, link.modulo)
            if arg == "outgoing":
                fut = self._pending.pop(remote, None)
                if fut is not None and not fut.done():
                    self._on_outgoing_connected(remote, fut)
                else:                              # nobody waits for it any more
                    link.disconnect(self.now())
            else:
                self._on_connect(remote)
        elif name == "data":
            conn = self.conns.get(remote)
            if conn is not None:
                conn.feed(arg)
        elif name == "reset":
            log.warning("%s: link re-established (%s) - data in flight may be lost",
                        remote, arg)
        elif name == "disconnected":
            if self.links.get(remote) is link:
                del self.links[remote]
            if link.peer_v20:
                self.v20_calls.add(remote)
            fut = self._pending.pop(remote, None)
            if fut is not None and not fut.done():
                fut.set_exception(ConnectionError(f"connect to {remote} failed ({arg})"))
            self._on_disconnect(remote, lost=arg == "retryout")

    # --- outgoing connects (forward module) ------------------------------------------------

    async def connect(self, remote: str, attach, via: list[str] | None = None,
                      timeout: float = 120) -> AgwConnection:
        remote = _call(remote)
        if not self.connected.is_set():
            raise ConnectionError("KISS link is not connected")
        if remote in self.conns or remote in self._pending or remote in self.links:
            raise ConnectionError(f"already connected to {remote}")
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        fut.attach = attach  # type: ignore[attr-defined]
        self._pending[remote] = fut
        now = self.now()
        link = Ax25Link(self.mycall, remote, path=[_call(v) for v in via or []],
                        cfg=self.link_cfg, now=now, peer_v20=remote in self.v20_calls)
        self.links[remote] = link
        log.info("connecting to %s%s", remote, f" via {','.join(via)}" if via else "")
        started = time.monotonic()
        link.connect(now)
        self.service(link)
        try:
            conn = await asyncio.wait_for(fut, timeout)
            log.info("link to %s up %s", remote, logsetup.ms(started))
            return conn
        except (asyncio.TimeoutError, ConnectionError) as exc:
            log.warning("connect to %s failed after %s: %s", remote,
                        logsetup.ms(started), exc or type(exc).__name__)
            if self.links.get(remote) is link and not link.connected:
                link.disconnect(self.now())           # stop calling
                self.service(link)
            raise
        finally:
            self._pending.pop(remote, None)

    # --- link quality: straight from the link -----------------------------------------------

    def ask_quality(self, remote: str) -> None:
        link, conn = self.links.get(remote), self.conns.get(remote)
        if link is not None and conn is not None:
            conn.quality.add(link.counters(self.now()))
        self._q_reply.set()

    # --- kisshub status (CR41, Weg 2) ---------------------------------------------------------

    async def _hub_poll(self) -> None:
        """Ask kisshub for the state of the TNC every quality_poll_sec (30 s)."""
        port = self.cfg.kiss.status_port
        every = self.cfg.direwolf.quality_poll_sec or 30
        if port <= 0:
            return
        while True:
            try:
                self.hub_status = await fetch_hub_status(self.cfg.kiss.host, port)
                self.hub_status_at = time.monotonic()
                self.hub_error = None
            except (OSError, asyncio.TimeoutError, ValueError) as exc:
                if self.hub_error is None:
                    log.info("kisshub status %s:%d not available (%s)", self.cfg.kiss.host,
                             port, exc or type(exc).__name__)
                self.hub_error = str(exc) or type(exc).__name__
                self.hub_status = None
            self.app.bus.publish("link.quality")          # web GUI: refresh
            await asyncio.sleep(every)

    def radio_state(self) -> dict:
        """What the header and STATUS show: link to kisshub plus the TNC behind it."""
        st = self.hub_status or {}
        tnc = st.get("tnc") or {}
        hub_ok = self.cfg.kiss.status_port <= 0 or self.hub_status is not None
        tnc_state = tnc.get("state")
        ready = self.connected.is_set() and (tnc_state in (None, "kiss"))
        return {"interface": "kiss", "connected": self.connected.is_set(),
                "hub": "off" if self.cfg.kiss.status_port <= 0
                       else ("ok" if hub_ok else "unreachable"),
                "tnc": tnc.get("name") or None, "tnc_state": tnc_state,
                "tnc_error": tnc.get("last_error"), "ready": ready}

    def channel_snapshot(self) -> dict:
        out = self.channel.snapshot()
        out["hub"] = self.hub_status
        out["hub_age"] = (None if self.hub_status_at is None
                          else round(time.monotonic() - self.hub_status_at))
        out["hub_error"] = self.hub_error
        out["radio"] = self.radio_state()
        return out


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
