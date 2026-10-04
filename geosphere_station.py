#!/usr/bin/env python3
"""
geosphere_station.py - Aktuelle Messwerte einer GeoSphere-Austria-Wetterstation (TAWES).

Standard: Station 11334 SCHOENGRABERN (bei Hollabrunn), 253 m, 48.6033 N / 16.0617 E.
Datenquelle: GeoSphere Austria Data Hub, Dataset "tawes-v1-10min" (CC BY 4.0)
  Doku:   https://dataset.api.hub.geosphere.at/v1/docs
  Aktuell:    /v1/station/current/tawes-v1-10min
  Verlauf:    /v1/station/historical/tawes-v1-10min

Nur Python-Standardbibliothek, kein API-Key noetig.

Beispiele:
  python geosphere_station.py                  # aktuelle Werte + 24-h-Zusammenfassung
  python geosphere_station.py --kurz           # nur aktuelle Werte
  python geosphere_station.py --stunden 6      # Zusammenfassung ueber 6 h
  python geosphere_station.py --json           # Rohwerte als JSON
  python geosphere_station.py --station 11022  # andere Station (hier: Retz)
  python geosphere_station.py --suche laa      # Station-ID suchen
  python geosphere_station.py --tinybox        # als Bulletin an WX in den TinyBox-Eingang
                                               # (Replace: geosphere-wetter-<ID>, Valid: 2h),
                                               # dazu die Wetterseite fuer brocast als Kopfzeile
                                               # "Brocast:" (TinyBox reicht sie an brocastd weiter)
  python geosphere_station.py --brocast        # nur zum Testen ohne TinyBox: Wetterseite direkt
                                               # an brocastd (Seite geosphere/wx-<ID>)

Exit-Codes: 0 = ok, 2 = Fehler
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = "https://dataset.api.hub.geosphere.at/v1/station"
DATASET = "tawes-v1-10min"
DEFAULT_STATION = "11334"  # SCHOENGRABERN

# Parameter fuer die Anzeige (Station 11334 hat laut Metadaten keine Sonnenschein-/Strahlungsmessung)
PARAMS = ["TL", "TP", "RF", "P", "PRED", "DD", "FF", "FFX", "RR"]

WINDRICHTUNG = ["N", "NNO", "NO", "ONO", "O", "OSO", "SO", "SSO",
                "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


# Zertifikatspruefung bewusst aus (Entscheidung OE3GAS, 03.10.2026): oeffentliche
# Wetterdaten, nicht sensibel; erspart auf Windows fehlende Stammzertifikate/certifi.
# Wieder einschalten: SSL_PRUEFEN = True
SSL_PRUEFEN = False


def ssl_kontext() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if not SSL_PRUEFEN:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def api_get(pfad: str, params: dict, timeout: int = 20) -> dict:
    url = f"{BASE}/{pfad}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "geosphere_station.py (OE3GAS)",
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=ssl_kontext()) as resp:
        return json.load(resp)


def lokalzeit(iso: str) -> str:
    dt = datetime.fromisoformat(iso).astimezone()
    return dt.strftime("%d.%m.%Y %H:%M")


def richtung(grad):
    if grad is None:
        return "-"
    return WINDRICHTUNG[int((grad % 360) / 22.5 + 0.5) % 16]


def beaufort(ms):
    grenzen = [0.3, 1.6, 3.4, 5.5, 8.0, 10.8, 13.9, 17.2, 20.8, 24.5, 28.5, 32.7]
    return next((i for i, g in enumerate(grenzen) if ms < g), 12)


def f(wert, fmt="{:.1f}", einheit=""):
    return "-" if wert is None else fmt.format(wert) + einheit


def metadaten() -> dict:
    return api_get(f"current/{DATASET}/metadata", {})


def station_info(station_id: str):
    for s in metadaten().get("stations", []):
        if s["id"] == station_id:
            return s
    return None


def aktuelle_werte(station_id: str):
    d = api_get(f"current/{DATASET}", {"station_ids": station_id, "parameters": ",".join(PARAMS)})
    feat = d["features"][0]["properties"]["parameters"]
    werte = {k: (v["data"][-1] if v.get("data") else None) for k, v in feat.items()}
    return d["timestamps"][-1], werte


def verlauf(station_id: str, stunden: int):
    ende = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    start = ende - timedelta(hours=stunden)
    d = api_get(f"historical/{DATASET}", {
        "station_ids": station_id,
        "parameters": "TL,RR,FFX,PRED",
        "start": start.strftime("%Y-%m-%dT%H:%M"),
        "end": ende.strftime("%Y-%m-%dT%H:%M"),
    })
    return d["timestamps"], {k: v["data"] for k, v in d["features"][0]["properties"]["parameters"].items()}


def zusammenfassung(ts, reihen, stunden):
    def gueltig(key):
        return [x for x in reihen.get(key, []) if x is not None]

    tl, rr, ffx = gueltig("TL"), gueltig("RR"), gueltig("FFX")
    zeilen = [f"Letzte {stunden} h:"]
    if tl:
        zeilen.append(f"  Temperatur     min {min(tl):.1f} / max {max(tl):.1f} °C")
    if rr:
        zeilen.append(f"  Niederschlag   {sum(rr):.1f} mm")
    if ffx:
        m = max(ffx)
        zeilen.append(f"  Max. Boe       {m:.1f} m/s ({m * 3.6:.0f} km/h, Bft {beaufort(m)})")

    # Drucktendenz ueber 3 h (18 x 10 min)
    pred = reihen.get("PRED", [])
    if len(pred) > 18 and pred[-1] is not None and pred[-19] is not None:
        diff = pred[-1] - pred[-19]
        trend = "steigend" if diff > 0.5 else "fallend" if diff < -0.5 else "gleichbleibend"
        zeilen.append(f"  Drucktendenz   {diff:+.1f} hPa / 3 h ({trend})")
    return "\n".join(zeilen)


def abrufen(station: str, stunden: int, kurz: bool) -> dict:
    """Alle Daten einmal holen: aktuelle Werte, Stationsinfo, optional der Verlauf."""
    zeit, w = aktuelle_werte(station)
    d = {"station": station, "zeit": zeit, "w": w, "info": station_info(station),
         "ts": [], "reihen": {}}
    if not kurz:
        d["ts"], d["reihen"] = verlauf(station, stunden)
    return d


def stationsname(d: dict) -> str:
    return d["info"]["name"].title() if d["info"] else d["station"]


def bericht(d: dict, stunden: int) -> tuple[str, str, list[str]]:
    """-> (Stationsname, Messzeit lokal, Textzeilen) fuer Bildschirm und TinyBox."""
    station, zeit, w, info = d["station"], d["zeit"], d["w"], d["info"]
    name = stationsname(d)
    hoehe = f" ({info['altitude']:.0f} m)" if info else ""
    zeilen = [f"GeoSphere Austria - Station {station} {name}{hoehe}",
              f"Messzeit: {lokalzeit(zeit)} (10-min-Werte)", "",
              f"  Temperatur     {f(w.get('TL'), einheit=' °C')}",
              f"  Taupunkt       {f(w.get('TP'), einheit=' °C')}",
              f"  Rel. Feuchte   {f(w.get('RF'), '{:.0f}', ' %')}",
              f"  Luftdruck QFF  {f(w.get('PRED'), einheit=' hPa')}"
              f"   (Stationsdruck {f(w.get('P'), einheit=' hPa')})"]
    ff, ffx, dd = w.get("FF"), w.get("FFX"), w.get("DD")
    if ff is not None:
        zeilen.append(f"  Wind           {richtung(dd)} ({f(dd, '{:.0f}', '°')}) {ff:.1f} m/s "
                      f"= {ff * 3.6:.0f} km/h, Bft {beaufort(ff)}")
    if ffx is not None:
        zeilen.append(f"  Windspitze     {ffx:.1f} m/s = {ffx * 3.6:.0f} km/h")
    zeilen.append(f"  Niederschlag   {f(w.get('RR'), einheit=' mm')} (letzte 10 min)")
    if d["ts"]:
        zeilen += ["", *zusammenfassung(d["ts"], d["reihen"], stunden).split("\n")]
    zeilen += ["", "Quelle: GeoSphere Austria, TAWES (CC BY 4.0)"]
    return name, lokalzeit(zeit), zeilen


# ---------------------------------------------------------------------------
# brocast: Wetterseite (typ wx) fuer die Ingest-API von brocastd
# ---------------------------------------------------------------------------

SERIE_SCHRITTE = 12          # Zeitreihe: ein Wert je 12 x 10 min = 2 h


def verdichten(reihe: list, schritte: int) -> list:
    """10-min-Reihe -> jeder n-te Wert, vom neuesten Wert rueckwaerts gezaehlt.

    Fehlt ein Wert, wird der naechste gueltige Wert desselben Abschnitts genommen;
    ist der ganze Abschnitt leer, steht None (der Listener laesst die Stelle aus)."""
    out = []
    for ende in range(len(reihe), 0, -schritte):
        fenster = reihe[max(0, ende - schritte):ende]
        gueltig = [x for x in reversed(fenster) if x is not None]
        out.append(gueltig[0] if gueltig else None)
    return list(reversed(out))


def brocast_seite(d: dict, stunden: int, gueltig_min: int) -> dict:
    """Seite fuer brocastd: Messwerte in dat (Dictionary wx, ab Version 2),
    dazu der Temperaturverlauf als Zeitreihe (alle 2 h ein Wert, 0,1 °C).

    Ziel ist ein einziger Frame (max. 240 Bytes): 13 Werte statt 25 sparen rund
    30 Bytes; wird es im Sommer (Werte ab 25,6 °C brauchen 3 Bytes) doch zu lang,
    teilt brocastd die Seite automatisch in zwei Unterseiten."""
    w, info = d["w"], d["info"]

    def r1(x):
        return None if x is None else round(x, 1)

    dat = {"temp": r1(w.get("TL")), "dew": r1(w.get("TP")),
           "hum": None if w.get("RF") is None else round(w["RF"]),
           "qff": r1(w.get("PRED")), "qfe": r1(w.get("P")),
           "wdir": None if w.get("DD") is None else round(w["DD"]) % 360,
           "wspd": r1(w.get("FF")), "gust10": r1(w.get("FFX")), "r10m": r1(w.get("RR"))}

    blk = []
    reihen = d["reihen"]
    if d["ts"]:
        # tmin/tmax/gmax/r24h sind im Dictionary als 24-h-Werte definiert
        def letzte_24h(key):
            return [x for x in reihen.get(key, [])[-144:] if x is not None]
        if stunden >= 24:
            tl, rr, ffx = letzte_24h("TL"), letzte_24h("RR"), letzte_24h("FFX")
            if tl:
                dat["tmin"], dat["tmax"] = r1(min(tl)), r1(max(tl))
            if rr:
                dat["r24h"] = r1(sum(rr))
            if ffx:
                dat["gmax"] = r1(max(ffx))
        pred = reihen.get("PRED", [])
        if len(pred) > 18 and pred[-1] is not None and pred[-19] is not None:
            dat["ptnd"] = r1(pred[-1] - pred[-19])
        werte = [None if x is None else round(x * 10)
                 for x in verdichten(reihen.get("TL", []), SERIE_SCHRITTE)]
        if sum(x is not None for x in werte) >= 2:
            blk.append({"k": "series", "n": f"Temperatur {stunden} h", "u": "Cel",
                        "sc": -1, "dt": SERIE_SCHRITTE * 600, "v": werte})
    dat = {k: v for k, v in dat.items() if v is not None}

    seite = {"typ": "wx", "cat": ["wx"], "exp": gueltig_min,
             "ti": f"Wetter {stationsname(d)} {lokalzeit(d['zeit'])[-5:]}"[:40],
             "src": "GeoSphere Austria, TAWES (CC BY 4.0)",
             "dat": dat}
    if info and info.get("lat") is not None and info.get("lon") is not None:
        seite["pos"] = [round(info["lat"], 4), round(info["lon"], 4)]
        if info.get("altitude") is not None:
            seite["pos"].append(round(info["altitude"]))
    if blk:
        seite["blk"] = blk
    return seite


def sende_brocast(url: str, seite: dict, token: str = "") -> dict:
    """PUT an die Ingest-API von brocastd (nur lokal, 127.0.0.1)."""
    kopf = {"Content-Type": "application/json", "User-Agent": "geosphere_station.py"}
    if token:
        kopf["X-Brocast-Token"] = token
    req = urllib.request.Request(url, data=json.dumps(seite, ensure_ascii=False).encode("utf-8"),
                                 headers=kopf, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        try:
            text = json.load(e).get("error", "")
        except ValueError:
            text = ""
        raise ValueError(f"brocastd lehnt die Seite ab (HTTP {e.code}): {text}") from None
    except urllib.error.URLError as e:
        raise OSError(f"brocastd nicht erreichbar ({url}): {e.reason}") from None


def gueltig_minuten(text: str) -> int:
    """'2h', '90m', '1d' oder Minuten als Zahl -> Minuten."""
    text = text.strip().lower()
    faktor = {"m": 1, "h": 60, "d": 1440}.get(text[-1:], None)
    return int(text[:-1]) * faktor if faktor else int(text)


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
    """Fehler/Ereignisse auch in eine Datei schreiben (fuer Laeufe ohne Konsole)."""
    if not datei:
        return
    try:
        Path(datei).parent.mkdir(parents=True, exist_ok=True)
        with open(datei, "a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} geosphere_station: {text}\n")
    except OSError:
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description="Messwerte einer GeoSphere-Austria-Station abrufen")
    ap.add_argument("--station", default=DEFAULT_STATION, help="Stations-ID (Standard 11334 Schoengrabern)")
    ap.add_argument("--stunden", type=int, default=24, help="Zeitraum der Zusammenfassung in Stunden")
    ap.add_argument("--kurz", action="store_true", help="nur aktuelle Werte, keine Zusammenfassung")
    ap.add_argument("--json", action="store_true", help="aktuelle Rohwerte als JSON ausgeben")
    ap.add_argument("--suche", metavar="NAME", help="Stationen nach Namen suchen und beenden")
    ap.add_argument("--tinybox", nargs="?", const=str(Path(__file__).with_name("eingang")),
                    metavar="ORDNER", help="als Bulletin in den TinyBox-Eingangsordner legen "
                    "(Standard: eingang neben diesem Skript)")
    ap.add_argument("--ziel", default="WX", help="Bulletin-Ziel (Standard WX)")
    ap.add_argument("--gueltig", default="2h", help="Gueltigkeit des Bulletins (Standard 2h)")
    ap.add_argument("--brocast", nargs="?", const="http://127.0.0.1:8090/api/v1",
                    metavar="URL", help="nur zum Testen ohne TinyBox: Wetterseite direkt an "
                    "brocastd senden (Standard: http://127.0.0.1:8090/api/v1)")
    ap.add_argument("--token", default="", help="Token der Ingest-API ([station] token)")
    ap.add_argument("--log", metavar="DATEI", help="Fehler zusaetzlich in diese Datei schreiben")
    args = ap.parse_args()
    if args.tinybox and args.brocast:
        ap.error("--tinybox liefert die Wetterseite schon mit (Kopfzeile Brocast:), "
                 "TinyBox reicht sie an brocastd weiter - --brocast nicht zusaetzlich angeben")

    try:
        if args.suche:
            for s in metadaten().get("stations", []):
                if args.suche.lower() in s["name"].lower() and s.get("is_active"):
                    print(f"{s['id']:>8}  {s['name']:<30} {s['state']:<18} {s['altitude']:.0f} m")
            return 0

        if args.json:
            zeit, w = aktuelle_werte(args.station)
            print(json.dumps({"station": args.station, "zeit_utc": zeit, "werte": w},
                             ensure_ascii=False, indent=2))
            return 0

        daten = abrufen(args.station, args.stunden, args.kurz)
        name, zeit, zeilen = bericht(daten, args.stunden)
        if args.brocast:
            seite = brocast_seite(daten, args.stunden, gueltig_minuten(args.gueltig))
            url = f"{args.brocast.rstrip('/')}/pages/geosphere/wx-{args.station}"
            res = sende_brocast(url, seite, args.token)
            info = (f"brocast: Seite {res.get('id')} rev {res.get('rev')}, "
                    f"{sum(res.get('bytes') or [])} Bytes, ca. {res.get('airtime_s')} s"
                    + ("" if res.get("changed", True) else " (unverändert)"))
            print(info)
            protokoll(args.log, info)
        if args.tinybox:
            seite = brocast_seite(daten, args.stunden, gueltig_minuten(args.gueltig))
            kopf = {"To": args.ziel, "Subject": f"Wetter {name} {zeit[-5:]}"[:60],
                    "Replace": f"geosphere-wetter-{args.station}", "Valid": args.gueltig,
                    "Brocast": json.dumps(seite, ensure_ascii=False, separators=(",", ":"))}
            ziel = schreibe_tinybox(Path(args.tinybox), f"geosphere_wetter_{args.station}",
                                    kopf, "\n".join(zeilen[2:]))     # Kopfzeile steckt im Betreff
            print(f"Bulletin abgelegt: {ziel}")
            protokoll(args.log, f"abgelegt: {ziel} ({kopf['Subject']})")
        if not args.tinybox and not args.brocast:
            print("\n".join(zeilen))
        return 0

    except urllib.error.HTTPError as e:
        meldung = f"HTTP {e.code} - {e.read().decode(errors='replace')[:200]}"
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, IndexError, OSError) as e:
        meldung = f"Abruf/Auswertung: {e}"
    except Exception as e:                    # unerwartet: ohne Konsole (pyw) sonst unsichtbar
        import traceback
        meldung = f"unerwarteter Fehler: {e!r}\n{traceback.format_exc()}"
    print(f"Fehler: {meldung}", file=sys.stderr)
    protokoll(args.log, f"Fehler: {meldung}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
