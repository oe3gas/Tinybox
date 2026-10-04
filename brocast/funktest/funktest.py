"""Automatic radio test for brocastd (M1).

    py -3 funktest\\funktest.py listener     on PC1 (receives, writes the result)
    py -3 funktest\\funktest.py station      on PC2 (sends a fixed test plan)

Station plan (minutes after the KISS link is up):
     0  weather page (1 frame) and bulletin (4 subpages)       -> ingest API
        repeats come from the carousel (after 2, 5, 10 min ...)
    10  weather page changed                                   -> new revision
    12  bulletin withdrawn                                     -> sent 3 times
    18  end page "brocast Funktest Ende"
    21  station stops

The listener stops by itself shortly after the end page (or after 45 min)
and writes funktest\\ergebnis_listener.txt.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from brocast import config  # noqa: E402
from brocast.codec import Codec  # noqa: E402
from brocast.daemon import Daemon  # noqa: E402

log = logging.getLogger("funktest")

END_TITLE = "brocast Funktest Ende"
SCALE = float(os.environ.get("FUNKTEST_SCALE", "1"))    # < 1 only for dry runs
LISTENER_MAX_MIN = 45
KISS_WAIT_S = 30


def setup_logging(role: str) -> Path:
    logfile = HERE / f"log_{role}.txt"
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for handler in (logging.StreamHandler(sys.stdout),
                    logging.FileHandler(logfile, mode="w", encoding="utf-8")):
        handler.setFormatter(fmt)
        root.addHandler(handler)
    return logfile


def banner(text: str) -> None:
    line = "=" * 64
    print(f"\n{line}\n  {text}\n{line}\n", flush=True)


async def http(port: int, method: str, path: str, body: object = None) -> tuple[int, dict]:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    data = b"" if body is None else json.dumps(body).encode("utf-8")
    head = (f"{method} {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
            f"Content-Length: {len(data)}\r\n")
    if body is not None:
        head += "Content-Type: application/json\r\n"
    writer.write(head.encode() + b"\r\n" + data)
    await writer.drain()
    raw = await reader.read()
    writer.close()
    return int(raw.split(b" ", 2)[1]), json.loads(raw.split(b"\r\n\r\n", 1)[1])


async def wait_for_kiss(daemon: Daemon) -> bool:
    for _ in range(KISS_WAIT_S * 2):
        if daemon.link.connected.is_set():
            return True
        await asyncio.sleep(0.5)
    return False


def load_cfg(mode: str) -> config.Config:
    cfg = config.load(ROOT / "brocastd.conf")
    cfg.mode = mode
    cfg.data_dir = HERE / "data"
    cfg.log_level = "INFO"
    return cfg


def fresh_db(role: str) -> Path:
    db = HERE / "data" / f"funktest_{role}.db"
    db.parent.mkdir(exist_ok=True)
    if db.exists():
        db.unlink()
    return db


# ---------------------------------------------------------------------------
# station (PC2)
# ---------------------------------------------------------------------------

async def run_station() -> int:
    cfg = load_cfg("station")
    daemon = Daemon(cfg, db_path=fresh_db("station"))
    task = asyncio.create_task(daemon.run())
    if not await wait_for_kiss(daemon):
        log.error("Keine Verbindung zu Direwolf (%s). Läuft Direwolf? Steht %s %s in "
                  "direwolf.conf?", cfg.direwolf.describe(),
                  "AGWPORT" if cfg.direwolf.interface == "agw" else "KISSPORT", cfg.direwolf.port)
        task.cancel()
        return 1
    port = daemon.ingest.port
    wetter = json.loads((ROOT / "test" / "wetter.json").read_text(encoding="utf-8"))
    bulletin = json.loads((ROOT / "test" / "bulletin.json").read_text(encoding="utf-8"))
    ende = {"typ": "text", "ti": END_TITLE, "flg": ["test"], "exp": 60,
            "blk": [{"k": "para", "x": "Ende des automatischen Funktests. 73"}]}
    start = time.monotonic()

    async def at(minute: float) -> None:
        delay = start + minute * 60 * SCALE - time.monotonic()
        if delay > 0:
            log.info("... nächster Schritt in %.0f min", delay / 60)
            await asyncio.sleep(delay)

    async def step(minute: float, text: str, method: str, path: str, body=None) -> None:
        await at(minute)
        status, res = await http(port, method, path, body)
        log.info("[Min %2.0f] %s -> HTTP %s %s", minute, text, status,
                 {k: res.get(k) for k in ("id", "rev", "changed", "subpages", "error")
                  if k in res})

    banner(f"STATION {cfg.callsign} sendet – Ablauf dauert ca. 21 Minuten")
    await step(0, "Wetterseite", "PUT", "/api/v1/pages/test/wetter", wetter)
    await step(0, "Bulletin", "PUT", "/api/v1/pages/test/bulletin", bulletin)
    changed = {**wetter, "dat": {**wetter["dat"], "temp": 13.1}}
    await step(10, "Wetterseite geändert", "PUT", "/api/v1/pages/test/wetter", changed)
    await step(12, "Bulletin zurückziehen", "DELETE", "/api/v1/pages/test/bulletin")
    await step(18, "Ende-Seite", "PUT", "/api/v1/pages/test/ende", ende)
    await at(21)

    st = daemon.status()
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    banner(f"Funktest STATION beendet: {st['tx_frames']} Frames gesendet, "
           f"Direwolf verbunden: {st['kiss_connected']}")
    return 0


# ---------------------------------------------------------------------------
# listener (PC1)
# ---------------------------------------------------------------------------

async def run_listener() -> int:
    cfg = load_cfg("listener")
    daemon = Daemon(cfg, db_path=fresh_db("listener"))
    codec = daemon.codec
    events: list[dict] = []
    original = daemon.listener.on_page

    def record(page, raw, heard_from):         # log every new page/revision as it arrives
        result = original(page, raw, heard_from)
        if result in ("new", "updated", "subpage", "withdrawn"):
            full = codec.decode(raw)
            sub, total = page.get("sub") or [1, 1]
            events.append({"time": time.strftime("%H:%M:%S"),
                           "org": page.get("org") or heard_from, "id": page["id"],
                           "sub": f"{sub}/{total}", "rev": page.get("rev", 0),
                           "flg": full.get("flg", []), "ti": full.get("ti", ""),
                           "page": full})
        return result

    daemon.listener.on_page = record
    task = asyncio.create_task(daemon.run())
    if not await wait_for_kiss(daemon):
        log.error("Keine Verbindung zu Direwolf (%s). Läuft Direwolf? Steht %s %s in "
                  "direwolf.conf?", cfg.direwolf.describe(),
                  "AGWPORT" if cfg.direwolf.interface == "agw" else "KISSPORT", cfg.direwolf.port)
        task.cancel()
        return 1
    banner("LISTENER bereit – jetzt auf PC2 die Station starten")

    deadline = time.monotonic() + LISTENER_MAX_MIN * 60
    end_seen_at = None
    last_status = time.monotonic()
    while time.monotonic() < deadline:
        await asyncio.sleep(2)
        if end_seen_at is None and any(e["ti"] == END_TITLE for e in events):
            end_seen_at = time.monotonic()
            log.info("Ende-Seite empfangen, Listener stoppt in 30 s")
        if end_seen_at and time.monotonic() - end_seen_at > 30 * SCALE:
            break
        if time.monotonic() - last_status > 300:
            last_status = time.monotonic()
            s = daemon.status()
            log.info("Status: %s Frames empfangen, %s brocast-Seiten, %s Fehler",
                     s["rx_frames"], s["rx_pages"], s["rx_errors"])

    status = daemon.status()
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    result = write_result(codec, events, status, end_seen_at is not None)
    banner(f"Funktest LISTENER beendet – Ergebnis: {result}")
    return 0


def write_result(codec: Codec, events: list[dict], status: dict, end_seen: bool) -> str:
    def seen(pred) -> bool:
        return any(pred(e) for e in events)

    wx = [e for e in events if e["page"].get("typ") == "wx"]
    bl = [e for e in events if e["ti"] == "brocast Testbulletin"]
    total = int(bl[0]["sub"].split("/")[1]) if bl else 0
    checks = [
        ("Wetterseite empfangen (rev 0)", seen(lambda e: e in wx and e["rev"] == 0)),
        ("Wetterseite geändert empfangen (rev 1)", seen(lambda e: e in wx and e["rev"] == 1)),
        (f"Bulletin: alle Unterseiten empfangen ({len({e['sub'] for e in bl})}/{total})",
         total > 0 and len({e["sub"] for e in bl}) == total),
        ("Bulletin zurückgezogen empfangen", seen(lambda e: "withdrawn" in e["flg"])),
        ("Ende-Seite empfangen", end_seen),
        ("keine Dekodierfehler", status["rx_errors"] == 0),
    ]
    ok = all(c[1] for c in checks)
    lines = ["brocast Funktest – Ergebnis Listener (PC1)",
             f"Datum: {time.strftime('%Y-%m-%d %H:%M')}", "",
             f"Frames von Direwolf: {status['rx_frames']}, brocast-Seiten: {status['rx_pages']}, "
             f"Dekodierfehler: {status['rx_errors']}", "",
             "Prüfungen:"]
    lines += [f"  [{'OK ' if passed else 'FEHLT'}] {text}" for text, passed in checks]
    lines += ["", "Empfangene Seiten/Revisionen (in Reihenfolge):"]
    for e in events:
        flags = f" [{', '.join(e['flg'])}]" if e["flg"] else ""
        lines.append(f"  {e['time']}  {e['org']:<9} Seite {e['id']:<4} {e['sub']:<5} "
                     f"rev {e['rev']}{flags}  {e['ti']}")
    lines += ["", "Inhalt der zuletzt empfangenen Fassungen:"]
    latest: dict[tuple, dict] = {}
    for e in events:
        latest[(e["org"], e["id"], e["sub"])] = e
    for key, e in sorted(latest.items()):
        lines.append(f"--- {key[0]} Seite {key[1]} Unterseite {key[2]} rev {e['rev']}")
        lines += ["  " + line for line in codec.describe(e["page"])]
    verdict = "BESTANDEN" if ok else "NICHT vollständig"
    lines += ["", f"Gesamt: {verdict}"]
    (HERE / "ergebnis_listener.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return verdict


def main() -> int:
    role = sys.argv[1] if len(sys.argv) > 1 else ""
    if role not in ("station", "listener"):
        print(__doc__)
        return 2
    logfile = setup_logging(role)
    log.info("Log-Datei: %s", logfile)
    try:
        return asyncio.run(run_station() if role == "station" else run_listener())
    except KeyboardInterrupt:
        log.info("abgebrochen")
        return 1
    except config.ConfigError as exc:
        log.error("Konfigurationsfehler: %s", exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
