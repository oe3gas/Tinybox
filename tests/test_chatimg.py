"""Small images in the chat (CR12): upload and download in one block each,
the compact reference, terminal text, board settings, purge."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from tinybox import chatimg, config
from tinybox.adapters import agw
from tinybox.config import ChatBoard, ChatCfg
from tinybox.session import Session
from tests.test_chat import chat_app
from tests.test_tinybox import ROOT, FakeTransport, login, type_lines

WEBP = b"RIFF\x20\x00\x00\x00WEBPVP8 " + bytes(range(256)) * 3     # looks like WebP
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 300
BH32 = "BEHV6nWB2yk8pyo0"             # 3x2 blurhash: 16 characters ('B' = 11 = 3x2)
BH33 = "KEHV6nWB2yk8pyo0adR*.7"       # 3x3: 22 ('K' = 20 = 3x3)


def h6(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:6]


def ref(data: bytes, bh: str = BH32) -> str:
    return f"~#{h6(data)}{chatimg.size_code(len(data))}{bh}"


class RadioTransport(FakeTransport):
    """A transport with write_bytes (as the AGW adapter): caps Z and IMG."""

    def __init__(self) -> None:
        super().__init__()
        self.raw = b""

    def write_bytes(self, data: bytes) -> None:
        self.raw += data


def img_app(**chat):
    app = chat_app()
    app.cfg.chat = ChatCfg(enabled=True, history_lines=5, max_line=200, boards=[
        ChatBoard("TREFF", 7 * 24, "Meeting point"),
        ChatBoard("TECH", 30 * 24, "No pictures", noimg=True),
        ChatBoard("RUNDE", 0, "Live only"),
    ], **chat)
    return app


def client(app, call="OE3GAS", board="1"):
    t = RadioTransport()
    s = Session(call, app.service, app.cfg, t, origin="radio")
    s.start()
    type_lines(s, "//CLIENT TB1 v=2026.10.12.6 caps=CHAT,SYNC,Z,IMG", f"C {board}")
    t.take()
    return s, t


def upload(s, t, data: bytes) -> str:
    """The way the client does it: //IMGPUT, //IMGGO, then the bytes at once."""
    h = h6(data)
    type_lines(s, f"//IMGPUT {h} {len(data)}")
    out = t.take()      # //IMGGO, then the event the whole board gets (CR30)
    assert out.startswith(f"//IMGGO {h} 0\r"), out
    s.feed_raw(data[:100])             # arrives in whatever pieces Direwolf makes
    assert t.take() == ""
    s.feed_raw(data[100:])
    out = t.take()
    assert out == f"//IMGOK {h}\r", out
    return h


class ConfigTests(unittest.TestCase):
    def test_sizes_and_noimg(self):
        self.assertEqual(config.parse_size("chat", "image_max", "8k"), 8192)
        self.assertEqual(config.parse_size("chat", "image_max", "4096"), 4096)
        self.assertEqual(config.parse_size("chat", "image_max", "off"), 0)
        with self.assertRaises(config.ConfigError):
            config.parse_size("chat", "image_max", "8m")
        cfg = config.load(ROOT / "tinybox.conf.example")
        self.assertEqual(cfg.chat.image_max, 8192)
        b = ChatBoard("X", 24, "desc", noimg=True)
        self.assertFalse(b.images)
        self.assertTrue(ChatBoard("Y", 24).images)
        self.assertFalse(ChatBoard("Z", 0).images)            # live: never
        self.assertEqual(cfg.chat.image_limit(ChatBoard("Y", 24)), 8192)
        self.assertEqual(cfg.chat.image_limit(b), 0)

    def test_board_line_with_noimg(self):
        base = (ROOT / "tinybox.conf.example").read_text(encoding="utf-8")
        text = base.replace("TECH  = 30d   Technical questions",
                            "TECH  = 30d noimg Technical questions")
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "tinybox.conf"
            p.write_text(text, encoding="utf-8")
            cfg = config.load(p)
        tech = cfg.chat.board("TECH")
        self.assertTrue(tech.noimg)
        self.assertEqual(tech.description, "Technical questions")
        self.assertFalse(cfg.chat.board("TREFF").noimg)


class ReferenceTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(chatimg.size_code(5120), "50")
        self.assertEqual(chatimg.size_code(5121), "51")
        self.assertEqual(chatimg.size_code(100000), "ff")
        self.assertEqual(chatimg.blurhash_len("B"), 16)       # 3x2
        self.assertEqual(chatimg.blurhash_len("K"), 22)       # 3x3
        self.assertEqual(chatimg.blurhash_len("L"), 28)       # 4x3 (the usual one)
        self.assertEqual(chatimg.blurhash_len("A"), 12)       # 2x2
        self.assertEqual(chatimg.blurhash_len(" "), 0)
        r = chatimg.parse_ref(f"~#a1b2c350{BH32} Blick vom Berg")
        self.assertEqual(r, ("a1b2c3", 5120, BH32, 0, 26))
        r = chatimg.parse_ref(f"~^OE3TEC 1402 ~#a1b2c350{BH33}")
        self.assertEqual(r[:3], ("a1b2c3", 5120, BH33))
        self.assertIsNone(chatimg.parse_ref("~#a1b2c350BEHV"))          # too short
        self.assertIsNone(chatimg.parse_ref(f"~#a1b2c350{BH32}x"))      # glued text
        self.assertIsNone(chatimg.parse_ref("plain ~# text"))
        self.assertIsNone(chatimg.parse_ref(f"x~#a1b2c350{BH32}"))       # not at a start

    def test_terminal_text(self):
        self.assertEqual(chatimg.terminal_text(f"~#a1b2c350{BH32} Blick vom Berg"),
                         "[Image 5.0 KB - TinyBox client only] Blick vom Berg")
        self.assertEqual(chatimg.terminal_text(f"~^OE3TEC 1402 ~#a1b2c350{BH33}"),
                         "~^OE3TEC 1402 [Image 5.0 KB - TinyBox client only]")
        self.assertEqual(chatimg.terminal_text("plain ~# text"), "plain ~# text")

    def test_types(self):
        self.assertEqual(chatimg.image_type(WEBP), "webp")
        self.assertEqual(chatimg.image_type(JPEG), "jpeg")
        self.assertIsNone(chatimg.image_type(b"GIF89a..."))


