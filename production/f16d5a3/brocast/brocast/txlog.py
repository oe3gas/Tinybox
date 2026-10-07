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
