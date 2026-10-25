"""Release version of the repository and the update check against GitHub (PLANUNG 24).

One version for everything (decided 25.10.2026, variant A): a GitHub release
`v1.1.0` is TinyBox, tbclient, brocastd and kisshub together. RELEASE below is
that version; it is raised right before the release is tagged (GIT-ANLEITUNG).
The modules keep their own build versions (tbclient 2026.10.24.2 ...) - those
say which commit runs, RELEASE says which release it belongs to.

The check asks the GitHub API for the newest release (drafts and pre-releases
are left out by GitHub itself) and compares it with RELEASE:

    GET https://api.github.com/repos/oe3gas/Tinybox/releases/latest

- at most once per `interval` (default a day); the answer is kept in a small
  JSON cache, a restart does not ask again
- with ETag / If-None-Match: an unchanged answer is "304 Not Modified" and does
  not count against GitHub's limit (60 requests per hour and IP without a token)
- TLS is checked as usual (urllib's default context), nothing is switched off
- offline or any error: no result, no message, no delay worth mentioning -
  a station without internet must not notice the check at all
- only a hint: nothing is downloaded or installed (an automatic updater would be
  a way into every station for whoever takes over the account or a release)

    result = check(cache=Path("data/release.json"))
    if result and result.newer: ...

Programs on asyncio start `watch()` as a task; it calls back on every result.
"""

from __future__ import annotations

import asyncio
import configparser
import json
import logging
import re
import time
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

RELEASE = "1.0.0"
REPO = "oe3gas/Tinybox"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{REPO}/releases"

DAY = 24 * 3600
TIMEOUT_SEC = 5

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class UpdateCfg:
    """[update] - the same section in tinybox.conf, tbclient.conf, brocastd.conf and
    kisshub.conf. announce is read by TinyBox only."""
    check: bool = True          # ask GitHub once a day
    announce: bool = True       # TinyBox: one TBNEWS bulletin per new release


def load_cfg(cp: configparser.ConfigParser) -> UpdateCfg:
    """[update] from a parsed config file; missing section = defaults.
    A wrong value raises ValueError (the caller turns it into its ConfigError)."""
    try:
        return UpdateCfg(check=cp.getboolean("update", "check", fallback=True),
                         announce=cp.getboolean("update", "announce", fallback=True))
    except ValueError as exc:
        raise ValueError(f"[update]: {exc}") from None


def load_cfg_file(path: str | Path) -> UpdateCfg:
    """[update] straight from a config file - for programs whose loader does not
    keep the parser. A missing or broken file gives the defaults."""
    cp = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
    try:
        cp.read(path, encoding="utf-8")
        return load_cfg(cp)
    except (configparser.Error, ValueError, OSError):
        return UpdateCfg()


def parse_version(tag: str) -> tuple[int, ...] | None:
    """'v1.2.0' / '1.2' -> (1, 2, 0) / (1, 2, 0); anything else (a date build,
    'prod-f16d5a3', '1.2.0-rc1') -> None."""
    m = re.fullmatch(r"[vV]?(\d+)(?:\.(\d+))?(?:\.(\d+))?", tag.strip())
    if not m:
        return None
    return tuple(int(g or 0) for g in m.groups())


def is_newer(latest: str, current: str = RELEASE) -> bool:
    a, b = parse_version(latest), parse_version(current)
    return a is not None and b is not None and a > b


@dataclass(frozen=True)
class UpdateResult:
    latest: str                 # tag of the newest release, e.g. "v1.1.0"
    url: str                    # its page on GitHub
    notes: str                  # release text (Markdown, as written on GitHub)
    published: str              # ISO time from GitHub, may be ""
    current: str                # RELEASE of this installation
    newer: bool                 # latest > current

    def as_dict(self) -> dict:
        return {"latest": self.latest, "url": self.url, "published": self.published,
                "current": self.current, "newer": self.newer}

    def hint(self) -> str:
        """One line for a log or a console."""
        return (f"new release {self.latest} on GitHub (running {self.current}): {self.url}"
                if self.newer else f"release {self.current} is current")


