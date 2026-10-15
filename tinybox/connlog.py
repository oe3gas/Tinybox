"""Connection logbook (CR44): one row per connection - station, way, connect,
disconnect, duration, bytes. No contents. Shared by TinyBox and the client:
the export as CSV and ADIF (the logbook exchange format, .adi) is the same.

A row is a dict:
    call     the other station (with SSID)
    via      radio | telnet | kiss ...
    start    connect time, UTC, "2026-10-15T18:46:03Z"
    end      disconnect time, UTC
    secs     duration in seconds
    rx, tx   payload bytes in / out (None = not counted)
    air_tx, air_rx   bytes on the air incl. repeats, from the Direwolf fork
                     (None = not known)
    ended    how it ended: bye | disc | lost (TinyBox), user | remote | failed |
             cancelled (client)
    freq     MHz of that connection (client: asked at the start of a session;
             optional - TinyBox takes [station] freq)
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

CSV_FIELDS = ("start", "end", "secs", "call", "via", "freq", "rx", "tx", "air_tx", "air_rx",
              "ended")

# ADIF band plan (MHz, lower edge, upper edge) - only the bands packet is used on
BANDS = (("2190m", 0.1357, 0.1378), ("630m", 0.472, 0.479), ("160m", 1.8, 2.0),
         ("80m", 3.5, 4.0), ("60m", 5.06, 5.45), ("40m", 7.0, 7.3), ("30m", 10.1, 10.15),
         ("20m", 14.0, 14.35), ("17m", 18.068, 18.168), ("15m", 21.0, 21.45),
         ("12m", 24.89, 24.99), ("10m", 28.0, 29.7), ("6m", 50.0, 54.0),
         ("4m", 70.0, 71.0), ("2m", 144.0, 148.0), ("1.25m", 222.0, 225.0),
         ("70cm", 420.0, 450.0), ("23cm", 1240.0, 1300.0))


def base_call(call: str) -> str:
    return (call or "").split("-", 1)[0].upper()


def duration(secs: int | None) -> str:
    """12 -> '0m12', 723 -> '12m03', 4000 -> '1h06m'."""
    s = max(0, int(secs or 0))
    if s >= 3600:
        return f"{s // 3600}h{s % 3600 // 60:02d}m"
    return f"{s // 60}m{s % 60:02d}"


def kb(n: int | None) -> str:
    if n is None:
        return "-"
    return str(n) if n < 1000 else f"{n / 1000:.1f}k" if n < 100000 else f"{n // 1000}k"


def band_of(freq: str) -> str:
    try:
        f = float(freq)
    except (TypeError, ValueError):
        return ""
    return next((name for name, lo, hi in BANDS if lo <= f <= hi), "")


def to_csv(rows: list[dict]) -> str:
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\r\n")
    w.writerow(CSV_FIELDS)
    for r in rows:
        w.writerow(["" if r.get(k) is None else r.get(k) for k in CSV_FIELDS])
    return out.getvalue()


def _field(name: str, value) -> str:
    v = str(value)
    return f"<{name}:{len(v.encode('ascii', 'replace'))}>{v} "


def _dt(iso: str) -> tuple[str, str]:
    """'2026-10-15T18:46:03Z' -> ('20261015', '184603')."""
    d = (iso or "").replace("-", "").replace(":", "").rstrip("Z")
    day, _, t = d.partition("T")
    return day[:8], (t + "000000")[:6]


def to_adif(rows: list[dict], station: str, program: str, version: str,
            freq: str = "", locator: str = "", operator: str = "") -> str:
    """ADIF 3 (.adi). CALL and STATION_CALLSIGN without SSID - logbook programs
    expect a callsign there; the full calls, the way and the bytes go into COMMENT.
    MODE PKT; FREQ/BAND from the row's freq, else freq (MHz) - none if both are empty."""
    now = datetime.now(timezone.utc)
    head = (f"TinyBox connection log {station}, exported {now:%Y-%m-%d %H:%M} UTC\n"
            + _field("ADIF_VER", "3.1.4") + _field("PROGRAMID", program)
            + _field("PROGRAMVERSION", version)
            + _field("CREATED_TIMESTAMP", now.strftime("%Y%m%d %H%M%S")) + "<EOH>\n")
    recs = []
    for r in rows:
        f = r.get("freq") or freq
        band = band_of(f)
        day_on, t_on = _dt(r["start"])
        day_off, t_off = _dt(r.get("end") or r["start"])
        comment = (f"{r['call']} via {r.get('via') or '-'}, {duration(r.get('secs'))}, "
                   f"rx {kb(r.get('rx'))} tx {kb(r.get('tx'))}"
                   + (f", air tx {kb(r.get('air_tx'))}" if r.get("air_tx") is not None else "")
                   + (f", {r['ended']}" if r.get("ended") else ""))
        rec = (_field("CALL", base_call(r["call"])) + _field("QSO_DATE", day_on)
               + _field("TIME_ON", t_on) + _field("QSO_DATE_OFF", day_off)
               + _field("TIME_OFF", t_off) + _field("MODE", "PKT")
               + _field("STATION_CALLSIGN", base_call(station)))
        if operator:
            rec += _field("OPERATOR", base_call(operator))
        if f:
            rec += _field("FREQ", f)
        if band:
            rec += _field("BAND", band)
        if locator:
            rec += _field("MY_GRIDSQUARE", locator)
        rec += _field("COMMENT", comment) + "<EOR>"
        recs.append(rec)
    return head + "\n".join(recs) + ("\n" if recs else "")
