"""TinyBox client protocol (PLANUNG.md section 12).

A TinyBox client announces itself right after login with one line:

    //CLIENT TB1 v=2026.10.11 caps=CHAT,UI sym=/-

and the mailbox answers with the features both sides know:

    //OK TB1 caps=CHAT,UI

v = client version (date). If the client in this repository is newer, the
answer also has cur=<newest version> and news=<number of the feature bulletin
in the rubric TBNEWS>, see clientnews.py.

From then on the session is in client mode: no prompts, and in a chat board
the client gets machine-readable lines instead of the human text:

    //IN <n> <board> <keep> <last seq>     entered board number n
    //H <unix time> <call>: <text>         history line (boards with history)
    //WHO <call>[=<sym>] ...               who else is in the board
    //OUT <board>                          left the board
    #<seq> ...                             chat events, format see chat.py

Other client commands:
    //BOARDS              -> //B <n> <board> <keep> <users> <description> ... //BEND
    //RESEND <a>-<b>      (inside a board) events a..b again, only to this client
    //LOST <a>-<b>        (inside a board) events a..b missed, too many to send again:
                          only counted for the receive quote (PLANUNG.md 14.3)
    //SYM <symbol>|-      new APRS symbol; inside a board the others get "=<call> <sym>"
    //HIST max=<n> [since=<unix>] [before=<unix>]   (inside a board) stored lines on
                          request, only to this client: //H ... //HEND <n> <older>
                          (CR13; //IN tells hist=<count> last=<unix> now=<unix>)
    //MOTD                (inside a board) -> //MOTD <crc> <text> | //MOTD -  (CR3;
                          //IN tells motd=<crc>, the client asks only if it changed)
    //MLIST, //GET, //SEND ...   offline mailbox, see clientsync.py

caps: CHAT = chat lines in the format above, UI = the client hears the
mailbox directly and takes chat events from the UI frames to TBCHAT-<n>
instead of I-frames. UI is only granted on radio sessions.
SYNC = offline mailbox commands, SYNC2 = delta sync (//SYNC, //BSYNC, CR26),
Z = message texts may come LZHUF-compressed
(binary, radio sessions only).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from . import clientnews, clientsync

if TYPE_CHECKING:
    from .session import Session

PROTO = "TB1"
KNOWN_CAPS = ("CHAT", "UI", "SYNC", "SYNC2", "Z")
# APRS symbol: table ('/', '\' or an overlay 0-9/A-Z) + symbol code (any printable)
SYMBOL_RE = re.compile(r"^[/\\0-9A-Z][!-~]$")


@dataclass
class ClientInfo:
    proto: str
    caps: set[str] = field(default_factory=set)
    symbol: str = ""
    version: str = ""          # v= of the client ('' = older client without it)

    @property
    def ui(self) -> bool:
        return "UI" in self.caps


def _parse_args(parts: list[str]) -> dict[str, str]:
    args = {}
    for p in parts:
        key, sep, value = p.partition("=")
        if sep:
            args[key.lower()] = value
    return args


def handle(s: Session, line: str) -> None:
    """One line starting with '//' (in the mailbox or inside a board)."""
    parts = line.strip()[2:].split()
    if not parts:
        return
    cmd = parts[0].upper()
    if cmd == "CLIENT":
        _client(s, parts[1:])
    elif s.client is None:
        s.out("//ERR not a client session")
    elif cmd == "BOARDS":
        _boards(s)
    elif cmd == "RESEND":
        _resend(s, parts[1:])
    elif cmd == "LOST":
        _resend(s, parts[1:], replay=False)
    elif cmd == "SYM":
        _symbol(s, parts[1:])
    elif cmd == "HIST":
        _hist(s, parts[1:])
    elif cmd == "MOTD":
        _motd(s)
    elif cmd in clientsync.COMMANDS:
        clientsync.handle(s, cmd, parts[1:])
    else:
        s.out(f"//ERR unknown {cmd}")


def _client(s: Session, parts: list[str]) -> None:
    if not parts or parts[0].upper() != PROTO:
        s.out("", f"//ERR protocol {PROTO} only")
        return
    args = _parse_args(parts[1:])
    wanted = {c.strip().upper() for c in args.get("caps", "").split(",") if c.strip()}
    caps = {c for c in wanted if c in KNOWN_CAPS}
    if s.origin != "radio" or s.service.chat.ui_send is None:
        caps.discard("UI")        # telnet, or no radio link: chat lines come as I-frames
    if s.origin != "radio" or not hasattr(s.transport, "write_bytes"):
        caps.discard("Z")         # compressed texts are binary: radio (AGW) only
    symbol = args.get("sym", "")
    s.client = ClientInfo(PROTO, caps, symbol if SYMBOL_RE.match(symbol) else "",
                          args.get("v", "")[:20])
    # newer client available (CR18): tell the version and the feature bulletin
    extra = ""
    cur = clientnews.client_version()
    if cur and clientnews.version_key(s.client.version) < clientnews.version_key(cur):
        extra = f" cur={cur}"
        if s.service.client_news_id:
            extra += f" news={s.service.client_news_id}"
    # the human prompt is still on the line: start the answer on a fresh line
    s.out("", f"//OK {PROTO} caps={','.join(sorted(caps))}{extra}")


def _iso(unix: str) -> str | None:
    if not unix.isdigit():
        return None
    return datetime.fromtimestamp(int(unix), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _motd(s: Session) -> None:
    """//MOTD: text of the current board's message of the day (CR3)
    -> //MOTD <crc> <text>, or //MOTD - without one."""
    board = s.service.chat.cfg.chat.board(s.chat_board or "")
    if board is None:
        s.out("//ERR motd")
        return
    s.out(f"//MOTD {board.motd_crc} {board.motd}" if board.motd else "//MOTD -")


