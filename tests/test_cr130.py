"""CR130: the TinyBox terminal of the client - //CMD, and when it is locked."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from tinybox.session import State
from tests.test_chat import chat_app
from tests.test_tinybox import login, type_lines


class BoxCmdTests(unittest.TestCase):
    def setUp(self):
        self.app = chat_app()

    def client(self, call, caps="CHAT,NUM,CMD,PRM"):
        s, t = login(self.app, call)
        type_lines(s, f"//CLIENT TB1 caps={caps}", "C TREFF")
        t.take()
        return s, t

    def test_cmd_in_a_board_stays_there_others_hear_nothing(self):
        a, ta = self.client("OE3GAS")
        b, tb = self.client("OE3TEC")
        tb.take()
        type_lines(a, "//CMD L")
        out = ta.take()
        self.assertNotIn("OE3GAS: L", out)                 # no chat line
        self.assertTrue(out.rstrip("\r").endswith("//P"))  # the terminal shows its prompt
        self.assertEqual((a.state, a.chat_board), (State.CHAT, "TREFF"))
        self.assertEqual(tb.take(), "")                    # the others notice nothing

    def test_without_the_cap_it_is_unknown(self):
        a, ta = self.client("OE3GAS", caps="CHAT,NUM")
        type_lines(a, "//CMD L")
        self.assertIn("//ERR", ta.take())

    def test_no_protocol_lines_through_cmd(self):
        a, ta = self.client("OE3GAS")
        type_lines(a, "//CMD //WHO")
        self.assertIn("//ERR cmd", ta.take())

    def test_outside_a_board_the_same(self):
        s, t = login(self.app, "OE3GAS")
        type_lines(s, "//CLIENT TB1 caps=CHAT,CMD")
        t.take()
        type_lines(s, "//CMD L")
        self.assertEqual(s.state, State.COMMAND)
        self.assertNotIn("//ERR", t.take())


class ClientSideTests(unittest.TestCase):
    def test_terminal_line_goes_as_cmd(self):
        from tbclient.channels import Channel
        sent = []
        core = SimpleNamespace(caps={"CMD"}, send_line=sent.append, changed=lambda: None,
                               console=[])
        ch = Channel.__new__(Channel)
        ch.core, ch.state, ch.peer, ch.term, ch.term_n, ch.act_n = core, "online", None, [], 0, 0
        core.chan = ch
        ch.send_raw("L")
        ch.send_raw("//MOTD")                          # protocol lines unchanged
        ch.send_raw("")                                # an empty line as it is
        core.caps = set()
        ch.send_raw("L")
        self.assertEqual(sent, ["//CMD L", "//MOTD", "", "L"])

    def test_term_ok_while_the_key_waits(self):
        """CR141: key not yet confirmed (//AUTHWAIT, no //OK) - the box is in its plain
        terminal, the TinyBox terminal must open (CR133)."""
        from tbclient.core import ClientCore as Core
        c = Core.__new__(Core)
        c.chan = SimpleNamespace(state="online")
        c.handshake_done, c.caps = True, set()
        c.images = SimpleNamespace(upload=None)
        c.bfiles = SimpleNamespace(upload=None)
        c.playing = lambda: False
        for st, ok in (("wait", True), ("refused", True), ("", False), ("ok", False)):
            c.auth = {"state": st}
            self.assertEqual(c.term_ok(), ok, st)
        c.auth, c.caps = {"state": "ok"}, {"CMD"}
        self.assertTrue(c.term_ok())
        c.chan.state = "offline"
        c.auth, c.caps = {"state": "wait"}, set()
        self.assertFalse(c.term_ok())


if __name__ == "__main__":
    unittest.main()
