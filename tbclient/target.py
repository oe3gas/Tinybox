"""Connect target with digipeater path (CR71): 'OE3XYZ-1 V OE3XTC-5,OE3ABC'.

One field, the classic TNC syntax: the call, then V or VIA and up to 8
digipeaters, separated by commas and/or spaces. Lower case is fine.

    parse("oe3xyz-1 via oe3xtc-5 oe3abc") -> ("OE3XYZ-1", ["OE3XTC-5", "OE3ABC"])
    label("OE3XYZ-1", ["OE3XTC-5"])        -> "OE3XYZ-1 via OE3XTC-5"

Via is layer 2 digipeating only: the digipeaters repeat our frames. A node
(NET/ROM, BPQ, Xnet) is connected like any station and asked there with C.
The same rules are in web/app.js (parseTarget) for the preview under the field.
"""

from __future__ import annotations

import re

from .config import CALL_RE

MAX_VIA = 8               # AX.25: at most 8 digipeaters in the address field
VIA_WORDS = ("V", "VIA")


class TargetError(ValueError):
    pass


def parse(text: str, mycall: str = "") -> tuple[str, list[str]]:
    """'CALL [V|VIA digi[,digi ...]]' -> (call, digis). Raises TargetError."""
    words = [w for w in re.split(r"[\s,]+", (text or "").strip().upper()) if w]
    if not words:
        raise TargetError("no call")
    call, rest = words[0], words[1:]
    if not CALL_RE.match(call):
        raise TargetError(f"{call}: not a call (e.g. OE3XYZ-8)")
    if mycall and call == mycall.upper():
        raise TargetError("that is your own call")
    if rest and rest[0] in VIA_WORDS:
        rest = rest[1:]
        if not rest:
            raise TargetError("digipeater missing after VIA")
    elif rest:
        raise TargetError(f"after the call: V or VIA, not {rest[0]}")
    if len(rest) > MAX_VIA:
        raise TargetError(f"at most {MAX_VIA} digipeaters")
    for d in rest:
        if not CALL_RE.match(d):
            raise TargetError(f"{d}: not a digipeater call")
        if d == call or (mycall and d == mycall.upper()):
            raise TargetError(f"{d} cannot be its own digipeater")
    if len(set(rest)) != len(rest):
        raise TargetError("a digipeater twice in the path")
    return call, rest


def label(call: str, via: list[str] | None) -> str:
    """The canonical text (connect field, recent list, logbook)."""
    return call + (" via " + ",".join(via) if via else "")


def valid(text: str) -> bool:
    try:
        parse(text)
    except TargetError:
        return False
    return True
