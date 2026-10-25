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
from kisshub.tnc import BUNDLE_MAGIC, TUNNEL_MAGIC, Tnc, is_ui, pack_bundle, unpack_bundle
from prcore import termcolor
from kisshub.transport import TcpTransport
from prcore.ax25 import frame as ax
from prcore import kiss

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
        self._dec = kiss.Decoder()

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
                if cmd == kiss.CMD_DATA:
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
        elif text == "KISS ON":
            pass                     # the real PK-232 gives no cmd: here (17.10.2026)
        else:
            self.out(b"\r\ncmd:")

    def receive(self, frame: bytes) -> None:
        """A frame heard on the air: to the host as KISS."""
        self.out(kiss.encode(frame))


class HubTestBase(unittest.IsolatedAsyncioTestCase):
    profile = fast(profiles.PK232)

    async def start_hub(self, fake: FakePK232, **hubkw) -> Hub:
        self.fake = fake
        self.tnc_server = await asyncio.start_server(fake.handle, "127.0.0.1", 0)
        tport = self.tnc_server.sockets[0].getsockname()[1]
        params = {kiss.CMD_TXDELAY: 30, kiss.CMD_P: 63}

        def factory(on_frame):
            return Tnc(self.profile, TcpTransport("127.0.0.1", tport), on_frame,
                       reconnect_sec=0.2, params=params)

        hubkw.setdefault("status_port", -1)            # -1 = any free port (tests)
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
        dec = kiss.Decoder()

        async def pump():
            while data := await reader.read(4096):
                got.extend(f for _, c, f in dec.feed(data) if c == kiss.CMD_DATA)
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
        self.assertEqual(self.fake.params, [(kiss.CMD_TXDELAY, bytes((30,))),
                                            (kiss.CMD_P, bytes((63,)))])

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

    async def test_ctrl_c_still_leaves_kiss(self):
        """Ctrl+C cancels the hub's tasks before stop() runs: the TNC task must not
        close the port then, or stop() can no longer switch the TNC out of KISS."""
        await self.start_hub(FakePK232("cmd"))
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        for t in self.hub._tasks:
            t.cancel()
        await asyncio.gather(*self.hub._tasks, return_exceptions=True)
        self.assertEqual(self.hub.tnc.state, "kiss")
        with self.assertLogs("kisshub.tnc", "INFO") as logs:
            await self.hub.stop()
        self.assertIn("leaving KISS mode", "\n".join(logs.output))
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
        w1.write(kiss.encode(mine) + kiss.encode_param(kiss.CMD_TXDELAY, 1))
        await self.wait(lambda: self.fake.transmitted == [mine] and len(got2) == 2)
        self.assertEqual(got2[-1], mine)                          # client 2 "hears" it
        self.assertEqual(got1, [heard])                           # not echoed to sender
        self.assertNotIn((kiss.CMD_TXDELAY, b"\x01"), self.fake.params)

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
        from prcore.ax25.link import Ax25Link
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


class FakeTMD710(FakePK232):
    """Kenwood TM-D710 TNC in PACKET mode: HBAUD, KISS ON, RESTART (Gerhard,
    22.10.2026). 'aprs': TNC key in APRS position - the TNC gives no cmd:."""

    def __init__(self, state: str = "cmd") -> None:
        super().__init__(state)
        self.kiss_on = False
        self.hbaud = 9600

    def _byte(self, b: int) -> None:
        if self.state == "aprs":
            return
        super()._byte(b)

    def _command(self, text: str) -> None:
        if not text:
            self.out(b"\r\ncmd:")
            return
        self.lines.append(text)
        word, _, arg = text.partition(" ")
        if word == "HBAUD":
            self.out(f"\r\nHBAUD was {self.hbaud}\r\ncmd:".encode())
            self.hbaud = int(arg)
        elif text == "KISS ON":
            self.out(b"\r\nKISS was OFF\r\ncmd:")
            self.kiss_on = True
        elif text == "KISS OFF":
            self.out(b"\r\nKISS was ON\r\ncmd:")
            self.kiss_on = False
        elif text == "RESTART":
            if self.kiss_on:
                self.state = "kiss"
            else:
                self.out(b"\r\nTM-D710 TNC\r\ncmd:")
        else:
            self.out(b"\r\n?EH\r\ncmd:")


