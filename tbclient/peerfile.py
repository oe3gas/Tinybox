"""Files between two TBClients (CR78) - like the pictures (peerimg.py).

The sender keeps the file (data/tbclient/files/<hash>). Over the air goes
only a chat line with the reference - in the chat history of both sides:

    ~%<hash 6 hex> <bytes> <bytes on air> <file name>

The other side shows a file bubble (name, size, time on air) and fetches it
on a tap, straight from the sender:

    //FGET <hash>                     -> //F <hash> <z|r> <n> + n bytes
                                      or //NOFILE <hash>

z = LZHUF (prcore/lzhuf.py, B0: 4-byte length + data), r = as it is (when
LZHUF does not make it smaller - a ZIP, a JPEG). The hash is over the file
itself, so the receiver checks what it unpacked. A client gives a file only
to the station it offered it to (the reference in its sent history with
it). Up to FILE_MAX bytes; packing runs in a thread (pure Python).
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING

from prcore import chatimg, lzhuf
from prcore.text import isnum

from . import budget, filecheck

if TYPE_CHECKING:
    from .peer import Peer

log = logging.getLogger(__name__)

FILE_MAX = 64 * 1024        # bytes of the file itself
IDLE_SEC = 120              # a download without a byte for this long may be asked again
REF_RE = re.compile(rf"^~%([0-9a-f]{{{chatimg.HASH_LEN}}}) (\d+) (\d+) (.+)$")


def parse_ref(text: str) -> tuple[str, int, int, str] | None:
    m = REF_RE.match(text or "")
    if not m:
        return None
    return m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)


def safe_name(name: str) -> str:
    """A file name that is harmless on every system (and on one line)."""
    name = Path(name.replace("\\", "/")).name
    name = re.sub(r"[^\w.\- ()+,]", "_", name, flags=re.ASCII).strip(" .")
    return name[:60] or "file"


class FileStore:
    def __init__(self, folder: Path) -> None:
        self.folder = folder

    def path(self, h: str) -> Path:
        return self.folder / h

    def has(self, h: str) -> bool:
        return chatimg.HASH_RE.match(h) is not None and self.path(h).is_file()

    def get(self, h: str) -> bytes | None:
        try:
            return self.path(h).read_bytes() if self.has(h) else None
        except OSError:
            return None

    def put(self, h: str, data: bytes, *, own: bool = False) -> bool:
        """Store; what came over the air never replaces what is here already
        (CR96, TB-05/TB-16) - only own data (own=True) may. False = kept the old."""
        if not own and self.has(h):
            return False
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path(h).write_bytes(data)
        return True


class PeerFiles:
    def __init__(self, peer: "Peer") -> None:
        self.peer = peer
        self._want: str | None = None
        self._last = 0.0

    @property
    def core(self):
        return self.peer.ch.core

    @property
    def store(self) -> FileStore:
        return self.core.files

    @property
    def loading(self) -> dict:
        return self.core.file_loading

    @property
    def ok(self) -> bool:
        return "FILE" in self.peer.caps and self.peer.ch.state == "online" \
            and self.peer.ch.link.kind != "telnet"

    # --- offering a file ------------------------------------------------------------

    async def send(self, name: str, data: bytes) -> str | None:
        if not self.ok or not data or len(data) > FILE_MAX:
            return None
        h = chatimg.image_hash(data)             # 6 hex over the bytes - for any file
        packed = await asyncio.to_thread(lzhuf.compress, data)
        air = min(len(packed), len(data))
        self.store.put(h, data, own=True)
        self.peer.ch.send_raw(f"~%{h} {len(data)} {air} {safe_name(name)}")
        return h

    # --- fetching one ---------------------------------------------------------------

    def _offer(self, h: str) -> tuple[str, int] | None:
        """(name, size) of the file this station offered us under h."""
        pc = self.core.peerchat
        if pc is None:
            return None
        for m in reversed(pc.messages(self.peer.call)):
            r = parse_ref(m["text"]) if m["dir"] == "rx" else None
            if r and r[0] == h:
                return r[3], r[1]
        return None

    def fetch(self, h: str) -> bool:
        if not chatimg.HASH_RE.match(h) or self.store.has(h) or not self.ok:
            return False
        offer = self._offer(h)
        why = filecheck.name_verdict(offer[0]) if offer else None
        if why or (offer and offer[1] > FILE_MAX):      # CR96: refused before a byte comes
            self.loading[h] = {"done": 0, "total": 0, "error": why or "too large"}
            self.core._touch()
            return False
        busy = self._want and time.monotonic() - self._last < IDLE_SEC
        if busy:
            return self._want == h                # one at a time
        self._want, self._last = h, time.monotonic()
        self.loading[h] = {"done": 0, "total": 0, "error": ""}
        self.peer._send(f"//FGET {h}")
        self.core._touch()
        return True

    def link_lost(self) -> None:
        if self._want:
            self._fail(self._want, "connection lost - tap to try again")

    def _fail(self, h: str, why: str) -> None:
        self.loading[h] = {**self.loading.get(h, {}), "error": why}
        if self._want == h:
            self._want = None
        self.core._touch()

    # --- lines from the other side --------------------------------------------------

    def take(self, word: str, rest: str) -> bool:
        p = rest.split()
        if word == "FGET" and p:
            asyncio.ensure_future(self._serve(p[0]))
            return True
        if word == "F" and len(p) == 3 and p[1] in ("z", "r") and isnum(p[2]):
            self._incoming(p[0], p[1], int(p[2]))
            return True
        if word == "NOFILE" and p:
            self._fail(p[0], "not available any more")
            return True
        return False

    def _offered(self, h: str) -> bool:
        pc = self.core.peerchat
        return pc is not None and any(m["dir"] == "tx" and m["text"].startswith(f"~%{h} ")
                                      for m in pc.messages(self.peer.call))

    async def _serve(self, h: str) -> None:
        data = self.store.get(h) if chatimg.HASH_RE.match(h) else None
        if data is None or not self.peer.trusted or not self._offered(h):    # CR99 (TB-06)
            self.peer._send(f"//NOFILE {h}")
            return
        packed = await asyncio.to_thread(lzhuf.compress, data)
        how, body = ("z", packed) if len(packed) < len(data) else ("r", data)
        if self.peer.ch.state != "online":
            return
        b = budget.of(self.core)             # CR97 (TB-03): twice an hour, and out of the budget
        if b.often(self.peer.call, "F" + h, 2, 3600) or \
                not b.allow(self.peer.call, len(body), f"file {h}"):
            self.peer._send(f"//NOFILE {h}")
            return
        self.peer._send(f"//F {h} {how} {len(body)}")      # line and bytes together
        self.peer.ch.link.send_bytes(body)
        log.info("file %s to %s (%d bytes, %d on air)", h, self.peer.call, len(data), len(body))

    def _incoming(self, h: str, how: str, n: int) -> None:
        if n > FILE_MAX:                       # CR96 (TB-05): also for 'r', not only 'z'
            log.warning("file %s from %s: %d bytes announced - link dropped", h, self.peer.call, n)
            self.peer.ch.disconnect()
            return
        if h != self._want:                    # CR96 (TB-05): only what we asked for
            log.warning("file %s from %s not asked for - ignored", h, self.peer.call)
            self.peer.ch.link.splitter.expect(n, lambda _body: None)
            return
        ld = self.loading.setdefault(h, {"done": 0, "total": n, "error": ""})
        ld["total"] = n

        def progress(got: int) -> None:
            self._last = time.monotonic()
            ld["done"] = got
            self.core._touch()

        def done(body: bytes) -> None:
            if self._want == h:
                self._want = None
            try:
                data = lzhuf.decompress(body, FILE_MAX) if how == "z" else body
            except Exception:
                data = b""
            if not data or chatimg.image_hash(data) != h:
                self._fail(h, "damaged, tap to try again")
                return
            offer = self._offer(h)
            why = filecheck.verdict(offer[0] if offer else "", data)
            if why:                            # CR96: a program does not land on the PC
                log.warning("file %s from %s: %s", h, self.peer.call, why)
                self._fail(h, why)
                return
            if not self.store.put(h, data):
                log.info("file %s is here already - kept", h)
            self.loading.pop(h, None)
            log.info("file %s from %s (%d bytes)", h, self.peer.call, len(data))
            self.core._touch()

        self.peer.ch.link.splitter.expect(n, done, progress)
