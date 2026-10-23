"""KISS framing and a TCP link to Direwolf's KISS port (reconnects by itself)."""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Optional

from .colorlog import OK

log = logging.getLogger(__name__)

FEND, FESC, TFEND, TFESC = 0xC0, 0xDB, 0xDC, 0xDD
CMD_DATA = 0x00


def encode(data: bytes, channel: int = 0) -> bytes:
    out = bytearray((FEND, (channel << 4) | CMD_DATA))
    for b in data:
        if b == FEND:
            out += bytes((FESC, TFEND))
        elif b == FESC:
            out += bytes((FESC, TFESC))
        else:
            out.append(b)
    out.append(FEND)
    return bytes(out)


class Decoder:
    """Feed raw bytes from the TCP stream, get complete (channel, data) frames."""

    def __init__(self, max_frame: int = 4096):
        self.buf = bytearray()
        self.in_frame = False
        self.escape = False
        self.max_frame = max_frame

    def feed(self, chunk: bytes) -> list[tuple[int, bytes]]:
        frames: list[tuple[int, bytes]] = []
        for b in chunk:
            if b == FEND:
                if self.in_frame and self.buf:
                    frames.extend(self._finish())
                self.buf.clear()
                self.in_frame = True
                self.escape = False
                continue
            if not self.in_frame:
                continue
            if self.escape:
                self.escape = False
                b = FEND if b == TFEND else FESC if b == TFESC else b
            elif b == FESC:
                self.escape = True
                continue
            if len(self.buf) >= self.max_frame:      # garbage, resync on next FEND
                self.buf.clear()
                self.in_frame = False
                continue
            self.buf.append(b)
        return frames

    def _finish(self) -> list[tuple[int, bytes]]:
        type_byte = self.buf[0]
        if type_byte & 0x0F != CMD_DATA:             # TXDELAY etc., not data
            return []
        return [(type_byte >> 4, bytes(self.buf[1:]))]


# evaluated at runtime, so no "X | None" here (Python 3.9 compatibility)
FrameHandler = Callable[[int, bytes], Optional[Awaitable[None]]]


class KissLink:
    """Keeps one TCP connection to Direwolf. send() drops frames while offline."""

    def __init__(self, host: str, port: int, on_frame: FrameHandler,
                 reconnect_sec: int = 5):
        self.host, self.port = host, port
        self.on_frame = on_frame
        self.reconnect_sec = reconnect_sec
        self._writer: asyncio.StreamWriter | None = None
        self.connected = asyncio.Event()
        self.rx_frames = 0
        self.tx_frames = 0

    async def run(self) -> None:
        delay = 1
        warned = False
        while True:
            try:
                reader, writer = await asyncio.open_connection(self.host, self.port)
            except OSError as exc:
                (log.debug if warned else log.error)(
                    "KISS %s:%s nicht erreichbar (%s), neuer Versuch in %s s",
                    self.host, self.port, exc, delay)
                warned = True
                await asyncio.sleep(delay)
                delay = min(delay * 2, max(self.reconnect_sec, 1) * 6)
                continue
            delay = 1
            warned = False
            log.info("KISS verbunden mit %s:%s", self.host, self.port, extra=OK)
            self._writer = writer
            self.connected.set()
            try:
                await self._read(reader)
            finally:
                self.connected.clear()
                self._writer = None
                writer.close()
                log.error("KISS-Verbindung verloren")
            await asyncio.sleep(self.reconnect_sec)

    async def _read(self, reader: asyncio.StreamReader) -> None:
        decoder = Decoder()
        while chunk := await reader.read(4096):
            for channel, data in decoder.feed(chunk):
                self.rx_frames += 1
                try:
                    result = self.on_frame(channel, data)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception:          # one bad frame must not stop the link
                    log.exception("Fehler beim Verarbeiten eines Frames")

    async def send(self, data: bytes, channel: int = 0) -> bool:
        writer = self._writer
        if writer is None:
            return False
        writer.write(encode(data, channel))
        await writer.drain()
        self.tx_frames += 1
        return True
