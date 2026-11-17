"""CR72: GETFC - the weather forecast for one's own locator, terminal and client."""

from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path
from unittest import mock

from tinybox import forecast, profiles
from tests.test_tinybox import login, make_app, type_lines

FIXTURE = Path(__file__).parent / "fixtures" / "geosphere_nwp_jn88bn.json"


class ForecastTests(unittest.TestCase):
    def setUp(self):
        if not forecast.available():
            self.skipTest("geosphere_prognose.py not here")
        forecast._cache.clear()
        forecast._asked.clear()
        self.api = mock.patch.object(forecast.gp, "api_get",
                                     return_value=json.loads(FIXTURE.read_text(encoding="utf-8")))
        self.calls = self.api.start()
        self.app = make_app()

    def tearDown(self):
        self.api.stop()

    def run_session(self, *lines, caps=None):
        async def go():
            s, t = login(self.app, "OE1ABC")
            if caps:
                type_lines(s, f"//CLIENT TB1 caps={caps}")
            t.take()
            type_lines(s, *lines)
            for _ in range(50):
                await asyncio.sleep(0.02)
                if "//FC " in t.buf or "Quelle:" in t.buf or "No forecast" in t.buf:
                    break
            return s, t.take()
        return asyncio.run(go())

    def test_terminal_with_locator(self):
        _, out = self.run_session("GETFC jn88bn")
        self.assertIn("Forecast for JN88BN is fetched", out)
        self.assertIn("Prognose JN88BN", out)
        self.assertIn("Quelle: GeoSphere Austria", out)

    def test_profile_locator_and_cache(self):
        profiles.save(self.app.store, "OE1ABC", {"loc": "JN88BN"})
        self.run_session("GETFC")
        self.run_session("GETFC")
        self.assertEqual(self.calls.call_count, 1)                 # the second from the cache

    def test_errors_in_words(self):
        for arg, word in (("", "MYLOC"), ("JN88", "too coarse"), ("IO91WM", "outside"),
                          ("XX", "invalid")):
            forecast._asked.clear()
            _, out = self.run_session(f"GETFC {arg}".strip())
            self.assertIn(word, out, arg)
        self.assertEqual(self.calls.call_count, 0)

    def test_limit_per_hour(self):
        for _ in range(forecast.PER_HOUR):
            self.assertTrue(forecast._allowed("OE1ABC-3"))
        self.assertFalse(forecast._allowed("OE1ABC"))

    def test_client_compact_line(self):
        _, out = self.run_session("//GETFC JN88BN", caps="CHAT,FC")
        line = [x for x in out.split("\r") if x.startswith("//FC ")][0]
        p = line.split(" ", 5)
        self.assertEqual(p[1], "JN88BN")
        steps = p[5].split(";")
        self.assertGreaterEqual(len(steps), 15)
        self.assertEqual(len(steps[0].split(",")), 7)
        self.assertLess(len(line), 600)                            # compact over the air

    def test_api_down_one_line(self):
        self.calls.side_effect = OSError("down")
        _, out = self.run_session("//GETFC JN88BN", caps="CHAT,FC")
        self.assertIn("//FC - forecast service not reachable", out)


class ClientParseTests(unittest.TestCase):
    def test_fc_line(self):
        from types import SimpleNamespace
        from tbclient.core import ClientCore
        core = SimpleNamespace(forecast=None, changed=lambda: None)
        ClientCore._c_fc(core, "FC", "JN88BN 2026-11-17T12:00+00:00 48.561 16.138 "
                         "1763380800,8,45,270,32,81,;1763391600,,,,,,12", "")
        f = core.forecast
        self.assertEqual((f["loc"], len(f["steps"])), ("JN88BN", 2))
        self.assertEqual(f["steps"][0], {"t": 1763380800, "sky": 8, "temp": 4.5, "wdir": 270,
                                          "wspd": 3.2, "gust": 8.1, "rr": None})
        self.assertEqual(f["steps"][1]["rr"], 1.2)
        ClientCore._c_fc(core, "FC", "- at most 6 forecasts per hour", "")
        self.assertEqual(core.forecast["err"], "at most 6 forecasts per hour")


if __name__ == "__main__":
    unittest.main()
