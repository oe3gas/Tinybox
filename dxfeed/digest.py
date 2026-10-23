"""Daily DX digest: the last N hours of spots condensed into one bulletin.

Relevance filter (dxfeed.conf [digest]):
  * spotter on one of spotter_continents (default EU): heard from here
  * band in bands (default 160m ... 4m)
  * DXCC entity known and not in exclude (the entities on the air every day);
    on all_dxcc_bands (default 2m 70cm) every entity counts, since DX on
    VHF/UHF from here is mostly Europe
One line per DX call: relevance, entity, bands, modes, first/last time, number
of different spotters, Club Log Most Wanted rank. Calls seen by fewer than
min_spotters stations are only counted (often busted calls). Then the band
activity of all spots from the spotter continents, split by mode (CW, SSB,
FT8, other - the other modes named), as a rough picture of yesterday's
propagation.

Relevance (PLANUNG.md 16a, mostwanted.py): score = rarity x log2(1 + spotters),
tier A/B/C by relevance_a / relevance_b. The table keeps the most relevant
calls and shows them in alphabetical order.

Two bulletins (PLANUNG 16a/16b): "DX-Zusammenfassung" (the stations) and
"DX-Bandaktivitaet". With [digest] brocast = yes each carries a brocast page
(header "Brocast:", PLANUNG 6d) of typ dxsum (dictionary v4): the stations
page only the tiers in brocast_tiers, entity as ADIF DXCC number, bands per
mode group as bit masks; the listener draws the band/mode grid and the heat
map from them. Each page fits into one or two frames.

The text stays below max_bytes (it goes over the air via brocast): table lines
are dropped from the end until it fits. Plain ASCII, lines below 80 columns.
"""

from __future__ import annotations

import json
import os
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import dxcc as dxccmod
from . import mostwanted as mwmod
from .config import DigestCfg
from .spots import BAND_ORDER

MODE_GROUPS = ("CW", "SSB", "FT8")          # everything else is "other"
ENTITY_TEXT_MAX = 30                        # dictionary: dxcc free_text


def mode_group(mode: str) -> int:
    """0 CW, 1 SSB, 2 FT8, 3 other (FT4, RTTY, FM, unknown ...)."""
    return MODE_GROUPS.index(mode) if mode in MODE_GROUPS else 3


def other_name(mode: str) -> str:
    return mode or "?"


@dataclass
class DxLine:
    call: str
    name: str
    prefix: str = ""
    bands: set[str] = field(default_factory=set)
    modes: set[str] = field(default_factory=set)
    band_modes: dict[str, set[str]] = field(default_factory=dict)
    spotters: set[str] = field(default_factory=set)
    first: int = 0
    last: int = 0
    count: int = 0
    rank: int | None = None         # Club Log Most Wanted, None = unknown
    dxcc: int | None = None         # ADIF DXCC number (brocast dictionary v4), None = unknown
    score: float = 0.0
    tier: str = "C"


@dataclass
class BandActivity:
    band: str
    spots: int = 0
    by_group: list[int] = field(default_factory=lambda: [0, 0, 0, 0])
    others: Counter = field(default_factory=Counter)
    hours: Counter = field(default_factory=Counter)

    @property
    def peak(self) -> int:
        return self.hours.most_common(1)[0][0] if self.hours else 0

    def other_text(self) -> str:
        """FT4 28 RTTY 9 JS8 5 - most frequent first."""
        return " ".join(f"{m} {n}" for m, n in
                        sorted(self.others.items(), key=lambda x: (-x[1], x[0])))


@dataclass
class Bulletin:
    subject: str
    text: str
    replace: str
    page: dict | None = None    # brocast page (header "Brocast:"), None = text only


