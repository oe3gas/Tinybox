"""Client user: the real TinyBox client core (tbclient.core.ClientCore), headless.

Everything the web GUI does goes through the same calls here: connect,
outbox + send_outbox, sync, fetch, open, delete, join/say/leave, images.send.
Each client has its own data folder (users/<CALL>) and its own AXUDP port. Its
radio port points to tbtest's dummy radio - the home box is reached over AXUDP
only.
"""

from __future__ import annotations

import asyncio
import dataclasses
import time
from pathlib import Path

from prcore import chatimg
from tbclient import config as ccfg
from tbclient.core import ClientCore

from .bed import RUBRIC
from .ledger import Ledger
from .user import ActionError, User

# a valid blurhash (4x3 components) for the test pictures
BLURHASH = "LEHV6nWB2yk8pyo0adR*.7kCMdnj"


async def until(cond, timeout: float, what: str, step: float = 0.05) -> None:
    end = time.monotonic() + timeout
    while not cond():
        if time.monotonic() > end:
            raise ActionError(f"timeout: {what}")
        await asyncio.sleep(step)


def make_image(rng, size: int) -> bytes:
    """A 'JPEG' for the test: the right magic bytes, random content. The box and
    the client check the type by its first bytes only and never decode it."""
    body = bytes(rng.getrandbits(8) for _ in range(max(0, size - 6)))
    return b"\xff\xd8\xff\xe0" + body + b"\xff\xd9"


