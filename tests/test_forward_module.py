"""F2: forward module - config, routing, queue, and real handshakes against fwdsim
over TCP and over a simulated Direwolf (AGW), in both directions."""

from __future__ import annotations

import asyncio
import socket
import tempfile
import unittest
from pathlib import Path

from fwdsim.agw import AgwClient
from fwdsim.config import Config as SimConfig
from fwdsim.harness import tinybox_login
from fwdsim.link import TcpLink as SimTcpLink, tcp_connect
from fwdsim.net import SimNet
from fwdsim.protocol import LATER
from fwdsim.session import Faults, ForwardSession as SimSession
from fwdsim.store import Store as SimStore

from tinybox import config
from tinybox.adapters import agw as tagw
from tinybox.adapters.forward import ForwardModule
from tinybox.app import App
from tinybox.config import PartnerCfg
from tinybox.fwd.router import Router

from tests.test_fwdsim import FakeDirewolf
from tests.test_tinybox import login, make_app, type_lines

HADDR = "OE3XTC.#NOE.AUT.EU"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def fwd_app(*partners: PartnerCfg) -> App:
    app = make_app()
    st = app.cfg.station
    st.mailbox_call, st.sysop_call, st.haddress, st.qth = "OE3XTC-1", "OE3XTC", HADDR, "Hollabrunn"
    app.cfg.forward.enabled = True
    app.cfg.forward.partners = {p.call: p for p in partners}
    return app


def gas(**kw) -> PartnerCfg:
    base = dict(call="OE3GAS", transport="tcp", host="127.0.0.1", port=1,
                haddress="OE3GAS.#OOE.AUT.EU", routes=["WW"], areas=["WW", "EU", "AUT"],
                password="geheim", timeout=10)
    base.update(kw)
    return PartnerCfg(**base)


def sim_net() -> SimNet:
    return SimNet(SimConfig(), SimStore())       # OE3GAS + DL0XTC, TinyBox = OE3XTC


class ConfigTests(unittest.TestCase):
    BASE = ("[station]\nmailbox_call = OE3XTC-1\nsysop_call = OE3XTC\n"
            "haddress = OE3XTC.#NOE.AUT.EU\n[forward]\nenabled = yes\n")

    def _load(self, extra: str):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.conf"
            p.write_text(self.BASE + extra, encoding="utf-8")
            return config.load(p)

    def test_partners(self):
        cfg = self._load("listen_port = 6312\n"
                         "[partner.OE3GAS]\ntransport = agw\nax25_call = oe3gas-5\n"
                         "via = OE3XNR\nhaddress = oe3gas.#ooe.aut\nroutes = WW\nareas = WW EU\n"
                         "[partner.OE3XAB]\ntransport = tcp\nhost = 44.1.2.3\nport = 8011\n"
                         "login = OE3XTC | pw\nprotocol = ascii\n")
        g, x = cfg.forward.partners["OE3GAS"], cfg.forward.partners["OE3XAB"]
        self.assertEqual((g.radio_call, g.via, g.haddress), ("OE3GAS-5", ["OE3XNR"],
                                                             "OE3GAS.#OOE.AUT.EU"))
        self.assertEqual((x.login, x.protocol, x.port), (["OE3XTC", "pw"], "ascii", 8011))
        self.assertIs(cfg.forward.partner_by_radio_call("OE3GAS-5"), g)
        self.assertEqual(cfg.forward.listen_port, 6312)

    def test_bad_partners(self):
        for extra in ("[partner.OE3GAS-1]\n",                         # SSID in the name
                      "[partner.OE3GAS]\ntransport = ftp\n",
                      "[partner.OE3GAS]\ntransport = tcp\n",          # no host
                      "[partner.OE3GAS]\nprotocol = b2\n",
                      "listen_host = 0.0.0.0\nlisten_port = 6312\n"   # open port ...
                      "[partner.OE3GAS]\ntransport = tcp\nhost = x\nport = 1\n"):  # ... no pw
            with self.assertRaises(config.ConfigError, msg=extra):
                self._load(extra)


