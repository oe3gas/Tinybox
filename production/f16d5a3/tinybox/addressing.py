"""Hierarchical addresses, BIDs and R: lines (packet radio BBS conventions).

Address:  CALL.#REGION.COUNTRY.CONTINENT, e.g. OE3XTC.#NOE.AUT.EU, read from
          the right. A mailbox appears without SSID; an SSID in an @ field is
          ignored when comparing.
Area:     for bulletins the @ field is a distribution area: WW, EU, AUT ...
BID:      <number>_<MAILBOXCALL>, at most 12 characters, unique network-wide.
R: line:  R:yymmdd/hhmmZ @:<address> [qth] #:<local nr> $:<bid>
          Every mailbox puts its own line on top when it stores a message.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

MAX_BID = 12
BID_RE = re.compile(r"^[A-Z0-9_\-/]{1,12}$")
# one element: a call (with optional SSID), #REGION, country or continent code
ELEMENT_RE = re.compile(r"^#?[A-Z0-9]{1,6}(-([0-9]|1[0-5]))?$")
# W0RLI spec: HEADER2 "R:yymmdd/hhmm[Z] @:BBS [comment] #:nr ..." (usual today)
#             HEADER1 "R:yymmdd/hhmm nr@BBS" (old form, must still be parsed)
RLINE_RE = re.compile(r"^R:(\d{6})/(\d{4})[A-Z]?\s+(?:@:(\S+)|\d+@(\S+))", re.IGNORECASE)

# ISO country code -> continent, for completing "AUT" to "AUT.EU"
CONTINENT = {
    "AUT": "EU", "DEU": "EU", "CHE": "EU", "LIE": "EU", "ITA": "EU", "CZE": "EU",
    "SVK": "EU", "HUN": "EU", "SVN": "EU", "HRV": "EU", "FRA": "EU", "GBR": "EU",
    "NLD": "EU", "BEL": "EU", "LUX": "EU", "POL": "EU", "DNK": "EU", "SWE": "EU",
    "NOR": "EU", "FIN": "EU", "ESP": "EU", "PRT": "EU", "IRL": "EU", "GRC": "EU",
    "ROU": "EU", "BGR": "EU", "SRB": "EU", "BIH": "EU", "MNE": "EU", "MKD": "EU",
    "ALB": "EU", "UKR": "EU", "EST": "EU", "LVA": "EU", "LTU": "EU", "ISL": "EU",
    "USA": "NOAM", "CAN": "NOAM", "AUS": "OC", "NZL": "OC", "JPN": "ASIA", "ZAF": "AF",
}
CONTINENTS = {"EU", "EURO", "NA", "NOAM", "SA", "SOAM", "AS", "ASIA", "AF", "AFR", "OC", "AUNZ"}


class AddressError(ValueError):
    pass


def base_call(call: str) -> str:
    return call.upper().split("-", 1)[0]


def parts(addr: str) -> list[str]:
    return [p for p in addr.upper().split(".") if p]


def addr_call(addr: str) -> str:
    """First element without SSID: the mailbox (for P) or the area (for B)."""
    p = parts(addr)
    return base_call(p[0]) if p else ""


def normalize(addr: str, aliases: dict[str, str] | None = None) -> str:
    """Upper case, alias replaced, country completed with its continent.

    'ALLOE' (alias -> AUT) -> 'AUT.EU';  'oe3gas.#ooe.aut' -> 'OE3GAS.#OOE.AUT.EU'.
    Raises AddressError for malformed addresses. '' stays ''.
    """
    addr = addr.strip().upper()
    if not addr:
        return ""
    if aliases and addr in aliases:
        addr = aliases[addr]
    p = addr.split(".")
    if len(p) > 6 or not all(ELEMENT_RE.match(x) for x in p):
        raise AddressError(addr)
    if p[-1] in CONTINENT and p[-1] not in CONTINENTS:
        p.append(CONTINENT[p[-1]])
    return ".".join(p)


def is_local(addr: str, mailbox_call: str) -> bool:
    """Empty or addressed to this mailbox (SSID ignored)."""
    return not addr or addr_call(addr) == base_call(mailbox_call)


def make_bid(number: int, mailbox_call: str) -> str:
    """FBB style. The number wraps at 100000 so the BID stays within 12 characters."""
    return f"{number % 100000}_{base_call(mailbox_call)}"[:MAX_BID]


def check_bid(bid: str) -> str:
    bid = bid.strip().upper().lstrip("$")
    if not BID_RE.match(bid):
        raise AddressError(bid)
    return bid


def make_rline(when: datetime, haddress: str, qth: str, nr: int, bid: str) -> str:
    qth_part = f" [{qth}]" if qth else ""
    return f"R:{when:%y%m%d/%H%M}Z @:{haddress}{qth_part} #:{nr} $:{bid}"


def rline_call(line: str) -> str:
    m = RLINE_RE.match(line)
    return addr_call(m.group(3) or m.group(4)) if m else ""


def rline_time(line: str) -> datetime | None:
    m = RLINE_RE.match(line)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1) + m.group(2), "%y%m%d%H%M").replace(
            tzinfo=timezone.utc)
    except ValueError:
        return None


def split_rlines(text: str) -> tuple[list[str], str]:
    """R: lines at the top of a received text, and the body after them."""
    lines = text.split("\n")
    found: list[str] = []
    while lines and RLINE_RE.match(lines[0]):
        found.append(lines.pop(0))
    if found and lines and lines[0] == "":
        lines.pop(0)
    return found, "\n".join(lines)
