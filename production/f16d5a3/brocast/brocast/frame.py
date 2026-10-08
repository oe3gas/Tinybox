"""brocast frames on air: AX.25 UI to BROCST, PID 0xF0, 1 header byte, CBOR page.

Header byte: high nibble = protocol version, low nibble = flags (reserved, 0).
"""

from __future__ import annotations

from .ax25 import PID_NO_L3, AX25Error, UIFrame

DEST = "BROCST"
PROTOCOL_VERSION = 1
MAX_INFO = 256                   # classic AX.25 N1


def build(src: str, page: bytes, path: list[str] | None = None) -> bytes:
    info = bytes(((PROTOCOL_VERSION << 4) | 0x0,)) + page
    if len(info) > MAX_INFO:
        raise ValueError(f"Info-Feld {len(info)} Bytes > {MAX_INFO}")
    return UIFrame(dest=DEST, src=src, info=info, path=list(path or [])).encode()


def parse(data: bytes) -> tuple[UIFrame, bytes] | None:
    """-> (frame, cbor page) for brocast frames we understand, else None."""
    try:
        frame = UIFrame.decode(data)
    except AX25Error:
        return None
    if frame.dest.split("-")[0] != DEST or frame.pid != PID_NO_L3 or not frame.info:
        return None
    if frame.info[0] >> 4 != PROTOCOL_VERSION:
        return None
    return frame, frame.info[1:]


def describe_other(data: bytes) -> tuple[str, str, str]:
    """(src, dest, kind) of any AX.25 frame, for the receive log. Never raises."""
    from .ax25 import decode_address
    try:
        addrs, pos = [], 0
        while pos + 7 <= len(data) and len(addrs) < 10:
            addrs.append(decode_address(data[pos:pos + 7]))
            pos += 7
            if addrs[-1][2]:
                break
        ctrl = data[pos] if pos < len(data) else 0
        kind = "UI" if ctrl & 0xEF == 0x03 else "I" if not ctrl & 1 else "S" if ctrl & 3 == 1 else "U"
        return addrs[1][0], addrs[0][0], kind
    except (IndexError, ValueError):
        return "?", "?", "?"


def airtime_s(frame_len: int, baud: int, txdelay_ms: int) -> float:
    """Rough time on air for one frame: TXDELAY + flags/FCS + ~5 % bit stuffing."""
    bits = (frame_len + 2 + 2) * 8 * 1.05
    return txdelay_ms / 1000 + bits / baud


def burst_airtime_s(frame_lens: list[int], baud: int, txdelay_ms: int) -> float:
    """Time on air for frames sent in one transmission: TXDELAY only once."""
    if not frame_lens:
        return 0.0
    return txdelay_ms / 1000 + sum(airtime_s(n, baud, 0) for n in frame_lens)


def tx_airtime_s(frame_lens: list[int], baud: int, txdelay_ms: int, burst_frames: int) -> float:
    """Time on air for a page split into transmissions of burst_frames (0 = one)."""
    size = burst_frames if burst_frames > 0 else max(len(frame_lens), 1)
    return sum(burst_airtime_s(frame_lens[i:i + size], baud, txdelay_ms)
               for i in range(0, len(frame_lens), size))
