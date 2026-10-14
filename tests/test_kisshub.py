"""kisshub: TNC dialog, KISS-TCP hub, priorities (KISS step K7).

FakePK232 plays the TNC over TCP in the states pk232py met on real devices:
command mode, autobaud after power-up, Converse, stopped by XOFF, Host Mode,
and KISS (from a previous hub run). The end-to-end test runs TinyBox ->
kisshub -> FakePK232 -> a station with its own AX.25 link.
"""

from __future__ import annotations

import asyncio
import dataclasses
import tempfile
import unittest
from pathlib import Path

from kisshub import config as hubconfig
from kisshub import profiles
from kisshub.hub import PRIO_CONTROL, PRIO_I, PRIO_UI, Hub, HubCfg, priority
from kisshub.tnc import Tnc
from kisshub.transport import TcpTransport
from tinybox.ax25 import frame as ax
from tinybox.ax25 import kissio

ROOT = Path(__file__).resolve().parent.parent
EXPERT_ONLY = {"RAWHDLC", "HPOLL", "PPERSIST"}
BANNER = b"\r\nAEA PK-232M Data Controller\r\nRelease 13.SEP.95\r\ncmd:"


def fast(p: profiles.Profile, factor: float = 0.1) -> profiles.Profile:
    """Same profile, timeouts scaled down for the tests."""
    def sc(steps):
        return tuple(dataclasses.replace(s, timeout=s.timeout * factor) for s in steps)
    return dataclasses.replace(p, wake=sc(p.wake), init=sc(p.init),
                               exit_lines=sc(p.exit_lines), settle_sec=0.05)


class FakePK232:
    """Just enough PK-232 behaviour on a TCP socket."""

    def __init__(self, state: str = "cmd") -> None:
        self.state = state          # autobaud | cmd | converse | xoff | host | kiss
        self.lines: list[str] = []
        self.transmitted: list[bytes] = []     # AX.25 frames sent "on the air"
        self.params: list[tuple[int, bytes]] = []
        self.on_air = None                     # callback(frame) for the e2e test
        self.writer: asyncio.StreamWriter | None = None
        self.connected = asyncio.Event()
        self.reject: set[str] = set()          # commands answered without a prompt
        self.expert = False
        self._line = bytearray()
        self._host = bytearray()
        self._dec = kissio.Decoder()

    async def handle(self, reader, writer) -> None:
        self.writer = writer
        self.connected.set()
        try:
            while data := await reader.read(4096):
                self.feed(data)
        except ConnectionError:
            pass
        finally:
            writer.close()

    def out(self, data: bytes) -> None:
        if self.writer is not None and not self.writer.is_closing():
            self.writer.write(data)

    def feed(self, data: bytes) -> None:
        if self.state == "kiss":
            if bytes((0xC0, 0xFF, 0xC0)) in data:              # leave KISS
                self.state = "cmd"
                return
            for port, cmd, frame in self._dec.feed(data):
                if cmd == kissio.CMD_DATA:
                    self.transmitted.append(frame)
                    if self.on_air:
                        self.on_air(frame)
                else:
                    self.params.append((cmd, frame))
            return
        if self.state == "host":
            self._host += data
            if profiles.PK_HOST_OFF in self._host:
                self.state, self._host = "cmd", bytearray()
            return
        for b in data:
            self._byte(b)

    def _byte(self, b: int) -> None:
        if self.state == "autobaud":
            if b == ord("*"):
                self.state = "cmd"
                self.out(BANNER)
            return
        if self.state == "xoff":
            self.out(bytes((b,)))                                # echo, nothing else
            if b == 0x11:
                self.state = "cmd"
            return
        if self.state == "converse":
            if b == 0x03:
                self.state = "cmd"
            return
        if b == 13:
            text = self._line.decode("ascii", "replace").strip("\x00\x03\x11* ")
            self._line.clear()
            self._command(text)
        elif 32 <= b < 127:
            self._line.append(b)
            self.out(bytes((b,)))                                # echo

    def _command(self, text: str) -> None:
        if not text:
            self.out(b"\r\ncmd:")
            return
        self.lines.append(text)
        if text in self.reject:
            self.out(b"\r\n?bad\r\n")
            return
        if text == "EXPERT ON":
            self.expert = True
        if text.split()[0] in EXPERT_ONLY and not self.expert:
            self.out(b"\r\n?EXPERT command\r\ncmd:")     # pk232py hw_logs, T175
            return
        if text == "RESTART":
            self.out(BANNER)
        elif text == "HOST ON" and "KISS ON" in self.lines:
            self.state = "kiss"
        elif text == "HOST ON":
            self.state = "host"
        else:
            self.out(b"\r\ncmd:")

    def receive(self, frame: bytes) -> None:
        """A frame heard on the air: to the host as KISS."""
        self.out(kissio.encode(frame))


