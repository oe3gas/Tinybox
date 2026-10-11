"""Current TinyBox client version and its feature bulletin (CR18).

TinyBox and the client live in the same repository, so after a `git pull`
the mailbox knows the newest client version by itself: it reads VERSION from
tbclient/__init__.py (as text, the client package is never imported).

The feature description tbclient/FEATURES.txt is kept as a fixed bulletin in
the rubric TBNEWS ("TinyBox News"). A client that announces an older version
gets the current one and the number of this bulletin in the //OK answer:

    //OK TB1 caps=CHAT,UI cur=2026.10.11 news=123

Fixed bulletins (replace_key "fixed:...") are never deleted by age. When the
text changes, the old bulletin is deleted and a new one is created - a new
number, so the clients' bulletin sync fetches it again.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .app import App

log = logging.getLogger(__name__)

CLIENT_DIR = Path(__file__).resolve().parent.parent / "tbclient"
RUBRIC = "TBNEWS"
KEY = "fixed:tbclient-features"
VERSION_RE = re.compile(r'^VERSION\s*=\s*"([0-9][0-9.]*)"', re.M)


def client_version(client_dir: Path = CLIENT_DIR) -> str:
    """Newest client version, '' if the client is not next to the TinyBox."""
    try:
        m = VERSION_RE.search((client_dir / "__init__.py").read_text(encoding="utf-8"))
    except OSError:
        return ""
    return m.group(1) if m else ""


def version_key(v: str) -> tuple[int, ...]:
    """'2026.10.11' -> (2026, 10, 11); also orders the old '0.1' before every date."""
    return tuple(int(p) for p in re.findall(r"\d+", v))


def ensure_bulletin(app: App, client_dir: Path = CLIENT_DIR) -> int | None:
    """Create or renew the feature bulletin. Returns its number (None: no text)."""
    version = client_version(client_dir)
    try:
        body = (client_dir / "FEATURES.txt").read_text(encoding="utf-8").strip() + "\n"
    except OSError:
        log.info("no tbclient/FEATURES.txt - no feature bulletin")
        return None
    subject = f"TinyBox client {version}: features" if version else "TinyBox client: features"
    store = app.store
    old = store.get_by_replace_key(KEY)
    if old is not None:
        if (old.subject, old.body, old.to_call) == (subject, body, RUBRIC):
            return old.id
        store.delete(old.id)                     # new text -> new number (clients fetch it)
        app.bus.publish("message.expired", ids=[old.id])
    msg_id = app.service.create(
        from_call=app.cfg.station.mailbox_call, to_call=RUBRIC, type="B",
        subject=subject, body=body, origin="sysop", sysop=True, replace_key=KEY)
    log.info("client feature bulletin %d (%s)", msg_id, version or "no version")
    return msg_id
