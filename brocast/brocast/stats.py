"""Statistik-Zähler der Station (13.11.2026): was 24 h lang auf dem Kanal los war.

Das Sendeprotokoll (txlog.py) hält jede eigene Aussendung fest. Was es nicht
weiß und was dieser Zähler sammelt, je Stunde (UTC):

  * Laufzeit von brocastd in der Stunde (Datenbasis, Lücken nach Neustarts)
  * fremder Verkehr, den brocastd auf dem Kanal hört: UI-Frames (APRS, Baken,
    andere brocast-Stationen) und Frames von Verbindungen (I/S/U), Bytes,
    geschätzte Sendezeit, Rufzeichen
  * eigene Sendezeit (Seiten, Bake) – Rückfall, wenn das Sendeprotokoll aus ist
  * wie lange die Sendung zurückgestellt war und warum (busy / channel /
    budget / link) und wie lange die TinyBox Stufe 1 oder 2 gemeldet hat
  * Verspätung: wie lange eine fällige Seite tatsächlich auf ihre Aussendung
    gewartet hat (Senden – geplanter Termin)
  * höchste Ausnutzung des Airtime-Budgets

Alles liegt im RAM und wird mit dem normalen Flush von brocastd (db_flush_sec,
Standard 600 s) und beim Beenden als kleine JSON-Datei gesichert
(data/statistik.json, einige kB, atomar ersetzt). Gehalten werden 48 h.
Die Auswertung macht advisor.py.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable

from .frame import airtime_s

log = logging.getLogger(__name__)

KEEP_H = 48                 # Stunden im Speicher und in der Datei
MAX_TICK_S = 90.0           # längere Lücken zwischen zwei Takten zählen nicht (Stillstand)
SAME_TX_S = 1.0             # fremde Frames derselben Station so dicht hintereinander: eine Aussendung
MAX_CALLS = 60              # Rufzeichen je Stunde (nur zum Zählen)
LATE_S = 60                 # ab so viel Verspätung zählt eine Aussendung als "spät"
HOLDS = ("busy", "channel", "budget", "link")
FILE_VERSION = 1


def _bucket(hour: int) -> dict[str, Any]:
    return {"h": hour, "run_s": 0.0, "lvl1_s": 0.0, "lvl2_s": 0.0,
            "hold": {k: 0.0 for k in HOLDS},
            "ui": 0, "conn": 0, "fbytes": 0, "fair_s": 0.0, "calls": [],
            "own_s": 0.0, "own_frames": 0, "own_pages": 0, "beacon_s": 0.0,
            "late_n": 0, "late_sum_s": 0.0, "late_max_s": 0.0, "late_over": 0,
            "sends": 0, "budget_peak_s": 0.0}


class Stats:
    def __init__(self, path: Path | None, baud: int, txdelay_ms: int,
                 clock: Callable[[], float]):
        self.path = Path(path) if path else None
        self.baud, self.txdelay_ms, self.clock = baud, txdelay_ms, clock
        self.buckets: dict[int, dict[str, Any]] = {}
        self.dirty = False
        self._tick_at: float | None = None
        self._last_src = ""
        self._last_end = 0.0

    # --- buckets -----------------------------------------------------------------

    def _b(self, ts: float) -> dict[str, Any]:
        hour = int(ts // 3600)
        b = self.buckets.get(hour)
        if b is None:
            b = self.buckets[hour] = _bucket(hour)
            for old in [h for h in self.buckets if h <= hour - KEEP_H]:
                del self.buckets[old]
        self.dirty = True
        return b

    def _spread(self, start: float, end: float, add: Callable[[dict, float], None]) -> None:
        """A duration over hour boundaries: each hour gets its share."""
        t = start
        while t < end:
            nxt = min(end, (int(t // 3600) + 1) * 3600)
            add(self._b(t), nxt - t)
            t = nxt

    # --- what the carousel and the daemon report ---------------------------------

    def tick(self, now: float, level: int, hold: str | None, budget_spent: float) -> None:
        """Called by the carousel at every step: the time since the last step had
        this state (TinyBox level, why sending was held, if it was)."""
        last, self._tick_at = self._tick_at, now
        b = self._b(now)
        b["budget_peak_s"] = max(b["budget_peak_s"], round(budget_spent, 1))
        if last is None or now <= last:
            return
        dt = now - last
        if dt > MAX_TICK_S:                          # standstill (sleep, debugger): not counted
            return

        def add(bk: dict, d: float) -> None:
            bk["run_s"] += d
            if level == 1:
                bk["lvl1_s"] += d
            elif level >= 2:
                bk["lvl2_s"] += d
            if hold in bk["hold"]:
                bk["hold"][hold] += d
        self._spread(last, now, add)

    def foreign(self, now: float, src: str, kind: str, nbytes: int) -> None:
        """A frame of another station on our channel."""
        b = self._b(now)
        if kind in ("I", "S", "U"):
            b["conn"] += 1
        else:
            b["ui"] += 1
        b["fbytes"] += nbytes
        # TXDELAY once per transmission: frames of the same station right after
        # each other were one PTT cycle
        same = src == self._last_src and now - self._last_end < SAME_TX_S
        air = airtime_s(nbytes, self.baud, 0 if same else self.txdelay_ms)
        b["fair_s"] += air
        self._last_src, self._last_end = src, now + air
        if src not in b["calls"] and len(b["calls"]) < MAX_CALLS:
            b["calls"].append(src)

    def own(self, now: float, airtime: float, frames: int, beacon: bool = False) -> None:
        b = self._b(now)
        b["own_s"] += airtime
        b["own_frames"] += frames
        if beacon:
            b["beacon_s"] += airtime
        else:
            b["own_pages"] += 1

    def late(self, now: float, seconds: float) -> None:
        """A page went out `seconds` after its planned time."""
        b = self._b(now)
        seconds = max(0.0, seconds)
        b["sends"] += 1
        if seconds >= 1:
            b["late_n"] += 1
            b["late_sum_s"] += seconds
            b["late_max_s"] = max(b["late_max_s"], round(seconds))
            if seconds >= LATE_S:
                b["late_over"] += 1

    # --- reading -----------------------------------------------------------------

    def window(self, now: float, hours: int = 24) -> list[dict[str, Any]]:
        """The last `hours` full and current hours, oldest first (missing = empty)."""
        cur = int(now // 3600)
        out = []
        for h in range(cur - hours + 1, cur + 1):
            b = self.buckets.get(h)
            out.append(json.loads(json.dumps(b)) if b else _bucket(h))
        return out

    # --- file --------------------------------------------------------------------

    def load(self) -> None:
        if self.path is None or not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            now_h = int(self.clock() // 3600)
            for b in data.get("buckets", []):
                h = int(b["h"])
                if h > now_h - KEEP_H:
                    full = _bucket(h)
                    full.update({k: v for k, v in b.items() if k in full})
                    full["hold"] = {**_bucket(h)["hold"], **(b.get("hold") or {})}
                    self.buckets[h] = full
        except (OSError, ValueError, KeyError, TypeError) as exc:
            log.warning("Statistik %s nicht lesbar, beginne neu: %s", self.path, exc)

    def save(self) -> bool:
        """Write the file if something changed. True = written."""
        if self.path is None or not self.dirty:
            return False
        data = {"version": FILE_VERSION, "saved": round(self.clock()),
                "buckets": [self._rounded(self.buckets[h]) for h in sorted(self.buckets)]}
        tmp = self.path.with_suffix(".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
            os.replace(tmp, self.path)
            self.dirty = False
            return True
        except OSError as exc:             # never stop brocastd because of the statistics
            log.error("Statistik nicht schreibbar (%s): %s", self.path, exc)
            return False

    @staticmethod
    def _rounded(b: dict[str, Any]) -> dict[str, Any]:
        out = {}
        for k, v in b.items():
            if isinstance(v, float):
                out[k] = round(v, 1)
            elif k == "hold":
                out[k] = {h: round(s, 1) for h, s in v.items()}
            else:
                out[k] = v
        return out


def load_file(path: Path) -> dict[int, dict[str, Any]]:
    """The saved buckets without a running brocastd (command line)."""
    st = Stats(path, 1200, 0, clock=lambda: 0.0)
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    for b in data.get("buckets", []):
        try:
            full = _bucket(int(b["h"]))
        except (KeyError, TypeError, ValueError):
            continue
        full.update({k: v for k, v in b.items() if k in full})
        full["hold"] = {**_bucket(0)["hold"], **(b.get("hold") or {})}
        st.buckets[full["h"]] = full
    return st.buckets
