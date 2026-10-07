"""Forward module: exchange mail with partner mailboxes ([forward] enabled = yes).

Started by __main__ only when enabled; without it TinyBox is a standalone mailbox.

- listens to the event bus: new mail with fwd '$' goes into the queue of the
  partner(s) the router picks; deleted / expired mail leaves the queue
- answers partner connects: over AGW (the AGW adapter hands them over) and on
  the TCP forward port ([forward] listen_port, with callsign + password login)
- calls partners: FWD <call> on the sysop console (automatic schedule: F4)

F3: sessions receive mail (tinybox/fwd/session.py, receive.py); sending follows in F4.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..app import App
from ..config import LOOPBACK_HOSTS, PartnerCfg, normalize_call
from ..fwd.link import AgwLink, TcpLink
from ..fwd.router import Router
from ..fwd.session import ForwardSession, SessionResult

log = logging.getLogger("tinybox.forward")

LOGIN_TIMEOUT = 60


class ForwardModule:
    def __init__(self, app: App) -> None:
        self.app = app
        self.cfg = app.cfg.forward
        self.router = Router(self.cfg)
        self.busy: set[str] = set()                       # partners in a session now
        self.last: dict[str, SessionResult] = {}          # last result per partner
        self.server: asyncio.AbstractServer | None = None
        self.listen_port = 0
        self.tasks: set[asyncio.Task] = set()
        for name in ("message.created", "message.deleted", "message.expired"):
            app.bus.subscribe(name, self.on_event)

    # --- queue -----------------------------------------------------------------

    def on_event(self, name: str, data: dict[str, Any]) -> None:
        store = self.app.store
        if name == "message.created":
            msg = data["message"]
            if msg is None or msg.fwd != "$":
                return
            targets = self.router.targets(msg)
            if not targets and msg.type == "B":
                # a bulletin nobody else needs (e.g. all partners already had it):
                # it is simply ours now, nothing to forward - not held
                self.app.service.set_fwd_state(msg.id, "", "")
                return
            if not targets:
                log.warning("msg %d (%s) @ %s: no partner - held", msg.id, msg.bid, msg.at_addr)
                self.app.service.set_fwd_state(msg.id, "H", "no route to " + msg.at_addr)
                return
            for partner in targets:
                store.fwd_enqueue(msg.id, partner)
            log.info("msg %d (%s) queued for %s", msg.id, msg.bid, ", ".join(targets))
        elif name == "message.deleted":
            store.fwd_remove([data["message"].id])
        elif name == "message.expired":
            store.fwd_remove(list(data.get("ids", [])))

    # --- partners ----------------------------------------------------------------

    def partner_for_radio(self, remote: str) -> PartnerCfg | None:
        p = self.cfg.partner_by_radio_call(remote)
        return p if p is not None and p.transport == "agw" else None

    def _spawn(self, coro) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    async def _run(self, partner: PartnerCfg, link, master: bool, transport: str) -> SessionResult:
        self.busy.add(partner.call)
        try:
            s = ForwardSession(self.app.cfg.station.bbs_call, partner, link, master=master,
                               transport=transport, service=self.app.service)
            result = await s.run()
        finally:
            self.busy.discard(partner.call)
        self.last[partner.call] = result
        return result

    # --- incoming ------------------------------------------------------------------

    def attach_agw(self, conn, remote: str) -> None:
        """Called by the AGW adapter for a connect from a partner's radio call."""
        partner = self.partner_for_radio(remote)
        if partner is None or partner.call in self.busy:
            log.warning("%s: forward connect refused (%s)", remote,
                        "busy" if partner else "no partner")
            conn.close()
            return
        link = AgwLink(conn, f"ax25:{remote}")
        conn.session = link
        self._spawn(self._run(partner, link, master=False, transport="agw"))

    async def _tcp_in(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        link = TcpLink(reader, writer, f"tcp:{peer}")
        try:
            link.write_lines("Callsign:")
            call = normalize_call((await link.readline(LOGIN_TIMEOUT)) or "")
            link.write_lines("Password:")
            password = ((await link.readline(LOGIN_TIMEOUT)) or "").strip()
        except asyncio.TimeoutError:
            await link.close()
            return
        partner = self.cfg.partner(call)
        open_port = self.cfg.listen_host in LOOPBACK_HOSTS
        ok = (partner is not None and partner.transport == "tcp"
              and (password == partner.password if partner.password else open_port)
              and partner.call not in self.busy)
        if not ok:
            log.warning("TCP forward login refused: %r from %s", call, peer)
            link.write_lines("Login failed.")
            await link.close()
            return
        log.info("TCP forward login %s from %s", partner.call, peer)
        await self._run(partner, link, master=False, transport="tcp")

    # --- outgoing ------------------------------------------------------------------

    async def call(self, call: str) -> SessionResult:
        """Connect to a partner now (sysop command FWD)."""
        partner = self.cfg.partner(call)
        if partner is None:
            raise KeyError(f"{call} is not a forward partner")
        if partner.call in self.busy:
            raise ConnectionError(f"already in a session with {partner.call}")
        if partner.transport == "tcp":
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(partner.host, partner.port), partner.timeout)
            link = TcpLink(reader, writer, f"tcp:{partner.call}")
            if partner.login:
                link.write_lines(*partner.login)
            return await self._run(partner, link, master=True, transport="tcp")
        agw = self.app.agw
        if agw is None:
            raise ConnectionError("AGW adapter not running")
        holder: dict[str, AgwLink] = {}

        def attach(conn) -> None:
            holder["link"] = conn.session = AgwLink(conn, f"ax25:{partner.radio_call}")

        await agw.connect(partner.radio_call, attach, partner.via, timeout=partner.timeout)
        return await self._run(partner, holder["link"], master=True, transport="agw")

    # --- lifecycle -----------------------------------------------------------------

    async def start_server(self) -> None:
        if self.cfg.listen_port:
            self.server = await asyncio.start_server(self._tcp_in, self.cfg.listen_host,
                                                     self.cfg.listen_port)
            self.listen_port = self.server.sockets[0].getsockname()[1]
            log.info("forward port listening on %s:%d", self.cfg.listen_host, self.listen_port)

    async def run(self) -> None:
        """Keeps the module alive; the automatic schedule follows in F4."""
        try:
            await asyncio.Event().wait()
        finally:
            if self.server is not None:
                self.server.close()
            for task in list(self.tasks):
                task.cancel()

    def status_lines(self) -> list[str]:
        queue = self.app.store.fwd_queue_list()
        out = [f"Forward: {self.app.cfg.station.address}, {len(self.cfg.partners)} partner(s), "
               f"{len(queue)} message(s) queued"
               + (f", TCP port {self.cfg.listen_host}:{self.listen_port}" if self.server else "")]
        for p in self.cfg.partners.values():
            n = sum(1 for q in queue if q[0] == p.call)
            last = self.last.get(p.call)
            state = "in session" if p.call in self.busy else (last.summary() if last else "-")
            out.append(f"  {p.call:<7} {p.transport:<3} {p.protocol:<5} queued {n:>3}  {state}")
        return out


async def start(app: App) -> asyncio.Task:
    module = ForwardModule(app)
    app.forward = module
    await module.start_server()
    log.info("forward module on: %s, partners %s", app.cfg.station.address,
             ", ".join(module.cfg.partners) or "none")
    return asyncio.create_task(module.run())
