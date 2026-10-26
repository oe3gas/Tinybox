"""PLANUNG 25, step 3: the client reaches its home TinyBox over AXUDP and every
other station over the radio - one transceiver, TinyBox and client on one PC.

A fake kisshub is "the air" (as in test_tbclient_kiss); the TinyBox runs its
radio over it plus its AXUDP port on loopback.
"""

from __future__ import annotations

import asyncio
import dataclasses
import tempfile
import unittest
from pathlib import Path

from prcore import axudp, kiss
from prcore.ax25 import frame as ax
from tbclient import config as ccfg
from tbclient import core as core_mod
from tinybox import config
from tinybox.adapters import axudp as axudpadapter
from tinybox.adapters import kiss as kissadapter
from tests.test_chat import chat_app
from tests.test_kiss_adapter import FAST
from tests.test_tbclient import until
from tests.test_tbclient_kiss import FakeHub, kiss_client
from tests.test_tinybox import login, type_lines

ROOT = Path(__file__).resolve().parent.parent
BOX = "OE3GAS-1"


class AirLog(FakeHub):
    """The fake kisshub, remembering who sent what over the air."""

    def __init__(self) -> None:
        super().__init__()
        self.pairs: list[tuple[str, str]] = []

    async def _conn(self, r, w) -> None:
        dec = kiss.Decoder()
        self.clients.append(w)
        try:
            while chunk := await r.read(4096):
                for port, cmd, data in dec.feed(chunk):
                    if cmd != kiss.CMD_DATA:
                        continue
                    dest, src, *_ = ax.peek(data)
                    self.pairs.append((src, dest))
                    for other in self.clients:
                        if other is not w and not other.is_closing():
                            other.write(kiss.encode(data, port))
        except (ConnectionError, OSError):
            pass
        finally:
            self.clients.remove(w)


