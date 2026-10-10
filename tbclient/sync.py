"""Mailbox sync with the TinyBox (C3, protocol see tinybox/clientsync.py).

One sync, in this order:
  1. send the outbox            //SEND ... -> //SENT <id>
  2. delete own mail            //KILL     -> //K ... //KEND
  3. report what was read here  //READ     -> //REND
  4. personal mail headers      //MLIST    -> //M ... //MEND   (always all)
  5. rubrics                    //RUBRICS  -> //RU ... //RUEND
  6. subscribed bulletins       //BLIST R=<last> ... -> //M ... //MEND
  7. missing texts              //GET in small batches (compressed on radio)

Everything is stored at once. If the link breaks, the next sync goes on
where this one stopped: texts already here are not fetched again.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from .mailstore import MailStore

if TYPE_CHECKING:
    from .core import ClientCore

log = logging.getLogger(__name__)

GET_BATCH = 5
IDLE_SEC = 120            # no answer for this long: the sync gives up
CONNECT_SEC = 90          # connect + handshake when the sync connects by itself
MAX_LINE_OUT = 1000       # longer text lines are wrapped (TinyBox line limit 1024)
CHUNK = 50                # ids per //KILL or //READ
PREFIXES = ("//M ", "//MEND", "//RU ", "//RUEND", "//MSG ", "//ZMSG ", "//NOMSG ", "//GEND",
            "//SENT ", "//K ", "//KEND", "//REND", "//ERR")


class SyncError(Exception):
    pass


def parse_header(rest: str) -> dict | None:
    """'<id> <P|B> <N|Y> <fwd> <size> <from> <to> <at> <bid> <unix> <subject>'"""
    p = rest.split(" ", 10)
    if len(p) < 10 or not p[0].isdigit() or p[1] not in ("P", "B"):
        return None
    try:
        return {"id": int(p[0]), "type": p[1], "status": p[2], "fwd": "" if p[3] == "-" else p[3],
                "size": int(p[4]), "from_call": p[5], "to_call": p[6],
                "at_addr": "" if p[7] == "-" else p[7], "bid": "" if p[8] == "-" else p[8],
                "created": int(p[9]), "subject": p[10] if len(p) > 10 else ""}
    except ValueError:
        return None


def decompress(data: bytes) -> str:
    from tinybox.fwd import lzhuf               # the same codec as FBB forwarding (B1)
    raw = lzhuf.decompress_b1(data, max_size=1_000_000)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


class Syncer:
    def __init__(self, core: ClientCore, store: MailStore) -> None:
        self.core = core
        self.store = store
        self.task: asyncio.Task | None = None
        self.own_connect = False          # the sync opened the connection itself
        self.queue: asyncio.Queue | None = None
        self._body: tuple[int, int, list[str]] | None = None    # (id, lines left, lines)
        self.status = {"running": False, "step": "", "done": 0, "total": 0, "error": "",
                       "bytes": 0, "saved": 0}

    @property
    def running(self) -> bool:
        return self.task is not None and not self.task.done()

    # --- lines from the link (called by the core first) ---------------------

    def take(self, line: str) -> bool:
        """True if the line belongs to the sync."""
        if self.queue is None:
            return False
        if self._body is None:
            line = line.rstrip()
        if self._body is not None:                 # text lines of //MSG, also empty ones
            msg_id, left, lines = self._body
            lines.append(line)
            if left <= 1:
                self._body = None
                self.queue.put_nowait(("text", msg_id, "\n".join(lines)))
            else:
                self._body = (msg_id, left - 1, lines)
            return True
        if not line.startswith(PREFIXES):
            return False
        if line.startswith("//MSG "):
            p = line.split()
            if len(p) == 3 and p[1].isdigit() and p[2].isdigit():
                if int(p[2]) == 0:
                    self.queue.put_nowait(("text", int(p[1]), ""))
                else:
                    self._body = (int(p[1]), int(p[2]), [])
            return True
        if line.startswith("//ZMSG "):
            p = line.split()
            if len(p) == 3 and p[1].isdigit() and p[2].isdigit():
                msg_id, n = int(p[1]), int(p[2])
                q = self.queue
                self.core.link.splitter.expect(n, lambda data: q.put_nowait(("z", msg_id, data)))
            return True
        self.queue.put_nowait(("line", line))
        return True

    # --- control -----------------------------------------------------------------

    def start(self) -> bool:
        if self.running:
            return False
        self.task = asyncio.ensure_future(self._run())
        return True

    def cancel(self) -> None:
        if self.running:
            self.task.cancel()

    def _set(self, **kw) -> None:
        self.status.update(kw)
        self.core._touch()

    async def _run(self) -> None:
        self.queue = asyncio.Queue()
        self._body = None
        self._set(running=True, step="connecting", done=0, total=0, error="", bytes=0, saved=0)
        own_connect = self.own_connect = False
        try:
            if self.core.state != "online":
                own_connect = self.own_connect = True
                await self.core.connect()
            await self._wait_ready()
            await self._sync()
            self.store.put("last_sync", int(time.time()))
            self._set(step="done")
        except asyncio.CancelledError:
            self._set(step="cancelled", error="cancelled")
        except SyncError as exc:
            log.warning("sync: %s", exc)
            self._set(step="failed", error=str(exc))
        except Exception as exc:                  # a bug must not kill the client
            log.exception("sync failed")
            self._set(step="failed", error=f"internal error: {exc}")
        finally:
            self.queue = None
            self._body = None
            self.own_connect = False
            self.status["running"] = False
            self.core.after_sync()
            if own_connect and self.core.state == "online" and not self.core.board:
                self.core.disconnect()             # offline again, as before
            self.core._touch()

    async def _wait_ready(self) -> None:
        start = time.monotonic()
        while time.monotonic() - start < CONNECT_SEC:
            if self.core.state == "offline" and time.monotonic() - start > 1:
                raise SyncError("not connected" + (f": {self.core.reason}"
                                                   if self.core.reason else ""))
            if self.core.state == "online" and self.core.caps:
                if "SYNC" not in self.core.caps:
                    raise SyncError("the TinyBox does not offer the mailbox sync (update it)")
                return
            await asyncio.sleep(0.2)
        raise SyncError("no connection to the TinyBox")

    # --- requests -------------------------------------------------------------------

    async def _next(self):
        if self.core.state != "online":
            raise SyncError("connection lost")
        try:
            item = await asyncio.wait_for(self.queue.get(), IDLE_SEC)
        except asyncio.TimeoutError:
            raise SyncError("no answer from the TinyBox") from None
        if item[0] == "lost":
            raise SyncError("connection lost")
        return item

    def link_lost(self) -> None:
        if self.queue is not None:
            self._body = None
            self.queue.put_nowait(("lost",))

    async def _lines_until(self, end: str) -> list[str]:
        out = []
        while True:
            item = await self._next()
            if item[0] != "line":
                continue
            line = item[1]
            if line.startswith("//ERR"):
                raise SyncError(line[2:])
            if line.startswith(end):
                return out
            out.append(line)

    def _send(self, *lines: str) -> None:
        self.core._send(lines[0])
        for line in lines[1:]:                   # message text: not into the monitor
            self.core.link.send_line(line)

    async def _sync(self) -> None:
        st = self.store
        # 1. outbox
        items = st.outbox()
        for i, item in enumerate(items):
            self._set(step=f"sending {i + 1}/{len(items)}")
            await self._send_one(item)
        # 2. + 3. deleted / read here
        kills = st.todo("kill")
        for i in range(0, len(kills), CHUNK):
            self._set(step="deleting")
            self._send("//KILL " + " ".join(map(str, kills[i:i + CHUNK])))
            done = []
            for line in await self._lines_until("//KEND"):
                p = line.split()
                if len(p) == 3 and p[0] == "//K" and p[1].isdigit():
                    done.append(int(p[1]))       # ok, or not possible: either way gone here
            st.todo_done("kill", done)
        reads = st.todo("read")
        for i in range(0, len(reads), CHUNK):
            self._send("//READ " + " ".join(map(str, reads[i:i + CHUNK])))
            await self._lines_until("//REND")
            st.todo_done("read", reads[i:i + CHUNK])
        # 4. personal mail
        self._set(step="mail list")
        self._send("//MLIST")
        for line in await self._lines_until("//MEND"):
            if line.startswith("//M ") and (h := parse_header(line[4:])):
                st.upsert_header(h)
        # 5. + 6. bulletins
        self._set(step="rubrics")
        self._send("//RUBRICS")
        rubrics = []
        for line in await self._lines_until("//RUEND"):
            p = line.split()
            if len(p) == 4 and p[0] == "//RU" and p[2].isdigit():
                rubrics.append({"name": p[1], "count": int(p[2]), "max": int(p[3])})
        st.put("rubrics", rubrics)
        subs = [r for r in st.get("subscribed", []) if any(x["name"] == r for x in rubrics)]
        want = [f"{r}={st.max_bulletin(r)}" for r in subs
                if next(x["max"] for x in rubrics if x["name"] == r) > st.max_bulletin(r)]
        if want:
            self._set(step="bulletin list")
            self._send("//BLIST " + " ".join(want))
            for line in await self._lines_until("//MEND"):
                if line.startswith("//M ") and (h := parse_header(line[4:])):
                    st.upsert_header(h)
        # 7. texts
        missing = st.missing_bodies()
        self._set(total=len(missing), done=0)
        for i in range(0, len(missing), GET_BATCH):
            batch = missing[i:i + GET_BATCH]
            self._set(step=f"texts {i + 1}-{i + len(batch)} of {len(missing)}")
            self._send("//GET " + " ".join(map(str, batch)))
            await self._get(batch)

    async def _send_one(self, item: dict) -> None:
        to = item["to_call"].replace(" ", "")
        lines = []
        for line in item["body"].replace("\r", "").replace("\x1a", "").split("\n"):
            while len(line) > MAX_LINE_OUT:
                lines.append(line[:MAX_LINE_OUT])
                line = line[MAX_LINE_OUT:]
            lines.append(line)
        if lines == [""]:
            lines = []
        subject = " ".join(item["subject"].split()) or "(no subject)"
        self._send(f"//SEND {item['type']} {to} {len(lines)} mid={item['mid']}", subject, *lines)
        while True:
            entry = await self._next()
            if entry[0] != "line":
                continue
            line = entry[1]
            if line.startswith("//SENT "):
                msg_id = int(line.split()[1])
                call, _, at = to.partition("@")
                self.store.add_sent(msg_id, item, self.core.cfg.mycall, call.upper(), at.upper())
                return
            if line.startswith("//ERR"):
                self.store.out_error(item["oid"], line[2:].replace("ERR send ", ""))
                return                              # stays in the outbox, the sync goes on

    async def _get(self, batch: list[int]) -> None:
        while True:
            item = await self._next()
            kind = item[0]
            if kind == "line":
                line = item[1]
                if line.startswith("//GEND"):
                    return
                if line.startswith("//ERR"):
                    raise SyncError(line[2:])
                if line.startswith("//NOMSG "):
                    p = line.split()
                    if p[1].isdigit():
                        self.store.remove(int(p[1]))       # gone in the TinyBox
                    self._set(done=self.status["done"] + 1)
                continue
            msg_id, data = item[1], item[2]
            if kind == "z":
                try:
                    text = decompress(data)
                except ValueError as exc:
                    log.warning("msg %d: bad compressed data (%s), fetched later", msg_id, exc)
                    self._set(done=self.status["done"] + 1)
                    continue
                self.status["bytes"] += len(data)
                self.status["saved"] += len(text.encode()) - len(data)
            else:
                text = data
                self.status["bytes"] += len(text.encode())
            self.store.set_body(msg_id, text)
            self._set(done=self.status["done"] + 1)
