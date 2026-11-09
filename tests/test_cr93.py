"""CR93 stage 1: the client logs in with the key of its user (Ed25519)."""

from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from prcore import auth
from tbclient.core import ClientCore
from tinybox import clientproto
from tinybox.adapters.sysop import MonitorFilter, SysopConsole

from tests.test_tbclient import client_cfg
from tests.test_tinybox import login, make_app, type_lines

# RFC 8032, 7.1 tests 1-3
VECTORS = [
    ("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
     "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a", "",
     "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc6"
     "1e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"),
    ("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
     "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c", "72",
     "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e45"
     "8f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
    ("c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
     "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025", "af82",
     "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff9b538d16f290ae"
     "67f760984dc6594a7c15e9716ed28dc027beceea1ec40a"),
]


class Ed25519(unittest.TestCase):
    def test_rfc8032_vectors_both_ways(self):
        for sk, pk, msg, sig in VECTORS:
            sk, pk, msg, sig = map(bytes.fromhex, (sk, pk, msg, sig))
            self.assertEqual(auth._py_public(sk), pk)
            self.assertEqual(auth._py_sign(sk, msg), sig)
            self.assertTrue(auth._py_verify(pk, msg, sig))
            self.assertFalse(auth._py_verify(pk, msg + b"x", sig))
            self.assertEqual(auth.public_key(sk), pk)
            self.assertEqual(auth.sign(sk, msg), sig)
            self.assertTrue(auth.verify(pk, msg, sig))

    def test_bad_input(self):
        pk = bytes.fromhex(VECTORS[0][1])
        self.assertFalse(auth.verify(pk, b"", b"\x00" * 64))
        self.assertFalse(auth.verify(pk[:31], b"", b"\x00" * 64))
        for bad in ("", "x" * 43 + "=", "ä" * 43, "a" * 42, "a" * 44):
            with self.assertRaises(auth.AuthError):
                auth.b64d(bad, 32)

    def test_sizes_and_fingerprint(self):
        pk = bytes.fromhex(VECTORS[0][1])
        self.assertEqual(len(auth.b64e(pk)), 43)
        self.assertEqual(len(auth.b64e(b"\x00" * 64)), 86)
        self.assertRegex(auth.fingerprint(pk), r"^[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}$")

    def test_identity_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x" / "identity.key"
            a = auth.Identity(p)
            self.assertEqual(auth.Identity(p).pub, a.pub)           # loaded, not new
            if os.name == "posix":
                self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600)
            p.write_text("garbage")
            with self.assertRaisesRegex(auth.AuthError, "damaged"):
                auth.Identity(p)                                     # never replaced silently


