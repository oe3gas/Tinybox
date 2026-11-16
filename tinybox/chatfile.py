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
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from prcore.chatimg import HASH_RE, parse_file_ref
from prcore.filecheck import name_verdict
from prcore.text import isnum

from .blobs import Uploads, send_from     # the common part (R10)

if TYPE_CHECKING:
    from .config import Config
    from .session import Session
    from .store import Store

log = logging.getLogger(__name__)

UNREF_GRACE_H = 1


class ChatFiles:
    def __init__(self, store: Store, cfg: Config) -> None:
        self.store = store
        self.cfg = cfg
        self.uploads = Uploads()             # half uploads (blobs.py, R10; owner: CR96)

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
        p = self.uploads.begin(h, s.call, size, how)
        if p is None:
            log.warning("%s: file upload %s refused - %s is uploading it", s.call, h,
                        self.uploads.owner(h))
            s.out("//ERR file busy")
            return
        s.out(f"//FGO {h} {p.have}")
        self.uploads.receive(s, h, lambda: self._done(s, h), lambda: self._cancel(s, h))

    def _cancel(self, s: Session, h: str) -> None:
        p = self.uploads.get(h)
        s.out(f"//ERR file timeout {p.have if p else 0}")

    def _done(self, s: Session, h: str) -> None:
        p = self.uploads.finish(h, s.call)
        if p is None:
            s.out("//ERR file not_started")
            return
        self.store.file_put(h, p.meta, bytes(p.data), s.call)
        log.info("%s uploaded file %s (%d bytes, %s)", s.call, h, p.have, p.meta)
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
        n = send_from(s, f"//BF {h} {how} {offset} {len(data)}", data, offset)
        log.info("%s > //FGET %s: %d bytes from %d of %d", s.call, h, n, offset, len(data))

    def purge(self) -> int:
        self.uploads.purge()
        before = (datetime.now(timezone.utc) - timedelta(hours=UNREF_GRACE_H)
                  ).strftime("%Y-%m-%dT%H:%M:%SZ")
        return self.store.file_purge(before)
