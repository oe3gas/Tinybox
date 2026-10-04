"""geosphere_station.py --brocast: weather page for brocastd (no network)."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "brocast"))

import geosphere_station as g                                    # noqa: E402
from brocast import Codec                                        # noqa: E402
from brocast.splitter import split                               # noqa: E402

N = 145                                                          # 24 h + 1 in 10-min steps


def daten(temp_offset: float = 0.0, kurz: bool = False) -> dict:
    tl = [14.6 + temp_offset + 8.3 * math.sin((i - 60) / 144 * 2 * math.pi) for i in range(N)]
    tl[50] = None
    return {
        "station": "11334", "zeit": "2026-10-03T16:00+00:00",
        "w": {"TL": 21.3 + temp_offset, "TP": 3.6, "RF": 31, "PRED": 1028.5, "P": 999.1,
              "DD": 126, "FF": 1.8, "FFX": 4.1, "RR": 0.0},
        "info": {"name": "SCHÖNGRABERN", "altitude": 253.0, "lat": 48.6033, "lon": 16.0617},
        "ts": [] if kurz else list(range(N)),
        "reihen": {} if kurz else {"TL": tl, "RR": [0.0] * N, "FFX": [3.0 + i % 8 for i in range(N)],
                                   "PRED": [1028.9] * (N - 18) + [1028.9 - 0.4 * (k + 1) / 18 for k in range(18)]},
    }


class BrocastSeiteTests(unittest.TestCase):
    def setUp(self):
        self.codec = Codec()

    def frames(self, seite):
        return split(self.codec, {**seite, "id": 29, "rev": 0, "t": 1790000000})

    def test_page_fits_one_frame_and_decodes(self):
        seite = g.brocast_seite(daten(), 24, 120)
        frames = self.frames(seite)
        self.assertEqual(len(frames), 1)
        page = self.codec.decode(frames[0])
        self.assertEqual(page["typ"], "wx")
        dat = page["dat"]
        self.assertEqual((dat["temp"], dat["qff"], dat["wdir"], dat["gust10"]), (21.3, 1028.5, 126, 4.1))
        self.assertEqual((dat["gmax"], dat["ptnd"]), (10.0, -0.4))
        self.assertIn("tmin", dat)
        series = page["blk"][0]
        self.assertEqual((series["k"], series["u"], series["sc"], series["dt"]), ("series", "Cel", -1, 7200))
        self.assertEqual(len(series["v"]), 13)
        self.assertEqual(page["pos"][2], 253)

    def test_hot_summer_day_still_works(self):
        """Values from 25.6 °C need 3 bytes; the page may grow but must stay valid."""
        frames = self.frames(g.brocast_seite(daten(temp_offset=14), 24, 120))
        self.assertLessEqual(len(frames), 2)

    def test_short_mode_has_no_history_fields(self):
        seite = g.brocast_seite(daten(kurz=True), 24, 120)
        self.assertNotIn("blk", seite)
        self.assertNotIn("tmin", seite["dat"])
        self.assertEqual(len(self.frames(seite)), 1)

    def test_other_period_skips_24h_fields(self):
        seite = g.brocast_seite(daten(), 6, 120)
        self.assertNotIn("tmin", seite["dat"])
        self.assertNotIn("r24h", seite["dat"])

    def test_verdichten(self):
        self.assertEqual(g.verdichten([1, None, 3, 4, 5, 6, 7, 8] + [None] * 6, 6), [1, 8, None])

    def test_gueltig_minuten(self):
        self.assertEqual([g.gueltig_minuten(x) for x in ("2h", "90m", "1d", "45")], [120, 90, 1440, 45])


class EndToEndTests(unittest.TestCase):
    """geosphere_station --tinybox -> inbox file -> TinyBox -> brocastd accepts the page."""

    def test_inbox_file_to_brocastd(self):
        import json
        import tempfile
        from brocast import config as bconfig
        from brocast.station import Station
        from brocast.store import Store as BStore
        from tests.test_tinybox import make_app
        from tinybox.adapters import brocast as adapter
        from tinybox.adapters.inbox import Inbox
        from tinybox.config import BrocastCfg, InboxCfg

        d = daten()
        seite = g.brocast_seite(d, 24, 120)
        with tempfile.TemporaryDirectory() as tmp:
            kopf = {"To": "WX", "Subject": "Wetter Schoengrabern 18:00",
                    "Replace": "geosphere-wetter-11334", "Valid": "2h",
                    "Brocast": json.dumps(seite, ensure_ascii=False, separators=(",", ":"))}
            name, _, zeilen = g.bericht(d, 24)
            f = g.schreibe_tinybox(Path(tmp), "geosphere_wetter_11334", kopf, "\n".join(zeilen[2:]))
            app = make_app()
            app.cfg.inbox = InboxCfg(enabled=True, directory=Path(tmp))
            app.cfg.brocast = BrocastCfg(publish=True)
            msg_id = Inbox(app).process(f)
            msg = app.store.get(msg_id)
            self.assertIn("Temperatur", msg.body)
            page = adapter.to_page(msg, app)
            conf = Path(tmp) / "brocastd.conf"
            conf.write_text("[brocastd]\nmode = station\ncallsign = OE3GAS-5\n"
                            f"dictionary = {ROOT / 'brocast' / 'brocast-core.yaml'}\n",
                            encoding="utf-8")
            station = Station(bconfig.load(conf), Codec(), BStore(":memory:"))
            res = station.put("tinybox", str(msg_id), page)
            self.assertEqual(res["subpages"], 1)


if __name__ == "__main__":
    unittest.main()
