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
        # message being composed
        self._to = ""
        self._type = "P"
        self._subject = ""
        self._body: list[str] = []
        self._body_bytes = 0

    # --- output ---------------------------------------------------------

    def out(self, *lines: str) -> None:
        text = "\r".join(lines) + "\r"
        if self.monitor:
            for line in lines:
                log.info("%s > %s", self.call, line)
        self.transport.write(text)

    def prompt(self) -> None:
        self.transport.write(texts.PROMPT_SYSOP if self.sysop else texts.PROMPT)

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
        self.out(*lines)
        self.prompt()

    def close(self) -> None:
        """Log off from the mailbox side (command B, timeout)."""
        if self.state != State.CLOSED:
            self.state = State.CLOSED
            self.transport.close()

    def end(self) -> None:
        """Called by the adapter when the connection is gone."""
        if self.state in (State.SEND_SUBJECT, State.SEND_BODY):
            log.info("%s disconnected while sending, message discarded", self.call)
        self.state = State.CLOSED
        self.service.chat.leave(self, reason=texts.CHAT_REASON_DISC)
        self.service.logout(self.call, self.origin)

    # --- input ----------------------------------------------------------

    def handle_line(self, line: str) -> None:
        if self.closed:
            return
        line = line[:MAX_LINE]
        if self.monitor:
            log.info("%s < %s", self.call, line)
        try:
            if self.state == State.COMMAND:
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

    # --- composing a message -------------------------------------------

    def begin_send(self, to_call: str, type: str) -> None:
        self._to, self._type = to_call, type
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
            try:
                msg_id = self.service.create(
                    from_call=self.call, to_call=self._to, type=self._type,
                    subject=self._subject, body="\n".join(self._body),
                    origin=self.origin, sysop=self.sysop,
                )
            except ServiceError as exc:
                self.error(exc)
                return
            self.out(texts.SAVED.format(id=msg_id))


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
