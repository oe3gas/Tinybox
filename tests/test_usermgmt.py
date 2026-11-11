"""User management (11.11.2026): the thank-you for choosing this box as home, and
the Users list of the web GUI (keys.people)."""

from __future__ import annotations

import unittest

from tinybox import keys, profiles

from tests.test_tinybox import login, make_app, type_lines


class HomeThanks(unittest.TestCase):
    def setUp(self):
        self.app = make_app(ask_profile=True)
        self.box = self.app.cfg.station.mailbox_call.upper()

    def test_intro_with_this_box_as_home(self):
        s, t = login(self.app, "OE1ABC-7")
        t.take()
        type_lines(s, "Quintus", "JN88bn", self.box.lower())
        self.assertIn(f"Thank you for choosing {self.box} as your home!", t.take())

    def test_other_home_no_thanks(self):
        s, t = login(self.app, "OE1ABC-7")
        t.take()
        type_lines(s, "Quintus", "JN88bn", "oe1xyz-1")
        self.assertNotIn("as your home", t.take())

    def test_nh_command(self):
        s, t = login(self.app, "OE1ABC")
        type_lines(s, "/AB")
        t.take()
        base = profiles.base_call(self.box)
        type_lines(s, f"NH {base}.#NOE.AUT.EU")
        self.assertIn("as your home", t.take())

    def test_home_is(self):
        self.assertTrue(profiles.home_is("OE3GAS", "OE3GAS-1"))
        self.assertTrue(profiles.home_is("oe3gas-1.#noe.aut.eu", "OE3GAS-1"))
        self.assertFalse(profiles.home_is("", "OE3GAS-1"))
        self.assertFalse(profiles.home_is("OE3GASX", "OE3GAS-1"))


class People(unittest.TestCase):
    def test_one_row_per_call_waiting_first(self):
        app = make_app()
        st = app.store
        st.key_put("OE3GAS", "A" * 43, "active", device="CF44562D")
        st.key_put("OE1ABC", "C" * 43, "pending")
        st.profile_set("OE1ABC", "Quintus", "JN88BN", "OE3GAS-1", 1)
        st.user_login("OE1ABC-7")
        st.user_login("OE3TEC")
        st.jlog_touch("OE1ABC-7")
        st.jlog_touch("OE1ABC-8")
        app.service.ban("OE1KBC", "x")
        rows = keys.people(app.service)
        self.assertEqual([r["call"] for r in rows], ["OE1ABC", "OE1KBC", "OE3GAS", "OE3TEC"])
        first = rows[0]
        self.assertEqual((first["name"], first["waiting"], first["ssids"]), ("Quintus", 1, ["OE1ABC-7", "OE1ABC-8"]))
        self.assertEqual(first["connects"], 2)                 # JLOG: all SSIDs together
        self.assertTrue(first["first"] and first["last"])
        self.assertTrue(rows[1]["ban"])
        self.assertEqual(len(rows[2]["keys"]), 1)


if __name__ == "__main__":
    unittest.main()
