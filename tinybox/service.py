"""MessageService: all mailbox rules live here.

Radio, telnet, sysop console and (later) MQTT all go through this class.
It validates input, enforces permissions, stores data and publishes events.
"""

from __future__ import annotations

import logging
import uuid

from datetime import datetime, timedelta, timezone

from . import addressing
from .addressing import AddressError
from .chat import ChatHub
from .config import DEST_RE, Config, base_call, is_valid_call, normalize_call
from .events import EventBus
from .store import Message, Store, utc_now

log = logging.getLogger(__name__)

ORIGINS = {"radio", "telnet", "sysop", "mqtt", "inbox", "forward"}
MAX_SUBJECT = 60          # what local users may type
MAX_SUBJECT_FWD = 80      # what partner mailboxes may send (FBB limit)
FWD_STATES = {"", "$", "F", "H"}


class ServiceError(Exception):
    """code: not_found, not_allowed, invalid_call, invalid_value, too_large,
    invalid_address, duplicate, no_forward"""

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
        if msg.fwd == "H" and not sysop:          # held mail waits for the sysop
            return False
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

    def check_address(self, type: str, at_addr: str, bid: str | None = None,
                      origin: str = "telnet") -> tuple[str, str | None]:
        """Normalize the @ address and an optional BID given by the user.
        Returns (at_addr, bid). '' = local."""
        try:
            at_addr = addressing.normalize(at_addr, self.cfg.forward.aliases)
        except AddressError as exc:
            raise ServiceError("invalid_address", str(exc)) from None
        if (origin != "forward" and type.upper() == "P" and not self.cfg.forward.enabled
                and not addressing.is_local(at_addr, self.cfg.station.mailbox_call)):
            raise ServiceError("no_forward", at_addr)
        if bid:
            try:
                bid = addressing.check_bid(bid)
            except AddressError as exc:
                raise ServiceError("invalid_value", f"BID {exc}") from None
            if self.store.bid_known(bid):
                raise ServiceError("duplicate", bid)
        return at_addr, bid or None

    def create(self, *, from_call: str, to_call: str, type: str, subject: str,
               body: str, origin: str, sysop: bool = False,
               msgid: str | None = None, created: str | None = None,
               replace_key: str | None = None, expires: str | None = None,
               brocast: str | None = None, at_addr: str = "", bid: str | None = None,
               rlines: list[str] | None = None, bid_kind: str | None = None,
               hold: str = "") -> int:
        """replace_key/expires/brocast: inbox folder only (bulletins). An existing
        bulletin with the same replace_key gets the new content under its old number.
        brocast: a ready brocast page (JSON text) that the brocast adapter sends
        instead of turning the text into a text page.
        at_addr/bid/rlines: forwarding. A partner mailbox (origin "forward") passes
        the R: lines it received; TinyBox adds its own on top.
        hold: forward module only - keep the message held (H) with this reason."""
        if origin not in ORIGINS:
            raise ServiceError("invalid_value", f"origin {origin}")
        from_call = normalize_call(from_call)
        if not is_valid_call(from_call):
            raise ServiceError("invalid_call", from_call)
        type = type.upper()
        forwarded = origin == "forward"
        # third-party rule is for local users, not for mail arriving from partners
        to_call = self.check_send(from_call, to_call, type, sysop or forwarded)
        at_addr, bid = self.check_address(type, at_addr, bid, origin)

        if len(body.encode("utf-8")) > self.cfg.mailbox.max_msg_bytes:
            raise ServiceError("too_large")
        max_subject = MAX_SUBJECT_FWD if forwarded else MAX_SUBJECT
        subject = " ".join(subject.split())[:max_subject] or "(no subject)"

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
            at_addr=at_addr, bid=bid,
        )
        self._forward_fields(msg_id, type, at_addr, bid, rlines or [], origin, bid_kind, hold)
        log.info("msg %d created: %s %s -> %s%s (%s)", msg_id, type, from_call, to_call,
                 f" @ {at_addr}" if at_addr else "", origin)
        self.bus.publish("message.created", message=self.store.get(msg_id))
        return msg_id

    # --- forwarding fields (core part; the forward module comes later) -----

    def _forward_fields(self, msg_id: int, type: str, at_addr: str, bid: str | None,
                        incoming: list[str], origin: str, bid_kind: str | None,
                        hold: str = "") -> None:
        """BID, own R: line, forward state ($ / H) of a new message.

        bid_kind (W0RLI): 'B' = real BID (bulletins, or given by the sender),
        'M' = generated MID of personal mail. A partner mailbox may pass the kind;
        otherwise a received P counts as MID, a B as BID."""
        st = self.cfg.station
        if bid_kind not in ("B", "M"):
            if bid is not None and origin != "forward":
                bid_kind = "B"                     # the user typed $BID
            else:
                bid_kind = "B" if type == "B" else "M"
        if bid is None:
            bid = addressing.make_bid(msg_id, st.mailbox_call)
            if self.store.bid_known(bid):          # only after 100000 messages
                log.warning("msg %d: BID %s already used, message has no BID", msg_id, bid)
                bid = None
        if bid:
            self.store.bid_add(bid, origin)
        forwarded = origin == "forward"
        leaves = bool(at_addr) and not addressing.is_local(at_addr, st.mailbox_call)
        rlines: list[str] = []
        fwd, note = "", ""
        if forwarded or leaves:
            rlines = [addressing.make_rline(datetime.now(timezone.utc), st.address, st.qth,
                                            msg_id, bid or "")] + incoming
        if forwarded:
            note = hold or self._hold_reason(incoming)
            if note:
                fwd = "H"
                log.warning("msg %d (%s) held: %s", msg_id, bid, note)
        if not fwd and leaves and self.cfg.forward.enabled:
            fwd = "$"
        self.store.set_forward_fields(msg_id, bid=bid or "", rlines="\n".join(rlines),
                                      fwd=fwd, note=note, bid_kind=bid_kind if bid else "")

    def _hold_reason(self, incoming: list[str]) -> str:
        own = self.cfg.station.bbs_call
        if own in {addressing.rline_call(x) for x in incoming}:
            return "loop: own call in R: lines"
        times = [t for t in (addressing.rline_time(x) for x in incoming) if t]
        days = self.cfg.forward.bid_days
        if times and datetime.now(timezone.utc) - min(times) > timedelta(days=days):
            return f"older than {days} days (BID lifetime)"
        return ""

    def bid_known(self, bid: str) -> bool:
        return self.store.bid_known(bid.upper())

    def set_fwd_state(self, msg_id: int, fwd: str, note: str = "") -> None:
        if fwd not in FWD_STATES:
            raise ServiceError("invalid_value", f"fwd {fwd}")
        self.store.set_forward_fields(msg_id, fwd=fwd, note=note)
        self.bus.publish("message.edited", message=self.store.get(msg_id), by="forward")

    def assign_missing_bids(self) -> int:
        """Schema 4 -> 5: give existing messages a BID (they stay local)."""
        n = 0
        for msg_id in self.store.ids_without_bid():
            bid = addressing.make_bid(msg_id, self.cfg.station.mailbox_call)
            if self.store.bid_known(bid):
                continue
            self.store.set_forward_fields(msg_id, bid=bid)
            self.store.bid_add(bid, "migration")
            n += 1
        self.store.fill_bid_kind()                # B for bulletins, M for personal mail
        if n:
            log.info("schema 5: %d existing message(s) got a BID", n)
        return n

    def purge_bids(self) -> int:
        n = self.store.purge_bids(self.cfg.forward.bid_days)
        if n:
            log.info("%d BID(s) older than %d days forgotten", n, self.cfg.forward.bid_days)
        return n

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
                    "STATUS": "status", "SUBJ": "subject", "AT": "at_addr"}

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
        elif column == "at_addr":
            value = "" if value in ("-", "") else value
            try:
                value = addressing.normalize(value, self.cfg.forward.aliases)
            except AddressError as exc:
                raise ServiceError("invalid_address", str(exc)) from None
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