class TmD710Tests(HubTestBase):
    profile = fast(profiles.TM_D710)

    async def test_init_hbaud_kiss_restart(self):
        await self.start_hub(FakeTMD710("cmd"))
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        self.assertEqual(self.fake.lines, ["HBAUD 1200", "KISS ON", "RESTART"])
        self.assertEqual((self.fake.state, self.fake.hbaud), ("kiss", 1200))
        await self.wait(lambda: len(self.fake.params) == 2)

    async def test_wakes_from_kiss_and_converse(self):
        for state in ("kiss", "converse", "xoff"):
            with self.subTest(state=state):
                await self.start_hub(FakeTMD710(state))
                await asyncio.wait_for(self.hub.tnc.ready.wait(), 10)
                self.assertEqual(self.fake.lines[-1], "RESTART")
                await self.asyncTearDown()

    async def test_aprs_mode_gives_the_hint(self):
        with self.assertLogs("kisshub.tnc", "ERROR") as logs:
            await self.start_hub(FakeTMD710("aprs"))
            await self.wait(lambda: any("PACKET" in o for o in logs.output), 10)
        self.assertFalse(self.hub.tnc.ready.is_set())

    async def test_stop_leaves_kiss_and_switches_it_off(self):
        await self.start_hub(FakeTMD710("cmd"))
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        await self.hub.tnc.stop()
        await self.wait(lambda: self.fake.state == "cmd" and not self.fake.kiss_on)


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
        self.assertEqual(cfg.tnc.params[kiss.CMD_TXDELAY], 30)

    def test_example_tm_d710(self):
        text = (ROOT / "kisshub.conf.example").read_text(encoding="utf-8")
        text = text.replace("; [tnc.tm-d710]", "[tnc.tm-d710]").replace("; device = COM7", "device = COM7")
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "k.conf"
            p.write_text(text, encoding="utf-8")
            cfg = hubconfig.load(p, "tm-d710")
        self.assertEqual((cfg.tnc.profile.name, cfg.tnc.device, cfg.tnc.serial_baud),
                         ("tm-d710", "COM7", 9600))
        self.assertEqual([s.note for s in cfg.tnc.profile.init], ["HBAUD 1200", "KISS ON", "RESTART"])

    def d710(self, extra: str = ""):
        return self.load("[tnc]\nprofile=tm-d710\ndevice=COM7\n" + extra)

    def test_tm_d710_hbaud_default_1200(self):
        cfg = self.d710()
        self.assertEqual([s.note for s in cfg.tnc.profile.init], ["HBAUD 1200", "KISS ON", "RESTART"])
        self.assertEqual(cfg.hub.ax25["t1_min_sec"], 3.0)

    def test_tm_d710_hbaud_9600(self):
        cfg = self.d710("[kiss.tm-d710]\nair_baud = 9600\n")
        init = cfg.tnc.profile.init
        self.assertEqual([s.note for s in init], ["HBAUD 9600", "KISS ON", "RESTART"])
        self.assertEqual(init[0].send, b"HBAUD 9600\r")
        self.assertEqual(init[0].expect, profiles.TM_D710.init[0].expect)
        self.assertEqual((cfg.hub.air_baud, cfg.hub.sources["air_baud"]), (9600, "kisshub.conf"))
        self.assertEqual((cfg.hub.ax25["maxframe"], cfg.hub.ax25["t1_min_sec"]), (7, 1.5))

    def test_tm_d710_hbaud_invalid(self):
        with self.assertRaises(hubconfig.ConfigError) as cm:
            self.d710("[kiss]\nair_baud = 4800\n")
        self.assertIn("1200 or 9600", str(cm.exception))

    def test_tm_d710_init_lines_win(self):
        cfg = self.d710("init_lines = HBAUD 1200 | KISS ON\n[kiss]\nair_baud = 4800\n")
        self.assertEqual([s.note for s in cfg.tnc.profile.init], ["HBAUD 1200", "KISS ON"])

    def test_pk232_hbaud_stays_fixed(self):
        cfg = self.load("[tnc]\nprofile=pk232\ndevice=COM6\n[kiss]\nair_baud=9600\n")
        self.assertIn("HBAUD 1200", [s.note for s in cfg.tnc.profile.init])

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


