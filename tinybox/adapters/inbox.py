"""Inbox folder: scripts on this PC drop text files, TinyBox makes bulletins.

File format (UTF-8, like an e-mail: header lines, blank line, text):

    To: WX
    Subject: Wetter Hollabrunn 02.10. 19:00
    From: OE3GAS              (optional, default: sysop call)
    Replace: geosphere-wetter (optional: update the bulletin with this name)
    Valid: 6h                 (optional: 90m, 6h, 2d - then deleted)
    Brocast: {"typ":"wx",...} (optional: ready brocast page, JSON in one line;
                               sent to brocastd instead of the text, PLANUNG 6d)

    Text ...

Only *.txt is read (write *.tmp first, then rename). Processed files move to
<dir>/erledigt/, rejected ones to <dir>/fehler/ together with a .err file.
Only bulletins - private mail cannot be sent this way.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from ..config import normalize_call
from ..service import ServiceError

if TYPE_CHECKING:
    from ..app import App

log = logging.getLogger(__name__)

HEADERS = {"to", "subject", "from", "replace", "valid", "brocast"}
BROCAST_MAX_BYTES = 8192
KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$")
VALID_RE = re.compile(r"^(\d+)\s*([mhd])$", re.IGNORECASE)
UNIT_MIN = {"m": 1, "h": 60, "d": 1440}
MIN_AGE_SEC = 2          # do not touch files that are still being written


class InboxError(ValueError):
    pass


@dataclass
class Bulletin:
    to: str
    subject: str
    body: str
    sender: str | None = None
    replace: str | None = None
    valid_min: int | None = None
    brocast: str | None = None           # compact JSON text of the brocast page


def parse(raw: bytes) -> Bulletin:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")             # Windows editors without UTF-8
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    head, sep, body = text.partition("\n\n")
    if not sep:
        raise InboxError("Leerzeile zwischen Kopfzeilen und Text fehlt")
    fields: dict[str, str] = {}
    for line in head.split("\n"):
        if not line.strip():
            continue
        name, colon, value = line.partition(":")
        name = name.strip().lower()
        if not colon or name not in HEADERS:
            raise InboxError(f"unbekannte Kopfzeile: {line.strip()[:40]!r} "
                             "(erlaubt: To, Subject, From, Replace, Valid, Brocast)")
        fields[name] = value.strip()
    for need in ("to", "subject"):
        if not fields.get(need):
            raise InboxError(f"Kopfzeile {need.capitalize()}: fehlt")
    replace = fields.get("replace") or None
    if replace and not KEY_RE.match(replace):
        raise InboxError(f"Replace: {replace!r} – erlaubt sind A-Z, a-z, 0-9, Punkt, - und _")
    valid_min = None
    if fields.get("valid"):
        m = VALID_RE.match(fields["valid"])
        if not m or int(m.group(1)) == 0:
            raise InboxError(f"Valid: {fields['valid']!r} – Beispiele: 90m, 6h, 2d")
        valid_min = int(m.group(1)) * UNIT_MIN[m.group(2).lower()]
    brocast = _brocast_page(fields["brocast"]) if fields.get("brocast") else None
    body = body.strip("\n")
    if not body.strip():
        raise InboxError("Text fehlt")
    return Bulletin(to=fields["to"], subject=fields["subject"], body=body,
                    sender=fields.get("from") or None, replace=replace, valid_min=valid_min,
                    brocast=brocast)


def _brocast_page(value: str) -> str:
    """Only a light check here (JSON object with "typ"); brocastd checks the
    content. Stored compact, so that "same content again" is recognized."""
    if len(value.encode("utf-8")) > BROCAST_MAX_BYTES:
        raise InboxError(f"Brocast: länger als {BROCAST_MAX_BYTES} Bytes")
    try:
        page = json.loads(value)
    except ValueError as exc:
        raise InboxError(f"Brocast: kein gültiges JSON ({exc})") from None
    if not isinstance(page, dict) or not page.get("typ"):
        raise InboxError("Brocast: JSON-Objekt mit \"typ\" erwartet")
    return json.dumps(page, ensure_ascii=False, separators=(",", ":"))


class Inbox:
    def __init__(self, app: App) -> None:
        self.app = app
        self.dir: Path = app.cfg.inbox.directory
        self.done = self.dir / "erledigt"
        self.failed = self.dir / "fehler"
        for d in (self.dir, self.done, self.failed):
            d.mkdir(parents=True, exist_ok=True)

    async def run(self) -> None:
        log.info("inbox: watching %s", self.dir)
        while True:
            try:
                self.scan()
            except OSError as exc:
                log.warning("inbox: %s", exc)
            await asyncio.sleep(self.app.cfg.inbox.poll_sec)

    def scan(self, now: float | None = None) -> int:
        now = time.time() if now is None else now
        count = 0
        for f in sorted(self.dir.glob("*.txt")):
            if now - f.stat().st_mtime < MIN_AGE_SEC:
                continue
            self.process(f)
            count += 1
        return count

    def process(self, f: Path) -> int | None:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        try:
            b = parse(f.read_bytes())
            msg_id = self.store(b)
        except (InboxError, ServiceError) as exc:
            reason = self._reason(exc)
            log.warning("inbox: %s rejected: %s", f.name, reason)
            target = self.failed / f"{stamp}_{f.name}"
            f.replace(target)
            target.with_suffix(".err").write_text(reason + "\n", encoding="utf-8")
            return None
        log.info("inbox: %s -> msg %d", f.name, msg_id)
        f.replace(self.done / f"{stamp}_{f.name}")
        return msg_id

    def store(self, b: Bulletin) -> int:
        svc, cfg = self.app.service, self.app.cfg
        expires = None
        if b.valid_min:
            expires = (datetime.now(timezone.utc) + timedelta(minutes=b.valid_min)) \
                .strftime("%Y-%m-%dT%H:%M:%SZ")
        return svc.create(from_call=normalize_call(b.sender or cfg.station.sysop_call),
                          to_call=b.to, type="B", subject=b.subject, body=b.body,
                          origin="inbox", sysop=True, replace_key=b.replace, expires=expires,
                          brocast=b.brocast)

    def _reason(self, exc: Exception) -> str:
        if isinstance(exc, ServiceError):
            texts = {"invalid_call": "ungültiges Rufzeichen/Ziel", "too_large":
                     f"Text zu lang (max. {self.app.cfg.mailbox.max_msg_bytes} Bytes)",
                     "invalid_value": "ungültiger Wert",
                     "bad_rubric": "Rubrik nicht in [rubrics] der tinybox.conf"}
            return f"{texts.get(exc.code, exc.code)}: {exc}"
        return str(exc)


async def start(app: App) -> asyncio.Task:
    inbox = Inbox(app)
    return asyncio.create_task(inbox.run(), name="inbox")
