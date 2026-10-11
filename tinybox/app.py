"""Wires the building blocks together."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from .config import Config
from .events import EventBus
from .service import MessageService
from .session import SessionRegistry
from .store import Store, utc_now


@dataclass
class App:
    cfg: Config
    store: Store
    bus: EventBus
    service: MessageService
    registry: SessionRegistry
    started: str = field(default_factory=utc_now)
    agw: Any = None                      # AgwAdapter, set when running
    stop_event: asyncio.Event | None = None
    web_login_url: str | None = None     # set when the web GUI runs
    brocast: Any = None                  # BrocastPublisher, set when publishing
    forward: Any = None                  # ForwardModule, only with [forward] enabled = yes
    shutdown: Any = None                 # ShutdownTimer (SHUTDOWN with warning)
    restart: bool = False                # stop for a restart (RESTART), not for good
    config_path: str | None = None       # tinybox.conf, checked again before RESTART

    @classmethod
    def create(cls, cfg: Config, db_path: str | None = None) -> "App":
        store = Store(db_path or cfg.storage.data_dir / "tinybox.db")
        bus = EventBus()
        service = MessageService(store, bus, cfg)
        service.assign_missing_bids()          # schema 4 -> 5, no-op afterwards
        app = cls(cfg, store, bus, service, SessionRegistry(cfg.mailbox.max_users))
        from .shutdown import ShutdownTimer
        app.shutdown = ShutdownTimer(app)
        return app