class FakeVara:
    """VARA's KISS-TCP port as found on 17.10.2026: type 0 takes UI frames only
    ("Wrong KISS frame" for the rest), type 2 takes any bytes."""

    def __init__(self) -> None:
        self.type0: list[bytes] = []
        self.type2: list[bytes] = []
        self.wrong = 0
        self.writer: asyncio.StreamWriter | None = None
        self._dec = kiss.Decoder()

    async def handle(self, reader, writer) -> None:
        self.writer = writer
        try:
            while data := await reader.read(4096):
                for port, cmd, frame in self._dec.feed(data):
                    if cmd == 0 and port == 0:
                        if is_ui(frame):
                            self.type0.append(frame)
                        else:
                            self.wrong += 1
                    elif cmd == 2 and port == 0:
                        self.type2.append(frame)
        except (ConnectionError, OSError):
            pass
        finally:
            writer.close()

    def out(self, kind: int, data: bytes) -> None:
        self.writer.write(kiss.encode(data, 0, kind))


class VaraTunnelTests(HubTestBase):
    profile = profiles.VARA_FM

    async def test_connected_frames_go_through_type_2(self):
        vara = FakeVara()
        await self.start_hub(vara)
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        w, got = await self.client()
        sabme = ax.u_frame("SABME", "OE3GAS-1", "OE3GAS", pf=True).encode()
        ui = ax.ui_frame("TEST", "OE3GAS", b"hello vara").encode()
        w.write(kiss.encode(sabme) + kiss.encode(ui))
        await self.wait(lambda: vara.type2 and vara.type0)
        self.assertEqual(vara.type2, [TUNNEL_MAGIC + sabme])     # unchanged inside
        self.assertEqual(vara.type0, [ui])                       # UI stays readable
        self.assertEqual(vara.wrong, 0)
        self.assertFalse(self.hub.tnc.set_param(kiss.CMD_P, 63))   # console: not to VARA
        # the other station's answer comes back through type 2 -> a normal frame
        ua = ax.u_frame("UA", "OE3GAS", "OE3GAS-1", command=False, pf=True).encode()
        vara.out(2, TUNNEL_MAGIC + ua)
        await self.wait(lambda: got == [ua])
        # VARA hands our own frame back: dropped; type-2 data of others: ignored
        vara.out(2, TUNNEL_MAGIC + sabme)
        vara.out(2, b"HE0\rsomebody's VarAC data")
        heard = ax.ui_frame("CQ", "OE1ABC", b"vara ui").encode()
        vara.out(0, heard)
        await self.wait(lambda: len(got) == 2)
        self.assertEqual(got, [ua, heard])
        st = self.hub.tnc.status()
        self.assertEqual((st["tunnel"], st["tunnel_tx"], st["tunnel_rx"], st["echoes"],
                          st["foreign"]), ("connected", 1, 1, 1, 1))

    async def test_bundling(self):
        vara = FakeVara()
        self.profile = dataclasses.replace(profiles.VARA_FM, bundle_ms=100, bundle_max=250)
        await self.start_hub(vara, max_lead_sec=60)
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        w, got = await self.client()
        frames = [ax.i_frame("OE3GAS-1", "OE3GAS", n, 0, bytes([65 + n]) * 60,
                             modulo=128).encode() for n in range(4)]
        ui = ax.ui_frame("TEST", "OE3GAS", b"stays type 0").encode()
        for f in frames:
            self.hub.enqueue(f)
        self.hub.enqueue(ui)
        await self.wait(lambda: len(vara.type2) == 2 and vara.type0)
        # 4 x (2 + 77) bytes: three fit into 250, the fourth goes alone
        self.assertEqual(unpack_bundle(vara.type2[0]), frames[:3])
        self.assertEqual(vara.type2[1], TUNNEL_MAGIC + frames[3])
        self.assertEqual(vara.type0, [ui])
        st = self.hub.tnc.status()
        self.assertEqual((st["bundles_tx"], st["bundled_tx"], st["tunnel_tx"]), (1, 3, 4))
        # the other station's bundle is unpacked into single frames for the clients
        answers = [ax.s_frame("RR", "OE3GAS", "OE3GAS-1", n, modulo=128).encode()
                   for n in (1, 2)]
        vara.out(2, pack_bundle(answers))
        vara.out(2, BUNDLE_MAGIC + b"\x00\x40broken")
        await self.wait(lambda: len(got) >= 2)
        await asyncio.sleep(0.05)
        self.assertEqual(got[-2:], answers)
        st = self.hub.tnc.status()
        self.assertEqual((st["bundles_rx"], st["bundled_rx"], st["foreign"]), (1, 2, 1))

    async def test_all_and_no(self):
        vara = FakeVara()
        self.profile = dataclasses.replace(profiles.VARA_FM, tunnel="all")
        await self.start_hub(vara)
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        ui = ax.ui_frame("TEST", "OE3GAS", b"x").encode()
        self.hub.enqueue(ui)
        await self.wait(lambda: vara.type2)
        self.assertEqual((vara.type2, vara.type0), ([TUNNEL_MAGIC + ui], []))
        self.assertFalse(is_ui(ax.u_frame("SABM", "A1A", "B1B").encode()))
        self.assertTrue(is_ui(ax.ui_frame("A1A", "B1B", b"", path=["C1C", "D1D"]).encode()))



