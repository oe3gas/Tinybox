"""KISS adapter end to end (KISS step K4, docs/kiss-mode-konzept.md).

A fake KISS-TCP server plays "the air": behind it stations run the same AX.25
state machine (v2.0 or v2.2), with optional frame loss. TinyBox runs complete
(sessions, store, commands) over the KissAdapter. Timers are scaled down so a
test takes about a second instead of minutes.
"""

from __future__ import annotations

import asyncio
import dataclasses
import random
import unittest

from tinybox import config
from tinybox.adapters import kiss as kissadapter
from tinybox.ax25 import frame as ax
from tinybox.ax25 import kissio
from tinybox.ax25.frame import Frame
from tinybox.ax25.link import Ax25Link, LinkCfg

from tests.test_tinybox import ROOT, make_app

MYCALL = "OE3GAS-1"
FAST = dict(t1_min_sec=0.3, t1_max_sec=2.0, t2_sec=0.05, t3_sec=30.0, srt_init_sec=0.1)


def station_cfg(version: str = "2.2", **kw) -> LinkCfg:
    return LinkCfg(version=version, air_baud=1_000_000, txdelay_sec=0.0, **(FAST | kw))


class Air:
    """KISS-TCP server + stations on the other side of the radio."""

    def __init__(self, loss: float = 0.0, seed: int = 1) -> None:
        self.stations: dict[str, Ax25Link] = {}
        self.rx: dict[str, bytearray] = {}
        self.events: dict[str, list] = {}
        self.heard: list[Frame] = []             # everything TinyBox transmitted
        self.writer: asyncio.StreamWriter | None = None
        self.client = asyncio.Event()
        self.loss = loss
        self.rnd = random.Random(seed)
        self._timer: asyncio.Task | None = None

    @staticmethod
    def now() -> float:
        return asyncio.get_running_loop().time()

    async def handle(self, reader, writer) -> None:
        self.writer = writer
        self.client.set()
        dec = kissio.Decoder()
        try:
            while chunk := await reader.read(4096):
                for _, cmd, data in dec.feed(chunk):
                    if cmd == kissio.CMD_DATA:
                        self._from_tinybox(data)
        except ConnectionError:
            pass

    def station(self, call: str, cfg: LinkCfg | None = None) -> Ax25Link:
        link = Ax25Link(call, MYCALL, cfg=cfg or station_cfg(), now=self.now())
        self.stations[call] = link
        self.rx[call] = bytearray()
        self.events[call] = []
        if self._timer is None:
            self._timer = asyncio.create_task(self._ticks())
        return link

    def _from_tinybox(self, data: bytes) -> None:
        dest, *_ = ax.peek(data)
        st = self.stations.get(dest)
        f = Frame.decode(data, st.modulo if st else 8)
        self.heard.append(f)
        if st is None or self.rnd.random() < self.loss:
            return
        st.receive(f, self.now())
        self.pump(st)

    def pump(self, st: Ax25Link) -> None:
        for f in st.pop_output():
            if self.rnd.random() >= self.loss:
                self.inject(f.encode())
        for ev in st.pop_events():
            self.events[st.mycall].append(ev)
            if ev[0] == "data":
                self.rx[st.mycall] += ev[1]

    def inject(self, raw: bytes) -> None:
        if self.writer is not None and not self.writer.is_closing():
            self.writer.write(kissio.encode(raw))

    async def _ticks(self) -> None:
        while True:
            await asyncio.sleep(0.02)
            now = self.now()
            for st in self.stations.values():
                d = st.next_deadline()
                if d is not None and d <= now:
                    st.tick(now)
                    self.pump(st)

    def text(self, call: str) -> str:
        return self.rx[call].decode("utf-8", "replace")

    async def wait(self, cond, timeout: float = 10.0) -> None:
        end = self.now() + timeout
        while not cond():
            if self.now() > end:
                raise AssertionError("timed out")
            await asyncio.sleep(0.02)

    def close(self) -> None:
        if self._timer:
            self._timer.cancel()
        if self.writer:
            self.writer.close()


def kiss_app(port: int, version: str = "2.2", **mailbox):
    app = make_app(**mailbox)
    app.cfg.radio = config.RadioCfg(interface="kiss")
    app.cfg.kiss = config.KissCfg(port=port, reconnect_sec=1, air_baud=1_000_000, txdelay_ms=0)
    app.cfg.ax25 = dataclasses.replace(app.cfg.ax25, version=version, paclen=128, n2=5, **FAST)
    return app


class KissAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def start(self, loss: float = 0.0, version: str = "2.2", **mailbox):
        self.air = Air(loss=loss)
        self.server = await asyncio.start_server(self.air.handle, "127.0.0.1", 0)
        port = self.server.sockets[0].getsockname()[1]
        self.app = kiss_app(port, version, **mailbox)
        self.adapter = kissadapter.KissAdapter(self.app)
        self.app.agw = self.adapter
        self.task = asyncio.create_task(self.adapter.run())
        await asyncio.wait_for(self.adapter.connected.wait(), 5)
        await asyncio.wait_for(self.air.client.wait(), 5)

    async def asyncTearDown(self):
        self.task.cancel()
        try:
            await self.task
        except asyncio.CancelledError:
            pass
        self.air.close()
        self.server.close()
        await self.server.wait_closed()

    async def session(self, call: str, cfg: LinkCfg | None = None) -> Ax25Link:
        st = self.air.station(call, cfg)
        st.connect(self.air.now())
        self.air.pump(st)
        await self.air.wait(lambda: "hello" in self.air.text(call))
        return st

    async def run_mail_session(self, call: str, cfg: LinkCfg | None = None) -> str:
        st = await self.session(call, cfg)
        st.send(b"S OE3GAS\rHello\rLine one\r/EX\rL\rB\r", self.air.now())
        self.air.pump(st)
        await self.air.wait(lambda: any(e[0] == "disconnected" for e in self.air.events[call]),
                            timeout=20)
        await self.air.wait(lambda: not self.adapter.links)
        return self.air.text(call)

    # --- sessions -------------------------------------------------------------------

    async def test_session_v22_station(self):
        await self.start()
        out = await self.run_mail_session("OE1ABC-7")
        self.assertIn("hello OE1ABC-7", out)
        self.assertIn("Msg 1 saved.", out)
        self.assertIn("73, bye", out)
        msg = self.app.store.get(1)
        self.assertEqual((msg.from_call, msg.origin, msg.body), ("OE1ABC-7", "radio", "Line one"))
        self.assertEqual(self.air.events["OE1ABC-7"][-1], ("disconnected", "remote"))
        self.assertEqual((len(self.app.registry), self.adapter.conns, self.adapter.links),
                         (0, {}, {}))
        kinds = [f.kind for f in self.air.heard]
        self.assertEqual(kinds[0], "UA")
        self.assertIn("XID", kinds)                          # our answer to the station's XID
        st = self.air.stations["OE1ABC-7"]
        self.assertEqual(st.peer_version, "2.2")
        for f in self.air.heard:
            if f.is_i:
                self.assertLessEqual(len(f.info), 128)
                self.assertEqual(f.modulo, 128)

    async def test_session_v20_station(self):
        await self.start()
        out = await self.run_mail_session("OE1ABC", station_cfg("2.0"))
        self.assertIn("Msg 1 saved.", out)
        self.assertIn("73, bye", out)
        self.assertEqual(self.air.heard[0].kind, "UA")
        self.assertTrue(all(f.modulo == 8 for f in self.air.heard if f.is_i))

    async def test_session_with_lossy_channel(self):
        await self.start(loss=0.2)
        out = await self.run_mail_session("OE5XYZ")
        self.assertIn("Msg 1 saved.", out)
        self.assertIn("73, bye", out)

    async def test_tinybox_version_20_refuses_sabme(self):
        await self.start(version="2.0")
        out = await self.run_mail_session("OE1ABC")        # station: SABME, DM, SABM
        self.assertIn("73, bye", out)
        self.assertEqual(self.air.heard[0].kind, "DM")

    async def test_busy(self):
        await self.start(max_users=1)
        await self.session("OE1ABC")
        st = self.air.station("OE5XYZ")
        st.connect(self.air.now())
        self.air.pump(st)
        await self.air.wait(lambda: any(e[0] == "disconnected"
                                        for e in self.air.events["OE5XYZ"]))
        self.assertIn("busy", self.air.text("OE5XYZ").lower())

    # --- router -------------------------------------------------------------------------

    async def test_stranger_gets_dm(self):
        await self.start()
        self.air.inject(ax.i_frame(MYCALL, "OE9XX", 0, 0, b"hi", poll=True).encode())
        await self.air.wait(lambda: self.air.heard)
        self.assertEqual((self.air.heard[0].kind, self.air.heard[0].dest), ("DM", "OE9XX"))
        self.assertEqual(self.adapter.links, {})

    async def test_frames_for_others_and_unrepeated_digi_path_ignored(self):
        await self.start()
        self.air.inject(ax.u_frame("SABM", "OE1XYZ", "OE9XX", pf=True).encode())
        self.air.inject(ax.u_frame("SABM", MYCALL, "OE9XX", pf=True, path=["OE3XWR"]).encode())
        await asyncio.sleep(0.3)
        self.assertEqual((self.air.heard, self.adapter.links), ([], {}))

    async def test_connect_via_repeated_digi_answers_backwards(self):
        await self.start()
        sabm = ax.u_frame("SABM", MYCALL, "OE9XX", pf=True, path=["OE3XWR", "OE1XUU"])
        sabm.repeated = [True, True]
        self.air.inject(sabm.encode())
        await self.air.wait(lambda: self.air.heard)
        self.assertEqual((self.air.heard[0].kind, self.air.heard[0].path),
                         ("UA", ["OE1XUU", "OE3XWR"]))

    async def test_ui_frame_for_chat(self):
        await self.start()
        self.adapter.send_ui("TBCHAT-1", "+1 OE1ABC")
        await self.air.wait(lambda: self.air.heard)
        f = self.air.heard[0]
        self.assertEqual((f.kind, f.dest, f.src, f.info), ("UI", "TBCHAT-1", MYCALL,
                                                            b"+1 OE1ABC"))

    # --- outgoing (forward module) ------------------------------------------------------

    async def test_outgoing_connect_and_v20_memory(self):
        await self.start()
        self.air.station("OE5BBS", station_cfg("2.0"))
        got = bytearray()

        class Sink:
            closed = False

            def feed_bytes(self, data):
                got.extend(data)

            def end(self):
                self.closed = True

        def attach(conn):
            conn.session = Sink()

        conn = await asyncio.wait_for(self.adapter.connect("OE5BBS", attach, timeout=10), 15)
        self.assertIn("OE5BBS", self.adapter.v20_calls)       # SABME was refused
        conn.write_bytes(b"[TinyBox-1.0-$]\r")
        await self.air.wait(lambda: b"TinyBox" in self.air.rx["OE5BBS"])
        st = self.air.stations["OE5BBS"]
        st.send(b"OK\r", self.air.now())
        self.air.pump(st)
        await self.air.wait(lambda: got == b"OK\r")
        conn.close()
        await self.air.wait(lambda: not self.adapter.links)
        kinds = [f.kind for f in self.air.heard if f.kind in ("SABM", "SABME")]
        self.assertEqual(kinds, ["SABME", "SABM"])
        # second time: straight SABM
        self.air.heard.clear()
        conn = await asyncio.wait_for(self.adapter.connect("OE5BBS", attach, timeout=10), 15)
        self.assertEqual(self.air.heard[0].kind, "SABM")
        conn.close()
        await self.air.wait(lambda: not self.adapter.links)

    async def test_outgoing_connect_nobody_there(self):
        await self.start()
        with self.assertRaises((ConnectionError, asyncio.TimeoutError)):
            await self.adapter.connect("OE9NIX", lambda c: None, timeout=20)
        self.assertEqual(self.adapter.links, {})

    # --- link quality and status ------------------------------------------------------------

    async def test_link_quality_from_own_link(self):
        await self.start()
        await self.session("OE1ABC")
        self.adapter.ask_quality("OE1ABC")
        q = self.adapter.conns["OE1ABC"].quality
        self.assertIsNotNone(q.last)
        self.assertGreater(q.last["i_new"], 0)
        self.assertTrue(self.adapter.q_supported)
        self.assertIn("OE1ABC", self.app.service.links)

    async def test_kiss_restart_keeps_running(self):
        await self.start()
        self.air.client.clear()
        self.air.writer.close()
        await self.air.wait(lambda: not self.adapter.connected.is_set(), 5)
        await asyncio.wait_for(self.air.client.wait(), 5)
        await asyncio.wait_for(self.adapter.connected.wait(), 5)
        out = await self.run_mail_session("OE1ABC")
        self.assertIn("73, bye", out)
        self.assertEqual(self.adapter.describe(), f"KISS 127.0.0.1:{self.app.cfg.kiss.port}")


