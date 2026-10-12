"""Lines from the TinyBox (client protocol, see tinybox/clientproto.py and chat.py).

Chat event:  #<seq> <call>: <text>      line
             #<seq> +<call> [<sym>]     joined
             #<seq> -<call>             left
             #<seq> =<call> [<sym>]     new APRS symbol
             #<seq> <call> *<ref> <e>   reaction to event <ref>
             #<seq> !<text>             system text
             #<seq> %<call> <b> ...     link quality, b = 0..5 bars (0 = one red bar) or ?
"""

from __future__ import annotations

import re
from dataclasses import dataclass

EVENT_RE = re.compile(r"^#([0-9A-F]{1,2}) (.+)$")
CALL = r"[A-Z0-9]{1,6}(?:-\d{1,2})?"
LINE_RE = re.compile(rf"^({CALL}): ?(.*)$", re.S)
JOIN_RE = re.compile(rf"^\+({CALL})(?: (\S{{2}}))?$")
LEAVE_RE = re.compile(rf"^-({CALL})$")
SYM_RE = re.compile(rf"^=({CALL})(?: (\S{{2}}))?$")
REACT_RE = re.compile(rf"^({CALL}) \*([0-9A-F]{{1,2}}) (\S{{1,8}})$")
QUALITY_ITEM_RE = re.compile(rf"^({CALL}) ([0-5?])$")


@dataclass
class Event:
    seq: int
    kind: str              # line | join | leave | symbol | react | system | quality
    call: str = ""
    text: str = ""
    symbol: str = ""
    ref: int = -1
    bars: dict | None = None   # quality: call -> 0..5, None = no result yet


def parse_event(line: str) -> Event | None:
    m = EVENT_RE.match(line.strip("\r\n"))
    if not m:
        return None
    seq, rest = int(m.group(1), 16), m.group(2)
    if rest.startswith("!"):
        return Event(seq, "system", text=rest[1:])
    if rest.startswith("%"):
        return _quality(seq, rest[1:])
    if (j := JOIN_RE.match(rest)):
        return Event(seq, "join", j.group(1), symbol=j.group(2) or "")
    if (lv := LEAVE_RE.match(rest)):
        return Event(seq, "leave", lv.group(1))
    if (sy := SYM_RE.match(rest)):
        return Event(seq, "symbol", sy.group(1), symbol=sy.group(2) or "")
    if (r := REACT_RE.match(rest)):
        return Event(seq, "react", r.group(1), text=r.group(3), ref=int(r.group(2), 16))
    if (ln := LINE_RE.match(rest)):
        return Event(seq, "line", ln.group(1), text=ln.group(2))
    return None


def _quality(seq: int, rest: str) -> Event | None:
    """'OE3TEC 4 OE1ABC ?' -> {'OE3TEC': 4, 'OE1ABC': None}"""
    parts = rest.split()
    if len(parts) % 2:
        return None
    bars: dict = {}
    for call, b in zip(parts[::2], parts[1::2]):
        if not QUALITY_ITEM_RE.match(f"{call} {b}"):
            return None
        bars[call] = None if b == "?" else int(b)
    return Event(seq, "quality", bars=bars)


class Unwrapper:
    """Turns the 0-255 sequence numbers into a running number (for ordering
    and gap detection). Numbers more than 128 behind count as older."""

    def __init__(self) -> None:
        self.last: int | None = None

    def reset(self, last_seq: int | None) -> None:
        self.last = last_seq            # small number: the base is 0 (fine)

    def unwrap(self, seq: int) -> int:
        if self.last is None:
            self.last = seq
            return seq
        diff = (seq - self.last) % 256
        value = self.last + diff if diff < 128 else self.last + diff - 256
        self.last = max(self.last, value)
        return value
