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

Bulletins, only when tinybox.conf has [rubrics] (CR19):
    rubric accepted (or ALL)            -> as above
    rubric refused, or TBNEWS           -> reject
    rubric unknown, first offer         -> accept, keep it held (H) and mail the sysop
    rubric unknown, sysop not decided   -> FBB: defer ('='); ASCII (no "later"
                                           in W0RLI): accept and keep it held
After the sysop's entry in [rubrics] and a restart, the held bulletins are
released or deleted (ForwardModule.resolve_rubrics).

A message is stored only after it arrived completely; the MessageService adds
our own R: line, checks for loops and too old mail (then status H).
"""

from __future__ import annotations

import logging

from .. import addressing
from ..config import is_valid_call, normalize_call
from ..service import NEW_RUBRIC_NOTE, MessageService, ServiceError
from .protocol import Proposal, Sid

log = logging.getLogger("tinybox.forward")

ACCEPT, REJECT, LATER = "+", "-", "="


class Receiver:
    def __init__(self, service: MessageService, partner_call: str) -> None:
        self.service = service
        self.partner = partner_call
        self.mode = ""                         # fbb | ascii
        self.peer_sid: Sid | None = None
        self.hold_dup: set[str] = set()        # known MIDs we take anyway (held)
        self.bad_addr: dict[str, str] = {}     # offer key -> unusable @ address (held)
        self.new_rubric: dict[str, str] = {}   # offer key -> new rubric (held + sysop mail)
        self.rubric_wait: dict[str, str] = {}  # offer key -> rubric waiting (held, ASCII)
        self.offered_new: set[str] = set()     # new rubrics offered in this session

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
        return self._rubric_answer(p)

    def _rubric_answer(self, p: Proposal) -> str:
        if p.type != "B":
            return ACCEPT
        name = normalize_call(p.to_call)
        state = self.service.rubric_state(name)
        if state == "accepted":
            return ACCEPT
        key = self._key(p)
        if state != "unknown":                  # refused, or the system rubric TBNEWS
            self.bad_addr.pop(key, None)
            log.info("%s: offer %s -> %s rejected: rubric %s", self.partner,
                     p.bid or "(no BID)", name, state)
            return REJECT
        if name in self.offered_new or self.service.new_rubric_waiting(name):
            if self.mode == "fbb":
                self.bad_addr.pop(key, None)
                log.info("%s: offer %s -> %s deferred: new rubric, sysop has not decided",
                         self.partner, p.bid or "(no BID)", name)
                return LATER
            self.rubric_wait[key] = name
            return ACCEPT
        self.offered_new.add(name)
        self.new_rubric[key] = name
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
        new = self.new_rubric.pop(self._key(p), None)
        rubric = new or self.rubric_wait.pop(self._key(p), None)
        if rubric and self.service._hold_reason(rlines):
            new = rubric = None                 # loop / too old: held for that reason
        if rubric:
            hold = f"{NEW_RUBRIC_NOTE} {rubric}: waiting for the sysop" + (
                f" (and unusable address @ {bad})" if bad is not None else "")
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
        if new:
            try:
                self.service.new_rubric_mail(new, self.partner, msg_id)
            except ServiceError as exc:
                log.warning("%s: no sysop mail for the new rubric %s: %s", self.partner,
                            new, exc)
        return msg_id
