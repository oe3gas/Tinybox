"""CR93: the client logs in with the key of its user (Ed25519, stage 1) and signs
the critical commands (stage 2)."""

from __future__ import annotations

import dataclasses
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from prcore import auth
from tbclient.core import ClientCore
from tinybox import clientproto, keys
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
        self.assertEqual(self.app.store.key_get("OE3ABC", self.key.pub)["status"], "pending")
        self.assertTrue(any(self.key.fp in m.body for m in self.app.store.list_messages()
                            if m.to_call == self.app.cfg.station.sysop_call))
        # the sysop releases it
        out = []
        SysopConsole(self.app, MonitorFilter(True), out.append).handle_line("USER OK oe3abc")
        self.assertEqual(self.app.store.key_get("OE3ABC", self.key.pub)["status"], "active")
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

    def test_second_device_and_revoked(self):
        # one key per device (OE3GAS, 10.11.2026): a second device waits for its own release
        self.app.store.key_put("OE3ABC", self.key.pub, "active")
        home = auth.Identity(Path(self.tmp.name) / "home.key")
        s, t, n = self.hello()
        with self.assertLogs("tinybox.clientproto", "WARNING"):
            type_lines(s, f"//AUTH sig={home.sign_login(self.box, 'OE3ABC', n)} pub={home.pub} "
                          "dev=SHACK-PC")
        self.assertIn(f"//AUTHWAIT fp={home.fp}", t.take())
        row = self.app.store.key_get("OE3ABC", home.pub)
        self.assertEqual((row["status"], row["device"]), ("pending", "SHACK-PC"))
        s, t, n = self.hello()                                       # the first one still works
        self.answer(s, n)
        self.assertIn("//OK TB1", t.take())
        out = []
        c = SysopConsole(self.app, MonitorFilter(True), out.append)
        c.handle_line("USER OK OE3ABC")                              # the only one not active
        self.assertEqual(self.app.store.key_get("OE3ABC", home.pub)["status"], "active")
        c.handle_line("USER REVOKE OE3ABC")                          # two fit: name it
        self.assertIn("several keys", "".join(out))
        c.handle_line(f"USER REVOKE OE3ABC {self.key.fp[:4]}")
        self.assertEqual(self.app.store.key_get("OE3ABC", self.key.pub)["status"], "revoked")
        s, t, n = self.hello()
        self.answer(s, n)
        self.assertIn("//ERR auth revoked", t.take())
        s, t, n = self.hello()                                       # the other device: still in
        type_lines(s, f"//AUTH sig={home.sign_login(self.box, 'OE3ABC', n)} pub={home.pub}")
        self.assertIn("//OK TB1", t.take())

    def test_at_most_five_devices(self):
        for i in range(5):
            self.app.store.key_put("OE3ABC", auth.Identity(Path(self.tmp.name) / f"{i}.key").pub,
                                   "active")
        s, t, n = self.hello()
        with self.assertLogs("tinybox.clientproto", "WARNING"):
            self.answer(s, n)
        self.assertIn("//ERR auth too_many_keys", t.take())

    def test_signed_for_another_box_is_refused(self):
        self.app.store.key_put("OE3ABC", self.key.pub, "active")
        s, t, n = self.hello()
        with self.assertLogs("tinybox.clientproto", "WARNING"):
            type_lines(s, f"//AUTH sig={self.key.sign_login('OE1XYZ', 'OE3ABC', n)} "
                          f"pub={self.key.pub}")
        self.assertIn("bad_signature", t.take())

    def test_user_console(self):
        self.app.store.key_put("OE3ABC", self.key.pub, "pending", note="from OE3ABC-7",
                               device="PC2")
        out = []
        c = SysopConsole(self.app, MonitorFilter(True), out.append)
        c.handle_line("USER")
        self.assertIn(self.key.fp, "".join(out))
        self.assertIn("PC2", "".join(out))
        c.handle_line("USER REVOKE OE3ABC")
        self.assertEqual(self.app.store.key_get("OE3ABC", self.key.pub)["status"], "revoked")
        c.handle_line("USER DEL OE3ABC")
        self.assertIsNone(self.app.store.key_get("OE3ABC", self.key.pub))
        c.handle_line("USER OK")
        self.assertIn("Usage: USER", "".join(out))

    def test_old_table_is_taken_over(self):
        import sqlite3

        from tinybox.store import Store
        db = Path(self.tmp.name) / "old.db"
        with sqlite3.connect(db) as con:
            con.execute("CREATE TABLE user_keys (call TEXT PRIMARY KEY, pub TEXT NOT NULL, "
                        "status TEXT NOT NULL, created TEXT NOT NULL, changed TEXT NOT NULL, "
                        "note TEXT NOT NULL DEFAULT '')")
            con.execute("INSERT INTO user_keys VALUES ('OE3GAS', ?, 'active', 'x', 'x', '')",
                        (self.key.pub,))
        st = Store(db)
        self.assertEqual(st.key_get("OE3GAS", self.key.pub)["status"], "active")
        self.assertIsNone(st._db.execute("SELECT 1 FROM sqlite_master WHERE name='user_keys'")
                          .fetchone())


