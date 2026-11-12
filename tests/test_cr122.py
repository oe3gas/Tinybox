"""CR122: CQ contest - the rules, the TinyBox as the opponent, the client slot."""

from __future__ import annotations

import random
import unittest

from prcore import contest as C
from tbclient.contest import ContestSlot
from tinybox import contest as boxcontest
from tests.test_chat import chat_app
from tests.test_tinybox import login, type_lines


def pair(hints=True, seed=1):
    rng = random.Random(seed)
    a = C.Game(C.new_state("JN88", hints, True, "B"), rng)
    b = C.Game(C.new_state("JN88", hints, False, "A"), rng)
    return a, b


def deliver(a, b, to, lines):
    """Deliver lines (to "a" or "b") back and forth until nothing is left."""
    q = [(to, x) for x in lines]
    while q:
        to, line = q.pop(0)
        g, other = (b, "a") if to == "b" else (a, "b")
        q += [(other, x) for x in g.take(line)]


def run(a, b, lines_to_b):
    deliver(a, b, "b", lines_to_b)


def start(a, b):
    a.random_place()
    b.random_place()
    deliver(a, b, "b", a.set_ready())
    deliver(a, b, "a", b.set_ready())


def play(a, b):
    start(a, b)
    for _ in range(200):
        g = a if a.my_turn() else b if b.my_turn() else None
        if g is None:
            break
        deliver(a, b, "b" if g is a else "a", g.cq(g.pick()))


class RulesTests(unittest.TestCase):
    def test_board_around_jn88(self):
        b = C.squares("JN88")
        self.assertEqual(len(b), 64)
        self.assertEqual(b[27], "JN88")
        self.assertEqual(b[0], "JO51")
        self.assertEqual(b[63], "KN24")
        self.assertEqual(C.label("JN88"), "OE3")
        self.assertEqual(C.label("KN08"), "OM")
        self.assertEqual(C.squares("XX99"), [])

    def test_callsigns_4_to_5(self):
        rng = random.Random(3)
        for loc in C.squares("JN88"):
            for _ in range(20):
                call = C.callsign(loc, rng)
                self.assertTrue(4 <= len(call) <= 5, call)
                self.assertTrue(any(ch.isdigit() for ch in call), call)
        self.assertTrue(C.callsign("JN77", rng).startswith("OE6"))

    def test_hint_and_answer(self):
        board = C.squares("JN88")
        st = {"JN88": "OE3A"}
        self.assertEqual(C.answer(st, board, True, "JN88"), "OE3A")
        self.assertEqual(C.answer(st, board, True, "JN98"), "WEAK")
        self.assertEqual(C.answer(st, board, False, "JN98"), "NIL")
        self.assertEqual(C.answer(st, board, True, "KN28"), "NIL")

    def test_full_games_end_and_check(self):
        for seed in range(30):
            a, b = pair(hints=seed % 2 == 0, seed=seed)
            play(a, b)
            self.assertEqual(a.s["st"], "end")
            self.assertEqual(b.s["st"], "end")
            self.assertEqual({a.s["res"], b.s["res"]} in ({"win", "loss"}, {"draw"}), True)
            self.assertEqual((a.s["check"], b.s["check"]), ("ok", "ok"))
            self.assertEqual(len(a.s["mc"]), len(b.s["mc"]))      # the round played out

    def test_turns(self):
        a, b = pair()
        a.random_place()
        b.random_place()
        self.assertEqual(a.cq("JN88"), [])                         # not started yet
        for line in a.set_ready():
            b.take(line)
        for line in b.set_ready():
            a.take(line)
        self.assertTrue(a.my_turn())
        self.assertFalse(b.my_turn())
        self.assertEqual(b.cq("JN88"), [])
        self.assertEqual(a.take("CQ JN88"), [])                    # b calls out of turn: ignored
        out = a.cq("JN88")
        self.assertEqual(out, ["CQ JN88"])
        self.assertFalse(a.my_turn())
        for line in b.take(out[0]):
            a.take(line)
        self.assertTrue(b.my_turn())

    def test_cheating_found(self):
        a, b = pair(hints=False, seed=5)
        a.random_place()
        b.random_place()
        for line in a.set_ready():
            b.take(line)
        for line in b.set_ready():
            a.take(line)
        loc = next(iter(b.s["me"]))
        a.cq(loc)
        a.take(f"R {loc} NIL")                 # b's client lies: "no answer"
        b.s["tc"].append([loc, "NIL"])
        b.resign()
        run(a, b, [])
        a.take(f"END {C.placement_text(b.s['me'])} {b.s['salt']}")
        self.assertEqual(a.s["check"], "bad")

    def test_resign_reveals(self):
        a, b = pair()
        a.random_place()
        b.random_place()
        for line in a.set_ready():
            b.take(line)
        for line in b.set_ready():
            a.take(line)
        out = a.resign()
        self.assertEqual(out[0], "RESIGN")
        self.assertTrue(out[1].startswith("END "))
        back = []
        for line in out:
            back += b.take(line)
        self.assertEqual(b.s["res"], "they resigned")
        self.assertTrue(back and back[0].startswith("END "))
        a.take(back[0])
        self.assertEqual((a.s["check"], b.s["check"]), ("ok", "ok"))