class BoxLogin(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(clientproto, "REQUIRE_AUTH", True)
        p.start()
        self.addCleanup(p.stop)
        self.app = make_app()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.key = auth.Identity(Path(self.tmp.name) / "identity.key")
        self.box = self.app.cfg.station.mailbox_call

    def hello(self, call="OE3ABC-7"):
        s, t = login(self.app, call)
        type_lines(s, "//CLIENT TB1 v=2026.11.09 caps=CHAT")
        out = t.take()
        self.assertIn("//AUTH? n=", out)
        self.assertNotIn("//OK", out)
        nonce = out.split("//AUTH? n=", 1)[1].split()[0]
        return s, t, nonce

    def answer(self, s, nonce, key=None, call="OE3ABC-7"):
        key = key or self.key
        type_lines(s, f"//AUTH sig={key.sign_login(self.box, call, nonce)} pub={key.pub}")

    def test_new_key_waits_then_released(self):
        s, t, n = self.hello()
        type_lines(s, "//BOARDS")                                   # no client mode yet
        self.assertIn("//ERR not a client session", t.take())
        with self.assertLogs("tinybox.clientproto", "WARNING"):
            self.answer(s, n)
        self.assertIn(f"//AUTHWAIT fp={self.key.fp}", t.take())
        self.assertEqual(self.app.store.key_get("OE3ABC")["status"], "pending")
        self.assertTrue(any(self.key.fp in m.body for m in self.app.store.list_messages()
                            if m.to_call == self.app.cfg.station.sysop_call))
        # the sysop releases it
        out = []
        SysopConsole(self.app, MonitorFilter(True), out.append).handle_line("USER OK oe3abc")
        self.assertEqual(self.app.store.key_get("OE3ABC")["status"], "active")
        s, t, n = self.hello("OE3ABC-2")                           # another SSID, same key
        self.answer(s, n, call="OE3ABC-2")
        self.assertIn("//OK TB1", t.take())
        self.assertTrue(s.auth)

    def test_wrong_signature_and_replay(self):
        s, t, n = self.hello()
        other = auth.Identity(Path(self.tmp.name) / "other.key")
        sig = other.sign_login(self.box, "OE3ABC", n)
        with self.assertLogs("tinybox.clientproto", "WARNING"):
            type_lines(s, f"//AUTH sig={sig} pub={self.key.pub}")    # sig of another key
        self.assertIn("//ERR auth bad_signature", t.take())
        self.answer(s, n)                                            # the nonce is used up
        self.assertIn("//ERR auth not_asked", t.take())
        s2, t2, n2 = self.hello()
        with self.assertLogs("tinybox.clientproto", "WARNING"):
            type_lines(s2, f"//AUTH sig={self.key.sign_login(self.box, 'OE3ABC', n)} "
                           f"pub={self.key.pub}")                     # old answer, new challenge
        self.assertIn("bad_signature", t2.take())

    def test_other_key_and_revoked(self):
        self.app.store.key_put("OE3ABC", self.key.pub, "active")
        thief = auth.Identity(Path(self.tmp.name) / "thief.key")
        s, t, n = self.hello()
        with self.assertLogs("tinybox.clientproto", "WARNING"):
            self.answer(s, n, key=thief)
        self.assertIn("//ERR auth other_key", t.take())
        self.app.store.key_status("OE3ABC", "revoked")
        s, t, n = self.hello()
        self.answer(s, n)
        self.assertIn("//ERR auth revoked", t.take())

    def test_signed_for_another_box_is_refused(self):
        self.app.store.key_put("OE3ABC", self.key.pub, "active")
        s, t, n = self.hello()
        with self.assertLogs("tinybox.clientproto", "WARNING"):
            type_lines(s, f"//AUTH sig={self.key.sign_login('OE1XYZ', 'OE3ABC', n)} "
                          f"pub={self.key.pub}")
        self.assertIn("bad_signature", t.take())

    def test_user_console(self):
        self.app.store.key_put("OE3ABC", self.key.pub, "pending", note="from OE3ABC-7")
        out = []
        c = SysopConsole(self.app, MonitorFilter(True), out.append)
        c.handle_line("USER")
        self.assertIn(self.key.fp, "".join(out))
        c.handle_line("USER REVOKE OE3ABC")
        self.assertEqual(self.app.store.key_get("OE3ABC")["status"], "revoked")
        c.handle_line("USER DEL OE3ABC")
        self.assertIsNone(self.app.store.key_get("OE3ABC"))
        c.handle_line("USER OK")
        self.assertIn("Usage: USER", "".join(out))


class ClientSide(unittest.TestCase):
    def test_answers_the_challenge(self):
        with tempfile.TemporaryDirectory() as tmp:
            core = ClientCore(client_cfg(tmp))
            sent = []
            core._send = sent.append
            core._on_line("//AUTH? n=abcDEF123 box=OE3XTC-1")
            [line] = sent
            args = dict(x.split("=", 1) for x in line.split()[1:])
            pub, sig = auth.b64d(args["pub"], 32), auth.b64d(args["sig"], 64)
            self.assertTrue(auth.verify(pub, auth.login_message("OE3XTC-1", "OE3GAS", "abcDEF123"),
                                        sig))
            core._on_line(f"//AUTHWAIT fp={core.identity.fp}")
            self.assertEqual(core.auth["state"], "wait")
            core._on_line("//ERR auth other_key")
            self.assertEqual((core.auth["state"], core.auth["reason"]), ("refused", "other_key"))
            core._on_line("//OK TB1 caps=CHAT")
            self.assertEqual(core.auth["state"], "ok")
            self.assertTrue((Path(tmp) / "identity.key").is_file())


if __name__ == "__main__":
    unittest.main()