class UploadTests(unittest.TestCase):
    def setUp(self):
        self.app = img_app()

    def test_caps(self):
        s, t = login(self.app, "OE3ABC")            # telnet: no raw bytes -> no IMG
        type_lines(s, "//CLIENT TB1 caps=CHAT,IMG")
        self.assertIn("caps=CHAT ", t.take() + " ")
        type_lines(s, "//IMGPUT 012345 100")
        self.assertIn("//ERR IMGPUT needs IMG", t.take())
        s, t = client(self.app)
        self.assertIn("IMG", s.client.caps)
        self.app.cfg.chat.image_max = 0
        s2, t2 = client(self.app, "OE3TEC")
        self.assertNotIn("IMG", s2.client.caps)

    def test_in_line_tells_the_limit(self):
        t = RadioTransport()
        s = Session("OE3GAS", self.app.service, self.app.cfg, t, origin="radio")
        s.start()
        type_lines(s, "//CLIENT TB1 caps=CHAT,IMG")
        t.take()
        type_lines(s, "C TREFF")
        self.assertTrue(t.take().split("\r")[0].endswith(" img"))
        type_lines(s, "/J TECH")
        self.assertNotIn("img", t.take().split("\r")[0])
        type_lines(s, "/J RUNDE")
        self.assertNotIn("img", t.take().split("\r")[0])
        self.app.cfg.chat.image_max = 4096
        type_lines(s, "/J TREFF")
        self.assertTrue(t.take().split("\r")[0].endswith(" img=1000"))

    def test_upload_download_and_terminal(self):
        term, tt = login(self.app, "OE3XYZ")
        type_lines(term, "C TREFF")
        tt.take()
        s, t = client(self.app)
        tt.take()
        h = upload(s, t, WEBP)
        self.assertEqual(self.app.store.image_get(h), WEBP)
        self.assertEqual(self.app.store.image_size(h), len(WEBP))
        # the same picture again: already here
        type_lines(s, f"//IMGPUT {h} {len(WEBP)}")
        self.assertEqual(t.take(), f"//IMGOK {h}\r")
        # the chat line: the client gets it as it is, the terminal reads [Image ...]
        line = f"{ref(WEBP)} vom Berg"
        type_lines(s, line)
        self.assertIn(f"OE3GAS: {line}", t.take())
        self.assertIn("OE3GAS: [Image 0.8 KB - TinyBox client only] vom Berg", tt.take())
        # terminal history shows the same text
        type_lines(term, "/H 5")
        self.assertIn("[Image", tt.take())
        self.assertNotIn("~#", tt.buf)
        # download: one block, or the rest from an offset
        type_lines(s, f"//IMG {h}")
        self.assertEqual(t.take(), f"//I {h} 0 {len(WEBP)}\r")
        self.assertEqual(t.raw, WEBP)
        t.raw = b""
        type_lines(s, f"//IMG {h} 100")
        self.assertEqual(t.take(), f"//I {h} 100 {len(WEBP)}\r")
        self.assertEqual(t.raw, WEBP[100:])
        type_lines(s, "//IMG 000000 0")
        self.assertEqual(t.take(), "//NOIMG 000000\r")
        # react to the image line: the terminal sees [Image ...] as target too
        type_lines(term, "/R 3 :+1")
        self.assertNotIn("~#", tt.take())

    def test_resume_bad_hash_bad_type_too_large(self):
        s, t = client(self.app)
        h = h6(WEBP)
        type_lines(s, f"//IMGPUT {h} {len(WEBP)}")
        t.take()
        s.feed_raw(WEBP[:200])
        self.assertEqual(t.take(), "")
        # the link breaks, a new session goes on at byte 200
        s.end(lost=True)
        s, t = client(self.app)
        type_lines(s, f"//IMGPUT {h} {len(WEBP)}")
        self.assertTrue(t.take().startswith(f"//IMGGO {h} 200\r"))
        s.feed_raw(WEBP[200:])
        self.assertEqual(t.take(), f"//IMGOK {h}\r")
        # wrong hash
        type_lines(s, f"//IMGPUT 0bad00 {len(JPEG)}")
        t.take()
        s.feed_raw(JPEG)
        self.assertEqual(t.take(), "//ERR img bad_hash\r")
        # not an image
        gif = b"GIF89a" + b"\x00" * 100
        type_lines(s, f"//IMGPUT {h6(gif)} {len(gif)}")
        t.take()
        s.feed_raw(gif)
        self.assertEqual(t.take(), "//ERR img bad_type\r")
        self.assertIsNone(self.app.store.image_size(h6(gif)))
        self.assertEqual(s.raw_need, 0)
        # too large
        type_lines(s, f"//IMGPUT {h6(gif)} 9000")
        self.assertEqual(t.take(), "//ERR img too_large 8192\r")

    def test_boards_without_images(self):
        s, t = client(self.app, board="TECH")
        type_lines(s, f"//IMGPUT {h6(WEBP)} {len(WEBP)}")
        self.assertEqual(t.take(), "//ERR img no_images\r")
        type_lines(s, ref(WEBP))
        self.assertEqual(t.take(), "//ERR img no_images\r")
        s2, t2 = client(self.app, "OE3TEC", board="RUNDE")
        type_lines(s2, f"//IMGPUT {h6(WEBP)} {len(WEBP)}")
        self.assertEqual(t2.take(), "//ERR img no_images\r")
        # a reference to an image that was never uploaded
        s3, t3 = client(self.app, "OE1ABC", board="TREFF")
        type_lines(s3, f"~#01234550{BH32}")
        self.assertEqual(t3.take(), "//ERR img unknown\r")
        # outside a board: download works, upload not
        type_lines(s3, "/Q")
        t3.take()
        type_lines(s3, f"//IMGPUT {h6(WEBP)} {len(WEBP)}")
        self.assertEqual(t3.take(), "//ERR img no_images\r")

    def test_purge_keeps_referenced_images(self):
        s, t = client(self.app)
        h = upload(s, t, WEBP)
        h2 = upload(s, t, JPEG)
        type_lines(s, ref(WEBP))
        t.take()
        store = self.app.store
        # fresh uploads survive even without a line
        self.assertEqual(store.image_purge("2000-01-01T00:00:00Z"), 0)
        # older: only the referenced one stays
        self.assertEqual(store.image_purge("2999-01-01T00:00:00Z"), 1)
        self.assertIsNotNone(store.image_get(h))
        self.assertIsNone(store.image_get(h2))
        self.assertEqual(self.app.service.chat.purge(), 0)