@dataclass
class Digest:
    subject: str
    text: str
    replace: str
    lines: int          # table lines shown
    spots: int          # spots in the window (all)
    page: dict | None = None    # brocast page of the stations, None = text only
    act: Bulletin | None = None  # second bulletin: band activity (PLANUNG 16b)

    def bulletins(self) -> list[Bulletin]:
        out = [Bulletin(self.subject, self.text, self.replace, self.page)]
        return out + ([self.act] if self.act is not None else [])


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
            d = by_call[r["dx"]] = DxLine(call=r["dx"], name=r["dx_name"],
                                          prefix=r["dx_prefix"], first=r["ts"])
        d.bands.add(r["band"])
        d.band_modes.setdefault(r["band"], set()).add(r["mode"])
        if r["mode"]:
            d.modes.add(r["mode"])
        d.spotters.add(r["spotter"])
        d.first = min(d.first, r["ts"])
        d.last = max(d.last, r["ts"])
        d.count += 1
    lines = sorted(by_call.values(), key=lambda d: (-len(d.spotters), -d.count, d.call))
    return lines, n


def rate(lines: list[DxLine], cfg: DigestCfg, mw: mwmod.MostWanted | None,
         dxcc: dxccmod.DxccList | None = None) -> None:
    """DXCC number, Most Wanted rank, score and tier for every line (in place).
    Club Log writes some prefixes differently from AD1C (1A0 for 1A): the
    dictionary's DXCC list knows both."""
    for d in lines:
        ent = dxcc.find(d.prefix, d.name) if dxcc is not None else None
        d.dxcc = ent.code if ent else None
        if mw is not None:
            d.rank = mw.rank(ent.clublog) if ent else None
            if d.rank is None:
                d.rank = mw.rank(d.prefix)
        else:
            d.rank = None
        d.score = mwmod.score(d.rank, len(d.spotters))
        d.tier = mwmod.tier(d.score, cfg.relevance_a, cfg.relevance_b)


def by_relevance(lines: list[DxLine]) -> list[DxLine]:
    return sorted(lines, key=lambda d: (-d.score, -len(d.spotters), d.call))


def activity(rows, cfg: DigestCfg) -> list[BandActivity]:
    """Spots per band and mode group from the spotter continents (all DX, not
    only the relevant ones), in band order; bands without spots included."""
    acts = {b: BandActivity(b) for b in BAND_ORDER if b in cfg.bands}
    for r in rows:
        if cfg.spotter_continents and r["sp_cont"] not in cfg.spotter_continents:
            continue
        a = acts.get(r["band"])
        if a is None:
            continue
        a.spots += 1
        g = mode_group(r["mode"])
        a.by_group[g] += 1
        if g == 3:
            a.others[other_name(r["mode"])] += 1
        a.hours[time.gmtime(r["ts"]).tm_hour] += 1
    return list(acts.values())


def band_activity(rows, cfg: DigestCfg) -> list[str]:
    """Text: one line per band - spots, per mode group, peak hour (UTC), other modes."""
    acts = activity(rows, cfg)
    if not any(a.spots for a in acts):
        return ["  (keine Spots)"]
    out = [f"  {'Band':>4} {'Spots':>6} {'CW':>4} {'SSB':>4} {'FT8':>4} {'And':>4} "
           "Spitze Andere"]
    for a in acts:
        if not a.spots:
            out.append(f"  {a.band:>4} {0:>6}")
            continue
        cw, ssb, ft8, oth = a.by_group
        out.append((f"  {a.band:>4} {a.spots:>6} {cw:>4} {ssb:>4} {ft8:>4} {oth:>4} "
                    f"{a.peak:02d}z    {_fit(a.other_text(), 30)}").rstrip())
    return out


def table_line(d: DxLine) -> str:
    bands = " ".join(_short_band(b) for b in BAND_ORDER if b in d.bands)
    modes = " ".join(sorted(d.modes)) or "?"
    rank = "-" if d.rank is None else str(d.rank)
    return (f"{d.tier} {_fit(d.call, 10):<10} {_fit(d.name, 16):<16} {_fit(bands, 11):<11} "
            f"{_fit(modes, 8):<8} {time_span(d.first, d.last):<15} {len(d.spotters):>2} "
            f"{rank:>3}").rstrip()


