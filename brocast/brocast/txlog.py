"""Sendeprotokoll: every frame brocastd hands to Direwolf, one line each.

Purpose: proof of what was transmitted, when and under which callsign
(e.g. towards the authority), especially in unattended continuous operation.

  * plain text, one file per month: Sendeprotokoll_<YYYY-MM>.txt (UTC)
  * append only, the file is opened and closed for every line
  * never deleted by brocastd - archiving is up to the station operator

Time = moment the frame is handed to Direwolf (AGW/KISS); Direwolf transmits it
immediately or after channel access (typically within seconds).
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

log = logging.getLogger(__name__)

HEADER = (
    "# brocast Sendeprotokoll {month} – Station {call}\n"
    "# Zeit (UTC) = Übergabe an Direwolf. Eine Zeile pro gesendetem Frame.\n"
    "# Zeit UTC            | Rufzeichen | Ziel/Pfad        | Seite | Rev | Teil  | Typ    "
    "| Bytes | Sek. | Lieferant/Schlüssel | Titel\n"
)


class TxLog:
    def __init__(self, directory: Path, callsign: str):
        self.dir = Path(directory)
        self.call = callsign
        self.dir.mkdir(parents=True, exist_ok=True)
        self.lines = 0

    def path_for(self, ts: float) -> Path:
        return self.dir / f"Sendeprotokoll_{time.strftime('%Y-%m', time.gmtime(ts))}.txt"

    def record(self, ts: float, dest_path: str, page_id: int, rev: int, sub: int, total: int,
               typ: str, nbytes: int, airtime: float, provider: str, key: str,
               title: str, withdrawn: bool = False) -> None:
        path = self.path_for(ts)
        new = not path.exists()
        title = " ".join(str(title or "").split())[:60]
        if withdrawn:
            title = f"[zurückgezogen] {title}".strip()
        line = (f"{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(ts))}Z | {self.call:<10} | "
                f"{dest_path:<16} | {page_id:>5} | {rev:>3} | {sub:>2}/{total:<2} | {typ:<6} | "
                f"{nbytes:>5} | {airtime:>4.1f} | {provider + '/' + key:<19} | {title}\n")
        try:
            with open(path, "a", encoding="utf-8", newline="\n") as fh:
                if new:
                    fh.write(HEADER.format(month=time.strftime("%Y-%m", time.gmtime(ts)),
                                           call=self.call))
                fh.write(line)
            self.lines += 1
        except OSError as exc:              # never stop transmitting because of the log
            log.error("Sendeprotokoll nicht schreibbar (%s): %s", path, exc)


def title_of(content_json: str) -> tuple[str, str]:
    """(typ, title) from a stored page's provider content."""
    try:
        content = json.loads(content_json)
    except ValueError:
        return "?", ""
    return str(content.get("typ", "?")), str(content.get("ti", ""))


# --- reading (statistics, advisor.py) ------------------------------------------

def files_for(directory: Path, since: float, until: float) -> list[Path]:
    """The monthly files that cover since..until (UTC), existing ones only."""
    months, t = [], since
    while True:
        m = time.strftime("%Y-%m", time.gmtime(t))
        if m not in months:
            months.append(m)
        if t >= until:
            break
        t = min(until, t + 20 * 86400)
    out = [Path(directory) / f"Sendeprotokoll_{m}.txt" for m in months]
    return [p for p in out if p.exists()]


def read_lines(paths: list[Path], since: float, until: float) -> list[dict]:
    """Frames of the Sendeprotokoll between since and until (UTC), oldest first.
    Lines that do not parse (header, damaged) are skipped."""
    import calendar
    out = []
    for path in paths:
        try:
            fh = open(path, encoding="utf-8", errors="replace")
        except OSError as exc:
            log.warning("Sendeprotokoll nicht lesbar (%s): %s", path, exc)
            continue
        with fh:
            for line in fh:
                if line.startswith("#") or "|" not in line:
                    continue
                cols = [c.strip() for c in line.rstrip("\n").split("|", 10)]
                if len(cols) < 11:
                    continue
                try:
                    ts = calendar.timegm(time.strptime(cols[0].rstrip("Z"), "%Y-%m-%d %H:%M:%S"))
                    if ts < since or ts > until:
                        continue
                    sub, _, total = cols[5].partition("/")
                    provider, _, key = cols[9].partition("/")
                    title = cols[10]
                    withdrawn = title.startswith("[zurückgezogen]")
                    out.append({"t": ts, "dest": cols[2], "page": int(cols[3]),
                                "rev": int(cols[4]), "sub": int(sub), "total": int(total),
                                "typ": cols[6], "bytes": int(cols[7]),
                                "air0": float(cols[8]), "provider": provider, "key": key,
                                "title": title[len("[zurückgezogen]"):].strip() if withdrawn
                                else title, "withdrawn": withdrawn,
                                "beacon": cols[6] == "beacon" or cols[2].startswith("BEACON")})
                except (ValueError, IndexError):
                    continue
    out.sort(key=lambda r: r["t"])
    return out


def group_sends(lines: list[dict]) -> list[dict]:
    """Frames -> sends: one entry per page handed to Direwolf (all its parts)."""
    sends: list[dict] = []
    open_: dict[tuple, dict] = {}
    for ln in lines:
        k = (ln["provider"], ln["key"], ln["page"])
        cur = open_.get(k)
        if (cur is None or ln["sub"] <= cur["last_sub"] or ln["rev"] != cur["rev"]
                or ln["t"] - cur["t_end"] > 600 or ln["beacon"]):
            cur = {"t": ln["t"], "t_end": ln["t"], "page": ln["page"], "rev": ln["rev"],
                   "provider": ln["provider"], "key": ln["key"], "typ": ln["typ"],
                   "title": ln["title"], "withdrawn": ln["withdrawn"], "beacon": ln["beacon"],
                   "total": ln["total"], "frames": 0, "bytes": 0, "air0": 0.0, "last_sub": 0}
            sends.append(cur)
            open_[k] = cur
        cur["frames"] += 1
        cur["bytes"] += ln["bytes"]
        cur["air0"] += ln["air0"]
        cur["last_sub"] = ln["sub"]
        cur["t_end"] = ln["t"]
    for s in sends:
        del s["last_sub"]
    return sends
