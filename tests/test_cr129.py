"""CR129: the language of the games - the box gives it, every client may choose its own;
Prefix raten sends DXCC numbers, the client shows the names."""

from __future__ import annotations

import random
import unittest

from prcore import prefixgame as pg
from tbclient.prefixgame import PrefixGame
from tinybox import boardgame
from tinybox import prefixgame as box
from tests.test_chat import chat_app
from tests.test_tinybox import login, type_lines


class ListTests(unittest.TestCase):
    def test_every_entity_has_both_names(self):
        for e in pg.load():
            self.assertTrue(e.name and e.name_de, e.dxcc)
        d = pg.by_dxcc()
        self.assertEqual((d[230].name_in("de"), d[230].name_in("en")),
                         ("Deutschland", "Germany (Federal Rep of)"))
        self.assertEqual(pg.label(d[210], "OM", "de"), "Saarland (alt)")   # deleted: marked


class BoxTests(unittest.TestCase):
    def setUp(self):
        self.app = chat_app()
        boardgame.GAMES.clear()
        self.pending = []
        boardgame.schedule = lambda delay, fn: self.pending.append(fn)
        box.rng_factory = lambda: random.Random(3)

    def tearDown(self):
        boardgame.schedule = boardgame._later
        box.rng_factory = random.Random
        boardgame.GAMES.clear()

    def test_ok_tells_the_language(self):
        s, t = login(self.app, "OE3GAS")
        type_lines(s, "//CLIENT TB1 caps=CHAT")
        self.assertIn(" lang=de", t.take())
        self.app.cfg.games.language = "en"
        s, t = login(self.app, "OE3TEC")
        type_lines(s, "//CLIENT TB1 caps=CHAT")
        self.assertIn(" lang=en", t.take())

    def test_question_carries_dxcc_numbers(self):
        s, t = login(self.app, "OE3GAS")
        type_lines(s, "//CLIENT TB1 caps=CHAT,NUM,PR", "C TREFF", "//PR START s=OM r=1 n=1")
        t.take()
        self.pending.pop()()                               # signup over: the question
        q = [x for x in t.take().split("\r") if " !PR Q " in x][0]
        opts = q.rsplit(" ", 1)[1].split("|")
        self.assertEqual(len(opts), 3)
        self.assertTrue(all(o.isdigit() for o in opts), q)
        g = box.game_in("TREFF")
        self.assertEqual([int(o) for o in opts], [e.dxcc for e in g.q.options])


class ClientTests(unittest.TestCase):
    def game(self, lang):
        g = PrefixGame(lambda line: None, lambda: "OE3GAS", lambda: lang)
        g.event("PR OPEN OE3GAS OM R1 1 100 60 30", now=0)
        g.event("PR GO OE3GAS", now=0)
        g.event("PR Q 1/1 DL1ABC 30 230|206|281", now=0)
        return g

    def test_names_in_the_own_language(self):
        self.assertEqual(self.game("de").summary(now=1)["q"]["options"],
                         ["Deutschland", "Österreich", "Spanien"])
        self.assertEqual(self.game("en").summary(now=1)["q"]["options"],
                         ["Germany (Federal Rep of)", "Austria", "Spain"])

    def test_log_follows_the_language_and_unknown_number(self):
        g = self.game("de")
        g.event("PR RES 1 A 1/1 OE3GAS=1+", now=2)
        self.assertEqual(g.summary(now=3)["log"][0]["name"], "Deutschland")
        g.event("PR Q 1/1 X1X 30 9999|230|206", now=4)
        self.assertEqual(g.summary(now=5)["q"]["options"][0], "DXCC 9999")


class ClientLanguageTests(unittest.TestCase):
    def test_own_setting_then_the_box_then_english(self):
        from types import SimpleNamespace
        from tbclient.core import ClientCore
        core = SimpleNamespace(cfg=SimpleNamespace(game_lang=""), settings={})
        f = ClientCore.game_lang
        self.assertEqual(f(core), "en")
        core.settings["box_lang"] = "de"
        self.assertEqual(f(core), "de")
        core.cfg.game_lang = "en"
        self.assertEqual(f(core), "en")


if __name__ == "__main__":
    unittest.main()
