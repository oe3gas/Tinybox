"""Chat boards: fixed rooms set by the sysop in tinybox.conf ([chat_boards]).

A board is either "live" (lines go only to stations in the board right now)
or keeps a history for n hours/days (shown when a station joins).
The ChatHub knows who is in which board and delivers the lines; the
sessions themselves only call join/leave/say.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from . import texts
from .config import ChatBoard, Config
from .events import EventBus
from .store import ChatLine, Store, utc_now

if TYPE_CHECKING:
    from .session import Session

log = logging.getLogger(__name__)


def _iso_hours_ago(hours: int) -> str:
    t = datetime.now(timezone.utc) - timedelta(hours=hours)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


class ChatHub:
    def __init__(self, store: Store, bus: EventBus, cfg: Config) -> None:
        self.store = store
        self.bus = bus
        self.cfg = cfg
        self._members: dict[str, list[Session]] = {}

    # --- boards ---------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self.cfg.chat.enabled and bool(self.cfg.chat.boards)

    @property
    def boards(self) -> list[ChatBoard]:
        return self.cfg.chat.boards

    def find(self, arg: str) -> ChatBoard | None:
        """Board by name, or by its number in the board list (1, 2, ...)."""
        arg = arg.strip()
        if arg.isdigit():
            n = int(arg)
            return self.boards[n - 1] if 1 <= n <= len(self.boards) else None
        return self.cfg.chat.board(arg)

    def members(self, board: str) -> list[Session]:
        return [s for s in self._members.get(board, []) if not s.closed]

    def total_members(self) -> int:
        return sum(len(self.members(b.name)) for b in self.boards)

    def history(self, board: ChatBoard) -> list[ChatLine]:
        if board.live or self.cfg.chat.history_lines == 0:
            return []
        return self.store.chat_recent(board.name, _iso_hours_ago(board.keep_hours),
                                      self.cfg.chat.history_lines)

    # --- membership -----------------------------------------------------

    def join(self, session: Session, board: ChatBoard) -> None:
        self.leave(session, quiet=False)
        self._members.setdefault(board.name, []).append(session)
        session.chat_board = board.name
        self._broadcast(board.name, texts.CHAT_JOINED.format(call=session.call,
                                                             board=board.name), skip=session)
        self.bus.publish("chat.joined", board=board.name, call=session.call)
        log.info("%s joined chat %s", session.call, board.name)

    def leave(self, session: Session, quiet: bool = False, reason: str = "") -> None:
        board = session.chat_board
        if board is None:
            return
        session.chat_board = None
        members = self._members.get(board, [])
        if session in members:
            members.remove(session)
        if not quiet:
            self._broadcast(board, texts.CHAT_LEFT.format(call=session.call, board=board,
                                                          reason=reason), skip=session)
        self.bus.publish("chat.left", board=board, call=session.call)
        log.info("%s left chat %s%s", session.call, board, reason)

    # --- talking --------------------------------------------------------

    def say(self, session: Session, text: str) -> None:
        board = self.cfg.chat.board(session.chat_board or "")
        if board is None:
            return
        now = utc_now()
        if not board.live:
            self.store.chat_add(board.name, session.call, text, now)
        # the sender's own terminal shows what was typed - no echo
        self._broadcast(board.name, texts.CHAT_LINE.format(call=session.call, text=text),
                        skip=session)
        self.bus.publish("chat.message", board=board.name, call=session.call,
                         text=text, created=now)

    def _broadcast(self, board: str, line: str, skip: Session | None = None) -> None:
        for s in self.members(board):
            if s is not skip:
                s.out(line)

    # --- housekeeping ---------------------------------------------------

    def purge(self) -> int:
        """Delete lines older than their board's keep time, and lines of
        boards that are gone or live now."""
        keep = {b.name: _iso_hours_ago(b.keep_hours) for b in self.boards if not b.live}
        n = self.store.chat_purge(keep)
        if n:
            log.info("chat: %s old line(s) deleted", n)
        return n
