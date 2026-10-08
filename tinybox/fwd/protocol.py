"""Protocol pieces: SID, FBB proposals, F> checksum, FS answers, W0RLI S commands.

Sources: W0RLI BBS specification of 12 Oct 1998 (docs/w0rli), F6FBB protocol
description (f6fbb.org/protocole.html).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .. import VERSION

# "[" AUTHOR_ID ["-" AUTHOR_DATA] "-" FEATURE_LIST "]"  (AUTHOR_DATA may contain '-')
SID_RE = re.compile(r"^\[([^\-\[\]]+)(?:-([^\[\]]*))?-([A-Za-z0-9$]+)\]$")
FEATURE_RE = re.compile(r"([A-Z$])(\d*)")
SEND_CMD_RE = re.compile(
    r"^S([BPT])\s+([^\s@<$]+)(?:\s*@\s*([^\s<$]+))?(?:\s+<\s*(\S+))?(?:\s+\$(\S*))?\s*$", re.I)
CTRL_Z = "\x1a"
MAX_BLOCK = 5            # proposals per FBB block


class ProtocolError(Exception):
    """The partner broke the protocol: hang up at once (W0RLI section 6)."""


@dataclass
class Sid:
    author: str
    version: str
    features: dict[str, str]

    def has(self, letter: str) -> bool:
        return letter in self.features


def parse_sid(line: str) -> Sid | None:
    m = SID_RE.match(line.strip())
    if not m:
        return None
    feats = {k: v for k, v in FEATURE_RE.findall(m.group(3).upper())}
    return Sid(m.group(1), m.group(2) or "", feats)


def own_sid(protocol: str) -> str:
    """No M: W0RLI discourages MIDs in the SID. F only if FBB batch is allowed,
    B1 only if compressed forwarding is allowed (protocol = b1)."""
    flags = {"b1": "B1FH$", "fbb": "FH$"}.get(protocol, "H$")
    return f"[TINYBOX-{VERSION}-{flags}]"


@dataclass
class Proposal:
    kind: str          # FB (ASCII), FA (compressed, B1 - later), S (W0RLI S command)
    type: str
    from_call: str
    at_addr: str
    to_call: str
    bid: str
    size: int


def parse_proposal(line: str) -> Proposal:
    parts = line.split()
    if len(parts) < 7 or parts[0].upper() not in ("FA", "FB"):
        raise ProtocolError(f"bad proposal {line!r}")
    kind, typ, frm, at, to, bid, size = parts[:7]
    if not size.isdigit():
        raise ProtocolError(f"bad size in {line!r}")
    return Proposal(kind.upper(), typ.upper(), frm.upper(), at.upper(), to.upper(),
                    bid.upper(), int(size))


def checksum(lines: list[str]) -> str:
    total = sum(sum((x + "\r").encode("ascii", "replace")) for x in lines)
    return f"{(-total) & 0xFF:02X}"


def block_end_ok(line: str, lines: list[str]) -> bool:
    rest = line[2:].strip()
    return not rest or rest.upper() == checksum(lines)


def parse_send_cmd(line: str) -> Proposal | None:
    m = SEND_CMD_RE.match(line.strip())
    if not m:
        return None
    typ, to, at, frm, bid = m.groups()
    return Proposal("S", typ.upper(), (frm or "").upper(), (at or "").upper(), to.upper(),
                    (bid or "").upper(), 0)


FS_SYMBOLS = {"+": "+", "Y": "+", "H": "+",          # H: accepted, will be held
              "-": "-", "N": "-", "R": "-", "E": "-",  # R reject, E error
              "=": "=", "L": "="}                      # later


FS_RE = re.compile(r"[!A]\d+|[^!A]", re.I)


def parse_fs(line: str, n: int) -> list[str]:
    """'FS +-=!1234' -> ['+', '-', '=', '!1234']; exactly n answers, else a
    protocol error. '!n' / 'An' = accepted, restart a B1 transfer at offset n."""
    if not line.upper().startswith("FS"):
        raise ProtocolError(f"expected FS, got {line!r}")
    out = []
    for tok in FS_RE.findall(line[2:].strip()):
        if tok[0] in "!Aa" and len(tok) > 1:
            out.append("!" + tok[1:])
        elif tok.upper() in FS_SYMBOLS:
            out.append(FS_SYMBOLS[tok.upper()])
        else:
            raise ProtocolError(f"bad FS answer {line!r}")
    if len(out) != n:
        raise ProtocolError(f"bad FS answer {line!r} for {n} proposal(s)")
    return out


def parse_rli_reply(line: str) -> str | None:
    """W0RLI answer to an S command: only the first letter counts.
    OK -> '+', NO / REJECT -> '-', LATER -> '='; None = not an answer."""
    return {"O": "+", "N": "-", "R": "-", "L": "="}.get(line.strip()[:1].upper())
