"""SQLite storage for the simulated mailboxes (fwdsim.db).

All simulated mailboxes share one file; every row carries the mailbox call.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .model import Message, iso, utc_now

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    bbs        TEXT NOT NULL,
    nr         INTEGER NOT NULL,          -- local number inside this mailbox
    type       TEXT NOT NULL,
    status     TEXT NOT NULL,
    to_call    TEXT NOT NULL,
    at_addr    TEXT NOT NULL,
    from_call  TEXT NOT NULL,
    bid        TEXT NOT NULL,
    subject    TEXT NOT NULL,
    body       TEXT NOT NULL,
    rlines     TEXT NOT NULL,             -- newest first, one per line
    created    TEXT NOT NULL,
    received_from TEXT NOT NULL,
    note       TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS bids (
    bbs  TEXT NOT NULL,
    bid  TEXT NOT NULL,
    seen TEXT NOT NULL,
    PRIMARY KEY (bbs, bid)
);
CREATE TABLE IF NOT EXISTS queue (
    bbs    TEXT NOT NULL,
    msg    INTEGER NOT NULL,              -- messages.id
    peer   TEXT NOT NULL,
    state  TEXT NOT NULL,                 -- open, later, done, rejected
    PRIMARY KEY (bbs, msg, peer)
);
CREATE TABLE IF NOT EXISTS counters (
    bbs  TEXT PRIMARY KEY,
    nr   INTEGER NOT NULL,
    bid  INTEGER NOT NULL
);
"""


class Store:
    def __init__(self, path: str | Path = ":memory:") -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def reset(self) -> None:
        """Empty the mailboxes. The counters stay, so BIDs are never reused."""
        with self.db:
            for t in ("messages", "bids", "queue"):
                self.db.execute(f"DELETE FROM {t}")

    # --- counters ---------------------------------------------------------

    def _next(self, bbs: str, column: str, start: int) -> int:
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO counters (bbs, nr, bid) VALUES (?, 0, ?)",
                            (bbs, start))
            self.db.execute(f"UPDATE counters SET {column} = {column} + 1 WHERE bbs = ?", (bbs,))
            row = self.db.execute(f"SELECT {column} FROM counters WHERE bbs = ?", (bbs,)).fetchone()
        return int(row[0])

    def next_nr(self, bbs: str) -> int:
        return self._next(bbs, "nr", 0)

    def next_bid_nr(self, bbs: str, start: int) -> int:
        return self._next(bbs, "bid", start)

    # --- BIDs ---------------------------------------------------------------

    def bid_known(self, bbs: str, bid: str) -> bool:
        return self.db.execute("SELECT 1 FROM bids WHERE bbs = ? AND bid = ?",
                               (bbs, bid.upper())).fetchone() is not None

    def bid_add(self, bbs: str, bid: str) -> None:
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO bids (bbs, bid, seen) VALUES (?, ?, ?)",
                            (bbs, bid.upper(), iso(utc_now())))

    # --- messages -----------------------------------------------------------

    def add(self, bbs: str, m: Message) -> Message:
        m.id = 0
        nr = self.next_nr(bbs)
        with self.db:
            cur = self.db.execute(
                "INSERT INTO messages (bbs, nr, type, status, to_call, at_addr, from_call, bid,"
                " subject, body, rlines, created, received_from, note)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (bbs, nr, m.type, m.status, m.to_call, m.at_addr, m.from_call, m.bid,
                 m.subject, m.body, "\n".join(m.rlines), m.created or iso(utc_now()),
                 m.received_from, m.note))
        m.id = nr
        self.bid_add(bbs, m.bid)
        return m

    def _row(self, r: sqlite3.Row) -> Message:
        return Message(type=r["type"], to_call=r["to_call"], at_addr=r["at_addr"],
                       from_call=r["from_call"], bid=r["bid"], subject=r["subject"],
                       body=r["body"], rlines=[x for x in r["rlines"].split("\n") if x],
                       id=r["nr"], status=r["status"], created=r["created"],
                       received_from=r["received_from"], note=r["note"])

    def rowid(self, bbs: str, nr: int) -> int:
        row = self.db.execute("SELECT id FROM messages WHERE bbs = ? AND nr = ?",
                              (bbs, nr)).fetchone()
        return int(row["id"]) if row else 0

    def get(self, bbs: str, nr: int) -> Message | None:
        r = self.db.execute("SELECT * FROM messages WHERE bbs = ? AND nr = ?",
                            (bbs, nr)).fetchone()
        return self._row(r) if r else None

    def by_bid(self, bbs: str, bid: str) -> Message | None:
        r = self.db.execute("SELECT * FROM messages WHERE bbs = ? AND bid = ? ORDER BY id DESC",
                            (bbs, bid.upper())).fetchone()
        return self._row(r) if r else None

    def list(self, bbs: str) -> list[Message]:
        rows = self.db.execute("SELECT * FROM messages WHERE bbs = ? ORDER BY nr",
                               (bbs,)).fetchall()
        return [self._row(r) for r in rows]

    def set_status(self, bbs: str, nr: int, status: str, note: str = "") -> None:
        with self.db:
            self.db.execute("UPDATE messages SET status = ?, note = ? WHERE bbs = ? AND nr = ?",
                            (status, note, bbs, nr))

    # --- forward queue -----------------------------------------------------

    def enqueue(self, bbs: str, nr: int, peer: str) -> None:
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO queue (bbs, msg, peer, state)"
                            " VALUES (?, ?, ?, 'open')", (bbs, self.rowid(bbs, nr), peer))

    def pending(self, bbs: str, peer: str) -> list[Message]:
        rows = self.db.execute(
            "SELECT m.* FROM queue q JOIN messages m ON m.id = q.msg"
            " WHERE q.bbs = ? AND q.peer = ? AND q.state IN ('open', 'later')"
            " ORDER BY m.id", (bbs, peer)).fetchall()
        return [self._row(r) for r in rows]

    def set_queue(self, bbs: str, nr: int, peer: str, state: str) -> None:
        with self.db:
            self.db.execute("UPDATE queue SET state = ? WHERE bbs = ? AND msg = ? AND peer = ?",
                            (state, bbs, self.rowid(bbs, nr), peer))

    def queue_states(self, bbs: str, nr: int) -> dict[str, str]:
        rows = self.db.execute("SELECT peer, state FROM queue WHERE bbs = ? AND msg = ?",
                               (bbs, self.rowid(bbs, nr))).fetchall()
        return {r["peer"]: r["state"] for r in rows}
