"""Minimal HTTP/JSON server on loopback (standard library only).

Shared by the ingest API (port 8090) and the listener API (port 7733).

Security:
  * listens on loopback only (checked in config); the listener GUI may
    listen in the LAN when [listener] allow_lan = yes
  * Host header must be a loopback name -> blocks DNS rebinding. In LAN
    mode an IP address, this PC's name or a name from lan_names is also
    accepted - never a foreign domain name, so DNS rebinding stays blocked
  * request bodies must be application/json; browsers can only send that
    cross-site after a CORS preflight, which we never answer
  * optional: token in X-Brocast-Token, and/or X-Brocast-Client header on
    every write (a second CSRF barrier for the browser GUI)
"""

from __future__ import annotations

import asyncio
import hmac
import ipaddress
import socket
import json
import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

log = logging.getLogger(__name__)

PREFIX = "/api/v1"
MAX_HEADER = 16 * 1024
MAX_BODY = 256 * 1024
LOOPBACK_NAMES = ("127.0.0.1", "localhost", "[::1]")
WRITE_METHODS = ("PUT", "POST", "DELETE", "PATCH")
REASONS = {200: "OK", 400: "Bad Request", 401: "Unauthorized", 403: "Forbidden",
           404: "Not Found", 405: "Method Not Allowed", 411: "Length Required",
           413: "Payload Too Large", 415: "Unsupported Media Type", 500: "Internal Server Error"}


def host_allowed(host: str, lan: bool, lan_names: frozenset[str] = frozenset()) -> bool:
    """host: Host header without port, IPv6 in brackets."""
    host = host.lower().rstrip(".")
    if host in LOOPBACK_NAMES:
        return True
    if not lan:
        return False
    try:
        ipaddress.ip_address(host[1:-1] if host.startswith("[") else host)
        return True
    except ValueError:
        pass
    return host in lan_names


def own_names() -> frozenset[str]:
    """This PC's name, short and with domain (e.g. pc2, pc2.fritz.box)."""
    names = {socket.gethostname(), socket.getfqdn()}
    return frozenset(n.lower().rstrip(".") for n in names if n)


class HttpError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


PAGE_HEADERS = {
    "Content-Security-Policy": ("default-src 'self'; script-src 'self'; style-src 'self'; "
                                "img-src 'self' data:; connect-src 'self'; "
                                "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"),
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}
CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                 ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml"}


@dataclass
class Request:
    method: str
    parts: list[str]                         # path below /api/v1, URL-decoded
    query: dict[str, str]
    body: Any = None
    headers: dict[str, str] = field(default_factory=dict)
    path: str = ""

    def q(self, name: str, default: str | None = None) -> str | None:
        return self.query.get(name, default)


def to_json(value: Any) -> Any:
    """Make decoded pages JSON-safe: int dict keys -> str, bytes -> hex."""
    if isinstance(value, dict):
        return {str(k): to_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json(v) for v in value]
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).hex()
    return value


