"""C3: offline mailbox - sync commands in the TinyBox, local store and sync in the client."""

from __future__ import annotations

import asyncio
import dataclasses
import random
import time
from unittest import mock
import tempfile
import unittest
from pathlib import Path

from tbclient.core import ClientCore
from tbclient.links import LineSplitter
from tbclient.mailstore import MailStore
from tbclient import VERSION, sync
from tbclient.sync import parse_header
from tinybox.adapters import agw as tb_agw
from tinybox.fwd import lzhuf
from tinybox.session import Session, State
from tests.test_chat import chat_app
from tests.test_tbclient import FakeDirewolf, client_cfg, until
from tests.test_tinybox import FakeTransport, login, type_lines

LONG = "\n".join(f"Zeile {i}: Das Wetter im Weinviertel ist heute wieder schoen." for i in range(30))


class BinTransport(FakeTransport):
    """Like the AGW transport: text and raw bytes in one stream."""

    def __init__(self) -> None:
        super().__init__()
        self.raw = b""

    def write(self, text: str) -> None:
        self.raw += text.encode("utf-8")

    def write_bytes(self, data: bytes) -> None:
        self.raw += data


def client(app, call="OE3GAS", caps="CHAT,SYNC,Z", radio=False):
    t = BinTransport() if radio else FakeTransport()
    s = Session(call, app.service, app.cfg, t, origin="radio" if radio else "telnet")
    s.start()
    type_lines(s, f"//CLIENT TB1 caps={caps}")
    if radio:
        t.raw = b""
    else:
        t.take()
    return s, t


