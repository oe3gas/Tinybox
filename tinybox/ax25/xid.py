"""AX.25 v2.2 XID parameter negotiation (KISS step K3).

Info field of an XID frame (AX.25 2.2, section 4.3.3.7, ISO 8885):

    FI 0x82   format indicator
    GI 0x80   group identifier (parameter negotiation)
    GL        group length, 2 bytes big endian
    then parameters, each  PI (1)  PL (1)  PV (PL bytes, big endian)

Parameters used:

    PI  2  Classes of procedures    2 bytes   balanced ABM, half / full duplex
    PI  3  HDLC optional functions  3 bytes   REJ, SREJ, modulo 8/128, ...
    PI  6  I field length Rx (N1)   in BITS
    PI  8  Window size Rx (k)       1 byte
    PI  9  Ack timer T1             milliseconds
    PI 10  Retries N2               1 byte

The bit values follow Direwolf's xid.c: the specification numbers the bits in
transmission order (LSB first per octet), so the masks below look "reversed".
They must match Direwolf on the air - checked in the interop test (K4).

Negotiation: each side states what IT can receive / supports; both use the
smaller window and I field and SREJ only if both support it.
"""

from __future__ import annotations

from dataclasses import dataclass

FI = 0x82
GI = 0x80

PI_CLASSES = 2
PI_HDLC = 3
PI_N1_RX = 6
PI_K_RX = 8
PI_T1 = 9
PI_N2 = 10

CLASS_BALANCED_ABM = 0x0100
CLASS_HALF_DUPLEX = 0x2000
CLASS_FULL_DUPLEX = 0x4000

HDLC_REJ = 0x020000
HDLC_SREJ = 0x040000
HDLC_EXTENDED_ADDRESS = 0x800000
HDLC_MODULO_8 = 0x000400
HDLC_MODULO_128 = 0x000800
HDLC_TEST = 0x002000
HDLC_FCS_16 = 0x008000
HDLC_SYNC_TX = 0x000002


class XidError(ValueError):
    pass


@dataclass(frozen=True)
class XidParams:
    """What one side offers. None = not stated (the other side's value stands)."""
    srej: bool | None = None
    rej: bool | None = None
    modulo: int | None = None          # 8 or 128
    full_duplex: bool | None = None
    n1_rx: int | None = None           # bytes (converted from bits)
    k_rx: int | None = None
    t1_ms: int | None = None
    n2: int | None = None


def _pv(value: int, length: int) -> bytes:
    return value.to_bytes(length, "big")


def encode(p: XidParams) -> bytes:
    params = bytearray()
    classes = CLASS_BALANCED_ABM | (CLASS_FULL_DUPLEX if p.full_duplex else CLASS_HALF_DUPLEX)
    params += bytes((PI_CLASSES, 2)) + _pv(classes, 2)
    hdlc = HDLC_EXTENDED_ADDRESS | HDLC_TEST | HDLC_FCS_16 | HDLC_SYNC_TX
    if p.rej or p.rej is None:
        hdlc |= HDLC_REJ
    if p.srej:
        hdlc |= HDLC_SREJ
    hdlc |= HDLC_MODULO_128 if p.modulo == 128 else HDLC_MODULO_8
    params += bytes((PI_HDLC, 3)) + _pv(hdlc, 3)
    if p.n1_rx is not None:
        params += bytes((PI_N1_RX, 2)) + _pv(min(p.n1_rx * 8, 0xFFFF), 2)
    if p.k_rx is not None:
        params += bytes((PI_K_RX, 1)) + _pv(p.k_rx, 1)
    if p.t1_ms is not None:
        params += bytes((PI_T1, 2)) + _pv(min(p.t1_ms, 0xFFFF), 2)
    if p.n2 is not None:
        params += bytes((PI_N2, 1)) + _pv(p.n2, 1)
    return bytes((FI, GI)) + _pv(len(params), 2) + bytes(params)


def decode(info: bytes) -> XidParams:
    """Raise XidError for anything that is not a parameter negotiation."""
    if len(info) < 4 or info[0] != FI or info[1] != GI:
        raise XidError("not an XID parameter negotiation")
    gl = int.from_bytes(info[2:4], "big")
    body = info[4:4 + gl]
    if len(body) != gl:
        raise XidError("XID group length beyond the frame")
    values: dict[int, int] = {}
    i = 0
    while i < len(body):
        if i + 2 > len(body):
            raise XidError("XID parameter header cut off")
        pi, pl = body[i], body[i + 1]
        if i + 2 + pl > len(body):
            raise XidError("XID parameter value cut off")
        values[pi] = int.from_bytes(body[i + 2:i + 2 + pl], "big") if pl else 0
        i += 2 + pl
    kw: dict = {}
    if PI_CLASSES in values:
        kw["full_duplex"] = bool(values[PI_CLASSES] & CLASS_FULL_DUPLEX)
    if PI_HDLC in values:
        v = values[PI_HDLC]
        kw["srej"] = bool(v & HDLC_SREJ)
        kw["rej"] = bool(v & HDLC_REJ)
        kw["modulo"] = 128 if v & HDLC_MODULO_128 else 8
    if PI_N1_RX in values:
        kw["n1_rx"] = values[PI_N1_RX] // 8
    if PI_K_RX in values:
        kw["k_rx"] = values[PI_K_RX]
    if PI_T1 in values:
        kw["t1_ms"] = values[PI_T1]
    if PI_N2 in values:
        kw["n2"] = values[PI_N2]
    return XidParams(**kw)


def combine(mine: XidParams, theirs: XidParams) -> XidParams:
    """The values both sides use: the smaller limits, SREJ only if both can."""
    def low(a, b):
        return b if a is None else a if b is None else min(a, b)
    return XidParams(
        srej=bool(mine.srej) and bool(theirs.srej),
        rej=True,
        modulo=128 if mine.modulo == 128 and theirs.modulo in (None, 128) else 8,
        full_duplex=bool(mine.full_duplex) and bool(theirs.full_duplex),
        n1_rx=low(mine.n1_rx, theirs.n1_rx),
        k_rx=low(mine.k_rx, theirs.k_rx),
        t1_ms=mine.t1_ms if theirs.t1_ms is None else max(mine.t1_ms or 0, theirs.t1_ms),
        n2=low(mine.n2, theirs.n2),
    )
