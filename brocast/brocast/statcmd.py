"""Befehl `statistik`: die letzten 24 h der Station auswerten, mit Vorschlag (advisor.py).

    py -3 -m brocast statistik                  Bericht als Text
    py -3 -m brocast statistik --stunden 12     anderer Zeitraum (1..48 h)
    py -3 -m brocast statistik --json           alles als JSON (zum Weiterverarbeiten)
    py -3 -m brocast statistik --konfig DATEI   brocastd.conf (Standard: im aktuellen Ordner)

Nur im Betriebsmodus station. Liest das Sendeprotokoll, die Zähler-Datei
data/statistik.json und die Seiten aus der Datenbank (nur lesend) – brocastd darf
dabei laufen. Die Zähler-Datei schreibt brocastd alle db_flush_sec Sekunden
(Standard 10 min); die Web-GUI (Ansicht "Statistik") ist darum aktueller.
Es wird nichts geändert: die Werte trägt der Sysop selbst in brocastd.conf ein.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from . import advisor, config, txlog
from .frame import build as build_frame
from .stats import Stats, load_file

STATS_FILE = "statistik.json"
KINDS = {"neu": "neue Revisionen", "staffel": "Staffel (repeat_minutes)",
         "wiederholung": "Wiederholung", "gealtert": "gealtert (aging)", "rücknahme": "Rücknahmen",
         "dictionary": "Dictionary", "bake": "Bake"}


def _pages(cfg: config.Config) -> list[dict]:
    """Pages of the carousel, read only (brocastd may be running)."""
    db = cfg.data_dir / "brocastd.db"
    if not db.exists():
        return []
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = [SimpleNamespace(**dict(r)) for r in con.execute("SELECT * FROM pages")]
        frames: dict[int, list[bytes]] = {}
        for r in con.execute("SELECT pid, data FROM frames ORDER BY pid, n"):
            frames.setdefault(r["pid"], []).append(r["data"])
    finally:
        con.close()
    for r in rows:
        r.rev_t = getattr(r, "rev_t", 0)
    st = cfg.station
    return advisor.pages_from_rows(
        rows, lambda row: [len(build_frame(cfg.callsign, d, st.path, row.hdr))
                           for d in frames.get(row.pid, [])], st)


def report(cfg: config.Config, hours: int = 24, now: float | None = None) -> dict[str, Any]:
    now = time.time() if now is None else now
    since = now - hours * 3600
    sends = None
    if cfg.txlog_dir is not None:
        sends = txlog.group_sends(txlog.read_lines(txlog.files_for(cfg.txlog_dir, since, now),
                                                   since, now))
    counter = Stats(None, cfg.station.baud, cfg.station.txdelay_ms, lambda: now)
    counter.buckets = load_file(cfg.data_dir / STATS_FILE)
    rep = advisor.analyze(cfg.station, cfg.traffic, cfg.beacon.interval_min, sends,
                          counter.window(now, hours), _pages(cfg), now, hours)
    rep.update({"station": True, "callsign": cfg.callsign})
    return rep


# --- text --------------------------------------------------------------------------

def _t(ts: float, fmt: str = "%d.%m. %H:%M") -> str:
    return time.strftime(fmt, time.localtime(ts))


def _m(s: float) -> str:
    return f"{s / 60:.1f} min".replace(".", ",") if s < 5400 else f"{s / 3600:.1f} h".replace(".", ",")


def _n(x: Any) -> str:
    return "–" if x is None else f"{x:g}".replace(".", ",")


def text(rep: dict[str, Any]) -> str:
    out: list[str] = []
    add = out.append
    b, ch, w = rep["basis"], rep["channel"], rep["waiting"]
    add(f"brocast-Statistik {rep.get('callsign', '')} – {_t(rep['since'])} bis {_t(rep['now'])} "
        f"({rep['hours']} h)")
    add(f"Datenbasis: brocastd lief {_n(b['run_h'])} h, Sendeprotokoll "
        + (f"{b['sends']} Aussendungen" if b["txlog"] else "aus"))
    for note in b["notes"]:
        add(f"  ! {note}")
    add("")
    add("KANAL")
    add(f"  eigene Sendezeit  {_m(ch['own_s']):>10}  ({_n(ch['own_pct'])} %)")
    add(f"  fremd (geschätzt) {_m(ch['foreign_s']):>10}  ({_n(ch['foreign_pct'])} %) – "
        f"{ch['ui']} UI-Frames, {ch['conn']} aus Verbindungen, {ch['calls']} Rufzeichen")
    if ch.get("busiest"):
        h = ch["busiest"]
        add(f"  am meisten fremd: {_t(h['t'], '%H')}–{_t(h['t'] + 3600, '%H')} Uhr, "
            f"{_m(h['foreign_s'])}")
    add("")
    add("WARTEN")
    hold = w["hold"]
    add(f"  zurückgestellt: Betrieb {_m(hold['busy'])}, Kanal {_m(hold['channel'])}, "
        f"Budget {_m(hold['budget'])}, Direwolf getrennt {_m(hold['link'])}")
    add(f"  Verspätung gegen den Plan: Ø {_n(w['late_avg_s'])} s, höchstens {w['late_max_s']} s, "
        f"{w['late_over']} von {w['sends']} Aussendungen über 1 min")
    add(f"  Budget: höchstens {_n(w['budget_peak_s'])} s von {_n(w['budget_limit_s'])} s genutzt")
    own = rep.get("own")
    if own:
        add("")
        add("EIGENE SENDUNGEN")
        add(f"  {own['sends']} Seiten-Aussendungen, {own['frames']} Frames, "
            f"{own['bytes'] / 1024:.0f} kB, {_m(own['air_s'])}")
        k = own["kinds"]
        add("  davon: " + ", ".join(f"{KINDS.get(name, name)} {_m(v)}" for name, v in k.items() if v))
        add("  größte Verbraucher:")
        for p in own["top"][:5]:
            add(f"    P{p['page']:<5} {p['title'][:34]:<34} {_m(p['air_s']):>9} {_n(p['share']):>5} %  "
                f"{p['sends']}× gesendet, {p['revs']} Rev.")
    if rep["options"]:
        add("")
        add("NACHGERECHNET (Sendezeit je Tag, Ø Wartezeit eines Hörers neu / älter)")
        for o in rep["options"]:
            mark = "→" if o["name"] == rep.get("recommended") else " "
            if o.get("same_as"):
                add(f"  {mark} {o['name']:<11} wie {o['same_as']}")
                continue
            add(f"  {mark} {o['name']:<11} {_m(o['air_day_s']):>9}   {_n(o['access_young_min']):>5} / "
                f"{_n(o['access_old_min']):>6} min   repeat {o['repeat_minutes']}, max "
                f"{o['max_interval_min']}, aging {o['aging'] or '-'}")
        chk = rep.get("sim_check")
        if chk:
            add(f"    (Kontrolle: gesendet {chk['measured_sends']}, nachgerechnet "
                f"{chk['simulated_sends']} Aussendungen)")
    add("")
    add("VORSCHLAG")
    for a in rep["advice"]:
        sign = {"change": "*", "info": "-", "ok": "="}.get(a["level"], "-")
        add(f"  {sign} {a['title']}: {a['text']}")
        for line in a["conf"]:
            add(f"        {line}")
    add("")
    add("Nur Empfehlung – Werte mit * in brocastd.conf eintragen ([station], Bake unter "
        "[beacon], Ruhezeit unter [traffic]) und brocastd neu starten.")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="py -3 -m brocast statistik",
                                 description="24-h-Auswertung der Station mit Vorschlag")
    ap.add_argument("--konfig", default="brocastd.conf", help="brocastd.conf")
    ap.add_argument("--stunden", type=int, default=24, help="Zeitraum in Stunden (1..48)")
    ap.add_argument("--json", action="store_true", help="Ausgabe als JSON")
    args = ap.parse_args(argv)
    if not 1 <= args.stunden <= 48:
        print("--stunden: 1 bis 48", file=sys.stderr)
        return 2
    cfg = config.load(Path(args.konfig))                  # ConfigError fängt __main__ ab
    if not cfg.is_station:
        print(f"Die Statistik gehört zur Station: {args.konfig} hat mode = {cfg.mode}.",
              file=sys.stderr)
        return 1
    rep = report(cfg, args.stunden)
    try:                                   # Windows: console or file with another code page
        sys.stdout.reconfigure(errors="replace")      # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass
    print(json.dumps(rep, ensure_ascii=False, indent=1) if args.json else text(rep))
    return 0
