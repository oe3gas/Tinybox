"""Start the TinyBox client:  python -m tbclient [-c tbclient.conf]"""

from __future__ import annotations

import argparse
import asyncio
import logging
import socket
import sys

from . import VERSION, config
from .core import ClientCore
from .web import WebServer


def main() -> int:
    ap = argparse.ArgumentParser(prog="tbclient", description="TinyBox client")
    ap.add_argument("-c", "--config", default="tbclient.conf")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="[tbcli] %(asctime)s %(message)s", datefmt="%H:%M:%S",
                        stream=sys.stdout)
    try:
        cfg = config.load(args.config)
    except (config.ConfigError, ValueError) as exc:
        print(f"Config error: {exc}")
        return 1
    log = logging.getLogger("tbclient")
    log.info("TinyBox client %s - %s -> %s via %s", VERSION, cfg.mycall, cfg.tinybox_call,
             cfg.link)
    for line in config.radio_lines(cfg):
        log.info("%s", line)

    async def run() -> None:
        core = ClientCore(cfg)
        await WebServer(core).start()
        if cfg.web_host in ("0.0.0.0", "::"):
            log.info("open http://%s:%s/ (or http://127.0.0.1:%s/ on this PC)",
                     socket.gethostname(), cfg.web_port, cfg.web_port)
        await core.run()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
    except OSError as exc:
        print(f"Error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
