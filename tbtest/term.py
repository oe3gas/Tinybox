"""Terminal user: AX.25 over AXUDP like a terminal program, types mailbox commands.

Own AX.25 layer 2 of prcore (KissPort with an AXUDP endpoint) under the user's
call; the only peer is the test box. Input is read like a human reads it:
wait for the prompt (or a question without line end), then type.
"""

from __future__ import annotations

import asyncio
import re
import time

from prcore import axudp
from prcore.ax25.link import Ax25Link, LinkCfg
from prcore.kissport import KissPort

from .ledger import Ledger
from .user import ActionError, User

PROMPT_RE = re.compile(r"TinyBox (?:SYSOP )?\([A-Z,?]+\) > ")
QUESTION_RE = re.compile(r"(Your first name|Your locator \(e\.g\. JN88EP\)|"
                         r"Your home BBS \(e\.g\. OE3XSR\)): ")
LIST_ROW_RE = re.compile(r"^\s*(\d+) ([PB])([NY])(.) +(\d+) (\S+)\s+(\S*)\s+(\S+)\s+"
                         r"\d{6} \d\d:\d\d (.*)$")
READ_HEAD_RE = re.compile(r"^Msg# (\d+)  Type/Status:")
CHAT_LINE_RE = re.compile(r"^([A-Z0-9]{1,6}(?:-\d{1,2})?): (.*)$")

AX_FAST = {"paclen": 256, "maxframe": 32, "t1_sec": 3.0, "n2": 10,   # no airtime
           "air_baud": 0, "txdelay_ms": 0}


def link_cfg(ax: dict) -> LinkCfg:
    """AX.25 over AXUDP, the same rule as the box's [axudp] and the client's
    [tinybox] axudp_*: T1 from t1_sec up to 4 times that (at least 10 s)."""
    t1, air = ax["t1_sec"], ax.get("air_baud", 0)
    return LinkCfg(paclen=ax["paclen"], maxframe=min(7, ax["maxframe"]),
                   maxframe_ext=ax["maxframe"], n2=ax["n2"], version="2.2",
                   srt_init_sec=t1 / 2, t1_min_sec=t1, t1_max_sec=max(t1 * 4, 10.0),
                   t2_sec=1.5 if air else 0.05, t3_sec=300.0, air_baud=air or 10_000_000,
                   txdelay_sec=ax.get("txdelay_ms", 0) / 1000,
                   max_rx_info=max(512, ax["paclen"]))


class _Port(KissPort):
    def __init__(self, user: "TermUser", listen_port: int, box: str, box_port: int,
                 ax: dict) -> None:
        peers = {box: axudp.Peer(box, "127.0.0.1", box_port)}
        super().__init__(user.call, "127.0.0.1", listen_port, link_cfg(ax),
                         half_duplex=ax.get("air_baud", 0) > 0,
                         transport=lambda on_frame: axudp.AxudpEndpoint(
                             "127.0.0.1", listen_port, peers, on_frame,
                             hear=user.call if ax.get("air_baud") else None))
        self.user = user

    def accept_incoming(self, link: Ax25Link) -> bool:
        return False                         # nobody connects to a test user

    def on_link_event(self, link: Ax25Link, name: str, arg) -> None:
        self.user._event(name, arg)


