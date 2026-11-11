"""CR115: BAN (shut out, data stays, UNBAN lets back) and PURGE (ban and delete his
keys, profile, logins, chat lines, board files - mail, bulletins and the connection
log stay)."""

from __future__ import annotations

import asyncio
import unittest

from tinybox.adapters.sysop import MonitorFilter, SysopConsole
from tinybox.service import ServiceError

from tests.test_agw import start, stop
from tests.test_tinybox import login, make_app, type_lines


def console(app, line):
    out = []
    SysopConsole(app, MonitorFilter(True), out.append).handle_line(line)
    return "\n".join(out)


class Ban(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        st = self.app.store
        st.key_put("OE1ABC", "A" * 43, "active")
        st.profile_set("OE1ABC", "Hans", "JN88", "OE3XBS", 1)
        st.user_login("OE1ABC-7")
        st.user_login("OE1ABC")
        st.user_login("OE1ABCD")                         # another call - stays
        self.s, self.t = login(self.app, "OE1ABC-7")
        type_lines(self.s, "S OE3GAS", "Hello", "a line", "/EX")

    def test_ban_ends_session_keeps_data_unban(self):
        self.app.registry.add(self.s)
        out = console(self.app, "BAN oe1abc-3 spam")
        self.assertIn("OE1ABC: banned (all SSIDs)", out)
        self.assertIn("1 session(s) ended", out)
        self.assertTrue(self.s.closed)
        self.assertIn("no access to this TinyBox", self.t.take())
        self.assertTrue(self.app.service.ban_of("OE1ABC-9"))
        self.assertEqual(self.app.store.purge_counts("OE1ABC")["keys"], 1)     # data stays
        self.assertIn("OE1ABC   banned", console(self.app, "BAN"))
        self.assertIn("may connect again", console(self.app, "UNBAN OE1ABC"))
        self.assertIsNone(self.app.service.ban_of("OE1ABC"))

    def test_purge_shows_first_then_deletes(self):
        out = console(self.app, "PURGE OE1ABC")
        self.assertIn("1 keys, 1 profile, 2 logins", out)
        self.assertIn("PURGE OE1ABC CONFIRM", out)
        self.assertEqual(self.app.store.purge_counts("OE1ABC")["profile"], 1)  # nothing yet
        out = console(self.app, "PURGE OE1ABC CONFIRM troll")
        self.assertIn("purged", out)
        c = self.app.store.purge_counts("OE1ABC")
        self.assertEqual(sum(c.values()), 0)
        self.assertEqual(self.app.store.purge_counts("OE1ABCD")["logins"], 1)
        self.assertIsNotNone(self.app.store.get(1))                 # mail stays
        self.assertEqual(self.app.store.ban_get("OE1ABC")["purged"], 1)

    def test_sysop_never_banned(self):
        sysop = self.app.cfg.station.sysop_call
        with self.assertRaises(ServiceError):
            self.app.service.ban(sysop)
        self.assertIsNone(self.app.service.ban_of(sysop))


class Connect(unittest.TestCase):
    def test_banned_station_refused_over_the_radio(self):
        async def scenario():
            app = make_app()
            app.service.ban("OE1ABC", "test")
            dw, server, adapter, task = await start(app)
            dw.connect("OE1ABC-7")
            await asyncio.wait_for(dw.disconnected.wait(), 5)
            await stop(server, task, dw)
            return app, dw

        with self.assertLogs("tinybox", "WARNING"):
            app, dw = asyncio.run(scenario())
        out = dw.output_for("OE1ABC-7")
        self.assertIn("no access to this TinyBox", out)
        self.assertNotIn("hello", out)
        self.assertEqual(len(app.registry), 0)


if __name__ == "__main__":
    unittest.main()
