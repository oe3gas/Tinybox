"""Statistik (13.11.2026): Zähler (stats.py), Sendeprotokoll lesen, Vorschlag (advisor.py).

Ein ganzer Betriebstag wird mit dem echten Karussell durchgespielt (Uhr im Test):
24 Wetterseiten stündlich neu, zwei DX-Seiten halbstündlich neu, ältere Bulletins,
dazu fremder Verkehr (APRS) – dann wird ausgewertet.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from brocast import advisor, txlog
from brocast.carousel import Carousel
from brocast.config import TrafficCfg
from brocast.frame import build as build_frame
from brocast.stats import Stats, load_file
from brocast.txlog import TxLog
from tests.test_daemon import BULLETIN, Clock, make_station

HOUR = 3600
DAY = 86400


def wx(i: int, hour: int) -> dict:
    return {"typ": "wx", "ti": f"Wetter Station {i}",
            "dat": {"temp": round(5 + i * 0.3 + hour * 0.1, 1), "hum": 60 + (i + hour) % 30}}


def dx(n: int, k: int) -> dict:
    return {"typ": "text", "ti": f"DX jetzt {n}", "cat": ["dx"], "exp": 120,
            "blk": [{"k": "para", "x": f"Spots Runde {k}: " + " ".join(
                f"DL{j}ABC 14.0{j:02d} CW" for j in range(k % 7, k % 7 + 12))}]}


class Day:
    """One day of operation with the real carousel, a test clock and a txlog."""

    def __init__(self, tmp: Path, beacon_min: int = 0, aprs_every_s: int = 120, **station):
        self.clock = Clock()
        self.tmp = tmp
        self.st, self.store = make_station(self.clock, **station)
        self.cfg = self.st.cfg.station
        self.txlog = TxLog(tmp / "logs", "OE3GAS-5")
        self.stats = Stats(tmp / "statistik.json", self.cfg.baud, self.cfg.txdelay_ms, self.clock)

        async def send(data: bytes) -> bool:
            return True

        async def sleep(s: float) -> None:
            self.clock.t += s

        self.car = Carousel(self.store, send, self.cfg, "OE3GAS-5", self.clock, txlog=self.txlog,
                            mono=self.clock, sleep=sleep, traffic=TrafficCfg(quiet_s=5,
                                                                             connected_quiet_s=10))
        self.car.stats = self.stats
        self.beacon_min = beacon_min
        if beacon_min:
            self.car.set_beacon(lambda: build_frame("OE3GAS-5", b"x" * 80, [], 0x20)[:100],
                                beacon_min, "Bake")
        self.aprs_every_s = aprs_every_s

    async def run(self, hours: int = 26) -> None:
        t0 = self.clock.t
        for i in range(8):                                    # old bulletins
            self.st.put("tinybox", f"b{i}", {**BULLETIN, "ti": f"Bulletin {i}",
                                             "born": int(t0) - 3 * DAY})
        next_wx = t0 + 5 * 60
        next_dx = t0
        next_aprs = t0 + 7
        hour = k = 0
        end = t0 + hours * HOUR
        while self.clock.t < end:
            now = self.clock.t
            if now >= next_wx:
                for i in range(24):
                    self.st.put("geosphere", f"wx{i}", wx(i, hour))
                hour += 1
                next_wx += HOUR
            if now >= next_dx:
                for n in range(2):
                    self.st.put("dxfeed", f"dx{n}", dx(n, k))
                k += 1
                next_dx += 30 * 60
            if self.aprs_every_s and now >= next_aprs:
                src = f"OE3XYZ-{int(now) % 5}"
                self.car.heard(src, "APRS", "UI")
                self.stats.foreign(now, src, "UI", 60)
                next_aprs += self.aprs_every_s
            delay = await self.car.step()
            self.clock.t += max(1.0, min(delay, next_wx - self.clock.t, next_dx - self.clock.t,
                                         (next_aprs - self.clock.t) if self.aprs_every_s else delay))

    def report(self, hours: int = 24) -> dict:
        now = self.clock.t
        lines = txlog.read_lines(txlog.files_for(self.tmp / "logs", now - hours * HOUR, now),
                                 now - hours * HOUR, now)
        sends = txlog.group_sends(lines)
        pages = advisor.pages_from_rows(
            self.store.list_pages(),
            lambda row: [len(build_frame("OE3GAS-5", d, [], row.hdr))
                         for d in self.store.frames(row.pid)], self.cfg)
        return advisor.analyze(self.cfg, TrafficCfg(quiet_s=5), self.beacon_min, sends,
                               self.stats.window(now, hours), pages, now, hours)


class StatsTests(unittest.TestCase):
    def test_tick_spreads_over_hours_and_counts_holds(self):
        clock = Clock(10 * HOUR - 20)
        st = Stats(None, 1200, 300, clock)
        st.tick(clock.t, 0, None, 0)
        clock.t += 40                                  # over the hour boundary, held by budget
        st.tick(clock.t, 1, "budget", 12.0)
        a, b = st.window(clock.t, 2)
        self.assertAlmostEqual(a["run_s"], 20)
        self.assertAlmostEqual(b["run_s"], 20)
        self.assertAlmostEqual(a["hold"]["budget"] + b["hold"]["budget"], 40)
        self.assertAlmostEqual(a["lvl1_s"] + b["lvl1_s"], 40)
        self.assertEqual(b["budget_peak_s"], 12.0)

    def test_standstill_is_not_counted(self):
        clock = Clock()
        st = Stats(None, 1200, 300, clock)
        st.tick(clock.t, 0, None, 0)
        clock.t += 3600                                # PC asleep
        st.tick(clock.t, 0, None, 0)
        self.assertEqual(sum(b["run_s"] for b in st.window(clock.t, 3)), 0)

    def test_foreign_txdelay_once_per_transmission(self):
        clock = Clock()
        st = Stats(None, 1200, 300, clock)
        st.foreign(clock.t, "OE1AAA", "I", 100)
        clock.t += 0.8                                 # same station right after: same PTT
        st.foreign(clock.t, "OE1AAA", "I", 100)
        clock.t += 10
        st.foreign(clock.t, "OE1AAA", "S", 20)
        b = st.window(clock.t, 1)[0]
        self.assertEqual((b["conn"], b["ui"], b["fbytes"]), (3, 0, 220))
        one = (100 + 4) * 8 * 1.05 / 1200
        self.assertAlmostEqual(b["fair_s"], 0.3 + one + one + 0.3 + (24 * 8 * 1.05 / 1200), places=3)

    def test_save_load_keeps_48h(self):
        with tempfile.TemporaryDirectory() as d:
            clock = Clock()
            path = Path(d) / "statistik.json"
            st = Stats(path, 1200, 300, clock)
            st.late(clock.t, 75)
            st.own(clock.t, 4.2, 3)
            self.assertTrue(st.save())
            self.assertFalse(st.save())                # nothing new
            again = Stats(path, 1200, 300, clock)
            again.load()
            b = again.window(clock.t, 1)[0]
            self.assertEqual((b["late_over"], b["own_frames"]), (1, 3))
            clock.t += 49 * HOUR
            later = Stats(path, 1200, 300, clock)
            later.load()
            self.assertEqual(later.buckets, {})
            self.assertEqual(len(load_file(path)), 1)  # the command line reads all


class TxlogReadTests(unittest.TestCase):
    def test_frames_to_sends(self):
        with tempfile.TemporaryDirectory() as d:
            log = TxLog(Path(d), "OE3GAS-5")
            t = 1_790_000_000
            for sub in (1, 2, 3):
                log.record(t + sub, "BROCST", 30, 2, sub, 3, "text", 200, 1.4, "tinybox", "17",
                           "Bulletin | mit Strich")
            log.record(t + 60, "BROCST", 30, 2, 1, 3, "text", 200, 1.4, "tinybox", "17", "B")
            log.record(t + 70, "BEACON", 0, 0, 1, 1, "beacon", 90, 0.6, "brocastd", "beacon", "x")
            log.record(t + 80, "BROCST", 31, 0, 1, 1, "wx", 90, 0.6, "geosphere", "w1", "W",
                       withdrawn=True)
            lines = txlog.read_lines(txlog.files_for(Path(d), t, t + 100), t, t + 100)
            sends = txlog.group_sends(lines)
            self.assertEqual([(s["page"], s["frames"]) for s in sends],
                             [(30, 3), (30, 1), (0, 1), (31, 1)])
            self.assertEqual(sends[0]["title"], "Bulletin | mit Strich")
            self.assertTrue(sends[2]["beacon"])
            self.assertTrue(sends[3]["withdrawn"])
            self.assertEqual(sends[3]["title"], "W")
            self.assertAlmostEqual(sends[0]["air0"], 4.2)


class AdvisorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    async def asyncTearDown(self):
        self._tmp.cleanup()

    def test_gap_rule_matches_the_carousel(self):
        st, store = make_station()
        car = Carousel(store, None, st.cfg.station, "OE3GAS-5", Clock())
        c = st.cfg.station
        for sends in range(1, 8):
            for age in (0, 10 * HOUR, 30 * HOUR, 100 * HOUR, 200 * HOUR):
                self.assertEqual(car.gap_min(sends, age),
                                 advisor.gap_min(c.repeat_minutes, c.max_interval_min, c.aging,
                                                 sends, age))

    async def test_a_day_with_hourly_weather(self):
        day = Day(self.tmp, beacon_min=15)
        await day.run()
        rep = day.report()
        json.dumps(rep)                                # the web GUI gets it as JSON
        self.assertFalse(rep["basis"]["preliminary"])
        self.assertGreater(rep["basis"]["run_h"], 23)
        self.assertGreater(rep["channel"]["own_s"], 0)
        self.assertGreater(rep["channel"]["ui"], 600)
        self.assertEqual(len(rep["channel"]["hours"]), 24)
        kinds = rep["own"]["kinds"]
        self.assertGreater(kinds["neu"], 0)
        self.assertGreater(kinds["staffel"], 0)
        self.assertGreater(kinds["bake"], 0)
        # the re-calculation of the current setting is close to what was sent
        chk = rep["sim_check"]
        self.assertLess(abs(chk["simulated_sends"] - chk["measured_sends"]),
                        0.1 * chk["measured_sends"] + 5, chk)
        names = [o["name"] for o in rep["options"]]
        self.assertEqual(names, ["aktuell", "ausgewogen", "sparsam", "schneller"])
        cur, bal = rep["options"][0], rep["options"][1]
        self.assertTrue(cur["same"])
        self.assertLessEqual(bal["air_day_s"], cur["air_day_s"])
        # hourly new weather with 0,2,5,10 + 30 min: there is something to save
        self.assertEqual(rep["recommended"], "ausgewogen")
        change = [a for a in rep["advice"] if a["title"] == "Karussell-Takt"][0]
        self.assertEqual(change["level"], "change")
        self.assertTrue(change["conf"])
        self.assertGreater(change["saving_s"], 60)
        titles = [a["title"] for a in rep["advice"]]
        self.assertIn("Oft neue Revisionen", titles)   # weather 24x, DX 48x a day
        self.assertNotIn("Bake seltener", titles)      # every 15 min, but small next to the pages
        self.assertEqual(rep["options"][2]["same_as"], "ausgewogen")   # sparsam: nothing more

    async def test_beacon_too_often(self):
        day = Day(self.tmp, beacon_min=10, aprs_every_s=0)
        day.st.put("tinybox", "b", {**BULLETIN, "born": int(day.clock.t) - 10 * DAY})
        # only the beacon and one old bulletin
        t0 = day.clock.t
        while day.clock.t < t0 + 25 * HOUR:
            delay = await day.car.step()
            day.clock.t += max(1.0, delay)
        rep = day.report()
        bake = [a for a in rep["advice"] if a["title"] == "Bake seltener"]
        self.assertEqual(len(bake), 1, rep["advice"])
        self.assertIn("interval_min = 60", bake[0]["conf"][0])
        self.assertGreater(bake[0]["saving_s"], 0)

    async def test_counter_only_without_txlog(self):
        day = Day(self.tmp)
        await day.run(hours=3)
        now = day.clock.t
        pages = []
        rep = advisor.analyze(day.cfg, TrafficCfg(), 0, None, day.stats.window(now, 24),
                              pages, now, 24)
        self.assertIsNone(rep["own"])
        self.assertEqual(rep["options"], [])
        self.assertTrue(rep["basis"]["preliminary"])
        self.assertTrue(any("Sendeprotokoll ist aus" in n for n in rep["basis"]["notes"]))
        self.assertGreater(rep["channel"]["own_s"], 0)  # from the counter

    async def test_holds_and_lateness_are_counted(self):
        day = Day(self.tmp, aprs_every_s=3)            # APRS all the time: quiet_s 5 s
        await day.run(hours=2)
        w = day.stats.window(day.clock.t, 3)
        self.assertGreater(sum(b["hold"]["channel"] for b in w), 600)
        self.assertGreater(sum(b["late_n"] for b in w), 0)

    async def test_daemon_report_and_api(self):
        from tests.test_daemon import make_cfg
        from brocast.daemon import Daemon
        cfg = make_cfg()
        cfg.data_dir = self.tmp
        cfg.txlog_dir = self.tmp / "logs"
        clock = Clock()
        d = Daemon(cfg, clock=clock, db_path=":memory:")
        self.assertIs(d.carousel.stats, d.stats)
        d.station.put("tinybox", "1", BULLETIN)
        d.link.send = _ok
        await d.carousel.step()
        clock.t += 120
        await d.carousel.step()
        first = d.web.stats_report(24)                 # computed in a thread
        self.assertTrue(first["station"])
        for _ in range(100):
            if d._report_job is None or not d._report_job.is_alive():
                break
            await asyncio.sleep(0.05)
        rep = d.web.stats_report(24)
        self.assertNotIn("computing", rep)
        self.assertEqual(rep["own"]["sends"], 2)
        self.assertIs(d.stats_report(24), rep)         # cached
        clock.t += 61
        again = d.stats_report(24)                     # stale: the old one, a new run started
        self.assertTrue(again.get("computing"))
        self.assertEqual(again["own"]["sends"], 2)
        self.assertEqual(d.stats_report(24, wait=True)["own"]["sends"], 2)
        d.stats.save()
        self.assertTrue((self.tmp / "statistik.json").exists())
        d.store.close()


class CommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_statistik_command(self):
        """py -3 -m brocast statistik: conf, Sendeprotokoll, Zähler-Datei, DB nur lesend."""
        import contextlib
        import io
        import re
        from brocast import statcmd
        from brocast.__main__ import main as cli
        from brocast.store import Store
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            conf = (Path(__file__).resolve().parent.parent / "brocastd.conf.example").read_text(
                encoding="utf-8")
            conf = re.sub(r"(?m)^mode\s*=.*$", "mode = station", conf)
            conf = re.sub(r"(?m)^callsign\s*=.*$", "callsign = OE3GAS-5", conf)
            (tmp / "brocastd.conf").write_text(conf, encoding="utf-8")
            (tmp / "brocast-core.yaml").write_text(
                (Path(__file__).resolve().parent.parent / "brocast-core.yaml").read_text(
                    encoding="utf-8"), encoding="utf-8")
            day = Day(tmp)
            await day.run(hours=4)
            day.stats.path = tmp / "data" / "statistik.json"
            day.stats.dirty = True
            day.stats.save()
            disk = Store(tmp / "data" / "brocastd.db")    # the carousel's pages on disk
            for row in day.store.list_pages():
                row.pid = 0
                disk.save_page(row, [])
            disk.close()
            cfg = statcmd.config.load(tmp / "brocastd.conf")
            rep = statcmd.report(cfg, 24, now=day.clock.t)
            self.assertEqual(rep["own"]["pages"], 34)
            self.assertGreater(rep["basis"]["run_h"], 3)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = cli(["statistik", "--konfig", str(tmp / "brocastd.conf"), "--json"])
            self.assertEqual(code, 0)
            self.assertTrue(json.loads(out.getvalue())["station"])
            text = statcmd.text(rep)
            self.assertIn("VORSCHLAG", text)
            self.assertIn("NACHGERECHNET", text)


async def _ok(data: bytes, channel: int = 0) -> bool:
    return True


if __name__ == "__main__":
    unittest.main()
