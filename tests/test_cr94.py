"""CR94 (Variante B): the sysop over the radio only through the client - his own
call, logged in with the key released here, every console command signed."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from prcore import auth
from tbclient.core import ClientCore
from tinybox import clientproto

from tests.test_tbclient import client_cfg
from tests.test_tinybox import login, make_app, type_lines


class AdminChannel(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(clientproto, "REQUIRE_AUTH", True)
        p.start()
        self.addCleanup(p.stop)
        self.app = make_app()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.key = auth.Identity(Path(self.tmp.name) / "identity.key")
        self.box = self.app.cfg.station.mailbox_call
        self.ctr = 0

    def logon(self, call="OE3GAS-7", status="active"):
        self.app.store.key_put(auth.base(call), self.key.pub, status)
        s, t = login(self.app, call)
        s.sysop = False                          # as over the radio: the call gives nothing
        type_lines(s, "//CLIENT TB1 v=2026.11.10 caps=CHAT,SYNC,ADM")
        n = t.take().split("//AUTH? n=", 1)[1].split()[0]
        type_lines(s, f"//AUTH sig={self.key.sign_login(self.box, call, n)} pub={self.key.pub}")
        return s, t, n, t.take()

    def adm(self, s, n, cmd, call="OE3GAS"):
        self.ctr += 1
        line = f"//ADM {cmd}"
        sig = self.key.sign_command(self.box, call, n, self.ctr, line)
        type_lines(s, f"{line} c={self.ctr} sig={sig}")

    def test_sysop_runs_console_commands(self):
        s, t, n, ok = self.logon()
        self.assertIn("ADM", ok.split("caps=", 1)[1].split()[0])
        with self.assertLogs("tinybox.clientproto", "WARNING"):
            self.adm(s, n, "STATUS")
        out = t.take()
        self.assertIn("//ADM> ", out)
        self.assertIn("//ADMEND ok", out)
        with self.assertLogs("tinybox.clientproto", "WARNING"):
            self.adm(s, n, "WEB")                                   # the login link: never
        self.assertIn("//ADMEND unknown", t.take())

    def test_unsigned_or_other_user_refused(self):
        s, t, n, _ = self.logon()
        with self.assertLogs("tinybox.clientproto", "WARNING"):
            type_lines(s, "//ADM SHUTDOWN")                          # slipped into the link
        self.assertIn("//ADMEND sig_missing", t.take())
        s, t, n, ok = self.logon("OE1ABC-7")                         # a normal user
        self.assertNotIn("ADM", ok.split("caps=", 1)[1].split()[0])
        with self.assertLogs("tinybox.clientproto", "WARNING"):
            self.adm(s, n, "STATUS", call="OE1ABC")
        self.assertIn("//ADMEND refused", t.take())

    def test_terminal_with_sysop_call_cannot(self):
        s, t = login(self.app, "OE3GAS-7")
        s.sysop = False
        type_lines(s, "//ADM STATUS")
        self.assertIn("//ERR not a client session", t.take())


class ClientSide(unittest.TestCase):
    def test_admin_sends_signed(self):
        with tempfile.TemporaryDirectory() as tmp:
            core = ClientCore(client_cfg(tmp))
            sent = []
            core._send = sent.append
            core.state = "online"
            self.assertFalse(core.admin("STATUS"))                  # no ADM granted
            core._on_line("//AUTH? n=abc123 box=OE3GAS-1")
            core._on_line("//OK TB1 caps=CHAT,ADM")
            self.assertTrue(core.admin("STATUS"))
            plain, ctr, sig = clientproto.split_signature(sent[-1])
            self.assertEqual(plain, "//ADM STATUS")
            msg = auth.command_message("OE3GAS-1", "OE3GAS", "abc123", ctr, plain)
            self.assertTrue(auth.verify(core.identity.public, msg, auth.b64d(sig, 64)))
            core._on_line("//ADM> TinyBox 1.0.0 up")
            core._on_line("//ADMEND ok")
            snap = core.snapshot()
            self.assertTrue(snap["adm"])
            self.assertEqual([e["k"] for e in snap["adm_log"]], ["cmd", "out", "end"])


if __name__ == "__main__":
    unittest.main()
