"""Who may use the web GUI (CR100).

No login - devices in the own network are trusted (PLANUNG 29.6, AR3). What
is checked instead:

- the address of the caller: only the own network by default (loopback,
  10/8, 172.16/12, 192.168/16, link-local, IPv6 ULA). A port forwarded by
  mistake at the router, or a PC directly on the internet, gets 403.
  [web] allow = lan | local | any, plus extra networks (HAMNET 44.0.0.0/8, VPN).
- the Host header: a web page from outside can make the browser send
  requests to the client if its own domain resolves to the LAN address
  (DNS rebinding). The browser then calls the client by that foreign name -
  so only IP addresses, single-label names (PC1), localhost and local
  suffixes (.local, .lan, .fritz.box ...) are accepted, plus [web] hosts.
- the Origin header of a POST, when the browser sends one: same host as Host.
"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit

Network = ipaddress.IPv4Network | ipaddress.IPv6Network

LAN = ("127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16",
       "::1/128", "fc00::/7", "fe80::/10")
LOCAL = ("127.0.0.0/8", "::1/128")
NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$")
LOCAL_SUFFIXES = (".local", ".lan", ".home", ".home.arpa", ".internal", ".localdomain",
                  ".fritz.box", ".localhost")


class GuardError(ValueError):
    pass


def parse_allow(text: str) -> list[Network] | None:
    """'lan', 'local', 'any' and networks, comma separated. None = any."""
    nets: list[Network] = []
    for word in (w.strip().lower() for w in text.replace(";", ",").split(",")):
        if not word:
            continue
        if word == "any":
            return None
        if word in ("lan", "local"):
            nets += [ipaddress.ip_network(n) for n in (LAN if word == "lan" else LOCAL)]
            continue
        try:
            nets.append(ipaddress.ip_network(word, strict=False))
        except ValueError:
            raise GuardError(f"[web] allow: {word!r} is no network (lan, local, any or "
                             "e.g. 44.0.0.0/8)") from None
    if not nets:
        raise GuardError("[web] allow is empty (lan, local, any or networks)")
    return nets


def parse_hosts(text: str) -> set[str]:
    return {w.strip().lower().rstrip(".") for w in text.replace(";", ",").split(",") if w.strip()}


def peer_allowed(addr: str | None, nets: list[Network] | None) -> bool:
    if nets is None:
        return True
    if not addr:
        return False
    try:
        ip = ipaddress.ip_address(addr.split("%", 1)[0])        # fe80::1%eth0
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:  # ::ffff:192.168.1.5
        ip = ip.ipv4_mapped
    return any(ip in n for n in nets)


def _hostname(value: str) -> str | None:
    """'pc1:7744' -> 'pc1', '[fe80::1]:7744' -> 'fe80::1'; None if unreadable."""
    value = value.strip().lower()
    if not value:
        return None
    try:
        host = urlsplit("//" + value).hostname
    except ValueError:
        return None
    return host.rstrip(".") if host else None


def host_allowed(value: str | None, extra: set[str] = frozenset()) -> bool:
    if value is None:                  # HTTP/1.0 tools without Host: no browser
        return True
    host = _hostname(value)
    if not host:
        return False
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    if not NAME_RE.match(host):
        return False
    if host == "localhost" or host in extra or "." not in host:
        return True
    return host.endswith(LOCAL_SUFFIXES)


def origin_allowed(origin: str | None, host: str | None) -> bool:
    """A POST from another site: the browser names it in Origin."""
    if origin is None:
        return True
    if origin == "null":
        return False
    return _hostname(urlsplit(origin).netloc) == _hostname(host or "")
