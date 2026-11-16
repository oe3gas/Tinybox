"""The TCP link to Direwolf's AGW port: connect, reconnect, read frames (R9).

TinyBox (tinybox/adapters/agw.py) and client (tbclient/links.py) had the same loop
twice: open the connection, warn once if Direwolf is not there, retry, read frame
after frame, survive one bad frame, clean up and reconnect when the link breaks.
That loop is here; what each program sends after connecting and does with the
frames stays in its own class (the hooks below).

    class MyAgw(AgwClient):
        def agw_address(self):  return host, port, retry_seconds
        def agw_opened(self):   send 'R', 'X' ...  (self._writer is set)
        def agw_frame(self, f): handle one frame
        def agw_closed(self):   clean up (self._writer still set, closing)
"""

from __future__ import annotations

import asyncio
import logging

from .agw import AgwProtocolError, Frame, read_frame
from .termcolor import OK


def parse_fork(data: bytes) -> dict:
    """'F' answer of the TinyBox Direwolf fork (CR112): "fork=2026-11-15 features=Q,E,O"
    -> {"version": "2026-11-15", "features": ["E", "O", "Q"]}."""
    words = dict(w.split("=", 1) for w in data.decode("ascii", "replace").split() if "=" in w)
    return {"version": words.get("fork", ""),
            "features": sorted(filter(None, words.get("features", "").split(",")))}


class AgwClient:
    """Base class: keeps the AGW connection open. Subclasses fill in the hooks."""

    def __init__(self, log: logging.Logger) -> None:
        self._agw_log = log
        self._writer: asyncio.StreamWriter | None = None

    # --- hooks ---

    def agw_address(self) -> tuple[str, int, float]:
        """(host, port, seconds between attempts) - asked before every attempt, so a
        reloaded config takes effect at the next reconnect."""
        raise NotImplementedError

    def agw_opened(self) -> None:
        """Connected: send the opening frames."""

    def agw_frame(self, frame: Frame) -> None:
        """One frame from Direwolf."""

    def agw_closed(self) -> None:
        """The link is gone (or the task is cancelled): drop what hangs on it."""

    # --- the link ---

    def write_frame(self, frame: Frame) -> bool:
        w = self._writer
        if w is None or w.is_closing():
            return False
        w.write(frame.pack())
        return True

    async def run(self) -> None:
        log = self._agw_log
        warned = False
        while True:
            host, port, retry = self.agw_address()
            try:
                reader, writer = await asyncio.open_connection(host, port)
            except OSError as exc:
                # warn once, then retry quietly until Direwolf is back
                (log.debug if warned else log.error)(
                    "Direwolf AGW %s:%d not reachable (%s), retrying every %ss",
                    host, port, exc, f"{retry:g}")
                warned = True
                await asyncio.sleep(retry)
                continue
            warned = False
            log.info("connected to Direwolf AGW %s:%d", host, port, extra=OK)
            self._writer = writer
            try:
                self.agw_opened()
                while True:
                    frame = await read_frame(reader)
                    try:
                        self.agw_frame(frame)
                    except Exception:      # one bad frame must not take the radio link down
                        log.exception("error handling AGW frame '%s' from %s",
                                      frame.kind, frame.call_from or "-")
            except (asyncio.IncompleteReadError, ConnectionError, AgwProtocolError,
                    OSError) as exc:
                log.error("AGW connection lost: %s", exc or type(exc).__name__)
            except Exception:
                log.exception("AGW link error, reconnecting")
            finally:
                try:
                    self.agw_closed()
                finally:
                    self._writer = None
                    writer.close()
            await asyncio.sleep(retry)
