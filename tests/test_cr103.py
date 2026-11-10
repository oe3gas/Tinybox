"""CR103: APRS statistics in a thread, kept for a few seconds - the client must not stand still."""

from __future__ import annotations

import asyncio
import tempfile
import threading
import time
import unittest

from tbclient.core import ClientCore
from tbclient.web import WebServer
from tests.test_tbclient import client_cfg


class Eval(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.web = WebServer(ClientCore(client_cfg(tmp.name, web_host="127.0.0.1", web_port=0)))
        self.calls = []
        st = self.web.core.aprs_stats

        def slow_report(window=0, now=None):            # a long "All" evaluation
            self.calls.append(threading.current_thread() is threading.main_thread())
            time.sleep(0.3)
            return {"window": window, "n": len(self.calls)}
        st.report = slow_report

    async def test_loop_goes_on(self):
        ticks = 0

        async def tick():
            nonlocal ticks
            while True:
                await asyncio.sleep(0.02)
                ticks += 1
        t = asyncio.ensure_future(tick())
        r = await self.web._aprs_eval("stats", 0)
        t.cancel()
        self.assertEqual(r["n"], 1)
        self.assertEqual(self.calls, [False])          # not in the event loop's thread
        self.assertGreater(ticks, 5)                   # the loop kept running meanwhile

    async def test_same_query_once(self):
        a, b = await asyncio.gather(self.web._aprs_eval("stats", 0), self.web._aprs_eval("stats", 0))
        self.assertEqual(a, b)
        self.assertEqual(len(self.calls), 1)           # two tabs at once: one evaluation
        await self.web._aprs_eval("stats", 0)
        self.assertEqual(len(self.calls), 1)           # within APRS_CACHE_SEC: kept
        await self.web._aprs_eval("stats", 3600)
        self.assertEqual(len(self.calls), 2)           # another window: a new evaluation


if __name__ == "__main__":
    unittest.main()
