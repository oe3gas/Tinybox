"""Daily DX digest: the last N hours of spots condensed into one bulletin.

Relevance filter (dxfeed.conf [digest]):
  * spotter on one of spotter_continents (default EU): heard from here
  * band in bands (default 160m ... 4m)
  * DXCC entity known and not in exclude (the entities on the air every day);
    on all_dxcc_bands (default 2m 70cm) every entity counts, since DX on
    VHF/UHF from here is mostly Europe
One line per DX call: entity, bands, modes, first/last time, number of
different spotters. Calls seen by fewer than min_spotters stations are only
counted (often busted calls). Then the band activity of all spots from the
spotter continents, as a rough picture of yesterday's propagation.

The text stays below max_bytes (it goes over the air via brocast): table lines
are dropped from the end until it fits. Plain ASCII, lines below 80 columns.
"""

from __future__ import annotations

import os
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .config import DigestCfg
from .spots import BAND_ORDER

BAR_WIDTH = 24


@dataclass
class DxLine:
    call: str
    name: str
    bands: set[str] = field(default_factory=set)
    modes: set[str] = field(default_factory=set)
    spotters: set[str] = field(default_factory=set)
    first: int = 0
    last: int = 0
    count: int = 0


@dataclass
class Digest:
    subject: str
    text: str
    replace: str
    lines: int          # table lines shown
    spots: int          # spots in the window (all)


HF_BANDS = {"160m", "80m", "60m", "40m", "30m", "20m", "17m", "15m", "12m", "10m"}


def _short_band(band: str) -> str:
    """HF without unit (20 17 15), VHF/UHF with it (6m 2m 70cm) - "2" would be unclear."""
    return band[:-1] if band in HF_BANDS else band


def time_span(first: int, last: int) -> str:
    """UTC day/time: 15/0912, 15/0912-1840, 14/1953-15/1928 (over midnight)."""
    a, b = time.gmtime(first), time.gmtime(last)
    start = time.strftime("%d/%H%M", a)
    if first // 60 == last // 60:
        return start
    if a.tm_yday == b.tm_yday:
        return f"{start}-{time.strftime('%H%M', b)}"
    return f"{start}-{time.strftime('%d/%H%M', b)}"


def _fit(text: str, width: int) -> str:
    return text if len(text) <= width else text[:width - 1] + "+"


def aggregate(rows, cfg: DigestCfg) -> tuple[list[DxLine], int]:
    """Relevant spots -> one DxLine per DX call, plus the number of relevant spots."""
    by_call: dict[str, DxLine] = {}
    n = 0
    for r in rows:
        if cfg.spotter_continents and r["sp_cont"] not in cfg.spotter_continents:
            continue
        if r["band"] not in cfg.bands:
            continue
        if not r["dx_prefix"]:
            continue
        if r["band"] not in cfg.all_dxcc_bands and r["dx_prefix"] in cfg.exclude:
            continue
        n += 1
        d = by_call.get(r["dx"])
        if d is None:
            d = by_call[r["dx"]] = DxLine(call=r["dx"], name=r["dx_name"], first=r["ts"])
        d.bands.add(r["band"])
        if r["mode"]:
            d.modes.add(r["mode"])
        d.spotters.add(r["spotter"])
        d.first = min(d.first, r["ts"])
        d.last = max(d.last, r["ts"])
        d.count += 1
    lines = sorted(by_call.values(), key=lambda d: (-len(d.spotters), -d.count, d.call))
    return lines, n


def band_activity(rows, cfg: DigestCfg) -> list[str]:
    """One line per band with spots: count, bar, hour (UTC) with most spots."""
    counts: Counter[str] = Counter()
    hours: dict[str, Counter[int]] = defaultdict(Counter)
    for r in rows:
        if cfg.spotter_continents and r["sp_cont"] not in cfg.spotter_continents:
            continue
        if r["band"] not in cfg.bands:
            continue
        counts[r["band"]] += 1
        hours[r["band"]][time.gmtime(r["ts"]).tm_hour] += 1
    if not counts:
        return ["  (keine Spots)"]
    top = max(counts.values())
    out = []
    for band in BAND_ORDER:
        if band not in cfg.bands:
            continue
        n = counts.get(band, 0)
        if n == 0:
            out.append(f"  {band:>4} {0:>5}")
            continue
        bar = "#" * max(1, round(n / top * BAR_WIDTH))
        peak = hours[band].most_common(1)[0][0]
        out.append(f"  {band:>4} {n:>5} {bar:<{BAR_WIDTH}} {peak:02d}z")
    return out


