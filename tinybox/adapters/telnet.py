"""Telnet test port (localhost only).

Lets you use the mailbox without a radio: telnet 127.0.0.1 6300
(Windows: PuTTY with connection type "Telnet", or the Windows telnet client).
The server does the echo, so the client switches to character mode.
"""

from __future__ import annotations

import asyncio
import logging

from .. import texts
from ..app import App
from ..config import is_valid_call, normalize_call
from ..session import MAX_LINE, Session

log = logging.getLogger(__name__)

IAC, DONT, DO, WONT, WILL, SB, SE = 255, 254, 253, 252, 251, 250, 240
ECHO, SGA = 1, 3


class TelnetTransport:
    def __init__(self, writer: asyncio.StreamWriter) -> None:
        self.writer = writer
        self.closing = False

    def write(self, text: str) -> None:
        if not self.closing:
            self.writer.write(text.replace("\r", "\r\n").encode("utf-8"))

    def close(self) -> None:
        if not self.closing:
            self.closing = True
            # flushes buffered output, then closes; a waiting read gets EOF
            self.writer.close()

    def abort_output(self) -> None:
        pass  # telnet output is written immediately, nothing is queued


class TelnetConnection:
    def __init__(self, app: App, reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter) -> None:
        self.app = app
        self.reader = reader
        self.writer = writer
        self._buf = bytearray()
        self._last_cr = False

    async def _byte(self) -> int:
        if not self._buf:
            data = await self.reader.read(512)
            if not data:
                raise EOFError
            self._buf.extend(data)
        return self._buf.pop(0)

    def _echo(self, data: bytes) -> None:
        self.writer.write(data)

    async def read_line(self) -> str:
        """Read one line, handle telnet commands, echo and backspace."""
        line = bytearray()
        while True:
            b = await self._byte()
            if b == IAC:
                cmd = await self._byte()
                if cmd in (WILL, WONT, DO, DONT):
                    await self._byte()
                elif cmd == SB:  # skip sub-negotiation up to IAC SE
                    prev = None
                    while True:
                        x = await self._byte()
                        if prev == IAC and x == SE:
                            break
                        prev = x
                continue
            if b in (10, 13):
                if b == 10 and self._last_cr:  # CR LF -> one line end
                    self._last_cr = False
                    continue
                self._last_cr = b == 13
                self._echo(b"\r\n")
                return line.decode("utf-8", "replace")
            self._last_cr = False
            if b == 0:
                continue
            if b in (8, 127):  # backspace
                if line:
                    line.pop()
                    self._echo(b"\b \b")
                continue
            if b == 0x1A:  # CTRL-Z ends a message
                self._echo(b"^Z\r\n")
                line.append(b)
                return line.decode("utf-8", "replace")
            if b < 32:
                continue
            if len(line) < MAX_LINE:
                line.append(b)
                self._echo(bytes([b]))

    async def _timed_line(self) -> str:
        timeout = self.app.cfg.mailbox.idle_timeout_min * 60
        line = await asyncio.wait_for(self.read_line(), timeout)
        await self.writer.drain()
        return line

    async def login(self, transport: TelnetTransport) -> str | None:
        for _ in range(3):
            transport.write(texts.TELNET_LOGIN)
            await self.writer.drain()
            call = normalize_call(await self._timed_line())
            if is_valid_call(call):
                return call
            transport.write(texts.TELNET_BAD_CALL + "\r")
        return None

    async def run(self) -> None:
        peer = self.writer.get_extra_info("peername")
        transport = TelnetTransport(self.writer)
        session: Session | None = None
        registered = False
        try:
            # Server echoes, client should send characters immediately.
            self.writer.write(bytes([IAC, WILL, ECHO, IAC, WILL, SGA]))
            transport.write(texts.TELNET_TEST_NOTE + "\r")
            call = await self.login(transport)
            if call is None:
                return
            cfg = self.app.cfg
            sysop = self.app.service.is_sysop_call(call)
            session = Session(call, self.app.service, cfg, transport,
                              origin="telnet", sysop=sysop)
            if not self.app.registry.add(session):
                transport.write(texts.BUSY + "\r")
                session = None
                return
            registered = True
            log.info("telnet connect %s from %s%s", call, peer, " (sysop)" if sysop else "")
            session.start()
            await self.writer.drain()
            while not session.closed:
                session.handle_line(await self._timed_line())
                await self.writer.drain()
        except asyncio.TimeoutError:
            transport.write(texts.IDLE_TIMEOUT + "\r")
        except (EOFError, ConnectionError, OSError):
            pass
        finally:
            if session is not None:
                session.end()
                if registered:
                    self.app.registry.remove(session)
                log.info("telnet disconnect %s", session.call)
            try:
                if not self.writer.is_closing():
                    await self.writer.drain()
                    self.writer.close()
                await self.writer.wait_closed()
            except (ConnectionError, OSError):
                pass


async def start(app: App) -> asyncio.AbstractServer:
    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await TelnetConnection(app, reader, writer).run()

    cfg = app.cfg.telnet
    server = await asyncio.start_server(handle, cfg.host, cfg.port)
    log.info("telnet test port listening on %s:%d", cfg.host, cfg.port)
    return server
