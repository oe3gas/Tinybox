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


def region_daten(ohne: tuple[str, ...] = ()) -> dict:
    """Ein Datensatz je Station der Region, leicht variiert; `ohne` fehlt (Ausfall)."""
    out = {}
    for i, sid in enumerate(g.REGION_IDS):
        if sid in ohne:
            continue
        d = daten(temp_offset=i * 0.3)
        d["station"] = sid
        d["info"] = {"name": g.REGION_NAME[sid].upper(), "altitude": 150.0 + i * 30,
                     "lat": 48.6, "lon": 16.0}
        d["reihen"]["RR"] = [0.1 * (i % 3)] * N
        d["reihen"]["FFX"] = [2.0 + i % 5] * N
        out[sid] = d
    return out


class RegionTests(unittest.TestCase):
    def setUp(self):
        self.codec = Codec()

    def test_station_list(self):
        self.assertEqual(len(g.REGION_IDS), 24)
        self.assertEqual(len(set(g.REGION_IDS)), 24)
        self.assertIn("11334", g.REGION_IDS)
        for kurz in g.REGION_NAME.values():
            self.assertLessEqual(len(kurz), 13)
            self.assertTrue(kurz.isascii())

    def test_je_station_maps_by_id_not_order(self):
        antwort = {"features": [
            {"properties": {"station": "11022", "parameters": {"TL": {"data": [11.4]}}}},
            {"properties": {"station": "11334", "parameters": {"TL": {"data": [7.2]}}}}]}
        self.assertEqual(g._je_station(antwort), {"11022": {"TL": [11.4]}, "11334": {"TL": [7.2]}})

    def test_aktuelle_werte_take_each_stations_own_latest_time(self):
        """API mit mehreren Stationen: zwei Zeitstempel, je Station nur an einem davon Werte."""
        from unittest import mock
        antwort = {"timestamps": ["2026-10-13T19:10+00:00", "2026-10-13T19:20+00:00"], "features": [
            {"properties": {"station": "11022", "parameters": {"TL": {"data": [None, 11.5]}, "RR": {"data": [None, 0.0]}}}},
            {"properties": {"station": "11334", "parameters": {"TL": {"data": [6.6, None]}, "RR": {"data": [0.1, None]}}}},
            {"properties": {"station": "11025", "parameters": {"TL": {"data": [None, None]}, "RR": {"data": [None, None]}}}}]}
        with mock.patch.object(g, "api_get", return_value=antwort):
            w = g.aktuelle_werte_mehrere(["11022", "11334", "11025"])
        self.assertEqual(w["11022"], ("2026-10-13T19:20+00:00", {"TL": 11.5, "RR": 0.0}))
        self.assertEqual(w["11334"], ("2026-10-13T19:10+00:00", {"TL": 6.6, "RR": 0.1}))
        self.assertNotIn("11025", w)
        with mock.patch.object(g, "api_get", return_value=antwort):
            self.assertEqual(g.aktuelle_werte("11334")[0], "2026-10-13T19:10+00:00")
            with self.assertRaises(ValueError):
                g.aktuelle_werte("11025")

    def test_bergstation_pred_is_dropped(self):
        from unittest import mock
        d = daten()
        d["w"]["PRED"] = 856.4
        d["reihen"]["PRED"] = [856.0] * N
        with mock.patch.object(g, "aktuelle_werte_mehrere", return_value={"11367": (d["zeit"], d["w"])}), \
                mock.patch.object(g, "verlauf_mehrere", return_value=(d["ts"], {"11367": d["reihen"]})), \
                mock.patch.object(g, "station_info", return_value=None):
            out = g.abrufen("11367", 24, False)
        self.assertIsNone(out["w"]["PRED"])
        self.assertTrue(all(x is None for x in out["reihen"]["PRED"]))
        self.assertNotIn("qff", g.brocast_seite(out, 24, 120)["dat"])

    def test_ueberblick_text(self):
        zeilen = g.ueberblick(region_daten(ohne=("11025",)), "2026-10-03T16:00+00:00", 24)
        text = "\n".join(zeilen)
        self.assertTrue(text.isascii(), "Ueberblick muss ASCII sein")
        self.assertLessEqual(max(len(z) for z in zeilen), 60)
        self.assertEqual(sum(z.startswith("---") for z in zeilen), 2)
        self.assertIn("Weitra           -  (keine Daten)", text)
        self.assertIn("Schoengrabern  240", text)
        self.assertIn("Tiefstwert", text)
        self.assertIn("Quelle: GeoSphere", text)
        # 24 Stationen + Kopf/Legende/Extreme: rund 1,9 kB (nur Mailbox-Text, geht nicht ueber brocast)
        self.assertLess(len(text.encode()), 2048)

    def test_brocast_table_page_is_small(self):
        seite = g.brocast_ueberblick(region_daten(), "2026-10-03T16:00+00:00", 120)
        self.assertEqual(seite["typ"], "text")
        self.assertEqual(sum(len(b["rows"]) for b in seite["blk"]), 24)
        self.assertEqual(len(seite["blk"]), 9)
        self.assertIn("hdr", seite["blk"][0])
        self.assertNotIn("hdr", seite["blk"][1])
        frames = split(self.codec, {**seite, "id": 30, "rev": 0, "t": 1790000000})
        self.assertLessEqual(len(frames), 5)
        for fr in frames:
            self.assertLessEqual(len(fr), 240)
        page = self.codec.decode(frames[0])
        self.assertEqual((page["blk"][0]["k"], page["blk"][0]["sc"]), ("table", -1))
        self.assertEqual(page["blk"][0]["rows"][0][:3], ["Retz", 213, "SO"])
        self.assertIn("Retz | 21.3 | SO | 1.8 | 2 | 0", "\n".join(self.codec.describe(page)))

    def test_brocast_table_worst_case_fits(self):
        """Lange Namen, Minusgrade, dreistellige Boeen/Regen: jeder Block bleibt unter 240 Bytes."""
        d = region_daten()
        for i, x in enumerate(d.values()):
            x["w"].update({"TL": -12.3, "FF": 25.5, "DD": 337})
            x["reihen"]["FFX"] = [41.7] * N
            x["reihen"]["RR"] = [0.9] * N
        g.REGION_NAME_SICHERUNG = dict(g.REGION_NAME)
        try:
            for sid in g.REGION_IDS:
                g.REGION_NAME[sid] = "Dreizehnzeich"          # 13 Zeichen
            seite = g.brocast_ueberblick(d, "2026-10-03T16:00+00:00", 120)
        finally:
            g.REGION_NAME.update(g.REGION_NAME_SICHERUNG)
        frames = split(self.codec, {**seite, "id": 30, "rev": 0, "t": 1790000000})
        self.assertLessEqual(len(frames), 7)


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

    def test_region_to_inbox_and_brocastd(self):
        """--region --tinybox (Abruf ersetzt): 24 Einzelbulletins + Ueberblick, brocastd nimmt die Tabelle."""
        import argparse
        import json
        import tempfile
        from unittest import mock
        from brocast import config as bconfig
        from brocast.station import Station
        from brocast.store import Store as BStore
        from tests.test_tinybox import make_app
        from tinybox.adapters import brocast as adapter
        from tinybox.adapters.inbox import Inbox
        from tinybox.config import BrocastCfg, InboxCfg

        d = region_daten(ohne=("11025",))
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(g, "abrufen_mehrere", return_value=d):
            args = argparse.Namespace(stunden=24, kurz=False, tinybox=tmp, ziel="WX", gueltig="2h",
                                      log=None, einzel_ohne_brocast=False)
            self.assertEqual(g.region(args), 0)
            dateien = sorted(Path(tmp).glob("*.txt"))
            self.assertEqual(len(dateien), 24)                         # 23 Stationen + Ueberblick
            app = make_app()
            app.cfg.inbox = InboxCfg(enabled=True, directory=Path(tmp))
            app.cfg.brocast = BrocastCfg(publish=True)
            conf = Path(tmp) / "brocastd.conf"
            conf.write_text("[brocastd]\nmode = station\ncallsign = OE3GAS-5\n"
                            f"dictionary = {ROOT / 'brocast' / 'brocast-core.yaml'}\n",
                            encoding="utf-8")
            station = Station(bconfig.load(conf), Codec(), BStore(":memory:"))
            msg = app.store.get(Inbox(app).process(Path(tmp) / "geosphere_wetter_region.txt"))
            self.assertEqual(msg.replace_key, "geosphere-wetter-region")
            self.assertIn("--- Waldviertel ---", msg.body)
            res = station.put("tinybox", str(msg.id), adapter.to_page(msg, app))
            self.assertLessEqual(res["subpages"], 5)
            msg = app.store.get(Inbox(app).process(Path(tmp) / "geosphere_wetter_11022.txt"))
            self.assertEqual(msg.replace_key, "geosphere-wetter-11022")
            self.assertEqual(json.loads(msg.brocast)["typ"], "wx")

    def test_region_einzel_ohne_brocast(self):
        import argparse
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(g, "abrufen_mehrere", return_value=region_daten()):
            args = argparse.Namespace(stunden=24, kurz=False, tinybox=tmp, ziel="WX", gueltig="2h",
                                      log=None, einzel_ohne_brocast=True)
            g.region(args)
            einzel = (Path(tmp) / "geosphere_wetter_11334.txt").read_text(encoding="utf-8")
            self.assertNotIn("Brocast:", einzel)
            self.assertIn("Brocast:", (Path(tmp) / "geosphere_wetter_region.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
