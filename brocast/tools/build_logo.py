#!/usr/bin/env python3
"""Den brocast-Schriftzug fuer den Kopf der Teletext-Ansicht erzeugen.

    py -3 brocast/tools/build_logo.py

Vorlage ist die Titelseite des ORF-Teletext: ein Feld aus lauter kleinen hellen
Quadraten mit schwarzen Fugen, und der Schriftzug steht als ausgesparte,
schwarze Flaeche darin - die Buchstaben sind also die Quadrate, die fehlen.
Darunter die rote Linie.

Gebaut wird das Feld aus Rasterzellen (ZELLE Bildpunkte, davon QUADRAT gefuellt).
Die Buchstaben entstehen aus Liberation Sans Bold (Arial-Nachbau, wie auf der
Vorlage), schwarz-weiss gerastert: ein
gesetztes Pixel der Schrift = eine Zelle ohne Quadrat. Die Schriftgroesse wird
automatisch so gewaehlt, dass der Schriftzug in die Breite passt.

Das Ergebnis (brocast/brocast/web/brocast-logo.svg) liegt im Repo; das Skript
muss nur laufen, wenn sich Schriftzug oder Raster aendern. SVG mit
shape-rendering="crispEdges": der Listener skaliert es auf die Breite des
Teletext-Bildschirms (40 Zeichen = 560 px bei font-size 32), die Kanten bleiben hart.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_teletext_font import rechtecke                        # noqa: E402

QUELLE = Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf")
ZIEL = Path(__file__).resolve().parent.parent / "brocast" / "web" / "brocast-logo.svg"

TEXT = "brocast"
BREITE = 560              # Einheiten im SVG; der Listener skaliert auf die
                          # Bildschirmbreite (40 Zeichen = 560 px bei font-size 32)
ZELLE = 6                 # Rasterzelle
QUADRAT = 5               # davon das helle Quadrat (der Rest ist die schwarze Fuge)
RAND = 1                  # Zellen Luft zwischen Feldrand und Schriftzug
SCHWARZ_RAND = 6          # schwarzer Rand um das Feld (wie der Fernsehrahmen)

HELL, SCHWARZ, ROT = "#D2D2D2", "#000000", "#E02A2A"


def buchstaben(text: str, zellen: int) -> tuple[set[tuple[int, int]], int, int]:
    """Groesstes Raster des Schriftzugs, das in `zellen` Zellen Breite passt."""
    for ppem in range(26, 7, -1):
        font = ImageFont.truetype(str(QUELLE), ppem)
        asc, desc = font.getmetrics()
        img = Image.new("1", (int(font.getlength(text)) + 4, asc + desc), 0)
        d = ImageDraw.Draw(img)
        d.fontmode = "1"                                         # bilevel, kein Antialiasing
        d.text((1, 0), text, font=font, fill=1, anchor="la")
        bb = img.getbbox()
        if bb is None or bb[2] - bb[0] > zellen:
            continue
        px = img.load()
        pixel = {(x - bb[0], y - bb[1]) for y in range(bb[1], bb[3]) for x in range(bb[0], bb[2])
                 if px[x, y]}
        return pixel, bb[2] - bb[0], bb[3] - bb[1]
    raise SystemExit(f"{text!r} passt nicht in {zellen} Zellen")


def main() -> int:
    if not QUELLE.exists():
        print(f"Quellschrift fehlt: {QUELLE}", file=sys.stderr)
        return 2
    feld_breite = BREITE - 2 * SCHWARZ_RAND
    spalten = feld_breite // ZELLE
    pixel, bw, bh = buchstaben(TEXT, spalten - 2 * RAND)
    zeilen = bh + 2 * RAND
    feld_hoehe = zeilen * ZELLE
    hoehe = feld_hoehe + 2 * SCHWARZ_RAND + 6                    # + schwarzer Rand + rote Linie
    ox = SCHWARZ_RAND + (feld_breite - spalten * ZELLE) // 2     # Feld waagrecht mittig
    sx = (spalten - bw) // 2                                     # Schriftzug im Feld mittig

    # Das Feld ist ein Muster aus hellen Quadraten; der Schriftzug liegt als
    # schwarze Flaeche darueber und verschluckt dort auch die Fugen.
    teile = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {BREITE} {hoehe}" '
             f'width="{BREITE}" height="{hoehe}" shape-rendering="crispEdges" '
             f'role="img" aria-label="brocast">',
             '<defs>',
             f'<pattern id="q" x="{ox}" y="{SCHWARZ_RAND}" width="{ZELLE}" height="{ZELLE}" '
             f'patternUnits="userSpaceOnUse">',
             f'<rect width="{QUADRAT}" height="{QUADRAT}" fill="{HELL}"/>',
             '</pattern>',
             '</defs>',
             f'<rect width="{BREITE}" height="{hoehe}" fill="{SCHWARZ}"/>',
             f'<rect x="{ox}" y="{SCHWARZ_RAND}" width="{spalten * ZELLE}" '
             f'height="{zeilen * ZELLE}" fill="url(#q)"/>']
    teile += [f'<rect x="{ox + (sx + x) * ZELLE}" y="{SCHWARZ_RAND + (RAND + y) * ZELLE}" '
              f'width="{w * ZELLE}" height="{h * ZELLE}" fill="{SCHWARZ}"/>'
              for x, y, w, h in rechtecke(pixel)]
    teile.append(f'<rect x="0" y="{hoehe - 4}" width="{BREITE}" height="4" fill="{ROT}"/>')
    teile.append('</svg>')
    ZIEL.write_text("\n".join(teile) + "\n", encoding="utf-8")
    print(f"{ZIEL} - {BREITE} x {hoehe} Bildpunkte, Feld {spalten} x {zeilen} Zellen, "
          f"Schriftzug {bw} x {bh}, {ZIEL.stat().st_size} Bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
