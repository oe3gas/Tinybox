"""tinybox/store.py: versioned migrations and WAL (Refactoring R12)."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from tinybox.store import SCHEMA_VERSION, Store


class Migrations(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "tinybox.db"

    def tearDown(self):
        self.tmp.cleanup()

    def test_fresh_database(self):
        s = Store(self.path)
        db = s._db
        self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        self.assertEqual(db.execute("PRAGMA journal_mode").fetchone()[0], "wal")
        self.assertEqual(s.migrate(), [])                   # nothing left to do
        s.close()

    def test_older_database_is_brought_up(self):
        Store(self.path).close()
        with sqlite3.connect(self.path) as db:              # back to schema 13
            db.execute("ALTER TABLE client_keys DROP COLUMN lotw")
            db.execute("CREATE TABLE user_keys (call TEXT, pub TEXT, status TEXT, created TEXT,"
                       " changed TEXT, note TEXT)")
            db.execute("INSERT INTO user_keys VALUES ('OE3GAS', 'k1', 'active', 't', 't', '')")
            db.execute("PRAGMA user_version = 13")
        s = Store(self.path)
        db = s._db
        self.assertIn("lotw", {r["name"] for r in db.execute("PRAGMA table_info(client_keys)")})
        self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name = 'user_keys'")
                          .fetchone())
        self.assertEqual(db.execute("SELECT call, pub FROM client_keys").fetchall()[0][:],
                         ("OE3GAS", "k1"))
        self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        s.close()

    def test_memory_database_works_without_wal(self):
        s = Store(":memory:")
        self.assertEqual(s._db.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        s.close()


if __name__ == "__main__":
    unittest.main()
