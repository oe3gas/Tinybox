"""Uploads in pieces and downloads from an offset - the TinyBox side (R10).

Chat images (chatimg.py, CR12) and board files (chatfile.py, CR86) move a blob
the same way; only the command names, the checks and the storage differ:

    upload    //...PUT <hash> ... <bytes>  ->  //...GO <hash> <have>, then the raw
              bytes from <have> on; a broken upload resumes there
    download  //... <hash> [<offset>]      ->  header line + the raw bytes from offset

This module holds that common part: the half uploads (who began them, how much is
here, when they expire - CR96: an upload belongs to the station that began it)
and the download from an offset. CR105 (profile photo) or another kind of blob
plugs in here instead of a third copy.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .session import Session

PARTIAL_TTL = 3600          # s a half upload is kept


@dataclass
class Partial:
    size: int               # bytes announced
    call: str               # the station that began it - no other may go on (CR96)
    meta: str = ""          # e.g. "z"/"r" for files: another value = a new upload
    data: bytearray = field(default_factory=bytearray)
    last: float = field(default_factory=time.monotonic)

    @property
    def have(self) -> int:
        return len(self.data)


class Uploads:
    """Half uploads by hash."""

    def __init__(self, ttl: float = PARTIAL_TTL) -> None:
        self.ttl = ttl
        self._p: dict[str, Partial] = {}

    def get(self, h: str) -> Partial | None:
        return self._p.get(h)

    def owner(self, h: str) -> str | None:
        """The station uploading h, or None."""
        p = self._p.get(h)
        return p.call if p is not None else None

    def begin(self, h: str, call: str, size: int, meta: str = "") -> Partial | None:
        """Start or resume. None: another station is uploading h (CR96)."""
        p = self._p.get(h)
        if p is not None and p.call != call:
            return None
        if p is None or p.size != size or p.meta != meta:
            p = self._p[h] = Partial(size, call, meta)
        p.last = time.monotonic()
        return p

    def receive(self, s: Session, h: str, done: Callable[[], None],
                cancel: Callable[[], None]) -> None:
        """The rest of the bytes come raw on the session (Session.collect_raw)."""
        p = self._p[h]
        s.collect_raw(p.size - p.have, lambda chunk: self._chunk(h, chunk), done, cancel)

    def _chunk(self, h: str, chunk: bytes) -> None:
        p = self._p.get(h)
        if p is not None:
            p.data += chunk
            p.last = time.monotonic()

    def finish(self, h: str, call: str) -> Partial | None:
        """All bytes are here: take the upload out. None if it is not this station's."""
        p = self._p.get(h)
        if p is None or p.call != call:
            return None
        return self._p.pop(h)

    def purge(self) -> int:
        now = time.monotonic()
        old = [h for h, p in self._p.items() if now - p.last > self.ttl]
        for h in old:
            del self._p[h]
        return len(old)


def send_from(s: Session, header: str, data: bytes, offset: int) -> int:
    """Download: the header line, then the raw bytes from offset. Returns their count."""
    piece = data[offset:]
    s.transport.write(header + "\r")
    s.transport.write_bytes(piece)
    return len(piece)
