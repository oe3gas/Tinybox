"""The two ways to reach the TinyBox.

AgwLink    radio, through Direwolf's AGW port: Direwolf does the AX.25
           connection; with 'k' (raw frames on) we also see every frame on
           the channel - that is how the UI frames to TBCHAT-<n> and APRS
           beacons (symbols) come in.
TelnetLink the TinyBox telnet test port on the same PC (no radio, no UI).

Both call back into the client core:
    on_state(state, reason)   state: offline | connecting | online
    on_line(text)             one line from the TinyBox
    on_frame(RawFrame)        a frame heard on the channel (AGW only)
"""

from __future__ import annotations

import asyncio
import logging
import struct
from typing import Callable

from . import radio
from .config import Config

log = logging.getLogger(__name__)

HEADER = struct.Struct("<B3xcxBx10s10sII")
PID_NO_L3 = 0xF0
PACLEN = 128
MAX_DATA = 65536
IAC = 255


class LineSplitter:
    """Bytes -> lines (CR, LF or CR LF), UTF-8 with Latin-1 fallback."""

    def __init__(self, on_line: Callable[[str], None]) -> None:
        self.on_line = on_line
        self.buf = bytearray()
        self.last_cr = False

    def feed(self, data: bytes) -> None:
        for b in data:
            if b in (10, 13):
                if b == 10 and self.last_cr:
                    self.last_cr = False
                    continue
                self.last_cr = b == 13
                raw = bytes(self.buf)
                self.buf.clear()
                try:
                    line = raw.decode("utf-8")
                except UnicodeDecodeError:
                    line = raw.decode("latin-1")
                self.on_line(line)
                continue
            self.last_cr = False
            if len(self.buf) < 4096:
                self.buf.append(b)


class BaseLink:
    def __init__(self, cfg: Config, on_state, on_line, on_frame) -> None:
        self.cfg = cfg
        self.on_state = on_state
        self.on_line = on_line
        self.on_frame = on_frame
        self.splitter = LineSplitter(self._line)
        self.online = False

    def _line(self, line: str) -> None:
        self.on_line(line)

    def _set(self, state: str, reason: str = "") -> None:
        self.online = state == "online"
        self.on_state(state, reason)


