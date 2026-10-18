"""Passive AX.25 link quality (CR67, part C) - the same numbers for every modem.

kisshub sees every frame of a connection in both directions: the frames its
clients (TinyBox, client) hand to the TNC ("tx") and the frames the TNC
receives ("rx"). From that it measures, per pair of stations, without help
from TinyBox:

    connect      SABM(E) tries until UA, version 2.0 / 2.2, refused (DM)
    I frames     per direction: frames, info bytes, new bytes, retransmissions
                 (same N(S) with the same info again before it was acknowledged)
    S frames     RR / RNR / REJ / SREJ, polls (an S command with P=1 - mostly a
                 T1 expiry: the sender waited in vain)
    ack time     an I frame (sent once) until the other side acknowledges it
                 (N(R) moves past it) - Karn: retransmitted frames do not count
    answer gap   a frame of station X after the last frame of station Y: how
                 long the channel "turns around" (the long pauses between the
                 two stations show up here)
    goodput      new info bytes per second of connection
    efficiency   new info bytes / all bytes both stations sent for this link

Times are taken when a frame passes the hub: tx = handed to the TNC, rx =
delivered by the TNC (after the modem decoded it). So the ack time contains
the own airtime, the modem's waiting (VARA: DCD, persistence), the other
station's processing (T2!) and its airtime - measured the same way for
PK-232 (HDLC) and VARA, so the numbers compare directly.

Finished links go to on_closed (one dict, kisshub writes it to the links
file as one JSON line) - run the same session once over the PK-232 and once
over VARA and compare the lines.
"""

from __future__ import annotations

import hashlib
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable

from prcore.ax25.frame import AX25Error, Frame, peek

IDLE_CLOSE_SEC = 900          # a link without any frame this long is reported as gone
CLOSED_KEEP = 20              # finished links kept for the status
SAMPLES = 300                 # ack times / answer gaps kept per link and direction
SN_WINDOW_SEC = 1.5           # VARA's SN line and the received frame belong together
SIZE_CLASSES = (32, 64, 128, 256, 512, 1024)   # frame size histogram, last class = more
MINUTES = 60                  # per-minute counters kept


def _stats(values) -> dict | None:
    """avg / min / max / n of a list of seconds (None when empty)."""
    v = list(values)
    if not v:
        return None
    return {"avg": round(sum(v) / len(v), 2), "min": round(min(v), 2),
            "max": round(max(v), 2), "n": len(v)}


def _acked(ns: int, nr: int, modulo: int) -> bool:
    """Is I frame N(S)=ns acknowledged by N(R)=nr? (nr = next expected frame:
    everything 'before' nr in the sequence circle, up to half the circle back)."""
    back = (nr - 1 - ns) % modulo
    return back < modulo // 2


def _size_class(n: int) -> str:
    for limit in SIZE_CLASSES:
        if n <= limit:
            return f"<={limit}"
    return f">{SIZE_CLASSES[-1]}"


@dataclass
class Direction:
    """Everything one station sent on the link."""
    frames: int = 0
    bytes: int = 0                 # whole frames (header + info)
    i_frames: int = 0
    info_bytes: int = 0            # info of all I frames, retransmissions included
    new_bytes: int = 0             # info sent for the first time
    retrans: int = 0               # I frames sent again
    rr: int = 0
    rnr: int = 0
    rej: int = 0
    srej: int = 0
    polls: int = 0                 # S commands with P=1 (T1 expired, "are you there?")
    airtime: float = 0.0           # estimated seconds on the air
    acks: deque = field(default_factory=lambda: deque(maxlen=SAMPLES))   # ack times
    gaps: deque = field(default_factory=lambda: deque(maxlen=SAMPLES))   # answer gaps
    sn: deque = field(default_factory=lambda: deque(maxlen=SAMPLES))     # VARA SN (dB)

    def summary(self) -> dict:
        return {"frames": self.frames, "bytes": self.bytes, "i_frames": self.i_frames,
                "info_bytes": self.info_bytes, "new_bytes": self.new_bytes,
                "retrans": self.retrans,
                "retrans_pct": round(100 * self.retrans / self.i_frames, 1)
                if self.i_frames else None,
                "rr": self.rr, "rnr": self.rnr, "rej": self.rej, "srej": self.srej,
                "polls": self.polls, "airtime_sec": round(self.airtime, 1),
                "ack_sec": _stats(self.acks), "answer_gap_sec": _stats(self.gaps),
                "sn_db": _stats(self.sn)}


