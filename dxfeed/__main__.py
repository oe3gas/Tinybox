"""python -m dxfeed [-c dxfeed.conf] <command>

    collect              connect to the cluster and store spots (runs until Ctrl+C)
    digest               print the DX digest of the last 24 hours
    digest --tinybox     ... and put it into the TinyBox inbox folder (bulletin to DX)
    show [-n 20]         the last spots in the database
    status               spots, coverage, cty.dat and Most Wanted state
    cty-update           download the AD1C country file now
    mw-update            download the Club Log Most Wanted list now

Exit codes: 0 ok, 1 nothing to report, 2 error.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from . import VERSION
from . import cty as ctymod
from . import dxcc as dxccmod
from . import mostwanted as mwmod
from .collector import Collector
from .config import Config, ConfigError, load
from .digest import build, write_inbox
from .store import Store

log = logging.getLogger("dxfeed")


def setup_logging(level: str, file: str) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if file:
        Path(file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(file, encoding="utf-8"))
    logging.basicConfig(level=getattr(logging, level, logging.INFO), handlers=handlers,
                        format="%(asctime)s %(levelname).1s [dxfeed] %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")


def load_cty(cfg: Config, *, fetch_if_missing: bool) -> ctymod.Cty | None:
    d = cfg.data
    if fetch_if_missing and not d.cty.is_file():
        try:
            ctymod.download(d.cty, d.cty_url, verify_ssl=d.ssl_verify)
        except Exception as exc:
            log.warning("cty.dat download failed: %s", exc)
    try:
        cty = ctymod.Cty.load(d.cty)
        log.info("cty.dat: %d entities %s", len(cty), cty.version)
        return cty
    except ctymod.CtyError as exc:
        log.warning("%s - spots are stored without country; the digest needs "
                    "it (python -m dxfeed cty-update, or put cty.dat into %s)",
                    exc, d.cty.parent)
        return None


def load_mostwanted(cfg: Config) -> mwmod.MostWanted | None:
    """The Most Wanted list for the relevance score; refreshed when older than
    mostwanted_update_days. A failed download keeps the old file."""
    d = cfg.data
    if ctymod.is_stale(d.mostwanted, d.mostwanted_update_days):
        try:
            mwmod.download(d.mostwanted, d.mostwanted_url, verify_ssl=d.ssl_verify)
        except Exception as exc:
            log.warning("most wanted list download failed: %s", exc)
    return mwmod.load_or_none(d.mostwanted)


def cmd_collect(cfg: Config, args) -> int:
    log.info("dxfeed %s: nodes %s, login %s, skimmer %s", VERSION,
             " ".join(f"{h}:{p}" for h, p in cfg.cluster.nodes), cfg.cluster.login,
             "on" if cfg.cluster.skimmer else "off")
    store = Store(cfg.data.db)
    cty = load_cty(cfg, fetch_if_missing=True)
    collector = Collector(cfg, store, cty)
    try:
        asyncio.run(collector.run())
    except KeyboardInterrupt:
        log.info("stopped, %d spots stored", collector.spots)
    finally:
        store.close()
    return 0


def cmd_digest(cfg: Config, args) -> int:
    store = Store(cfg.data.db)
    try:
        until = time.time() if args.until is None else \
            datetime.strptime(args.until, "%Y-%m-%d %H:%M").timestamp()
        until = until // 60 * 60
        since = until - cfg.digest.hours * 3600
        rows = store.spots(since, until)
        cov = store.coverage(since, until)
        node = " ".join(f"{h}:{p}" for h, p in cfg.cluster.nodes[:1])
        d = build(rows, cfg.digest, since, until, cov, node, load_mostwanted(cfg),
                  dxccmod.load_or_none(cfg.data.dictionary))
    finally:
        store.close()
    if d is None:
        log.error("digest: no spots between %s and %s - collector running?",
                  datetime.fromtimestamp(since), datetime.fromtimestamp(until))
        return 1
    if args.tinybox is None:
        for i, b in enumerate(d.bulletins()):
            if i:
                print("\n" + "=" * 73 + "\n")
            print(f"Subject: {b.subject}\n")
            print(b.text, end="")
            print(f"\n[{len(b.text.encode('ascii', 'replace'))} Bytes]")
            if b.page is not None:
                dat = b.page["blk"][0]["v"]
                what = (f"{len(dat['st'])} Stationen" if "st" in dat
                        else f"{len(dat.get('act', []))} Baender")
                size = len(json.dumps(b.page, separators=(",", ":")))
                print(f"[brocast-Seite dxsum: {what}, JSON {size} Bytes]")
        return 0
    if not args.tinybox:
        log.info("inbox %s (%s)", cfg.digest.inbox, cfg.inbox_source)
    for hint in cfg.hints:
        log.info("config hint: %s", hint)
    for target in write_inbox(args.tinybox or cfg.digest.inbox, d, cfg.digest):
        log.info("digest: %s -> %s", target.stem, target)
    log.info("digest: %s, %d lines", d.subject, d.lines)
    return 0


def cmd_show(cfg: Config, args) -> int:
    store = Store(cfg.data.db)
    try:
        for r in store.last(args.n):
            t = time.strftime("%d.%m. %H:%M", time.gmtime(r["ts"]))
            print(f"{t}z {r['freq']:>9.1f} {r['dx']:<11} {r['dx_name'][:16]:<16} "
                  f"{r['mode']:<4} de {r['spotter']:<9} {r['sp_cont']:<2} {r['comment']}")
    finally:
        store.close()
    return 0


def cmd_status(cfg: Config, args) -> int:
    store = Store(cfg.data.db)
    try:
        now = time.time()
        rows = store.spots(now - 86400, now)
        cov = store.coverage(now - 86400, now)
        last = store.last(1)
    finally:
        store.close()
    print(f"Datenbank:   {cfg.data.db}")
    print(f"Spots 24 h:  {len(rows)}  (ohne Land: {sum(1 for r in rows if not r['dx_prefix'])})")
    print(f"Verbunden:   {cov / 3600:.1f} von 24 h")
    if last:
        print(f"Letzter Spot: {datetime.fromtimestamp(last[0]['ts']):%d.%m.%Y %H:%M:%S}")
    try:
        cty = ctymod.Cty.load(cfg.data.cty)
        age = (now - cfg.data.cty.stat().st_mtime) / 86400
        print(f"cty.dat:     {len(cty)} Gebiete, {cty.version or '?'}, {age:.0f} Tage alt")
    except (ctymod.CtyError, OSError):
        print(f"cty.dat:     fehlt ({cfg.data.cty}) - python -m dxfeed cty-update")
        cty = None
    try:
        mw = mwmod.MostWanted.load(cfg.data.mostwanted)
        age = (now - cfg.data.mostwanted.stat().st_mtime) / 86400
        line = (f"Most Wanted: {len(mw)} Gebiete ("
                + ("nach DXCC-Nummer" if mw.by_adif else "nach Praefix") + f"), {age:.0f} Tage alt")
        if cty is not None:
            dx = dxccmod.load_or_none(cfg.data.dictionary)
            missing = []
            for p, n in sorted({(e.prefix, e.name) for e, _ in cty.prefixes.values()}):
                ent = dx.find(p, n) if dx is not None else None
                if (mw.rank_code(ent.code) if ent else None) is None \
                        and mw.rank(ent.clublog if ent else p) is None and mw.rank(p) is None:
                    missing.append(p)
            if missing:
                line += f"; ohne Rang: {' '.join(missing[:12])}" + (" ..." if len(missing) > 12 else "")
        print(line)
    except (mwmod.MostWantedError, OSError):
        print(f"Most Wanted: fehlt ({cfg.data.mostwanted}) - python -m dxfeed mw-update")
    dx = dxccmod.load_or_none(cfg.data.dictionary)
    if dx is None:
        print(f"DXCC-Liste:  fehlt ({cfg.data.dictionary}, ab Dictionary v4, PyYAML) - "
              "brocast-Seite mit Gebietsnamen als Text")
    else:
        line = f"DXCC-Liste:  {len(dx)} Gebiete (Dictionary v{dx.version})"
        if cty is not None:
            ents = {(e.prefix, e.name) for e, _ in cty.prefixes.values()}
            missing = sorted(p for p, n in ents if dx.find(p, n) is None)
            if missing:
                line += (f"; ohne DXCC-Nummer: {' '.join(missing[:12])}"
                         + (" ..." if len(missing) > 12 else ""))
        print(line)
    return 0


def cmd_mw_update(cfg: Config, args) -> int:
    try:
        mwmod.download(cfg.data.mostwanted, cfg.data.mostwanted_url,
                       verify_ssl=cfg.data.ssl_verify)
    except Exception as exc:
        log.error("most wanted list download failed: %s", exc)
        return 2
    mw = mwmod.MostWanted.load(cfg.data.mostwanted)
    print(f"Most Wanted: {len(mw)} Gebiete -> {cfg.data.mostwanted}")
    return 0


def cmd_cty_update(cfg: Config, args) -> int:
    try:
        ctymod.download(cfg.data.cty, cfg.data.cty_url, verify_ssl=cfg.data.ssl_verify)
    except Exception as exc:
        log.error("cty.dat download failed: %s", exc)
        return 2
    cty = ctymod.Cty.load(cfg.data.cty)
    print(f"cty.dat: {len(cty)} Gebiete, {cty.version or '?'} -> {cfg.data.cty}")
    return 0


def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="dxfeed", description="DX cluster feed for TinyBox")
    ap.add_argument("-c", "--config", default="dxfeed.conf")
    ap.add_argument("--log", metavar="FILE", help="also log into this file")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("collect", help="connect to the cluster and store spots")
    p = sub.add_parser("digest", help="DX digest of the last hours")
    p.add_argument("--tinybox", nargs="?", const="", metavar="DIR",
                   help="put it into the TinyBox inbox folder (default from dxfeed.conf)")
    p.add_argument("--until", metavar="'YYYY-MM-DD HH:MM'",
                   help="end of the window, local time (default: now)")
    p = sub.add_parser("show", help="last spots")
    p.add_argument("-n", type=int, default=20)
    sub.add_parser("status", help="database and cty.dat state")
    sub.add_parser("cty-update", help="download cty.dat")
    sub.add_parser("mw-update", help="download the Club Log Most Wanted list")
    args = ap.parse_args(argv)

    try:
        cfg = load(args.config)
    except ConfigError as exc:
        print(f"dxfeed: {exc}", file=sys.stderr)
        return 2
    setup_logging(cfg.log_level, args.log or cfg.log_file)
    handler = {"collect": cmd_collect, "digest": cmd_digest, "show": cmd_show,
               "status": cmd_status, "cty-update": cmd_cty_update,
               "mw-update": cmd_mw_update}[args.cmd]
    try:
        return handler(cfg, args)
    except Exception:
        log.exception("unexpected error")      # pyw has no console: goes to --log
        return 2


if __name__ == "__main__":
    sys.exit(run())
