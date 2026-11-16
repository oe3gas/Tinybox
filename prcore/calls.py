"""Callsigns: normalizing, the base call and the checks - in one place (Refactoring R6).

Before, about ten regexes and nine base-call functions with slightly different rules
lived in tinybox, tbclient and prcore. Who is the sysop, whose key is it, who is banned:
all of that compares calls, so all of it goes through the same functions here.

    normalize_call(" oe3gas-1 ")  -> "OE3GAS-1"     blanks off, upper case
    norm_call("oe3gas-0")         -> "OE3GAS"       as normalize_call, "-0" dropped
                                                    (the form links are keyed by)
    base_call("oe3gas-1")         -> "OE3GAS"       without the SSID

    is_ax25_call(c)     any AX.25 address: 1-6 letters/digits, SSID 0-15
                        (destinations like BEACON or APRS too)
    is_valid_call(c)    a station: 3-6 characters with a digit and a letter, SSID 0-15
    plausible_call(c)   a station that connects (CR92): also the structure
                        prefix + digits + suffix - not 70CM, QO100, ABCDEF

The checks expect a normalized call (upper case); they do not normalize themselves.
TinyBox, client, kisshub and brocast use these (PLANUNG 17.4); fwdsim, release/konfig.py
and dxfeed keep their own copies on purpose.
"""

from __future__ import annotations

import re

_SSID = r"(-([0-9]|1[0-5]))?"

# any AX.25 address field entry
AX25_CALL_RE = re.compile(r"^[A-Z0-9]{1,6}" + _SSID + r"\Z")
# a station: 3-6 characters, at least one digit and one letter, optional SSID
CALL_RE = re.compile(r"^(?=[A-Z0-9]*[0-9])(?=[A-Z0-9]*[A-Z])[A-Z0-9]{3,6}" + _SSID + r"\Z")
# the same without SSID (a base call)
BASE_CALL_RE = re.compile(r"^(?=[A-Z0-9]*[0-9])(?=[A-Z0-9]*[A-Z])[A-Z0-9]{3,6}\Z")


def normalize_call(call: str | None) -> str:
    """' oe3gas-1 ' -> 'OE3GAS-1'"""
    return (call or "").strip().upper()


def norm_call(call: str | None) -> str:
    """'oe3gas-0 ' -> 'OE3GAS': the form links are keyed by."""
    call = normalize_call(call)
    return call[:-2] if call.endswith("-0") else call


def base_call(call: str | None) -> str:
    """'oe3gas-1' -> 'OE3GAS'"""
    return normalize_call(call).split("-", 1)[0]


def is_ax25_call(call: str) -> bool:
    return bool(AX25_CALL_RE.match(call))


def is_valid_call(call: str) -> bool:
    return bool(CALL_RE.match(call))


def plausible_call(call: str) -> bool:
    """A station that connects: at most 6 characters, prefix (with a letter) +
    digit(s) + letters (OE3GAS, DL1ABC-7, 4X1AB) - not 'ABCDEF', 'QST',
    '123456', or a rubric name like '70CM' or 'QO100'."""
    call = call.upper()
    if not CALL_RE.match(call):
        return False
    return _structure_ok(call.split("-", 1)[0])


def _structure_ok(base: str) -> bool:
    """CR92 (TB-15): prefix of 1-3 characters with a letter, digits, a suffix of
    letters - OE3GAS, 4X1AB, 2E0ABC, 3DA0RU, K1A. Rubric names like 70CM, 10M,
    23CM, QO100 or WX are no call."""
    i = len(base)
    while i and base[i - 1].isalpha():
        i -= 1
    suffix = base[i:]
    j = i
    while j and base[j - 1] in "0123456789":
        j -= 1
    prefix = base[:j]
    return bool(suffix) and j < i and 1 <= len(prefix) <= 3 and any(c.isalpha() for c in prefix)
