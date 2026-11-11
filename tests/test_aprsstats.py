"""CR61: APRS statistics of the channel."""

import tempfile
import unittest
from pathlib import Path

from prcore import aprs
from prcore.aprsstats import AprsStats, country

T0 = 1_792_000_000.0


def feed(st, t, src, path, used, info, dest="APMI06"):
    rep = [bool(x) for x in used]
    a = aprs.decode(dest, src, path, rep, info, now=t)
    st.add(src, path, rep, info, 7 * (2 + len(path)) + 2 + len(info), a, now=t)


class StatsTests(unittest.TestCase):
    def setUp(self):
        self.st = AprsStats(None, aprs.locator_to_latlon("JN88EP"))
        self.st.since = T0 - 1

    def test_counts(self):
        for i in range(5):                        # a stationary car every 60 s
            feed(self.st, T0 + 60 * i, "OE1IAH-8", ["OE6XTR", "OE3XWJ-10", "WIDE2"], [1, 1, 1],
                 b"!4807.19N/01656.63Ev209/000/A=000891Arnold car 578", dest="APDR10")
        feed(self.st, T0 + 10, "OM0ODX", ["OE3XWJ-10", "WIDE2"], [1, 1],
             b"}OM5KV-15>APNL51,TCPIP,OM0ODX*:!4746.48N/01805.55E`Radiosonde")
        feed(self.st, T0 + 20, "OE3XKN-10", ["WIDE1", "WIDE3-3"], [0, 0], b"!/6,fxRISM} st", dest="APOT2A")
        r = self.st.report(0, now=T0 + 400)
        self.assertEqual(r["totals"]["frames"], 7)
        self.assertEqual(r["totals"]["inet"], 1)
        heard = {h["call"]: h["n"] for h in r["heard"]}
        self.assertEqual(heard, {"OE3XWJ-10": 6, "OE3XKN-10": 1})
        senders = {s["call"] for s in r["senders"]}
        self.assertIn("OM5KV-15", senders)                     # the station inside, not the iGate
        self.assertEqual(r["igates"][0]["call"], "OM0ODX")
        self.assertEqual(r["digis"][0], {"call": "OE3XWJ-10", "n": 6})
        self.assertIn({"chain": "OE6XTR → OE3XWJ-10", "n": 5}, r["chains"])
        kinds = {(s["call"], s["kind"]) for s in r["sins"]}
        self.assertIn(("OE1IAH-8", "too often"), kinds)
        self.assertIn(("OE3XKN-10", "long path"), kinds)
        self.assertIn(("OM0ODX", "internet → radio"), kinds)  # 1 of 7 frames = 14 %
        self.assertEqual(r["range"]["farthest_direct"]["call"], "OE3XKN-10")

    def test_station_page(self):
        for i in range(5):
            feed(self.st, T0 + 300 * i, "OE1IAH-8", ["OE6XTR", "OE3XWJ-10", "WIDE2"], [1, 1, 1],
                 b"!4807.19N/01656.63Ev209/000/A=000891Arnold car 578", dest="APDR10")
        feed(self.st, T0 + 10, "OM0ODX", ["OE3XWJ-10", "WIDE2"], [1, 1],
             b"}OM5KV-15>APNL51,TCPIP,OM0ODX*:!4746.48N/01805.55E`Radiosonde")
        s = self.st.station("oe1iah-8", 0, now=T0 + 1500)
        self.assertEqual(s["frames"], 5)
        self.assertEqual(s["types"][0]["cat"], "position")
        self.assertEqual(s["beacon"]["median"], 300)
        self.assertEqual(s["ways"]["chains"][0]["chain"], "OE1IAH-8 → OE6XTR → OE3XWJ-10")
        self.assertEqual(s["roles"][0], "fixed station")
        self.assertEqual(sum(map(sum, s["activity"])), 5)
        self.assertIn("km", s["pos"])
        digi = self.st.station("OE3XWJ-10", 0, now=T0 + 1500)
        self.assertEqual(digi["frames"], 0)
        self.assertEqual(digi["relayed"], 6)
        self.assertIn("digipeater", digi["roles"])
        gate = self.st.station("OM0ODX", 0, now=T0 + 1500)
        self.assertEqual(gate["as_igate"], [{"call": "OM5KV-15", "n": 1}])

    def test_window_and_reset(self):
        feed(self.st, T0, "OE3CRA-2", [], [], b">old")
        feed(self.st, T0 + 7200, "OE3CRA-2", [], [], b">new")
        self.assertEqual(self.st.report(3600, now=T0 + 7300)["totals"]["frames"], 1)
        self.assertEqual(self.st.report(0, now=T0 + 7300)["totals"]["frames"], 2)
        self.st.reset()
        self.assertEqual(self.st.report(0)["totals"]["frames"], 0)

    def test_kept_over_a_restart(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "aprsstats.db"
            st = AprsStats(p)
            feed(st, __import__("time").time(), "OE3CRA-2", [], [], b">hello")
            st.close()
            st2 = AprsStats(p)
            self.assertEqual(st2.report(0)["totals"]["frames"], 1)
            st2.close()

    def test_file_is_tidied_while_running(self):   # CR103: by count, no age limit
        import sqlite3
        from unittest import mock
        from prcore import aprsstats
        with tempfile.TemporaryDirectory() as d, mock.patch.object(aprsstats, "MAX_RECORDS", 3), \
                mock.patch.object(aprsstats, "TRIM_SLACK", 1):
            p = Path(d) / "aprsstats.db"
            st = AprsStats(p)
            now = __import__("time").time()
            for i in range(5):
                feed(st, now + i, "OE3OLD", [], [], b">old %d" % i)
            feed(st, now + aprsstats.PRUNE_SEC + 10, "OE3NEW", [], [], b">new")   # an hour later
            st.close()
            db = sqlite3.connect(str(p))
            self.assertEqual(db.execute("SELECT count(*) FROM rec").fetchone()[0], 3)
            db.close()
            st2 = AprsStats(p)
            self.assertEqual(len(st2.recs), 3)
            self.assertEqual(st2.recs[-1]["origin"], "OE3NEW")
            st2.close()

    def test_limit_without_copy_per_frame(self):    # CR103
        from unittest import mock
        from prcore import aprsstats
        with mock.patch.object(aprsstats, "MAX_RECORDS", 10), mock.patch.object(aprsstats, "TRIM_SLACK", 5):
            ids = []
            for i in range(16):
                feed(self.st, T0 + i, "OE3ABC", [], [], b">%d" % i)
                ids.append(id(self.st.recs))
            self.assertEqual(len(set(ids[:15])), 1)    # up to 10 + 5: the same list, only appended
            self.assertEqual(len(self.st.recs), 10)   # the 16th trims to the limit
            r = self.st.report(0, now=T0 + 100)
            self.assertEqual(r["totals"]["frames"], 10)
            self.assertEqual(r["kept_from"], T0 + 6)  # "All" starts at the oldest frame kept
            self.assertTrue(r["kept_full"])
            self.assertEqual(r["since"], T0 + 6)

    def test_no_age_limit(self):                      # CR103: only the count limits
        feed(self.st, T0 - 40 * 86400, "OE3OLD", [], [], b">old")
        self.st.since = T0 - 41 * 86400
        feed(self.st, T0, "OE3NEW", [], [], b">new")
        self.assertEqual(self.st.report(0, now=T0 + 10)["totals"]["frames"], 2)

    def test_kept_span(self):                         # CR103: for the label "last ... days"
        feed(self.st, T0 + 5, "OE3ABC", [], [], b">x")
        for r in (self.st.report(0, now=T0 + 400), self.st.graph(0, now=T0 + 400),
                  self.st.station("OE3ABC", 0, now=T0 + 400)):
            self.assertEqual(r["kept_from"], T0 - 1)   # limit not reached: since the reset
            self.assertFalse(r["kept_full"])
            self.assertEqual(r["kept_max"], 250_000)

    def test_graph(self):                        # CR79: the network graph
        for i in range(3):
            feed(self.st, T0 + 60 * i, "OE1IAH-8", ["OE6XTR", "OE3XWJ-10", "WIDE2"], [1, 1, 1],
                 b"!4807.19N/01656.63Ev209/000/A=000891Arnold car 578", dest="APDR10")
        feed(self.st, T0 + 10, "OM0ODX", ["OE3XWJ-10", "WIDE2"], [1, 1],
             b"}OM5KV-15>APNL51,TCPIP,OM0ODX*:!4746.48N/01805.55E`Radiosonde")
        feed(self.st, T0 + 20, "OE3XKN-10", ["WIDE1", "WIDE3-3"], [0, 0], b"!/6,fxRISM} st", dest="APOT2A")
        g = self.st.graph(0, now=T0 + 400, me="OE3GAS-10")
        kinds = {n["call"]: n["kind"] for n in g["nodes"]}
        self.assertEqual(kinds["OE3GAS-10"], "me")
        self.assertEqual(kinds["OE3XWJ-10"], "digi")
        self.assertEqual(kinds["OM0ODX"], "igate")
        self.assertEqual(kinds["OM5KV-15"], "station")
        ways = {tuple(w["chain"]): w for w in g["ways"]}
        self.assertEqual(ways[("OE1IAH-8", "OE6XTR", "OE3XWJ-10", "OE3GAS-10")]["n"], 3)
        self.assertTrue(ways[("OM5KV-15", "OM0ODX", "OE3XWJ-10", "OE3GAS-10")]["inet"])
        self.assertIn(("OE3XKN-10", "OE3GAS-10"), ways)              # heard directly
        me = next(n for n in g["nodes"] if n["call"] == "OE3GAS-10")
        self.assertIsNotNone(me["lat"])                               # our locator

    def test_graph_stage2(self):                 # CR79 stage 2: time, hop type, channel health
        for i in range(6):                        # the same status every 2 min: unchanged repeat
            feed(self.st, T0 + 120 * i, "OE3ABC", ["OE3XWJ-10", "WIDE2-1"], [1, 0],
                 b">same old status", dest="APRS")
        feed(self.st, T0 + 30, "OE1XYZ", ["OE3XWJ-10", "WIDE1"], [1, 1],
             b"!4807.19N/01656.63E-hello", dest="APRS")
        feed(self.st, T0 + 40, "OE3KLM", ["WIDE1", "WIDE3-3"], [0, 0], b"!/6,fxRISM} st", dest="APOT2A")
        g = self.st.graph(0, now=T0 + 720, me="OE3GAS-10")
        self.assertEqual(g["buckets"], 24)
        hops = {w["chain"][0]: w["hop"] for w in g["ways"]}
        self.assertEqual(hops["OE3ABC"], "wide2")
        self.assertEqual(hops["OE1XYZ"], "wide1")
        self.assertEqual(hops["OE3KLM"], "flood")
        w = next(w for w in g["ways"] if w["chain"][0] == "OE3ABC")
        self.assertEqual(sum(w["tb"]), w["n"])
        self.assertEqual(len([x for x in w["tb"] if x]), 6)          # spread over the time axis
        digi = next(n for n in g["nodes"] if n["call"] == "OE3XWJ-10")
        self.assertEqual(digi["through"], 7)
        self.assertEqual(digi["rep_n"], 6)
        self.assertEqual(digi["rep_calls"], ["OE3ABC"])
        self.assertAlmostEqual(digi["rep"], 0.86)

    def test_objects_are_not_the_senders_position(self):
        """CR116: an iGate sending repeater objects is not mobile at 3000 km/h."""
        for i in range(10):
            feed(self.st, T0 + 60 * i, "OE3MZC-2", ["WIDE2-2"], [0], b"!4825.00N/01615.00E#iGate")
            feed(self.st, T0 + 60 * i + 30, "OE3MZC-2", ["WIDE2-2"], [0],
                 b";OE3XWR   *111111z4815.00N/01600.00Er145.650MHz T088 -060")
        s = self.st.station("OE3MZC-2", 0, now=T0 + 700)
        self.assertEqual(s["move"]["km"], 0.0)
        self.assertEqual(s["move"]["max_kmh"], 0)
        self.assertIn("fixed station", s["roles"])
        self.assertNotIn("mobile", s["roles"])
        self.assertAlmostEqual(s["pos"]["lat"], 48.41667, places=4)     # the iGate, not the repeater
        n = next(n for n in self.st.graph(0, now=T0 + 700)["nodes"] if n["call"] == "OE3MZC-2")
        self.assertFalse(n["moving"])
        self.assertAlmostEqual(n["lat"], 48.41667, places=4)

    def test_wrong_fix_is_no_top_speed(self):
        """CR116: one bad GPS fix (15 km away for 20 s) does not give 2700 km/h."""
        fixes = [(0, "4825.00N", "01615.00E"), (60, "4825.20N", "01615.00E"), (80, "4833.20N", "01615.00E"),
                 (100, "4825.40N", "01615.00E"), (160, "4825.60N", "01615.00E")]
        for dt, la, lo in fixes:
            feed(self.st, T0 + dt, "OE3ABC-9", ["WIDE1-1"], [0], f"!{la}/{lo}>car".encode())
        m = self.st.station("OE3ABC-9", 0, now=T0 + 200)["move"]
        self.assertLess(m["max_kmh"], 100)
        self.assertLess(m["km"], 2)

    def test_country(self):
        self.assertEqual(country("OE3GAS-1"), "Austria")
        self.assertEqual(country("OK1KZE-1"), "Czechia")
        self.assertEqual(country("SR6NPK"), "Poland")
        self.assertEqual(country("9A1DD-9"), "Croatia")
        self.assertEqual(country("DB0RDH"), "Germany")
        self.assertEqual(country("HG2PPA-2"), "Hungary")


if __name__ == "__main__":
    unittest.main()
