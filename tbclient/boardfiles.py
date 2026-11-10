"""Files in a chat board (CR86) - the client side. Protocol: tinybox/chatfile.py.

Like the board images (images.py, the same job queue, waiting for a mailbox
sync, holding back other lines while the bytes go out): upload once to the
TinyBox, the chat line carries only the reference

    ~%<hash 16 hex> <bytes> <bytes on air> <name>

and everybody fetches the file from the TinyBox on a tap. Packed with LZHUF
when that makes it smaller (z), else raw (r). The receiver unpacks, checks the
hash and the content (prcore.filecheck: no programs) and keeps it in
data/tbclient/files/<hash> - the same place as the files between two TBClients.
"""

from __future__ import annotations

import asyncio
import logging
import time

from prcore import chatimg, filecheck, lzhuf
from prcore.text import isnum

from .images import Images

log = logging.getLogger(__name__)

FILE_MAX = 64 * 1024            # bytes of the file itself (the TinyBox limits what is sent)


class BoardFiles(Images):
    """Board files, one transfer at a time (shares the link with the images)."""

    # --- what the GUI asks for ------------------------------------------------

    def send_file(self, name: str, data: bytes, prefix: str = "") -> str | None:
        """Check, pack, keep; queue the upload - the chat line follows when it is up."""
        from .peerfile import safe_name
        name = safe_name(name)
        if not data or len(data) > FILE_MAX or filecheck.name_verdict(name) \
                or filecheck.content_verdict(data):
            return None
        packed = lzhuf.compress(data)
        how, blob = ("z", packed) if len(packed) < len(data) else ("r", data)
        limit = (self.core.board or {}).get("file", 0)
        if not limit or len(blob) > limit:
            return None
        h = chatimg.image_hash(data)
        self.store.put(h, data, own=True)
        line = f"{prefix}~%{h} {len(data)} {len(blob)} {name}"
        self.upload = {"hash": h, "size": len(blob), "sent": 0, "state": "waiting",
                       "error": "", "line": line, "at": time.time(), "known": False,
                       "name": name, "file": True}
        self._jobs.append({"kind": "up", "hash": h, "data": blob, "how": how, "line": line})
        self._kick()
        return h

    def retry(self) -> bool:
        up = self.upload
        data = self.store.get(up["hash"]) if up and up["state"] == "error" else None
        if data is None:
            return False
        packed = lzhuf.compress(data)
        how, blob = ("z", packed) if len(packed) < len(data) else ("r", data)
        up.update(state="waiting", sent=0, error="")
        self._jobs.append({"kind": "up", "hash": up["hash"], "data": blob, "how": how,
                           "line": up["line"]})
        self._kick()
        return True

    def fetch_file(self, hash: str, name: str) -> bool:
        if not chatimg.HASH_RE.match(hash) or self.store.has(hash):
            return False
        why = filecheck.name_verdict(name)
        if why:                                      # CR96: refused before a byte comes
            self.loading[hash] = {"done": 0, "total": 0, "error": why}
            self.core._touch()
            return False
        if hash in self.loading and not self.loading[hash].get("error"):
            return True
        self.loading[hash] = {"done": len(self._partial.get(hash, b"")), "total": 0, "error": ""}
        self._jobs.append({"kind": "down", "hash": hash, "name": name})
        self._kick()
        return True

    # --- lines from the link -------------------------------------------------------

    def take(self, line: str) -> bool:
        if self.queue is None:
            return False
        p = line.split()
        if not p:
            return False
        if p[0] == "//BF" and len(p) == 5 and p[2] in ("z", "r") and isnum(p[3]) and isnum(p[4]):
            q, h, how, off, total = self.queue, p[1], p[2], int(p[3]), int(p[4])
            n = max(0, total - off)
            if total > FILE_MAX + 64:               # CR96: no board file is that big
                log.warning("file %s: %d bytes announced - link dropped", h, total)
                self.core.link.disconnect()
                return True
            if h != self.current:
                self.core.link.splitter.expect(n, lambda _data: None)
                return True
            prog = self.loading.get(h)
            if prog is not None:
                prog["total"] = total

            def progress(got: int) -> None:
                if prog is not None:
                    prog["done"] = off + got
                    self.core._touch()
            self.core.link.splitter.expect(
                n, lambda data: q.put_nowait(("data", h, off, total, data, how)), progress)
            return True
        if p[0] in ("//FGO", "//FOK", "//NOBFILE") or (p[0] == "//ERR" and p[1:2] == ["file"]):
            self.queue.put_nowait(("line", line))
            return True
        return False

    # --- the transfers ---------------------------------------------------------------

    def _check(self) -> str | None:
        if self.core.state != "online" or not self.core.caps:
            return "not connected"
        if "BFILE" not in self.core.caps:
            return "the TinyBox does not offer files (update it)"
        return None

    async def _wait_free(self) -> None:
        await super()._wait_free()
        while self.core.images.busy:                 # one binary transfer at a time
            await asyncio.sleep(0.5)

    def status(self, hashes: set[str]) -> dict:
        return {"have": sorted(h for h in hashes if self.store.has(h)),
                "loading": {h: v for h, v in self.loading.items() if h in hashes},
                "upload": self.upload, "max": FILE_MAX}

    async def _upload(self, job: dict) -> None:
        h, data, how = job["hash"], job["data"], job["how"]
        up = self.upload if self.upload and self.upload["hash"] == h else None
        why = self._check() or (None if self.core.board else "not in a board")
        if why:
            self._fail(job, why)
            return
        progress = None
        try:
            self.core._send(f"//FPUT {h} {how} {len(data)}")
            self.core.hold_lines(True)
            while True:
                item = await self._answer(progress)
                if item[0] != "line":
                    continue
                p = item[1].split()
                if p[0] == "//FOK" and p[1:2] == [h]:
                    if progress is None:
                        self.core.say(job["line"])       # the TinyBox had it already
                        if up:
                            up["known"] = True
                    break
                if p[0] == "//FGO" and p[1:2] == [h] and len(p) == 3 and isnum(p[2]):
                    progress = await self._send_all(data, int(p[2]), job["line"], up)
                    continue
                if p[0] == "//ERR":
                    raise ConnectionError(_reason(item[1]))
        except ConnectionError as exc:
            self._fail(job, str(exc))
            return
        finally:
            self.core.hold_lines(False)
        if up:
            up.update(state="done", sent=len(data))
        self.core._touch()

    async def _download(self, job: dict) -> None:
        h = job["hash"]
        why = self._check()
        if why:
            self._fail(job, why)
            return
        have = self._partial.get(h, bytearray())
        self.current = h
        how = "r"
        try:
            self.core._send(f"//FGET {h} {len(have)}" if have else f"//FGET {h}")
            while True:
                item = await self._answer()
                if item[0] == "data" and item[1] == h:
                    _, _, off, total, data, how = item
                    if off != len(have):
                        have = bytearray()
                        if off != 0:
                            raise ConnectionError("bad offset")
                    have += data
                    break
                if item[0] == "line":
                    if item[1].startswith("//NOBFILE"):
                        self._partial.pop(h, None)
                        raise ConnectionError("not available any more")
                    if item[1].startswith("//ERR"):
                        raise ConnectionError(_reason(item[1]))
        except ConnectionError as exc:
            if "lost" in str(exc) or "answer" in str(exc):
                self._partial[h] = have
            self._fail(job, str(exc))
            return
        finally:
            self.current = None
        self._partial.pop(h, None)
        blob = bytes(have)
        try:
            data = await asyncio.to_thread(lzhuf.decompress, blob) if how == "z" else blob
        except Exception:                            # damaged LZHUF
            self._fail(job, "damaged, try again")
            return
        if len(data) > FILE_MAX or chatimg.image_hash(data) != h:
            self._fail(job, "damaged, try again")
            return
        why = filecheck.content_verdict(data)
        if why:
            self._fail(job, why)
            return
        self.store.put(h, data)
        self.loading.pop(h, None)
        log.info("board file %s fetched (%d bytes)", h, len(data))
        self.core._touch()


def _reason(line: str) -> str:
    p = line.split()
    code = p[2] if len(p) > 2 else "error"
    text = {"no_files": "no files in this board", "too_large": "too large",
            "busy": "another station is uploading the same file - try again later",
            "unknown": "the TinyBox does not know the file", "program": "program files are "
            "not allowed", "syntax": "refused", "not_started": "not started"}.get(code, code)
    if code == "too_large" and len(p) > 3:
        text += f" (max {p[3]} bytes as sent)"
    return text
