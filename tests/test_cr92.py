"""CR92: roles and rights (PLANUNG 29.7) - guests, users, sysop."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from prcore import auth
from prcore.kissport import plausible_call
from tinybox import clientproto, rights
from tinybox.adapters import brocast
from tinybox.service import ServiceError

from tests.test_brocast_adapter import msg
from tests.test_tinybox import login, make_app, type_lines


class Limits(unittest.TestCase):
    def setUp(self):
        for name, value in ((rights, "GUEST_LIMITS"), (clientproto, "REQUIRE_AUTH")):
            p = mock.patch.object(name, value, True)
            p.start()
            self.addCleanup(p.stop)
        self.app = make_app()
        self.app.cfg.forward.enabled = True


class Guest(Limits):
    def test_no_bulletins(self):
        s, t = login(self.app, "OE1ABC")
        type_lines(s, "SB ALL")
        self.assertIn("Bulletins only with the TinyBox client", t.take())
        with self.assertRaises(ServiceError) as e:
            self.app.service.create(from_call="OE1ABC", to_call="ALL", type="B", subject="x",
                                    body="y", origin="telnet", role=rights.GUEST)
        self.assertEqual(e.exception.code, "need_login")

    def test_mail_local_and_to_the_sysop(self):
        s, t = login(self.app, "OE1ABC")
        type_lines(s, "SP OE3XYZ", "Hallo", "Text 😀 ende", "/EX")
        out = t.take()
        self.assertNotIn("waits until the sysop", out)
        m = self.app.store.list_messages()[-1]
        self.assertEqual((m.to_call, m.fwd), ("OE3XYZ", ""))
        self.assertEqual(m.body, "Text  ende")                 # PLANUNG 29.9: text only

    def test_mail_to_another_bbs_is_held(self):
        s, t = login(self.app, "OE1ABC")
        type_lines(s, "SP OE5XYZ @ OE5XBL.#OOE.AUT.EU", "Hallo", "Text", "/EX")
        self.assertIn("waits until the sysop OE3GAS releases it", t.take())
        m = self.app.store.list_messages()[-1]
        self.assertEqual((m.fwd, m.note), ("H", rights.GUEST_HOLD))

    def test_deletes_no_bulletin(self):
        b = self.app.service.create(from_call="OE1ABC", to_call="ALL", type="B", subject="x",
                                    body="y", origin="sysop")
        s, t = login(self.app, "OE1ABC")                          # even the author
        type_lines(s, f"K {b}")
        self.assertIn("Not allowed", t.take())
        self.assertIsNotNone(self.app.store.get(b))


class Tb15(Limits):
    def test_call_named_like_the_rubric(self):
        ids = [self.app.service.create(from_call="OE1ABC", to_call="70CM", type="B",
                                       subject="x", body="y", origin="sysop") for _ in range(2)]
        for who, sysop in (("70CM", False), ("OE1ABC", False)):
            for i in ids:
                with self.assertRaises(ServiceError):
                    self.app.service.delete(i, who, sysop)
        self.app.service.delete(ids[0], "OE3GAS", True)

    def test_user_deletes_own_bulletin(self):
        b = self.app.service.create(from_call="OE1ABC", to_call="ALL", type="B", subject="x",
                                    body="y", origin="radio", role=rights.USER)
        with self.assertRaises(ServiceError):
            self.app.service.delete(b, "OE1XYZ", False, rights.USER)
        self.app.service.delete(b, "OE1ABC", False, rights.USER)

    def test_plausible_calls(self):
        for ok in ("OE3GAS", "OE3GAS-15", "4X1AB", "2E0ABC", "3DA0RU", "K1A", "9V1NE"):
            self.assertTrue(plausible_call(ok), ok)
        for bad in ("70CM", "10M", "23CM", "40M", "QO100", "WX", "TBTEST", "ABCDEF", "QST"):
            self.assertFalse(plausible_call(bad), bad)


class Tb14(Limits):
    def test_alert_only_from_the_sysop(self):
        self.assertTrue(brocast.wanted(msg(to_call="WARN", origin="sysop"), self.app))
        self.assertTrue(brocast.wanted(msg(to_call="WARN", origin="inbox"), self.app))
        for origin in ("radio", "telnet", "axudp", "forward"):
            self.assertFalse(brocast.wanted(msg(to_call="WARN", origin=origin,
                                                from_call="OE3GAS"), self.app), origin)
        self.assertTrue(brocast.wanted(msg(to_call="ALL", origin="radio"), self.app))


class User(Limits):
    def test_client_user_writes_bulletins(self):
        with tempfile.TemporaryDirectory() as tmp:
            key = auth.Identity(Path(tmp) / "identity.key")
            self.app.store.key_put("OE1ABC", key.pub, "active")
            s, t = login(self.app, "OE1ABC-7")
            type_lines(s, "//CLIENT TB1 v=2026.11.10 caps=SYNC")
            n = t.take().split("//AUTH? n=", 1)[1].split()[0]
            box = self.app.cfg.station.mailbox_call
            type_lines(s, f"//AUTH sig={key.sign_login(box, 'OE1ABC', n)} pub={key.pub}")
            t.take()
            self.assertEqual(rights.role_of(s), rights.USER)
            line = "//SEND B ALL 1 mid=abcdefgh99"
            sig = key.sign_command(box, "OE1ABC", n, 1, line, ["Betreff", "Text 😀"])
            type_lines(s, f"{line} c=1 sig={sig}", "Betreff", "Text 😀")
            self.assertIn("//SENT", t.take())
            self.assertEqual(self.app.store.list_messages()[-1].body, "Text 😀")


if __name__ == "__main__":
    unittest.main()
