"""Command line: show what a brocast page looks like on the air.

    py -3 -m brocast demo              Beispiel-Wetterseite kodieren und anzeigen
    py -3 -m brocast decode <hex>      CBOR-Hexstring dekodieren und anzeigen
    py -3 -m brocast dict              Dictionary-Version und Hash anzeigen
    py -3 -m brocast bild <datei>      Bild als Teletext-Mosaik (nur Station, --help dort)
"""

from __future__ import annotations

import sys

from .codec import BrocastError, Codec
from .config import ConfigError

DEMO_PAGE = {
    "id": 7,
    "rev": 42,
    "t": 1790000000,
    "exp": 60,
    "typ": "wx",
    "pos": [48.12345, 16.12345],
    "dat": {"temp": 12.5, "hum": 65, "qnh": 1013.2, "wdir": 270,
            "wspd": 3.6, "gust": 5.4, "r1h": 0.0, "r24h": 1.2},
}


def show(codec: Codec, data: bytes, ax25_src: str | None = None) -> None:
    page = codec.decode(data, ax25_src=ax25_src)
    print(f"{len(data)} Bytes: {data.hex()}")
    print()
    for line in codec.describe(page):
        print(line)


def main(argv: list[str]) -> int:
    codec = Codec()
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    try:
        if argv[0] == "demo":
            show(codec, codec.encode(DEMO_PAGE), ax25_src="OE3GAS-10")
        elif argv[0] == "decode" and len(argv) == 2:
            show(codec, bytes.fromhex(argv[1]))
        elif argv[0] == "bild":
            from .imagecmd import main as bild_main
            return bild_main(argv[1:])
        elif argv[0] == "dict":
            d = codec.d
            print(f"{d.name} Version {d.version}, Hash {d.hash4.hex()}")
        else:
            print(__doc__)
            return 2
    except (BrocastError, ConfigError, ValueError, OSError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
