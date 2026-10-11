"""CR3: message of the day per board ([chat_motd], set by the sysop)."""

from __future__ import annotations

import asyncio
import tempfile
import unittest

from tbclient.core import ClientCore
from tinybox import config
from tinybox.config import ConfigError
from tests.test_chat import chat_app
from tests.test_tbclient import client_cfg
from tests.test_tinybox import ROOT, login, type_lines


class MotdTests(unittest.TestCase):
    def setUp(self):
        self.app = chat_app()
        self.board = self.app.cfg.chat.board("TREFF")
        self.board.motd = "Net Sunday 19:00"

    def test_config(self):
        text = (ROOT / "tinybox.conf.example").read_text(encoding="utf-8")
        text = text.replace("#TREFF = Welcome!", "TREFF = Welcome!")
        with tempfile.TemporaryDirectory() as tmp:
            p = f"{tmp}/t.conf"
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)
            cfg = config.load(p)
            self.assertTrue(cfg.chat.board("TREFF").motd.startswith("Welcome! Net every"))
            self.assertEqual(cfg.chat.board("DX").motd, "")
            with open(p, "w", encoding="utf-8") as f:
                f.write(text.replace("[chat_motd]", "[chat_motd]\nDX = " + "x" * 121))
            with self.assertRaises(ConfigError):
                config.load(p)

    def test_terminal(self):
        s, t = login(self.app, "OE1ABC")
        t.take()
        type_lines(s, "C TREFF")
        out = t.take()
        self.assertIn("*** Net Sunday 19:00", out)

    def test_client(self):
        s, t = login(self.app, "OE1ABC")
        t.take()
        type_lines(s, "//CLIENT TB1 v=2026.10.11.7 caps=CHAT")
        t.take()
        type_lines(s, "C TREFF")
        out = t.take()
        crc = self.board.motd_crc
        self.assertRegex(crc, r"^[0-9a-f]{4}$")
        self.assertIn(f" motd={crc}", out)
        self.assertNotIn("Net Sunday", out)                  # only the check value
        type_lines(s, "//MOTD")
        self.assertEqual(t.take(), f"//MOTD {crc} Net Sunday 19:00\r")
        self.board.motd = ""
        type_lines(s, "//MOTD")
        self.assertEqual(t.take(), "//MOTD -\r")


class ClientMotdTests(unittest.TestCase):
    def test_fetch_only_when_new(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp, link="telnet"))
                sent = []
                core.link.send_line = sent.append
                core._control("//IN 1 TREFF 7d - hist=0 now=1 motd=ab12")
                self.assertEqual((core.board["motd"], sent), ("", ["//MOTD"]))
                core._control("//MOTD ab12 Net Sunday")
                self.assertEqual(core.board["motd"], "Net Sunday")
                sent.clear()
                core._control("//IN 1 TREFF 7d - hist=0 now=1 motd=ab12")   # known: no request
                self.assertEqual((core.board["motd"], sent), ("Net Sunday", []))
                core._control("//IN 1 TREFF 7d - hist=0 now=1")            # removed by the sysop
                self.assertEqual(core.board["motd"], "")
        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
