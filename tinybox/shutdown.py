"""Shutdown (and restart) with advance warning, like 'shutdown +1' on Unix.

The sysop starts it with SHUTDOWN [seconds] on the console (default 60) or
with the button in the web GUI. Every connected station gets a system
message at once and again shortly before (30 s, 10 s), stations that
connect in the meantime get it at login. SHUTDOWN CANCEL stops it.
RESTART [seconds] works the same way, then TinyBox starts again (new
tinybox.conf, new code after a git pull); RESTART CANCEL calls it off.

Client sessions get the message as a control line they can show:
    //SYS <seconds left> <text>          (seconds = -1: cancelled)
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from . import texts

if TYPE_CHECKING:
    from .app import App

log = logging.getLogger(__name__)

DEFAULT_SEC = 60
MAX_SEC = 3600
REMINDERS = (30, 10)


def _left_text(sec: int) -> str:
    if sec >= 120 and sec % 60 == 0:
        return f"{sec // 60} minutes"
    return "1 second" if sec == 1 else f"{sec} seconds"


class ShutdownTimer:
    def __init__(self, app: App) -> None:
        self.app = app
        self.task: asyncio.Task | None = None
        self.at: float | None = None          # time.monotonic() of the shutdown
        self.by = ""
        self.restart = False                  # stop for a restart

    @property
    def pending(self) -> bool:
        return self.task is not None and not self.task.done()

    def seconds_left(self) -> int | None:
        if not self.pending or self.at is None:
            return None
        return max(0, round(self.at - time.monotonic()))

    def schedule(self, seconds: int, by: str = "", restart: bool = False) -> int:
        """Start (or restart with a new time). Returns the seconds used.
        restart: TinyBox starts again afterwards (RESTART)."""
        seconds = max(0, min(int(seconds), MAX_SEC))
        if self.pending:
            self.task.cancel()
        self.restart = restart
        self.by = by or self.app.cfg.station.sysop_call
        self.at = time.monotonic() + seconds
        self.app.service.shutdown_left = self.seconds_left
        log.warning("%s in %d s (by %s)", "restart" if restart else "shutdown", seconds, self.by)
        if seconds > 0:                       # at once, before the console answers
            self.broadcast(self.message(seconds), seconds)
        self.task = asyncio.ensure_future(self._run())
        return seconds

    def cancel(self) -> bool:
        if not self.pending:
            return False
        self.task.cancel()
        self.task = None
        self.at = None
        self.app.service.shutdown_left = None
        log.warning("shutdown cancelled")
        self.broadcast(texts.SHUTDOWN_CANCELLED.format(mailbox=self.app.cfg.station.mailbox_call),
                       -1)
        return True

    def message(self, sec: int) -> str:
        tpl = texts.RESTART_WARNING if self.restart else texts.SHUTDOWN_WARNING
        return tpl.format(mailbox=self.app.cfg.station.mailbox_call,
                          sysop=self.by, left=_left_text(sec))

    def broadcast(self, text: str, sec: int) -> None:
        for s in self.app.registry:
            if s.closed:
                continue
            if s.client is not None:
                s.out(f"//SYS {sec} {text}")
            else:
                # on a line of its own, then the prompt again if the user was at it
                s.out("", text)
                s.prompt_again()

    async def _run(self) -> None:
        for mark in REMINDERS:
            left = self.seconds_left() or 0
            if mark < left:
                await asyncio.sleep(left - mark)
                self.broadcast(self.message(mark), mark)
        await asyncio.sleep(self.seconds_left() or 0)
        self.app.service.shutdown_left = None
        log.warning("restart now" if self.restart else "shutdown now")
        self.app.restart = self.restart
        if self.app.stop_event is not None:
            self.app.stop_event.set()
