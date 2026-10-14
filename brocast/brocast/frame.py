"""brocast frames on air: AX.25 UI to BROCST, PID 0xF0, 1 header byte, payload.

Header byte: high nibble = frame format, low nibble = flags.

Format 1 (klassisch, bis 13.10.2026 das einzige): payload = eine vollständige
CBOR-Seite. Lange Inhalte werden in Unterseiten geteilt, jede mit ganzem
Umschlag (splitter.py). Flags: keine (0).

Format 2 (ab 14.10.2026, Standard): payload = CBOR-Umschlag + Stück der
gepackten Blockliste. Der Umschlag steht nur im ersten Fragment, die Frames
sind voll gefüllt (fragment.py). Flags:

    Bit 0      Blockliste mit deflate gepackt (Preset-Wörterbuch, zdict.py)
    Bit 1..3   Generation des Preset-Wörterbuchs (0..7), nur mit Bit 0

Ein Listener, der ein Format nicht kennt, erkennt das am Header-Byte und lässt
die Frames liegen (keine halben Seiten). Darum bekommt jede Änderung am
Aufbau der Nutzdaten eine neue Formatnummer.
"""

from __future__ import annotations

from typing import NamedTuple

from .ax25 import PID_NO_L3, AX25Error, UIFrame

DEST = "BROCST"
FORMAT_PAGE = 1                  # eine Seite je Frame
FORMAT_FRAGMENT = 2              # Umschlag einmal, Blockliste gepackt in Fragmenten
FORMATS = (FORMAT_PAGE, FORMAT_FRAGMENT)
PROTOCOL_VERSION = FORMAT_PAGE   # alter Name, weiter benutzbar
FLAG_PACKED = 0x1                # Format 2: Blockliste ist gepackt
MAX_INFO = 256                   # classic AX.25 N1
HDR_LEN = 1


class Parsed(NamedTuple):
    """Ein gelesenes brocast-Frame."""

    frame: UIFrame
    fmt: int                     # 1 = Seite, 2 = Fragment
    flags: int                   # unteres Nibble des Header-Bytes
    payload: bytes               # Info-Feld ohne Header-Byte

    @property
    def packed(self) -> bool:
        return bool(self.flags & FLAG_PACKED)

    @property
    def zdict_gen(self) -> int:
        return (self.flags >> 1) & 0x7


def header(fmt: int = FORMAT_PAGE, flags: int = 0) -> int:
    if not 0 <= fmt <= 15 or not 0 <= flags <= 15:
        raise ValueError("Format und Flags müssen 0..15 sein")
    return (fmt << 4) | flags


def flags_for(packed: bool, zdict_gen: int = 0) -> int:
    """Flag-Nibble für Format 2."""
    if not 0 <= zdict_gen <= 7:
        raise ValueError("Generation des Wörterbuchs muss 0..7 sein")
    return (FLAG_PACKED | (zdict_gen << 1)) if packed else 0


def build(src: str, payload: bytes, path: list[str] | None = None,
          hdr: int | None = None) -> bytes:
    """AX.25-UI-Frame aus Nutzdaten. hdr = Header-Byte (Standard: Format 1)."""
    info = bytes((header() if hdr is None else hdr,)) + payload
    if len(info) > MAX_INFO:
        raise ValueError(f"Info-Feld {len(info)} Bytes > {MAX_INFO}")
    return UIFrame(dest=DEST, src=src, info=info, path=list(path or [])).encode()


def parse(data: bytes) -> Parsed | None:
    """-> Parsed for brocast frames in a format we know, else None."""
    try:
        frame = UIFrame.decode(data)
    except AX25Error:
        return None
    if frame.dest.split("-")[0] != DEST or frame.pid != PID_NO_L3 or not frame.info:
        return None
    fmt = frame.info[0] >> 4
    if fmt not in FORMATS:
        return None
    return Parsed(frame, fmt, frame.info[0] & 0xF, frame.info[1:])


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


def unknown_format(data: bytes) -> int | None:
    """Formatnummer eines brocast-Frames, das wir nicht lesen können (sonst None).

    Damit kann der Listener sagen: "neueres brocast-Format, bitte aktualisieren",
    statt das Frame als fremd (APRS, Mailbox) abzutun.
    """
    try:
        frame = UIFrame.decode(data)
    except AX25Error:
        return None
    if frame.dest.split("-")[0] != DEST or frame.pid != PID_NO_L3 or not frame.info:
        return None
    fmt = frame.info[0] >> 4
    return None if fmt in FORMATS else fmt


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
