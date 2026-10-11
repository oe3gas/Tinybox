"""Chat board tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tinybox import config
from tinybox.config import ChatBoard, ChatCfg
from tinybox.session import State
from tests.test_tinybox import ROOT, login, make_app, type_lines


def chat_app():
    app = make_app()
    app.cfg.chat = ChatCfg(enabled=True, history_lines=5, max_line=50, boards=[
        ChatBoard("TREFF", 7 * 24, "Meeting point"),
        ChatBoard("RUNDE", 0, "Live only"),
    ])
    return app


class ChatConfigTests(unittest.TestCase):
    def load(self, extra: str) -> config.Config:
        base = (ROOT / "tinybox.conf.example").read_text(encoding="utf-8")
        start = base.index("[chat]")
        end = base.index("[mqtt]")
        text = base[:start] + extra + "\n" + base[end:]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "tinybox.conf"
            p.write_text(text, encoding="utf-8")
            return config.load(p)

    def test_example_boards(self):
        cfg = config.load(ROOT / "tinybox.conf.example")
        self.assertTrue(cfg.chat.enabled)
        names = [b.name for b in cfg.chat.boards]
        self.assertEqual(names[0], "TREFF")
        self.assertIn("RUNDE", names)
        self.assertTrue(cfg.chat.board("runde").live)
        self.assertEqual(cfg.chat.board("TREFF").keep_hours, 168)
        self.assertEqual(cfg.chat.board("TREFF").description, "General meeting point")

    def test_parse_keep(self):
        self.assertEqual(config.parse_keep("live"), 0)
        self.assertEqual(config.parse_keep("12h"), 12)
        self.assertEqual(config.parse_keep("2D"), 48)
        for bad in ("0h", "366d", "7w", "x"):
            with self.assertRaises(ValueError):
                config.parse_keep(bad)

    def test_bad_board(self):
        with self.assertRaises(config.ConfigError):
            self.load("[chat]\nenabled = yes\n[chat_boards]\nTOOLONGNAME = 1d x\n")
        with self.assertRaises(config.ConfigError):
            self.load("[chat]\nenabled = yes\n[chat_boards]\nTREFF = 1w x\n")
        with self.assertRaises(config.ConfigError):
            self.load("[chat]\nenabled = yes\n")

    def test_disabled_without_section(self):
        cfg = self.load("")
        self.assertFalse(cfg.chat.enabled)


class ChatTests(unittest.TestCase):
    def setUp(self):
        self.app = chat_app()
        self.a, self.ta = login(self.app, "OE3ABC")
        self.b, self.tb = login(self.app, "OE3XYZ-2")
        self.ta.take(), self.tb.take()

    def test_list_boards(self):
        type_lines(self.a, "C")
        out = self.ta.take()
        self.assertIn("TREFF", out)
        self.assertIn("live", out)
        self.assertIn("Meeting point", out)

    def test_chat_off(self):
        self.app.cfg.chat.enabled = False
        type_lines(self.a, "C")
        self.assertIn("not available", self.ta.take())

    def test_not_on_console(self):
        from tinybox.session import Session
        from tests.test_tinybox import FakeTransport
        t = FakeTransport()
        s = Session("OE3GAS", self.app.service, self.app.cfg, t, origin="sysop", sysop=True)
        type_lines(s, "C TREFF")
        self.assertIn("not on the console", t.take())
        self.assertEqual(s.state, State.COMMAND)

    def test_unknown_board(self):
        type_lines(self.a, "C NIX")
        self.assertIn("No such chat board: NIX", self.ta.take())
        self.assertEqual(self.a.state, State.COMMAND)

    def test_live_delivery_and_no_echo(self):
        type_lines(self.a, "C TREFF")
        self.assertEqual(self.a.state, State.CHAT)
        self.assertIn("Nobody else", self.ta.take())
        type_lines(self.b, "C 1")          # by number
        self.assertIn("In this board: OE3ABC", self.tb.take())
        self.assertIn("*** OE3XYZ-2 joined TREFF", self.ta.take())
        type_lines(self.a, "Hallo Welt")
        self.assertIn("OE3ABC: Hallo Welt", self.tb.take())
        self.assertNotIn("Hallo Welt", self.ta.take())   # no echo, no prompt
        type_lines(self.b, "/W")
        self.assertIn("OE3ABC", self.tb.take())

    def test_history_board(self):
        type_lines(self.a, "C TREFF", "erste", "zweite", "/Q")
        self.assertEqual(self.a.state, State.COMMAND)
        self.assertIn("back in the mailbox", self.ta.take())
        type_lines(self.b, "C TREFF")
        out = self.tb.take()
        # CR13: no history unasked, only how much is stored and how to read it
        self.assertNotIn("erste", out)
        self.assertRegex(out, r"\*\*\* 2 lines stored\. Last from 20\d\d-\d\d-\d\d \d\d:\d\d UTC\r"
                              r"\*\*\* /H n to read")
        type_lines(self.b, "/H 10")
        out = self.tb.take()
        self.assertIn("OE3ABC: erste", out)
        self.assertIn("OE3ABC: zweite", out)
        self.assertLess(out.index("erste"), out.index("zweite"))
        type_lines(self.b, "/H 1")
        out = self.tb.take()
        self.assertNotIn("erste", out)
        self.assertIn("OE3ABC: zweite", out)
        type_lines(self.b, "/H")                                   # without a number: help
        self.assertIn("/H n       Show the last n stored lines", self.tb.take())

    def test_history_limit(self):
        type_lines(self.a, "C TREFF", *[f"zeile {i}" for i in range(8)], "/Q")
        type_lines(self.b, "C TREFF", "/H 50")                     # at most history_lines (5)
        out = self.tb.take()
        self.assertIn("8 lines stored", out)
        self.assertNotIn("zeile 2", out)
        self.assertIn("zeile 3", out)
        self.assertIn("zeile 7", out)

    def test_live_board_stores_nothing(self):
        type_lines(self.a, "C RUNDE", "geheim", "/Q")
        type_lines(self.b, "C RUNDE")
        out = self.tb.take()
        self.assertNotIn("geheim", out)
        self.assertIn("Live board", out)

    def test_switch_board(self):
        type_lines(self.a, "C TREFF")
        type_lines(self.b, "C TREFF")
        self.ta.take()
        type_lines(self.b, "/J RUNDE")
        self.assertIn("*** OE3XYZ-2 left TREFF", self.ta.take())
        self.assertEqual(self.b.chat_board, "RUNDE")
        type_lines(self.b, "test")
        self.assertNotIn("test", self.ta.take())

    def test_ctrl_z_leaves(self):
        type_lines(self.a, "C TREFF", "tschuess\x1a")
        self.assertEqual(self.a.state, State.COMMAND)
        self.assertIsNone(self.a.chat_board)

    def test_disconnect_leaves(self):
        type_lines(self.a, "C TREFF")
        type_lines(self.b, "C TREFF")
        self.ta.take()
        self.b.end()
        self.assertIn("left TREFF (disconnected)", self.ta.take())
        self.assertEqual(self.app.service.chat.members("TREFF"), [self.a])

    def test_long_line_cut(self):
        type_lines(self.a, "C TREFF")
        type_lines(self.b, "C TREFF")
        type_lines(self.a, "x" * 80)
        self.assertIn("cut to 50", self.ta.take())
        self.assertIn("OE3ABC: " + "x" * 50 + "\r", self.tb.take())

    def test_mailbox_commands_not_in_chat(self):
        type_lines(self.a, "C TREFF")
        type_lines(self.b, "C TREFF")
        type_lines(self.a, "L")     # plain text in the chat, not the list command
        self.assertIn("OE3ABC: L", self.tb.take())

    def test_login_shows_active_chat(self):
        type_lines(self.a, "C TREFF")
        _, t = login(self.app, "OE1AAA")
        self.assertIn("1 station(s) in the chat", t.take())

    def test_purge(self):
        store = self.app.store
        store.chat_add("TREFF", "OE3ABC", "alt", "2000-01-01T00:00:00Z")
        store.chat_add("WEG", "OE3ABC", "board removed", "2099-01-01T00:00:00Z")
        type_lines(self.a, "C TREFF", "neu", "/Q")
        self.assertEqual(self.app.service.chat.purge(), 2)
        lines = store.chat_recent("TREFF", "1970-01-01T00:00:00Z", 10)
        self.assertEqual([c.text for c in lines], ["neu"])

    def test_no_idle_timeout_in_chat(self):
        self.assertFalse(self.a.idle_exempt)
        type_lines(self.a, "C RUNDE")
        self.assertTrue(self.a.idle_exempt)
        type_lines(self.a, "/Q")
        self.assertFalse(self.a.idle_exempt)

    def test_events(self):
        seen = []
        self.app.bus.subscribe("chat.message", lambda n, d: seen.append(d))
        type_lines(self.a, "C RUNDE", "hi")
        self.assertEqual(seen[0]["board"], "RUNDE")
        self.assertEqual(seen[0]["text"], "hi")


if __name__ == "__main__":
    unittest.main()
