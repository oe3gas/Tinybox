"""Messages, hierarchical addresses and R: lines.

As in the real network, a mailbox appears in addresses, R: lines and BIDs
without SSID (OE3GAS.#OOE.AUT.EU, 12_OE3GAS). An SSID exists only on the
AX.25 connect. If an SSID shows up in an @ field anyway, it is ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

# W0RLI: HEADER2 "R:yymmdd/hhmm[Z] @:BBS ... #:nr ..."  or  HEADER1 "R:yymmdd/hhmm nr@BBS"
RLINE_RE = re.compile(r"^R:(\d{6})/(\d{4})[A-Z]?\s+(?:@:(\S+)|\d+@(\S+))", re.IGNORECASE)
MAX_BID = 12
MAX_SUBJECT = 80


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Message:
    type: str                 # P or B
    to_call: str              # call (P) or topic like ALL (B)
    at_addr: str              # hierarchical address (P) or area like WW (B)
    from_call: str
    bid: str
    subject: str
    body: str                 # text without R: lines, lines separated by "\n"
    rlines: list[str] = field(default_factory=list)   # newest first
    id: int = 0               # local number in the owning mailbox
    status: str = "N"         # N, Y, H (held), F (forwarded to all)
    created: str = ""
    received_from: str = ""   # partner call, empty = created locally
    note: str = ""            # why a message is held

    def wire_text(self) -> str:
        """Text as it goes over the air: R: lines, a blank line, the body."""
        parts = list(self.rlines)
        if parts:
            parts.append("")
        parts.append(self.body)
        return "\n".join(parts)

    @property
    def size(self) -> int:
        return len(self.wire_text().replace("\n", "\r").encode("utf-8"))


def split_wire_text(text: str) -> tuple[list[str], str]:
    """Separate the R: lines at the top from the body."""
    lines = text.split("\n")
    rlines: list[str] = []
    while lines and RLINE_RE.match(lines[0]):
        rlines.append(lines.pop(0))
    if rlines and lines and lines[0] == "":
        lines.pop(0)
    return rlines, "\n".join(lines)


def base(call: str) -> str:
    return call.upper().split("-", 1)[0]


def rline_call(rline: str) -> str:
    """'R:261006/1830Z @:OE3GAS.#OOE.AUT.EU [Linz] ...' -> 'OE3GAS'"""
    m = RLINE_RE.match(rline)
    return base((m.group(3) or m.group(4)).split(".", 1)[0]) if m else ""


def make_rline(when: datetime, haddr: str, qth: str, local_nr: int, bid: str) -> str:
    return (f"R:{when:%y%m%d/%H%M}Z @:{haddr} [{qth}] #:{local_nr} $:{bid}")


def addr_parts(addr: str) -> list[str]:
    """Elements of an address; an SSID on the mailbox call is dropped."""
    parts = [p for p in addr.upper().split(".") if p]
    if parts:
        parts[0] = base(parts[0])
    return parts


def addr_call(addr: str) -> str:
    """First element of a hierarchical address, the mailbox call (no SSID)."""
    parts = addr_parts(addr)
    return parts[0] if parts else ""


def route_score(addr: str, pattern: str) -> float:
    """How well a route pattern matches an address, compared from the right.

    'AUT.EU' against 'OE1ABC.#WIE.AUT.EU' -> 2. A pattern that is a full
    mailbox call (first element) and matches it -> 100. 'WW' matches
    everything with the lowest score (0.5). No match -> 0.
    """
    a = addr_parts(addr)
    p = addr_parts(pattern)
    if not a or not p:
        return 0
    if p == ["WW"]:
        return 0.5
    if len(p) == 1 and a[0] == p[0]:
        return 100
    if len(p) > len(a):
        return 0
    if a[-len(p):] == p:
        return len(p)
    return 0
