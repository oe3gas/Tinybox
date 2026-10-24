"""User profiles in the mailbox (CR73, PLANUNG.md section 21).

The TinyBox keeps the profile of every station - name, locator, home BBS -
one per call without SSID. It comes from three places, the newest wins:
  - the terminal: questions after the login, commands N, NL, NH
  - the client: //PROF (clientproto.py)
Everybody may read every profile (I <call>, //WHOIS, who list in the chat).
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from prcore import profile as pf

from .addressing import base_call

ASK_AGAIN_DAYS = 30      # an incomplete profile: the terminal asks again after this
WHOIS_MAX = 10           # calls per //WHOIS line


def get(store, call: str) -> dict | None:
    """The profile of a station (any SSID), None if it never gave one."""
    p = store.profile_get(base_call(call))
    return None if p is None or pf.empty(p) else p


def save(store, call: str, fields: dict, changed: int | None = None) -> dict:
    """Store the (already checked) fields; missing ones keep their value."""
    base = base_call(call)
    old = store.profile_get(base) or {"name": "", "loc": "", "home": ""}
    new = {f: fields.get(f, old.get(f, "")) for f in pf.FIELDS}
    t = int(time.time()) if changed is None else changed
    store.profile_set(base, new["name"], new["loc"], new["home"], t)
    return {**new, "t": t}


def ask_due(store, call: str) -> list[str]:
    """The fields the terminal should ask for after the login: the missing
    ones of name, locator, home BBS - but only once in ASK_AGAIN_DAYS."""
    p = store.profile_get(base_call(call)) or {}
    missing = [f for f in pf.FIELDS if not p.get(f)]
    if not missing:
        return []
    asked = p.get("asked")
    if asked:
        try:
            when = datetime.strptime(asked, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            when = None
        if when and datetime.now(timezone.utc) - when < timedelta(days=ASK_AGAIN_DAYS):
            return []
    return missing


def check_field(field: str, text: str) -> str:
    """One field checked (raises pf.ProfileError)."""
    return {"name": pf.check_name, "loc": pf.check_locator, "home": pf.check_home}[field](text)
