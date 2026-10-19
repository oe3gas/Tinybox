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
  python geosphere_station.py --region         # alle Stationen Wein-/Waldviertel (REGION):
                                               # am Bildschirm der Gesamtueberblick
  python geosphere_station.py --region --tinybox
                                               # je Station ein Einzelbericht wie Schoengrabern
                                               # (Replace: geosphere-wetter-<ID>) und dazu der
                                               # Gesamtueberblick (Replace: geosphere-wetter-region,
                                               # Brocast: Tabellenseite)
  python geosphere_station.py --region --tinybox --einzel-ohne-brocast
                                               # Einzelberichte nur als Text in der Mailbox
                                               # (spart ~24 Frames je Karussell-Lauf)

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
PRED_MIN = 950             # hPa; darunter ist PRED kein reduzierter Druck (Bergstationen)

# Parameter fuer die Anzeige (Station 11334 hat laut Metadaten keine Sonnenschein-/Strahlungsmessung)
PARAMS = ["TL", "TP", "RF", "P", "PRED", "DD", "FF", "FFX", "RR"]

WINDRICHTUNG = ["N", "NNO", "NO", "ONO", "O", "OSO", "SO", "SSO",
                "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]

# Stationen fuer --region: (ID, Kurzname fuer den Ueberblick), Stand TAWES-Metadaten 13.10.2026.
# Kurznamen ASCII und max. 13 Zeichen (Tabelle im Ueberblick, Tabellenseite fuer brocast).
REGION = {
    "Weinviertel": [
        ("11022", "Retz"), ("11335", "Laa/Thaya"), ("11032", "Poysdorf"),
        ("11334", "Schoengrabern"), ("11332", "Mistelbach"), ("11333", "Hohenau"),
        ("11083", "Leiser Berge"), ("11045", "Wolkersdorf"), ("11027", "Stockerau"),
        ("11048", "Gaenserndorf"), ("11085", "Marchegg"), ("11037", "Gr.Enzersdorf"),
    ],
    "Waldviertel": [
        ("11047", "Raabs/Thaya"), ("11021", "Litschau"), ("11025", "Weitra"),
        ("8989083", "Schwarzau/Fw"), ("11019", "Allentsteig"), ("11020", "Stift Zwettl"),
        ("11297", "Horn"), ("11064", "Gars/Kamp"), ("11367", "Baernkopf"),
        ("11024", "Jauerling"), ("11075", "Langenlois"), ("11070", "Krems"),
    ],
}
REGION_IDS = [sid for liste in REGION.values() for sid, _ in liste]
REGION_NAME = {sid: kurz for liste in REGION.values() for sid, kurz in liste}


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


_METADATEN: dict | None = None


def metadaten() -> dict:
    global _METADATEN
    if _METADATEN is None:
        _METADATEN = api_get(f"current/{DATASET}/metadata", {})
    return _METADATEN


def station_info(station_id: str):
    for s in metadaten().get("stations", []):
        if s["id"] == station_id:
            return s
    return None


def _je_station(d: dict) -> dict:
    """GeoJSON-Antwort -> {Stations-ID: {Parameter: Datenliste}}.
    Die API liefert die Features nicht in der angefragten Reihenfolge."""
    return {f["properties"]["station"]: {k: v.get("data") or [] for k, v in
                                         f["properties"]["parameters"].items()}
            for f in d.get("features", [])}


def aktuelle_werte_mehrere(station_ids: list[str]) -> dict[str, tuple[str, dict]]:
    """-> {ID: (Messzeit, {Parameter: Wert})} fuer alle Stationen in einem Abruf.

    Bei mehreren Stationen liefert die API mehrere Zeitstempel (z. B. xx:10 und
    xx:20); jede Station hat nur an ihrem eigenen juengsten Zeitpunkt Werte, sonst
    null. Daher je Station den letzten Zeitpunkt mit Werten nehmen."""
    d = api_get(f"current/{DATASET}", {"station_ids": ",".join(station_ids),
                                       "parameters": ",".join(PARAMS)})
    ts = d.get("timestamps") or []
    out = {}
    for sid, p in _je_station(d).items():
        idx = [i for i in range(len(ts)) if any(r[i] is not None for r in p.values() if len(r) > i)]
        if not idx:
            continue
        i = idx[-1]
        out[sid] = (ts[i], {k: (r[i] if len(r) > i else None) for k, r in p.items()})
    return out


def aktuelle_werte(station_id: str):
    werte = aktuelle_werte_mehrere([station_id])
    if station_id not in werte:
        raise ValueError(f"Station {station_id}: keine aktuellen Werte")
    return werte[station_id]


def verlauf_mehrere(station_ids: list[str], stunden: int):
    """-> (Zeitstempel, {ID: {Parameter: Reihe}}) fuer alle Stationen in einem Abruf."""
    ende = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    start = ende - timedelta(hours=stunden)
    d = api_get(f"historical/{DATASET}", {
        "station_ids": ",".join(station_ids),
        "parameters": "TL,RR,FFX,PRED",
        "start": start.strftime("%Y-%m-%dT%H:%M"),
        "end": ende.strftime("%Y-%m-%dT%H:%M"),
    })
    return d["timestamps"], _je_station(d)


def verlauf(station_id: str, stunden: int):
    ts, reihen = verlauf_mehrere([station_id], stunden)
    return ts, reihen[station_id]


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


def abrufen_mehrere(stationen: list[str], stunden: int, kurz: bool) -> dict[str, dict]:
    """Alle Daten fuer mehrere Stationen in zwei Abrufen holen: -> {ID: Datensatz}.
    Stationen ohne aktuelle Werte (Ausfall) fehlen im Ergebnis."""
    werte = aktuelle_werte_mehrere(stationen)
    ts, reihen = ([], {}) if kurz else verlauf_mehrere(stationen, stunden)
    out = {}
    for sid in stationen:
        if sid not in werte:
            continue
        zeit, w = werte[sid]
        r = reihen.get(sid, {})
        # Bergstationen (Baernkopf, Jauerling): unter 950 hPa ist PRED laut GeoSphere
        # kein reduzierter Druck (dann gilt PGPM) - lieber kein Wert als ein falscher
        if w.get("PRED") is not None and w["PRED"] < PRED_MIN:
            w["PRED"] = None
        if "PRED" in r:
            r["PRED"] = [None if x is not None and x < PRED_MIN else x for x in r["PRED"]]
        out[sid] = {"station": sid, "zeit": zeit, "w": w, "info": station_info(sid),
                    "ts": ts if sid in reihen else [], "reihen": r}
    return out


def abrufen(station: str, stunden: int, kurz: bool) -> dict:
    """Alle Daten einmal holen: aktuelle Werte, Stationsinfo, optional der Verlauf."""
    daten = abrufen_mehrere([station], stunden, kurz)
    if station not in daten:
        raise ValueError(f"Station {station}: keine aktuellen Werte")
    return daten[station]


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
# Gesamtueberblick Wein-/Waldviertel (--region)
# ---------------------------------------------------------------------------

def _kennzahlen(d: dict) -> dict:
    """Die Werte einer Station fuer den Ueberblick: aktuell + letzte Stunde/24 h."""
    w, reihen = d["w"], d["reihen"]

    def gueltig(key, n):
        return [x for x in reihen.get(key, [])[-n:] if x is not None]

    rr24, ffx1, tl24 = gueltig("RR", 144), gueltig("FFX", 6), gueltig("TL", 144)
    return {"name": REGION_NAME.get(d["station"], stationsname(d)[:13]),
            "hoehe": d["info"]["altitude"] if d["info"] else None,
            "temp": w.get("TL"), "dew": w.get("TP"), "hum": w.get("RF"), "qff": w.get("PRED"),
            "wdir": w.get("DD"), "wspd": w.get("FF"),
            "boe1h": max(ffx1) if ffx1 else w.get("FFX"),
            "rr24": sum(rr24) if rr24 else None,
            "tmin": min(tl24) if tl24 else None, "tmax": max(tl24) if tl24 else None}


def ueberblick(daten: dict[str, dict], zeit: str, stunden: int) -> list[str]:
    """Textzeilen des Gesamtueberblicks: eine Zeile je Station, dann die Extremwerte.
    Nur ASCII, max. 60 Zeichen je Zeile (Terminal und Funk)."""
    kz = {sid: _kennzahlen(d) for sid, d in daten.items()}
    def zeile(name, hoehe, temp, dew, hum, qff, wind, wspd, boe, rr):
        return (f"{name:<13} {hoehe:>4} {temp:>5} {dew:>4} {hum:>3} {qff:>6} "
                f"{wind:<3}{wspd:>4} {boe:>5} {rr:>5}")

    zeilen = [f"Wetter Wein- & Waldviertel {lokalzeit(zeit)} (10-min-Werte)", "",
              zeile("Station", "m", "T", "Tp", "rF", "QFF", "", "Wind", "Boe", "RR24")]
    for gebiet, liste in REGION.items():
        zeilen.append(f"--- {gebiet} ---")
        for sid, kurz in liste:
            k = kz.get(sid)
            if k is None:
                zeilen.append(f"{kurz:<13}    -  (keine Daten)")
                continue
            zeilen.append(zeile(k["name"], f(k["hoehe"], "{:.0f}"), f(k["temp"]), f(k["dew"]),
                                f(k["hum"], "{:.0f}"), f(k["qff"]),
                                richtung(k["wdir"]) if k["wspd"] is not None else "-",
                                f(k["wspd"]), f(k["boe1h"]), f(k["rr24"])))
    zeilen += ["", "T Tp in C, rF %, QFF hPa, Wind/Boe m/s (Boe = Spitze",
               f"der letzten Stunde), RR24 = Niederschlag mm, letzte {min(stunden, 24)} h"]

    def extrem(key, fn, einheit, label):
        kandidaten = [(k[key], k["name"]) for k in kz.values() if k[key] is not None]
        if not kandidaten:
            return None
        wert, name = fn(kandidaten)
        if fn is max and wert <= 0:                     # "Regen max. 0.0 mm" sagt nichts
            return None
        return f"{label} {name} {wert:.1f}{einheit}"
    e = [extrem("tmin", min, " C", "  Tiefstwert  "), extrem("tmax", max, " C", "  Hoechstwert "),
         extrem("rr24", max, " mm", "  Regen max.  "), extrem("boe1h", max, " m/s", "  Boe max.    ")]
    zeilen += ["", f"Letzte {min(stunden, 24)} h in der Region:", *[x for x in e if x],
               "", "Quelle: GeoSphere Austria, TAWES (CC BY 4.0)"]
    return zeilen


# Zeilen je Tabellenblock: ein Block muss auch im schlimmsten Fall (13-Zeichen-Namen,
# dreistellige Werte) in einen Frame (240 Bytes) passen; der Splitter von brocastd
# packt dann so viele Bloecke je Unterseite, wie hineingehen (normal 4-5 Frames).
TABELLE_ZEILEN = 3


# Spaltenbedeutung der Tabellenseite (Block-Key n): dat-Felder des Wetter-Dictionarys,
# alles andere ("name") ist eine Textspalte. Der Listener zeichnet daraus das
# Wetterraster (Farbbalken, Windpfeile, Extremwerte); Terminal/Rohansicht ignorieren n.
TABELLE_HDR = ["Station", "°C", "Wind aus", "Wind m/s", "Böen", "Niederschlag 24h mm"]
TABELLE_N = ["name", "temp", "wdir", "wspd", "gust", "r24h"]


def brocast_ueberblick(daten: dict[str, dict], zeit: str, gueltig_min: int) -> dict:
    """Tabellenseite (typ text, Bloecke table) fuer brocastd: Kurzname, T, Wind, Boe, RR24.

    Zahlen als Ganzzahlen in 0,1-Einheiten (sc -1, wie bei series; Floats kosten
    9 Bytes je Zelle), Windrichtung als Kompass-Text. Bewusst wenige Spalten:
    24 Zeilen x ~22 Bytes, gepackt 3 Frames je Karussell-Lauf. Je Gebiet eine
    Gruppenzeile mit nur einer Zelle (["Weinviertel"]) als Zwischenueberschrift."""
    def z(x):
        return None if x is None else round(x * 10)

    rows = []
    for gebiet, liste in REGION.items():
        rows.append([gebiet])
        for sid, _ in liste:
            d = daten.get(sid)
            if d is None:
                continue
            k = _kennzahlen(d)
            rows.append([k["name"], z(k["temp"]),
                         richtung(k["wdir"]) if k["wspd"] is not None else None,
                         z(k["wspd"]), z(k["boe1h"]), z(k["rr24"])])
    # Kopfzeile und Spaltenbedeutung nur einmal (Bytes); der erste Block traegt dazu
    # nur die erste Gruppenzeile, damit er auch im Frame-Format 1 in einen Frame passt
    blk = [{"k": "table", "sc": -1, "rows": rows[:1], "hdr": TABELLE_HDR, "n": TABELLE_N}]
    blk += [{"k": "table", "sc": -1, "rows": rows[i:i + TABELLE_ZEILEN]}
            for i in range(1, len(rows), TABELLE_ZEILEN)]
    return {"typ": "text", "cat": ["wx"], "exp": gueltig_min,
            "ti": f"Wetter Wein- & Waldviertel {lokalzeit(zeit)[-5:]}",
            "src": ["geosphere"], "blk": blk}


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
             "src": ["geosphere"],
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


def bulletin_station(d: dict, args, mit_brocast: bool) -> Path:
    """Einzelbericht einer Station als Bulletin in den TinyBox-Eingang (Vorlage Schoengrabern)."""
    name, zeit, zeilen = bericht(d, args.stunden)
    kopf = {"To": args.ziel, "Subject": f"Wetter {name} {zeit[-5:]}"[:60],
            "Replace": f"geosphere-wetter-{d['station']}", "Valid": args.gueltig}
    if mit_brocast:
        seite = brocast_seite(d, args.stunden, gueltig_minuten(args.gueltig))
        kopf["Brocast"] = json.dumps(seite, ensure_ascii=False, separators=(",", ":"))
    return schreibe_tinybox(Path(args.tinybox), f"geosphere_wetter_{d['station']}",
                            kopf, "\n".join(zeilen[2:]))     # Kopfzeile steckt im Betreff


def region(args) -> int:
    """--region: alle Stationen in zwei Abrufen, Einzelberichte + Gesamtueberblick."""
    daten = abrufen_mehrere(REGION_IDS, args.stunden, args.kurz)
    if not daten:
        raise ValueError("keine Station der Region liefert aktuelle Werte")
    zeit = max(d["zeit"] for d in daten.values())      # juengste Messzeit der Region
    fehlend = [REGION_NAME[s] for s in REGION_IDS if s not in daten]
    if fehlend:
        protokoll(args.log, f"ohne Daten: {', '.join(fehlend)}")
    zeilen = ueberblick(daten, zeit, args.stunden)
    if not args.tinybox:
        print("\n".join(zeilen))
        return 0
    for sid in REGION_IDS:
        if sid in daten:
            bulletin_station(daten[sid], args, not args.einzel_ohne_brocast)
    kopf = {"To": args.ziel, "Subject": f"Wetter Wein- & Waldviertel {lokalzeit(zeit)[-5:]}",
            "Replace": "geosphere-wetter-region", "Valid": args.gueltig,
            "Brocast": json.dumps(brocast_ueberblick(daten, zeit, gueltig_minuten(args.gueltig)),
                                  ensure_ascii=False, separators=(",", ":"))}
    ziel = schreibe_tinybox(Path(args.tinybox), "geosphere_wetter_region", kopf,
                            "\n".join(zeilen[2:]))
    info = f"Region: {len(daten)} Einzelberichte + Ueberblick abgelegt ({ziel})"
    print(info)
    protokoll(args.log, info)
    return 0


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
    ap.add_argument("--region", action="store_true",
                    help="alle Stationen Wein-/Waldviertel: Einzelberichte (nur mit --tinybox) "
                         "und Gesamtueberblick")
    ap.add_argument("--einzel-ohne-brocast", action="store_true",
                    help="--region: Einzelberichte ohne Brocast-Seite (nur Text in der Mailbox)")
    args = ap.parse_args()
    if args.tinybox and args.brocast:
        ap.error("--tinybox liefert die Wetterseite schon mit (Kopfzeile Brocast:), "
                 "TinyBox reicht sie an brocastd weiter - --brocast nicht zusaetzlich angeben")
    if args.region and (args.brocast or args.json):
        ap.error("--region geht nur am Bildschirm oder mit --tinybox")

    try:
        if args.region:
            return region(args)

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
            ziel = bulletin_station(daten, args, mit_brocast=True)
            print(f"Bulletin abgelegt: {ziel}")
            protokoll(args.log, f"abgelegt: {ziel} (Wetter {name} {zeit[-5:]})")
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
