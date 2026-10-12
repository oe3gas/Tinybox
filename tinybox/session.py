"""One user session, independent of the transport (AGW, telnet, ...).

The adapter feeds complete input lines into Session.handle_line() and
gives the session a Transport to write to and to close the connection.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Protocol

from . import texts
from .config import Config
from .service import MessageService, ServiceError
from .store import utc_now

log = logging.getLogger("tinybox.monitor")

MAX_LINE = 1024
CTRL_Z = "\x1a"


class Transport(Protocol):
    def write(self, text: str) -> None:
        """Send text. Lines are separated by CR ('\\r')."""

    def close(self) -> None:
        """Disconnect after pending output is sent."""

    def abort_output(self) -> None:
        """Drop output that is still queued (command A)."""


class State(Enum):
    COMMAND = 1
    SEND_SUBJECT = 2
    SEND_BODY = 3
    CLOSED = 4
    CHAT = 5
    COLLECT = 6     # client protocol: n raw lines for a callback (//SEND)


class Session:
    def __init__(self, call: str, service: MessageService, cfg: Config,
                 transport: Transport, origin: str, sysop: bool = False,
                 monitor: bool = True) -> None:
        self.call = call
        self.service = service
        self.cfg = cfg
        self.transport = transport
        self.origin = origin
        self.sysop = sysop
        self.monitor = monitor  # log traffic to logger "tinybox.monitor"
        self.started = utc_now()
        self.state = State.COMMAND
        self.chat_board: str | None = None  # set by ChatHub while in a board
        self.client = None  # clientproto.ClientInfo after //CLIENT (TinyBox client)
        self.ui_rx = None   # linkq.RxWindow while a UI client is in a chat board
        # message being composed
        self._to = ""
        self._type = "P"
        self._at = ""
        self._bid: str | None = None
        self._subject = ""
        self._body: list[str] = []
        self._body_bytes = 0
        # client protocol: lines to collect (see collect())
        self._collect_n = 0
        self._collect_lines: list[str] = []
        self._collect_done = None
        self._collect_back = State.COMMAND
        # client protocol: raw bytes to collect (image upload, CR12 - see collect_raw())
        self.raw_need = 0
        self._raw_chunk = None
        self._raw_done = None

    # --- output ---------------------------------------------------------

    def out(self, *lines: str) -> None:
        text = "\r".join(lines) + "\r"
        if self.monitor:
            for line in lines:
                log.info("%s > %s", self.call, line)
        self.transport.write(text)

    def prompt(self) -> None:
        if self.client is not None:     # a client program needs no prompt
            return
        self.transport.write(texts.PROMPT_SYSOP if self.sysop else texts.PROMPT)

    def prompt_again(self) -> None:
        """After a message in between (system message): the prompt once more,
        but not while the user types a message or chats."""
        if self.state == State.COMMAND:
            self.prompt()

    def error(self, exc: ServiceError, msg_id: int | str = "") -> None:
        if exc.code == "not_found":
            self.out(texts.NO_SUCH_MSG.format(id=msg_id))
        elif exc.code == "not_allowed" and "third party" in str(exc):
            self.out(texts.THIRD_PARTY_OFF.format(sysop=self.cfg.station.sysop_call))
        elif exc.code == "not_allowed":
            self.out(texts.NOT_ALLOWED)
        elif exc.code == "invalid_call":
            self.out(texts.INVALID_CALL.format(call=str(exc)))
        elif exc.code == "too_large":
            self.out(texts.TOO_LARGE.format(max=self.cfg.mailbox.max_msg_bytes))
        elif exc.code == "invalid_address":
            self.out(texts.INVALID_ADDRESS.format(addr=str(exc)))
        elif exc.code == "duplicate":
            self.out(texts.DUPLICATE_BID.format(bid=str(exc)))
        elif exc.code == "no_forward":
            self.out(texts.NO_FORWARD.format(addr=str(exc)))
        elif exc.code == "bad_rubric":
            self.out(texts.BAD_RUBRIC.format(rubric=str(exc),
                                             rubrics=" ".join(self.service.writable_rubrics())))
        else:
            self.out(texts.INVALID_VALUE.format(value=str(exc)))

    # --- lifecycle ------------------------------------------------------

    @property
    def idle_exempt(self) -> bool:
        """In a chat board, reading along without typing is allowed."""
        return self.state == State.CHAT

    @property
    def closed(self) -> bool:
        return self.state == State.CLOSED

    def start(self) -> None:
        self.service.login(self.call, self.origin)
        mailbox = self.cfg.station.mailbox_call
        lines = [texts.HELLO.format(mailbox=mailbox, call=self.call)]
        if self.cfg.mailbox.welcome_enabled and self.cfg.mailbox.welcome_text:
            lines.append(self.cfg.mailbox.welcome_text)
        n = len(self.service.unread_for(self.call))
        lines.append(texts.NEW_MSGS.format(n=n) if n else texts.NO_NEW_MSGS)
        chat = self.service.chat
        if chat.enabled and chat.total_members():
            lines.append(texts.CHAT_ACTIVE.format(n=chat.total_members()))
        left = self.service.shutdown_left() if self.service.shutdown_left else None
        if left is not None:             # shutdown pending: warn new stations too
            lines.append(texts.SHUTDOWN_WARNING.format(
                mailbox=mailbox, sysop=self.cfg.station.sysop_call,
                left="1 second" if left == 1 else f"{left} seconds"))
        self.out(*lines)
        self.prompt()

    def close(self) -> None:
        """Log off from the mailbox side (command B, timeout)."""
        if self.state != State.CLOSED:
            self.state = State.CLOSED
            self.transport.close()

    def end(self, lost: bool = False) -> None:
        """Called by the adapter when the connection is gone (lost: retries used up)."""
        if self.state in (State.SEND_SUBJECT, State.SEND_BODY):
            log.info("%s disconnected while sending, message discarded", self.call)
        self.state = State.CLOSED
        self.service.chat.leave(self, reason=texts.CHAT_REASON_LOST if lost
                                else texts.CHAT_REASON_DISC, lost=lost)
        self.service.logout(self.call, self.origin)

    # --- input ----------------------------------------------------------

    def handle_line(self, line: str) -> None:
        if self.closed:
            return
        line = line[:MAX_LINE]
        if self.monitor:
            log.info("%s < %s", self.call, line)
        try:
            if self.state == State.COLLECT:
                self._on_collect(line)
            elif self.state == State.COMMAND:
                from . import commands  # local import avoids a cycle
                commands.dispatch(self, line)
            elif self.state == State.SEND_SUBJECT:
                self._on_subject(line)
            elif self.state == State.SEND_BODY:
                self._on_body_line(line)
            elif self.state == State.CHAT:
                from . import chatcmd  # local import avoids a cycle
                chatcmd.handle(self, line)
        except Exception:
            # A bug or a storage error must not kill the connection (or, over
            # AGW, the whole radio link). Log the traceback, tell the user.
            logging.getLogger("tinybox").exception(
                "%s: internal error handling %r (state %s)", self.call, line, self.state.name)
            if self.state != State.CLOSED:
                self.service.chat.leave(self)
                self.state = State.COMMAND
                self.out(texts.INTERNAL_ERROR)
        if self.state == State.COMMAND:
            self.prompt()

    # --- client protocol: take the next n lines as they are --------------

    def collect(self, n: int, done) -> None:
        """The next n input lines go unchanged to done(lines) - also inside a
        chat board, where the session returns to afterwards."""
        self._collect_back = self.state
        self._collect_n, self._collect_lines, self._collect_done = n, [], done
        self.state = State.COLLECT

    def _on_collect(self, line: str) -> None:
        self._collect_lines.append(line)
        if len(self._collect_lines) < self._collect_n:
            return
        self.state = self._collect_back
        done, lines = self._collect_done, self._collect_lines
        self._collect_done, self._collect_lines = None, []
        done(lines)

    # --- client protocol: the next n bytes as they are (binary) ----------

    def collect_raw(self, n: int, chunk, done) -> None:
        """The next n input bytes are binary data, not lines: every piece goes
        to chunk(bytes) as it arrives (so nothing is lost when the link breaks),
        done() is called after the last one. The adapter looks at raw_need
        before it splits lines (AGW only)."""
        if n <= 0:
            done()
            return
        self.raw_need, self._raw_chunk, self._raw_done = n, chunk, done

    def feed_raw(self, data: bytes) -> None:
        """At most raw_need bytes from the adapter."""
        self.raw_need -= len(data)
        try:
            self._raw_chunk(data)
            if self.raw_need <= 0:
                self.raw_need = 0
                done = self._raw_done
                self._raw_chunk = self._raw_done = None
                done()
        except Exception:
            self.raw_need = 0
            self._raw_chunk = self._raw_done = None
            logging.getLogger("tinybox").exception(
                "%s: internal error handling %d raw bytes", self.call, len(data))
            if self.state != State.CLOSED:
                self.out(texts.INTERNAL_ERROR)

    # --- composing a message -------------------------------------------

    def begin_send(self, to_call: str | list[str], type: str, at_addr: str = "",
                   bid: str | None = None) -> None:
        # CR27: a list = one message per recipient, same text
        self._to = [to_call] if isinstance(to_call, str) else list(to_call)
        self._type = type
        self._at, self._bid = at_addr, bid
        self._subject, self._body, self._body_bytes = "", [], 0
        self.state = State.SEND_SUBJECT
        # written without CR so the user types on the same line -> log it here,
        # out() would append a line break
        if self.monitor:
            log.info("%s > %s", self.call, texts.SUBJECT_PROMPT.rstrip())
        self.transport.write(texts.SUBJECT_PROMPT)

    def _on_subject(self, line: str) -> None:
        if CTRL_Z in line or line.strip().upper() == "/AB":
            self.out(texts.CANCELLED)
            self.state = State.COMMAND
            return
        self._subject = line.strip()
        self.out(texts.BODY_PROMPT)
        self.state = State.SEND_BODY

    def _on_body_line(self, line: str) -> None:
        finished = False
        if CTRL_Z in line:
            line = line.split(CTRL_Z, 1)[0]
            finished = True
        elif line.strip().upper() == "/EX":
            line, finished = "", True
        elif line.strip().upper() == "/AB":
            self.out(texts.CANCELLED)
            self.state = State.COMMAND
            return

        if line or not finished:
            self._body.append(line)
            self._body_bytes += len(line.encode("utf-8")) + 1
            if self._body_bytes > self.cfg.mailbox.max_msg_bytes:
                self.out(texts.TOO_LARGE.format(max=self.cfg.mailbox.max_msg_bytes))
                self.state = State.COMMAND
                return

        if finished:
            self.state = State.COMMAND
            ids = []
            body = self.service.multi_to_line(self._to) + "\n".join(self._body)
            try:
                for to in self._to:
                    ids.append(self.service.create(
                        from_call=self.call, to_call=to, type=self._type,
                        subject=self._subject, body=body,
                        origin=self.origin, sysop=self.sysop,
                        at_addr=self._at, bid=self._bid,
                    ))
            except ServiceError as exc:
                self.error(exc)
                if not ids:
                    return
            self.out(texts.SAVED.format(id=", ".join(map(str, ids))))


class SessionRegistry:
    """Keeps track of active sessions across all adapters (max_users)."""

    def __init__(self, max_users: int) -> None:
        self.max_users = max_users
        self._sessions: list[Session] = []

    def add(self, session: Session) -> bool:
        if len(self._sessions) >= self.max_users:
            return False
        self._sessions.append(session)
        return True

    def remove(self, session: Session) -> None:
        if session in self._sessions:
            self._sessions.remove(session)

    def __len__(self) -> int:
        return len(self._sessions)

    def __iter__(self):
        return iter(list(self._sessions))
