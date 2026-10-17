"""The TNC: wake it, switch it into KISS, then pass KISS frames.

Life cycle (repeats on every loss of the port):

    open transport -> wake (terminal mode, until a step gets its answer)
                   -> init (every line must get its answer, the last enters KISS)
                   -> KISS parameters (TXDELAY, P, SlotTime, full duplex off)
                   -> KISS: frames to the hub, frames from the hub
    stop():        -> C0 FF C0 (leave KISS) and the profile's exit lines

Everything the TNC answers during wake/init is logged, so a failing init on
real hardware shows exactly which line got which answer (pk232py lesson:
"log both the bytes sent and what came back").
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Callable

from prcore import kiss
from prcore.ax25 import frame as ax
from prcore.ax25.frame import AX25Error

from .profiles import KISS_EXIT, Profile, Step

log = logging.getLogger(__name__)

PARAM_NAMES = {kiss.CMD_TXDELAY: "TXDELAY", kiss.CMD_P: "PERSIST",
               kiss.CMD_SLOTTIME: "SLOTTIME", kiss.CMD_TXTAIL: "TXTAIL",
               kiss.CMD_FULLDUPLEX: "FULLDUPLEX"}

# VARA tunnel (profiles.VARA_FM): KISS frame type 2 = "Generic Data" in VARA
VARA_GENERIC = 0x02
TUNNEL_MAGIC = b"AX"           # marks our tunnelled AX.25 frames among other type-2 data
ECHO_SEC = 30.0                # a frame VARA hands back within this time is our own


def is_ui(ax25: bytes) -> bool:
    """UI frame? (control field after the address field, P/F bit ignored)"""
    pos = 0
    while pos + 7 <= len(ax25):
        pos += 7
        if ax25[pos - 1] & 0x01:
            return pos < len(ax25) and ax25[pos] & 0xEF == 0x03
    return False


def _hex(data: bytes, limit: int = 400) -> str:
    text = data[:limit].hex(" ")
    return text + (f" ... (+{len(data) - limit})" if len(data) > limit else "")


def summary(ax25: bytes) -> str:
    """'OE3GAS-1>OE3GAS,DIGI* 118 B' for the trace."""
    try:
        dest, src, path, rep = ax.peek(ax25)
    except AX25Error:
        return f"{len(ax25)} B (no AX.25 address)"
    via = "".join("," + c + ("*" if h else "") for c, h in zip(path, rep))
    return f"{src}>{dest}{via} {len(ax25)} B"


class TncError(Exception):
    pass


def _show(data: bytes, limit: int = 120) -> str:
    """Terminal text for the log: printable as is, the rest as <hex>."""
    out = []
    for b in data[:limit]:
        if b in (10, 13):
            out.append("|")
        elif 32 <= b < 127:
            out.append(chr(b))
        else:
            out.append(f"<{b:02X}>")
    return "".join(out) + ("..." if len(data) > limit else "")


def _refused(answer: bytes, sent: bytes) -> bool:
    """The TNC answered with an error line ('?...'). The echo of what we sent is
    cut off first, so a '?' typed by us does not count."""
    echo = sent.strip()
    if echo and echo in answer:
        answer = answer.split(echo, 1)[1]
    return any(part.strip().startswith(b"?") for part in answer.replace(b"\n", b"\r").split(b"\r"))


class Tnc:
    def __init__(self, profile: Profile, transport, on_frame: Callable[[int, bytes], None],
                 *, reconnect_sec: float = 10, params: dict[int, int] | None = None,
                 on_state: Callable[[str], None] | None = None) -> None:
        self.profile = profile
        self.transport = transport
        self.on_frame = on_frame
        self.reconnect_sec = reconnect_sec
        self.params = params or {}                   # KISS command -> value
        self.on_state = on_state or (lambda s: None)
        self.state = "down"                          # down | init | kiss
        self.ready = asyncio.Event()                 # set while in KISS
        self.rx_frames = self.tx_frames = 0
        self._term = bytearray()
        self._term_event = asyncio.Event()
        self._decoder = kiss.Decoder()
        self._stopping = False
        self.trace = False                           # LOG TRACE: every byte in hex
        # for the status query (CR41)
        self.state_since = time.time()
        self.inits = 0                               # times the TNC reached KISS
        self.port_losses = 0                         # port lost while in KISS
        self.last_error: str | None = None
        self.init_log: deque[dict] = deque(maxlen=40)  # last wake/init lines with answers
        # VARA tunnel (type 2) - profile.tunnel: no | connected | all
        self.tunnel_tx = self.tunnel_rx = 0          # frames through type 2
        self.foreign = 0                             # type-2 data that is not ours (VarAC ...)
        self.echoes = 0                              # own frames handed back by the modem
        self._sent: deque[tuple[float, bytes]] = deque()   # (time, AX.25) for the echo check

    def describe(self) -> str:
        return f"{self.profile.name} on {self.transport.describe()}"

    def _set_state(self, state: str) -> None:
        if state != self.state:
            self.state_since = time.time()
        self.state = state
        if state == "kiss":
            self.ready.set()
        else:
            self.ready.clear()
        self.on_state(state)

    # --- main loop -------------------------------------------------------------------

    async def run(self) -> None:
        warned = False
        while not self._stopping:
            try:
                await self.transport.open()
            except Exception as exc:
                (log.debug if warned else log.warning)(
                    "TNC %s not reachable (%s), retrying every %ss",
                    self.transport.describe(), exc, self.reconnect_sec)
                warned = True
                await asyncio.sleep(self.reconnect_sec)
                continue
            warned = False
            log.info("TNC port open: %s", self.describe())
            self._set_state("init")
            cancelled = False
            reader = asyncio.create_task(self._read_loop())
            try:
                await self._wake()
                await self._init()
                self._decoder = kiss.Decoder()
                self._term.clear()
                self._set_state("kiss")
                self.inits += 1
                self.last_error = None
                self._send_params()
                log.info("TNC in KISS mode - ready")
                if self.profile.tunnel != "no":
                    log.info("VARA tunnel %s: %s through KISS type 2, no KISS parameters sent",
                             self.profile.tunnel, "all frames" if self.profile.tunnel == "all"
                             else "connected-mode frames (UI as type 0)")
                await reader                             # until the port is lost
            except TncError as exc:
                log.error("TNC init failed: %s", exc)
                self.last_error = f"init failed: {exc}"
            except ConnectionError as exc:
                log.warning("TNC lost: %s", exc)
                if self.state == "kiss":
                    self.port_losses += 1
                self.last_error = f"lost: {exc}"
            except asyncio.CancelledError:
                # Ctrl+C: stop() comes next and must still find the port open and
                # the state 'kiss', or it cannot switch the TNC back out of KISS
                reader.cancel()
                cancelled = True
                raise
            finally:
                reader.cancel()
                if not self._stopping and not cancelled:
                    self.transport.close()
                    self._set_state("down")
            if not self._stopping:
                await asyncio.sleep(self.reconnect_sec)

    async def _read_loop(self) -> None:
        while True:
            data = await self.transport.read()
            if self.trace:
                log.info("<< TNC %d bytes | %s", len(data), _hex(data))
            if self.state == "kiss":
                for port, cmd, frame in self._decoder.feed(data):
                    if self.trace:
                        log.info("<< TNC frame %s", summary(frame) if cmd == kiss.CMD_DATA
                                 else f"KISS command 0x{cmd:02x}")
                    if cmd == kiss.CMD_DATA:
                        self._received(port, frame)
                    elif cmd == VARA_GENERIC and port == 0 and self.profile.tunnel != "no":
                        if frame.startswith(TUNNEL_MAGIC) and len(frame) >= len(TUNNEL_MAGIC) + 15:
                            self._received(0, frame[len(TUNNEL_MAGIC):], tunnelled=True)
                        else:
                            self.foreign += 1
                            log.debug("type-2 data that is not ours (%d bytes) ignored", len(frame))
            else:
                self._term += data
                del self._term[:-4096]                   # keep the tail only
                self._term_event.set()

    def _received(self, port: int, frame: bytes, tunnelled: bool = False) -> None:
        if self.profile.tunnel != "no" and self._is_echo(frame):
            self.echoes += 1                         # VARA gave us our own frame back
            if self.trace:
                log.info("<< own frame back from the modem - dropped")
            return
        self.rx_frames += 1
        self.tunnel_rx += tunnelled
        try:
            self.on_frame(port, frame)
        except Exception:
            log.exception("error handling a frame from the TNC")

    def _is_echo(self, frame: bytes) -> bool:
        now = time.monotonic()
        while self._sent and self._sent[0][0] < now - ECHO_SEC:
            self._sent.popleft()
        for i, (_, sent) in enumerate(self._sent):
            if sent == frame:
                del self._sent[i]
                return True
        return False

    # --- terminal dialog ------------------------------------------------------------------

    async def _step(self, step: Step) -> tuple[bool, bytes]:
        """Send one step; True if one of its expected answers arrived."""
        self._term.clear()
        self._write(step.send)
        if not step.expect:
            await asyncio.sleep(step.timeout)
            return True, bytes(self._term)
        loop = asyncio.get_running_loop()
        end = loop.time() + step.timeout
        while True:
            got = bytes(self._term)
            if any(m in got for m in step.expect):
                return True, got
            left = end - loop.time()
            if left <= 0:
                return False, got
            self._term_event.clear()
            try:
                await asyncio.wait_for(self._term_event.wait(), left)
            except asyncio.TimeoutError:
                pass

    async def _wake(self) -> None:
        if not self.profile.wake:
            return
        for step in self.profile.wake:
            ok, got = await self._step(step)
            log.debug("wake %-26s -> %s", step.note or _show(step.send), _show(got))
            self._note("wake", step.note or _show(step.send), got, ok and bool(step.expect))
            if ok and step.expect:
                log.info("TNC answers (%s)", step.note or _show(step.send))
                return
        raise TncError("no answer from the TNC - wrong port/baud rate, TNC off or "
                       "hanging (switch it off and on)")

    async def _init(self) -> None:
        for step in self.profile.init:
            ok, got = await self._step(step)
            answer = _show(got)
            refused = bool(step.expect) and _refused(got, step.send)
            self._note("init", step.note, got, ok and not refused)
            if not ok:
                raise TncError(f"'{step.note}': expected {step.expect}, got '{answer}'")
            if refused:
                # ?bad, ?What?, ?EXPERT command ...: the setting was NOT made - going
                # on would leave the TNC in KISS with a wrong setup
                raise TncError(f"'{step.note}' refused by the TNC: '{answer}'")
            log.info("init %-16s -> %s", step.note, answer)
        await asyncio.sleep(self.profile.settle_sec)

    def _note(self, phase: str, what: str, answer: bytes, ok: bool) -> None:
        self.init_log.append({"t": time.time(), "phase": phase, "send": what,
                              "answer": _show(answer, 80), "ok": ok})

    def status(self) -> dict:
        return {"name": self.profile.display or self.profile.name, "profile": self.profile.name,
                "port": self.transport.describe(), "state": self.state,
                "since": self.state_since, "inits": self.inits,
                "port_losses": self.port_losses, "last_error": self.last_error,
                "rx_frames": self.rx_frames, "tx_frames": self.tx_frames,
                "tunnel": self.profile.tunnel, "tunnel_tx": self.tunnel_tx,
                "tunnel_rx": self.tunnel_rx, "foreign": self.foreign, "echoes": self.echoes,
                "init_log": list(self.init_log)[-20:]}

    def _send_params(self) -> None:
        if not self.profile.kiss_params:
            return          # VARA: KISS command 1/2 are its frame types 1/2 - would go on air
        for cmd, value in self.params.items():
            self._write(kiss.encode_param(cmd, value), f"param {PARAM_NAMES.get(cmd, cmd)}={value}")

    def set_param(self, cmd: int, value: int) -> bool:
        """Change a KISS parameter (TXDELAY, P, SLOTTIME ...) while running. It is
        kept for the next init too. True if it went to the TNC at once (in KISS)."""
        self.params[cmd] = value
        if self.state != "kiss" or not self.profile.kiss_params:
            return False
        self._write(kiss.encode_param(cmd, value), f"param {PARAM_NAMES.get(cmd, cmd)}={value}")
        return True

    # --- KISS ---------------------------------------------------------------------------

    def _write(self, data: bytes, what: str = "") -> None:
        if self.trace:
            log.info(">> TNC %s%s", f"{what} | " if what else "", _hex(data))
        self.transport.write(data)

    def send(self, kiss_frame: bytes, ax25: bytes | None = None) -> bool:
        """One complete KISS frame (FEND ... FEND). False while not in KISS."""
        if self.state != "kiss":
            return False
        self._write(kiss_frame, summary(ax25) if ax25 is not None else "")
        self.tx_frames += 1
        return True

    def send_ax25(self, ax25: bytes, port: int = 0) -> bool:
        """One AX.25 frame to the TNC. With the VARA tunnel the frames VARA does not
        take as KISS type 0 go as type 2 (TUNNEL_MAGIC + frame)."""
        t = self.profile.tunnel
        if t == "all" or (t == "connected" and not is_ui(ax25)):
            ok = self.send(kiss.encode(TUNNEL_MAGIC + ax25, 0, VARA_GENERIC), ax25)
            if ok:
                self.tunnel_tx += 1
        else:
            ok = self.send(kiss.encode(ax25, port), ax25)
        if ok and t != "no":
            self._sent.append((time.monotonic(), ax25))
            while len(self._sent) > 200:
                self._sent.popleft()
        return ok

    async def stop(self) -> None:
        """Leave KISS (if the profile wants that) and close the port."""
        self._stopping = True
        if self.state == "kiss" and self.profile.exit_kiss:
            log.info("leaving KISS mode")
            self.state = "init"
            self._write(KISS_EXIT, "leave KISS")
            await asyncio.sleep(1.5)
            for step in self.profile.exit_lines:
                self._write(step.send)
                await asyncio.sleep(0.5)
            await self.transport.drain()
        self.transport.close()
        self._set_state("down")
