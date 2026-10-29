"""One test run: start the dummy radio and the test box, let the users work,
check end to end, write the report."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import string
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import VERSION, report
from .bed import RUBRIC, Bed
from .box import Air, TestBox, busy_ports
from .client import ClientUser
from .ledger import Ledger
from .term import TermUser
from .user import ActionError, User

log = logging.getLogger("tbtest")

# function -> (who can do it, weight when a user picks his next action, description)
FUNCS = {
    "conn": ("TC", 0, "connect, log in, disconnect - a new session every few actions"),
    "send": ("TC", 3, "personal mail to another test user"),
    "bull": ("TC", 1, f"bulletin to the rubric {RUBRIC}"),
    "read": ("TC", 3, "read own mail and bulletins, compare the checksum"),
    "kill": ("TC", 1, "delete read personal mail, check it is gone"),
    "info": ("T", 2, "other commands: V H L LB LP F I N NL J QSO C, an unknown one"),
    "chat": ("TC", 2, "join a board, write lines, leave - every line must reach everybody there"),
    "img": ("C", 1, "picture into a board; the other clients there fetch and compare it"),
}
CHAT_BOARDS = [("TREFF", 6), ("RUNDE", 3), ("TECH", 2)]
IMG_BOARDS = ["TREFF", "TECH"]               # RUNDE is live: no pictures


@dataclass
class Options:
    users: int = 4
    terminals: int | None = None             # None = half (rounded up)
    funcs: list[str] = field(default_factory=lambda: list(FUNCS))
    duration: float = 300.0                  # s
    rounds: int = 0                          # actions per user, 0 = only the time counts
    think: tuple[float, float] = (2.0, 10.0)
    chat_stay: tuple[float, float] = (15.0, 45.0)
    seed: int | None = None
    timeout: float = 60.0
    final: bool = True                       # read everything at the end
    fresh: bool = False


@dataclass
class Rec:
    func: str
    call: str
    kind: str
    t: float                                 # seconds since the start
    secs: float
    ok: bool
    idle: bool = False                       # nothing to do (e.g. no mail to read)
    detail: str = ""
    error: str = ""


def run_id() -> str:
    """Short id of this run - in every key, subject and chat line."""
    t = int(time.time()) % (36 ** 4)
    digits = string.digits + string.ascii_lowercase
    out = ""
    for _ in range(4):
        t, r = divmod(t, 36)
        out = digits[r] + out
    return out


class Run:
    def __init__(self, bed: Bed, opt: Options, folder: Path, quiet: bool = False) -> None:
        self.bed, self.opt, self.folder = bed, opt, folder
        self.quiet = quiet
        self.id = run_id()
        self.seed = opt.seed if opt.seed is not None else random.randrange(1 << 30)
        self.rng = random.Random(self.seed)
        self.ledger = Ledger(self.id, random.Random(self.seed + 1))
        self.recs: list[Rec] = []
        self.users: list[User] = []
        self.t0 = time.monotonic()
        self.deadline = 0.0
        self.stopping = False
        self.aborted = False
        self.air: Air | None = None
        self.box: TestBox | None = None
        self.counts: dict[str, int] = {}

    # --- helpers ---------------------------------------------------------------------------

    def say(self, text: str) -> None:
        if not self.quiet:
            print(text, flush=True)
        log.info("%s", text)

    def elapsed(self) -> float:
        return time.monotonic() - self.t0

    def stamp(self) -> str:
        s = int(self.elapsed())
        return f"{s // 60:02d}:{s % 60:02d}"

    async def measure(self, u: User, func: str, coro, detail=None) -> Rec:
        start = time.monotonic()
        rec = Rec(func, u.call, u.kind, round(start - self.t0, 2), 0.0, True)
        u.status = func
        try:
            result = await asyncio.wait_for(coro, self.opt.timeout * 3)
            if detail is not None:
                rec.detail, rec.idle = detail(result)
        except ActionError as exc:
            rec.ok, rec.error = False, str(exc)
        except asyncio.TimeoutError:
            rec.ok, rec.error = False, "hard timeout"
        except (ConnectionError, OSError) as exc:
            rec.ok, rec.error = False, f"{type(exc).__name__}: {exc}"
        rec.secs = round(time.monotonic() - start, 3)
        u.status = "idle"
        self.recs.append(rec)
        self.counts[func] = self.counts.get(func, 0) + 1
        if not rec.ok:
            u.last_error = rec.error
            self.say(f"  ! [{self.stamp()}] {u.label} {func}: {rec.error}")
        return rec

    def done(self, u: User, actions: int) -> bool:
        if self.stopping or time.monotonic() >= self.deadline:
            return True
        return bool(self.opt.rounds) and actions >= self.opt.rounds

    def pick(self, u: User) -> str | None:
        funcs = [f for f in self.opt.funcs if f != "conn" and u.kind in FUNCS[f][0]]
        if not funcs:
            return None
        return self.rng.choices(funcs, [FUNCS[f][1] for f in funcs])[0]

    def others(self, u: User) -> list[str]:
        return [x.call for x in self.users if x is not u]

    async def think(self) -> None:
        await asyncio.sleep(self.rng.uniform(*self.opt.think))

    # --- the actions ----------------------------------------------------------------------

    async def action(self, u: User, func: str) -> None:
        if func == "send":
            to = self.rng.choice(self.others(u) or [u.call])
            await self.measure(u, "send", u.send_msg("P", to))
        elif func == "bull":
            await self.measure(u, "bull", u.send_msg("B", RUBRIC))
        elif func == "read":
            await self.measure(u, "read", u.read_mail(3),
                               lambda r: (f"{r[0]} read", r[0] == 0))
        elif func == "kill":
            await self.measure(u, "kill", u.kill(), lambda did: ("", not did))
        elif func == "info":
            other = self.rng.choice(self.others(u) or [u.call])
            await self.measure(u, "info", u.info(other), lambda cmd: (cmd, False))
        elif func == "chat":
            await self.chat(u, self.board_for(u, [b for b, _ in CHAT_BOARDS],
                                              [w for _, w in CHAT_BOARDS]), image=False)
        elif func == "img":
            await self.chat(u, self.board_for(u, IMG_BOARDS, [1] * len(IMG_BOARDS)),
                            image=True)

    def board_for(self, u: User, boards: list[str], weights: list[int]) -> str:
        """Half of the time where the others are (people go where the talk is),
        otherwise a board by its weight."""
        busy = {b: sum(1 for x in self.users if x is not u and x.board == b) for b in boards}
        best = max(boards, key=lambda b: busy[b])
        if busy[best] and self.rng.random() < 0.5:
            return best
        return self.rng.choices(boards, weights)[0]

    async def chat(self, u: User, board: str, image: bool) -> None:
        """Join, stay a while and write (or send a picture), leave. Clients also
        fetch pictures of the others they see meanwhile (if img is chosen)."""
        rec = await self.measure(u, "chat", u.chat_join(board), lambda _: (board, False))
        if not rec.ok:
            return
        stay = self.rng.uniform(*self.opt.chat_stay)
        end = time.monotonic() + stay
        n_lines = self.rng.randint(1, 4)
        times = sorted(self.rng.uniform(1.0, max(1.5, stay - 2.5)) for _ in range(n_lines))
        start = time.monotonic()
        try:
            if image:
                key = self.ledger.chat_key(u.call)
                size = self.rng.choice((1500, 3000, 5000, 7500))
                await self.measure(u, "img", u.send_image(key, size),
                                   lambda h: (f"{size} B", False))
                times = times[:1]
            for at in times:
                await asyncio.sleep(max(0.0, start + at - time.monotonic()))
                if not u.connected or u.board is None:
                    raise ActionError("left the board unexpectedly")
                key = self.ledger.chat_key(u.call)
                text = f"tbt {key} " + " ".join(self.rng.choice(("73", "qrv", "test", "hi",
                                                                  "wx", "ant", "rig"))
                                                 for _ in range(self.rng.randint(1, 8)))
                self.ledger.said(u.call, board, text, key)
                await u.chat_say(text)
                await self.fetch_images(u)
            while time.monotonic() < end and u.connected:
                await asyncio.sleep(min(1.0, end - time.monotonic()))
                await self.fetch_images(u)
        except ActionError as exc:
            self.recs.append(Rec("chat", u.call, u.kind, round(self.elapsed(), 2), 0.0,
                                 False, error=str(exc)))
            self.say(f"  ! [{self.stamp()}] {u.label} chat: {exc}")
        finally:
            if u.connected and u.board is not None:
                await self.measure(u, "chat_out", u.chat_leave())
            else:
                self.ledger.left(u.call)

    async def fetch_images(self, u: User) -> None:
        if isinstance(u, ClientUser) and u.pending_images():
            await self.measure(u, "img_get", u.fetch_images(1), lambda n: (f"{n}", n == 0))

    # --- one user ---------------------------------------------------------------------------

    async def user_loop(self, u: User) -> None:
        await asyncio.sleep(self.rng.uniform(0, min(5.0, self.opt.think[1])))
        per_session = "conn" in self.opt.funcs
        actions = 0
        while not self.done(u, actions):
            rec = await self.measure(u, "conn", u.connect())
            if not rec.ok:
                await self.think()
                continue
            n = self.rng.randint(1, 5) if per_session else 1 << 30
            for _ in range(n):
                if self.done(u, actions):
                    break
                func = self.pick(u)
                if func is not None:
                    await self.action(u, func)
                    actions += 1
                if not u.connected:
                    break
                await self.think()
            if u.connected:
                await self.measure(u, "disc", u.disconnect())

    async def final(self, u: User) -> None:
        """At the end: read everything that is still unread for this user."""
        if not self.ledger.unread_for(u.call):
            return
        rec = await self.measure(u, "conn", u.connect())
        if not rec.ok:
            return
        for _ in range(50):
            if not self.ledger.unread_for(u.call):
                break
            r = await self.measure(u, "final", u.read_mail(None),
                                   lambda r: (f"{r[0]} read", r[0] == 0))
            if not r.ok or r.idle:
                break
        await self.measure(u, "disc", u.disconnect())

    # --- live line ---------------------------------------------------------------------------

    async def watch_box(self) -> None:
        """The test box stopped by itself: no point going on."""
        while self.box.died is None:
            await asyncio.sleep(0.5)
        self.say(f"  ! [{self.stamp()}] the test box stopped (exit code {self.box.died}) - "
                 "ending the run, see tinybox.out")
        self.stopping = True

    async def ticker(self) -> None:
        while True:
            await asyncio.sleep(15)
            online = sum(1 for u in self.users if u.connected)
            fails = sum(1 for r in self.recs if not r.ok)
            counts = " ".join(f"{f} {n}" for f, n in sorted(self.counts.items()))
            inboard = sum(1 for u in self.users if u.board)
            self.say(f"[{self.stamp()}] online {online}/{len(self.users)}, in chat {inboard}"
                     f" | {counts} | failed {fails}")

    # --- the run -------------------------------------------------------------------------------

    def make_users(self) -> None:
        n = self.opt.users
        t = (n + 1) // 2 if self.opt.terminals is None else self.opt.terminals
        for i, call in enumerate(self.bed.users[:n]):
            port = self.bed.port_of(call)
            if i < t:
                u: User = TermUser(call, self.bed.box_call, self.bed.box_port, port,
                                   self.ledger, self.opt.timeout)
            else:
                u = ClientUser(call, self.bed.box_call, self.bed.box_port, port,
                               self.bed.air_port, self.bed.user_dir(call), self.ledger,
                               self.opt.timeout)
                self.ledger.client_calls.add(call)
            self.users.append(u)

    async def run(self) -> dict:
        busy = busy_ports(self.bed, self.opt.users)
        if busy:
            raise RuntimeError("ports in use (is a test box still running?): " + ", ".join(busy))
        self.folder.mkdir(parents=True, exist_ok=True)
        self.air = Air(self.bed.air_port)
        await self.air.start()
        self.box = TestBox(self.bed, self.folder / "tinybox.out")
        ticker = None
        started = time.time()
        try:
            await self.box.start()
            self.say(f"test box {self.bed.box_call} up - web GUI: {self.box.web_url or '-'}")
            self.make_users()
            for u in self.users:
                await u.start()
            kinds = ", ".join(u.label for u in self.users)
            self.say(f"run {self.id}: {len(self.users)} users ({kinds}), functions "
                     f"{','.join(self.opt.funcs)}, "
                     + (f"{self.opt.rounds} actions each, at most " if self.opt.rounds else "")
                     + f"{report.human(self.opt.duration)}, seed {self.seed}")
            self.t0 = time.monotonic()
            self.deadline = self.t0 + self.opt.duration
            ticker = asyncio.create_task(self.ticker())
            watcher = asyncio.create_task(self.watch_box())
            try:
                await asyncio.gather(*(self.user_loop(u) for u in self.users))
                if self.opt.final and self.ledger.msgs and not self.stopping:
                    self.say(f"[{self.stamp()}] actions done - final check: everybody reads "
                             "what is still unread")
                    await asyncio.gather(*(self.final(u) for u in self.users))
            except asyncio.CancelledError:
                self.aborted = True
                task = asyncio.current_task()
                if task is not None and hasattr(task, "uncancel"):
                    task.uncancel()
                self.say("aborted (Ctrl+C) - writing the report")
        finally:
            if ticker is not None:
                ticker.cancel()
                watcher.cancel()
            for u in self.users:
                try:
                    if u.connected:
                        await asyncio.wait_for(u.disconnect(), 10)
                except Exception:
                    pass
                await u.close()
            await asyncio.sleep(0.5)                   # the last frames to the dummy radio
            await self.box.stop()
            self.air.close()
        result = self.result(started)
        (self.folder / "result.json").write_text(json.dumps(result, indent=1,
                                                            ensure_ascii=False),
                                                 encoding="utf-8")
        text = report.text(result)
        (self.folder / "report.txt").write_text(text, encoding="utf-8")
        return result

    def result(self, started: float) -> dict:
        calls = [u.call for u in self.users]
        return {
            "tbtest": VERSION, "run": self.id, "seed": self.seed,
            "started": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(started)),
            "secs": round(self.elapsed(), 1), "aborted": self.aborted,
            "options": {**{k: v for k, v in asdict(self.opt).items()}},
            "box": {"call": self.bed.box_call, "errors": self.box.n_errors if self.box else 0,
                    "error_lines": self.box.errors if self.box else [],
                    "warnings": self.box.n_warnings if self.box else 0,
                    "warning_lines": self.box.warnings if self.box else [],
                    "out": "tinybox.out", "died": self.box.died if self.box else None},
            "users": [{"call": u.call, "kind": u.kind} for u in self.users],
            "records": [asdict(r) for r in self.recs],
            "verify": self.ledger.verify(calls),
            "air": self.air.summary(self.bed.box_call) if self.air else {},
        }
