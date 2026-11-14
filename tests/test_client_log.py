"""R13: the client writes a log file per day (prcore/dailylog.py)."""

from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tbclient import __main__ as main


class ClientLog(unittest.TestCase):
    def test_daily_file_with_legend_and_visible_control_chars(self):
        with tempfile.TemporaryDirectory() as d:
            h = main.file_log(SimpleNamespace(data_dir=Path(d)), debug=False)
            self.assertIsNotNone(h)
            log = logging.getLogger("tbclient.test")
            log.addHandler(h)
            log.setLevel(logging.DEBUG)       # main() sets the root logger
            try:
                log.info("connect OE3GAS-1\x07")
                log.debug("not written without -v")
            finally:
                log.removeHandler(h)
                h.close()
            self.assertTrue(h.path.name.startswith("tbclient-"))
            text = h.path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("# TBClient log"))
            self.assertIn("I tbclient.test", text)
            self.assertIn("connect OE3GAS-1", text)
            self.assertNotIn("\x07", text)
            self.assertNotIn("not written", text)


if __name__ == "__main__":
    unittest.main()
