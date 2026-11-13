"""Statistik und Vorschlag (13.11.2026): 24 h Betrieb auswerten, Karussell-Takt empfehlen.

Quellen:
  * Sendeprotokoll (txlog.py): jede eigene Aussendung mit Seite, Revision, Bytes
  * Zähler (stats.py): fremder Verkehr, Wartezeiten nach Grund, TinyBox-Stufen,
    Verspätung gegenüber dem Plan, Laufzeit
  * Seiten im Karussell (Datenbank): aktuelle Revision und ihr Alter (rev_t)

Kern ist eine Nachrechnung: aus dem Protokoll ergibt sich für jede Seite, wann
eine neue Revision kam und wie lange sie lebte. Für den aktuellen Takt und eine
Reihe anderer Einstellungen (repeat_minutes, max_interval_min, aging) wird
gerechnet, wie oft die Seiten gesendet worden wären – mit derselben Regel wie im
Karussell (carousel.gap_min). Verglichen werden:

  * Sendezeit je Tag
  * Ø Wartezeit eines Hörers, der zu einem beliebigen Zeitpunkt einschaltet, bis
    die Seite kommt – getrennt für junge (< 24 h) und ältere Inhalte

Vorgeschlagen wird die Einstellung mit der geringsten Sendezeit, die die
Wartezeiten nicht spürbar verschlechtert ("ausgewogen"), bei vollem Kanal die
sparsamere. Dazu Hinweise aus den Zählern (Budget, Ruhezeit, Bake,
Aussendungsgröße, große Verbraucher). Nur Empfehlung: brocastd.conf ändert der
Sysop selbst.
"""

from __future__ import annotations

import math
from typing import Any, Iterable

from .config import StationCfg, TrafficCfg

DICT_DATA = ("brocastd", "dictionary-data")     # eigener Takt (daemon.DICT_DATA)
YOUNG_S = 24 * 3600
DAY = 86400

# Kandidaten der Nachrechnung (zusätzlich immer der aktuelle Wert)
REPEATS = [[0, 2, 5, 10], [0, 2, 10], [0, 3, 10], [0, 5, 15], [0, 2, 10, 20], [0, 5], [0, 10]]
MAX_INTERVALS = [20, 30, 45, 60, 90]
AGINGS = [[(24, 120), (72, 360), (168, 1440)],
          [(12, 90), (24, 180), (72, 720), (168, 1440)],
          [(6, 60), (24, 240), (72, 720), (168, 1440)]]


# --- helpers -----------------------------------------------------------------------

def gap_min(repeat: list[int], max_interval: int, aging: list[tuple[int, int]],
            sends_done: int, age_s: float) -> int:
    """Same rule as Carousel.gap_min."""
    gaps = repeat[1:]
    if sends_done - 1 < len(gaps):
        return gaps[sends_done - 1]
    gap = max_interval
    for hours, minutes in aging:
        if age_s >= hours * 3600:
            gap = minutes
    return gap


def conf_repeat(r: list[int]) -> str:
    return ",".join(str(x) for x in r)


def conf_aging(a: list[tuple[int, int]]) -> str:
    return ", ".join(f"{h}:{m}" for h, m in a) if a else ""


def first_hour_sends(repeat: list[int], max_interval: int) -> int:
    """How often a new revision goes out in its first hour (robustness)."""
    t, n, k = 0, 0, 0
    while t <= 60 and n < 50:
        n += 1
        k += 1
        g = gap_min(repeat, max_interval, [], k, 0)
        if g <= 0:
            break
        t += g
    return n


def send_air(air0: float, frames: int, cfg: StationCfg, burst: int | None = None) -> float:
    """Airtime of a page send with TXDELAY once per transmission."""
    b = cfg.burst_frames if burst is None else burst
    bursts = math.ceil(frames / b) if b > 0 else 1
    return air0 + max(bursts, 1) * cfg.txdelay_ms / 1000


# --- building the page timelines ---------------------------------------------------