class HubTestBase(unittest.IsolatedAsyncioTestCase):
    profile = fast(profiles.PK232)

    async def start_hub(self, fake: FakePK232, **hubkw) -> Hub:
        self.fake = fake
        self.tnc_server = await asyncio.start_server(fake.handle, "127.0.0.1", 0)
        tport = self.tnc_server.sockets[0].getsockname()[1]
        params = {kissio.CMD_TXDELAY: 30, kissio.CMD_P: 63}

        def factory(on_frame):
            return Tnc(self.profile, TcpTransport("127.0.0.1", tport), on_frame,
                       reconnect_sec=0.2, params=params)

        cfg = HubCfg(port=0, air_baud=hubkw.pop("air_baud", 1_000_000),
                     txdelay_sec=hubkw.pop("txdelay_sec", 0.0), status_every_sec=0, **hubkw)
        self.hub = Hub(cfg, factory)
        await self.hub.start()
        return self.hub

    async def asyncTearDown(self):
        await self.hub.stop()
        self.tnc_server.close()
        await self.tnc_server.wait_closed()

    async def wait(self, cond, timeout: float = 5.0) -> None:
        loop = asyncio.get_running_loop()
        end = loop.time() + timeout
        while not cond():
            if loop.time() > end:
                raise AssertionError("timed out")
            await asyncio.sleep(0.01)

    async def client(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.hub.port)
        got: list[bytes] = []
        dec = kissio.Decoder()

        async def pump():
            while data := await reader.read(4096):
                got.extend(f for _, c, f in dec.feed(data) if c == kissio.CMD_DATA)
        task = asyncio.create_task(pump())
        self.addAsyncCleanup(self._close, writer, task)
        await self.wait(lambda: len(self.hub.clients) >= 1)
        return writer, got

    @staticmethod
    async def _close(writer, task):
        writer.close()
        task.cancel()


