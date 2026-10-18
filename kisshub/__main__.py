"""python -m kisshub [-c kisshub.conf]

Commands can be typed into the window while it runs (H for help): LOG MARK,
LOG DEBUG, LOG TRACE, TXDELAY ... - see console.py.

Ctrl+C ends kisshub cleanly: the TNC is switched back out of KISS first
(if the profile says so), so a terminal program or pk232py finds it at cmd:.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from . import VERSION
from .config import ConfigError, load, make_transport
from .console import Console, LogControl
from .hub import Hub
from .tnc import Tnc


def setup_logging(level: str, file: str) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if file:
        handlers.append(logging.FileHandler(file, encoding="utf-8"))
    logging.basicConfig(level=getattr(logging, level, logging.INFO), handlers=handlers,
                        format="%(asctime)s %(levelname).1s [kisshub] %(message)s",
                        datefmt="%H:%M:%S")


async def main(cfg) -> None:
    t = cfg.tnc

    def tnc_factory(on_frame):
        return Tnc(t.profile, make_transport(t), on_frame,
                   reconnect_sec=t.reconnect_sec, params=t.params)

    hub = Hub(cfg.hub, tnc_factory)
    hub.tnc.trace = cfg.trace
    if sys.stdin is not None and sys.stdin.isatty():
        Console(hub, LogControl(cfg.log_level, cfg.log_file)).start_stdin()
    try:
        await hub.run()
    finally:
        await asyncio.shield(hub.stop())


def log_lines(config_path: str, cfg) -> list[str]:
    """Where this run is logged - shown at every start, so a test run is never
    lost because the log went nowhere (or somewhere unexpected)."""
    trace = ", trace on" if cfg.trace else ""
    lines = [f"config {Path(config_path).resolve()}"]
    if cfg.log_file:
        lines.append(f"log file {Path(cfg.log_file).resolve()} (level {cfg.log_level}{trace})")
    else:
        lines.append(f"log: console only - NO log file (level {cfg.log_level}{trace}); "
                     "set [log] file = kisshub.log to keep it")
    if cfg.hub.links_file:
        lines.append(f"links file {Path(cfg.hub.links_file).resolve()} "
                     "(one JSON line per finished AX.25 link)")
    else:
        lines.append("links file: off - finished AX.25 links are not written "
                     "([log] links_file)")
    return lines


def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kisshub", description="KISS TNC hub for TinyBox")
    ap.add_argument("-c", "--config", default="kisshub.conf")
    args = ap.parse_args(argv)
    try:
        cfg = load(args.config)
    except ConfigError as exc:
        print(f"kisshub: {exc}", file=sys.stderr)
        return 2
    setup_logging(cfg.log_level, cfg.log_file)
    log = logging.getLogger("kisshub")
    log.info("kisshub %s: %s (%s), KISS-TCP %s:%d", VERSION, cfg.tnc.profile.name,
             cfg.tnc.profile.notes, cfg.hub.listen, cfg.hub.port)
    for line in log_lines(args.config, cfg):
        log.info("%s", line)
    try:
        asyncio.run(main(cfg))
    except KeyboardInterrupt:
        log.info("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(run())
