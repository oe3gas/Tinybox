"""Frame-Format 2: Umschlag einmal, Blockliste gepackt, Frames randvoll.

Warum: Im Format 1 trägt jede Unterseite den ganzen Umschlag (Titel, Quelle,
Rubrik, Zeit …). Bei einer Seite mit acht Unterseiten gingen so rund 40 % der
Funkbytes für achtmal dasselbe weg, und die Frames waren nur zu drei Vierteln
gefüllt, weil der Splitter nur ganze Blöcke packt.

Format 2 dreht das um:

    Fragment 1   CBOR-Umschlag (ohne blk, mit sub = [1, m]) + Anfang des Blobs
    Fragment n   CBOR {id, rev, sub = [n, m]} + weiteres Stück des Blobs
    Blob         CBOR der Blockliste, als Ganzes mit deflate gepackt
                 (Preset-Wörterbuch, zdict.py; Flag und Generation im Frame)

Die Fragmente sind bis auf das letzte voll. Eine Seite ist erst mit allen
Fragmenten lesbar – dafür sind es deutlich weniger. Terminal-Lesbarkeit war
nie gegeben und ist ausdrücklich nicht das Ziel (Entscheidung 13.10.2026).

Nummern werden hier **nicht** aus dem Dictionary geholt, sondern sind fest
(wie bei dicttransfer.py): sonst könnte ein Fragment nicht gelesen werden,
ohne die Seite schon zu kennen.
"""

from __future__ import annotations

import io
import logging
import time
import zlib
from typing import Any, Callable, NamedTuple

import cbor2

from .codec import BrocastError, Codec
from .frame import FLAG_PACKED, MAX_INFO, HDR_LEN, flags_for, header, FORMAT_FRAGMENT
from .splitter import TooLargeError
from .zdict import ZDict

log = logging.getLogger(__name__)

# feste Umschlag-Nummern (seit Dictionary v1 unverändert, nie umnummerieren)
ENV_ID, ENV_REV, ENV_BLK, ENV_SUB = 1, 2, 19, 23

MAX_PAYLOAD = MAX_INFO - HDR_LEN          # 255 Bytes Nutzdaten je Frame
PENDING_TTL_S = 900.0                     # unvollständige Seite so lange aufheben
MAX_PENDING = 64                          # höchstens so viele halbe Seiten im Speicher
MAX_FRAGMENTS = 255


class Built(NamedTuple):
    """Fertige Fragmente einer Seite."""

    payloads: list[bytes]                 # Nutzdaten je Frame (ohne Header-Byte)
    hdr: int                              # Header-Byte für frame.build
    packed: bool
    blob_raw: int                         # Blockliste vor dem Packen
    blob_sent: int                        # Blockliste auf Funk

    @property
    def fragments(self) -> int:
        return len(self.payloads)


class Feed(NamedTuple):
    """Was ein empfangenes Fragment ergeben hat."""

    status: str              # page | fragment | repeat | zdict | bad
    page: bytes | None       # vollständige Seite als CBOR (wie Format 1)
    id: int | None
    rev: int | None
    sub: tuple[int, int] | None
    fragments: int = 0       # bei status page: wie viele Frames die Seite hatte
    bytes_on_air: int = 0
    note: str = ""


# ---------------------------------------------------------------------------
# senden
# ---------------------------------------------------------------------------

