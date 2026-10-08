"""Links for forward sessions: one byte stream, read as lines or as raw bytes.

TcpLink  a TCP connection (transparent: no telnet options, no echo)
AgwLink  an AX.25 connection of the AGW adapter. It sits where a user Session
         would sit (AgwConnection.session) and gets the raw bytes (feed_bytes).

Lines end with CR (CR LF and LF are accepted). Ctrl-Z also ends a line and
stays in it; the line end right after a Ctrl-Z is skipped. Compressed FBB (B1)
reads the same buffer byte by byte (read_bytes), so switching between line and
binary mode never loses or splits data.
"""

from __future__ import annotations

import asyncio
import logging

log = logging.getLogger("tinybox.forward.link")

MAX_LINE = 4096
CTRL_Z = 0x1A


def _decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


class Link:
    def __init__(self, name: str) -> None:
        self.name = name
        self.is_closed = False
        self._buf = bytearray()
        self._eof = False
        self._data = asyncio.Event()
        self._last_cr = False          # the previous line ended with CR (an LF may follow)
        self._after_z = False          # the previous line ended with Ctrl-Z (a line end may follow)

    # --- input (called by the transport) ---------------------------------------

    def _feed(self, data: bytes | None) -> None:
        """New bytes from the partner; None = connection closed."""
        if data is None:
            self._eof = True
        else:
            self._buf += data
        self._data.set()

    async def _wait(self) -> None:
        self._data.clear()
        await self._data.wait()

    def _skip_line_end(self) -> None:
        """Drop a line end left over from the previous line (LF after CR, CR/LF after ^Z)."""
        while self._buf:
            b = self._buf[0]
            if b == 10 and self._last_cr:
                self._last_cr = False
            elif b in (10, 13) and self._after_z:
                self._after_z = False
                self._last_cr = b == 13
            else:
                return
            del self._buf[0]

    def _take_line(self) -> str | None:
        self._skip_line_end()
        buf = self._buf
        for i, b in enumerate(buf):
            if b in (10, 13):
                line = bytes(buf[:i])
                del buf[:i + 1]
                self._last_cr, self._after_z = b == 13, False
                return _decode(line[:MAX_LINE])
            if b == CTRL_Z:
                line = bytes(buf[:i + 1])
                del buf[:i + 1]
                self._last_cr, self._after_z = False, True
                return _decode(line[-MAX_LINE:])
        if len(buf) > 4 * MAX_LINE:                 # no line end at all: cut it
            line = bytes(buf[:MAX_LINE])
            del buf[:]
            return _decode(line)
        return None

    # --- reading ----------------------------------------------------------------------

    async def readline(self, timeout: float) -> str | None:
        """Next line; None when the connection is gone. Raises asyncio.TimeoutError."""
        async def get() -> str | None:
            while True:
                line = self._take_line()
                if line is not None:
                    return line
                if self._eof:
                    if self._buf:
                        rest = _decode(bytes(self._buf[:MAX_LINE]))
                        self._buf.clear()
                        return rest
                    return None
                await self._wait()
        line = await asyncio.wait_for(get(), timeout)
        if line is not None:
            log.debug("%s < %s", self.name, line)
        return line

    async def read_bytes(self, n: int, timeout: float) -> bytes | None:
        """Exactly n raw bytes (compressed forwarding); None if the connection ends first."""
        async def get() -> bytes | None:
            self._skip_line_end()
            self._last_cr = self._after_z = False
            while len(self._buf) < n:
                if self._eof:
                    return None
                await self._wait()
            data = bytes(self._buf[:n])
            del self._buf[:n]
            return data
        return await asyncio.wait_for(get(), timeout)

    def partial(self) -> bytes:
        """Bytes received but not read yet (for logging an aborted transfer)."""
        return bytes(self._buf)

    # --- writing ----------------------------------------------------------------------

    def write_lines(self, *lines: str) -> None:
        for line in lines:
            log.debug("%s > %s", self.name, line)
        self._write("".join(x + "\r" for x in lines).encode("utf-8"))

    def write_raw(self, data: bytes) -> None:
        log.debug("%s > [%d bytes binary]", self.name, len(data))
        self._write(data)

    def _write(self, data: bytes) -> None:
        raise NotImplementedError

    async def drain(self) -> None:
        pass

    async def close(self) -> None:
        raise NotImplementedError


class TcpLink(Link):
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                 name: str) -> None:
        super().__init__(name)
        self.writer = writer
        self._task = asyncio.create_task(self._read(reader))

    async def _read(self, reader: asyncio.StreamReader) -> None:
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                self._feed(data)
        except (ConnectionError, OSError, asyncio.CancelledError):
            pass
        self._feed(None)

    def _write(self, data: bytes) -> None:
        if not self.writer.is_closing():
            self.writer.write(data)

    async def drain(self) -> None:
        try:
            await self.writer.drain()
        except (ConnectionError, OSError):
            pass

    async def close(self) -> None:
        if self.is_closed:
            return
        self.is_closed = True
        await self.drain()
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except (ConnectionError, OSError):
            pass
        self._task.cancel()


class AgwLink(Link):
    """Plugged into AgwConnection.session; the adapter calls feed_bytes/end."""

    idle_exempt = True        # forward sessions have their own timeout

    def __init__(self, conn, name: str) -> None:
        super().__init__(name)
        self.conn = conn

    # --- what AgwConnection / the idle watchdog expect from a session ------

    @property
    def closed(self) -> bool:
        return self.is_closed

    def feed_bytes(self, data: bytes) -> None:
        self._feed(data)

    def end(self) -> None:
        self._feed(None)

    # --- Link -----------------------------------------------------------------

    def _write(self, data: bytes) -> None:
        self.conn.write_bytes(data)

    async def close(self) -> None:
        if not self.is_closed:
            self.is_closed = True
            self.conn.close()        # drains the queued packets, then disconnects
