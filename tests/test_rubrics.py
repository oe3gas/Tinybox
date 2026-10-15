"""CR19: bulletin rubrics are set by the sysop ([rubrics] in tinybox.conf).

Users, scripts and MQTT write only to ALL and the accepted rubrics, the sysop
is free; forwarding takes accepted rubrics, refuses refused ones and sends a new
rubric to the sysop (first bulletin held + mail, the rest deferred); the client
gets the list with //RUBRICS and offers it in the composer.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tbclient.mailstore import MailStore
from tbclient.sync import parse_rubrics
from tinybox.adapters.brocast import wanted
from tinybox.adapters.forward import ForwardModule
from tinybox.config import Rubric
from tinybox.fwd.protocol import Proposal, parse_sid
from tinybox.fwd.receive import Receiver
from tinybox.service import ServiceError

from fwdsim.protocol import ACCEPT, LATER, REJECT

from tests.test_forward_module import HADDR, fwd_app, gas
from tests import test_forward_receive as _fr
from tests.test_tinybox import login, make_app, type_lines

RUBRICS = [Rubric("ALL", "To everybody"), Rubric("WX", "Weather and warnings"),
           Rubric("CONTEST", "Contests, results"), Rubric("HUMOR", "not wanted", False)]


def bulletin(app, to, origin="telnet", frm="OE1ABC", **kw):
    return app.service.create(from_call=frm, to_call=to, type="B", subject="s", body="b",
                              origin=origin, **kw)


class ServiceRules(unittest.TestCase):
    def setUp(self):
        self.app = make_app()

    def test_without_list_everything_is_free(self):
        self.assertEqual(self.app.cfg.rubrics, [])
        self.assertTrue(bulletin(self.app, "FUCHS"))
        self.assertEqual(self.app.service.writable_rubrics(), [])
        with self.assertRaises(ServiceError) as cm:           # TBNEWS is never for users
            bulletin(self.app, "TBNEWS")
        self.assertEqual(cm.exception.code, "bad_rubric")

    def test_users_only_accepted(self):
        self.app.cfg.rubrics = RUBRICS
        svc = self.app.service
        self.assertTrue(bulletin(self.app, "WX"))
        self.assertTrue(bulletin(self.app, "all"))
        for to in ("FUCHS", "HUMOR", "TBNEWS"):
            with self.assertRaises(ServiceError) as cm:
                bulletin(self.app, to)
            self.assertEqual((cm.exception.code, str(cm.exception)), ("bad_rubric", to))
        self.assertEqual(svc.writable_rubrics(), ["ALL", "WX", "CONTEST"])
        self.assertEqual([svc.rubric_state(x) for x in ("WX", "HUMOR", "XYZ", "TBNEWS", "ALL")],
                         ["accepted", "refused", "unknown", "system", "accepted"])

    def test_all_always_first_and_accepted(self):
        self.app.cfg.rubrics = [Rubric("WX", "W"), Rubric("ALL", "", False)]
        self.assertEqual(self.app.service.writable_rubrics(), ["WX", "ALL"])
        self.app.cfg.rubrics = [Rubric("WX", "W")]
        self.assertEqual(self.app.service.writable_rubrics(), ["ALL", "WX"])
        self.assertTrue(bulletin(self.app, "ALL"))

    def test_sysop_is_free_scripts_are_not(self):
        self.app.cfg.rubrics = RUBRICS
        sysop = self.app.cfg.station.sysop_call
        self.assertTrue(bulletin(self.app, "FUCHS", "sysop", sysop, sysop=True))
        self.assertTrue(bulletin(self.app, "WX", "inbox", sysop, sysop=True))
        for origin in ("inbox", "mqtt"):
            with self.assertRaises(ServiceError):
                bulletin(self.app, "FUCHS", origin, sysop, sysop=True)

    def test_terminal_error_lists_rubrics(self):
        self.app.cfg.rubrics = RUBRICS
        s, t = login(self.app, "OE1ABC")
        t.take()
        type_lines(s, "SB FUCHS")
        self.assertIn("Rubric FUCHS is not open for bulletins here. Rubrics: ALL WX CONTEST",
                      t.take())
        type_lines(s, "SB WX @ WW", "Rain", "Tonight\x1a")
        self.assertIn("saved", t.take())
        sysop, st = login(self.app, self.app.cfg.station.sysop_call)
        st.take()
        type_lines(sysop, "SB FUCHS", "Hunt", "Sunday\x1a")
        self.assertIn("saved", st.take())


class ClientList(unittest.TestCase):
    def test_rubrics_answer(self):
        app = make_app()
        app.cfg.rubrics = RUBRICS
        wx = bulletin(app, "WX")
        s, t = login(app, "OE1ABC")
        t.take()
        type_lines(s, "//CLIENT TB1 caps=SYNC")
        t.take()
        type_lines(s, "//RUBRICS")
        out = t.take()
        self.assertEqual(out.split("\r")[:-1], [
            "//RU ALL 0 0", "//RU CONTEST 0 0", f"//RU WX 1 {wx}",
            "//RU ALL : To everybody", "//RU WX : Weather and warnings",
            "//RU CONTEST : Contests, results", "//RU + ALL WX CONTEST", "//RUEND"])
        rubrics, writable = parse_rubrics(out.split("\r")[:-2])
        self.assertEqual(writable, ["ALL", "WX", "CONTEST"])
        self.assertEqual(rubrics[2], {"name": "WX", "count": 1, "max": wx,
                                      "desc": "Weather and warnings"})

    def test_old_tinybox_and_old_client(self):
        # an old TinyBox: no descriptions, no list -> free field in the composer
        rubrics, writable = parse_rubrics(["//RU ALL 2 5", "//RU WX 1 7"])
        self.assertEqual((len(rubrics), writable, rubrics[0]["desc"]), (2, [], ""))
        # an old client takes only lines with 4 fields and a number
        for line in ("//RU WX : Weather and warnings", "//RU + ALL WX CONTEST",
                     "//RU ALL : To everybody", "//RU + ALL WX"):
            p = line.split()
            self.assertFalse(len(p) == 4 and p[2].isdigit(), line)

    def test_mailstore_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            box = MailStore(Path(tmp) / "m.db", "OE1ABC")
            box.put("rubrics", [{"name": "WX", "count": 1, "max": 3, "desc": "Weather"}])
            box.put("writable", ["ALL", "WX"])
            s = box.summary()
            box.close()
        self.assertEqual(s["writable"], [{"name": "ALL", "desc": ""},
                                         {"name": "WX", "desc": "Weather"}])
        self.assertEqual(s["rubrics"][0]["desc"], "Weather")


class Forwarding(unittest.TestCase):
    def setUp(self):
        self.app = fwd_app(gas())
        self.app.cfg.rubrics = list(RUBRICS)
        self.rx = Receiver(self.app.service, "OE3GAS")
        self.rx.mode = "fbb"

    def prop(self, to, bid, **kw):
        base = dict(kind="FB", type="B", from_call="OE3GAS", at_addr="WW", to_call=to,
                    bid=bid, size=100)
        base.update(kw)
        return Proposal(**base)

    def take(self, p):
        return self.rx.store(p, f"Subject {p.bid}", f"Text of {p.bid}")

    def mails_to_sysop(self):
        return [m for m in self.app.store.list_messages() if m.type == "P"]

    def test_accepted_refused_system(self):
        self.assertEqual(self.rx.answer(self.prop("WX", "1_X")), "+")
        self.assertEqual(self.rx.answer(self.prop("ALL", "2_X")), "+")
        self.assertEqual(self.rx.answer(self.prop("HUMOR", "3_X")), "-")
        self.assertEqual(self.rx.answer(self.prop("TBNEWS", "4_X")), "-")
        self.assertEqual(self.rx.answer(self.prop("OE1ABC", "5_X", type="P",
                                                  at_addr=HADDR)), "+")

    def test_no_list_takes_everything(self):
        self.app.cfg.rubrics = []
        self.assertEqual(self.rx.answer(self.prop("FUCHS", "1_X")), "+")
        self.assertEqual(self.rx.answer(self.prop("TBNEWS", "2_X")), "-")

    def test_new_rubric_first_held_and_mailed_rest_deferred(self):
        a, b = self.prop("FUCHS", "1_X"), self.prop("FUCHS", "2_X")
        self.assertEqual([self.rx.answer(a), self.rx.answer(b)], ["+", "="])   # same block
        held = self.app.store.get(self.take(a))
        self.assertEqual((held.fwd, held.to_call), ("H", "FUCHS"))
        self.assertTrue(held.note.startswith("new rubric FUCHS"))
        self.assertFalse(wanted(held, self.app))                  # not on brocast
        self.app.cfg.forward.publish_to_brocast = True
        self.assertFalse(wanted(held, self.app))
        self.assertNotIn(held.id, [m.id for m in self.app.service.list_for("OE1ABC", False)])
        mails = self.mails_to_sysop()
        self.assertEqual(len(mails), 1)
        m = mails[0]
        self.assertEqual((m.to_call, m.from_call, m.subject),
                         ("OE3XTC", "OE3XTC-1", "New rubric FUCHS offered by OE3GAS"))
        self.assertIn("FUCHS = description", m.body)
        self.assertIn("Text of 1_X", m.body)
        self.assertIn("Subject: Subject 1_X", m.body)
        # next session: still undecided -> deferred, no second mail
        rx2 = Receiver(self.app.service, "OE3GAS")
        rx2.mode = "fbb"
        self.assertEqual(rx2.answer(self.prop("FUCHS", "3_X")), "=")
        # ASCII has no "later": taken and held, no mail
        rx2.mode = "ascii"
        rx2.peer_sid = parse_sid("[X-1-HM$]")
        p = self.prop("FUCHS", "4_X")
        self.assertEqual(rx2.answer(p), "+")
        m4 = self.app.store.get(rx2.store(p, "s", "t"))
        self.assertEqual(m4.fwd, "H")
        self.assertEqual(len(self.mails_to_sysop()), 1)

    def test_sysop_accepts(self):
        self.assertEqual(self.rx.answer(self.prop("FUCHS", "1_X", at_addr="")), "+")
        held = self.take(self.prop("FUCHS", "1_X", at_addr=""))
        self.app.cfg.rubrics.append(Rubric("FUCHS", "Fox hunting"))
        module = ForwardModule(self.app)
        self.assertEqual(module.resolve_rubrics(), (1, 0))
        msg = self.app.store.get(held)
        self.assertEqual((msg.fwd, msg.note), ("", ""))        # local: simply released
        self.assertIn(held, [m.id for m in self.app.service.list_for("OE1ABC", False)])
        rx = Receiver(self.app.service, "OE3GAS")
        rx.mode = "fbb"
        self.assertEqual(rx.answer(self.prop("FUCHS", "2_X")), "+")

    def test_sysop_refuses(self):
        self.rx.answer(self.prop("FUCHS", "1_X"))
        held = self.take(self.prop("FUCHS", "1_X"))
        self.app.cfg.rubrics.append(Rubric("FUCHS", "", False))
        self.assertEqual(ForwardModule(self.app).resolve_rubrics(), (0, 1))
        self.assertIsNone(self.app.store.get(held))
        rx = Receiver(self.app.service, "OE3GAS")
        rx.mode = "fbb"
        self.assertEqual(rx.answer(self.prop("FUCHS", "2_X")), "-")

    def test_undecided_stays_held(self):
        self.rx.answer(self.prop("FUCHS", "1_X"))
        held = self.take(self.prop("FUCHS", "1_X"))
        self.assertEqual(ForwardModule(self.app).resolve_rubrics(), (0, 0))
        self.assertEqual(self.app.store.get(held).fwd, "H")

    def test_sysop_deleted_mail_and_held_bulletin(self):
        """Without a held bulletin, the next offer starts over (new mail)."""
        self.rx.answer(self.prop("FUCHS", "1_X"))
        held = self.take(self.prop("FUCHS", "1_X"))
        self.app.service.delete(held, "OE3XTC", sysop=True)
        rx = Receiver(self.app.service, "OE3GAS")
        rx.mode = "fbb"
        self.assertEqual(rx.answer(self.prop("FUCHS", "2_X")), "+")


class ForwardSessionFbb(unittest.IsolatedAsyncioTestCase):
    """End to end with fwdsim (FBB): accept, refuse, new rubric, defer."""
    asyncSetUp = _fr.ReceiveTests.asyncSetUp
    asyncTearDown = _fr.ReceiveTests.asyncTearDown
    hop_calls = _fr.ReceiveTests.hop_calls
    got = _fr.ReceiveTests.got

    async def test_batch(self):
        self.app.cfg.rubrics = list(RUBRICS)
        wx = self.hop.create("B", "WX", "WW", "Rain", "Text")
        humor = self.hop.create("B", "HUMOR", "WW", "Joke", "Text")
        f1 = self.hop.create("B", "FUCHS", "WW", "Hunt 1", "Text 1")
        f2 = self.hop.create("B", "FUCHS", "WW", "Hunt 2", "Text 2")
        r, tb = await self.hop_calls()
        self.assertTrue(r.ok and tb.ok, (r.error, tb.error))
        self.assertEqual(r.sent, {wx.bid: ACCEPT, humor.bid: REJECT, f1.bid: ACCEPT,
                                  f2.bid: LATER})
        self.assertEqual(tb.deferred, [f2.bid])
        self.assertEqual(self.got(wx.bid).fwd, "")
        self.assertIsNone(self.got(humor.bid))
        self.assertEqual(self.got(f1.bid).fwd, "H")
        self.assertIsNone(self.got(f2.bid))
        # the sysop accepts FUCHS and restarts
        self.app.cfg.rubrics.append(Rubric("FUCHS", "Fox hunting"))
        self.assertEqual(self.module.resolve_rubrics(), (1, 0))
        self.assertNotEqual(self.got(f1.bid).fwd, "H")
        r, tb = await self.hop_calls()
        self.assertEqual(r.sent, {f2.bid: ACCEPT})
        self.assertEqual(self.got(f2.bid).to_call, "FUCHS")


if __name__ == "__main__":
    unittest.main()


class RubricValidity(unittest.TestCase):
    """CR40: every rubric may keep its bulletins for its own number of days."""

    def test_parse(self):
        import configparser
        from tinybox.config import _load_rubrics
        cp = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
        cp.read_string("[rubrics]\nALL = To everybody | 14\nWX = Weather | 3d\n"
                       "DX = DX news\nOLD = Old stuff | 0\nBAD = Bad | x\nHUMOR = - no | 5\n")
        got = {r.name: (r.description, r.accepted, r.expire_days) for r in _load_rubrics(cp)}
        self.assertEqual(got, {"ALL": ("To everybody", True, 14), "WX": ("Weather", True, 3),
                               "DX": ("DX news", True, None), "OLD": ("Old stuff", True, 0),
                               "BAD": ("Bad", True, None), "HUMOR": ("no", False, 5)})

    def test_purge_per_rubric(self):
        app = make_app()
        app.cfg.rubrics = [Rubric("ALL", "x", True, 0), Rubric("WX", "w", True, 3),
                           Rubric("DX", "d")]
        app.cfg.mailbox.bulletin_expire_days = 30
        ids = {}
        for to, age in (("WX", 2), ("WX", 4), ("DX", 10), ("DX", 40), ("ALL", 400)):
            m = bulletin(app, to)
            app.store._db.execute("UPDATE messages SET created = datetime('now', ?) WHERE id = ?",
                                  (f"-{age} days", m))
            ids[(to, age)] = m
        app.store._db.execute("UPDATE messages SET created = replace(created, ' ', 'T') || 'Z'")
        self.assertEqual(app.service.purge_expired(), 2)
        left = {m.id for m in app.store.list_messages()}
        self.assertEqual(left, {ids[("WX", 2)], ids[("DX", 10)], ids[("ALL", 400)]})
        self.assertEqual(app.service.rubric_expire_days("WX"), 3)
        self.assertEqual(app.service.rubric_expire_days("DX"), 30)
        self.assertEqual(app.service.rubric_expire_days("ALL"), 0)
