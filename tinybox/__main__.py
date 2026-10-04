"""Start TinyBox:  python -m tinybox [-c tinybox.conf]"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime

from . import VERSION, config, texts
from .adapters import agw, brocast, inbox, sysop, telnet, web
from .app import App

log = logging.getLogger("tinybox")

SHUTDOWN_GRACE_SEC = 10


def setup_logging(cfg: config.Config) -> sysop.MonitorFilter:
    """Console, plus an optional plain-text log file if [logging] log_dir is set.
    Returns the console monitor filter (switched with MON ON/OFF)."""
    cfg.storage.data_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(cfg.logging.level)

    console_filter = sysop.MonitorFilter(cfg.console.monitor)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
    console.addFilter(console_filter)
    root.addHandler(console)

    if cfg.logging.log_dir is not None:
        name = f"Tinybox_log_{datetime.now():%Y-%m-%d_%H-%M-%S}.log"
        logfile = logging.FileHandler(cfg.logging.log_dir / name, encoding="utf-8")
        logfile.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"))
        logfile.addFilter(sysop.MonitorFilter(cfg.logging.monitor))
        root.addHandler(logfile)
        log.info("log file: %s", cfg.logging.log_dir / name)
    return console_filter


async def housekeeping(app: App) -> None:
    # every minute: bulletins from the inbox may be valid for only 90 minutes
    while True:
        app.service.purge_expired()
        await asyncio.sleep(60)


async def close_sessions(app: App) -> None:
    """Say goodbye to connected users and give them time to receive it."""
    for s in app.registry:
        s.out(texts.SHUTDOWN)
        s.close()
    for _ in range(SHUTDOWN_GRACE_SEC * 10):
        if len(app.registry) == 0:
            return
        await asyncio.sleep(0.1)


async def run(cfg: config.Config, monitor_filter: sysop.MonitorFilter) -> None:
    app = App.create(cfg)
    app.stop_event = asyncio.Event()
    log.info("TinyBox %s starting, mailbox %s, sysop %s",
             VERSION, cfg.station.mailbox_call, cfg.station.sysop_call)
    log.info("data directory: %s", cfg.storage.data_dir)

    servers = []
    if cfg.telnet.enabled:
        servers.append(await telnet.start(app))
    web_server = None
    if cfg.web.enabled:
        web_server = await web.start(app)
        # the login link contains the secret token: console only, never the log file
        print(f"\n  Web GUI login:  {app.web_login_url}\n", flush=True)
    app.agw = agw.AgwAdapter(app)
    tasks = [asyncio.create_task(app.agw.run()),
             asyncio.create_task(housekeeping(app))]
    if cfg.brocast.publish:
        tasks.append(await brocast.start(app))
    if cfg.inbox.enabled:
        tasks.append(await inbox.start(app))
    if cfg.mqtt.enabled:
        log.warning("[mqtt] enabled = yes, but MQTT follows in milestone M5 - ignored.")

    if cfg.console.enabled and sys.stdin is not None and sys.stdin.isatty():
        console = sysop.SysopConsole(app, monitor_filter)
        console.start()
        console.start_stdin()

    try:
        await app.stop_event.wait()
        await close_sessions(app)
    finally:
        for task in tasks:
            task.cancel()
        for server in servers:
            server.close()
        if web_server is not None:
            web_server.close()
        await asyncio.gather(*tasks, return_exceptions=True)
        app.store.close()
        log.info("TinyBox stopped.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tinybox", description="TinyBox mailbox")
    parser.add_argument("-c", "--config", default="tinybox.conf",
                        help="path to tinybox.conf (default: ./tinybox.conf)")
    args = parser.parse_args(argv)
    try:
        cfg = config.load(args.config)
    except config.ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2
    monitor_filter = setup_logging(cfg)
    try:
        asyncio.run(run(cfg, monitor_filter))
    except KeyboardInterrupt:
        log.info("TinyBox stopped (Ctrl+C).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
