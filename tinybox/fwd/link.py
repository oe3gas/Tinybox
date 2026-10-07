"""Line links for forward sessions.

TcpLink  a TCP connection (transparent: no telnet options, no echo)
AgwLink  an AX.25 connection of the AGW adapter. It sits where a user Session
         would sit (AgwConnection.session) and receives complete lines.

Lines end with CR. Ctrl-Z also ends a line and stays in it.
"""

from __future__ import annotations

import asyncio
import logging

log = logging.getLogger("tinybox.forward.link")

MAX_LINE = 4096


def _decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


class Link:
    def __init__(self, name: str) -> None:
        self.name = name
        self.lines: asyncio.Queue[str | None] = asyncio.Queue()
        self.is_closed = False

    async def readline(self, timeout: float) -> str | None:
        """Next line; None when the connection is gone. Raises asyncio.TimeoutError."""
        line = await asyncio.wait_for(self.lines.get(), timeout)
        if line is not None:
            log.debug("%s < %s", self.name, line)
        return line

    def write_lines(self, *lines: str) -> None:
        for line in lines:
            log.debug("%s > %s", self.name, line)
        self._write("".join(x + "\r" for x in lines))

    def _write(self, text: str) -> None:
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
        buf = bytearray()
        last_cr = False
        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break
                for b in data:
                    if b in (10, 13):
                        if b == 10 and last_cr:
                            last_cr = False
                            continue
                        last_cr = b == 13
                        self.lines.put_nowait(_decode(bytes(buf)))
                        buf.clear()
                    elif b == 0x1A:
                        buf.append(b)
                        self.lines.put_nowait(_decode(bytes(buf)))
                        buf.clear()
                        last_cr = True            # the CR after Ctrl-Z
                    else:
                        last_cr = False
                        if len(buf) < MAX_LINE:
                            buf.append(b)
        except (ConnectionError, OSError, asyncio.CancelledError):
            pass
        if buf:
            self.lines.put_nowait(_decode(bytes(buf)))
        self.lines.put_nowait(None)

    def _write(self, text: str) -> None:
        if not self.writer.is_closing():
            self.writer.write(text.encode("utf-8"))

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
    """Plugged into AgwConnection.session; the adapter calls handle_line/end."""

    idle_exempt = True        # forward sessions have their own timeout

    def __init__(self, conn, name: str) -> None:
        super().__init__(name)
        self.conn = conn

    # --- what AgwConnection / the idle watchdog expect from a session ------

    @property
    def closed(self) -> bool:
        return self.is_closed

    def handle_line(self, line: str) -> None:
        self.lines.put_nowait(line)

    def end(self) -> None:
        self.lines.put_nowait(None)

    # --- Link -----------------------------------------------------------------

    def _write(self, text: str) -> None:
        self.conn.write(text)

    async def close(self) -> None:
        if not self.is_closed:
            self.is_closed = True
            self.conn.close()        # drains the queued packets, then disconnects
