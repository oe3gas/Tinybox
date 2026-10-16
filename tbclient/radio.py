"""Raw AX.25 frames (as Direwolf hands them out with AGW 'k') and APRS symbols.

Frame layout without flags/FCS:
    destination(7) source(7) [digipeater(7) x 0..8] control(1) [pid(1)] info(n)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tinybox import aprs

UI_CONTROL = 0x03


@dataclass
class RawFrame:
    dest: str
    src: str
    path: list[str] = field(default_factory=list)
    control: int = 0
    info: bytes = b""
    rest: bytes = b""          # everything after the address field (monitor, modulo 128)
    repeated: list[bool] = field(default_factory=list)   # H bit per digipeater (CR55)

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


def _hbit(raw: bytes) -> bool:
    """'has been repeated' of a digipeater address (shown as '*')."""
    return bool(raw[6] & 0x80)


def decode(data: bytes) -> RawFrame | None:
    """None for anything that is not a sane AX.25 frame."""
    calls: list[str] = []
    hbits: list[bool] = []
    pos = 0
    while True:
        if pos + 7 > len(data) or len(calls) > 10:
            return None
        call, last = _addr(data[pos:pos + 7])
        calls.append(call)
        hbits.append(_hbit(data[pos:pos + 7]))
        pos += 7
        if last:
            break
    if len(calls) < 2 or pos >= len(data):
        return None
    control = data[pos]
    frame = RawFrame(calls[0], calls[1], calls[2:], control, rest=bytes(data[pos:]),
                     repeated=hbits[2:])
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


def frame_type(control: int, ext: int | None = None) -> str:
    """Control field in the style of the classic monitors: 'I 3,2', 'RR 4',
    'SABM', 'UI'; a '+' marks the poll/final bit. ext = the second control byte
    of an I or S frame with modulo 128 (AX.25 v2.2 after SABME)."""
    if control & 0x03 == 0x03:                     # U frames: always one byte
        return U_NAMES.get(control & 0xEF, f"U{control:02X}") + ("+" if control & 0x10 else "")
    if ext is not None:                            # modulo 128
        pf, nr = ("+" if ext & 0x01 else ""), ext >> 1
        if control & 0x01 == 0:
            return f"I {control >> 1},{nr}{pf}"
        return f"{S_NAMES.get(control & 0x0F, 'S?')} {nr}{pf}"
    pf = "+" if control & 0x10 else ""
    if control & 0x01 == 0:
        return f"I {(control >> 1) & 7},{(control >> 5) & 7}{pf}"
    return f"{S_NAMES.get(control & 0x0F, 'S?')} {(control >> 5) & 7}{pf}"


def guess_mod128(f: RawFrame) -> bool | None:
    """Modulo 128 without having seen the SABME (Direwolf does not show our own
    frames): an I frame has the PID (0xF0) right after one control byte (mod 8)
    or after two (mod 128); an S frame is one byte long (mod 8) or two (mod 128).
    None = cannot tell (U frames)."""
    r = f.rest
    if not r or f.control & 0x03 == 0x03:
        return None
    if f.control & 0x01 == 0:                      # I frame
        if len(r) >= 2 and r[1] == 0xF0:
            return False
        if len(r) >= 3 and r[2] == 0xF0:
            return True
        return None
    return len(r) == 2                             # S frame


def payload(f: RawFrame, mod128: bool = False) -> bytes:
    """The info field, with modulo 128 after two control bytes and the PID."""
    if mod128 and f.control & 0x03 != 0x03:
        return f.rest[3:] if f.control & 0x01 == 0 else b""
    return f.info


def text_of(info: bytes) -> str:
    raw = info.decode("utf-8", "replace").replace("\r", " ").replace("\n", " ")
    return "".join(c if c.isprintable() else "." for c in raw)[:200]


def monitor_entry(f: RawFrame, mod128: bool = False, tinyboxes: frozenset = frozenset(),
                  aprs_memory: "aprs.TelemetryMemory | None" = None,
                  home: tuple[float, float] | None = None) -> dict:
    """One monitor line as parts (CR50): the GUI colours the calls and filters.
    kind = what the TinyBox sends besides normal text (empty for anything else):
        chat     UI to TBCHAT-n: chat events (#seq ...)
        quality  %Q lines: the numbers behind the link quality bars
        mail     UI to TBMAIL: "OE3ABC 2 new" (new private mail)
        beacon   any other UI frame from a TinyBox (the beacon, CR48)
        proto    I frame with client protocol lines (//IN, //WHO, //SYNC ...)"""
    ext = f.rest[1] if mod128 and f.control & 0x03 != 0x03 and len(f.rest) >= 2 else None
    info = payload(f, mod128)
    text = text_of(info) if info else ""
    kind = ""
    if f.is_ui:
        if f.dest.startswith("TBCHAT"):
            kind = "quality" if text.startswith("%Q ") else "chat"
        elif f.dest == "TBMAIL":
            kind = "mail"
        elif f.src in tinyboxes:
            kind = "beacon"
    elif f.control & 0x01 == 0 and text:
        if text.lstrip().startswith("//"):
            kind = "proto"
        elif text.startswith("%Q "):
            kind = "quality"
    entry = {"src": f.src, "dst": f.dest,
             "via": [c + ("*" if h else "") for c, h in zip(f.path, f.repeated or [False] * len(f.path))],
             "typ": frame_type(f.control, ext), "text": text, "kind": kind}
    if f.is_ui and kind in ("", "beacon") and f.rest[1:2] == b"\xf0":
        try:                                       # CR55: APRS in plain language
            a = aprs.decode(f.dest, f.src, f.path, f.repeated, f.info, memory=aprs_memory, home=home)
        except Exception:                          # the monitor must never break the radio
            a = None
        if a is not None:
            entry["aprs"] = a
    return entry


def describe(f: RawFrame, mod128: bool = False) -> str:
    """One monitor line (CR45 channel 0): 'fm OE3XYZ to APRS via OE1XAR <UI>: text'.
    mod128: this pair talks AX.25 v2.2 with modulo 128 (SABME seen): I and S
    frames have two control bytes."""
    head = f"fm {f.src} to {f.dest}" + (f" via {','.join(f.path)}" if f.path else "")
    ext = None
    info = f.info
    if mod128 and f.control & 0x03 != 0x03 and len(f.rest) >= 2:
        ext = f.rest[1]
        info = f.rest[3:] if f.control & 0x01 == 0 else b""   # I: two control bytes + PID
    text = ""
    if info:
        raw = info.decode("utf-8", "replace").replace("\r", " ").replace("\n", " ")
        text = ": " + "".join(c if c.isprintable() else "." for c in raw)[:200]
    return f"{head} <{frame_type(f.control, ext)}>{text}"
