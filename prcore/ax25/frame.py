"""AX.25 v2.2 frame codec (KISS step K1, docs/kiss-mode-konzept.md).

A KISS frame carries the AX.25 frame without flags and without FCS:

    destination(7) source(7) [digipeater(7) x 0..8] control(1|2) [pid(1)] [info(n)]

Address: 6 callsign characters shifted left by one bit, then the SSID byte

    bit 7  C bit (destination/source) or H bit "has been repeated" (digipeater)
    bit 6,5 reserved, sent as 1
    bit 4-1 SSID
    bit 0  1 = last address

Command or response (v2): destination C=1 / source C=0 -> command,
destination C=0 / source C=1 -> response. Equal bits = old v1 frame.

Control field (P/F bit 0x10 in one-byte fields, 0x01 of the second byte in
two-byte fields):

    modulo 8    I  NNN P SSS 0        S  NNN F TT 01        U  MMM P/F MM 11
    modulo 128  I  SSSSSSS 0 | NNNNNNN P    S  0000 TT 01 | NNNNNNN P/F
                (first byte sent first)                     U  always one byte

The frame does not say whether it uses modulo 8 or 128: that comes from the
link state (SABM -> 8, SABME -> 128). decode() therefore takes the modulo.
U frames decode the same in both.

PID only in I and UI frames. Info field in I, UI, FRMR, XID and TEST (and,
since v2.2 multi-SREJ, optionally SREJ - kept as raw bytes).
"""

from __future__ import annotations

import re

from dataclasses import dataclass, field

PID_NO_L3 = 0xF0
MAX_DIGIS = 8
PF_BIT = 0x10                 # one-byte control field
PF_BIT_EXT = 0x01             # second byte of a two-byte control field

# S frames: the two "TT" bits
S_KINDS = {0: "RR", 1: "RNR", 2: "REJ", 3: "SREJ"}
S_CODES = {v: k for k, v in S_KINDS.items()}

# U frames: control byte with the P/F bit cleared
U_KINDS = {
    0x6F: "SABME",
    0x2F: "SABM",
    0x43: "DISC",
    0x0F: "DM",
    0x63: "UA",
    0x87: "FRMR",
    0x03: "UI",
    0xAF: "XID",
    0xE3: "TEST",
}
U_CODES = {v: k for k, v in U_KINDS.items()}

KINDS = ("I",) + tuple(S_CODES) + tuple(U_CODES)
WITH_PID = ("I", "UI")
WITH_INFO = ("I", "UI", "FRMR", "XID", "TEST", "SREJ")


class AX25Error(ValueError):
    """Not a valid AX.25 frame (or a frame that cannot be encoded)."""


# --- addresses ------------------------------------------------------------------

def split_call(call: str) -> tuple[str, int]:
    """'OE3GAS-1' -> ('OE3GAS', 1). Raises AX25Error for anything AX.25 cannot carry."""
    base, _, ssid_text = call.strip().upper().partition("-")
    try:
        ssid = int(ssid_text) if ssid_text else 0
    except ValueError:
        raise AX25Error(f"invalid SSID in {call!r}") from None
    if not 1 <= len(base) <= 6 or not base.isascii() or not base.isalnum() \
            or not 0 <= ssid <= 15:
        raise AX25Error(f"invalid AX.25 address {call!r}")
    return base, ssid


def encode_address(call: str, *, last: bool, high_bit: bool) -> bytes:
    """high_bit: C bit for destination/source, H bit for a digipeater."""
    base, ssid = split_call(call)
    out = bytearray(ch << 1 for ch in base.ljust(6).encode("ascii"))
    out.append(0x60 | (ssid << 1) | (0x80 if high_bit else 0) | (0x01 if last else 0))
    return bytes(out)


def decode_address(raw: bytes) -> tuple[str, bool, bool]:
    """7 bytes -> (call, high_bit, last). Raises AX25Error for garbage."""
    if len(raw) != 7:
        raise AX25Error("address field too short")
    if any(b & 0x01 for b in raw[:6]):
        raise AX25Error("address extension bit set inside a callsign")
    try:
        base = bytes(b >> 1 for b in raw[:6]).decode("ascii").rstrip()
    except UnicodeDecodeError:
        raise AX25Error("callsign is not ASCII") from None
    if not base or not base.isalnum():
        raise AX25Error(f"invalid callsign {base!r}")
    ssid = (raw[6] >> 1) & 0x0F
    call = f"{base}-{ssid}" if ssid else base
    return call, bool(raw[6] & 0x80), bool(raw[6] & 0x01)


# --- the frame ---------------------------------------------------------------------

