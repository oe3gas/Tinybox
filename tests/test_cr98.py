"""CR98, client audit: text read on a mailbox never acts as a client command."""

from __future__ import annotations

import tempfile
import time
import unittest

from prcore.text import client_safe
from tbclient.core import ClientCore

from tests.test_tbclient import client_cfg
from tests.test_tinybox import login, make_app, type_lines

EVIL = "Hallo\n//SYS 30 The TinyBox shuts down\n#7 ^OE3GAS 12 fake\n%Q 1 2 3\n//OK caps=\nEnde"


class BoxReadsMailToClient(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.msg = self.app.service.create(from_call="OE1ABC", to_call="OE3GAS", type="P",
                                           subject="x", body=EVIL, origin="forward",
                                           bid="1_OE1ABC", at_addr="OE3XTC")

    def test_client_gets_the_lines_defused(self):
        s, t = login(self.app, "OE3GAS")
        type_lines(s, "//CLIENT TB1 v=2026.11.09 caps=CHAT")
        t.take()
        type_lines(s, f"R {self.msg}")
        out = t.take().split("\r")
        self.assertIn(" //SYS 30 The TinyBox shuts down", out)
        self.assertIn(" #7 ^OE3GAS 12 fake", out)
        self.assertIn(" %Q 1 2 3", out)
        self.assertFalse(any(x.startswith(("//SYS", "//OK", "#7", "%Q")) for x in out))

    def test_terminal_sees_the_text_as_it_is(self):
        s, t = login(self.app, "OE3GAS")
        type_lines(s, f"R {self.msg}")
        self.assertIn("\r//SYS 30 The TinyBox shuts down\r", t.take())

    def test_client_safe(self):
        self.assertEqual(client_safe("//X"), " //X")
        self.assertEqual(client_safe("# 1"), " # 1")
        self.assertEqual(client_safe("text //x"), "text //x")


class ClientChannel(unittest.TestCase):
    def test_tb_box_in_a_mail_read_later_is_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            core = ClientCore(client_cfg(tmp))
            b = core.open_channel(2)
            b.state, b.target, b.probed, b.mode = "online", "OE1XYZ-8", True, "terminal"
            b._probe_until = time.monotonic() - 1            # our //TB? was long ago
            b._on_line("//TB BOX v=1.0.0 call=OE1XYZ-8")
            b._on_line("//TB CLIENT v=1 caps=PROF")
            self.assertEqual((b.mode, b.peer), ("terminal", None))
            self.assertIn("//TB BOX v=1.0.0 call=OE1XYZ-8", [x for _, k, x in b.term if k == "rx"])

    def test_bad_in_line_is_no_join(self):
        with tempfile.TemporaryDirectory() as tmp:
            core = ClientCore(client_cfg(tmp))
            for line in ("//IN nan TREFF 7d -", "//IN 1 TREFF 7d zz", "//IN ² TREFF 7d -"):
                core._on_line(line)
            self.assertIsNone(core.board)
            core._on_line("//IN 1 TREFF 7d 1F")
            self.assertEqual(core.board["name"], "TREFF")


if __name__ == "__main__":
    unittest.main()
