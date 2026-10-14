"""python -m kisshub [-c kisshub.conf]

Ctrl+C ends kisshub cleanly: the TNC is switched back out of KISS first
(if the profile says so), so a terminal program or pk232py finds it at cmd:.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from . import VERSION
from .config import ConfigError, load, make_transport
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
    try:
        await hub.run()
    finally:
        await asyncio.shield(hub.stop())


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
    try:
        asyncio.run(main(cfg))
    except KeyboardInterrupt:
        log.info("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(run())
