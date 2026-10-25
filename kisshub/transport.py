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

RTS/CTS (profile tm-d710, [tnc] rtscts = yes, 25.10.2026): the radio holds
CTS low while its buffer is full and the port driver stops sending - the
radio itself paces kisshub. RTS is then driven by the driver (we are ready
to receive). The writer sends in small pieces and waits while CTS is low, so
Ctrl+C never hangs in a blocked write; how long the radio held CTS low is
counted and shown in the status (cts_waits, cts_wait_s).

TcpTransport is for a TNC behind a network serial server (ser2net and the
like) and for the tests.
"""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
import time

log = logging.getLogger(__name__)

CHUNK = 64                 # bytes per write with RTS/CTS: a short block if CTS drops
CTS_WARN_SEC = 5.0         # CTS low this long: one warning (radio busy, cable, menu)


class SerialTransport:
    def __init__(self, device: str, baud: int, dtr: bool = True, rts: bool = True,
                 rtscts: bool = False) -> None:
        self.device, self.baud, self.dtr, self.rts = device, baud, dtr, rts
        self.rtscts = rtscts
        self.cts_waits = 0                 # times the writer waited for CTS
        self.cts_wait_s = 0.0              # total time CTS held us back
        self._ser = None
        self._rx: asyncio.Queue | None = None
        self._tx: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    def describe(self) -> str:
        return f"{self.device} {self.baud} Bd" + (" RTS/CTS" if self.rtscts else "")

    def flow_status(self) -> dict:
        cts = None
        if self._ser is not None and self.rtscts:
            try:
                cts = bool(self._ser.cts)
            except Exception:
                pass
        return {"flow": "rtscts" if self.rtscts else "none", "cts": cts,
                "cts_waits": self.cts_waits, "cts_wait_s": round(self.cts_wait_s, 1)}

    async def open(self) -> None:
        import serial                                  # pyserial, only needed here

        def _open():
            ser = serial.Serial(port=None, baudrate=self.baud, bytesize=8, parity="N",
                                stopbits=1, timeout=0.1, xonxoff=False,
                                rtscts=self.rtscts, dsrdtr=False,
                                write_timeout=2.0 if self.rtscts else None)
            ser.port = self.device
            ser.dtr = self.dtr                           # before open: no glitch
            if not self.rtscts:                          # with RTS/CTS the driver drives RTS
                ser.rts = self.rts
            ser.open()
            ser.reset_input_buffer()
            if self.rtscts and not ser.cts:
                log.warning("%s: CTS is low - the radio does not take data yet "
                            "(TNC busy, cable without RTS/CTS lines, or radio off?)",
                            self.device)
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
                if self.rtscts:
                    for i in range(0, len(data), CHUNK):
                        if not self._wait_cts():
                            return
                        self._ser.write(data[i:i + CHUNK])
                else:
                    self._ser.write(data)
                self._ser.flush()
            except Exception as exc:
                log.warning("serial write failed: %s", exc)
                return

    def _wait_cts(self) -> bool:
        """RTS/CTS: wait while the radio holds CTS low. False when stopping."""
        if self._ser.cts:
            return True
        start = time.monotonic()
        warned = False
        self.cts_waits += 1
        while not self._ser.cts:
            if self._stop.is_set():
                return False
            waited = time.monotonic() - start
            if not warned and waited >= CTS_WARN_SEC:
                log.warning("%s: CTS low for %.0f s - the radio holds data back",
                            self.device, waited)
                warned = True
            time.sleep(0.01)
        waited = time.monotonic() - start
        self.cts_wait_s += waited
        if warned:
            log.info("%s: CTS high again after %.1f s", self.device, waited)
        else:
            log.debug("%s: waited %.0f ms for CTS", self.device, waited * 1000)
        return True

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
