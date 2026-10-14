"""KISS-TCP server in front of the TNC.

Clients (TinyBox, brocastd, a monitor) connect to the KISS-TCP port. Every
frame the TNC receives goes to all clients. Frames from clients go into ONE
send queue for the TNC:

    priority 0  U and S frames (UA, DM, RR, RNR, REJ, SREJ, SABM, DISC, XID ...)
    priority 1  I frames
    priority 2  UI frames (brocast pages, TBCHAT, beacons) and anything else

A KISS TNC takes every frame at once into its own buffer and sends them in
order - priorities would be useless if the hub passed frames on immediately.
So the hub only hands a frame to the TNC when the estimated air time already
queued in the TNC is below max_lead (default 1.5 s at the configured air
baud rate): an acknowledgement then waits at most that long, never behind a
whole brocast page.

Frames a client sends are also given to the OTHER clients when they go to the
TNC, as if heard on the air: brocastd sees what TinyBox sends and the other
way round (TinyBox's T1 pauses while the channel is busy).

KISS parameter frames from clients are ignored: the hub owns the TNC settings.
"""

from __future__ import annotations

import asyncio
import heapq
import itertools
import logging
from dataclasses import dataclass

from tinybox.ax25 import kissio

from .tnc import Tnc

log = logging.getLogger(__name__)

PRIO_CONTROL, PRIO_I, PRIO_UI = 0, 1, 2


def priority(ax25: bytes) -> int:
    """Send priority of an AX.25 frame from its control field."""
    pos = 0
    while pos + 7 <= len(ax25):
        last = ax25[pos + 6] & 0x01
        pos += 7
        if last:
            break
    else:
        return PRIO_UI                                 # no proper address field
    if pos >= len(ax25) or pos < 14:
        return PRIO_UI
    c = ax25[pos]
    if c & 0x01 == 0:
        return PRIO_I
    if c & 0x03 == 0x01:
        return PRIO_CONTROL                            # S frame
    if c & 0xEF == 0x03:
        return PRIO_UI                                 # UI
    return PRIO_CONTROL                                # other U frames


@dataclass
class Client:
    name: str
    writer: asyncio.StreamWriter
    rx: int = 0           # frames from this client
    tx: int = 0           # frames to this client


@dataclass(frozen=True)
class HubCfg:
    listen: str = "127.0.0.1"
    port: int = 8101
    air_baud: int = 1200
    txdelay_sec: float = 0.3
    max_lead_sec: float = 1.5
    status_every_sec: float = 600


class Hub:
    def __init__(self, cfg: HubCfg, tnc_factory) -> None:
        """tnc_factory(on_frame) -> Tnc (lets tests plug in their own transport)."""
        self.cfg = cfg
        self.tnc: Tnc = tnc_factory(self._from_tnc)
        self.clients: dict[asyncio.StreamWriter, Client] = {}
        self._queue: list[tuple[int, int, bytes, int, Client | None]] = []
        self._seq = itertools.count()
        self._kick = asyncio.Event()
        self._busy_until = 0.0                          # estimated end of the TNC's backlog
        self._server: asyncio.base_events.Server | None = None
        self._tasks: list[asyncio.Task] = []
        self.dropped = 0
        self._names = itertools.count(1)

    @property
    def port(self) -> int:
        return self._server.sockets[0].getsockname()[1] if self._server else self.cfg.port

    @staticmethod
    def now() -> float:
        return asyncio.get_running_loop().time()

    def airtime(self, nbytes: int) -> float:
        return self.cfg.txdelay_sec + (nbytes + 4) * 8 / self.cfg.air_baud

    # --- life cycle ------------------------------------------------------------------

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._client, self.cfg.listen, self.cfg.port)
        log.info("KISS-TCP server on %s:%d", self.cfg.listen, self.port)
        self._tasks = [asyncio.create_task(self.tnc.run()),
                       asyncio.create_task(self._sender()),
                       asyncio.create_task(self._status())]

    async def run(self) -> None:
        await self.start()
        await asyncio.gather(*self._tasks)

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
        for w in list(self.clients):
            w.close()
        try:
            await self.tnc.stop()
        finally:
            for t in self._tasks:
                t.cancel()
            await asyncio.gather(*self._tasks, return_exceptions=True)

    # --- clients -------------------------------------------------------------------------

    async def _client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        c = Client(f"client{next(self._names)} {peer[0]}:{peer[1]}" if peer else "client",
                   writer)
        self.clients[writer] = c
        log.info("%s connected (%d clients)", c.name, len(self.clients))
        dec = kissio.Decoder()
        try:
            while data := await reader.read(4096):
                for port, cmd, frame in dec.feed(data):
                    if cmd != kissio.CMD_DATA:
                        log.debug("%s: KISS command 0x%02X ignored", c.name, cmd)
                        continue
                    c.rx += 1
                    self.enqueue(frame, port, c)
        except (ConnectionError, OSError):
            pass
        finally:
            self.clients.pop(writer, None)
            writer.close()
            log.info("%s disconnected (%d clients)", c.name, len(self.clients))

    def _to_clients(self, port: int, frame: bytes, skip: Client | None = None) -> None:
        raw = kissio.encode(frame, port)
        for c in list(self.clients.values()):
            if c is skip or c.writer.is_closing():
                continue
            c.writer.write(raw)
            c.tx += 1

    # --- from the TNC ---------------------------------------------------------------------

    def _from_tnc(self, port: int, frame: bytes) -> None:
        self._to_clients(port, frame)
        now = self.now()
        if self._busy_until > now:                       # it could not send meanwhile
            self._busy_until += self.airtime(len(frame))

    # --- to the TNC -------------------------------------------------------------------------

    def enqueue(self, frame: bytes, port: int = 0, origin: Client | None = None) -> None:
        heapq.heappush(self._queue, (priority(frame), next(self._seq), frame, port, origin))
        self._kick.set()

    async def _sender(self) -> None:
        while True:
            if not self._queue or not self.tnc.ready.is_set():
                if not self._queue:
                    self._kick.clear()
                    await self._kick.wait()
                else:
                    await self.tnc.ready.wait()
                continue
            wait = self._busy_until - self.now() - self.cfg.max_lead_sec
            if wait > 0:                                  # TNC still has enough to send
                self._kick.clear()
                try:
                    await asyncio.wait_for(self._kick.wait(), wait)
                except asyncio.TimeoutError:
                    pass
                continue
            prio, _, frame, port, origin = heapq.heappop(self._queue)
            if not self.tnc.send(kissio.encode(frame, port)):
                self.dropped += 1
                continue
            now = self.now()
            air = self.airtime(len(frame))
            if self._busy_until <= now:
                self._busy_until = now + air
            else:
                self._busy_until += air - self.cfg.txdelay_sec
            self._to_clients(port, frame, skip=origin)    # the others "hear" it

    # --- status ------------------------------------------------------------------------------

    def status(self) -> str:
        names = ", ".join(f"{c.name} rx {c.rx} tx {c.tx}" for c in self.clients.values())
        return (f"TNC {self.tnc.describe()} {self.tnc.state}: rx {self.tnc.rx_frames} "
                f"tx {self.tnc.tx_frames}, queued {len(self._queue)}, dropped "
                f"{self.dropped}; clients: {names or 'none'}")

    async def _status(self) -> None:
        if self.cfg.status_every_sec <= 0:
            return
        while True:
            await asyncio.sleep(self.cfg.status_every_sec)
            log.info("status: %s", self.status())
