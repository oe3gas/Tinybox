"""CR123: Prefix raten - the game list, the pool, the calls, a game in a board."""

from __future__ import annotations

import random
import re
import unittest

from prcore import prefixgame as pg
from tinybox import prefixgame as box
from tests.test_chat import chat_app
from tests.test_tinybox import login, type_lines


class ListTests(unittest.TestCase):
    def setUp(self):
        self.ents = pg.entities()

    def test_list_loads(self):
        self.assertGreater(len(self.ents), 290)
        names = {e.name for e in self.ents}
        self.assertIn("Austria", names)
        self.assertIn("Saar (alt)", names)
        self.assertEqual(len(names), len(self.ents))         # every answer text once

    def test_stage_sizes(self):
        rng = random.Random(1)
        n = {st: len([e for e in self.ents if st in e.stages]) for st in pg.STAGES}
        self.assertEqual(n, {"NC": 125, "OM": 261, "PRO": 64, "GOD": 66})
        self.assertEqual(len(pg.pool(self.ents, "PRO", "2", rng)), 50)     # filled up from OM
        self.assertEqual(len(pg.pool(self.ents, "NC", "3", rng)), 16)      # no weaker stage
        self.assertEqual(len(pg.pool(self.ents, "OM", "123", rng)), 261)

    def test_fill_takes_the_rarest_first(self):
        rng = random.Random(2)
        p = pg.pool(self.ents, "GOD", "1", rng)
        own = [e for e in p if "GOD" in e.stages]
        extra = [e for e in p if "GOD" not in e.stages]
        self.assertEqual(len(own) + len(extra), 50)
        self.assertTrue(all("PRO" in e.stages for e in extra[:20]))

    def test_calls_fit_the_pattern(self):
        rng = random.Random(3)
        for e in self.ents:
            for _ in range(5):
                call = pg.make_call(e, rng)
                self.assertTrue(re.fullmatch(r"[A-Z0-9]{3,9}", call), call)
                self.assertTrue(any(re.match("^" + p.replace("#", "[0-9]"), call)
                                    for p in e.patterns), (e.name, call))

    def test_question(self):
        rng = random.Random(4)
        p = pg.pool(self.ents, "OM", "1", rng)
        used = set()
        q = pg.question(p, used, rng)
        self.assertEqual(len(q.options), 3)
        self.assertEqual(len({e.dxcc for e in q.options}), 3)
        self.assertIn(q.options[q.right].dxcc, used)


class Timers:
    """Instead of the asyncio loop: the tests fire the timers."""

    def __init__(self):
        self.pending = []

    def __call__(self, delay, fn):
        h = Handle(fn)
        self.pending.append(h)
        return h

    def fire(self):
        live = [h for h in self.pending if not h.cancelled]
        self.pending = []
        for h in live:
            h.fn()


class Handle:
    def __init__(self, fn):
        self.fn, self.cancelled = fn, False

    def cancel(self):
        self.cancelled = True


