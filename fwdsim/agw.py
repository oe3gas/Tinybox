"""AX.25 connected mode through Direwolf's AGW interface.

Frames used (36 byte header, little endian, then data):
    R version   X register call   C connect / connected   v connect via digis
    D data      d disconnect      Y outstanding frames

Direwolf does the AX.25 work. fwdsim registers the hop call (e.g. OE3GAS),
answers connects to it, and can connect to TinyBox itself.
"""

from __future__ import annotations

import asyncio
import logging
import struct
from collections import deque
from dataclasses import dataclass
from typing import Awaitable, Callable

from .config import AgwCfg
from .link import Link

log = logging.getLogger("fwdsim.agw")

HEADER = struct.Struct("<B3xcxBx10s10sII")
PID_NO_L3 = 0xF0
MAX_DATA = 65536


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
        raise ConnectionError(f"AGW frame too large: {length}")
    data = await reader.readexactly(length) if length else b""
    return Frame(kind.decode("ascii", "replace"), port, pid, _call(cfrom), _call(cto), data)


class AgwLink(Link):
    """One AX.25 connection, with simple flow control via 'Y'."""

    def __init__(self, client: "AgwClient", remote: str) -> None:
        super().__init__(f"ax25:{remote}")
        self.client = client
        self.remote = remote
        self.rx: asyncio.Queue[bytes] = asyncio.Queue()
        self.tx: deque[bytes] = deque()
        self.outstanding = 0
        self._wake = asyncio.Event()
        self._y = asyncio.Event()
        self._gone = False
        self._pump = asyncio.create_task(self._run_pump())

    async def _recv(self) -> bytes:
        return await self.rx.get()

    def _send(self, data: bytes) -> None:
        n = self.client.cfg.paclen
        self.tx.extend(data[i:i + n] for i in range(0, len(data), n))
        self._wake.set()

    async def drain(self) -> None:
        while self.tx and not self._gone:
            await asyncio.sleep(0.2)

    def gone(self) -> None:
        self._gone = True
        self.rx.put_nowait(b"")
        self._wake.set()

    async def _query_y(self) -> None:
        self._y.clear()
        self.client.send(Frame("Y", self.client.cfg.radio_port,
                               call_from=self.client.mycall, call_to=self.remote))
        try:
            await asyncio.wait_for(self._y.wait(), 5)
        except asyncio.TimeoutError:
            self.outstanding = 0

    async def _run_pump(self) -> None:
        try:
            while not self._gone:
                if not self.tx:
                    self._wake.clear()
                    await self._wake.wait()
                    continue
                while self.tx and self.outstanding < self.client.cfg.max_outstanding:
                    self.client.send(Frame("D", self.client.cfg.radio_port, PID_NO_L3,
                                           self.client.mycall, self.remote, self.tx.popleft()))
                    self.outstanding += 1
                if self.tx:
                    await asyncio.sleep(0.5)
                    await self._query_y()
        except asyncio.CancelledError:
            pass

    async def _close(self) -> None:
        await self.drain()
        # wait until Direwolf has sent everything, then disconnect
        for _ in range(120):
            if self._gone:
                break
            await self._query_y()
            if self.outstanding == 0:
                break
            await asyncio.sleep(1)
        if not self._gone:
            self.client.send(Frame("d", self.client.cfg.radio_port,
                                   call_from=self.client.mycall, call_to=self.remote))
        self._pump.cancel()


class AgwClient:
    def __init__(self, cfg: AgwCfg, mycall: str,
                 on_incoming: Callable[[AgwLink], Awaitable[None]] | None = None) -> None:
        self.cfg = cfg
        self.mycall = mycall.upper()
        self.on_incoming = on_incoming
        self.links: dict[str, AgwLink] = {}
        self._pending: dict[str, asyncio.Future] = {}
        self._writer: asyncio.StreamWriter | None = None
        self._task: asyncio.Task | None = None
        self.registered = asyncio.Event()

    def send(self, f: Frame) -> None:
        if self._writer is not None and not self._writer.is_closing():
            self._writer.write(f.pack())

    async def start(self) -> None:
        reader, self._writer = await asyncio.open_connection(self.cfg.host, self.cfg.port)
        self.send(Frame("R"))
        self.send(Frame("X", self.cfg.radio_port, call_from=self.mycall))
        self._task = asyncio.create_task(self._read_loop(reader))
        await asyncio.wait_for(self.registered.wait(), 10)

    async def stop(self) -> None:
        for link in list(self.links.values()):
            await link.close()
        if self._task:
            self._task.cancel()
        if self._writer:
            self._writer.close()

    def _remote(self, f: Frame) -> str:
        return f.call_to if f.call_from == self.mycall else f.call_from

    async def _read_loop(self, reader: asyncio.StreamReader) -> None:
        try:
            while True:
                f = await read_frame(reader)
                self._dispatch(f)
        except (asyncio.IncompleteReadError, ConnectionError) as exc:
            log.warning("AGW connection lost: %s", exc)
        except asyncio.CancelledError:
            pass
        for link in list(self.links.values()):
            link.gone()

    def _dispatch(self, f: Frame) -> None:
        remote = self._remote(f)
        if f.kind == "X":
            if f.data[:1] == b"\x01":
                log.info("%s registered with Direwolf", self.mycall)
                self.registered.set()
            else:
                log.error("Direwolf refused to register %s", self.mycall)
        elif f.kind == "C":
            link = AgwLink(self, remote)
            self.links[remote] = link
            fut = self._pending.pop(remote, None)
            if fut is not None and not fut.done():
                log.info("connected to %s", remote)
                fut.set_result(link)
            elif self.on_incoming is not None:
                log.info("incoming connect from %s", remote)
                asyncio.create_task(self.on_incoming(link))
        elif f.kind == "D":
            link = self.links.get(remote)
            if link:
                link.rx.put_nowait(f.data)
        elif f.kind == "d":
            fut = self._pending.pop(remote, None)
            if fut is not None and not fut.done():
                fut.set_exception(ConnectionError(f"connect to {remote} failed"))
            link = self.links.pop(remote, None)
            if link:
                link.gone()
            log.info("disconnected from %s", remote)
        elif f.kind == "Y":
            link = self.links.get(remote)
            if link and len(f.data) >= 4:
                link.outstanding = struct.unpack("<I", f.data[:4])[0]
                link._y.set()

    async def connect(self, remote: str, via: list[str] | None = None,
                      timeout: float = 120) -> AgwLink:
        remote = remote.upper()
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[remote] = fut
        if via:
            data = bytes([len(via)]) + b"".join(v.upper().encode("ascii").ljust(10, b"\0")
                                                 for v in via)
            self.send(Frame("v", self.cfg.radio_port, PID_NO_L3, self.mycall, remote, data))
        else:
            self.send(Frame("C", self.cfg.radio_port, PID_NO_L3, self.mycall, remote))
        return await asyncio.wait_for(fut, timeout)
