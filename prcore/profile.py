"""User profile: name, locator and home BBS of a station (CR73).

Shared by the TinyBox (stores the profile, PLANUNG.md section 21) and the
client (where the user types it in). One profile per call WITHOUT SSID:
OE3GAS-7 and OE3GAS are the same person.

On the air (TinyBox client protocol TB1) a profile is one line of fields:

    t=<unix> loc=<locator> home=<home BBS> name=<name>

name= comes last because a name may contain spaces. Empty fields stay
(loc=), so a field can also be cleared. t = time of the last change: the
newer profile wins when client and TinyBox disagree.
"""

from __future__ import annotations

import re
import zlib

FIELDS = ("name", "loc", "home")
MAX_NAME = 12
MAX_HOME = 40
LOCATOR_RE = re.compile(r"^[A-R]{2}[0-9]{2}([A-X]{2})?$")
# home BBS: a call without SSID, optionally the hierarchical address behind it
HOME_RE = re.compile(r"^[A-Z0-9]{3,6}(\.#?[A-Z0-9]{1,6})*$")
CALL_RE = re.compile(r"^(?=.{3,6}$)[A-Z0-9]{1,3}[0-9][A-Z]{1,4}$")   # prefix, digit, suffix


class ProfileError(ValueError):
    """str(exc) is the field that is wrong: name, loc or home."""


def check_name(text: str) -> str:
    """Up to 12 letters, spaces, '-', '.' and "'" (Hans-Peter, J. Smith).
    Letters with accents are fine (Jürgen). '' = no name."""
    name = " ".join(text.split())
    if not name:
        return ""
    if len(name) > MAX_NAME or not name[0].isalpha() \
            or not all(c.isalpha() or c in " -.'" for c in name):
        raise ProfileError("name")
    return name


def check_locator(text: str) -> str:
    """Maidenhead locator, 4 or 6 characters (JN88 or JN88EP). '' = none.
    The user decides how exact: everybody sees what he enters."""
    loc = text.strip().upper()
    if loc and not LOCATOR_RE.match(loc):
        raise ProfileError("loc")
    return loc


def check_home(text: str) -> str:
    """Home BBS: its call (OE3XSR) or the hierarchical address
    (OE3XSR.#NOE.AUT.EU). An SSID is dropped. '' = none."""
    home = text.strip().upper()
    if not home:
        return ""
    first, dot, rest = home.partition(".")
    home = first.split("-", 1)[0] + dot + rest
    if len(home) > MAX_HOME or not HOME_RE.match(home) or not CALL_RE.match(home.split(".")[0]):
        raise ProfileError("home")
    return home


def check(name: str = "", loc: str = "", home: str = "") -> dict[str, str]:
    """All three fields checked, as a dict (raises ProfileError)."""
    return {"name": check_name(name), "loc": check_locator(loc), "home": check_home(home)}


def empty(p: dict | None) -> bool:
    return not p or not any(p.get(f) for f in FIELDS)


def complete(p: dict | None) -> bool:
    """Name and locator given (the home BBS is optional)."""
    return bool(p and p.get("name") and p.get("loc"))


def crc(p: dict | None) -> str:
    """4 hex digits over the three fields, '-' for no profile. The client
    compares it with its own: the profile goes on the air only when it differs."""
    if empty(p):
        return "-"
    text = "\x1f".join(p.get(f, "") for f in FIELDS)
    return f"{zlib.crc32(text.encode('utf-8')) & 0xFFFF:04x}"


def encode(p: dict, with_time: bool = True) -> str:
    """The fields as one line: [t=..] loc=.. home=.. name=.."""
    head = f"t={int(p.get('t', 0))} " if with_time else ""
    return f"{head}loc={p.get('loc', '')} home={p.get('home', '')} name={p.get('name', '')}"


def decode(text: str) -> dict:
    """The opposite of encode(): {'t', 'name', 'loc', 'home'} as given, NOT
    checked yet (check() does that). Unknown keys are ignored, missing ones ''."""
    out: dict = {"t": 0, "name": "", "loc": "", "home": ""}
    head, sep, name = text.partition("name=")
    if sep:
        out["name"] = name.strip()
    for part in head.split():
        key, eq, value = part.partition("=")
        if not eq:
            continue
        if key == "t":
            out["t"] = int(value) if value.isdigit() else 0
        elif key in ("loc", "home"):
            out[key] = value
    return out


def short(p: dict | None) -> str:
    """'Gerhard, JN88EP' - for the who list of the chat and the terminal."""
    if not p:
        return ""
    return ", ".join(x for x in (p.get("name", ""), p.get("loc", "")) if x)