class BoxTests(unittest.TestCase):
    def setUp(self):
        self.app = chat_app()
        self.app.cfg.station.locator = "JN88IN"
        boxcontest._games.clear()

    def client(self, call):
        s, t = login(self.app, call)
        type_lines(s, "//CLIENT TB1 caps=CHAT,CT")
        self.assertIn("CT", t.take())
        return s, t

    @staticmethod
    def lines(t):
        return [x[5:] for x in t.take().split("\r") if x.startswith("//CT ")]

    def test_box_plays_a_whole_game(self):
        s, t = self.client("OE3ABC")
        type_lines(s, "//CT NEW h=1")
        out = self.lines(t)
        self.assertEqual(out[0], "OK c=JN88 h=1")
        me = C.Game(C.new_state("", True, True, "BOX"))
        me.take(out[0])
        self.assertEqual(me.s["c"], "JN88")
        me.take(out[1])                                        # READY of the box
        me.random_place()
        type_lines(s, "//CT " + me.set_ready()[0])
        self.assertEqual(self.lines(t), [])
        self.assertEqual(me.s["st"], "play")
        for _ in range(100):
            if me.s["st"] == "end":
                break
            self.assertTrue(me.my_turn())
            type_lines(s, "//CT " + me.cq(me.pick())[0])
            for line in self.lines(t):                         # R, then the box's CQ
                for back in me.take(line):
                    type_lines(s, "//CT " + back)
            # answers to the box's call may end it: the box lays open
            for line in self.lines(t):
                me.take(line)
        self.assertEqual(me.s["st"], "end")
        self.assertEqual(me.s["check"], "ok")
        self.assertNotIn("OE3ABC", boxcontest._games)          # done: forgotten

    def test_two_games_at_once_and_no_locator(self):
        s1, t1 = self.client("OE3ABC")
        s2, t2 = self.client("OE1XYZ")
        type_lines(s1, "//CT NEW h=0")
        type_lines(s2, "//CT NEW h=1")
        self.assertIn("OK c=JN88 h=0", self.lines(t1))
        self.assertIn("OK c=JN88 h=1", self.lines(t2))
        self.assertEqual(set(boxcontest._games), {"OE3ABC", "OE1XYZ"})
        self.app.cfg.station.locator = ""
        type_lines(s1, "//CT NEW h=1")
        self.assertIn("ERR no_locator", self.lines(t1))

    def test_needs_cap(self):
        s, t = login(self.app, "OE3ABC")
        type_lines(s, "//CLIENT TB1 caps=CHAT")
        t.take()
        type_lines(s, "//CT NEW h=1")
        self.assertIn("//ERR CT needs CT", t.take())


class FakeProfiles:
    def __init__(self, loc):
        self.loc = loc

    @property
    def mine(self):
        return {"loc": self.loc}


class FakeCore:
    def __init__(self, loc):
        self.settings = {}
        self.profiles = FakeProfiles(loc)
        self.cfg = type("Cfg", (), {"locator": ""})()

    def _save_settings(self):
        pass

    def _touch(self):
        pass


class SlotTests(unittest.TestCase):
    def test_two_clients(self):
        ca, cb = FakeCore("JN88IP"), FakeCore("JN78")
        q: list[tuple[str, str]] = []
        notes = []
        a = ContestSlot(ca, lambda: "OE3B", lambda: "OE3B", lambda line: q.append(("b", line)),
                        lambda: "JN88", notes.append)
        b = ContestSlot(cb, lambda: "OE3A", lambda: "OE3A", lambda line: q.append(("a", line)),
                        lambda: "JN78", notes.append)

        def flush():
            while q:
                to, line = q.pop(0)
                self.assertTrue(line.startswith("//CT "))
                (a if to == "a" else b).take(line[5:])

        self.assertTrue(a.act("new", "1"))
        flush()
        self.assertEqual(b.state["c"], "JN88")                 # the inviter's square
        self.assertFalse(b.state["first"])
        a.act("random")
        b.act("random")
        self.assertTrue(a.act("ready"))
        self.assertTrue(b.act("ready"))
        flush()
        self.assertEqual(a.state["st"], "play")
        for _ in range(200):
            if a.state["st"] == "end" and b.state["st"] == "end":
                break
            for slot in (a, b):
                g = C.Game(slot.state)
                if g.my_turn():
                    self.assertTrue(slot.act("cq", g.pick()))
                    flush()
        self.assertEqual((a.state["check"], b.state["check"]), ("ok", "ok"))
        self.assertTrue(any("CQ contest:" in n for n in notes))
        summ = a.summary()
        self.assertEqual(len(summ["cells"]), 64)
        self.assertTrue(a.act("close"))
        self.assertIsNone(a.state)


if __name__ == "__main__":
    unittest.main()