def valid_minutes(valid: str) -> int | None:
    """7d -> 10080, 36h -> 2160, 90m -> 90, empty -> None (rubric default)."""
    if not valid:
        return None
    n, unit = int(valid[:-1]), valid[-1].lower()
    return n * {"m": 1, "h": 60, "d": 1440}[unit]


def _mask(d: DxLine, group: int) -> int:
    """Bands (bit = index in BAND_ORDER) on which the call was spotted in this mode group."""
    m = 0
    for i, band in enumerate(BAND_ORDER):
        if any(mode_group(x) == group for x in d.band_modes.get(band, ())):
            m |= 1 << i
    return m


def _dat_head(cfg: DigestCfg, until: float, since: float) -> dict:
    dat = {"end": int(until)}
    win = round((until - since) / 60)
    if win != 1440:
        dat["win"] = win
    if cfg.spotter_continents:
        dat["conts"] = "/".join(sorted(cfg.spotter_continents))
    return dat


def _page(title: str, dat: dict, cfg: DigestCfg) -> dict:
    # the data go into a block k data, not into dat: the envelope (with dat) has
    # to fit into the first frame, the block list is packed and fragmented
    page = {"typ": "dxsum", "cat": ["dx"], "src": ["tinybox"], "ti": title,
            "blk": [{"k": "data", "v": dat}]}
    exp = valid_minutes(cfg.valid)
    if exp:
        page["exp"] = exp
    return page


def station_page(sel: list[DxLine], cfg: DigestCfg, since: float, until: float,
                 n_calls: int, n_spots: int, coverage_min: int | None, rated: bool) -> dict:
    """brocast page typ dxsum (dictionary v4) with the DX stations.

    st rows: tier, call, entity (ADIF number, else name as text), spotters,
    Most Wanted rank, first/last spot as minutes before end, bands per mode
    group as bit masks (bit i = band i of the dictionary list band), other
    modes. Names go as dictionary names, the codec turns them into numbers."""
    dat = _dat_head(cfg, until, since)
    dat.update({"calls": n_calls, "spots": n_spots,
                "tiers": "".join(cfg.brocast_tiers) if rated else ""})
    if coverage_min is not None:
        dat["cov"] = coverage_min
    rows = []
    for d in sel:
        om = sorted({other_name(m) for b in d.band_modes.values() for m in b if mode_group(m) == 3})
        rows.append([d.tier, d.call, d.dxcc if d.dxcc is not None else d.name[:ENTITY_TEXT_MAX],
                     len(d.spotters), d.rank,
                     max(0, round((until - d.first) / 60)), max(0, round((until - d.last) / 60)),
                     _mask(d, 0), _mask(d, 1), _mask(d, 2), _mask(d, 3), om or None])
    dat["st"] = rows
    return _page(f"DX-Cluster {datetime.fromtimestamp(until):%d.%m.}", dat, cfg)


def activity_page(acts: list[BandActivity], cfg: DigestCfg, since: float, until: float) -> dict:
    """brocast page typ dxsum with the band activity: spots per band and mode
    group, peak hour (UTC), other modes with counts. Bands without spots stay off."""
    dat = _dat_head(cfg, until, since)
    dat["act"] = [[a.band, *a.by_group, a.peak,
                   sorted(a.others.items(), key=lambda x: (-x[1], x[0])) or None]
                  for a in acts if a.spots]
    return _page(f"DX-Bandaktivität {datetime.fromtimestamp(until):%d.%m.}", dat, cfg)