def build(codec: Codec, page: dict[str, Any], zd: ZDict | None = None,
          max_fragments: int = 40) -> Built:
    """Seite (benannte Felder) -> Fragmente für das Format 2."""
    wire = codec.to_wire({k: v for k, v in page.items() if k != "sub"})
    blocks = wire.pop(ENV_BLK, None)
    env = dict(wire)
    page_id, rev = env.get(ENV_ID), env.get(ENV_REV, 0)
    if not isinstance(page_id, int):
        raise BrocastError("Seite ohne id kann nicht fragmentiert werden")

    blob = cbor2.dumps(blocks, canonical=True) if blocks else b""
    blob_raw = len(blob)
    packed_flag, gen = False, 0
    if blob and zd is not None and zd.ok:
        packed = zd.compress(blob)
        if packed is not None:
            blob, packed_flag, gen = packed, True, zd.gen
    hdr = header(FORMAT_FRAGMENT, flags_for(packed_flag, gen))

    def first_head(m: int) -> bytes:
        head = dict(env) if m == 1 else {**env, ENV_SUB: [1, m]}
        return cbor2.dumps(head, canonical=True)

    def cont_head(n: int, m: int) -> bytes:
        return cbor2.dumps({ENV_ID: page_id, ENV_REV: rev, ENV_SUB: [n, m]}, canonical=True)

    if len(first_head(1)) > MAX_PAYLOAD:
        raise TooLargeError("Umschlag der Seite passt nicht in einen Frame")

    def cut(m: int) -> list[bytes]:
        """Blob in Stücke schneiden, passend zu m angekündigten Fragmenten."""
        out: list[bytes] = []
        pos, n = 0, 1
        while pos < len(blob) or n == 1:
            head = first_head(m) if n == 1 else cont_head(n, m)
            room = MAX_PAYLOAD - len(head)
            if room <= 0:
                raise TooLargeError("Umschlag lässt keinen Platz für Inhalt")
            chunk = blob[pos:pos + room]
            out.append(head + chunk)
            pos += len(chunk)
            n += 1
            if n > MAX_FRAGMENTS:
                raise TooLargeError(f"mehr als {MAX_FRAGMENTS} Fragmente nötig")
        return out

    m = 1
    for _ in range(6):                     # m wirkt auf die Kopfgröße: Fixpunkt suchen
        parts = cut(m)
        if len(parts) == m:
            break
        m = len(parts)
    else:                                  # pragma: no cover – konvergiert in 2 Runden
        parts = cut(m)
    if len(parts) > max_fragments:
        raise TooLargeError(f"mehr als {max_fragments} Fragmente nötig")
    return Built(parts, hdr, packed_flag, blob_raw, len(blob))


# ---------------------------------------------------------------------------
# empfangen
# ---------------------------------------------------------------------------

def read_payload(payload: bytes) -> tuple[dict[Any, Any], bytes]:
    """Nutzdaten -> (CBOR-Map, Rest = Stück des Blobs)."""
    fp = io.BytesIO(payload)
    head = cbor2.CBORDecoder(fp).decode()
    if not isinstance(head, dict):
        raise BrocastError("Fragment beginnt nicht mit einer CBOR-Map")
    return head, payload[fp.tell():]


class _Pending:
    __slots__ = ("env", "total", "parts", "flags", "first_seen", "bytes_on_air")

    def __init__(self, flags: int, total: int, now: float):
        self.env: dict[Any, Any] | None = None
        self.total = total
        self.parts: dict[int, bytes] = {}
        self.flags = flags
        self.first_seen = now
        self.bytes_on_air = 0


