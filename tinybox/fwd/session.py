"""One forward session with a partner mailbox.

F2 scope: connection, SID exchange, choice of protocol, clean end. Nothing is
sent or stored yet; whatever the partner offers is deferred so that nothing is
lost (FBB: answer '=' = "later"; W0RLI ASCII: hang up before answering, the
partner tries again). F3 adds receiving, F4 sending.

Choice of protocol (concept, section W0RLI):
    both SIDs with F           -> FBB batch
    otherwise, partner has SID -> W0RLI ASCII
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from ..config import PartnerCfg
from .link import Link
from .protocol import (MAX_BLOCK, ProtocolError, block_end_ok, own_sid, parse_proposal,
                       parse_send_cmd, parse_sid)

log = logging.getLogger("tinybox.forward")


class Gone(Exception):
    """The partner hung up."""


@dataclass
class SessionResult:
    partner: str
    master: bool
    transport: str
    mode: str = ""                  # fbb | ascii
    peer_sid: str = ""
    deferred: list[str] = field(default_factory=list)   # BIDs offered to us, not taken yet
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error

    def summary(self) -> str:
        role = "called" if self.master else "was called by"
        return (f"{role} {self.partner} via {self.transport}, mode {self.mode or '-'}, "
                f"SID {self.peer_sid or '-'}, deferred {len(self.deferred)}"
                + (f", ERROR {self.error}" if self.error else ""))


class ForwardSession:
    def __init__(self, bbs_call: str, partner: PartnerCfg, link: Link, *, master: bool,
                 transport: str) -> None:
        self.bbs_call = bbs_call
        self.p = partner
        self.link = link
        self.master = master
        self.r = SessionResult(partner.call, master, transport)
        self.sid = own_sid(partner.protocol)

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

    # --- entry ----------------------------------------------------------------

    async def run(self) -> SessionResult:
        log.info("%s: forward session %s %s", self.p.call,
                 "to" if self.master else "from", self.r.transport)
        try:
            await (self._master() if self.master else self._slave())
        except asyncio.TimeoutError:
            self.r.error = f"timeout ({self.p.timeout} s)"
        except Gone as exc:
            if not self.r.mode or self.r.mode == "fbb":
                self.r.error = str(exc)
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
        self.r.peer_sid = line
        await self._wait_prompt()
        self._w(self.sid)
        await self.link.drain()
        if sid.has("F") and self.p.protocol == "fbb":
            self.r.mode = "fbb"
            await self._fbb(our_turn=True)
        else:
            self.r.mode = "ascii"
            await self._wait_prompt()               # short prompt after our SID
            # F2: nothing to send; reverse forwarding (F>) comes with F3/F4

    async def _slave(self) -> None:
        self._w(self.sid, f"TinyBox {self.bbs_call} forward port", f"{self.bbs_call}>")
        await self.link.drain()
        while True:
            line = await self._command()
            sid = parse_sid(line)
            if sid:
                break
            if parse_send_cmd(line):               # old mailbox without SID
                self.r.mode = "ascii"
                self.r.deferred.append(parse_send_cmd(line).bid)
                return                              # F2: hang up, partner retries
        self.r.peer_sid = line
        if sid.has("F") and self.p.protocol == "fbb":
            self.r.mode = "fbb"
            await self._fbb(our_turn=False)
            return
        self.r.mode = "ascii"
        self._w(">")
        await self.link.drain()
        line = await self._command()
        cmd = parse_send_cmd(line)
        if cmd:
            self.r.deferred.append(cmd.bid)         # F2: hang up before OK/NO
        # 'F>' (reverse request): nothing to send -> hang up as W0RLI describes

    # --- FBB batch ----------------------------------------------------------------

    async def _fbb(self, our_turn: bool) -> None:
        while True:
            if our_turn:
                self._w("FF")                       # F2: nothing to send
                await self.link.drain()
                our_turn = False
            line = await self._command()
            u = line.upper()
            if u == "FQ":
                return
            if u == "FF":
                self._w("FQ")
                await self.link.drain()
                return
            if u.startswith(("FA", "FB")):
                await self._defer_block(line)
                our_turn = True
                continue
            raise ProtocolError(f"unexpected {line!r}")

    async def _defer_block(self, first: str) -> None:
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
        self.r.deferred += [p.bid for p in props]
        self._w("FS " + "=" * len(props))          # later: we cannot store yet (F3)
        await self.link.drain()