def table_line(d: DxLine) -> str:
    bands = " ".join(_short_band(b) for b in BAND_ORDER if b in d.bands)
    modes = " ".join(sorted(d.modes)) or "?"
    return (f"{_fit(d.call, 10):<10} {_fit(d.name, 17):<17} {_fit(bands, 11):<11} "
            f"{_fit(modes, 8):<8} {time_span(d.first, d.last):<15} {len(d.spotters):>2}").rstrip()


def build(rows, cfg: DigestCfg, since: float, until: float, coverage_sec: float,
          node: str = "") -> Digest | None:
    """None if there is nothing to report (no spots at all in the window)."""
    if not rows:
        return None
    lines, n_rel = aggregate(rows, cfg)
    shown = [d for d in lines if len(d.spotters) >= cfg.min_spotters]
    single = len(lines) - len(shown)
    entities = len({d.name for d in lines})

    t0, t1 = datetime.fromtimestamp(since), datetime.fromtimestamp(until)
    window_h = (until - since) / 3600
    conts = "/".join(sorted(cfg.spotter_continents)) or "allen Kontinenten"
    head = [f"DX-Zusammenfassung {t0:%d.%m.%Y %H:%M} - {t1:%d.%m.%Y %H:%M} Lokalzeit",
            f"Spots von Stationen in {conts}, ohne haeufige DXCC-Gebiete"
            + (f" (auf {' '.join(b for b in BAND_ORDER if b in cfg.all_dxcc_bands and b in cfg.bands)}"
               " alle)." if cfg.all_dxcc_bands & set(cfg.bands) else "."),
            f"{len(rows)} Spots gesamt, davon {n_rel} relevant: {len(lines)} DX-Rufzeichen "
            f"aus {entities} Gebieten."]
    if coverage_sec < 0.9 * (until - since):
        head.append(f"Achtung: Cluster nur {coverage_sec / 3600:.1f} von {window_h:.0f} h "
                    "verbunden - unvollstaendig.")

    table_head = ["Zeit: Tag/UTC erster-letzter Spot, Sp: verschiedene Spotter.", "",
                  f"{'Call':<10} {'Gebiet':<17} {'Baender':<11} {'Modes':<8} {'Zeit UTC':<15} Sp",
                  "-" * 69]
    tail_parts = ["", "Bandaktivitaet (alle Spots, Spitze in UTC):", *band_activity(rows, cfg),
                  "", "Quelle: DX-Cluster" + (f" {node}" if node else "")
                  + ", Laenderdaten AD1C cty.dat. TinyBox dxfeed."]

    rows_out = [table_line(d) for d in shown[:cfg.max_lines]]
    hidden = len(shown) - len(rows_out)

    def compose() -> str:
        body = list(head) + [""]
        if rows_out:
            body += table_head + rows_out
        else:
            body.append("Keine seltenen DX-Spots im Zeitraum.")
        more = []
        if hidden:
            more.append(f"{hidden} weitere mit {cfg.min_spotters}+ Spottern nicht gezeigt")
        if single:
            more.append(f"{single} Rufzeichen mit weniger als {cfg.min_spotters} Spottern "
                        "ausgelassen")
        if more:
            body.append("(" + "; ".join(more) + ")")
        return "\n".join(body + tail_parts) + "\n"

    text = compose()
    while len(text.encode("ascii", "replace")) > cfg.max_bytes and rows_out:
        rows_out.pop()
        hidden += 1
        text = compose()

    return Digest(subject=f"DX-Zusammenfassung {t1:%d.%m.%Y}",
                  text=text, replace=f"dxfeed-{t1:%Y%m%d}",
                  lines=len(rows_out), spots=len(rows))


def write_inbox(directory: str | Path, d: Digest, cfg: DigestCfg) -> Path:
    """Bulletin file for the TinyBox inbox folder: .tmp first, then rename.
    No @ address: the bulletin stays in this mailbox (local only)."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    head = {"To": cfg.to, "Subject": d.subject, "Replace": d.replace}
    if cfg.valid:
        head["Valid"] = cfg.valid
    content = "".join(f"{k}: {v}\n" for k, v in head.items()) + "\n" + d.text
    name = d.replace.replace("-", "_")
    tmp = directory / f"{name}.tmp"
    tmp.write_text(content, encoding="ascii", errors="replace")
    target = directory / f"{name}.txt"
    os.replace(tmp, target)
    return target
