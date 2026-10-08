"""Chat boards: fixed rooms set by the sysop in tinybox.conf ([chat_boards]).

A board is either "live" (lines go only to stations in the board right now)
or keeps a history for n hours/days (shown when a station joins).
The ChatHub knows who is in which board and delivers the lines; the
sessions themselves only call join/leave/say/react.

Every chat event gets a sequence number per board (hex 0-FF, wraps) and a
readable text form for TinyBox clients (PLANUNG.md 12.4):

    #4F OE3GAS: Servus             line
    #50 +OE3GAS /-                 joined (with APRS symbol, if the client sent one)
    #51 -OE3GAS                    left
    #52 OE3TEC *4F :+1             reaction to event 4F

Terminal users get the usual human text. Clients get the event line: if at
least one client in the board hears the mailbox directly (UI mode), the line
goes out ONCE as UI frame to TBCHAT-<board number>; clients without UI get
it as I-frame. The last 256 events per board are kept in memory for //RESEND.
"""

from __future__ import annotations

import logging
import re
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Callable

from . import texts
from .config import ChatBoard, Config
from .events import EventBus
from .store import ChatLine, Store, utc_now

if TYPE_CHECKING:
    from .session import Session

log = logging.getLogger(__name__)

SEQ_MOD = 256
MAX_UI_BOARD = 15          # TBCHAT-1 .. TBCHAT-15 (SSID)
UI_DEST = "TBCHAT"
REACTION_RE = re.compile(r"^[!-~]{1,8}$")    # an emoji code: :+1, <3, ~0A ...


def _iso_hours_ago(hours: int) -> str:
    t = datetime.now(timezone.utc) - timedelta(hours=hours)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


class ChatHub:
    def __init__(self, store: Store, bus: EventBus, cfg: Config) -> None:
        self.store = store
        self.bus = bus
        self.cfg = cfg
        self._members: dict[str, list[Session]] = {}
        self._seq: dict[str, int] = {}                       # last number per board
        self._recent: dict[str, deque[tuple[int, str]]] = {}  # for //RESEND
        # set by the AGW adapter: ui_send(dest_call, text) sends one UI frame
        self.ui_send: Callable[[str, str], None] | None = None

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

    def number(self, board: str) -> int:
        """1-based number of a board (0 if unknown)."""
        for i, b in enumerate(self.boards, 1):
            if b.name == board:
                return i
        return 0

    def members(self, board: str) -> list[Session]:
        return [s for s in self._members.get(board, []) if not s.closed]

    def total_members(self) -> int:
        return sum(len(self.members(b.name)) for b in self.boards)

    def history(self, board: ChatBoard) -> list[ChatLine]:
        if board.live or self.cfg.chat.history_lines == 0:
            return []
        return self.store.chat_recent(board.name, _iso_hours_ago(board.keep_hours),
                                      self.cfg.chat.history_lines)

    def last_seq(self, board: str) -> str:
        n = self._seq.get(board)
        return "-" if n is None else f"{n:X}"

    # --- membership -----------------------------------------------------

    def join(self, session: Session, board: ChatBoard) -> None:
        self.leave(session, quiet=False)
        self._members.setdefault(board.name, []).append(session)
        session.chat_board = board.name
        sym = session.client.symbol if session.client else ""
        self._deliver(board.name, f"+{session.call}" + (f" {sym}" if sym else ""),
                      texts.CHAT_JOINED.format(call=session.call, board=board.name),
                      sender=session)
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
            self._deliver(board, f"-{session.call}",
                          texts.CHAT_LEFT.format(call=session.call, board=board,
                                                 reason=reason), sender=session)
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
        self._deliver(board.name, f"{session.call}: {text}",
                      texts.CHAT_LINE.format(call=session.call, text=text), sender=session)
        self.bus.publish("chat.message", board=board.name, call=session.call,
                         text=text, created=now)

    def react(self, session: Session, ref: int, emoji: str) -> bool:
        """Reaction (emoji code) to event number ref of the session's board."""
        board = session.chat_board
        if board is None or not REACTION_RE.match(emoji) or not 0 <= ref < SEQ_MOD:
            return False
        target = self._line_of(board, ref)
        human = texts.CHAT_REACT.format(call=session.call, emoji=emoji,
                                        target=target[:40] if target else f"#{ref:X}")
        self._deliver(board, f"{session.call} *{ref:X} {emoji}", human, sender=session)
        return True

    def replay(self, board: str, first: int, last: int) -> list[str]:
        """Events first..last (inclusive, may wrap) still in memory."""
        count = (last - first) % SEQ_MOD + 1
        wanted = {(first + i) % SEQ_MOD for i in range(min(count, 64))}
        return [line for seq, line in self._recent.get(board, ()) if seq in wanted]

    # --- delivery -------------------------------------------------------

    def _line_of(self, board: str, ref: int) -> str:
        for seq, line in self._recent.get(board, ()):
            if seq == ref:
                text = line.split(" ", 1)[1] if " " in line else ""
                return text if ":" in text.split(" ", 1)[0] else ""
        return ""

    def _next_event(self, board: str, payload: str) -> str:
        seq = (self._seq.get(board, -1) + 1) % SEQ_MOD
        self._seq[board] = seq
        line = f"#{seq:X} {payload}"
        self._recent.setdefault(board, deque(maxlen=SEQ_MOD)).append((seq, line))
        return line

    def _deliver(self, board: str, payload: str, human: str, sender: Session) -> None:
        line = self._next_event(board, payload)
        members = self.members(board)
        ui_clients = [s for s in members if s.client and s.client.ui]
        n = self.number(board)
        sent_ui = False
        if ui_clients and self.ui_send is not None and 1 <= n <= MAX_UI_BOARD:
            self.ui_send(f"{UI_DEST}-{n}", line)
            sent_ui = True
        for s in members:
            if s.client:
                if not (sent_ui and s.client.ui):
                    s.out(line)            # clients get every event, also their own
            elif s is not sender:          # a terminal shows what was typed: no echo
                s.out(human)

    # --- housekeeping ---------------------------------------------------

    def purge(self) -> int:
        """Delete lines older than their board's keep time, and lines of
        boards that are gone or live now."""
        keep = {b.name: _iso_hours_ago(b.keep_hours) for b in self.boards if not b.live}
        n = self.store.chat_purge(keep)
        if n:
            log.info("chat: %s old line(s) deleted", n)
        return n
