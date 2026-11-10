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


class MoveCopy(unittest.TestCase):
    """CR21 (with CR94): the sysop moves and copies bulletins - console, web GUI and
    over the radio through the client."""

    def setUp(self):
        self.app = make_app()
        self.svc = self.app.service
        self.b = self.svc.create(from_call="OE1ABC", to_call="ALL", type="B", subject="Treffen",
                                 body="Freitag 19 Uhr", origin="sysop", sysop=True)

    def test_move_keeps_content_new_number(self):
        old = self.app.store.get(self.b)
        new = self.svc.move_bulletin(self.b, "WX", "OE3GAS")
        self.assertIsNone(self.app.store.get(self.b))
        m = self.app.store.get(new)
        self.assertGreater(new, self.b)
        self.assertEqual((m.to_call, m.from_call, m.subject, m.body, m.bid, m.created, m.fwd),
                         ("WX", "OE1ABC", "Treffen", "Freitag 19 Uhr", old.bid, old.created, ""))
        gone = [i for i, _, typ, to, _ in self.app.store.gone_since(0)]
        self.assertIn(self.b, gone)                         # clients of ALL drop it (//D)

    def test_copy(self):
        new = self.svc.copy_bulletin(self.b, "WX", "OE3GAS")
        m, old = self.app.store.get(new), self.app.store.get(self.b)
        self.assertEqual(m.to_call, "WX")
        self.assertTrue(m.body.startswith(f"(copied from ALL #{self.b})\n"))
        self.assertNotEqual(m.bid, old.bid)

    def test_refused(self):
        from tinybox.service import ServiceError
        for rubric in ("ALL", "TBNEWS", "70CM-"):
            with self.assertRaises(ServiceError):
                self.svc.move_bulletin(self.b, rubric, "OE3GAS")
        p = self.svc.create(from_call="OE1ABC", to_call="OE3GAS", type="P", subject="x",
                            body="y", origin="telnet")
        with self.assertRaises(ServiceError):
            self.svc.copy_bulletin(p, "WX", "OE3GAS")

    def test_console(self):
        from tinybox.adapters.sysop import MonitorFilter, SysopConsole
        out = []
        c = SysopConsole(self.app, MonitorFilter(True), out.append)
        c.handle_line(f"COPY {self.b} WX")
        c.handle_line(f"MOVE {self.b} DX")
        c.handle_line("MOVE x")
        text = "".join(out)
        self.assertIn("copied to WX", text)
        self.assertIn("moved to DX", text)
        self.assertIn("Usage: MOVE", text)
        c.handle_line(f"KILL {self.b}")
        self.assertIn("No such message", "".join(out))


class SysopOverTheClient(unittest.TestCase):
    setUp, logon, adm = AdminChannel.setUp, AdminChannel.logon, AdminChannel.adm

    def test_move_kill_and_warn(self):
        b = self.app.service.create(from_call="OE1ABC", to_call="ALL", type="B", subject="x",
                                    body="y", origin="sysop", sysop=True)
        s, t, n, _ = self.logon()
        with self.assertLogs("tinybox.clientproto", "WARNING"):
            self.adm(s, n, f"MOVE {b} WX")
        self.assertIn("moved to WX", t.take())
        new = max(m.id for m in self.app.store.list_messages())
        with self.assertLogs("tinybox.clientproto", "WARNING"):
            self.adm(s, n, f"KILL {new}")
        self.assertIn(f"Msg {new} killed", t.take())
        # a bulletin to WARN from the sysop's client is the sysop's (TB-14: warning page)
        self.ctr += 1
        line = "//SEND B WARN 1 mid=abcdefgh77"
        sig = self.key.sign_command(self.box, "OE3GAS", n, self.ctr, line, ["Sturm", "Achtung"])
        type_lines(s, f"{line} c={self.ctr} sig={sig}", "Sturm", "Achtung")
        self.assertIn("//SENT", t.take())
        self.assertEqual(self.app.store.list_messages()[-1].origin, "sysop")
