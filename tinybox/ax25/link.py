"""AX.25 data link state machine for ONE connection (KISS step K2).

Follows the SDL of the AX.25 2.2 specification (Direwolf's ax25_link.c
implements the same SDL). Step K2 covers the v2.0 part: modulo 8, REJ,
RR/RNR, T1/T2/T3, N2. K3 adds SABME / modulo 128 / SREJ / XID.

The machine is PURE: no clock, no sockets, no asyncio. Every call gets the
current time `now` (seconds, any monotonic origin) and leaves its results in
two lists the caller drains:

    pop_output() -> [Frame, ...]      frames to transmit, in order
    pop_events() -> [(name, arg), ...]
        ("connected", "incoming" | "outgoing")
        ("data", bytes)                 in-order payload for the session
        ("reset", reason)               link re-established, unacked data lost
        ("disconnected", reason)        "remote" | "local" | "retryout" |
                                        "refused" | "timeout" | "dm" | "protocol"

and next_deadline() says when tick(now) must be called at the latest. That
makes the machine testable without radio and network (tests/ax25sim.py).

Timers
    T1  acknowledgement timer; value T1V from the smoothed round trip time
        SRT (SDL "select T1 value": SRT = 7/8 SRT + 1/8 measured, T1V = 2 SRT;
        after an expiry T1V = SRT * 2^(RC+1)), clamped to t1_min..t1_max
    T2  acknowledgement delay: restarted by every received I frame, so the RR
        goes out once the peer's burst is over - one RR for the whole window
    T3  idle link check (poll after t3 seconds without traffic)

Own transmit time: a KISS TNC does not report when a frame has actually gone
out. At 1200 Bd four 128-byte frames take over 5 s, so a T1 started when the
frames are queued would expire before any answer can come. The machine
therefore estimates its own air time (air_baud, txdelay) and starts T1 from
the estimated end of transmission - what Direwolf does by pausing T1 while
it transmits. The same holds while OTHERS transmit (half duplex, T1 is
paused while the channel is busy in Direwolf): receive() pauses T1 for the
air time of every frame of this link, and the KISS adapter reports all other
frames heard on the frequency with channel_busy().
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import IntEnum

from .frame import Frame, i_frame, s_frame, u_frame


class State(IntEnum):
    # numbers as in Direwolf's ax25_link.c, so 'state=' in link quality means the same
    DISCONNECTED = 0
    AWAITING_CONNECTION = 1
    AWAITING_RELEASE = 2
    CONNECTED = 3
    TIMER_RECOVERY = 4
    AWAITING_V22_CONNECTION = 5      # K3


@dataclass(frozen=True)
class LinkCfg:
    paclen: int = 128            # N1: max info bytes per I frame we send
    maxframe: int = 4            # k: max unacknowledged I frames (modulo 8: 1..7)
    n2: int = 10                 # max retries
    srt_init_sec: float = 2.5    # starting SRT per hop (T1V = 2 * SRT * hops)
    t1_min_sec: float = 3.0
    t1_max_sec: float = 30.0
    t2_sec: float = 1.5          # 0 = acknowledge every I frame at once
    t3_sec: float = 300.0        # 0 = no idle check
    max_rx_info: int = 512       # longer I frames from the air are dropped
    air_baud: int = 1200         # radio bit rate, for the own transmit time
    txdelay_sec: float = 0.3     # key-up time per transmission


@dataclass
class _Sent:
    info: bytes
    sends: int = 0


class Ax25Link:
    """One AX.25 connection between mycall and remote."""

    def __init__(self, mycall: str, remote: str, path: list[str] | None = None,
                 cfg: LinkCfg | None = None, now: float = 0.0) -> None:
        self.mycall = mycall.upper()
        self.remote = remote.upper()
        self.path = list(path or [])          # digipeaters in OUR sending order
        self.cfg = cfg or LinkCfg()
        self.created = now
        self.state = State.DISCONNECTED
        self.modulo = 8
        self.k = self.cfg.maxframe
        self._reset_vars()
        hops = 1 + len(self.path)
        self.srt = self.cfg.srt_init_sec * hops
        self.t1v = self._clamp(2 * self.srt)
        self.rc = 0
        self.t1_at: float | None = None
        self.t1_started: float | None = None
        self.t2_at: float | None = None
        self.t3_at: float | None = None
        self.queue: deque[bytes] = deque()     # not yet sent
        self.retx: deque[_Sent] = deque()      # to send again (REJ, recovery)
        self.own_busy = False
        self._reestablish = False              # SABM after an error, session stays
        self._rx_accepted = 0                  # in-sequence I frames, for dup detection
        self._out: list[Frame] = []
        self._now = now
        self.tx_end = now                      # estimated end of our own transmission
        self.tx_busy = 0.0                     # estimated seconds on air (tx_busy_ms)
        self._events: list[tuple[str, object]] = []
        # counters in the format of linkq.parse() (PLANUNG.md section 14)
        self.c = dict(i_new=0, i_retry=0, bytes_new=0, bytes_retry=0, i_rx=0,
                      retry_rx=0, rej_rx=0, rej_tx=0, t1_exp=0, rnr_rx=0, bytes_rx=0)

    # ======================================================================
    # public interface
    # ======================================================================

    def connect(self, now: float) -> None:
        """Start an outgoing connection (SABM)."""
        self._now = now
        if self.state != State.DISCONNECTED:
            return
        self._establish(now)

    def disconnect(self, now: float) -> None:
        """Release the link. Unsent data is dropped: the caller waits for
        is_idle before calling this when it wants everything delivered."""
        self._now = now
        if self.state in (State.CONNECTED, State.TIMER_RECOVERY):
            self.queue.clear()
            self.retx.clear()
            self.rc = 0
            self._tx_u("DISC", command=True, pf=True)
            self._stop_t3()
            self._start_t1(now)
            self.t2_at = None
            self.state = State.AWAITING_RELEASE
        elif self.state == State.AWAITING_CONNECTION:
            self._stop_t1()
            self._to_disconnected("local")

    def send(self, data: bytes, now: float) -> None:
        """Queue payload; it is cut into I frames of at most paclen bytes."""
        self._now = now
        n = self.cfg.paclen
        self.queue.extend(data[i:i + n] for i in range(0, len(data), n))
        self._pump(now)

    def set_busy(self, busy: bool, now: float) -> None:
        """Our receiver cannot take more (RNR) / can again (RR)."""
        self._now = now
        if busy == self.own_busy:
            return
        self.own_busy = busy
        if self.state in (State.CONNECTED, State.TIMER_RECOVERY):
            self._tx_s("RNR" if busy else "RR", command=False, pf=False)
            self.t2_at = None

    def receive(self, f: Frame, now: float) -> None:
        """A frame from the air addressed to this link (dest = mycall, src = remote)."""
        self._now = now
        self.channel_busy(self._airtime(len(f.encode())), now)
        if self.state == State.DISCONNECTED:
            self._rx_disconnected(f, now)
        elif self.state == State.AWAITING_CONNECTION:
            self._rx_awaiting_connection(f, now)
        elif self.state == State.AWAITING_RELEASE:
            self._rx_awaiting_release(f, now)
        else:
            self._rx_connected(f, now)
        self._pump(now)

    def channel_busy(self, seconds: float, now: float) -> None:
        """The channel was occupied for `seconds` (a frame just heard): nobody could
        answer us meanwhile and we could not send. Pause T1 and push our own
        pending transmission back by that time."""
        if self.t1_at is not None:
            self.t1_at += seconds
            if self.t1_started is not None:
                self.t1_started += seconds          # SRT counts only the waiting
        if self.tx_end > now:
            self.tx_end += seconds

    def tick(self, now: float) -> None:
        """Run expired timers. Call at next_deadline() (or more often)."""
        self._now = now
        if self.t1_at is not None and now >= self.t1_at:
            self.t1_at = None
            self._t1_expired(now)
        if self.t3_at is not None and now >= self.t3_at:
            self.t3_at = None
            if self.state == State.CONNECTED:
                self.rc = 0
                self._transmit_enquiry(now)
                self.state = State.TIMER_RECOVERY
        if self.t2_at is not None and now >= self.t2_at:
            self.t2_at = None
            if self.state in (State.CONNECTED, State.TIMER_RECOVERY):
                self._tx_s(self._rr(), command=False, pf=False)
        self._pump(now)

    def next_deadline(self) -> float | None:
        times = [t for t in (self.t1_at, self.t2_at, self.t3_at) if t is not None]
        return min(times) if times else None

    def pop_output(self) -> list[Frame]:
        out, self._out = self._out, []
        return out

    def pop_events(self) -> list[tuple[str, object]]:
        ev, self._events = self._events, []
        return ev

    @property
    def connected(self) -> bool:
        return self.state in (State.CONNECTED, State.TIMER_RECOVERY)

    @property
    def unacked(self) -> int:
        return (self.vs - self.va) % self.modulo

    @property
    def is_idle(self) -> bool:
        """Everything handed to send() is out and acknowledged."""
        return not self.queue and not self.retx and self.unacked == 0

    def counters(self, now: float) -> dict:
        """Link quality counters, same names as the Direwolf fork's 'Q' line (v=2)."""
        return dict(v=2, state=int(self.state), **self.c, rc=self.rc, unack=self.unacked,
                    srt=round(self.srt, 2), t1v=round(self.t1v, 2),
                    age=round(now - self.created, 1),
                    tx_busy_ms=int(self.tx_busy * 1000), baud=self.cfg.air_baud)

    # ======================================================================
    # receiving, per state
    # ======================================================================

    def _rx_disconnected(self, f: Frame, now: float) -> None:
        if f.kind == "SABM" and f.command:
            self._reset_vars()
            self._tx_u("UA", command=False, pf=f.pf)
            self._stop_t1()
            self._start_t3(now)
            self.state = State.CONNECTED
            self._events.append(("connected", "incoming"))
        elif f.kind in ("SABME", "DISC"):
            # SABME: v2.2 not before K3 - DM makes the caller fall back to SABM
            self._tx_u("DM", command=False, pf=f.pf)
        elif f.command and f.pf and f.kind not in ("UI", "XID", "TEST"):
            self._tx_u("DM", command=False, pf=True)

    def _rx_awaiting_connection(self, f: Frame, now: float) -> None:
        if f.kind == "UA" and f.pf:
            self._stop_t1()
            self._select_t1(now, measured=True)
            reestablish = self._reestablish
            self._reset_vars()
            self.rc = 0
            self._start_t3(now)
            self.state = State.CONNECTED
            if reestablish:
                self._events.append(("reset", "reestablished"))
            else:
                self._events.append(("connected", "outgoing"))
        elif f.kind == "DM" and f.pf:
            self._stop_t1()
            self._to_disconnected("retryout" if self._reestablish else "refused")
        elif f.kind == "SABM" and f.command:          # both sides called at once
            self._tx_u("UA", command=False, pf=f.pf)
        elif f.kind == "DISC" and f.command:
            self._tx_u("DM", command=False, pf=f.pf)

    def _rx_awaiting_release(self, f: Frame, now: float) -> None:
        if f.kind in ("UA", "DM") and f.pf:
            self._stop_t1()
            self._to_disconnected("local")
        elif f.kind == "DISC" and f.command:          # both sides release at once
            self._tx_u("UA", command=False, pf=f.pf)
        elif f.kind in ("SABM", "SABME") and f.command:
            self._tx_u("DM", command=False, pf=f.pf)
        elif f.command and f.pf and (f.is_i or f.is_s):
            self._tx_u("DM", command=False, pf=True)

    def _rx_connected(self, f: Frame, now: float) -> None:
        kind = f.kind
        if kind == "I":
            self._rx_i(f, now)
        elif f.is_s:
            self._rx_s(f, now)
        elif kind == "SABM" and f.command:            # peer restarted the link
            self._tx_u("UA", command=False, pf=f.pf)
            self._stop_t1()
            self._reset_vars()
            self.queue.clear()
            self._start_t3(now)
            self.state = State.CONNECTED
            self._events.append(("reset", "remote"))
        elif kind == "SABME" and f.command:
            self._tx_u("DM", command=False, pf=f.pf)
            self._stop_timers()
            self._to_disconnected("protocol")
        elif kind == "DISC" and f.command:
            self._tx_u("UA", command=False, pf=f.pf)
            self._stop_timers()
            self._to_disconnected("remote")
        elif kind == "DM":
            self._stop_timers()
            self._to_disconnected("dm")
        elif kind == "FRMR":
            self._establish(now, reestablish=True)
        elif kind == "TEST" and f.command:
            self._emit(u_frame("TEST", self.remote, self.mycall, command=False,
                                     pf=f.pf, info=f.info, path=self.path))
        # UA here is unexpected (SDL: DL-ERROR C) and ignored; XID follows in K3

    # --- I frames -----------------------------------------------------------------

    def _rx_i(self, f: Frame, now: float) -> None:
        if not f.command or len(f.info) > self.cfg.max_rx_info:
            return                                    # SDL: DL-ERROR, frame ignored
        self.c["i_rx"] += 1
        if not self._nr_valid(f.nr):
            self._nr_error(now)
            return
        if self.state == State.CONNECTED and not self.peer_busy:
            self._check_i_acked(f.nr, now)
        else:
            self._set_va(f.nr)
            if self.peer_busy and self.t1_at is None and self.unacked:
                self._start_t1(now)
        if self.own_busy:                              # cannot take it: drop
            if f.pf:
                self._tx_s("RNR", command=False, pf=True)
                self.t2_at = None
            return
        if f.ns == self.vr:
            self.vr = (self.vr + 1) % self.modulo
            self._rx_accepted += 1
            self.reject_exception = False
            self.c["bytes_rx"] += len(f.info)
            self._events.append(("data", f.info))
            if f.pf:
                self._tx_s("RR", command=False, pf=True)
                self.t2_at = None
            else:
                self._ack_later(now)
            return
        # out of sequence: a repeat of something we have, or a gap (lost frame)
        behind = (self.vr - 1 - f.ns) % self.modulo
        if behind < min(self._rx_accepted, self.modulo // 2):
            self.c["retry_rx"] += 1                    # duplicate: just tell V(R) again
            if f.pf:
                self._tx_s(self._rr(), command=False, pf=True)
                self.t2_at = None
            else:
                self._ack_later(now)
        elif self.reject_exception:
            if f.pf:
                self._tx_s("RR", command=False, pf=True)
                self.t2_at = None
        else:
            self.reject_exception = True
            self.c["rej_tx"] += 1
            self._tx_s("REJ", command=False, pf=f.pf)
            self.t2_at = None

    # --- S frames -----------------------------------------------------------------

    def _rx_s(self, f: Frame, now: float) -> None:
        kind = f.kind
        self.peer_busy = kind == "RNR"
        if kind == "RNR":
            self.c["rnr_rx"] += 1
        if kind in ("REJ", "SREJ"):
            self.c["rej_rx"] += 1
        if f.command and f.pf:
            self._tx_s(self._rr(), command=False, pf=True)      # enquiry response
            self.t2_at = None
        if not self._nr_valid(f.nr):
            self._nr_error(now)
            return
        if self.state == State.CONNECTED:
            if kind in ("REJ", "SREJ"):              # SREJ as REJ until K3
                self._set_va(f.nr)
                self._stop_t1()
                self._stop_t3()
                self._invoke_retransmission(f.nr)
            elif self.peer_busy:
                self._set_va(f.nr)
                if self.t1_at is None:
                    self._start_t1(now)              # poll the busy peer later
            else:
                self._check_i_acked(f.nr, now)
            return
        # TIMER_RECOVERY: waiting for the answer (F=1) to our poll
        if not f.command and f.pf:
            self._select_t1(now, measured=False)
            self._stop_t1()
            self._set_va(f.nr)
            self.rc = 0
            self.state = State.CONNECTED
            if self.vs == self.va:
                self._start_t3(now)
            else:
                self._invoke_retransmission(f.nr)
            if self.peer_busy and self.t1_at is None:
                self._start_t1(now)
        else:
            self._set_va(f.nr)
            if kind in ("REJ", "SREJ"):
                self._invoke_retransmission(f.nr)

    # ======================================================================
    # timers
    # ======================================================================

    def _t1_expired(self, now: float) -> None:
        self.c["t1_exp"] += 1
        st = self.state
        if st == State.CONNECTED:
            self.rc = 1
            self._select_t1(now, measured=False)
            self._transmit_enquiry(now)
            self.state = State.TIMER_RECOVERY
        elif st == State.TIMER_RECOVERY:
            if self.rc >= self.cfg.n2:
                self._tx_u("DM", command=False, pf=False)
                self._stop_timers()
                self._to_disconnected("retryout")
            else:
                self.rc += 1
                self._select_t1(now, measured=False)
                self._transmit_enquiry(now)
        elif st == State.AWAITING_CONNECTION:
            if self.rc >= self.cfg.n2:
                self._to_disconnected("retryout" if self._reestablish else "timeout")
            else:
                self.rc += 1
                self._select_t1(now, measured=False)
                self._tx_u("SABM", command=True, pf=True)
                self._start_t1(now)
        elif st == State.AWAITING_RELEASE:
            if self.rc >= self.cfg.n2:
                self._to_disconnected("local")
            else:
                self.rc += 1
                self._tx_u("DISC", command=True, pf=True)
                self._start_t1(now)

    def _clamp(self, t1v: float) -> float:
        return max(self.cfg.t1_min_sec, min(self.cfg.t1_max_sec, t1v))

    def _select_t1(self, now: float, measured: bool) -> None:
        """SDL 'select T1 value'. measured: T1 is being stopped by an acknowledgement."""
        if self.rc == 0 and measured and self.t1_started is not None:
            elapsed = max(0.0, now - self.t1_started)
            self.srt = 7 / 8 * self.srt + 1 / 8 * elapsed
            self.t1v = self._clamp(2 * self.srt)
        elif self.rc > 0:
            self.t1v = self._clamp(self.srt * 2 ** (self.rc + 1))

    def _start_t1(self, now: float) -> None:
        """T1 runs from the estimated end of our own transmission."""
        start = max(now, self.tx_end)
        self.t1_at = start + self.t1v
        self.t1_started = start

    def _stop_t1(self) -> None:
        self.t1_at = None

    def _start_t3(self, now: float) -> None:
        self.t3_at = now + self.cfg.t3_sec if self.cfg.t3_sec > 0 else None

    def _stop_t3(self) -> None:
        self.t3_at = None

    def _stop_timers(self) -> None:
        self.t1_at = self.t2_at = self.t3_at = None

    def _ack_later(self, now: float) -> None:
        """Acknowledge once the peer's burst is over (T2 restarts per I frame)."""
        if self.cfg.t2_sec <= 0:
            self._tx_s("RR", command=False, pf=False)
        else:
            self.t2_at = now + self.cfg.t2_sec

    # ======================================================================
    # helpers
    # ======================================================================

    def _reset_vars(self) -> None:
        self.vs = self.va = self.vr = 0
        self.peer_busy = False
        self.reject_exception = False
        self.sent: dict[int, _Sent] = {}
        self.retx = deque()
        self.t2_at = None
        self._rx_accepted = 0

    def _establish(self, now: float, reestablish: bool = False) -> None:
        """SDL 'establish data link': SABM and wait for UA."""
        self._reestablish = reestablish
        self._stop_timers()
        self.rc = 0
        self._tx_u("SABM", command=True, pf=True)
        self._start_t1(now)
        self.state = State.AWAITING_CONNECTION

    def _to_disconnected(self, reason: str) -> None:
        self._stop_timers()
        self.state = State.DISCONNECTED
        self.queue.clear()
        self.retx.clear()
        self._events.append(("disconnected", reason))

    def _nr_valid(self, nr: int) -> bool:
        """V(A) <= N(R) <= V(S), modulo."""
        return (nr - self.va) % self.modulo <= (self.vs - self.va) % self.modulo

    def _nr_error(self, now: float) -> None:
        """SDL 'N(R) error recovery': the peer acks something we never sent."""
        self._establish(now, reestablish=True)

    def _set_va(self, nr: int) -> None:
        while self.va != nr:
            self.sent.pop(self.va, None)
            self.va = (self.va + 1) % self.modulo

    def _check_i_acked(self, nr: int, now: float) -> None:
        """SDL 'check I frame acknowledged' (state CONNECTED, peer not busy)."""
        if nr == self.vs:
            if self.t1_at is not None:
                self._select_t1(now, measured=True)
                self._stop_t1()
            self._set_va(nr)
            self._start_t3(now)
        elif nr != self.va:
            self._set_va(nr)
            self._start_t1(now)

    def _invoke_retransmission(self, nr: int) -> None:
        """Send everything from N(R) again: back to the front of the send order."""
        again = []
        n = nr
        while n != self.vs:
            if n in self.sent:
                again.append(self.sent.pop(n))
            n = (n + 1) % self.modulo
        self.retx = deque(again + list(self.retx))
        self.vs = nr

    def _pump(self, now: float) -> None:
        """Send I frames while the window is open.

        Only in CONNECTED: in TIMER_RECOVERY we wait for the answer (F=1) to our
        poll first - frames sent meanwhile would not be covered by that answer
        and be sent twice. T1 starts after the whole burst is queued, so it runs
        from the estimated end of the last frame.
        """
        if self.state != State.CONNECTED:
            return
        sent = False
        while (not self.peer_busy and self.unacked < self.k
               and (self.retx or self.queue)):
            entry = self.retx.popleft() if self.retx else _Sent(self.queue.popleft())
            ns = self.vs
            self.sent[ns] = entry
            self._emit(i_frame(self.remote, self.mycall, ns, self.vr, entry.info,
                                     modulo=self.modulo, path=self.path))
            if entry.sends:
                self.c["i_retry"] += 1
                self.c["bytes_retry"] += len(entry.info)
            else:
                self.c["i_new"] += 1
                self.c["bytes_new"] += len(entry.info)
            entry.sends += 1
            self.vs = (self.vs + 1) % self.modulo
            self.t2_at = None                     # the I frame carries our N(R)
            sent = True
        if sent and self.t1_at is None:
            self._stop_t3()
            self._start_t1(now)

    def _emit(self, f: Frame) -> None:
        """Queue a frame for the TNC and advance the estimated end of our transmission."""
        air = self._airtime(len(f.encode()))
        if self.tx_end <= self._now:                  # channel was free: new key-up
            self.tx_end = self._now + air
        else:                                          # appended to the running burst
            air -= self.cfg.txdelay_sec
            self.tx_end += air
        self.tx_busy += air
        self._out.append(f)

    def _airtime(self, nbytes: int) -> float:
        """Estimated seconds on air for one frame (+ flags/FCS, + key-up)."""
        return self.cfg.txdelay_sec + (nbytes + 4) * 8 / self.cfg.air_baud

    def _rr(self) -> str:
        return "RNR" if self.own_busy else "RR"

    def _transmit_enquiry(self, now: float) -> None:
        self._tx_s(self._rr(), command=True, pf=True)
        self.t2_at = None
        self._start_t1(now)

    def _tx_s(self, kind: str, *, command: bool, pf: bool) -> None:
        self._emit(s_frame(kind, self.remote, self.mycall, self.vr, command=command,
                                 pf=pf, modulo=self.modulo, path=self.path))

    def _tx_u(self, kind: str, *, command: bool, pf: bool) -> None:
        self._emit(u_frame(kind, self.remote, self.mycall, command=command, pf=pf,
                                 path=self.path))
