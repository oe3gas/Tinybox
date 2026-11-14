"""prcore/tbproto.py: the TB1 client protocol in one place, and the command table of
the box built on it (Refactoring R1)."""

from __future__ import annotations

import unittest

from prcore import tbproto
from tinybox import clientproto
from tests.test_clientproto import radio_login
from tests.test_chat import chat_app
from tests.test_tinybox import login, type_lines


class Caps(unittest.TestCase):
    def test_client_offers_every_cap_the_box_knows(self):
        offered = set(tbproto.client_caps(ui=True, binary=True).split(","))
        self.assertEqual(offered, set(tbproto.CAPS))

    def test_client_caps_as_before(self):
        self.assertEqual(tbproto.client_caps(ui=False, binary=False),
                         "CHAT,SYNC,SYNC2,SHORT,NUM,HAVE,PROF,HSEQ,ADM,LOTW,CT,CTR,PR,GAMES,GAME")
        self.assertEqual(tbproto.client_caps(ui=True, binary=True),
                         "CHAT,UI,SYNC,SYNC2,SHORT,NUM,HAVE,PROF,HSEQ,ADM,LOTW,CT,CTR,PR,"
                         "GAMES,GAME,Z,IMG,BFILE")

    def test_command_table_names_known_caps(self):
        for name, c in clientproto.COMMANDS.items():
            if c.cap:
                self.assertIn(c.cap, tbproto.CAPS, name)


class Signatures(unittest.TestCase):
    def test_needs_signature(self):
        yes = ["SEND P OE3ABC 2", "KILL 5", "ADM STATUS", "PROF t=1 name=x", "SYNC k=1,2",
               "GAME RES id=1"]
        no = ["PROF ?", "SYNC after=3", "GAME ST", "GAMES TOP", "MLIST", "BOARDS"]
        for line in yes:
            p = line.split()
            self.assertTrue(tbproto.needs_signature(p[0], p), line)
        for line in no:
            p = line.split()
            self.assertFalse(tbproto.needs_signature(p[0], p), line)

    def test_with_and_split_signature(self):
        line = tbproto.with_signature("//KILL 5", 3, "abc")
        self.assertEqual(line, "//KILL 5 c=3 sig=abc")
        self.assertEqual(tbproto.split_signature(line), ("//KILL 5", 3, "abc"))
        self.assertEqual(tbproto.split_signature("//KILL 5"), ("//KILL 5", None, None))


class Dispatch(unittest.TestCase):
    def setUp(self):
        self.app = chat_app()

    def test_game_commands_need_their_cap(self):
        """R1: every game command checks its cap like CT and IMG always did."""
        c, ct = login(self.app, "OE3GAS")
        type_lines(c, "//CLIENT TB1 caps=CHAT")
        ct.take()
        for cmd, cap in (("PR START", "PR"), ("GAMES TOP", "GAMES"), ("GAME ST", "GAME")):
            type_lines(c, "//" + cmd)
            self.assertIn(f"//ERR {cmd.split()[0]} needs {cap}", ct.take())

    def test_unknown_and_not_a_client(self):
        term, tt = login(self.app, "OE3XYZ")
        tt.take()
        type_lines(term, "//BOARDS")
        self.assertIn("//ERR not a client session", tt.take())
        c, ct = radio_login(self.app, "OE3GAS")
        type_lines(c, "//CLIENT TB1 caps=CHAT")
        ct.take()
        type_lines(c, "//FLY")
        self.assertIn("//ERR unknown FLY", ct.take())


if __name__ == "__main__":
    unittest.main()