class AgwRawTests(unittest.TestCase):
    """The AGW adapter hands the announced bytes to the session unsplit, even
    CR, LF and Ctrl-Z, and goes on with lines right after them."""

    def test_feed_raw_bytes(self):
        app = img_app()
        adapter = agw.AgwAdapter(app)
        conn = agw.AgwConnection(adapter, "OE3GAS")
        s = Session("OE3GAS", app.service, app.cfg, conn, origin="radio")
        conn.session = s
        s.start()
        conn.queue.clear()
        s.handle_line("//CLIENT TB1 caps=CHAT,IMG")
        s.handle_line("C TREFF")
        conn.queue.clear()
        data = b"RIFF\x20\x00\x00\x00WEBP\r\n\x1a\r\r\n" + bytes(range(256))
        h = h6(data)
        conn.feed(f"//IMGPUT {h} {len(data)}\r".encode())
        self.assertIn(f"//IMGGO {h} 0".encode(), b"".join(conn.queue))
        conn.queue.clear()
        # the bytes and the next line in one AGW frame, split anywhere
        stream = data + b"/W\r"
        conn.feed(stream[:30])
        conn.feed(stream[30:31])
        conn.feed(stream[31:])
        out = b"".join(conn.queue)
        self.assertIn(f"//IMGOK {h}".encode(), out)
        self.assertEqual(app.store.image_get(h), data)
        self.assertIn(b"Nobody else is here", out)            # /W was handled as a line
        self.assertEqual(s.raw_need, 0)


if __name__ == "__main__":
    unittest.main()


