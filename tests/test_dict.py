"""DICT command: brocast dictionary as framed ASCII text."""

from __future__ import annotations

import dataclasses
import hashlib
import tempfile
import unittest
from pathlib import Path

from tinybox import dictfile
from tinybox.config import BrocastCfg
from tests.test_tinybox import ROOT, login, make_app, type_lines

SAMPLE = """# comment line
dictionary: test
version: 3   # inline comment stays

envelope:
  8: { name: ti, de: "Gültig für", en: "Valid for" }
"""


class DictFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "d.yaml"
        self.path.write_text(SAMPLE, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_prepare(self):
        d = dictfile.prepare(self.path)
        self.assertEqual(d.version, 3)
        self.assertEqual(len(d.lines), 4)                       # comments/blank lines dropped
        self.assertTrue(all(line.isascii() for line in d.lines))
        self.assertIn('"G\\u00fcltig f\\u00fcr"', d.lines[-1])  # same YAML value, ASCII only
        self.assertEqual(d.sha256, hashlib.sha256("\n".join(d.lines).encode()).hexdigest())
        framed = d.framed()
        self.assertEqual(framed[0], f"#BROCAST-DICT BEGIN v3 lines=4 sha256={d.sha256}")
        self.assertEqual(framed[-1], "#BROCAST-DICT END")

    def test_no_version(self):
        self.path.write_text("dictionary: x\n", encoding="utf-8")
        with self.assertRaises(dictfile.DictError):
            dictfile.prepare(self.path)

    def test_real_dictionary_is_ascii_after_prepare(self):
        d = dictfile.prepare(ROOT / "brocast" / "brocast-core.yaml")
        self.assertGreaterEqual(d.version, 1)
        self.assertTrue(all(line.isascii() for line in d.lines))


class DictCommandTests(unittest.TestCase):
    def test_dict_command(self):
        app = make_app()
        app.cfg.brocast = BrocastCfg(dict_file=ROOT / "brocast" / "brocast-core.yaml")
        s, t = login(app, "OE1ABC")
        t.take()
        type_lines(s, "dict")
        out = t.take()
        self.assertIn("#BROCAST-DICT BEGIN v", out)
        self.assertIn("#BROCAST-DICT END", out)
        self.assertIn("Dictionary sent.", out)
        self.assertTrue(out.isascii())

    def test_not_configured(self):
        app = make_app()
        app.cfg.brocast = BrocastCfg(dict_file=None)
        s, t = login(app, "OE1ABC")
        t.take()
        type_lines(s, "DICT")
        self.assertIn("No brocast dictionary available", t.take())

    def test_missing_file(self):
        app = make_app()
        app.cfg.brocast = BrocastCfg(dict_file=Path("/nonexistent/x.yaml"))
        s, t = login(app, "OE1ABC")
        t.take()
        type_lines(s, "DICT")
        self.assertIn("No brocast dictionary available", t.take())

    def test_config_reads_dict_file(self):
        app = make_app()
        self.assertEqual(app.cfg.brocast.dict_file, ROOT / "brocast" / "brocast-core.yaml")


if __name__ == "__main__":
    unittest.main()