@dataclass
class Frame:
    """One AX.25 frame.

    kind     'I', 'RR', 'RNR', 'REJ', 'SREJ', 'SABM', 'SABME', 'DISC', 'DM', 'UA',
             'FRMR', 'UI', 'XID', 'TEST'
    command  True = command, False = response, None = v1 frame (C bits equal);
             encode() needs True or False
    pf       poll bit (command) or final bit (response)
    ns, nr   send / receive sequence number (I: both, S: nr only)
    modulo   8 or 128 - only matters for I and S frames
    path     digipeaters; repeated[i] = H bit of path[i]
    """

    kind: str
    dest: str
    src: str
    command: bool | None = True
    pf: bool = False
    ns: int = 0
    nr: int = 0
    pid: int = PID_NO_L3
    info: bytes = b""
    modulo: int = 8
    path: list[str] = field(default_factory=list)
    repeated: list[bool] = field(default_factory=list)

    # --- convenience ------------------------------------------------------------

    @property
    def is_i(self) -> bool:
        return self.kind == "I"

    @property
    def is_s(self) -> bool:
        return self.kind in S_CODES

    @property
    def is_u(self) -> bool:
        return self.kind in U_CODES

    @property
    def fully_repeated(self) -> bool:
        """True when no digipeater is left to repeat it (or there is no path)."""
        return all(self.repeated) if self.path else True

    def reply_path(self) -> list[str]:
        """Path for the answer: the digipeaters in reverse order (H bits cleared)."""
        return list(reversed(self.path))

    def __str__(self) -> str:
        """Monitor-style text, e.g. 'OE3ABC>OE3GAS-1,DIGI*: I s=2 r=5 P len=10'."""
        via = ""
        if self.path:
            via = "," + ",".join(c + ("*" if h else "")
                                 for c, h in zip(self.path, self.repeated or
                                                 [False] * len(self.path)))
        parts = [self.kind]
        if self.is_i:
            parts.append(f"s={self.ns}")
        if self.is_i or self.is_s:
            parts.append(f"r={self.nr}")
        if self.pf:
            parts.append("P" if self.command else "F")
        if self.command is not None:
            parts.append("C" if self.command else "R")
        if self.modulo == 128 and (self.is_i or self.is_s):
            parts.append("m128")
        if self.info:
            parts.append(f"len={len(self.info)}")
        return f"{self.src}>{self.dest}{via}: " + " ".join(parts)

    # --- encode --------------------------------------------------------------------

    def encode(self) -> bytes:
        if self.kind not in KINDS:
            raise AX25Error(f"unknown frame kind {self.kind!r}")
        if self.command is None:
            raise AX25Error("command must be True or False to encode")
        if len(self.path) > MAX_DIGIS:
            raise AX25Error(f"at most {MAX_DIGIS} digipeaters")
        if self.modulo not in (8, 128):
            raise AX25Error(f"modulo must be 8 or 128, not {self.modulo}")
        if self.info and self.kind not in WITH_INFO:
            raise AX25Error(f"{self.kind} frames carry no info field")
        if not 0 <= self.pid <= 0xFF:
            raise AX25Error("PID must be one byte")
        repeated = self.repeated or [False] * len(self.path)
        if len(repeated) != len(self.path):
            raise AX25Error("repeated must have one entry per digipeater")

        out = bytearray()
        out += encode_address(self.dest, last=False, high_bit=self.command)
        out += encode_address(self.src, last=not self.path, high_bit=not self.command)
        for i, (digi, h) in enumerate(zip(self.path, repeated)):
            out += encode_address(digi, last=i == len(self.path) - 1, high_bit=h)
        out += self._control()
        if self.kind in WITH_PID:
            out.append(self.pid)
        out += self.info
        return bytes(out)

    def _seq(self, name: str, value: int) -> int:
        if not 0 <= value < self.modulo:
            raise AX25Error(f"{name}={value} out of range for modulo {self.modulo}")
        return value

    def _control(self) -> bytes:
        pf = bool(self.pf)
        if self.is_u:
            return bytes((U_CODES[self.kind] | (PF_BIT if pf else 0),))
        nr = self._seq("nr", self.nr)
        if self.is_i:
            ns = self._seq("ns", self.ns)
            if self.modulo == 8:
                return bytes(((nr << 5) | (PF_BIT if pf else 0) | (ns << 1),))
            return bytes((ns << 1, (nr << 1) | (PF_BIT_EXT if pf else 0)))
        tt = S_CODES[self.kind] << 2 | 0x01
        if self.modulo == 8:
            return bytes(((nr << 5) | (PF_BIT if pf else 0) | tt,))
        return bytes((tt, (nr << 1) | (PF_BIT_EXT if pf else 0)))

    # --- decode ------------------------------------------------------------------------

    @classmethod
    def decode(cls, data: bytes, modulo: int = 8) -> "Frame":
        """Raise AX25Error for anything that is not a well-formed AX.25 frame.

        modulo: 8 or 128, as negotiated on the link this frame belongs to. Frames
        that do not belong to a link (UI, SABM(E), ...) decode the same either way.
        """
        if modulo not in (8, 128):
            raise AX25Error(f"modulo must be 8 or 128, not {modulo}")
        if len(data) < 15:
            raise AX25Error("frame too short")
        addrs: list[tuple[str, bool, bool]] = []
        pos = 0
        while True:
            if pos + 7 > len(data):
                raise AX25Error("address field incomplete")
            addrs.append(decode_address(data[pos:pos + 7]))
            pos += 7
            if addrs[-1][2]:
                break
            if len(addrs) >= 2 + MAX_DIGIS:
                raise AX25Error("too many addresses")
        if len(addrs) < 2:
            raise AX25Error("only one address")
        if pos >= len(data):
            raise AX25Error("control field missing")

        (dest, c_dest, _), (src, c_src, _) = addrs[0], addrs[1]
        command = None if c_dest == c_src else c_dest
        path = [a[0] for a in addrs[2:]]
        repeated = [a[1] for a in addrs[2:]]
        frame = cls(kind="", dest=dest, src=src, command=command, modulo=modulo,
                    path=path, repeated=repeated, pid=0)

        c0 = data[pos]
        if c0 & 0x03 == 0x03:                                 # U frame, always one byte
            code = c0 & ~PF_BIT & 0xFF
            if code not in U_KINDS:
                raise AX25Error(f"unknown U frame control 0x{c0:02X}")
            frame.kind = U_KINDS[code]
            frame.pf = bool(c0 & PF_BIT)
            frame.modulo = modulo
            pos += 1
        elif modulo == 8:
            frame.pf = bool(c0 & PF_BIT)
            frame.nr = c0 >> 5
            if c0 & 0x01 == 0:
                frame.kind, frame.ns = "I", (c0 >> 1) & 0x07
            else:
                frame.kind = S_KINDS[(c0 >> 2) & 0x03]
            pos += 1
        else:
            if pos + 2 > len(data):
                raise AX25Error("two-byte control field incomplete")
            c1 = data[pos + 1]
            frame.pf = bool(c1 & PF_BIT_EXT)
            frame.nr = c1 >> 1
            if c0 & 0x01 == 0:
                frame.kind, frame.ns = "I", c0 >> 1
            else:
                if c0 & 0xF0:
                    raise AX25Error(f"invalid S frame control 0x{c0:02X}")
                frame.kind = S_KINDS[(c0 >> 2) & 0x03]
            pos += 2

        if frame.kind in WITH_PID:
            if pos >= len(data):
                raise AX25Error(f"{frame.kind} frame without PID")
            frame.pid = data[pos]
            pos += 1
        else:
            frame.pid = PID_NO_L3
        rest = bytes(data[pos:])
        if rest and frame.kind not in WITH_INFO:
            raise AX25Error(f"{frame.kind} frame with info field")
        frame.info = rest
        return frame


