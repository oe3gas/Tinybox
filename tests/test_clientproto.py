"""TinyBox client protocol on the mailbox side (//CLIENT, TBCHAT events)."""

from __future__ import annotations

import unittest

from tinybox.session import Session, State
from tests.test_chat import chat_app
from tests.test_tinybox import FakeTransport, login, type_lines


def radio_login(app, call):
    t = FakeTransport()
    s = Session(call, app.service, app.cfg, t, origin="radio")
    s.start()
    t.take()
    return s, t


class ClientProtoTests(unittest.TestCase):
    def setUp(self):
        self.app = chat_app()
        self.ui = []
        self.app.service.chat.ui_send = lambda dest, text: self.ui.append((dest, text))

    def test_handshake_telnet_has_no_ui(self):
        s, t = login(self.app, "OE3ABC")
        t.take()
        type_lines(s, "//CLIENT TB1 caps=CHAT,UI,FOO sym=/-")
        out = t.take()
        self.assertTrue(out.startswith("\r//OK TB1 caps=CHAT\r"), out)
        self.assertNotIn("TinyBox (", out)            # no prompt in client mode
        self.assertEqual(s.client.symbol, "/-")

    def test_handshake_radio_ui_and_bad_symbol(self):
        s, t = radio_login(self.app, "OE3ABC")
        type_lines(s, "//CLIENT TB1 caps=CHAT,UI sym=xx")
        self.assertIn("//OK TB1 caps=CHAT,UI", t.take())
        self.assertEqual(s.client.symbol, "")

    def test_wrong_proto_and_not_client(self):
        s, t = login(self.app, "OE3ABC")
        t.take()
        type_lines(s, "//BOARDS")
        self.assertIn("//ERR", t.take())
        type_lines(s, "//CLIENT TB9")
        self.assertIn("//ERR protocol", t.take())
        self.assertIsNone(s.client)

    def test_boards(self):
        s, t = login(self.app, "OE3ABC")
        type_lines(s, "//CLIENT TB1 caps=CHAT")
        t.take()
        type_lines(s, "//BOARDS")
        self.assertEqual(t.take(), "//B 1 TREFF 7d 0 Meeting point\r"
                                   "//B 2 RUNDE live 0 Live only\r//BEND\r")

    def test_ui_chat_flow(self):
        term, tt = login(self.app, "OE3XYZ")
        type_lines(term, "C TREFF", "vorher")
        tt.take()
        c, ct = radio_login(self.app, "OE3GAS")
        type_lines(c, "//CLIENT TB1 caps=CHAT,UI sym=/-")
        ct.take()
        type_lines(c, "C 1")
        out = ct.take().split("\r")
        self.assertEqual(out[0], "//IN 1 TREFF 7d 1")      # 0 = join, 1 = 'vorher'
        self.assertTrue(out[1].startswith("//H ") and out[1].endswith(" OE3XYZ: vorher"))
        self.assertEqual(out[2], "//WHO OE3XYZ")
        self.assertEqual(self.ui[-1], ("TBCHAT-1", "#2 +OE3GAS /-"))
        self.assertIn("*** OE3GAS joined TREFF", tt.take())
        self.assertEqual(c.state, State.CHAT)
        # terminal user speaks: one UI frame, the UI client gets no I-frame
        type_lines(term, "Servus :+1")
        self.assertEqual(self.ui[-1], ("TBCHAT-1", "#3 OE3XYZ: Servus :+1"))
        self.assertEqual(ct.take(), "")
        # client speaks and reacts
        type_lines(c, "Hallo ~0A", "/R 3 :+1")
        self.assertEqual(self.ui[-2:], [("TBCHAT-1", "#4 OE3GAS: Hallo ~0A"),
                                        ("TBCHAT-1", "#5 OE3GAS *3 :+1")])
        out = tt.take()
        self.assertIn("OE3GAS: Hallo ~0A", out)
        self.assertIn("*** OE3GAS :+1 to: OE3XYZ: Servus :+1", out)
        # resend, only to the client, as I-frames
        type_lines(c, "//RESEND 3-4")
        self.assertEqual(ct.take(), "#3 OE3XYZ: Servus :+1\r#4 OE3GAS: Hallo ~0A\r")
        type_lines(c, "/Q")
        self.assertEqual(ct.take(), "//OUT TREFF\r")
        self.assertIn("*** OE3GAS left TREFF", tt.take())

    def test_non_ui_client_gets_iframes_incl_own(self):
        c, ct = login(self.app, "OE3GAS")
        type_lines(c, "//CLIENT TB1 caps=CHAT")
        type_lines(c, "C RUNDE")
        ct.take()
        type_lines(c, "test")
        self.assertEqual(ct.take(), "#1 OE3GAS: test\r")
        self.assertEqual(self.ui, [])                 # nobody needs UI

    def test_seq_wraps_and_board_over_15_has_no_ui(self):
        hub = self.app.service.chat
        hub._seq["TREFF"] = 0xFE
        c, ct = radio_login(self.app, "OE3GAS")
        type_lines(c, "//CLIENT TB1 caps=CHAT,UI", "C 1", "a")
        self.assertEqual([x[1] for x in self.ui], ["#FF +OE3GAS", "#0 OE3GAS: a"])
        self.assertEqual(hub.replay("TREFF", 0xFF, 0x0), ["#FF +OE3GAS", "#0 OE3GAS: a"])
        hub.boards[0:0] = [type(hub.boards[0])(f"B{i}", 1) for i in range(15)]
        self.ui.clear()
        type_lines(c, "b")          # TREFF is board 16 now
        self.assertEqual(self.ui, [])
        self.assertIn("OE3GAS: b", ct.take())


if __name__ == "__main__":
    unittest.main()
