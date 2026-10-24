#!/usr/bin/env python3
"""
geosphere_prognose.py - Wetterprognose fuer einen Maidenhead-Locator (GeoSphere Austria).

Datenquelle: GeoSphere Austria Data Hub, Wettermodell "nwp-v1-1h-2500m" (C-LAEF,
2,5-km-Gitter, Stundenwerte, 61 h, neuer Lauf alle 3 h; CC BY 4.0)
  Doku:      https://dataset.api.hub.geosphere.at/v1/docs
  Prognose:  /v1/timeseries/forecast/nwp-v1-1h-2500m?lat_lon=<lat>,<lon>&parameters=...

Der Locator (6- oder 8-stellig) wird in seinen Mittelpunkt umgerechnet; die API
liefert die Werte der Gitterzelle an diesem Punkt. Ein 6-stelliges Kleinfeld
(ca. 6 x 5 km) entspricht etwa 3 x 2 Modellzellen - feiner gibt die Prognose
nichts her. 4-stellige Locators (150 x 110 km) werden abgelehnt.

Nur Python-Standardbibliothek, kein API-Key noetig.

Beispiele:
  python geosphere_prognose.py                          # JN88BN, 48 h in 3-h-Schritten
  python geosphere_prognose.py --locator JN78wm         # anderer Locator
  python geosphere_prognose.py --stunden 24             # nur ein Tag (max. 54 h)
  python geosphere_prognose.py --schritt 1 --stunden 12 # stuendlich
  python geosphere_prognose.py --json                   # aufbereitete Werte als JSON
  python geosphere_prognose.py --locator JN88bn,JN78wm --tinybox
                                                # je Locator ein Bulletin an WX
                                                # (Replace: geosphere-prognose-<LOC>,
                                                # Valid: 4h) mit brocast-Seite
                                                # (Kopfzeile "Brocast:", Prognosetabelle)
  python geosphere_prognose.py --brocast        # nur zum Testen ohne TinyBox: Seite
                                                # direkt an brocastd (geosphere/fc-<LOC>)

Takt: das Modell rechnet alle 3 h neu und ist erst einige Stunden spaeter
abrufbar. Die Aufgabenplanung ruft das Skript daher alle 3 h auf (zur vollen
3-Stunden-Zeit + 35 min, z. B. 15:35); dann beginnt die Tabelle genau auf dem
3-Stunden-Raster.

Exit-Codes: 0 = ok, 2 = Fehler
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import geosphere_station as gs        # TLS-Kontext, Bulletin-Datei, brocast-PUT, Helfer

BASE = "https://dataset.api.hub.geosphere.at/v1/timeseries/forecast"
DATASET = "nwp-v1-1h-2500m"
PARAMS = ["t2m", "u10m", "v10m", "ugust", "vgust", "rr_acc", "tcc"]
DEFAULT_LOCATOR = "JN88BN"
# Modellgebiet laut Metadaten (bbox): Sueden, Westen, Norden, Osten
BBOX = (42.981, 5.498, 51.819, 22.102)
# Quellenangabe: der Listen-Eintrag "geosphere" im Dictionary nennt TAWES (Messnetz),
# das passt fuer die Prognose nicht - bis zu einem eigenen Eintrag (PLANUNG 20) als Text
QUELLE = "GeoSphere Austria, NWP (CC BY 4.0)"

WOCHENTAG = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


# ---------------------------------------------------------------------------
# Locator
# ---------------------------------------------------------------------------

LOCATOR_RE = re.compile(r"[A-R]{2}[0-9]{2}[A-X]{2}([0-9]{2})?")


def locator_norm(loc: str) -> str:
    """'jn88bn' -> 'JN88BN'; ValueError bei ungueltigem oder zu grobem Locator."""
    loc = loc.strip().upper()
    if not LOCATOR_RE.fullmatch(loc):
        if re.fullmatch(r"[A-R]{2}[0-9]{2}", loc):
            raise ValueError(f"Locator {loc} ist zu grob (ca. 150 x 110 km) - "
                             f"bitte 6-stellig, z. B. {loc}BN")
        raise ValueError(f"Locator ungueltig: {loc} (6- oder 8-stellig, z. B. JN88BN)")
    return loc


def locator_feld(loc: str) -> tuple[float, float, float, float]:
    """-> (Sued, West, Nord, Ost) des Locator-Feldes in Grad."""
    loc = locator_norm(loc)
    lon = (ord(loc[0]) - 65) * 20 - 180 + int(loc[2]) * 2 + (ord(loc[4]) - 65) * 5 / 60
    lat = (ord(loc[1]) - 65) * 10 - 90 + int(loc[3]) + (ord(loc[5]) - 65) * 2.5 / 60
    dlon, dlat = 5 / 60, 2.5 / 60
    if len(loc) == 8:
        dlon, dlat = dlon / 10, dlat / 10
        lon += int(loc[6]) * dlon
        lat += int(loc[7]) * dlat
    return lat, lon, lat + dlat, lon + dlon


def locator_mitte(loc: str) -> tuple[float, float]:
    """Mittelpunkt (lat, lon) eines 6- oder 8-stelligen Locators, z. B. JN88BN -> (48.5625, 16.125)."""
    s, w, n, o = locator_feld(loc)
    lat, lon = round((s + n) / 2, 4), round((w + o) / 2, 4)
    if not (BBOX[0] <= lat <= BBOX[2] and BBOX[1] <= lon <= BBOX[3]):
        raise ValueError(f"Locator {locator_norm(loc)} liegt ausserhalb des Modellgebiets "
                         "(Oesterreich mit Umland, etwa 43-51,8 N / 5,5-22 O)")
    return lat, lon


# ---------------------------------------------------------------------------
# Abruf
# ---------------------------------------------------------------------------

def api_get(punkte: list[tuple[float, float]], timeout: int = 30) -> dict:
    params = [("lat_lon", f"{lat},{lon}") for lat, lon in punkte]
    params.append(("parameters", ",".join(PARAMS)))
    url = f"{BASE}/{DATASET}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "geosphere_prognose.py (OE3GAS)",
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=gs.ssl_kontext()) as resp:
        return json.load(resp)


def zuordnen(antwort: dict, punkte: list[tuple[float, float]]) -> list[dict]:
    """GeoJSON-Antwort -> je angefragtem Punkt (gleiche Reihenfolge) ein Datensatz
    {"ts", "lauf", "zelle": (lat, lon), "p": {Parameter: Reihe}}.

    Die Features tragen die Koordinaten der Gitterzelle, nicht die angefragten;
    zugeordnet wird daher ueber den kleinsten Abstand."""
    ts = antwort.get("timestamps") or []
    features = antwort.get("features") or []
    if not ts or not features:
        raise ValueError("Antwort ohne Prognosewerte")
    out = []
    for lat, lon in punkte:
        f = min(features, key=lambda f: (f["geometry"]["coordinates"][1] - lat) ** 2
                + ((f["geometry"]["coordinates"][0] - lon) * math.cos(math.radians(lat))) ** 2)
        glon, glat = f["geometry"]["coordinates"][:2]
        if abs(glat - lat) > 0.05 or abs(glon - lon) > 0.05:      # Gitter: 0,018 / 0,028 Grad
            raise ValueError(f"keine Prognose fuer {lat},{lon} in der Antwort")
        out.append({"ts": ts, "lauf": antwort.get("reference_time"),
                    "zelle": (round(glat, 4), round(glon, 4)),
                    "p": {k: v.get("data") or [] for k, v in f["properties"]["parameters"].items()}})
    return out


# ---------------------------------------------------------------------------
# Aufbereitung: Stundenwerte -> Zeilen je Schritt
# ---------------------------------------------------------------------------

def wind(u, v):
    """(u, v) in m/s -> (Geschwindigkeit m/s, Richtung woher in Grad) oder (None, None)."""
    if u is None or v is None:
        return None, None
    ff = math.hypot(u, v)
    dd = (270 - math.degrees(math.atan2(v, u))) % 360
    return ff, dd


def lokal(iso: str) -> datetime:
    return datetime.fromisoformat(iso).astimezone()


def schritte(d: dict, stunden: int, schritt: int) -> list[dict]:
    """Zeilen der Prognose: je Schritt Beginn (lokal), Temperatur am Beginn, mittlerer
    Wind (Vektormittel), staerkste Boe und Niederschlag im Schritt, Bewoelkung (Achtel).

    Der erste Schritt beginnt mit dem ersten Wert der API (aktuelle Stunde), die
    weiteren auf dem lokalen Raster (Stunde durch schritt teilbar) - so bleibt die
    Tabelle auch ueber die Zeitumstellung lesbar."""
    ts, p = d["ts"], d["p"]
    n = len(ts)
    zeiten = [lokal(t) for t in ts]
    beginne = [0] + [i for i in range(1, n) if zeiten[i].hour % schritt == 0]
    ende_zeit = zeiten[0].timestamp() + stunden * 3600
    reihe = lambda k: p.get(k) or [None] * n                     # noqa: E731
    t2m, u, v, ug, vg, rr, tcc = (reihe(k) for k in PARAMS)

    zeilen = []
    for j, s in enumerate(beginne):
        e = beginne[j + 1] if j + 1 < len(beginne) else min(n - 1, s + schritt)
        if e <= s or zeiten[s].timestamp() >= ende_zeit:
            break
        # Vektormittel des Windes ueber die Stunden des Schritts
        uu = [u[i] for i in range(s, e) if u[i] is not None and v[i] is not None]
        vv = [v[i] for i in range(s, e) if u[i] is not None and v[i] is not None]
        ff, dd = wind(sum(uu) / len(uu), sum(vv) / len(vv)) if uu else (None, None)
        # Boe: Maximum der letzten Stunde -> Werte bei s+1 .. e gehoeren zum Schritt
        boeen = [math.hypot(ug[i], vg[i]) for i in range(s + 1, e + 1)
                 if ug[i] is not None and vg[i] is not None]
        regen = None
        if rr[s] is not None and rr[e] is not None:
            regen = max(0.0, rr[e] - rr[s])        # Summenreihe schwankt minimal (Rundung)
        wolken = [tcc[i] for i in range(s, e) if tcc[i] is not None]
        zeilen.append({
            "zeit": zeiten[s], "bis": zeiten[e], "temp": t2m[s],
            "wspd": ff, "wdir": dd, "boe": max(boeen) if boeen else None, "regen": regen,
            "achtel": round(sum(wolken) / len(wolken) * 8) if wolken else None,
        })
    return zeilen


def kennzahlen(zeilen: list[dict]) -> dict:
    """Extreme ueber die ganze Prognose: Tmin/Tmax, staerkste Boe, Regensumme."""
    def extrem(key, fn):
        mit = [z for z in zeilen if z[key] is not None]
        return fn(mit, key=lambda z: z[key]) if mit else None
    nass = [z for z in zeilen if (z["regen"] or 0) >= 0.1]
    return {"tmin": extrem("temp", min), "tmax": extrem("temp", max),
            "boe": extrem("boe", max),
            "regen": sum(z["regen"] or 0 for z in zeilen),
            "regen_ab": nass[0] if nass else None}


def tag(dt: datetime) -> str:
    return f"{WOCHENTAG[dt.weekday()]} {dt:%d.%m.}"


def wann(dt: datetime) -> str:
    return f"{WOCHENTAG[dt.weekday()]} {dt:%H} Uhr"


def kmh(ms) -> str:
    return "-" if ms is None else f"{ms * 3.6:.0f}"


# ---------------------------------------------------------------------------
# Ausgabe: Text (Bildschirm, Mailbox) und brocast-Seite
# ---------------------------------------------------------------------------

def zeile(uhr, wolken, temp, wdir, wspd, boe, bft, regen) -> str:
    return f"  {uhr:>3} {wolken:>6} {temp:>6}  {wdir:<4} {wspd:>4} {boe:>6} {bft:>3} {regen:>6}"


def bericht(loc: str, d: dict, zeilen: list[dict], schritt: int) -> list[str]:
    """Textbericht, max. 60 Zeichen breit (Terminal-User der TinyBox)."""
    glat, glon = d["zelle"]
    out = [f"Prognose {loc} (Zelle {glat:.3f} N {glon:.3f} O)",
           f"Modelllauf {gs.lokalzeit(d['lauf'])}, Werte je {schritt} h", "",
           zeile("Uhr", "Wolken", "Temp", "Wind", "km/h", "Boeen", "Bft", "Regen"),
           zeile("", "/8", "°C", "aus", "", "km/h", "", "mm")]
    letzter_tag = None
    for z in zeilen:
        if z["zeit"].date() != letzter_tag:
            letzter_tag = z["zeit"].date()
            out.append(f"{tag(z['zeit'])}")
        boe = z["boe"]
        out.append(zeile(f"{z['zeit']:%H}", gs.f(z["achtel"], "{:d}"), gs.f(z["temp"]),
                         gs.richtung(z["wdir"]) if z["wspd"] is not None else "-", kmh(z["wspd"]),
                         kmh(boe), "-" if boe is None else str(gs.beaufort(boe)), gs.f(z["regen"])))
    k = kennzahlen(zeilen)
    out.append("")
    if k["tmin"] and k["tmax"]:
        out.append(f"Temperatur  {k['tmin']['temp']:.1f} bis {k['tmax']['temp']:.1f} °C")
    if k["boe"]:
        b = k["boe"]["boe"]
        out.append(f"Max. Boe    {b * 3.6:.0f} km/h (Bft {gs.beaufort(b)}) {wann(k['boe']['zeit'])}")
    if k["regen_ab"]:
        out.append(f"Regen       {k['regen']:.1f} mm, ab {wann(k['regen_ab']['zeit'])}")
    else:
        out.append("Regen       keiner erwartet")
    out += ["", f"Quelle: {QUELLE}"]
    return out


# brocast: eine Tabelle mit Spaltenbedeutung n (wie die Regionsuebersicht, PLANUNG 6g).
# Die erste Spalte "hour" macht daraus im Listener die Prognosegrafik (Meteogramm):
# Uhrzeit-Leiste, Wolkensymbole, Temperaturkurve, Regenbalken, Windpfeile, Boeen.
# Terminal/Teletext/Text zeigen die schlichte Tabelle. Alle Zahlen in 0,1-Einheiten
# (sc -1), auch die Achtel (8/8 -> 80); Uhrzeit und Windrichtung als Text.
PROGNOSE_HDR = ["Uhr", "Wolken/8", "°C", "Wind", "m/s", "Böe m/s", "Regen mm"]
PROGNOSE_N = ["hour", "sky", "temp", "wdir", "wspd", "gust", "rr"]
PROGNOSE_ZEILEN = 4                    # Zeilen je Tabellenblock (ein Block = ein Frame)


def brocast_seite(loc: str, d: dict, zeilen: list[dict], schritt: int, gueltig_min: int) -> dict:
    def z(x):
        return None if x is None else round(x * 10)

    rows = []
    letzter_tag = None
    for r in zeilen:
        if r["zeit"].date() != letzter_tag:
            letzter_tag = r["zeit"].date()
            rows.append([tag(r["zeit"])])                     # Gruppenzeile je Tag
        rows.append([f"{r['zeit']:%H}", None if r["achtel"] is None else r["achtel"] * 10,
                     z(r["temp"]),
                     gs.richtung(r["wdir"]) if r["wspd"] is not None else None,
                     z(r["wspd"]), z(r["boe"]), z(r["regen"])])
    # Kopfzeile und Spaltenbedeutung nur einmal; der erste Block traegt dazu nur die
    # erste Tageszeile, damit er mit dem Umschlag sicher in einen Frame passt
    blk = [{"k": "table", "sc": -1, "hdr": PROGNOSE_HDR, "n": PROGNOSE_N, "rows": rows[:1]}]
    blk += [{"k": "table", "sc": -1, "rows": rows[i:i + PROGNOSE_ZEILEN]}
            for i in range(1, len(rows), PROGNOSE_ZEILEN)]
    erste = zeilen[0]["zeit"]
    return {"typ": "wx", "cat": ["wx"], "exp": gueltig_min,
            "ti": f"Prognose {loc} {WOCHENTAG[erste.weekday()]} {erste:%H} Uhr",
            "area": loc, "pos": list(d["zelle"]), "src": QUELLE, "blk": blk}


def als_json(loc: str, d: dict, zeilen: list[dict]) -> dict:
    return {"locator": loc, "zelle": d["zelle"], "lauf": d["lauf"],
            "zeilen": [{**z, "zeit": z["zeit"].isoformat(), "bis": z["bis"].isoformat()}
                       for z in zeilen]}


# ---------------------------------------------------------------------------
# Hauptprogramm
# ---------------------------------------------------------------------------

def protokoll(datei: str | None, text: str) -> None:
    if not datei:
        return
    try:
        Path(datei).parent.mkdir(parents=True, exist_ok=True)
        with open(datei, "a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} geosphere_prognose: {text}\n")
    except OSError:
        pass


def bulletin(loc: str, d: dict, zeilen: list[dict], args) -> Path:
    text = bericht(loc, d, zeilen, args.schritt)
    erste = zeilen[0]["zeit"]
    seite = brocast_seite(loc, d, zeilen, args.schritt, gs.gueltig_minuten(args.gueltig))
    kopf = {"To": args.ziel, "Subject": f"Prognose {loc} ab {tag(erste)} {erste:%H} Uhr"[:60],
            "Replace": f"geosphere-prognose-{loc}", "Valid": args.gueltig,
            "Brocast": json.dumps(seite, ensure_ascii=False, separators=(",", ":"))}
    return gs.schreibe_tinybox(Path(args.tinybox), f"geosphere_prognose_{loc}", kopf,
                               "\n".join(text[1:]))           # Kopfzeile steckt im Betreff


def main() -> int:
    ap = argparse.ArgumentParser(description="Wetterprognose fuer Maidenhead-Locators (GeoSphere Austria)")
    ap.add_argument("--locator", default=DEFAULT_LOCATOR,
                    help="ein oder mehrere Locators, mit Komma getrennt (Standard JN88BN)")
    ap.add_argument("--stunden", type=int, default=48, help="Zeitraum in Stunden (Standard 48, max. 54)")
    ap.add_argument("--schritt", type=int, default=3, choices=[1, 2, 3, 6],
                    help="Stunden je Zeile (Standard 3)")
    ap.add_argument("--json", action="store_true", help="aufbereitete Werte als JSON ausgeben")
    ap.add_argument("--tinybox", nargs="?", const=str(Path(__file__).with_name("eingang")),
                    metavar="ORDNER", help="je Locator ein Bulletin in den TinyBox-Eingangsordner "
                    "(Standard: eingang neben diesem Skript)")
    ap.add_argument("--ziel", default="WX", help="Bulletin-Ziel (Standard WX)")
    ap.add_argument("--gueltig", default="4h", help="Gueltigkeit des Bulletins (Standard 4h)")
    ap.add_argument("--brocast", nargs="?", const="http://127.0.0.1:8090/api/v1",
                    metavar="URL", help="nur zum Testen ohne TinyBox: Seite direkt an brocastd")
    ap.add_argument("--token", default="", help="Token der Ingest-API ([station] token)")
    ap.add_argument("--log", metavar="DATEI", help="Fehler zusaetzlich in diese Datei schreiben")
    args = ap.parse_args()
    if args.tinybox and args.brocast:
        ap.error("--tinybox liefert die Seite schon mit (Kopfzeile Brocast:) - "
                 "--brocast nicht zusaetzlich angeben")
    if not 1 <= args.stunden <= 54:
        ap.error("--stunden: 1 bis 54 (das Modell rechnet 61 h ab Laufbeginn)")

    try:
        locs = [locator_norm(x) for x in args.locator.split(",") if x.strip()]
        punkte = [locator_mitte(x) for x in locs]
        daten = zuordnen(api_get(punkte), punkte)
        ergebnis = []
        for loc, d in zip(locs, daten):
            zeilen = schritte(d, args.stunden, args.schritt)
            if not zeilen:
                raise ValueError(f"{loc}: keine Prognosewerte")
            ergebnis.append((loc, d, zeilen))

        if args.json:
            print(json.dumps([als_json(*e) for e in ergebnis], ensure_ascii=False, indent=2))
            return 0
        for loc, d, zeilen in ergebnis:
            if args.tinybox:
                ziel = bulletin(loc, d, zeilen, args)
                print(f"Bulletin abgelegt: {ziel}")
                protokoll(args.log, f"abgelegt: {ziel}")
            elif args.brocast:
                seite = brocast_seite(loc, d, zeilen, args.schritt, gs.gueltig_minuten(args.gueltig))
                url = f"{args.brocast.rstrip('/')}/pages/geosphere/fc-{loc.lower()}"
                res = gs.sende_brocast(url, seite, args.token)
                info = (f"brocast: Seite {res.get('id')} rev {res.get('rev')}, "
                        f"{sum(res.get('bytes') or [])} Bytes, ca. {res.get('airtime_s')} s")
                print(info)
                protokoll(args.log, info)
            else:
                print("\n".join(bericht(loc, d, zeilen, args.schritt)))
                print()
        return 0

    except urllib.error.HTTPError as e:
        meldung = f"HTTP {e.code} - {e.read().decode(errors='replace')[:200]}"
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, IndexError, OSError) as e:
        meldung = f"Abruf/Auswertung: {e}" + (f" - {gs.TLS_HINWEIS}" if gs.tls_fehler(e) else "")
    except Exception as e:                    # unerwartet: ohne Konsole (pyw) sonst unsichtbar
        import traceback
        meldung = f"unerwarteter Fehler: {e!r}\n{traceback.format_exc()}"
    print(f"Fehler: {meldung}", file=sys.stderr)
    protokoll(args.log, f"Fehler: {meldung}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
