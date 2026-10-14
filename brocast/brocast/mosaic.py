"""Bilder als Teletext-Mosaik (Sextanten) – die Vorlage für Bildseiten.

Ein Zeichen der Teletext-Schrift ist 7 x 12 Bildpunkte groß und wird in
2 Spalten x 3 Zeilen geteilt; jedes der sechs Felder ist an oder aus. Für alle
64 Kombinationen gibt es ein Unicode-Zeichen: die „Block Sextants“ U+1FB00…
U+1FB3B und dazu Leerzeichen, Halb- und Vollblock. Ein Bild ist damit ein ganz
gewöhnlicher Text – wie ASCII-Art, nur sechsmal feiner – und braucht weder eine
neue Blockart noch ein neues Dictionary. Der Listener zeichnet die Zeichen in
seiner Pixelschrift lückenlos aneinander, ein Terminal zeigt sie als Mosaik oder
(ohne passende Schrift) als Kästchen.

Bitmaske eines Zeichens:

    1   2        1 = oben links     8 = Mitte rechts
    4   8        2 = oben rechts   16 = unten links
   16  32        4 = Mitte links   32 = unten rechts

Über Funk kosten die Sextanten je Zeichen vier Bytes (UTF-8), die ersten drei
sind aber bei allen gleich – die Kompression mit dem Preset-Wörterbuch (PLANUNG
6e) macht daraus rund ein Byte je Zeichen. Rechnen lässt sich das mit
`bytes_geschaetzt()`; der Konverter (`py -3 -m brocast bild`) zeigt es an.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:                                  # Pillow ist nur für den Konverter nötig
    from PIL.Image import Image

# Index = Bitmaske der sechs Felder. Erzeugt aus den Unicode-Namen
# ("BLOCK SEXTANT-135" = Felder 1, 3, 5); Gegenprobe in tests/test_mosaic.py.
TABELLE = (" \U0001FB00\U0001FB01\U0001FB02\U0001FB03\U0001FB04\U0001FB05\U0001FB06"
           "\U0001FB07\U0001FB08\U0001FB09\U0001FB0A\U0001FB0B\U0001FB0C\U0001FB0D\U0001FB0E"
           "\U0001FB0F\U0001FB10\U0001FB11\U0001FB12\U0001FB13▌\U0001FB14\U0001FB15"
           "\U0001FB16\U0001FB17\U0001FB18\U0001FB19\U0001FB1A\U0001FB1B\U0001FB1C\U0001FB1D"
           "\U0001FB1E\U0001FB1F\U0001FB20\U0001FB21\U0001FB22\U0001FB23\U0001FB24\U0001FB25"
           "\U0001FB26\U0001FB27▐\U0001FB28\U0001FB29\U0001FB2A\U0001FB2B\U0001FB2C"
           "\U0001FB2D\U0001FB2E\U0001FB2F\U0001FB30\U0001FB31\U0001FB32\U0001FB33\U0001FB34"
           "\U0001FB35\U0001FB36\U0001FB37\U0001FB38\U0001FB39\U0001FB3A\U0001FB3B█")
MOSAIK_ZEICHEN = frozenset(TABELLE)

FELD_BITS = (1, 2, 4, 8, 16, 32)       # (Spalte, Zeile): (0,0) (1,0) (0,1) (1,1) (0,2) (1,2)
ZEICHEN_BREITE = 7                     # Bildpunkte je Zeichen in der Teletext-Schrift
ZEICHEN_HOEHE = 12                     # Bildpunkte je Zeile (= line-height der Mosaikblöcke)
SPALTEN_MAX = 40                       # Zeichen je Zeile im Teletext-Bildschirm


def ist_mosaik(text: str) -> bool:
    """Besteht der Text nur aus Mosaikzeichen (und Zeilenumbrüchen)? So erkennt der
    Listener einen Bildblock, ohne dass die Seite es eigens sagen muss."""
    rest = set(text) - MOSAIK_ZEICHEN - {"\n"}
    return not rest and any(ch in MOSAIK_ZEICHEN and ch != " " for ch in text)


def zeilen_fuer(spalten: int, breite_px: int, hoehe_px: int) -> int:
    """Zeilenzahl, bei der das Mosaik dieselben Seitenverhältnisse hat wie das Bild.

    Ein Zeichen ist 7 x 12 Bildpunkte, ein Feld also 3,5 x 4 – die Felder sind
    schmaler als hoch, das muss beim Umrechnen hinein."""
    zeilen = round(spalten * ZEICHEN_BREITE * hoehe_px / (ZEICHEN_HOEHE * max(breite_px, 1)))
    return max(1, zeilen)


def aus_punkten(punkte, spalten: int, zeilen: int) -> list[str]:
    """Punktraster (Funktion (x, y) -> bool, 2*spalten x 3*zeilen) -> Mosaikzeilen."""
    out = []
    for zeile in range(zeilen):
        text = []
        for spalte in range(spalten):
            bits = 0
            for i, (dx, dy) in enumerate(((0, 0), (1, 0), (0, 1), (1, 1), (0, 2), (1, 2))):
                if punkte(spalte * 2 + dx, zeile * 3 + dy):
                    bits |= FELD_BITS[i]
            text.append(TABELLE[bits])
        out.append("".join(text).rstrip())
    return out


def aus_bild(bild: "Image", spalten: int = SPALTEN_MAX, invertieren: bool = False,
             raster: bool = True, schwelle: int = 128) -> list[str]:
    """Bild -> Mosaikzeilen. raster=True streut den Fehler (Floyd-Steinberg), sonst
    harte Schwelle. invertieren=True für helle Motive auf dunklem Grund."""
    from PIL import Image as PILImage, ImageFilter, ImageOps

    spalten = max(1, min(spalten, SPALTEN_MAX))
    zeilen = zeilen_fuer(spalten, bild.width, bild.height)
    grau = ImageOps.autocontrast(bild.convert("L"), cutoff=2)      # Ausreisser nicht mitrechnen
    if invertieren:
        grau = ImageOps.invert(grau)
    klein = grau.resize((spalten * 2, zeilen * 3), PILImage.LANCZOS)
    # bei so wenig Punkten verschwinden Kanten im Mittelwert - vor dem Schwellwert schaerfen
    klein = klein.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=2))
    sw = klein.convert("1") if raster else klein.point(lambda v: 255 if v >= schwelle else 0, "1")
    px = sw.load()
    return aus_punkten(lambda x, y: bool(px[x, y]), spalten, zeilen)


def bloecke(zeilen: list[str], zeilen_je_block: int = 3) -> list[dict[str, Any]]:
    """Mosaikzeilen -> Blöcke `pre` für eine brocast-Seite.

    Mehrere kleine Blöcke statt eines großen, damit auch im alten Frame-Format 1
    (eine Seite je Frame, der Splitter kann einen Block nicht teilen) jeder Block
    in einen Frame passt. Der Listener setzt aufeinanderfolgende Mosaikblöcke
    wieder lückenlos zusammen."""
    return [{"k": "pre", "x": "\n".join(zeilen[i:i + zeilen_je_block])}
            for i in range(0, len(zeilen), zeilen_je_block)]


def bytes_geschaetzt(zeilen: list[str]) -> int:
    """Grobe Zahl der Bytes auf Funk (UTF-8, gepackt mit dem Preset-Wörterbuch).
    Die genaue Zahl meldet brocastd beim Einstellen der Seite."""
    from .zdict import load
    roh = "\n".join(zeilen).encode("utf-8")
    zd = load()
    gepackt = zd.compress(roh) if zd.ok else None
    return len(gepackt) if gepackt else len(roh)
