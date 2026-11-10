"""Files in a chat board (CR86, docs/client-change-requests.md) - the TinyBox side.

Like the images (chatimg.py): the file is uploaded once and kept in the TinyBox;
the chat line carries only the reference (prcore.chatimg.parse_file_ref)

    ~%<hash 16 hex> <bytes> <bytes on air> <name>

and whoever wants it fetches it with I-frames. The client packs (LZHUF, or raw if
that saves nothing); the TinyBox never unpacks, it checks the size and the name
(no programs, prcore.filecheck) and keeps the blob under the hash of the
unpacked file. The receiving client checks hash and content after unpacking.

Client commands (cap BFILE: radio/AXUDP sessions, in a board that allows files):

    //FPUT <hash> <z|r> <bytes>     start/resume an upload
        -> //FGO <hash> <have>      send the bytes from <have> on, raw
           //FOK <hash>             already here
           //ERR file <reason>      no_files | too_large <max> | busy | syntax
       (after the bytes)
        -> //FOK <hash>             stored
    //FGET <hash> [<offset>]        a stored file
        -> //BF <hash> <z|r> <offset> <total> + (total - offset) raw bytes
           //NOBFILE <hash>

A half upload is kept for an hour and belongs to the station that began it
(CR96). A file goes when no stored chat line refers to it (the board's keep
time), never within the first hour.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from prcore.chatimg import HASH_RE, parse_file_ref
from prcore.filecheck import name_verdict
from prcore.text import isnum

if TYPE_CHECKING:
    from .config import Config
    from .session import Session
    from .store import Store

log = logging.getLogger(__name__)

PARTIAL_TTL = 3600
UNREF_GRACE_H = 1


class ChatFiles:
    def __init__(self, store: Store, cfg: Config) -> None:
        self.store = store
        self.cfg = cfg
        self._partial: dict[str, list] = {}   # hash -> [how, size, bytearray, last, call]

    def limit(self, s: Session) -> int:
        board = self.cfg.chat.board(s.chat_board or "")
        return self.cfg.chat.file_limit(board) if board else 0

    def check_line(self, s: Session, text: str) -> str | None:
        """A file reference in a client's chat line: allowed here, uploaded, and no
        program by its name. Returns the error reason, or None."""
        r = parse_file_ref(text)
        if r is None:
            return None
        if not self.limit(s):
            return "no_files"
        if self.store.file_get(r[0]) is None:
            return "unknown"
        if name_verdict(r[3]):
            return "program"
        return None

    # --- upload -------------------------------------------------------------------

    def put(self, s: Session, parts: list[str]) -> None:
        if len(parts) != 3 or not HASH_RE.match(parts[0]) or parts[1] not in ("z", "r") \
                or not isnum(parts[2]):
            s.out("//ERR file syntax")
            return
        h, how, size = parts[0], parts[1], int(parts[2])
        limit = self.limit(s)
        if not limit:
            s.out("//ERR file no_files")
            return
        if not 1 <= size <= limit:
            s.out(f"//ERR file too_large {limit}")
            return
        if self.store.file_get(h) is not None:
            s.out(f"//FOK {h}")
            return
        p = self._partial.get(h)
        if p is not None and p[4] != s.call:
            log.warning("%s: file upload %s refused - %s is uploading it", s.call, h, p[4])
            s.out("//ERR file busy")
            return
        if p is None or p[0] != how or p[1] != size:
            p = self._partial[h] = [how, size, bytearray(), time.monotonic(), s.call]
        p[3] = time.monotonic()
        s.out(f"//FGO {h} {len(p[2])}")
        s.collect_raw(size - len(p[2]), lambda chunk: self._chunk(h, chunk),
                      lambda: self._done(s, h), lambda: self._cancel(s, h))

    def _chunk(self, h: str, chunk: bytes) -> None:
        p = self._partial.get(h)
        if p is not None:
            p[2] += chunk
            p[3] = time.monotonic()

    def _cancel(self, s: Session, h: str) -> None:
        p = self._partial.get(h)
        s.out(f"//ERR file timeout {len(p[2]) if p else 0}")

    def _done(self, s: Session, h: str) -> None:
        p = self._partial.pop(h, None)
        if p is None or p[4] != s.call:
            s.out("//ERR file not_started")
            return
        self.store.file_put(h, p[0], bytes(p[2]), s.call)
        log.info("%s uploaded file %s (%d bytes, %s)", s.call, h, len(p[2]), p[0])
        s.out(f"//FOK {h}")

    # --- download -----------------------------------------------------------------

    def get(self, s: Session, parts: list[str]) -> None:
        if not 1 <= len(parts) <= 2 or not HASH_RE.match(parts[0]) \
                or (len(parts) == 2 and not isnum(parts[1])):
            s.out("//ERR file syntax")
            return
        h = parts[0]
        offset = int(parts[1]) if len(parts) == 2 else 0
        got = self.store.file_get(h)
        if got is None:
            s.out(f"//NOBFILE {h}")
            return
        how, data = got
        piece = data[offset:]
        s.transport.write(f"//BF {h} {how} {offset} {len(data)}\r")
        s.transport.write_bytes(piece)
        log.info("%s > //FGET %s: %d bytes from %d of %d", s.call, h, len(piece), offset,
                 len(data))

    def purge(self) -> int:
        now = time.monotonic()
        for h in [h for h, p in self._partial.items() if now - p[3] > PARTIAL_TTL]:
            del self._partial[h]
        before = (datetime.now(timezone.utc) - timedelta(hours=UNREF_GRACE_H)
                  ).strftime("%Y-%m-%dT%H:%M:%SZ")
        return self.store.file_purge(before)
