"""dxfeed live: short-lived DX pages next to the 24 h overview (PLANUNG 16c).

Run every 10 minutes ("python -m dxfeed live --tinybox"). Each run decides
itself what is due, from a small state file (written only when it changes,
which spares the SD card of the feeder Pi):

  DX jetzt         the most relevant stations (tiers A/B, at most 8) of the
                   last 2 hours, checked every 30 minutes and sent only when
                   the set of stations or bands changed (or the last one is
                   about to expire). Replace: dxfeed-jetzt, Valid 2h.
  Baender jetzt    spots of the last hour per band and continent of the DX
                   station: ALL entities (CE, LU ... tell the path to South
                   America), spotters on the spotter continents only. Hourly.
                   Replace: dxfeed-baender, Valid 90m.
  Neu auf dem Band a rare entity (Club Log rank <= new_max_rank) spotted by
                   at least new_min_spotters stations within new_window
                   minutes, and not at all in the new_quiet_hours before.
                   One bulletin per call and day, at most new_per_hour per
                   hour. Replace: dxfeed-neu-<call>, Valid 2h.

All of them are mailbox bulletins with a brocast page typ dxsum (kind now,
paths, new; dictionary v5), like the 24 h overview. Replace keeps one
bulletin per kind (per call for "neu"), Valid lets them run out by themselves.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

from . import dxcc as dxccmod
from . import mostwanted as mwmod
from .config import Config
from .digest import (Bulletin, DxLine, _dat_head, _fit, _page, aggregate,
                     by_relevance, rate, relevant, station_page, utc_hm)
from .spots import BAND_ORDER

log = logging.getLogger(__name__)

CONTS = ("AF", "AN", "AS", "EU", "NA", "OC", "SA")    # dictionary v5: dxsum path columns
REPLACE_NOW = "dxfeed-jetzt"
REPLACE_BANDS = "dxfeed-baender"
REPLACE_NEW = "dxfeed-neu-"
KEY_CHARS = re.compile(r"[^A-Za-z0-9._-]")


# ---------------------------------------------------------------------------
# state
# ---------------------------------------------------------------------------

class State:
    """{"now": {"checked", "sent", "sig"}, "bands": {"checked"},
        "new": {"calls": {call: ts}, "sent": [ts, ...]}} - Unix seconds."""

    def __init__(self, path: Path) -> None:
        self.path = path
        try:
            self.data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(self.data, dict):
                raise ValueError("no object")
        except (OSError, ValueError):
            self.data = {}
        self._saved = json.dumps(self.data, sort_keys=True)

    def part(self, name: str) -> dict:
        p = self.data.get(name)
        if not isinstance(p, dict):
            p = self.data[name] = {}
        return p

    def save(self) -> None:
        text = json.dumps(self.data, sort_keys=True)
        if text == self._saved:
            return                                  # nothing changed: no write
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, self.path)
        self._saved = text


def due(part: dict, every_min: int, now: float) -> bool:
    return now - float(part.get("checked", 0)) >= every_min * 60 - 30   # 30 s jitter


# ---------------------------------------------------------------------------
# DX jetzt
# ---------------------------------------------------------------------------

def _mode_text(d: DxLine) -> str:
    return d.last_mode or "?"


def now_bulletin(rows, cfg: Config, mw, dxcc, now: float) -> tuple[Bulletin, list]:
    """The stations of the last now_hours. Returns the bulletin and its signature
    (calls with bands), which decides whether anything changed."""
    lc, dc = cfg.live, cfg.digest
    since = now - lc.now_hours * 3600
    lines, n_rel = aggregate([r for r in rows if r["ts"] >= since], dc)
    rate(lines, dc, mw, dxcc)
    shown = [d for d in by_relevance(lines) if len(d.spotters) >= dc.min_spotters]
    rated = mw is not None
    sel = [d for d in shown if d.tier in lc.now_tiers] if rated else shown
    sel = sorted(sel[:lc.now_max_rows], key=lambda d: d.call)
    sig = [[d.call, sorted(d.bands)] for d in sel]
    hours = f"{lc.now_hours:g}"
    page = station_page(sel, dc, since, now, len(lines), n_rel, None, rated,
                        title=f"DX jetzt ({hours} h bis {utc_hm(now)} UTC)",
                        valid=lc.now_valid, with_qrg=True, tiers=lc.now_tiers)
    page["blk"][0]["v"]["kind"] = "now"
    conts = "/".join(sorted(dc.spotter_continents)) or "allen Kontinenten"
    text = [f"DX jetzt: die letzten {hours} Stunden bis {utc_hm(now)} UTC, Spotter in {conts}.",
            ("Relevanz " + "/".join(lc.now_tiers) + " nach Club Log Most Wanted und Spotterzahl."
             if rated else "Ohne Most-Wanted-Liste: die meistgespotteten."), ""]
    if sel:
        text += [f"R {'Call':<10} {'Gebiet':<16} {'QRG':>8} {'Mode':<5} {'zuletzt':<7} Sp  MW",
                 "-" * 64]
        for d in sel:
            rank = "-" if d.rank is None else str(d.rank)
            text.append(f"{d.tier} {_fit(d.call, 10):<10} {_fit(d.name, 16):<16} {d.qrg:>8.1f} "
                        f"{_fit(_mode_text(d), 5):<5} {utc_hm(d.last):<7} {len(d.spotters):>2} "
                        f"{rank:>3}".rstrip())
    else:
        text.append("Gerade keine DX-Station dieser Relevanz.")
    text += ["", "Wird alle 30 Minuten erneuert, wenn sich etwas aendert. TinyBox dxfeed."]
    b = Bulletin(subject=f"DX jetzt bis {utc_hm(now)} UTC", text="\n".join(text) + "\n",
                 replace=REPLACE_NOW, page=page if dc.brocast else None, valid=lc.now_valid)
    return b, sig


# ---------------------------------------------------------------------------
# Baender jetzt
# ---------------------------------------------------------------------------

def path_counts(rows, cfg: Config) -> tuple[dict[str, list[int]], int]:
    """Band -> spots per DX continent (CONTS). All entities, also the excluded
    ones: what counts is the path. Spotters on the spotter continents only."""
    dc = cfg.digest
    out: dict[str, list[int]] = {}
    n = 0
    for r in rows:
        if dc.spotter_continents and r["sp_cont"] not in dc.spotter_continents:
            continue
        if r["band"] not in dc.bands or r["dx_cont"] not in CONTS:
            continue
        out.setdefault(r["band"], [0] * len(CONTS))[CONTS.index(r["dx_cont"])] += 1
        n += 1
    return out, n


def bands_bulletin(rows, cfg: Config, now: float) -> Bulletin | None:
    since = now - 3600
    counts, n = path_counts([r for r in rows if r["ts"] >= since], cfg)
    if not n:
        return None                                 # collector down or band dead: nothing
    dc = cfg.digest
    dat = _dat_head(dc, now, since)
    dat.update({"kind": "paths", "spots": n,
                "path": [[b, *counts[b]] for b in BAND_ORDER if b in counts]})
    page = _page(f"DX-Bänder jetzt (1 h bis {utc_hm(now)} UTC)", dat, dc, cfg.live.bands_valid)
    conts = "/".join(sorted(dc.spotter_continents)) or "allen Kontinenten"
    text = [f"DX-Baender jetzt: {n} Spots der letzten Stunde bis {utc_hm(now)} UTC,",
            f"Spotter in {conts}, alle DXCC-Gebiete, nach Kontinent der DX-Station.", "",
            "Band  " + " ".join(f"{c:>4}" for c in CONTS), "-" * 41]
    for b in BAND_ORDER:
        if b in counts:
            text.append(f"{b:>4}  "
                        + " ".join(f"{x:>4}" if x else "   ." for x in counts[b]))
    text += ["", "Stuendlich erneuert. TinyBox dxfeed."]
    b = Bulletin(subject=f"DX-Baender jetzt bis {utc_hm(now)} UTC", text="\n".join(text) + "\n",
                 replace=REPLACE_BANDS, page=page if dc.brocast else None,
                 valid=cfg.live.bands_valid)
    return b


# ---------------------------------------------------------------------------
# Neu auf dem Band
# ---------------------------------------------------------------------------

def new_candidates(rows, cfg: Config, mw, dxcc, now: float) -> list[DxLine]:
    """Rare calls that just appeared: rank <= new_max_rank, enough spotters in the
    window, no spot at all in the quiet hours before the window. Rarest first."""
    lc, dc = cfg.live, cfg.digest
    start = now - lc.new_window * 60
    quiet_from = start - lc.new_quiet_hours * 3600
    recent = [r for r in rows if r["ts"] >= start]
    lines, _ = aggregate(recent, dc)
    rate(lines, dc, mw, dxcc)
    seen_before = {r["dx"] for r in rows
                   if quiet_from <= r["ts"] < start and relevant(r, dc)}
    out = [d for d in lines
           if d.rank is not None and d.rank <= lc.new_max_rank
           and len(d.spotters) >= lc.new_min_spotters and d.call not in seen_before]
    return sorted(out, key=lambda d: (d.rank, -len(d.spotters), d.call))


def new_bulletin(d: DxLine, cfg: Config, now: float) -> Bulletin:
    lc, dc = cfg.live, cfg.digest
    since = now - lc.new_window * 60
    page = station_page([d], dc, since, now, 1, d.count, None, True,
                        title=_fit(f"Neu: {d.call} {d.name}", 40), valid=lc.new_valid,
                        with_qrg=True, tiers=d.tier)
    page["blk"][0]["v"]["kind"] = "new"
    rank = f"Most Wanted {d.rank}" if d.rank is not None else "Most Wanted ?"
    text = [f"Neu auf dem Band: {d.call}  {d.name} ({rank})",
            f"Zuletzt {d.qrg:.1f} kHz {_mode_text(d)} um {utc_hm(d.last)} UTC, "
            f"{len(d.spotters)} Spotter in {lc.new_window} min",
            f"(erster Spot {utc_hm(d.first)} UTC). In den {lc.new_quiet_hours} Stunden davor "
            "nicht gespottet.",
            "", "Baender: " + " ".join(b for b in BAND_ORDER if b in d.bands),
            "", "TinyBox dxfeed."]
    b = Bulletin(subject=_fit(f"DX neu: {d.call} {d.name} {d.qrg:.0f} {_mode_text(d)}", 60),
                 text="\n".join(text) + "\n",
                 replace=REPLACE_NEW + KEY_CHARS.sub("_", d.call),
                 page=page if dc.brocast else None, valid=lc.new_valid)
    return b


# ---------------------------------------------------------------------------
# one run
# ---------------------------------------------------------------------------

@dataclass
class LiveResult:
    bulletins: list[Bulletin]
    notes: list[str]


def run(rows, cfg: Config, state: State | None, now: float, mw: mwmod.MostWanted | None,
        dxcc: dxccmod.DxccList | None, force: bool = False) -> LiveResult:
    """What is due now. rows: spots of at least the last new_quiet_hours +
    new_window (and now_hours). state None (or force): everything, nothing kept."""
    lc = cfg.live
    out: list[Bulletin] = []
    notes: list[str] = []
    st = state if state is not None else State(Path(os.devnull))

    if lc.now:
        part = st.part("now")
        if force or due(part, lc.now_every, now):
            b, sig = now_bulletin(rows, cfg, mw, dxcc, now)
            part["checked"] = now
            old = part.get("sig")
            stale = now - float(part.get("sent", 0)) >= lc.now_refresh * 60
            if force or sig != old or (stale and sig):
                out.append(b)
                part.update(sent=now, sig=sig)
                notes.append(f"jetzt: gesendet ({len(sig)})")
            else:
                notes.append("jetzt: unveraendert")

    if lc.bands:
        part = st.part("bands")
        if force or due(part, lc.bands_every, now):
            part["checked"] = now
            b = bands_bulletin(rows, cfg, now)
            if b is not None:
                out.append(b)
                notes.append("baender: gesendet")
            else:
                notes.append("baender: keine Spots in der letzten Stunde")

    if lc.new:
        if mw is None:
            notes.append("neu: ohne Most-Wanted-Liste aus")
        else:
            part = st.part("new")
            calls = {c: t for c, t in (part.get("calls") or {}).items()
                     if now - float(t) < 86400}                   # once per call and day
            sent = [t for t in (part.get("sent") or []) if now - float(t) < 3600]
            for d in new_candidates(rows, cfg, mw, dxcc, now):
                if d.call in calls:
                    continue
                if len(sent) >= lc.new_per_hour and not force:
                    notes.append(f"neu: {d.call} zurueckgestellt (Limit {lc.new_per_hour}/h)")
                    break
                out.append(new_bulletin(d, cfg, now))
                calls[d.call] = now
                sent.append(now)
                notes.append(f"neu: {d.call} ({d.name}, Rang {d.rank})")
            part["calls"], part["sent"] = calls, sent

    if state is not None:
        state.save()
    return LiveResult(out, notes)


def window_start(cfg: Config, now: float) -> float:
    """Earliest spot a live run needs."""
    lc = cfg.live
    return now - max(lc.now_hours * 3600, 3600, lc.new_window * 60 + lc.new_quiet_hours * 3600)