class JsonServer:
    name = "API"

    def __init__(self, host: str, port: int, token: str = "",
                 require_client_header: bool = False, static: dict[str, Any] | None = None,
                 lan: bool = False, lan_names: tuple[str, ...] = ()):
        self.host, self.port, self.token = host, port, token
        self.lan = lan
        self.lan_names = (own_names() | {n.lower().rstrip(".") for n in lan_names}) \
            if lan else frozenset()
        self.require_client_header = require_client_header
        self.static = static or {}               # URL path -> file Path
        self.server: Any = None

    async def start(self) -> None:
        self.server = await asyncio.start_server(self._handle, self.host, self.port,
                                                 limit=MAX_HEADER)
        self.port = self.server.sockets[0].getsockname()[1]
        log.info("%s auf http://%s:%s%s", self.name, self.host, self.port, PREFIX)
        if self.lan:
            log.warning("%s im LAN erreichbar (allow_lan = yes), ohne Anmeldung – "
                        "Zugriff per Firewall auf das Heimnetz beschränken", self.name)

    async def close(self) -> None:
        if self.server:
            self.server.close()
            await self.server.wait_closed()

    def route(self, req: Request) -> tuple[int, Any]:     # override
        raise HttpError(404, "unbekannter Pfad")

    # -- plumbing -----------------------------------------------------------

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        content_type = "application/json; charset=utf-8"
        extra: dict[str, str] = {}
        body: bytes | None = None
        try:
            req = await self._read(reader)
            if req.path in self.static and req.method == "GET":
                file = self.static[req.path]
                body = file.read_bytes()
                content_type = CONTENT_TYPES.get(file.suffix, "application/octet-stream")
                extra = PAGE_HEADERS
                status = 200
            else:
                if not req.path.startswith(PREFIX + "/"):
                    raise HttpError(404, "unbekannter Pfad")
                status, payload = self.route(req)
        except HttpError as exc:
            status, payload = exc.status, {"error": str(exc)}
        except Exception:
            log.exception("Fehler in %s", self.name)
            status, payload = 500, {"error": "interner Fehler"}
        if body is None:
            body = json.dumps(to_json(payload), ensure_ascii=False, indent=1).encode("utf-8")
        head = (f"HTTP/1.1 {status} {REASONS.get(status, '')}\r\n"
                f"Content-Type: {content_type}\r\n"
                f"Content-Length: {len(body)}\r\n"
                "Cache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n"
                + "".join(f"{k}: {v}\r\n" for k, v in extra.items())
                + "Connection: close\r\n\r\n")
        try:
            writer.write(head.encode("ascii") + body)
            await writer.drain()
        except ConnectionError:
            pass
        finally:
            writer.close()

    async def _read(self, reader: asyncio.StreamReader) -> Request:
        try:
            head = await reader.readuntil(b"\r\n\r\n")
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError):
            raise HttpError(400, "unvollständige Anfrage") from None
        lines = head.decode("latin-1").split("\r\n")
        try:
            method, target, _ = lines[0].split(" ", 2)
        except ValueError:
            raise HttpError(400, "ungültige Anfragezeile") from None
        headers: dict[str, str] = {}
        for line in lines[1:]:
            if ":" in line:
                name, value = line.split(":", 1)
                headers[name.strip().lower()] = value.strip()

        host_header = headers.get("host", "")
        host = host_header.split("]")[0] + "]" if host_header.startswith("[") \
            else host_header.split(":")[0]
        if not host_allowed(host, self.lan, self.lan_names):
            raise HttpError(403, "Host nicht erlaubt")
        if self.token and not hmac.compare_digest(
                headers.get("x-brocast-token", "").encode(), self.token.encode()):
            raise HttpError(401, "Token fehlt oder falsch")
        if self.require_client_header and method in WRITE_METHODS \
                and headers.get("x-brocast-client") != "1":
            raise HttpError(403, "Header X-Brocast-Client fehlt")

        body: Any = None
        if method in ("PUT", "POST"):
            if "content-length" not in headers:
                raise HttpError(411, "Content-Length fehlt")
            try:
                length = int(headers["content-length"])
            except ValueError:
                raise HttpError(400, "ungültige Content-Length") from None
            if not 0 <= length <= MAX_BODY:
                raise HttpError(413, "Anfrage zu groß")
            if not headers.get("content-type", "").startswith("application/json"):
                raise HttpError(415, "Content-Type application/json erwartet")
            raw = await reader.readexactly(length)
            try:
                body = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise HttpError(400, f"ungültiges JSON: {exc}") from None

        url = urlsplit(target)
        parts = [unquote(p) for p in url.path[len(PREFIX) + 1:].split("/") if p] \
            if url.path.startswith(PREFIX + "/") else []
        query = {k: v[0] for k, v in parse_qs(url.query).items()}
        return Request(method, parts, query, body, headers, url.path)