class AxudpClientTests(unittest.TestCase):
    def setUp(self):
        self._old = core_mod.HANDSHAKE_FALLBACK_SEC
        core_mod.HANDSHAKE_FALLBACK_SEC = 0.3

    def tearDown(self):
        core_mod.HANDSHAKE_FALLBACK_SEC = self._old

    def test_home_over_axudp_others_over_radio(self):
        async def scenario():
            hub = AirLog()
            port = await hub.start()
            app = chat_app()
            app.cfg.radio = config.RadioCfg(interface="kiss")
            app.cfg.kiss = config.KissCfg(port=port, reconnect_sec=1, air_baud=1_000_000,
                                          txdelay_ms=0, status_port=0)
            app.cfg.ax25 = dataclasses.replace(app.cfg.ax25, paclen=128, n2=5, **FAST)
            app.cfg.axudp = config.AxudpCfg(enabled=True, port=0, t1_sec=0.5, peers={})
            radio = kissadapter.KissAdapter(app)
            app.agw = radio
            box = axudpadapter.AxudpAdapter(app)
            app.axudp = box
            tasks = [asyncio.create_task(radio.run()), asyncio.create_task(box.run())]
            await asyncio.wait_for(radio.connected.wait(), 5)
            await asyncio.wait_for(box.connected.wait(), 5)
            term, tt = login(app, "OE3XYZ")             # somebody in the chat on the box
            type_lines(term, "C TREFF")
            with tempfile.TemporaryDirectory() as ta, tempfile.TemporaryDirectory() as tb:
                me = kiss_client(ta, port, "OE3GAS", axudp_host="127.0.0.1",
                                 axudp_port=box.endpoint.local_port, axudp_listen=0)
                other = kiss_client(tb, port, "OE3TEC")
                tasks += [asyncio.create_task(me.run()), asyncio.create_task(other.run())]
                await asyncio.wait_for(me.port.agw_up.wait(), 5)
                await asyncio.wait_for(other.port.agw_up.wait(), 5)
                await asyncio.wait_for(me.udp.agw_up.wait(), 5)
                box.endpoint.table = axudp.PeerTable(
                    {"OE3GAS": axudp.Peer("OE3GAS", "127.0.0.1", me.udp.kiss.local_port)})
                self.assertTrue(me.snapshot()["axudp"]["up"])
                # the home TinyBox: over AXUDP, full client mode, no UI frames
                self.assertTrue(await me.connect(BOX, ch=1))
                await until(lambda: me.boards, 10)
                ch1 = me.channels[1]
                self.assertEqual((ch1.link.kind, ch1.mode), ("axudp", "tinybox"))
                self.assertTrue({"IMG", "Z", "SYNC"} <= me.caps)
                self.assertNotIn("UI", me.caps)
                s = next(x for x in app.registry if x.call == "OE3GAS")
                self.assertEqual((s.origin, s.sysop), ("axudp", True))
                self.assertTrue(me.join(1))
                await until(lambda: me.board is not None)
                me.say("ueber AXUDP")
                await until(lambda: "OE3GAS: ueber AXUDP" in tt.buf)
                type_lines(term, "Antwort")
                await until(lambda: any(m.get("text") == "Antwort" for m in me.messages))
                # another station: over the radio, at the same time
                self.assertTrue(await me.connect("OE3TEC", ch=2))
                await until(lambda: me.channels[2].state == "online", 5)
                self.assertEqual(me.channels[2].link.kind, "kiss")
                await until(lambda: any(c.incoming and c.state == "online"
                                        for c in other.channels.values()), 5)
                self.assertTrue(me.send_raw("Hallo Tobias", ch=2))
                inc = next(c for c in other.channels.values() if c.incoming)
                await until(lambda: any(x == "Hallo Tobias" for _, k, x in inc.term if k == "rx"))
                # nothing between me and the box went over the air, the radio link did
                self.assertNotIn(("OE3GAS", BOX), hub.pairs)
                self.assertNotIn((BOX, "OE3GAS"), hub.pairs)
                self.assertIn(("OE3GAS", "OE3TEC"), hub.pairs)
                chips = {c["n"]: c["link"] for c in me.snapshot()["channels"]}
                self.assertEqual(chips, {1: "axudp", 2: "kiss"})
                # the home box over a digipeater still goes over the radio
                me.disconnect(1)
                await until(lambda: ch1.state == "offline", 10)
                self.assertEqual(me.logbook.rows()[0]["via"], "axudp")
                me.relink(ch1, BOX, ["OE3XWR"])
                self.assertEqual(ch1.link.kind, "kiss")
                me.relink(ch1, BOX, [])
                self.assertEqual(ch1.link.kind, "axudp")
                for t in tasks:
                    t.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            hub.close()
            app.store.close()
        asyncio.run(scenario())


class ConfigTests(unittest.TestCase):
    def load(self, extra: str, interface: str = "kiss") -> ccfg.Config:
        base = (ROOT / "tbclient.conf.example").read_text(encoding="utf-8")
        base = base.replace("interface    = agw", f"interface    = {interface}", 1)
        base = base.replace("[tinybox]\n", "[tinybox]\n" + extra + "\n", 1)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "tbclient.conf"
            p.write_text(base, encoding="utf-8")
            return ccfg.load(p)

    def test_default_off(self):
        cfg = ccfg.load(ROOT / "tbclient.conf.example")
        self.assertEqual(cfg.axudp_host, "")

    def test_on(self):
        cfg = self.load("axudp = 127.0.0.1:10093\naxudp_port = 10095")
        self.assertEqual((cfg.axudp_host, cfg.axudp_port, cfg.axudp_listen),
                         ("127.0.0.1", 10093, 10095))
        self.assertTrue(any("AXUDP" in line for line in ccfg.radio_lines(cfg)))

    def test_errors(self):
        for extra, iface in (("axudp = 44.143.0.1:10093", "kiss"),
                             ("axudp = box.example", "kiss"),
                             ("axudp = 127.0.0.1\naxudp_port = 0", "kiss"),
                             ("axudp = 127.0.0.1", "telnet")):
            with self.subTest(extra=extra, iface=iface), \
                    self.assertRaisesRegex(ccfg.ConfigError, "axudp"):
                self.load(extra, iface)


if __name__ == "__main__":
    unittest.main()