class RouterTests(unittest.TestCase):
    def setUp(self):
        self.app = fwd_app(gas(), gas(call="DL0XTC", routes=["DEU.EU"], areas=["DEU", "EURO"]))
        self.router = Router(self.app.cfg.forward)

    def _msg(self, type, at, rlines=""):
        m = self.app.store.get(self.app.service.create(
            from_call="OE1ABC", to_call="ALL" if type == "B" else "DL1ABC", type=type,
            subject="x", body="x", origin="telnet", at_addr=at))
        m.rlines = rlines or m.rlines
        return m

    def test_personal(self):
        self.assertEqual(self.router.targets(self._msg("P", "DL1XYZ.#BAY.DEU.EU")), ["DL0XTC"])
        self.assertEqual(self.router.targets(self._msg("P", "DL0XTC")), ["DL0XTC"])
        self.assertEqual(self.router.targets(self._msg("P", "W1AW.#WMA.MA.USA.NOAM")),
                         ["OE3GAS"])                                   # default route WW

    def test_flood_and_split_horizon(self):
        self.assertEqual(sorted(self.router.targets(self._msg("B", "EU"))), ["DL0XTC", "OE3GAS"])
        self.assertEqual(self.router.targets(self._msg("B", "AUT")), ["OE3GAS"])
        came = ("R:261006/1200Z @:OE3XTC.#NOE.AUT.EU #:1 $:1_X\n"
                "R:261006/1100Z @:OE3GAS.#OOE.AUT.EU #:5 $:1_X")
        self.assertEqual(self.router.targets(self._msg("B", "EU", came)), ["DL0XTC"])


class QueueTests(unittest.TestCase):
    def test_events_fill_and_clear_queue(self):
        app = fwd_app(gas(routes=["AUT.EU"]))
        ForwardModule(app)
        s, t = login(app, "OE1ABC")
        type_lines(s, "SB ALL @ WW", "net", "x", "/EX",
                   "SP OE1XYZ @ OE1XAB.#WIE.AUT", "p", "x", "/EX",
                   "SP W1AW @ W1AW.MA.USA.NOAM", "far", "x", "/EX",
                   "SP OE3XTC", "local", "x", "/EX")
        q = app.store.fwd_queue_list()
        self.assertEqual([(p, i) for p, i, _, _ in q], [("OE3GAS", 1), ("OE3GAS", 2)])
        far = app.store.get(3)
        self.assertEqual((far.fwd, far.note), ("H", "no route to W1AW.MA.USA.NOAM"))
        self.assertEqual(app.store.get(4).fwd, "")
        app.service.delete(1, "OE3XTC", sysop=True)
        self.assertEqual([i for _, i, _, _ in app.store.fwd_queue_list()], [2])


