"""Schreiben auf die Platte (PLANUNG 11, Punkt 9 – eMMC am NanoPi).

Flüchtiges (rxlog, gehörte Stationen, Sendezeitplan, Wiederholungen) wird erst
mit flush() geschrieben, echte Änderungen sofort. Geprüft wird mit einer
zweiten Verbindung auf dieselbe Datei: sie sieht nur, was committet ist.
"""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from brocast import frame
from brocast.codec import Codec
from brocast.daemon import Daemon
from brocast.store import Store

from .test_daemon import T0, make_cfg


class DbFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "brocastd.db"

    def tearDown(self):
        self.tmp.cleanup()

    def on_disk(self, sql: str, params: tuple = ()) -> list[tuple]:
        """Was eine fremde Verbindung sieht = was committet ist."""
        con = sqlite3.connect(self.path)
        try:
            return con.execute(sql, params).fetchall()
        finally:
            con.close()


class StoreTests(DbFile):
    def setUp(self):
        super().setUp()
        self.store = Store(self.path)

    def tearDown(self):
        self.store.close()
        super().tearDown()

    def test_wal_and_normal_sync(self):
        self.assertEqual(self.store.db.execute("PRAGMA journal_mode").fetchone()[0], "wal")
        self.assertEqual(self.store.db.execute("PRAGMA synchronous").fetchone()[0], 1)

    def test_volatile_writes_wait_for_flush(self):
        self.store.add_rxlog({"ts": T0, "heard_from": "OE3XYZ", "result": "foreign"})
        self.store.heard("OE3XYZ", T0)
        # sofort lesbar (Web-GUI) ...
        self.assertEqual(len(self.store.rxlog()), 1)
        self.assertEqual(len(self.store.stations()), 1)
        self.assertTrue(self.store.pending())
        # ... aber noch nicht auf der Platte
        self.assertEqual(self.on_disk("SELECT COUNT(*) FROM rxlog"), [(0,)])
        self.assertTrue(self.store.flush())
        self.assertFalse(self.store.pending())
        self.assertFalse(self.store.flush())                 # nichts mehr zu tun
        self.assertEqual(self.on_disk("SELECT COUNT(*) FROM rxlog"), [(1,)])
        self.assertEqual(self.on_disk("SELECT call FROM stations"), [("OE3XYZ",)])

    def test_real_change_is_written_at_once(self):
        self.store.set_setting("lang", "de")
        self.assertFalse(self.store.pending())
        self.assertEqual(self.on_disk("SELECT value FROM settings"), [("de",)])

    def test_real_change_takes_pending_data_along(self):
        self.store.heard("OE3XYZ", T0)
        self.store.set_setting("lang", "de")
        self.assertFalse(self.store.pending())
        self.assertEqual(self.on_disk("SELECT COUNT(*) FROM stations"), [(1,)])

    def test_repeated_page_is_volatile(self):
        args = dict(org="OE3GAS-5", page_id=1, sub=1, sub_total=1, rev=0, t=T0, typ=None,
                    data=b"x", heard_from="OE3GAS-5")
        self.assertEqual(self.store.save_received(**args, now=T0), "new")
        self.assertFalse(self.store.pending())              # neue Seite: sofort
        self.assertEqual(self.store.save_received(**args, now=T0 + 60), "same")
        self.assertTrue(self.store.pending())               # Wiederholung: später
        self.assertEqual(self.on_disk("SELECT received_at FROM received"), [(T0,)])
        self.store.flush()
        self.assertEqual(self.on_disk("SELECT received_at FROM received"), [(T0 + 60,)])

    def test_close_flushes(self):
        self.store.heard("OE3XYZ", T0)
        self.store.close()
        self.store = Store(self.path)                       # für tearDown
        self.assertEqual(self.on_disk("SELECT COUNT(*) FROM stations"), [(1,)])


class DaemonTests(DbFile):
    """Ein Funk-Frame, der nur wiederholt, darf nichts committen."""

    def test_repeat_frame_writes_nothing(self):
        d = Daemon(make_cfg("listener", ""), db_path=self.path)
        try:
            raw = frame.build("OE3GAS-5", Codec().encode(
                {"id": 24, "rev": 0, "t": T0, "typ": "text", "ti": "Test"}))
            d.on_frame(0, raw)                               # neu: Seite sofort gespeichert
            self.assertEqual(self.on_disk("SELECT COUNT(*) FROM lpages"), [(1,)])
            d.store.flush()
            changes = d.store.db.total_changes
            d.on_frame(0, raw)                               # Karussell-Wiederholung
            d.on_frame(0, frame.build("OE3XYZ-9", b"\xff\xff"))   # kaputter Frame
            self.assertGreater(d.store.db.total_changes, changes)  # im RAM verbucht ...
            self.assertTrue(d.store.pending())                     # ... aber nicht committet
            self.assertEqual(self.on_disk("SELECT COUNT(*) FROM rxlog"), [(1,)])
            self.assertEqual(len(d.store.rxlog()), 3)
        finally:
            d.store.close()
        self.assertEqual(self.on_disk("SELECT COUNT(*) FROM rxlog"), [(3,)])


class ConfigTests(unittest.TestCase):
    def _load(self, text: str):
        from brocast import config
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "brocastd.conf"
            p.write_text("[brocastd]\nmode = listener\n" + text, encoding="utf-8")
            return config.load(p), Path(tmp)

    def test_txlog_default_is_logs(self):
        cfg, base = self._load("")
        self.assertEqual(cfg.txlog_dir, base / "logs")

    def test_empty_txlog_dir_switches_it_off(self):
        cfg, _ = self._load("[logging]\ntxlog_dir =\n")
        self.assertIsNone(cfg.txlog_dir)

    def test_flush_interval(self):
        cfg, _ = self._load("")
        self.assertEqual(cfg.db_flush_sec, 600)
        cfg, _ = self._load("db_flush_sec = 120\n")
        self.assertEqual(cfg.db_flush_sec, 120)
        from brocast.config import ConfigError
        with self.assertRaises(ConfigError):
            self._load("db_flush_sec = 0\n")


if __name__ == "__main__":
    unittest.main()
