"""CR44: connection log - TinyBox (table, QSO command, CSV/ADIF in the web GUI)
and the export helpers shared with the client."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import tempfile
import unittest
from pathlib import Path

from tinybox import connlog
from tinybox.adapters import web
from tests.test_tinybox import login, make_app, type_lines
from tests import test_web
from tests.test_web import request

ROW = {"call": "OE3TEC-2", "via": "radio", "start": "2026-10-15T18:46:03Z",
       "end": "2026-10-15T18:58:10Z", "secs": 727, "rx": 812, "tx": 4120,
       "air_tx": 4600, "air_rx": 900, "ended": "disc"}


class ExportTests(unittest.TestCase):
    def test_helpers(self):
        self.assertEqual(connlog.duration(727), "12m07")
        self.assertEqual(connlog.duration(4000), "1h06m")
        self.assertEqual(connlog.kb(812), "812")
        self.assertEqual(connlog.kb(4120), "4.1k")
        self.assertEqual(connlog.kb(None), "-")
        self.assertEqual(connlog.band_of("144.800"), "2m")
        self.assertEqual(connlog.band_of("438.1"), "70cm")
        self.assertEqual(connlog.band_of("7.045"), "40m")
        self.assertEqual(connlog.band_of(""), "")

    def test_csv(self):
        text = connlog.to_csv([ROW])
        lines = text.splitlines()
        self.assertEqual(lines[0], "start,end,secs,call,via,freq,rx,tx,air_tx,air_rx,ended")
        self.assertEqual(lines[1], "2026-10-15T18:46:03Z,2026-10-15T18:58:10Z,727,OE3TEC-2,"
                                   "radio,,812,4120,4600,900,disc")

    def test_adif(self):
        text = connlog.to_adif([ROW], "OE3GAS-1", "TinyBox", "0.1", freq="144.800",
                               locator="JN88EP", operator="OE3GAS")
        head, _, body = text.partition("<EOH>")
        self.assertIn("<ADIF_VER:5>3.1.4", head)
        self.assertIn("<PROGRAMID:7>TinyBox", head)
        for f in ("<CALL:6>OE3TEC", "<QSO_DATE:8>20261015", "<TIME_ON:6>184603",
                  "<QSO_DATE_OFF:8>20261015", "<TIME_OFF:6>185810", "<MODE:3>PKT",
                  "<STATION_CALLSIGN:6>OE3GAS", "<OPERATOR:6>OE3GAS", "<FREQ:7>144.800",
                  "<BAND:2>2m", "<MY_GRIDSQUARE:6>JN88EP", "<EOR>"):
            self.assertIn(f, body)
        # every field length is right
        import re
        for name, n, rest in re.findall(r"<(\w+):(\d+)>([^<]*)", body):
            self.assertEqual(len(rest.rstrip(" \n")), int(n), name)
        self.assertNotIn("<FREQ", connlog.to_adif([ROW], "OE3GAS-1", "TinyBox", "0.1"))
        # the row's own frequency (client: asked per session) wins
        text = connlog.to_adif([dict(ROW, freq="438.100")], "OE3GAS", "TBClient", "1",
                               freq="144.800")
        self.assertIn("<FREQ:7>438.100 <BAND:4>70cm", text)


class TinyBoxLogTests(unittest.TestCase):
    def test_session_rows_and_qso(self):
        app = make_app()
        s, t = login(app, "OE3TEC-2")
        t.rx_bytes, t.tx_bytes = 30, 500          # as the adapters count them
        s.end(lost=True)
        s2, t2 = login(app, "OE3TEC-9")
        type_lines(s2, "B")
        s2.end()
        s3, t3 = login(app, "OE1ABC")
        s3.end()
        rows = app.store.connlog_list()
        self.assertEqual([(r["call"], r["via"], r["ended"]) for r in rows],
                         [("OE1ABC", "telnet", "disc"), ("OE3TEC-9", "telnet", "bye"),
                          ("OE3TEC-2", "telnet", "lost")])
        self.assertEqual((rows[2]["rx"], rows[2]["tx"]), (30, 500))
        self.assertIsNone(rows[0]["rx"])            # transport without counters
        # a user sees his own connects (all SSIDs), nobody else's
        u, ut = login(app, "OE3TEC")
        type_lines(u, "QSO")
        self.assertIn("OE3TEC-2", ut.buf)
        self.assertIn("OE3TEC-9", ut.buf)
        self.assertIn(" lost", ut.buf)
        self.assertNotIn("OE1ABC", ut.buf)
        ut.buf = ""
        type_lines(u, "QSO ALL")
        self.assertIn("Usage: QSO", ut.buf)
        ut.buf = ""
        type_lines(u, "QSO 1")
        self.assertIn("Older connects: QSO 2", ut.buf)
        # the sysop sees everybody, and one station
        so, st = login(app, "OE3GAS")
        type_lines(so, "QSO ALL")
        self.assertIn("OE1ABC", st.buf)
        st.buf = ""
        type_lines(so, "QSO OE1ABC")
        self.assertIn("OE1ABC", st.buf)
        self.assertNotIn("OE3TEC", st.buf)
        # the end is logged once, the local sysop console never
        s3.end()
        self.assertEqual(len(app.store.connlog_list("OE1ABC")), 1)

    def test_help_lists_qso(self):
        app = make_app()
        s, t = login(app, "OE3TEC")
        type_lines(s, "H")
        self.assertIn("QSO", t.buf)


class WebExportTests(unittest.TestCase):
    setUp, tearDown = test_web.WebTests.setUp, test_web.WebTests.tearDown
    run_async, login = test_web.WebTests.run_async, test_web.WebTests.login

    def test_connlog_api_and_files(self):
        self.app.cfg.station = dataclasses.replace(self.app.cfg.station, freq="144.800")
        self.app.store.connlog_add(ROW)
        self.app.store.connlog_add(dict(ROW, call="OE1ABC", start="2026-10-15T19:00:00Z"))

        async def scenario(s):
            cookie, _ = await self.login(s)
            out = {}
            out["no_login"] = (await request(s.port, "GET", "/api/connlog.adi"))[0]
            _, _, p = await request(s.port, "GET", "/api/connlog", cookie=cookie)
            out["json"] = json.loads(p)
            out["csv"] = await request(s.port, "GET", "/api/connlog.csv?call=x%0d%0aSet-Cookie:a",
                                       cookie=cookie)
            out["adi"] = await request(s.port, "GET", "/api/connlog.adi?call=oe3tec-2",
                                       cookie=cookie)
            return out

        out = self.run_async(scenario)
        self.assertEqual(out["no_login"], 401)
        self.assertEqual([r["call"] for r in out["json"]], ["OE1ABC", "OE3TEC-2"])
        st, hdrs, body = out["csv"]
        self.assertEqual(st, 200)
        self.assertIn("attachment", hdrs["content-disposition"])
        self.assertNotIn("set-cookie", hdrs)               # no header injection via ?call=
        self.assertEqual(body.count(b"\r\n"), 1)             # nobody is called XSET-COOK
        st, hdrs, body = out["adi"]
        self.assertEqual(st, 200)
        self.assertIn("-OE3TEC-2.adi", hdrs["content-disposition"])
        self.assertIn(b"<BAND:2>2m", body)
        self.assertIn(b"<CALL:6>OE3TEC", body)          # the filter: only OE3TEC
        self.assertNotIn(b"OE1ABC", body)


if __name__ == "__main__":
    unittest.main()
