"""One forward session with a partner mailbox.

F2: connection, SID exchange, choice of protocol, clean end.
F3: receiving. Offers are answered and taken (see receive.py); a message is
    stored only when it arrived completely.
F4: sending (see send.py) and both directions in one session: FBB takes turns
    block by block; in ASCII the caller sends its S commands, then asks for the
    other side's mail with F> (reverse forwarding, W0RLI).

Choice of protocol (concept, section W0RLI):
    both SIDs with F           -> FBB batch
    otherwise, partner has SID -> W0RLI ASCII
    no SID at all              -> ASCII without BIDs

FBB batch: up to 5 "FB" proposals, "F> checksum", answer "FS +-=", then the
accepted messages (title, text, Ctrl-Z) in order. "FF" = nothing to send,
"FQ" = end. W0RLI ASCII: "S? TO @ AT < FROM $BID" -> OK/NO -> title, text,
Ctrl-Z or /EX -> prompt ">" (reverse forwarding: "F>" instead of ">").
Errors: hang up at once without sending anything (W0RLI section 6).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from ..config import PartnerCfg
from ..service import MessageService
from .link import Link
from .protocol import (CTRL_Z, MAX_BLOCK, Proposal, ProtocolError, block_end_ok, checksum,
                       own_sid, parse_fs, parse_proposal, parse_rli_reply, parse_send_cmd,
                       parse_sid)
from .receive import ACCEPT, Receiver
from .send import Sender

log = logging.getLogger("tinybox.forward")

MAX_MESSAGES = 500        # per session; protects against a partner that never stops


class Gone(Exception):
    """The partner hung up."""


@dataclass
class SessionResult:
    partner: str
    master: bool
    transport: str
    mode: str = ""                  # fbb | ascii
    peer_sid: str = ""
    received: list[str] = field(default_factory=list)   # BIDs stored here
    rejected: list[str] = field(default_factory=list)   # BIDs we answered with - / NO
    deferred: list[str] = field(default_factory=list)   # BIDs answered with = (later)
    sent: dict[str, str] = field(default_factory=dict)  # our BIDs -> done/rejected/later
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error

    def _sent_text(self) -> str:
        if not self.sent:
            return "0"
        n = {s: sum(1 for v in self.sent.values() if v == s) for s in ("done", "rejected", "later")}
        return f"{n['done']} (rejected {n['rejected']}, later {n['later']})"

    def summary(self) -> str:
        role = "called" if self.master else "was called by"
        return (f"{role} {self.partner} via {self.transport}, mode {self.mode or '-'}, "
                f"SID {self.peer_sid or '-'}, received {len(self.received)}, "
                f"rejected {len(self.rejected)}, sent {self._sent_text()}"
                + (f", deferred {len(self.deferred)}" if self.deferred else "")
                + (f", ERROR {self.error}" if self.error else ""))


class ForwardSession:
    def __init__(self, bbs_call: str, partner: PartnerCfg, link: Link, *, master: bool,
                 transport: str, service: MessageService) -> None:
        self.bbs_call = bbs_call
        self.p = partner
        self.link = link
        self.master = master
        self.r = SessionResult(partner.call, master, transport)
        self.sid = own_sid(partner.protocol)
        self.rx = Receiver(service, partner.call)
        self.tx = Sender(service, partner.call)
        self.in_message = False

    # --- helpers ----------------------------------------------------------------

    async def _line(self) -> str:
        line = await self.link.readline(self.p.timeout)
        if line is None:
            raise Gone("connection closed by partner")
        return line

    async def _command(self) -> str:
        """Next non-empty line; ';' lines are null commands (W0RLI feature I)."""
        while True:
            line = (await self._line()).strip()
            if line and not line.startswith(";"):
                return line

    async def _wait_prompt(self) -> None:
        while not (await self._command()).endswith(">"):
            pass

    def _w(self, *lines: str) -> None:
        self.link.write_lines(*lines)

    def _set_mode(self, mode: str, sid_line: str = "") -> None:
        self.r.mode = self.rx.mode = mode
        if sid_line:
            self.r.peer_sid = sid_line
            self.rx.peer_sid = parse_sid(sid_line)

    # --- entry ----------------------------------------------------------------

    async def run(self) -> SessionResult:
        log.info("%s: forward session %s %s", self.p.call,
                 "to" if self.master else "from", self.r.transport)
        try:
            await (self._master() if self.master else self._slave())
        except asyncio.TimeoutError:
            self.r.error = f"timeout ({self.p.timeout} s)"
        except Gone as exc:
            # in ASCII mode hanging up is the normal end - except inside a message
            if not self.r.mode or self.r.mode == "fbb" or self.in_message:
                self.r.error = str(exc) + (" (in a message)" if self.in_message else "")
        except ProtocolError as exc:
            self.r.error = f"protocol: {exc}"       # W0RLI: hang up, send nothing
        finally:
            await self.link.drain()
            await self.link.close()
        (log.info if self.r.ok else log.warning)("%s: %s", self.p.call, self.r.summary())
        return self.r

    async def _master(self) -> None:
        sid = None
        while sid is None:                          # node texts may come first
            line = await self._command()
            sid = parse_sid(line)
        await self._wait_prompt()
        self._w(self.sid)
        await self.link.drain()
        if sid.has("F") and self.p.protocol == "fbb":
            self._set_mode("fbb", line)
            await self._fbb(our_turn=True)
        else:
            self._set_mode("ascii", line)
            await self._wait_prompt()               # short prompt after our SID
            for m in self.tx.pending():
                await self._ascii_send(m)
                await self._wait_prompt()           # '>' after each message (also after NO)
            await self._ascii_reverse()

    async def _slave(self) -> None:
        self._w(self.sid, f"TinyBox {self.bbs_call} forward port", f"{self.bbs_call}>")
        await self.link.drain()
        while True:
            line = await self._command()
            sid = parse_sid(line)
            if sid:
                break
            if parse_send_cmd(line):               # old mailbox without SID
                self._set_mode("ascii")
                await self._ascii_slave(first=line)
                return
        if sid.has("F") and self.p.protocol == "fbb":
            self._set_mode("fbb", line)
            await self._fbb(our_turn=False)
            return
        self._set_mode("ascii", line)
        self._w(">")                                # W0RLI: short prompt after the SID
        await self.link.drain()
        await self._ascii_slave()

    # --- receiving a message ------------------------------------------------------

    async def _read_message(self) -> tuple[str, str]:
        """Title line, then text up to Ctrl-Z (also inside a line) or a line /EX."""
        self.in_message = True
        limit = self.rx.max_bytes * 2 + 8192
        subject = (await self._line()).replace(CTRL_Z, "").strip()
        lines: list[str] = []
        size = 0
        while True:
            line = await self._line()
            if CTRL_Z in line:
                before = line.split(CTRL_Z, 1)[0]
                if before:
                    lines.append(before)
                break
            if line.strip().upper() == "/EX":
                break
            lines.append(line)
            size += len(line) + 1
            if size > limit:
                raise ProtocolError(f"message longer than {limit} bytes")
        self.in_message = False
        return subject, "\n".join(lines)

    def _count(self) -> None:
        if len(self.r.received) + len(self.r.rejected) > MAX_MESSAGES:
            raise ProtocolError(f"more than {MAX_MESSAGES} messages in one session")

    async def _take(self, prop: Proposal) -> None:
        subject, text = await self._read_message()
        if self.rx.store(prop, subject, text) is None:
            self.r.rejected.append(prop.bid or "-")
        else:
            self.r.received.append(prop.bid or "-")

    # --- FBB batch ----------------------------------------------------------------

    async def _fbb(self, our_turn: bool) -> None:
        while True:
            if our_turn:
                block = self.tx.block(MAX_BLOCK)
                if block:
                    await self._send_block(block)
                else:
                    self._w("FF")                   # nothing (more) to send
                    await self.link.drain()
                our_turn = False
            line = await self._command()
            u = line.upper()
            if u == "FQ":
                return
            if u == "FF":                           # partner has nothing more
                if self.tx.block(MAX_BLOCK):
                    our_turn = True
                    continue
                self._w("FQ")
                await self.link.drain()
                return
            if u.startswith(("FA", "FB")):
                await self._receive_block(line)
                our_turn = True
                continue
            raise ProtocolError(f"unexpected {line!r}")

    async def _receive_block(self, first: str) -> None:
        lines = [first]
        while True:
            line = await self._command()
            if line.upper().startswith("F>"):
                if not block_end_ok(line, lines):
                    raise ProtocolError(f"checksum error in {line!r}")
                break
            lines.append(line)
            if len(lines) > MAX_BLOCK:
                raise ProtocolError("more than 5 proposals in one block")
        props = [parse_proposal(x) for x in lines]
        if any(p.kind == "FA" for p in props):
            raise ProtocolError("compressed proposal (FA) without B in our SID")
        answers: list[str] = []
        seen: set[str] = set()
        for p in props:
            answers.append(self.rx.answer(p, seen))
            seen.add(p.bid)
        self._w("FS " + "".join(answers))
        await self.link.drain()
        for p, a in zip(props, answers):
            if a == ACCEPT:
                await self._take(p)
            else:
                self.r.rejected.append(p.bid)
        self._count()

    async def _send_block(self, block) -> None:
        props = [self.tx.proposal(m) for m in block]
        lines = [self.tx.fb_line(p) for p in props]
        self._w(*lines, f"F> {checksum(lines)}")
        await self.link.drain()
        answers = parse_fs(await self._command(), len(block))
        for m, a in zip(block, answers):
            if a == "+":
                self._w(*self.tx.message_lines(m))
                await self.link.drain()
                state = "done"
            else:
                state = "rejected" if a == "-" else "later"
            self.tx.mark(m, state)
            self.r.sent[m.bid or str(m.id)] = state

    # --- W0RLI ASCII --------------------------------------------------------------

    async def _ascii_send(self, m) -> None:
        """S command, answer, message. The caller waits for the prompt afterwards."""
        self._w(self.tx.send_cmd(m))
        await self.link.drain()
        reply = await self._command()
        answer = parse_rli_reply(reply)
        if answer is None:
            raise ProtocolError(f"expected OK/NO, got {reply!r}")
        if answer == "+":
            self._w(*self.tx.message_lines(m))
            await self.link.drain()
            state = "done"
        else:
            state = "rejected" if answer == "-" else "later"
        self.tx.mark(m, state)
        self.r.sent[m.bid or str(m.id)] = state

    async def _ascii_offer(self, cmd: Proposal) -> None:
        """Answer one S command with OK/NO and take the message after OK."""
        if self.rx.answer(cmd) != ACCEPT:
            self.r.rejected.append(cmd.bid or "-")
            self._w("NO")
            await self.link.drain()
            return
        self._w("OK")
        await self.link.drain()
        await self._take(cmd)
        self._count()

    async def _ascii_slave(self, first: str | None = None) -> None:
        line = first
        while True:
            if line is None:
                line = await self._command()       # partner hangs up = normal end
            cmd = parse_send_cmd(line)
            u = line.upper()
            if cmd:
                await self._ascii_offer(cmd)
            elif u.startswith("F>"):                # reverse: the caller asks for our mail
                todo = self.tx.pending()
                if not todo:
                    return                          # nothing to send: hang up (W0RLI)
                await self._ascii_send(todo[0])
                line = None                         # the caller confirms with F> again
                continue
            elif u in ("B", "BYE", "*** DONE"):
                return
            self._w(">")
            await self.link.drain()
            line = None

    async def _ascii_reverse(self) -> None:
        """We called: ask for the partner's mail with F> until it hangs up."""
        while True:
            self._w("F>")
            await self.link.drain()
            line = await self._command()           # hang up = nothing more (normal)
            cmd = parse_send_cmd(line)
            if cmd is None:
                return
            await self._ascii_offer(cmd)