def peek(data: bytes) -> tuple[str, str, list[str], list[bool]]:
    """Only the address field: (dest, src, path, repeated). Lets the router find
    the link - and with it the modulo - before decoding the control field."""
    addrs: list[tuple[str, bool, bool]] = []
    pos = 0
    while True:
        if pos + 7 > len(data):
            raise AX25Error("address field incomplete")
        addrs.append(decode_address(data[pos:pos + 7]))
        pos += 7
        if addrs[-1][2]:
            break
        if len(addrs) >= 2 + MAX_DIGIS:
            raise AX25Error("too many addresses")
    if len(addrs) < 2:
        raise AX25Error("only one address")
    return addrs[0][0], addrs[1][0], [a[0] for a in addrs[2:]], [a[1] for a in addrs[2:]]


_CALL_RE = re.compile(r"[A-Z0-9]{1,6}(-([0-9]|1[0-5]))?")


def addresses_valid(data: bytes) -> bool:
    """True when the address field is a sane AX.25 address field with callsigns
    of upper case letters and digits only. A TNC whose checksum passed by chance
    on noise (9600 Bd, open squelch) delivers '^?kDa?-8' - such frames must not
    reach the heard lists (CR74)."""
    try:
        dest, src, path, _ = peek(data)
    except AX25Error:
        return False
    return all(_CALL_RE.fullmatch(c) for c in (dest, src, *path))


# --- constructors for the frames the link layer sends --------------------------------

def i_frame(dest: str, src: str, ns: int, nr: int, info: bytes, *, poll: bool = False,
            modulo: int = 8, path: list[str] | None = None, pid: int = PID_NO_L3) -> Frame:
    return Frame("I", dest, src, command=True, pf=poll, ns=ns, nr=nr, info=info,
                 modulo=modulo, path=list(path or []), pid=pid)


def s_frame(kind: str, dest: str, src: str, nr: int, *, command: bool = False,
            pf: bool = False, modulo: int = 8, path: list[str] | None = None) -> Frame:
    if kind not in S_CODES:
        raise AX25Error(f"{kind} is not an S frame")
    return Frame(kind, dest, src, command=command, pf=pf, nr=nr, modulo=modulo,
                 path=list(path or []))


def u_frame(kind: str, dest: str, src: str, *, command: bool = True, pf: bool = False,
            info: bytes = b"", path: list[str] | None = None) -> Frame:
    if kind not in U_CODES:
        raise AX25Error(f"{kind} is not a U frame")
    return Frame(kind, dest, src, command=command, pf=pf, info=info, path=list(path or []))


def ui_frame(dest: str, src: str, info: bytes, *, path: list[str] | None = None,
             pid: int = PID_NO_L3) -> Frame:
    return Frame("UI", dest, src, command=True, info=info, path=list(path or []), pid=pid)
