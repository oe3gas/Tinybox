"""The dictionary over the air: packed, in parts (spec: "Dictionary über Funk").

Bootstrap rule: this format must not depend on the dictionary itself, or a
listener with version 1 could never read the pages that bring version 2.
So the page is built from raw numbers that are fixed since version 1:

    envelope  0 dv, 1 id, 2 rev, 4 t, 6 typ = 10 (dict), 23 sub [n, m]   (no title:
              these pages are not shown, every byte counts)
    dat       0 version, 1 hash (8 hex chars), 3 zdata (bytes), 4 zlen (uint)

Payload: the dictionary as canonical CBOR (the same bytes the hash is taken
from), packed with zlib, cut into equal pieces so that every part fits into
one frame (MAX_PAGE_BYTES).
"""

from __future__ import annotations

import hashlib
import zlib
from typing import Any

import cbor2

from .codec import MAX_PAGE_BYTES
from .dictionary import Dictionary, DictionaryError

# fixed numbers (never taken from the dictionary)
ENV_DV, ENV_ID, ENV_REV, ENV_T, ENV_TYP, ENV_DAT, ENV_SUB = 0, 1, 2, 4, 6, 20, 23
TYP_DICT = 10
DAT_VERSION, DAT_HASH, DAT_ZDATA, DAT_ZLEN = 0, 1, 3, 4
DAT_INTERVAL = 5                   # in the announcement: sent over the air every n hours

MAX_UNPACKED = 256 * 1024          # protection against "zip bombs"
MAX_PACKED = 64 * 1024
MAX_PARTS = 255


class TransferError(ValueError):
    """Received dictionary parts are unusable."""


def payload(d: Dictionary) -> bytes:
    """Canonical CBOR of the dictionary, packed with zlib."""
    return zlib.compress(cbor2.dumps(d.raw, canonical=True), 9)


def _page(d: Dictionary, page_id: int, rev: int, t: int,
          n: int, m: int, chunk: bytes, zlen: int) -> bytes:
    wire = {ENV_DV: d.version, ENV_ID: page_id, ENV_REV: rev, ENV_T: t, ENV_TYP: TYP_DICT,
            ENV_SUB: [n, m],
            ENV_DAT: {DAT_VERSION: d.version, DAT_HASH: d.hash4.hex(),
                      DAT_ZDATA: chunk, DAT_ZLEN: zlen}}
    return cbor2.dumps(wire, canonical=True)


def build_frames(d: Dictionary, page_id: int, rev: int, t: int) -> list[bytes]:
    """All parts of the packed dictionary, each one a complete page (<= 240 bytes)."""
    data = payload(d)
    if len(data) > MAX_PACKED:
        raise TransferError(f"gepacktes Dictionary hat {len(data)} Bytes, erlaubt {MAX_PACKED}")
    # room for data = frame limit minus the page around it; the size of `sub`
    # depends on the number of parts, so start small and grow if needed
    m = 1
    while True:
        overhead = len(_page(d, page_id, rev, t, m, m, b"", len(data)))
        room = MAX_PAGE_BYTES - overhead - 2      # 2: byte string header for 24..255 bytes
        need = -(-len(data) // room)
        if need <= m:
            break
        m = need
        if m > MAX_PARTS:
            raise TransferError(f"{m} Teile nötig, erlaubt {MAX_PARTS}")
    size = -(-len(data) // m)                     # equal pieces
    chunks = [data[i:i + size] for i in range(0, len(data), size)]
    frames = [_page(d, page_id, rev, t, n, len(chunks), c, len(data))
              for n, c in enumerate(chunks, start=1)]
    assert all(len(f) <= MAX_PAGE_BYTES for f in frames)
    return frames


def part_of(page: dict[Any, Any]) -> dict[str, Any] | None:
    """Data part of a decoded typ-dict page, or None (e.g. an announcement).
    Accepts dat keys by number (older dictionary) or by name (zdata/zlen)."""
    dat = page.get("dat")
    sub = page.get("sub")
    if not isinstance(dat, dict) or not isinstance(sub, list) or len(sub) != 2:
        return None

    def get(num: int, name: str) -> Any:
        return dat.get(name, dat.get(num))

    chunk, zlen = get(DAT_ZDATA, "zdata"), get(DAT_ZLEN, "zlen")
    version, h = get(DAT_VERSION, "version"), get(DAT_HASH, "hash")
    n, m = sub
    if not (isinstance(chunk, bytes) and isinstance(zlen, int) and isinstance(version, int)
            and isinstance(h, str) and isinstance(n, int) and isinstance(m, int)
            and 1 <= n <= m <= MAX_PARTS and 0 < zlen <= MAX_PACKED):
        return None
    return {"version": version, "hash": h.lower(), "n": n, "m": m, "zlen": zlen, "chunk": chunk}


def assemble(chunks: list[bytes], zlen: int, version: int, hash_hex: str) -> Dictionary:
    """Join, unpack (limited), check length, hash and version. -> the new Dictionary."""
    data = b"".join(chunks)
    if len(data) != zlen:
        raise TransferError(f"{len(data)} statt {zlen} Bytes empfangen")
    unpacker = zlib.decompressobj()
    try:
        raw = unpacker.decompress(data, MAX_UNPACKED)
    except zlib.error as exc:
        raise TransferError(f"Entpacken fehlgeschlagen: {exc}") from None
    if unpacker.unconsumed_tail or not unpacker.eof:
        raise TransferError(f"entpackt größer als {MAX_UNPACKED // 1024} kB oder unvollständig")
    if hashlib.sha256(raw).digest()[:4].hex() != hash_hex:
        raise TransferError("Prüfsumme stimmt nicht")
    try:
        new = Dictionary(cbor2.loads(raw))
    except (DictionaryError, KeyError, TypeError, ValueError, cbor2.CBORDecodeError) as exc:
        raise TransferError(f"kein gültiges Dictionary: {exc}") from None
    if new.version != version or new.hash4.hex() != hash_hex:
        raise TransferError("Version oder Prüfsumme passen nicht zur Ankündigung")
    return new
