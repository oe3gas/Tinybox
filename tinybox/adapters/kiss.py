"""KISS adapter: TinyBox's own AX.25 layer 2 instead of Direwolf/AGW (KISS step K4).

docs/kiss-mode-konzept.md, PLANUNG.md section 15. Selected with

    [radio]
    interface = kiss

TinyBox talks KISS over TCP to kisshub (which owns the TNC) or to Direwolf's
KISS port. Everything above the connection - Session, chat, forwarding,
client sync, link quality - is the same as with AGW: KissAdapter is an
AgwAdapter with another way to the radio, KissConnection an AgwConnection
whose output goes into an Ax25Link instead of AGW 'D' frames.

    KISS-TCP  ->  frame router  ->  Ax25Link per station (prcore/kissport.py)
                                        |  events: connected / data / disconnected
                                        v
                                  KissConnection -> Session / forward link

Router (no Direwolf 'X' registration any more, TinyBox sees every frame):
    not to the mailbox call                 -> only pauses T1 of all links
    digipeater path not fully repeated      -> ignored (still on its way)
    SABM / SABME to the mailbox call        -> new Ax25Link
    anything else for a known station       -> that link
    I / S / DISC from an unknown station    -> DM (a throw-away link answers)

The KISS port itself (link timers, routing, airtime, DM for strangers, v2.0
memory, kisshub status) is prcore/kissport.py, shared with the client; this
module adds the BBS side: sessions, monitor, channel statistics.

Differences to AGW:
    - the link quality comes straight from the link (no Direwolf fork needed)
    - a lost KISS-TCP connection does not end the AX.25 links: frames sent
      meanwhile are lost and the links recover by their own timers
    - stations that answered SABME with DM are remembered (v2.0, next time SABM)
"""

from __future__ import annotations

import asyncio
import logging
import time

from prcore.ax25 import frame as ax
from prcore.ax25.frame import AX25Error, Frame
from prcore.ax25.link import Ax25Link, LinkCfg
from prcore.kissport import KissPort, describe_changes, norm_call, poll_hub

from .. import chanmon, framemon, logsetup
from ..app import App
from ..config import Config
from .agw import DRAIN_TIMEOUT, AgwAdapter, AgwConnection

log = logging.getLogger(__name__)
monitor = logging.getLogger("tinybox.monitor.kiss")


def link_cfg(cfg: Config) -> LinkCfg:
    a, k = cfg.ax25, cfg.kiss
    return LinkCfg(paclen=a.paclen, maxframe=a.maxframe, maxframe_ext=a.maxframe_ext,
                   srej=a.srej, n2=a.n2, version=a.version, srt_init_sec=a.srt_init_sec,
                   t1_min_sec=a.t1_min_sec, t1_max_sec=a.t1_max_sec, t2_sec=a.t2_sec,
                   t3_sec=a.t3_sec, v20_digis=a.v20_digis,
                   v20_digi_paclen=a.v20_digi_paclen, air_baud=k.air_baud, txdelay_sec=k.txdelay_ms / 1000,
                   max_rx_info=max(512, a.paclen))


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


class _BoxPort(KissPort):
    """The shared KISS port with the TinyBox's monitor, statistics and sessions."""

    def __init__(self, adapter: "KissAdapter") -> None:
        k = adapter.cfg.kiss
        super().__init__(adapter.cfg.station.mailbox_call, k.host, k.port,
                         link_cfg(adapter.cfg), channel=k.channel,
                         reconnect_sec=k.reconnect_sec)
        self.adapter = adapter

    def on_heard(self, data: bytes, peeked: tuple | None, target: Ax25Link | None) -> None:
        if peeked is None:
            return
        dest, src, path, repeated = peeked
        a = self.adapter
        a.channel.record(src, len(data),
                         path=[c + ("*" if h else "") for c, h in zip(path, repeated)])
        # CR52: every frame heard goes to the web monitor; a known link knows its modulo
        known = target or (self.links.get(dest) if src == self.mycall else None)
        framemon.emit(data, tx=False, mycall=self.mycall,
                      mod128=(known.modulo == 128) if known else None)

    def on_transmit(self, f: Frame, raw: bytes) -> None:
        logsetup.counters.frames_out += 1
        self.adapter.channel.record(self.mycall, len(raw), path=f.path)
        framemon.emit(raw, tx=True, mycall=self.mycall, mod128=f.modulo == 128)   # CR52

    def received(self, f: Frame, target: Ax25Link | None, now: float) -> None:
        logsetup.counters.frames_in += 1
        conn = self.adapter.conns.get(norm_call(f.src))
        with logsetup.session_context(getattr(conn, "log_ctx", None) or logsetup.NO_SESSION):
            log.debug("<< %s", f)
            super().received(f, target, now)

    def on_link_event(self, link: Ax25Link, name: str, arg) -> None:
        self.adapter._on_link_event(link, name, arg)


