"""Image references in chat lines (CR12, docs/client-change-requests.md).

Shared by the TinyBox (tinybox/chatimg.py: upload, storage, //IMG commands)
and the client (tbclient/images.py).

Over the air the chat line carries only a reference; the image itself is a
blob the TinyBox stores under its hash. Whoever wants to see it fetches it
over the connection (I-frames). The TinyBox never decodes an image: it checks
size, hash and the file signature (WebP or JPEG) and keeps one copy per hash.

Reference in a chat line (after an optional quote prefix ~^CALL HHMM), no
separators - every field has a fixed or self-describing length:

    ~#a1b2c3d4e5f6a7b850LEHV6nWB2yk8pyo0ad [caption]
      ^^^^^^^^^^^^^^^^            hash: first 16 hex digits (64 bits) of SHA-256 of the
                                  data (CR86/CR96: was 6 - too easy to find a second
                                  picture with the same hash)
                      ^^          size: 2 hex digits, in steps of 64 bytes (50 = 5120)
                        ^^^^^^^^  blurhash (base83); its first character tells
                                  the component counts and so its length
                                  (3x2 = 16, 3x3 = 22 characters), and the
                                  client shapes the placeholder from them
Terminal users read "[Image 5.0 KB - TinyBox client only]" instead.

"""
from __future__ import annotations

import hashlib
import re

HASH_LEN = 16                       # hex digits (CR86/CR96, 10.11.2026; before: 6)
HASH_RE = re.compile(rf"^[0-9a-f]{{{HASH_LEN}}}$")
SIZE_UNIT = 64
MAX_SIZE = 255 * SIZE_UNIT          # what two hex digits can say
B83 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz#$%*+,-.:;=?@[]^_{|}~"
# the fixed part of a reference: at the start or after a space (quote prefix)
REF_START = re.compile(rf"(?:^|(?<= ))~#([0-9a-f]{{{HASH_LEN}}})([0-9a-f]{{2}})")


def image_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:HASH_LEN]


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


# CR86: a file in a chat line (board or client to client) - the rest of the line:
#   ~%<hash 16 hex> <bytes> <bytes on air> <name>
FILE_REF = re.compile(rf"(?:^|(?<= ))~%([0-9a-f]{{{HASH_LEN}}}) (\d{{1,7}}) (\d{{1,7}}) (\S.{{0,79}})$")


def parse_file_ref(text: str) -> tuple[str, int, int, str, int] | None:
    """(hash, bytes, bytes on air, name, start) of a file reference."""
    m = FILE_REF.search(text)
    if m is None:
        return None
    return m.group(1), int(m.group(2)), int(m.group(3)), m.group(4).strip(), m.start()


def terminal_text(text: str, short: bool = False) -> str:
    """What a terminal user reads instead of the reference. short: inside a
    quoted excerpt, where the long note would eat the whole excerpt."""
    f = parse_file_ref(text)
    if f is not None:
        mark = f"[File {f[3]}]" if short else f"[File {f[3]} {kb(f[1])} - TinyBox client only]"
        return text[:f[4]] + mark
    r = parse_ref(text)
    if r is None:
        return text
    _, size, _, a, z = r
    mark = "[Image]" if short else f"[Image {kb(size)} - TinyBox client only]"
    return f"{text[:a]}{mark}{text[z:]}"
