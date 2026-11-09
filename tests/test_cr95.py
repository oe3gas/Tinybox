"""CR95 (PLANUNG 29.9, audit TB-11/TB-12/TB-22): any script in free text, but no
characters that trick a reader, a terminal, a mailbox or a logbook program."""

from __future__ import annotations

import io
import json
import logging
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from prcore import termcolor
from prcore.text import clean_text, defuse_lines, mixed_script, protocol_like, visible
from tinybox import logsetup
from tinybox.adapters import sysop

from tests.test_forward_module import fwd_app, gas

ROOT = Path(__file__).resolve().parent.parent


class CleanText(unittest.TestCase):
    def test_scripts_stay(self):
        for t in ("Grüße aus Hollabrunn", "Привет из Вены", "Καλημέρα", "مرحبا بك",
                  "こんにちは、世界", "नमस्ते", "שלום", "73 de OE3GAS – 5 °C, 12 €",
                  "a\tb\nc", "🙂 👍🏽", "👨\u200d👩\u200d👧", "❤\ufe0f"):
            self.assertEqual(clean_text(t), t, t)

    def test_tricks_go(self):
        self.assertEqual(clean_text("ab\u202edc"), "abdc")              # bidi override
        self.assertEqual(clean_text("a\u2066b\u2069"), "ab")             # isolates
        self.assertEqual(clean_text("in\u200bvis\ufeffible"), "invisible")
        self.assertEqual(clean_text("x\x1b[2Jy\x07z\x1a"), "x[2Jyz")      # ESC, BEL, Ctrl-Z
        self.assertEqual(clean_text("a\u2028b"), "ab")                   # line separator
        self.assertEqual(clean_text("p\ue000q"), "pq")                   # private use
        self.assertEqual(clean_text("a\u00a0b\u3000c"), "a b c")         # other spaces
        self.assertEqual(clean_text("l1\r\nl2\rl3"), "l1\nl2\nl3")

    def test_zalgo_and_joiners(self):
        zalgo = "e" + "\u0301" * 30                    # NFC makes the first one "é"
        self.assertEqual(clean_text(zalgo), "\u00e9" + "\u0301" * 3)
        self.assertEqual(clean_text("क्\u200dष"), "क्\u200dष")              # ZWJ between letters
        self.assertEqual(clean_text("\u200dabc\u200d"), "abc")           # at the edge: gone

    def test_nfc(self):
        self.assertEqual(clean_text("a\u0308"), "ä")

    def test_no_emoji_level(self):
        self.assertEqual(clean_text("ok 🙂", emoji=False), "ok ")


class Defuse(unittest.TestCase):
    def test_protocol_lines(self):
        for ln in ("/EX", "/ex", "***", "R:261109/1200 @:OE3XTC", "F>", "FB P A B C 1_X 5",
                   "FS +", "FF", "FQ", "; null", "//FGET abc", "／ＥＸ", "ｒ:x"):
            self.assertTrue(protocol_like(ln), ln)
            self.assertEqual(defuse_lines(ln), " " + ln)

    def test_ordinary_lines(self):
        text = "Hallo,\nFrage: wie geht's?\n# hashtag\nFBB ist fein\n -- 73"
        self.assertEqual(defuse_lines(text), text)


class Visible(unittest.TestCase):
    def test_terminal_controls(self):
        self.assertEqual(visible("a\x1b[2Jb"), "a\\x1b[2Jb")
        osc52 = "\x1b]52;c;ZXZpbA==\x07"
        self.assertNotIn("\x1b", visible(osc52))
        self.assertEqual(visible("x\u202ey"), "x\\u202ey")
        self.assertEqual(visible("c1\x9b31m"), "c1\\x9b31m")

    def test_text_stays(self):
        for t in ("OE3GAS: Grüße", "Привет", "مرحبا", "two\nlines\tok"):
            self.assertEqual(visible(t), t)

    def test_console_formatter(self):
        f = termcolor.ConsoleFormatter("[tinyb]", color=True)
        rec = logging.LogRecord("x", logging.INFO, "", 0, "< %s", ("\x1b]0;pwned\x07hi",), None)
        out = f.format(rec)
        self.assertNotIn("\x1b]0", out)
        self.assertIn("\\x1b]0;pwned\\x07hi", out)

    def test_log_file_formatter(self):
        rec = logging.LogRecord("tinybox.monitor", logging.INFO, "", 0, "< %s",
                                ("\x1b[2J\u202e",), None)
        out = logsetup.Formatter().format(rec)
        self.assertNotIn("\x1b", out)
        self.assertIn("\\x1b[2J\\u202e", out)

    def test_sysop_console(self):
        buf = io.StringIO()
        with mock.patch.object(sysop.sys, "stdout", buf):
            sysop._stdout_write("Subj: \x1b[2Jboom\r\n")
        self.assertEqual(buf.getvalue(), "Subj: \\x1b[2Jboom\r\n")


class MixedScript(unittest.TestCase):
    def test(self):
        self.assertTrue(mixed_script("\u041eE3GAS"))       # Cyrillic O + Latin
        self.assertTrue(mixed_script("pаypal"))            # Cyrillic a
        self.assertFalse(mixed_script("OE3GAS"))
        self.assertFalse(mixed_script("Москва"))
        self.assertFalse(mixed_script("Grüße"))


class Stored(unittest.TestCase):
    def setUp(self):
        self.app = fwd_app(gas())

    def test_local_mail(self):
        msg_id = self.app.service.create(
            from_call="OE1ABC", to_call="OE3GAS", type="P", subject="Hi\u202e\x1b[31m",
            body="Text\n/EX\nR:261109/1200 @:FAKE\n//FGET 1\nGrüße", origin="telnet")
        m = self.app.store.get(msg_id)
        self.assertEqual(m.subject, "Hi[31m")
        self.assertEqual(m.body, "Text\n /EX\n R:261109/1200 @:FAKE\n //FGET 1\nGrüße")

    def test_forwarded_mail_not_defused(self):
        msg_id = self.app.service.create(
            from_call="OE1ABC", to_call="ALL", type="B", subject="x", body="; a note\nok",
            origin="forward", at_addr="WW", bid="5_OE3GAS")
        self.assertEqual(self.app.store.get(msg_id).body, "; a note\nok")


class Adif(unittest.TestCase):                                    # TB-22
    def test_fields(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        cases = [["CALL", "OE3GAS"], ["GRIDSQUARE", "JN88ef"],
                 ["GRIDSQUARE", "ÄÄÄÄ<CALL:5>EVIL1"], ["NAME", "Jürgen"], ["QTH", "Wien <x>"],
                 ["GRIDSQUARE", "-"]]
        out = subprocess.run([node, str(ROOT / "tests" / "fixtures" / "adif.js"),
                              str(ROOT / "tbclient" / "web" / "app.js"), json.dumps(cases)],
                             capture_output=True, text=True, encoding="utf-8", check=True)
        r = json.loads(out.stdout)
        self.assertEqual(r[0], ["<CALL:6>OE3GAS ", False])
        self.assertEqual(r[1], ["<GRIDSQUARE:6>JN88ef ", True])
        self.assertNotIn("<CALL", r[2][0][1:])                  # no second field inside
        self.assertFalse(r[2][1])                               # and not a locator
        self.assertEqual(r[3][0], "<NAME:6>Jurgen ")
        self.assertEqual(r[4][0], "<QTH:6>Wien x ")
        self.assertEqual(r[5][0], "")


if __name__ == "__main__":
    unittest.main()