def build(rows, cfg: DigestCfg, since: float, until: float, coverage_sec: float,
          node: str = "", mw: mwmod.MostWanted | None = None,
          dxcc: dxccmod.DxccList | None = None) -> Digest | None:
    """None if there is nothing to report (no spots at all in the window)."""
    if not rows:
        return None
    lines, n_rel = aggregate(rows, cfg)
    rate(lines, cfg, mw, dxcc)
    shown = by_relevance([d for d in lines if len(d.spotters) >= cfg.min_spotters])
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
    coverage_note = ""
    if coverage_sec < 0.9 * (until - since):
        coverage_note = (f"Achtung: Cluster nur {coverage_sec / 3600:.1f} von {window_h:.0f} h "
                         "verbunden - unvollstaendig.")
        head.append(coverage_note)

    table_head = ["R: Relevanz A (selten) bis C, nach Club Log Most Wanted (MW) und",
                  "Spotterzahl. Zeit: Tag/UTC erster-letzter Spot, Sp: verschiedene Spotter.",
                  "" if mw is not None else "(Most-Wanted-Liste fehlt: Relevanz nur nach Spottern.)",
                  f"R {'Call':<10} {'Gebiet':<16} {'Baender':<11} {'Modes':<8} {'Zeit UTC':<15} "
                  "Sp  MW",
                  "-" * 73]
    if table_head[2] == "":
        del table_head[2]
    table_head.insert(len(table_head) - 2, "")
    source = ("Quelle: DX-Cluster" + (f" {node}" if node else "")
              + ", Laenderdaten AD1C cty.dat"
              + (", Club Log Most Wanted" if mw is not None else "") + ". TinyBox dxfeed.")
    tail_parts = ["", "Bandaktivitaet: eigenes Bulletin \"DX-Bandaktivitaet\".", "", source]

    kept = shown[:cfg.max_lines]                 # most relevant first
    hidden = len(shown) - len(kept)

    def compose() -> str:
        body = list(head) + [""]
        if kept:
            body += table_head + [table_line(d) for d in sorted(kept, key=lambda d: d.call)]
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
    while len(text.encode("ascii", "replace")) > cfg.max_bytes and kept:
        kept.pop()                                  # the least relevant goes first
        hidden += 1
        text = compose()

    acts = activity(rows, cfg)
    act_text = "\n".join([f"DX-Bandaktivitaet {t0:%d.%m.%Y %H:%M} - {t1:%d.%m.%Y %H:%M} Lokalzeit",
                          f"Alle Spots von Stationen in {conts}, Spitze = Stunde (UTC) mit den",
                          "meisten Spots. Andere: FT4, RTTY, FM ... (Anzahl).", "",
                          *band_activity(rows, cfg), "", source]) + "\n"
    page = act_page = None
    if cfg.brocast:
        # without the Most Wanted list every entity has the same rarity and the
        # tiers say little: then the most relevant by spotters, up to the limit
        sel = shown if mw is None else [d for d in shown if d.tier in cfg.brocast_tiers]
        sel = sel[:cfg.brocast_max_rows]
        cov = round(coverage_sec / 60) if coverage_note else None
        page = station_page(sorted(sel, key=lambda d: d.call), cfg, since, until,
                            len(lines), n_rel, cov, mw is not None)
        act_page = activity_page(acts, cfg, since, until)

    act = Bulletin(subject=f"DX-Bandaktivitaet {t1:%d.%m.%Y}", text=act_text,
                   replace=f"dxfeed-act-{t1:%Y%m%d}", page=act_page)
    return Digest(subject=f"DX-Zusammenfassung {t1:%d.%m.%Y}",
                  text=text, replace=f"dxfeed-{t1:%Y%m%d}",
                  lines=len(kept), spots=len(rows), page=page, act=act)


def write_inbox(directory: str | Path, d: Digest | Bulletin, cfg: DigestCfg) -> list[Path]:
    """Bulletin files for the TinyBox inbox folder (.tmp first, then rename):
    the stations and the band activity. No @ address: they stay in this mailbox."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    out = []
    for b in d.bulletins() if isinstance(d, Digest) else [d]:
        head = {"To": cfg.to, "Subject": b.subject, "Replace": b.replace}
        if cfg.valid:
            head["Valid"] = cfg.valid
        if b.page is not None:
            head["Brocast"] = json.dumps(b.page, ensure_ascii=True, separators=(",", ":"))
        content = "".join(f"{k}: {v}\n" for k, v in head.items()) + "\n" + b.text
        name = b.replace.replace("-", "_")
        tmp = directory / f"{name}.tmp"
        tmp.write_text(content, encoding="ascii", errors="replace")
        target = directory / f"{name}.txt"
        os.replace(tmp, target)
        out.append(target)
    return out
