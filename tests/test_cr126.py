"""CR126: tip time, results per call, the scores of the games and the leaderboards."""

from __future__ import annotations

import random
import re
import unittest

from tinybox import games
from tinybox import prefixgame as box
from tests.test_chat import chat_app
from tests.test_cr123 import Timers
from tests.test_tinybox import login, type_lines


class ScoreTests(unittest.TestCase):
    def setUp(self):
        self.app = chat_app()
        self.st = self.app.store

    def test_record_quote_and_rank(self):
        games.record(self.st, "prefix", [{"call": "OE3GAS-7", "hits": 8, "tries": 10, "asked": 10, "wins": 1},
                                         {"call": "OE3TEC", "hits": 9, "tries": 10, "asked": 10}])
        games.record(self.st, "prefix", [{"call": "OE3GAS", "hits": 4, "tries": 10, "asked": 10}])
        r = games.ranked(self.st, "prefix")
        self.assertEqual([(x["call"], x["games"], x["quote"]) for x in r],
                         [("OE3TEC", 1, 90), ("OE3GAS", 2, 60)])          # base call, summed
        self.assertEqual(self.st.game_total("prefix"), 2)
        games.record(self.st, "chess", [{"call": "OE1A", "wins": 1}, {"call": "OE1B"}])
        games.record(self.st, "chess", [{"call": "OE1A", "draws": 1}, {"call": "OE1B", "draws": 1}])
        q = {x["call"]: x["quote"] for x in games.ranked(self.st, "chess")}
        self.assertEqual(q, {"OE1A": 75, "OE1B": 25})

    def test_board_lines(self):
        for i in range(12):
            games.record(self.st, "prefix", [{"call": f"OE1A{chr(65 + i)}", "hits": i, "tries": 12}])
        lb1 = games.board(self.st, None, "OE3GAS")
        self.assertEqual(lb1[0], "G prefix 12 12")
        self.assertEqual(lb1[1], "R prefix 1 OE1AL 1 92 11/12")
        self.assertEqual(lb1[4:], ["G contest 0 0", "G chess 0 0", "END"])
        lb2 = games.board(self.st, "prefix", "OE1AA-3")
        self.assertEqual(len([x for x in lb2 if x.startswith("R ")]), 10)
        self.assertEqual(lb2[-2], "ME prefix 12 OE1AA 1 0 0/12")         # own row outside the top 10

    def test_console_clear(self):
        games.record(self.st, "prefix", [{"call": "OE1A", "hits": 1, "tries": 1}, {"call": "OE1B"}])
        games.record(self.st, "chess", [{"call": "OE1A", "wins": 1}])
        out = games.console(self.st, "")
        self.assertIn("prefix", out[0])
        out = games.console(self.st, "CLEAR prefix OE1A")
        self.assertIn("deletes 1 score row(s)", out[0])
        self.assertEqual(out[1], "To do it: GAMES CLEAR prefix OE1A CONFIRM")
        self.assertEqual(len(self.st.game_rows("prefix")), 2)              # only shown
        games.console(self.st, "CLEAR prefix OE1A CONFIRM")
        self.assertEqual([r["call"] for r in self.st.game_rows("prefix")], ["OE1B"])
        self.assertEqual(self.st.game_total("prefix"), 1)                  # one player: counter stays
        games.console(self.st, "CLEAR ALL CONFIRM")
        self.assertEqual(self.st.game_counts(None, None), 0)
        self.assertEqual(self.st.game_total("chess"), 0)
        self.assertIn("Unknown game", games.console(self.st, "CLEAR xyz")[0])

    def test_purge_takes_the_scores(self):
        games.record(self.st, "prefix", [{"call": "OE1A", "hits": 1, "tries": 1}])
        self.assertEqual(self.st.purge_counts("OE1A")["game scores"], 1)


