"""Lines from the TinyBox (client protocol, see tinybox/clientproto.py and chat.py).

Chat event:  #<seq> <call>: <text>      line
             #<seq> +<n> <call> [<sym>] joined as member number n (CR33)
             #<seq> -<n>                member n left
             #<seq> =<n> [<sym>]        member n has a new APRS symbol
             #<seq> <call> *<ref> <e>   reaction to event <ref>
             #<seq> !<text>             system text
             #<seq> %<n> <b> ...        link quality, b = 0..5 bars (0 = one red bar) or ?
             #<seq> ^<call> <size>      a picture is going up (CR30), size in
                                        64-byte steps (hex)
             %Q <n> <14 values>;...     link statistics of all members with data
                                        (CR33), no sequence number

Older TinyBoxes (before CR33) send calls instead of member numbers in +, -, =
and %; both forms are understood (num = 0 then).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

EVENT_RE = re.compile(r"^#([0-9A-F]{1,2}) (.+)$")
CALL = r"[A-Z0-9]{1,6}(?:-\d{1,2})?"
LINE_RE = re.compile(rf"^({CALL}): ?(.*)$", re.S)
NUM = r"[1-9]\d?"
JOIN_RE = re.compile(rf"^\+({CALL})(?: (\S{{2}}))?$")
JOIN_NUM_RE = re.compile(rf"^\+({NUM}) ({CALL})(?: (\S{{2}}))?$")
LEAVE_RE = re.compile(rf"^-({CALL})$")
LEAVE_NUM_RE = re.compile(rf"^-({NUM})$")
SYM_RE = re.compile(rf"^=({CALL})(?: (\S{{2}}))?$")
SYM_NUM_RE = re.compile(rf"^=({NUM})(?: (\S{{2}}))?$")
REACT_RE = re.compile(rf"^({CALL}) \*([0-9A-F]{{1,2}}) (\S{{1,8}})$")
QUALITY_ITEM_RE = re.compile(rf"^({CALL}|{NUM}) ([0-5?])$")
UPLOAD_RE = re.compile(rf"^\^({CALL}) ([0-9a-f]{{1,2}})$")

# %Q (CR33): per member 14 numbers, see QSTAT_FIELDS
QSTAT_FIELDS = ("num", "bars", "out_frames", "out_retry", "in_frames", "rej_tx", "retry_rx",
                "rej_rx", "t1", "bytes_new", "bytes_retry", "rx_sent", "rx_missed", "srt")


@dataclass
class Event:
    seq: int
    kind: str              # line | join | leave | symbol | react | system | quality | upload
    call: str = ""
    text: str = ""
    symbol: str = ""
    ref: int = -1          # react: the event it answers; upload: size in bytes
    bars: dict | None = None   # quality: call or member number -> 0..5, None = no result
    num: int = 0           # join/leave/symbol: member number (0 = old TinyBox, call set)


def parse_event(line: str) -> Event | None:
    m = EVENT_RE.match(line.strip("\r\n"))
    if not m:
        return None
    seq, rest = int(m.group(1), 16), m.group(2)
    if rest.startswith("!"):
        return Event(seq, "system", text=rest[1:])
    if rest.startswith("%"):
        return _quality(seq, rest[1:])
    if (u := UPLOAD_RE.match(rest)):
        return Event(seq, "upload", u.group(1), ref=int(u.group(2), 16) * 64)
    if (j := JOIN_NUM_RE.match(rest)):
        return Event(seq, "join", j.group(2), symbol=j.group(3) or "", num=int(j.group(1)))
    if (j := JOIN_RE.match(rest)):
        return Event(seq, "join", j.group(1), symbol=j.group(2) or "")
    if (lv := LEAVE_NUM_RE.match(rest)):
        return Event(seq, "leave", num=int(lv.group(1)))
    if (lv := LEAVE_RE.match(rest)):
        return Event(seq, "leave", lv.group(1))
    if (sy := SYM_NUM_RE.match(rest)):
        return Event(seq, "symbol", symbol=sy.group(2) or "", num=int(sy.group(1)))
    if (sy := SYM_RE.match(rest)):
        return Event(seq, "symbol", sy.group(1), symbol=sy.group(2) or "")
    if (r := REACT_RE.match(rest)):
        return Event(seq, "react", r.group(1), text=r.group(3), ref=int(r.group(2), 16))
    if (ln := LINE_RE.match(rest)):
        return Event(seq, "line", ln.group(1), text=ln.group(2))
    return None


def _quality(seq: int, rest: str) -> Event | None:
    """'2 4 3 ?' -> {2: 4, 3: None}; old form 'OE3TEC 4 OE1ABC ?' -> {'OE3TEC': 4, ...}"""
    parts = rest.split()
    if len(parts) % 2:
        return None
    bars: dict = {}
    for who, b in zip(parts[::2], parts[1::2]):
        if not QUALITY_ITEM_RE.match(f"{who} {b}"):
            return None
        bars[int(who) if who.isdigit() else who] = None if b == "?" else int(b)
    return Event(seq, "quality", bars=bars)


def parse_qstat(line: str) -> dict[int, dict] | None:
    """'%Q 2 4 48 2 50 3 1 1 0 41 1 48 2 14;3 ...' -> {2: {...}, 3: {...}} (CR33).
    bytes_* come in 100-byte steps, srt in tenths of a second: scaled back here.
    None if the line is not a %Q line or is broken."""
    line = line.strip("\r\n")
    if not line.startswith("%Q "):
        return None
    out: dict[int, dict] = {}
    for item in line[3:].split(";"):
        parts = item.split()
        if len(parts) != len(QSTAT_FIELDS):
            return None
        try:
            rec = {k: (None if v == "?" else int(v)) for k, v in zip(QSTAT_FIELDS, parts)}
        except ValueError:
            return None
        if rec["num"] is None or rec["num"] <= 0 or any(
                rec[k] is None for k in QSTAT_FIELDS if k != "bars"):
            return None
        rec["bytes_new"] *= 100
        rec["bytes_retry"] *= 100
        rec["srt"] = rec["srt"] / 10
        out[rec["num"]] = rec
    return out


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