class KissAdapter(AgwAdapter):
    conn_class = KissConnection

    def __init__(self, app: App) -> None:
        super().__init__(app)
        k = self.cfg.kiss
        self.port = _BoxPort(self)
        self.mycall = self.port.mycall
        self.radio_port = k.channel
        self.link_cfg = self.port.link_cfg
        self.kiss = self.port.kiss
        self.connected = self.port.connected
        self.q_supported = True                # quality comes from our own links
        # CR41: channel monitor (from the KISS stream) and kisshub's status
        self.channel = chanmon.ChannelMonitor(self.mycall, k.air_baud, k.txdelay_ms / 1000)
        self.hub_status: dict | None = None     # last answer of kisshub's /status
        self.hub_status_at: float | None = None  # time.monotonic() of that answer
        self.hub_error: str | None = None       # why the last query failed

    @property
    def links(self) -> dict[str, Ax25Link]:
        return self.port.links

    @property
    def v20_calls(self) -> set[str]:
        return self.port.v20

    def describe(self) -> str:
        return f"KISS {self.cfg.kiss.host}:{self.cfg.kiss.port}"

    @staticmethod
    def now() -> float:
        return time.monotonic()

    def service(self, link: Ax25Link) -> None:
        self.port.service(link)

    # --- main loop --------------------------------------------------------------

    async def run(self) -> None:
        log.info("KISS mode: own AX.25 layer 2 (version %s), KISS %s:%d",
                 self.link_cfg.version, self.cfg.kiss.host, self.cfg.kiss.port)
        k = self.cfg.kiss
        try:
            await self.port.run(self._idle_watchdog(), self._quality_poll(),
                                poll_hub(k.host, k.status_port,
                                         self.cfg.direwolf.quality_poll_sec or 30,
                                         self._on_hub_status))
        finally:
            self._drop_all()

    def send_ui(self, dest: str, text: str, path: list[str] | None = None) -> None:
        """One UI frame (unproto) from the mailbox call, e.g. to TBCHAT-1."""
        try:
            f = ax.ui_frame(dest, self.mycall, text.encode("utf-8"), path=path or None)
        except AX25Error as exc:
            log.warning("UI frame to %s not sent: %s", dest, exc)
            return
        self.port.transmit(f, None)
        monitor.info("UI %s > %s", dest, text)

    # --- link events (the port keeps links and v2.0 memory up to date) ---------------

    def _on_link_event(self, link: Ax25Link, name: str, arg) -> None:
        remote = link.remote
        if name == "connected":
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
            fut = self._pending.pop(remote, None)
            if fut is not None and not fut.done():
                fut.set_exception(ConnectionError(f"connect to {remote} failed ({arg})"))
            self._on_disconnect(remote, lost=arg == "retryout")

    # --- outgoing connects (forward module) ------------------------------------------------

    async def connect(self, remote: str, attach, via: list[str] | None = None,
                      timeout: float = 120) -> AgwConnection:
        remote = norm_call(remote)
        if not self.connected.is_set():
            raise ConnectionError("KISS link is not connected")
        if remote in self.conns or remote in self._pending or remote in self.links:
            raise ConnectionError(f"already connected to {remote}")
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        fut.attach = attach  # type: ignore[attr-defined]
        self._pending[remote] = fut
        link = self.port.open_link(remote, via)
        log.info("connecting to %s%s", remote, f" via {','.join(via)}" if via else "")
        started = time.monotonic()
        link.connect(self.now())
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

    def _on_hub_status(self, status: dict | None, exc: Exception | None) -> None:
        """Every quality_poll_sec (30 s): the state of the TNC behind kisshub."""
        if exc is None:
            self.hub_status = status
            self.hub_status_at = time.monotonic()
            self.hub_error = None
            changed = self.port.apply_hub_status(status, self.cfg.kiss_fixed)   # CR70
            if changed:
                self.link_cfg = self.port.link_cfg
                src = ((status or {}).get("radio") or {}).get("source") or {}
                log.info("radio values from kisshub (%s): %s", src.get("air_baud", "?"),
                         describe_changes(changed))
        else:
            if self.hub_error is None:
                log.info("kisshub status %s:%d not available (%s)", self.cfg.kiss.host,
                         self.cfg.kiss.status_port, exc or type(exc).__name__)
            self.hub_error = str(exc) or type(exc).__name__
            self.hub_status = None
        self.app.bus.publish("link.quality")          # web GUI: refresh

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
