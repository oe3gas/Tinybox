"""CR86: files in a chat board - upload once to the TinyBox, the chat line carries
only the reference, everybody fetches it (and the 16-hex hashes from CR96)."""

from __future__ import annotations

import hashlib
import unittest

from prcore import chatimg
from tinybox.config import ChatBoard, ChatCfg
from tinybox.session import Session

from tests.test_chat import chat_app
from tests.test_chatimg import RadioTransport
from tests.test_tinybox import type_lines

DATA = b"Hallo, das ist eine Testdatei.\n" * 20


def h16(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def file_app():
    app = chat_app()
    app.cfg.chat = ChatCfg(enabled=True, history_lines=5, max_line=200, boards=[
        ChatBoard("TREFF", 7 * 24, "Meeting point"),
        ChatBoard("TECH", 30 * 24, "No files", nofile=True),
        ChatBoard("RUNDE", 0, "Live only"),
    ])
    return app


def client(app, call="OE3GAS", board="1", caps="CHAT,SYNC,Z,IMG,BFILE"):
    t = RadioTransport()
    s = Session(call, app.service, app.cfg, t, origin="radio")
    s.start()
    type_lines(s, f"//CLIENT TB1 v=2026.11.10 caps={caps}", f"C {board}")
    return s, t


class BoardFiles(unittest.TestCase):
    def setUp(self):
        self.app = file_app()

    def upload(self, s, t, data=DATA, name="notes.txt"):
        h = h16(data)
        t.take()
        type_lines(s, f"//FPUT {h} r {len(data)}")
        self.assertEqual(t.take(), f"//FGO {h} 0\r")
        s.feed_raw(data[:50])
        s.feed_raw(data[50:])
        self.assertEqual(t.take(), f"//FOK {h}\r")
        return h, f"~%{h} {len(data)} {len(data)} {name}"

    def test_upload_line_fetch_terminal(self):
        s, t = client(self.app)
        self.assertIn(" file=4000", t.take())              # //IN: 16 KB allowed here
        h, line = self.upload(s, t)
        type_lines(s, line)
        self.assertIn(line, t.take())
        # another client fetches it
        s2, t2 = client(self.app, "OE3TEC")
        t2.take()
        type_lines(s2, f"//FGET {h}")
        self.assertEqual(t2.take(), f"//BF {h} r 0 {len(DATA)}\r")
        self.assertEqual(t2.raw, DATA)
        type_lines(s2, f"//FGET {h} 100")                     # going on after a break
        self.assertTrue(t2.take().startswith(f"//BF {h} r 100 "))
        type_lines(s2, "//FGET 0000000000000000")
        self.assertEqual(t2.take(), "//NOBFILE 0000000000000000\r")
        self.assertEqual(chatimg.terminal_text(line),
                         "[File notes.txt 0.6 KB - TinyBox client only]")

    def test_refused(self):
        s, t = client(self.app, board="2")                    # TECH: nofile
        self.assertNotIn(" file=", t.take())
        type_lines(s, f"//FPUT {h16(DATA)} r {len(DATA)}")
        self.assertEqual(t.take(), "//ERR file no_files\r")
        s, t = client(self.app)
        t.take()
        type_lines(s, f"//FPUT {h16(DATA)} r 99999")
        self.assertEqual(t.take(), "//ERR file too_large 16384\r")
        h, _ = self.upload(s, t)
        type_lines(s, f"~%{h} {len(DATA)} {len(DATA)} evil.exe")   # a program by its name
        self.assertIn("//ERR file program", t.take())
        type_lines(s, f"~%{'1' * 16} 10 10 ghost.txt")             # never uploaded
        self.assertIn("//ERR file unknown", t.take())

    def test_upload_belongs_to_its_station(self):
        s, t = client(self.app)
        t.take()
        h = h16(DATA)
        type_lines(s, f"//FPUT {h} r {len(DATA)}")
        t.take()
        s.feed_raw(DATA[:10])
        s2, t2 = client(self.app, "OE3TEC")
        t2.take()
        type_lines(s2, f"//FPUT {h} r {len(DATA)}")
        self.assertEqual(t2.take(), "//ERR file busy\r")

    def test_no_files_for_telnet_or_without_cap(self):
        s, t = client(self.app, caps="CHAT")
        t.take()
        type_lines(s, f"//FPUT {h16(DATA)} r 10")
        self.assertIn("needs BFILE", t.take())

    def test_purge_keeps_referenced(self):
        s, t = client(self.app)
        h, line = self.upload(s, t)
        type_lines(s, line)
        h2, _ = self.upload(s, t, b"other file" * 10, "x.txt")
        self.assertEqual(self.app.store.file_purge("2999-01-01T00:00:00Z"), 1)
        self.assertIsNotNone(self.app.store.file_get(h))
        self.assertIsNone(self.app.store.file_get(h2))


class Hash16(unittest.TestCase):
    def test_hashes_are_16_hex(self):
        self.assertEqual(len(chatimg.image_hash(b"x")), 16)
        self.assertTrue(chatimg.HASH_RE.match("0123456789abcdef"))
        self.assertFalse(chatimg.HASH_RE.match("012345"))


class Config(unittest.TestCase):
    def test_nofile_and_noimg_in_any_order(self):
        import tempfile
        from pathlib import Path

        from tinybox import config

        from tests.test_tinybox import ROOT
        base = (ROOT / "tinybox.conf.example").read_text(encoding="utf-8")
        start, end = base.index("[chat_boards]"), base.index("[", base.index("[chat_boards]") + 5)
        text = base[:start] + ("[chat_boards]\nTREFF = 7d nofile noimg Meeting point\n"
                               "TECH = 30d noimg Tech\n\n") + base[end:]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "tinybox.conf"
            p.write_text(text, encoding="utf-8")
            cfg = config.load(p)
        b = cfg.chat.board("TREFF")
        self.assertEqual((b.noimg, b.nofile, b.description), (True, True, "Meeting point"))
        self.assertTrue(cfg.chat.board("TECH").files)
        self.assertEqual(cfg.chat.file_max, 16384)


if __name__ == "__main__":
    unittest.main()


class OverTheRadio(unittest.TestCase):
    """The client puts a file into the board, the line carries the reference, a
    tap fetches it back (LZHUF, hash checked); programs never leave the client."""

    def test_client_to_box_and_back(self):
        import asyncio
        import dataclasses
        import tempfile

        from tbclient.core import ClientCore
        from tinybox.adapters import agw as tb_agw

        from tests.test_tbclient import FakeDirewolf, client_cfg, until
        from tests.test_tinybox import login

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
            term, tt = login(app, "OE3XYZ")
            type_lines(term, "C TREFF")
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp, agw_port=port))
                t2 = asyncio.create_task(core.run())
                await asyncio.wait_for(core.link.agw_up.wait(), 5)
                await core.connect()
                await until(lambda: core.boards, 10)
                self.assertIn("BFILE", core.caps)
                core.join(1)
                await until(lambda: core.board and core.board.get("file") == 16384)
                self.assertIsNone(core.send_board_file("tool.exe", b"MZ" + DATA, ""))
                h = core.send_board_file("notes.txt", DATA, "")
                self.assertEqual(h, h16(DATA))
                await until(lambda: core.bfiles.upload["state"] == "done", 15)
                await until(lambda: any((m.get("text") or "").startswith(f"~%{h} ")
                                        for m in core.messages), 10)
                self.assertIn("[File notes.txt 0.6 KB - TinyBox client only]", tt.buf)
                how, blob = app.store.file_get(h)
                self.assertEqual(how, "z")                       # LZHUF made it smaller
                self.assertLess(len(blob), len(DATA))
                core.files.path(h).unlink()
                self.assertTrue(core.fetch_board_file(h, "notes.txt"))
                await until(lambda: core.files.has(h), 15)
                self.assertEqual(core.files.get(h), DATA)
                self.assertEqual(core.snapshot()["bfiles"]["have"], [h])
                core.disconnect()
                await until(lambda: core.state == "offline")
                t2.cancel()
            t1.cancel()
            dw.server.close()
        asyncio.run(scenario())


class Console(unittest.TestCase):
    def test_files_command(self):
        from tinybox.adapters.sysop import MonitorFilter, SysopConsole
        app = file_app()
        app.store.file_put("a" * 16, "r", b"xyz", "OE3TEC")
        out = []
        c = SysopConsole(app, MonitorFilter(True), out.append)
        c.handle_line("FILES")
        self.assertIn("aaaaaaaaaaaaaaaa", "".join(out))
        c.handle_line("FILES DEL " + "a" * 16)
        self.assertIsNone(app.store.file_get("a" * 16))
