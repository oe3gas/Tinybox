#!/usr/bin/env python3
"""Pixelschrift fuer die Teletext-Ansicht des Listeners erzeugen.

    py -3 brocast/tools/build_teletext_font.py

Die Glyphen entstehen durch Rastern von DejaVu Sans Mono Bold in reinem Schwarz-
Weiss (FreeType-Hinting, keine Graustufen) bei 10 px. Das ergibt dieselbe Koernung
wie die Zeichensaetze der Teletext-Decoder: Grossbuchstabe 7 Pixel, x-Hoehe 5 Pixel,
Zelle 7 Pixel breit. Die fette Schnittlage wird genommen, weil die Striche dann
2 Pixel breit sind - das ist der grobe Teletext-Eindruck; die magere Schnittlage
wirkt bei dieser Groesse duenn und zerfranst. Jedes gesetzte Pixel wird zu einem
Quadrat im Umriss (gleiche Pixel vorher zu moeglichst grossen Rechtecken
zusammengefasst), daher bleibt die Schrift in jeder Groesse pixelig und scharf.

Raster: 1 Pixel = 64 Einheiten, em = 1024 Einheiten = 16 Pixel. Bei font-size 32 px
ist ein Schriftpixel also genau 2 Bildschirmpixel - deshalb im CSS nur geradzahlige
Groessen verwenden (16, 24, 32 px), sonst verwischen die Kanten.

Das Ergebnis liegt im Repo (brocast/brocast/web/teletext.woff); dieses Skript muss
nur laufen, wenn sich der Zeichenvorrat oder das Raster aendert. Es braucht
fontTools und Pillow (pip install fonttools pillow) und DejaVu Sans Mono.

Lizenz: DejaVu steht unter der Bitstream-Vera-Lizenz - Aendern und Weitergeben
erlaubt, der Name muss ein anderer sein. Die Schrift heisst daher "brocast
Teletext"; der Hinweis steht auch im Font selbst (Name-Tabelle).
"""

from __future__ import annotations

import sys
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from PIL import Image, ImageDraw, ImageFont

QUELLE = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf")
ZIEL = Path(__file__).resolve().parent.parent / "brocast" / "web" / "teletext.woff"

PPEM = 10                 # Rastergroesse: Grossbuchstabe 7 Pixel, x-Hoehe 5, Strich 2
ZELLE = 7                 # Zellenbreite in Pixeln (Buchstaben 5 breit, die breitesten 6)
                          # -> 1 ch = 7/16 em, bei font-size 32 px also 14 px
PX = 64                   # Einheiten je Pixel
EM_PX = 16                # Pixel je em -> upem 1024
ASC_PX, DESC_PX = 12, 4   # Zeilenkasten der Schrift (CSS setzt den Abstand selbst)

# Zeichenvorrat: ASCII, Latin-1 (Umlaute, Akzente) und die Sonderzeichen, die in
# brocast-Seiten und in der Bedienung vorkommen. Fehlt ein Zeichen (z. B. Emoji),
# faellt der Browser auf die normale Monospace zurueck.
ZEICHEN = (
    [chr(c) for c in range(0x20, 0x7F)]
    + [chr(c) for c in range(0xA0, 0x100)]
    + list("€–—‘’‚“”„•…‹›′″≈≠≤≥±×÷←↑→↓◀▶▲▼■□●○★☆✓✗⌀Ω")
)


def raster(ch: str, font: ImageFont.FreeTypeFont, asc: int, desc: int) -> set[tuple[int, int]]:
    """Gesetzte Pixel eines Zeichens, (x, y) mit y = 0 an der Oberkante (Grundlinie bei asc)."""
    breite = max(1, int(round(font.getlength(ch)))) + 2
    img = Image.new("1", (breite, asc + desc), 0)
    d = ImageDraw.Draw(img)
    d.fontmode = "1"                                  # bilevel: kein Antialiasing
    d.text((0, 0), ch, font=font, fill=1, anchor="la")
    px = img.load()
    return {(x, y) for y in range(img.height) for x in range(img.width) if px[x, y]}


