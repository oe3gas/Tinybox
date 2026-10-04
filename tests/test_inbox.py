"""Inbox folder: text files -> bulletins (Replace, Valid), schema migration."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from tinybox.adapters import brocast
from tinybox.adapters.inbox import Inbox, InboxError, parse
from tinybox.config import BrocastCfg, InboxCfg
from tinybox.store import Store
from tests.test_tinybox import make_app

WETTER = """To: WX
Subject: Wetter Hollabrunn 19:00
Replace: geosphere-wetter
Valid: 2h

Temperatur 12,5 °C
Feuchte 65 %

Daten: GeoSphere Austria, CC BY 4.0
"""


class ParseTests(unittest.TestCase):
    def test_full(self):
        b = parse(WETTER.encode("utf-8"))
        self.assertEqual((b.to, b.subject, b.replace, b.valid_min, b.sender),
                         ("WX", "Wetter Hollabrunn 19:00", "geosphere-wetter", 120, None))
        self.assertTrue(b.body.startswith("Temperatur 12,5 °C\nFeuchte"))

    def test_crlf_bom_and_cp1252(self):
        self.assertEqual(parse(("﻿" + WETTER).replace("\n", "\r\n").encode()).to, "WX")
        self.assertIn("°C", parse(WETTER.encode("cp1252")).body)

    def test_errors(self):
        cases = {
            "Subject: x\n\nText": "To",
            "To: WX\n\nText": "Subject",
            "To: WX\nSubjekt: x\n\nText": "unbekannte Kopfzeile",
            "To: WX\nSubject: x\nValid: morgen\n\nText": "Valid",
            "To: WX\nSubject: x\nReplace: a b\n\nText": "Replace",
            "To: WX\nSubject: x\n\n   ": "Text fehlt",
            "To: WX\nSubject: x": "Leerzeile",
        }
        for text, expected in cases.items():
            with self.subTest(text=text), self.assertRaisesRegex(InboxError, expected):
                parse(text.encode())


class InboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "eingang"
        self.app = make_app()
        self.app.cfg.inbox = InboxCfg(enabled=True, directory=self.dir)
        self.app.cfg.brocast = BrocastCfg()
        self.events = []
        self.app.bus.subscribe("*", lambda name, data: self.events.append((name, data)))
        self.inbox = Inbox(self.app)

    def tearDown(self):
        self.tmp.cleanup()

    def drop(self, name: str, text: str, age: float = 10) -> Path:
        f = self.dir / name
        f.write_text(text, encoding="utf-8")
        old = time.time() - age
        os.utime(f, (old, old))
        return f

    def test_bulletin_created_and_file_moved(self):
        self.drop("wetter.txt", WETTER)
        self.assertEqual(self.inbox.scan(), 1)
        msg = self.app.store.list_messages()[0]
        self.assertEqual((msg.type, msg.to_call, msg.from_call, msg.origin),
                         ("B", "WX", "OE3GAS", "inbox"))
        self.assertEqual(list(self.dir.glob("*.txt")), [])
        self.assertEqual(len(list((self.dir / "erledigt").glob("*wetter.txt"))), 1)
        self.assertEqual(self.events[-1][0], "message.created")

    def test_replace_keeps_number(self):
        self.drop("a.txt", WETTER)
        self.inbox.scan()
        first = self.app.store.list_messages()[0]
        self.app.store.mark_read(first.id)
        self.drop("b.txt", WETTER.replace("12,5", "13,1").replace("19:00", "20:00"))
        self.inbox.scan()
        msgs = self.app.store.list_messages()
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0].id, first.id)
        self.assertIn("13,1", msgs[0].body)
        self.assertEqual((msgs[0].status, msgs[0].subject), ("N", "Wetter Hollabrunn 20:00"))
        self.assertEqual(self.events[-1][0], "message.edited")

    def test_sysop_reading_marks_inbox_bulletin_read(self):
        self.drop("w.txt", WETTER)                      # nominal author: OE3GAS (sysop)
        self.inbox.scan()
        msg_id = self.app.store.list_messages()[0].id
        self.app.service.read(msg_id, "OE3GAS", sysop=True)
        self.assertEqual(self.app.store.get(msg_id).status, "Y")

    def test_identical_replace_is_quiet(self):
        self.drop("a.txt", WETTER)
        self.inbox.scan()
        msg = self.app.store.list_messages()[0]
        self.app.store.mark_read(msg.id)
        n_events = len(self.events)
        self.drop("b.txt", WETTER)                      # same content again
        self.inbox.scan()
        again = self.app.store.list_messages()[0]
        self.assertEqual((again.id, again.status), (msg.id, "Y"))
        self.assertEqual(len(self.events), n_events)    # no event -> no new page revision

    def test_warn_becomes_alert_page(self):
        self.drop("w.txt", WETTER.replace("To: WX", "To: WARN").replace(
            "Replace: geosphere-wetter", "Replace: geosphere-warnung"))
        self.inbox.scan()
        page = brocast.to_page(self.app.store.list_messages()[0], self.app)
        self.assertEqual((page["typ"], page["cat"]), ("alert", ["notfunk"]))

    def test_valid_expires_and_page_validity(self):
        self.drop("w.txt", WETTER)
        self.inbox.scan()
        msg = self.app.store.list_messages()[0]
        self.assertIsNotNone(msg.expires)
        self.assertEqual(brocast.to_page(msg, self.app)["exp"], 120)
        # pretend the time is over
        self.app.store._db.execute("UPDATE messages SET expires='2000-01-01T00:00:00Z'")
        self.assertEqual(self.app.service.purge_expired(), 1)
        self.assertEqual(self.app.store.list_messages(), [])
        self.assertEqual(self.events[-1], ("message.expired", {"ids": [msg.id]}))

    def test_rejected_file(self):
        self.drop("kaputt.txt", "Subject: ohne Ziel\n\nText")
        self.inbox.scan()
        failed = list((self.dir / "fehler").iterdir())
        self.assertEqual(len(failed), 2)
        err = next(f for f in failed if f.suffix == ".err").read_text(encoding="utf-8")
        self.assertIn("To", err)
        self.assertEqual(self.app.store.list_messages(), [])

    def test_bad_destination_and_too_long(self):
        self.drop("a.txt", "To: WX-1\nSubject: x\n\nText")
        self.drop("b.txt", "To: WX\nSubject: x\n\n" + "x" * 9000)
        self.inbox.scan()
        errs = sorted(f.read_text(encoding="utf-8") for f in (self.dir / "fehler").glob("*.err"))
        self.assertTrue(any("Rufzeichen" in e for e in errs))
        self.assertTrue(any("zu lang" in e for e in errs))

    def test_young_and_other_files_ignored(self):
        self.drop("neu.txt", WETTER, age=0)
        self.drop("halb.tmp", WETTER)
        self.assertEqual(self.inbox.scan(), 0)


WX_PAGE = '{"typ": "wx", "dat": {"temp": 12.5, "hum": 65}}'
WETTER_BROCAST = WETTER.replace("Valid: 2h\n", "Valid: 2h\nBrocast: " + WX_PAGE + "\n")


class BrocastHeaderTests(unittest.TestCase):
    """Header "Brocast:": a ready page for brocastd next to the text (PLANUNG 6d)."""

    setUp, tearDown, drop = InboxTests.setUp, InboxTests.tearDown, InboxTests.drop

    def test_parse(self):
        b = parse(WETTER_BROCAST.encode())
        self.assertEqual(b.brocast, '{"typ":"wx","dat":{"temp":12.5,"hum":65}}')   # compact
        self.assertTrue(b.body.startswith("Temperatur"))
        self.assertIsNone(parse(WETTER.encode()).brocast)

    def test_parse_errors(self):
        for value, text in (("{kaputt", "kein gültiges JSON"), ('["wx"]', "typ"),
                            ('{"ti": "x"}', "typ"), ('{"typ": "' + "x" * 9000 + '"}', "länger")):
            with self.subTest(value=value[:20]):
                with self.assertRaisesRegex(InboxError, text):
                    parse(WETTER.replace("Valid: 2h\n", f"Valid: 2h\nBrocast: {value}\n").encode())

    def test_page_is_sent_instead_of_text(self):
        self.drop("w.txt", WETTER_BROCAST)
        self.inbox.scan()
        msg = self.app.store.list_messages()[0]
        self.assertIn("Temperatur", msg.body)                    # mailbox: the text
        page = brocast.to_page(msg, self.app)                    # brocast: the page
        self.assertEqual((page["typ"], page["dat"]), ("wx", {"temp": 12.5, "hum": 65}))
        self.assertEqual((page["ti"], page["cat"], page["exp"]),
                         ("Wetter Hollabrunn 19:00", ["wx"], 120))   # filled in by TinyBox
        self.assertNotIn("to", page)
        self.assertEqual(brocast.text_page(msg, self.app)["typ"], "text")   # fallback

    def test_own_fields_win(self):
        self.drop("w.txt", WETTER.replace("Valid: 2h\n", 'Valid: 2h\nBrocast: {"typ":"wx",'
                                          '"ti":"Eigener Titel","exp":30,"cat":["notfunk"]}\n'))
        self.inbox.scan()
        page = brocast.to_page(self.app.store.list_messages()[0], self.app)
        self.assertEqual((page["ti"], page["exp"], page["cat"]), ("Eigener Titel", 30, ["notfunk"]))

    def test_new_page_with_same_text_is_a_change(self):
        self.drop("a.txt", WETTER_BROCAST)
        self.inbox.scan()
        n_events = len(self.events)
        self.drop("b.txt", WETTER_BROCAST)                       # identical: quiet
        self.inbox.scan()
        self.assertEqual(len(self.events), n_events)
        self.drop("c.txt", WETTER_BROCAST.replace("12.5", "13.0"))   # only the page differs
        self.inbox.scan()
        self.assertEqual(self.events[-1][0], "message.edited")
        msg = self.app.store.list_messages()[0]
        self.assertIn("13.0", msg.brocast)


class MigrationTests(unittest.TestCase):
    def test_old_database_gets_new_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "old.db"
            con = sqlite3.connect(db)
            con.execute("""CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT,
                msgid TEXT NOT NULL UNIQUE, type TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'N',
                to_call TEXT NOT NULL, from_call TEXT NOT NULL, subject TEXT NOT NULL,
                body TEXT NOT NULL, size INTEGER NOT NULL, origin TEXT NOT NULL,
                created TEXT NOT NULL, read_at TEXT)""")
            con.execute("INSERT INTO messages (msgid,type,to_call,from_call,subject,body,size,"
                        "origin,created) VALUES ('u','B','ALL','OE3GAS','alt','x',1,'radio',"
                        "'2026-09-27T10:00:00Z')")
            con.commit()
            con.close()
            store = Store(db)
            msg = store.list_messages()[0]
            self.assertEqual((msg.subject, msg.replace_key, msg.expires, msg.brocast),
                             ("alt", None, None, None))
            store.close()


if __name__ == "__main__":
    unittest.main()
