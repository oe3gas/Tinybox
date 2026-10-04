"""Direwolf adapter using the AGWPE TCP protocol.

Direwolf does the AX.25 connected-mode work (SABM/UA, I-frames, acks,
retries). TinyBox registers the mailbox callsign with an 'X' frame;
Direwolf then accepts connects to that call and passes them to us.

AGW frame = 36 byte header (little endian) + data:
    0  port (1)   1-3 reserved
    4  kind (1)   5 reserved   6 PID (1)   7 reserved
    8  call_from (10, NUL padded)
    18 call_to   (10, NUL padded)
    28 data_len (uint32)   32 user (uint32, unused)

Frames used:
    R  version        X  register call     C  connected
    D  connected data d  disconnect        Y  outstanding frames
"""

from __future__ import annotations

import asyncio
import logging
import struct
import time
from collections import deque
from dataclasses import dataclass

from .. import texts
from ..app import App
from ..config import is_valid_call, normalize_call
from ..session import MAX_LINE, Session

log = logging.getLogger(__name__)

HEADER = struct.Struct("<B3xcxBx10s10sII")
MAX_DATA = 65536
PID_NO_L3 = 0xF0
CTRL_Z = 0x1A
DRAIN_TIMEOUT = 120  # s to wait for the last packets before disconnecting
Y_TIMEOUT = 5


class AgwProtocolError(Exception):
    pass


@dataclass
class Frame:
    kind: str
    port: int = 0
    pid: int = 0
    call_from: str = ""
    call_to: str = ""
    data: bytes = b""

    def pack(self) -> bytes:
        return HEADER.pack(self.port, self.kind.encode("ascii"), self.pid,
                           self.call_from.encode("ascii"), self.call_to.encode("ascii"),
                           len(self.data), 0) + self.data


