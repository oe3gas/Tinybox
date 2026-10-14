"""The way to the TNC: a serial port or a TCP connection.

Both give the same small interface to tnc.py:
    await open()    raises OSError / serial errors when the TNC is not there
    write(data)     never blocks the event loop
    await read()    next chunk of bytes; raises ConnectionError when the link is gone
    close()

SerialTransport uses pyserial with one reader and one writer thread: at
9600 Bd a 300-byte write takes 0.3 s, which must not stall the asyncio loop.
Port settings as pk232py found them working on the PK-232 (P54.2): 8N1,
no XON/XOFF, no RTS/CTS, DTR and RTS asserted.

TcpTransport is for a TNC behind a network serial server (ser2net and the
like) and for the tests.
"""

from __future__ import annotations

import asyncio
import logging
import queue
import threading

log = logging.getLogger(__name__)


class SerialTransport:
    def __init__(self, device: str, baud: int, dtr: bool = True, rts: bool = True) -> None:
        self.device, self.baud, self.dtr, self.rts = device, baud, dtr, rts
        self._ser = None
        self._rx: asyncio.Queue | None = None
        self._tx: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    def describe(self) -> str:
        return f"{self.device} {self.baud} Bd"

    async def open(self) -> None:
        import serial                                  # pyserial, only needed here

        def _open():
            ser = serial.Serial(port=None, baudrate=self.baud, bytesize=8, parity="N",
                                stopbits=1, timeout=0.1, xonxoff=False, rtscts=False,
                                dsrdtr=False)
            ser.port = self.device
            ser.dtr, ser.rts = self.dtr, self.rts        # before open: no glitch
            ser.open()
            ser.reset_input_buffer()
            return ser

        self._ser = await asyncio.get_running_loop().run_in_executor(None, _open)
        loop = asyncio.get_running_loop()
        self._rx = asyncio.Queue()
        self._stop.clear()
        self._tx = queue.Queue()
        self._threads = [
            threading.Thread(target=self._reader, args=(loop,), daemon=True,
                             name="kisshub-rx"),
            threading.Thread(target=self._writer, daemon=True, name="kisshub-tx"),
        ]
        for t in self._threads:
            t.start()

    def _reader(self, loop: asyncio.AbstractEventLoop) -> None:
        try:
            while not self._stop.is_set():
                data = self._ser.read(self._ser.in_waiting or 1)
                if data:
                    loop.call_soon_threadsafe(self._rx.put_nowait, data)
        except Exception as exc:                       # unplugged USB adapter and the like
            if not self._stop.is_set():
                log.warning("serial read failed: %s", exc)
        loop.call_soon_threadsafe(self._rx.put_nowait, None)

    def _writer(self) -> None:
        while not self._stop.is_set():
            try:
                data = self._tx.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                self._ser.write(data)
                self._ser.flush()
            except Exception as exc:
                log.warning("serial write failed: %s", exc)
                return

    def write(self, data: bytes) -> None:
        self._tx.put(data)

    async def drain(self, timeout: float = 5.0) -> None:
        """Wait until everything written has left the port (used before close)."""
        end = asyncio.get_running_loop().time() + timeout
        while not self._tx.empty() and asyncio.get_running_loop().time() < end:
            await asyncio.sleep(0.05)
        await asyncio.sleep(0.2)

    async def read(self) -> bytes:
        data = await self._rx.get()
        if data is None:
            raise ConnectionError(f"serial port {self.device} lost")
        return data

    def close(self) -> None:
        self._stop.set()
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None


class TcpTransport:
    def __init__(self, host: str, port: int) -> None:
        self.host, self.port = host, port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    def describe(self) -> str:
        return f"tcp {self.host}:{self.port}"

    async def open(self) -> None:
        self._reader, self._writer = await asyncio.open_connection(self.host, self.port)

    def write(self, data: bytes) -> None:
        if self._writer is not None and not self._writer.is_closing():
            self._writer.write(data)

    async def drain(self, timeout: float = 5.0) -> None:
        if self._writer is not None:
            try:
                await asyncio.wait_for(self._writer.drain(), timeout)
            except (asyncio.TimeoutError, ConnectionError):
                pass

    async def read(self) -> bytes:
        data = await self._reader.read(4096)
        if not data:
            raise ConnectionError(f"TNC connection {self.host}:{self.port} closed")
        return data

    def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            self._writer = None