class RadioValuesTests(unittest.TestCase):
    """CR70: kisshub owns the radio values and tells where each one came from."""

    def load(self, text: str, dw: str | None = None):
        with tempfile.TemporaryDirectory() as d:
            if dw is not None:
                (Path(d) / "direwolf.conf").write_text(dw, encoding="utf-8")
                text = text.replace("DWDIR", d)
            p = Path(d) / "k.conf"
            p.write_text(text, encoding="utf-8")
            return hubconfig.load(p)

    def test_vara_profile_defaults(self):
        cfg = self.load("[tnc]\nprofile=vara-fm\n")          # transport tcp, port 8100 implied
        self.assertEqual((cfg.tnc.transport, cfg.tnc.port), ("tcp", 8100))
        h = cfg.hub
        self.assertEqual((h.air_baud, h.txdelay_sec, h.max_lead_sec), (350, 2.7, 12.0))
        self.assertEqual(h.sources["air_baud"], "profile vara-fm")
        self.assertEqual((h.ax25["paclen"], h.ax25["maxframe"], h.ax25["t1_min_sec"]),
                         (256, 4, 18.0))
        self.assertEqual((h.status_port, cfg.hints), (8102, ()))
        text = "\n".join(termcolor.kv_plain(*x) for x in hubconfig.radio_lines(cfg))
        self.assertIn("air_baud 350 (profile vara-fm)", text)

    def test_overrides_and_old_keys(self):
        cfg = self.load("[tnc]\nprofile=vara-fm\n[kiss]\nair_baud=600\n"
                        "[ax25]\nt1_min_sec=25\n[server]\nport=8201\nstatus_port=8202\n")
        h = cfg.hub
        self.assertEqual((h.air_baud, h.sources["air_baud"]), (600, "kisshub.conf"))
        self.assertEqual(h.ax25["t1_min_sec"], 25.0)
        self.assertIn("kisshub.conf [ax25]", h.sources["ax25"])
        self.assertEqual(h.status_port, 8202)
        self.assertIn("can be removed", cfg.hints[0])
        self.assertEqual(self.load("[tnc]\nprofile=vara-fm\n[server]\nport=8201\n")
                         .hub.status_port, 8202)
        with self.assertRaises(hubconfig.ConfigError):
            self.load("[tnc]\nprofile=vara-fm\n[ax25]\nwindow=3\n")

    def test_direwolf_profile(self):
        dw = "MODEM 9600\nTXDELAY 15\nKISSPORT 8011\nPACLEN 200\nEMAXFRAME 6\n"
        cfg = self.load("[tnc]\nprofile=direwolf\ndirewolf_conf=DWDIR\n", dw)
        self.assertEqual((cfg.tnc.transport, cfg.tnc.port, cfg.tnc.params), ("tcp", 8011, {}))
        h = cfg.hub
        self.assertEqual((h.air_baud, round(h.txdelay_sec * 1000)), (9600, 150))
        self.assertEqual(h.sources["txdelay_ms"], "direwolf.conf")
        self.assertEqual((h.ax25["paclen"], h.ax25["maxframe_ext"]), (200, 6))
        self.assertIn("MODEM 9600", "\n".join(termcolor.kv_plain(*x) for x in hubconfig.radio_lines(cfg)))
        with self.assertRaises(hubconfig.ConfigError):
            self.load("[tnc]\nprofile=direwolf\n")
        with self.assertRaises(hubconfig.ConfigError):
            self.load("[tnc]\nprofile=direwolf\ndirewolf_conf=/nowhere/x\n")

    def test_status_has_radio_block(self):
        cfg = self.load("[tnc]\nprofile=vara-fm\n")
        from tests.test_kisshub_quality import _NoTnc
        hub = Hub(dataclasses.replace(cfg.hub, port=0, status_port=0, links_file=""),
                  lambda on_frame: _NoTnc())
        r = hub.radio_dict()
        self.assertEqual((r["air_baud"], r["txdelay_ms"], r["profile"]), (350, 2700, "vara-fm"))
        self.assertEqual(r["ax25"]["t2_sec"], 0.3)
        self.assertEqual(r["source"]["max_lead_ms"], "profile vara-fm")


