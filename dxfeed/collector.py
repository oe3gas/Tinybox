"""Telnet client to a DX cluster node: log in, read spots, store them.

Runs for days. On a broken or silent connection it waits (growing pause, up to
reconnect_max_sec) and tries the next node of the list. Telnet option requests
are refused politely (DO -> WONT, WILL -> DONT); the cluster does not need any.
Everything received is untrusted: control characters are dropped, overlong
lines are thrown away, spots go through spots.parse (calls, ASCII, length).
"""

from __future__ import annotations

import asyncio
import logging
import time

from . import cty as ctymod
from .config import Config
from .spots import parse
from .store import Store

log = logging.getLogger(__name__)

IAC, DONT, DO, WONT, WILL, SB, SE = 255, 254, 253, 252, 251, 250, 240
MAX_LINE = 1024
LOGIN_WAIT_SEC = 15
ALIVE_EVERY_SEC = 60          # commit + mark the session as alive
PRUNE_EVERY_SEC = 3600
CTY_CHECK_EVERY_SEC = 86400


class TelnetFilter:
    """Removes telnet commands from the byte stream, collects the replies."""

    def __init__(self) -> None:
        self.state = 0          # 0 data, 1 after IAC, 2 option byte, 3 in SB, 4 IAC in SB
        self.verb = 0
        self.replies = bytearray()

    def feed(self, data: bytes) -> bytes:
        out = bytearray()
        for b in data:
            if self.state == 0:
                if b == IAC:
                    self.state = 1
                else:
                    out.append(b)
            elif self.state == 1:
                if b == IAC:
                    out.append(IAC)
                    self.state = 0
                elif b in (DO, DONT, WILL, WONT):
                    self.verb, self.state = b, 2
                elif b == SB:
                    self.state = 3
                else:
                    self.state = 0             # NOP, GA ... ignored
            elif self.state == 2:
                if self.verb == DO:
                    self.replies += bytes((IAC, WONT, b))
                elif self.verb == WILL:
                    self.replies += bytes((IAC, DONT, b))
                self.state = 0
            elif self.state == 3:
                if b == IAC:
                    self.state = 4
            elif self.state == 4:
                self.state = 0 if b == SE else 3
        return bytes(out)

    def take_replies(self) -> bytes:
        r, self.replies = bytes(self.replies), bytearray()
        return r


def clean_line(raw: bytes) -> str:
    text = raw.decode("latin-1")
    return "".join(ch for ch in text if ch >= " " or ch == "\t").strip()


class Collector:
    def __init__(self, cfg: Config, store: Store, cty: ctymod.Cty | None) -> None:
        self.cfg = cfg
        self.store = store
        self.cty = cty
        self.spots = 0                      # stored since start
        self.dropped = 0                    # skimmer spots dropped
        self._last_prune = 0.0
        self._last_cty_check = time.time()

    # --- main loop -----------------------------------------------------------

    async def run(self) -> None:
        nodes = self.cfg.cluster.nodes
        pause = self.cfg.cluster.reconnect_sec
        i = 0
        while True:
            host, port = nodes[i % len(nodes)]
            started = time.time()
            try:
                await self.session(host, port)
            except (OSError, asyncio.TimeoutError, ConnectionError) as exc:
                log.warning("%s:%d: %s", host, port, exc or type(exc).__name__)
            # a session that ran for a while resets the pause
            if time.time() - started > 600:
                pause = self.cfg.cluster.reconnect_sec
            i += 1
            log.info("reconnect in %d s (next node %s:%d)", pause, *nodes[i % len(nodes)])
            await asyncio.sleep(pause)
            pause = min(pause * 2, self.cfg.cluster.reconnect_max_sec)

    async def session(self, host: str, port: int) -> None:
        c = self.cfg.cluster
        log.info("connecting to %s:%d as %s", host, port, c.login)
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), 20)
        tf = TelnetFilter()
        buf = bytearray()
        session_id = None
        try:
            await self._login(reader, writer, tf, buf)
            session_id = self.store.session_start(f"{host}:{port}", time.time())
            log.info("logged in at %s:%d", host, port)
            if not c.skimmer:
                await self._send(writer, "unset/skimmer")
            for cmd in c.init:
                await self._send(writer, cmd)
            last_alive = time.time()
            while True:
                data = await asyncio.wait_for(reader.read(4096), c.idle_timeout_sec)
                if not data:
                    raise ConnectionError("connection closed by node")
                buf += tf.feed(data)
                if tf.replies:
                    writer.write(tf.take_replies())
                self._take_lines(buf)
                now = time.time()
                if now - last_alive >= ALIVE_EVERY_SEC:
                    self.store.session_alive(session_id, now)
                    self.store.commit()
                    last_alive = now
                    await self._housekeeping(now)
        finally:
            if session_id is not None:
                self.store.session_alive(session_id, time.time())
            self.store.commit()
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), 5)
            except (OSError, asyncio.TimeoutError):
                pass

    # --- helpers -------------------------------------------------------------

    async def _login(self, reader, writer, tf: TelnetFilter, buf: bytearray) -> None:
        """Wait for the login prompt (or a few seconds of silence), send the call."""
        deadline = time.time() + LOGIN_WAIT_SEC
        while time.time() < deadline:
            try:
                data = await asyncio.wait_for(reader.read(4096),
                                              max(0.1, deadline - time.time()))
            except asyncio.TimeoutError:
                break
            if not data:
                raise ConnectionError("connection closed before login")
            buf += tf.feed(data)
            if tf.replies:
                writer.write(tf.take_replies())
            low = buf.decode("latin-1").lower()
            if "login" in low or "call" in low:
                break
        buf.clear()
        await self._send(writer, self.cfg.cluster.login)

    @staticmethod
    async def _send(writer, text: str) -> None:
        writer.write(text.encode("ascii", "ignore") + b"\r\n")
        await writer.drain()

    def _take_lines(self, buf: bytearray) -> None:
        while True:
            nl = buf.find(b"\n")
            if nl < 0:
                if len(buf) > MAX_LINE:          # no line end: garbage, drop it
                    buf.clear()
                return
            raw = bytes(buf[:nl])
            del buf[:nl + 1]
            if len(raw) <= MAX_LINE:
                self.handle_line(clean_line(raw))

    def handle_line(self, line: str, now: float | None = None) -> bool:
        spot = parse(line)
        if spot is None:
            return False
        if spot.skimmer and not self.cfg.cluster.skimmer:
            self.dropped += 1
            return False
        dx = self.cty.lookup(spot.dx) if self.cty else None
        sp = self.cty.lookup(spot.spotter) if self.cty else None
        self.store.add(spot, time.time() if now is None else now, dx, sp)
        self.spots += 1
        if self.spots % 500 == 0:
            log.info("%d spots stored since start", self.spots)
        return True

    async def _housekeeping(self, now: float) -> None:
        if now - self._last_prune >= PRUNE_EVERY_SEC:
            n = self.store.prune(self.cfg.data.keep_days, now)
            if n:
                log.info("pruned %d spots older than %d days", n, self.cfg.data.keep_days)
            self._last_prune = now
        if now - self._last_cty_check >= CTY_CHECK_EVERY_SEC:
            self._last_cty_check = now
            d = self.cfg.data
            if ctymod.is_stale(d.cty, d.cty_update_days):
                try:
                    await asyncio.to_thread(ctymod.download, d.cty, d.cty_url,
                                            verify_ssl=d.ssl_verify)
                    self.cty = ctymod.Cty.load(d.cty)
                except Exception as exc:          # keep the old table, try tomorrow
                    log.warning("cty.dat update failed: %s", exc)
