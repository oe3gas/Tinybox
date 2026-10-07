"""A simulated mailbox: stores messages, writes R: lines, routes and floods.

Routing follows the BPQ model:
  personal mail   -> the partner whose route pattern matches the address best
                     (compared from the right, the mailbox call scores highest)
  bulletins       -> stored locally, flooded to every partner whose area list
                     covers the @ area - never back to where it came from and
                     never to a mailbox that already appears in the R: lines
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .model import (MAX_BID, MAX_SUBJECT, Message, addr_call, addr_parts, base, iso, make_rline,
                    rline_call, route_score, utc_now, RLINE_RE)
from .protocol import ACCEPT, REJECT, Proposal
from .store import Store

log = logging.getLogger("fwdsim.bbs")


@dataclass
class Peer:
    call: str                                        # partner mailbox call (no SSID)
    routes: list[str] = field(default_factory=list)  # personal / directed: HR patterns
    floods: list[str] = field(default_factory=list)  # bulletin areas, "*" = all


class SimBBS:
    def __init__(self, store: Store, call: str, haddr: str, qth: str, bid_start: int,
                 peers: list[Peer], *, max_bytes: int = 0, hold_days: int = 0) -> None:
        self.store = store
        self.call = base(call)
        self.haddr = haddr.upper()
        self.qth = qth
        self.bid_start = bid_start
        self.peers = {base(p.call): p for p in peers}
        self.max_bytes = max_bytes        # 0 = no limit
        self.hold_days = hold_days        # 0 = no age check

    # --- creating ---------------------------------------------------------------

    def new_bid(self) -> str:
        """FBB style <nr>_<CALL>, at most 12 characters. The counter survives 'reset',
        so a new test run never reuses a BID that TinyBox already knows."""
        n = self.bid_start + self.store.next_bid_nr(self.call, 0)
        bid = f"{n}_{self.call}"
        if len(bid) > MAX_BID:
            raise ValueError(f"BID {bid} longer than {MAX_BID} characters")
        return bid

    def create(self, type: str, to_call: str, at_addr: str, subject: str, body: str,
               from_call: str | None = None, *, bid: str | None = None,
               extra_rlines: list[str] | None = None, when: datetime | None = None) -> Message:
        """A message written on this mailbox (by a user or a test case)."""
        when = when or utc_now()
        m = Message(type=type.upper(), to_call=to_call.upper(), at_addr=at_addr.upper(),
                    from_call=(from_call or self.call).upper(), bid=(bid or self.new_bid()).upper(),
                    subject=subject, body=body, created=iso(when))
        m.rlines = list(extra_rlines or [])
        self.store.add(self.call, m)
        m.rlines.insert(0, make_rline(when, self.haddr, self.qth, m.id, m.bid))
        self._save_rlines(m)
        self.route(m, from_peer="")
        return m

    def _save_rlines(self, m: Message) -> None:
        with self.store.db:
            self.store.db.execute("UPDATE messages SET rlines = ? WHERE bbs = ? AND nr = ?",
                                  ("\n".join(m.rlines), self.call, m.id))

    # --- receiving --------------------------------------------------------------

    def answer(self, p: Proposal, seen_in_block: set[str]) -> str:
        """Decide on one proposal: accept or reject (already have it / too large)."""
        if p.bid in seen_in_block or self.store.bid_known(self.call, p.bid):
            return REJECT
        if self.max_bytes and p.size > self.max_bytes:
            return REJECT
        return ACCEPT

    def receive(self, p: Proposal, subject: str, rlines: list[str], body: str,
                from_peer: str) -> Message:
        """A complete message arrived from a partner."""
        if not p.bid:
            # a personal message without BID (allowed by W0RLI): keep a local id
            p.bid = f"L{self.store.next_bid_nr(self.call, 0)}_{self.call}"[:MAX_BID]
        m = Message(type=p.type, to_call=p.to_call, at_addr=p.at_addr, from_call=p.from_call,
                    bid=p.bid, subject=subject[:MAX_SUBJECT], body=body, rlines=list(rlines),
                    created=iso(utc_now()), received_from=base(from_peer))
        held = ""
        if self.call in {rline_call(r) for r in rlines}:
            held = "loop: own call in R: lines"
        elif self.hold_days and self._older_than(rlines, self.hold_days):
            held = f"older than {self.hold_days} days"
        if held:
            m.status, m.note = "H", held
        self.store.add(self.call, m)
        m.rlines.insert(0, make_rline(utc_now(), self.haddr, self.qth, m.id, m.bid))
        self._save_rlines(m)
        log.info("%s: received %s %s from %s%s", self.call, m.type, m.bid, from_peer,
                 f" - HELD ({held})" if held else "")
        if not held:
            self.route(m, from_peer=base(from_peer))
        return m

    @staticmethod
    def _older_than(rlines: list[str], days: int) -> bool:
        if not rlines:
            return False
        m = RLINE_RE.match(rlines[-1])          # the oldest line = origin
        if not m:
            return False
        try:
            when = datetime.strptime(m.group(1) + m.group(2), "%y%m%d%H%M").replace(
                tzinfo=timezone.utc)
        except ValueError:
            return False
        return utc_now() - when > timedelta(days=days)

    # --- routing ----------------------------------------------------------------

    def route(self, m: Message, from_peer: str) -> list[str]:
        """Put the message in the queue of the right partner(s). Returns them."""
        if m.type == "B":
            targets = self._flood_targets(m, from_peer)
        else:
            targets = self._personal_target(m)
        for peer in targets:
            self.store.enqueue(self.call, m.id, peer)
        return targets

    def _personal_target(self, m: Message) -> list[str]:
        dest = addr_call(m.at_addr)
        if not m.at_addr or dest == self.call:
            return []                                   # for a local user
        best, score = "", 0.0
        for peer in self.peers.values():
            for pattern in [peer.call] + peer.routes:
                s = route_score(m.at_addr, pattern)
                if s > score:
                    best, score = peer.call, s
        if not best:
            self.store.set_status(self.call, m.id, "H", "no route")
            log.info("%s: no route for %s @ %s - held", self.call, m.bid, m.at_addr)
            return []
        return [best]

    def _flood_targets(self, m: Message, from_peer: str) -> list[str]:
        area = addr_parts(m.at_addr)
        been = {rline_call(r) for r in m.rlines}
        out = []
        for peer in self.peers.values():
            if peer.call == from_peer or peer.call in been:
                continue
            if any(f == "*" or f.upper() in area for f in peer.floods):
                out.append(peer.call)
        return out

    # --- queue --------------------------------------------------------------------

    def pending(self, peer: str) -> list[Message]:
        return self.store.pending(self.call, base(peer))

    def mark(self, m: Message, peer: str, state: str) -> None:
        self.store.set_queue(self.call, m.id, base(peer), state)
        states = self.store.queue_states(self.call, m.id)
        if states and all(s in ("done", "rejected") for s in states.values()):
            self.store.set_status(self.call, m.id, "F")

    def messages(self) -> list[Message]:
        return self.store.list(self.call)

    def find(self, *, bid: str | None = None, subject: str | None = None) -> list[Message]:
        out = []
        for m in self.messages():
            if bid and m.bid != bid.upper():
                continue
            if subject and m.subject != subject:
                continue
            out.append(m)
        return out
