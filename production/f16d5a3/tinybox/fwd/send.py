"""Sending side of a forward session (F4): what we offer a partner and how.

The queue (table fwd_queue) holds one row per message and partner. States:
    open   waiting                 later  partner said '=' / LATER, try again
    done   partner took it         rejected  partner had it already ('-' / NO)
When no row of a message is open or later any more, the message gets fwd 'F'.

On the wire a message is: title (max 79 characters, W0RLI), the R: lines,
an empty line, the text, Ctrl-Z. A text line "/EX" travels as '/EX'.
"""

from __future__ import annotations

import logging

from ..service import MessageService
from ..store import Message
from .protocol import CTRL_Z, Proposal

log = logging.getLogger("tinybox.forward")

MAX_SUBJECT_SEND = 79
BLOCK_BYTES = 10_000          # one FBB block (sum of the proposed sizes)


def wire_lines(m: Message) -> list[str]:
    """Title and text lines as they go out (without Ctrl-Z)."""
    text = list(m.rline_list)
    if text:
        text.append("")
    text += ["'/EX'" if x.strip().upper() == "/EX" else x for x in m.body.split("\n")]
    return [m.subject[:MAX_SUBJECT_SEND]] + text


def wire_size(m: Message) -> int:
    """Size in the FBB proposal: the text (not the title) with CR line ends."""
    return len("".join(x + "\r" for x in wire_lines(m)[1:]).encode("utf-8"))


class Sender:
    def __init__(self, service: MessageService, partner_call: str) -> None:
        self.service = service
        self.store = service.store
        self.partner = partner_call
        self.offered: set[int] = set()        # message ids offered in this session

    def pending(self) -> list[Message]:
        return [m for m in self.store.fwd_pending(self.partner) if m.id not in self.offered]

    def block(self, max_n: int) -> list[Message]:
        """Up to max_n messages not yet offered, at most BLOCK_BYTES together."""
        out, total = [], 0
        for m in self.pending():
            size = wire_size(m)
            if len(out) >= max_n or (out and total + size > BLOCK_BYTES):
                break
            out.append(m)
            total += size
        return out

    def proposal(self, m: Message) -> Proposal:
        return Proposal("FB", m.type, m.from_call, m.at_addr or self.partner, m.to_call,
                        m.bid or "", wire_size(m))

    @staticmethod
    def fb_line(p: Proposal) -> str:
        return f"FB {p.type} {p.from_call} {p.at_addr} {p.to_call} {p.bid} {p.size}"

    @staticmethod
    def send_cmd(m: Message) -> str:
        """W0RLI S command; $BID only for real BIDs (not for generated MIDs)."""
        bid = f" ${m.bid}" if m.bid and m.bid_kind == "B" else ""
        return f"S{m.type} {m.to_call} @ {m.at_addr} < {m.from_call}{bid}"

    @staticmethod
    def message_lines(m: Message) -> list[str]:
        return wire_lines(m) + [CTRL_Z]

    def mark(self, m: Message, state: str) -> None:
        """state: done, rejected, later. Sets fwd 'F' when nothing is left to do."""
        self.offered.add(m.id)
        self.store.fwd_set(m.id, self.partner, state)
        log.info("%s: message %d (%s) %s", self.partner, m.id, m.bid, state)
        states = self.store.fwd_states(m.id).values()
        if not any(s in ("open", "later") for s in states):
            msg = self.store.get(m.id)
            if msg is not None and msg.fwd == "$":
                self.service.set_fwd_state(m.id, "F")