class TcpTests(unittest.IsolatedAsyncioTestCase):
    async def test_partner_calls_tinybox(self):
        app = fwd_app(gas())
        module = ForwardModule(app)
        module.cfg.listen_port = free_port()
        await module.start_server()
        net = sim_net()
        m = net.hop.create("P", "OE1ABC", HADDR, "for TinyBox", "text")
        try:
            link = await tcp_connect("127.0.0.1", module.listen_port, "OE3GAS>tinybox")
            await tinybox_login(link, "OE3GAS", "geheim", 5)
            r = await SimSession(net.hop, link, "OE3XTC", master=True, timeout=5).run()
            await asyncio.sleep(0.1)
            self.assertTrue(r.ok, r.error)
            self.assertEqual(r.mode, "fbb")
            self.assertEqual(r.sent, {m.bid: LATER})              # F2: deferred, not lost
            last = module.last["OE3GAS"]
            self.assertTrue(last.ok, last.error)
            self.assertEqual(last.deferred, [m.bid])
            self.assertIn("TINYBOX", r.peer_sid)
        finally:
            module.server.close()

    async def test_wrong_password(self):
        app = fwd_app(gas())
        module = ForwardModule(app)
        module.cfg.listen_port = free_port()
        await module.start_server()
        try:
            link = await tcp_connect("127.0.0.1", module.listen_port, "x")
            await tinybox_login(link, "OE3GAS", "falsch", 5)
            lines = []
            while (line := await link.readline(5)) is not None:
                lines.append(line)
            self.assertIn("Login failed.", lines)
            self.assertNotIn("OE3GAS", module.last)
        finally:
            module.server.close()

    async def _sim_server(self, faults: Faults | None = None):
        net = sim_net()
        done: asyncio.Queue = asyncio.Queue()

        async def handle(reader, writer):
            s = SimSession(net.hop, SimTcpLink(reader, writer, "hop<tcp"), "OE3XTC",
                           master=False, faults=faults, timeout=5)
            await done.put(await s.run())

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        return net, server, done

    async def test_tinybox_calls_partner(self):
        net, server, done = await self._sim_server()
        net.hop.create("P", "OE1ABC", HADDR, "waiting at OE3GAS", "text")
        app = fwd_app(gas(port=server.sockets[0].getsockname()[1]))
        module = ForwardModule(app)
        try:
            r = await module.call("OE3GAS")
            sim = await asyncio.wait_for(done.get(), 5)
            self.assertTrue(r.ok, r.error)
            self.assertTrue(sim.ok, sim.error)
            self.assertEqual(r.mode, "fbb")
            self.assertEqual(len(r.deferred), 1)        # offered in reverse, deferred
        finally:
            server.close()

    async def test_ascii_partner(self):
        net, server, done = await self._sim_server(Faults(sid="[FWDSIM-0.1-H$]"))
        app = fwd_app(gas(port=server.sockets[0].getsockname()[1]))
        r = await ForwardModule(app).call("OE3GAS")
        sim = await asyncio.wait_for(done.get(), 5)
        server.close()
        self.assertTrue(r.ok, r.error)
        self.assertEqual((r.mode, sim.mode), ("ascii", "rli"))


class AgwTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.dw = FakeDirewolf()
        self.server = await asyncio.start_server(self.dw.handle, "127.0.0.1", 0)
        port = self.server.sockets[0].getsockname()[1]
        self.app = fwd_app(gas(transport="agw", ax25_call="OE3GAS", port=0, host=""))
        self.app.cfg.direwolf.agw_port = port
        self.module = ForwardModule(self.app)
        self.app.forward = self.module
        self.app.agw = tagw.AgwAdapter(self.app)
        self.agw_task = asyncio.create_task(self.app.agw.run())
        await asyncio.wait_for(self.app.agw.connected.wait(), 5)
        self.simcfg = SimConfig()
        self.simcfg.agw.port = port
        self.net = sim_net()
        self.done: asyncio.Queue = asyncio.Queue()

        async def incoming(link):
            s = SimSession(self.net.hop, link, "OE3XTC", master=False, timeout=5)
            await self.done.put(await s.run())

        self.hop = AgwClient(self.simcfg.agw, "OE3GAS", incoming)
        await self.hop.start()

    async def asyncTearDown(self):
        await self.hop.stop()
        self.agw_task.cancel()
        self.server.close()

    async def test_partner_connects_over_radio(self):
        m = self.net.hop.create("B", "ALL", "WW", "bulletin", "text")
        link = await self.hop.connect("OE3XTC-1", timeout=5)
        r = await SimSession(self.net.hop, link, "OE3XTC", master=True, timeout=5).run()
        await asyncio.sleep(0.3)
        self.assertTrue(r.ok, r.error)
        self.assertEqual(r.sent, {m.bid: LATER})
        self.assertEqual(len(self.app.registry), 0)          # no user session was made
        self.assertTrue(self.module.last["OE3GAS"].ok)

    async def test_tinybox_connects_over_radio(self):
        r = await self.module.call("OE3GAS")
        sim = await asyncio.wait_for(self.done.get(), 5)
        self.assertTrue(r.ok, r.error)
        self.assertTrue(sim.ok, sim.error)
        self.assertEqual((r.transport, r.mode), ("agw", "fbb"))


if __name__ == "__main__":
    unittest.main()
