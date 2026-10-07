"""The system under test, seen from fwdsim.

StubTarget    a fwdsim mailbox playing TinyBox (OE3XTC) - tests fwdsim itself
TinyboxTarget the real TinyBox: test mail is typed in over its telnet port,
              results are read from tinybox.db (read-only, optional)
"""

from __future__ import annotations

import asyncio
import re
import sqlite3
from pathlib import Path
from typing import Any

from .bbs import SimBBS
from .config import Config
from .link import TcpLink
from .session import ForwardSession, SessionResult

Found = dict[str, Any]   # bid, type, status, subject, body, rlines, origin


class StubTarget:
    kind = "stub"

    def __init__(self, cfg: Config, bbs: SimBBS, timeout: float) -> None:
        self.cfg = cfg
        self.bbs = bbs
        self.call = bbs.call
        self.haddr = bbs.haddr
        self.timeout = timeout
        self.server: asyncio.AbstractServer | None = None
        self.port = 0
        self.slave_results: asyncio.Queue[SessionResult] = asyncio.Queue()

    async def start(self) -> None:
        async def handle(reader, writer):
            link = TcpLink(reader, writer, f"{self.call}<tcp")
            s = ForwardSession(self.bbs, link, self.cfg.hop.call, master=False,
                               timeout=self.timeout)
            await self.slave_results.put(await s.run())

        self.server = await asyncio.start_server(handle, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self.server:
            self.server.close()

    async def submit(self, type: str, to_call: str, at_addr: str, subject: str,
                     body: str) -> str:
        return self.bbs.create(type, to_call, at_addr, subject, body).bid

    def find(self, *, bid: str | None = None, subject: str | None = None) -> list[Found] | None:
        return [{"bid": m.bid, "type": m.type, "status": m.status, "subject": m.subject,
                 "body": m.body, "rlines": m.rlines,
                 "origin": "forward" if m.received_from else "local"}
                for m in self.bbs.find(bid=bid, subject=subject)]


class TelnetClient:
    """Types test mail into TinyBox like a user would."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.reader, self.writer = reader, writer
        self.buf = ""

    async def expect(self, text: str, timeout: float = 15) -> str:
        async def _wait() -> str:
            while text not in self.buf:
                data = await self.reader.read(1024)
                if not data:
                    raise ConnectionError(f"telnet closed while waiting for {text!r}")
                data = re.sub(rb"\xff[\xfb-\xfe].|\xff\xfa.*?\xff\xf0", b"", data, flags=re.S)
                self.buf += data.decode("utf-8", "replace")
            before, _, self.buf = self.buf.partition(text)
            return before
        return await asyncio.wait_for(_wait(), timeout)

    def send(self, line: str) -> None:
        self.writer.write((line + "\r\n").encode("utf-8"))


class TinyboxTarget:
    kind = "tinybox"

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.call = cfg.tinybox.call
        self.haddr = cfg.tinybox.haddress
        db = cfg.tinybox.db
        self.db_path = Path(db) if db else None

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def submit(self, type: str, to_call: str, at_addr: str, subject: str,
                     body: str) -> str:
        """Write a message on TinyBox through its telnet port. Returns the subject,
        which identifies the message (the BID is chosen by TinyBox)."""
        t = self.cfg.tinybox
        reader, writer = await asyncio.open_connection(t.telnet_host, t.telnet_port)
        c = TelnetClient(reader, writer)
        try:
            await c.expect("Callsign:")
            c.send(t.telnet_user)
            await c.expect("> ")
            cmd = "SP" if type.upper() == "P" else "SB"
            c.send(f"{cmd} {to_call} @ {at_addr}")
            await c.expect("Subject:")
            c.send(subject)
            await c.expect("Enter message")
            for line in body.split("\n"):
                c.send(line)
            c.send("/EX")
            text = await c.expect("> ")
            if "saved" not in text:
                raise RuntimeError(f"TinyBox did not save the message: {text.strip()!r}")
            c.send("B")
        finally:
            writer.close()
        return subject

    def find(self, *, bid: str | None = None, subject: str | None = None) -> list[Found] | None:
        """Rows from tinybox.db (schema 5, see the concept). None = no database configured."""
        if self.db_path is None:
            return None
        uri = f"file:{self.db_path.as_posix()}?mode=ro"
        db = sqlite3.connect(uri, uri=True)
        db.row_factory = sqlite3.Row
        try:
            cols = {r["name"] for r in db.execute("PRAGMA table_info(messages)")}
            where, args = [], []
            if bid and "bid" in cols:
                where.append("bid = ?")
                args.append(bid.upper())
            if subject:
                where.append("subject = ?")
                args.append(subject)
            sql = "SELECT * FROM messages" + (" WHERE " + " AND ".join(where) if where else "")
            out = []
            for r in db.execute(sql, args):
                d = dict(r)
                out.append({"bid": d.get("bid", ""), "type": d.get("type"),
                            "status": d.get("status"), "subject": d.get("subject"),
                            "body": d.get("body", ""),
                            "rlines": [x for x in (d.get("rlines") or "").split("\n") if x],
                            "origin": d.get("origin", ""), "at": d.get("at_addr", ""),
                            "fwd": d.get("fwd", ""), "note": d.get("note", "")})
            return out
        finally:
            db.close()
