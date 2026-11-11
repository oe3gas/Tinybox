"""How much the client sends because another station asked (CR97, audit TB-03).

A short line from a peer (//FGET, //IMG, //ST, //HEARD?, //PING) makes the client
transmit - under its own call, on a shared channel. The calls of the asking
station can be made up, so every such answer comes out of two token buckets:
one per base call and one for all stations together, refilled over REFILL_SEC.
On top, answers that cost a lot are counted per call and thing (the same file
at most twice an hour, a speed test every ten minutes).

What the user starts himself (sending a picture, a chat line) is not counted.
"""

from __future__ import annotations

import logging
import time

log = logging.getLogger(__name__)

PER_CALL_BYTES = 96 * 1024      # one station: a 64 KB file plus some pictures
ALL_BYTES = 256 * 1024          # everybody together
REFILL_SEC = 30 * 60            # ... per half hour
MAX_KEYS = 500                  # remembered (call, thing) pairs


def _base(call: str) -> str:
    return call.upper().split("-", 1)[0]


class Bucket:
    def __init__(self, capacity: float, refill_sec: float, clock=time.monotonic) -> None:
        self.capacity, self.rate, self.clock = capacity, capacity / refill_sec, clock
        self.tokens, self.t = capacity, clock()

    def _fill(self) -> None:
        now = self.clock()
        self.tokens = min(self.capacity, self.tokens + (now - self.t) * self.rate)
        self.t = now

    def can(self, n: float) -> bool:
        self._fill()
        return self.tokens >= n

    def take(self, n: float) -> None:
        self._fill()
        self.tokens -= n


class SendBudget:
    def __init__(self, clock=time.monotonic) -> None:
        self.clock = clock
        self.calls: dict[str, Bucket] = {}
        self.all = Bucket(ALL_BYTES, REFILL_SEC, clock)
        self._seen: dict[tuple[str, str], list[float]] = {}
        self.refused: dict[str, float] = {}      # CR110: base call -> last answer held back

    def allow(self, call: str, nbytes: int, what: str = "") -> bool:
        """May we send nbytes because call asked? Takes them if yes."""
        b = self.calls.get(_base(call))
        if b is None:
            if len(self.calls) >= MAX_KEYS:
                self.calls.clear()
            b = self.calls[_base(call)] = Bucket(PER_CALL_BYTES, REFILL_SEC, self.clock)
        if not (b.can(nbytes) and self.all.can(nbytes)):
            log.warning("%s: %s not sent - too much asked for (%d bytes)", call, what or "answer",
                        nbytes)
            self._refuse(call)
            return False
        b.take(nbytes)
        self.all.take(nbytes)
        return True

    def _refuse(self, call: str) -> None:
        if len(self.refused) >= MAX_KEYS:
            self.refused.clear()
        self.refused[_base(call)] = self.clock()

    def slowed(self, call: str, window_sec: float = 600) -> bool:
        """CR110: an answer to call was held back within window_sec."""
        t = self.refused.get(_base(call))
        return t is not None and self.clock() - t < window_sec

    def often(self, call: str, key: str, times: int, window_sec: float) -> bool:
        """True if call asked for key `times` times within window_sec already
        (then it is not answered); otherwise counts this one."""
        now = self.clock()
        k = (_base(call), key)
        hits = [t for t in self._seen.get(k, []) if now - t < window_sec]
        if len(hits) >= times:
            log.warning("%s: %s asked for too often - not answered", call, key)
            self._seen[k] = hits
            self._refuse(call)
            return True
        if len(self._seen) >= MAX_KEYS:
            self._seen.clear()
        self._seen[k] = hits + [now]
        return False


def of(core) -> SendBudget:
    """The one budget of a client core."""
    b = getattr(core, "_send_budget", None)
    if b is None:
        b = core._send_budget = SendBudget()
    return b
