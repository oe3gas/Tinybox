"""Which partner gets a message (BPQ model, see the concept).

Personal mail / directed bulletins: the partner whose route pattern matches
the @ address best, compared from the right. The partner's own call scores
highest, 'WW' matches everything with the lowest score (default route).

Bulletins: every partner whose area list contains the distribution, the first
element of the @ field ('*' = all). Directed bulletins outside our own area
(@FRA.EU from Austria) are refined in F4. Never
to a partner that already appears in the R: lines (it came from there or has
seen it), which also stops ping-pong between two mailboxes.

EU and EURO (TAPR continent code) count as the same.
"""

from __future__ import annotations

from .. import addressing
from ..config import ForwardCfg, PartnerCfg
from ..store import Message

SAME = {"EURO": "EU", "NOAM": "NA", "SOAM": "SA"}


def _elems(addr: str) -> list[str]:
    return [SAME.get(p, p) for p in addressing.parts(addr)]


def score(addr: str, pattern: str, partner_call: str) -> float:
    a, p = _elems(addr), _elems(pattern)
    if not a or not p:
        return 0
    if p == ["WW"]:
        return 0.5
    if len(p) == 1 and addressing.base_call(a[0]) == p[0] and p[0] == partner_call:
        return 100
    if len(p) <= len(a) and a[-len(p):] == p:
        return len(p)
    return 0


class Router:
    def __init__(self, cfg: ForwardCfg) -> None:
        self.cfg = cfg

    def targets(self, msg: Message) -> list[str]:
        """Partner calls for this message ([] = none)."""
        been = {addressing.rline_call(x) for x in msg.rline_list}
        if msg.type == "B":
            return self._flood(msg, been)
        best = self._best(msg.at_addr)
        return [best.call] if best and best.call not in been else []

    def _best(self, addr: str) -> PartnerCfg | None:
        best, top = None, 0.0
        for p in self.cfg.partners.values():
            for pattern in [p.call] + p.routes:
                s = score(addr, pattern, p.call)
                if s > top:
                    best, top = p, s
        return best

    def _flood(self, msg: Message, been: set[str]) -> list[str]:
        """W0RLI appendix C: the first element is the distribution (AUT in
        @AUT.EU), the rest only routes the bulletin towards it."""
        e = _elems(msg.at_addr)
        area = e[0] if e else ""
        out = []
        for p in self.cfg.partners.values():
            if p.call in been:
                continue
            if any(a == "*" or SAME.get(a, a) == area for a in p.areas):
                out.append(p.call)
        return out
