"""geosphere_prognose.py: locator, forecast steps, text and brocast page (no network).

The fixture is a real API answer for JN88BN (run 24.10.2026 06 UTC, 55 hours from
12 UTC); it spans the end of summer time on 25.10.2026, 03:00 CEST -> 02:00 CET.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "brocast"))

import geosphere_prognose as gp                                  # noqa: E402
from brocast import Codec                                        # noqa: E402
from brocast import fragment                                     # noqa: E402
from brocast.splitter import split                               # noqa: E402
from brocast.zdict import load as load_zdict                     # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "geosphere_nwp_jn88bn.json"


def vienna(test):
    """Run with Austrian local time (hours and day change as on PC1/PC2)."""
    def wrapper(self):
        old = os.environ.get("TZ")
        os.environ["TZ"] = "Europe/Vienna"
        time.tzset()
        try:
            return test(self)
        finally:
            if old is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = old
            time.tzset()
    return wrapper


def daten():
    antwort = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return gp.zuordnen(antwort, [gp.locator_mitte("JN88BN")])[0]


class LocatorTests(unittest.TestCase):
    def test_centre_of_six_and_eight_characters(self):
        self.assertEqual(gp.locator_mitte("jn88bn"), (48.5625, 16.125))
        self.assertEqual(gp.locator_mitte("JN88BN45"), (48.5646, 16.1208))

    def test_field_corners(self):
        s, w, n, o = gp.locator_feld("JN88BN")
        self.assertAlmostEqual(s, 48 + 32.5 / 60)
        self.assertAlmostEqual(w, 16 + 5 / 60)
        self.assertAlmostEqual(n - s, 2.5 / 60)
        self.assertAlmostEqual(o - w, 5 / 60)

    def test_too_coarse_or_invalid(self):
        with self.assertRaisesRegex(ValueError, "zu grob"):
            gp.locator_norm("JN88")
        for bad in ("JN8BN", "ZZ88BN", "JN88BZ", "JN88BN4"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                gp.locator_norm(bad)

    def test_outside_model_area(self):
        with self.assertRaisesRegex(ValueError, "ausserhalb"):
            gp.locator_mitte("JO62QM")                           # Berlin


class AssignTests(unittest.TestCase):
    def test_grid_cell_and_missing_point(self):
        antwort = json.loads(FIXTURE.read_text(encoding="utf-8"))
        d = gp.zuordnen(antwort, [(48.5625, 16.125)])[0]
        self.assertEqual(d["zelle"], (48.561, 16.138))
        self.assertEqual(d["lauf"], "2026-10-24T06:00+00:00")
        with self.assertRaisesRegex(ValueError, "keine Prognose"):
            gp.zuordnen(antwort, [(48.5625, 16.125), (47.0625, 15.4583)])   # Graz fehlt


class StepTests(unittest.TestCase):
    @vienna
    def test_three_hour_grid_across_end_of_summer_time(self):
        zeilen = gp.schritte(daten(), 48, 3)
        stunden = [z["zeit"].strftime("%a %H") for z in zeilen]
        self.assertEqual(stunden[:6], ["Sat 14", "Sat 15", "Sat 18", "Sat 21", "Sun 00", "Sun 03"])
        # 00:00 CEST -> 03:00 CET are four real hours: the step ends at the next grid hour
        self.assertEqual((zeilen[5]["zeit"] - zeilen[4]["zeit"]).total_seconds(), 4 * 3600)
        self.assertEqual(len(zeilen), 17)                        # Sa 14 .. Mo 12

    @vienna
    def test_values_of_a_step(self):
        z = gp.schritte(daten(), 48, 3)[0]                       # Sa 14 (12 UTC), only 1 h to 15
        self.assertEqual(z["temp"], 11.8)
        self.assertEqual(z["achtel"], 8)
        self.assertAlmostEqual(z["wspd"], (4 ** 2 + 0.6 ** 2) ** 0.5, places=3)
        self.assertEqual(gp.gs.richtung(z["wdir"]), "W")
        self.assertAlmostEqual(z["boe"], (8.1 ** 2 + 0.4 ** 2) ** 0.5, places=3)   # gust of 13 UTC

    @vienna
    def test_rain_is_difference_and_never_negative(self):
        zeilen = gp.schritte(daten(), 48, 3)
        self.assertTrue(all(z["regen"] >= 0 for z in zeilen))  # rr_acc dips 0.182 -> 0.179
        regen = {z["zeit"].strftime("%a %H"): round(z["regen"], 2) for z in zeilen}
        self.assertEqual(regen["Sun 12"], 0.72)                  # 0.198 -> 0.92

    @vienna
    def test_hourly_steps_and_limit(self):
        zeilen = gp.schritte(daten(), 6, 1)
        self.assertEqual(len(zeilen), 6)
        self.assertEqual([z["zeit"].hour for z in zeilen], [14, 15, 16, 17, 18, 19])

    def test_wind_direction_convention(self):
        self.assertEqual(round(gp.wind(0, -5)[1]), 0)             # blows south = from north
        self.assertEqual(round(gp.wind(-5, 0)[1]), 90)            # from east
        self.assertEqual(round(gp.wind(5, 0)[1]), 270)            # from west


class OutputTests(unittest.TestCase):
    def setUp(self):
        self.codec = Codec()

    @vienna
    def test_text_report(self):
        d = daten()
        text = gp.bericht("JN88BN", d, gp.schritte(d, 24, 3), 3)
        self.assertTrue(text[0].startswith("Prognose JN88BN (Zelle 48.561 N 16.138 O)"))
        self.assertIn("Sa 24.10.", text)
        self.assertIn("Max. Boe    46 km/h (Bft 6) So 12 Uhr", text)
        self.assertTrue(all(len(z) <= 60 for z in text), max(text, key=len))

    @vienna
    def test_brocast_page_decodes_with_column_meaning(self):
        d = daten()
        seite = gp.brocast_seite("JN88BN", d, gp.schritte(d, 48, 3), 3, 240)
        self.assertEqual((seite["typ"], seite["area"], seite["src"]), ("wx", "JN88BN", gp.QUELLE))
        self.assertLessEqual(len(seite["ti"]), 40)
        pages = [self.codec.decode(f) for f in split(self.codec, {**seite, "id": 31, "rev": 0,
                                                                     "t": 1790000000})]
        blocks = [b for p in pages for b in p.get("blk", [])]
        self.assertEqual(blocks[0]["n"], gp.PROGNOSE_N)
        rows = [r for b in blocks for r in b["rows"]]
        self.assertEqual(rows[0], ["Sa 24.10."])
        self.assertEqual(rows[1], ["14", 80, 118, "W", 40, 81, 0])
        self.assertEqual(sum(len(r) == 1 for r in rows), 3)      # Sa, So, Mo

    @vienna
    def test_two_days_need_two_packed_frames(self):
        d = daten()
        seite = gp.brocast_seite("JN88BN", d, gp.schritte(d, 48, 3), 3, 240)
        built = fragment.build(self.codec, {**seite, "id": 31, "rev": 0, "t": 1790000000},
                               load_zdict())
        self.assertLessEqual(len(built.payloads), 2)

    @vienna
    def test_bulletin_file(self):
        d = daten()
        zeilen = gp.schritte(d, 24, 3)
        with tempfile.TemporaryDirectory() as tmp:
            args = Namespace(tinybox=tmp, ziel="WX", gueltig="4h", schritt=3)
            ziel = gp.bulletin("JN88BN", d, zeilen, args)
            kopf, _, text = ziel.read_text(encoding="utf-8").partition("\n\n")
        felder = dict(z.split(": ", 1) for z in kopf.splitlines())
        self.assertEqual(felder["Replace"], "geosphere-prognose-JN88BN")
        self.assertEqual(felder["Valid"], "4h")
        self.assertEqual(felder["Subject"], "Prognose JN88BN ab Sa 24.10. 14 Uhr")
        self.assertEqual(json.loads(felder["Brocast"])["area"], "JN88BN")
        self.assertIn("Quelle: GeoSphere Austria, NWP (CC BY 4.0)", text)


if __name__ == "__main__":
    unittest.main()