def mail(app, frm, to, subject, body="x", type="P"):
    return app.service.create(from_call=frm, to_call=to, type=type, subject=subject, body=body,
                              origin="telnet")


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.app = chat_app()
        self.a = mail(self.app, "OE3TEC", "OE3GAS", "Hallo Gerhard", "Text 1\nZeile 2")
        self.b = mail(self.app, "OE3GAS", "OE3TEC", "Antwort")
        self.c = mail(self.app, "OE3TEC", "OE1ABC", "Fremd")                  # not mine
        self.d = mail(self.app, "OE3TEC", "ALL", "Bulletin 1", type="B")
        self.e = mail(self.app, "OE3TEC", "WX", "Wetter", LONG, type="B")

    def test_caps_and_lists(self):
        s, t = login(self.app, "OE3GAS")
        t.take()
        type_lines(s, "//MLIST")
        self.assertIn("//ERR", t.take())                  # not a client yet
        type_lines(s, f"//CLIENT TB1 v={VERSION} caps=CHAT,SYNC,Z")   # current client
        self.assertIn("//OK TB1 caps=CHAT,SYNC\r", t.take())   # Z only on radio
        type_lines(s, "//MLIST")
        rows = t.take().split("\r")[:-1]
        self.assertEqual(rows[-1], "//MEND 2 0")
        h = parse_header(rows[0][4:])                    # oldest first
        self.assertEqual((h["id"], h["type"], h["status"], h["from_call"], h["subject"]),
                         (self.a, "P", "N", "OE3TEC", "Hallo Gerhard"))
        self.assertGreater(h["created"], 1_700_000_000)
        type_lines(s, "//RUBRICS")
        self.assertEqual(t.take(), f"//RU ALL 1 {self.d}\r//RU WX 1 {self.e}\r//RUEND\r")
        type_lines(s, f"//BLIST ALL=0 WX={self.e}")
        out = t.take().split("\r")
        self.assertTrue(out[0].startswith(f"//M {self.d} B "))
        self.assertEqual(out[1], "//MEND 1 0")
        type_lines(s, "//BLIST ALL=x")
        self.assertEqual(t.take(), "//ERR blist\r")
        # page by page
        type_lines(s, "//MLIST max=1")
        out = t.take().split("\r")
        self.assertTrue(out[0].startswith(f"//M {self.a} "))
        self.assertEqual(out[1], "//MEND 1 1")
        type_lines(s, f"//MLIST after={self.a} max=1")
        out = t.take().split("\r")
        self.assertTrue(out[0].startswith(f"//M {self.b} "))
        self.assertEqual(out[1], "//MEND 1 0")
        type_lines(s, "//BLIST ALL=0 WX=0 max=1")
        self.assertTrue(t.take().endswith("//MEND 1 1\r"))

    def test_get_plain_and_foreign(self):
        s, t = client(self.app)
        type_lines(s, f"//GET {self.a} {self.c} 999")
        self.assertEqual(t.take(), f"//MSG {self.a} 2\rText 1\rZeile 2\r"
                                   f"//NOMSG {self.c}\r//NOMSG 999\r//GEND\r")
        self.assertEqual(self.app.service.store.get(self.a).status, "N")   # GET is not reading
        type_lines(s, "//GET " + " ".join(["1"] * 21))
        self.assertEqual(t.take(), "//ERR get\r//GEND\r")

    def test_get_compressed_on_radio(self):
        s, t = client(self.app, radio=True)
        type_lines(s, f"//GET {self.e} {self.a}")
        raw = t.raw
        head, _, rest = raw.partition(b"\r")
        _, msg_id, n = head.decode().split()
        self.assertEqual(int(msg_id), self.e)
        data, rest = rest[:int(n)], rest[int(n):]
        self.assertLess(len(data), len(LONG) / 2)
        self.assertEqual(lzhuf.decompress_b1(data).decode(), LONG)
        # short text: not worth compressing
        self.assertEqual(rest, f"//MSG {self.a} 2\rText 1\rZeile 2\r//GEND\r".encode())

    def test_part(self):
        s, t = client(self.app, radio=True)
        whole = b""
        while True:
            type_lines(s, f"//PART {self.e} {len(whole)} 50")
            head, _, rest = t.raw.partition(b"\r")
            t.raw = b""
            _, msg_id, kind, off, total, n = head.decode().split()
            self.assertEqual((int(msg_id), kind, int(off), len(rest)), (self.e, "Z", len(whole),
                                                                         int(n)))
            whole += rest
            if len(whole) >= int(total):
                break
        self.assertEqual(lzhuf.decompress_b1(whole).decode(), LONG)
        type_lines(s, f"//PART {self.c} 0 50")             # not mine
        self.assertEqual(t.raw, f"//NOMSG {self.c}\r".encode())
        s2, t2 = client(self.app)                          # telnet: no pieces
        type_lines(s2, f"//PART {self.e} 0 50")
        self.assertEqual(t2.take(), "//ERR part\r")

    def test_send_kill_read(self):
        s, t = client(self.app)
        type_lines(s, "//SEND P OE3TEC@OE3GAS-1 2 mid=abcdef123456", "Betreff hier",
                   "Erste Zeile", "")
        out = t.take()
        self.assertTrue(out.startswith("//SENT "), out)
        new = int(out.split()[1])
        m = self.app.service.store.get(new)
        self.assertEqual((m.from_call, m.to_call, m.subject, m.body), ("OE3GAS", "OE3TEC",
                                                                       "Betreff hier",
                                                                       "Erste Zeile\n"))
        # the same message again (answer was lost): old number, not stored twice
        type_lines(s, "//SEND P OE3TEC 2 mid=abcdef123456", "Betreff hier", "Erste Zeile", "")
        self.assertEqual(t.take(), f"//SENT {new}\r")
        # errors: the text lines are still taken away
        type_lines(s, "//SEND P NOCALL!! 1", "x", "y")
        self.assertIn("//ERR send invalid", t.take())
        self.assertEqual(s.state, State.COMMAND)
        type_lines(s, "//SEND B WX 0", "Bulletin vom Client")
        self.assertTrue(t.take().startswith("//SENT "))
        # read and kill
        type_lines(s, f"//READ {self.a}")
        self.assertEqual(t.take(), "//REND\r")
        self.assertEqual(self.app.service.store.get(self.a).status, "Y")
        type_lines(s, f"//KILL {self.a} {self.c} {self.d} 999")
        self.assertEqual(t.take(), f"//K {self.a} ok\r//K {self.c} not_found\r"
                                   f"//K {self.d} not_allowed\r//K 999 ok\r//KEND\r")
        self.assertIsNone(self.app.service.store.get(self.a))
        self.assertIsNotNone(self.app.service.store.get(self.c))

    def test_send_inside_board(self):
        s, t = client(self.app)
        type_lines(s, "C 1")
        t.take()
        type_lines(s, "//SEND P OE3TEC 1", "Aus dem Chat", "Text")
        self.assertTrue(t.take().startswith("//SENT "))
        self.assertEqual(s.state, State.CHAT)

    def test_no_sync_cap(self):
        s, t = client(self.app, caps="CHAT")
        type_lines(s, "//MLIST")
        self.assertEqual(t.take(), "//ERR MLIST needs SYNC\r")


