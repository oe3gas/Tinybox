"""Forward protocol pieces: SID, FBB proposals (FB), checksum, FS answers.

References: f6fbb.org/protocole.html, FBB docfwpro.htm, W0RLI SID/BID notes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# W0RLI spec, section 1:  "[" AUTHOR_ID ["-" AUTHOR_DATA] "-" FEATURE_LIST "]"
# AUTHOR_DATA is optional and may itself contain '-'.
SID_RE = re.compile(r"^\[([^\-\[\]]+)(?:-([^\[\]]*))?-([A-Za-z0-9$]+)\]$")
FEATURE_RE = re.compile(r"([A-Z$])(\d*)")
CTRL_Z = "\x1a"
# W0RLI section 7:  "S" TYPE WHITE TO [WHITE "<" WHITE FROM] [WHITE "$" [BID]]
#                   TO = CALLSIGN [("@" | WHITE "@" WHITE) BBS]
SEND_CMD_RE = re.compile(
    r"^S([BPT])\s+([^\s@<$]+)(?:\s*@\s*([^\s<$]+))?(?:\s+<\s*(\S+))?(?:\s+\$(\S*))?\s*$", re.I)


@dataclass
class Sid:
    author: str
    version: str
    features: dict[str, str]          # letter -> revision ("" = none), e.g. {"B": "1"}

    @property
    def fbb(self) -> bool:
        return "F" in self.features

    @property
    def bid(self) -> bool:
        return "$" in self.features

    @property
    def hier(self) -> bool:
        return "H" in self.features

    def text(self) -> str:
        flags = "".join(k + v for k, v in self.features.items() if k != "$")
        if "$" in self.features:
            flags += "$"                 # must be the last character
        return f"[{self.author}-{self.version}-{flags}]"


def parse_sid(line: str) -> Sid | None:
    m = SID_RE.match(line.strip())
    if not m:
        return None
    feats: dict[str, str] = {}
    for letter, rev in FEATURE_RE.findall(m.group(3).upper()):
        feats[letter] = rev
    return Sid(m.group(1), m.group(2) or "", feats)


def parse_rli_response(line: str) -> str | None:
    """OK / NO answer to an S command. W0RLI: send the words, look at the first
    letter only; it must be followed by a blank or the line end. With feature R
    also LATER and REJECT (first letters L, R). None = not a response."""
    s = line.strip().upper()
    return {"O": ACCEPT, "N": REJECT, "R": REJECT, "L": LATER}.get(s[:1])


def parse_send_cmd(line: str) -> Proposal | None:
    """'SB ALL @ WW < OE1ABC $12_OE3GAS' -> Proposal (size 0). None = no S command."""
    m = SEND_CMD_RE.match(line.strip())
    if not m:
        return None
    typ, to, at, frm, bid = m.groups()
    return Proposal("S", typ.upper(), (frm or "").upper(), (at or "").upper(), to.upper(),
                    (bid or "").upper(), 0)


def make_sid(author: str, version: str, flags: str) -> str:
    return f"[{author}-{version}-{flags}]"


@dataclass
class Proposal:
    kind: str        # FB (ASCII message); FA would be compressed (B1, later)
    type: str        # P or B
    from_call: str
    at_addr: str
    to_call: str
    bid: str
    size: int

    def line(self) -> str:
        return (f"{self.kind} {self.type} {self.from_call} {self.at_addr} "
                f"{self.to_call} {self.bid} {self.size}")


class ProtocolError(Exception):
    pass


def parse_proposal(line: str) -> Proposal:
    parts = line.split()
    if len(parts) < 7 or parts[0] not in ("FA", "FB"):
        raise ProtocolError(f"bad proposal: {line!r}")
    kind, typ, frm, at, to, bid, size = parts[:7]
    if not size.isdigit():
        raise ProtocolError(f"bad size in proposal: {line!r}")
    return Proposal(kind, typ.upper(), frm.upper(), at.upper(), to.upper(), bid.upper(), int(size))


def checksum(lines: list[str]) -> str:
    """Two's complement of the byte sum of all proposal lines including CR."""
    total = 0
    for line in lines:
        total += sum((line + "\r").encode("ascii", "replace"))
    return f"{(-total) & 0xFF:02X}"


def check_block_end(line: str, lines: list[str]) -> bool:
    """'F> HH' -> True if the checksum fits (or none was sent)."""
    rest = line[2:].strip()
    if not rest:
        return True
    return rest.upper() == checksum(lines)


# FS answer symbols -> meaning
ACCEPT, REJECT, LATER, HOLD = "accept", "reject", "later", "hold"
FS_SYMBOLS = {"+": ACCEPT, "Y": ACCEPT, "-": REJECT, "N": REJECT,
              "=": LATER, "L": LATER, "H": HOLD, "R": REJECT, "E": REJECT}


def parse_fs(line: str, count: int) -> list[str]:
    if not line.upper().startswith("FS"):
        raise ProtocolError(f"expected FS, got {line!r}")
    symbols = line[2:].strip()
    out: list[str] = []
    i = 0
    while i < len(symbols) and len(out) < count:
        c = symbols[i].upper()
        if c in ("!", "A"):          # resume offset follows (B1); treat as accept
            i += 1
            while i < len(symbols) and symbols[i].isdigit():
                i += 1
            out.append(ACCEPT)
            continue
        if c not in FS_SYMBOLS:
            raise ProtocolError(f"unknown FS symbol {c!r} in {line!r}")
        out.append(FS_SYMBOLS[c])
        i += 1
    if len(out) != count:
        raise ProtocolError(f"FS has {len(out)} answers for {count} proposals: {line!r}")
    return out


def make_fs(answers: list[str]) -> str:
    sym = {ACCEPT: "+", REJECT: "-", LATER: "=", HOLD: "H"}
    return "FS " + "".join(sym[a] for a in answers)
