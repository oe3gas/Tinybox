"""Tiny internal event bus.

Every source (radio, telnet, sysop, later MQTT) goes through the
MessageService, which publishes events here. Adapters such as the
future MQTT adapter subscribe to these events - the core stays unchanged.

Events:
    message.created   message.read   message.deleted   message.edited
    message.expired   (ids=[...], bulletins removed by housekeeping)
    session.connected session.disconnected
    chat.joined chat.left (board, call)   chat.message (board, call, text, created)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Callable

log = logging.getLogger(__name__)

Handler = Callable[[str, dict], None]


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, name: str, handler: Handler) -> None:
        """Subscribe to one event name, or '*' for all events."""
        self._subs[name].append(handler)

    def publish(self, name: str, **data) -> None:
        for handler in self._subs[name] + self._subs["*"]:
            try:
                handler(name, data)
            except Exception:  # a broken subscriber must not break the mailbox
                log.exception("event handler failed for %s", name)