def _hist(s: Session, parts: list[str]) -> None:
    """//HIST max=n [since=unix] [before=unix]: history lines on request (CR13)."""
    from .chatcmd import history_rows
    hub = s.service.chat
    board = hub.cfg.chat.board(s.chat_board or "")
    args = _parse_args(parts)
    if board is None or not args.get("max", "").isdigit():
        s.out("//ERR hist")
        return
    lines, older = hub.history_page(board, int(args["max"]),
                                    after_iso=_iso(args.get("since", "")),
                                    before_iso=_iso(args.get("before", "")))
    s.out(*history_rows(lines), f"//HEND {len(lines)} {older}")


def _symbol(s: Session, parts: list[str]) -> None:
    """//SYM <symbol>  ("-" = none): new APRS symbol, the board sees it at once."""
    sym = parts[0] if parts else ""
    if sym == "-":
        sym = ""
    if sym and not SYMBOL_RE.match(sym):
        s.out("//ERR sym")
        return
    if sym != s.client.symbol:
        s.client.symbol = sym
        s.service.chat.symbol_changed(s)


def _boards(s: Session) -> None:
    hub = s.service.chat
    rows = []
    if hub.enabled and s.origin != "sysop":
        for i, b in enumerate(hub.boards, 1):
            rows.append(f"//B {i} {b.name} {b.keep_label} {len(hub.members(b.name))} "
                        f"{b.description}".rstrip())
    s.out(*rows, "//BEND")


def _resend(s: Session, parts: list[str], replay: bool = True) -> None:
    m = re.match(r"^([0-9A-Fa-f]{1,2})-([0-9A-Fa-f]{1,2})$", parts[0] if parts else "")
    if s.chat_board is None or not m:
        s.out("//ERR resend" if replay else "//ERR lost")
        return
    first, last = int(m.group(1), 16), int(m.group(2), 16)
    if s.ui_rx is not None:                 # missed UI frames: receive quote (14.3)
        s.ui_rx.missed(first, last)
    if replay:
        lines = s.service.chat.replay(s.chat_board, first, last)
        if lines:
            s.out(*lines)
