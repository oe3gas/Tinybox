"""KISS framing and a KISS-TCP client (KISS step K1, docs/kiss-mode-konzept.md).

TinyBox only speaks KISS over TCP: to kisshub (which owns the TNC) or, for
tests, to Direwolf's KISS port. Serial ports are kisshub's business (K7).

KISS frame:  FEND  type  data(escaped)  FEND
    type = port << 4 | command
    FEND 0xC0 -> FESC TFEND (0xDB 0xDC),  FESC 0xDB -> FESC TFESC (0xDB 0xDD)
Commands: 0 data, 1 TXDELAY (10 ms units), 2 P (persistence 0..255),
3 SlotTime (10 ms units), 4 TXtail (10 ms units, obsolete), 5 FullDuplex,
6 SetHardware; type 0xFF = leave KISS mode (no port).

SMACK ("Stuttgarter Modifiziertes Amateurfunk-CRC-KISS", TNC7multi handbook 4.1):
a data frame with bit 7 of the type byte set carries a CRC-16 over type byte and
data, appended low byte first (CRC-16/ARC: polynomial 0x8005 reflected = 0xA001,
start value 0). A SMACK TNC switches to SMACK by itself on the first CRC frame
from the PC and from then on sends CRC frames too; only data frames carry the
CRC, parameter frames stay plain KISS. Back to plain KISS only by a TNC restart.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Optional

from .termcolor import OK

log = logging.getLogger(__name__)

FEND, FESC, TFEND, TFESC = 0xC0, 0xDB, 0xDC, 0xDD

CMD_DATA = 0x00
CMD_TXDELAY = 0x01
CMD_P = 0x02
CMD_SLOTTIME = 0x03
CMD_TXTAIL = 0x04
CMD_FULLDUPLEX = 0x05
CMD_SETHW = 0x06
CMD_RETURN = 0xFF            # whole type byte, not port-shifted

MAX_FRAME = 4096             # an AX.25 frame is far smaller; guards against garbage


class KissError(ValueError):
    pass


def escape(data: bytes) -> bytes:
    return data.replace(bytes((FESC,)), bytes((FESC, TFESC))) \
               .replace(bytes((FEND,)), bytes((FESC, TFEND)))


def encode(data: bytes, port: int = 0, command: int = CMD_DATA) -> bytes:
    """One KISS frame. Leading FEND too, so a TNC resynchronises after line noise."""
    if not 0 <= port <= 15:
        raise KissError(f"KISS port {port} out of range 0..15")
    if not 0 <= command <= 0x0F:
        raise KissError(f"KISS command {command} out of range")
    return bytes((FEND, (port << 4) | command)) + escape(data) + bytes((FEND,))


SMACK_FLAG = 0x80             # bit 7 of the type byte: data frame with CRC


def _crc_table() -> tuple[int, ...]:
    table = []
    for i in range(256):
        crc = i
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
        table.append(crc)
    return tuple(table)


_CRC16 = _crc_table()


def crc16(data: bytes, crc: int = 0) -> int:
    """CRC-16/ARC as SMACK uses it (check value of b"123456789" = 0xBB3D)."""
    for b in data:
        crc = (crc >> 8) ^ _CRC16[(crc ^ b) & 0xFF]
    return crc


def encode_smack(data: bytes, port: int = 0) -> bytes:
    """One SMACK data frame: type byte 0x80 | port << 4, data, CRC low byte first."""
    if not 0 <= port <= 7:
        raise KissError(f"SMACK port {port} out of range 0..7")
    raw = bytes((SMACK_FLAG | (port << 4),)) + data
    return bytes((FEND,)) + escape(raw + crc16(raw).to_bytes(2, "little")) + bytes((FEND,))


def smack_check(port: int, data: bytes) -> bytes | None:
    """A frame the Decoder gave as port 8..15 (bit 7 set): the AX.25 data without
    the CRC if the CRC is right, else None. port is the Decoder's port (with bit 3)."""
    if len(data) < 3:
        return None
    raw = bytes(((port << 4) | CMD_DATA,)) + data
    return data[:-2] if crc16(raw) == 0 else None


def encode_param(command: int, value: int, port: int = 0) -> bytes:
    """Parameter frame, e.g. encode_param(CMD_TXDELAY, 30) = 300 ms."""
    if command not in (CMD_TXDELAY, CMD_P, CMD_SLOTTIME, CMD_TXTAIL, CMD_FULLDUPLEX):
        raise KissError(f"0x{command:02X} is not a KISS parameter command")
    if not 0 <= value <= 255:
        raise KissError(f"KISS parameter value {value} out of range 0..255")
    return encode(bytes((value,)), port, command)


