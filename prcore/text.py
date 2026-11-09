"""Text checks shared by TinyBox, the client and the tools (CR88, later CR95).

isnum() is the only allowed way to ask "is this a number?" before int():
isdigit() alone is also True for '¹²³' (they are in Latin-1, so any terminal can
send them) and for other Unicode digits - int('²') then raises ValueError
(audit TB-23). A test (tests/test_cr88.py) keeps isdigit() out of the code.
"""

from __future__ import annotations


def isnum(s: str) -> bool:
    """True for a non-empty string of ASCII digits 0-9 only."""
    return s.isascii() and s.isdigit()


def to_int(s: str, default: int | None = None) -> int | None:
    """int(s) for ASCII digits, else default."""
    return int(s) if isnum(s) else default