class ClientUser(User):
    kind = "C"

    def __init__(self, call: str, box: str, box_port: int, listen_port: int,
                 air_port: int, data_dir: Path, ledger: Ledger, timeout: float = 60.0,
                 rubric: str = RUBRIC) -> None:
        super().__init__(call, box, ledger, timeout)
        data_dir.mkdir(parents=True, exist_ok=True)
        cfg = dataclasses.replace(
            ccfg.Config(), mycall=call, tinybox_call=box, link="kiss", ui="no",
            auto_connect=False, data_dir=data_dir, update_check=False,
            kiss_host="127.0.0.1", kiss_port=air_port, kiss_status_port=0,
            axudp_host="127.0.0.1", axudp_port=box_port, axudp_listen=listen_port,
            sync_on_login=True)
        self.rubric = rubric
        self.core = ClientCore(cfg)
        self.core.mailbox.subscribe(rubric, True)
        self._task: asyncio.Task | None = None
        add = self.core._add

        def _add(msg: dict) -> None:            # every chat event the client shows
            if msg.get("kind") == "line":
                if msg.get("seq", -1) >= 0:             # live lines; history does not count
                    self.ledger.chat_heard(self.call, msg.get("text", ""))
                if chatimg.parse_ref(msg.get("text", "")):
                    self._seen_lines.append(msg.get("text", ""))   # pictures, history too
            add(msg)
        self.core._add = _add
        self._seen_lines: list[str] = []
        self.fetched: set[str] = set()

    # --- lifecycle -----------------------------------------------------------------------

    async def start(self) -> None:
        self._task = asyncio.create_task(self.core.run())
        await asyncio.wait_for(self.core.udp.agw_up.wait(), 10)

    async def close(self) -> None:
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        try:
            self.core.mailbox.close()
        except Exception:
            pass

    @property
    def connected(self) -> bool:
        return self.core.state == "online" and self.core.handshake_done

    async def connect(self) -> None:
        if self.connected:
            return
        if not await self.core.connect(self.box, ch=1):
            raise ActionError("connect not started")
        await until(lambda: self.core.state == "online" or self.core.state == "offline"
                    and self.core.reason, 20, "link up")
        if self.core.state != "online":
            raise ActionError(f"connect failed: {self.core.reason}")
        await until(lambda: self.core.caps or self.core.state != "online",
                    15, "//OK of the box")
        if not self.core.caps:
            raise ActionError("link lost during the handshake")
        if "SYNC" not in self.core.caps:
            raise ActionError(f"box offers no SYNC (caps {sorted(self.core.caps)})")
        await until(lambda: bool(self.core.boards), 10, "board list")

    async def disconnect(self) -> None:
        if self.core.state == "offline":
            return
        if self.core.board:
            await self.chat_leave()
        await self._sync_idle()
        self.core.disconnect(1)
        await until(lambda: self.core.state == "offline", 15, "link down")
        self.board = None

    async def _sync_idle(self, timeout: float | None = None) -> None:
        await until(lambda: not self.core.sync.running, timeout or self.timeout,
                    "running sync")

    async def _sync(self, scope: str) -> None:
        await self._sync_idle()
        if not self.core.sync.start(scope):
            raise ActionError(f"sync {scope} did not start")
        await self._sync_idle()
        err = self.core.sync.status.get("error")
        if err:
            raise ActionError(f"sync {scope}: {err}")

    # --- mail --------------------------------------------------------------------------

    async def send_msg(self, type: str, to: str) -> None:
        m = self.ledger.new_msg(self.call, type, to, self.kind)
        box = self.core.mailbox
        oid = box.save_out(None, type, to, m.subject, m.body)
        waits = self.core.send_outbox()
        if waits and "next sync" in waits:
            await self._sync_idle()
            if any(o["oid"] == oid for o in box.outbox()):
                self.core.send_outbox()

        def gone() -> bool:
            return not any(o["oid"] == oid for o in box.outbox())

        def error() -> str:
            return next((o["error"] for o in box.outbox() if o["oid"] == oid), "")

        await until(lambda: gone() or error(), self.timeout,
                    "outbox sent" + (f" ({waits})" if waits else ""))
        if not gone():
            raise ActionError(f"outbox: {error()}")
        row = box.db.execute("SELECT id FROM messages WHERE subject=? ORDER BY id DESC",
                             (m.subject,)).fetchone()
        if row is None:
            raise ActionError("sent, but no message number came back")
        self.ledger.stored(m, int(row[0]))

    async def read_mail(self, limit: int | None = 3) -> tuple[int, int]:
        """Sync, fetch the texts still to check, open them (reported read at the
        next sync). Returns (read, corrupt)."""
        todo = {m.id: m for m in self.ledger.unread_for(self.call)}
        if not todo:
            return 0, 0
        await self._sync("login")                     # mail and bulletins
        box = self.core.mailbox
        here = [i for i in sorted(todo) if box.message(i) is not None]
        missing = [i for i in todo if i not in here and todo[i].type == "P"]
        if missing:
            raise ActionError(f"not in the mailbox after sync: {missing[:5]}")
        n = bad = 0
        for msg_id in here[:limit]:
            if box.message(msg_id)["body"] is None:
                err = self.core.sync.fetch(msg_id)
                if err:
                    raise ActionError(f"fetch {msg_id}: {err}")
                await until(lambda: (box.message(msg_id) or {}).get("body") is not None
                            or self.core.sync.status.get("fetch_error"),
                            self.timeout, f"text of {msg_id}")
                if box.message(msg_id)["body"] is None:
                    raise ActionError(f"fetch {msg_id}: {self.core.sync.status['fetch_error']}")
            m = box.open(msg_id)
            key, ok = self.ledger.read_by(self.call, m["body"])
            if key is None:
                raise ActionError(f"message {msg_id}: no testbed marker")
            n += 1
            bad += 0 if ok else 1
        if bad:
            raise ActionError(f"{bad} of {n} texts wrong (checksum)")
        return n, bad

    async def kill(self) -> bool:
        cand = [m for m in self.ledger.killable(self.call)
                if self.core.mailbox.message(m.id) is not None]
        if not cand:
            return False
        m = self.ledger.rng.choice(cand)
        if not self.core.mailbox.delete(m.id):
            raise ActionError(f"delete {m.id}: not in the mailbox")
        await self._sync("mail")
        if m.id in self.core.mailbox.todo("kill"):
            raise ActionError(f"kill {m.id} not confirmed by the box")
        m.killed = True
        await self._sync("mail")                      # it must not come back
        if self.core.mailbox.message(m.id) is not None:
            raise ActionError(f"message {m.id} back after kill")
        return True

    # --- chat --------------------------------------------------------------------------

    def _board_n(self, name: str) -> int:
        for b in self.core.boards:
            if b["name"] == name:
                return b["n"]
        raise ActionError(f"no board {name}")

    async def chat_join(self, board: str) -> None:
        if not self.core.join(self._board_n(board)):
            raise ActionError(f"join {board} refused")
        await until(lambda: self.core.board is not None
                    and self.core.board.get("name") == board, 15, f"//IN {board}")
        self.board = board
        self.ledger.joined(self.call, board)

    async def chat_say(self, text: str) -> None:
        if not self.core.say(text):
            raise ActionError("say refused")

    async def chat_leave(self) -> None:
        if not self.core.board:
            self.board = None
            return
        self.ledger.left(self.call)
        self.core.leave()
        await until(lambda: self.core.board is None or self.core.state != "online",
                    15, "//OUT")
        self.board = None

    async def send_image(self, key: str, size: int) -> str:
        data = make_image(self.ledger.rng, size)
        h = self.core.images.send(data, BLURHASH, caption=f"tbt {key}")
        if h is None:
            raise ActionError("picture refused by the client")
        self.ledger.images[h] = data
        self.fetched.add(h)                           # own picture: nothing to fetch
        self.ledger.said(self.call, self.board or "", f"tbt {key}", key, image=h)
        await until(lambda: (self.core.images.upload or {}).get("state") in ("done", "error"),
                    self.timeout, "picture upload")
        up = self.core.images.upload
        if up["state"] != "done":
            raise ActionError(f"picture upload: {up.get('error')}")
        return h

    def pending_images(self) -> int:
        """Pictures of the others seen in the board, not fetched yet."""
        n = 0
        for text in self._seen_lines:
            ref = chatimg.parse_ref(text)
            if ref and ref[0] in self.ledger.images and ref[0] not in self.fetched:
                n += 1
        return n

    async def fetch_images(self, limit: int = 1) -> int:
        """Pictures of the others seen in the board: fetch and compare (at most limit)."""
        n = 0
        for text in list(self._seen_lines):
            ref = chatimg.parse_ref(text)
            if ref is None:
                continue
            h = ref[0]
            if h in self.fetched or h not in self.ledger.images:
                continue
            if self.ledger.images and self.core.images.store.has(h):
                self.fetched.add(h)                   # own picture
                continue
            self.fetched.add(h)
            if not self.core.images.fetch(h):
                raise ActionError(f"picture {h}: fetch refused")
            await until(lambda: self.core.images.store.has(h)
                        or (self.core.images.loading.get(h) or {}).get("error"),
                        self.timeout, f"picture {h}")
            data = self.core.images.store.get(h)
            ok = data == self.ledger.images[h]
            self.ledger.img_checks.setdefault(h, {})[self.call] = ok
            if not ok:
                err = (self.core.images.loading.get(h) or {}).get("error") or "content differs"
                raise ActionError(f"picture {h}: {err}")
            n += 1
            if n >= limit:
                break
        return n