class OneConfTests(unittest.TestCase):
    """One kisshub.conf for PK-232, VARA and Direwolf: -p, [<section>.<profile>], {profile}."""

    CONF = ("[tnc]\nprofile = pk232\ndevice = COM3\ndirewolf_conf = DWDIR\n"
            "[tnc.vara-fm]\nhost = 127.0.0.2\n"
            "[kiss.pk232]\ntxdelay_ms = 400\n"
            "[log]\nfile = kisshub-{profile}.log\nlinks_file = links-{profile}.jsonl\n"
            "[vara]\nmonitor = yes\n")

    def load(self, profile=None, conf=None):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "direwolf.conf").write_text("KISSPORT 8001\nMODEM 1200\nTXDELAY 25\n",
                                                   encoding="utf-8")
            p = Path(d) / "k.conf"
            p.write_text((conf or self.CONF).replace("DWDIR", d), encoding="utf-8")
            return hubconfig.load(p, profile)

    def test_three_profiles_one_file(self):
        pk = self.load()
        self.assertEqual((pk.tnc.profile.name, pk.tnc.transport, pk.tnc.device),
                         ("pk232", "serial", "COM3"))
        self.assertEqual((round(pk.hub.txdelay_sec * 1000), pk.tnc.params[kiss.CMD_TXDELAY]),
                         (400, 40))                        # [kiss.pk232]
        self.assertEqual((pk.log_file, pk.hub.links_file),
                         ("kisshub-pk232.log", "links-pk232.jsonl"))
        self.assertFalse(pk.hub.vara_monitor)              # ignored, not an error
        self.assertIn("monitor = yes: ignored", pk.hints[0])
        va = self.load("vara-fm")
        self.assertEqual((va.tnc.transport, va.tnc.host, va.tnc.port), ("tcp", "127.0.0.2", 8100))
        self.assertEqual((va.hub.air_baud, round(va.hub.txdelay_sec * 1000)), (350, 2700))
        self.assertTrue(va.hub.vara_monitor)
        self.assertEqual(va.log_file, "kisshub-vara-fm.log")
        dw = self.load("direwolf")
        self.assertEqual((dw.tnc.port, round(dw.hub.txdelay_sec * 1000)), (8001, 250))

    def test_bad_section_and_profile(self):
        with self.assertRaises(hubconfig.ConfigError):
            self.load(conf="[tnc]\nprofile = pk232\ndevice = COM3\n[kiss.pk999]\nx = 1\n")
        with self.assertRaises(hubconfig.ConfigError):
            self.load("nix")

    def test_help(self):
        import contextlib
        import io
        from kisshub.__main__ import parser
        for opt in ("-h", "-?"):
            out = io.StringIO()
            with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
                parser().parse_args([opt])
            self.assertIn("one kisshub.conf for all TNCs", out.getvalue())
        self.assertEqual(parser().parse_args(["-p", "vara-fm"]).profile, "vara-fm")