def encode_return() -> bytes:
    """Leave KISS mode (C0 FF C0)."""
    return bytes((FEND, CMD_RETURN, FEND))


def ms_to_units(ms: int) -> int:
    """TXDELAY / SlotTime / TXtail are sent in 10 ms units (rounded, clamped)."""
    return max(0, min(255, round(ms / 10)))


class Decoder:
    """Feed raw bytes from a stream, get complete frames as (port, command, data).

    Empty frames (FEND FEND) are skipped, invalid escapes are kept as the raw
    byte (as most TNCs do), oversized frames are dropped until the next FEND.
    """

    def __init__(self, max_frame: int = MAX_FRAME) -> None:
        self.buf = bytearray()
        self.in_frame = False
        self.escape = False
        self.max_frame = max_frame
        self.dropped = 0          # oversized frames thrown away

    def feed(self, chunk: bytes) -> list[tuple[int, int, bytes]]:
        frames: list[tuple[int, int, bytes]] = []
        for b in chunk:
            if b == FEND:
                if self.in_frame and self.buf:
                    frames.append(self._finish())
                self.buf.clear()
                self.in_frame = True
                self.escape = False
                continue
            if not self.in_frame:
                continue
            if self.escape:
                self.escape = False
                b = FEND if b == TFEND else FESC if b == TFESC else b
            elif b == FESC:
                self.escape = True
                continue
            if len(self.buf) >= self.max_frame:
                self.buf.clear()
                self.in_frame = False      # resync on the next FEND
                self.dropped += 1
                continue
            self.buf.append(b)
        return frames

    def _finish(self) -> tuple[int, int, bytes]:
        type_byte = self.buf[0]
        if type_byte == CMD_RETURN:
            return 0, CMD_RETURN, bytes(self.buf[1:])
        return type_byte >> 4, type_byte & 0x0F, bytes(self.buf[1:])


# called with (port, ax25_bytes) for every data frame; may be a coroutine function
FrameHandler = Callable[[int, bytes], Optional[Awaitable[None]]]


class KissTcpClient:
    """One TCP connection to a KISS server (kisshub or Direwolf), reconnecting.

    Only data frames reach on_frame. send() returns False while the link is down:
    the link layer above then treats the frame as lost and its timers recover.
    """

    def __init__(self, host: str, port: int, on_frame: FrameHandler,
                 reconnect_sec: float = 5, kiss_port: int = 0) -> None:
        self.host, self.port = host, port
        self.on_frame = on_frame
        self.reconnect_sec = reconnect_sec
        self.kiss_port = kiss_port
        self.connected = asyncio.Event()
        self.rx_frames = 0
        self.tx_frames = 0
        self.tx_bytes = 0
        self._writer: asyncio.StreamWriter | None = None

    def describe(self) -> str:
        return f"KISS {self.host}:{self.port}"

    async def run(self) -> None:
        warned = False
        while True:
            try:
                reader, writer = await asyncio.open_connection(self.host, self.port)
            except OSError as exc:
                (log.debug if warned else log.error)(
                    "KISS %s:%d not reachable (%s), retrying every %ss",
                    self.host, self.port, exc, self.reconnect_sec)
                warned = True
                await asyncio.sleep(self.reconnect_sec)
                continue
            warned = False
            log.info("connected to KISS %s:%d", self.host, self.port, extra=OK)
            self._writer = writer
            self.connected.set()
            try:
                await self._read(reader)
                log.error("KISS connection closed by %s:%d", self.host, self.port)
            except (ConnectionError, OSError) as exc:
                log.error("KISS connection lost: %s", exc or type(exc).__name__)
            finally:
                self.connected.clear()
                self._writer = None
                writer.close()
            await asyncio.sleep(self.reconnect_sec)

    async def _read(self, reader: asyncio.StreamReader) -> None:
        decoder = Decoder()
        while chunk := await reader.read(4096):
            for port, command, data in decoder.feed(chunk):
                if command != CMD_DATA or port != self.kiss_port:
                    continue
                self.rx_frames += 1
                try:
                    result = self.on_frame(port, data)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception:          # one bad frame must not stop the link
                    log.exception("error handling a KISS frame")

    def send(self, ax25: bytes) -> bool:
        """Queue one AX.25 frame for sending. False = link down, frame dropped."""
        writer = self._writer
        if writer is None or writer.is_closing():
            return False
        writer.write(encode(ax25, self.kiss_port))
        self.tx_frames += 1
        self.tx_bytes += len(ax25)
        return True

    def send_param(self, command: int, value: int) -> bool:
        writer = self._writer
        if writer is None or writer.is_closing():
            return False
        writer.write(encode_param(command, value, self.kiss_port))
        return True