class SplitterTests(unittest.TestCase):
    def test_binary_after_line(self):
        got = []
        sp = LineSplitter(None)
        sp.on_line = lambda line: (got.append(line),
                                   line.startswith("//ZMSG") and sp.expect(4, got.append))
        data = b"//ZMSG 1 4\r\n\r\x00\xffnext\r"       # binary starts with LF and CR
        for i in range(len(data)):                       # byte by byte, like small frames
            sp.feed(data[i:i + 1])
        self.assertEqual(got, ["//ZMSG 1 4", b"\n\r\x00\xff", "next"])


class StoreTests(unittest.TestCase):
    def test_folders_read_delete_outbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = MailStore(Path(tmp) / "m.db", "OE3GAS-5")
            self.assertTrue(st.unused)
            self.assertEqual(st.summary()["inbox"], 0)
            hdr = dict(type="P", status="N", fwd="", size=3, at_addr="", bid="", created=1)
            self.assertTrue(st.upsert_header({**hdr, "id": 1, "from_call": "OE3TEC",
                                              "to_call": "OE3GAS", "subject": "a"}))
            st.upsert_header({**hdr, "id": 2, "from_call": "OE3GAS", "to_call": "OE3TEC",
                              "subject": "b", "status": "Y"})
            st.upsert_header({**hdr, "id": 3, "type": "B", "from_call": "OE3TEC",
                              "to_call": "ALL", "subject": "c"})
            self.assertEqual([m["id"] for m in st.folder("inbox")], [1])
            self.assertEqual([m["id"] for m in st.folder("sent")], [2])
            self.assertEqual([m["id"] for m in st.folder("b:ALL")], [3])
            self.assertEqual(st.missing_bodies(), [1, 2, 3])
            st.set_body(1, "hallo")
            self.assertFalse(st.upsert_header({**hdr, "id": 1, "from_call": "OE3TEC",
                                               "to_call": "OE3GAS", "subject": "a"}))
            self.assertEqual(st.summary()["unread"], 1)
            st.open(1)
            self.assertEqual((st.summary()["unread"], st.todo("read")), (0, [1]))
            st.delete(1)
            self.assertEqual((st.folder("inbox"), st.todo("kill")), ([], [1]))
            st.delete(3)                                   # bulletin: only here
            self.assertEqual(st.max_bulletin("ALL"), 3)
            oid = st.save_out(None, "P", "OE3TEC", "s", "b")
            self.assertEqual(st.save_out(oid, "P", "OE3TEC", "s2", "b2"), oid)
            self.assertEqual(st.outbox()[0]["subject"], "s2")
            st.subscribe("WX", True)
            self.assertEqual([r["name"] for r in st.summary()["rubrics"] if r["sub"]], ["WX"])
            st.close()


