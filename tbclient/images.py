"""Small images in the chat (CR12) - the client side.

The browser shrinks the picture (WebP, long side at most 320 px, under the
TinyBox limit) and computes the blurhash; this module keeps the bytes, moves
them over the air and knows what is here. Protocol: tinybox/chatimg.py.

Upload    //IMGPUT <hash> <bytes> -> //IMGGO <hash> <have>, then the bytes
          from <have> on. They are handed to Direwolf in pieces with a pause
          in between (tbclient.conf [images]), and never more than one piece
          waits in Direwolf's queue - so chat lines still get through and
          other stations get the frequency. Then //IMGOK, and the chat line
          with the reference goes out.
Download  //IMG <hash> [<offset>] -> //I <hash> <offset> <total> + the bytes.
          A broken download goes on at the offset next time.

Images are files in <data_dir>/images/<hash> (WebP or JPEG). The web GUI
serves them as /img/<hash>. One transfer at a time, never during a mailbox
sync (both use the same binary channel).
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

from tinybox import chatimg               # reference format, hash, type check

if TYPE_CHECKING:
    from .core import ClientCore

log = logging.getLogger(__name__)

IDLE_SEC = 120            # no answer for this long: the transfer gives up
WAIT_SYNC_SEC = 600       # a transfer waits this long for a running sync
KEEP_DAYS = 60            # local image files older than this are deleted at start


class ImageStore:
    def __init__(self, folder: Path) -> None:
        self.folder = folder

    def path(self, hash: str) -> Path:
        return self.folder / hash

    def has(self, hash: str) -> bool:
        return chatimg.HASH_RE.match(hash) is not None and self.path(hash).is_file()

    def get(self, hash: str) -> bytes | None:
        try:
            return self.path(hash).read_bytes() if self.has(hash) else None
        except OSError:
            return None

    def put(self, hash: str, data: bytes) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path(hash).write_bytes(data)

    def purge(self, days: int = KEEP_DAYS) -> int:
        n = 0
        if not self.folder.is_dir():
            return 0
        limit = time.time() - days * 86400
        for p in self.folder.iterdir():
            try:
                if p.is_file() and p.stat().st_mtime < limit:
                    p.unlink()
                    n += 1
            except OSError:
                pass
        return n


class Images:
    def __init__(self, core: ClientCore, store: ImageStore) -> None:
        self.core = core
        self.store = store
        self.task: asyncio.Task | None = None
        self.queue: asyncio.Queue | None = None          # answers for the running job
        self.upload: dict | None = None                  # the (last) upload for the GUI
        self.loading: dict[str, dict] = {}               # hash -> {done, total, error}
        self._partial: dict[str, bytearray] = {}         # broken downloads, to go on
        self._jobs: list[dict] = []

    @property
    def busy(self) -> bool:
        return self.task is not None and not self.task.done()

    # --- what the GUI asks for ------------------------------------------------

    def send(self, data: bytes, blurhash: str, caption: str = "", prefix: str = "") -> str | None:
        """Keep the picture, queue the upload; the chat line follows when it is
        up. Returns the hash, or None if the data is no image."""
        if chatimg.image_type(data) is None or not data:
            return None
        if not blurhash or chatimg.blurhash_len(blurhash[:1]) != len(blurhash) \
                or any(c not in chatimg.B83 for c in blurhash):
            return None
        h = chatimg.image_hash(data)
        self.store.put(h, data)
        line = f"{prefix}~#{h}{chatimg.size_code(len(data))}{blurhash}"
        if caption.strip():
            line += " " + caption.strip()
        self.upload = {"hash": h, "size": len(data), "sent": 0, "state": "waiting",
                       "error": "", "line": line, "at": time.time()}
        self._jobs.append({"kind": "up", "hash": h, "data": data, "line": line})
        self._kick()
        return h

    def fetch(self, hash: str) -> bool:
        """Tap on a placeholder: get the image from the TinyBox."""
        if not chatimg.HASH_RE.match(hash) or self.store.has(hash):
            return False
        if hash in self.loading and not self.loading[hash].get("error"):
            return True                                  # already on its way
        self.loading[hash] = {"done": len(self._partial.get(hash, b"")), "total": 0,
                              "error": ""}
        self._jobs.append({"kind": "down", "hash": hash})
        self._kick()
        return True

    def status(self, hashes: set[str]) -> dict:
        """For the snapshot: which of the referenced images are here, which are
        loading, and the upload under way."""
        return {"have": sorted(h for h in hashes if self.store.has(h)),
                "loading": {h: v for h, v in self.loading.items() if h in hashes},
                "upload": self.upload}

    def dismiss_upload(self) -> None:
        if self.upload and self.upload["state"] in ("done", "error"):
            self.upload = None

    # --- lines from the link (called by the core first) -------------------------

    def take(self, line: str) -> bool:
        """True if the line belongs to a running transfer."""
        if self.queue is None:
            return False
        p = line.split()
        if not p:
            return False
        if p[0] == "//I" and len(p) == 4 and p[2].isdigit() and p[3].isdigit():
            q, h, off, total = self.queue, p[1], int(p[2]), int(p[3])
            n = max(0, total - off)
            prog = self.loading.get(h)
            if prog is not None:
                prog["total"] = total

            def progress(got: int) -> None:
                if prog is not None:
                    prog["done"] = off + got
                    self.core._touch()
            self.core.link.splitter.expect(n, lambda data: q.put_nowait(("data", h, off, total, data)),
                                           progress)
            return True
        if p[0] in ("//IMGGO", "//IMGOK", "//NOIMG") or (p[0] == "//ERR" and p[1:2] == ["img"]):
            self.queue.put_nowait(("line", line))
            return True
        return False

    def link_lost(self) -> None:
        if self.queue is not None:
            self.queue.put_nowait(("lost",))

    # --- the transfers, one after the other -------------------------------------

    def _kick(self) -> None:
        if not self.busy:
            self.task = asyncio.ensure_future(self._run())
        self.core._touch()

    async def _run(self) -> None:
        while self._jobs:
            job = self._jobs.pop(0)
            self.queue = asyncio.Queue()
            try:
                await self._wait_free()
                if job["kind"] == "up":
                    await self._upload(job)
                else:
                    await self._download(job)
            except asyncio.CancelledError:
                self._fail(job, "cancelled")
                break
            except Exception as exc:          # a bug must not kill the client
                log.exception("image transfer failed")
                self._fail(job, f"internal error: {exc}")
            finally:
                self.queue = None
                self.core._touch()

    def _fail(self, job: dict, why: str) -> None:
        log.warning("image %s %s: %s", job["hash"], job["kind"], why)
        if job["kind"] == "up":
            if self.upload and self.upload["hash"] == job["hash"]:
                self.upload.update(state="error", error=why)
        else:
            self.loading[job["hash"]] = {**self.loading.get(job["hash"], {}), "error": why}

    async def _wait_free(self) -> None:
        start = time.monotonic()
        while self.core.sync.running and time.monotonic() - start < WAIT_SYNC_SEC:
            await asyncio.sleep(0.5)

    async def _answer(self):
        if self.core.state != "online":
            raise ConnectionError("not connected")
        try:
            item = await asyncio.wait_for(self.queue.get(), IDLE_SEC)
        except asyncio.TimeoutError:
            raise ConnectionError("no answer from the TinyBox") from None
        if item[0] == "lost":
            raise ConnectionError("connection lost")
        return item

    def _check(self) -> str | None:
        """Why a transfer cannot start right now (None = go)."""
        if self.core.state != "online" or not self.core.caps:
            return "not connected"
        if "IMG" not in self.core.caps:
            return "the TinyBox does not offer images (update it)"
        return None

    async def _upload(self, job: dict) -> None:
        h, data = job["hash"], job["data"]
        up = self.upload if self.upload and self.upload["hash"] == h else None
        why = self._check()
        if why is None and not self.core.board:
            why = "not in a board"
        if why:
            self._fail(job, why)
            return
        try:
            self.core._send(f"//IMGPUT {h} {len(data)}")
            while True:
                item = await self._answer()
                if item[0] != "line":
                    continue
                p = item[1].split()
                if p[0] == "//IMGOK" and p[1:2] == [h]:
                    break
                if p[0] == "//IMGGO" and p[1:2] == [h] and len(p) == 3 and p[2].isdigit():
                    await self._send_bytes(data, int(p[2]), up)
                    continue
                if p[0] == "//ERR":
                    raise ConnectionError(_reason(item[1]))
        except ConnectionError as exc:
            self._fail(job, str(exc))
            return
        if up:
            up.update(state="done", sent=len(data))
        self.core.say(job["line"])          # the chat line, now that the picture is up
        self.core._touch()

    async def _send_bytes(self, data: bytes, offset: int, up: dict | None) -> None:
        cfg = self.core.cfg
        link = self.core.link
        if up:
            up.update(state="sending", sent=offset)
        while offset < len(data):
            piece = data[offset:offset + cfg.img_piece]
            link.send_bytes(piece)
            offset += len(piece)
            if up:
                up["sent"] = offset
                self.core._touch()
            if offset >= len(data):
                break
            await asyncio.sleep(cfg.img_pause)
            # the piece before must be on air before the next one goes to Direwolf
            for _ in range(60):
                if self.core.state != "online":
                    raise ConnectionError("connection lost")
                if await link.outstanding() <= 1:
                    break
                await asyncio.sleep(1)

    async def _download(self, job: dict) -> None:
        h = job["hash"]
        why = self._check()
        if why:
            self._fail(job, why)
            return
        have = self._partial.get(h, bytearray())
        try:
            self.core._send(f"//IMG {h} {len(have)}" if have else f"//IMG {h}")
            while True:
                item = await self._answer()
                if item[0] == "data" and item[1] == h:
                    _, _, off, total, data = item
                    if off != len(have):
                        have = bytearray()
                        if off != 0:
                            raise ConnectionError("bad offset")
                    have += data
                    break
                if item[0] == "line":
                    if item[1].startswith("//NOIMG"):
                        self._partial.pop(h, None)
                        raise ConnectionError("not available any more")
                    if item[1].startswith("//ERR"):
                        raise ConnectionError(_reason(item[1]))
        except ConnectionError as exc:
            if "lost" in str(exc) or "answer" in str(exc):
                self._partial[h] = have             # go on next time
            self._fail(job, str(exc))
            return
        data = bytes(have)
        self._partial.pop(h, None)
        if chatimg.image_hash(data) != h or chatimg.image_type(data) is None:
            self._fail(job, "damaged, try again")
            return
        self.store.put(h, data)
        self.loading.pop(h, None)
        log.info("image %s fetched (%d bytes)", h, len(data))
        self.core._touch()


def _reason(line: str) -> str:
    """'//ERR img too_large 8192' -> 'too large (max 8192 bytes)'"""
    p = line.split()
    code = p[2] if len(p) > 2 else "error"
    text = {"no_images": "no images in this board", "too_large": "too large",
            "bad_hash": "damaged on the way, try again", "bad_type": "not a WebP/JPEG",
            "unknown": "the TinyBox does not know the image", "not_started": "not started",
            "syntax": "refused"}.get(code, code)
    if code == "too_large" and len(p) > 3:
        text += f" (max {p[3]} bytes)"
    return text
