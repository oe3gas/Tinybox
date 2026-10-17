"""APRS statistics of the channel (CR61).

Every APRS frame the monitor hears becomes one small record. The records of
the last days are kept in memory and - if a file is given - in a SQLite
database, so a restart does not lose them. report() sums up a time window:

    totals      frames, stations, frames per minute, bytes, estimated air time
    heard       the stations the radio actually received (last digipeater with
                '*', or the sender directly)
    senders     who sent the packets; third-party packets count for the station
                inside (from the internet), the iGate is listed under igates
    devices     the device list entry (tocall or Mic-E) per frame and station
    types       position, Mic-E, weather, telemetry, objects ...
    digis       every digipeater that relayed (all calls with '*'), chains, hops
    igates      third-party packets (internet -> radio) per iGate
    range       distances from the own locator, the farthest stations
    countries   by call prefix
    timeline    frames per time slot
    sins        what burdens the channel: beacons too often, unchanged repeats,
                long paths, wrong clocks, broken packets, much internet traffic

Shared by the client and (later) the TinyBox; no web code here.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import sqlite3
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path

log = logging.getLogger(__name__)

KEEP_SEC = 7 * 86400          # records older than this are dropped
MAX_RECORDS = 200_000
BAUD = 1200
TXDELAY_SEC = 0.3             # assumed key-up time per frame (air time estimate)

# ---------------------------------------------------------------- call prefixes

_PREFIXES = [  # longest first wins; (prefix regex, country)
    (r"OE", "Austria"), (r"O[KL]", "Czechia"), (r"OM", "Slovakia"), (r"S5", "Slovenia"),
    (r"H[AG]", "Hungary"), (r"S[N-R]|3Z|HF", "Poland"), (r"9A", "Croatia"), (r"D[A-R]", "Germany"),
    (r"HB0", "Liechtenstein"), (r"HB", "Switzerland"), (r"I", "Italy"), (r"Y[T-U]|YZ", "Serbia"),
    (r"E7", "Bosnia and Herzegovina"), (r"Z3", "North Macedonia"), (r"4O", "Montenegro"),
    (r"ZA", "Albania"), (r"Y[O-R]", "Romania"), (r"LZ", "Bulgaria"), (r"S[V-Z]|J4", "Greece"),
    (r"T[A-C]", "Turkey"), (r"U[R-Z]|E[M-O]", "Ukraine"), (r"EW", "Belarus"), (r"ER", "Moldova"),
    (r"LY", "Lithuania"), (r"YL", "Latvia"), (r"ES", "Estonia"), (r"OH", "Finland"),
    (r"S[A-M]|7S|8S", "Sweden"), (r"L[A-N]", "Norway"), (r"O[U-Z]|5[PQ]", "Denmark"),
    (r"P[A-I]", "Netherlands"), (r"O[N-T]", "Belgium"), (r"LX", "Luxembourg"),
    (r"F|T[MOK]", "France"), (r"[GM]|2[EIMW]", "United Kingdom"), (r"E[I-J]", "Ireland"),
    (r"E[A-H]", "Spain"), (r"C[T-U]", "Portugal"), (r"9H", "Malta"), (r"R|U[A-I]", "Russia"),
    (r"K|N|W|A[A-K]", "USA"), (r"V[A-G]|VO|VY", "Canada"),
]
_PREFIX_RE = [(re.compile(p), c) for p, c in _PREFIXES]


def country(call: str) -> str:
    base = call.split("-")[0].upper()
    if "/" in base:                                  # OE3GAS/P -> OE3GAS, DL/OE3GAS -> DL
        parts = base.split("/")
        base = parts[0] if len(parts[0]) >= len(parts[1]) or parts[1] in ("P", "M", "MM", "A") else parts[1]
    best, n = "other", 0
    for rx, c in _PREFIX_RE:
        m = rx.match(base)
        if m and m.end() > n:
            best, n = c, m.end()
    return best


# ---------------------------------------------------------------- helpers

_TS = re.compile(r"^([/@])\d{6}[zh/]")
_OBJ_TS = re.compile(r"^(;.{9}[*_])\d{6}[zh/]")


def _norm(info: str) -> str:
    """The content without the timestamp: is it the same packet again?"""
    info = _TS.sub(r"\1", info)
    info = _OBJ_TS.sub(r"\1", info)
    m = re.match(r"^(\}[^:]*:)(.*)$", info)          # third party: the inner packet
    if m:
        return _norm(m.group(2))
    return info.rstrip(" \r\n")


def airtime(nbytes: int) -> float:
    """Seconds on the air at 1200 Bd: key-up + flags + frame + FCS, ~5 % bit stuffing."""
    return TXDELAY_SEC + (nbytes + 4) * 8 * 1.05 / BAUD


def _fmt_interval(sec: float) -> str:
    return f"{sec:.0f} s" if sec < 120 else f"{sec / 60:.0f} min"


def _dist(a, b) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    return 2 * 6371.0 * math.asin(math.sqrt(math.sin((la2 - la1) / 2) ** 2 +
                                            math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2))


# ---------------------------------------------------------------- the store

FIELDS = ("t", "src", "origin", "gate", "heard", "digis", "dev", "cat", "nbytes", "lat", "lon",
          "flags", "h", "req")


class AprsStats:
    def __init__(self, path: Path | None = None, home: tuple[float, float] | None = None) -> None:
        self.path = path
        self.home = home
        self.recs: list[dict] = []
        self.since = time.time()                     # counting since (start or reset)
        self._db: sqlite3.Connection | None = None
        if path is not None:
            self._open()

    # --- storage ------------------------------------------------------------------
    def _open(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(str(self.path), check_same_thread=False)
            self._db.execute("CREATE TABLE IF NOT EXISTS rec (t REAL, j TEXT)")
            self._db.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
            self._db.execute("CREATE INDEX IF NOT EXISTS rec_t ON rec (t)")
            cut = time.time() - KEEP_SEC
            self._db.execute("DELETE FROM rec WHERE t < ?", (cut,))
            self._db.commit()
            for (j,) in self._db.execute("SELECT j FROM rec ORDER BY t"):
                try:
                    self.recs.append(json.loads(j))
                except ValueError:
                    pass
            row = self._db.execute("SELECT v FROM meta WHERE k = 'since'").fetchone()
            if row:
                self.since = float(row[0])
            elif self.recs:
                self.since = self.recs[0]["t"]
        except sqlite3.Error as exc:
            log.warning("APRS statistics not stored: %s", exc)
            self._db = None

    def _save(self, rec: dict) -> None:
        if self._db is None:
            return
        try:
            self._db.execute("INSERT INTO rec VALUES (?, ?)", (rec["t"], json.dumps(rec, separators=(",", ":"))))
            self._db.commit()
        except sqlite3.Error as exc:
            log.warning("APRS statistics: %s", exc)

    def reset(self) -> None:
        self.recs.clear()
        self.since = time.time()
        if self._db is not None:
            try:
                self._db.execute("DELETE FROM rec")
                self._db.execute("INSERT OR REPLACE INTO meta VALUES ('since', ?)", (str(self.since),))
                self._db.commit()
            except sqlite3.Error as exc:
                log.warning("APRS statistics: %s", exc)

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None

    # --- input --------------------------------------------------------------------
    def add(self, src: str, path: list[str], repeated: list[bool], info: bytes, nbytes: int,
            aprs: dict, now: float | None = None) -> dict:
        """One APRS frame heard (aprs = tinybox.aprs.decode() of it)."""
        now = time.time() if now is None else now
        origin = (aprs.get("origin") or {}).get("call") or src
        gate = (aprs.get("origin") or {}).get("gate") or ""
        dev = (aprs.get("origin") or {}).get("device") if aprs.get("origin") else aprs["dest"].get("device", "")
        req = 0
        for c in path:                                  # hops asked for (WIDEn-N: n)
            m = re.match(r"^(?:WIDE|[A-Z]{2})(\d)(?:-\d{1,2})?$", c)
            if m:
                req += int(m.group(1))
        rec = {"t": round(now, 1), "src": src, "origin": origin, "gate": gate,
               "heard": aprs["heard"]["call"], "digis": [c["call"] for c in aprs.get("chain", [])[1:]
                                                       if c["call"] != "?"],
               "dev": dev or "", "cat": aprs.get("cat", "other"), "nbytes": nbytes,
               "lat": aprs.get("lat"), "lon": aprs.get("lon"), "flags": aprs.get("flags", []),
               "h": hashlib.blake2s(_norm(info.decode("latin-1")).encode("latin-1"), digest_size=6).hexdigest(),
               "req": req}
        self.recs.append(rec)
        cut = now - KEEP_SEC
        if len(self.recs) > MAX_RECORDS or (self.recs and self.recs[0]["t"] < cut):
            self.recs = [r for r in self.recs[-MAX_RECORDS:] if r["t"] >= cut]
        self._save(rec)
        return rec

    # --- output -------------------------------------------------------------------
    def report(self, window: int = 0, now: float | None = None) -> dict:
        """Sums of the last window seconds (0 = everything kept)."""
        now = time.time() if now is None else now
        start = max(self.since, now - window) if window else self.since
        recs = [r for r in self.recs if r["t"] >= start]
        span = max(60.0, now - (recs[0]["t"] if recs and not window else start))
        n = len(recs)
        air = sum(airtime(r["nbytes"]) for r in recs)

        def top(counter: Counter, k: int = 50) -> list:
            return counter.most_common(k)

        heard = Counter(r["heard"] or "?" for r in recs)
        last_heard: dict[str, float] = {}
        for r in recs:
            last_heard[r["heard"] or "?"] = r["t"]

        senders: dict[str, dict] = {}
        for r in recs:
            s = senders.setdefault(r["origin"], {"call": r["origin"], "n": 0, "cats": Counter(),
                                                 "last": 0, "dev": r["dev"], "inet": 0, "dist": None})
            s["n"] += 1
            s["cats"][r["cat"]] += 1
            s["last"] = r["t"]
            s["dev"] = r["dev"] or s["dev"]
            if r["gate"]:
                s["inet"] += 1
            if self.home and r["lat"] is not None:
                s["dist"] = round(_dist(self.home, (r["lat"], r["lon"])))
        times = defaultdict(list)
        for r in recs:
            times[r["origin"]].append(r["t"])
        for c, s in senders.items():
            ts = times[c]
            gaps = [b - a for a, b in zip(ts, ts[1:]) if b - a > 30]      # bursts (PARM, UNIT ...) count once
            s["every"] = round(statistics.median(gaps)) if len(gaps) >= 2 else None
            s["cats"] = ", ".join(f"{k} {v}" for k, v in s["cats"].most_common())

        dev_frames = Counter(r["dev"] or "(unknown)" for r in recs)
        dev_stations: dict[str, set] = defaultdict(set)
        for r in recs:
            dev_stations[r["dev"] or "(unknown)"].add(r["origin"])

        digis = Counter(d for r in recs for d in r["digis"])
        chains = Counter(" → ".join(r["digis"]) for r in recs if r["digis"])
        hops = Counter(len(r["digis"]) for r in recs)

        igates: dict[str, dict] = {}
        for r in recs:
            if r["gate"]:
                g = igates.setdefault(r["gate"], {"call": r["gate"], "n": 0, "stations": set()})
                g["n"] += 1
                g["stations"].add(r["origin"])

        ctry = Counter(country(r["origin"]) for r in recs)
        ctry_st: dict[str, set] = defaultdict(set)
        for r in recs:
            ctry_st[country(r["origin"])].add(r["origin"])

        rng = {"have_home": bool(self.home)}
        if self.home:
            direct, via = None, None
            buckets = Counter()
            edges = [25, 50, 100, 200, 400]
            seen_d: dict[str, float] = {}
            for r in recs:
                if r["lat"] is None:
                    continue
                d = _dist(self.home, (r["lat"], r["lon"]))
                seen_d[r["origin"]] = d
                is_direct = r["heard"] == r["src"] and not r["gate"]
                cand = {"call": r["origin"], "km": round(d)}
                if is_direct and (direct is None or d > direct["km"]):
                    direct = cand
                if not is_direct and (via is None or d > via["km"]):
                    via = cand
            for d in seen_d.values():
                label = next((f"< {e} km" for e in edges if d < e), f"≥ {edges[-1]} km")
                buckets[label] += 1
            order = [f"< {e} km" for e in edges] + [f"≥ {edges[-1]} km"]
            rng.update({"farthest_direct": direct, "farthest_via": via,
                        "buckets": [[b, buckets.get(b, 0)] for b in order]})

        slot = 300 if window and window <= 3600 else 3600 if (window and window <= 86400) or span <= 2 * 86400 \
            else 6 * 3600
        t0 = recs[0]["t"] if recs and not window else start
        first = math.floor(t0 / slot) * slot
        nslots = max(1, math.ceil((now - first) / slot))
        tl = [0] * nslots
        for r in recs:
            i = int((r["t"] - first) // slot)
            if 0 <= i < nslots:
                tl[i] += 1

        return {
            "window": window, "since": start, "now": now, "kept_since": self.since,
            "totals": {"frames": n, "stations": len(senders), "heard": len(heard),
                       "per_min": round(n / (span / 60), 2), "bytes": sum(r["nbytes"] for r in recs),
                       "air_sec": round(air), "busy_pct": round(100 * air / span, 1),
                       "inet": sum(1 for r in recs if r["gate"])},
            "heard": [{"call": c, "n": k, "pct": round(100 * k / n, 1) if n else 0, "last": last_heard[c]}
                      for c, k in top(heard)],
            "senders": sorted(senders.values(), key=lambda s: -s["n"])[:100],
            "devices": [{"dev": d, "n": k, "stations": len(dev_stations[d])} for d, k in top(dev_frames)],
            "types": [{"cat": c, "n": k, "pct": round(100 * k / n, 1) if n else 0}
                      for c, k in Counter(r["cat"] for r in recs).most_common()],
            "digis": [{"call": c, "n": k} for c, k in top(digis, 30)],
            "chains": [{"chain": c, "n": k} for c, k in top(chains, 15)],
            "hops": [[h, hops[h]] for h in sorted(hops)],
            "igates": [{"call": g["call"], "n": g["n"], "stations": len(g["stations"]),
                        "pct": round(100 * g["n"] / n, 1) if n else 0}
                       for g in sorted(igates.values(), key=lambda g: -g["n"])],
            "range": rng,
            "countries": [{"country": c, "n": k, "stations": len(ctry_st[c])} for c, k in ctry.most_common()],
            "timeline": {"slot": slot, "first": first, "counts": tl},
            "sins": self._sins(recs, n, span),
        }

    # --- what burdens the channel ---------------------------------------------------
    def _sins(self, recs: list[dict], n: int, span: float) -> list[dict]:
        sins: list[dict] = []
        by = defaultdict(list)
        for r in recs:
            by[r["origin"]].append(r)

        def add(call, kind, text, count, weight):
            sins.append({"call": call, "kind": kind, "text": text, "count": count, "weight": weight})

        what = {"tdef": "telemetry definitions (PARM/UNIT/EQNS/BITS)", "status": "status", "position": "position report",
                "object": "object", "weather": "weather report"}
        for call, rs in by.items():
            often = False
            # 1) beacons too often while standing still
            pos = [r for r in rs if r["cat"] in ("position", "mice", "weather") and r["lat"] is not None]
            if len(pos) >= 3:
                still = max(abs(r["lat"] - pos[0]["lat"]) + abs(r["lon"] - pos[0]["lon"]) for r in pos) < 0.001
                gaps = [b["t"] - a["t"] for a, b in zip(pos, pos[1:])]
                med = statistics.median(gaps)
                if still and med < 300:
                    often = True
                    add(call, "too often", f"position every {_fmt_interval(med)} while standing still "
                        f"(10–30 min is enough)", len(pos), len(pos) * 300 / max(med, 1))
                elif not still and med < 30:
                    often = True
                    add(call, "too often", f"position every {_fmt_interval(med)} while moving "
                        f"(smart beaconing: ≥ 1 min)", len(pos), len(pos) * 30 / max(med, 1))
            # 2) the same packet again and again (timestamps ignored)
            same = defaultdict(list)
            cat_of = {}
            for r in rs:
                if r["cat"] not in ("telemetry", "message"):
                    same[r["h"]].append(r["t"])
                    cat_of[r["h"]] = r["cat"]
            worst = None
            for h, ts in same.items():
                gaps = [b - a for a, b in zip(ts, ts[1:]) if b - a > 30]     # < 30 s: heard twice
                if len(gaps) >= 2 and statistics.median(gaps) < 600:
                    med = statistics.median(gaps)
                    if worst is None or len(ts) > worst[1]:
                        worst = (cat_of[h], len(ts), med)
            if worst and not (often and worst[0] in ("position", "mice", "weather")):
                cat, k, med = worst
                if cat == "tdef":
                    text = f"{what[cat]} every {_fmt_interval(med)} (once an hour is enough)"
                else:
                    text = (f"the same {what.get(cat, 'packet')} every {_fmt_interval(med)} "
                            f"(fixed stations: every 10–30 min)")
                add(call, "unchanged repeat", text, k, k * 600 / max(med, 1) / 2)
            # 3) long path
            k = sum(1 for r in rs if "longpath" in r["flags"])
            if k:
                hops = max(r["req"] for r in rs if "longpath" in r["flags"])
                add(call, "long path", f"asks for {hops} hops (mobiles 2, fixed stations 1 or none)",
                    k, k * hops)
            # 4) wrong clock
            k = sum(1 for r in rs if "clock" in r["flags"])
            if k:
                add(call, "wrong clock", "timestamp far from the real time (no GPS time?)", k, k * 0.5)
            # 5) broken packets
            k = sum(1 for r in rs if "malformed" in r["flags"])
            if k:
                add(call, "malformed", "fields that do not follow the APRS format", k, k * 0.5)
        # 6) much internet traffic on the air
        gates = Counter(r["gate"] for r in recs if r["gate"])
        for g, k in gates.items():
            share = 100 * k / n if n else 0
            per_h = k * 3600 / span
            if share >= 5 or per_h >= 30:
                add(g, "internet → radio", f"gates {k} internet packets to the air ({share:.0f} % of the "
                    f"channel, {per_h:.0f}/h) - only messages for local stations should go out", k, k)
        sins.sort(key=lambda s: -s["weight"])
        for s in sins:
            del s["weight"]
        return sins