class KissConfigTests(unittest.TestCase):
    def load(self, extra: str):
        import tempfile
        from pathlib import Path
        text = (ROOT / "tinybox.conf.example").read_text(encoding="utf-8") + "\n" + extra
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.conf"
            p.write_text(text, encoding="utf-8")
            return config.load(p)

    def test_defaults_follow_agw(self):
        cfg = self.load("")
        self.assertEqual(cfg.radio.interface, "agw")
        self.assertEqual(cfg.ax25.paclen, cfg.direwolf.paclen)
        self.assertEqual(cfg.ax25.maxframe, min(7, cfg.direwolf.max_outstanding))

    def test_kiss_sections(self):
        cfg = self.load("[radio]\ninterface = KISS\n[kiss]\nport = 8100\nair_baud = 9600\n"
                        "[ax25]\nversion = 2.0\nt2_sec = 0.5\n")
        self.assertEqual((cfg.radio.interface, cfg.kiss.port, cfg.kiss.air_baud),
                         ("kiss", 8100, 9600))
        self.assertEqual((cfg.ax25.version, cfg.ax25.t2_sec), ("2.0", 0.5))
        lc = kissadapter.link_cfg(cfg)
        self.assertEqual((lc.version, lc.air_baud, lc.t2_sec), ("2.0", 9600, 0.5))

    def test_invalid(self):
        for extra in ("[radio]\ninterface = serial\n", "[ax25]\nversion = 2.1\n",
                      "[ax25]\nmaxframe = 8\n", "[kiss]\nchannel = 16\n",
                      "[ax25]\nt1_min_sec = 40\nt1_max_sec = 30\n"):
            with self.assertRaises(config.ConfigError, msg=extra):
                self.load(extra)


if __name__ == "__main__":
    unittest.main()
