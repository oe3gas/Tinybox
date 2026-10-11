"""SHUTDOWN with warning to all connected stations (like 'shutdown +1' on Unix)."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from unittest import mock

from pathlib import Path

from tbclient.core import ClientCore
from tinybox import __main__ as tb_main
from tinybox import shutdown
from tinybox.adapters.sysop import MonitorFilter, SysopConsole
from tests.test_tbclient import client_cfg
from tests.test_tinybox import ROOT, login, make_app, type_lines


class ShutdownTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.out = []
        self.console = SysopConsole(self.app, MonitorFilter(False), self.out.append)

    def cmd(self, line):
        self.out.clear()
        self.console.handle_line(line)
        return "".join(self.out)

    def station(self, call, client=False):
        s, t = login(self.app, call)
        self.app.registry.add(s)
        if client:
            type_lines(s, "//CLIENT TB1 caps=CHAT")
        t.take()
        return s, t

    def test_warning_reminders_and_stop(self):
        async def scenario():
            self.app.stop_event = asyncio.Event()
            user, ut = self.station("OE3TEC")
            cl, ct = self.station("OE3ABC", client=True)
            writer, wt = self.station("OE1XYZ")
            type_lines(writer, "SP OE3GAS", "Betreff")        # is typing a message
            wt.take()
            with mock.patch.object(shutdown, "REMINDERS", (1,)):
                out = self.cmd("SHUTDOWN 2")
                self.assertIn("Shutdown in 2 s, 3 station(s) warned", out)
                text = ut.take()
                self.assertIn("*** System message from OE3GAS: OE3GAS-1 goes down in "
                              "2 seconds. Please finish and disconnect (B). ***", text)
                self.assertTrue(text.startswith("\r") and text.endswith(") > "),
                                repr(text))
                self.assertTrue(ct.take().startswith("//SYS 2 *** System message"))
                w = wt.take()
                self.assertIn("goes down in 2 seconds", w)
                self.assertNotIn("TinyBox (", w)              # no prompt while writing
                self.assertIn("Shutdown pending", self.cmd("STATUS"))
                # a station connecting now is warned at login
                late, lt = login(self.app, "OE3LAT")
                self.assertIn("goes down in", lt.take())
                await asyncio.wait_for(self.app.stop_event.wait(), 5)
                self.assertIn("goes down in 1 second.", ut.take())
        asyncio.run(scenario())

    def test_cancel_now_and_usage(self):
        async def scenario():
            self.app.stop_event = asyncio.Event()
            user, ut = self.station("OE3TEC")
            self.cmd("SHUTDOWN")                                # default 60 s
            self.assertEqual(self.app.shutdown.seconds_left(), 60)
            self.assertIn("goes down in 60 seconds", ut.take())
            self.assertIn("Shutdown cancelled", self.cmd("SHUTDOWN CANCEL"))
            self.assertIn("shutdown of OE3GAS-1 cancelled", ut.take())
            self.assertIsNone(self.app.shutdown.seconds_left())
            self.assertIsNone(self.app.service.shutdown_left)
            self.assertIn("No shutdown pending", self.cmd("SHUTDOWN CANCEL"))
            self.assertIn("Usage", self.cmd("SHUTDOWN soon"))
            self.assertFalse(self.app.stop_event.is_set())
            self.assertIn("Shutting down", self.cmd("SHUTDOWN NOW"))
            self.assertTrue(self.app.stop_event.is_set())
        asyncio.run(scenario())

    def test_client_shows_message(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp, link="telnet"))
                core._on_line("//SYS 60 *** System message ... ***")
                snap = core.snapshot()
                self.assertEqual((snap["sysmsg"]["left"], snap["sysmsg"]["text"]),
                                 (60, "*** System message ... ***"))
                core._on_state("offline", "disconnected")
                self.assertIsNone(core.snapshot()["sysmsg"])
        asyncio.run(scenario())


class RestartTests(unittest.TestCase):
    """CR22: RESTART in the sysop console (checks tinybox.conf first)."""

    def setUp(self):
        self.app = make_app()
        self.app.config_path = str(ROOT / "tinybox.conf.example")
        self.out = []
        self.console = SysopConsole(self.app, MonitorFilter(False), self.out.append)

    def cmd(self, line):
        self.out.clear()
        self.console.handle_line(line)
        return "".join(self.out)

    def test_restart_now_and_bad_config(self):
        async def scenario():
            self.app.stop_event = asyncio.Event()
            with tempfile.TemporaryDirectory() as tmp:
                bad = Path(tmp) / "tinybox.conf"
                bad.write_text("[station]\nmailbox_call = nonsense!\n", encoding="utf-8")
                self.app.config_path = str(bad)
                out = self.cmd("RESTART NOW")
                self.assertIn("tinybox.conf has an error, NOT restarted", out)
                self.assertFalse(self.app.stop_event.is_set() or self.app.restart)
            self.app.config_path = str(ROOT / "tinybox.conf.example")
            self.assertIn("Usage: RESTART", self.cmd("RESTART later"))
            out = self.cmd("RESTART")                     # nobody connected: at once
            self.assertIn("checked: OK", out)
            self.assertIn("restarts now", out)
            self.assertTrue(self.app.stop_event.is_set() and self.app.restart)
        asyncio.run(scenario())

    def test_restart_with_warning(self):
        async def scenario():
            self.app.stop_event = asyncio.Event()
            s, t = login(self.app, "OE3TEC")
            self.app.registry.add(s)
            t.take()
            with mock.patch.object(shutdown, "REMINDERS", ()):
                self.assertIn("Restart in 1 s, 1 station(s) warned", self.cmd("RESTART 1"))
                self.assertIn("OE3GAS-1 restarts in 1 second and is back shortly", t.take())
                await asyncio.wait_for(self.app.stop_event.wait(), 5)
            self.assertTrue(self.app.restart)
        asyncio.run(scenario())

    def test_restart_cancel(self):
        async def scenario():
            self.app.stop_event = asyncio.Event()
            s, t = login(self.app, "OE3TEC")
            self.app.registry.add(s)
            self.cmd("RESTART 60")
            self.assertIn("Shutdown cancelled", self.cmd("RESTART CANCEL"))
            self.assertFalse(self.app.restart)
            # a later SHUTDOWN is a real shutdown again
            self.cmd("SHUTDOWN 60")
            self.assertFalse(self.app.shutdown.restart)
            self.app.shutdown.cancel()
        asyncio.run(scenario())

    def test_exit_code_for_batch_file(self):
        with mock.patch.dict("os.environ", {"TINYBOX_LAUNCHER": "1"}):
            self.assertEqual(tb_main.restart_process([]), 3)
        with mock.patch.dict("os.environ", {"TINYBOX_LAUNCHER": ""}), \
                mock.patch("os.execv") as execv:
            tb_main.restart_process(["-c", "x.conf"])
            self.assertEqual(execv.call_args[0][1][1:], ["-m", "tinybox", "-c", "x.conf"])


if __name__ == "__main__":
    unittest.main()
