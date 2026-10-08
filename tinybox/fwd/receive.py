"""Receiving side of a forward session (F3): which offers we take, and storing them.

Decision per offer (FBB proposal or W0RLI S command):
    type T (NTS), unknown type          -> reject
    bad call, or too large              -> reject
    bad @ address                       -> accept, keep it held (H) for the sysop
                                           (rejecting would lose it: '-' means
                                           "have it already" to the sender)
    same BID twice in one block         -> reject the second
    BID already known here:
        FBB batch                       -> reject ('-')
        ASCII, partner SID with M       -> reject (NO)
        ASCII, partner SID without M:
            personal mail whose known ID is a MID (or unknown kind)
                                        -> accept, keep it held (H) for the sysop
            otherwise                   -> reject (NO)
    otherwise                           -> accept
(concept, decision BID/MID of 06.10.2026, following W0RLI)

A message is stored only after it arrived completely; the MessageService adds
our own R: line, checks for loops and too old mail (then status H).
"""

from __future__ import annotations

import logging

from .. import addressing
from ..config import is_valid_call, normalize_call
from ..service import MessageService, ServiceError
from .protocol import Proposal, Sid

log = logging.getLogger("tinybox.forward")

ACCEPT, REJECT = "+", "-"


class Receiver:
    def __init__(self, service: MessageService, partner_call: str) -> None:
        self.service = service
        self.partner = partner_call
        self.mode = ""                         # fbb | ascii
        self.peer_sid: Sid | None = None
        self.hold_dup: set[str] = set()        # known MIDs we take anyway (held)
        self.bad_addr: dict[str, str] = {}     # offer key -> unusable @ address (held)

    @property
    def max_bytes(self) -> int:
        return self.service.cfg.mailbox.max_msg_bytes

    # --- decision -----------------------------------------------------------------

    def answer(self, p: Proposal, seen: set[str] | None = None) -> str:
        why = self._reject_reason(p, seen or set())
        if why:
            log.info("%s: offer %s %s -> %s @ %s rejected: %s", self.partner, p.type,
                     p.bid or "(no BID)", p.to_call, p.at_addr or "-", why)
            return REJECT
        return ACCEPT

    def _reject_reason(self, p: Proposal, seen: set[str]) -> str:
        if p.type not in ("P", "B"):
            return f"type {p.type}"
        if p.size and p.size > self.max_bytes + 2048:        # R: lines come on top
            return f"too large ({p.size} bytes)"
        frm = normalize_call(p.from_call or self.partner)
        if not is_valid_call(frm):
            return f"bad sender {p.from_call!r}"
        try:
            self.service.check_send(frm, p.to_call, p.type, sysop=True)
        except ServiceError as exc:
            return f"{exc.code} {exc}"
        try:
            self.service.check_address(p.type, p.at_addr, None, origin="forward")
        except ServiceError:
            log.warning("%s: offer %s has an unusable address %r - taken and held",
                        self.partner, p.bid or "-", p.at_addr)
            self.bad_addr[self._key(p)] = p.at_addr
        if not p.bid:
            return ""
        if p.bid in seen:
            return "same BID twice in this block"
        if not self.service.bid_known(p.bid):
            return ""
        if self.mode == "fbb":
            return "BID known"
        if self.peer_sid is not None and self.peer_sid.has("M"):
            return "BID known"
        known = self.service.store.get_by_bid(p.bid)
        if p.type == "P" and (known is None or known.bid_kind != "B"):
            self.hold_dup.add(p.bid)            # W0RLI: MID may repeat - keep it for the sysop
            return ""
        return "BID known"

    @staticmethod
    def _key(p: Proposal) -> str:
        return p.bid or f"{p.to_call}@{p.at_addr}"

    # --- storing ------------------------------------------------------------------

    def store(self, p: Proposal, subject: str, text: str) -> int | None:
        rlines, body = addressing.split_rlines(text)
        # W0RLI: a text line "/EX" travels as '/EX'
        lines = ["/EX" if x.strip().upper() == "'/EX'" else x for x in body.split("\n")]
        while lines and not lines[-1].strip():       # some mailboxes add blank lines
            lines.pop()
        body = "\n".join(lines)
        if self.mode == "fbb":
            kind = "B" if p.type == "B" else "M"
        else:                                   # ASCII: $BID only for real BIDs
            kind = "B" if p.bid else "M"
        hold = ""
        bid = p.bid or None
        at_addr = p.at_addr
        if bid and bid in self.hold_dup:
            hold = f"known MID {bid} offered again (ASCII without M)"
            bid = None
        bad = self.bad_addr.pop(self._key(p), None)
        if bad is not None:
            hold = f"unusable address @ {bad}"
            at_addr = ""
        try:
            msg_id = self.service.create(
                from_call=p.from_call or self.partner, to_call=p.to_call, type=p.type,
                subject=subject, body=body, origin="forward", at_addr=at_addr, bid=bid,
                rlines=rlines, bid_kind=kind, hold=hold)
        except ServiceError as exc:
            log.warning("%s: message %s not stored: %s %s", self.partner, p.bid or "-",
                        exc.code, exc)
            return None
        log.info("%s: message %s stored as %d", self.partner, p.bid or "-", msg_id)
        return msg_id
