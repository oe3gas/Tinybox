"""Two stations under one call (CR90, audit TB-02).

Over the air the only identity is the callsign - anyone can send it. But when a
station connects (or is connected) under the call of a forward partner while
the real partner is on the frequency, the real one gives itself away: it has
no link with us, so it answers our polls with DM (AX.25 2.2, disconnected
state), and if we called, both may answer our SABM with UA.

The guard watches the frames heard from a partner's call during a forward
session: any DM or FRMR, and more UA than the connect itself explains, mean
"two stations, or the partner lost the link" - in both cases what this session
did cannot be trusted. The forward adapter then holds what was received and
offers again what was sent (adapters/forward.py).

Fed with every received frame: AGW mode from Direwolf's raw monitor ('K'),
KISS/AXUDP mode from the own AX.25 stack. Frames after our own DISC do not
count (a partner may answer it with DM).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from prcore.ax25 import frame as ax
from prcore.ax25.frame import AX25Error

log = logging.getLogger("tinybox.forward")

DM, UA, FRMR = 0x0F, 0x63, 0x87


@dataclass
class Watch:
    mycall: str
    ua_allowed: int                 # 1 when we called (the partner's answer), else 0
    ua: int = 0
    events: list[str] = field(default_factory=list)
    open: bool = True


class LinkGuard:
    def __init__(self) -> None:
        self.watches: dict[str, Watch] = {}

    def watch(self, remote: str, mycall: str, *, we_called: bool) -> None:
        self.watches[remote.upper()] = Watch(mycall.upper(), 1 if we_called else 0)

    def stop(self, remote: str) -> None:
        """Our own DISC goes out now: what follows is the partner's answer to it."""
        w = self.watches.get(remote.upper())
        if w:
            w.open = False

    def result(self, remote: str) -> str:
        """'' = nothing seen, else what was seen. Ends the watch."""
        w = self.watches.pop(remote.upper(), None)
        if w is None or not w.events:
            return ""
        return ", ".join(w.events)

    def heard(self, data: bytes) -> None:
        """One frame heard on the channel (raw AX.25, without FCS)."""
        if not self.watches:
            return
        try:
            dest, src, path, _ = ax.peek(data)
        except AX25Error:
            return
        w = self.watches.get(src.upper())
        if w is None or not w.open or dest.upper() != w.mycall:
            return
        rest = data[7 * (2 + len(path)):]
        if not rest or rest[0] & 0x03 != 0x03:
            return
        u = rest[0] & 0xEF
        if u == UA:
            w.ua += 1
            if w.ua <= w.ua_allowed:
                return
            what = "unexpected UA"
        elif u == DM:
            what = "DM"
        elif u == FRMR:
            what = "FRMR"
        else:
            return
        w.events.append(what)
        log.warning("%s: %s from the partner's call during a forward session - "
                    "two stations under one call?", src, what)


guard = LinkGuard()
