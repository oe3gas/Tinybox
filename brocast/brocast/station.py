"""Station logic behind the ingest API: turn provider content into pages on air.

Providers send named content (JSON). The station adds id, rev, t, cuts the
page into frames and stores them for the carousel. org is not put on air:
it defaults to the AX.25 sender, which is this station.

Zwei Frame-Formate ([station] wire_format):
  2 (Standard)  Umschlag einmal, Blockliste gepackt, Frames randvoll
                (fragment.py) – deutlich weniger Funkbytes
  1 (alt)       eine vollständige Seite je Frame, lange Inhalte als
                Unterseiten (splitter.py); nur noch für Vergleichsmessungen
                und Gegenstellen mit alter Software
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Callable

from . import fragment
from .codec import BrocastError, Codec
from .config import Config
from .frame import FORMAT_PAGE, airtime_s, build as build_frame, header
from .splitter import TooLargeError, split
from .store import PageRow, Store
from .zdict import ZDict

PROVIDER_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.@-]{0,63}$")
MANAGED = ("dv", "rev", "t", "org", "sub")      # set by brocastd, never by providers


class NotFound(BrocastError):
    pass


class Station:
    def __init__(self, cfg: Config, codec: Codec, store: Store,
                 clock: Callable[[], float] = time.time,
                 on_change: Callable[[], None] = lambda: None,
                 zd: ZDict | None = None):
        self.cfg, self.codec, self.store = cfg, codec, store
        self.clock = clock
        self.on_change = on_change
        self.zd = zd                  # Preset-Wörterbuch; None = nicht komprimieren

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def check_names(provider: str, key: str | None = None) -> None:
        if not PROVIDER_RE.match(provider):
            raise BrocastError(f"ungültiger Lieferanten-Name {provider!r} (a-z, 0-9, _ -)")
        if key is not None and not KEY_RE.match(key):
            raise BrocastError(f"ungültiger Schlüssel {key!r}")

    @staticmethod
    def content_hash(content: dict[str, Any]) -> str:
        text = json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _check_content(self, content: Any) -> dict[str, Any]:
        if not isinstance(content, dict):
            raise BrocastError("Seite muss ein JSON-Objekt sein")
        bad = [k for k in MANAGED if k in content]
        if bad:
            raise BrocastError(f"Felder {', '.join(bad)} setzt brocastd selbst")
        if "typ" not in content:
            raise BrocastError("Pflichtfeld 'typ' fehlt")
        if "parts" in content:
            parts = content["parts"]
            if "blk" in content:
                raise BrocastError("entweder 'blk' oder 'parts' angeben, nicht beides")
            if not isinstance(parts, list) or not all(
                    isinstance(p, list) and all(isinstance(b, dict) for b in p) for p in parts):
                raise BrocastError("'parts' muss eine Liste von Block-Listen sein")
        return content

    def _exp_min(self, content: dict[str, Any]) -> int | None:
        if "exp" in content:
            return content["exp"]
        typ = self.codec.d.enums["typ"].by_name.get(content["typ"]) \
            if isinstance(content["typ"], str) else self.codec.d.typ_entry(content["typ"])
        return typ.spec.get("exp") if typ else None

    def _pri(self, content: dict[str, Any]) -> int:
        return self.codec.d.enums["pri"].num(content.get("pri", 0))

    def _frames(self, content: dict[str, Any], page_id: int, rev: int,
                t: int) -> tuple[list[bytes], int]:
        """Frames (Nutzdaten ohne Header-Byte) und das Header-Byte dieser Seite."""
        # "parts" is an ingest-only field: thematic sections, each starts a subpage
        page = {k: v for k, v in content.items() if k != "parts"}
        page.update({"id": page_id, "rev": rev, "t": t})
        st = self.cfg.station
        if st.wire_format == FORMAT_PAGE:
            return split(self.codec, page, max_subpages=st.max_subpages,
                         parts=content.get("parts")), header()
        # Format 2: der ganze Inhalt geht als ein Blob über Funk. "parts" teilt
        # dort nichts mehr auf (die Frames werden ohnehin voll gefüllt), die
        # Blöcke der Abschnitte kommen aber hintereinander in die Blockliste.
        if content.get("parts") and "blk" not in page:
            page["blk"] = [block for part in content["parts"] for block in part]
        built = fragment.build(self.codec, page, self.zd if st.compress else None,
                               max_fragments=st.max_subpages)
        return built.payloads, built.hdr

    def _airtime(self, frames: list[bytes], hdr: int) -> float:
        st = self.cfg.station
        return round(sum(airtime_s(len(build_frame(self.cfg.callsign, f, st.path, hdr)),
                                   st.baud, st.txdelay_ms) for f in frames), 1)

    def _result(self, row: PageRow, frames: list[bytes], changed: bool) -> dict[str, Any]:
        return {
            "id": row.id, "rev": row.rev, "changed": changed, "state": row.state,
            "subpages": len(frames), "bytes": [len(f) for f in frames],
            "airtime_s": self._airtime(frames, row.hdr),
            "wire": row.hdr >> 4, "packed": bool(row.hdr >> 4 != FORMAT_PAGE and row.hdr & 0x1),
            "next_tx": datetime.fromtimestamp(row.next_tx, timezone.utc).isoformat(),
        }

    # -- API operations -----------------------------------------------------

    def put(self, provider: str, key: str, content: Any) -> dict[str, Any]:
        self.check_names(provider, key)
        content = self._check_content(content)
        now = int(self.clock())
        h = self.content_hash(content)
        row = self.store.get_page(provider, key)

        fixed_id = content.get("id")
        if fixed_id is not None and (row is None or row.id != fixed_id):
            if not isinstance(fixed_id, int) or isinstance(fixed_id, bool) or fixed_id < 1:
                raise BrocastError("id muss eine positive Ganzzahl sein")
            if self.store.id_in_use(fixed_id):
                raise BrocastError(f"Seitennummer {fixed_id} ist bereits vergeben")
        body = {k: v for k, v in content.items() if k != "id"}

        if row and row.state == "active" and row.content_hash == h:
            frames, hdr = self._frames(body, row.id, row.rev, now)  # confirm: refresh t only
            row.t = now
            row.hdr = hdr
            self.store.save_page(row, frames)
            return self._result(row, frames, changed=False)

        if row:
            page_id, rev = (fixed_id or row.id), row.rev + 1
        else:
            page_id = fixed_id or self.store.next_auto_id(self.cfg.station.id_auto_start)
            rev = 0
        frames, hdr = self._frames(body, page_id, rev, now)
        new = PageRow(pid=row.pid if row else 0, provider=provider, pkey=key, id=page_id,
                      rev=rev, t=now, content=json.dumps(content, ensure_ascii=False),
                      content_hash=h, exp_min=self._exp_min(content), pri=self._pri(content),
                      state="active", withdraw_left=0, tx_count=0, last_tx=None, next_tx=now,
                      hdr=hdr)
        new.pid = self.store.save_page(new, frames)
        self.on_change()
        return self._result(new, frames, changed=True)

    def put_frames(self, provider: str, key: str, build: Callable[[int, int, int], list[bytes]],
                   content_hash: str, description: dict[str, Any]) -> dict[str, Any] | None:
        """Station-internal pages whose frames are built elsewhere (dictionary
        transfer). build(page_id, rev, t) -> frames. Nothing happens while the
        page with this content_hash is active. The page never expires."""
        row = self.store.get_page(provider, key)
        if row and row.state == "active" and row.content_hash == content_hash:
            return None
        now = int(self.clock())
        page_id = row.id if row else self.store.next_auto_id(self.cfg.station.id_auto_start)
        rev = row.rev + 1 if row else 0
        frames = build(page_id, rev, now)
        new = PageRow(pid=row.pid if row else 0, provider=provider, pkey=key, id=page_id,
                      rev=rev, t=now, content=json.dumps(description, ensure_ascii=False),
                      content_hash=content_hash, exp_min=None, pri=0, state="active",
                      withdraw_left=0, tx_count=0, last_tx=None, next_tx=now)
        new.pid = self.store.save_page(new, frames)
        self.on_change()
        return self._result(new, frames, changed=True)

    def delete(self, provider: str, key: str) -> dict[str, Any]:
        self.check_names(provider, key)
        row = self.store.get_page(provider, key)
        if row is None:
            raise NotFound(f"Seite {provider}/{key} nicht vorhanden")
        if row.state == "withdrawn":
            return self._result(row, self.store.frames(row.pid), changed=False)
        content = json.loads(row.content)
        now = int(self.clock())
        row.rev += 1
        row.t = now
        row.state = "withdrawn"
        row.withdraw_left = self.cfg.station.withdraw_repeats
        row.tx_count, row.next_tx = 0, now
        frames, row.hdr = self._frames({"typ": content["typ"], "flg": ["withdrawn"]},
                                       row.id, row.rev, now)
        self.store.save_page(row, frames)
        self.on_change()
        return self._result(row, frames, changed=True)

    def sync(self, provider: str, pages: Any) -> dict[str, Any]:
        """Full list of a provider's current pages; missing ones are withdrawn."""
        self.check_names(provider)
        if not isinstance(pages, dict):
            raise BrocastError("'pages' muss ein Objekt {schlüssel: seite} sein")
        results: dict[str, Any] = {}
        errors: dict[str, str] = {}
        for key, content in pages.items():
            try:
                results[key] = self.put(provider, key, content)
            except BrocastError as exc:
                errors[key] = str(exc)
        withdrawn = []
        for row in self.store.list_pages(provider):
            if row.pkey not in pages and row.state == "active":
                self.delete(provider, row.pkey)
                withdrawn.append(row.pkey)
        return {"pages": results, "errors": errors, "withdrawn": withdrawn}

    def get(self, provider: str, key: str) -> dict[str, Any]:
        self.check_names(provider, key)
        row = self.store.get_page(provider, key)
        if row is None:
            raise NotFound(f"Seite {provider}/{key} nicht vorhanden")
        info = self._result(row, self.store.frames(row.pid), changed=False)
        del info["changed"]
        info.update({"key": row.pkey, "tx_count": row.tx_count, "exp_min": row.exp_min,
                     "last_tx": row.last_tx and datetime.fromtimestamp(
                         row.last_tx, timezone.utc).isoformat()})
        return info

    def list(self, provider: str | None) -> list[dict[str, Any]]:
        if provider is not None:
            self.check_names(provider)
        return [{"provider": r.provider, "key": r.pkey, "id": r.id, "rev": r.rev,
                 "state": r.state, "tx_count": r.tx_count}
                for r in self.store.list_pages(provider)]

    def validate(self, content: Any) -> dict[str, Any]:
        content = self._check_content(content)
        body = {k: v for k, v in content.items() if k != "id"}
        frames, hdr = self._frames(body, content.get("id", self.cfg.station.id_auto_start),
                                   0, int(self.clock()))
        return {"ok": True, "subpages": len(frames), "bytes": [len(f) for f in frames],
                "airtime_s": self._airtime(frames, hdr), "wire": hdr >> 4,
                "packed": bool(hdr >> 4 != FORMAT_PAGE and hdr & 0x1)}


__all__ = ["Station", "NotFound", "TooLargeError"]
