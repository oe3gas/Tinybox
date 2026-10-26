"""AXUDP adapter: a second port next to the radio (PLANUNG.md section 25, step 2).

    [axudp]
    enabled = yes
    listen  = 127.0.0.1
    port    = 10093
    peers   = OE3GAS 127.0.0.1:10094

The TinyBox's own AX.25 (prcore/kissport.py, as in the KISS mode) over UDP
(prcore/axudp.py) instead of KISS-TCP. Everything above the link - Session,
chat, client sync, images, compression - is the same as over the radio: the
AxudpAdapter is a KissAdapter with another port. Use: the TinyBox client on the
same PC reaches its home box without the radio, while it uses the radio for
every other station (one transceiver for both).

What stays with the radio adapter (app.agw): UI frames (chat events to
TBCHAT-n, beacon), monitor, channel statistics, link quality via Direwolf.
Over AXUDP there is no airtime: no half duplex, short T1, large window.

Security: AXUDP has no login. Only frames from a listed peer IP with that
peer's source call are accepted (prcore/axudp.py); for now listen and peers
must be loopback (config.py). Sysop rights only for the sysop call from a
loopback peer - like the telnet port.
"""

from __future__ import annotations

import logging

from prcore import axudp as udp
from prcore.ax25.frame import Frame
from prcore.ax25.link import Ax25Link, LinkCfg
from prcore.kissport import KissPort, norm_call

from .. import logsetup
from ..app import App
from ..config import Config
from .kiss import KissAdapter

log = logging.getLogger(__name__)


def axudp_link_cfg(cfg: Config) -> LinkCfg:
    """AX.25 values for a link without airtime."""
    a = cfg.axudp
    return LinkCfg(paclen=a.paclen, maxframe=7, maxframe_ext=a.maxframe_ext, n2=a.n2,
                   version="2.2", srt_init_sec=a.t1_sec / 2, t1_min_sec=a.t1_sec,
                   t1_max_sec=max(a.t1_sec * 4, 10.0), t2_sec=0.05, t3_sec=300.0,
                   air_baud=10_000_000, txdelay_sec=0.0, srej=cfg.ax25.srej,
                   max_rx_info=max(512, a.paclen))


class _UdpPort(KissPort):
    def __init__(self, adapter: "AxudpAdapter") -> None:
        a = adapter.cfg.axudp
        super().__init__(adapter.cfg.station.mailbox_call, a.listen, a.port,
                         axudp_link_cfg(adapter.cfg), half_duplex=False,
                         transport=lambda on_frame: udp.AxudpEndpoint(
                             a.listen, a.port, a.peers, on_frame))
        self.adapter = adapter

    def on_transmit(self, f: Frame, raw: bytes) -> None:
        logsetup.counters.frames_out += 1

    def received(self, f: Frame, target: Ax25Link | None, now: float) -> None:
        logsetup.counters.frames_in += 1
        conn = self.adapter.conns.get(norm_call(f.src))
        with logsetup.session_context(getattr(conn, "log_ctx", None) or logsetup.NO_SESSION):
            log.debug("<< %s", f)
            super().received(f, target, now)

    def on_link_event(self, link: Ax25Link, name: str, arg) -> None:
        self.adapter._on_link_event(link, name, arg)


class AxudpAdapter(KissAdapter):
    origin = "axudp"
    owns_ui = False                 # the radio adapter keeps the chat's UI frames

    def __init__(self, app: App) -> None:
        super().__init__(app)
        self.radio_port = 0
        self.endpoint: udp.AxudpEndpoint = self.port.kiss

    def _make_port(self) -> KissPort:
        return _UdpPort(self)

    def describe(self) -> str:
        a = self.cfg.axudp
        return f"AXUDP {a.listen}:{a.port}"

    def port_label(self) -> str:
        return "axudp"

    def _sysop_allowed(self, remote: str) -> bool:
        """Only the sysop call from a loopback peer (like telnet)."""
        if not self.app.service.is_sysop_call(remote):
            return False
        peer = self.endpoint.table.owner(remote)
        return peer is not None and udp.is_loopback(peer.host)

    async def run(self) -> None:
        a = self.cfg.axudp
        log.info("AXUDP port %s:%d, peers %s", a.listen, a.port,
                 ", ".join(f"{p.call} {p.host}:{p.port}" for p in a.peers.values()))
        try:
            await self.port.run(self._idle_watchdog())
        finally:
            self._drop_all()

    def send_ui(self, dest: str, text: str, path: list[str] | None = None) -> None:
        log.debug("UI frame to %s not sent over AXUDP", dest)

    def state(self) -> dict:
        """For STATUS and the web GUI."""
        ep = self.endpoint
        return {"listen": f"{self.cfg.axudp.listen}:{self.cfg.axudp.port}",
                "up": self.connected.is_set(), "peers": sorted(self.cfg.axudp.peers),
                "links": sorted(self.conns), "rx": ep.rx_frames, "tx": ep.tx_frames,
                "dropped": dict(ep.dropped)}
