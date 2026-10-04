"""AX.25 UI frames (connectionless), as carried inside KISS.

KISS frames contain the AX.25 frame without flags and without FCS:
    destination(7) source(7) [digipeater(7) x 0..8] control(1) pid(1) info(n)
Each address: 6 callsign chars shifted left by one bit, then one SSID byte.
"""

from __future__ import annotations

from dataclasses import dataclass, field

UI_CONTROL = 0x03
PID_NO_L3 = 0xF0


class AX25Error(ValueError):
    """Not a valid AX.25 frame."""


def encode_address(call: str, *, last: bool, high_bit: bool) -> bytes:
    """high_bit: C bit for destination/source, H (has-been-repeated) for digis."""
    base, _, ssid_text = call.upper().partition("-")
    try:
        ssid = int(ssid_text) if ssid_text else 0
    except ValueError:
        raise AX25Error(f"ungültige SSID in {call!r}") from None
    if not 1 <= len(base) <= 6 or not base.isalnum() or not 0 <= ssid <= 15:
        raise AX25Error(f"ungültige AX.25-Adresse {call!r}")
    out = bytearray(ch << 1 for ch in base.ljust(6).encode("ascii"))
    out.append(0x60 | (ssid << 1) | (0x80 if high_bit else 0) | (0x01 if last else 0))
    return bytes(out)


def decode_address(raw: bytes) -> tuple[str, bool, bool]:
    """-> (call, high_bit, last)"""
    base = bytes(b >> 1 for b in raw[:6]).decode("ascii", errors="replace").rstrip()
    ssid = (raw[6] >> 1) & 0x0F
    call = f"{base}-{ssid}" if ssid else base
    return call, bool(raw[6] & 0x80), bool(raw[6] & 0x01)


@dataclass
class UIFrame:
    dest: str
    src: str
    info: bytes
    path: list[str] = field(default_factory=list)
    pid: int = PID_NO_L3
    repeated: list[bool] = field(default_factory=list)   # H bits, receive side

    def encode(self) -> bytes:
        if len(self.path) > 8:
            raise AX25Error("höchstens 8 Digipeater")
        out = bytearray()
        out += encode_address(self.dest, last=False, high_bit=True)       # command
        out += encode_address(self.src, last=not self.path, high_bit=False)
        for i, digi in enumerate(self.path):
            out += encode_address(digi, last=i == len(self.path) - 1, high_bit=False)
        out += bytes((UI_CONTROL, self.pid))
        out += self.info
        return bytes(out)

    @classmethod
    def decode(cls, data: bytes) -> "UIFrame":
        """Raise AX25Error for anything that is not a UI frame."""
        if len(data) < 16:
            raise AX25Error("Frame zu kurz")
        addrs: list[tuple[str, bool, bool]] = []
        pos = 0
        while True:
            if pos + 7 > len(data):
                raise AX25Error("Adressfeld unvollständig")
            addrs.append(decode_address(data[pos:pos + 7]))
            pos += 7
            if addrs[-1][2]:
                break
            if len(addrs) > 10:
                raise AX25Error("zu viele Adressen")
        if len(addrs) < 2 or pos + 2 > len(data):
            raise AX25Error("Frame zu kurz")
        control, pid = data[pos], data[pos + 1]
        if control & 0xEF != UI_CONTROL:          # ignore P/F bit
            raise AX25Error("kein UI-Frame")
        return cls(dest=addrs[0][0], src=addrs[1][0], info=bytes(data[pos + 2:]),
                   path=[a[0] for a in addrs[2:]], pid=pid,
                   repeated=[a[1] for a in addrs[2:]])
