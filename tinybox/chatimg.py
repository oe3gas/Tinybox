"""Small images in the chat (CR12, docs/client-change-requests.md).

The reference format and its helpers are in prcore/chatimg.py. This module is
the TinyBox side: upload, storage and the client commands.

Client commands (cap IMG: radio sessions only). AX.25 is reliable, so the data
goes in one block each way - no pieces, no acknowledgements:

    //IMGPUT <hash> <bytes>   start/resume an upload (in a board with images)
        -> //IMGGO <hash> <have>   now send the bytes from <have> on, raw,
                                   right after the CR of this answer
           //IMGOK <hash>          already here (same picture sent before)
           //ERR img <reason>      no_images | too_large <max> | syntax
       (after the bytes)
        -> //IMGOK <hash>          complete, hash and type checked, stored
           //ERR img bad_hash | bad_type
    //IMG <hash> [<offset>]   a stored image (any board, or none)
        -> //I <hash> <offset> <total> + (total - offset) raw bytes
           //NOIMG <hash>

A half uploaded image stays in memory for one hour; //IMGPUT answers with the
bytes already there, the client goes on from that offset. If the bytes stop
coming (RAW_TIMEOUT), the session goes back to reading lines and answers
//ERR img timeout - what arrived is kept for the next //IMGPUT. Images are deleted
when no stored chat line refers to them any more (the board's keep time), but
never within the first hour after the upload.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from prcore.chatimg import HASH_RE, image_hash, image_type, parse_ref, size_code
from prcore.text import isnum

from .blobs import Uploads, send_from     # the common part (R10)

if TYPE_CHECKING:
    from .config import Config
    from .session import Session
    from .store import Store

log = logging.getLogger(__name__)

RAW_TIMEOUT = 120                   # s without a byte: the upload is over for now
UNREF_GRACE_H = 1                   # h a stored image survives without a chat line


class ChatImages:
    def __init__(self, store: Store, cfg: Config) -> None:
        self.store = store
        self.cfg = cfg
        # uploads under way (blobs.py, R10). CR96 (TB-16): an upload belongs to the
        # station that began it - no other may start, replace or finish it while kept
        self.uploads = Uploads()

    # --- what a board allows -----------------------------------------------

    def limit(self, s: Session) -> int:
        """Max image bytes in the session's board (0 = none)."""
        board = self.cfg.chat.board(s.chat_board or "")
        return self.cfg.chat.image_limit(board) if board else 0

    def check_line(self, s: Session, text: str) -> str | None:
        """A client's chat line: an image reference must be allowed here and
        name an uploaded image. Returns the error reason, or None."""
        r = parse_ref(text)
        if r is None:
            return None
        if not self.limit(s):
            return "no_images"
        if self.store.image_size(r[0]) is None:
            return "unknown"
        return None

    # --- upload -----------------------------------------------------------------

    def put(self, s: Session, parts: list[str]) -> None:
        """//IMGPUT <hash> <bytes> -> //IMGGO <hash> <have>, then the bytes come."""
        if len(parts) != 2 or not HASH_RE.match(parts[0]) or not isnum(parts[1]):
            s.out("//ERR img syntax")
            return
        h, size = parts[0], int(parts[1])
        limit = self.limit(s)
        if not limit:
            s.out("//ERR img no_images")
            return
        if size > limit or size < 1:
            s.out(f"//ERR img too_large {limit}")
            return
        if self.store.image_size(h) is not None:
            s.out(f"//IMGOK {h}")
            return
        p = self.uploads.begin(h, s.call, size)
        if p is None:
            log.warning("%s: upload of %s refused - %s is uploading it", s.call, h,
                        self.uploads.owner(h))
            s.out("//ERR img busy")
            return
        s.out(f"//IMGGO {h} {p.have}")
        # CR30: the others see "OE1ABC uploading picture" with a progress bar
        s.service.chat.upload_started(s, size_code(size), size)
        # everything that comes now is image data - the client holds back its
        # other lines until the last byte is out (CR12, 12.10.2026)
        self.uploads.receive(s, h, lambda: self._done(s, h), lambda: self._cancel(s, h))

    def _cancel(self, s: Session, h: str) -> None:
        """The bytes stopped coming: keep what is here, tell the client."""
        p = self.uploads.get(h)
        log.info("%s: upload of %s stopped at %d bytes", s.call, h, p.have if p else 0)
        s.out(f"//ERR img timeout {p.have if p else 0}")

    def _done(self, s: Session, h: str) -> None:
        p = self.uploads.finish(h, s.call)
        if p is None:
            s.out("//ERR img not_started")
            return
        data = bytes(p.data)
        if image_hash(data) != h:
            s.out("//ERR img bad_hash")
            return
        if image_type(data) is None:
            s.out("//ERR img bad_type")
            return
        old = self.store.image_get(h)
        if old is not None and old != data:      # CR96 (TB-16): same short hash, other picture
            log.warning("%s: image %s collides with a stored one - refused", s.call, h)
            s.out("//ERR img collision")
            return
        self.store.image_put(h, data)
        log.info("%s uploaded image %s (%d bytes, %s)", s.call, h, len(data), image_type(data))
        s.out(f"//IMGOK {h}")

    # --- download ---------------------------------------------------------------

    def get(self, s: Session, parts: list[str]) -> None:
        """//IMG <hash> [<offset>] -> //I <hash> <offset> <total> + bytes, or //NOIMG."""
        if (not 1 <= len(parts) <= 2 or not HASH_RE.match(parts[0])
                or (len(parts) == 2 and not isnum(parts[1]))):
            s.out("//ERR img syntax")
            return
        h = parts[0]
        offset = int(parts[1]) if len(parts) == 2 else 0
        data = self.store.image_get(h)
        if data is None:
            s.out(f"//NOIMG {h}")
            return
        n = send_from(s, f"//I {h} {offset} {len(data)}", data, offset)
        log.info("%s > //IMG %s: %d bytes from %d of %d", s.call, h, n, offset, len(data))

    # --- housekeeping ---------------------------------------------------------------

    def purge(self) -> int:
        self.uploads.purge()
        before = (datetime.now(timezone.utc) - timedelta(hours=UNREF_GRACE_H)
                  ).strftime("%Y-%m-%dT%H:%M:%SZ")
        return self.store.image_purge(before)
