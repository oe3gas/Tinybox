"""CR73: user profile (name, locator, home BBS) - shared checks, the TinyBox
(questions after the login, commands, chat who list, TB1 //PROF //WHOIS) and
the client (store, compare, invitation, profiles of the others)."""

from __future__ import annotations

import asyncio
import tempfile
import time
import unittest

from prcore import profile as pf
from tbclient.core import ClientCore
from tinybox import profiles
from tinybox.session import State
from tests.test_chat import chat_app
from tests.test_tbclient import client_cfg
from tests.test_tinybox import login, make_app, type_lines


class SharedTests(unittest.TestCase):
    def test_checks(self):
        self.assertEqual(pf.check_name("  Hans   Peter "), "Hans Peter")
        self.assertEqual(pf.check_name("Jürgen"), "Jürgen")
        self.assertEqual(pf.check_name(""), "")
        for bad in ("Gerhard Maximilian", "R2D2", "x=y", "-Hans"):
            with self.assertRaises(pf.ProfileError):
                pf.check_name(bad)
        self.assertEqual(pf.check_locator("jn88ep"), "JN88EP")
        self.assertEqual(pf.check_locator("JN88"), "JN88")
        for bad in ("JN8", "JN88E", "ZZ88", "JN88EPXX"):
            with self.assertRaises(pf.ProfileError):
                pf.check_locator(bad)
        self.assertEqual(pf.check_home("oe3xsr-8"), "OE3XSR")
        self.assertEqual(pf.check_home("oe3xsr-8.#noe.aut.eu"), "OE3XSR.#NOE.AUT.EU")
        for bad in ("OE3", "ALLOE", "OE3XSR..AUT", "OE3XSR.#NOE.AUT.EU.TOO.LONG.FOR.THE.FIELD"):
            with self.assertRaises(pf.ProfileError, msg=bad):
                pf.check_home(bad)

    def test_line_format_and_crc(self):
        p = {"t": 7, "name": "Hans Peter", "loc": "JN88", "home": ""}
        line = pf.encode(p)
        self.assertEqual(line, "t=7 loc=JN88 home= name=Hans Peter")
        self.assertEqual(pf.decode(line), p)
        self.assertEqual(pf.crc(None), "-")
        self.assertEqual(pf.crc({"name": "", "loc": "", "home": ""}), "-")
        self.assertRegex(pf.crc(p), r"^[0-9a-f]{4}$")
        self.assertNotEqual(pf.crc(p), pf.crc({**p, "loc": "JN88EP"}))
        self.assertEqual(pf.crc(p), pf.crc({**p, "t": 99}))       # the time does not count


class TerminalQuestionTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app(ask_profile=True)

    def test_questions_after_login(self):
        s, t = login(self.app, "OE3ABC-7")
        out = t.take()
        self.assertIn("Please introduce yourself", out)
        self.assertTrue(out.endswith("Your first name: "), out)
        self.assertNotIn("TinyBox (", out)                  # no prompt yet
        type_lines(s, "Gerhard", "JN8")
        self.assertIn("Locator: 4 or 6", t.take())          # explained, asked again
        type_lines(s, "jn88ep", "")                          # home BBS skipped
        out = t.take()
        self.assertIn("Thank you", out)
        self.assertTrue(out.endswith("TinyBox (A,B,C,F,H,J,K,L,R,S,V,?) > "))
        p = profiles.get(self.app.store, "OE3ABC")          # one profile for all SSIDs
        self.assertEqual((p["name"], p["loc"], p["home"]), ("Gerhard", "JN88EP", ""))
        # the next login: the home BBS is still missing, but asked only every 30 days
        s2, t2 = login(self.app, "OE3ABC")
        self.assertNotIn("introduce", t2.take())

    def test_only_missing_fields_and_abort(self):
        profiles.save(self.app.store, "OE3ABC", {"name": "Hans", "loc": "JN88"})
        s, t = login(self.app, "OE3ABC")
        self.assertTrue(t.take().endswith("Your home BBS (e.g. OE3XSR): "))
        type_lines(s, "/AB")
        self.assertIn("Set it later with N name", t.take())
        self.assertEqual(s.state, State.COMMAND)

    def test_client_line_ends_the_questions(self):
        s, t = login(self.app, "OE3NEW")
        t.take()
        type_lines(s, "//CLIENT TB1 caps=CHAT,PROF")
        out = t.take()
        self.assertIn("//OK TB1 caps=CHAT,PROF", out)
        self.assertIn("prof=-", out)
        self.assertNotIn("Thank you", out)
        self.assertNotIn("Set it later", out)
        self.assertEqual(s.state, State.COMMAND)

    def test_disconnect_keeps_answers(self):
        s, t = login(self.app, "OE3ABC")
        type_lines(s, "Gerhard")
        s.end()
        self.assertEqual(profiles.get(self.app.store, "OE3ABC")["name"], "Gerhard")

    def test_switched_off_and_sysop_console(self):
        app = make_app()                                      # ask_profile = no
        s, t = login(app, "OE3ABC")
        self.assertNotIn("introduce", t.take())


class TerminalCommandTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()

    def test_n_nl_nh_i(self):
        s, t = login(self.app, "OE3ABC-2")
        t.take()
        type_lines(s, "N")
        self.assertIn("No profile for OE3ABC.", t.take())
        type_lines(s, "N Hans Peter")
        self.assertIn("OE3ABC: name Hans Peter, locator -, home BBS -", t.take())
        type_lines(s, "NL jn88yy")
        self.assertIn("Locator: 4 or 6", t.take())          # YY is not a subsquare
        type_lines(s, "NL jn88ep", "NH oe3xsr.#noe.aut.eu")
        self.assertIn("locator JN88EP, home BBS OE3XSR.#NOE.AUT.EU", t.take())
        type_lines(s, "NH -")
        self.assertIn("home BBS -", t.take())
        u, ut = login(self.app, "OE3XYZ")
        ut.take()
        type_lines(u, "I oe3abc-9", "I OE3QQQ", "I 1234567", "I")
        out = ut.take()
        self.assertIn("OE3ABC: name Hans Peter, locator JN88EP", out)
        self.assertIn("No profile for OE3QQQ.", out)
        self.assertIn("Invalid callsign", out)
        self.assertIn("No profile for OE3XYZ.", out)

    def test_chat_who_list_with_profile(self):
        app = chat_app()
        profiles.save(app.store, "OE3ABC", {"name": "Hans", "loc": "JN88"})
        a, at = login(app, "OE3ABC-7")
        b, bt = login(app, "OE3XYZ")
        type_lines(a, "C TREFF")
        type_lines(b, "C TREFF")
        self.assertIn("In this board: OE3ABC-7 (Hans, JN88)", bt.take())
        type_lines(a, "/W")
        self.assertIn("In this board: OE3XYZ", at.take())


class ClientProtoTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()

    def client(self, call="OE3ABC", caps="CHAT,PROF"):
        s, t = login(self.app, call)
        t.take()
        type_lines(s, f"//CLIENT TB1 caps={caps}")
        return s, t, t.take()

    def test_ok_tells_crc(self):
        _, _, ok = self.client()
        self.assertIn("prof=-", ok)
        saved = profiles.save(self.app.store, "OE3ABC", {"name": "Hans", "loc": "JN88"})
        _, _, ok = self.client("OE3ABC-5")
        self.assertIn(f"prof={pf.crc(saved)}", ok)
        _, _, ok = self.client("OE3ABC", caps="CHAT")        # older client: nothing extra
        self.assertNotIn("prof=", ok)

    def test_store_fetch_and_newer_wins(self):
        s, t, _ = self.client()
        type_lines(s, "//PROF ?")
        self.assertEqual(t.take(), "//PROF -\r")
        type_lines(s, "//PROF t=1000 loc=jn88ep home= name=Hans Peter")
        crc = pf.crc({"name": "Hans Peter", "loc": "JN88EP", "home": ""})
        self.assertEqual(t.take(), f"//PROF OK {crc}\r")
        type_lines(s, "//PROF ?")
        self.assertEqual(t.take(), f"//PROF = {crc} t=1000 loc=JN88EP home= name=Hans Peter\r")
        type_lines(s, "//PROF t=900 loc=JN87 home= name=Old")       # older than ours
        self.assertIn("//PROF = ", t.take())
        self.assertEqual(profiles.get(self.app.store, "OE3ABC")["loc"], "JN88EP")
        type_lines(s, "//PROF t=2000 loc=XX99 home= name=Hans")
        self.assertEqual(t.take(), "//PROF ERR loc\r")

    def test_whois(self):
        profiles.save(self.app.store, "OE3XYZ", {"name": "Eva", "loc": "JN78", "home": "OE1XAB"})
        s, t, _ = self.client()
        type_lines(s, "//WHOIS OE3XYZ-7,oe1qqq OE3XYZ")
        self.assertEqual(t.take(), "//WI OE3XYZ loc=JN78 home=OE1XAB name=Eva\r"
                                   "//WI OE1QQQ -\r//WIEND\r")
        type_lines(s, "//WHOIS " + ",".join(f"OE1A{c}" for c in "BCDEFGHIJKL"))
        self.assertEqual(t.take(), "//ERR whois\r")


