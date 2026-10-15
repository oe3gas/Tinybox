"""SQLite store for spots and the times the collector was connected.

The connection times let the digest say how much of the 24 hours it really
covers - a summary built from three hours of data must not look like a full day.
Spots older than keep_days are deleted (prune).
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from .spots import Spot

SCHEMA = """
CREATE TABLE IF NOT EXISTS spot (
    id        INTEGER PRIMARY KEY,
    ts        INTEGER NOT NULL,          -- received, unix time UTC
    freq      REAL    NOT NULL,          -- kHz
    band      TEXT    NOT NULL,
    mode      TEXT    NOT NULL,
    dx        TEXT    NOT NULL,
    spotter   TEXT    NOT NULL,
    comment   TEXT    NOT NULL,
    skimmer   INTEGER NOT NULL,
    dx_prefix TEXT    NOT NULL,          -- primary prefix of the DXCC entity, '' = unknown
    dx_name   TEXT    NOT NULL,
    dx_cont   TEXT    NOT NULL,
    sp_prefix TEXT    NOT NULL,
    sp_cont   TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS spot_ts ON spot (ts);
CREATE TABLE IF NOT EXISTS uptime (
    id    INTEGER PRIMARY KEY,
    node  TEXT    NOT NULL,
    start INTEGER NOT NULL,
    last  INTEGER NOT NULL
);
"""


class Store:
    def __init__(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    # --- writing (collector) -------------------------------------------------

    def add(self, spot: Spot, ts: float, dx_ent=None, sp_ent=None) -> None:
        """dx_ent / sp_ent: (Entity, continent) from Cty.lookup or None."""
        self.db.execute(
            "INSERT INTO spot (ts, freq, band, mode, dx, spotter, comment, skimmer,"
            " dx_prefix, dx_name, dx_cont, sp_prefix, sp_cont)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (int(ts), spot.freq, spot.band, spot.mode, spot.dx, spot.spotter,
             spot.comment, int(spot.skimmer),
             dx_ent[0].prefix if dx_ent else "", dx_ent[0].name if dx_ent else "",
             dx_ent[1] if dx_ent else "",
             sp_ent[0].prefix if sp_ent else "", sp_ent[1] if sp_ent else ""))

    def session_start(self, node: str, ts: float) -> int:
        cur = self.db.execute("INSERT INTO uptime (node, start, last) VALUES (?,?,?)",
                              (node, int(ts), int(ts)))
        self.db.commit()
        return int(cur.lastrowid)

    def session_alive(self, session_id: int, ts: float) -> None:
        self.db.execute("UPDATE uptime SET last = ? WHERE id = ?", (int(ts), session_id))

    def commit(self) -> None:
        self.db.commit()

    def prune(self, keep_days: int, now: float | None = None) -> int:
        cutoff = int((time.time() if now is None else now) - keep_days * 86400)
        n = self.db.execute("DELETE FROM spot WHERE ts < ?", (cutoff,)).rowcount
        self.db.execute("DELETE FROM uptime WHERE last < ?", (cutoff,))
        self.db.commit()
        return n

    # --- reading (digest, show) ----------------------------------------------

    def spots(self, since: float, until: float) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM spot WHERE ts >= ? AND ts < ? ORDER BY ts",
                               (int(since), int(until))).fetchall()

    def last(self, n: int) -> list[sqlite3.Row]:
        rows = self.db.execute("SELECT * FROM spot ORDER BY ts DESC, id DESC LIMIT ?",
                               (n,)).fetchall()
        return rows[::-1]

    def coverage(self, since: float, until: float) -> float:
        """Seconds within [since, until) in which the collector was connected."""
        rows = self.db.execute("SELECT start, last FROM uptime WHERE last >= ? AND start < ?",
                               (int(since), int(until))).fetchall()
        spans = sorted((max(r["start"], since), min(r["last"], until)) for r in rows)
        total, end = 0.0, since
        for a, b in spans:                      # merge overlapping sessions
            a = max(a, end)
            if b > a:
                total += b - a
                end = b
        return total
