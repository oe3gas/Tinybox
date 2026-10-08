"""Compressed FBB forwarding (B0/B1): how one message travels as bytes.

After "FS +" (or "FS !offset") the sender transmits, per accepted proposal:

    SOH  len  title NUL  offset NUL      header; len = len(title) + 8,
                                         offset = 6 characters ("%6d")
    STX  n    n data bytes               repeated, n = 1..255, 0 means 256
    EOT  checksum                        checksum = -(sum of all data bytes) & 0xFF

The data bytes are the compressed payload (lzhuf.py): B0 = length + LZHUF,
B1 = CRC-16 + length + LZHUF. Restart (B1 only, answer "!offset" to a
proposal): the header carries the offset, the first STX block holds the first
6 payload bytes (CRC and length), then the payload continues at the offset.
This matches LinBPQ (FBBRoutines.c: SendCompressed, UnpackFBBBinary).

The text inside the payload is: the R: lines, an empty line, the message,
lines ending with CR LF. The title travels only in the header.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .protocol import ProtocolError

SOH, STX, EOT = 1, 2, 4
BLOCK = 250                    # what LinBPQ and FBB send per STX block
MAX_TITLE = 79


def frame(title: str, payload: bytes, offset: int = 0) -> bytes:
    """The bytes for one message. offset > 0: restart, payload[offset:] after the 6-byte block."""
    t = title.encode("utf-8", "replace")[:MAX_TITLE].replace(b"\0", b" ")
    out = bytearray([SOH, len(t) + 8]) + t + b"\0" + f"{offset:6d}".encode() + b"\0"
    data = payload[:6] if offset else b""
    chunks: list[bytes] = [data] if data else []
    rest = payload[offset:] if offset else payload
    chunks += [rest[i:i + BLOCK] for i in range(0, len(rest), BLOCK)]
    total = 0
    for c in chunks:
        out += bytes([STX, len(c) & 0xFF]) + c
        total += sum(c)
    out += bytes([EOT, (-total) & 0xFF])
    return bytes(out)


def text_to_bytes(rlines: list[str], body: str) -> bytes:
    lines = list(rlines) + ([""] if rlines else []) + body.split("\n")
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def bytes_to_text(data: bytes) -> str:
    try:
        s = data.decode("utf-8")
    except UnicodeDecodeError:
        s = data.decode("latin-1")
    return s.replace("\r\n", "\n").replace("\r", "\n")


@dataclass
class Received:
    title: str = ""
    offset: int = 0
    data: bytearray = field(default_factory=bytearray)   # STX payload bytes so far
    complete: bool = False


async def read_frame(link, timeout: float, limit: int, got: Received) -> Received:
    """Read one message frame into `got` (kept by the caller, so an aborted
    transfer still shows what arrived). Raises ProtocolError on bad framing."""

    async def need(n: int) -> bytes:
        data = await link.read_bytes(n, timeout)
        if data is None:
            from .session import Gone            # avoid an import cycle at load time
            raise Gone("connection closed by partner (in a compressed message)")
        return data

    head = await need(2)
    if head[0] != SOH:
        raise ProtocolError(f"compressed message must start with SOH, got {head[0]:#04x}")
    body = await need(head[1])
    parts = body.split(b"\0")
    if len(parts) < 2:
        raise ProtocolError("bad compressed header")
    got.title = parts[0].decode("utf-8", "replace")
    try:
        got.offset = int(parts[1].decode("ascii").strip() or "0")
    except ValueError:
        raise ProtocolError(f"bad offset in compressed header {parts[1]!r}") from None
    total = 0
    while True:
        kind, n = await need(2)
        if kind == STX:
            n = n or 256
            chunk = await need(n)
            total += sum(chunk)
            got.data += chunk
            if len(got.data) > limit:
                raise ProtocolError(f"compressed message longer than {limit} bytes")
        elif kind == EOT:
            if (total + n) & 0xFF:
                raise ProtocolError("checksum error in compressed message")
            got.complete = True
            return got
        else:
            raise ProtocolError(f"unexpected byte {kind:#04x} in compressed message")