def _fetch(etag: str | None, timeout: float, user_agent: str) -> tuple[int, dict | None, str | None]:
    """(HTTP status, JSON or None, ETag). Raises on network errors."""
    req = urllib.request.Request(API_URL, headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": user_agent})         # GitHub refuses requests without one
    if etag:
        req.add_header("If-None-Match", etag)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8")), r.headers.get("ETag")
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            return 304, None, etag
        raise


def read_cache(path: Path | None) -> dict:
    if path is None:
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_cache(path: Path | None, data: dict) -> None:
    """Keeps keys of other users of the file (TinyBox stores 'announced' here)."""
    if path is None:
        return
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        log.debug("update check: cannot write %s: %s", path, exc)


def _result(rel: dict | None, current: str) -> UpdateResult | None:
    if not rel or not rel.get("tag_name"):
        return None
    tag = str(rel["tag_name"])
    return UpdateResult(latest=tag, url=str(rel.get("html_url") or RELEASES_URL),
                        notes=str(rel.get("body") or ""),
                        published=str(rel.get("published_at") or ""),
                        current=current, newer=is_newer(tag, current))


def check(current: str = RELEASE, cache: Path | None = None, interval: float = DAY,
          program: str = "tinybox", timeout: float = TIMEOUT_SEC,
          fetch: Callable = _fetch, now: Callable[[], float] = time.time,
          force: bool = False) -> UpdateResult | None:
    """Newest release compared with `current`. None: offline, error, no release yet.
    Blocking (up to `timeout`) - from asyncio call it in a thread (watch() does)."""
    data = read_cache(cache)
    if not force and now() - float(data.get("ts", 0) or 0) < interval:
        return _result(data.get("release"), current)
    data["ts"] = now()                       # also on errors: no retry every minute
    try:
        status, rel, etag = fetch(data.get("etag"), timeout, f"TinyBox-{program}/{current}")
    except Exception as exc:                  # offline, DNS, TLS, 403 rate limit ...
        log.debug("update check failed: %s", exc)
        write_cache(cache, data)
        return _result(data.get("release"), current)
    if status == 200 and rel is not None:
        data["release"] = {k: rel.get(k) for k in
                           ("tag_name", "html_url", "body", "published_at")}
        data["etag"] = etag
    write_cache(cache, data)
    return _result(data.get("release"), current)


async def watch(on_result: Callable[[UpdateResult], None], *, current: str = RELEASE,
                cache: Path | None = None, program: str = "tinybox",
                first_after_sec: float = 30, interval: float = DAY,
                check_fn: Callable = check) -> None:
    """Task: first check `first_after_sec` after the start (the start itself is
    never delayed), then every `interval`. Calls on_result with every result,
    newer or not; errors in on_result are logged and do not end the task."""
    await asyncio.sleep(first_after_sec)
    while True:
        result = await asyncio.to_thread(check_fn, current, cache, interval, program)
        if result is not None:
            try:
                on_result(result)
            except Exception:
                log.exception("update check: handling the result failed")
        await asyncio.sleep(interval)


_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe",
                          "Ü": "Ue", "ß": "ss", "–": "-", "—": "-", "“": '"',
                          "”": '"', "„": '"', "’": "'", "…": "..."})


def ascii_notes(notes: str, max_lines: int = 8, max_bytes: int = 500) -> str:
    """Release text for a bulletin over the radio: ASCII, no Markdown decoration,
    at most a few lines - like tbclient/news, every byte counts."""
    out: list[str] = []
    size = 0
    for raw in notes.replace("\r", "").split("\n"):
        line = raw.translate(_UMLAUTS)
        line = unicodedata.normalize("NFKD", line).encode("ascii", "ignore").decode()
        line = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", line)     # [text](link) -> text
        line = re.sub(r"^\s*#+\s*", "", line)                    # headings
        line = re.sub(r"^(\s*)[*+]\s+", r"\1- ", line)           # bullets -> "- "
        line = line.replace("**", "").replace("__", "").replace("`", "").rstrip()
        if not line.strip():
            if out and out[-1]:
                out.append("")
            continue
        if size + len(line) + 1 > max_bytes or len([x for x in out if x]) >= max_lines:
            out.append("...")
            break
        out.append(line)
        size += len(line) + 1
    while out and not out[-1]:
        out.pop()
    return "\n".join(out)
