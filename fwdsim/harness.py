"""Glue for test runs: the simulated network, its listeners and the target.

OE3GAS is reachable for the target over TCP (always) and AGW (if enabled).
Sessions the target opens to OE3GAS land in `incoming`.
"""

from __future__ import annotations

import asyncio
import logging
import secrets

from .agw import AgwClient, AgwLink
from .config import Config
from .link import Link, TcpLink, tcp_connect
from .net import SimNet, make_standin
from .session import Faults, ForwardSession, SessionResult
from .store import Store
from .targets import StubTarget, TinyboxTarget

log = logging.getLogger("fwdsim.harness")


async def tinybox_login(link: Link, call: str, password: str, timeout: float) -> None:
    """TinyBox's TCP forward port asks 'Callsign:' and 'Password:' first."""
    for prompt, answer in (("CALLSIGN", call), ("PASSWORD", password)):
        while True:
            line = await link.readline(timeout)
            if line is None:
                raise ConnectionError("TinyBox closed the forward port during login")
            if line.strip().upper().startswith(prompt):
                link.write_line(answer)
                await link.drain()
                break


class Harness:
    def __init__(self, cfg: Config, store: Store, *, stub: bool, use_agw: bool,
                 stub_timeout: float = 10) -> None:
        self.cfg = cfg
        self.store = store
        self.net = SimNet(cfg, store)
        self.hop, self.remote = self.net.hop, self.net.remote
        self.use_agw = use_agw and not stub
        self.timeout = cfg.timeout_radio if self.use_agw else cfg.timeout_tcp
        if stub:
            self.timeout = stub_timeout
            self.target = StubTarget(cfg, make_standin(cfg, store), stub_timeout)
        else:
            self.target = TinyboxTarget(cfg)
        self.incoming: asyncio.Queue[SessionResult] = asyncio.Queue()
        self.next_faults: Faults | None = None
        self.server: asyncio.AbstractServer | None = None
        self.agw: AgwClient | None = None
        self.run_id = secrets.token_hex(2).upper()

    # --- lifecycle ----------------------------------------------------------------

    async def start(self) -> None:
        await self.target.start()
        port = 0 if isinstance(self.target, StubTarget) else self.cfg.tcp_listen_port

        async def tcp_in(reader, writer):
            await self._serve(TcpLink(reader, writer, f"{self.hop.call}<tcp"))

        self.server = await asyncio.start_server(tcp_in, self.cfg.tcp_listen_host, port)
        self.listen_port = self.server.sockets[0].getsockname()[1]
        log.info("%s listens on TCP %s:%d", self.hop.call, self.cfg.tcp_listen_host,
                 self.listen_port)
        if self.use_agw:
            self.agw = AgwClient(self.cfg.agw, self.cfg.hop_ax25_call, self._serve_agw)
            await self.agw.start()

    async def stop(self) -> None:
        if self.server:
            self.server.close()
        if self.agw:
            await self.agw.stop()
        await self.target.stop()

    async def _serve_agw(self, link: AgwLink) -> None:
        await self._serve(link)

    async def _serve(self, link: Link) -> None:
        faults, self.next_faults = self.next_faults, None
        s = ForwardSession(self.hop, link, self.target.call, master=False,
                           faults=faults, timeout=self.timeout)
        result = await s.run()
        await self.net.settle()
        await self.incoming.put(result)

    # --- actions ------------------------------------------------------------------

    def tag(self, tid: str, extra: str = "") -> str:
        return f"{tid} {self.run_id}{(' ' + extra) if extra else ''}"

    async def hop_calls_target(self, faults: Faults | None = None) -> SessionResult:
        """OE3GAS connects to the target and hands over its queue (reverse forward included)."""
        await self.net.settle()
        if isinstance(self.target, StubTarget):
            link: Link = await tcp_connect("127.0.0.1", self.target.port, f"{self.hop.call}>stub")
        elif self.use_agw:
            assert self.agw is not None
            link = await self.agw.connect(self.cfg.tinybox.ax25_call, self.cfg.agw.via,
                                          timeout=self.timeout)
        else:
            t = self.cfg.tinybox
            if not t.forward_port:
                raise RuntimeError("[tinybox] forward_port is not set - TinyBox has no "
                                   "incoming forward port to call")
            link = await tcp_connect(t.forward_host, t.forward_port, f"{self.hop.call}>tinybox")
            await tinybox_login(link, self.hop.call, t.forward_password, self.timeout)
        s = ForwardSession(self.hop, link, self.target.call, master=True,
                           faults=faults, timeout=self.timeout)
        result = await s.run()
        if isinstance(self.target, StubTarget):
            try:
                await asyncio.wait_for(self.target.slave_results.get(), self.timeout + 5)
            except asyncio.TimeoutError:
                pass
        await self.net.settle()
        return result

    async def target_calls_hop(self, faults: Faults | None = None,
                               wait: float | None = None) -> SessionResult | None:
        """The target forwards to OE3GAS. The stub is told to call; the real TinyBox is
        expected to call by itself (it has mail queued). Returns OE3GAS's view or None."""
        self.next_faults = faults
        if isinstance(self.target, StubTarget):
            link = await tcp_connect("127.0.0.1", self.listen_port, f"stub>{self.hop.call}")
            s = ForwardSession(self.target.bbs, link, self.hop.call, master=True,
                               timeout=self.timeout)
            await s.run()
        try:
            return await asyncio.wait_for(self.incoming.get(),
                                          wait if wait is not None else self.cfg.wait_for_tinybox)
        except asyncio.TimeoutError:
            self.next_faults = None
            return None

    def drop_queue(self, bid: str) -> None:
        """Remove a message from all simulated queues (after a fault test)."""
        for bbs in (self.hop, self.remote):
            for m in bbs.find(bid=bid):
                for peer in bbs.store.queue_states(bbs.call, m.id):
                    bbs.store.set_queue(bbs.call, m.id, peer, "rejected")
