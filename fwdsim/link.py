"""Line-oriented links: TCP, in-memory pair, and (in agw.py) AX.25 via Direwolf.

A link delivers lines without their line end. CR, LF and CR LF all end a
line; Ctrl-Z also ends a line and stays at its end, so the session can see
it. Every line in and out is kept in `transcript` and logged.
"""

from __future__ import annotations

import asyncio
import logging

log = logging.getLogger("fwdsim.link")

CTRL_Z = 0x1A
MAX_LINE = 4096


def decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


class Link:
    """Base class. Subclasses implement _recv() and _send()."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.eol = "\r"
        self.encoding = "utf-8"
        self.transcript: list[str] = []
        self._buf = bytearray()
        self._lines: list[str] = []
        self._last_cr = False
        self._eof = False
        self.closed = False

    # --- subclass interface ---------------------------------------------------

    async def _recv(self) -> bytes:
        """Next chunk of bytes, b'' at end of connection."""
        raise NotImplementedError

    def _send(self, data: bytes) -> None:
        raise NotImplementedError

    async def _close(self) -> None:
        raise NotImplementedError

    # --- reading --------------------------------------------------------------

    def _split(self, data: bytes) -> None:
        for b in data:
            if b in (10, 13):
                if b == 10 and self._last_cr:
                    self._last_cr = False
                    continue
                self._last_cr = b == 13
                self._emit()
                continue
            if b == CTRL_Z:
                self._buf.append(b)
                self._emit()
                self._last_cr = True          # swallow the CR that usually follows
                continue
            self._last_cr = False
            if len(self._buf) < MAX_LINE:
                self._buf.append(b)

    def _emit(self) -> None:
        line = decode(bytes(self._buf))
        self._buf.clear()
        self._lines.append(line)

    async def readline(self, timeout: float = 60) -> str | None:
        """Next line, None at end of connection. Raises asyncio.TimeoutError."""
        async def _get() -> str | None:
            while not self._lines:
                if self._eof:
                    if self._buf:
                        self._emit()
                        continue
                    return None
                data = await self._recv()
                if not data:
                    self._eof = True
                    continue
                self._split(data)
            return self._lines.pop(0)

        line = await asyncio.wait_for(_get(), timeout)
        if line is not None:
            self.transcript.append("< " + line)
            log.debug("%s < %s", self.name, line)
        return line

    # --- writing --------------------------------------------------------------

    def write_line(self, line: str) -> None:
        self.transcript.append("> " + line)
        log.debug("%s > %s", self.name, line)
        self._send((line + self.eol).encode(self.encoding, "replace"))

    def write_lines(self, lines: list[str]) -> None:
        for line in lines:
            self.write_line(line)

    def write_raw(self, data: bytes) -> None:
        self.transcript.append(f"> <{len(data)} raw bytes>")
        self._send(data)

    async def drain(self) -> None:
        pass

    async def close(self) -> None:
        if not self.closed:
            self.closed = True
            await self._close()


class TcpLink(Link):
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                 name: str = "tcp") -> None:
        super().__init__(name)
        self.reader = reader
        self.writer = writer

    async def _recv(self) -> bytes:
        try:
            return await self.reader.read(1024)
        except (ConnectionError, OSError):
            return b""

    def _send(self, data: bytes) -> None:
        if not self.writer.is_closing():
            self.writer.write(data)

    async def drain(self) -> None:
        try:
            await self.writer.drain()
        except (ConnectionError, OSError):
            pass

    async def _close(self) -> None:
        try:
            await self.drain()
            self.writer.close()
            await self.writer.wait_closed()
        except (ConnectionError, OSError):
            pass


async def tcp_connect(host: str, port: int, name: str = "tcp") -> TcpLink:
    reader, writer = await asyncio.open_connection(host, port)
    return TcpLink(reader, writer, name)


class MemoryLink(Link):
    """One end of an in-process connection (used for the internal hop -11 <-> -22)."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.inbox: asyncio.Queue[bytes] = asyncio.Queue()
        self.peer: MemoryLink | None = None

    async def _recv(self) -> bytes:
        return await self.inbox.get()

    def _send(self, data: bytes) -> None:
        if self.peer is not None and not self.closed:
            self.peer.inbox.put_nowait(data)

    async def _close(self) -> None:
        if self.peer is not None:
            self.peer.inbox.put_nowait(b"")


def memory_pair(name_a: str, name_b: str) -> tuple[MemoryLink, MemoryLink]:
    a, b = MemoryLink(name_a), MemoryLink(name_b)
    a.peer, b.peer = b, a
    return a, b
