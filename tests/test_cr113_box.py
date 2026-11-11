"""CR113 stage 2: the TinyBox checks the LoTW confirmation of a client key
(//LOTW?, //LOTWP), marks the key, issues TBC2 certificates with level lotw, and
with [client] lotw_release = yes releases a new key without the sysop."""

from __future__ import annotations

import base64
import dataclasses
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from prcore import auth, lotw
from tinybox import clientproto, lotwbox

from tests.test_cr113 import HAVE, make_lotw, p12_of
from tests.test_tinybox import login, make_app, type_lines


def chunks(proof):
    text = base64.urlsafe_b64encode(json.dumps(proof, separators=(",", ":")).encode()).decode()
    text = text.rstrip("=")
    parts = [text[i:i + 200] for i in range(0, len(text), 200)]
    return [f"//LOTWP {i}/{len(parts)} {c}" for i, c in enumerate(parts, 1)]


@unittest.skipUnless(HAVE, "needs cryptography")
class BoxLotw(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(clientproto, "REQUIRE_AUTH", True)
        p.start()
        self.addCleanup(p.stop)
        self.app = make_app()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.key = auth.Identity(Path(self.tmp.name) / "identity.key")
        self.box = self.app.cfg.station.mailbox_call
        now = dt.datetime.now(dt.timezone.utc)
        self.lkey, self.leaf, self.inter, self.root = make_lotw(
            "OE3ABC", start=now - dt.timedelta(days=10), end=now + dt.timedelta(days=400))
        self.p12 = p12_of(self.lkey, self.leaf, [self.inter, self.root])
        f = Path(self.tmp.name) / "tqsl.p12"
        f.write_bytes(self.p12)
        with self.assertLogs("tinybox.lotwbox", "WARNING"):
            out = lotwbox.add_file(self.app.store, str(f), "geheim")
        self.assertEqual(sum(1 for x in out if x.startswith("added")), 2)    # root + intermediate
        self.proof = lotw.sign_binding(self.p12, "geheim", "OE3ABC", self.key.pub)

    def logon(self, status="active"):
        if status:
            self.app.store.key_put("OE3ABC", self.key.pub, status)
        s, t = login(self.app, "OE3ABC-7")
        type_lines(s, "//CLIENT TB1 v=2026.11.11 caps=CHAT,SYNC,LOTW")
        n = t.take().split("//AUTH? n=", 1)[1].split()[0]
        type_lines(s, f"//AUTH sig={self.key.sign_login(self.box, 'OE3ABC-7', n)} pub={self.key.pub}")
        return s, t

    def test_released_key_gets_the_mark_and_a_lotw_certificate(self):
        s, t = self.logon()
        self.assertIn("LOTW", t.take().split("caps=", 1)[1].split()[0])
        type_lines(s, "//LOTW?")
        self.assertIn("//LOTW -", t.take())
        with self.assertLogs("tinybox.lotwbox", "WARNING"):
            type_lines(s, *chunks(self.proof))
        self.assertIn(f"//LOTW ok until={self.proof['until']}", t.take())
        row = self.app.store.key_get("OE3ABC", self.key.pub)
        self.assertEqual((row["status"], row["lotw"]), ("active", self.proof["until"]))
        type_lines(s, "//LOTW?")
        self.assertIn(f"//LOTW until={self.proof['until']}", t.take())
        type_lines(s, "//CERT?")
        cert = t.take().split("//CERT ", 1)[1].split()[0]
        c = auth.parse_cert(cert)
        self.assertEqual(c["level"], "lotw")
        self.assertTrue(auth.check_cert(c, self.app.service.box_identity().public, "20000101"))
        from tinybox import keys
        self.assertTrue(keys.users(self.app.service)[0]["lotw"])

    def test_waiting_key_stays_waiting_by_default(self):
        with self.assertLogs("tinybox", "WARNING"):
            s, t = self.logon(status="")
            self.assertIn("//AUTHWAIT", t.take())
            type_lines(s, *chunks(self.proof))
        self.assertIn("//LOTW ok", t.take())
        self.assertEqual(self.app.store.key_get("OE3ABC", self.key.pub)["status"], "pending")
        self.assertIsNone(s.client)

    def test_lotw_release_logs_in_at_once(self):
        self.app.cfg = dataclasses.replace(
            self.app.cfg, client=dataclasses.replace(self.app.cfg.client, lotw_release=True))
        with self.assertLogs("tinybox", "WARNING"):
            s, t = self.logon(status="")
            t.take()
            s.cfg = self.app.cfg
            type_lines(s, *chunks(self.proof))
        out = t.take()
        self.assertIn("//LOTW ok", out)
        self.assertIn("//OK TB1", out)
        self.assertEqual(self.app.store.key_get("OE3ABC", self.key.pub)["status"], "active")
        self.assertIsNotNone(s.client)

    def test_proof_of_another_key_or_untrusted_root(self):
        s, t = self.logon()
        t.take()
        other = auth.Identity(Path(self.tmp.name) / "other.key")
        bad = lotw.sign_binding(self.p12, "geheim", "OE3ABC", other.pub)
        with self.assertLogs("tinybox.lotwbox", "WARNING"):
            type_lines(s, *chunks(bad))
        self.assertIn("//LOTW err not for this key", t.take())
        self.app.store.lotw_root_delete("")                       # no ARRL certificate
        type_lines(s, "//LOTW?")
        self.assertIn("//LOTW off", t.take())

    def test_out_of_order_and_too_many(self):
        s, t = self.logon()
        t.take()
        lines = chunks(self.proof)
        type_lines(s, lines[1] if len(lines) > 1 else "//LOTWP 2/1 x")
        self.assertIn("//LOTW err", t.take())
        type_lines(s, "//LOTWP 1/999 x")
        self.assertIn("//LOTW err syntax", t.take())


class CertLevels(unittest.TestCase):
    def test_tbc1_and_tbc2(self):
        with tempfile.TemporaryDirectory() as d:
            box = auth.Identity(Path(d) / "box.key")
            user = auth.Identity(Path(d) / "u.key")
            c1 = auth.make_cert(box, "OE3ABC", user.pub, "OE3XBS-1", "20270101")
            c2 = auth.make_cert(box, "OE3ABC", user.pub, "OE3XBS-1", "20270101", "lotw")
            self.assertTrue(c1.startswith("TBC1:"))
            self.assertTrue(c2.startswith("TBC2:"))
            p1, p2 = auth.parse_cert(c1), auth.parse_cert(c2)
            self.assertEqual((p1["level"], p2["level"]), ("", "lotw"))
            self.assertTrue(auth.check_cert(p2, box.public, "20261111"))
            p2["level"] = ""                                     # level not removable
            self.assertFalse(auth.check_cert(p2, box.public, "20261111"))


if __name__ == "__main__":
    unittest.main()