def _call(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode("ascii", "replace").strip().upper()


async def read_frame(reader: asyncio.StreamReader) -> Frame:
    head = await reader.readexactly(HEADER.size)
    port, kind, pid, cfrom, cto, length, _ = HEADER.unpack(head)
    if length > MAX_DATA:
        raise AgwProtocolError(f"frame too large: {length}")
    data = await reader.readexactly(length) if length else b""
    return Frame(kind.decode("ascii", "replace"), port, pid, _call(cfrom), _call(cto), data)


def decode_line(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")  # older terminals send Latin-1 umlauts


class AgwConnection:
    """One AX.25 connection. Acts as Transport for the Session."""

    def __init__(self, adapter: "AgwAdapter", remote: str) -> None:
        self.adapter = adapter
        self.remote = remote
        self.session: Session | None = None
        self.queue: deque[bytes] = deque()
        self.outstanding = 0
        self.closing = False
        self.gone = False
        self.last_activity = time.monotonic()
        self._wakeup = asyncio.Event()
        self._y_reply = asyncio.Event()
        self._rx = bytearray()
        self._last_cr = False
        self.pump_task: asyncio.Task | None = None

    # --- Transport interface -------------------------------------------

    def write(self, text: str) -> None:
        if self.gone:
            return
        data = text.encode("utf-8")
        n = self.adapter.cfg.direwolf.paclen
        self.queue.extend(data[i:i + n] for i in range(0, len(data), n))
        self._wakeup.set()

    def close(self) -> None:
        self.closing = True
        self._wakeup.set()

    def abort_output(self) -> None:
        dropped = len(self.queue)
        self.queue.clear()
        log.debug("%s: output aborted, %d packets dropped", self.remote, dropped)

    # --- input -----------------------------------------------------------

    def feed(self, data: bytes) -> None:
        self.last_activity = time.monotonic()
        for b in data:
            if self.session is None or self.session.closed:
                return
            if b in (10, 13):
                if b == 10 and self._last_cr:  # CR LF -> one line end
                    self._last_cr = False
                    continue
                self._last_cr = b == 13
                self._line()
                continue
            self._last_cr = False
            if b == CTRL_Z:
                self._rx.append(b)
                self._line()
            elif len(self._rx) < MAX_LINE:
                self._rx.append(b)

    def _line(self) -> None:
        line = decode_line(bytes(self._rx))
        self._rx.clear()
        self.session.handle_line(line)

    # --- output pump with flow control ------------------------------------

    def on_outstanding(self, count: int) -> None:
        self.outstanding = count
        self._y_reply.set()

    async def _query_outstanding(self) -> None:
        self._y_reply.clear()
        self.adapter.send(Frame("Y", self.adapter.radio_port,
                                call_from=self.adapter.mycall, call_to=self.remote))
        try:
            await asyncio.wait_for(self._y_reply.wait(), Y_TIMEOUT)
        except asyncio.TimeoutError:
            log.warning("%s: no 'Y' reply from Direwolf", self.remote)
            self.outstanding = 0

    async def pump(self) -> None:
        cfg = self.adapter.cfg.direwolf
        try:
            while not self.gone:
                if not self.queue:
                    if self.closing:
                        await self._drain_and_disconnect()
                        return
                    self._wakeup.clear()
                    await self._wakeup.wait()
                    continue
                while self.queue and self.outstanding < cfg.max_outstanding:
                    self.adapter.send(Frame("D", self.adapter.radio_port, PID_NO_L3,
                                            self.adapter.mycall, self.remote,
                                            self.queue.popleft()))
                    self.outstanding += 1
                if self.queue:  # window full: wait for acks
                    await asyncio.sleep(0.5)
                    await self._query_outstanding()
        except asyncio.CancelledError:
            pass

    async def _drain_and_disconnect(self) -> None:
        deadline = time.monotonic() + DRAIN_TIMEOUT
        await self._query_outstanding()
        while self.outstanding > 0 and time.monotonic() < deadline and not self.gone:
            await asyncio.sleep(1)
            await self._query_outstanding()
        if not self.gone:
            log.info("%s: disconnecting", self.remote)
            self.adapter.send(Frame("d", self.adapter.radio_port,
                                    call_from=self.adapter.mycall, call_to=self.remote))


class AgwAdapter:
    def __init__(self, app: App) -> None:
        self.app = app
        self.cfg = app.cfg
        self.mycall = app.cfg.station.mailbox_call
        self.radio_port = app.cfg.direwolf.agw_radio_port
        self.conns: dict[str, AgwConnection] = {}
        self._writer: asyncio.StreamWriter | None = None
        self.connected = asyncio.Event()  # AGW link up (used by tests)

    def send(self, frame: Frame) -> None:
        if self._writer is not None and not self._writer.is_closing():
            self._writer.write(frame.pack())

    # --- main loop --------------------------------------------------------

    async def run(self) -> None:
        dw = self.cfg.direwolf
        warned = False
        while True:
            try:
                reader, writer = await asyncio.open_connection(dw.agw_host, dw.agw_port)
            except OSError as exc:
                # warn once, then retry quietly until Direwolf is back
                (log.debug if warned else log.warning)(
                    "Direwolf AGW %s:%d not reachable (%s), retrying every %ds",
                    dw.agw_host, dw.agw_port, exc, dw.reconnect_sec)
                warned = True
                await asyncio.sleep(dw.reconnect_sec)
                continue
            warned = False
            log.info("connected to Direwolf AGW %s:%d", dw.agw_host, dw.agw_port)
            self._writer = writer
            watchdog = asyncio.create_task(self._idle_watchdog())
            try:
                self.send(Frame("R"))
                self.send(Frame("X", self.radio_port, call_from=self.mycall))
                self.connected.set()
                while True:
                    frame = await read_frame(reader)
                    try:
                        self._dispatch(frame)
                    except Exception:  # one bad frame must not take the radio link down
                        log.exception("error handling AGW frame '%s' from %s",
                                      frame.kind, frame.call_from)
            except (asyncio.IncompleteReadError, ConnectionError, AgwProtocolError) as exc:
                log.warning("AGW connection lost: %s", exc or type(exc).__name__)
            except Exception:
                log.exception("AGW adapter error, reconnecting")
            finally:
                self.connected.clear()
                watchdog.cancel()
                self._drop_all()
                self._writer = None
                writer.close()
            await asyncio.sleep(dw.reconnect_sec)

    # --- incoming frames ----------------------------------------------------

    def _remote_of(self, f: Frame) -> str:
        # Direwolf: call_from = remote station, call_to = our call.
        return f.call_to if f.call_from == self.mycall else f.call_from

    def _dispatch(self, f: Frame) -> None:
        if f.kind == "R":
            if len(f.data) >= 8:
                major, _, minor, _ = struct.unpack("<hhhh", f.data[:8])
                log.info("Direwolf AGW version %d.%d", major, minor)
        elif f.kind == "X":
            if f.data[:1] == b"\x01":
                log.info("mailbox call %s registered with Direwolf", self.mycall)
            else:
                log.error("Direwolf refused to register %s - already in use?", self.mycall)
        elif f.kind == "C":
            self._on_connect(self._remote_of(f))
        elif f.kind == "D":
            conn = self.conns.get(self._remote_of(f))
            if conn:
                conn.feed(f.data)
        elif f.kind == "d":
            self._on_disconnect(self._remote_of(f))
        elif f.kind == "Y":
            conn = self.conns.get(self._remote_of(f))
            if conn and len(f.data) >= 4:
                conn.on_outstanding(struct.unpack("<I", f.data[:4])[0])
        else:
            log.debug("AGW frame '%s' ignored", f.kind)

    def _on_connect(self, remote: str) -> None:
        remote = normalize_call(remote)
        if remote in self.conns:
            log.warning("%s: duplicate connect ignored", remote)
            return
        conn = AgwConnection(self, remote)
        self.conns[remote] = conn
        conn.pump_task = asyncio.create_task(conn.pump())
        if not is_valid_call(remote):
            log.warning("connect from invalid call %r refused", remote)
            conn.write(texts.INVALID_CALL.format(call=remote) + "\r")
            conn.close()
            return
        sysop = self.cfg.station.sysop_via_radio and self.app.service.is_sysop_call(remote)
        session = Session(remote, self.app.service, self.cfg, conn, origin="radio", sysop=sysop)
        if not self.app.registry.add(session):
            log.info("%s: busy (max_users reached)", remote)
            conn.write(texts.BUSY + "\r")
            conn.close()
            return
        conn.session = session
        log.info("radio connect %s%s", remote, " (sysop)" if sysop else "")
        session.start()

    def _on_disconnect(self, remote: str) -> None:
        conn = self.conns.pop(remote, None)
        if conn is None:
            return
        conn.gone = True
        conn._wakeup.set()
        if conn.pump_task:
            conn.pump_task.cancel()
        if conn.session is not None:
            conn.session.end()
            self.app.registry.remove(conn.session)
        log.info("radio disconnect %s", remote)

    def _drop_all(self) -> None:
        for remote in list(self.conns):
            self._on_disconnect(remote)

    async def _idle_watchdog(self) -> None:
        limit = self.cfg.mailbox.idle_timeout_min * 60
        while True:
            await asyncio.sleep(10)
            now = time.monotonic()
            for conn in list(self.conns.values()):
                if (conn.session and not conn.session.closed
                        and now - conn.last_activity > limit):
                    log.info("%s: idle timeout", conn.remote)
                    conn.write(texts.IDLE_TIMEOUT + "\r")
                    conn.session.close()
