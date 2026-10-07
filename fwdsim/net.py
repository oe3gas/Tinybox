"""The simulated network: OE3GAS (hop) and DL0XTC (behind it), plus an optional
stand-in for TinyBox (OE3XTC) used to test fwdsim itself.

    TinyBox OE3XTC  <-- TCP / AGW -->  OE3GAS  <-- in memory, same protocol -->  DL0XTC
"""

from __future__ import annotations

import asyncio
import logging

from .bbs import Peer, SimBBS
from .config import Config
from .link import memory_pair
from .session import ForwardSession, SessionResult
from .store import Store

log = logging.getLogger("fwdsim.net")


class SimNet:
    def __init__(self, cfg: Config, store: Store) -> None:
        self.cfg = cfg
        self.store = store
        t, h, r = cfg.tinybox, cfg.hop, cfg.remote
        self.hop = SimBBS(store, h.call, h.haddress, h.qth, h.bid_start, [
            Peer(t.call, routes=["AUT.EU"], floods=["WW", "EU", "AUT"]),
            Peer(r.call, routes=["DEU.EU"], floods=["WW", "EU", "DEU"]),
        ])
        self.remote = SimBBS(store, r.call, r.haddress, r.qth, r.bid_start, [
            Peer(h.call, routes=["WW"], floods=["*"]),
        ])
        self.hop_results: list[SessionResult] = []

    def bbs(self, call: str) -> SimBBS:
        call = call.upper()
        if call == self.hop.call:
            return self.hop
        if call == self.remote.call:
            return self.remote
        raise KeyError(f"unknown simulated mailbox {call} (use {self.hop.call} or {self.remote.call})")

    async def settle(self, rounds: int = 5) -> None:
        """Run internal forward sessions OE3GAS <-> DL0XTC until both queues are empty."""
        for _ in range(rounds):
            if not self.hop.pending(self.remote.call) and not self.remote.pending(self.hop.call):
                return
            a, b = memory_pair(f"{self.hop.call}>{self.remote.call}",
                               f"{self.remote.call}>{self.hop.call}")
            master = ForwardSession(self.hop, a, self.remote.call, master=True, timeout=10)
            slave = ForwardSession(self.remote, b, self.hop.call, master=False, timeout=10)
            r1, r2 = await asyncio.gather(master.run(), slave.run())
            self.hop_results.append(r1)
            if r1.error or r2.error:
                log.warning("internal hop session failed: %s / %s", r1.error, r2.error)
                return


def make_standin(cfg: Config, store: Store) -> SimBBS:
    """A fwdsim mailbox that plays TinyBox (OE3XTC), with the checks TinyBox should have."""
    t = cfg.tinybox
    return SimBBS(store, t.call, t.haddress, "Hollabrunn", 1,
                  [Peer(cfg.hop.call, routes=["WW"], floods=["*"])],
                  max_bytes=8192, hold_days=60)
