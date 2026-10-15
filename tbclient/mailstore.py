"""Local mailbox of the client (C3): what was fetched from the TinyBox,
the outbox and what still has to be told to the TinyBox (deleted, read).

SQLite file mailbox.db in the client's data_dir. Message numbers are those
of the TinyBox (they are never reused there).
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,          -- number in the TinyBox
    type TEXT NOT NULL,              -- P | B
    status TEXT NOT NULL,            -- N | Y in the TinyBox
    fwd TEXT NOT NULL DEFAULT '',
    size INTEGER NOT NULL DEFAULT 0,
    from_call TEXT NOT NULL,
    to_call TEXT NOT NULL,
    at_addr TEXT NOT NULL DEFAULT '',
    bid TEXT NOT NULL DEFAULT '',
    created INTEGER NOT NULL,        -- unix time
    subject TEXT NOT NULL,
    body TEXT,                       -- NULL = not fetched yet
    seen INTEGER NOT NULL DEFAULT 0, -- read here in the client
    fetched INTEGER                  -- unix time the text came in
);
CREATE TABLE IF NOT EXISTS outbox (
    oid INTEGER PRIMARY KEY AUTOINCREMENT,
    mid TEXT NOT NULL,               -- unique id, protects against double sending
    type TEXT NOT NULL,
    to_call TEXT NOT NULL,           -- may contain @address
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    created INTEGER NOT NULL,
    error TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS todo (    -- for the next sync
    kind TEXT NOT NULL,              -- kill | read
    id INTEGER NOT NULL,
    PRIMARY KEY (kind, id)
);
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

COLS = ("id", "type", "status", "fwd", "size", "from_call", "to_call", "at_addr", "bid",
        "created", "subject")


def base(call: str) -> str:
    return call.upper().split("-")[0].split("/")[0]


class MailStore:
    def __init__(self, path: Path, mycall: str) -> None:
        self.path = path
        self._db: sqlite3.Connection | None = None
        self.me = base(mycall)
        self.version = 0                  # changes -> the GUI reloads the list

    @property
    def db(self) -> sqlite3.Connection:
        """Opened on first use: a client that never uses the mailbox has no file."""
        if self._db is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(str(self.path))
            self._db.row_factory = sqlite3.Row
            self._db.executescript(SCHEMA)
        return self._db

    @property
    def unused(self) -> bool:
        return self._db is None and not self.path.exists()

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None

    def _changed(self) -> None:
        self.version += 1
        self.db.commit()

    # --- key/value ------------------------------------------------------

    def get(self, key: str, default=None):
        row = self.db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def put(self, key: str, value) -> None:
        self.db.execute("INSERT OR REPLACE INTO kv VALUES (?, ?)", (key, json.dumps(value)))
        self._changed()

    # --- messages from the TinyBox -----------------------------------------

    def upsert_header(self, h: dict, content: bool = False) -> bool:
        """Header from //M. Returns True if the text still has to be fetched.
        Mail deleted here (waiting for the TinyBox) is not taken back.
        content=True (delta sync): the TinyBox says the content is new - a text
        already here is dropped if size or time differ (bulletin replaced); own
        mail is kept (sent from here, the TinyBox has its own time and size)."""
        if self.db.execute("SELECT 1 FROM todo WHERE kind='kill' AND id=?",
                           (h["id"],)).fetchone():
            return False
        row = self.db.execute("SELECT body, seen, size, created FROM messages WHERE id=?",
                              (h["id"],)).fetchone()
        seen = 1 if h["status"] == "Y" and self._is_mine(h) else 0
        if row is None:
            self.db.execute(f"INSERT INTO messages ({','.join(COLS)}, seen) "
                            f"VALUES ({','.join('?' * len(COLS))}, ?)",
                            [h[c] for c in COLS] + [seen])
            self._changed()
            return True
        # read on the terminal -> read here too; read here -> stays read
        self.db.execute("UPDATE messages SET status=?, fwd=?, size=?, subject=?, to_call=?, "
                        "at_addr=?, created=?, seen=MAX(seen, ?) WHERE id=?",
                        (h["status"], h["fwd"], h["size"], h["subject"], h["to_call"],
                         h["at_addr"], h["created"], seen, h["id"]))
        if (content and row["body"] is not None and base(h["from_call"]) != self.me
                and (row["size"] != h["size"] or row["created"] != h["created"])):
            self.db.execute("UPDATE messages SET body=NULL, seen=0 WHERE id=?", (h["id"],))
            self._changed()
            return True
        self._changed()
        return row["body"] is None

    def set_status(self, msg_id: int, status: str, fwd: str) -> None:
        """//S of the delta sync: only status and forward flag changed."""
        m = self.message(msg_id)
        if m is None:
            return
        seen = 1 if status == "Y" and self._is_mine(m) else 0
        self.db.execute("UPDATE messages SET status=?, fwd=?, seen=MAX(seen, ?) WHERE id=?",
                        (status, fwd, seen, msg_id))
        self._changed()

    def remove_many(self, ids: list[int]) -> None:
        """//D of the delta sync: gone in the TinyBox, gone here."""
        if ids:
            self.db.executemany("DELETE FROM messages WHERE id=?", [(i,) for i in ids])
            self.db.executemany("DELETE FROM todo WHERE id=?", [(i,) for i in ids])
            self._changed()

    def _is_mine(self, h) -> bool:
        return h["type"] == "P" and base(h["to_call"]) == self.me

    def set_body(self, msg_id: int, body: str) -> None:
        self.db.execute("UPDATE messages SET body=?, fetched=? WHERE id=?",
                        (body, int(time.time()), msg_id))
        self._changed()

    def remove(self, msg_id: int) -> None:
        self.db.execute("DELETE FROM messages WHERE id=?", (msg_id,))
        self.db.execute("DELETE FROM todo WHERE id=?", (msg_id,))
        self._changed()

    def missing_bodies(self, kind: str | None = None) -> list[int]:
        """Texts still to fetch, oldest first (kind P or B, None = both)."""
        return [r[0] for r in self.db.execute(
            "SELECT id FROM messages WHERE body IS NULL AND id NOT IN "
            "(SELECT id FROM todo WHERE kind='kill') AND type LIKE ? ORDER BY type DESC, id",
            (kind or "%",))]

    def max_bulletin(self, rubric: str) -> int:
        row = self.db.execute("SELECT MAX(id) FROM messages WHERE type='B' AND to_call=?",
                              (rubric,)).fetchone()
        return max(row[0] or 0, self.get(f"after.{rubric}", 0))

    def add_sent(self, msg_id: int, item: dict, from_call: str, to_call: str,
                 at_addr: str) -> None:
        """Our own message, accepted by the TinyBox: no need to fetch it again."""
        self.db.execute(
            f"INSERT OR REPLACE INTO messages ({','.join(COLS)}, body, seen, fetched) "
            f"VALUES ({','.join('?' * len(COLS))}, ?, 1, ?)",
            (msg_id, item["type"], "N", "", len(item["body"].encode()), from_call,
             to_call, at_addr, "", int(time.time()), item["subject"], item["body"],
             int(time.time())))
        self.db.execute("DELETE FROM outbox WHERE oid=?", (item["oid"],))
        self._changed()

    # --- the GUI ------------------------------------------------------------

    def message(self, msg_id: int) -> dict | None:
        row = self.db.execute("SELECT * FROM messages WHERE id=?", (msg_id,)).fetchone()
        return dict(row) if row else None

    def open(self, msg_id: int) -> dict | None:
        """Show a message: read here; personal mail to me is reported at the next sync."""
        m = self.message(msg_id)
        if m is None:
            return None
        if not m["seen"] and m["body"] is not None:
            self.db.execute("UPDATE messages SET seen=1 WHERE id=?", (msg_id,))
            if self._is_mine(m) and m["status"] == "N":
                self.db.execute("INSERT OR IGNORE INTO todo VALUES ('read', ?)", (msg_id,))
            self._changed()
            m["seen"] = 1
        return m

    def delete(self, msg_id: int) -> bool:
        """Personal mail: gone here, deleted in the TinyBox at the next sync.
        Bulletins: only here (they belong to everyone)."""
        m = self.message(msg_id)
        if m is None:
            return False
        if m["type"] == "P":
            self.db.execute("INSERT OR IGNORE INTO todo VALUES ('kill', ?)", (msg_id,))
            self.db.execute("DELETE FROM todo WHERE kind='read' AND id=?", (msg_id,))
        else:
            self.put(f"after.{m['to_call']}", max(self.get(f"after.{m['to_call']}", 0), msg_id))
            self.db.execute("DELETE FROM messages WHERE id=?", (msg_id,))
        self._changed()
        return True

    def todo(self, kind: str) -> list[int]:
        return [r[0] for r in self.db.execute("SELECT id FROM todo WHERE kind=? ORDER BY id",
                                              (kind,))]

    def todo_done(self, kind: str, ids: list[int]) -> None:
        self.db.executemany("DELETE FROM todo WHERE kind=? AND id=?", [(kind, i) for i in ids])
        if kind == "kill":
            self.db.executemany("DELETE FROM messages WHERE id=?", [(i,) for i in ids])
        self._changed()

    def folder(self, name: str) -> list[dict]:
        hidden = "id NOT IN (SELECT id FROM todo WHERE kind='kill')"
        cols = "id, type, status, fwd, size, from_call, to_call, at_addr, bid, created, " \
               "subject, seen, body IS NOT NULL AS has_body"
        if name == "outbox":
            return [dict(r) for r in self.db.execute("SELECT * FROM outbox ORDER BY oid")]
        if name.startswith("s:"):
            return self.search(name[2:])
        rows = self.db.execute(f"SELECT {cols} FROM messages WHERE {hidden} ORDER BY id DESC")
        out = []
        for r in rows:
            r = dict(r)
            mine_to, mine_from = base(r["to_call"]) == self.me, base(r["from_call"]) == self.me
            if name == "inbox" and r["type"] == "P" and mine_to:
                out.append(r)
            elif name == "sent" and mine_from and (r["type"] == "B" or not mine_to):
                out.append(r)
            elif name.startswith("b:") and r["type"] == "B" and r["to_call"] == name[2:]:
                out.append(r)
        return out

    def search(self, text: str) -> list[dict]:
        """CR49: personal mail and bulletins here whose subject, text, sender,
        addressee or @address contain text (case does not matter), newest
        first. Texts not fetched yet (CR40) can only be found by their header;
        hit = "text" or "header" says where it was found."""
        q = text.strip().casefold()
        if len(q) < 2:
            return []
        hidden = "id NOT IN (SELECT id FROM todo WHERE kind='kill')"
        cols = "id, type, status, fwd, size, from_call, to_call, at_addr, bid, created, " \
               "subject, seen, body IS NOT NULL AS has_body, body"
        out = []
        for r in self.db.execute(f"SELECT {cols} FROM messages WHERE {hidden} ORDER BY id DESC"):
            r = dict(r)
            body = r.pop("body") or ""
            head = " ".join((r["subject"], r["from_call"], r["to_call"], r["at_addr"])).casefold()
            if q in head:
                r["hit"] = "header"
            elif q in body.casefold():
                r["hit"] = "text"
                i = body.casefold().index(q)
                snip = body[max(0, i - 30):i + len(q) + 50].replace("\n", " ")
                r["snippet"] = ("…" if i > 30 else "") + snip
            else:
                continue
            out.append(r)
        return out

    def summary(self) -> dict:
        if self.unused:
            return {"version": 0, "inbox": 0, "unread": 0, "outbox": 0, "sent": 0,
                    "rubrics": [], "writable": [], "todo": 0, "missing": 0, "missing_b": 0,
                    "last_mail": 0, "last_bulletins": 0}
        q = self.db.execute
        hidden = "id NOT IN (SELECT id FROM todo WHERE kind='kill')"
        inbox = [dict(r) for r in q(f"SELECT to_call, seen FROM messages WHERE type='P' "
                                    f"AND {hidden}")]
        mine = [r for r in inbox if base(r["to_call"]) == self.me]
        local: dict[str, list[int]] = {}
        for r in q("SELECT to_call, seen FROM messages WHERE type='B'"):
            c = local.setdefault(r[0], [0, 0])
            c[0] += 1
            c[1] += 0 if r[1] else 1
        server = {r["name"]: r for r in self.get("rubrics", [])}
        subs = set(self.get("subscribed", []))
        rubrics = []
        for name in sorted(set(server) | set(local) | subs):
            n, unread = local.get(name, [0, 0])
            rubrics.append({"name": name, "local": n, "unread": unread, "sub": name in subs,
                            "server": server.get(name, {}).get("count", 0),
                            "desc": server.get(name, {}).get("desc", "")})
        writable = [{"name": w, "desc": server.get(w, {}).get("desc", "")}
                    for w in self.get("writable", [])]
        return {
            "version": self.version,
            "inbox": len(mine), "unread": sum(1 for r in mine if not r["seen"]),
            "outbox": q("SELECT COUNT(*) FROM outbox").fetchone()[0],
            "sent": len(self.folder("sent")),
            "rubrics": rubrics,
            "writable": writable,       # CR19: rubrics for the composer, [] = free field
            "todo": len(self.todo("kill")) + len(self.todo("read")),
            "missing": len(self.missing_bodies("P")),
            "missing_b": len(self.missing_bodies("B")),
            "last_mail": self.get("last_sync.mail", 0) or self.get("last_sync", 0),
            "last_bulletins": self.get("last_sync.bulletins", 0) or self.get("last_sync", 0),
        }

    # --- outbox --------------------------------------------------------------

    def save_out(self, oid: int | None, type: str, to: str, subject: str, body: str) -> int:
        if oid:
            cur = self.db.execute("UPDATE outbox SET type=?, to_call=?, subject=?, body=?, "
                                  "error='' WHERE oid=?", (type, to, subject, body, oid))
            if cur.rowcount:
                self._changed()
                return oid
        cur = self.db.execute("INSERT INTO outbox (mid, type, to_call, subject, body, created) "
                              "VALUES (?, ?, ?, ?, ?, ?)",
                              (uuid.uuid4().hex, type, to, subject, body, int(time.time())))
        self._changed()
        return cur.lastrowid

    def discard_out(self, oid: int) -> bool:
        ok = self.db.execute("DELETE FROM outbox WHERE oid=?", (oid,)).rowcount > 0
        self._changed()
        return ok

    def out_error(self, oid: int, error: str) -> None:
        self.db.execute("UPDATE outbox SET error=? WHERE oid=?", (error, oid))
        self._changed()

    def outbox(self) -> list[dict]:
        return self.folder("outbox")

    def subscribe(self, rubric: str, on: bool) -> None:
        subs = set(self.get("subscribed", []))
        (subs.add if on else subs.discard)(rubric)
        self.put("subscribed", sorted(subs))