class ClientSide(unittest.TestCase):
    def test_answers_the_challenge(self):
        with tempfile.TemporaryDirectory() as tmp:
            core = ClientCore(client_cfg(tmp))
            sent = []
            core._send = sent.append
            core._on_line("//AUTH? n=abcDEF123 box=OE3XTC-1")
            [line] = sent
            args = dict(x.split("=", 1) for x in line.split()[1:])
            self.assertTrue(args["dev"])
            pub, sig = auth.b64d(args["pub"], 32), auth.b64d(args["sig"], 64)
            self.assertTrue(auth.verify(pub, auth.login_message("OE3XTC-1", "OE3GAS", "abcDEF123"),
                                        sig))
            core._on_line(f"//AUTHWAIT fp={core.identity.fp}")
            self.assertEqual(core.auth["state"], "wait")
            core._on_line("//ERR auth revoked")
            self.assertEqual((core.auth["state"], core.auth["reason"]), ("refused", "revoked"))
            core._on_line("//OK TB1 caps=CHAT")
            self.assertEqual(core.auth["state"], "ok")
            self.assertTrue((Path(tmp) / "identity.key").is_file())


class SignedCommands(unittest.TestCase):
    """Stage 2: after the login //SEND, //KILL, //SYNC k= and //PROF come signed."""

    def setUp(self):
        p = mock.patch.object(clientproto, "REQUIRE_AUTH", True)
        p.start()
        self.addCleanup(p.stop)
        self.app = make_app()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.key = auth.Identity(Path(self.tmp.name) / "identity.key")
        self.box = self.app.cfg.station.mailbox_call
        self.app.store.key_put("OE3ABC", self.key.pub, "active")
        self.s, self.t = login(self.app, "OE3ABC-7")
        self.n = self.logon()
        self.ctr = 0

    def logon(self) -> str:
        type_lines(self.s, "//CLIENT TB1 v=2026.11.10 caps=CHAT,SYNC,SYNC2,PROF")
        out = self.t.take()
        n = out.split("//AUTH? n=", 1)[1].split()[0]
        type_lines(self.s, f"//AUTH sig={self.key.sign_login(self.box, 'OE3ABC-7', n)} "
                           f"pub={self.key.pub}")
        self.assertIn("//OK TB1", self.t.take())
        return n

    def signed(self, line, payload=(), key=None, ctr=None):
        if ctr is None:
            self.ctr += 1
            ctr = self.ctr
        sig = (key or self.key).sign_command(self.box, "OE3ABC", self.n, ctr, line, payload)
        return f"{line} c={ctr} sig={sig}"

    def mail(self) -> int:
        return self.app.service.create(from_call="OE3ABC", to_call="OE1XYZ", type="P",
                                       subject="x", body="y", origin="telnet")

    def test_kill(self):
        m = self.mail()
        with self.assertLogs("tinybox.clientproto", "WARNING"):
            type_lines(self.s, f"//KILL {m}")                       # injected: no signature
        self.assertIn("//ERR kill sig_missing\r//KEND", self.t.take())
        self.assertIsNotNone(self.app.store.get(m))
        line = self.signed(f"//KILL {m}")
        type_lines(self.s, line)
        self.assertIn(f"//K {m} ok", self.t.take())
        self.assertIsNone(self.app.store.get(m))
        with self.assertLogs("tinybox.clientproto", "WARNING"):
            type_lines(self.s, line)                                 # recorded and sent again
        self.assertIn("sig_replay", self.t.take())
        other = auth.Identity(Path(self.tmp.name) / "other.key")
        with self.assertLogs("tinybox.clientproto", "WARNING"):
            type_lines(self.s, self.signed(f"//KILL {self.mail()}", key=other))
        self.assertIn("//ERR kill sig_bad", self.t.take())

    def test_send_covers_the_text(self):
        line = "//SEND B ALL 2 mid=abcdefgh12"
        type_lines(self.s, self.signed(line, ["Subject", "line 1", "line 2"]),
                   "Subject", "line 1", "line 2")
        self.assertIn("//SENT ", self.t.take())
        before = len(self.app.store.list_messages())
        with self.assertLogs("tinybox.clientproto", "WARNING"):
            type_lines(self.s, self.signed("//SEND B ALL 2 mid=abcdefgh13",
                                           ["Subject", "line 1", "line 2"]),
                       "Subject", "K 1", "line 2")                  # text changed on the way
        out = self.t.take()
        self.assertIn("//ERR send sig_bad", out)
        self.assertNotIn("Unknown", out)                            # the text ran as nothing
        self.assertEqual(len(self.app.store.list_messages()), before)
        with self.assertLogs("tinybox.clientproto", "WARNING"):
            type_lines(self.s, "//SEND P OE1XYZ 1", "s", "//KILL 1")    # unsigned
        self.assertIn("//ERR send sig_missing", self.t.take())

    def test_profile_and_sync(self):
        type_lines(self.s, "//PROF ?")                              # reading: not signed
        self.assertIn("//PROF -", self.t.take())
        with self.assertLogs("tinybox.clientproto", "WARNING"):
            type_lines(self.s, "//PROF t=1 loc=JN88 home= name=Fake")
        self.assertIn("//PROF ERR sig_missing", self.t.take())
        type_lines(self.s, self.signed("//PROF t=1 loc=JN88 home= name=Gerhard"))
        self.assertIn("//PROF OK", self.t.take())
        type_lines(self.s, "//SYNC seq=0 max=2000")                 # no k=: not signed
        self.assertIn("//SYNCEND", self.t.take())
        with self.assertLogs("tinybox.clientproto", "WARNING"):
            type_lines(self.s, f"//SYNC seq=0 k={self.mail()} max=2000")
        self.assertIn("//ERR sync sig_missing", self.t.take())

    def test_terminal_writes_refused_in_client_mode(self):
        type_lines(self.s, f"K {self.mail()}")
        self.assertIn("Not in client mode", self.t.take())
        type_lines(self.s, "L")                                     # reading stays
        self.assertNotIn("Not in client mode", self.t.take())
        s, t = login(self.app, "OE3ABC-2")                          # a plain terminal: as before
        type_lines(s, f"K {self.mail()}")
        self.assertNotIn("Not in client mode", t.take())

    def test_client_again_means_a_new_login(self):
        type_lines(self.s, "//CLIENT TB1 v=2026.11.10 caps=CHAT,SYNC")
        out = self.t.take()
        self.assertIn("//AUTH? n=", out)
        self.assertNotIn(self.n, out)
        self.assertFalse(self.s.auth)


