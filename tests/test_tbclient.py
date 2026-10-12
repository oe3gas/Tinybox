"""TinyBox client: parsers, emoji-free wire format, and end to end against a
real TinyBox (telnet test port, and radio through a fake Direwolf)."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import struct
import tempfile
import time
import unittest
from pathlib import Path

from tbclient import config as ccfg
from tbclient import proto, radio
from tbclient.core import ClientCore
from tbclient.web import WebServer
from tinybox.adapters import agw as tb_agw
from tinybox.adapters import telnet
from tests.test_chat import chat_app
from tests.test_tinybox import ROOT, FakeTransport, login, type_lines


def addr(call: str, last: bool) -> bytes:
    base, _, ssid = call.partition("-")
    return bytes(c << 1 for c in base.ljust(6).encode()) + bytes(
        [0x60 | (int(ssid or 0) << 1) | (1 if last else 0)])


def raw_frame(dest, src, control, info=b"", path=()):
    calls = [dest, src, *path]
    a = b"".join(addr(c, i == len(calls) - 1) for i, c in enumerate(calls))
    return a + bytes([control]) + ((bytes([0xF0]) + info) if control in (0x03, 0x00) else b"")


class RadioTests(unittest.TestCase):
    def test_decode_ui_and_path(self):
        f = radio.decode(raw_frame("TBCHAT-1", "OE3GAS-1", 0x03, b"#1 X: y"))
        self.assertTrue(f.is_ui and f.direct)
        self.assertEqual((f.dest, f.src, f.info), ("TBCHAT-1", "OE3GAS-1", b"#1 X: y"))
        f = radio.decode(raw_frame("APRS", "OE3TEC", 0x03, b"x", ["OE1XAR"]))
        self.assertFalse(f.direct)
        self.assertIsNone(radio.decode(b"\x00\x01"))

    def test_aprs_symbols(self):
        self.assertEqual(radio.aprs_symbol(b"!4833.07N/01606.22E-PHG2360"), "/-")
        self.assertEqual(radio.aprs_symbol(b"=4833.07N/01606.22E>mobil"), "/>")
        self.assertEqual(radio.aprs_symbol(b"@092345z4833.07N\\01606.22E#"), "\\#")
        self.assertEqual(radio.aprs_symbol(b"!/5L!!<*e7>7P["), "/>")       # compressed
        self.assertEqual(radio.aprs_symbol(b"`c51!f?>/]\"4V}="), "/>")     # Mic-E
        self.assertIsNone(radio.aprs_symbol(b">status text"))


class ProtoTests(unittest.TestCase):
    def test_events(self):
        e = proto.parse_event("#4F OE3GAS: Servus, Wetter passt :+1")
        self.assertEqual((e.seq, e.kind, e.call, e.text), (0x4F, "line", "OE3GAS",
                                                          "Servus, Wetter passt :+1"))
        e = proto.parse_event("#50 +OE3GAS /-")
        self.assertEqual((e.kind, e.call, e.symbol), ("join", "OE3GAS", "/-"))
        self.assertEqual(proto.parse_event("#51 -OE3GAS-9").kind, "leave")
        e = proto.parse_event("#52 OE3TEC *4F :+1")
        self.assertEqual((e.kind, e.ref, e.text), ("react", 0x4F, ":+1"))
        self.assertEqual(proto.parse_event("#53 !Board closes").kind, "system")
        self.assertIsNone(proto.parse_event("#zz nonsense"))
        self.assertIsNone(proto.parse_event("# 12 nothing"))

    def test_unwrap(self):
        u = proto.Unwrapper()
        u.reset(0xFE)
        self.assertEqual([u.unwrap(s) for s in (0xFF, 0x00, 0x01)], [255, 256, 257])
        self.assertEqual(u.unwrap(0xFF), 255)            # an old one, resent


class ConfigTests(unittest.TestCase):
    def test_example(self):
        cfg = ccfg.load(ROOT / "tbclient.conf.example")
        self.assertEqual((cfg.mycall, cfg.tinybox_call, cfg.link, cfg.web_port),
                         ("OE3GAS", "OE3GAS-1", "agw", 7744))
        self.assertEqual(cfg.data_dir, ROOT / "data" / "tbclient")


def client_cfg(tmp: str, **kw) -> ccfg.Config:
    return dataclasses.replace(ccfg.Config(), mycall="OE3GAS", tinybox_call="OE3GAS-1",
                               data_dir=Path(tmp), **kw)


async def until(cond, timeout=5.0):
    for _ in range(int(timeout / 0.02)):
        if cond():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("condition not reached")


# --- a fake Direwolf: AGW server, the "air" connects the AGW clients -------------

H = tb_agw.HEADER


class FakeDirewolf:
    def __init__(self) -> None:
        self.clients: list[dict] = []
        self.ui_sent: list[tuple[str, str]] = []
        self.chat_iframes: list[bytes] = []

    async def start(self) -> int:
        self.server = await asyncio.start_server(self._conn, "127.0.0.1", 0)
        return self.server.sockets[0].getsockname()[1]

    def _put(self, c, kind, cfrom="", cto="", data=b"", pid=0):
        c["w"].write(H.pack(0, kind.encode(), pid, cfrom.encode(), cto.encode(), len(data), 0)
                     + data)

    def _owner(self, call):
        return next((c for c in self.clients if call in c["calls"]), None)

    def _air(self, sender, frame: bytes):
        for c in self.clients:
            if c is not sender and c["mon"]:
                self._put(c, "K", data=b"\x00" + frame)

    async def _conn(self, r, w):
        me = {"w": w, "calls": set(), "mon": False}
        self.clients.append(me)
        try:
            while True:
                _p, kind, pid, cf, ct, n, _ = H.unpack(await r.readexactly(H.size))
                data = await r.readexactly(n) if n else b""
                kind, cf, ct = kind.decode(), tb_agw._call(cf), tb_agw._call(ct)
                if kind == "X":
                    me["calls"].add(cf)
                    self._put(me, "X", cf, data=b"\x01")
                elif kind == "k":
                    me["mon"] = True
                elif kind == "C":
                    other = self._owner(ct)
                    self._put(other, "C", cf, ct)                 # incoming connect
                    self._put(me, "C", ct, cf)                    # connected
                    self._air(me, raw_frame(ct, cf, 0x2F))        # SABM
                    self._air(other, raw_frame(cf, ct, 0x63))     # UA, heard directly
                elif kind == "D":
                    if data.startswith(b"#"):
                        self.chat_iframes.append(data)
                    self._put(self._owner(ct), "D", cf, ct, data, 0xF0)
                    self._air(me, raw_frame(ct, cf, 0x00, data))
                elif kind == "M":
                    self.ui_sent.append((ct, data.decode()))
                    self._air(me, raw_frame(ct, cf, 0x03, data))
                elif kind == "Y":
                    self._put(me, "Y", cf, ct, struct.pack("<I", 0))
                elif kind == "d":
                    other = self._owner(ct)
                    if other:
                        self._put(other, "d", cf, ct)
                    self._put(me, "d", ct, cf)
                await w.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass


class OwnReactionTests(unittest.TestCase):
    """CR8: an own reaction shows at once, the echo confirms it."""

    def test_react_shows_at_once(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp, link="telnet"))
                sent: list[str] = []
                core.link.send_line = sent.append
                core.board = {"n": 1, "name": "Chat", "keep": "live"}
                core._event(proto.Event(5, "line", "OE3TEC", text="hallo"))
                self.assertTrue(core.react(5, ":+1"))
                self.assertEqual(sent, ["/R 5 :+1"])
                snap = core.snapshot()
                self.assertEqual(snap["messages"][0]["reactions"], {":+1": ["OE3GAS"]})
                self.assertEqual(snap["pending_reacts"], ["5::+1"])
                # the echo from the TinyBox: no double entry, no longer pending
                core._event(proto.Event(6, "react", "OE3GAS", text=":+1", ref=5))
                snap = core.snapshot()
                self.assertEqual(snap["messages"][0]["reactions"], {":+1": ["OE3GAS"]})
                self.assertEqual(snap["pending_reacts"], [])
                # no echo within 2 minutes: taken back
                core.react(5, "~01")
                core.pending_reacts[(5, "~01")] -= 200
                snap = core.snapshot()
                self.assertEqual(snap["messages"][0]["reactions"], {":+1": ["OE3GAS"]})
                self.assertEqual(snap["pending_reacts"], [])
        asyncio.run(scenario())


class SymbolChangeTests(unittest.TestCase):
    """CR7: own change goes out as //SYM, a change of others updates the avatars."""

    def test_symbol_change(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp, link="telnet"))
                sent: list[str] = []
                core.link.send_line = sent.append
                core.state, core.caps = "online", {"CHAT"}
                core.board = {"n": 1, "name": "TREFF", "keep": "7d"}
                core._event(proto.Event(1, "join", "OE3TEC", symbol="/-"))
                self.assertEqual(core.snapshot()["symbols"]["OE3TEC"], "/-")
                core._event(proto.parse_event("#2 =OE3TEC /k"))
                self.assertEqual(core.snapshot()["symbols"]["OE3TEC"], "/k")
                self.assertEqual([m["kind"] for m in core.messages], ["join"])  # no chat line
                core._event(proto.parse_event("#3 =OE3TEC"))
                self.assertNotIn("OE3TEC", core.snapshot()["symbols"])
                self.assertTrue(core.set_symbol("/>"))
                self.assertEqual(sent[-1], "//SYM />")
                core.set_symbol("")
                self.assertEqual(sent[-1], "//SYM -")
        asyncio.run(scenario())


