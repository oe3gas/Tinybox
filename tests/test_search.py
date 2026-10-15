"""CR49: search in mail and bulletins - TinyBox (F command, sysop web) and client."""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from tbclient.mailstore import MailStore
from tests import test_web
from tests.test_tinybox import login, make_app, type_lines
from tests.test_web import request


def put(app, frm, to, subject, body, type="P"):
    return app.service.create(from_call=frm, to_call=to, type=type, subject=subject, body=body,
                              origin="telnet")


class TinyBoxSearchTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        put(self.app, "OE3XYZ", "OE3TEC", "Antenne", "Der neue Dipol fuer 2m ist fertig.")
        put(self.app, "OE3XYZ", "OE1ABC", "Geheim", "Dipol nur fuer dich")
        put(self.app, "OE3XYZ", "ALL", "Treffen", "Fieldday mit DIPOL-Bau", type="B")

    def test_service(self):
        s = self.app.service
        self.assertEqual([m.subject for m in s.search("OE3TEC", False, "dipol")],
                         ["Treffen", "Antenne"])           # not the mail of OE1ABC
        self.assertEqual(len(s.search("OE3GAS", True, "dipol")), 3)       # sysop: all
        self.assertEqual([m.subject for m in s.search("OE3TEC", False, "oe3xyz")][-1], "Antenne")
        self.assertEqual(s.search("OE3TEC", False, "d"), [])               # too short

    def test_command(self):
        sess, t = login(self.app, "OE3TEC")
        type_lines(sess, "F dipol")
        self.assertIn("2 message(s) with 'dipol':", t.buf)
        self.assertIn("Antenne", t.buf)
        self.assertNotIn("Geheim", t.buf)
        t.buf = ""
        type_lines(sess, "FIND kurzwelle")
        self.assertIn("Nothing found for 'kurzwelle'.", t.buf)
        t.buf = ""
        type_lines(sess, "F x")
        self.assertIn("Usage: F text", t.buf)
        type_lines(sess, "H")
        self.assertIn("F text", t.buf)


class WebSearchTests(unittest.TestCase):
    setUp, tearDown = test_web.WebTests.setUp, test_web.WebTests.tearDown
    run_async, login = test_web.WebTests.run_async, test_web.WebTests.login

    def test_api(self):
        put(self.app, "OE3XYZ", "OE3TEC", "Antenne", "Der neue Dipol")
        put(self.app, "OE3XYZ", "ALL", "Wetter", "Sonne", type="B")

        async def scenario(s):
            cookie, _ = await self.login(s)
            _, _, p = await request(s.port, "GET", "/api/messages?q=dipol", cookie=cookie)
            return json.loads(p)

        rows = self.run_async(scenario)
        self.assertEqual([r["subject"] for r in rows], ["Antenne"])


class ClientSearchTests(unittest.TestCase):
    def test_mailstore(self):
        with tempfile.TemporaryDirectory() as tmp:
            box = MailStore(Path(tmp) / "m.db", "OE3GAS")
            now = int(time.time())
            hdr = dict(type="P", status="N", fwd="", size=10, from_call="OE3TEC", to_call="OE3GAS",
                       at_addr="", bid="", created=now)
            box.upsert_header(dict(hdr, id=1, subject="Hallo"))
            box.set_body(1, "Der Dipol haengt jetzt\\nauf 12 m Hoehe.")
            box.upsert_header(dict(hdr, id=2, subject="Dipol-Frage"))           # no text yet
            box.upsert_header(dict(hdr, id=3, subject="Wetter", type="B", to_call="WX"))
            box.set_body(3, "Sonne")
            found = box.folder("s:dipol")
            self.assertEqual([(r["id"], r["hit"]) for r in found], [(2, "header"), (1, "text")])
            self.assertIn("Dipol haengt", found[1]["snippet"])
            self.assertEqual([r["id"] for r in box.folder("s:WX")], [3])      # the rubric too
            self.assertEqual(box.folder("s:x"), [])
            box.close()


if __name__ == "__main__":
    unittest.main()
