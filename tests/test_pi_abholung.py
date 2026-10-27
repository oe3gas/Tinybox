"""pi_abholung.py: late fetch (Valid: shortened / dropped), outage warning."""

from __future__ import annotations

import io
import tarfile
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pi_abholung as pa
from tinybox.adapters.inbox import parse

WETTER = (b"To: WX\nSubject: Wetter Hollabrunn 19:00\nReplace: geosphere-wetter-11082\n"
          b"Valid: 2h\n\nTemperatur 12,5 C\nValid: 2h steht auch im Text\n")


def tar_mit(dateien: dict[str, tuple[bytes, float]]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for name, (inhalt, mtime) in dateien.items():
            ti = tarfile.TarInfo(name)
            ti.size, ti.mtime = len(inhalt), mtime
            tf.addfile(ti, io.BytesIO(inhalt))
    return buf.getvalue()


class GueltigkeitTests(unittest.TestCase):
    def test_frisch_unveraendert(self):
        self.assertEqual(pa.gueltigkeit_anpassen(WETTER, 60), WETTER)

    def test_alter_wird_abgezogen(self):
        neu = pa.gueltigkeit_anpassen(WETTER, 45 * 60)
        b = parse(neu)
        self.assertEqual(b.valid_min, 75)
        self.assertIn("Valid: 2h steht auch im Text", b.body)   # text untouched

    def test_abgelaufen(self):
        self.assertIsNone(pa.gueltigkeit_anpassen(WETTER, 2 * 3600))
        self.assertIsNone(pa.gueltigkeit_anpassen(WETTER, 30 * 3600))

    def test_mindestens_eine_minute(self):
        self.assertEqual(parse(pa.gueltigkeit_anpassen(WETTER, 119 * 60 + 50)).valid_min, 1)

    def test_ohne_valid_unveraendert(self):
        roh = b"To: DX\nSubject: x\n\ntext\n"
        self.assertEqual(pa.gueltigkeit_anpassen(roh, 10 * 86400), roh)

    def test_pi_uhr_voraus(self):
        self.assertEqual(pa.gueltigkeit_anpassen(WETTER, -600), WETTER)

    def test_crlf_und_tage(self):
        roh = b"To: DX\r\nSubject: x\r\nValid: 7d\r\n\r\ntext\r\n"
        self.assertEqual(parse(pa.gueltigkeit_anpassen(roh, 86400)).valid_min, 6 * 1440)


class AbholenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.args = SimpleNamespace(eingang=self.dir / "eingang", log=None)
        self.acks: list[str] = []

    def fake_ssh(self, paket):
        def ssh(_args, befehl, timeout=60):
            if befehl[0] == "bundle":
                return paket
            self.acks.extend(befehl[1:])
            return b""
        return ssh

    def test_abgelaufenes_nicht_zustellen_aber_quittieren(self):
        jetzt = 1_800_000_000
        paket = tar_mit({"alt.txt": (WETTER, jetzt - 3 * 3600),
                         "spaet.txt": (WETTER, jetzt - 30 * 60),
                         "frisch.txt": (WETTER, jetzt - 10)})
        with mock.patch.object(pa, "ssh", self.fake_ssh(paket)), \
                mock.patch.object(pa, "protokoll"):
            geholt = pa.abholen(self.args, jetzt)
        self.assertEqual(sorted(geholt), ["frisch.txt", "spaet.txt"])
        self.assertEqual(sorted(self.acks), ["alt.txt", "frisch.txt", "spaet.txt"])
        self.assertFalse((self.args.eingang / "alt.txt").exists())
        self.assertEqual(parse((self.args.eingang / "spaet.txt").read_bytes()).valid_min, 90)


class WarnungTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        d = Path(tmp.name)
        key = d / "key"
        key.write_text("x")
        self.argv = ["--host", "pi", "--key", str(key), "--eingang", str(d / "ein")]
        p = mock.patch.object(pa, "STATE", d / "state")
        p.start()
        self.addCleanup(p.stop)
        self.zeilen: list[str] = []

    def lauf(self, zeit, fehler=True):
        def abholen(_args, _jetzt):
            if fehler:
                raise pa.AbholFehler("Pi pi antwortet nicht")
            return []
        with mock.patch.object(pa, "abholen", abholen), \
                mock.patch.object(pa.time, "time", return_value=zeit), \
                mock.patch.object(pa, "protokoll", lambda _a, t: self.zeilen.append(t)):
            return pa.main(self.argv)

    def test_ablauf(self):
        t0 = 1_800_000_000
        self.assertEqual(self.lauf(t0, fehler=False), 0)
        self.assertEqual(self.zeilen, [])
        self.lauf(t0 + 300)                                   # first failure: reported
        self.lauf(t0 + 600)                                   # silent
        self.assertEqual(len(self.zeilen), 1)
        self.assertTrue(self.zeilen[0].startswith("FEHLER"))
        self.lauf(t0 + 3600)                                  # 60 min since last ok: warn
        self.lauf(t0 + 7200)                                  # only once
        self.assertEqual(len(self.zeilen), 2)
        self.assertIn("WARNUNG seit 60 min", self.zeilen[1])
        self.assertEqual(self.lauf(t0 + 9000, fehler=False), 0)
        self.assertIn("wieder in Ordnung (letzte Abholung vor 2 h 30 min)", self.zeilen[2])

    def test_altes_zustandsformat(self):
        pa.STATE.write_text("fehler\n", encoding="ascii")
        self.lauf(1_800_000_000)
        self.assertEqual(self.zeilen, [])                     # outage already reported


if __name__ == "__main__":
    unittest.main()