class HistoryOnRequestTests(unittest.TestCase):
    """CR13: the client asks for the history itself (missed lines by default)."""

    def make(self, tmp):
        core = ClientCore(client_cfg(tmp, link="telnet"))
        sent: list[str] = []
        core.link.send_line = sent.append
        core.state, core.caps = "online", {"CHAT"}
        return core, sent

    def test_join_modes(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                core, sent = self.make(tmp)
                now = int(time.time())
                core._control(f"//IN 1 TREFF 7d 5 hist=7 last=1000 now={now}")
                self.assertEqual(sent[-1], "//HIST max=20")          # first visit: last 20
                self.assertTrue(core.board["loading"])
                core._control("//H 990 OE3TEC: alt")
                core._control("//H 1000 OE3TEC: neu")
                core._control("//H 1000 OE3TEC: neu")               # same line twice: once
                core._control("//HEND 2 5")
                hist = [m for m in core.messages if m.get("history")]
                self.assertEqual([m["text"] for m in hist], ["alt", "neu"])
                self.assertEqual((core.board["older"], core.board["loading"]), (5, False))
                # older ones on request: before the oldest one shown (inclusive)
                self.assertTrue(core.load_history(10))
                self.assertEqual(sent[-1], "//HIST max=10 before=990")
                core._control("//H 980 OE3TEC: noch aelter")
                core._control("//H 990 OE3TEC: auch 990")           # same second as "alt"
                core._control("//H 990 OE3TEC: alt")                # inclusive: already here
                core._control("//HEND 3 4")
                texts = [m["text"] for m in core.messages if m.get("history")]
                self.assertEqual(texts, ["noch aelter", "auch 990", "alt", "neu"])   # in order
                # leaving remembers the visit (TinyBox time); next time only what was missed
                core._clear_board()
                seen = core.settings["seen"]["TREFF"]
                self.assertLessEqual(abs(seen - now), 2)
                n = len(sent)
                core._control(f"//IN 1 TREFF 7d 9 hist=7 last=1000 now={now}")
                self.assertEqual(len(sent), n)                       # nothing new: no request
                core._control(f"//IN 1 TREFF 7d 9 hist=8 last={now + 60} now={now}")
                self.assertEqual(sent[-1], f"//HIST max=20 since={seen}")
                # other modes
                core.set_history_mode("none")
                n = len(sent)
                core._control(f"//IN 1 TREFF 7d 9 hist=8 last={now + 60} now={now}")
                self.assertEqual(len(sent), n)
                self.assertEqual(core.board["older"], 8)             # the bar offers them
                core.set_history_mode("10")
                core._control(f"//IN 1 TREFF 7d 9 hist=8 last={now + 60} now={now}")
                self.assertEqual(sent[-1], "//HIST max=10")
                self.assertFalse(core.set_history_mode("all"))
                self.assertEqual(core.snapshot()["history_mode"], "10")
                # an older TinyBox (no hist=) sends the history by itself: no request
                n = len(sent)
                core._control("//IN 2 DX 24h 3")
                self.assertEqual(len(sent), n)
                self.assertFalse(core.load_history(10))
        asyncio.run(scenario())


class EndToEndTests(unittest.TestCase):
    def test_radio_with_ui(self):
        async def scenario():
            dw = FakeDirewolf()
            port = await dw.start()
            app = chat_app()
            app.cfg.direwolf = dataclasses.replace(app.cfg.direwolf, agw_port=port,
                                                   reconnect_sec=1)
            adapter = tb_agw.AgwAdapter(app)
            app.agw = adapter
            from tinybox import notify
            notify.MailNotifier(app)
            t1 = asyncio.create_task(adapter.run())
            await asyncio.wait_for(adapter.connected.wait(), 5)
            term, tt = login(app, "OE3XYZ")
            type_lines(term, "C TREFF")
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp, agw_port=port))
                core.set_symbol("/-")
                t2 = asyncio.create_task(core.run())
                await asyncio.wait_for(core.link.agw_up.wait(), 5)
                await core.connect()
                await until(lambda: core.boards, 10)
                self.assertEqual(core.caps, {"CHAT", "UI", "SYNC", "SYNC2", "Z"})
                self.assertTrue(core.join(1))
                await until(lambda: core.board and "OE3GAS" in core.members)
                self.assertEqual(core.members, {"OE3XYZ": "", "OE3GAS": "/-"})
                type_lines(term, "Servus :+1")
                await until(lambda: any(m.get("text") == "Servus :+1" for m in core.messages))
                core.say("Hallo ~0A")
                await until(lambda: "OE3GAS: Hallo ~0A" in tt.buf)
                await until(lambda: not core.pending)
                seq = next(m["seq"] for m in core.messages if m.get("text") == "Servus :+1")
                core.react(seq, ":+1")
                await until(lambda: any(m.get("reactions") for m in core.messages))
                # every chat event came once as UI, never as I-frame to the client
                self.assertEqual(dw.chat_iframes, [])
                self.assertIn(("TBCHAT-1", "#2 OE3XYZ: Servus :+1"), dw.ui_sent)
                # C1: private mail -> UI frame to TBMAIL -> notice in the client
                self.assertEqual(core.mail["count"], 0)     # "No new messages." at login
                app.service.create(from_call="OE3XYZ", to_call="OE3GAS", type="P",
                                   subject="Test", body="x", origin="telnet")
                await until(lambda: core.mail and core.mail["count"] == 1)
                self.assertIn(("TBMAIL", "OE3GAS 1 new"), dw.ui_sent)
                snap = core.snapshot()
                self.assertTrue(snap["ui"])
                self.assertEqual(snap["mail"]["count"], 1)
                self.assertEqual(snap["symbols"]["OE3GAS"], "/-")
                core.leave()
                await until(lambda: core.board is None)
                core.disconnect()
                await until(lambda: core.state == "offline")
                t2.cancel()
            t1.cancel()
            dw.server.close()
        asyncio.run(scenario())

    def test_telnet_and_web_api(self):
        async def scenario():
            app = chat_app()
            server = await asyncio.start_server(
                lambda r, w: telnet.TelnetConnection(app, r, w).run(), "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            term, tt = login(app, "OE3XYZ")
            type_lines(term, "C RUNDE")
            with tempfile.TemporaryDirectory() as tmp:
                cfg = client_cfg(tmp, link="telnet", telnet_port=port, web_host="127.0.0.1",
                                 web_port=0)
                core = ClientCore(cfg)
                web = await WebServer(core).start()
                wport = web.sockets[0].getsockname()[1]

                async def http(method, path, body=None, headers=True):
                    r, w = await asyncio.open_connection("127.0.0.1", wport)
                    data = json.dumps(body or {}).encode() if method == "POST" else b""
                    h = (f"{method} {path} HTTP/1.1\r\nHost: x\r\nConnection: close\r\n"
                         f"Content-Length: {len(data)}\r\n")
                    if headers and method == "POST":
                        h += "Content-Type: application/json\r\nX-TBClient: 1\r\n"
                    w.write(h.encode() + b"\r\n" + data)
                    raw = await r.read()
                    w.close()
                    head, _, payload = raw.partition(b"\r\n\r\n")
                    return int(head.split()[1]), payload

                self.assertEqual((await http("POST", "/api/connect", headers=False))[0], 403)
                self.assertEqual((await http("POST", "/api/connect"))[0], 200)
                await until(lambda: core.boards, 10)
                self.assertEqual(core.caps, {"CHAT", "SYNC", "SYNC2"})   # telnet: no UI, no Z
                await http("POST", "/api/join", {"board": 2})
                await until(lambda: core.board is not None)
                await http("POST", "/api/say", {"text": "per telnet ~01"})
                await until(lambda: "OE3GAS: per telnet ~01" in tt.buf)
                await until(lambda: any(m.get("text") == "per telnet ~01"
                                        for m in core.messages))
                status, body = await http("GET", "/api/state?since=-1")
                state = json.loads(body)
                self.assertEqual((status, state["board"]["name"]), (200, "RUNDE"))
                status, body = await http("GET", "/")
                self.assertIn(b"<title>TinyBox</title>", body)
                self.assertEqual((await http("GET", "/aprs/symbols-0.png"))[0], 200)
                self.assertEqual((await http("GET", "/../tbclient.conf"))[0], 404)
                core.disconnect()
                await until(lambda: core.state == "offline")
                web.close()
            server.close()
        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()


class EmoticonTests(unittest.TestCase):
    """CR28: emoticons <-> emojis in app.js, run with node (skipped without it)."""

    def run_js(self, cases):
        import shutil
        import subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        root = Path(__file__).resolve().parent.parent
        out = subprocess.run([node, str(root / "tests" / "fixtures" / "emoticons.js"),
                              str(root / "tbclient" / "web" / "app.js"),
                              str(root / "tbclient" / "web" / "emoji.json"), json.dumps(cases)],
                             capture_output=True, text=True, encoding="utf-8", check=True)
        return json.loads(out.stdout)

    def test_both_directions(self):
        r = self.run_js([["in", "das funktioniert ;-)"], ["in", "Hallo!:-) und :) oder :-D"],
                         ["in", "QTH:Pinkafeld http://x.at/ :/"], ["in", "sehr nett!~0B"],
                         ["in", "xD ~~ ~0C"],
                         ["out", "sehr nett!\U0001F642"], ["out", "\U0001F60A \U0001F604 \U0001F60E \U0001F914 \U0001F622"],
                         ["out", "Hallo \U0001F44D"],
                         ["live", "Hallo ;-) "], ["live", "nett!:-),"], ["live", "QTH:P "], ["live", "http://"],
                         ["groups", ""]])
        self.assertEqual(r["in:das funktioniert ;-)"], "das funktioniert \U0001F609")       # nose
        self.assertEqual(r["in:Hallo!:-) und :) oder :-D"], "Hallo!\U0001F642 und \U0001F642 oder \U0001F604")
        self.assertEqual(r["in:QTH:Pinkafeld http://x.at/ :/"], "QTH:Pinkafeld http://x.at/ \U0001F615")
        self.assertEqual(r["in:sehr nett!~0B"], "sehr nett!\U0001F642")                     # old client
        self.assertEqual(r["in:xD ~~ ~0C"], "\U0001F602 ~ \U0001F914")
        self.assertEqual(r["out:sehr nett!\U0001F642"], "sehr nett! :-)")                    # space added
        self.assertEqual(r["out:\U0001F60A \U0001F604 \U0001F60E \U0001F914 \U0001F622"], ":-) :-D 8-) ~0C :'(")
        self.assertEqual(r["out:Hallo \U0001F44D"], "Hallo :+1")
        self.assertEqual(r["live:Hallo ;-) "], "Hallo \U0001F609 |9")                       # cursor after
        self.assertEqual(r["live:nett!:-),"], "nett!\U0001F642,|8")
        self.assertEqual(r["live:QTH:P "], "QTH:P |6")                                       # not a word
        self.assertEqual(r["live:http://"], "http://|7")
        self.assertTrue(r["groups"][0].startswith("Smileys (ASCII, cheapest)=\U0001F642"))
        self.assertNotIn("\U0001F642", r["groups"][1])                                       # not twice
