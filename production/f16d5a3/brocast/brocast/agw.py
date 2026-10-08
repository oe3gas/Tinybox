"""TCP link to Direwolf's AGW port (AGWPE protocol), reconnects by itself.

Used frames (36-byte header, little endian, then data):
  'R'  version            -> reply 'R' (major, minor), only logged
  'k'  raw frames on      -> afterwards every received frame comes as 'K'
  'K'  raw AX.25 frame    send and receive; data = 1 byte (0) + frame without FCS
  'y'  outstanding frames -> reply 'y' with the number of frames still waiting
                             in Direwolf's transmit queue for that port (channel)

The AGW port number is Direwolf's radio channel. Several AGW clients may be
connected at the same time (TinyBox uses the same port).
"""

from __future__ import annotations

import asyncio
import logging
import struct
from typing import Optional

from .kiss import FrameHandler

log = logging.getLogger(__name__)

HEADER = struct.Struct("<B3xcxBx10s10sII")      # port, kind, pid, from, to, len, user
MAX_DATA = 4096
QUERY_TIMEOUT_S = 2.0


def pack(kind: str, port: int = 0, data: bytes = b"", pid: int = 0) -> bytes:
    return HEADER.pack(port, kind.encode("ascii"), pid, b"", b"", len(data), 0) + data


def unpack_header(raw: bytes) -> tuple[int, str, int]:
    port, kind, _pid, _src, _dst, length, _user = HEADER.unpack(raw)
    return port, kind.decode("latin-1"), length


class AgwLink:
    """Same interface as KissLink (run, send, connected, rx/tx counters),
    plus queue_len(): frames still waiting in Direwolf's transmit queue."""

    def __init__(self, host: str, port: int, on_frame: FrameHandler,
                 reconnect_sec: int = 5):
        self.host, self.port = host, port
        self.on_frame = on_frame
        self.reconnect_sec = reconnect_sec
        self._writer: asyncio.StreamWriter | None = None
        self.connected = asyncio.Event()
        self.rx_frames = 0
        self.tx_frames = 0
        self.version: Optional[tuple[int, int]] = None
        self._query_lock = asyncio.Lock()
        self._query: tuple[int, asyncio.Future] | None = None
        self.query_unanswered = 0

    async def run(self) -> None:
        delay = 1
        while True:
            try:
                reader, writer = await asyncio.open_connection(self.host, self.port)
            except OSError as exc:
                log.warning("AGW %s:%s nicht erreichbar (%s), neuer Versuch in %s s",
                            self.host, self.port, exc, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, max(self.reconnect_sec, 1) * 6)
                continue
            delay = 1
            log.info("AGW verbunden mit %s:%s", self.host, self.port)
            writer.write(pack("R") + pack("k"))          # version, raw frames on
            self._writer = writer
            self.connected.set()
            try:
                await writer.drain()
                await self._read(reader)
            except (OSError, asyncio.IncompleteReadError, ValueError) as exc:
                log.debug("AGW: %s", exc)
            finally:
                self.connected.clear()
                self._writer = None
                self._fail_query()
                writer.close()
                log.warning("AGW-Verbindung verloren")
            await asyncio.sleep(self.reconnect_sec)

    async def _read(self, reader: asyncio.StreamReader) -> None:
        while True:
            port, kind, length = unpack_header(await reader.readexactly(HEADER.size))
            if length > MAX_DATA:
                raise ValueError(f"AGW-Frame mit {length} Bytes, Verbindung wird neu aufgebaut")
            data = await reader.readexactly(length) if length else b""
            if kind == "K" and len(data) > 1:
                self.rx_frames += 1
                try:
                    result = self.on_frame(port, data[1:])
                    if asyncio.iscoroutine(result):
                        await result
                except Exception:          # one bad frame must not stop the link
                    log.exception("Fehler beim Verarbeiten eines Frames")
            elif kind == "y" and len(data) >= 4:
                q = self._query
                if q and q[0] == port and not q[1].done():
                    q[1].set_result(int.from_bytes(data[:4], "little"))
            elif kind == "R" and len(data) >= 8:
                self.version = (int.from_bytes(data[:4], "little"),
                                int.from_bytes(data[4:8], "little"))
                log.info("Direwolf (AGW) Version %s.%s", *self.version)

    def _fail_query(self) -> None:
        if self._query and not self._query[1].done():
            self._query[1].set_result(None)

    async def send(self, data: bytes, channel: int = 0) -> bool:
        writer = self._writer
        if writer is None:
            return False
        writer.write(pack("K", channel, b"\x00" + data))
        await writer.drain()
        self.tx_frames += 1
        return True

    async def queue_len(self, channel: int = 0) -> Optional[int]:
        """Frames in Direwolf's transmit queue for this channel; None if unknown
        (offline, or no answer within QUERY_TIMEOUT_S)."""
        async with self._query_lock:
            writer = self._writer
            if writer is None:
                return None
            fut: asyncio.Future = asyncio.get_running_loop().create_future()
            self._query = (channel, fut)
            try:
                writer.write(pack("y", channel))
                await writer.drain()
                n = await asyncio.wait_for(fut, QUERY_TIMEOUT_S)
            except (asyncio.TimeoutError, OSError):
                n = None
            finally:
                self._query = None
            if n is None and self._writer is not None:
                self.query_unanswered += 1
                if self.query_unanswered == 1:
                    log.warning("Direwolf beantwortet die AGW-Abfrage 'y' nicht – "
                                "Sendepausen werden wie bei KISS berechnet")
            return n
