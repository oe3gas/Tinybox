"""CR127: results of chess and CQ contest, signed by both players, into the scores."""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from prcore import auth
from tinybox import clientproto, gamereport, games

from tests.test_tinybox import login, make_app, type_lines


class BoxTests(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(clientproto, "REQUIRE_AUTH", True)
        p.start()
        self.addCleanup(p.stop)
        self.app = make_app()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.box = self.app.cfg.station.mailbox_call
        self.keys, self.ctr = {}, {}

    def logon(self, call):
        key = auth.Identity(Path(self.tmp.name) / f"{call}.key")
        self.keys[call] = key
        self.app.store.key_put(auth.base(call), key.pub, "active")
        s, t = login(self.app, call)
        type_lines(s, "//CLIENT TB1 v=2026.11.13 caps=CHAT,SYNC,GAME,GAMES")
        n = t.take().split("//AUTH? n=", 1)[1].split()[0]
        type_lines(s, f"//AUTH sig={key.sign_login(self.box, call, n)} pub={key.pub}")
        t.take()
        s._n = n
        self.ctr[call] = 0
        return s, t

    def res(self, s, call, gid="0123456789abcdef", vs="OE3TEC", r="win", h="aaaabbbbccccdddd",
            n=40, t=None, game="chess"):
        self.ctr[call] += 1
        line = f"//GAME RES g={game} id={gid} vs={vs} r={r} h={h} n={n} t={t or int(time.time())}"
        sig = self.keys[call].sign_command(self.box, call, s._n, self.ctr[call], line)
        type_lines(s, f"{line} c={self.ctr[call]} sig={sig}")

    def test_both_report_then_it_counts(self):
        a, ta = self.logon("OE3GAS")
        b, tb = self.logon("OE3TEC")
        t = int(time.time())
        self.res(a, "OE3GAS", vs="OE3TEC-7", r="win", t=t)
        self.assertIn("//GAME OK 0123456789abcdef pending", ta.take())
        self.assertEqual(self.app.store.game_total("chess"), 0)
        self.res(b, "OE3TEC", vs="OE3GAS", r="loss", t=t + 30)
        self.assertIn("//GAME OK 0123456789abcdef counted", tb.take())
        q = {r["call"]: (r["games"], r["wins"]) for r in games.ranked(self.app.store, "chess")}
        self.assertEqual(q, {"OE3GAS": (1, 1), "OE3TEC": (1, 0)})
        type_lines(a, "//GAME ST 0123456789abcdef")
        self.assertIn("//GAME OK 0123456789abcdef counted", ta.take())
        self.res(a, "OE3GAS", vs="OE3TEC-7", r="win", t=t)              # the same again
        self.assertIn("counted", ta.take())
        self.assertEqual(self.app.store.game_total("chess"), 1)

    def test_draw_and_contest(self):
        a, ta = self.logon("OE3GAS")
        b, tb = self.logon("OE3TEC")
        self.res(a, "OE3GAS", r="draw", game="contest")
        self.res(b, "OE3TEC", vs="OE3GAS", r="draw", game="contest")
        self.assertIn("counted", tb.take())
        self.assertEqual({r["call"]: r["draws"] for r in self.app.store.game_rows("contest")},
                         {"OE3GAS": 1, "OE3TEC": 1})

    def test_a_joke_does_not_count(self):
        a, ta = self.logon("OE3GAS")
        b, tb = self.logon("OE3TEC")
        self.res(a, "OE3GAS", r="win")
        with self.assertLogs("tinybox.gamereport", "WARNING"):
            self.res(b, "OE3TEC", vs="OE3GAS", r="win")                   # both say they won
        self.assertIn("//GAME ERR 0123456789abcdef mismatch", tb.take())
        self.assertEqual(self.app.store.game_total("chess"), 0)
        self.assertIn("not counted: chess", "\n".join(games.console(self.app.store, "")))
        type_lines(a, "//GAME ST 0123456789abcdef")
        self.assertIn("//GAME ERR 0123456789abcdef mismatch", ta.take())

    def test_other_hash_or_moves_or_time(self):
        a, ta = self.logon("OE3GAS")
        b, tb = self.logon("OE3TEC")
        t = int(time.time())
        for i, kw in enumerate(({"h": "ffffffffffffffff"}, {"n": 41}, {"t": t - 3600})):
            gid = f"{i:016x}"
            self.res(a, "OE3GAS", gid=gid, t=t)
            with self.assertLogs("tinybox.gamereport", "WARNING"):
                self.res(b, "OE3TEC", gid=gid, vs="OE3GAS", r="loss", **({"t": t} | kw))
            self.assertIn("mismatch", tb.take())

    def test_unsigned_self_old_limit(self):
        a, ta = self.logon("OE3GAS")
        with self.assertLogs("tinybox.clientproto", "WARNING"):
            type_lines(a, f"//GAME RES g=chess id=0123456789abcdef vs=OE3TEC r=win "
                          f"h=aaaabbbbccccdddd n=4 t={int(time.time())}")
        self.assertIn("//GAME ERR 0123456789abcdef unsigned", ta.take())
        self.res(a, "OE3GAS", vs="OE3GAS-5")
        self.assertIn("self", ta.take())
        self.res(a, "OE3GAS", gid="1111111111111111", t=int(time.time()) - 8 * 86400)
        self.assertIn("old", ta.take())
        b, tb = self.logon("OE3TEC")
        with mock.patch.object(gamereport, "PAIR_DAY", 1):
            for gid, want in (("2222222222222222", "counted"), ("3333333333333333", "limit")):
                self.res(a, "OE3GAS", gid=gid)
                self.res(b, "OE3TEC", gid=gid, vs="OE3GAS", r="loss")
                self.assertIn(want, tb.take())

    def test_without_key_nothing(self):
        clientproto.REQUIRE_AUTH = False                    # an older login without a key
        s, t = login(self.app, "OE1ABC")
        type_lines(s, "//CLIENT TB1 caps=CHAT,GAME")
        t.take()
        type_lines(s, f"//GAME RES g=chess id=0123456789abcdef vs=OE3TEC r=win h=aaaabbbbccccdddd "
                      f"n=4 t={int(time.time())}")
        self.assertIn("//GAME ERR 0123456789abcdef nokey", t.take())

    def test_pending_expires(self):
        a, ta = self.logon("OE3GAS")
        self.res(a, "OE3GAS")
        ta.take()
        self.app.store.report_expire("2999-01-01T00:00:00Z")
        type_lines(a, "//GAME ST 0123456789abcdef")
        self.assertIn("//GAME ERR 0123456789abcdef expired", ta.take())


class ClientTests(unittest.TestCase):
    def test_hashes_are_the_same_on_both_sides(self):
        from tbclient import gamereport as cg
        self.assertEqual(cg.chess_hash(["e2e4", "e7e5"]), cg.chess_hash(["e2e4", "e7e5"]))
        self.assertNotEqual(cg.chess_hash(["e2e4"]), cg.chess_hash(["d2d4"]))
        a = {"first": True, "hm": "H1", "ht": "H2", "mc": [["A1", "QSO"], ["B2", "-"]], "tc": [["C3", "-"]]}
        b = {"first": False, "hm": "H2", "ht": "H1", "mc": [["C3", "-"]], "tc": [["A1", "QSO"], ["B2", "-"]]}
        self.assertEqual(cg.contest_hash(a), cg.contest_hash(b))
        self.assertEqual(cg.contest_hash(a)[1], 3)

    def test_reports_queue_flush_answer(self):
        from tbclient.gamereport import Reports

        class Core:
            def __init__(self):
                self.settings, self.state, self.caps, self.at_home = {}, "offline", set(), True
                self.sent, self.peerchat = [], None

            def _save_settings(self): pass
            def _touch(self): pass
            def _send(self, line): self.sent.append(line)
            def signed(self, line): return line + " c=1 sig=x"

        core = Core()
        rp = Reports(core)
        rp.add("chess", "0123456789abcdef", "OE3TEC-7", "win", "aaaabbbbccccdddd", 30)
        self.assertEqual(core.sent, [])                                   # offline: waits
        core.state, core.caps = "online", {"GAME"}
        rp.on_login()
        self.assertTrue(core.sent[0].startswith("//GAME RES g=chess id=0123456789abcdef vs=OE3TEC-7 r=win"))
        self.assertTrue(core.sent[0].endswith("c=1 sig=x"))
        rp.answer("OK 0123456789abcdef pending")
        rp.on_login()
        self.assertEqual(core.sent[-1], "//GAME ST 0123456789abcdef")
        rp.answer("OK 0123456789abcdef counted")
        self.assertEqual(rp.summary(), {"counted": 1, "waiting": 0, "not": 0})
        rp.add("chess", "", "OE3TEC", "win", "x", 1)                      # no id: nothing
        self.assertEqual(len(rp.items), 1)


if __name__ == "__main__":
    unittest.main()
