"""SQLite storage. Only this module talks SQL (always with parameters)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA_VERSION = 4   # 4: chat_lines

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,  -- numbers are never reused
    msgid     TEXT NOT NULL UNIQUE,               -- UUID, for MQTT de-duplication
    type      TEXT NOT NULL CHECK (type IN ('P', 'B')),
    status    TEXT NOT NULL DEFAULT 'N' CHECK (status IN ('N', 'Y')),
    to_call   TEXT NOT NULL,
    from_call TEXT NOT NULL,
    subject   TEXT NOT NULL,
    body      TEXT NOT NULL,
    size      INTEGER NOT NULL,
    origin    TEXT NOT NULL,                      -- radio, telnet, sysop, mqtt
    created   TEXT NOT NULL,                      -- ISO 8601 UTC
    read_at   TEXT,
    replace_key TEXT,                             -- inbox "Replace:": update instead of new
    expires   TEXT,                               -- inbox "Valid:": ISO 8601 UTC, then deleted
    brocast   TEXT                                -- inbox "Brocast:": page as JSON (or NULL)
);
CREATE TABLE IF NOT EXISTS jlog (
    call       TEXT PRIMARY KEY,
    first_seen TEXT NOT NULL,
    last_seen  TEXT NOT NULL,
    count      INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
    call       TEXT PRIMARY KEY,
    last_login TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chat_lines (               -- only boards with history
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    board   TEXT NOT NULL,
    call    TEXT NOT NULL,
    text    TEXT NOT NULL,
    created TEXT NOT NULL                             -- ISO 8601 UTC
);
CREATE INDEX IF NOT EXISTS chat_lines_board ON chat_lines (board, created);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Message:
    id: int
    msgid: str
    type: str
    status: str
    to_call: str
    from_call: str
    subject: str
    body: str
    size: int
    origin: str
    created: str
    read_at: str | None
    replace_key: str | None = None
    expires: str | None = None
    brocast: str | None = None          # brocast page (JSON text) delivered with the bulletin


@dataclass
class ChatLine:
    board: str
    call: str
    text: str
    created: str


@dataclass
class JlogEntry:
    call: str
    first_seen: str
    last_seen: str
    count: int


class Store:
    def __init__(self, db_path: Path | str) -> None:
        if str(db_path) != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(db_path))
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.executescript(SCHEMA)
        # schema 1 -> 2: two columns for the inbox folder; 2 -> 3: brocast page
        # (existing rows stay as they are)
        cols = {r["name"] for r in self._db.execute("PRAGMA table_info(messages)")}
        for col in ("replace_key", "expires", "brocast"):
            if col not in cols:
                self._db.execute(f"ALTER TABLE messages ADD COLUMN {col} TEXT")
        self._db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    # --- messages -------------------------------------------------------

    def add_message(self, *, msgid: str, type: str, to_call: str, from_call: str,
                    subject: str, body: str, origin: str, created: str,
                    replace_key: str | None = None, expires: str | None = None,
                    brocast: str | None = None) -> int:
        size = len(body.encode("utf-8"))
        with self._db:
            cur = self._db.execute(
                "INSERT INTO messages (msgid, type, status, to_call, from_call, subject,"
                " body, size, origin, created, replace_key, expires, brocast)"
                " VALUES (?, ?, 'N', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (msgid, type, to_call, from_call, subject, body, size, origin, created,
                 replace_key, expires, brocast),
            )
        return int(cur.lastrowid)

    def get_by_replace_key(self, key: str) -> Message | None:
        row = self._db.execute("SELECT * FROM messages WHERE replace_key = ? AND type = 'B'"
                               " ORDER BY id DESC", (key,)).fetchone()
        return Message(**dict(row)) if row else None

    def replace_content(self, msg_id: int, *, to_call: str, from_call: str, subject: str,
                        body: str, created: str, expires: str | None,
                        brocast: str | None = None) -> None:
        """New content for the same message number; it counts as new (unread) again."""
        with self._db:
            self._db.execute(
                "UPDATE messages SET to_call = ?, from_call = ?, subject = ?, body = ?, size = ?,"
                " created = ?, expires = ?, brocast = ?, status = 'N', read_at = NULL"
                " WHERE id = ?",
                (to_call, from_call, subject, body, len(body.encode("utf-8")), created,
                 expires, brocast, msg_id))

    def set_expires(self, msg_id: int, expires: str | None) -> None:
        with self._db:
            self._db.execute("UPDATE messages SET expires = ? WHERE id = ?", (expires, msg_id))

    def delete_expired(self, now_iso: str) -> list[int]:
        """Bulletins whose own validity ("Valid:") is over."""
        rows = self._db.execute(
            "SELECT id FROM messages WHERE expires IS NOT NULL AND expires < ?", (now_iso,)
        ).fetchall()
        ids = [r["id"] for r in rows]
        with self._db:
            self._db.executemany("DELETE FROM messages WHERE id = ?", [(i,) for i in ids])
        return ids

    def get(self, msg_id: int) -> Message | None:
        row = self._db.execute("SELECT * FROM messages WHERE id = ?", (msg_id,)).fetchone()
        return Message(**dict(row)) if row else None

    def get_by_msgid(self, msgid: str) -> Message | None:
        row = self._db.execute("SELECT * FROM messages WHERE msgid = ?", (msgid,)).fetchone()
        return Message(**dict(row)) if row else None

    def list_messages(self) -> list[Message]:
        rows = self._db.execute("SELECT * FROM messages ORDER BY id DESC").fetchall()
        return [Message(**dict(r)) for r in rows]

    def mark_read(self, msg_id: int) -> None:
        with self._db:
            self._db.execute(
                "UPDATE messages SET status = 'Y', read_at = COALESCE(read_at, ?) WHERE id = ?",
                (utc_now(), msg_id),
            )

    def delete(self, msg_id: int) -> bool:
        with self._db:
            cur = self._db.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
        return cur.rowcount > 0

    _EDITABLE = {"to_call", "from_call", "type", "status", "subject"}

    def update_field(self, msg_id: int, field: str, value: str) -> None:
        if field not in self._EDITABLE:  # column names cannot be parameters
            raise ValueError(f"field not editable: {field}")
        with self._db:
            self._db.execute(f"UPDATE messages SET {field} = ? WHERE id = ?", (value, msg_id))

    def delete_bulletins_older_than(self, days: int) -> list[int]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = self._db.execute(
            "SELECT id FROM messages WHERE type = 'B' AND created < ?", (cutoff,)
        ).fetchall()
        ids = [r["id"] for r in rows]
        with self._db:
            self._db.executemany("DELETE FROM messages WHERE id = ?", [(i,) for i in ids])
        return ids

    # --- chat -----------------------------------------------------------

    def chat_add(self, board: str, call: str, text: str, created: str) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO chat_lines (board, call, text, created) VALUES (?, ?, ?, ?)",
                (board, call, text, created))

    def chat_recent(self, board: str, since_iso: str, limit: int) -> list[ChatLine]:
        """The newest `limit` lines since `since_iso`, oldest first."""
        rows = self._db.execute(
            "SELECT board, call, text, created FROM chat_lines"
            " WHERE board = ? AND created >= ? ORDER BY id DESC LIMIT ?",
            (board, since_iso, limit)).fetchall()
        return [ChatLine(**dict(r)) for r in reversed(rows)]

    def chat_purge(self, keep: dict[str, str]) -> int:
        """keep: board -> oldest allowed ISO time. Lines of other boards
        (removed from the config or switched to live) are deleted too."""
        with self._db:
            n = 0
            for board, cutoff in keep.items():
                n += self._db.execute("DELETE FROM chat_lines WHERE board = ? AND created < ?",
                                      (board, cutoff)).rowcount
            marks = ",".join("?" * len(keep))
            n += self._db.execute(f"DELETE FROM chat_lines WHERE board NOT IN ({marks})",
                                  list(keep)).rowcount
        return n

    # --- JLOG / users ---------------------------------------------------

    def jlog_touch(self, call: str) -> None:
        now = utc_now()
        with self._db:
            self._db.execute(
                "INSERT INTO jlog (call, first_seen, last_seen, count) VALUES (?, ?, ?, 1)"
                " ON CONFLICT(call) DO UPDATE SET last_seen = excluded.last_seen,"
                " count = count + 1",
                (call, now, now),
            )

    def jlog_list(self, limit: int = 20) -> list[JlogEntry]:
        rows = self._db.execute(
            "SELECT * FROM jlog ORDER BY last_seen DESC LIMIT ?", (limit,)
        ).fetchall()
        return [JlogEntry(**dict(r)) for r in rows]

    def user_login(self, call: str) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO users (call, last_login) VALUES (?, ?)"
                " ON CONFLICT(call) DO UPDATE SET last_login = excluded.last_login",
                (call, utc_now()),
            )
