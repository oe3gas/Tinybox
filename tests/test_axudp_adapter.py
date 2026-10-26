"""AXUDP adapter end to end (PLANUNG.md section 25, step 2).

A complete TinyBox (sessions, store, commands) with an AXUDP port on loopback;
on the other side a station with the same AX.25 (prcore/kissport.py) over its
own AXUDP socket - what the TinyBox client will do in step 3.
"""

from __future__ import annotations

import asyncio
import dataclasses
import unittest

from prcore import axudp
from prcore.ax25 import frame as ax
from prcore.ax25.link import LinkCfg
from prcore.kissport import KissPort
from tinybox import config
from tinybox.adapters import axudp as axudpadapter

from tests.test_tinybox import ROOT, make_app

BOX = "OE3GAS-1"
FAST = LinkCfg(version="2.2", air_baud=10_000_000, txdelay_sec=0.0, t1_min_sec=0.5,
               t1_max_sec=2.0, t2_sec=0.05, srt_init_sec=0.1, paclen=256, maxframe_ext=32)


class Station(KissPort):
    """The other side: our AX.25 over its own AXUDP socket."""

    def __init__(self, call: str) -> None:
        super().__init__(call, "127.0.0.1", 0, FAST, half_duplex=False,
                         transport=lambda on_frame: axudp.AxudpEndpoint(
                             "127.0.0.1", 0, {}, on_frame))
        self.rx = bytearray()
        self.events: list[tuple[str, object]] = []

    def on_link_event(self, link, name, arg) -> None:
        self.events.append((name, arg))
        if name == "data":
            self.rx += arg

    def text(self) -> str:
        return self.rx.decode("utf-8", "replace")

    def dial(self, remote: str = BOX):
        link = self.open_link(remote)
        link.connect(self.now())
        self.service(link)
        return link

    def say(self, link, text: str) -> None:
        link.send(text.encode(), self.now())
        self.service(link)


async def wait(cond, timeout: float = 10.0) -> None:
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while not cond():
        if loop.time() > end:
            raise AssertionError("timed out")
        await asyncio.sleep(0.02)


class AxudpAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def start(self, *calls: str):
        self.stations = {}
        self.tasks = []
        for call in calls:                       # their sockets first: the box needs the ports
            st = Station(call)
            await st.kiss.open()
            self.stations[call] = st
        self.app = make_app()
        peers = {c: axudp.Peer(c, "127.0.0.1", st.kiss.local_port)
                 for c, st in self.stations.items()}
        self.app.cfg.axudp = config.AxudpCfg(enabled=True, listen="127.0.0.1", port=0,
                                             peers=peers, t1_sec=0.5)
        self.ui_before = self.app.service.chat.ui_send
        self.adapter = axudpadapter.AxudpAdapter(self.app)
        self.app.axudp = self.adapter
        self.tasks.append(asyncio.create_task(self.adapter.run()))
        await asyncio.wait_for(self.adapter.connected.wait(), 5)
        box = axudp.Peer(BOX, "127.0.0.1", self.adapter.endpoint.local_port)
        for st in self.stations.values():
            st.kiss.table = axudp.PeerTable({BOX: box})
            self.tasks.append(asyncio.create_task(st._timer_loop()))

    async def asyncTearDown(self):
        for t in self.tasks:
            t.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        for st in self.stations.values():
            st.kiss.close()
        self.app.store.close()

    async def test_session_over_axudp(self):
        await self.start("OE1ABC")
        st = self.stations["OE1ABC"]
        link = st.dial()
        await wait(lambda: "hello OE1ABC" in st.text())
        self.assertEqual(link.peer_version, "2.2")
        self.assertEqual(link.modulo, 128)
        self.assertEqual(self.app.registry and next(iter(self.app.registry)).origin, "axudp")
        st.say(link, "S OE3GAS\rHello\rLine one\r/EX\rB\r")
        await wait(lambda: ("disconnected", "remote") in st.events)
        msg = self.app.store.get(1)
        self.assertEqual((msg.from_call, msg.origin, msg.body), ("OE1ABC", "axudp", "Line one"))
        self.assertIn("73, bye", st.text())
        await wait(lambda: not self.adapter.links and not self.adapter.conns)
        self.assertEqual(len(self.app.registry), 0)

    async def test_long_output_in_large_frames(self):
        await self.start("OE1ABC")
        st = self.stations["OE1ABC"]
        link = st.dial()
        await wait(lambda: "hello OE1ABC" in st.text())
        body = "\r".join(f"line {i:03d} " + "x" * 60 for i in range(60))
        st.say(link, f"S OE3GAS\rBig\r{body}\r/EX\r")
        await wait(lambda: "saved" in st.text())
        st.say(link, "R 1\r")
        await wait(lambda: "line 059" in st.text(), timeout=15)
        self.assertGreater(self.adapter.endpoint.tx_frames, 15)

    async def test_ui_frames_stay_with_the_radio(self):
        await self.start("OE1ABC")
        self.assertIs(self.app.service.chat.ui_send, self.ui_before)

    async def test_sysop_only_from_loopback_peer(self):
        await self.start("OE3GAS-9")                # sysop_call OE3GAS, any SSID
        st = self.stations["OE3GAS-9"]
        st.dial()
        await wait(lambda: "hello OE3GAS-9" in st.text())
        self.assertTrue(next(iter(self.app.registry)).sysop)
        self.adapter.endpoint.table = axudp.PeerTable(
            {"OE3GAS-9": axudp.Peer("OE3GAS-9", "44.143.0.1", 93)})
        self.assertFalse(self.adapter._sysop_allowed("OE3GAS-9"))

    async def test_stranger_and_spoofed_call_are_ignored(self):
        await self.start("OE1ABC")
        sp = Station("OE5XYZ")                      # not a peer, same IP
        await sp.kiss.open()
        try:
            sp.kiss.table = axudp.PeerTable(
                {BOX: axudp.Peer(BOX, "127.0.0.1", self.adapter.endpoint.local_port)})
            sp.dial()
            await wait(lambda: self.adapter.endpoint.dropped["stranger"] >= 1)
            await asyncio.sleep(0.3)
            self.assertEqual(self.adapter.links, {})
            self.assertEqual(sp.rx, b"")             # not even a DM came back
        finally:
            sp.kiss.close()

    async def test_refused_while_connected_over_the_radio(self):
        await self.start("OE1ABC")

        class Radio:
            origin = "radio"
            conns = {"OE1ABC": object()}

        self.app.agw = Radio()
        st = self.stations["OE1ABC"]
        st.dial()
        await wait(lambda: "busy" in st.text().lower())
        self.assertEqual(len(self.app.registry), 0)


    async def test_status_line(self):
        from tinybox.adapters.sysop import MonitorFilter, SysopConsole
        await self.start("OE1ABC")
        self.app.stop_event = asyncio.Event()
        out: list[str] = []
        console = SysopConsole(self.app, MonitorFilter(True), out.append)
        console.start()
        out.clear()
        console.handle_line("STATUS")
        text = "".join(out)
        self.assertIn("AXUDP:     127.0.0.1:0 up, peers OE1ABC, links -", text)


class ConfigTests(unittest.TestCase):
    def load(self, text: str) -> config.Config:
        import tempfile, pathlib
        import re
        base = (ROOT / "tinybox.conf.example").read_text(encoding="utf-8")
        base = re.sub(r"(?ms)^\[axudp\].*?(?=^\[)", "", base)    # the example's own
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "tinybox.conf"
            p.write_text(base + "\n" + text, encoding="utf-8")
            return config.load(p)

    def test_default_off(self):
        cfg = config.load(ROOT / "tinybox.conf.example")
        self.assertFalse(cfg.axudp.enabled)

    def test_peers(self):
        cfg = self.load("[axudp]\nenabled = yes\npeers = OE3GAS 127.0.0.1:10094, "
                        "OE3TEC-2 = 127.0.0.1:10095   # second client\n")
        self.assertEqual(sorted(cfg.axudp.peers), ["OE3GAS", "OE3TEC-2"])
        self.assertEqual(cfg.axudp.peers["OE3TEC-2"].port, 10095)

    def test_multiline_peers(self):
        cfg = self.load("[axudp]\nenabled = yes\npeers = OE3GAS 127.0.0.1:10094\n"
                        "        OE3TEC 127.0.0.1:10095\n")
        self.assertEqual(len(cfg.axudp.peers), 2)

    def test_loopback_only_for_now(self):
        for text in ("listen = 0.0.0.0\npeers = OE3GAS 127.0.0.1",
                     "peers = OE3GAS 44.143.0.1"):
            with self.subTest(text=text), \
                    self.assertRaisesRegex(config.ConfigError, r"\[axudp\] (listen|peers)"):
                self.load("[axudp]\nenabled = yes\n" + text + "\n")

    def test_enabled_needs_peers(self):
        with self.assertRaisesRegex(config.ConfigError, "peer"):
            self.load("[axudp]\nenabled = yes\n")


if __name__ == "__main__":
    unittest.main()