class TermUser(User):
    kind = "T"

    def __init__(self, call: str, box: str, box_port: int, listen_port: int,
                 ledger: Ledger, timeout: float = 60.0, ax: dict | None = None) -> None:
        super().__init__(call, box, ledger, timeout)
        self.port = _Port(self, listen_port, box, box_port, ax or AX_FAST)
        self.link: Ax25Link | None = None
        self.buf = ""                        # everything received since the connect
        self.pos = 0                         # what expect() has consumed
        self._line = ""                      # incomplete last line (chat parsing)
        self._wake = asyncio.Event()
        self._state = "offline"
        self._task: asyncio.Task | None = None
        self.board: str | None = None
        self.nudge_sec = max(10.0, timeout / 4)    # silence before "Enter" (see expect)
        self.nudges = 0

    # --- port and link -----------------------------------------------------------------

    async def start(self) -> None:
        self._task = asyncio.create_task(self.port.run())
        await asyncio.wait_for(self.port.connected.wait(), 10)

    async def close(self) -> None:
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)

    @property
    def connected(self) -> bool:
        return self._state == "online"

    def _event(self, name: str, arg) -> None:
        if name == "connected":
            self._state = "online"
        elif name == "disconnected":
            self._state = "offline"
            self.link = None
            if self.board is not None:
                self.ledger.left(self.call)
                self.board = None
        elif name == "data":
            text = bytes(arg).decode("utf-8", "replace") if not isinstance(arg, str) else arg
            text = text.replace("\r\n", "\r").replace("\n", "\r")
            self.buf += text.replace("\r", "\n")
            self._lines(text)
        self._wake.set()

    def _lines(self, text: str) -> None:
        """Complete lines: chat lines of the others go to the ledger."""
        self._line += text
        *done, self._line = self._line.split("\r")
        if self.board is None:
            return
        for line in done:
            m = CHAT_LINE_RE.match(line)
            if m and m.group(1) != self.call:
                self.ledger.chat_heard(self.call, line)

    def _send(self, text: str) -> None:
        if self.link is None or not self.connected:
            raise ActionError("not connected")
        self.link.send(text.encode("utf-8"), self.port.now())
        self.port.service(self.link)

    def line(self, text: str) -> None:
        self._send(text + "\r")

    async def expect(self, pattern: re.Pattern | str, timeout: float | None = None,
                     nudge: bool = True) -> tuple[str, re.Match]:
        """Wait until pattern appears after what was read; returns (text before, match).
        nudge: after long silence press Enter - never while a message is being written
        (the empty line would become its subject or a line of its text)."""
        rx = re.compile(pattern) if isinstance(pattern, str) else pattern
        end = time.monotonic() + (timeout or self.timeout)
        quiet_since = time.monotonic()
        seen = len(self.buf)
        while True:
            m = rx.search(self.buf, self.pos)
            if m:
                before = self.buf[self.pos:m.start()]
                self.pos = m.end()
                return before, m
            if not self.connected and self._state == "offline" and self.link is None:
                raise ActionError(f"link gone while waiting for {rx.pattern!r}")
            now = time.monotonic()
            left = end - now
            if left <= 0:
                tail = self.buf[self.pos:][-120:].replace("\n", " | ")
                raise ActionError(f"timeout waiting for {rx.pattern!r} - got: {tail!r}")
            if len(self.buf) != seen:
                seen, quiet_since = len(self.buf), now
            elif nudge and self.connected and now - quiet_since >= self.nudge_sec:
                # nothing comes: the answer may have been lost with a link reset
                # ("data in flight may be lost") - a human presses Enter
                self.nudges += 1
                self.line("")
                quiet_since = now
            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(),
                                       min(left, max(1.0, self.nudge_sec / 2)))
            except asyncio.TimeoutError:
                pass

    async def cmd(self, text: str, timeout: float | None = None,
                  keep_empty: bool = False) -> list[str]:
        """A mailbox command; returns the output lines up to the next prompt
        (without the abort hint of long output; empty lines only if keep_empty)."""
        self.pos = len(self.buf)             # what came before is old (e.g. a prompt after Enter)
        self.line(text)
        while True:
            out, _ = await self.expect(PROMPT_RE, timeout)
            if out.strip():                  # an empty answer: a stray prompt, not ours
                break
        lines = out.split("\n")
        if lines and lines[-1] == "":
            lines.pop()                      # the line end before the prompt
        lines = [ln for ln in lines if not (ln.startswith("*** ") and "lines follow" in ln)]
        return lines if keep_empty else [ln for ln in lines if ln.strip()]

    # --- connect / disconnect -----------------------------------------------------------

    async def connect(self) -> None:
        if self.connected:
            return
        self.buf, self.pos, self._line = "", 0, ""
        link = self.port.open_link(self.box)
        self.link = link
        self._state = "connecting"
        link.connect(self.port.now())
        self.port.service(link)
        end = time.monotonic() + self.timeout
        while self._state == "connecting":
            if time.monotonic() > end:
                link.disconnect(self.port.now())
                self.port.service(link)
                self.link, self._state = None, "offline"
                raise ActionError("no answer to the connect")
            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(), 1)
            except asyncio.TimeoutError:
                pass
        if not self.connected:
            raise ActionError("connect refused")
        # welcome, maybe the profile questions (first login), then the prompt
        while True:
            _, m = await self.expect(re.compile(PROMPT_RE.pattern + "|" + QUESTION_RE.pattern))
            q = m.group(0)
            if PROMPT_RE.fullmatch(q):
                break
            if q.startswith("Your first name"):
                self.line("Tester")
            elif q.startswith("Your locator"):
                self.line("JN88EP")
            else:
                self.line(self.box.split("-")[0])

    async def drop(self) -> None:
        """After a failed action the session may be anywhere (half a message, a
        question of the box): take the link down, the next connect starts clean."""
        link = self.link
        if link is None or not self.connected:
            return
        link.disconnect(self.port.now())
        self.port.service(link)
        end = time.monotonic() + 30
        while self.connected and time.monotonic() < end:
            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(), 1)
            except asyncio.TimeoutError:
                pass

    async def disconnect(self) -> None:
        if not self.connected:
            return
        if self.board is not None:
            await self.chat_leave()
        self.line("B")
        await self.expect("73, bye")
        end = time.monotonic() + self.timeout
        while self.connected and time.monotonic() < end:     # the box takes the link down
            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(), 1)
            except asyncio.TimeoutError:
                pass
        if self.connected:
            raise ActionError("the box did not take the link down after B")

    # --- mail ------------------------------------------------------------------------------

    async def send_msg(self, type: str, to: str) -> None:
        m = self.ledger.new_msg(self.call, type, to, self.kind)
        self.line(f"SB {to}" if type == "B" else f"SP {to}")
        await self.expect("Subject: ", nudge=False)
        self.line(m.subject)
        await self.expect(r"end with /EX", nudge=False)
        self._send("\r".join(m.body.split("\n")) + "\r/EX\r")
        out, _ = await self.expect(PROMPT_RE)
        found = re.search(r"Msg (\d+) saved\.", out)
        if found is None:
            raise ActionError(f"not stored: {out.strip()[-120:]!r}")
        self.ledger.stored(m, int(found.group(1)))

    async def _list(self, command: str) -> list[dict]:
        rows = []
        for ln in await self.cmd(command):
            m = LIST_ROW_RE.match(ln)
            if m:
                rows.append({"id": int(m.group(1)), "type": m.group(2), "status": m.group(3),
                             "to": m.group(6), "from": m.group(8), "subject": m.group(9)})
        return rows

    async def read_msg(self, msg_id: int) -> str:
        """R n -> the text of the message."""
        lines = await self.cmd(f"R {msg_id}", keep_empty=True)
        if any(ln.startswith("No such message") for ln in lines):
            raise ActionError(f"R {msg_id}: no such message")
        try:
            start = next(i for i, ln in enumerate(lines) if ln.startswith("Subject:"))
            end = next(i for i, ln in enumerate(lines) if ln.startswith("[End of message"))
        except StopIteration:
            raise ActionError(f"R {msg_id}: no complete message") from None
        return "\n".join(lines[start + 1:end])

    async def read_mail(self, limit: int | None = 3) -> tuple[int, int]:
        """Read what this user still has to check: personal mail (LM), then
        bulletins (L> TBTEST). Returns (read, corrupt)."""
        todo = {m.id: m for m in self.ledger.unread_for(self.call)}
        if not todo:
            return 0, 0
        listed = await self._list("LM")
        if any(m.type == "B" for m in todo.values()):
            listed += await self._list("L> TBTEST")
        ids = [r["id"] for r in listed if r["id"] in todo]
        missing = [i for i, m in todo.items() if i not in ids and m.type == "P"]
        if missing:
            raise ActionError(f"not in LM: {missing[:5]}")
        n = bad = 0
        for msg_id in sorted(ids)[:limit]:
            key, ok = self.ledger.read_by(self.call, await self.read_msg(msg_id))
            if key is None:
                raise ActionError(f"R {msg_id}: no testbed marker")
            n += 1
            bad += 0 if ok else 1
        if bad:
            raise ActionError(f"{bad} of {n} texts wrong (checksum)")
        return n, bad

    async def kill(self) -> bool:
        cand = self.ledger.killable(self.call)
        if not cand:
            return False
        m = self.ledger.rng.choice(cand)
        lines = await self.cmd(f"K {m.id}")
        if not any(f"Msg {m.id} killed." in ln for ln in lines):
            raise ActionError(f"K {m.id}: {' / '.join(lines)[:120]!r}")
        m.killed = True
        lines = await self.cmd(f"R {m.id}")
        if not any(ln.startswith("No such message") for ln in lines):
            raise ActionError(f"R {m.id} after K still shows the message")
        return True

    # --- other commands -------------------------------------------------------------------

    INFO = [("V", r"^TinyBox \S+ - local mailbox"),
            ("H", r"^TinyBox commands:"),
            ("L", r"MSG# TS|No messages\."),
            ("LB", r"MSG# TS|No messages\."),
            ("LP", r"MSG# TS|No messages\."),
            ("F tbt", r"message\(s\) with 'tbt'|Nothing found"),
            ("I {other}", r"^{otherbase}: name|^No profile for {otherbase}\."),
            ("N Tester", r"^{base}: name Tester"),
            ("NL JN88EP", r"^{base}: name .*locator JN88EP"),
            ("J", r"^Call +Last seen|No stations logged"),
            ("QSO", r"^Connect \(UTC\)|No connects logged"),
            ("C", r"^ #  BOARD"),
            ("XYZZY", r"^Unknown command")]

    async def info(self, other: str) -> str:
        cmd, want = self.ledger.rng.choice(self.INFO)
        fill = {"other": other, "otherbase": other.split("-")[0],
                "base": self.call.split("-")[0]}
        cmd, want = cmd.format(**fill), want.format(**fill)
        lines = await self.cmd(cmd)
        if not any(re.search(want, ln) for ln in lines):
            raise ActionError(f"{cmd}: unexpected answer {' / '.join(lines)[:120]!r}")
        return cmd.split()[0]

    # --- chat -----------------------------------------------------------------------------

    async def chat_join(self, board: str) -> None:
        self.line(f"C {board}")
        await self.expect(rf"\*\*\* Chat board {board} ")
        await self.expect(r"/Q back to the mailbox\.")
        self.board = board
        self.ledger.joined(self.call, board)

    async def chat_say(self, text: str) -> None:
        self.line(text)

    async def chat_leave(self) -> None:
        if self.board is None:
            return
        self.ledger.left(self.call)
        self.line("/Q")
        try:          # lines sent on before the box got /Q still come and are counted
            await self.expect(r"Left chat \S+, back in the mailbox\.")
        finally:
            self.board = None
        await self.expect(PROMPT_RE)
