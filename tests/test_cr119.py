"""CR119: SB is not in the help of a guest on the terminal (he may not write
bulletins, CR92); the sysop and a user with key still see it."""

from __future__ import annotations

import unittest
from unittest import mock

from tinybox import rights, texts
from tests.test_tinybox import login, make_app, type_lines


class HelpTests(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(rights, "GUEST_LIMITS", True)     # as in real operation
        p.start()
        self.addCleanup(p.stop)
        self.app = make_app()

    def test_guest_does_not_see_sb(self):
        s, t = login(self.app, "OE3ABC-7")
        t.take()
        type_lines(s, "H")
        out = t.take()
        self.assertIn("S call", out)
        self.assertNotIn("SB topic", out)
        type_lines(s, "S")
        self.assertNotIn("SB", t.take())                  # usage without SB
        type_lines(s, "SB")
        self.assertIn(texts.NEED_LOGIN.split(" - ")[0], t.take())

    def test_sysop_sees_sb(self):
        s, t = login(self.app, self.app.cfg.station.sysop_call)
        self.assertTrue(s.sysop)
        t.take()
        type_lines(s, "H")
        out = t.take()
        self.assertIn("SB topic", out)
        i, j = out.index("OE1XAB.#WIE.AUT.EU"), out.index("SB topic")
        self.assertLess(i, j)                             # right behind SP
        type_lines(s, "SB")
        self.assertIn(texts.USAGE_SB, t.take())


if __name__ == "__main__":
    unittest.main()
