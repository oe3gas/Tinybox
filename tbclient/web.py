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
  POST /api/history  {"n": 10}   older history lines of the board (CR13)
  POST /api/histmode {"mode": "missed"|"none"|"10"|"20"}   history when joining

Mailbox (C3), all local - only "sync" goes on air:
  GET  /api/mail?folder=inbox|sent|outbox|b:<RUBRIC>   message list (no texts)
  POST /api/mail/open     {"id": n}          -> the message with text (marks it read)
  POST /api/mail/delete   {"id": n}
  POST /api/mail/save     {"oid": n|null, "type": "P"|"B", "to": "...", "subject": "...",
                           "body": "..."}   -> {"oid": n}  (into the outbox)
  POST /api/mail/discard  {"oid": n}
  POST /api/mail/subscribe {"rubric": "ALL", "on": true}
  POST /api/mail/sync {"scope": "mail"|"bulletins"} | /api/mail/cancel
  POST /api/mail/news   subscribe TBNEWS + fetch bulletins ("Read about new features")
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import VERSION
from .core import ClientCore

log = logging.getLogger(__name__)

STATIC = Path(__file__).resolve().parent / "web"
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".js": "text/javascript; charset=utf-8", ".json": "application/json",
         ".png": "image/png", ".svg": "image/svg+xml", ".webp": "image/webp"}
FILES = {"/": "index.html", "/app.css": "app.css", "/app.js": "app.js",
         "/emoji.json": "emoji.json", "/aprs/symbols-0.png": "aprs/aprs-symbols-24-0@2x.png",
         "/aprs/symbols-1.png": "aprs/aprs-symbols-24-1@2x.png",
         "/aprs/names.json": "aprs/names.json", "/manifest.json": "manifest.json",
         "/logo.svg": "logo.svg"}
# CR11: the sticker set (fixed files in the client, never sent over the air)
FILES.update({f"/stickers/{p.name}": f"stickers/{p.name}"
              for p in (STATIC / "stickers").glob("*") if p.suffix in (".webp", ".json")})
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
CALL_AT_RE = re.compile(r"^[A-Z0-9]{1,6}(-\d{1,2})?(@[A-Z0-9#.-]{1,40})?$")
RUBRIC_RE = re.compile(r"^[A-Z0-9]{1,6}$")
MAX_BODY = 131072        # a message for the outbox can be long
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
            if method == "GET" and path == "/api/mail":
                folder = (query.get("folder") or ["inbox"])[0]
                if folder not in ("inbox", "sent", "outbox") and not folder.startswith("b:"):
                    return 400, {"error": "folder"}, None
                return 200, {"folder": folder, "items": core.mailbox.folder(folder)}, None
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
            elif path == "/api/history":
                ok = core.load_history(int(data.get("n", 10)))
            elif path == "/api/histmode":
                ok = core.set_history_mode(str(data.get("mode", "")))
            elif path.startswith("/api/mail/"):
                return self._mail(path[10:], data)
            else:
                return 404, {"error": "unknown"}, None
            return (200 if ok else 400), {"ok": ok}, None
        if method != "GET":
            return 405, {"error": "method"}, None
        name = FILES.get(path)
        if name is None or not (STATIC / name).is_file():
            return 404, {"error": "not found"}, None
        data = (STATIC / name).read_bytes()
        if name == "index.html":                 # the page knows its version (CR18)
            data = data.replace(b"__TBC_VERSION__", VERSION.encode())
        return 200, data, TYPES.get(Path(name).suffix, "application/octet-stream")

    def _mail(self, action: str, data: dict):
        core, box = self.core, self.core.mailbox
        try:
            if action == "open":
                m = box.open(int(data.get("id", 0)))
                core._touch()
                return (200, m, None) if m else (404, {"error": "not found"}, None)
            if action == "delete":
                ok = box.delete(int(data.get("id", 0)))
            elif action == "save":
                kind = str(data.get("type", "P")).upper()
                to = str(data.get("to", "")).strip().upper().replace(" ", "")
                subject = " ".join(str(data.get("subject", "")).split())[:60]
                body = str(data.get("body", "")).replace("\r\n", "\n")
                if kind not in ("P", "B") or not CALL_AT_RE.match(to):
                    return 400, {"error": "address"}, None
                oid = box.save_out(int(data.get("oid") or 0) or None, kind, to, subject, body)
                core._touch()
                return 200, {"ok": True, "oid": oid}, None
            elif action == "discard":
                ok = box.discard_out(int(data.get("oid", 0)))
            elif action == "subscribe":
                rubric = str(data.get("rubric", "")).upper()
                if not RUBRIC_RE.match(rubric):
                    return 400, {"error": "rubric"}, None
                box.subscribe(rubric, bool(data.get("on")))
                ok = True
            elif action == "sync":
                ok = core.sync.start(str(data.get("scope", "mail")))
            elif action == "news":
                ok = core.open_news()
            elif action == "cancel":
                core.sync.cancel()
                ok = True
            else:
                return 404, {"error": "unknown"}, None
        except (TypeError, ValueError):
            return 400, {"error": "bad value"}, None
        core._touch()
        return (200 if ok else 400), {"ok": ok}, None

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
