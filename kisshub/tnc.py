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

from .profiles import KISS_EXIT, Profile, Step

log = logging.getLogger(__name__)


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
        # for the status query (CR41)
        self.state_since = time.time()
        self.inits = 0                               # times the TNC reached KISS
        self.port_losses = 0                         # port lost while in KISS
        self.last_error: str | None = None
        self.init_log: deque[dict] = deque(maxlen=40)  # last wake/init lines with answers

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
            if self.state == "kiss":
                for port, cmd, frame in self._decoder.feed(data):
                    if cmd == kiss.CMD_DATA:
                        self.rx_frames += 1
                        try:
                            self.on_frame(port, frame)
                        except Exception:
                            log.exception("error handling a frame from the TNC")
            else:
                self._term += data
                del self._term[:-4096]                   # keep the tail only
                self._term_event.set()

    # --- terminal dialog ------------------------------------------------------------------

    async def _step(self, step: Step) -> tuple[bool, bytes]:
        """Send one step; True if one of its expected answers arrived."""
        self._term.clear()
        self.transport.write(step.send)
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
                "init_log": list(self.init_log)[-20:]}

    def _send_params(self) -> None:
        for cmd, value in self.params.items():
            self.transport.write(kiss.encode_param(cmd, value))

    # --- KISS ---------------------------------------------------------------------------

    def send(self, kiss_frame: bytes) -> bool:
        """One complete KISS frame (FEND ... FEND). False while not in KISS."""
        if self.state != "kiss":
            return False
        self.transport.write(kiss_frame)
        self.tx_frames += 1
        return True

    async def stop(self) -> None:
        """Leave KISS (if the profile wants that) and close the port."""
        self._stopping = True
        if self.state == "kiss" and self.profile.exit_kiss:
            log.info("leaving KISS mode")
            self.state = "init"
            self.transport.write(KISS_EXIT)
            await asyncio.sleep(1.5)
            for step in self.profile.exit_lines:
                self.transport.write(step.send)
                await asyncio.sleep(0.5)
            await self.transport.drain()
        self.transport.close()
        self._set_state("down")