class EndToEndTests(unittest.TestCase):
    def test_sync_over_radio(self):
        async def scenario():
            dw = FakeDirewolf()
            port = await dw.start()
            app = chat_app()
            app.cfg.direwolf = dataclasses.replace(app.cfg.direwolf, agw_port=port,
                                                   reconnect_sec=1)
            adapter = tb_agw.AgwAdapter(app)
            app.agw = adapter
            t1 = asyncio.create_task(adapter.run())
            await asyncio.wait_for(adapter.connected.wait(), 5)
            a = mail(app, "OE3TEC", "OE3GAS", "Lang", LONG)
            mail(app, "OE3TEC", "OE3GAS", "Kurz", "kurz")
            rnd = random.Random(7)                         # hardly compressible: in pieces
            noise = "\n".join(" ".join(f"{rnd.randrange(16**8):08x}" for _ in range(8))
                              for _ in range(40))
            big = mail(app, "OE1ABC", "OE3GAS", "Gross", noise)
            for i in range(4):                             # more headers than one page
                mail(app, "OE3TEC", "OE3GAS", f"Nr {i}", f"Text {i}")
            mail(app, "OE3TEC", "WX", "Wetter", LONG, type="B")
            mail(app, "OE3TEC", "ALL", "Nicht abonniert", type="B")
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp, agw_port=port, sync_chunk=256,
                                             sync_pause=0.05))
                box = core.mailbox
                t2 = asyncio.create_task(core.run())
                await asyncio.wait_for(core.link.agw_up.wait(), 5)
                box.subscribe("WX", True)
                box.save_out(None, "P", "OE3TEC", "Vom Client", "Hallo Tec\n73")
                # offline: the sync connects, does its work and disconnects again
                self.assertTrue(core.sync.start("mail"))
                self.assertFalse(core.sync.start("bulletins"))       # one at a time
                await until(lambda: not core.sync.running, 30)
                self.assertEqual(core.sync.status["error"], "")
                self.assertIn("*** client mode, caps: CHAT,SYNC,UI,Z", core.console)
                await until(lambda: core.state == "offline")
                inbox = box.folder("inbox")
                self.assertEqual([m["subject"] for m in inbox],
                                 ["Nr 3", "Nr 2", "Nr 1", "Nr 0", "Gross", "Kurz", "Lang"])
                self.assertEqual(box.message(a)["body"], LONG)
                self.assertEqual(box.message(big)["body"], noise)
                self.assertTrue(any(x.startswith(f"> //PART {big} ") for x in core.console))
                self.assertGreater(core.sync.status["saved"], 1000)       # compression
                self.assertEqual(box.folder("b:WX"), [])          # bulletins: own sync
                self.assertTrue(box.summary()["last_mail"])
                self.assertFalse(box.summary()["last_bulletins"])
                self.assertTrue(core.sync.start("bulletins"))
                await until(lambda: not core.sync.running, 30)
                self.assertEqual(core.sync.status["error"], "")
                self.assertEqual([m["subject"] for m in box.folder("b:WX")], ["Wetter"])
                self.assertEqual(box.folder("b:ALL"), [])
                sent = [m for m in app.service.store.list_messages() if m.subject == "Vom Client"]
                self.assertEqual(sent[0].body, "Hallo Tec\n73")
                self.assertEqual(box.folder("outbox"), [])
                self.assertEqual(box.folder("sent")[0]["id"], sent[0].id)
                names = {r["name"]: r for r in box.summary()["rubrics"]}
                self.assertEqual((names["ALL"]["server"], names["WX"]["local"]), (1, 1))
                # read and delete here, then sync: the TinyBox follows
                box.open(a)
                kurz = inbox[5]["id"]
                box.delete(kurz)
                core.sync.start()
                await until(lambda: not core.sync.running, 30)
                self.assertEqual(core.sync.status["error"], "")
                self.assertEqual(core.sync.status["total"], 0)       # nothing fetched again
                self.assertEqual(app.service.store.get(a).status, "Y")
                self.assertIsNone(app.service.store.get(kurz))
                self.assertEqual(box.todo("kill") + box.todo("read"), [])
                box.close()
                t2.cancel()
            t1.cancel()
            dw.server.close()
        asyncio.run(scenario())

    def test_pause_and_busy_channel(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp, sync_pause=0.2))
                sent = []
                core.link.send_line = lambda line: sent.append((line, time.monotonic()))
                core.state = "online"
                syncer = core.sync
                with mock.patch.object(sync, "BUSY_QUIET_SEC", 0.3):
                    await syncer._send("//MLIST")               # first request: at once
                    t0 = time.monotonic()
                    await syncer._send("//RUBRICS")              # pause
                    self.assertGreaterEqual(time.monotonic() - t0, 0.19)
                    core.channel_busy_at = time.monotonic() + 0.2   # others still talking
                    t0 = time.monotonic()
                    await syncer._send("//GET 1")
                    self.assertGreaterEqual(time.monotonic() - t0, 0.45)
                self.assertEqual([x[0] for x in sent], ["//MLIST", "//RUBRICS", "//GET 1"])
                core.mailbox.close()
        asyncio.run(scenario())

    def test_sync_fails_cleanly_without_direwolf(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp, agw_port=1))
                core.sync.start()
                await until(lambda: not core.sync.running, 10)
                self.assertIn("not connected", core.sync.status["error"])
                core.mailbox.close()
        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
