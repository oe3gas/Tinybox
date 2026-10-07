#!/usr/bin/env python3
"""
geosphere_warnungen.py - Wetterwarnungen der GeoSphere Austria abfragen.

Nutzt die offene Warn API der GeoSphere Austria (Lizenz CC BY 4.0):
  Doku:     https://openapi.hub.geosphere.at/warnapi/v1/
  Endpoint: https://warnungen.zamg.at/wsapp/api/getWarningsForCoords

Gibt nur dann etwas aus, wenn fuer den Standort Warnungen vorliegen
(ausser mit --verbose). Nur Python-Standardbibliothek, keine Pakete noetig.

Beispiele:
  python geosphere_warnungen.py                       # Standard: Hollabrunn
  python geosphere_warnungen.py --lat 48.21 --lon 16.37
  python geosphere_warnungen.py --min-stufe 2         # nur Orange/Rot
  python geosphere_warnungen.py --nur-neue            # nur neue/geaenderte (fuer Aufgabenplanung)
  python geosphere_warnungen.py --details             # inkl. Auswirkungen/Empfehlungen

  python geosphere_warnungen.py --tinybox             # als Bulletin an WARN in den TinyBox-Eingang
                                                      # (nur bei Aenderung; Valid bis Warnungsende)

Exit-Codes: 0 = keine Warnung, 1 = Warnung(en) vorhanden, 2 = Fehler
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

API_URL = "https://warnungen.zamg.at/wsapp/api/getWarningsForCoords"

# Standard-Standort: Hollabrunn (NOe)
DEFAULT_LAT = 48.5627
DEFAULT_LON = 16.0797

WARNTYP = {1: "Sturm", 2: "Regen", 3: "Schnee", 4: "Glatteis",
           5: "Gewitter", 6: "Hitze", 7: "Kaelte"}
WARNSTUFE = {1: "GELB", 2: "ORANGE", 3: "ROT"}

STATE_FILE = Path(__file__).with_name(".geosphere_warnungen_state.json")


def hole_warnungen(lat: float, lon: float, lang: str = "de", timeout: int = 20) -> dict:
    query = urllib.parse.urlencode({"lat": lat, "lon": lon, "lang": lang})
    req = urllib.request.Request(
        f"{API_URL}?{query}",
        headers={"User-Agent": "geosphere_warnungen.py (OE3GAS)",
                 "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout, context=ssl_kontext()) as resp:
        return json.load(resp)


# Zertifikatspruefung bewusst aus (Entscheidung OE3GAS, 03.10.2026): oeffentliche
# Warndaten, nicht sensibel; erspart auf Windows fehlende Stammzertifikate/certifi.
# Wieder einschalten: SSL_PRUEFEN = True
SSL_PRUEFEN = False


def ssl_kontext() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if not SSL_PRUEFEN:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def ts(epoch) -> str:
    """Unix-Zeitstempel (String/Int) -> lokale Zeit."""
    try:
        dt = datetime.fromtimestamp(int(epoch))
        return ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")[dt.weekday()] + dt.strftime(" %d.%m.%Y %H:%M")
    except (TypeError, ValueError):
        return "?"


def formatiere(w: dict, details: bool) -> str:
    raw = w.get("rawinfo") or {}
    typ = WARNTYP.get(w.get("warntypid"), f"Typ {w.get('warntypid')}")
    stufe = WARNSTUFE.get(w.get("warnstufeid"), f"Stufe {w.get('warnstufeid')}")
    zeilen = [
        f"[{stufe}] {typ}: {ts(raw.get('start'))} bis {ts(raw.get('end'))}",
        f"  {w.get('text', '').strip()}",
    ]
    if w.get("updategrund"):
        zeilen.append(f"  Update: {w['updategrund'].strip()}")
    if details:
        for feld, titel in (("meteotext", "Wetterlage"),
                            ("auswirkungen", "Auswirkungen"),
                            ("empfehlungen", "Empfehlungen")):
            if w.get(feld):
                zeilen.append(f"  {titel}:")
                zeilen += [f"    {z}" for z in w[feld].strip().splitlines()]
    return "\n".join(zeilen)


def lade_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def speichere_state(state: dict) -> None:
    try:
        STATE_FILE.write_text(json.dumps(state), encoding="utf-8")
    except OSError as e:
        print(f"Warnung: Statusdatei nicht schreibbar: {e}", file=sys.stderr)


TINYBOX_STATE = Path(__file__).with_name(".geosphere_warnungen_tinybox.json")
ENTWARNUNG_GUELTIG = "3h"


def schreibe_tinybox(ordner: Path, dateiname: str, kopf: dict, text: str) -> Path:
    """Bulletin-Datei fuer den TinyBox-Eingangsordner: erst .tmp, dann umbenennen."""
    ordner.mkdir(parents=True, exist_ok=True)
    inhalt = "".join(f"{k}: {v}\n" for k, v in kopf.items()) + "\n" + text.rstrip() + "\n"
    tmp = ordner / (dateiname + ".tmp")
    tmp.write_text(inhalt, encoding="utf-8")
    ziel = ordner / (dateiname + ".txt")
    os.replace(tmp, ziel)
    return ziel


def protokoll(datei: str | None, text: str) -> None:
    if not datei:
        return
    try:
        Path(datei).parent.mkdir(parents=True, exist_ok=True)
        with open(datei, "a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} geosphere_warnungen: {text}\n")
    except OSError:
        pass


def tinybox_bulletin(warnungen: list[dict], ort: str, args) -> dict | None:
    """Kopf + Text fuer TinyBox, oder None wenn nichts zu tun ist.

    * Warnungen aktiv: Bulletin bis zum Ende der letzten Warnung (Valid)
    * keine Warnung mehr, vorher aber eine gemeldet: kurze Entwarnung
    * sonst / unveraendert: nichts (TinyBox und Funk bleiben ruhig)
    """
    try:
        alt = json.loads(TINYBOX_STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        alt = {}
    ende = 0
    if warnungen:
        ende = max(int((w.get("rawinfo") or {}).get("end") or 0) for w in warnungen)
        minuten = max(int((ende - time.time()) / 60), 30)
        typen = ", ".join(sorted({f"{WARNTYP.get(w.get('warntypid'), '?')} "
                                  f"{WARNSTUFE.get(w.get('warnstufeid'), '?')}" for w in warnungen}))
        betreff = f"Warnung {ort}: {typen}"
        text = "\n\n".join(formatiere(w, args.details) for w in warnungen)
        text += "\n\nQuelle: GeoSphere Austria (CC BY 4.0) - https://warnungen.zamg.at"
        gueltig = f"{minuten}m"
    elif alt.get("aktiv") and time.time() >= alt.get("ende", 0):
        # Warnung ist regulaer abgelaufen: TinyBox hat sie per Valid schon entfernt
        try:
            TINYBOX_STATE.write_text(json.dumps({"aktiv": False}), encoding="utf-8")
        except OSError:
            pass
        return None
    elif alt.get("aktiv"):
        betreff, text, gueltig = (f"Entwarnung {ort}",
                                  f"Fuer {ort} liegen keine Wetterwarnungen mehr vor.\n\n"
                                  "Quelle: GeoSphere Austria (CC BY 4.0)", ENTWARNUNG_GUELTIG)
    else:
        return None
    pruef = hashlib.sha256((betreff + text).encode("utf-8")).hexdigest()
    if pruef == alt.get("pruef"):
        return None                                   # nichts geaendert
    try:
        TINYBOX_STATE.write_text(json.dumps({"aktiv": bool(warnungen), "pruef": pruef,
                                             "ende": ende if warnungen else 0}), encoding="utf-8")
    except OSError as e:
        print(f"Warnung: Statusdatei nicht schreibbar: {e}", file=sys.stderr)
    return {"kopf": {"To": args.ziel, "Subject": betreff[:60],
                     "Replace": "geosphere-warnung", "Valid": gueltig}, "text": text}


def main() -> int:
    ap = argparse.ArgumentParser(description="Wetterwarnungen der GeoSphere Austria abfragen")
    ap.add_argument("--lat", type=float, default=DEFAULT_LAT, help="Breite (WGS84)")
    ap.add_argument("--lon", type=float, default=DEFAULT_LON, help="Laenge (WGS84)")
    ap.add_argument("--lang", choices=["de", "en"], default="de")
    ap.add_argument("--min-stufe", type=int, choices=[1, 2, 3], default=1,
                    help="Mindest-Warnstufe: 1=Gelb, 2=Orange, 3=Rot")
    ap.add_argument("--details", action="store_true", help="Wetterlage, Auswirkungen, Empfehlungen")
    ap.add_argument("--nur-neue", action="store_true",
                    help="nur neue/geaenderte Warnungen seit dem letzten Lauf melden")
    ap.add_argument("--json", action="store_true", help="Rohdaten der Warnungen als JSON ausgeben")
    ap.add_argument("--verbose", action="store_true", help="auch 'keine Warnung' ausgeben")
    ap.add_argument("--tinybox", nargs="?", const=str(Path(__file__).with_name("eingang")),
                    metavar="ORDNER", help="als Bulletin in den TinyBox-Eingangsordner legen "
                    "(Standard: eingang neben diesem Skript)")
    ap.add_argument("--ziel", default="WARN", help="Bulletin-Ziel (Standard WARN)")
    ap.add_argument("--log", metavar="DATEI", help="Fehler zusaetzlich in diese Datei schreiben")
    args = ap.parse_args()

    try:
        data = hole_warnungen(args.lat, args.lon, args.lang)
    except urllib.error.HTTPError as e:
        msg = "kein Gemeindegebiet fuer diese Koordinaten (nur Oesterreich)" if e.code == 404 else str(e)
        print(f"Fehler: {msg}", file=sys.stderr)
        protokoll(args.log, f"Fehler: {msg}")
        return 2
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        print(f"Fehler beim Abruf: {e}", file=sys.stderr)
        protokoll(args.log, f"Fehler beim Abruf: {e}")
        return 2

    props = data.get("properties", {})
    ort = props.get("location", {}).get("properties", {}).get("name", "?")
    warnungen = [w.get("properties", {}) for w in props.get("warnings", [])]
    warnungen = [w for w in warnungen if (w.get("warnstufeid") or 0) >= args.min_stufe]
    warnungen.sort(key=lambda w: int((w.get("rawinfo") or {}).get("start") or 0))

    if args.tinybox:
        b = tinybox_bulletin(warnungen, ort, args)
        if b is None:
            print("TinyBox: keine Aenderung, nichts abgelegt.")
        else:
            try:
                ziel = schreibe_tinybox(Path(args.tinybox), "geosphere_warnung", b["kopf"], b["text"])
            except OSError as e:
                print(f"Fehler: {e}", file=sys.stderr)
                protokoll(args.log, f"Fehler beim Ablegen: {e}")
                return 2
            print(f"Bulletin abgelegt: {ziel} ({b['kopf']['Subject']})")
            protokoll(args.log, f"abgelegt: {b['kopf']['Subject']}")
        return 1 if warnungen else 0

    if args.nur_neue:
        alt = lade_state()
        # Schluessel warnid -> chgid; neue ID oder geaenderte chgid = melden
        neu = {str(w.get("warnid")): w.get("chgid") for w in warnungen}
        speichere_state(neu)
        warnungen = [w for w in warnungen if alt.get(str(w.get("warnid"))) != w.get("chgid")]

    if not warnungen:
        if args.verbose:
            print(f"Keine Warnungen fuer {ort}.")
        return 0

    if args.json:
        print(json.dumps({"ort": ort, "warnungen": warnungen}, ensure_ascii=False, indent=2))
    else:
        print(f"GeoSphere Austria - {len(warnungen)} Warnung(en) fuer {ort}:\n")
        print("\n\n".join(formatiere(w, args.details) for w in warnungen))
        print("\nQuelle: GeoSphere Austria (CC BY 4.0) - https://warnungen.zamg.at")
    return 1


def main_mit_protokoll() -> int:
    """Wie main(), aber unerwartete Fehler landen auch in --log (pyw hat keine Konsole)."""
    try:
        return main()
    except SystemExit:
        raise
    except Exception as e:
        import traceback
        text = f"unerwarteter Fehler: {e!r}\n{traceback.format_exc()}"
        print(text, file=sys.stderr)
        if "--log" in sys.argv:
            i = sys.argv.index("--log")
            if i + 1 < len(sys.argv):
                protokoll(sys.argv[i + 1], text)
        return 2


if __name__ == "__main__":
    sys.exit(main_mit_protokoll())