class RawStreamTests(unittest.TestCase):
    """What went wrong on the air on 12.10.2026: a line slipped into the byte
    stream, so the last image bytes were read as a chat line. The TinyBox side
    now has a time limit for the raw mode and drops binary chat lines."""

    def setUp(self):
        self.app = img_app()

    def test_timeout_keeps_what_came_and_resumes(self):
        s, t = client(self.app)
        h = h6(WEBP)
        type_lines(s, f"//IMGPUT {h} {len(WEBP)}")
        self.assertTrue(t.take().startswith(f"//IMGGO {h} 0\r"))
        s.feed_raw(WEBP[:300])
        self.assertGreater(s.raw_need, 0)
        self.assertFalse(s.raw_timeout(120, now=s.raw_since + 10))     # still fresh
        self.assertTrue(s.raw_timeout(120, now=s.raw_since + 121))
        self.assertEqual(s.raw_need, 0)
        self.assertEqual(t.take(), "//ERR img timeout 300\r")
        type_lines(s, "/W")                       # lines work again at once
        self.assertIn("here", t.take())
        type_lines(s, f"//IMGPUT {h} {len(WEBP)}")   # go on where it stopped
        self.assertTrue(t.take().startswith(f"//IMGGO {h} 300\r"))
        s.feed_raw(WEBP[300:])
        self.assertEqual(t.take(), f"//IMGOK {h}\r")
        self.assertEqual(self.app.store.image_get(h), WEBP)

    def test_binary_chat_line_is_dropped(self):
        from tinybox import chatcmd
        self.assertFalse(chatcmd.looks_binary("Servus :+1"))
        self.assertFalse(chatcmd.looks_binary("Gruß – schön!"))   # CP1252 dash
        self.assertTrue(chatcmd.looks_binary("wü\x00\x9c\x81ah"))
        self.assertTrue(chatcmd.looks_binary("ÕÙvi\x11õê"))
        term, tt = login(self.app, "OE3XYZ")
        type_lines(term, "C TREFF")
        s, t = client(self.app)
        tt.take(), t.take()
        type_lines(s, "ÕÙvi\x11õê}¹ÊÐn")      # rest of an image
        self.assertEqual(t.take(), "")            # nothing on the air, nothing stored
        self.assertEqual(tt.take(), "")
        self.assertEqual(self.app.store.chat_recent("TREFF", "2000-01-01T00:00:00Z", 10), [])
        type_lines(s, "Servus")                   # normal text still works
        self.assertIn("OE3GAS: Servus", t.take())


class UploadNoticeAndQuoteTests(unittest.TestCase):
    """CR30: the board learns about an upload. CR31: the comment reference is
    the event number, and terminals read the quoted line."""

    def setUp(self):
        self.app = img_app()

    def test_upload_event(self):
        term, tt = login(self.app, "OE3XYZ")
        type_lines(term, "C TREFF")
        other, ot = client(self.app, "OE1ABC")
        tt.take(), ot.take()
        s, t = client(self.app)
        tt.take(), ot.take(), t.take()
        type_lines(s, f"//IMGPUT {h6(WEBP)} {len(WEBP)}")
        # the uploader gets //IMGGO, everybody in the board the event
        self.assertIn(f"//IMGGO {h6(WEBP)} 0", t.take())
        self.assertIn(f"^OE3GAS {chatimg.size_code(len(WEBP))}", ot.take())
        self.assertIn("*** OE3GAS is sending a picture (0.8 KB)", tt.take())
        # not stored in the history
        self.assertEqual(self.app.store.chat_recent("TREFF", "2000-01-01T00:00:00Z", 10), [])

    def test_quote_is_resolved_for_terminals(self):
        term, tt = login(self.app, "OE3XYZ")
        type_lines(term, "C TREFF")
        s, t = client(self.app)
        tt.take()
        type_lines(s, "Wer ist heute QRV?")
        seq = t.take().split()[0].lstrip("#")           # the number of that event
        tt.take()
        type_lines(s, f"~^{seq} Ich bin QRV")
        self.assertIn('OE3GAS: [re OE3GAS: "Wer ist heute QRV?"] Ich bin QRV', tt.take())
        # clients get the raw reference
        self.assertIn(f"OE3GAS: ~^{seq} Ich bin QRV", t.buf)
        # an unknown number: the text still goes through
        type_lines(s, "~^FE spaet dran")
        self.assertIn("OE3GAS: [re #FE] spaet dran", tt.take())
        # a picture inside the quoted line stays readable
        t.take()
        h = upload(s, t, WEBP)
        tt.take()
        type_lines(s, f"{ref(WEBP)} schau mal")
        seq2 = t.take().split()[0].lstrip("#")
        tt.take()
        type_lines(s, f"~^{seq2} schoen!")
        out = tt.take()
        self.assertIn('[re OE3GAS: "[Image] schau mal"] schoen!', out)   # short in a quote
        self.assertNotIn("~#", out)
        # history: the numbers mean nothing any more
        type_lines(term, "/H 9")
        hist = tt.take()
        self.assertIn("[re #", hist)
        self.assertNotIn("~^", hist)
