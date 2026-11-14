"""tinybox/boardgame.py: the frame of the board games (Refactoring R3) - with a tiny
quiz of its own, so the frame is tested apart from Prefix raten."""

from __future__ import annotations

import re
import unittest
from types import SimpleNamespace

from tinybox import boardgame, games
from tests.test_chat import chat_app
from tests.test_cr123 import Timers
from tests.test_tinybox import login, type_lines


class TinyQuiz(boardgame.QuizGame):
    EVENT, TITLE, STORE = "TQ", "Tiny quiz", "tinyquiz"

    def open_event(self):
        return f"OPEN {self.starter} {self.calls}", f"Tiny quiz by {self.starter}"

    def next_question(self):
        return SimpleNamespace(options=["one", "two", "three"], right=1)

    def question_event(self):
        return "one|two|three", "Which is two?"

    def answer_text(self):
        return "B two"


class QuizFrame(unittest.TestCase):
    def setUp(self):
        self.app = chat_app()
        boardgame.GAMES.clear()
        self.timers = Timers()
        boardgame.schedule = self.timers

    def tearDown(self):
        boardgame.schedule = boardgame._later
        boardgame.GAMES.clear()

    def member(self, call):
        s, t = login(self.app, call)
        type_lines(s, "//CLIENT TB1 caps=CHAT,NUM", "C TREFF")
        t.take()
        return s, t

    @staticmethod
    def events(t):
        return [x.split(" ", 1)[1][4:] for x in t.take().replace("\n", "").split("\r")
                if re.match(r"^#[0-9A-F]{1,2} !TQ ", x)]

    def test_a_whole_quiz_and_its_record(self):
        a, ta = self.member("OE3GAS")
        b, tb = self.member("OE3TEC")
        g = TinyQuiz(self.app.service.chat, "TREFF", "OE3GAS", calls=2, tip_sec=10)
        g.open()
        self.assertIs(boardgame.game_in("TREFF"), g)        # one game per board
        self.assertEqual(g.join("OE3TEC"), "")
        self.assertEqual(g.join("OE3TEC"), "twice")
        self.timers.fire()                                   # signup over -> question 1
        ev = self.events(tb)
        self.assertEqual(ev[:3], ["OPEN OE3GAS 2", "IN OE3TEC", "GO OE3GAS OE3TEC"])
        self.assertEqual(ev[3], "Q 1/2 one|two|three")
        self.assertEqual(g.tip("OE3GAS", "B"), "")
        self.assertEqual(g.tip("OE3GAS", "B"), "twice")
        self.assertEqual(g.tip("OE3TEC", "A"), "")          # all tipped: the answer
        self.assertIn("RES 1 B 1/2 OE3GAS=1+ OE3TEC=0", self.events(tb)[-1])
        self.timers.fire()                                   # pause -> question 2
        g.tip("OE3GAS", "B")
        g.tip("OE3TEC", "B")
        ev = self.events(tb)
        self.assertTrue(any(e.startswith("END OE3GAS=2/2 OE3TEC=1/2") for e in ev), ev)
        self.assertIsNone(boardgame.game_in("TREFF"))
        rows = {r["call"]: r for r in games.ranked(self.app.service.store, "tinyquiz")}
        self.assertEqual(rows["OE3GAS"]["games"], 1)

    def test_stop_frees_the_board(self):
        self.member("OE3GAS")
        g = TinyQuiz(self.app.service.chat, "TREFF", "OE3GAS", calls=1, tip_sec=10)
        g.open()
        g.stop("by OE3GAS")
        self.assertIsNone(boardgame.game_in("TREFF"))
        self.assertIsNone(g.timer)


if __name__ == "__main__":
    unittest.main()
