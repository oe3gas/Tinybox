"""Connection logbook of the client (CR44): one row per connection - station,
way, connect, disconnect, duration, bytes in/out. No contents. Kept forever in
data/tbclient/connlog.db; export as CSV or ADIF (tinybox.connlog)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS connlog (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    call    TEXT NOT NULL,
    via     TEXT NOT NULL,
    t_on    TEXT NOT NULL,
    t_off   TEXT NOT NULL,
    secs    INTEGER NOT NULL,
    rx      INTEGER,
    tx      INTEGER,
    ended   TEXT NOT NULL,           -- user | remote | failed | cancelled
    freq    TEXT                     -- MHz of the session ('' / NULL = not given)
);
"""


class Logbook:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._db: sqlite3.Connection | None = None

    @property
    def db(self) -> sqlite3.Connection:
        """Opened on first use."""
        if self._db is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(str(self.path))
            self._db.row_factory = sqlite3.Row
            self._db.executescript(SCHEMA)
            cols = {r["name"] for r in self._db.execute("PRAGMA table_info(connlog)")}
            if "freq" not in cols:                       # first version of CR44
                self._db.execute("ALTER TABLE connlog ADD COLUMN freq TEXT")
        return self._db

    def add(self, row: dict) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO connlog (call, via, t_on, t_off, secs, rx, tx, ended, freq)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (row["call"], row["via"], row["start"], row["end"], row["secs"], row.get("rx"),
                 row.get("tx"), row["ended"], row.get("freq") or None))

    def rows(self, limit: int | None = None, connected_only: bool = False) -> list[dict]:
        """Newest first."""
        sql = "SELECT * FROM connlog" + (" WHERE ended NOT IN ('failed', 'cancelled')"
                                         if connected_only else "")
        sql += " ORDER BY id DESC" + (" LIMIT ?" if limit else "")
        cur = self.db.execute(sql, (limit,) if limit else ())
        return [{"call": r["call"], "via": r["via"], "start": r["t_on"], "end": r["t_off"],
                 "secs": r["secs"], "rx": r["rx"], "tx": r["tx"], "air_tx": None,
                 "air_rx": None, "ended": r["ended"], "freq": r["freq"] or ""} for r in cur]

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None