class Assembler:
    """Sammelt Fragmente des Formats 2, bis eine Seite vollständig ist.

    Nur im Arbeitsspeicher (nichts in die Datenbank, siehe PLANUNG, offener
    Punkt 9: der NanoPi soll nicht je Frame schreiben). Halbe Seiten verfallen
    nach ttl; von einer Seite wird immer nur die neueste Revision gesammelt.
    """

    def __init__(self, zd: ZDict | None = None, ttl: float = PENDING_TTL_S,
                 max_pending: int = MAX_PENDING, clock: Callable[[], float] = time.time):
        self.zd = zd
        self.ttl = ttl
        self.max_pending = max_pending
        self.clock = clock
        self.pending: dict[tuple[str, int, int], _Pending] = {}
        self.assembled = 0
        self.dropped = 0

    # -- Verwaltung ---------------------------------------------------------

    def _expire(self) -> None:
        now = self.clock()
        old = [k for k, p in self.pending.items() if now - p.first_seen > self.ttl]
        for key in old:
            del self.pending[key]
            self.dropped += 1
        while len(self.pending) > self.max_pending:
            key = min(self.pending, key=lambda k: self.pending[k].first_seen)
            del self.pending[key]
            self.dropped += 1

    def waiting(self) -> list[dict[str, Any]]:
        """Für die Statusseite: welche Seiten noch auf Fragmente warten."""
        return [{"station": call, "id": pid, "rev": rev,
                 "have": sorted(p.parts), "total": p.total,
                 "age_s": round(self.clock() - p.first_seen)}
                for (call, pid, rev), p in sorted(self.pending.items())]

    # -- Empfang ------------------------------------------------------------

    def feed(self, heard_from: str, payload: bytes, flags: int, frame_bytes: int = 0) -> Feed:
        try:
            head, chunk = read_payload(payload)
        except (BrocastError, Exception) as exc:        # cbor2 wirft mehrere Typen
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            return Feed("bad", None, None, None, None, note=f"Fragment unlesbar: {exc}")

        page_id = head.get(ENV_ID)
        rev = head.get(ENV_REV, 0)
        if not isinstance(page_id, int) or isinstance(page_id, bool) \
                or not isinstance(rev, int) or isinstance(rev, bool):
            return Feed("bad", None, None, None, None, note="Fragment ohne id/rev")
        sub = head.get(ENV_SUB)
        if sub is None:
            n, total = 1, 1
        elif (isinstance(sub, list) and len(sub) == 2
                and all(isinstance(v, int) and not isinstance(v, bool) for v in sub)
                and 1 <= sub[0] <= sub[1] <= MAX_FRAGMENTS):
            n, total = sub
        else:
            return Feed("bad", None, page_id, rev, None, note="Fragment mit ungültigem sub")

        if flags & FLAG_PACKED:
            gen = (flags >> 1) & 0x7
            if self.zd is None or not self.zd.ok or gen != self.zd.gen:
                have = self.zd.gen if (self.zd and self.zd.ok) else "keines"
                return Feed("zdict", None, page_id, rev, (n, total),
                            note=f"gepackt mit Wörterbuch {gen}, hier {have}")

        if total == 1 and n == 1:
            return self._finish(head, chunk, flags, 1, frame_bytes, page_id, rev)

        self._expire()
        key = (heard_from, page_id, rev)
        for other in [k for k in self.pending
                      if k[0] == heard_from and k[1] == page_id and k[2] < rev]:
            del self.pending[other]                     # neue Revision: alte Teile weg
        entry = self.pending.get(key)
        if entry is None or entry.total != total:
            entry = _Pending(flags, total, self.clock())
            self.pending[key] = entry
        if n in entry.parts and (n != 1 or entry.env is not None):
            return Feed("repeat", None, page_id, rev, (n, total),
                        note=f"Teil {n}/{total} schon vorhanden")
        entry.parts[n] = chunk
        entry.bytes_on_air += frame_bytes
        if n == 1:
            entry.env = head
        if len(entry.parts) < total or entry.env is None:
            return Feed("fragment", None, page_id, rev, (n, total),
                        note=f"{len(entry.parts)}/{total} Teile")
        del self.pending[key]
        blob = b"".join(entry.parts[i] for i in range(1, total + 1))
        return self._finish(entry.env, blob, entry.flags, total,
                            entry.bytes_on_air, page_id, rev)

    def _finish(self, env: dict[Any, Any], blob: bytes, flags: int, fragments: int,
                bytes_on_air: int, page_id: int, rev: int) -> Feed:
        if flags & FLAG_PACKED and blob:
            try:
                blob = self.zd.decompress(blob)          # type: ignore[union-attr]
            except (zlib.error, AttributeError) as exc:
                return Feed("bad", None, page_id, rev, None, fragments, bytes_on_air,
                            f"nicht entpackbar: {exc}")
        page = {k: v for k, v in env.items() if k != ENV_SUB}
        if blob:
            try:
                blocks = cbor2.loads(blob)
            except Exception as exc:                     # cbor2 wirft mehrere Typen
                return Feed("bad", None, page_id, rev, None, fragments, bytes_on_air,
                            f"Blockliste unlesbar: {exc}")
            if not isinstance(blocks, list):
                return Feed("bad", None, page_id, rev, None, fragments, bytes_on_air,
                            "Blockliste ist keine CBOR-Liste")
            page[ENV_BLK] = blocks
        self.assembled += 1
        return Feed("page", cbor2.dumps(page, canonical=True), page_id, rev, (1, 1),
                    fragments, bytes_on_air)


__all__ = ["Assembler", "Built", "Feed", "build", "read_payload", "TooLargeError"]
