"""Roles and rights (CR92, PLANUNG 29.7) - the one place that decides.

    sysop   the sysop: console, web GUI, inbox/MQTT scripts, a session with
            sysop rights
    user    logged in with the key of his call (TBClient, CR93) - at the home
            BBS, or at another TinyBox with a certificate of his home BBS
    guest   everybody else: a terminal session (the call is not proven)
    forward a partner mailbox (fwd/, not a Session)

| right                         | sysop | forward | user | guest                     |
|-------------------------------|-------|---------|------|---------------------------|
| read mail and bulletins       |  yes  |    -    | yes  | yes                       |
| write personal mail           |  yes  |  yes    | yes  | text only; to another BBS |
|                               |       |         |      | only after the sysop's    |
|                               |       |         |      | release (held, REL n)     |
| write bulletins               |  yes  |  yes    | yes  | no                        |
| delete bulletins              |  yes  |  no     | no   | no                        |
| brocast pages, alerts (WARN)  |  yes  |  no     | no   | no                        |
| TBClient (client mode)        |  yes  |  -      | yes  | no (CR93)                 |

Bulletins of users still become text pages in brocast (as before); only an
alert page needs a sysop source (adapters/brocast.py, TB-14).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .session import Session

# Switched off only by the test suite (tests/__init__.py) for the tests that are
# about something else and use terminal sessions to write bulletins.
GUEST_LIMITS = True

SYSOP, USER, GUEST, FORWARD = "sysop", "user", "guest", "forward"
TRUSTED = ""            # no session: the sysop's own tools, the mailbox itself

GUEST_HOLD = "guest mail - the sysop releases it (REL n)"


def role_of(s: Session) -> str:
    if s.sysop:
        return SYSOP
    if s.auth:
        return USER
    if s.client is not None:
        # only without REQUIRE_AUTH (tests): client mode without a key login
        return USER
    return GUEST if GUEST_LIMITS else USER


def may_write_bulletin(role: str) -> bool:
    return role != GUEST


def emoji_ok(role: str) -> bool:
    """PLANUNG 29.9: emoji only from proven users."""
    return role != GUEST


def hold_reason(role: str, leaves: bool) -> str:
    """Mail of a guest to another BBS waits for the sysop."""
    return GUEST_HOLD if role == GUEST and leaves else ""


def default_role() -> str:
    """Role of a caller that names none (scripts, tests without guest limits)."""
    return GUEST if GUEST_LIMITS else USER


def may_delete(msg_type: str, role: str, addressee: bool, author: bool) -> bool:
    """Personal mail: the sysop, addressee or author. Bulletins: the sysop, or the
    author when his call is proven (user) - never the 'addressee': that is the
    rubric, and a station named like it (70CM, QO100) must get no rights (TB-15)."""
    if role == SYSOP:
        return True
    if msg_type == "P":
        return addressee or author
    return role == USER and author