class Link:
    """One AX.25 connection between two stations, as heard by the hub."""

    def __init__(self, a: str, b: str, t: float, wall: float, modulo: int = 8) -> None:
        self.a, self.b = a, b          # a = the station that started it (or was seen first)
        self.modulo = modulo
        self.version = "2.2" if modulo == 128 else "2.0"
        self.state = "connecting"      # connecting | connected | disconnecting | closed
        self.t0, self.wall0 = t, wall
        self.t_connected: float | None = None
        self.t_last = t
        self.end_reason = ""
        self.connect_tries = 0
        self.local: set[str] = set()   # calls of our own clients (they send "tx")
        self.dir = {a: Direction(), b: Direction()}
        # I frames sent and not yet acknowledged, per sender: ns -> [t_first, sends, hash]
        self.outstanding: dict[str, dict[int, list]] = {a: {}, b: {}}
        self.last_sender: str | None = None
        self.last_t = t

    def other(self, call: str) -> str:
        return self.b if call == self.a else self.a

    def summary(self, now: float) -> dict:
        end = self.t_last if self.state == "closed" else now
        conn = (end - self.t_connected) if self.t_connected is not None else 0.0
        total = sum(d.bytes for d in self.dir.values())
        new = sum(d.new_bytes for d in self.dir.values())
        return {
            "a": self.a, "b": self.b, "local": sorted(self.local),
            "state": self.state, "version": self.version, "modulo": self.modulo,
            "started": self.wall0, "duration_sec": round(end - self.t0, 1),
            "connected_sec": round(conn, 1),
            "connect_sec": round(self.t_connected - self.t0, 1)
            if self.t_connected is not None else None,
            "connect_tries": self.connect_tries, "end": self.end_reason or None,
            "goodput_bps": round(new * 8 / conn, 1) if conn > 0 else None,
            "goodput_Bps": round(new / conn, 1) if conn > 0 else None,
            "efficiency_pct": round(100 * new / total, 1) if total else None,
            "dir": {self.a: self.dir[self.a].summary(), self.b: self.dir[self.b].summary()},
        }


@dataclass
class Heard:
    """A station heard by the TNC (rx only)."""
    frames: int = 0
    bytes: int = 0
    first: float = 0.0
    last: float = 0.0              # wall clock
    sn: deque = field(default_factory=lambda: deque(maxlen=SAMPLES))


