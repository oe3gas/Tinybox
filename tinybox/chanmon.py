"""Channel monitor for the KISS mode (CR41, Weg 1).

kisshub passes every frame the TNC hears and every frame the other hub clients
(brocastd) send on to TinyBox; TinyBox adds its own. From that stream this
module estimates how busy the channel is.

A KISS TNC reports no carrier detect, no signal level, no frames with a bad
checksum and not when it really transmitted. So the air time of a frame is an
estimate: TXDELAY + (bytes + flags/FCS) * 8 / air baud. Frames sent back to
back really share one key-up, so the estimate is slightly high for bursts -
good enough to tell "quiet channel" from "busy channel".

Kept in memory only: the last 60 minutes of frames, the heard list since the
start (at most MAX_HEARD calls).
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass

KEEP_SEC = 3600
MAX_HEARD = 200


@dataclass
class Heard:
    call: str
    first: float            # wall clock (time.time) for display
    last: float
    frames: int = 0
    bytes: int = 0
    air: float = 0.0        # estimated seconds on air
    own: bool = False
    via: str = ""           # last digipeater path, "" = direct


class ChannelMonitor:
    def __init__(self, mycall: str, air_baud: int, txdelay_sec: float) -> None:
        self.mycall = mycall.upper()
        self.air_baud = air_baud
        self.txdelay = txdelay_sec
        self.started = time.monotonic()
        self.events: deque[tuple[float, float, bool]] = deque()   # (monotonic, air, own)
        self.heard: dict[str, Heard] = {}

    def airtime(self, nbytes: int) -> float:
        return self.txdelay + (nbytes + 4) * 8 / self.air_baud

    def record(self, src: str, nbytes: int, *, path: list[str] | None = None,
               now: float | None = None, wall: float | None = None) -> None:
        """One frame on the channel (heard, sent by another hub client, or our own)."""
        now = time.monotonic() if now is None else now
        wall = time.time() if wall is None else wall
        own = src.upper() == self.mycall
        air = self.airtime(nbytes)
        self.events.append((now, air, own))
        while self.events and self.events[0][0] < now - KEEP_SEC:
            self.events.popleft()
        h = self.heard.get(src)
        if h is None:
            if len(self.heard) >= MAX_HEARD:          # forget the longest silent one
                del self.heard[min(self.heard.values(), key=lambda x: x.last).call]
            h = self.heard[src] = Heard(src, wall, wall, own=own)
        h.last = wall
        h.frames += 1
        h.bytes += nbytes
        h.air += air
        h.via = ",".join(path or [])

    # --- evaluation -----------------------------------------------------------------

    def load(self, window_sec: float, now: float | None = None) -> dict:
        """Share of the window the channel was busy (0..1), total / own / others.
        A window that started before TinyBox did counts only from the start."""
        now = time.monotonic() if now is None else now
        span = max(1.0, min(window_sec, now - self.started))
        own = other = 0.0
        frames = 0
        for t, air, is_own in self.events:
            if t >= now - window_sec:
                frames += 1
                if is_own:
                    own += air
                else:
                    other += air
        return {"window_sec": window_sec, "span_sec": round(span),
                "total": min(1.0, (own + other) / span), "own": min(1.0, own / span),
                "other": min(1.0, other / span), "frames": frames}

    def per_minute(self, minutes: int = 60, now: float | None = None) -> list[dict]:
        """Oldest first: frames and busy share per minute (own / others)."""
        now = time.monotonic() if now is None else now
        out = [{"frames": 0, "own": 0.0, "other": 0.0} for _ in range(minutes)]
        for t, air, is_own in self.events:
            age = now - t
            if 0 <= age < minutes * 60:
                b = out[minutes - 1 - int(age // 60)]
                b["frames"] += 1
                b["own" if is_own else "other"] += air
        for b in out:
            b["own"] = round(min(1.0, b["own"] / 60), 3)
            b["other"] = round(min(1.0, b["other"] / 60), 3)
        return out

    def heard_list(self, limit: int = 30) -> list[dict]:
        rows = sorted(self.heard.values(), key=lambda x: x.last, reverse=True)[:limit]
        return [{"call": h.call, "first": h.first, "last": h.last, "frames": h.frames,
                 "bytes": h.bytes, "air_sec": round(h.air, 1), "own": h.own, "via": h.via}
                for h in rows]

    def snapshot(self) -> dict:
        return {"load_1min": self.load(60), "load_10min": self.load(600),
                "per_minute": self.per_minute(60), "heard": self.heard_list(),
                "air_baud": self.air_baud, "txdelay_ms": round(self.txdelay * 1000)}
