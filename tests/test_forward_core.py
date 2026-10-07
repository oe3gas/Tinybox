"""F1: forwarding fields in the core (schema 5, addresses, BIDs, R: lines).
No forward module is needed for these tests."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tinybox import addressing, config, texts
from tinybox.app import App
from tinybox.addressing import AddressError
from tinybox.service import ServiceError
from tinybox.store import Store

from tests.test_tinybox import ROOT, login, make_app, type_lines

HADDR = "OE3GAS.#NOE.AUT.EU"


def forward_on(app: App) -> App:
    app.cfg.station.haddress = HADDR
    app.cfg.station.qth = "Hollabrunn"
    app.cfg.forward.enabled = True
    return app


def rline(when: datetime, addr: str, bid: str) -> str:
    return addressing.make_rline(when, addr, "", 1, bid)


class AddressingTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(addressing.normalize("aut"), "AUT.EU")
        self.assertEqual(addressing.normalize("oe1xab.#wie.aut"), "OE1XAB.#WIE.AUT.EU")
        self.assertEqual(addressing.normalize("WW"), "WW")
        self.assertEqual(addressing.normalize("ALLOE", {"ALLOE": "AUT"}), "AUT.EU")
        self.assertEqual(addressing.normalize(""), "")
        for bad in ("OE1XAB..AUT", "A.B.C.D.E.F.G", "OE1 XAB", "TOOLONG7.AUT"):
            with self.assertRaises(AddressError, msg=bad):
                addressing.normalize(bad)

    def test_ssid_is_ignored(self):
        self.assertEqual(addressing.addr_call("OE3GAS-1.#NOE.AUT.EU"), "OE3GAS")
        self.assertTrue(addressing.is_local("OE3GAS-1.#NOE.AUT.EU", "OE3GAS-1"))
        self.assertTrue(addressing.is_local("", "OE3GAS-1"))
        self.assertFalse(addressing.is_local("WW", "OE3GAS-1"))

    def test_bid_and_rline(self):
        self.assertEqual(addressing.make_bid(42, "OE3GAS-1"), "42_OE3GAS")
        self.assertLessEqual(len(addressing.make_bid(123456789, "OE3GAS-1")), 12)
        when = datetime(2026, 10, 6, 18, 30, tzinfo=timezone.utc)
        r = addressing.make_rline(when, HADDR, "Hollabrunn", 7, "7_OE3GAS")
        self.assertEqual(r, "R:261006/1830Z @:OE3GAS.#NOE.AUT.EU [Hollabrunn] #:7 $:7_OE3GAS")
        self.assertEqual(addressing.rline_call(r), "OE3GAS")
        self.assertEqual(addressing.rline_time(r), when)
        found, body = addressing.split_rlines(r + "\n\nHello")
        self.assertEqual((found, body), ([r], "Hello"))

    def test_both_rline_forms(self):
        """W0RLI spec: HEADER1 (nr@BBS) and HEADER2 (@:BBS ... #:nr) must be parsed."""
        h1 = "R:930101/0000 1530@KA6FUB.#NOCAL.CA.USA.NOAM"
        h2 = "R:930108/1729 @:N6QMY.#NOCAL.CA.USA.NA Fremont #:1114 Z:94536"
        self.assertEqual(addressing.rline_call(h1), "KA6FUB")
        self.assertEqual(addressing.rline_call(h2), "N6QMY")
        self.assertEqual(addressing.rline_time(h1),
                         datetime(1993, 1, 1, 0, 0, tzinfo=timezone.utc))
        found, body = addressing.split_rlines(f"{h2}\n{h1}\n\nText")
        self.assertEqual((len(found), body), (2, "Text"))


class ConfigTests(unittest.TestCase):
    BASE = "[station]\nmailbox_call = OE3GAS-1\nsysop_call = OE3GAS\n"

    def _load(self, extra: str):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.conf"
            p.write_text(self.BASE + extra, encoding="utf-8")
            return config.load(p)

    def test_haddress(self):
        cfg = self._load("haddress = oe3gas.#noe.aut\n[forward]\nenabled = yes\n"
                         "aliases = ALLOE:AUT\n")
        self.assertEqual(cfg.station.haddress, HADDR)
        self.assertTrue(cfg.forward.enabled)
        self.assertEqual(cfg.forward.aliases, {"ALLOE": "AUT"})
        with self.assertRaises(config.ConfigError):
            self._load("haddress = OE1XAB.#WIE.AUT.EU\n")        # not our call
        with self.assertRaises(config.ConfigError):
            self._load("[forward]\nenabled = yes\n")              # haddress missing

    def test_defaults_standalone(self):
        cfg = config.load(ROOT / "tinybox.conf.example")
        self.assertFalse(cfg.forward.enabled)
        self.assertEqual(cfg.station.address, "OE3GAS")


class StandaloneTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()

    def test_local_mail_gets_bid_but_no_rline(self):
        s, t = login(self.app, "OE1ABC")
        type_lines(s, "S OE3GAS", "Hi", "text", "/EX")
        m = self.app.store.list_messages()[0]
        self.assertEqual(m.bid, f"{m.id}_OE3GAS")
        self.assertEqual((m.at_addr, m.rlines, m.fwd), ("", "", ""))
        self.assertTrue(self.app.service.bid_known(m.bid))

    def test_remote_address_refused_without_forwarding(self):
        s, t = login(self.app, "OE1ABC")
        t.take()
        type_lines(s, "SP OE1XYZ @ OE1XAB.#WIE.AUT")
        self.assertIn("does not forward", t.take())
        self.assertEqual(self.app.store.list_messages(), [])

    def test_bulletin_area_allowed_standalone(self):
        s, t = login(self.app, "OE1ABC")
        type_lines(s, "SB ALL @ WW", "Test", "text", "/EX")
        m = self.app.store.list_messages()[0]
        self.assertEqual((m.at_addr, m.fwd), ("WW", ""))     # nobody to forward to

    def test_own_address_with_ssid_is_local(self):
        s, t = login(self.app, "OE1ABC")
        type_lines(s, "SP OE3GAS @ OE3GAS-1.#NOE.AUT.EU", "Hi", "x", "/EX")
        self.assertEqual(len(self.app.store.list_messages()), 1)

    def test_version_says_standalone(self):
        s, t = login(self.app, "OE1ABC")
        t.take()
        type_lines(s, "V")
        self.assertIn("no forwarding", t.take())


class ForwardFieldsTests(unittest.TestCase):
    def setUp(self):
        self.app = forward_on(make_app())
        self.svc = self.app.service

    def test_user_sends_to_other_mailbox(self):
        s, t = login(self.app, "OE1ABC")
        type_lines(s, "SP OE1XYZ @ oe1xab.#wie.aut $MYBID1", "Sked", "80 m tonight", "/EX")
        m = self.app.store.list_messages()[0]
        self.assertEqual((m.at_addr, m.bid, m.fwd), ("OE1XAB.#WIE.AUT.EU", "MYBID1", "$"))
        self.assertEqual(len(m.rline_list), 1)
        self.assertEqual(addressing.rline_call(m.rline_list[0]), "OE3GAS")
        self.assertIn("[Hollabrunn]", m.rlines)

    def test_bid_kind(self):
        """W0RLI: real BID for bulletins and user-given IDs, MID for generated P ids."""
        s, t = login(self.app, "OE1ABC")
        type_lines(s, "SP OE3GAS", "a", "x", "/EX",                       # generated -> M
                   "SP OE1XYZ @ OE1XAB.#WIE.AUT $MINE01", "b", "x", "/EX",  # user BID -> B
                   "SB ALL @ WW", "c", "x", "/EX")                          # bulletin -> B
        kinds = {m.subject: m.bid_kind for m in self.app.store.list_messages()}
        self.assertEqual(kinds, {"a": "M", "b": "B", "c": "B"})
        msg_id = self.svc.create(from_call="DL1ABC", to_call="OE1ABC", type="P", subject="f",
                                 body="x", origin="forward", at_addr=HADDR, bid="77_DL0XTC")
        self.assertEqual(self.app.store.get(msg_id).bid_kind, "M")
        msg_id = self.svc.create(from_call="DL1ABC", to_call="OE1ABC", type="P", subject="g",
                                 body="x", origin="forward", at_addr=HADDR, bid="MYBID",
                                 bid_kind="B")
        self.assertEqual(self.app.store.get(msg_id).bid_kind, "B")

    def test_duplicate_bid_from_user(self):
        s, t = login(self.app, "OE1ABC")
        type_lines(s, "SB DX @ EU $DX0815", "a", "b", "/EX")
        t.take()
        type_lines(s, "SB DX @ EU $DX0815")
        self.assertIn("already known", t.take())

    def test_received_from_partner(self):
        old = rline(datetime.now(timezone.utc), "DL0XTC.#BAY.DEU.EU", "5_DL0XTC")
        msg_id = self.svc.create(from_call="DL1ABC", to_call="OE1ABC", type="P",
                                 subject="S" * 79, body="hello", origin="forward",
                                 at_addr=HADDR, bid="5_DL0XTC", rlines=[old])
        m = self.app.store.get(msg_id)
        self.assertEqual(m.origin, "forward")
        self.assertEqual(len(m.subject), 79)                   # partners may send up to 80
        self.assertEqual([addressing.rline_call(x) for x in m.rline_list], ["OE3GAS", "DL0XTC"])
        self.assertEqual(m.fwd, "")                            # delivered here
        with self.assertRaises(ServiceError) as cm:            # same BID again
            self.svc.create(from_call="DL1ABC", to_call="OE1ABC", type="P", subject="x",
                            body="x", origin="forward", at_addr=HADDR, bid="5_DL0XTC")
        self.assertEqual(cm.exception.code, "duplicate")

    def test_forwarded_ignores_third_party_rule(self):
        self.app.cfg.mailbox.third_party = False
        self.svc.create(from_call="DL1ABC", to_call="OE1ABC", type="P", subject="x",
                        body="x", origin="forward", at_addr=HADDR, bid="6_DL0XTC")

    def test_loop_is_held_and_hidden(self):
        mine = rline(datetime.now(timezone.utc) - timedelta(hours=2), HADDR, "9_OE3GAS")
        msg_id = self.svc.create(from_call="DL1ABC", to_call="ALL", type="B", subject="loop",
                                 body="x", origin="forward", at_addr="WW", bid="7_DL0XTC",
                                 rlines=[mine])
        m = self.app.store.get(msg_id)
        self.assertEqual(m.fwd, "H")
        self.assertIn("loop", m.note)
        self.assertNotIn(msg_id, [x.id for x in self.svc.list_for("OE1ABC", sysop=False)])
        self.assertIn(msg_id, [x.id for x in self.svc.list_for("OE3GAS", sysop=True)])

    def test_too_old_is_held(self):
        old = rline(datetime.now(timezone.utc) - timedelta(days=400), "DL0XTC.#BAY.DEU.EU",
                    "8_DL0XTC")
        msg_id = self.svc.create(from_call="DL1ABC", to_call="ALL", type="B", subject="old",
                                 body="x", origin="forward", at_addr="WW", bid="8_DL0XTC",
                                 rlines=[old])
        self.assertEqual(self.app.store.get(msg_id).fwd, "H")

    def test_forwarded_bulletin_waits_for_forward(self):
        msg_id = self.svc.create(from_call="DL1ABC", to_call="ALL", type="B", subject="b",
                                 body="x", origin="forward", at_addr="WW", bid="10_DL0XTC",
                                 rlines=[rline(datetime.now(timezone.utc), "DL0XTC", "10_DL0XTC")])
        self.assertEqual(self.app.store.get(msg_id).fwd, "$")

    def test_list_filters_and_read(self):
        s, t = login(self.app, "OE1ABC")
        type_lines(s, "SB ALL @ WW", "net", "x", "/EX", "SP OE3GAS", "p", "x", "/EX")
        t.take()
        type_lines(s, "LB")
        out = t.take()
        self.assertIn("net", out)
        self.assertNotIn(" p\r", out)
        type_lines(s, "L@ WW")
        self.assertIn("WW", t.take())
        type_lines(s, "R 1")
        out = t.take()
        self.assertIn("BID: 1_OE3GAS", out)
        self.assertIn("R:", out)
        self.assertIn("@ WW", out)

    def test_bid_purge(self):
        self.app.store.bid_add("OLD_X", "forward")
        self.app.store._db.execute("UPDATE bids SET first_seen = '2000-01-01T00:00:00Z'")
        self.assertEqual(self.svc.purge_bids(), 1)
        self.assertFalse(self.svc.bid_known("OLD_X"))

    def test_sysop_edit_at(self):
        s, t = login(self.app, "OE1ABC")
        type_lines(s, "SP OE3GAS", "x", "x", "/EX")
        m = self.svc.edit(1, "AT", "aut", "OE3GAS", sysop=True)
        self.assertEqual(m.at_addr, "AUT.EU")


class MigrationTests(unittest.TestCase):
    def test_schema4_database_gets_bids(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "tinybox.db"
            con = sqlite3.connect(db)
            con.executescript("""
                CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  msgid TEXT NOT NULL UNIQUE, type TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'N',
                  to_call TEXT NOT NULL, from_call TEXT NOT NULL, subject TEXT NOT NULL,
                  body TEXT NOT NULL, size INTEGER NOT NULL, origin TEXT NOT NULL,
                  created TEXT NOT NULL, read_at TEXT, replace_key TEXT, expires TEXT,
                  brocast TEXT);
                INSERT INTO messages (msgid, type, to_call, from_call, subject, body, size,
                  origin, created) VALUES ('a', 'P', 'OE3GAS', 'OE1ABC', 'old', 'x', 1, 'radio',
                  '2026-09-27T10:00:00Z'), ('b', 'B', 'ALL', 'OE1ABC', 'old b', 'y', 1,
                  'radio', '2026-09-28T10:00:00Z');
                PRAGMA user_version = 4;
            """)
            con.close()
            cfg = config.load(ROOT / "tinybox.conf.example")
            app = App.create(cfg, db_path=str(db))
            msgs = sorted(app.store.list_messages(), key=lambda m: m.id)
            self.assertEqual([m.bid for m in msgs], ["1_OE3GAS", "2_OE3GAS"])
            self.assertEqual([m.subject for m in msgs], ["old", "old b"])
            self.assertEqual([m.bid_kind for m in msgs], ["M", "B"])
            self.assertTrue(all(m.fwd == "" and m.at_addr == "" for m in msgs))
            self.assertEqual(app.service.assign_missing_bids(), 0)   # second start: nothing
            app.store.close()


if __name__ == "__main__":
    unittest.main()
