"""Bilder als Teletext-Mosaik: Zeichentabelle, Umrechnung, Seite, Konverter."""

from __future__ import annotations

import unicodedata
import unittest
from pathlib import Path

from brocast import mosaic
from brocast.imagecmd import gueltig_minuten, schluessel, seite

ROOT = Path(__file__).resolve().parent.parent


class TabelleTests(unittest.TestCase):
    def test_table_matches_unicode(self):
        """Gegenprobe zur Tabelle: die Unicode-Namen nennen die belegten Felder."""
        feld = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16, 6: 32}        # Name "SEXTANT-135" -> Bits
        self.assertEqual(len(mosaic.TABELLE), 64)
        self.assertEqual(mosaic.TABELLE[0], " ")
        self.assertEqual(mosaic.TABELLE[63], "█")
        for bits, ch in enumerate(mosaic.TABELLE):
            if bits in (0, 21, 42, 63):                      # leer, links, rechts, voll
                continue
            name = unicodedata.name(ch)
            self.assertTrue(name.startswith("BLOCK SEXTANT-"), name)
            self.assertEqual(sum(feld[int(d)] for d in name.rsplit("-", 1)[1]), bits, name)

    def test_half_blocks(self):
        self.assertEqual(unicodedata.name(mosaic.TABELLE[21]), "LEFT HALF BLOCK")
        self.assertEqual(unicodedata.name(mosaic.TABELLE[42]), "RIGHT HALF BLOCK")

    def test_no_duplicates(self):
        self.assertEqual(len(set(mosaic.TABELLE)), 64)


class RasterTests(unittest.TestCase):
    def test_single_dots(self):
        """Jedes der sechs Felder einzeln: ergibt genau das Zeichen der Tabelle."""
        felder = ((0, 0), (1, 0), (0, 1), (1, 1), (0, 2), (1, 2))
        for i, (dx, dy) in enumerate(felder):
            zeilen = mosaic.aus_punkten(lambda x, y, dx=dx, dy=dy: (x, y) == (dx, dy), 1, 1)
            self.assertEqual(zeilen, [mosaic.TABELLE[mosaic.FELD_BITS[i]]])

    def test_full_and_empty(self):
        self.assertEqual(mosaic.aus_punkten(lambda x, y: True, 3, 1), ["███"])
        self.assertEqual(mosaic.aus_punkten(lambda x, y: False, 3, 2), ["", ""])

    def test_rows_keep_the_aspect(self):
        """7 x 12 Bildpunkte je Zeichen: ein quadratisches Bild wird nicht verzerrt."""
        zeilen = mosaic.zeilen_fuer(40, 300, 300)
        self.assertEqual(zeilen, round(40 * 7 / 12))
        breit = mosaic.zeilen_fuer(40, 400, 200)
        self.assertEqual(breit, round(40 * 7 * 200 / (12 * 400)))

    def test_is_mosaic(self):
        bild = mosaic.aus_punkten(lambda x, y: (x + y) % 2 == 0, 4, 2)
        self.assertTrue(mosaic.ist_mosaik("\n".join(bild)))
        self.assertFalse(mosaic.ist_mosaik("Wetter Hollabrunn"))
        self.assertFalse(mosaic.ist_mosaik("   \n  "))            # nur Leerzeichen ist kein Bild
        self.assertFalse(mosaic.ist_mosaik(bild[0] + " Text"))


class SeiteTests(unittest.TestCase):
    def setUp(self):
        self.zeilen = mosaic.aus_punkten(lambda x, y: (x // 3 + y // 3) % 2 == 0, 20, 7)

    def test_blocks_are_small_enough_for_one_frame(self):
        bloecke = mosaic.bloecke(self.zeilen, 3)
        self.assertEqual(len(bloecke), 3)                         # 7 Zeilen -> 3 + 3 + 1
        for b in bloecke:
            self.assertEqual(b["k"], "pre")
            self.assertLessEqual(len(b["x"].encode("utf-8")), 240)

    def test_page(self):
        page = seite(self.zeilen, "Testbild", "bild", 10080, "Unterschrift")
        self.assertEqual((page["typ"], page["cat"], page["exp"]), ("text", ["bild"], 10080))
        self.assertEqual(page["blk"][-1], {"k": "para", "x": "Unterschrift"})
        self.assertTrue(all(mosaic.ist_mosaik(b["x"]) for b in page["blk"][:-1]))

    def test_page_fits_in_fragments(self):
        """Die Seite muss im Frame-Format 2 in wenige Frames passen."""
        from brocast import fragment, zdict
        from brocast.codec import Codec
        page = {**seite(self.zeilen, "Testbild", "bild", 10080), "id": 48, "rev": 0, "t": 1790000000}
        built = fragment.build(Codec(), page, zdict.load())
        self.assertTrue(built.packed)
        self.assertLessEqual(built.fragments, 4)

    def test_valid_and_key(self):
        self.assertEqual((gueltig_minuten("7d"), gueltig_minuten("6h"), gueltig_minuten("90m")),
                         (10080, 360, 90))
        self.assertEqual(gueltig_minuten("45"), 45)
        with self.assertRaises(ValueError):
            gueltig_minuten("morgen")
        self.assertEqual(schluessel(Path("/tmp/Shack OE3GAS (2).JPG")), "shack-oe3gas-2")
        self.assertEqual(schluessel(Path("...jpg")), "bild")


class SchriftTests(unittest.TestCase):
    """Die Pixelschrift muss jedes Mosaikzeichen kennen, sonst bleiben im Bild Lücken."""

    def test_font_has_every_mosaic_character(self):
        try:
            from fontTools.ttLib import TTFont
        except ImportError:
            self.skipTest("fontTools nicht installiert (nur fuer den Schrift-Bau noetig)")
        font = TTFont(ROOT / "brocast" / "web" / "teletext.woff")
        bekannt = set(font.getBestCmap())
        fehlt = [ch for ch in mosaic.TABELLE if ord(ch) not in bekannt]
        self.assertEqual(fehlt, [], "teletext.woff neu bauen: tools/build_teletext_font.py")


if __name__ == "__main__":
    unittest.main()