class BoardTests(unittest.TestCase):
    def setUp(self):
        self.app = chat_app()
        box._games.clear()
        self.timers = Timers()
        box.schedule = self.timers
        box.rng_factory = lambda: random.Random(7)

    def tearDown(self):
        box.schedule = box._later
        box.rng_factory = random.Random
        box._games.clear()

    def client(self, call):
        s, t = login(self.app, call)
        type_lines(s, "//CLIENT TB1 caps=CHAT,NUM,PR", "C TREFF")
        t.take()
        return s, t

    def terminal(self, call):
        s, t = login(self.app, call)
        type_lines(s, "C TREFF")
        t.take()
        return s, t

    @staticmethod
    def events(t):
        return [x.split(" ", 1)[1][4:] for x in t.take().replace("\n", "").split("\r")
                if re.match(r"^#[0-9A-F]{1,2} !PR ", x)]

    def test_a_whole_game(self):
        a, ta = self.client("OE3GAS")
        b, tb = self.client("OE3TEC")
        w, tw = self.client("OE1XYZ")                       # only watches
        type_lines(a, "//PR START s=OM r=12 n=2")
        self.assertIn("//PR OK START", ta.take())
        ev = self.events(tw)
        self.assertTrue(ev[0].startswith("OPEN OE3GAS OM R12 2 215 60"), ev)
        type_lines(b, "mit")                                 # the chat word joins
        self.assertEqual(self.events(tw), ["IN OE3TEC"])
        self.timers.fire()                                   # signup over
        ev = self.events(tw)
        self.assertEqual(ev[0], "GO OE3GAS OE3TEC")
        q = ev[1].split(" ", 4)
        self.assertEqual(q[0:2], ["Q", "1/2"])
        self.assertEqual(q[3], "30")
        g = box.game_in("TREFF")
        right = "ABC"[g.q.right]
        wrong = "ABC"[(g.q.right + 1) % 3]
        type_lines(a, f"//PR {right}")
        self.assertIn(f"//PR OK TIP 1 {right}", ta.take())
        self.assertEqual(self.events(tw), ["TIP OE3GAS"])    # without the letter
        type_lines(w, "//PR A")                              # a watcher: no tip
        self.assertIn("//PR ERR not_player", tw.take())
        type_lines(b, f"//PR {wrong}")                       # all tipped: the answer at once
        ev = self.events(tw)
        self.assertEqual(ev[0], "TIP OE3TEC")
        self.assertEqual(ev[1], f"RES 1 {right} 1/2 OE3GAS=1+ OE3TEC=0")
        self.timers.fire()                                   # the pause: question 2
        ev = self.events(tw)
        self.assertTrue(ev[0].startswith("Q 2/2 "))
        self.timers.fire()                                   # nobody tips: time is up
        ev = self.events(tw)
        self.assertTrue(ev[0].startswith("RES 2 "))
        self.assertEqual(ev[1], "END OE3GAS=1/2 OE3TEC=0/2")
        self.assertEqual(ev[2], "ALL OE3GAS=1/100 OE3TEC=1/0")     # CR126: games/quote (right of the tips)
        self.assertIsNone(box.game_in("TREFF"))

    def test_terminal_plays_and_reads_text(self):
        a, ta = self.terminal("OE3GAS")
        type_lines(a, "/PR START s=NC r=1 n=1")
        out = ta.take()
        self.assertIn("Prefix raten: OE3GAS starts Newcomer, IARU R1, 1 calls from 79", out)
        self.timers.fire()
        out = ta.take()
        self.assertIn("Prefix raten 1/1:", out)
        g = box.game_in("TREFF")
        type_lines(a, "/PR " + "ABC"[g.q.right])
        out = ta.take()
        self.assertIn("Tip", out)
        self.assertIn("Prefix raten over: OE3GAS 1/1 - winner OE3GAS", out)

    def test_errors_and_stop(self):
        a, ta = self.client("OE3GAS")
        b, tb = self.client("OE3TEC")
        type_lines(b, "//PR A")
        self.assertIn("//PR ERR no_game", tb.take())
        type_lines(a, "//PR START s=XX")
        self.assertIn("//PR ERR bad", ta.take())
        type_lines(a, "//PR START s=PRO r=2 n=5")
        ta.take()
        type_lines(b, "//PR START s=OM")
        self.assertIn("//PR ERR busy", tb.take())
        type_lines(b, "//PR STOP")
        self.assertIn("//PR ERR not_starter", tb.take())
        type_lines(a, "//PR STOP")
        self.assertIn("STOP by OE3GAS", self.events(tb)[0])
        self.assertIsNone(box.game_in("TREFF"))

    def test_starter_ends_the_signup(self):                  # CR124
        a, ta = self.client("OE3GAS")
        b, tb = self.client("OE3TEC")
        type_lines(a, "//PR START s=OM r=1 n=2")
        type_lines(b, "//PR JOIN")
        tb.take()
        type_lines(b, "//PR GO")
        self.assertIn("//PR ERR not_starter", tb.take())
        type_lines(a, "//PR GO")
        self.assertIn("//PR OK GO", ta.take())
        ev = self.events(tb)
        self.assertEqual(ev[0], "GO OE3GAS OE3TEC")
        self.assertTrue(ev[1].startswith("Q 1/2 "))
        self.assertEqual(box.game_in("TREFF").phase, "ask")
        type_lines(a, "//PR GO")
        self.assertIn("//PR ERR not_open", ta.take())
        self.timers.fire()                                   # only the question timer was left
        self.assertTrue(self.events(tb)[0].startswith("RES 1 "))

    def test_late_join_and_leaving(self):
        a, ta = self.client("OE3GAS")
        b, tb = self.client("OE3TEC")
        type_lines(a, "//PR START s=OM r=1 n=3")
        self.timers.fire()                                   # only OE3GAS plays
        type_lines(b, "//PR JOIN")                           # during question 1
        self.assertIn("//PR OK JOIN", tb.take())
        type_lines(b, "//PR A")
        self.assertIn("//PR ERR late", tb.take())            # from the next call on
        type_lines(a, "/Q")                                  # the only player of question 1 goes
        self.timers.fire()                                   # time up, the answer
        self.timers.fire()                                   # question 2 - OE3TEC plays now
        g = box.game_in("TREFF")
        self.assertEqual(g.k, 2)
        type_lines(b, "//PR B")                              # the only player left: answer
        self.assertTrue(any(e.startswith("RES 2 B") or e.startswith("RES 2 ")
                            for e in self.events(tb)))
        type_lines(b, "/Q")
        self.timers.fire()                                   # nobody left in the board
        self.assertIsNone(box.game_in("TREFF"))