class LinkStats:
    def __init__(self, airtime: Callable[[int], float] | None = None,
                 on_closed: Callable[[dict], None] | None = None,
                 sn_window_sec: float = SN_WINDOW_SEC) -> None:
        self.airtime = airtime or (lambda n: 0.0)
        self.on_closed = on_closed or (lambda rec: None)
        self.sn_window = sn_window_sec
        self.links: dict[frozenset, Link] = {}
        self.closed: deque[dict] = deque(maxlen=CLOSED_KEEP)
        self.heard: dict[str, Heard] = {}
        self.sizes = {"tx": {}, "rx": {}}          # size class -> frames
        self.minutes: deque[dict] = deque(maxlen=MINUTES)   # per-minute counters
        self.undecodable = 0
        self._last_rx: tuple[float, str, Link | None] | None = None  # for the SN
        self._pending_sn: tuple[float, float] | None = None          # SN before its frame
        self._rx_has_sn = True

    # --- frames -------------------------------------------------------------------------

    def frame(self, raw: bytes, t: float, tx: bool, wall: float | None = None) -> None:
        """One frame on the air: tx = our client sent it, rx = the TNC received it."""
        wall = time.time() if wall is None else wall
        self._count(raw, t, tx)
        try:
            dest, src, path, _ = peek(raw)           # the address field finds the link ...
            key = frozenset((src, dest))
            link = self.links.get(key)
            modulo = link.modulo if link is not None else self._guess_modulo(raw, len(path))
            f = Frame.decode(raw, modulo)            # ... and the link the modulo
        except AX25Error:
            self.undecodable += 1
            return
        if not tx:
            h = self.heard.setdefault(f.src, Heard(first=wall))
            h.frames += 1
            h.bytes += len(raw)
            h.last = wall
        if f.kind in ("UI", "XID", "TEST"):
            if not tx:
                self._rx_frame(t, f.src, None)
            return
        if f.kind in ("SABM", "SABME") and f.command:
            # a new connection - unless it is a repeated SABM of the one being set up
            if link is None or link.state != "connecting":
                if link is not None:
                    self._close(link, "new connect")
                link = Link(f.src, f.dest, t, wall, 128 if f.kind == "SABME" else 8)
                self.links[key] = link
            link.connect_tries += 1
            if f.kind == "SABM":
                link.modulo, link.version = 8, "2.0"   # (fell back to) v2.0
        elif link is None:
            if f.kind in ("UA", "DM", "DISC", "FRMR"):
                return                                  # end of something we never saw
            link = Link(f.src, f.dest, t, wall, modulo)
            link.state = "connected"                    # joined in the middle
            link.t_connected = t
            self.links[key] = link
        if tx:
            link.local.add(f.src)
        self._on_link_frame(link, f, raw, t)
        if not tx:
            self._rx_frame(t, f.src, link)

    @staticmethod
    def _guess_modulo(raw: bytes, digis: int) -> int:
        """Joined a link without seeing SABM(E): an I frame has the PID (F0) after
        one control byte (mod 8) or after two (mod 128); an S frame is 1 or 2 bytes."""
        rest = raw[14 + 7 * digis:]
        if not rest or rest[0] & 0x03 == 0x03:          # U frame: no difference
            return 8
        if rest[0] & 0x01 == 0:                         # I frame
            return 128 if len(rest) >= 3 and rest[2] == 0xF0 and rest[1] != 0xF0 else 8
        return 128 if len(rest) == 2 else 8             # S frame

    def _on_link_frame(self, link: Link, f: Frame, raw: bytes, t: float) -> None:
        sender = f.src
        if sender not in link.dir:                      # should not happen (same pair)
            return
        d = link.dir[sender]
        d.frames += 1
        d.bytes += len(raw)
        d.airtime += self.airtime(len(raw))
        # answer gap: the channel turned around from the other station to this one
        if link.last_sender is not None and link.last_sender != sender:
            d.gaps.append(t - link.last_t)
        link.last_sender, link.last_t, link.t_last = sender, t, t
        k = f.kind
        if k == "UA" and link.state == "connecting":
            link.state, link.t_connected = "connected", t
        elif k == "UA" and link.state == "disconnecting":
            self._close(link, "disc")
        elif k == "DM":
            self._close(link, "refused" if link.state == "connecting" else "dm")
        elif k == "DISC":
            link.state = "disconnecting"
        elif k == "FRMR":
            link.end_reason = "frmr"
        elif f.is_i:
            d.i_frames += 1
            d.info_bytes += len(f.info)
            h = hashlib.blake2b(f.info, digest_size=8).digest()
            out = link.outstanding[sender]
            rec = out.get(f.ns)
            if rec is not None and rec[2] == h:
                d.retrans += 1                          # same frame again
                rec[1] += 1
            else:
                out[f.ns] = [t, 1, h]
                d.new_bytes += len(f.info)
            self._ack(link, sender, f.nr, t)            # an I frame carries N(R) too
        elif f.is_s:
            if k == "RR":
                d.rr += 1
            elif k == "RNR":
                d.rnr += 1
            elif k == "REJ":
                d.rej += 1
            elif k == "SREJ":
                d.srej += 1
            if f.command and f.pf:
                d.polls += 1
            if k != "SREJ":                             # SREJ asks for one frame only
                self._ack(link, sender, f.nr, t)

    def _ack(self, link: Link, sender: str, nr: int, t: float) -> None:
        """sender acknowledges the other station's I frames up to nr."""
        other = link.other(sender)
        out = link.outstanding[other]
        for ns in [n for n in out if _acked(n, nr, link.modulo)]:
            t_first, sends, _ = out.pop(ns)
            if sends == 1:                              # Karn: only frames sent once
                link.dir[other].acks.append(t - t_first)

    def _close(self, link: Link, reason: str) -> None:
        if link.state == "closed":
            return
        link.state = "closed"
        link.end_reason = link.end_reason or reason
        rec = link.summary(link.t_last)
        self.closed.append(rec)
        for key, l in list(self.links.items()):
            if l is link:
                del self.links[key]
        self.on_closed(rec)

    def tick(self, t: float) -> None:
        """Called every few seconds: links nobody talks on any more are reported."""
        for link in list(self.links.values()):
            if link.state != "closed" and t - link.t_last > IDLE_CLOSE_SEC:
                self._close(link, "idle")

    def close_all(self, reason: str = "kisshub stopped") -> None:
        for link in list(self.links.values()):
            self._close(link, reason)

    # --- per-minute counters, sizes ---------------------------------------------------

    def _count(self, raw: bytes, t: float, tx: bool) -> None:
        minute = int(t // 60)
        if not self.minutes or self.minutes[-1]["m"] != minute:
            self.minutes.append({"m": minute, "tx": 0, "rx": 0, "tx_bytes": 0, "rx_bytes": 0,
                                 "airtime": 0.0})
        m = self.minutes[-1]
        side = "tx" if tx else "rx"
        m[side] += 1
        m[side + "_bytes"] += len(raw)
        m["airtime"] += self.airtime(len(raw))
        c = _size_class(len(raw))
        self.sizes[side][c] = self.sizes[side].get(c, 0) + 1

    # --- VARA SN (part A) ----------------------------------------------------------------

    def _rx_frame(self, t: float, src: str, link: Link | None) -> None:
        """A frame arrived: take an SN that came just before it, else wait for one."""
        p = self._pending_sn
        self._pending_sn = None
        if p is not None and t - p[0] <= self.sn_window:
            self._give_sn(src, link, p[1])
            self._last_rx = None
        else:
            self._last_rx = (t, src, link)

    def sn(self, value: float, t: float) -> str | None:
        """VARA reported an SN: give it to the frame received just before (or the
        next one). Returns the call it went to, None if not (yet) assigned."""
        r = self._last_rx
        if r is not None and t - r[0] <= self.sn_window:
            self._last_rx = None
            self._give_sn(r[1], r[2], value)
            return r[1]
        self._pending_sn = (t, value)
        return None

    def _give_sn(self, src: str, link: Link | None, value: float) -> None:
        h = self.heard.get(src)
        if h is not None:
            h.sn.append(value)
        if link is not None and src in link.dir:
            link.dir[src].sn.append(value)

    # --- status -----------------------------------------------------------------------------

    def status(self, now: float) -> dict:
        last = list(self.minutes)[-10:]
        return {
            "links": [l.summary(now) for l in self.links.values()],
            "closed": list(self.closed)[-5:],
            "stations": {c: {"frames": h.frames, "bytes": h.bytes, "last": h.last,
                             "sn_db": _stats(h.sn),
                             "sn_last": h.sn[-1] if h.sn else None}
                         for c, h in sorted(self.heard.items(), key=lambda x: -x[1].last)[:30]},
            "sizes": self.sizes,
            "last_10min": {"tx": sum(m["tx"] for m in last), "rx": sum(m["rx"] for m in last),
                           "tx_bytes": sum(m["tx_bytes"] for m in last),
                           "rx_bytes": sum(m["rx_bytes"] for m in last),
                           "airtime_sec": round(sum(m["airtime"] for m in last), 1)},
            "undecodable": self.undecodable,
        }

    def lines(self, now: float) -> list[str]:
        """Short text for the console (LINKS)."""
        out = []
        for rec in [l.summary(now) for l in self.links.values()] + list(self.closed)[-5:]:
            out.append(describe(rec))
        return out or ["no AX.25 links seen yet"]


def describe(rec: dict) -> str:
    """One line per link: what kisshub logs when a link ends."""
    def side(call: str) -> str:
        d = rec["dir"][call]
        ack = d["ack_sec"]
        gap = d["answer_gap_sec"]
        sn = d["sn_db"]
        return (f"{call}: I {d['i_frames']} ({d['new_bytes']} B new), retrans "
                f"{d['retrans']}{' (' + str(d['retrans_pct']) + '%)' if d['retrans_pct'] is not None else ''}, "
                f"REJ {d['rej']} SREJ {d['srej']} polls {d['polls']}, "
                f"ack {ack['avg'] if ack else '-'} s, answers after "
                f"{gap['avg'] if gap else '-'} s (max {gap['max'] if gap else '-'})"
                + (f", SN {sn['avg']} dB" if sn else ""))
    head = (f"{rec['a']} <> {rec['b']} [{rec['state']}{', ' + rec['end'] if rec['end'] else ''}] "
            f"v{rec['version']}, {rec['connected_sec']} s connected, "
            f"{rec['goodput_Bps'] if rec['goodput_Bps'] is not None else '-'} B/s, "
            f"efficiency {rec['efficiency_pct'] if rec['efficiency_pct'] is not None else '-'}%"
            + (f", connect {rec['connect_sec']} s / {rec['connect_tries']} tries"
               if rec["connect_sec"] is not None else ""))
    return head + "\n    " + "\n    ".join(side(c) for c in (rec["a"], rec["b"]))
