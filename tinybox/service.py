"""MessageService: all mailbox rules live here.

Radio, telnet, sysop console and (later) MQTT all go through this class.
It validates input, enforces permissions, stores data and publishes events.
"""

from __future__ import annotations

import logging
import uuid

from .chat import ChatHub
from .config import DEST_RE, Config, base_call, is_valid_call, normalize_call
from .events import EventBus
from .store import Message, Store, utc_now

log = logging.getLogger(__name__)

ORIGINS = {"radio", "telnet", "sysop", "mqtt", "inbox"}
MAX_SUBJECT = 60


class ServiceError(Exception):
    """code: not_found, not_allowed, invalid_call, invalid_value, too_large"""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(detail or code)
        self.code = code


class MessageService:
    def __init__(self, store: Store, bus: EventBus, cfg: Config) -> None:
        self.store = store
        self.bus = bus
        self.cfg = cfg
        self.chat = ChatHub(store, bus, cfg)

    # --- helpers --------------------------------------------------------

    def is_sysop_call(self, call: str) -> bool:
        return base_call(call) == base_call(self.cfg.station.sysop_call)

    @staticmethod
    def _is_addressee(msg: Message, call: str) -> bool:
        return base_call(msg.to_call) == base_call(call)

    @staticmethod
    def _is_author(msg: Message, call: str) -> bool:
        return base_call(msg.from_call) == base_call(call)

    def can_see(self, msg: Message, call: str, sysop: bool) -> bool:
        return (sysop or msg.type == "B"
                or self._is_addressee(msg, call) or self._is_author(msg, call))

    def can_delete(self, msg: Message, call: str, sysop: bool) -> bool:
        return sysop or self._is_addressee(msg, call) or self._is_author(msg, call)

    def _visible(self, msg_id: int, call: str, sysop: bool) -> Message:
        msg = self.store.get(msg_id)
        # Do not reveal that a private message exists.
        if msg is None or not self.can_see(msg, call, sysop):
            raise ServiceError("not_found")
        return msg

    # --- sending --------------------------------------------------------

    def check_send(self, from_call: str, to_call: str, type: str, sysop: bool) -> str:
        """Validate a destination before the user types the whole message.
        Returns the normalized destination."""
        to_call = normalize_call(to_call)
        if type == "P":
            if not is_valid_call(to_call):
                raise ServiceError("invalid_call", to_call)
        elif type == "B":
            if not DEST_RE.match(to_call):
                raise ServiceError("invalid_call", to_call)
        else:
            raise ServiceError("invalid_value", f"type {type}")
        if (not self.cfg.mailbox.third_party and not sysop
                and not self.is_sysop_call(from_call)
                and not (type == "P" and self.is_sysop_call(to_call))):
            raise ServiceError("not_allowed", "third party traffic is disabled")
        return to_call

    def create(self, *, from_call: str, to_call: str, type: str, subject: str,
               body: str, origin: str, sysop: bool = False,
               msgid: str | None = None, created: str | None = None,
               replace_key: str | None = None, expires: str | None = None,
               brocast: str | None = None) -> int:
        """replace_key/expires/brocast: inbox folder only (bulletins). An existing
        bulletin with the same replace_key gets the new content under its old number.
        brocast: a ready brocast page (JSON text) that the brocast adapter sends
        instead of turning the text into a text page."""
        if origin not in ORIGINS:
            raise ServiceError("invalid_value", f"origin {origin}")
        from_call = normalize_call(from_call)
        if not is_valid_call(from_call):
            raise ServiceError("invalid_call", from_call)
        type = type.upper()
        to_call = self.check_send(from_call, to_call, type, sysop)

        if len(body.encode("utf-8")) > self.cfg.mailbox.max_msg_bytes:
            raise ServiceError("too_large")
        subject = " ".join(subject.split())[:MAX_SUBJECT] or "(no subject)"

        if replace_key and type == "B":
            old = self.store.get_by_replace_key(replace_key)
            if old is not None and (old.to_call, old.from_call, old.subject, old.body,
                                    old.brocast) == (to_call, from_call, subject, body, brocast):
                # same content again (e.g. script runs repeatedly): only extend validity,
                # do not mark it unread or send a new revision
                self.store.set_expires(old.id, expires)
                return old.id
            if old is not None:
                self.store.replace_content(old.id, to_call=to_call, from_call=from_call,
                                           subject=subject, body=body,
                                           created=created or utc_now(), expires=expires,
                                           brocast=brocast)
                log.info("msg %d replaced (%s): %s -> %s (%s)", old.id, replace_key,
                         from_call, to_call, origin)
                self.bus.publish("message.edited", message=self.store.get(old.id), by=from_call)
                return old.id

        if msgid:
            existing = self.store.get_by_msgid(msgid)
            if existing:  # duplicate delivery (e.g. MQTT QoS 1) - ignore
                log.info("duplicate msgid %s ignored (msg %d)", msgid, existing.id)
                return existing.id
        else:
            msgid = str(uuid.uuid4())

        msg_id = self.store.add_message(
            msgid=msgid, type=type, to_call=to_call, from_call=from_call,
            subject=subject, body=body, origin=origin, created=created or utc_now(),
            replace_key=replace_key if type == "B" else None,
            expires=expires if type == "B" else None,
            brocast=brocast if type == "B" else None,
        )
        log.info("msg %d created: %s %s -> %s (%s)", msg_id, type, from_call, to_call, origin)
        self.bus.publish("message.created", message=self.store.get(msg_id))
        return msg_id

    # --- reading / listing ----------------------------------------------

    def list_for(self, call: str, sysop: bool, mine: bool = False) -> list[Message]:
        msgs = [m for m in self.store.list_messages() if self.can_see(m, call, sysop)]
        if mine:
            msgs = [m for m in msgs if self._is_addressee(m, call)]
        return msgs

    def unread_for(self, call: str) -> list[Message]:
        return [m for m in self.store.list_messages()
                if m.type == "P" and m.status == "N" and self._is_addressee(m, call)]

    def read(self, msg_id: int, call: str, sysop: bool) -> Message:
        msg = self._visible(msg_id, call, sysop)
        # A bulletin is "read" when someone else reads it - the author reading his own
        # does not count. Inbox bulletins come from scripts, the sysop call is only
        # their nominal author, so for them every reader counts.
        mark = (msg.type == "P" and self._is_addressee(msg, call)) or \
               (msg.type == "B" and (msg.origin == "inbox" or not self._is_author(msg, call)))
        if mark and msg.status == "N":
            self.store.mark_read(msg_id)
            msg = self.store.get(msg_id)
            self.bus.publish("message.read", message=msg, by=call)
        return msg

    # --- deleting / editing ---------------------------------------------

    def delete(self, msg_id: int, call: str, sysop: bool) -> None:
        msg = self._visible(msg_id, call, sysop)
        if not self.can_delete(msg, call, sysop):
            raise ServiceError("not_allowed")
        self.store.delete(msg_id)
        log.info("msg %d deleted by %s", msg_id, call)
        self.bus.publish("message.deleted", message=msg, by=call)

    def kill_mine(self, call: str) -> list[int]:
        """Delete all read private messages addressed to call."""
        ids = [m.id for m in self.store.list_messages()
               if m.type == "P" and m.status == "Y" and self._is_addressee(m, call)]
        for msg_id in ids:
            self.delete(msg_id, call, sysop=False)
        return ids

    _EDIT_FIELDS = {"TO": "to_call", "FROM": "from_call", "TYPE": "type",
                    "STATUS": "status", "SUBJ": "subject"}

    def edit(self, msg_id: int, field: str, value: str, call: str, sysop: bool) -> Message:
        if not sysop:
            raise ServiceError("not_allowed")
        msg = self._visible(msg_id, call, sysop)
        column = self._EDIT_FIELDS.get(field.upper())
        if column is None:
            raise ServiceError("invalid_value", field)
        value = value.strip()
        if column in ("to_call", "from_call"):
            value = normalize_call(value)
            ok = DEST_RE.match(value) if (column == "to_call" and msg.type == "B") \
                else is_valid_call(value)
            if not ok:
                raise ServiceError("invalid_call", value)
        elif column == "type":
            value = value.upper()
            if value not in ("P", "B"):
                raise ServiceError("invalid_value", value)
        elif column == "status":
            value = value.upper()
            if value not in ("N", "Y"):
                raise ServiceError("invalid_value", value)
        else:
            value = " ".join(value.split())[:MAX_SUBJECT] or "(no subject)"
        self.store.update_field(msg_id, column, value)
        msg = self.store.get(msg_id)
        self.bus.publish("message.edited", message=msg, by=call)
        return msg

    # --- sessions / housekeeping ----------------------------------------

    def login(self, call: str, origin: str) -> None:
        self.store.jlog_touch(call)
        self.store.user_login(call)
        self.bus.publish("session.connected", call=call, origin=origin)

    def logout(self, call: str, origin: str) -> None:
        self.bus.publish("session.disconnected", call=call, origin=origin)

    def purge_expired(self) -> int:
        """Delete bulletins past their own validity ("Valid:") or past
        bulletin_expire_days."""
        ids = self.store.delete_expired(utc_now())
        days = self.cfg.mailbox.bulletin_expire_days
        if days > 0:
            ids += self.store.delete_bulletins_older_than(days)
        if ids:
            log.info("expired bulletins deleted: %s", ids)
            self.bus.publish("message.expired", ids=ids)
        return len(ids)
