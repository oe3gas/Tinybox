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
    #53 =OE3GAS /k                 new APRS symbol (no symbol: "=OE3GAS"), clients only
    #52 OE3TEC *4F :+1             reaction to event 4F
    #54 %OE3TEC 4 OE1ABC ?         link quality bars 1-5 per station, ? = no result
                                   yet (PLANUNG.md 14.4), clients only, not stored
    #55 !Connection to OE1ABC lost system text (after "-OE1ABC" when the link broke)

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

from . import chatimg, linkq, texts
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
        self._q_text: dict[str, str] = {}       # board -> last % event (link quality)
        self._q_at: dict[str, float] = {}       # board -> when it was sent
        self.images = chatimg.ChatImages(store, cfg)     # small images (CR12)

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
        """The last history_lines lines (old clients get them when joining)."""
        if board.live or self.cfg.chat.history_lines == 0:
            return []
        return self.store.chat_recent(board.name, _iso_hours_ago(board.keep_hours),
                                      self.cfg.chat.history_lines)

    # History on request (CR13): joining only tells how much is stored.

    def history_info(self, board: ChatBoard) -> tuple[int, str | None]:
        """(number of stored lines, time of the newest) - (0, None) for live boards."""
        if board.live or self.cfg.chat.history_lines == 0:
            return 0, None
        return self.store.chat_stats(board.name, _iso_hours_ago(board.keep_hours))

    def history_page(self, board: ChatBoard, n: int, after_iso: str | None = None,
                     before_iso: str | None = None) -> tuple[list[ChatLine], int]:
        """Up to n lines (at most history_lines per request), and how many older
        lines are left."""
        n = max(0, min(n, self.cfg.chat.history_lines))
        if board.live or n == 0:
            return [], 0
        return self.store.chat_page(board.name, _iso_hours_ago(board.keep_hours), n,
                                    after_iso, before_iso)

    def last_seq(self, board: str) -> str:
        n = self._seq.get(board)
        return "-" if n is None else f"{n:X}"

    # --- membership -----------------------------------------------------

    def join(self, session: Session, board: ChatBoard) -> None:
        self.leave(session, quiet=False)
        self._members.setdefault(board.name, []).append(session)
        session.chat_board = board.name
        session.ui_rx = (linkq.RxWindow(linkq.cfg_from(self.cfg.direwolf))
                         if session.client and session.client.ui else None)
        sym = session.client.symbol if session.client else ""
        self._deliver(board.name, f"+{session.call}" + (f" {sym}" if sym else ""),
                      texts.CHAT_JOINED.format(call=session.call, board=board.name),
                      sender=session)
        self.bus.publish("chat.joined", board=board.name, call=session.call)
        log.info("%s joined chat %s", session.call, board.name)

    def leave(self, session: Session, quiet: bool = False, reason: str = "",
              lost: bool = False) -> None:
        """lost: the radio link broke (Direwolf: retries used up) - clients also
        get a system line, so everybody sees why the station is gone."""
        board = session.chat_board
        if board is None:
            return
        session.chat_board = None
        session.ui_rx = None
        members = self._members.get(board, [])
        if session in members:
            members.remove(session)
        if not quiet:
            self._deliver(board, f"-{session.call}",
                          texts.CHAT_LEFT.format(call=session.call, board=board,
                                                 reason=reason), sender=session)
            if lost:
                self._deliver(board, "!" + texts.CHAT_LOST_SYS.format(call=session.call), None,
                              sender=session)
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
        # terminals read "[Image ...]" instead of an image reference (CR12)
        self._deliver(board.name, f"{session.call}: {text}",
                      texts.CHAT_LINE.format(call=session.call,
                                             text=chatimg.terminal_text(text)), sender=session)
        self.bus.publish("chat.message", board=board.name, call=session.call,
                         text=text, created=now)

    def react(self, session: Session, ref: int, emoji: str) -> bool:
        """Reaction (emoji code) to event number ref of the session's board."""
        board = session.chat_board
        if board is None or not REACTION_RE.match(emoji) or not 0 <= ref < SEQ_MOD:
            return False
        target = chatimg.terminal_text(self._line_of(board, ref))
        human = texts.CHAT_REACT.format(call=session.call, emoji=emoji,
                                        target=target[:40] if target else f"#{ref:X}")
        self._deliver(board, f"{session.call} *{ref:X} {emoji}", human, sender=session)
        return True

    def symbol_changed(self, session: Session) -> None:
        """The client chose another APRS symbol: tell the board at once (CR7),
        so every avatar of this station changes. Only for clients (2-3 bytes)."""
        board = session.chat_board
        if board is None or session.client is None:
            return
        sym = session.client.symbol
        self._deliver(board, f"={session.call}" + (f" {sym}" if sym else ""), None,
                      sender=session)

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

    def _deliver(self, board: str, payload: str, human: str | None, sender: Session) -> None:
        """human None: an event only for clients (terminals get nothing)."""
        line = self._next_event(board, payload)
        members = self.members(board)
        ui_clients = [s for s in members if s.client and s.client.ui]
        n = self.number(board)
        sent_ui = False
        if ui_clients and self.ui_send is not None and 1 <= n <= MAX_UI_BOARD:
            self.ui_send(f"{UI_DEST}-{n}", line)
            sent_ui = True
            seq = self._seq[board]
            for s in ui_clients:                # receive quote: they should hear it
                if s.ui_rx is not None:
                    s.ui_rx.sent(seq)
        for s in members:
            if s.client:
                if not (sent_ui and s.client.ui):
                    s.out(line)            # clients get every event, also their own
            elif s is not sender and human is not None:   # a terminal shows what was typed
                s.out(human)

    # --- link quality (PLANUNG.md 14.4) -----------------------------------

    QUALITY_MIN_SEC = 60        # at most one % event per board and minute

    def quality_tick(self, service, now: float | None = None) -> None:
        """Called after each round of Direwolf queries: per board one % event with
        the bars of all stations that have link data - only if something changed."""
        import time
        now = time.monotonic() if now is None else now
        for b in self.boards:
            members = self.members(b.name)
            if not members or not any(s.client for s in members):
                continue
            items = []
            for s in members:
                r = linkq.result_for(service, s.call, s)
                if r is not None or s.call in service.links:
                    items.append(f"{s.call} {linkq.bar_code(r)}")
            if not items:
                continue
            text = "%" + " ".join(items)
            if text == self._q_text.get(b.name):
                continue
            if now - self._q_at.get(b.name, -1e9) < self.QUALITY_MIN_SEC:
                continue
            self._q_text[b.name], self._q_at[b.name] = text, now
            self._deliver(b.name, text, None, sender=members[0])

    # --- housekeeping ---------------------------------------------------

    def purge(self) -> int:
        """Delete lines older than their board's keep time, and lines of
        boards that are gone or live now."""
        keep = {b.name: _iso_hours_ago(b.keep_hours) for b in self.boards if not b.live}
        n = self.store.chat_purge(keep)
        if n:
            log.info("chat: %s old line(s) deleted", n)
        m = self.images.purge()
        if m:
            log.info("chat: %s image(s) without a line deleted", m)
        return n
