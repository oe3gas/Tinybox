"""CR118: the welcome questions - a greeting after the name, the home BBS
checked like a connecting call, "S SYSOP" in the middle of the questions."""

from __future__ import annotations

import unittest

from prcore import profile as pf
from tinybox import profiles, texts
from tinybox.session import State
from tests.test_tinybox import login, make_app, type_lines


class HomeCheckTests(unittest.TestCase):
    def test_plausible_home_bbs(self):
        for good in ("OE3XSR", "oe3xsr-8.#noe.aut.eu", "DB0FHN", "4X1AB", "K1A"):
            pf.check_home(good)
        for bad in ("this", "jn77ss", "JO44KT", "70CM", "QO100", "123456", "ABCDEF"):
            with self.assertRaises(pf.ProfileError, msg=bad):
                pf.check_home(bad)


class WelcomeTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app(ask_profile=True)

    def test_greeting_after_the_name(self):
        s, t = login(self.app, "OE3ABC-7")
        self.assertIn("S SYSOP", t.take())
        type_lines(s, "Hans")
        out = t.take()
        self.assertTrue(any(g.format(name="Hans") in out for g in texts.PROFILE_GREET), out)
        self.assertTrue(out.endswith("Your locator (e.g. JN88EP): "), out)
        self.assertEqual(len(texts.PROFILE_GREET), 8)
        self.assertTrue(all("{name}" in g for g in texts.PROFILE_GREET))
        self.assertTrue(all(g.isascii() for g in texts.PROFILE_GREET))

    def test_no_greeting_without_a_name(self):
        s, t = login(self.app, "OE3ABC-7")
        t.take()
        type_lines(s, "")
        self.assertTrue(t.take().startswith("Your locator"))

    def test_locator_as_home_is_refused(self):
        s, t = login(self.app, "OE3ABC-7")
        type_lines(s, "Hans", "JO44KT", "jn77ss")
        self.assertIn(texts.PROFILE_BAD["home"], t.take())
        self.assertEqual(s.state, State.PROFILE)            # asked again

    def test_s_sysop_in_the_questions(self):
        s, t = login(self.app, "OE3ABC-7")
        type_lines(s, "Hans", "s sysop")
        out = t.take()
        self.assertIn(texts.SUBJECT_PROMPT.strip(), out)
        self.assertEqual(s.state, State.SEND_SUBJECT)
        self.assertEqual(profiles.get(self.app.store, "OE3ABC")["name"], "Hans")   # kept
        type_lines(s, "Hilfe", "Komme nicht weiter", "/EX")
        sysop = self.app.cfg.station.sysop_call
        out = t.take()
        self.assertIn("saved", out)
        msgs = self.app.service.unread_for(sysop)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0].subject, "Hilfe")

    def test_s_sysop_as_a_command(self):
        s, t = login(self.app, "OE3ABC-7")
        type_lines(s, "/AB")
        t.take()
        type_lines(s, "S SYSOP")
        self.assertEqual(s.state, State.SEND_SUBJECT)


if __name__ == "__main__":
    unittest.main()
