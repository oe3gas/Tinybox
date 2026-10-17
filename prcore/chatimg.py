"""Image references in chat lines (CR12, docs/client-change-requests.md).

Shared by the TinyBox (tinybox/chatimg.py: upload, storage, //IMG commands)
and the client (tbclient/images.py).

Over the air the chat line carries only a reference; the image itself is a
blob the TinyBox stores under its hash. Whoever wants to see it fetches it
over the connection (I-frames). The TinyBox never decodes an image: it checks
size, hash and the file signature (WebP or JPEG) and keeps one copy per hash.

Reference in a chat line (after an optional quote prefix ~^CALL HHMM), no
separators - every field has a fixed or self-describing length:

    ~#a1b2c350LEHV6nWB2yk8pyo0ad [caption]
      ^^^^^^                      hash: first 6 hex digits of SHA-256 of the data
            ^^                    size: 2 hex digits, in steps of 64 bytes (50 = 5120)
              ^^^^^^^^^^^^^^^^    blurhash (base83); its first character tells
                                  the component counts and so its length
                                  (3x2 = 16, 3x3 = 22 characters), and the
                                  client shapes the placeholder from them
Terminal users read "[Image 5.0 KB - TinyBox client only]" instead.

"""
from __future__ import annotations

import hashlib
import re

HASH_RE = re.compile(r"^[0-9a-f]{6}$")
SIZE_UNIT = 64
MAX_SIZE = 255 * SIZE_UNIT          # what two hex digits can say
B83 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz#$%*+,-.:;=?@[]^_{|}~"
# the fixed part of a reference: at the start or after a space (quote prefix)
REF_START = re.compile(r"(?:^|(?<= ))~#([0-9a-f]{6})([0-9a-f]{2})")


def image_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:6]


def size_code(size: int) -> str:
    """Bytes -> the two hex digits of the reference (rounded up to 64)."""
    return f"{min(255, -(-size // SIZE_UNIT)):02x}"


def image_type(data: bytes) -> str | None:
    """'webp' | 'jpeg' | None (anything else is refused)."""
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    return None


def kb(size: int) -> str:
    return f"{size / 1024:.1f} KB"


def blurhash_len(first: str) -> int:
    """Length of a blurhash from its first character (component counts)."""
    i = B83.find(first)
    if i < 0:
        return 0
    nx, ny = i % 9 + 1, i // 9 + 1
    return 4 + 2 * nx * ny


def parse_ref(text: str) -> tuple[str, int, str, int, int] | None:
    """(hash, bytes, blurhash, start, end) of the reference in a chat line."""
    m = REF_START.search(text)
    if m is None:
        return None
    rest = text[m.end():]
    n = blurhash_len(rest[:1])
    bh = rest[:n]
    if not n or len(bh) < n or any(c not in B83 for c in bh):
        return None
    if len(rest) > n and rest[n] != " ":
        return None
    return m.group(1), int(m.group(2), 16) * SIZE_UNIT, bh, m.start(), m.end() + n


def terminal_text(text: str, short: bool = False) -> str:
    """What a terminal user reads instead of the reference. short: inside a
    quoted excerpt, where the long note would eat the whole excerpt."""
    r = parse_ref(text)
    if r is None:
        return text
    _, size, _, a, z = r
    mark = "[Image]" if short else f"[Image {kb(size)} - TinyBox client only]"
    return f"{text[:a]}{mark}{text[z:]}"
