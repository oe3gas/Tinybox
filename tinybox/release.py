"""New release on GitHub: hint for the sysop, one bulletin for the users (PLANUNG 24).

The check itself is prcore.release (once a day, cached in data_dir/release.json).
TinyBox adds:

- the hint: log line once per new release, STATUS/UPDATE at the console,
  "update" in the web GUI status
- exactly one bulletin per release in TBNEWS - the rubric of the client news,
  so users get it by connecting or via the client; TBNEWS is never forwarded
  and never sent over brocast, so there is no flood of copies in the network.
  The tag already announced is kept in release.json: a restart, a second check
  or a deleted bulletin do not bring it again ("keine Dauerbeschallung").
  A newer release replaces the bulletin of the older one.
  [update] announce = no: hint only; the sysop can send it with UPDATE NEWS.

Nothing is downloaded or installed - updating stays `git pull` by the sysop.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from prcore import release

from .config import NEWS_RUBRIC

if TYPE_CHECKING:
    from .app import App

log = logging.getLogger(__name__)

KEY_PREFIX = "release:"
CACHE_NAME = "release.json"


def cache_path(app: App) -> Path:
    return Path(app.cfg.storage.data_dir) / CACHE_NAME


def bulletin_text(result: release.UpdateResult) -> tuple[str, str]:
    """(subject, body): short ASCII, like the client news."""
    subject = f"TinyBox {result.latest} verfuegbar"
    notes = release.ascii_notes(result.notes)
    body = (f"Neuer TinyBox-Release {result.latest} (TinyBox, Client,\n"
            f"brocastd, kisshub).\n")
    if notes:
        body += "\n" + notes + "\n"
    body += f"\n{result.url}\n"
    return subject, body


class UpdateNotice:
    """Takes the results of prcore.release.watch() (and of UPDATE at the console)."""

    def __init__(self, app: App) -> None:
        self.app = app
        self.result: release.UpdateResult | None = None
        self._logged: str | None = None

    # --- results ------------------------------------------------------------

    def handle(self, result: release.UpdateResult) -> None:
        self.result = result
        if not result.newer:
            return
        if self._logged != result.latest:
            self._logged = result.latest
            log.warning("update: %s", result.hint())
        if self.app.cfg.update.announce:
            self.announce(result)

    def announced(self) -> str:
        return str(release.read_cache(cache_path(self.app)).get("announced") or "")

    def announce(self, result: release.UpdateResult, force: bool = False) -> int | None:
        """The bulletin for this release, once. Returns its number, None if it was
        announced before (and not forced) or the release is not newer."""
        if not result.newer:
            return None
        cache = cache_path(self.app)
        data = release.read_cache(cache)
        if data.get("announced") == result.latest and not force:
            return None
        store, key = self.app.store, KEY_PREFIX + result.latest
        for m in store.list_messages():          # the bulletin of an older release
            if m.replace_key and m.replace_key.startswith(KEY_PREFIX) and m.replace_key != key:
                store.delete(m.id)
                self.app.bus.publish("message.expired", ids=[m.id])
        subject, body = bulletin_text(result)
        msg_id = self.app.service.create(
            from_call=self.app.cfg.station.mailbox_call, to_call=NEWS_RUBRIC, type="B",
            subject=subject, body=body, origin="sysop", sysop=True, replace_key=key)
        data["announced"] = result.latest
        release.write_cache(cache, data)
        log.info("update: bulletin %d in %s (%s)", msg_id, NEWS_RUBRIC, subject)
        return msg_id

    def status(self) -> dict | None:
        """For the web GUI status (None = no answer from GitHub yet)."""
        if self.result is None:
            return None
        d = self.result.as_dict()
        d["announced"] = self.announced() == self.result.latest
        return d

    # --- task ------------------------------------------------------------------

    async def run(self) -> None:
        await release.watch(self.handle, cache=cache_path(self.app), program="tinybox")

    async def check_now(self) -> release.UpdateResult | None:
        """UPDATE at the console: ask GitHub now, regardless of the daily cache."""
        result = await asyncio.to_thread(release.check, release.RELEASE,
                                         cache_path(self.app), release.DAY, "tinybox",
                                         force=True)
        if result is not None:
            self.handle(result)
        return result
