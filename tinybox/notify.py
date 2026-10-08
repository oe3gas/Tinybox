"""Mail notice for TinyBox clients (PLANUNG.md 12.3, C1).

When private mail for a local user arrives, the mailbox sends one UI frame

    to TBMAIL:   OE3ABC 2 new

(call of the addressee, number of unread private messages). A TinyBox client
that hears it shows the notice without being connected; for everybody else
it is a readable line on the monitor. Only local mail (not mail waiting to be
forwarded or held), at most one frame per call and minute - more mail within
that minute is announced once at the end of it, with the new count.
"""

from __future__ import annotations

import asyncio
import logging
import time

from .config import base_call

log = logging.getLogger(__name__)

UI_DEST = "TBMAIL"
MIN_GAP_SEC = 60


class MailNotifier:
    def __init__(self, app) -> None:
        self.app = app
        self._last: dict[str, float] = {}
        self._waiting: set[str] = set()
        app.bus.subscribe("message.created", self._on_created)

    def _on_created(self, _name: str, data: dict) -> None:
        msg = data.get("message")
        if (msg is None or msg.type != "P" or msg.fwd != ""
                or not self.app.cfg.client.mail_notify):
            return
        self.notify(base_call(msg.to_call))

    def notify(self, call: str) -> None:
        send = self.app.service.chat.ui_send
        if send is None or call in self._waiting:
            return
        wait = self._last.get(call, 0) + MIN_GAP_SEC - time.monotonic()
        if wait > 0:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return
            self._waiting.add(call)
            loop.call_later(wait, self._later, call)
            return
        n = len(self.app.service.unread_for(call))
        if n:
            self._last[call] = time.monotonic()
            send(UI_DEST, f"{call} {n} new")

    def _later(self, call: str) -> None:
        self._waiting.discard(call)
        self.notify(call)
