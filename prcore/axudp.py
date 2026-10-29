"""AX.25 over UDP (AXUDP) - PLANUNG.md section 25, step 1.

The same wire format as BPQ32/LinBPQ "AXIP UDP", XNet and JNOS: one UDP
datagram carries one AX.25 frame (address field, control, PID, info - no HDLC
flags, no bit stuffing) followed by the FCS, CRC-16/X.25 as on HDLC, low byte
first. A datagram with a wrong FCS is dropped.

    datagram = ax25_frame + fcs16(ax25_frame).to_bytes(2, "little")

Peers are a fixed table callsign -> (ip, port), like BPQ's MAP lines. To send,
the endpoint looks up the destination call of the frame (with SSID first, then
without); with a digipeater path the first digi that has not repeated it yet. A datagram is accepted only if it comes from the IP of a peer AND
its source call belongs to that peer; everything else is dropped silently
(no DM - a stranger learns nothing) and counted.

AXUDP has no login and no encryption: the callsign in a frame is a claim.
Loopback first; over the internet only through WireGuard or HAMNET.

AxudpEndpoint has the interface of kiss.KissTcpClient (run, send, connected,
describe, rx/tx counters), so prcore/kissport.py can use either transport.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
from dataclasses import dataclass
from typing import Iterable, Mapping

from .ax25.frame import AX25Error, peek
from .kiss import FrameHandler
from .termcolor import OK

log = logging.getLogger(__name__)

DEFAULT_PORT = 10093
MAX_FRAME = 2048             # an AX.25 frame is far smaller (PACLEN 256 + addresses)
MIN_FRAME = 15               # two addresses + control


class AxudpError(ValueError):
    pass


# --- FCS: CRC-16/X.25 (poly 0x1021 reflected = 0x8408, init and xorout 0xFFFF) ------------

def _table() -> list[int]:
    t = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (c >> 1) ^ 0x8408 if c & 1 else c >> 1
        t.append(c)
    return t


_TABLE = _table()


def fcs16(data: bytes) -> int:
    """HDLC frame check sequence. fcs16(b"123456789") == 0x906E."""
    crc = 0xFFFF
    for b in data:
        crc = (crc >> 8) ^ _TABLE[(crc ^ b) & 0xFF]
    return crc ^ 0xFFFF


def encode(ax25: bytes) -> bytes:
    """One AXUDP datagram for one AX.25 frame."""
    if not MIN_FRAME <= len(ax25) <= MAX_FRAME:
        raise AxudpError(f"AX.25 frame of {len(ax25)} bytes")
    return ax25 + fcs16(ax25).to_bytes(2, "little")


def decode(datagram: bytes) -> bytes:
    """The AX.25 frame of a datagram; AxudpError if too short/long or FCS wrong."""
    if not MIN_FRAME + 2 <= len(datagram) <= MAX_FRAME + 2:
        raise AxudpError(f"datagram of {len(datagram)} bytes")
    ax25, fcs = datagram[:-2], int.from_bytes(datagram[-2:], "little")
    if fcs16(ax25) != fcs:
        raise AxudpError("FCS wrong")
    return ax25


# --- peers ---------------------------------------------------------------------------------

def norm_call(call: str) -> str:
    """OE3GAS-0 -> OE3GAS, upper case, no blanks (as kissport.norm_call)."""
    call = call.strip().upper()
    return call[:-2] if call.endswith("-0") else call


def base_call(call: str) -> str:
    return norm_call(call).split("-", 1)[0]


@dataclass(frozen=True)
class Peer:
    call: str                 # as configured: OE3GAS (every SSID) or OE3GAS-1 (only that one)
    host: str                 # IP address (v4 or v6)
    port: int

    @property
    def addr(self) -> tuple[str, int]:
        return self.host, self.port

    def owns(self, call: str) -> bool:
        """Is call (a frame's source) this peer's station?"""
        call = norm_call(call)
        return call == self.call if "-" in self.call else base_call(call) == self.call


def parse_addr(text: str, default_port: int = DEFAULT_PORT) -> tuple[str, int]:
    """'127.0.0.1:10093', '127.0.0.1', '[::1]:10093' -> (ip, port). Only IP addresses
    for now (hostnames/DynDNS with forwarding, PLANUNG 25 step 4)."""
    text = text.strip()
    host, port = text, default_port
    if text.startswith("["):                       # [v6]:port
        host, _, rest = text[1:].partition("]")
        if rest:
            if not rest.startswith(":"):
                raise AxudpError(f"address {text!r}: ':port' expected after ]")
            port = _port(rest[1:], text)
    elif text.count(":") == 1:                     # v4:port
        host, p = text.split(":")
        port = _port(p, text)
    try:
        host = str(ipaddress.ip_address(host))
    except ValueError:
        raise AxudpError(f"address {text!r}: IP address expected") from None
    return host, port


def _port(p: str, text: str) -> int:
    try:
        port = int(p)
    except ValueError:
        raise AxudpError(f"address {text!r}: port is not a number") from None
    if not 1 <= port <= 65535:
        raise AxudpError(f"address {text!r}: port out of range")
    return port


def is_loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _valid_call(call: str) -> bool:
    base, _, ssid = call.partition("-")
    if not (1 <= len(base) <= 6 and base.isalnum()):
        return False
    return not ssid or (ssid.isdigit() and 0 <= int(ssid) <= 15)


def parse_peers(peers: Mapping[str, str] | Iterable[str]) -> dict[str, Peer]:
    """Peers from a config section {call: 'ip:port'} or lines 'CALL ip:port' /
    'CALL = ip:port'. Returns {call: Peer}; AxudpError names the bad entry."""
    items: list[tuple[str, str]] = []
    if isinstance(peers, Mapping):
        items = [(str(k), str(v)) for k, v in peers.items()]
    else:
        for line in peers:
            line = line.split("#", 1)[0].split(";", 1)[0].strip()
            if not line:
                continue
            parts = line.replace("=", " ").split()
            if len(parts) != 2:
                raise AxudpError(f"peer {line!r}: 'CALL ip:port' expected")
            items.append((parts[0], parts[1]))
    out: dict[str, Peer] = {}
    for call, addr in items:
        call = norm_call(call)
        if not _valid_call(call):
            raise AxudpError(f"peer {call!r}: not a callsign")
        if call in out:
            raise AxudpError(f"peer {call}: listed twice")
        host, port = parse_addr(addr.split("#", 1)[0].split(";", 1)[0])
        out[call] = Peer(call, host, port)
    return out


class PeerTable:
    def __init__(self, peers: Mapping[str, Peer]) -> None:
        self.peers = dict(peers)

    def route(self, dest: str) -> Peer | None:
        """Peer for a destination call: with SSID first, then the bare call."""
        dest = norm_call(dest)
        return self.peers.get(dest) or self.peers.get(base_call(dest))

    def owner(self, call: str) -> Peer | None:
        """The peer whose station call is (with SSID first, then every SSID)."""
        call = norm_call(call)
        exact = self.peers.get(call)
        if exact is not None:
            return exact
        bare = self.peers.get(base_call(call))
        return bare if bare is not None and "-" not in bare.call else None

    def sender(self, ip: str, src: str) -> Peer | None:
        """The peer a datagram from ip with source call src belongs to, or None."""
        try:
            a = ipaddress.ip_address(ip.split("%", 1)[0])
        except ValueError:
            return None
        mapped = getattr(a, "ipv4_mapped", None)   # v4-mapped on a dual-stack socket
        ip = str(mapped or a)
        for peer in self.peers.values():
            if peer.host == ip and peer.owns(src):
                return peer
        return None


# --- the endpoint --------------------------------------------------------------------------

class AxudpEndpoint:
    """One UDP socket: send AX.25 frames to peers, receive frames from them.

    Same interface as kiss.KissTcpClient: on_frame(port, ax25) for every accepted
    frame (port = kiss_port, 0), send() False when the frame cannot go out (socket
    not open, no peer for the destination), connected set while the socket is bound.
    """

    def __init__(self, listen: str, port: int, peers: Mapping[str, Peer],
                 on_frame: FrameHandler, kiss_port: int = 0, hear: str | None = None) -> None:
        self.listen, self.port = listen, port
        self.table = PeerTable(peers)
        # hear = own call: a way with air time (PLANUNG 27.2, half duplex). Frames of
        # other stations from a peer's address that are NOT for us are passed on too,
        # so the AX.25 sees the channel busy (T1 waits) - like hearing the frequency.
        # Never a frame for our own call from a stranger: that is still dropped.
        self.hear = norm_call(hear) if hear else None
        self.heard = 0
        self.on_frame = on_frame
        self.kiss_port = kiss_port
        self.connected = asyncio.Event()
        self.rx_frames = 0
        self.tx_frames = 0
        self.tx_bytes = 0
        self.dropped = {"fcs": 0, "stranger": 0, "garbage": 0, "no_route": 0}
        self._transport: asyncio.DatagramTransport | None = None

    def describe(self) -> str:
        return f"AXUDP {self.listen}:{self.port}"

    @property
    def local_port(self) -> int | None:
        """The bound port (useful with port 0 in tests)."""
        if self._transport is None:
            return None
        return self._transport.get_extra_info("sockname")[1]

    async def open(self) -> None:
        loop = asyncio.get_running_loop()
        family = socket.AF_INET6 if ":" in self.listen else socket.AF_INET
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: _Protocol(self), local_addr=(self.listen, self.port), family=family)
        self.connected.set()
        log.info("AXUDP listening on %s:%d (%d peers)", self.listen, self.local_port,
                 len(self.table.peers), extra=OK)

    def close(self) -> None:
        self.connected.clear()
        if self._transport is not None:
            self._transport.close()
            self._transport = None

    async def run(self) -> None:
        """Open the socket and keep it until cancelled (KissTcpClient.run)."""
        await self.open()
        try:
            await asyncio.Event().wait()
        finally:
            self.close()

    def send(self, ax25: bytes) -> bool:
        """Send one AX.25 frame to the peer of its destination call."""
        transport = self._transport
        if transport is None or transport.is_closing():
            return False
        try:
            dest, _, path, repeated = peek(ax25)
        except AX25Error:
            self.dropped["garbage"] += 1
            return False
        # via digipeaters: to the first one that has not repeated it yet (as BPQ)
        nxt = next((d for d, r in zip(path, repeated) if not r), None)
        if nxt is not None:
            dest = nxt
        peer = self.table.route(dest)
        if peer is None:
            self.dropped["no_route"] += 1
            log.debug("AXUDP: no peer for %s, frame not sent", dest)
            return False
        transport.sendto(encode(ax25), peer.addr)
        self.tx_frames += 1
        self.tx_bytes += len(ax25)
        return True

    def _heard(self, ip: str, dest: str) -> bool:
        """A frame between two other stations, from a peer's address (hear mode)."""
        if self.hear is None or norm_call(dest) == self.hear:
            return False
        if base_call(dest) == self.hear:          # our call without SSID: not either
            return False
        return any(_same_ip(ip, p.host) for p in self.table.peers.values())

    def received(self, datagram: bytes, addr) -> None:
        """One datagram from the socket (also called directly by tests)."""
        try:
            ax25 = decode(datagram)
        except AxudpError as exc:
            self.dropped["fcs" if "FCS" in str(exc) else "garbage"] += 1
            log.debug("AXUDP from %s dropped: %s", addr, exc)
            return
        try:
            dest, src = peek(ax25)[:2]
        except AX25Error:
            self.dropped["garbage"] += 1
            return
        if self.table.sender(addr[0], src) is None:
            if not self._heard(addr[0], dest):
                self.dropped["stranger"] += 1
                log.debug("AXUDP from %s (%s) dropped: no such peer", addr, src)
                return
            self.heard += 1
        self.rx_frames += 1
        try:
            result = self.on_frame(self.kiss_port, ax25)
            if asyncio.iscoroutine(result):
                asyncio.ensure_future(result)
        except Exception:                          # one bad frame must not stop the port
            log.exception("error handling an AXUDP frame")


def _same_ip(a: str, b: str) -> bool:
    try:
        x = ipaddress.ip_address(a.split("%", 1)[0])
        x = getattr(x, "ipv4_mapped", None) or x
        return x == ipaddress.ip_address(b)
    except ValueError:
        return False


class _Protocol(asyncio.DatagramProtocol):
    def __init__(self, endpoint: AxudpEndpoint) -> None:
        self.endpoint = endpoint

    def datagram_received(self, data: bytes, addr) -> None:
        self.endpoint.received(data, addr)

    def error_received(self, exc: Exception) -> None:
        # e.g. ICMP port unreachable on Windows when the peer is not running:
        # AX.25 timers recover, nothing to do here
        log.debug("AXUDP socket error: %s", exc)