class AgwLink(BaseLink):
    kind = "agw"

    def __init__(self, *a) -> None:
        super().__init__(*a)
        self._writer: asyncio.StreamWriter | None = None
        self.agw_up = asyncio.Event()
        self.connecting = False

    def _send(self, kind: str, call_from: str = "", call_to: str = "",
              data: bytes = b"", pid: int = 0) -> None:
        w = self._writer
        if w is not None and not w.is_closing():
            w.write(HEADER.pack(self.cfg.radio_port, kind.encode(), pid, call_from.encode(),
                                call_to.encode(), len(data), 0) + data)

    async def run(self) -> None:
        """Keep the TCP link to Direwolf open (reconnects by itself)."""
        warned = False
        while True:
            try:
                reader, writer = await asyncio.open_connection(self.cfg.agw_host,
                                                               self.cfg.agw_port)
            except OSError as exc:
                if not warned:
                    log.warning("Direwolf AGW %s:%s not reachable (%s)",
                                self.cfg.agw_host, self.cfg.agw_port, exc)
                warned = True
                await asyncio.sleep(5)
                continue
            warned = False
            self._writer = writer
            log.info("connected to Direwolf AGW %s:%s", self.cfg.agw_host, self.cfg.agw_port)
            self._send("R")
            self._send("X", self.cfg.mycall)
            self._send("k")
            self.agw_up.set()
            try:
                while True:
                    head = await reader.readexactly(HEADER.size)
                    _port, kind, _pid, cfrom, cto, length, _ = HEADER.unpack(head)
                    if length > MAX_DATA:
                        raise ConnectionError("AGW frame too large")
                    data = await reader.readexactly(length) if length else b""
                    try:
                        self._dispatch(kind.decode("latin-1"), _c(cfrom), _c(cto), data)
                    except Exception:
                        log.exception("error handling AGW frame")
            except (asyncio.IncompleteReadError, ConnectionError, OSError) as exc:
                log.warning("AGW connection lost: %s", exc or type(exc).__name__)
            finally:
                self.agw_up.clear()
                self._writer = None
                writer.close()
                if self.online or self.connecting:
                    self.connecting = False
                    self._set("offline", "Direwolf connection lost")
            await asyncio.sleep(5)

    def _dispatch(self, kind: str, cfrom: str, cto: str, data: bytes) -> None:
        tb = self.cfg.tinybox_call
        if kind == "K" and len(data) > 1:
            frame = radio.decode(data[1:])
            if frame is not None:
                self.on_frame(frame)
        elif kind == "X":
            if data[:1] != b"\x01":
                log.error("Direwolf refused to register %s", self.cfg.mycall)
        elif kind == "C" and tb in (cfrom, cto):
            self.connecting = False
            self._set("online")
        elif kind == "D" and tb in (cfrom, cto):
            self.splitter.feed(data)
        elif kind == "d" and tb in (cfrom, cto):
            was = self.online or self.connecting
            self.connecting = False
            if was:
                self._set("offline", "disconnected")

    async def connect(self) -> None:
        if not self.agw_up.is_set():
            self._set("offline", "Direwolf not reachable")
            return
        self.connecting = True
        self._set("connecting")
        self._send("C", self.cfg.mycall, self.cfg.tinybox_call, pid=PID_NO_L3)

    def send_line(self, text: str) -> None:
        data = (text + "\r").encode("utf-8")
        for i in range(0, len(data), PACLEN):
            self._send("D", self.cfg.mycall, self.cfg.tinybox_call, data[i:i + PACLEN],
                       PID_NO_L3)

    def disconnect(self) -> None:
        self._send("d", self.cfg.mycall, self.cfg.tinybox_call)


def _c(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode("ascii", "replace").strip().upper()


class TelnetLink(BaseLink):
    kind = "telnet"

    def __init__(self, *a) -> None:
        super().__init__(*a)
        self._writer: asyncio.StreamWriter | None = None
        self._task: asyncio.Task | None = None
        self._sent: list[str] = []       # our own lines come back as telnet echo

    async def run(self) -> None:
        await asyncio.Event().wait()      # nothing to keep open between sessions

    def _line(self, line: str) -> None:
        # the server echoes what we typed (after a prompt on the same line)
        if self._sent and self._sent[0] and line.rstrip().endswith(self._sent[0].rstrip()):
            self._sent.pop(0)
            return
        self.on_line(line)

    async def connect(self) -> None:
        self._set("connecting")
        try:
            reader, writer = await asyncio.open_connection(self.cfg.telnet_host,
                                                           self.cfg.telnet_port)
        except OSError as exc:
            self._set("offline", f"telnet: {exc}")
            return
        self._writer = writer
        writer.write((self.cfg.mycall + "\r\n").encode())       # answers the call prompt
        self._sent = [self.cfg.mycall]
        self._set("online")
        self._task = asyncio.create_task(self._read(reader))

    async def _read(self, reader: asyncio.StreamReader) -> None:
        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break
                self.splitter.feed(_strip_iac(data))
        except (ConnectionError, OSError):
            pass
        self._writer = None
        self._set("offline", "disconnected")

    def send_line(self, text: str) -> None:
        if self._writer is not None:
            self._sent.append(text)
            del self._sent[:-20]
            self._writer.write((text + "\r\n").encode("utf-8"))

    def disconnect(self) -> None:
        if self._writer is not None:
            self._writer.close()          # the reader then reports "offline"


def _strip_iac(data: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(data):
        b = data[i]
        if b == IAC and i + 1 < len(data):
            cmd = data[i + 1]
            i += 3 if cmd in (251, 252, 253, 254) else 2
            continue
        out.append(b)
        i += 1
    return bytes(out)
