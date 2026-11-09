"""Text checks shared by TinyBox, the client and the tools (CR88, CR95).

Numbers - isnum() is the only allowed way to ask "is this a number?" before
int(): isdigit() alone is also True for '¹²³' (they are in Latin-1, so any
terminal can send them) and for other Unicode digits - int('²') then raises
ValueError (audit TB-23). A test (tests/test_cr88.py) keeps isdigit() out of
the code.

Free text (CR95, PLANUNG 29.9) - subjects and mail texts may be written in any
script, but nothing that can trick a reader or a program:

- clean_text(): NFC; letters, marks, digits, punctuation, symbols, spaces stay;
  control and format characters (bidi overrides, invisible characters), private
  use, unassigned code points, line/paragraph separators go; at most
  MAX_MARKS combining marks per letter ("Zalgo"); emoji only if allowed.
- defuse_lines(): lines that a mailbox or the client would read as protocol
  ("/EX", "***", "R:", "F>", "FA "/"FB "/"FS "/"FF"/"FQ", ";", "//") get one
  leading space - recognised on an NFKC copy, so a full-width "／ＥＸ" is caught.
- visible(): for the console and log files (audit TB-12) - control characters,
  bidi and C1 codes become "\\x1b", "\\u202e" ... instead of acting on the terminal.
- mixed_script(): a word of Latin and Cyrillic/Greek letters (e.g. "ОE3GAS"
  with a Cyrillic O) - for marking, never in protocol fields.

Protocol fields (calls, BIDs, routes, rubrics, commands) stay strictly ASCII;
their own checks (config.is_valid_call, addressing.BID_RE ...) do that.
"""

from __future__ import annotations

import re
import unicodedata as ud


def isnum(s: str) -> bool:
    """True for a non-empty string of ASCII digits 0-9 only."""
    return s.isascii() and s.isdigit()


def to_int(s: str, default: int | None = None) -> int | None:
    """int(s) for ASCII digits, else default."""
    return int(s) if isnum(s) else default


# --- free text --------------------------------------------------------------

MAX_MARKS = 3
JOINERS = {"‌", "‍"}          # ZWNJ/ZWJ: needed by Indic and Arabic scripts
_KEEP_CATS = {"Lu", "Ll", "Lt", "Lm", "Lo", "Mn", "Mc", "Me", "Nd", "Nl", "No",
              "Pc", "Pd", "Ps", "Pe", "Pi", "Pf", "Po", "Sc", "Sm", "Sk", "So"}
_EMOJI_CATS = {"So"}


def _joinable(ch: str, emoji: bool) -> bool:
    cat = ud.category(ch)
    return cat[0] in "LM" or (emoji and cat == "So") or ch == "\ufe0f"


def clean_text(text: str, *, emoji: bool = True) -> str:
    """Free text as it may be stored and shown (see module doc). Line ends become
    LF, tabs stay; everything not allowed is dropped, other spaces become ' '."""
    text = ud.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
    out: list[str] = []
    marks = 0
    for i, ch in enumerate(text):
        if ch in "\n\t":
            out.append(ch)
            marks = 0
            continue
        cat = ud.category(ch)
        if cat == "Zs":
            out.append(" ")
            marks = 0
            continue
        if ch in JOINERS:               # only inside a word or an emoji sequence (👨‍👩‍👧)
            if 0 < i < len(text) - 1 and _joinable(text[i - 1], emoji) \
                    and _joinable(text[i + 1], emoji):
                out.append(ch)
            continue
        if cat not in _KEEP_CATS or (not emoji and cat in _EMOJI_CATS):
            continue
        if cat[0] == "M":
            marks += 1
            if marks > MAX_MARKS:
                continue
        else:
            marks = 0
        out.append(ch)
    return "".join(out)


_PROTO_LINE = re.compile(r"^(/EX|\*\*\*|R:|F>|F[ABS] |FF\s*$|FQ\s*$|;|//)", re.IGNORECASE)


def protocol_like(line: str) -> bool:
    folded = ud.normalize("NFKC", line)
    return bool(_PROTO_LINE.match(folded))


def defuse_lines(text: str) -> str:
    """One leading space for every line a mailbox or the client would read as
    protocol - the text reads the same, but no program takes it as a command."""
    return "\n".join(" " + ln if protocol_like(ln) else ln for ln in text.split("\n"))


# --- console and log files --------------------------------------------------

def _escape(ch: str) -> str:
    n = ord(ch)
    return f"\\x{n:02x}" if n < 0x100 else f"\\u{n:04x}"


def _unsafe(ch: str) -> bool:
    n = ord(ch)
    if n < 0x20 or 0x7F <= n <= 0x9F:
        return True
    return n > 0x9F and ud.category(ch) in ("Cf", "Zl", "Zp", "Co", "Cs", "Cn")


def visible(text: str, keep: str = "\n\t") -> str:
    """Text for a terminal or log file: control, C1, bidi and other format
    characters escaped, so a received line cannot clear the screen, fake lines,
    set the window title or write the clipboard (audit TB-12)."""
    if text.isascii() and text.isprintable():
        return text
    return "".join(_escape(ch) if ch not in keep and _unsafe(ch) else ch for ch in text)


# --- mixed scripts ----------------------------------------------------------

_SCRIPTS = ("LATIN", "CYRILLIC", "GREEK", "ARMENIAN", "CHEROKEE")   # look-alike groups


def _script(ch: str) -> str | None:
    if not ch.isalpha():
        return None
    name = ud.name(ch, "")
    for s in _SCRIPTS:
        if name.startswith(s):
            return s
    return "OTHER"


def mixed_script(word: str) -> bool:
    """True for one word with letters from two look-alike scripts (UTS #39)."""
    seen = {s for s in map(_script, word) if s and s != "OTHER"}
    return len(seen) > 1
