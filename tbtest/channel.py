"""The simulated radio channel inside the AXUDP path (PLANUNG 27, part 2).

Every AXUDP datagram between the test box and a user goes through this relay
instead of straight to the other side:

    user OE1TBA  ──UDP──►  channel 127.0.0.1:10192  ──UDP──►  box OE3TBX-1
                 ◄──────                            ◄──────

With air_baud = 0 the relay passes every frame on at once (no radio). With
air_baud = 1200 it behaves like ONE shared half-duplex frequency with a TNC
per station:

- every station has a send queue (the TNC buffer); frames wait there
- carrier sense: a station sends only when it hears nobody else on the air,
  then p-persistence (persist / slottime, the KISS defaults 63 / 100 ms)
- one key-up = TXDELAY, then all queued frames (at most 7) back to back;
  airtime per frame = (bytes + FCS) * 8 * 1.03 (bit stuffing) / baud
- collisions: a frame is lost at its receiver if another station the receiver
  hears was on the air at the same time, or the receiver itself was sending
  (half duplex)
- hidden stations: a hidden user does not hear the other users and they do
  not hear him - they cannot hold back for each other and collide at the box
  (everybody hears the box, the box hears everybody)
- noise: each user has a quality profile, the frame loss for a 256-byte frame
  in both directions; shorter frames are lost less often (bit error rate)

- the frequency is shared: every station that hears the sender also gets a
  copy of the frame (it is not addressed to it - its AX.25 only sees that the
  channel was busy and holds T1, as on the radio)

The relay only times, copies and drops frames, it never changes them. Box,
users and guest run AXUDP with air time ([axudp] air_baud / txdelay_ms in
tinybox.conf, axudp_air_baud in tbclient.conf): half duplex, T1 starts after
their own estimated transmission, small window, long T1.
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections import deque
from dataclasses import dataclass, field

from prcore import axudp
from prcore.ax25 import frame as ax

log = logging.getLogger("tbtest.channel")

MAX_BURST = 7                 # frames per key-up (a TNC sends what it has, up to MAXFRAME)
STUFFING = 1.03               # HDLC bit stuffing, about 3 % on random data
REPEAT_WINDOW = 120.0         # s: the same I-frame again within this = a retransmission


@dataclass(frozen=True)
class Profile:
    name: str
    loss: float               # frame loss for a 256-byte frame, 0..1, each direction


PROFILES = {"good": Profile("good", 0.01), "medium": Profile("medium", 0.08),
            "poor": Profile("poor", 0.25)}


@dataclass
class Station:
    call: str                                 # as in the frames (box with SSID)
    addr: tuple[str, int]                     # where its AXUDP endpoint listens
    profile: Profile = PROFILES["good"]
    hidden: bool = False
    is_box: bool = False
    queue: deque = field(default_factory=deque)   # (datagram, ax25, arrival time)
    wake: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task | None = None
    recent: deque = field(default_factory=deque)  # (time, key) of sent I-frames
    st: dict = field(default_factory=lambda: dict(
        frames=0, bytes=0, keyups=0, airtime=0.0, delivered=0, lost_noise=0,
        lost_collision=0, repeats=0, wait_sum=0.0, wait_max=0.0, queue_max=0,
        rx_noise=0, rx_collision=0, heard=0))


@dataclass
class Tx:
    station: Station
    start: float
    end: float


def addr_len(ax25: bytes) -> int:
    """Length of the address field (7 bytes per call, the last one has bit 0 set)."""
    for i in range(6, min(len(ax25), 70), 7):
        if ax25[i] & 1:
            return i + 1
    return len(ax25)


def frame_loss(p256: float, nbytes: int) -> float:
    """Loss of a frame of nbytes when a 256-byte frame is lost with p256."""
    if p256 <= 0:
        return 0.0
    return 1.0 - (1.0 - min(p256, 0.999)) ** ((nbytes + 2) / 258)


class Channel:
    def __init__(self, port: int, air_baud: int = 1200, txdelay_ms: int = 300,
                 persist: int = 63, slottime_ms: int = 100, seed: int = 0) -> None:
        self.port = port
        self.air_baud = air_baud
        self.txdelay = txdelay_ms / 1000
        self.persist = persist
        self.slottime = slottime_ms / 1000
        self.rng = random.Random(seed)
        self.stations: dict[str, Station] = {}
        self.txs: list[Tx] = []
        self.busy_total = 0.0
        self._busy_until = 0.0
        self.dropped = {"fcs": 0, "stranger": 0, "no_route": 0}
        self.t0 = 0.0
        self._transport: asyncio.DatagramTransport | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def radio(self) -> bool:
        return self.air_baud > 0

    def add(self, station: Station) -> None:
        self.stations[axudp.norm_call(station.call)] = station

    def find(self, call: str) -> Station | None:
        call = axudp.norm_call(call)
        st = self.stations.get(call)
        if st is not None:
            return st
        base = axudp.base_call(call)
        return next((s for s in self.stations.values()
                     if "-" not in s.call and axudp.base_call(s.call) == base), None)

    # --- life cycle ----------------------------------------------------------------------

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._transport, _ = await self._loop.create_datagram_endpoint(
            lambda: _Proto(self), local_addr=("127.0.0.1", self.port))
        self.t0 = self._loop.time()
        if self.radio:
            for st in self.stations.values():
                st.task = asyncio.create_task(self._sender(st))

    def close(self) -> None:
        for st in self.stations.values():
            if st.task is not None:
                st.task.cancel()
        if self._transport is not None:
            self._transport.close()
            self._transport = None

    # --- receiving a datagram (a station hands a frame to its TNC) --------------------------

    def received(self, datagram: bytes, addr) -> None:
        try:
            ax25 = axudp.decode(datagram)
            dest, src, _path, _rep = ax.peek(ax25)
        except Exception:
            self.dropped["fcs"] += 1
            return
        st = self.find(src)
        if st is None or not axudp.is_loopback(addr[0]):
            self.dropped["stranger"] += 1
            return
        if not self.radio:
            self._send_to(dest, datagram, st)
            st.st["frames"] += 1
            st.st["bytes"] += len(ax25)
            return
        st.queue.append((datagram, ax25, self._loop.time()))
        st.st["queue_max"] = max(st.st["queue_max"], len(st.queue))
        st.wake.set()

    def _send_to(self, dest: str, datagram: bytes, sender: Station) -> bool:
        d = self.find(dest)
        if d is None or self._transport is None:
            self.dropped["no_route"] += 1
            return False
        self._transport.sendto(datagram, d.addr)
        sender.st["delivered"] += 1
        return True

    # --- the channel -------------------------------------------------------------------------

    def hears(self, a: Station, b: Station) -> bool:
        if a is b or a.is_box or b.is_box:
            return True
        return not (a.hidden or b.hidden)

    def busy_for(self, st: Station, now: float) -> bool:
        """Does st hear somebody on the air right now?"""
        return any(t.start <= now < t.end and t.station is not st and self.hears(st, t.station)
                   for t in self.txs)

    def airtime(self, nbytes: int) -> float:
        return (nbytes + 2) * 8 * STUFFING / self.air_baud + 8 / self.air_baud

    async def _sender(self, st: Station) -> None:
        """The TNC of one station: carrier sense, p-persistence, key-up, frames."""
        loop = self._loop
        while True:
            while not st.queue:
                st.wake.clear()
                await st.wake.wait()
            while True:                                    # CSMA
                now = loop.time()
                if not self.busy_for(st, now) and self.rng.randint(0, 255) <= self.persist:
                    break
                await asyncio.sleep(self.slottime)
            now = loop.time()
            burst = [st.queue.popleft() for _ in range(min(MAX_BURST, len(st.queue)))]
            t = now + self.txdelay
            frames = []
            for datagram, ax25, arrived in burst:
                dur = self.airtime(len(ax25))
                frames.append((t, t + dur, datagram, ax25))
                wait = now - arrived
                st.st["wait_sum"] += wait
                st.st["wait_max"] = max(st.st["wait_max"], wait)
                t += dur
            tx = Tx(st, now, t)
            self.txs.append(tx)
            self.busy_total += max(0.0, tx.end - max(tx.start, self._busy_until))
            self._busy_until = max(self._busy_until, tx.end)
            st.st["keyups"] += 1
            st.st["airtime"] += tx.end - tx.start
            for fs, fe, datagram, ax25 in frames:
                st.st["frames"] += 1
                st.st["bytes"] += len(ax25)
                self._count_repeat(st, ax25, now)
                loop.call_at(fe, self._deliver, st, fs, fe, datagram, ax25)
            await asyncio.sleep(max(0.0, tx.end - loop.time()))
            self._prune(loop.time())

    def _count_repeat(self, st: Station, ax25: bytes, now: float) -> None:
        n = addr_len(ax25)
        if len(ax25) <= n + 4:                     # no info field: RR, RNR, SABM ...
            return
        key = (ax25[:7], ax25[n + 3:])             # destination + info (I-frame contents)
        while st.recent and now - st.recent[0][0] > REPEAT_WINDOW:
            st.recent.popleft()
        if any(k == key for _, k in st.recent):
            st.st["repeats"] += 1
        else:
            st.recent.append((now, key))

    def _lost_at(self, sender: Station, r: Station, fs: float, fe: float,
                 nbytes: int) -> str:
        """Why receiver r does not get this frame: 'collision', 'noise' or ''."""
        for t in self.txs:
            if t.station is sender or t.end <= fs or t.start >= fe:
                continue
            if t.station is r or self.hears(r, t.station):
                return "collision"
        if sender.is_box or r.is_box:                  # box <-> user: the user's quality
            loss = (r if sender.is_box else sender).profile.loss
        else:                                          # user hears user: the worse one
            loss = max(r.profile.loss, sender.profile.loss)
        return "noise" if self.rng.random() < frame_loss(loss, nbytes) else ""

    def _deliver(self, sender: Station, fs: float, fe: float, datagram: bytes,
                 ax25: bytes) -> None:
        """End of a frame on the air: to its addressee - and, as on the radio, to
        every other station that hears the sender (they do not take it, but
        their AX.25 sees that the channel was busy: T1 waits)."""
        try:
            dest = ax.peek(ax25)[0]
        except Exception:
            return
        d = self.find(dest)
        if d is None:
            self.dropped["no_route"] += 1
            return
        why = self._lost_at(sender, d, fs, fe, len(ax25))
        if why == "collision":
            sender.st["lost_collision"] += 1
            d.st["rx_collision"] += 1
        elif why == "noise":
            sender.st["lost_noise"] += 1
            d.st["rx_noise"] += 1
        elif self._transport is not None:
            self._transport.sendto(datagram, d.addr)
            sender.st["delivered"] += 1
        if log.isEnabledFor(logging.DEBUG):
            log.debug("%s>%s %d B %s (%.2f-%.2f)", sender.call, d.call, len(ax25),
                      why.upper() or "ok", fs - self.t0, fe - self.t0)
        if self._transport is None:
            return
        for r in self.stations.values():               # the others on the frequency
            if r is sender or r is d or not self.hears(r, sender):
                continue
            if not self._lost_at(sender, r, fs, fe, len(ax25)):
                self._transport.sendto(datagram, r.addr)
                r.st["heard"] += 1

    def _prune(self, now: float) -> None:
        if len(self.txs) > 200:
            self.txs = [t for t in self.txs if t.end > now - 30]

    # --- result ------------------------------------------------------------------------------

    def summary(self) -> dict:
        now = self._loop.time() if self._loop else 0.0
        span = max(1e-6, now - self.t0)
        rows = []
        for st in self.stations.values():
            s = st.st
            rows.append({"call": st.call, "box": st.is_box, "profile": st.profile.name,
                         "hidden": st.hidden, **{k: (round(v, 2) if isinstance(v, float) else v)
                                                 for k, v in s.items()},
                         "wait_avg": round(s["wait_sum"] / s["frames"], 2) if s["frames"] else 0})
        return {"air_baud": self.air_baud, "txdelay_ms": round(self.txdelay * 1000),
                "persist": self.persist, "slottime_ms": round(self.slottime * 1000),
                "secs": round(span, 1),
                "busy_pct": round(100 * self.busy_total / span, 1) if self.radio else None,
                "dropped": dict(self.dropped), "stations": rows}


class _Proto(asyncio.DatagramProtocol):
    def __init__(self, ch: Channel) -> None:
        self.ch = ch

    def datagram_received(self, data: bytes, addr) -> None:
        try:
            self.ch.received(data, addr)
        except Exception:
            log.exception("channel: datagram from %s", addr)

    def error_received(self, exc: Exception) -> None:
        log.debug("channel socket: %s", exc)


def assign_profiles(calls: list[str], mix: dict[str, float], hidden: float,
                    overrides: dict[str, tuple[str, bool | None]],
                    rng: random.Random) -> dict[str, tuple[Profile, bool]]:
    """Quality per user: by the mix (shares of good/medium/poor) and the share of hidden
    users, shuffled with the seed; overrides from tbtest.conf win."""
    n = len(calls)
    names: list[str] = []
    for name, share in mix.items():
        names += [name] * round(share * n)
    while len(names) < n:
        names.append("good")
    names = names[:n]
    rng.shuffle(names)
    hide = set(rng.sample(calls, round(hidden * n))) if n else set()
    out = {}
    for call, name in zip(calls, names):
        prof, hid = PROFILES[name], call in hide
        if call in overrides:
            o_name, o_hid = overrides[call]
            prof = PROFILES[o_name] if o_name else prof
            hid = hid if o_hid is None else o_hid
        out[call] = (prof, hid)
    return out
