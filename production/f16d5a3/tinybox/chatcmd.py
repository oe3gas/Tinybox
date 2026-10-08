"""User side of the chat: command C in the mailbox, and /commands inside a board.

Inside a board every line is chat text, except lines starting with "/":
    /Q  /EX  ^Z   back to the mailbox
    /W            who is in this board
    /L            list all boards
    /J board      change to another board
    /H            help
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import texts
from .config import ChatBoard

if TYPE_CHECKING:
    from .session import Session

CTRL_Z = "\x1a"


def _time(iso: str) -> str:
    """2026-10-04T14:32:05Z -> 10-04 14:32"""
    return f"{iso[5:10]} {iso[11:16]}"


def list_boards(s: Session) -> None:
    hub = s.service.chat
    rows = [texts.CHAT_LIST_HEADER]
    for i, b in enumerate(hub.boards, 1):
        rows.append(texts.CHAT_LIST_ROW.format(n=i, board=b.name, keep=b.keep_label,
                                               users=len(hub.members(b.name)),
                                               desc=b.description))
    s.out(*rows, texts.CHAT_LIST_FOOT)


def cmd_chat(s: Session, arg: str) -> None:
    """Mailbox command C [board]: without a board, list the boards."""
    hub = s.service.chat
    if not hub.enabled:
        s.out(texts.CHAT_OFF)
        return
    if s.origin == "sysop":       # the chat is for users on radio/telnet only
        s.out(texts.CHAT_NOT_CONSOLE)
        return
    if not arg:
        list_boards(s)
        return
    board = hub.find(arg)
    if board is None:
        s.out(texts.CHAT_NO_BOARD.format(board=arg.upper()))
        return
    enter(s, board)


def enter(s: Session, board: ChatBoard) -> None:
    from .session import State  # local import avoids a cycle
    hub = s.service.chat
    lines = [texts.CHAT_HEADER.format(board=board.name, desc=board.description,
                                      keep=board.keep_label)]
    if board.live:
        lines.append(texts.CHAT_LIVE_NOTE)
    else:
        history = hub.history(board)
        if history:
            lines.append(texts.CHAT_HISTORY.format(keep=board.keep_label))
            lines += [texts.CHAT_HISTORY_ROW.format(time=_time(c.created), call=c.call,
                                                    text=c.text) for c in history]
            lines.append(texts.CHAT_HISTORY_END)
        else:
            lines.append(texts.CHAT_HISTORY_NONE.format(keep=board.keep_label))
    hub.join(s, board)
    lines.append(_who_line(s))
    lines.append(texts.CHAT_HINT)
    s.state = State.CHAT
    s.out(*lines)


def _who_line(s: Session) -> str:
    others = [m.call for m in s.service.chat.members(s.chat_board or "") if m is not s]
    if not others:
        return texts.CHAT_ALONE
    return texts.CHAT_WHO.format(calls=", ".join(others))


def _quit(s: Session) -> None:
    from .session import State
    board = s.chat_board
    s.service.chat.leave(s)
    s.state = State.COMMAND
    s.out(texts.CHAT_BACK.format(board=board))


def handle(s: Session, line: str) -> None:
    """One input line while in a board."""
    hub = s.service.chat
    if s.chat_board is None or hub.cfg.chat.board(s.chat_board) is None:
        _quit(s)
        return
    if CTRL_Z in line:
        text = line.split(CTRL_Z, 1)[0].strip()
        if text:
            hub.say(s, text[:hub.cfg.chat.max_line])
        _quit(s)
        return
    text = line.strip()
    if not text:
        return
    if text.startswith("/"):
        cmd, _, arg = text[1:].partition(" ")
        cmd = cmd.upper()
        if cmd in ("Q", "QUIT", "EX", "B"):
            _quit(s)
        elif cmd in ("W", "WHO"):
            s.out(_who_line(s))
        elif cmd in ("L", "LIST"):
            list_boards(s)
        elif cmd in ("J", "JOIN"):
            board = hub.find(arg) if arg.strip() else None
            if board is None:
                s.out(texts.CHAT_NO_BOARD.format(board=arg.strip().upper() or "?"))
            elif board.name == s.chat_board:
                s.out(texts.CHAT_ALREADY.format(board=board.name))
            else:
                enter(s, board)
        elif cmd in ("H", "HELP", "?"):
            s.out(*texts.CHAT_HELP)
        else:
            s.out(texts.CHAT_UNKNOWN)
        return
    if len(text) > hub.cfg.chat.max_line:
        text = text[:hub.cfg.chat.max_line]
        s.out(texts.CHAT_CUT.format(max=hub.cfg.chat.max_line))
    hub.say(s, text)