class OnAirTests(unittest.TestCase):
    def setUp(self):
        self.app = chat_app()
        box._games.clear()
        self.timers = Timers()
        box.schedule, box.rng_factory = self.timers, (lambda: random.Random(3))

    def tearDown(self):
        box.schedule, box.rng_factory = box._later, random.Random
        box._games.clear()

    def client(self, call):
        s, t = login(self.app, call)
        type_lines(s, "//CLIENT TB1 caps=CHAT,NUM,PR,GAMES", "C TREFF")
        t.take()
        return s, t

    def test_tip_time_and_scores(self):
        a, ta = self.client("OE3GAS")
        type_lines(a, "//PR START s=OM r=1 n=1 t=4")
        self.assertIn("//PR ERR bad", ta.take())                          # 5 to 30 s
        type_lines(a, "//PR START s=OM r=1 n=1 t=10")
        out = ta.take()
        self.assertIn("!PR OPEN OE3GAS OM R1 1 155 60 10", out)
        type_lines(a, "//PR GO")
        out = ta.take()
        self.assertRegex(out, r"!PR Q 1/1 \S+ 10 ")
        g = box.game_in("TREFF")
        type_lines(a, "//PR " + "ABC"[(g.q.right + 1) % 3])               # wrong
        out = ta.take()
        self.assertRegex(out, r"!PR RES 1 [ABC] 0/1 OE3GAS=0")
        self.assertIn("!PR END OE3GAS=0/1", out)
        self.assertIn("!PR ALL OE3GAS=1/0", out)
        type_lines(a, "//GAMES TOP prefix")
        out = ta.take()
        self.assertIn("//GAMES G prefix 1 1", out)
        self.assertIn("//GAMES R prefix 1 OE3GAS 1 0 0/1", out)
        self.assertIn("//GAMES END", out)
        type_lines(a, "/TOP")
        out = ta.take()
        self.assertIn("Prefix raten: 1 games, 1 players", out)
        self.assertIn("Schach: 0 games, 0 players", out)

    def test_stopped_game_does_not_count(self):
        a, ta = self.client("OE3GAS")
        type_lines(a, "//PR START s=OM r=1 n=3", "//PR GO", "//PR STOP")
        self.assertEqual(self.app.store.game_total("prefix"), 0)


if __name__ == "__main__":
    unittest.main()


class ClientTests(unittest.TestCase):
    def test_leaderboard_and_game_log(self):
        from tbclient.prefixgame import Leaderboard, PrefixGame
        sent = []
        lb = Leaderboard(sent.append)
        lb.ask("prefix")
        self.assertEqual(sent[-1], "//GAMES TOP prefix")
        for x in ["G prefix 4 2", "R prefix 1 OE3TEC 1 90 9/10", "ME prefix 7 OE3GAS 2 60 12/20", "END"]:
            lb.line(x)
        d = lb.summary()["data"]["games"]["prefix"]
        self.assertEqual((d["total"], d["players"], d["rows"][0]["call"], d["me"]["rank"]), (4, 2, "OE3TEC", 7))
        pg = PrefixGame(sent.append, lambda: "OE3GAS")
        self.assertTrue(pg.act("start", "OM 12 10 15"))
        self.assertEqual(sent[-1], "//PR START s=OM r=12 n=10 t=15")
        pg.event("PR OPEN OE3GAS OM R12 10 215 60 15", 100.0)
        pg.event("PR Q 1/10 DL1ABC 15 Germany|Malta|Chile", 101.0)
        pg.event("PR RES 1 A 1/1 OE3GAS=1+", 102.0)
        pg.event("PR END OE3GAS=1/1", 103.0)
        pg.event("PR ALL OE3GAS=3/80", 103.0)
        g = pg.summary(104.0)
        self.assertEqual(g["tip"], 15)
        self.assertEqual(g["log"], [{"k": 1, "call": "DL1ABC", "name": "Germany", "right": 1, "asked": 1}])
        self.assertEqual(g["asked"], {"OE3GAS": 1})
        self.assertEqual(g["totals"], {"OE3GAS": {"games": 3, "quote": 80}})
