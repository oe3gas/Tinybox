"""Bildkonverter: aus einem Bild eine brocast-Bildseite machen (nur Station).

    py -3 -m brocast bild foto.jpg --titel "Shack von OE3GAS"

Das Bild wird zu Teletext-Mosaik (brocast/mosaic.py): 2 x 3 Felder je Zeichen,
also wie ASCII-Art, nur sechsmal feiner. Ohne weitere Angabe zeigt der Befehl
die Vorschau im Fenster und was die Seite auf Funk kosten wuerde; erst
`--senden` oder `--tinybox` gibt sie weiter.

Nur im Betriebsmodus **station** (brocastd.conf `mode = station`): ein Listener
sendet nicht, dort waere der Befehl sinnlos.

    --spalten 40     Breite in Zeichen (hoechstens 40, das ist die Bildschirmbreite)
    --invert         helles Motiv auf dunklem Grund
    --hart           harte Schwelle statt Fehlerstreuung (Zeichnungen, Logos)
    --titel TEXT     Seitentitel (sonst der Dateiname)
    --text TEXT      Bildunterschrift
    --rubrik NAME    Rubrik der Seite (Standard: bild)
    --gueltig 7d     Gueltigkeit (90m, 6h, 7d; Standard 7d)
    --senden         Seite an das laufende brocastd geben (Ingest-API, 127.0.0.1)
    --tinybox ORDNER als Bulletin in den TinyBox-Eingang legen (mit Kopfzeile Brocast:)
    --ziel ALL       Bulletin-Ziel fuer --tinybox (Standard ALL)
    --konfig DATEI   brocastd.conf (Standard: brocastd.conf im aktuellen Ordner)
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from . import config, mosaic

MAX_SPALTEN = mosaic.SPALTEN_MAX
ZEILEN_JE_BLOCK = 3


def gueltig_minuten(text: str) -> int:
    """'7d', '6h', '90m' oder Minuten als Zahl -> Minuten."""
    text = text.strip().lower()
    faktor = {"m": 1, "h": 60, "d": 1440}.get(text[-1:])
    zahl = text[:-1] if faktor else text
    if not zahl.isdigit():
        raise ValueError(f"Gueltigkeit {text!r}: z. B. 90m, 6h, 7d")
    return max(1, int(zahl) * (faktor or 1))


def schluessel(datei: Path) -> str:
    """Dateiname -> Schluessel der Seite (gleiches Bild = gleiche Seite, neue Revision)."""
    name = re.sub(r"[^a-z0-9]+", "-", datei.stem.lower()).strip("-")
    return name or "bild"


def seite(zeilen: list[str], titel: str, rubrik: str, gueltig: int,
          text: str = "") -> dict[str, Any]:
    """Die brocast-Seite: Mosaikbloecke, davor der Titel, danach die Bildunterschrift."""
    blk: list[dict[str, Any]] = mosaic.bloecke(zeilen, ZEILEN_JE_BLOCK)
    if text:
        blk.append({"k": "para", "x": text})
    return {"typ": "text", "cat": [rubrik], "exp": gueltig, "ti": titel[:40], "blk": blk}


def bulletin_text(zeilen: list[str], titel: str, text: str) -> str:
    """Der Text fuer die Mailbox: das Bild als Mosaik, damit es auch dort etwas zu
    sehen gibt (im Terminal ohne passende Schrift bleiben Kaestchen)."""
    teile = [titel, "", *zeilen, ""]
    if text:
        teile += [text, ""]
    teile.append(f"Bild {len(zeilen[0]) if zeilen else 0} x {len(zeilen)} Zeichen, "
                 "am besten im brocast-Listener ansehen.")
    return "\n".join(teile)


def sende(cfg: config.Config, key: str, page: dict[str, Any]) -> dict[str, Any]:
    """PUT an die Ingest-API des laufenden brocastd (nur lokal)."""
    url = (f"http://{cfg.station.ingest_host}:{cfg.station.ingest_port}"
           f"/api/v1/pages/bild/{key}")
    kopf = {"Content-Type": "application/json", "User-Agent": "brocast bild"}
    if cfg.station.token:
        kopf["X-Brocast-Token"] = cfg.station.token
    req = urllib.request.Request(url, data=json.dumps(page, ensure_ascii=False).encode("utf-8"),
                                 headers=kopf, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        try:
            grund = json.load(exc).get("error", "")
        except ValueError:
            grund = ""
        raise ValueError(f"brocastd lehnt die Seite ab (HTTP {exc.code}): {grund}") from None
    except urllib.error.URLError as exc:
        raise OSError(f"brocastd laeuft nicht oder antwortet nicht ({url}): {exc.reason}") from None


def in_tinybox(ordner: Path, key: str, kopf: dict[str, str], text: str) -> Path:
    """Bulletin-Datei fuer den TinyBox-Eingang: erst .tmp, dann umbenennen."""
    ordner.mkdir(parents=True, exist_ok=True)
    inhalt = "".join(f"{k}: {v}\n" for k, v in kopf.items()) + "\n" + text.rstrip() + "\n"
    tmp = ordner / f"brocast_bild_{key}.tmp"
    tmp.write_text(inhalt, encoding="utf-8")
    ziel = ordner / f"brocast_bild_{key}.txt"
    os.replace(tmp, ziel)
    return ziel


def main(argv: list[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="brocast bild", description="Bild als Teletext-Mosaik")
    ap.add_argument("datei", help="Bilddatei (jpg, png, gif ...)")
    ap.add_argument("--spalten", type=int, default=MAX_SPALTEN, help=f"Breite in Zeichen (max {MAX_SPALTEN})")
    ap.add_argument("--invert", action="store_true", help="helles Motiv auf dunklem Grund")
    ap.add_argument("--hart", action="store_true", help="harte Schwelle statt Fehlerstreuung")
    ap.add_argument("--titel", default="", help="Seitentitel (Standard: Dateiname)")
    ap.add_argument("--text", default="", help="Bildunterschrift")
    ap.add_argument("--rubrik", default="bild", help="Rubrik der Seite (Standard bild)")
    ap.add_argument("--gueltig", default="7d", help="Gueltigkeit, z. B. 90m, 6h, 7d")
    ap.add_argument("--senden", action="store_true", help="Seite an das laufende brocastd geben")
    ap.add_argument("--tinybox", metavar="ORDNER", help="als Bulletin in den TinyBox-Eingang legen")
    ap.add_argument("--ziel", default="ALL", help="Bulletin-Ziel fuer --tinybox (Standard ALL)")
    ap.add_argument("--konfig", default="brocastd.conf", help="brocastd.conf")
    args = ap.parse_args(argv)

    cfg = config.load(args.konfig)                    # ConfigError faengt __main__ ab
    if not cfg.is_station:
        print(f"Der Bildkonverter gehoert zur Station: {args.konfig} hat mode = {cfg.mode}. "
              "Auf einem Listener gibt es nichts zu senden.")
        return 2

    datei = Path(args.datei)
    try:
        from PIL import Image
    except ImportError:
        print("Fuer den Bildkonverter fehlt Pillow:  py -3 -m pip install pillow")
        return 2
    with Image.open(datei) as bild:
        zeilen = mosaic.aus_bild(bild, args.spalten, invertieren=args.invert, raster=not args.hart)
        gross = bild.size
    titel = args.titel or datei.stem
    gueltig = gueltig_minuten(args.gueltig)
    page = seite(zeilen, titel, args.rubrik, gueltig, args.text)

    print("\n".join(zeilen))
    print()
    bytes_etwa = mosaic.bytes_geschaetzt(zeilen)
    frames = max(1, -(-bytes_etwa // 200))            # ~200 Byte Nutzlast je Frame
    print(f"{datei.name} {gross[0]}x{gross[1]} -> {len(zeilen[0]) if zeilen else 0} x {len(zeilen)} "
          f"Zeichen, {len(page['blk'])} Bloecke, gepackt etwa {bytes_etwa} Bytes "
          f"(~{frames} Frames, {frames * 2.2:.0f} s auf 1200 Bd)")

    if args.senden:
        res = sende(cfg, schluessel(datei), page)
        print(f"an brocastd: Seite {res.get('id')} rev {res.get('rev')}, "
              f"{sum(res.get('bytes') or [])} Bytes, {res.get('subpages')} Teile, "
              f"ca. {res.get('airtime_s')} s")
    if args.tinybox:
        kopf = {"To": args.ziel, "Subject": titel[:60],
                "Replace": f"brocast-bild-{schluessel(datei)}",
                "Valid": args.gueltig,
                "Brocast": json.dumps(page, ensure_ascii=False, separators=(",", ":"))}
        ziel = in_tinybox(Path(args.tinybox), schluessel(datei), kopf,
                          bulletin_text(zeilen, titel, args.text))
        print(f"Bulletin abgelegt: {ziel}")
    if not args.senden and not args.tinybox:
        print("Nur Vorschau. Senden: --senden (an brocastd) oder --tinybox ORDNER (als Bulletin).")
    return 0
