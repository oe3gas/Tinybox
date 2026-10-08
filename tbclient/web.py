"""Web GUI of the client: static files + a small JSON API (standard library only).

Reachable in the LAN/WAN without login (decided, see PLANUNG.md 11/5).
What stays protected:
  * writes need Content-Type application/json and the header X-TBClient: 1.
    A foreign web page cannot send that without a CORS preflight, which we
    never answer -> no sending under your call from a malicious page.
  * strict Content-Security-Policy, the page only uses textContent
    (chat texts come from the air and are untrusted).

API:
  GET  /api/state?since=<version>   snapshot; waits up to 25 s for a change
  POST /api/connect | /api/disconnect | /api/leave
  POST /api/join   {"board": n}
  POST /api/say    {"text": "..."}
  POST /api/react  {"seq": n, "emoji": ":+1"}
  POST /api/symbol {"symbol": "/-"}  ("" = none)
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .core import ClientCore

log = logging.getLogger(__name__)

STATIC = Path(__file__).resolve().parent / "web"
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".js": "text/javascript; charset=utf-8", ".json": "application/json",
         ".png": "image/png", ".svg": "image/svg+xml"}
FILES = {"/": "index.html", "/app.css": "app.css", "/app.js": "app.js",
         "/emoji.json": "emoji.json", "/aprs/symbols-0.png": "aprs/aprs-symbols-24-0@2x.png",
         "/aprs/symbols-1.png": "aprs/aprs-symbols-24-1@2x.png",
         "/aprs/names.json": "aprs/names.json", "/manifest.json": "manifest.json"}
HEADERS = {
    "Content-Security-Policy": ("default-src 'self'; script-src 'self'; style-src 'self'; "
                                "img-src 'self' data:; connect-src 'self'; "
                                "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}
REASONS = {200: "OK", 400: "Bad Request", 403: "Forbidden", 404: "Not Found",
           405: "Method Not Allowed", 413: "Payload Too Large", 415: "Unsupported Media Type"}
MAX_BODY = 8192
POLL_SEC = 25


class WebServer:
    def __init__(self, core: ClientCore) -> None:
        self.core = core

    async def start(self) -> asyncio.base_events.Server:
        cfg = self.core.cfg
        server = await asyncio.start_server(self._client, cfg.web_host, cfg.web_port)
        log.info("web GUI on http://%s:%s/", "<this PC>" if cfg.web_host in ("0.0.0.0", "::")
                 else cfg.web_host, cfg.web_port)
        return server

    async def _client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                keep = await self._request(reader, writer)
                if not keep:
                    break
        except (asyncio.IncompleteReadError, ConnectionError, asyncio.LimitOverrunError,
                ValueError):
            pass
        except Exception:
            log.exception("web request failed")
        finally:
            writer.close()

    async def _request(self, reader, writer) -> bool:
        head = await reader.readuntil(b"\r\n\r\n")
        if len(head) > 16384:
            return False
        lines = head.decode("latin-1").split("\r\n")
        method, target, _ = (lines[0].split(" ") + ["", ""])[:3]
        headers = {}
        for h in lines[1:]:
            k, sep, v = h.partition(":")
            if sep:
                headers[k.strip().lower()] = v.strip()
        length = int(headers.get("content-length", "0") or 0)
        if length > MAX_BODY:
            await self._send(writer, 413, {"error": "too large"})
            return False
        body = await reader.readexactly(length) if length else b""
        url = urlsplit(target)
        status, payload, ctype = await self._route(method, url.path, parse_qs(url.query),
                                                  headers, body)
        await self._send(writer, status, payload, ctype)
        return headers.get("connection", "").lower() != "close"

    async def _route(self, method, path, query, headers, body):
        core = self.core
        if path.startswith("/api/"):
            if method == "GET" and path == "/api/state":
                since = int((query.get("since") or ["-1"])[0] or -1)
                await core.wait_change(since, POLL_SEC)
                return 200, core.snapshot(), None
            if method != "POST":
                return 405, {"error": "method"}, None
            if headers.get("x-tbclient") != "1":
                return 403, {"error": "X-TBClient header missing"}, None
            if not headers.get("content-type", "").startswith("application/json"):
                return 415, {"error": "json only"}, None
            try:
                data = json.loads(body or b"{}")
                if not isinstance(data, dict):
                    raise ValueError
            except ValueError:
                return 400, {"error": "bad json"}, None
            ok = True
            if path == "/api/connect":
                await core.connect()
            elif path == "/api/disconnect":
                core.disconnect()
            elif path == "/api/leave":
                core.leave()
            elif path == "/api/join":
                ok = core.join(int(data.get("board", 0)))
            elif path == "/api/say":
                ok = core.say(str(data.get("text", "")))
            elif path == "/api/react":
                ok = core.react(int(data.get("seq", -1)), str(data.get("emoji", "")))
            elif path == "/api/symbol":
                ok = core.set_symbol(str(data.get("symbol", "")))
            else:
                return 404, {"error": "unknown"}, None
            return (200 if ok else 400), {"ok": ok}, None
        if method != "GET":
            return 405, {"error": "method"}, None
        name = FILES.get(path)
        if name is None or not (STATIC / name).is_file():
            return 404, {"error": "not found"}, None
        return 200, (STATIC / name).read_bytes(), TYPES.get(Path(name).suffix,
                                                           "application/octet-stream")

    async def _send(self, writer, status, payload, ctype=None) -> None:
        if isinstance(payload, (bytes, bytearray)):
            data = bytes(payload)
        else:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            ctype = "application/json; charset=utf-8"
        head = [f"HTTP/1.1 {status} {REASONS.get(status, '')}",
                f"Content-Type: {ctype}", f"Content-Length: {len(data)}",
                "Cache-Control: no-store"] + [f"{k}: {v}" for k, v in HEADERS.items()]
        writer.write(("\r\n".join(head) + "\r\n\r\n").encode("latin-1") + data)
        await writer.drain()
