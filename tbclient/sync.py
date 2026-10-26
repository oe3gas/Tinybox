"""Mailbox sync with the TinyBox (C3, protocol see tinybox/clientsync.py).

Two kinds of sync, each started on its own:

send       only the outbox (CR47: a mail put into the outbox goes out at once)
mail       1. send the outbox            //SEND ... -> //SENT <id>
           2. delete own mail            //KILL     -> //K ... //KEND
           3. report what was read here  //READ     -> //REND
           4. personal mail headers      //MLIST after= max= (page by page)
           5. missing texts of personal mail
bulletins  1. rubrics                    //RUBRICS
           2. new bulletins of the subscribed rubrics   //BLIST ... max= (pages)
           3. missing texts of bulletins

Easy on the channel (radio only): every request asks for about chunk_bytes
([sync] in tbclient.conf); between two requests the client pauses pause_sec
and waits further while other stations are heard, so they get the frequency.
A long text comes in pieces (//PART). Texts are fetched oldest first.

Everything is stored at once. If the link breaks, the next sync goes on
where this one stopped: texts already here are not fetched again, and the
pieces of a long text that already came are kept while the client runs.

Delta sync (cap SYNC2 of the TinyBox, CR26): steps 2-5 of the mail sync are one
request //SYNC seq=<n> k=.. r=.. max= want= - the TinyBox answers with what
changed since the last sync (new headers //M, status //S, deleted //D) and the
texts of new short mail right away. Bulletins alike with //BSYNC: the rubric
list comes only when it changed (hash h=). Without SYNC2 the old steps run.

Headers first, texts on demand (CR40): a sync fetches headers only. Personal
mail up to [sync] short_bytes comes with its text (cap SHORT: short= in //SYNC,
else one //GET); everything else is fetched when the user opens it (fetch(),
never connects by itself). After every login the client syncs by itself
(scope "login" = mail + bulletins). Abort is orderly: the exchange on the air
is finished and stored, then no new request goes out; the next sync goes on
from there. At the start and at an abort the user sees what is still pending
and about how long it takes.
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

HEADER_BYTES = 90        # about one //M line, to size the header pages
BUSY_QUIET_SEC = 3       # the channel counts as free after this much silence
BUSY_MAX_SEC = 30        # never wait longer than this for a free channel
IDLE_SEC = 120            # no answer for this long: the sync gives up ...
SEND_WAIT_MAX_SEC = 1800  # ... unless own frames are still on their way (at most this long)
ABORT_GRACE_SEC = 30      # orderly abort: wait this long for the answer on the air (CR40)
SCOPES = ("mail", "bulletins", "login", "fetch", "send")
END_LINES = ("//SYNCEND", "//BSYNCEND", "//GEND", "//MEND", "//RUEND", "//KEND", "//REND",
             "//SENT ", "//NOMSG ", "//ERR", "//HAVE ")
CONNECT_SEC = 90          # connect + handshake when the sync connects by itself
MAX_LINE_OUT = 1000       # longer text lines are wrapped (TinyBox line limit 1024)
CHUNK = 50                # ids per //KILL or //READ
PREFIXES = ("//M ", "//MEND", "//RU ", "//RUEND", "//MSG ", "//ZMSG ", "//NOMSG ", "//GEND",
            "//P ",
            "//SENT ", "//K ", "//KEND", "//REND", "//ERR", "//HAVE ",
            "//S ", "//D ", "//RL ", "//RN ", "//SYNCEND", "//BSYNCEND", "//ZSYNC ")


class SyncError(Exception):
    pass


class Aborted(Exception):
    """Orderly abort (CR40): raised before the next request goes out."""


def human_secs(sec: float) -> str:
    """'approx. 1 min 40 s' - rounded, no false precision."""
    sec = int(sec)
    if sec < 10:
        return "a few seconds"
    if sec < 60:
        return f"approx. {round(sec / 5) * 5} s"
    if sec < 600:
        m, s = divmod(round(sec / 10) * 10, 60)
        return f"approx. {m} min" + (f" {s} s" if s else "")
    return f"approx. {round(sec / 60)} min"


def human_bytes(n: int) -> str:
    return f"{n} bytes" if n < 1000 else f"{n / 1000:.1f} kB"


def _no_loop(asked: set[str], req: str) -> None:
    """A delta sync asks on until the TinyBox reports more=0. Every round has to
    move seq= or after= on, so the very same request a second time means it never
    will: the client stops instead of staying on the air for ever."""
    if req in asked:
        raise SyncError("the TinyBox sends the same page again (sync stopped)")
    asked.add(req)


def parse_rubrics(lines: list[str]) -> tuple[list[dict], list[str]]:
    """Answer to //RUBRICS -> (rubrics with name/count/max/desc, rubrics users may
    write to in the sysop's order; empty = the TinyBox has no list, free field)."""
    rubrics, writable, desc = [], [], {}
    for line in lines:
        p = line.split()
        if len(p) == 4 and p[0] == "//RU" and p[2].isdigit():
            rubrics.append({"name": p[1], "count": int(p[2]), "max": int(p[3])})
        elif len(p) >= 3 and p[0] == "//RU" and p[1] == "+":
            writable = p[2:]
        elif len(p) >= 3 and p[0] == "//RU" and p[2] == ":":
            desc[p[1]] = line.split(None, 3)[3] if len(p) > 3 else ""
    for r in rubrics:
        r["desc"] = desc.get(r["name"], "")
    return rubrics, writable


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
    from prcore import lzhuf               # the same codec as FBB forwarding (B1)
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
        self.send_again = False           # CR47: outbox changed while busy - send after
        self.queue: asyncio.Queue | None = None
        self._body: tuple[int, int, list[str]] | None = None    # (id, lines left, lines)
        self.status = {"running": False, "scope": "", "step": "", "done": 0, "total": 0,
                       "error": "", "bytes": 0, "saved": 0, "aborting": False,
                       "notice": "", "fetch": 0, "fetch_error": ""}
        self.parts: dict[int, tuple[str, int, bytearray]] = {}   # id -> (kind, total, data)
        self._last_req = 0.0
        self._rubric_names: list[str] | None = None     # //RL of the last //BSYNC answer
        self._rubric_static: list[str] = []             # //RU lines of it
        self._rubric_counts: dict[str, int] = {}        # //RN
        # CR40: orderly abort, texts on demand, time estimate
        self._abort = False
        self._fetch_q: list[int] = []                   # texts asked for while a sync runs
        self._in_fetch = False
        self._ids: list[int] = []                       # scope "fetch"
        self._req_at = 0.0                              # last request out
        self._rx_at = 0.0                               # last answer byte in
        self._rx = 0                                    # bytes in since the request
        self._air_bytes = 0                             # measured: bytes and seconds of
        self._air_secs = 0.0                            # finished exchanges
        self._pend_mail: int | None = None              # rows left in the TinyBox (//SYNCEND)
        self._pend_bul: dict[str, int] | None = None    # bulletin headers left per rubric

    @property
    def running(self) -> bool:
        return self.task is not None and not self.task.done()

    # --- lines from the link (called by the core first) ---------------------

    def take(self, line: str) -> bool:
        """True if the line belongs to the sync."""
        if self.queue is None:
            return False
        self._rx += len(line) + 1
        self._rx_at = time.monotonic()
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
        if line.startswith("//P "):
            p = line.split()
            if len(p) == 6 and p[1].isdigit() and all(x.isdigit() for x in p[3:]):
                msg_id, kind, off, total = int(p[1]), p[2], int(p[3]), int(p[4])
                self._rx += int(p[5])
                q = self.queue
                self.core.link.splitter.expect(
                    int(p[5]), lambda data: q.put_nowait(("part", msg_id, kind, off, total, data)))
            return True
        if line.startswith("//ZSYNC "):
            p = line.split()
            if len(p) == 2 and p[1].isdigit():
                self._rx += int(p[1])
                self.core.link.splitter.expect(int(p[1]), self._zsync)
            return True
        if line.startswith("//ZMSG "):
            p = line.split()
            if len(p) == 3 and p[1].isdigit() and p[2].isdigit():
                msg_id, n = int(p[1]), int(p[2])
                self._rx += n
                q = self.queue
                self.core.link.splitter.expect(n, lambda data: q.put_nowait(("z", msg_id, data)))
            return True
        self.queue.put_nowait(("line", line))
        return True

    def _zsync(self, data: bytes) -> None:
        """A whole delta answer in one LZHUF block: its lines go the usual way."""
        if self.queue is None:
            return
        try:
            text = decompress(data)
        except ValueError as exc:
            log.warning("bad compressed sync answer (%s)", exc)
            self.queue.put_nowait(("line", "//ERR zsync"))
            return
        self.status["bytes"] += len(data)
        self.status["saved"] += len(text.encode()) - len(data)
        lines = text.split("\r")
        if lines and lines[-1] == "":              # every line ends in \r: nothing after the last
            lines.pop()
        rx = self._rx                              # the block counted, not what is in it
        for line in lines:                         # empty lines too: they count in //MSG texts
            self.take(line)
        self._rx = rx

    # --- control -----------------------------------------------------------------

    def start(self, scope: str = "mail") -> bool:
        if self.running or scope not in SCOPES or self.core.images.busy:
            return False                  # one binary transfer at a time (CR12)
        if self.core.state != "offline" and not self.core.at_home:
            return False                  # CR42: the mailbox is the own TinyBox's
        self.task = asyncio.ensure_future(self._run(scope))
        return True

    def fetch(self, msg_id: int) -> str:
        """Text of one message on demand (CR40). '' = on its way (or already
        here), else why not. Never connects by itself, and a request that cannot
        go out now is forgotten, not kept for later."""
        m = self.store.message(msg_id)
        if m is None:
            return "not found"
        if m["body"] is not None:
            return ""
        if self.core.state != "online" or not self.core.caps:
            return "not connected"
        if not self.core.at_home:
            return f"connected to {self.core.target}, the mailbox is at {self.core.home}"
        if "SYNC" not in self.core.caps:
            return "the TinyBox does not offer the mailbox sync"
        if self.running:
            if self.status["scope"] == "fetch" and msg_id in self._ids:
                return ""
            if self._abort:
                return "a sync is being aborted - try again in a moment"
            if msg_id not in self._fetch_q:
                self._fetch_q.append(msg_id)      # between two exchanges of the sync
            self._set(fetch=msg_id, fetch_error="")
            return ""
        if self.core.images.busy:
            return "a picture is being transferred - try again in a moment"
        self._ids = [msg_id]
        self._set(fetch=msg_id, fetch_error="")
        self.task = asyncio.ensure_future(self._run("fetch"))
        return ""

    def abort(self) -> None:
        """Orderly abort (CR40): the answer on the air still comes and is stored,
        then no new request goes out. If it does not come in time: hard stop."""
        if not self.running or self._abort:
            return
        self._abort = True
        self._fetch_q.clear()
        self._set(aborting=True, step=self.status["step"].split(" (")[0] + " (aborting)")
        asyncio.get_event_loop().call_later(ABORT_GRACE_SEC, self._hard_abort, self.task)

    def _hard_abort(self, task: asyncio.Task | None) -> None:
        if task is self.task and self.running and self._abort:
            log.info("sync: no answer after abort, stopping hard")
            task.cancel()

    cancel = abort                        # the old name (web API /api/mail/cancel)

    def _set(self, **kw) -> None:
        self.status.update(kw)
        self.core._touch()

    def _notice(self, text: str, console: bool = True) -> None:
        """Message for the user: in the mail view and in the console (CR40)."""
        self._set(notice=text)
        if console and text:
            self.core.console.append("*** " + text)

    # --- what is left, and how long it takes (CR40) ------------------------------

    def _close_exchange(self) -> None:
        """The answer to the last request is in: its bytes and air time count for
        the rate (from the request out to the last byte in)."""
        if self._req_at and self._rx_at > self._req_at and self._rx:
            self._air_bytes += self._rx
            self._air_secs += self._rx_at - self._req_at
        self._req_at, self._rx = 0.0, 0

    def _rate(self) -> float:
        """Net bytes per second of this link: measured, else [images] bytes_per_sec
        (radio) or a fast guess (telnet)."""
        if self._air_secs >= 2 and self._air_bytes >= 200:
            return max(10.0, self._air_bytes / self._air_secs)
        return float(self.core.cfg.img_rate) if self.radio else 5000.0

    def estimate(self, nbytes: int) -> float:
        """Seconds for nbytes: air time plus, per exchange, the pause (radio) and,
        while nothing is measured yet, the turnaround."""
        if nbytes <= 0:
            return 0.0
        cfg = self.core.cfg
        exchanges = max(1, -(-nbytes // cfg.sync_chunk))
        per = (cfg.sync_pause + (0 if self._air_secs >= 2 else 3)) if self.radio else 0.2
        return nbytes / self._rate() + exchanges * per

    def pending(self, phase: str = "") -> tuple[list[str], int, bool]:
        """(parts of the text, bytes, unknown left): what this sync still has to
        fetch - all of it, or only of one phase ("mail" / "bulletins")."""
        parts, nbytes, unknown = [], 0, False
        scope = phase or self.status["scope"]
        if scope in ("mail", "login"):
            if self._pend_mail is None:
                unknown = True
            elif self._pend_mail:
                parts.append(f"{self._pend_mail} mail header(s)")
                nbytes += self._pend_mail * HEADER_BYTES
            short = self._short_missing()
            if short:
                parts.append(f"{len(short)} short text(s)")
                nbytes += sum(short)
        if scope in ("bulletins", "login"):
            if self._pend_bul is None:
                subs = self.store.get("subscribed", [])
                if subs:
                    unknown = True
                    parts.append("bulletin headers of " + " ".join(subs))
            elif sum(self._pend_bul.values()):
                left = {r: n for r, n in self._pend_bul.items() if n}
                parts.append(f"{sum(left.values())} bulletin header(s) ("
                             + ", ".join(f"{r} {n}" for r, n in left.items()) + ")")
                nbytes += sum(left.values()) * HEADER_BYTES
        if scope == "fetch":
            for msg_id in self._ids:
                m = self.store.message(msg_id)
                if m is not None and m["body"] is None:
                    parts.append(f"text #{msg_id} ({human_bytes(m['size'])})")
                    nbytes += m["size"]
        return parts, nbytes, unknown

    def pending_text(self, phase: str = "") -> str:
        """'4 mail header(s), 2 short text(s) (approx. 20 s)'"""
        parts, nbytes, unknown = self.pending(phase)
        if not parts:
            return ""
        txt = ", ".join(parts)
        if nbytes:
            txt += f" ({human_secs(self.estimate(nbytes))}" + (" and more)" if unknown else ")")
        return txt

    def _short_missing(self) -> list[int]:
        """Sizes of personal texts up to short_bytes still to fetch."""
        short = self.core.cfg.sync_short
        out = []
        for msg_id in self.store.missing_bodies("P"):
            m = self.store.message(msg_id)
            if m is not None and 0 < m["size"] <= short:
                out.append(m["size"])
        return out

    def _bulletins_left(self) -> dict[str, int]:
        """Headers per subscribed rubric still in the TinyBox only (from //RN)."""
        local = {r["name"]: r["local"] for r in self.store.summary()["rubrics"]}
        return {r: max(0, self._rubric_counts.get(r, 0) - local.get(r, 0))
                for r in self.store.get("subscribed", []) if r in self._rubric_counts}

    def _start_notice(self, phase: str) -> None:
        """At the start of a transfer: what is pending, how long, and that Abort
        stops it. Gone again when the sync is through."""
        txt = self.pending_text(phase)
        if txt:
            self._notice(f"{phase.capitalize()}: {txt} to fetch. Press Abort to stop at any time.")

    # --- the run ----------------------------------------------------------------------

    async def _run(self, scope: str) -> None:
        self.queue = asyncio.Queue()
        self._body = None
        self._last_req = 0.0
        self._abort = False
        self._req_at, self._rx = 0.0, 0
        self._pend_mail, self._pend_bul = None, None
        if scope != "fetch":
            self._fetch_q.clear()
        self._set(running=True, scope=scope, step="connecting", done=0, total=0, error="",
                  bytes=0, saved=0, aborting=False,
                  **({"notice": ""} if scope != "fetch" else {}))
        own_connect = self.own_connect = False
        try:
            if self.core.state != "online":
                if scope == "fetch":                # CR40: a click never connects
                    raise SyncError("not connected")
                own_connect = self.own_connect = True
                # CR42/CR45: always the own TinyBox, in a free channel of its own
                if not await self.core.connect(self.core.home, auto=True):
                    raise SyncError("no free channel for the mailbox")
            await self._wait_ready()
            if scope == "fetch":
                for msg_id in list(self._ids):
                    await self._fetch_one(msg_id)
                if self._fetch_q:                    # another click meanwhile
                    await self._serve_fetches()
            else:
                if scope == "send":                  # CR47: only what waits in the outbox
                    items = self.store.outbox()
                    for i, item in enumerate(items):
                        self._set(step=f"sending {i + 1}/{len(items)}")
                        await self._send_one(item)
                if scope in ("mail", "login"):
                    await self._sync_mail()
                if scope in ("bulletins", "login"):
                    await self._sync_bulletins()
                if self._fetch_q:                    # clicked during the last exchange
                    await self._serve_fetches()
                for name in {"login": ("mail", "bulletins"), "send": ()}.get(scope, (scope,)):
                    self.store.put(f"last_sync.{name}", int(time.time()))
                self._set(notice="")                 # the start notice is done
            self._set(step="done")
        except Aborted:
            left = self.pending_text()
            if scope == "fetch":
                self._notice("Fetching the text aborted.", console=False)
            else:
                self._notice("Sync aborted." + (f" Still pending: {left}." if left else "")
                             + " It goes on from here at the next login or with Sync.")
            self._set(step="aborted", error="")
        except asyncio.CancelledError:
            left = self.pending_text()
            self._notice("Sync stopped." + (f" Still pending: {left}." if left else ""),
                         console=scope != "fetch")
            self._set(step="cancelled", error="cancelled")
        except SyncError as exc:
            log.warning("sync: %s", exc)
            self._set(step="failed", error=str(exc))
        except Exception as exc:                  # a bug must not kill the client
            log.exception("sync failed")
            self._set(step="failed", error=f"internal error: {exc}")
        if scope == "fetch" and self.status["error"]:
            self._set(fetch_error=self.status["error"])
        try:
            self.queue = None
            self._body = None
            if scope != "fetch":
                self.core.after_sync()
            if own_connect and self.core.state == "online" and not self.core.board:
                self.core.disconnect()             # offline again, as before
                for _ in range(150):               # until it is really down (next sync!)
                    if self.core.state == "offline":
                        break
                    await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        finally:
            self.queue = None
            self.own_connect = False
            self._abort = False
            self._fetch_q.clear()
            self.status["running"] = False
            self.status["aborting"] = False
            self.core._touch()
        if self.send_again and self.status["step"] == "done":
            self.send_again = False               # CR47: written meanwhile - out it goes,
            task = asyncio.current_task()         # once this run is really over
            if task is not None:
                task.add_done_callback(lambda _t: self.core.send_outbox())

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
        """The next answer. "No answer" only counts once our own request has left:
        a long mail over a slow link (VARA FM: ~13 B/s) is still on its way for
        minutes, and the TinyBox can answer //SENT only after the last line came
        (lauf 5, 18.10.2026: the sync gave up after 120 s, the //SENT came later
        and the mail stayed in the outbox)."""
        waited = 0.0
        while True:
            if self.core.state != "online":
                raise SyncError("connection lost")
            try:
                item = await asyncio.wait_for(self.queue.get(), IDLE_SEC)
            except asyncio.TimeoutError:
                waited += IDLE_SEC
                if waited < SEND_WAIT_MAX_SEC and await self._still_sending():
                    log.info("sync: own data still on its way, waiting for the answer")
                    continue
                raise SyncError("no answer from the TinyBox") from None
            if item[0] == "lost":
                raise SyncError("connection lost")
            return item

    async def _still_sending(self) -> bool:
        """Frames of ours not yet sent or not yet acknowledged by the TinyBox."""
        try:
            return await self.core.link.outstanding() > 0
        except Exception:                          # a link without the count: no
            return False

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

    @property
    def radio(self) -> bool:
        """Over the air: pauses between requests, compressed pieces. Telnet and
        AXUDP (PLANUNG 25) have no airtime."""
        return self.core.link.kind not in ("telnet", "axudp")

    async def _send(self, *lines: str) -> None:
        """One request. On radio with a pause before it (not before the first),
        longer while other stations use the channel. After Abort nothing goes
        out any more (CR40); texts clicked meanwhile go first."""
        self._close_exchange()
        if self._abort:
            raise Aborted()
        if self._fetch_q and not self._in_fetch:
            await self._serve_fetches()
            if self._abort:
                raise Aborted()
        if self.radio and self._last_req:
            cfg = self.core.cfg
            wait = self._last_req + cfg.sync_pause - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            until = time.monotonic() + BUSY_MAX_SEC
            while time.monotonic() < until:
                quiet = time.monotonic() - self.core.channel_busy_at
                if quiet >= BUSY_QUIET_SEC:
                    break
                self._set(step=self.status["step"].split(" (")[0] + " (channel busy)")
                await asyncio.sleep(BUSY_QUIET_SEC - quiet)
        if self._abort:
            raise Aborted()
        if self.core.state != "online":
            raise SyncError("connection lost")
        self._last_req = self._req_at = time.monotonic()
        self._rx = 0
        self.core._send(lines[0])
        for line in lines[1:]:                   # message text: not into the monitor
            self.core.link.send_line(line)

    def _page_size(self) -> int:
        return max(3, self.core.cfg.sync_chunk // HEADER_BYTES)

    async def _headers(self, request: str, step: str) -> int:
        """//MLIST or //BLIST page by page. Returns the number of headers."""
        st, n, after = self.store, 0, 0
        rub: dict[str, int] = {}
        if request.startswith("//BLIST"):
            rub = {r.split("=")[0]: int(r.split("=")[1]) for r in request.split()[1:]}
        while True:
            self._set(step=f"{step} ({n})" if n else step)
            if rub:
                line = "//BLIST " + " ".join(f"{r}={a}" for r, a in rub.items())
            else:
                line = request + (f" after={after}" if after else "")
            await self._send(f"{line} max={self._page_size()}")
            more = 0
            while True:
                item = await self._next()
                if item[0] != "line":
                    continue
                text = item[1]
                if text.startswith("//ERR"):
                    raise SyncError(text[2:])
                if text.startswith("//MEND"):
                    p = text.split()
                    more = int(p[2]) if len(p) > 2 and p[2].isdigit() else 0
                    break
                if text.startswith("//M ") and (h := parse_header(text[4:])):
                    st.upsert_header(h)
                    n += 1
                    after = max(after, h["id"])
                    if h["to_call"] in rub:
                        rub[h["to_call"]] = max(rub[h["to_call"]], h["id"])
            if not more:
                return n

    @property
    def delta(self) -> bool:
        return "SYNC2" in self.core.caps

    async def _sync_mail(self) -> None:
        st = self.store
        items = st.outbox()
        for i, item in enumerate(items):
            self._set(step=f"sending {i + 1}/{len(items)}")
            await self._send_one(item)
        if self.delta:
            await self._delta_mail()
            await self._texts("P", short_only=True)
            return
        kills = st.todo("kill")
        for i in range(0, len(kills), CHUNK):
            self._set(step="deleting")
            await self._send("//KILL " + " ".join(map(str, kills[i:i + CHUNK])))
            done = []
            for line in await self._lines_until("//KEND"):
                p = line.split()
                if len(p) == 3 and p[0] == "//K" and p[1].isdigit():
                    done.append(int(p[1]))       # ok, or not possible: either way gone here
            st.todo_done("kill", done)
        reads = st.todo("read")
        for i in range(0, len(reads), CHUNK):
            self._set(step="reporting read mail")
            await self._send("//READ " + " ".join(map(str, reads[i:i + CHUNK])))
            await self._lines_until("//REND")
            st.todo_done("read", reads[i:i + CHUNK])
        await self._headers("//MLIST", "mail list")
        self._pend_mail = 0
        await self._texts("P", short_only=True)

    async def _sync_bulletins(self) -> None:
        st = self.store
        if self.delta:
            await self._delta_bulletins()     # headers only: texts on demand (CR40)
            return
        self._set(step="rubrics")
        await self._send("//RUBRICS")
        rubrics, writable = parse_rubrics(await self._lines_until("//RUEND"))
        st.put("rubrics", rubrics)
        st.put("writable", writable)
        subs = [r for r in st.get("subscribed", []) if any(x["name"] == r for x in rubrics)]
        want = [f"{r}={st.max_bulletin(r)}" for r in subs
                if next(x["max"] for x in rubrics if x["name"] == r) > st.max_bulletin(r)]
        if want:
            await self._headers("//BLIST " + " ".join(want), "bulletin list")
        self._pend_bul = {}

    # --- delta sync (SYNC2) --------------------------------------------------------

    def _want(self) -> int:
        """Bytes of text the TinyBox may add to a delta answer: the chunk minus
        room for a few headers."""
        return max(0, self.core.cfg.sync_chunk - 3 * HEADER_BYTES)

    def _texts_arg(self) -> str:
        """CR40: only short personal texts come along (cap SHORT). A TinyBox
        without it would send any text that fits: then none, they come with
        one //GET (short ones) or on demand."""
        short = self.core.cfg.sync_short
        if "SHORT" in self.core.caps and short > 0:
            return f"want={self._want()} short={short}"
        return "want=0"

    async def _delta_answer(self, end: str, content: bool) -> list[str]:
        """Takes one delta answer up to the end line (returned as words). Headers,
        status lines, deletions and pushed texts are stored on the way."""
        st = self.store
        while True:
            item = await self._next()
            kind = item[0]
            if kind in ("text", "z"):
                msg_id, data = item[1], item[2]
                if kind == "z":
                    try:
                        text = decompress(data)
                    except ValueError as exc:
                        log.warning("msg %d: bad compressed data (%s), fetched later",
                                    msg_id, exc)
                        continue
                    self.status["bytes"] += len(data)
                    self.status["saved"] += len(text.encode()) - len(data)
                else:
                    text = data
                    self.status["bytes"] += len(text.encode())
                if st.message(msg_id) is not None:
                    st.set_body(msg_id, text)
                continue
            if kind != "line":
                continue
            line = item[1]
            if line.startswith("//ERR"):
                raise SyncError(line[2:])
            if line.startswith(end):
                return line.split()
            p = line.split()
            if line.startswith("//M ") and (h := parse_header(line[4:])):
                st.upsert_header(h, content=content)
                self._set(done=self.status["done"] + 1)
            elif line.startswith("//S ") and len(p) == 4 and p[1].isdigit():
                st.set_status(int(p[1]), p[2], "" if p[3] == "-" else p[3])
            elif line.startswith("//D "):
                st.remove_many([int(x) for x in p[1:] if x.isdigit()])
            elif line.startswith("//K ") and len(p) == 3 and p[1].isdigit():
                st.todo_done("kill", [int(p[1])])     # ok or not: gone here either way
            elif line.startswith("//RL "):
                self._rubric_names = p[1:]
                self._rubric_static = []
            elif line.startswith("//RU "):
                self._rubric_static.append(line)
            elif line.startswith("//RN "):
                self._rubric_counts = {k: int(v) for k, _, v in (x.partition("=") for x in p[1:])
                                       if v.isdigit()}

    async def _delta_mail(self) -> None:
        st = self.store
        seq = st.get("seq.mail", 0)
        retry = True
        asked: set[str] = set()
        while True:
            kills = st.todo("kill")[:CHUNK]
            reads = st.todo("read")[:CHUNK]
            req = f"//SYNC seq={seq}"
            if kills:
                req += " k=" + ",".join(map(str, kills))
            if reads:
                req += " r=" + ",".join(map(str, reads))
            req += f" max={self.core.cfg.sync_chunk} {self._texts_arg()}"
            _no_loop(asked, req)
            self._set(step="mail changes" if seq else "mail list")
            await self._send(req)
            try:
                end = await self._delta_answer("//SYNCEND", content=True)
            except SyncError as exc:
                if str(exc).strip() == "ERR seq" and retry and seq:
                    log.info("sync: the TinyBox does not know seq %d, starting over", seq)
                    seq, retry = 0, False           # database set up anew: everything
                    continue
                raise
            st.todo_done("read", reads)             # no answer line: done with the end line
            more = int(end[1]) if len(end) > 1 and end[1].isdigit() else 0
            for word in end[2:]:
                if word.startswith("seq=") and word[4:].isdigit():
                    seq = int(word[4:])
            st.put("seq.mail", seq)
            first = self._pend_mail is None
            self._pend_mail = more
            if first:
                self._start_notice("mail")
            if not more:
                return

    async def _delta_bulletins(self) -> None:
        st = self.store
        seq = st.get("seq.bulletins", 0)
        self._rubric_names = None
        self._rubric_static = []
        self._rubric_counts = {}
        retry = True
        asked: set[str] = set()
        while True:
            subs = st.get("subscribed", [])
            want = " ".join(f"{r}={st.max_bulletin(r)}" for r in subs)
            req = (f"//BSYNC seq={seq} h={st.get('rubrics.h', '0')}"
                   f"{' ' + want if want else ''} max={self.core.cfg.sync_chunk} "
                   f"want=0")                       # headers only (CR40)
            _no_loop(asked, req)
            self._set(step="bulletin changes" if seq else "bulletin list")
            await self._send(req)
            try:
                end = await self._delta_answer("//BSYNCEND", content=True)
            except SyncError as exc:
                if str(exc).strip() == "ERR seq" and retry and seq:
                    seq, retry = 0, False
                    continue
                raise
            more = int(end[1]) if len(end) > 1 and end[1].isdigit() else 0
            for word in end[2:]:
                if word.startswith("seq=") and word[4:].isdigit():
                    seq = int(word[4:])
                elif word.startswith("h="):
                    st.put("rubrics.h", word[2:])
            st.put("seq.bulletins", seq)
            self._store_rubrics()
            first = self._pend_bul is None
            self._pend_bul = self._bulletins_left() if more else {}
            if first:
                self._start_notice("bulletins")
            if not more:
                return

    def _store_rubrics(self) -> None:
        """Rubric list for the folder view: names and descriptions as last sent
        (only when changed), counts from every answer."""
        st = self.store
        old = {r["name"]: r for r in st.get("rubrics", [])}
        if self._rubric_names is not None:
            _, writable = parse_rubrics(self._rubric_static)
            desc = {}
            for line in self._rubric_static:
                p = line.split(None, 3)
                if len(p) >= 3 and p[2] == ":":
                    desc[p[1]] = p[3] if len(p) > 3 else ""
            names = list(dict.fromkeys(self._rubric_names + writable))
            rubrics = [{"name": n, "count": old.get(n, {}).get("count", 0), "max": 0,
                        "desc": desc.get(n, "")} for n in names]
            st.put("writable", writable)
        else:
            rubrics = list(old.values())
        for r in rubrics:
            if r["name"] in self._rubric_counts:
                r["count"] = self._rubric_counts[r["name"]]
        st.put("rubrics", rubrics)

    async def _serve_fetches(self) -> None:
        """Texts the user clicked while a sync ran: between two of its exchanges."""
        self._in_fetch = True
        try:
            while self._fetch_q and not self._abort:
                await self._fetch_one(self._fetch_q.pop(0))
        finally:
            self._in_fetch = False

    async def _fetch_one(self, msg_id: int) -> None:
        """One text on demand (CR40): //GET, or piece by piece if it is long."""
        m = self.store.message(msg_id)
        if m is None or m["body"] is not None:
            return
        self._set(fetch=msg_id, fetch_error="")
        chunk = self.core.cfg.sync_chunk
        if self.radio and "Z" in self.core.caps and m["size"] > chunk:
            await self._fetch_parts(msg_id, 1, 1, f"text #{msg_id}")
            return
        step = self.status["step"]
        self._set(step=f"text #{msg_id} ({human_bytes(m['size'])}, "
                       f"{human_secs(self.estimate(m['size']))})")
        await self._send(f"//GET {msg_id}")
        await self._get([msg_id])
        if self.status["scope"] != "fetch":
            self._set(step=step)

    async def _texts(self, kind: str, short_only: bool = False) -> None:
        """Missing texts, oldest first: short ones together up to chunk_bytes,
        long ones (radio) piece by piece. short_only: personal texts up to
        short_bytes (CR40), the rest comes on demand."""
        chunk = self.core.cfg.sync_chunk
        pieces = self.radio and "Z" in self.core.caps
        todo = [(m, self.store.message(m)["size"]) for m in self.store.missing_bodies(kind)]
        if short_only:
            todo = [(m, n) for m, n in todo if 0 < n <= self.core.cfg.sync_short]
        self._set(total=len(todo), done=0)
        while todo:
            n = self.status["done"]
            if pieces and todo[0][1] > chunk:
                msg_id = todo.pop(0)[0]
                await self._fetch_parts(msg_id, n + 1, len(todo) + n + 1)
                continue
            batch, size = [], 0
            while todo and len(batch) < 20 and (not batch or size + todo[0][1] <= chunk) \
                    and not (pieces and todo[0][1] > chunk):
                size += todo[0][1]
                batch.append(todo.pop(0)[0])
            total = self.status["total"]
            self._set(step=f"texts {n + 1}-{n + len(batch)} of {total}")
            await self._send("//GET " + " ".join(map(str, batch)))
            await self._get(batch)

    async def _fetch_parts(self, msg_id: int, nr: int, total: int, label: str = "") -> None:
        chunk = self.core.cfg.sync_chunk
        while True:
            kind, size, data = self.parts.get(msg_id, ("", 0, bytearray()))
            pct = f", {100 * len(data) // size} %" if size else ""
            if label:
                m = self.store.message(msg_id)
                left = (size - len(data)) if size else (m["size"] if m else 0)
                self._set(step=f"{label} in pieces{pct}, {human_secs(self.estimate(left))}")
            else:
                self._set(step=f"text {nr} of {self.status['total']} in pieces{pct}")
            await self._send(f"//PART {msg_id} {len(data)} {chunk}")
            while True:
                item = await self._next()
                if item[0] == "part" and item[1] == msg_id:
                    break
                if item[0] == "line" and item[1].startswith(("//NOMSG", "//ERR")):
                    self.parts.pop(msg_id, None)
                    if item[1].startswith("//ERR"):
                        raise SyncError(item[1][2:])
                    self.store.remove(msg_id)
                    self._set(done=self.status["done"] + 1)
                    return
            _, _, pkind, off, ptotal, piece = item
            if (kind and (pkind != kind or ptotal != size)) or off != len(data):
                data = bytearray()                 # the text changed meanwhile: start again
                if off != 0:
                    self.parts.pop(msg_id, None)
                    continue
            data += piece
            self.status["bytes"] += len(piece)
            self.parts[msg_id] = (pkind, ptotal, data)
            if len(data) >= ptotal or not piece:
                break
        self.parts.pop(msg_id, None)
        raw = bytes(data)
        try:
            text = decompress(raw) if pkind == "Z" else raw.decode("utf-8", "replace")
        except ValueError as exc:
            log.warning("msg %d: bad compressed data (%s), fetched later", msg_id, exc)
            self._set(done=self.status["done"] + 1)
            return
        if pkind == "Z":
            self.status["saved"] += len(text.encode()) - len(raw)
        self.store.set_body(msg_id, text)
        self._set(done=self.status["done"] + 1)

    async def _send_one(self, item: dict) -> None:
        to = item["to_call"].replace(" ", "")
        tried = f"out_try.{item['mid']}"
        # CR69: tried before and no //SENT came - ask first, so the text does not
        # go over the air again only to hear "had it already" (slow links: minutes)
        if self.store.get(tried) and "HAVE" in self.core.caps:
            await self._send(f"//HAVE {item['mid']} {to}")
            while True:
                entry = await self._next()
                if entry[0] == "line" and entry[1].startswith(("//HAVE ", "//ERR")):
                    break
            p = entry[1].split()
            ids = [int(x) for x in p[2:] if x.isdigit()] if p[0] == "//HAVE" else []
            if ids:
                log.info("mail %s was already in the TinyBox (%s) - not sent again",
                         item["mid"], " ".join(map(str, ids)))
                self._stored(item, to, ids)
                self.store.drop(tried)
                return
        self.store.put(tried, int(time.time()))
        lines = []
        for line in item["body"].replace("\r", "").replace("\x1a", "").split("\n"):
            while len(line) > MAX_LINE_OUT:
                lines.append(line[:MAX_LINE_OUT])
                line = line[MAX_LINE_OUT:]
            lines.append(line)
        if lines == [""]:
            lines = []
        subject = " ".join(item["subject"].split()) or "(no subject)"
        await self._send(f"//SEND {item['type']} {to} {len(lines)} mid={item['mid']}", subject,
                         *lines)
        while True:
            entry = await self._next()
            if entry[0] != "line":
                continue
            line = entry[1]
            if line.startswith("//SENT "):
                self._stored(item, to, [int(x) for x in line.split()[1:] if x.isdigit()])
                self.store.drop(tried)
                return
            if line.startswith("//ERR"):
                self.store.out_error(item["oid"], line[2:].replace("ERR send ", ""))
                return                              # stays in the outbox, the sync goes on

    def _stored(self, item: dict, to: str, ids: list[int]) -> None:
        """The TinyBox has the mail (//SENT or //HAVE): from the outbox to Sent."""
        calls, _, at = to.partition("@")
        # CR27: one number per recipient, in the order sent; the TinyBox
        # puts "To: A, B" on top of every copy, so does the Sent folder
        if len(ids) > 1:
            item = dict(item, body=f"To: {calls.upper().replace(',', ', ')}\n" + item["body"])
        for msg_id, call in zip(ids, calls.split(",")):
            self.store.add_sent(msg_id, item, self.core.cfg.mycall, call.upper(), at.upper())

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