class TncDialogTests(HubTestBase):
    async def test_init_from_command_mode(self):
        await self.start_hub(FakePK232("cmd"))
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        self.assertEqual(self.fake.lines, [s.note for s in profiles.PK232.init])
        self.assertIn("VHF ON", self.fake.lines)
        self.assertEqual(self.fake.lines[0], "EXPERT ON")
        self.assertEqual(self.fake.lines[-2:], ["KISS ON", "HOST ON"])
        await self.wait(lambda: len(self.fake.params) == 2)
        self.assertEqual(self.fake.params, [(kissio.CMD_TXDELAY, bytes((30,))),
                                            (kissio.CMD_P, bytes((63,)))])

    async def test_wakes_from_every_state(self):
        for state in ("autobaud", "converse", "xoff", "host", "kiss"):
            with self.subTest(state=state):
                await self.start_hub(FakePK232(state))
                await asyncio.wait_for(self.hub.tnc.ready.wait(), 10)
                self.assertEqual(self.fake.lines[-1], "HOST ON")
                await self.asyncTearDown()

    async def test_failing_init_line_is_reported_and_retried(self):
        fake = FakePK232("cmd")
        fake.reject = {"PACKET"}
        with self.assertLogs("kisshub.tnc", "ERROR") as logs:
            await self.start_hub(fake)
            await self.wait(lambda: fake.lines.count("PACKET") >= 2, 10)
        self.assertIn("PACKET", "\n".join(logs.output))
        self.assertIn("?bad", "\n".join(logs.output))
        self.assertFalse(self.hub.tnc.ready.is_set())

    async def test_expert_command_refused_stops_the_init(self):
        """Without EXPERT ON the PK-232 says '?EXPERT command' and still prompts:
        that must stop the init, not end in a half set-up KISS."""
        self.profile = dataclasses.replace(
            self.profile, init=tuple(s for s in self.profile.init if s.note != "EXPERT ON"))
        fake = FakePK232("cmd")
        with self.assertLogs("kisshub.tnc", "ERROR") as logs:
            await self.start_hub(fake)
            await self.wait(lambda: any("EXPERT command" in o for o in logs.output), 10)
        self.assertIn("RAWHDLC ON", "\n".join(logs.output))
        self.assertNotIn("KISS ON", fake.lines)
        self.assertFalse(self.hub.tnc.ready.is_set())

    async def test_stop_leaves_kiss_and_switches_it_off(self):
        await self.start_hub(FakePK232("cmd"))
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        await self.hub.tnc.stop()
        await self.wait(lambda: self.fake.state == "cmd" and "KISS OFF" in self.fake.lines)

    async def test_tnc_lost_and_back(self):
        await self.start_hub(FakePK232("cmd"))
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        self.fake.connected.clear()
        self.fake.writer.close()
        await self.wait(lambda: not self.hub.tnc.ready.is_set())
        await asyncio.wait_for(self.fake.connected.wait(), 5)
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 10)   # woken from KISS again


class HubTests(HubTestBase):
    async def test_frames_to_all_clients_and_mirror(self):
        await self.start_hub(FakePK232("cmd"))
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        w1, got1 = await self.client()
        w2, got2 = await self.client()
        await self.wait(lambda: len(self.hub.clients) == 2)
        heard = ax.ui_frame("APRS", "OE1ABC", b"!test").encode()
        self.fake.receive(heard)
        await self.wait(lambda: got1 == [heard] and got2 == [heard])
        mine = ax.ui_frame("TBCHAT-1", "OE3GAS-1", b"hi").encode()
        w1.write(kissio.encode(mine) + kissio.encode_param(kissio.CMD_TXDELAY, 1))
        await self.wait(lambda: self.fake.transmitted == [mine] and len(got2) == 2)
        self.assertEqual(got2[-1], mine)                          # client 2 "hears" it
        self.assertEqual(got1, [heard])                           # not echoed to sender
        self.assertNotIn((kissio.CMD_TXDELAY, b"\x01"), self.fake.params)

    async def test_acknowledgement_overtakes_ui_frames(self):
        # 1200 Bd, 0.3 s lead: only about one 100-byte frame at a time goes to the TNC
        await self.start_hub(FakePK232("cmd"), air_baud=1200, txdelay_sec=0.0,
                             max_lead_sec=0.3)
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        pages = [ax.ui_frame("BROCST", "OE3GAS-2", bytes([i]) * 100).encode()
                 for i in range(5)]
        for p in pages:
            self.hub.enqueue(p)
        await self.wait(lambda: len(self.fake.transmitted) >= 1)
        rr = ax.s_frame("RR", "OE1ABC", "OE3GAS-1", 3).encode()
        self.hub.enqueue(rr)
        await self.wait(lambda: len(self.fake.transmitted) == 6, 15)
        self.assertLess(self.fake.transmitted.index(rr), 3)

    async def test_priority_classes(self):
        self.assertEqual(priority(ax.s_frame("RR", "A1A", "B1B", 1).encode()), PRIO_CONTROL)
        self.assertEqual(priority(ax.u_frame("UA", "A1A", "B1B", command=False).encode()),
                         PRIO_CONTROL)
        self.assertEqual(priority(ax.u_frame("SABME", "A1A", "B1B").encode()), PRIO_CONTROL)
        self.assertEqual(priority(ax.i_frame("A1A", "B1B", 0, 0, b"x").encode()), PRIO_I)
        self.assertEqual(priority(ax.i_frame("A1A", "B1B", 0, 0, b"x", modulo=128).encode()),
                         PRIO_I)
        self.assertEqual(priority(ax.ui_frame("A1A", "B1B", b"x").encode()), PRIO_UI)
        self.assertEqual(priority(b"\x00garbage"), PRIO_UI)
        self.hub = None

    async def asyncTearDown(self):
        if self.hub is not None:
            await super().asyncTearDown()


