"""Baut das Preset-Wörterbuch für die Kompression (brocast/zdict/brocast-zdict-<Gen>.bin).

Aufruf aus dem Ordner brocast:

    py -3 tools/build_zdict.py            baut die aktuelle Generation neu
    py -3 tools/build_zdict.py --gen 2    baut die nächste Generation

Warum: deflate muss die erste Wendung einer Seite ausschreiben. Mit einem
Wörterbuch, das Station und Listener beide schon haben, findet der Packer
"Rundspruch", "Quelle: GeoSphere Austria" oder einen Blockkopf sofort als
Verweis – bei kurzen Seiten macht das den Unterschied.

Die Datei ist Teil der Software (nicht des brocast-Dictionarys) und wird nach
hinten hin wichtiger: deflate bezahlt kurze Abstände billiger, deshalb stehen
die häufigsten Wendungen am Ende. Beide Seiten müssen dieselbe Generation
haben; die Nummer steht im Frame (siehe frame.py) und der Hash im Modul
brocast/zdict.py. Nach jeder Änderung hier also:

  1. Generation erhöhen (--gen) und die neue Datei committen
  2. ZDICT_GEN und ZDICT_SHA256 in brocast/zdict.py anpassen (das Skript
     schreibt die Werte zum Kopieren auf den Bildschirm)
  3. Beide PCs aktualisieren (git pull) – eine Station mit neuer Generation
     wird von Listenern mit alter Generation nicht gelesen (Hinweis im Log).
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import cbor2
import yaml

ROOT = Path(__file__).resolve().parent.parent          # ...\brocast
MAX_BYTES = 32 * 1024                                  # deflate-Fenster
PHRASES = Path(__file__).resolve().parent / "zdict-phrasen.txt"
# Prosa als Hintergrund: deutscher Fachwortschatz, wie er in Bulletins steht
PROSE = [ROOT.parent / "README.md", ROOT.parent / "PLANUNG.md", ROOT / "README.md"]
NEWS_DIR = ROOT.parent / "tbclient" / "news"           # echte Bulletins der Mailbox


def dictionary_words(path: Path) -> list[str]:
    """Alle Namen und Anzeigetexte des brocast-Dictionarys."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    out: list[str] = []

    def walk(value: object) -> None:
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, str):
            out.append(value)

    walk(data)
    return out


def block_patterns() -> bytes:
    """CBOR-Gerüst der häufigen Blockarten (Keys und Struktur ohne Inhalt).

    Eine Blockliste beginnt immer gleich: Listenkopf, Map mit k, dann x.
    Diese Bytes sind in jeder Seite dieselben und sollen nicht übertragen werden.
    """
    blocks = []
    for k in range(0, 11):                             # Blockarten 0..10
        blocks.append({-1: k, -2: ""})
        blocks.append({-1: k, -2: "", -5: ""})
    series = {-1: 5, -3: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], -4: -1, -6: 7200, -5: ""}
    table = {-1: 7, -3: [["", 0, "", 0, 0, 0]], -4: -1, -8: ["", "", "", "", "", ""]}
    out = b""
    for n in (1, 2, 3, 4, 5, 8):
        out += cbor2.dumps(blocks[:n], canonical=True)
    out += cbor2.dumps([series], canonical=True) + cbor2.dumps([table], canonical=True)
    return out


def read_phrases() -> list[str]:
    lines = PHRASES.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.startswith(";")]


def build() -> bytes:
    parts: list[bytes] = []
    # 1. Hintergrund: Prosa (wird bei Platzmangel zuerst abgeschnitten)
    for path in PROSE:
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8", errors="ignore").encode("utf-8"))
    # 2. echte Bulletins: die Client-News gehen genauso über Funk
    if NEWS_DIR.is_dir():
        for path in sorted(NEWS_DIR.glob("*.txt")):
            parts.append(path.read_text(encoding="utf-8", errors="ignore").encode("utf-8"))
    # 3. Namen und Texte des Dictionarys
    parts.append("\n".join(dictionary_words(ROOT / "brocast-core.yaml")).encode("utf-8"))
    # 4. CBOR-Gerüst der Blockarten
    parts.append(block_patterns())
    # 5. Kernwortschatz zum Schluss: die kürzesten Abstände für das Häufigste
    parts.append("\n".join(read_phrases()).encode("utf-8"))
    data = b"\n".join(parts).replace(b"\r\n", b"\n")
    return data[-MAX_BYTES:]                            # das Ende ist das Wertvollste


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="build_zdict.py")
    ap.add_argument("--gen", type=int, default=None,
                    help="Generation (Standard: die in brocast/zdict.py eingetragene)")
    args = ap.parse_args(argv)

    sys.path.insert(0, str(ROOT))
    from brocast import zdict as zmod                   # noqa: E402  (Pfad erst jetzt bekannt)

    gen = args.gen if args.gen is not None else zmod.ZDICT_GEN
    data = build()
    out = zmod.path_for(gen)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    print(f"geschrieben: {out.relative_to(ROOT)}  {len(data)} Bytes")
    print(f"Generation:   {gen}")
    print(f"SHA-256:      {digest}")
    if gen != zmod.ZDICT_GEN or digest != zmod.ZDICT_SHA256:
        print("\nIn brocast/zdict.py eintragen:")
        print(f'    ZDICT_GEN = {gen}')
        print(f'    ZDICT_SHA256 = "{digest}"')
    else:
        print("\nbrocast/zdict.py passt dazu.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