def timelines(sends: list[dict], pages_now: list[dict], cfg: StationCfg,
              w0: float, w1: float) -> dict[tuple[str, str], dict]:
    """Per page: revisions (schedule start, birth, airtime) and lifetime."""
    now_by_key = {(p["provider"], p["key"]): p for p in pages_now}
    pages: dict[tuple[str, str], dict] = {}
    for s in sends:
        if s["beacon"] or (s["provider"], s["key"]) == DICT_DATA:
            continue
        k = (s["provider"], s["key"])
        p = pages.setdefault(k, {"page": s["page"], "title": s["title"], "typ": s["typ"],
                                 "revs": {}, "withdrawn_at": None, "last": s["t"]})
        p["last"] = max(p["last"], s["t"])
        p["title"], p["page"] = s["title"] or p["title"], s["page"]
        if s["withdrawn"]:
            if p["withdrawn_at"] is None:
                p["withdrawn_at"] = s["t"]
            continue
        r = p["revs"].setdefault(s["rev"], {"rev": s["rev"], "first": s["t"], "n": 0})
        r["n"] += 1
        r["air"] = send_air(s["air0"], s["frames"], cfg)
        r["air0"], r["frames"] = s["air0"], s["frames"]
    for k, cur in now_by_key.items():           # pages that did not go out at all (resting)
        if k == DICT_DATA or cur.get("state") == "withdrawn":
            continue
        p = pages.setdefault(k, {"page": cur["id"], "title": cur.get("title", ""),
                                 "typ": cur.get("typ", ""), "revs": {}, "withdrawn_at": None,
                                 "last": cur.get("rev_t", w0)})
        if cur["rev"] not in p["revs"]:
            p["revs"][cur["rev"]] = {"rev": cur["rev"], "first": max(cur.get("rev_t", w0), w0),
                                     "n": 0, "air": cur["air"], "air0": cur["air0"],
                                     "frames": cur["frames"]}
    for k, p in pages.items():
        cur = now_by_key.get(k)
        revs = sorted(p["revs"].values(), key=lambda r: r["first"])
        for r in revs:
            r["born"] = r["start"] = r["first"]
            if cur is not None and cur["rev"] == r["rev"] and cur.get("rev_t"):
                r["born"] = min(cur["rev_t"], r["first"])
                if cur["rev_t"] < w0:                 # started before the window: phase from birth
                    r["start"] = cur["rev_t"]
        if p["withdrawn_at"] is not None:
            end = p["withdrawn_at"]
        elif cur is not None and cur.get("state") != "withdrawn":
            end = w1
        else:
            end = p["last"] + 1
        for i, r in enumerate(revs):
            r["end"] = min(revs[i + 1]["start"] if i + 1 < len(revs) else end, w1)
        p["revs"] = revs
        p["end"] = min(end, w1)
        p["begin"] = max(w0, revs[0]["start"]) if revs else w0
    return pages


def simulate(pages: dict, repeat: list[int], max_interval: int, aging: list[tuple[int, int]],
             w0: float, w1: float, window_s: float) -> dict[str, Any]:
    """Sends, airtime, access time and budget peak for one setting."""
    total_air, n_sends = 0.0, 0
    acc = {"young": [0.0, 0.0], "old": [0.0, 0.0]}      # [sum g^2/2, sum g]
    events: list[tuple[float, float]] = []
    per_page: dict[tuple[str, str], tuple[int, float]] = {}
    for key, p in pages.items():
        times: list[tuple[float, dict]] = []
        for r in p["revs"]:
            t, k, guard = r["start"], 0, 0
            while t < r["end"] and guard < 20000:
                guard += 1
                if t >= w0:
                    times.append((t, r))
                k += 1
                g = gap_min(repeat, max_interval, aging, k, t - r["born"])
                if g <= 0:
                    break
                t += g * 60
        air = sum(r["air"] for _, r in times)
        per_page[key] = (len(times), air)
        total_air += air
        n_sends += len(times)
        events += [(t, r["air"]) for t, r in times]
        # access time: gaps between presence start, sends, presence end; a gap
        # belongs to the revision on the air at its start
        times.sort(key=lambda x: x[0])
        begin, end = p["begin"], p["end"]
        prev_t = begin
        prev_r = next((r for r in reversed(p["revs"]) if r["start"] <= begin), None)
        for t, r in times + [(end, None)]:
            if t < begin or t > end:
                continue
            g = t - prev_t
            if g > 0:
                young = prev_r is not None and prev_t - prev_r["born"] < YOUNG_S
                cls = acc["young" if young else "old"]
                cls[0] += g * g / 2
                cls[1] += g
            prev_t, prev_r = t, r if r is not None else prev_r
    events.sort()
    peak, run, j = 0.0, 0.0, 0
    for i, (t, a) in enumerate(events):
        run += a
        while events[j][0] < t - window_s:
            run -= events[j][1]
            j += 1
        peak = max(peak, run)

    def mean(c: str) -> float | None:
        s2, s = acc[c]
        return round(s2 / s / 60, 1) if s > 0 else None
    return {"air_s": total_air, "sends": n_sends, "access_young_min": mean("young"),
            "access_old_min": mean("old"), "peak_s": round(peak, 1), "per_page": per_page}


