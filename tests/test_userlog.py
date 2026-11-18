"""User log: every login of a user (also refused and failed client logins), shown in
the Users list of the web GUI and with USER LOG on the console. And [web] token_login:
the web GUI opens without the secret token unless it is switched on."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from prcore import auth
from tinybox import clientproto
from tinybox.adapters import web
from tinybox.adapters.sysop import MonitorFilter, SysopConsole

from tests.test_tinybox import login, make_app, type_lines
from tests.test_web import request


class UserLogStore(unittest.TestCase):
    def setUp(self):
        self.app = make_app()

    def events(self, base="OE3ABC"):
        return [(r["call"], r["via"], r["event"]) for r in self.app.store.userlog_list(base)]

    def test_login_and_logout_per_base_call(self):
        s, _ = login(self.app, "OE3ABC-7")
        s.end()
        s2, _ = login(self.app, "OE3ABC")
        s2.end(lost=True)
        login(self.app, "OE3XYZ")
        self.assertEqual(self.events(), [("OE3ABC", "telnet", "logout"),
                                         ("OE3ABC", "telnet", "login"),
                                         ("OE3ABC-7", "telnet", "logout"),
                                         ("OE3ABC-7", "telnet", "login")])
        rows = self.app.store.userlog_list("OE3ABC")
        self.assertTrue(rows[0]["detail"].startswith("lost, "))
        self.assertTrue(rows[2]["detail"].startswith("disc, "))
        self.assertEqual(len(self.app.store.userlog_list()), 5)       # all stations
        self.assertEqual(len(self.app.store.userlog_list("OE3ABC", limit=1)), 1)

    def test_sysop_console_is_no_user(self):
        sysop = self.app.cfg.station.local_sysop
        self.app.service.login(sysop, "sysop")
        self.assertEqual(self.app.store.userlog_list(), [])

    def test_refused_ban(self):
        self.app.service.user_event("OE3ABC-1", "radio", "refused", "banned")
        self.assertEqual(self.events(), [("OE3ABC-1", "radio", "refused")])

    def test_a_broken_log_never_breaks_the_login(self):
        with mock.patch.object(self.app.store, "userlog_add", side_effect=RuntimeError("x")), \
                self.assertLogs("tinybox.service", "ERROR"):
            s, t = login(self.app, "OE3ABC")
        self.assertIn("OE3ABC", t.take())

    def test_console_user_log(self):
        s, _ = login(self.app, "OE3ABC-7")
        s.end()
        out = []
        con = SysopConsole(self.app, MonitorFilter(True), lambda *l: out.extend(l))
        con.handle_line("USER LOG oe3abc")
        text = "\n".join(out)
        self.assertIn("OE3ABC-7  telnet  login", text)
        self.assertIn("logout    disc, ", text)
        self.assertLess(text.index(" login "), text.index(" logout "))    # oldest first
        out.clear()
        con.handle_line("USER LOG OE9ZZZ")
        self.assertIn("OE9ZZZ: no login logged.", "\n".join(out))


class UserLogClientLogin(unittest.TestCase):
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
        nonce = t.take().split("//AUTH? n=", 1)[1].split()[0]
        return s, nonce

    def last(self):
        r = self.app.store.userlog_list("OE3ABC", limit=1)[0]
        return r["event"], r["detail"]

    def test_wait_released_and_wrong_signature(self):
        s, n = self.hello()
        with self.assertLogs("tinybox.clientproto", "WARNING"):
            type_lines(s, f"//AUTH sig={self.key.sign_login(self.box, 'OE3ABC', n)} pub={self.key.pub}")
        self.assertEqual(self.last(), ("auth_wait", f"key {self.key.fp} waits for release"))
        SysopConsole(self.app, MonitorFilter(True), lambda *l: None).handle_line("USER OK oe3abc")
        s, n = self.hello()
        type_lines(s, f"//AUTH sig={self.key.sign_login(self.box, 'OE3ABC', n)} pub={self.key.pub}")
        self.assertEqual(self.last(), ("auth", f"key {self.key.fp}"))
        s, n = self.hello()
        other = auth.Identity(Path(self.tmp.name) / "other.key")
        with self.assertLogs("tinybox.clientproto", "WARNING"):
            type_lines(s, f"//AUTH sig={other.sign_login(self.box, 'OE3ABC', n)} pub={self.key.pub}")
        self.assertEqual(self.last(), ("auth_fail", "wrong signature"))


class WebUserLogAndTokenLogin(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = make_app()
        self.app.cfg.storage = dataclasses.replace(self.app.cfg.storage,
                                                   data_dir=Path(self.tmp.name))
        self.app.cfg.web = dataclasses.replace(self.app.cfg.web, port=0)
        self.app.stop_event = asyncio.Event()

    def run_async(self, coro_fn):
        async def wrapper():
            server = await web.start(self.app)
            try:
                return await coro_fn(server)
            finally:
                server.close()
                await server.server.wait_closed()
        return asyncio.run(wrapper())

    def test_default_is_no_token_login(self):
        self.assertFalse(self.app.cfg.web.token_login)          # the example file: no

        async def scenario(s):
            r = {"url": self.app.web_login_url}
            r["api_without"] = (await request(s.port, "GET", "/api/status"))[0]
            r["root"] = (await request(s.port, "GET", "/"))[0]   # -> /login
            st, hdrs, _ = await request(s.port, "GET", "/login")
            r["login"] = st
            cookie = hdrs["set-cookie"].split(";")[0].split("=", 1)[1]
            _, _, p = await request(s.port, "GET", "/api/session", cookie=cookie)
            csrf = json.loads(p)["csrf"]
            r["status"] = (await request(s.port, "GET", "/api/status", cookie=cookie))[0]
            r["post_no_csrf"] = (await request(s.port, "POST", "/api/messages", cookie=cookie,
                                               body={"to": "ALL"}))[0]
            r["rebinding"] = (await request(s.port, "GET", "/login",
                                            host=f"evil.example:{s.port}"))[0]
            r["csrf"] = csrf
            return r

        r = self.run_async(scenario)
        self.assertNotIn("token", r["url"])
        self.assertEqual(r["api_without"], 401)
        self.assertEqual(r["root"], 303)
        self.assertEqual(r["login"], 303)                    # a session without a token
        self.assertEqual(r["status"], 200)
        self.assertEqual(r["post_no_csrf"], 403)             # CSRF stays
        self.assertEqual(r["rebinding"], 421)                # host check stays

    def test_token_login_on(self):
        self.app.cfg.web = dataclasses.replace(self.app.cfg.web, token_login=True)

        async def scenario(s):
            return (self.app.web_login_url, s.token,
                    (await request(s.port, "GET", "/login"))[0],
                    (await request(s.port, "GET", "/login?token=wrong"))[0],
                    (await request(s.port, "GET", f"/login?token={s.token}"))[0])

        url, token, plain, wrong, right = self.run_async(scenario)
        self.assertIn(f"token={token}", url)
        self.assertEqual(plain, 200)                         # the login form
        self.assertEqual(wrong, 403)
        self.assertEqual(right, 303)

    def test_userlog_api_and_csv(self):
        s1, _ = login(self.app, "OE3ABC-7")
        s1.end()
        self.app.service.user_event("OE3ABC", "radio", "refused", "=cmd|' /C calc'!A0")

        async def scenario(s):
            st, hdrs, _ = await request(s.port, "GET", "/login")
            cookie = hdrs["set-cookie"].split(";")[0].split("=", 1)[1]
            _, _, p = await request(s.port, "GET", "/api/userlog?call=oe3abc-7", cookie=cookie)
            st_csv, h_csv, c = await request(s.port, "GET", "/api/userlog.csv?call=OE3ABC",
                                             cookie=cookie)
            st_no = (await request(s.port, "GET", "/api/userlog?call=OE3ABC"))[0]
            return json.loads(p), st_csv, h_csv, c.decode(), st_no

        rows, st_csv, h_csv, csv_text, st_no = self.run_async(scenario)
        self.assertEqual([r["event"] for r in rows], ["refused", "logout", "login"])
        self.assertEqual(st_csv, 200)
        self.assertIn("tinybox-userlog-", h_csv["content-disposition"])
        self.assertTrue(csv_text.startswith("t,call,via,event,detail"))
        self.assertIn("'=cmd", csv_text)                     # no formula in a spreadsheet
        self.assertEqual(st_no, 401)
        app_js = (Path(__file__).resolve().parent.parent / "tinybox/web/app.js").read_text(
            encoding="utf-8")
        self.assertIn('api("userlog?call="', app_js)


if __name__ == "__main__":
    unittest.main()