class ClientSigns(unittest.TestCase):
    def test_signed_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            core = ClientCore(client_cfg(tmp))
            core._send = lambda line: None
            self.assertEqual(core.signed("//KILL 5"), "//KILL 5")       # no login: as before
            core._on_line("//AUTH? n=xyz123 box=OE3XTC-1")
            pub = core.identity.public
            for n in (1, 2):
                line = core.signed("//SEND P OE1XYZ 1 mid=abcdefgh", ["subj", "text"])
                plain, ctr, sig = clientproto.split_signature(line)
                self.assertEqual((plain, ctr), ("//SEND P OE1XYZ 1 mid=abcdefgh", n))
                msg = auth.command_message("OE3XTC-1", "OE3GAS", "xyz123", n, plain,
                                           ["subj", "text"])
                self.assertTrue(auth.verify(pub, msg, auth.b64d(sig, 64)))
            core._clear_chat()
            self.assertEqual(core.signed("//KILL 5"), "//KILL 5")


class Certificates(unittest.TestCase):
    """Stage 3: the home BBS confirms the key, another TinyBox that trusts it
    lets the user log in."""

    def setUp(self):
        p = mock.patch.object(clientproto, "REQUIRE_AUTH", True)
        p.start()
        self.addCleanup(p.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        d = Path(self.tmp.name)
        self.home, self.other = make_app(), make_app()
        for app, name, call in ((self.home, "home", "OE3GAS-1"), (self.other, "other", "OE5XBL-1")):
            app.cfg.storage = dataclasses.replace(app.cfg.storage, data_dir=d / name)
            app.cfg.station = dataclasses.replace(app.cfg.station, mailbox_call=call)
        self.key = auth.Identity(d / "identity.key")
        self.home.store.key_put("OE3ABC", self.key.pub, "active")

    def login(self, app, cert=None):
        s, t = login(app, "OE3ABC-7")
        type_lines(s, "//CLIENT TB1 v=2026.11.10 caps=CHAT")
        n = t.take().split("//AUTH? n=", 1)[1].split()[0]
        box = app.cfg.station.mailbox_call
        type_lines(s, f"//AUTH sig={self.key.sign_login(box, 'OE3ABC', n)} pub={self.key.pub}"
                      + (f" cert={cert}" if cert else ""))
        return s, t

    def cert(self) -> str:
        s, t = self.login(self.home)
        self.assertIn("//OK", t.take())
        type_lines(s, "//CERT?")
        line = t.take().strip()
        self.assertTrue(line.startswith("//CERT TBC1:OE3ABC:"), line)
        return line[7:]

    def test_login_elsewhere_with_the_certificate(self):
        cert = self.cert()
        c = auth.parse_cert(cert)
        self.assertEqual((c["issuer"], c["pub"]), ("OE3GAS-1", self.key.pub))
        with self.assertLogs("tinybox.clientproto", "WARNING"):
            s, t = self.login(self.other, cert)                    # not trusted yet
        self.assertIn("//AUTHWAIT", t.take())
        me = keys.this_box(self.home.service)
        keys.trust_add(self.other.service, me["box"], me["pub"])
        s, t = self.login(self.other, cert)
        self.assertIn("//OK", t.take())
        self.assertEqual((s.auth, s.auth_cert), (True, "OE3GAS-1"))
        self.assertEqual(self.other.store.key_get("OE3ABC", self.key.pub)["status"], "cert")
        type_lines(s, "//CERT?")                                     # only the home BBS issues
        self.assertIn("//CERT -", t.take())
        keys.user_action(self.other.service, "REVOKE", "OE3ABC")     # the sysop there decides
        s, t = self.login(self.other, cert)
        self.assertIn("//ERR auth revoked", t.take())

    def test_bad_certificates(self):
        me = keys.this_box(self.home.service)
        keys.trust_add(self.other.service, me["box"], me["pub"])
        ident = self.home.service.box_identity()
        thief = auth.Identity(Path(self.tmp.name) / "thief.key")
        for cert in (auth.make_cert(ident, "OE3ABC", self.key.pub, "OE3GAS-1", "20200101"),
                     auth.make_cert(ident, "OE3ABC", thief.pub, "OE3GAS-1", "20991231"),
                     auth.make_cert(thief, "OE3ABC", self.key.pub, "OE3GAS-1", "20991231"),
                     "TBC1:garbage"):
            with self.assertLogs("tinybox.clientproto", "WARNING"):
                s, t = self.login(self.other, cert)
            self.assertIn("//AUTHWAIT", t.take(), cert)

    def test_console_trust(self):
        out = []
        c = SysopConsole(self.other, MonitorFilter(True), out.append)
        c.handle_line("TRUST")
        self.assertIn("This box OE5XBL-1", "".join(out))
        me = keys.this_box(self.home.service)
        c.handle_line(f"TRUST ADD OE3GAS-1 {me['pub']}")
        c.handle_line("TRUST")
        self.assertIn(me["fp"], "".join(out))
        c.handle_line("TRUST ADD OE3GAS-1 nonsense")
        self.assertIn("Not a public key", "".join(out))
        c.handle_line("TRUST DEL OE3GAS-1")
        self.assertIsNone(self.other.store.trust_get("OE3GAS-1"))


class ClientCertificate(unittest.TestCase):
    def test_fetch_at_home_send_elsewhere(self):
        with tempfile.TemporaryDirectory() as tmp:
            core = ClientCore(client_cfg(tmp))
            sent = []
            core._send = sent.append
            core._on_line("//AUTH? n=abc123 box=OE3GAS-1")
            core._on_line("//OK TB1 caps=CHAT")
            self.assertIn("//CERT?", sent)
            box = auth.Identity(Path(tmp) / "box.key")
            cert = auth.make_cert(box, "OE3GAS", core.identity.pub, "OE3GAS-1", "20991231")
            core._on_line("//CERT " + cert)
            self.assertEqual(core.settings["certs"]["OE3GAS-1"], cert)
            sent.clear()
            core._on_line("//OK TB1 caps=CHAT")
            self.assertNotIn("//CERT?", sent)                        # still long valid
            core._on_line("//AUTH? n=xyz789 box=OE5XBL-1")
            self.assertTrue(sent[-1].endswith(" cert=" + cert))
            core._on_line("//AUTH? n=xyz780 box=OE3GAS-1")           # at home: no certificate
            self.assertNotIn("cert=", sent[-1])


if __name__ == "__main__":
    unittest.main()