class ClientSideTests(unittest.TestCase):
    """The client against a real TinyBox session: what one sends the other gets."""

    def bridge(self, core, call="OE3GAS"):
        s, t = login(self.app, call)
        t.take()
        queue: list[str] = []

        def send(line):
            queue.append(line)

        def pump():
            while queue:
                type_lines(s, queue.pop(0))
                for line in t.take().split("\r"):
                    if line:
                        core._on_line(line)

        core.link.send_line = send
        core.state = "online"
        core._handshake()
        pump()
        return s, pump, queue

    def setUp(self):
        self.app = make_app()

    def test_first_entry_goes_to_the_tinybox(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp, link="telnet", locator="JN88EP"))
                s, pump, queue = self.bridge(core)
                self.assertIn("PROF", core.caps)
                snap = core.snapshot()
                self.assertTrue(snap["profile_ask"])           # name missing: invitation
                self.assertEqual(snap["profile"]["loc"], "JN88EP")  # proposal from the conf
                self.assertFalse(snap["profile_set"])
                self.assertIsNone(profiles.get(self.app.store, "OE3GAS"))   # nothing sent yet
                self.assertEqual(core.profiles.set("Gerhard", "JN88EP", "R2D2"), "home")
                self.assertEqual(core.profiles.set("Gerhard", "jn88ep", ""), "")
                pump()
                self.assertEqual(profiles.get(self.app.store, "OE3GAS")["name"], "Gerhard")
                self.assertFalse(core.snapshot()["profile_ask"])
                self.assertEqual(core.profiles.box_crc,
                                 pf.crc({"name": "Gerhard", "loc": "JN88EP", "home": ""}))
                # next login: same crc - nothing on the air
                core._clear_chat()
                sent = []
                s2, pump2, _ = self.bridge(core)
                core.link.send_line = sent.append
                core.profiles.on_ok(f"caps=CHAT,PROF prof={core.profiles.box_crc}")
                self.assertEqual(sent, [])
        asyncio.run(scenario())

    def test_terminal_change_comes_back(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp, link="telnet"))
                core.settings["profile"] = {"name": "Gerhard", "loc": "JN88", "home": "", "t": 100}
                profiles.save(self.app.store, "OE3GAS", {"name": "Gerhard", "loc": "JN88EP"},
                              changed=int(time.time()))           # NL in the terminal, later
                self.bridge(core)
                self.assertEqual(core.profiles.mine["loc"], "JN88EP")
        asyncio.run(scenario())

    def test_new_pc_takes_the_profile(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                profiles.save(self.app.store, "OE3GAS", {"name": "Gerhard", "loc": "JN88EP"},
                              changed=100)
                core = ClientCore(client_cfg(tmp, link="telnet", locator="JN77"))
                self.bridge(core)
                self.assertEqual(core.profiles.mine["loc"], "JN88EP")
                self.assertFalse(core.snapshot()["profile_ask"])
        asyncio.run(scenario())

    def test_later_snoozes(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp, link="telnet"))
                self.bridge(core)
                self.assertTrue(core.snapshot()["profile_ask"])
                core.profiles.later()
                self.assertFalse(core.snapshot()["profile_ask"])
        asyncio.run(scenario())

    def test_profiles_of_others(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                profiles.save(self.app.store, "OE3XYZ", {"name": "Eva", "loc": "JN78"})
                core = ClientCore(client_cfg(tmp, link="telnet", locator="JN88EP"))
                s, pump, queue = self.bridge(core)
                core.board = {"n": 1, "name": "TREFF", "keep": "7d"}
                core._control("//WHO OE3XYZ-7=/- OE3QQQ OE3GAS")
                await asyncio.sleep(0.7)                       # gathered into one //WHOIS
                self.assertEqual(queue, ["//WHOIS OE3XYZ,OE3QQQ"])
                pump()
                snap = core.snapshot()
                eva = snap["profiles"]["OE3XYZ-7"]
                self.assertEqual((eva["name"], eva["loc"]), ("Eva", "JN78"))
                self.assertGreater(eva["km"], 50)
                self.assertNotIn("OE3QQQ", snap["profiles"])
                core._control("//WHO OE3XYZ-7=/- OE3QQQ")      # known now: no new //WHOIS
                await asyncio.sleep(0.7)
                self.assertEqual(queue, [])
        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
