"""AGW packet engine protocol (Direwolf's AGW port): the 36-byte frame header
and reading/writing whole frames. Used by the TinyBox (tinybox/adapters/agw.py),
the client (tbclient/links.py) and fwdsim (fwdsim/agw.py); what each of them
does with the frames stays there.

Header, little endian, 36 bytes:

    port(1) 3x kind(1) x pid(1) x call_from(10) call_to(10) data_len(4) user(4)

Calls are ASCII, NUL padded to 10 bytes.
"""

from __future__ import annotations

import asyncio
import struct
from dataclasses import dataclass

HEADER = struct.Struct("<B3xcxBx10s10sII")
MAX_DATA = 65536            # longer data in one frame: the stream is broken
PID_NO_L3 = 0xF0


class AgwProtocolError(ConnectionError):
    """The AGW stream makes no sense any more (e.g. a frame that is too large)."""


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
                           self.call_from.encode("ascii", "replace"),
                           self.call_to.encode("ascii", "replace"),
                           len(self.data), 0) + self.data


def decode_call(raw: bytes) -> str:
    """A call field of the header -> 'OE3GAS-1' (upper case, no padding)."""
    return raw.split(b"\0", 1)[0].decode("ascii", "replace").strip().upper()


def via_data(calls: list[str]) -> bytes:
    """Data of the 'v' (connect via) and 'V' (UI via) frames: the number of
    digipeaters, then 10 bytes per call. The caller normalizes the calls."""
    return bytes([len(calls)]) + b"".join(
        c.encode("ascii", "replace").ljust(10, b"\0") for c in calls)


async def read_frame(reader: asyncio.StreamReader) -> Frame:
    """Read one frame. Raises asyncio.IncompleteReadError when the connection
    closes, AgwProtocolError when the header announces too much data."""
    head = await reader.readexactly(HEADER.size)
    port, kind, pid, cfrom, cto, length, _ = HEADER.unpack(head)
    if length > MAX_DATA:
        raise AgwProtocolError(f"AGW frame too large: {length}")
    data = await reader.readexactly(length) if length else b""
    return Frame(kind.decode("ascii", "replace"), port, pid,
                 decode_call(cfrom), decode_call(cto), data)
