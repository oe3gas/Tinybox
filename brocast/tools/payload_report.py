"""Vorher/Nachher: wie viel Funk kostet eine Seite in Format 1 bzw. Format 2?

Aufruf aus dem Ordner brocast:

    py -3 tools/payload_report.py                     Seiten der eigenen Datenbank
    py -3 tools/payload_report.py --db data\\brocastd.db
    py -3 tools/payload_report.py test\\*.json         Seiten aus Dateien
    py -3 tools/payload_report.py --conf brocastd.conf   Baudrate usw. von dort

Gerechnet wird mit demselben Code, der auch sendet (splitter.py, fragment.py,
frame.py), nicht mit Schätzwerten. Die Sendezeit ist die Zeit auf Funk
einschließlich TXDELAY je Aussendung; "Dauer" zählt zusätzlich die Pausen
zwischen den Aussendungen (burst_gap_s), also die Zeit, die die Frequenz
belegt ist.
"""

from __future__ import annotations

import argparse
import glob
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from brocast import fragment, zdict                      # noqa: E402
from brocast.codec import BrocastError, Codec            # noqa: E402
from brocast.config import ConfigError, StationCfg, load as load_cfg  # noqa: E402
from brocast.frame import build as build_frame, header, tx_airtime_s  # noqa: E402
from brocast.splitter import TooLargeError, split        # noqa: E402

T0 = 1_790_000_000
CALL = "OE3GAS-5"


def frames_of(payloads: list[bytes], hdr: int, cfg: StationCfg) -> tuple[int, int, float, float]:
    """(Frames, Bytes auf Funk, Sendezeit, Dauer mit Pausen)."""
    lens = [len(build_frame(CALL, p, cfg.path, hdr)) for p in payloads]
    air = tx_airtime_s(lens, cfg.baud, cfg.txdelay_ms, cfg.burst_frames)
    bursts = -(-len(lens) // cfg.burst_frames) if cfg.burst_frames > 0 else 1
    return len(lens), sum(lens), air, air + cfg.burst_gap_s * (bursts - 1)


def variants(codec: Codec, content: dict, cfg: StationCfg, zd: zdict.ZDict,
             page_id: int) -> dict[str, tuple[int, int, float, float] | str]:
    page = {k: v for k, v in content.items() if k not in ("parts", "id")}
    page.update({"id": content.get("id", page_id), "rev": 0, "t": T0})
    parts = content.get("parts")
    out: dict[str, tuple[int, int, float, float] | str] = {}
    try:
        out["f1"] = frames_of(split(codec, page, parts=parts), header(), cfg)
    except (BrocastError, TooLargeError) as exc:
        out["f1"] = f"geht nicht: {exc}"
    with_blocks = dict(page)
    if parts and "blk" not in with_blocks:
        with_blocks["blk"] = [b for part in parts for b in part]
    for name, dictionary in (("f2", None), ("f2z", zd)):
        try:
            built = fragment.build(codec, with_blocks, dictionary)
            out[name] = frames_of(built.payloads, built.hdr, cfg)
        except (BrocastError, TooLargeError) as exc:
            out[name] = f"geht nicht: {exc}"
    return out


def pages_from_db(path: Path) -> list[tuple[str, dict]]:
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    rows = db.execute("SELECT id, provider, pkey, content FROM pages ORDER BY id").fetchall()
    db.close()
    out = []
    for row in rows:
        try:
            content = json.loads(row["content"])
        except ValueError:
            continue
        if isinstance(content, dict) and "typ" in content:
            out.append((f"{row['id']} {row['provider']}/{row['pkey']}", content))
    return out


def pages_from_files(patterns: list[str]) -> list[tuple[str, dict]]:
    out = []
    for pattern in patterns:
        for name in sorted(glob.glob(pattern)):
            try:
                content = json.loads(Path(name).read_text(encoding="utf-8"))
            except ValueError as exc:
                print(f"{name}: kein JSON ({exc})")
                continue
            if isinstance(content, dict) and "typ" in content:
                out.append((Path(name).stem, content))
    return out


def cell(value: tuple[int, int, float, float] | str) -> str:
    if isinstance(value, str):
        return f"{'-':>21}"
    frames, byts, air, dur = value
    return f"{frames:>3} {byts:>6} {air:>5.1f} {dur:>5.0f}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="payload_report.py")
    ap.add_argument("files", nargs="*", help="JSON-Dateien mit Seiten (Ingest-Format)")
    ap.add_argument("--db", default=None, help="brocastd-Datenbank (Standard: data/brocastd.db)")
    ap.add_argument("--conf", default=None, help="brocastd.conf für Baudrate, TXDELAY, Pausen")
    args = ap.parse_args(argv)

    cfg = StationCfg()
    if args.conf:
        try:
            cfg = load_cfg(args.conf).station
        except ConfigError as exc:
            print(f"Konfiguration nicht lesbar: {exc}")
            return 2
    codec, zd = Codec(), zdict.load()
    if not zd.ok:
        print(f"Hinweis: Preset-Wörterbuch {zd.problem} – die Spalte „+ gepackt“ fehlt.\n")

    if args.files:
        pages = pages_from_files(args.files)
    else:
        db = Path(args.db) if args.db else ROOT / "data" / "brocastd.db"
        if not db.is_file():
            print(f"Keine Datenbank {db} und keine Dateien angegeben.")
            return 2
        pages = pages_from_db(db)
    if not pages:
        print("Keine Seiten gefunden.")
        return 1

    print(f"{cfg.baud} Bd, TXDELAY {cfg.txdelay_ms} ms, {cfg.burst_frames} Frames je "
          f"Aussendung, {cfg.burst_gap_s} s Pause\n")
    head = f"{'Fr  Bytes     s Dauer':>21}"
    print(f"{'Seite':<34} | {head} | {head} | {head}")
    print(f"{'':<34} | {'Format 1 (alt)':^21} | {'Format 2':^21} "
          f"| {'Format 2 + gepackt':^21}")
    print("-" * 34 + "-+-" + "-" * 21 + "-+-" + "-" * 21 + "-+-" + "-" * 21)
    total = {k: [0, 0, 0.0, 0.0] for k in ("f1", "f2", "f2z")}
    for n, (name, content) in enumerate(pages):
        res = variants(codec, content, cfg, zd, page_id=cfg.id_auto_start + n)
        print(f"{name[:34]:<34} | {cell(res['f1'])} | {cell(res['f2'])} | {cell(res['f2z'])}")
        for key, value in res.items():
            if not isinstance(value, str):
                for i in range(4):
                    total[key][i] += value[i]
    print("-" * 34 + "-+-" + "-" * 21 + "-+-" + "-" * 21 + "-+-" + "-" * 21)
    print(f"{f'SUMME ({len(pages)} Seiten)':<34} | " + " | ".join(
        cell(tuple(total[k])) for k in ("f1", "f2", "f2z")))        # type: ignore[arg-type]
    base = total["f1"]
    for key, label in (("f2", "Format 2"), ("f2z", "Format 2 + gepackt")):
        if base[1]:
            print(f"{label}: {100 - 100 * total[key][1] / base[1]:.0f} % weniger Bytes, "
                  f"{100 - 100 * total[key][3] / base[3]:.0f} % weniger Kanalzeit, "
                  f"{base[0] - total[key][0]} Frames gespart")
    return 0


if __name__ == "__main__":
    sys.exit(main())
