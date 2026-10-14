"""Preset-Wörterbuch für die Kompression der Blockliste (Frame-Format 2).

Beide Seiten packen und entpacken mit demselben Wörterbuch, das nicht über
Funk geht. Es gehört zur Software, nicht zum brocast-Dictionary: die Datei
liegt in zdict/ und wird mit tools/build_zdict.py erzeugt.

Damit eine falsche Datei nicht zu Buchstabensalat führt, steht die
**Generation** (0..7) im Frame und wird beim Empfang verglichen; der Hash hier
im Modul erkennt eine beschädigte oder von Git umkodierte Datei sofort
(deshalb *.bin in .gitattributes als binary).

Fehlt oder passt die Datei nicht:
  * Station: sendet unkomprimiert weiter (nur eine Warnung im Log)
  * Listener: komprimierte Seiten anderer Generation werden verworfen,
    mit Hinweis "brocastd aktualisieren (git pull)"
"""

from __future__ import annotations

import hashlib
import logging
import zlib
from pathlib import Path

log = logging.getLogger(__name__)

ZDICT_DIR = Path(__file__).resolve().parent.parent / "zdict"
ZDICT_GEN = 1                      # 0..7, steht im Frame (frame.py: FLAG_ZDICT_GEN)
ZDICT_SHA256 = "8314fb2aa3eec225342ced40efb36622d93ed4a468d021d27b8fd2036ba82073"
MIN_GAIN = 8                       # unter 8 gesparten Bytes nicht komprimieren
LEVEL = 9
WBITS = -15                        # raw deflate: kein zlib-Kopf, keine Prüfsumme
MAX_UNPACKED = 64 * 1024           # Schutz gegen aufgeblasene Daten


def path_for(gen: int) -> Path:
    return ZDICT_DIR / f"brocast-zdict-{gen}.bin"


class ZDict:
    """Das geladene Wörterbuch (oder keines, dann wird nicht komprimiert)."""

    def __init__(self, data: bytes | None, gen: int = ZDICT_GEN, problem: str = ""):
        self.data = data
        self.gen = gen
        self.problem = problem

    @property
    def ok(self) -> bool:
        return self.data is not None

    def compress(self, raw: bytes) -> bytes | None:
        """Gepackte Form, oder None wenn es sich nicht lohnt bzw. nicht geht."""
        if not self.data:
            return None
        packer = zlib.compressobj(LEVEL, zlib.DEFLATED, WBITS, 9,
                                  zlib.Z_DEFAULT_STRATEGY, self.data)
        out = packer.compress(raw) + packer.flush()
        return out if len(out) + MIN_GAIN <= len(raw) else None

    def decompress(self, packed: bytes) -> bytes:
        """Entpacken. Wirft zlib.error, wenn die Daten nicht passen."""
        if not self.data:
            raise zlib.error("kein Preset-Wörterbuch geladen")
        unpacker = zlib.decompressobj(WBITS, zdict=self.data)
        raw = unpacker.decompress(packed, MAX_UNPACKED)
        if unpacker.unconsumed_tail:
            raise zlib.error("entpackte Daten zu groß")
        return raw + unpacker.flush()

    def describe(self) -> str:
        return f"Generation {self.gen}" if self.ok else f"nicht verfügbar ({self.problem})"


def load(gen: int = ZDICT_GEN, expect_sha256: str = ZDICT_SHA256) -> ZDict:
    """Wörterbuch dieser Generation laden und prüfen. Wirft nie."""
    path = path_for(gen)
    try:
        data = path.read_bytes()
    except OSError as exc:
        log.warning("Preset-Wörterbuch %s nicht lesbar: %s – es wird unkomprimiert "
                    "gesendet (git pull?)", path.name, exc)
        return ZDict(None, gen, f"{path.name} fehlt")
    digest = hashlib.sha256(data).hexdigest()
    if expect_sha256 and digest != expect_sha256:
        log.warning("Preset-Wörterbuch %s hat den falschen Inhalt (SHA-256 %s…) – "
                    "es wird unkomprimiert gesendet. Datei neu holen (git pull) oder mit "
                    "tools/build_zdict.py erzeugen.", path.name, digest[:8])
        return ZDict(None, gen, f"{path.name} verändert")
    return ZDict(data, gen)


__all__ = ["ZDict", "ZDICT_GEN", "ZDICT_SHA256", "load", "path_for"]