if __name__ == "__main__":
    unittest.main()


class ClientTests(unittest.TestCase):
    """tbclient/prefixgame.py takes the events of a real game in the box."""

    def test_client_follows_a_game(self):
        from tbclient.prefixgame import PrefixGame
        app = chat_app()
        box._games.clear()
        timers = Timers()
        box.schedule, box.rng_factory = timers, (lambda: random.Random(9))
        try:
            sent = []
            s, t = login(app, "OE3GAS")
            type_lines(s, "//CLIENT TB1 caps=CHAT,NUM,PR", "C TREFF")
            t.take()
            pg_ = PrefixGame(sent.append, lambda: "OE3GAS")

            def feed(now=1000.0):
                for x in t.take().replace("\n", "").split("\r"):
                    m = re.match(r"^#[0-9A-F]{1,2} !(PR .*)$", x)
                    if m:
                        self.assertTrue(pg_.event(m.group(1), now))
                    elif x.startswith("//PR "):
                        pg_.answer(x[5:])

            self.assertTrue(pg_.act("go"))
            self.assertEqual(sent[-1], "//PR GO")
            self.assertTrue(pg_.act("start", "PRO 2 2"))
            self.assertEqual(sent[-1], "//PR START s=PRO r=2 n=2 t=30")
            type_lines(s, sent[-1])
            feed()
            g = pg_.summary(1000.0)
            self.assertEqual((g["phase"], g["stage"], g["regions"], g["entities"], g["secs"]),
                             ("signup", "PRO", "2", 50, 60))
            self.assertTrue(g["me_plays"] and g["me_starter"])
            timers.fire()
            feed(1001.0)
            g = pg_.summary(1001.0)
            self.assertEqual(g["phase"], "ask")
            self.assertEqual(len(g["q"]["options"]), 3)
            self.assertEqual(g["q"]["until"], 1031.0)
            right = "ABC"[box.game_in("TREFF").q.right]
            self.assertTrue(pg_.act("tip", right))
            self.assertFalse(pg_.act("tip", right))             # one tip per call
            type_lines(s, sent[-1])
            feed()
            g = pg_.summary(1002.0)
            self.assertEqual(g["phase"], "wait")
            self.assertEqual(g["mytip"], right)
            self.assertEqual(g["res"]["right"], ["OE3GAS"])
            timers.fire()
            feed()
            timers.fire()                                      # question 2 runs out
            feed(1100.0)
            g = pg_.summary(1100.0)
            self.assertEqual(g["phase"], "over")
            self.assertEqual(g["winners"], ["OE3GAS"])
            self.assertIsNone(pg_.summary(1100.0 + 16 * 60))     # gone after a while
        finally:
            box.schedule, box.rng_factory = box._later, random.Random
            box._games.clear()
