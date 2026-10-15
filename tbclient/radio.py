"""Raw AX.25 frames (as Direwolf hands them out with AGW 'k') and APRS symbols.

Frame layout without flags/FCS:
    destination(7) source(7) [digipeater(7) x 0..8] control(1) [pid(1)] info(n)
"""

from __future__ import annotations

from dataclasses import dataclass, field

UI_CONTROL = 0x03


@dataclass
class RawFrame:
    dest: str
    src: str
    path: list[str] = field(default_factory=list)
    control: int = 0
    info: bytes = b""

    @property
    def is_ui(self) -> bool:
        return self.control & 0xEF == UI_CONTROL

    @property
    def is_i(self) -> bool:
        """An I-frame (data of a connection). Modulo 8 - what Direwolf uses
        with maxframe <= 7; with modulo 128 one byte more belongs to the
        control field, which only shifts the counted length by one byte."""
        return self.control & 0x01 == 0

    @property
    def direct(self) -> bool:
        """Heard straight from the source, not through a digipeater."""
        return not self.path


def _addr(raw: bytes) -> tuple[str, bool]:
    base = bytes(b >> 1 for b in raw[:6]).decode("ascii", "replace").rstrip()
    ssid = (raw[6] >> 1) & 0x0F
    return (f"{base}-{ssid}" if ssid else base), bool(raw[6] & 0x01)


def decode(data: bytes) -> RawFrame | None:
    """None for anything that is not a sane AX.25 frame."""
    calls: list[str] = []
    pos = 0
    while True:
        if pos + 7 > len(data) or len(calls) > 10:
            return None
        call, last = _addr(data[pos:pos + 7])
        calls.append(call)
        pos += 7
        if last:
            break
    if len(calls) < 2 or pos >= len(data):
        return None
    control = data[pos]
    frame = RawFrame(calls[0], calls[1], calls[2:], control)
    if frame.is_ui or frame.is_i:
        frame.info = bytes(data[pos + 2:])      # skip the PID
    return frame


def aprs_symbol(info: bytes) -> str | None:
    """APRS symbol (table + code) from a position report, None if there is none.
    Handles uncompressed and compressed positions and Mic-E."""
    if not info:
        return None
    try:
        text = info.decode("latin-1")
    except Exception:
        return None
    kind = text[0]
    if kind in "!=/@":
        body = text[1:]
        if kind in "/@":                         # with timestamp (7 chars)
            body = body[7:]
        if len(body) >= 19 and body[0].isdigit():            # uncompressed
            table, code = body[8], body[18]
        elif len(body) >= 10:                                 # compressed
            table, code = body[0], body[9]
        else:
            return None
    elif kind in "`'" and len(text) >= 9:                     # Mic-E
        code, table = text[7], text[8]
    else:
        return None
    sym = table + code
    if (table in "/\\" or table.isdigit() or "A" <= table <= "Z") and "!" <= code <= "~":
        return sym
    return None


U_NAMES = {0x2F: "SABM", 0x6F: "SABME", 0x43: "DISC", 0x0F: "DM", 0x63: "UA", 0x87: "FRMR",
           0x03: "UI", 0xAF: "XID", 0xE3: "TEST"}
S_NAMES = {0x01: "RR", 0x05: "RNR", 0x09: "REJ", 0x0D: "SREJ"}


def frame_type(control: int) -> str:
    """Control field in the style of the classic monitors (modulo 8): 'I 3,2',
    'RR 4', 'SABM', 'UI'; a '+' / '-' marks the poll/final bit."""
    pf = "+" if control & 0x10 else ""
    if control & 0x01 == 0:
        return f"I {(control >> 1) & 7},{(control >> 5) & 7}{pf}"
    if control & 0x03 == 0x01:
        return f"{S_NAMES.get(control & 0x0F, 'S?')} {(control >> 5) & 7}{pf}"
    return U_NAMES.get(control & 0xEF, f"U{control:02X}") + pf


def describe(f: RawFrame) -> str:
    """One monitor line (CR45 channel 0): 'fm OE3XYZ to APRS via OE1XAR <UI>: text'."""
    head = f"fm {f.src} to {f.dest}" + (f" via {','.join(f.path)}" if f.path else "")
    text = ""
    if f.info:
        raw = f.info.decode("utf-8", "replace").replace("\r", " ").replace("\n", " ")
        text = ": " + "".join(c if c.isprintable() else "." for c in raw)[:200]
    return f"{head} <{frame_type(f.control)}>{text}"