def rechtecke(pixel: set[tuple[int, int]]) -> list[tuple[int, int, int, int]]:
    """Gesetzte Pixel zu moeglichst grossen Rechtecken (x, y, w, h) zusammenfassen."""
    offen = set(pixel)
    out = []
    while offen:
        x, y = min(offen, key=lambda p: (p[1], p[0]))
        w = 1
        while (x + w, y) in offen:
            w += 1
        h = 1
        while all((x + i, y + h) in offen for i in range(w)):
            h += 1
        for j in range(h):
            for i in range(w):
                offen.discard((x + i, y + j))
        out.append((x, y, w, h))
    return out


def glyph(pixel: set[tuple[int, int]], asc: int):
    """Umriss aus Rechtecken; y wird an der Grundlinie gespiegelt (Schriftkoordinaten)."""
    pen = TTGlyphPen(None)
    for x, y, w, h in rechtecke(pixel):
        x0, x1 = x * PX, (x + w) * PX
        y1, y0 = (asc - y) * PX, (asc - y - h) * PX     # oben/unten ueber der Grundlinie
        pen.moveTo((x0, y0))                            # im Uhrzeigersinn = gefuellt
        pen.lineTo((x0, y1))
        pen.lineTo((x1, y1))
        pen.lineTo((x1, y0))
        pen.closePath()
    return pen.glyph()


def main() -> int:
    if not QUELLE.exists():
        print(f"Quellschrift fehlt: {QUELLE}", file=sys.stderr)
        return 2
    font = ImageFont.truetype(str(QUELLE), PPEM)
    asc, desc = font.getmetrics()
    advance = ZELLE
    print(f"Raster {advance} x {asc + desc} Pixel (Grundlinie bei {asc})")

    glyphen = {".notdef": TTGlyphPen(None).glyph()}
    vorschub = {".notdef": (advance * PX, 0)}
    cmap = {}
    breit = []
    for ch in ZEICHEN:
        name = f"uni{ord(ch):04X}"
        pixel = raster(ch, font, asc, desc)
        if pixel and max(x for x, _ in pixel) >= advance:
            breit.append(ch)                            # passt nicht in die Zelle: beschneiden
            pixel = {(x, y) for x, y in pixel if x < advance}
        glyphen[name] = glyph(pixel, asc)
        links = min((x for x, _ in pixel), default=0) * PX
        vorschub[name] = (advance * PX, links)
        cmap[ord(ch)] = name
    if breit:
        print("breiter als die Zelle, beschnitten:", "".join(breit))

    fb = FontBuilder(EM_PX * PX, isTTF=True)
    fb.setupGlyphOrder(list(glyphen))
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphen)
    fb.setupHorizontalMetrics(vorschub)
    fb.setupHorizontalHeader(ascent=ASC_PX * PX, descent=-DESC_PX * PX)
    fb.setupNameTable({
        "familyName": "brocast Teletext", "styleName": "Regular",
        "uniqueFontIdentifier": "brocast Teletext 1.0",
        "fullName": "brocast Teletext", "psName": "brocastTeletext-Regular",
        "version": "Version 1.0",
        "copyright": "Pixelraster aus DejaVu Sans Mono (Bitstream-Vera-Lizenz), "
                     "erzeugt mit brocast/tools/build_teletext_font.py",
        "licenseDescription": "Abgeleitet von DejaVu Sans Mono, Bitstream-Vera-Lizenz.",
    })
    fb.setupOS2(sTypoAscender=ASC_PX * PX, sTypoDescender=-DESC_PX * PX,
                usWinAscent=ASC_PX * PX, usWinDescent=DESC_PX * PX,
                sxHeight=5 * PX, sCapHeight=7 * PX,
                panose=dict(bFamilyType=2, bSerifStyle=11, bWeight=5, bProportion=9,
                            bContrast=2, bStrokeVariation=2, bArmStyle=2, bLetterForm=2,
                            bMidline=2, bXHeight=4))                 # 9 = Monospace
    fb.setupPost(isFixedPitch=1)
    # feste Zeitstempel: derselbe Lauf ergibt dieselbe Datei (sonst rauscht der Diff)
    fb.font["head"].created = fb.font["head"].modified = 3_600_000_000
    fb.font.flavor = "woff"
    ZIEL.parent.mkdir(parents=True, exist_ok=True)
    fb.save(str(ZIEL))
    print(f"{ZIEL} - {len(cmap)} Zeichen, {ZIEL.stat().st_size} Bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
