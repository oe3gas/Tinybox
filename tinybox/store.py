"""SQLite storage. Only this module talks SQL (always with parameters)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA_VERSION = 6   # 4: chat_lines; 5: forwarding fields, bids, fwd_queue; 6: fwd_partial

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
    brocast   TEXT,                               -- inbox "Brocast:": page as JSON (or NULL)
    -- schema 5: forwarding (all empty for purely local mail)
    at_addr   TEXT NOT NULL DEFAULT '',           -- @ address (P) or area (B), '' = local
    bid       TEXT,                               -- BID/MID, max 12 chars, unique
    bid_kind  TEXT NOT NULL DEFAULT '',           -- B real BID, M generated MID (W0RLI)
    rlines    TEXT NOT NULL DEFAULT '',           -- R: lines, newest first, one per line
    fwd       TEXT NOT NULL DEFAULT '',           -- '' local, $ to forward, F forwarded, H held
    note      TEXT NOT NULL DEFAULT ''            -- why a message is held
);
CREATE TABLE IF NOT EXISTS bids (                     -- every BID ever seen (duplicate check)
    bid        TEXT PRIMARY KEY,
    first_seen TEXT NOT NULL,
    origin     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fwd_queue (                -- filled by the forward module only
    msg_id  INTEGER NOT NULL,
    partner TEXT NOT NULL,
    state   TEXT NOT NULL,                            -- open, later, done, rejected
    changed TEXT NOT NULL,
    PRIMARY KEY (msg_id, partner)
);
CREATE TABLE IF NOT EXISTS fwd_partial (              -- B1 restart: half received messages
    partner TEXT NOT NULL,
    bid     TEXT NOT NULL,
    data    BLOB NOT NULL,                            -- compressed payload received so far
    tries   INTEGER NOT NULL DEFAULT 0,               -- restarts asked for
    created TEXT NOT NULL,
    PRIMARY KEY (partner, bid)
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
    at_addr: str = ""                   # @ address (P) or distribution area (B); '' = local
    bid: str | None = None              # BID/MID
    rlines: str = ""                    # R: lines, newest first, "\n"-separated
    fwd: str = ""                       # '' local, '$' to forward, 'F' forwarded, 'H' held
    note: str = ""                      # reason for 'H'
    bid_kind: str = ""                  # 'B' real BID, 'M' generated MID (personal mail)

    @property
    def rline_list(self) -> list[str]:
        return [x for x in self.rlines.split("\n") if x]


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
        # schema 1 -> 2: two columns for the inbox folder; 2 -> 3: brocast page;
        # 4 -> 5: forwarding fields (existing rows stay as they are, BIDs are
        # given by MessageService.assign_missing_bids)
        cols = {r["name"] for r in self._db.execute("PRAGMA table_info(messages)")}
        for col in ("replace_key", "expires", "brocast", "bid"):
            if col not in cols:
                self._db.execute(f"ALTER TABLE messages ADD COLUMN {col} TEXT")
        for col in ("at_addr", "rlines", "fwd", "note", "bid_kind"):
            if col not in cols:
                self._db.execute(f"ALTER TABLE messages ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
        self._db.execute("CREATE UNIQUE INDEX IF NOT EXISTS messages_bid ON messages (bid)")
        self._db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    # --- messages -------------------------------------------------------

    def add_message(self, *, msgid: str, type: str, to_call: str, from_call: str,
                    subject: str, body: str, origin: str, created: str,
                    replace_key: str | None = None, expires: str | None = None,
                    brocast: str | None = None, at_addr: str = "", bid: str | None = None,
                    rlines: str = "", fwd: str = "", note: str = "") -> int:
        size = len(body.encode("utf-8"))
        with self._db:
            cur = self._db.execute(
                "INSERT INTO messages (msgid, type, status, to_call, from_call, subject,"
                " body, size, origin, created, replace_key, expires, brocast,"
                " at_addr, bid, rlines, fwd, note)"
                " VALUES (?, ?, 'N', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (msgid, type, to_call, from_call, subject, body, size, origin, created,
                 replace_key, expires, brocast, at_addr, bid, rlines, fwd, note),
            )
        return int(cur.lastrowid)

    # --- forwarding fields ------------------------------------------------

    def set_forward_fields(self, msg_id: int, *, bid: str | None = None,
                           rlines: str | None = None, fwd: str | None = None,
                           note: str | None = None, bid_kind: str | None = None) -> None:
        sets, args = [], []
        for col, val in (("bid", bid), ("rlines", rlines), ("fwd", fwd), ("note", note),
                         ("bid_kind", bid_kind)):
            if val is not None:
                sets.append(f"{col} = ?")
                args.append(val)
        if sets:
            with self._db:
                self._db.execute(f"UPDATE messages SET {', '.join(sets)} WHERE id = ?",
                                 (*args, msg_id))

    # --- forward queue (used by the forward module only) -----------------

    def fwd_enqueue(self, msg_id: int, partner: str) -> None:
        with self._db:
            self._db.execute("INSERT OR IGNORE INTO fwd_queue (msg_id, partner, state, changed)"
                             " VALUES (?, ?, 'open', ?)", (msg_id, partner, utc_now()))

    def fwd_pending(self, partner: str) -> list[Message]:
        rows = self._db.execute(
            "SELECT m.* FROM fwd_queue q JOIN messages m ON m.id = q.msg_id"
            " WHERE q.partner = ? AND q.state IN ('open', 'later') AND m.fwd != 'H'"
            " ORDER BY m.id", (partner,)).fetchall()
        return [Message(**dict(r)) for r in rows]

    def fwd_set(self, msg_id: int, partner: str, state: str) -> None:
        with self._db:
            self._db.execute("UPDATE fwd_queue SET state = ?, changed = ?"
                             " WHERE msg_id = ? AND partner = ?",
                             (state, utc_now(), msg_id, partner))

    def fwd_states(self, msg_id: int) -> dict[str, str]:
        return {r["partner"]: r["state"] for r in self._db.execute(
            "SELECT partner, state FROM fwd_queue WHERE msg_id = ?", (msg_id,))}

    def fwd_remove(self, msg_ids: list[int]) -> None:
        with self._db:
            self._db.executemany("DELETE FROM fwd_queue WHERE msg_id = ?", [(i,) for i in msg_ids])

    def fwd_queue_list(self) -> list[tuple[str, int, str, str]]:
        """(partner, msg_id, state, changed) of everything not yet done."""
        return [(r["partner"], r["msg_id"], r["state"], r["changed"]) for r in self._db.execute(
            "SELECT * FROM fwd_queue WHERE state IN ('open', 'later') ORDER BY partner, msg_id")]

    # --- B1 restart data (forward module only) -----------------------------

    def partial_get(self, partner: str, bid: str) -> tuple[bytes, int] | None:
        row = self._db.execute("SELECT data, tries FROM fwd_partial WHERE partner = ? AND bid = ?",
                               (partner, bid)).fetchone()
        return (bytes(row["data"]), row["tries"]) if row else None

    def partial_put(self, partner: str, bid: str, data: bytes) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO fwd_partial (partner, bid, data, tries, created) VALUES (?, ?, ?, 0, ?)"
                " ON CONFLICT (partner, bid) DO UPDATE SET data = excluded.data",
                (partner, bid, data, utc_now()))

    def partial_tried(self, partner: str, bid: str) -> None:
        with self._db:
            self._db.execute("UPDATE fwd_partial SET tries = tries + 1 WHERE partner = ? AND bid = ?",
                             (partner, bid))

    def partial_drop(self, partner: str, bid: str) -> None:
        with self._db:
            self._db.execute("DELETE FROM fwd_partial WHERE partner = ? AND bid = ?", (partner, bid))

    def purge_partials(self, days: int = 2) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._db:
            return self._db.execute("DELETE FROM fwd_partial WHERE created < ?", (cutoff,)).rowcount

    def fill_bid_kind(self) -> None:
        with self._db:
            self._db.execute("UPDATE messages SET bid_kind = CASE type WHEN 'B' THEN 'B' ELSE 'M'"
                             " END WHERE bid_kind = '' AND bid IS NOT NULL AND bid != ''")

    def ids_without_bid(self) -> list[int]:
        return [r["id"] for r in self._db.execute(
            "SELECT id FROM messages WHERE bid IS NULL OR bid = '' ORDER BY id")]

    def get_by_bid(self, bid: str) -> Message | None:
        row = self._db.execute("SELECT * FROM messages WHERE bid = ?", (bid,)).fetchone()
        return Message(**dict(row)) if row else None

    def bid_known(self, bid: str) -> bool:
        return (self._db.execute("SELECT 1 FROM bids WHERE bid = ?", (bid,)).fetchone()
                is not None or self.get_by_bid(bid) is not None)

    def bid_add(self, bid: str, origin: str) -> None:
        with self._db:
            self._db.execute("INSERT OR IGNORE INTO bids (bid, first_seen, origin)"
                             " VALUES (?, ?, ?)", (bid, utc_now(), origin))

    def purge_bids(self, days: int) -> int:
        """Forget BIDs older than `days` (BIDs of stored messages stay known anyway)."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._db:
            return self._db.execute("DELETE FROM bids WHERE first_seen < ?", (cutoff,)).rowcount

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

    _EDITABLE = {"to_call", "from_call", "type", "status", "subject", "at_addr"}

    def update_field(self, msg_id: int, field: str, value: str) -> None:
        if field not in self._EDITABLE:  # column names cannot be parameters
            raise ValueError(f"field not editable: {field}")
        with self._db:
            self._db.execute(f"UPDATE messages SET {field} = ? WHERE id = ?", (value, msg_id))

    def delete_bulletins_older_than(self, days: int) -> list[int]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = self._db.execute(
            "SELECT id FROM messages WHERE type = 'B' AND created < ?"
            " AND (replace_key IS NULL OR replace_key NOT LIKE 'fixed:%')", (cutoff,)
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

    def chat_stats(self, board: str, since_iso: str) -> tuple[int, str | None]:
        """Number of stored lines since `since_iso` and the time of the newest."""
        row = self._db.execute(
            "SELECT COUNT(*) AS n, MAX(created) AS last FROM chat_lines"
            " WHERE board = ? AND created >= ?", (board, since_iso)).fetchone()
        return row["n"], row["last"]

    def chat_page(self, board: str, since_iso: str, limit: int, after_iso: str | None = None,
                  before_iso: str | None = None) -> tuple[list[ChatLine], int]:
        """The newest `limit` lines since `since_iso` (and from `after_iso`, up to
        `before_iso` - both inclusive: lines of the same second are not lost, the
        client drops what it has already), oldest first, and how many stored lines
        are older than them."""
        where, args = "board = ? AND created >= ?", [board, since_iso]
        if after_iso:
            where += " AND created >= ?"
            args.append(after_iso)
        if before_iso:
            where += " AND created <= ?"
            args.append(before_iso)
        rows = self._db.execute(
            f"SELECT id, board, call, text, created FROM chat_lines WHERE {where}"
            " ORDER BY id DESC LIMIT ?", (*args, limit)).fetchall()
        if rows:
            older = self._db.execute(
                "SELECT COUNT(*) FROM chat_lines WHERE board = ? AND created >= ? AND id < ?",
                (board, since_iso, rows[-1]["id"])).fetchone()[0]
        else:
            older = self._db.execute(
                "SELECT COUNT(*) FROM chat_lines WHERE board = ? AND created >= ?"
                + (" AND created <= ?" if before_iso else ""),
                (board, since_iso, *([before_iso] if before_iso else []))).fetchone()[0]
            if after_iso:        # nothing new since then: everything stored is "older"
                older = self.chat_stats(board, since_iso)[0]
        lines = [ChatLine(board=r["board"], call=r["call"], text=r["text"], created=r["created"])
                 for r in reversed(rows)]
        return lines, older

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
