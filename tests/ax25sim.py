"""Simulated radio channel for two Ax25Link machines (KISS steps K2/K3).

One shared half-duplex channel at `baud` bit/s: a frame occupies the channel
for TXDELAY + its bits, frames queue behind each other. Every frame goes
through the real codec (encode -> bytes -> decode). Frames are lost at random
(`loss`, seeded = repeatable) or on purpose (`drop(frame, sender) -> bool`).
Time is simulated: an hour of radio takes milliseconds.
"""

from __future__ import annotations

import heapq
import random
from typing import Callable

from prcore.ax25.frame import Frame
from prcore.ax25.link import Ax25Link


class Sim:
    def __init__(self, a: Ax25Link, b: Ax25Link, *, loss: float = 0.0, seed: int = 1,
                 baud: int = 1200, txdelay: float = 0.3,
                 drop: Callable[[Frame, str], bool] | None = None) -> None:
        self.links = {"A": a, "B": b}
        self.peer = {"A": "B", "B": "A"}
        self.loss, self.baud, self.txdelay, self.drop = loss, baud, txdelay, drop
        self.rnd = random.Random(seed)
        self.now = 0.0
        self.busy_until = 0.0
        self._air: list[tuple[float, int, str, bytes]] = []
        self._seq = 0
        self.rx = {"A": bytearray(), "B": bytearray()}
        self.events: dict[str, list] = {"A": [], "B": []}
        self.sent: list[tuple[float, str, Frame]] = []      # everything put on the air
        self.lost = 0

    # --- channel -------------------------------------------------------------------

    def _transmit(self, sender: str, f: Frame) -> None:
        raw = f.encode()
        start = max(self.now, self.busy_until)
        end = start + self.txdelay + (len(raw) + 6) * 8 / self.baud   # + flags/FCS
        self.busy_until = end
        self.sent.append((start, sender, f))
        if self.rnd.random() < self.loss or (self.drop and self.drop(f, sender)):
            self.lost += 1
            return
        self._seq += 1
        heapq.heappush(self._air, (end, self._seq, self.peer[sender], raw))

    def _collect(self) -> None:
        for name, link in self.links.items():
            for f in link.pop_output():
                self._transmit(name, f)
            for ev in link.pop_events():
                self.events[name].append(ev)
                if ev[0] == "data":
                    self.rx[name] += ev[1]

    # --- driving ----------------------------------------------------------------------

    def run(self, until: float = 3600.0, stop: Callable[[], bool] | None = None) -> bool:
        """Advance time until stop() is true (-> True) or nothing is left / until."""
        while True:
            self._collect()
            if stop is not None and stop():
                return True
            times = [link.next_deadline() for link in self.links.values()]
            times = [t for t in times if t is not None]
            if self._air:
                times.append(self._air[0][0])
            if not times:
                return False
            t = max(min(times), self.now)
            if t > until:
                self.now = until
                return False
            self.now = t
            while self._air and self._air[0][0] <= self.now:
                _, _, to, raw = heapq.heappop(self._air)
                link = self.links[to]
                f = Frame.decode(raw, modulo=link.modulo)
                if f.dest == link.mycall:
                    link.receive(f, self.now)
            for link in self.links.values():
                deadline = link.next_deadline()
                if deadline is not None and deadline <= self.now:
                    link.tick(self.now)

    # --- helpers for tests -----------------------------------------------------------

    def kinds(self, sender: str) -> list[str]:
        return [f.kind for _, s, f in self.sent if s == sender]

    def event_names(self, name: str) -> list:
        return [e for e in self.events[name] if e[0] != "data"]


def pair(cfg=None, cfg_b=None) -> tuple[Ax25Link, Ax25Link]:
    """A = OE3ABC (the user who calls), B = OE3GAS-1 (the mailbox)."""
    return (Ax25Link("OE3ABC", "OE3GAS-1", cfg=cfg),
            Ax25Link("OE3GAS-1", "OE3ABC", cfg=cfg_b or cfg))
