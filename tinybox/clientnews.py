"""Current TinyBox client version and its news bulletins (CR18).

TinyBox and the client live in the same repository, so after a `git pull`
the mailbox knows the newest client version by itself: it reads VERSION from
tbclient/__init__.py (as text, the client package is never imported).

What is new in a version is in tbclient/news/<version>.txt - short ASCII, a
few lines, because it goes out over the radio. Each file becomes its own fixed
bulletin in the rubric TBNEWS ("TinyBox News"), subject "Client <version>".
The bulletins are incremental: a client fetches only the ones it does not have.
Only the newest MAX_NEWS versions are kept; older files may simply be deleted
from the repository, their bulletins go too. A client that announces an older
version gets the current one and the number of the newest news bulletin:

    //OK TB1 caps=CHAT,UI cur=2026.10.11 news=123

Fixed bulletins (replace_key "fixed:...") are never deleted by age. When the
text of a file changes, its bulletin gets a new number, so the clients'
bulletin sync fetches it again. tbclient/FEATURES.txt is only the overview in
the repository and is not sent.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

from .config import NEWS_RUBRIC

if TYPE_CHECKING:
    from .app import App

log = logging.getLogger(__name__)

CLIENT_DIR = Path(__file__).resolve().parent.parent / "tbclient"
RUBRIC = NEWS_RUBRIC
KEY_PREFIX = "fixed:tbclient-news-"
MAX_NEWS = 10
NEWS_NAME_RE = re.compile(r"^\d+(\.\d+)*$")
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


def news_files(client_dir: Path = CLIENT_DIR) -> list[tuple[str, Path]]:
    """(version, file) of tbclient/news/*.txt, oldest first, at most MAX_NEWS."""
    found = [(f.stem, f) for f in (client_dir / "news").glob("*.txt")
             if NEWS_NAME_RE.match(f.stem)]
    return sorted(found, key=lambda x: version_key(x[0]))[-MAX_NEWS:]


def ensure_bulletin(app: App, client_dir: Path = CLIENT_DIR) -> int | None:
    """One bulletin per news file; remove bulletins of files that are gone (and
    the single feature bulletin from before). Returns the number of the newest
    (None: no news)."""
    store = app.store
    wanted: dict[str, tuple[str, str]] = {}
    for version, f in news_files(client_dir):
        try:
            body = f.read_text(encoding="utf-8").strip() + "\n"
        except OSError:
            continue
        wanted[KEY_PREFIX + version] = (f"Client {version}", body)
    for m in store.list_messages():
        if m.replace_key and m.replace_key.startswith("fixed:tbclient-") \
                and m.replace_key not in wanted:
            store.delete(m.id)                   # old version or the old FEATURES bulletin
            app.bus.publish("message.expired", ids=[m.id])
    newest = None
    for key, (subject, body) in wanted.items():  # oldest first -> rising numbers
        old = store.get_by_replace_key(key)
        if old is not None and (old.subject, old.body, old.to_call) == (subject, body, RUBRIC):
            newest = old.id
            continue
        if old is not None:
            store.delete(old.id)                 # new text -> new number (clients fetch it)
            app.bus.publish("message.expired", ids=[old.id])
        newest = app.service.create(
            from_call=app.cfg.station.mailbox_call, to_call=RUBRIC, type="B",
            subject=subject, body=body, origin="sysop", sysop=True, replace_key=key)
        log.info("client news bulletin %d (%s)", newest, subject)
    return newest