class EndToEndTests(HubTestBase):
    async def test_tinybox_over_kisshub_and_pk232(self):
        """TinyBox (KissAdapter) -> kisshub -> PK-232 -> air -> a station."""
        from tinybox.adapters import kiss as kissadapter
        from tinybox.ax25.link import Ax25Link
        from tests.test_kiss_adapter import kiss_app, station_cfg

        fake = FakePK232("kiss")                       # left in KISS by a previous run
        await self.start_hub(fake)
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 10)
        loop = asyncio.get_running_loop()
        st = Ax25Link("OE1ABC", "OE3GAS-1", cfg=station_cfg("2.0"), now=loop.time())
        rx = bytearray()
        events = []

        def pump():
            for f in st.pop_output():
                fake.receive(f.encode())
            for e in st.pop_events():
                events.append(e)
                if e[0] == "data":
                    rx.extend(e[1])

        def on_air(raw):
            dest, *_ = ax.peek(raw)
            if dest == "OE1ABC":
                st.receive(ax.Frame.decode(raw, st.modulo), loop.time())
                pump()
        fake.on_air = on_air

        async def ticks():
            while True:
                await asyncio.sleep(0.02)
                d = st.next_deadline()
                if d is not None and d <= loop.time():
                    st.tick(loop.time())
                    pump()
        ticker = asyncio.create_task(ticks())

        app = kiss_app(self.hub.port, "2.2")
        adapter = kissadapter.KissAdapter(app)
        app.agw = adapter
        task = asyncio.create_task(adapter.run())
        try:
            await asyncio.wait_for(adapter.connected.wait(), 5)
            st.connect(loop.time())
            pump()
            await self.wait(lambda: b"hello" in rx, 10)
            st.send(b"S OE3GAS\rVia PK-232\rKISS works\r/EX\rB\r", loop.time())
            pump()
            await self.wait(lambda: any(e[0] == "disconnected" for e in events), 20)
        finally:
            task.cancel()
            ticker.cancel()
            await asyncio.gather(task, ticker, return_exceptions=True)
        self.assertIn(b"Msg 1 saved.", bytes(rx))
        self.assertEqual(app.store.get(1).body, "KISS works")
        kinds = [ax.Frame.decode(f).kind for f in fake.transmitted[:1]]
        self.assertEqual(kinds, ["UA"])                # v2.0 station called with SABM


class HubConfigTests(unittest.TestCase):
    def load(self, text: str):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "k.conf"
            p.write_text(text, encoding="utf-8")
            return hubconfig.load(p)

    def test_example(self):
        cfg = hubconfig.load(ROOT / "kisshub.conf.example")
        self.assertEqual((cfg.tnc.profile.name, cfg.tnc.device, cfg.hub.port),
                         ("pk232", "COM3", 8101))
        self.assertEqual(cfg.tnc.params[kissio.CMD_TXDELAY], 30)

    def test_init_lines_override(self):
        cfg = self.load("[tnc]\nprofile=generic\ntransport=tcp\nport=4001\n"
                        "init_lines = A ONE | B TWO | KISS ON\n")
        self.assertEqual([s.note for s in cfg.tnc.profile.init], ["A ONE", "B TWO", "KISS ON"])
        self.assertEqual(cfg.tnc.profile.init[-1].expect, ())

    def test_invalid(self):
        for text in ("[tnc]\nprofile=pk9999\ndevice=COM1\n", "[tnc]\nprofile=pk232\n",
                     "[tnc]\nprofile=pk232\ntransport=tcp\n",
                     "[tnc]\ndevice=COM1\n[kiss]\npersist=300\n"):
            with self.assertRaises(hubconfig.ConfigError, msg=text):
                self.load(text)


if __name__ == "__main__":
    unittest.main()
