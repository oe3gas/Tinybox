"""One forward session between two mailboxes.

FBB batch protocol (both SIDs carry F):
    slave (called) : SID, text, prompt ">"
    master (caller): own SID, then the first block
    block          : up to 5 "FB ..." lines, then "F> checksum"
    answer         : "FS +-=" ; then the accepted messages: title, text, Ctrl-Z
    turn           : after a block the other side sends its block, or FF
    end            : "FF" = nothing to send; the other side answers "FQ" and hangs up

MBL/RLI ASCII (one side without F), W0RLI BBS specification of 12 Oct 1998:
    slave  : SID, prompt ">" ; after the master's SID a short prompt ">"
    master : "SP TO @ AT < FROM $BID"
    slave  : "OK" | "NO" (first letter counts; R: also LATER, REJECT)
    master : title, R: lines, blank line, text, Ctrl-Z (or /EX)
    slave  : ">"                       (also after NO)
    reverse: master sends "F>", the slave sends its S command, the master answers
             OK/NO and confirms each message with "F>" instead of ">". The slave
             hangs up when it has nothing more.
Errors: the side that notices one disconnects at once, without sending anything.
Lines starting with ';' are null commands (feature I) and are ignored.

Faults let a test case break the rules on purpose.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from . import SOFTWARE, VERSION
from .bbs import SimBBS
from .link import Link
from .model import Message, base, split_wire_text
from .protocol import (ACCEPT, HOLD, LATER, REJECT, CTRL_Z, Proposal, ProtocolError,
                       check_block_end, checksum, make_fs, parse_fs, parse_proposal,
                       parse_rli_response, parse_send_cmd, parse_sid)

log = logging.getLogger("fwdsim.session")

MAX_BLOCK = 5
BLOCK_BYTES = 10_000
# No M: W0RLI discourages MIDs in the SID ("will on occasion cause the loss of messages")
OWN_FLAGS = "FH$"


@dataclass
class Faults:
    sid: str | None = None            # send this SID instead of our own
    fs: str | None = None             # answer incoming proposals with these symbols
    fb_fields: int = 7                # send FB lines with fewer fields
    bad_checksum: bool = False
    abort_after: int | None = None    # hang up after n bytes of the first message text
    no_ctrl_z: bool = False           # never end a message
    prompt_trap: bool = False         # as slave: node-like line ending in '>' before the SID
    crlf: bool = False                # line end CR LF instead of CR
    latin1: bool = False              # send text in Latin-1
    eomb: bool = False                # end messages with a line /EX instead of Ctrl-Z
    null_lines: bool = False          # send '; CALL de CALL' null commands (feature I)


@dataclass
class SessionResult:
    peer: str
    master: bool
    mode: str = ""                                  # fbb | rli
    peer_sid: str = ""
    sent: dict[str, str] = field(default_factory=dict)       # bid -> answer of the peer
    received: list[str] = field(default_factory=list)        # bids stored here
    proposed_to_us: list[str] = field(default_factory=list)  # bids the peer offered
    error: str = ""
    transcript: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.error


class Aborted(Exception):
    """The connection ended in the middle of something."""


class ForwardSession:
    def __init__(self, bbs: SimBBS, link: Link, peer: str, *, master: bool,
                 faults: Faults | None = None, timeout: float = 60) -> None:
        self.bbs = bbs
        self.link = link
        self.peer = base(peer)
        self.master = master
        self.f = faults or Faults()
        self.timeout = timeout
        self.r = SessionResult(peer=self.peer, master=master)
        if self.f.crlf:
            link.eol = "\r\n"
        if self.f.latin1:
            link.encoding = "latin-1"

    # --- helpers ----------------------------------------------------------------

    def our_sid(self) -> str:
        return self.f.sid or f"[{SOFTWARE}-{VERSION}-{OWN_FLAGS}]"

    async def _line(self) -> str:
        line = await self.link.readline(self.timeout)
        if line is None:
            raise Aborted("connection closed by peer")
        return line

    async def _nonblank(self) -> str:
        """Next command line: blank lines and ';' null commands are skipped."""
        while True:
            line = (await self._line()).strip()
            if line and not line.startswith(";"):
                return line

    async def _wait_prompt(self) -> None:
        while not (await self._nonblank()).endswith(">"):
            pass

    def _w(self, *lines: str) -> None:
        self.link.write_lines(list(lines))

    # --- entry ------------------------------------------------------------------

    async def run(self) -> SessionResult:
        try:
            if self.master:
                await self._run_master()
            else:
                await self._run_slave()
        except asyncio.TimeoutError:
            self.r.error = "timeout"
        except Aborted as exc:
            self.r.error = f"aborted: {exc}"
        except ProtocolError as exc:
            self.r.error = f"protocol: {exc}"      # W0RLI section 6: hang up, say nothing
        finally:
            await self.link.drain()
            await self.link.close()
            self.r.transcript = list(self.link.transcript)
        level = logging.INFO if self.r.ok else logging.WARNING
        log.log(level, "%s <-> %s (%s, %s): sent %s, received %s%s", self.bbs.call, self.peer,
                "master" if self.master else "slave", self.r.mode or "-", self.r.sent,
                self.r.received, f", error: {self.r.error}" if self.r.error else "")
        return self.r

    async def _run_slave(self) -> None:
        if self.f.prompt_trap:
            self._w(f"NODE:{self.bbs.call}}} Connected to {self.bbs.call} >")
        self._w(self.our_sid(), f"Hello, this is {self.bbs.call} (fwdsim).",
                f"{self.bbs.call} BBS>")
        await self.link.drain()
        while True:
            line = await self._nonblank()
            sid = parse_sid(line)
            if sid:
                break
            if parse_send_cmd(line):     # master without SID: plain ASCII
                self.r.mode = "rli"
                await self._rli_slave(first=line)
                return
        self.r.peer_sid = line
        ours = parse_sid(self.our_sid())
        if sid.fbb and ours and ours.fbb:
            self.r.mode = "fbb"
            await self._fbb_loop(our_turn=False)
        else:
            self.r.mode = "rli"
            self._w(">")                         # W0RLI: abbreviated prompt after the SID
            await self.link.drain()
            await self._rli_slave()

    async def _run_master(self) -> None:
        sid = None
        while sid is None:                       # skip node texts until the SID
            line = await self._nonblank()
            sid = parse_sid(line)
        self.r.peer_sid = line
        await self._wait_prompt()                # the BBS prompt after the SID
        self._w(self.our_sid())
        await self.link.drain()
        ours = parse_sid(self.our_sid())
        if sid.fbb and ours and ours.fbb:
            self.r.mode = "fbb"
            await self._fbb_loop(our_turn=True)
        else:
            self.r.mode = "rli"
            await self._wait_prompt()            # the short prompt after our SID
            await self._rli_master()

    # --- FBB batch ----------------------------------------------------------------

    async def _fbb_loop(self, our_turn: bool) -> None:
        while True:
            if our_turn:
                block = self._next_block()
                if not block:
                    self._w("FF")
                else:
                    await self._send_block(block)
                our_turn = False
                continue
            line = await self._nonblank()
            u = line.upper()
            if u == "FQ":
                return
            if u == "FF":
                if self._next_block():
                    our_turn = True
                    continue
                self._w("FQ")
                return
            if u.startswith(("FA", "FB")):
                await self._receive_block(line)
                our_turn = True
                continue
            if u.startswith("***"):
                raise Aborted(line)
            raise ProtocolError(f"unexpected line {line!r}")

    def _next_block(self) -> list[Message]:
        """Up to 5 queued messages not yet offered in this session."""
        block, total = [], 0
        for m in self.bbs.pending(self.peer):
            if m.bid in self.r.sent:
                continue
            if len(block) >= MAX_BLOCK or (block and total + m.size > BLOCK_BYTES):
                break
            block.append(m)
            total += m.size
        return block

    def _proposal(self, m: Message) -> Proposal:
        return Proposal("FB", m.type, m.from_call, m.at_addr, m.to_call, m.bid, m.size)

    async def _send_block(self, block: list[Message]) -> None:
        lines = []
        for m in block:
            parts = self._proposal(m).line().split()
            lines.append(" ".join(parts[:self.f.fb_fields]))
        cs = checksum(lines)
        if self.f.bad_checksum:
            cs = f"{(int(cs, 16) + 1) & 0xFF:02X}"
        self._null()
        self._w(*lines, f"F> {cs}")
        await self.link.drain()
        answers = parse_fs(await self._nonblank(), len(block))
        for m, a in zip(block, answers):
            self.r.sent[m.bid] = a
            if a in (ACCEPT, HOLD):
                await self._send_message(m)
                self.bbs.mark(m, self.peer, "done")
            elif a == REJECT:
                self.bbs.mark(m, self.peer, "rejected")
            elif a == LATER:
                self.bbs.mark(m, self.peer, "later")

    async def _send_message(self, m: Message) -> None:
        text_lines = m.wire_text().split("\n")
        if self.f.abort_after is not None:
            data = "\r".join([m.subject] + text_lines).encode(self.link.encoding, "replace")
            self.link.write_raw(data[:self.f.abort_after])
            await self.link.drain()
            await self.link.close()
            raise Aborted(f"fault: hung up after {self.f.abort_after} bytes")
        # W0RLI: a body line "/EX" would end the message - send it as '/EX'
        text_lines = ["'/EX'" if x.strip().upper() == "/EX" else x for x in text_lines]
        self._w(m.subject, *text_lines)
        if self.f.eomb:
            self._w("/EX")
        elif not self.f.no_ctrl_z:
            self._w(CTRL_Z)
        await self.link.drain()

    def _null(self) -> None:
        if self.f.null_lines:
            self._w(f"; {self.peer} de {self.bbs.call}")

    async def _receive_block(self, first: str) -> None:
        lines = [first]
        while True:
            line = await self._nonblank()
            if line.upper().startswith("F>"):
                if not check_block_end(line, lines):
                    raise ProtocolError(f"checksum error in {line!r}")
                break
            lines.append(line)
            if len(lines) > MAX_BLOCK:
                raise ProtocolError("more than 5 proposals in one block")
        props = [parse_proposal(x) for x in lines]
        self.r.proposed_to_us += [p.bid for p in props]
        if self.f.fs:
            sym = (self.f.fs * len(props))[:len(props)]
            answers = parse_fs("FS " + sym, len(props))
        else:
            seen: set[str] = set()
            answers = []
            for p in props:
                answers.append(self.bbs.answer(p, seen))
                seen.add(p.bid)
        self._w(make_fs(answers))
        await self.link.drain()
        for p, a in zip(props, answers):
            if a in (ACCEPT, HOLD):
                subject, text = await self._read_message()
                rlines, body = split_wire_text(text)
                self.bbs.receive(p, subject, rlines, body, self.peer)
                self.r.received.append(p.bid)

    async def _read_message(self) -> tuple[str, str]:
        """Title, then text up to Ctrl-Z (EOMA) or a line /EX (EOMB)."""
        subject = await self._line()
        lines: list[str] = []
        while True:
            line = await self._line()
            if CTRL_Z in line:
                before = line.split(CTRL_Z, 1)[0]
                if before:
                    lines.append(before)
                return subject, "\n".join(lines)
            if line.strip().upper() == "/EX":
                return subject, "\n".join(lines)
            lines.append(line)

    # --- MBL/RLI ASCII (W0RLI) ----------------------------------------------------

    def _send_cmd(self, m: Message) -> str:
        bid = f" ${m.bid}" if m.bid else ""
        return f"S{m.type} {m.to_call} @ {m.at_addr} < {m.from_call}{bid}"

    async def _rli_offer(self, m: Message) -> None:
        """S command, answer, message; then wait for '>' (or 'F>' in reverse)."""
        self._null()
        self._w(self._send_cmd(m))
        await self.link.drain()
        reply = await self._nonblank()
        answer = parse_rli_response(reply)
        if answer is None:
            raise ProtocolError(f"expected OK/NO, got {reply!r}")
        self.r.sent[m.bid] = answer
        if answer == ACCEPT:
            await self._send_message(m)
            self.bbs.mark(m, self.peer, "done")
        else:
            self.bbs.mark(m, self.peer, "rejected" if answer == REJECT else "later")
        await self._wait_prompt()

    async def _rli_accept(self, p: Proposal) -> None:
        """Answer an S command with OK/NO and take the message if OK."""
        self.r.proposed_to_us.append(p.bid)
        if p.type == "T" or self.bbs.answer(p, set()) != ACCEPT:
            self._w("NO")                         # duplicate BID (no NTS traffic here)
            await self.link.drain()
            return
        self._w("OK")
        await self.link.drain()
        subject, text = await self._read_message()
        rlines, body = split_wire_text(text)
        m = self.bbs.receive(p, subject, rlines, body, self.peer)
        self.r.received.append(m.bid)

    async def _rli_master(self) -> None:
        for m in list(self.bbs.pending(self.peer)):
            await self._rli_offer(m)
        while True:                               # reverse forwarding
            self._w("F>")
            await self.link.drain()
            try:
                line = await self._nonblank()
            except Aborted:
                return                            # slave hung up: nothing more for us
            p = parse_send_cmd(line)
            if p is None:
                return                            # anything else ends reverse forwarding
            await self._rli_accept(p)

    async def _rli_slave(self, first: str | None = None) -> None:
        line = first
        while True:
            if line is None:
                try:
                    line = await self._nonblank()
                except Aborted:
                    return                        # master hung up: normal end
            p = parse_send_cmd(line)
            if p is not None:
                await self._rli_accept(p)
                self._w(">")
            elif line.upper().startswith("F>"):   # master asks for reverse forwarding
                todo = [m for m in self.bbs.pending(self.peer) if m.bid not in self.r.sent]
                if not todo:
                    return                        # nothing to send: hang up
                await self._rli_offer(todo[0])    # consumed the master's next "F>"
                line = "F>"
                continue
            elif line.upper() in ("B", "BYE"):
                return
            else:
                self._w(">")
            await self.link.drain()
            line = None