class VaraConfigTests(unittest.TestCase):
    def test_config(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "k.conf"
            p.write_text("[tnc]\nprofile=vara-fm\ntransport=tcp\nport=8100\n", encoding="utf-8")
            cfg = hubconfig.load(p)
            self.assertEqual((cfg.tnc.profile.tunnel, cfg.tnc.params), ("connected", {}))
            p.write_text("[tnc]\nprofile=vara-fm\ntransport=tcp\nport=8100\nvara_tunnel=all\n",
                         encoding="utf-8")
            self.assertEqual(hubconfig.load(p).tnc.profile.tunnel, "all")
            # KISS parameters would be VARA frames of type 1/2 on the air
            p.write_text("[tnc]\nprofile=vara-fm\ntransport=tcp\nport=8100\n"
                         "[kiss]\nsend_params=yes\n", encoding="utf-8")
            with self.assertRaises(hubconfig.ConfigError):
                hubconfig.load(p)
            p.write_text("[tnc]\nprofile=vara-fm\ntransport=tcp\nport=8100\nvara_tunnel=maybe\n",
                         encoding="utf-8")
            with self.assertRaises(hubconfig.ConfigError):
                hubconfig.load(p)


if __name__ == "__main__":
    unittest.main()


class ConsoleTests(HubTestBase):
    async def test_console_mark_debug_trace_and_live_txdelay(self):
        import logging as _logging
        from kisshub.console import Console, LogControl
        await self.start_hub(FakePK232("cmd"))
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        await self.wait(lambda: len(self.fake.params) == 2)
        lines: list[str] = []
        ctl = LogControl("INFO", "")
        con = Console(self.hub, ctl, out=lambda *a: lines.append(" ".join(map(str, a))))
        with self.assertLogs("kisshub", "INFO") as logs:
            con.handle_line("log mark test 1")
            con.handle_line("LOG TRACE")
            con.handle_line("TXDELAY 600")
        text = "\n".join(logs.output)
        self.assertIn("MARK: test 1", text)
        self.assertIn(">> TNC param TXDELAY=60", text)
        await self.wait(lambda: len(self.fake.params) == 3)
        self.assertEqual(self.fake.params[-1], (kiss.CMD_TXDELAY, bytes((60,))))
        self.assertEqual(self.hub.tnc.state, "kiss")            # never left KISS
        self.assertAlmostEqual(self.hub.cfg.txdelay_sec, 0.6)
        con.handle_line("LOG DEBUG")
        self.assertEqual(_logging.getLogger("kisshub").level, _logging.DEBUG)
        con.handle_line("LOG OFF")
        self.assertFalse(self.hub.tnc.trace)
        self.assertEqual(_logging.getLogger("kisshub").level, _logging.NOTSET)
        con.handle_line("PARAMS")
        self.assertIn("TXDELAY 600 ms", lines[-1])
        con.handle_line("bogus")
        self.assertIn("unknown command", lines[-1])