# --- the report --------------------------------------------------------------------

def _hourly(buckets: list[dict], sends: list[dict] | None, cfg: StationCfg) -> list[dict]:
    own_by_h: dict[int, float] = {}
    if sends is not None:
        for s in sends:
            h = int(s["t"] // 3600)
            own_by_h[h] = own_by_h.get(h, 0.0) + send_air(s["air0"], s["frames"], cfg,
                                                          1 if s["beacon"] else None)
    out = []
    for b in buckets:
        own = own_by_h.get(b["h"], 0.0) if sends is not None else b["own_s"]
        late = b["late_sum_s"] / b["sends"] if b["sends"] else 0.0
        out.append({"t": b["h"] * 3600, "run_s": round(b["run_s"]), "own_s": round(own, 1),
                    "foreign_s": round(b["fair_s"], 1), "ui": b["ui"], "conn": b["conn"],
                    "calls": len(b["calls"]), "late_avg_s": round(late, 1),
                    "late_max_s": b["late_max_s"],
                    "hold": {k: round(v) for k, v in b["hold"].items()},
                    "lvl1_s": round(b["lvl1_s"]), "lvl2_s": round(b["lvl2_s"])})
    return out


def analyze(cfg: StationCfg, traffic: TrafficCfg, beacon_min: int,
            sends: list[dict] | None, buckets: list[dict], pages_now: list[dict],
            now: float, hours: int = 24) -> dict[str, Any]:
    w1, w0 = now, now - hours * 3600
    span_h = hours
    run_s = sum(b["run_s"] for b in buckets)
    have_counter = run_s > 0
    notes: list[str] = []
    if sends is None:
        notes.append("Sendeprotokoll ist aus ([logging] txlog_dir leer) – eigene Sendungen "
                     "nur aus dem Zähler, keine Takt-Nachrechnung.")
    if not have_counter:
        notes.append("Der Zähler hat noch keine Daten (brocastd mit dieser Version noch nicht "
                     "gelaufen): fremder Verkehr und Wartezeiten fehlen.")
    elif run_s < hours * 3600 * 0.8:
        notes.append(f"Zähler-Daten erst über {run_s / 3600:.1f} von {hours} h – "
                     "die Auswertung ist vorläufig.")

    hourly = _hourly(buckets, sends, cfg)
    ref_s = run_s if have_counter else span_h * 3600
    own_s = sum(h["own_s"] for h in hourly)
    foreign_s = sum(h["foreign_s"] for h in hourly)
    calls = sorted({c for b in buckets for c in b["calls"]})
    channel = {"hours": hourly, "own_s": round(own_s), "foreign_s": round(foreign_s),
               "ref_s": round(ref_s), "own_pct": round(100 * own_s / ref_s, 1) if ref_s else 0,
               "foreign_pct": round(100 * foreign_s / ref_s, 1) if ref_s else 0,
               "ui": sum(b["ui"] for b in buckets), "conn": sum(b["conn"] for b in buckets),
               "calls": len(calls), "call_list": calls[:30]}
    busiest = max(hourly, key=lambda h: h["foreign_s"], default=None)
    channel["busiest"] = busiest if busiest and busiest["foreign_s"] > 0 else None

    hold = {k: round(sum(b["hold"][k] for b in buckets)) for k in ("busy", "channel", "budget", "link")}
    n_sends = sum(b["sends"] for b in buckets)
    late_n = sum(b["late_n"] for b in buckets)
    waiting = {"sends": n_sends, "late_n": late_n,
               "late_over": sum(b["late_over"] for b in buckets),
               "late_avg_s": round(sum(b["late_sum_s"] for b in buckets) / n_sends, 1) if n_sends else 0,
               "late_max_s": max((b["late_max_s"] for b in buckets), default=0),
               "hold": hold, "lvl1_s": round(sum(b["lvl1_s"] for b in buckets)),
               "lvl2_s": round(sum(b["lvl2_s"] for b in buckets)),
               "budget_peak_s": max((b["budget_peak_s"] for b in buckets), default=0),
               "budget_limit_s": round(cfg.airtime_window_min * 60 * cfg.airtime_percent / 100, 1)}

    report: dict[str, Any] = {
        "now": now, "since": w0, "hours": hours,
        "basis": {"run_h": round(run_s / 3600, 1), "txlog": sends is not None,
                  "sends": len(sends) if sends is not None else None, "notes": notes,
                  "preliminary": not have_counter or run_s < hours * 3600 * 0.8},
        "config": {"airtime_percent": cfg.airtime_percent,
                   "airtime_window_min": cfg.airtime_window_min,
                   "burst_frames": cfg.burst_frames, "burst_gap_s": cfg.burst_gap_s,
                   "repeat_minutes": conf_repeat(cfg.repeat_minutes),
                   "max_interval_min": cfg.max_interval_min, "aging": conf_aging(cfg.aging),
                   "quiet_s": traffic.quiet_s, "connected_quiet_s": traffic.connected_quiet_s,
                   "beacon_min": beacon_min, "baud": cfg.baud, "txdelay_ms": cfg.txdelay_ms},
        "channel": channel, "waiting": waiting, "own": None, "options": [],
        "recommended": None, "advice": []}
    advice: list[dict] = report["advice"]

    if sends is None:
        _counter_advice(report, cfg, traffic, beacon_min)
        return report

    # --- own transmissions from the Sendeprotokoll ---------------------------------
    pages = timelines(sends, pages_now, cfg, w0, w1)
    kinds = {"neu": 0.0, "staffel": 0.0, "wiederholung": 0.0, "gealtert": 0.0,
             "rücknahme": 0.0, "dictionary": 0.0, "bake": 0.0}
    seen: dict[tuple, int] = {}
    by_page: dict[tuple, dict] = {}
    first_aging_h = cfg.aging[0][0] if cfg.aging else None
    for s in sends:
        a = send_air(s["air0"], s["frames"], cfg, 1 if s["beacon"] else None)
        if s["beacon"]:
            kinds["bake"] += a
            continue
        key = (s["provider"], s["key"])
        bp = by_page.setdefault(key, {"page": s["page"], "title": s["title"], "typ": s["typ"],
                                      "provider": s["provider"], "key": s["key"],
                                      "air_s": 0.0, "sends": 0, "revs": set(), "frames": 0})
        bp["air_s"] += a
        bp["sends"] += 1
        bp["frames"] = s["frames"]
        bp["revs"].add(s["rev"])
        bp["title"] = s["title"] or bp["title"]
        if key == DICT_DATA:
            kinds["dictionary"] += a
            continue
        if s["withdrawn"]:
            kinds["rücknahme"] += a
            continue
        rk = (key, s["rev"])
        seen[rk] = seen.get(rk, 0) + 1
        rev = next((r for r in pages.get(key, {}).get("revs", []) if r["rev"] == s["rev"]), None)
        fresh = rev is not None and rev["start"] >= w0
        age = s["t"] - rev["born"] if rev else 0
        if fresh and seen[rk] == 1:
            kinds["neu"] += a
        elif fresh and seen[rk] <= len(cfg.repeat_minutes):
            kinds["staffel"] += a
        elif first_aging_h is not None and age >= first_aging_h * 3600:
            kinds["gealtert"] += a
        else:
            kinds["wiederholung"] += a
    own_total = sum(kinds.values())
    top = sorted(by_page.values(), key=lambda p: p["air_s"], reverse=True)
    for p in top:
        p["revs"] = len(p["revs"])
        p["air_s"] = round(p["air_s"], 1)
        p["share"] = round(100 * p["air_s"] / own_total, 1) if own_total else 0
    report["own"] = {"sends": sum(1 for s in sends if not s["beacon"]),
                     "frames": sum(s["frames"] for s in sends),
                     "bytes": sum(s["bytes"] for s in sends), "air_s": round(own_total, 1),
                     "kinds": {k: round(v, 1) for k, v in kinds.items()},
                     "pages": len(by_page), "top": top[:10]}

    # --- re-calculation of the carousel for other settings ---------------------------
    window_s = cfg.airtime_window_min * 60
    fixed = kinds["dictionary"] + kinds["rücknahme"] + kinds["bake"]
    cur_set = (tuple(cfg.repeat_minutes), cfg.max_interval_min, tuple(cfg.aging))
    sets = {cur_set}
    for r in REPEATS:
        for m in MAX_INTERVALS:
            for ag in AGINGS + [cfg.aging]:
                sets.add((tuple(r), m, tuple(ag)))
    results = []
    for r, m, ag in sets:
        res = simulate(pages, list(r), m, list(ag), w0, w1, window_s)
        res.update({"repeat": list(r), "max_interval": m, "aging": list(ag),
                    "first_hour": first_hour_sends(list(r), m), "current": (r, m, ag) == cur_set})
        res["air_total_s"] = res["air_s"] + fixed
        results.append(res)
    cur = next(x for x in results if x["current"])
    report["sim_check"] = {"measured_s": round(own_total - fixed, 1), "simulated_s": round(cur["air_s"], 1),
                           "measured_sends": sum(r["n"] for p in pages.values() for r in p["revs"]),
                           "simulated_sends": cur["sends"]}

    def ok_young(x: dict, factor: float, plus: float) -> bool:
        a, c = x["access_young_min"], cur["access_young_min"]
        return a is None or c is None or a <= c * factor + plus

    def ok_old(x: dict, factor: float, plus: float) -> bool:
        a, c = x["access_old_min"], cur["access_old_min"]
        return a is None or c is None or a <= c * factor + plus

    def access(x: dict) -> float:
        """Access time relative to now (1 = like now), young content counts double."""
        a = 0.0
        for k, w in (("access_young_min", 2), ("access_old_min", 1)):
            if x[k] is not None and cur[k]:
                a += w * x[k] / cur[k]
        return a

    def cheapest(cands: list[dict]) -> dict:
        """Least airtime; within 3 % of it the shortest access time; the current
        setting wins a tie (no change for nothing)."""
        if not cands:
            return cur
        low = min(x["air_s"] for x in cands)
        near = [x for x in cands if x["air_s"] <= low * 1.03 + 1]
        return min(near, key=lambda x: (round(access(x), 2), not x["current"]))

    robust = [x for x in results if x["first_hour"] >= 3]   # >= 3 sends in the first hour
    balanced = cheapest([x for x in robust if ok_young(x, 1.15, 0.5) and ok_old(x, 1.15, 2)])
    thrifty = cheapest([x for x in robust if ok_young(x, 1.6, 2) and ok_old(x, 2.0, 10)])
    if thrifty["air_s"] > balanced["air_s"] * 0.92:          # hardly cheaper: not worth it
        thrifty = balanced
    faster = min((x for x in robust if x["air_s"] <= cur["air_s"] * 1.05 + 1),
                 key=lambda x: (round(access(x), 2), not x["current"]), default=cur)

    def option(name: str, x: dict, label: str) -> dict:
        lines = []
        if x["repeat"] != cfg.repeat_minutes:
            lines.append(f"repeat_minutes     = {conf_repeat(x['repeat'])}")
        if x["max_interval"] != cfg.max_interval_min:
            lines.append(f"max_interval_min   = {x['max_interval']}")
        if x["aging"] != cfg.aging:
            lines.append(f"aging              = {conf_aging(x['aging'])}")
        scale = DAY / (w1 - w0)
        return {"name": name, "label": label, "repeat_minutes": conf_repeat(x["repeat"]),
                "max_interval_min": x["max_interval"], "aging": conf_aging(x["aging"]),
                "air_day_s": round(x["air_total_s"] * scale), "sends": x["sends"],
                "access_young_min": x["access_young_min"], "access_old_min": x["access_old_min"],
                "peak_s": x["peak_s"], "first_hour": x["first_hour"], "conf": lines,
                "same": not lines}
    report["options"] = [option("aktuell", cur, "so wie jetzt (nachgerechnet)"),
                         option("ausgewogen", balanced, "weniger Sendezeit, Wartezeiten fast gleich"),
                         option("sparsam", thrifty, "deutlich weniger Sendezeit, Hörer warten länger"),
                         option("schneller", faster, "kürzere Wartezeiten bei gleicher Sendezeit")]
    for o in report["options"][1:]:                 # the same setting as an option before it
        o["same_as"] = next((q["name"] for q in report["options"]
                             if q is not o and q["conf"] == o["conf"]
                             and report["options"].index(q) < report["options"].index(o)), None)

    # --- which option fits the channel ---------------------------------------------
    run_ref = run_s if have_counter else span_h * 3600
    held = hold["busy"] + hold["channel"] + hold["budget"]
    crowded = have_counter and (channel["foreign_pct"] >= 15 or held >= 0.10 * run_ref)
    pick = report["options"][2 if crowded else 1]
    base = report["options"][0]
    saving = base["air_day_s"] - pick["air_day_s"]
    if not pick["same"] and saving >= max(60, 0.10 * base["air_day_s"]):
        report["recommended"] = pick["name"]
        why = ("Der Kanal ist gut belegt (" + (f"fremd {channel['foreign_pct']:g} %" if
               channel["foreign_pct"] >= 15 else f"{held / 60:.0f} min zurückgestellt") + "), "
               "darum die sparsame Variante. " if crowded else "")
        advice.append({"level": "change", "title": "Karussell-Takt",
                       "text": why + f"Spart rund {_dur(saving)} Sendezeit am Tag "
                               f"({100 * saving / max(base['air_day_s'], 1):.0f} %). "
                               + _access_text(base, pick),
                       "conf": pick["conf"], "saving_s": round(saving)})
    else:
        advice.append({"level": "ok", "title": "Karussell-Takt",
                       "text": "Der Takt passt zum Betrieb – keine der nachgerechneten "
                               "Einstellungen spart nennenswert, ohne dass Hörer länger warten.",
                       "conf": [], "saving_s": 0})
    fast = report["options"][3]
    if not crowded and not fast["same"] and report["recommended"] is None \
            and (fast["access_young_min"] or 0) < (base["access_young_min"] or 0) * 0.85:
        advice.append({"level": "info", "title": "Schneller bei gleicher Sendezeit",
                       "text": "Der Kanal ist ruhig. Mit dieser Einstellung kommen Seiten öfter, "
                               "ohne mehr zu senden. " + _access_text(base, fast),
                       "conf": fast["conf"], "saving_s": 0})

    _counter_advice(report, cfg, traffic, beacon_min, pick if report["recommended"] else base)
    _page_advice(report, pages, w0, w1)
    _burst_advice(report, sends, cfg, crowded)
    return report


def _dur(s: float) -> str:
    s = abs(s)
    if s >= 3600:
        return f"{s / 3600:.1f} h".replace(".", ",")
    if s >= 90:
        return f"{s / 60:.0f} min"
    return f"{s:.0f} s"


def _access_text(base: dict, new: dict) -> str:
    def part(k: str, label: str) -> str:
        a, b = base[k], new[k]
        if a is None or b is None:
            return ""
        return f"{label} {a:g} → {b:g} min".replace(".", ",")
    parts = [p for p in (part("access_young_min", "neue Inhalte"),
                         part("access_old_min", "ältere")) if p]
    return ("Ø Wartezeit eines Hörers: " + ", ".join(parts) + ".") if parts else ""


def _counter_advice(report: dict, cfg: StationCfg, traffic: TrafficCfg, beacon_min: int,
                    chosen: dict | None = None) -> None:
    """Hints from the counter: budget, quiet time, beacon."""
    advice, w, ch = report["advice"], report["waiting"], report["channel"]
    run = report["basis"]["run_h"] * 3600
    if run <= 0:
        return
    limit = w["budget_limit_s"]
    window_s = cfg.airtime_window_min * 60
    need = chosen["peak_s"] if chosen else w["budget_peak_s"]
    if w["hold"]["budget"] >= 0.02 * run and w["late_over"] >= max(3, 0.03 * max(w["sends"], 1)):
        pct = min(30, max(cfg.airtime_percent + 1, math.ceil(100 * need * 1.2 / window_s)))
        advice.append({"level": "change", "title": "Airtime-Budget zu knapp",
                       "text": f"Das Budget hat die Sendung {_dur(w['hold']['budget'])} lang "
                               f"aufgehalten, {w['late_over']} Aussendungen kamen über eine Minute "
                               "zu spät. Mehr Budget – oder weniger senden (Takt oben).",
                       "conf": [f"airtime_percent    = {pct:g}"], "saving_s": 0})
    elif w["budget_peak_s"] and w["budget_peak_s"] < 0.5 * limit and run >= 12 * 3600:
        pct = max(5, math.ceil(100 * max(w["budget_peak_s"], need) * 1.3 / window_s))
        if pct < cfg.airtime_percent:
            advice.append({"level": "info", "title": "Budget hat viel Reserve",
                           "text": f"Höchstens {w['budget_peak_s']:g} s von {limit:g} s in "
                                   f"{cfg.airtime_window_min} min genutzt. Ein kleineres Budget "
                                   "ändert die Sendung nicht, begrenzt aber Ausreißer (z. B. "
                                   "viele neue Seiten auf einmal) – optional.",
                           "conf": [f"airtime_percent    = {pct:g}"], "saving_s": 0})
    ch_hold = w["hold"]["channel"]
    if ch_hold >= 0.15 * run and w["late_over"] >= max(3, 0.05 * max(w["sends"], 1)):
        ui_heavy = ch["ui"] > 3 * max(ch["conn"], 1)
        if ui_heavy and traffic.quiet_s > 5:
            q = max(5, traffic.quiet_s // 2)
            advice.append({"level": "change", "title": "Ruhezeit nach fremden Frames",
                           "text": f"Die Sendung stand {_dur(ch_hold)} wegen gehörter Frames, fast nur "
                                   f"UI ({ch['ui']} UI, {ch['conn']} Verbindung). Bei viel APRS/Baken "
                                   "auf der Frequenz kommt brocast sonst kaum zum Zug – kürzere Ruhe "
                                   "nach UI-Frames; nach Verbindungen bleibt sie lang.",
                           "conf": [f"quiet_s           = {q}"], "saving_s": 0})
        else:
            advice.append({"level": "info", "title": "Viel Verbindungsverkehr",
                           "text": f"Die Sendung stand {_dur(ch_hold)} wegen Verbindungen anderer "
                                   "Stationen – so gewollt (echter Verkehr geht vor). Weniger senden "
                                   "(Takt) hilft, die Verspätungen klein zu halten.",
                           "conf": [], "saving_s": 0})
    if w["lvl1_s"] or w["lvl2_s"]:
        advice.append({"level": "info", "title": "TinyBox-Betrieb",
                       "text": f"Benutzer über Funk verbunden: {_dur(w['lvl1_s'])}, Forward: "
                               f"{_dur(w['lvl2_s'])}. In dieser Zeit sendet brocast weniger "
                               "bzw. nichts (außer Notfall-Seiten).", "conf": [], "saving_s": 0})
    own = report.get("own")
    if own and beacon_min:
        bake = own["kinds"]["bake"] * DAY / (report["hours"] * 3600)
        share = own["kinds"]["bake"] / own["air_s"] if own["air_s"] else 0
        if beacon_min < 30 and share >= 0.05:
            new = 60 if share >= 0.10 else 30
            advice.append({"level": "change", "title": "Bake seltener",
                           "text": f"Die Bake braucht {_dur(bake)} am Tag ({100 * share:.0f} % der "
                                   f"eigenen Sendezeit). Alle {new} min reicht, damit Zuhörer am "
                                   "Monitor das System erkennen.",
                           "conf": [f"interval_min = {new}   ; Abschnitt [beacon]"],
                           "saving_s": round(bake * (1 - beacon_min / new))})


def _page_advice(report: dict, pages: dict, w0: float, w1: float) -> None:
    """Big consumers and pages that come with a new revision very often."""
    own, advice = report["own"], report["advice"]
    scale = DAY / (w1 - w0)
    for p in own["top"][:5]:
        if p["share"] >= 15 and (p["provider"], p["key"]) != DICT_DATA:
            advice.append({"level": "info", "title": f"Großer Verbraucher P{p['page']}",
                           "text": f"„{p['title'] or p['typ']}“ braucht {p['share']:g} % der eigenen "
                                   f"Sendezeit ({p['sends']} Aussendungen, {p['frames']} Teile, "
                                   f"{p['revs']} Revisionen). Kleiner machen oder seltener neu liefern "
                                   "lohnt hier am meisten.", "conf": [], "saving_s": 0})
    churn: dict[str, list[float]] = {}             # provider -> revisions a day per page
    for (provider, _), p in pages.items():
        n = sum(1 for r in p["revs"] if r["start"] >= w0) * scale
        if n >= 20:
            churn.setdefault(provider, []).append(n)
    if churn:
        parts = []
        for provider, ns in sorted(churn.items(), key=lambda x: -sum(x[1])):
            per = f"{min(ns):.0f}×" if round(min(ns)) == round(max(ns)) \
                else f"{min(ns):.0f}–{max(ns):.0f}×"
            parts.append(f"{provider}: {len(ns)} Seite{'' if len(ns) == 1 else 'n'} je {per}")
        advice.append({"level": "info", "title": "Oft neue Revisionen",
                       "text": "Jede neue Revision startet die Wiederholungs-Staffel von vorn. "
                               "Sehr oft neu am Tag: " + "; ".join(parts) + ". Ändert sich "
                               "inhaltlich wenig, beim Lieferanten seltener ersetzen – gleicher "
                               "Inhalt per Replace verlängert nur die Gültigkeit.",
                       "conf": [], "saving_s": 0})


def _burst_advice(report: dict, sends: list[dict], cfg: StationCfg, crowded: bool) -> None:
    """Bigger transmissions save TXDELAY - only when the channel is quiet."""
    if crowded or cfg.burst_frames <= 0 or cfg.burst_frames >= 8:
        return
    new = cfg.burst_frames + 2
    saved = 0
    for s in sends:
        if s["beacon"]:
            continue
        saved += math.ceil(s["frames"] / cfg.burst_frames) - math.ceil(s["frames"] / new)
    scale = DAY / (report["hours"] * 3600)
    air = saved * cfg.txdelay_ms / 1000 * scale
    gaps = saved * cfg.burst_gap_s * scale
    if air >= 30:
        report["advice"].append({
            "level": "info", "title": "Größere Aussendungen",
            "text": f"Der Kanal ist ruhig. Mit {new} statt {cfg.burst_frames} Frames je Aussendung "
                    f"fallen {saved * scale:.0f} PTT-Zyklen am Tag weg: {_dur(air)} TXDELAY weniger, "
                    f"die Seiten sind {_dur(gaps)} früher durch. Dafür ist der Kanal je Aussendung "
                    "etwas länger belegt.", "conf": [f"burst_frames       = {new}"],
            "saving_s": round(air)})


def pages_from_rows(rows: Iterable[Any], frames_of, cfg: StationCfg) -> list[dict]:
    """Current carousel pages for the analysis. rows: PageRow-like objects;
    frames_of(row) -> list of on-air frame lengths."""
    from .frame import airtime_s
    from .txlog import title_of
    out = []
    for row in rows:
        lens = frames_of(row)
        air0 = sum(airtime_s(n, cfg.baud, 0) for n in lens)
        typ, title = title_of(row.content)
        out.append({"provider": row.provider, "key": row.pkey, "id": row.id, "rev": row.rev,
                    "rev_t": row.rev_t or row.t, "state": row.state, "title": title, "typ": typ,
                    "frames": len(lens), "air0": air0,
                    "air": send_air(air0, len(lens), cfg)})
    return out
