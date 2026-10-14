"""Listener: keeps received pages like teletext (spec section "Listener").

Rules implemented here:
  * subpages of one page are kept together; a newer revision replaces the
    page (older subpages are dropped)
  * new page -> unread; new revision of a page -> unread + "updated"
  * deleted by the user -> stays hidden until a newer revision arrives
  * withdrawn by the station -> removed at once
  * expired (t + exp) -> removed, favorites are kept
  * limits per rubric and in total; eviction order:
    oldest read -> oldest unread; favorites are never evicted
  * subscription by opt-out (station x rubric, '*' = all);
    alerts (typ alert or priority emergency) are always kept
  * a station's rubric index page (typ index) is not shown as a page: it
    announces the station's rubrics (with description), so they appear in
    the rubric list and the subscription matrix before their first page
    arrives; a rubric lives while a station announces it or pages of it
    exist, then it goes (with its opt-out line)
"""

from __future__ import annotations

import base64
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable

from . import dictimport, dicttransfer
from .codec import Codec
from .config import is_ax25_call
from .dictionary import Dictionary
from .frame import airtime_s
from .store import Store

log = logging.getLogger(__name__)

RESULT_TEXT = {
    "new": "neu – angezeigt",
    "updated": "neue Revision – wieder ungelesen",
    "subpage": "weiterer Teil ergänzt",
    "repeat": "Wiederholung – schon vorhanden, keine Änderung",
    "old": "ältere Revision – ignoriert",
    "deleted": "von dir gelöscht – ausgeblendet bis zur nächsten Revision",
    "blocked": "abgewählt (Abo) – nicht angezeigt",
    "withdrawn": "von der Station zurückgezogen – entfernt",
    "ignored": "Rückzug einer unbekannten Seite – ignoriert",
    "error": "nicht dekodierbar",
    "foreign": "kein brocast-Frame (z. B. APRS, Mailbox, Node)",
    "fragment": "Teil einer Seite – wartet auf die übrigen Fragmente",
    "zdict": "gepackt mit einem anderen Preset-Wörterbuch – brocastd aktualisieren",
    "bad": "Fragment unbrauchbar – verworfen (siehe Log)",
    "newer_format": "brocast-Frame in einem neueren Format – brocastd aktualisieren",
    "dictionary": "Dictionary-Ankündigung, Version bereits installiert",
    "dictionary_new": "Dictionary-Ankündigung einer neueren Version",
    "dict_part": "Dictionary über Funk: Teil gesammelt",
    "dict_have": "Dictionary über Funk: Teil schon vorhanden",
    "dict_current": "Dictionary über Funk: Version bereits installiert",
    "dict_ready": "Dictionary über Funk vollständig – wartet auf Freigabe",
    "dict_installed": "Dictionary über Funk vollständig – installiert",
    "dict_bad": "Dictionary über Funk unbrauchbar – verworfen (siehe Log)",
    "index": "Rubrikenliste der Station – übernommen",
    "index_same": "Rubrikenliste der Station – unverändert",
    "index_old": "ältere Rubrikenliste – ignoriert",
}
# short chip in the receive log: (label, kind for the colour)
RESULT_CHIP = {
    "new": ("Neuer Inhalt", "new"), "updated": ("Neuer Inhalt", "new"),
    "subpage": ("Neuer Inhalt", "new"), "dictionary_new": ("Neuer Inhalt", "new"),
    "repeat": ("Wiederholung", "repeat"), "dictionary": ("Wiederholung", "repeat"),
    "blocked": ("Nicht angezeigt", "hidden"), "deleted": ("Nicht angezeigt", "hidden"),
    "old": ("Nicht angezeigt", "hidden"), "ignored": ("Nicht angezeigt", "hidden"),
    "withdrawn": ("Zurückgezogen", "withdrawn"),
    "error": ("Nicht dekodierbar", "error"),
    "foreign": ("anderer Frame", "foreign"),
    "dict_part": ("Neuer Inhalt", "new"), "dict_ready": ("Neuer Inhalt", "new"),
    "dict_installed": ("Neuer Inhalt", "new"), "dict_have": ("Wiederholung", "repeat"),
    "dict_current": ("Wiederholung", "repeat"), "dict_bad": ("Nicht dekodierbar", "error"),
    "fragment": ("Teil gesammelt", "new"), "zdict": ("Nicht dekodierbar", "error"),
    "bad": ("Nicht dekodierbar", "error"), "newer_format": ("Nicht dekodierbar", "error"),
    "index": ("Neuer Inhalt", "new"), "index_same": ("Wiederholung", "repeat"),
    "index_old": ("Nicht angezeigt", "hidden"),
}

DEFAULT_SETTINGS: dict[str, Any] = {
    "max_pages_total": 500,
    "max_pages_per_cat": 100,
    "max_age_days": 30,
    "lang": "de",
    "alert_sound": True,
    "dict_trusted": [],             # stations whose dictionary over the air is installed at once
}
DICT_COLLECTIONS = 3                # parallel dictionary transfers kept while collecting
ALL = "*"
GENERAL = "all"                     # dictionary rubric "Allgemein"
CUSTOM_PREFIX = "x:"
INDEX_DAT_RUBRICS = 0               # index page: dat {0: [[cat, text], ...]} (station.py)
INDEX_MAX = 64                      # rubrics taken from one index page


class ListenerError(ValueError):
    pass


class NotFound(ListenerError):
    pass


def iso(ts: int | None) -> str | None:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat() if ts is not None else None


class Listener:
    def __init__(self, store: Store, codec: Codec, clock: Callable[[], float] = time.time,
                 baud: int = 1200, txdelay_ms: int = 300):
        self.store, self.codec, self.clock = store, codec, clock
        self.d = codec.d
        self.baud, self.txdelay_ms = baud, txdelay_ms
        # set by the daemon: install a dictionary received over the air
        self.install_dictionary: Callable[[Dictionary, str], None] | None = None

    # -- settings and subscriptions -----------------------------------------

    @property
    def settings(self) -> dict[str, Any]:
        out = dict(DEFAULT_SETTINGS)
        for key, value in self.store.settings().items():
            if key in out:
                out[key] = json.loads(value)
        return out

    def set_settings(self, values: Any) -> dict[str, Any]:
        if not isinstance(values, dict):
            raise ListenerError("Objekt mit Einstellungen erwartet")
        checks = {
            "max_pages_total": lambda v: isinstance(v, int) and 10 <= v <= 100_000,
            "max_pages_per_cat": lambda v: isinstance(v, int) and 1 <= v <= 100_000,
            "max_age_days": lambda v: isinstance(v, int) and 1 <= v <= 3650,
            "lang": lambda v: v in self.d.raw.get("languages", ["de", "en"]),
            "alert_sound": lambda v: isinstance(v, bool),
            "dict_trusted": lambda v: isinstance(v, list) and len(v) <= 20 and all(
                isinstance(c, str) and is_ax25_call(c.strip().upper()) for c in v),
        }
        for key, value in values.items():
            if key not in checks:
                raise ListenerError(f"unbekannte Einstellung {key!r}")
            if isinstance(value, bool) and key != "alert_sound" or not checks[key](value):
                raise ListenerError(f"ungültiger Wert für {key}: {value!r}")
        if "dict_trusted" in values:
            values = {**values, "dict_trusted": sorted({c.strip().upper()
                                                        for c in values["dict_trusted"]})}
        for key, value in values.items():
            self.store.set_setting(key, json.dumps(value))
        self.enforce_limits()
        return self.settings

    def optouts(self) -> list[dict[str, str]]:
        return [{"station": s, "cat": c} for s, c in self.store.optouts()]

    def set_optouts(self, items: Any) -> list[dict[str, str]]:
        if not isinstance(items, list):
            raise ListenerError("Liste [{station, cat}] erwartet")
        pairs = []
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("station"), str) \
                    or not isinstance(item.get("cat"), str):
                raise ListenerError("jeder Eintrag braucht station und cat (Text, '*' = alle)")
            station, cat = item["station"].strip().upper() or ALL, item["cat"].strip() or ALL
            if (station, cat) == (ALL, ALL):
                raise ListenerError("alles abwählen ist nicht möglich – dann Modus listener beenden")
            pairs.append((station, cat if cat == ALL else self.cat_key(cat)))
        self.store.set_optouts(pairs)
        return self.optouts()

    def blocked(self, org: str, keys: list[str]) -> bool:
        out = set(self.store.optouts())
        if (org, ALL) in out:
            return True
        return all((org, k) in out or (ALL, k) in out for k in keys)

    # -- rubrics ------------------------------------------------------------

    def cat_key(self, cat: Any) -> str:
        if isinstance(cat, int):
            return str(self.d.enums["cat"].name(cat))
        if cat in self.d.enums["cat"].by_name or cat.startswith(CUSTOM_PREFIX):
            return cat
        return CUSTOM_PREFIX + cat.strip().lower()

    def cat_keys(self, cats: list[Any]) -> list[str]:
        keys = [self.cat_key(c) for c in cats or []]
        return list(dict.fromkeys(keys)) or [GENERAL]

    def cat_name(self, key: str, examples: list[Any] | None = None) -> str:
        entry = self.d.enums["cat"].by_name.get(key)
        if entry:
            return entry.text(self.settings["lang"])
        for c in examples or []:                       # original spelling of own rubric
            if isinstance(c, str) and self.cat_key(c) == key:
                return c
        return key[len(CUSTOM_PREFIX):] if key.startswith(CUSTOM_PREFIX) else key

    def _is_alert(self, page: dict[str, Any]) -> bool:
        return page.get("typ") == "alert" or page.get("pri") == "emergency"

    # -- receive ------------------------------------------------------------

    def on_page(self, page: dict[str, Any], raw: bytes, heard_from: str,
                wire: tuple[int, int] | None = None) -> str:
        """Process one decoded subpage. Returns what happened (for logging/tests).

        wire: (Frames, Bytes) wie die Seite tatsächlich über Funk kam. Im
        Format 2 ist das die Summe der Fragmente – aus den gespeicherten Daten
        wäre sie nicht mehr zu erkennen, denn dort liegt die zusammengesetzte,
        entpackte Seite."""
        now = int(self.clock())
        self.store.heard(heard_from, now)
        org = page.get("org") or heard_from
        self._note_dictionary(page.get("dv"), org, now)
        if page.get("typ") == "dict":               # not a page to read
            part = dicttransfer.part_of(page)
            if part is not None:                    # a part of the packed dictionary
                return self._dict_part(part, org, now)
            newer = self._note_announcement(page, org, now)
            return "dictionary_new" if newer else "dictionary"
        if page.get("typ") == "index":              # the station's rubric list
            return self._index_page(page, org, now)
        page_id, rev = page["id"], page.get("rev", 0)
        lp = self.store.lpage(org, page_id)

        if "withdrawn" in (page.get("flg") or []):
            if lp and lp["rev"] <= rev:
                self.store.delete_lpage(org, page_id)
                return "withdrawn"
            return "ignored"
        if lp and rev < lp["rev"]:
            return "old"
        if lp and lp["deleted_rev"] is not None and rev <= lp["deleted_rev"]:
            return "deleted"
        cats = page.get("cat") or []
        keys = self.cat_keys(cats)
        alert = self._is_alert(page)
        if not alert and self.blocked(org, keys):
            return "blocked"

        sub, total = page.get("sub") or [1, 1]
        typ_entry = self.d.enums["typ"].by_name.get(page.get("typ"))
        stored = self.store.save_received(
            org=org, page_id=page_id, sub=sub, sub_total=total, rev=rev, t=page["t"],
            typ=typ_entry.num if typ_entry else None, data=raw, heard_from=heard_from, now=now)

        newer = lp is None or rev > lp["rev"] or lp["deleted_rev"] is not None
        if newer:
            self.store.drop_older_subpages(org, page_id, rev)
            visible_before = lp is not None and lp["deleted_rev"] is None
            exp = page.get("exp")
            if exp is None and typ_entry:
                exp = typ_entry.spec.get("exp")
            self.store.save_lpage({
                "org": org, "id": page_id, "rev": rev, "t": page["t"],
                "typ": page.get("typ"), "ti": page.get("ti", ""),
                "cats": json.dumps(cats, ensure_ascii=False), "cat_key": keys[0],
                "pri": self.d.enums["pri"].num(page.get("pri", 0)) if isinstance(
                    page.get("pri", 0), (int, str)) else 0,
                "alert": int(alert), "exp_min": exp, "sub_total": total,
                "wire_frames": wire[0] if wire else 0, "wire_bytes": wire[1] if wire else 0,
                "status": "unread", "updated": int(visible_before),
                "favorite": lp["favorite"] if lp else 0, "deleted_rev": None,
                "first_seen": lp["first_seen"] if lp else now, "last_seen": now,
                "search": self._search_text(org, page_id),
            })
            self.enforce_limits()
            return "updated" if visible_before else "new"

        fields: dict[str, Any] = {"last_seen": now}
        if wire:
            fields["wire_frames"], fields["wire_bytes"] = wire
        if stored == "new":                          # a subpage we did not have yet
            fields["search"] = self._search_text(org, page_id)
            fields["sub_total"] = total
            if not lp["ti"] and page.get("ti"):
                fields["ti"] = page["ti"]
        if page["t"] > lp["t"]:                      # station confirmed the page: extend validity
            fields["t"] = page["t"]
        self.store.update_lpage(org, page_id, **fields)
        return "subpage" if stored == "new" else "repeat"

    # -- rubric index of a station -------------------------------------------

    def _index_entries(self, page: dict[str, Any]) -> list[dict[str, Any]]:
        dat = page.get("dat")
        if not isinstance(dat, dict):
            return []
        raw = dat.get(INDEX_DAT_RUBRICS, dat.get(str(INDEX_DAT_RUBRICS), dat.get("rubrics")))
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for entry in raw if isinstance(raw, list) else []:
            if isinstance(entry, (int, str)):
                entry = [entry]
            if not isinstance(entry, list) or not entry or not isinstance(entry[0], (int, str)) \
                    or isinstance(entry[0], bool):
                continue
            cat = entry[0]
            key = self.cat_key(cat)
            if key in seen:
                continue
            seen.add(key)
            descr = entry[1] if len(entry) > 1 and isinstance(entry[1], str) else ""
            out.append({"cat": key, "name": self.cat_name(key, [cat]), "descr": descr[:120]})
            if len(out) >= INDEX_MAX:
                break
        return out

    def _index_page(self, page: dict[str, Any], org: str, now: int) -> str:
        rev = page.get("rev", 0)
        have = self.store.station_rubrics(org)
        if have and rev < have[0]["rev"]:
            return "index_old"
        if "withdrawn" in (page.get("flg") or []):
            self.store.set_station_rubrics(org, [], rev, now)
            return "index" if have else "index_same"
        entries = self._index_entries(page)
        same = [(r["cat"], r["name"], r["descr"]) for r in have] == \
            [(r["cat"], r["name"], r["descr"]) for r in entries]
        if same and have:
            self.store.touch_station_rubrics(org, now)
            return "index_same"
        self.store.set_station_rubrics(org, entries, rev, now)
        self._prune_optouts()
        return "index"

    def declared(self, station: str | None = None) -> dict[str, dict[str, Any]]:
        """Rubrics announced by the stations: key -> {name, desc, stations}."""
        out: dict[str, dict[str, Any]] = {}
        for r in self.store.station_rubrics(station):
            d = out.setdefault(r["cat"], {"key": r["cat"], "name": r["name"],
                                          "desc": "", "stations": []})
            d["stations"].append(r["station"])
            if r["descr"] and not d["desc"]:
                d["desc"] = r["descr"]
        return out

    def _withdrawn_keys(self) -> set[str]:
        """Own rubrics with pages that their station no longer announces."""
        announcing = {r["station"] for r in self.store.station_rubrics()}
        declared = {(r["station"], r["cat"]) for r in self.store.station_rubrics()}
        gone: set[str] = set()
        for p in self.store.lpages():
            if p["org"] not in announcing:
                continue
            for key in self.cat_keys(json.loads(p["cats"])):
                if key.startswith(CUSTOM_PREFIX) and (p["org"], key) not in declared:
                    gone.add(key)
        return gone

    def _prune_optouts(self) -> None:
        """Opt-out lines of own rubrics that nobody announces and no page carries."""
        alive = set(self.declared())
        for p in self.store.lpages():
            alive.update(self.cat_keys(json.loads(p["cats"])))
        for _, key in self.store.optouts():
            if key.startswith(CUSTOM_PREFIX) and key not in alive:
                self.store.delete_optout(key)

    # -- dictionary version -------------------------------------------------

    def _note_dictionary(self, dv: Any, org: str, now: int) -> None:
        """Remember the highest dictionary version heard on the air."""
        if not isinstance(dv, int) or dv <= self.d.version:
            return
        seen = self.dictionary_seen()
        if seen is None or dv > seen["version"]:
            self.store.set_meta("dict_seen", json.dumps(
                {"version": dv, "station": org, "first": now, "last": now}))
        elif dv == seen["version"]:
            seen["last"] = now
            self.store.set_meta("dict_seen", json.dumps(seen))

    def _note_announcement(self, page: dict[str, Any], org: str, now: int) -> bool:
        """typ dict page: which version a station uses and where to get it.
        Returns True if it announces a version newer than the installed one."""
        dat = page.get("dat") if isinstance(page.get("dat"), dict) else {}
        version = dat.get("version")
        if not isinstance(version, int):
            return False
        self._note_dictionary(version, org, now)
        known = self.store.get_meta("dict_announced")
        old = json.loads(known) if known else None
        if old is None or version >= old["version"]:
            hours = dat.get("zint", dat.get(dicttransfer.DAT_INTERVAL))   # by name or number
            self.store.set_meta("dict_announced", json.dumps({
                "version": version, "hash": str(dat.get("hash", "")),
                "source": str(dat.get("source", ""))[:120], "station": org, "time": now,
                # the station also sends the dictionary itself over the air, every n hours
                "air_hours": hours if isinstance(hours, int) and 0 < hours <= 720 else None}))
        return version > self.d.version

    # -- dictionary over the air (spec "Dictionary über Funk") --------------

    def _collections(self) -> dict[str, Any]:
        raw = self.store.get_meta("dict_rx")
        return json.loads(raw) if raw else {}

    def _dict_part(self, part: dict[str, Any], org: str, now: int) -> str:
        if part["version"] <= self.d.version:
            return "dict_current"
        self._note_dictionary(part["version"], org, now)
        cols = self._collections()
        key = f"{part['version']}-{part['hash']}"
        col = cols.get(key)
        if col is None or col["m"] != part["m"] or col["zlen"] != part["zlen"]:
            col = {"version": part["version"], "hash": part["hash"], "station": org,
                   "m": part["m"], "zlen": part["zlen"], "parts": {}, "first": now}
        n = str(part["n"])
        if n in col["parts"]:
            col["last"] = now
            cols[key] = col
            self.store.set_meta("dict_rx", json.dumps(cols))
            return "dict_have"
        col["parts"][n] = base64.b64encode(part["chunk"]).decode("ascii")
        col["last"] = now
        cols[key] = col
        # keep only the newest few transfers
        for old in sorted(cols, key=lambda k: cols[k].get("last", 0))[:-DICT_COLLECTIONS]:
            del cols[old]
        if len(col["parts"]) < col["m"]:
            self.store.set_meta("dict_rx", json.dumps(cols))
            return "dict_part"
        del cols[key]                                   # complete: no longer collecting
        self.store.set_meta("dict_rx", json.dumps(cols))
        return self._dict_complete(col, org, now)

    def _dict_from(self, col: dict[str, Any]) -> Dictionary:
        chunks = [base64.b64decode(col["parts"][str(n)]) for n in range(1, col["m"] + 1)]
        new = dicttransfer.assemble(chunks, col["zlen"], col["version"], col["hash"])
        if new.version <= self.d.version:
            raise dicttransfer.TransferError(f"Version {new.version} ist nicht neuer")
        try:
            dictimport.check(self.d, new)               # only additions allowed
        except dictimport.ImportError_ as exc:
            raise dicttransfer.TransferError(str(exc)) from None
        return new

    def _dict_complete(self, col: dict[str, Any], org: str, now: int) -> str:
        try:
            new = self._dict_from(col)
        except dicttransfer.TransferError as exc:
            log.warning("Dictionary v%s über Funk von %s verworfen: %s", col["version"], org, exc)
            return "dict_bad"
        if org in self.settings["dict_trusted"] and self.install_dictionary:
            try:
                self.install_dictionary(new, org)
            except (OSError, ValueError) as exc:
                log.warning("Dictionary v%s über Funk: Installation fehlgeschlagen: %s",
                            new.version, exc)
                return "dict_bad"
            self.store.set_meta("dict_ready", "")
            return "dict_installed"
        ready = self.dictionary_ready()
        if ready is None or new.version >= ready["version"]:
            self.store.set_meta("dict_ready", json.dumps({**col, "station": org, "time": now}))
        log.info("Dictionary v%s über Funk von %s empfangen – wartet auf Freigabe",
                 new.version, org)
        return "dict_ready"

    def dictionary_ready(self) -> dict[str, Any] | None:
        raw = self.store.get_meta("dict_ready")
        return json.loads(raw) if raw else None

    def install_ready_dictionary(self) -> dict[str, Any]:
        """GUI button: install the complete dictionary received over the air."""
        col = self.dictionary_ready()
        if col is None:
            raise ListenerError("kein über Funk empfangenes Dictionary vorhanden")
        try:
            new = self._dict_from(col)
        except dicttransfer.TransferError as exc:
            self.store.set_meta("dict_ready", "")
            raise ListenerError(f"Dictionary nicht installierbar: {exc}") from None
        if self.install_dictionary is None:
            raise ListenerError("Installation hier nicht möglich")
        try:
            self.install_dictionary(new, col["station"])
        except (OSError, ValueError) as exc:
            raise ListenerError(f"Installation fehlgeschlagen: {exc}") from None
        self.store.set_meta("dict_ready", "")
        return {"installed": True, "version": new.version,
                "message": f"Dictionary Version {new.version} (über Funk von "
                           f"{col['station']}) installiert."}

    def dictionary_seen(self) -> dict[str, Any] | None:
        raw = self.store.get_meta("dict_seen")
        return json.loads(raw) if raw else None

    def dictionary_status(self) -> dict[str, Any]:
        """Local dictionary vs. the newest version heard; outdated -> GUI hint."""
        seen = self.dictionary_seen()
        raw = self.store.get_meta("dict_announced")
        ann = json.loads(raw) if raw else None
        newer = seen is not None and seen["version"] > self.d.version
        source = None
        if newer and ann and ann["version"] >= seen["version"]:
            source = {"text": ann["source"], "station": ann["station"], "hash": ann["hash"],
                      "air_hours": ann.get("air_hours")}
        mismatch = bool(ann and ann["version"] == self.d.version and ann["hash"]
                        and ann["hash"] != self.d.hash4.hex())
        radio = None
        cols = [c for c in self._collections().values() if c["version"] > self.d.version]
        if cols:
            c = max(cols, key=lambda c: (c["version"], len(c["parts"])))
            radio = {"version": c["version"], "station": c["station"],
                     "have": len(c["parts"]), "total": c["m"]}
        ready = self.dictionary_ready()
        if ready and ready["version"] <= self.d.version:
            ready = None
        return {
            "radio": radio,
            "ready": {"version": ready["version"], "station": ready["station"],
                      "received": iso(ready["time"])} if ready else None,
            "local": self.d.version, "hash": self.d.hash4.hex(), "outdated": newer,
            "newest_heard": seen["version"] if newer else self.d.version,
            "heard_from": seen["station"] if newer else None,
            "first_heard": iso(seen["first"]) if newer else None,
            "last_heard": iso(seen["last"]) if newer else None,
            "source": source,
            "hash_mismatch": mismatch,
        }

    def _search_text(self, org: str, page_id: int) -> str:
        words: list[str] = []

        def walk(value: Any) -> None:
            if isinstance(value, str):
                words.append(value)
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                words.append(str(value))
            elif isinstance(value, list):
                for v in value:
                    walk(v)
            elif isinstance(value, dict):
                for v in value.values():
                    walk(v)

        for row in self.store.subpages(org, page_id):
            page = self.codec.decode(row["data"], defaults=False)
            for key in ("ti", "txt", "blk", "dat", "cat", "to", "area"):
                walk(page.get(key))
        words.append(org)
        return " ".join(words).lower()

    # -- housekeeping -------------------------------------------------------

    def housekeeping(self) -> int:
        """Remove expired and too old pages, enforce limits. Returns removed count."""
        now = int(self.clock())
        removed = 0
        max_age = now - self.settings["max_age_days"] * 86400
        for p in self.store.lpages():
            if p["typ"] in ("dict", "index"):   # stored by an older brocastd: not a page
                self.store.delete_lpage(p["org"], p["id"])
                removed += 1
                continue
            if p["favorite"]:
                continue
            expired = p["exp_min"] is not None and p["t"] + p["exp_min"] * 60 < now
            if expired or p["last_seen"] < max_age:
                self.store.delete_lpage(p["org"], p["id"])
                removed += 1
        for p in self.store.lpages_hidden_before(max_age):
            self.store.delete_lpage(p["org"], p["id"])
        self._prune_optouts()
        return removed + self.enforce_limits()

    def enforce_limits(self) -> int:
        s = self.settings
        removed = 0

        def evict(pages: list[dict], limit: int) -> int:
            if len(pages) <= limit:
                return 0
            candidates = sorted((p for p in pages if not p["favorite"]),
                                key=lambda p: (p["status"] == "unread", p["t"]))
            gone = 0
            for p in candidates[:len(pages) - limit]:
                self.store.delete_lpage(p["org"], p["id"])
                gone += 1
            return gone

        by_cat: dict[str, list[dict]] = {}
        for p in self.store.lpages():
            by_cat.setdefault(p["cat_key"], []).append(p)
        for pages in by_cat.values():
            removed += evict(pages, s["max_pages_per_cat"])
        removed += evict(self.store.lpages(), s["max_pages_total"])
        return removed

    # -- queries for the API ------------------------------------------------

    def _summary(self, p: dict) -> dict[str, Any]:
        now = int(self.clock())
        cats = json.loads(p["cats"])
        typ = self.d.enums["typ"].by_name.get(p["typ"])
        present = len(self.store.subpages(p["org"], p["id"]))
        return {
            "org": p["org"], "id": p["id"], "rev": p["rev"], "t": iso(p["t"]),
            "typ": p["typ"], "typ_name": typ.text(self.settings["lang"]) if typ else p["typ"],
            "ti": p["ti"],
            "cats": [{"key": k, "name": self.cat_name(k, cats)} for k in self.cat_keys(cats)],
            "status": p["status"], "updated": bool(p["updated"]),
            "favorite": bool(p["favorite"]), "alert": bool(p["alert"]),
            "pri": self.d.enums["pri"].name(p["pri"]),
            "sub_total": p["sub_total"], "sub_present": present,
            "wire_frames": p["wire_frames"], "wire_bytes": p["wire_bytes"],
            "expired": p["exp_min"] is not None and p["t"] + p["exp_min"] * 60 < now,
        }

    def _filtered(self, cat: str | None = None, station: str | None = None,
                  unread: bool = False, favorite: bool = False,
                  q: str | None = None) -> list[dict]:
        pages = self.store.lpages(order="alert DESC, t DESC")
        out = []
        for p in pages:
            if station and p["org"] != station.upper():
                continue
            if cat and self.cat_key(cat) not in self.cat_keys(json.loads(p["cats"])):
                continue
            if unread and p["status"] != "unread":
                continue
            if favorite and not p["favorite"]:
                continue
            if q and not all(word in p["search"] for word in q.lower().split()):
                continue
            out.append(p)
        return out

    def list_pages(self, **filters: Any) -> list[dict[str, Any]]:
        return [self._summary(p) for p in self._filtered(**filters)]

    def categories(self, station: str | None = None) -> list[dict[str, Any]]:
        """Rubrics with pages, plus the ones the stations announce (also empty)."""
        declared = self.declared(station)
        withdrawn = self._withdrawn_keys()
        groups: dict[str, dict[str, Any]] = {}

        def group(key: str, name: str) -> dict[str, Any]:
            return groups.setdefault(key, {
                "key": key, "name": name, "custom": key.startswith(CUSTOM_PREFIX),
                "desc": declared.get(key, {}).get("desc", ""),
                "declared": key in declared, "withdrawn": key in withdrawn,
                "total": 0, "unread": 0, "alerts": 0})

        for p in self._filtered(station=station):
            cats = json.loads(p["cats"])
            for key in self.cat_keys(cats):
                g = group(key, self.cat_name(key, cats))
                g["total"] += 1
                g["unread"] += p["status"] == "unread"
                g["alerts"] += p["alert"]
        for key, d in declared.items():
            if not self.blocked(d["stations"][0], [key]) or key in groups:
                group(key, d["name"])
        core = {e.name: e.num for e in self.d.enums["cat"].by_num.values()}
        return sorted(groups.values(),
                      key=lambda g: (g["custom"], core.get(g["key"], 999), g["name"].lower()))

    def all_rubrics(self) -> list[dict[str, Any]]:
        """Every rubric for the subscription matrix: dictionary + announced by a
        station + own ones seen in pages + opted out."""
        declared = self.declared()
        withdrawn = self._withdrawn_keys()

        def entry(key: str, name: str, custom: bool) -> dict[str, Any]:
            d = declared.get(key, {})
            return {"key": key, "name": name, "custom": custom, "desc": d.get("desc", ""),
                    "stations": d.get("stations", []), "withdrawn": key in withdrawn}

        out = [entry(e.name, e.text(self.settings["lang"]), False)
               for e in self.d.enums["cat"].by_num.values()]
        seen = {r["key"] for r in out}
        for key, d in declared.items():
            if key not in seen:
                out.append(entry(key, d["name"], True))
                seen.add(key)
        for c in self.categories():
            if c["key"] not in seen:
                out.append(entry(c["key"], c["name"], True))
                seen.add(c["key"])
        for _, key in self.store.optouts():
            if key != ALL and key not in seen:
                out.append(entry(key, self.cat_name(key), True))
                seen.add(key)
        return out

    def stations(self, cat: str | None = None) -> list[dict[str, Any]]:
        out_station = {s for s, c in self.store.optouts() if c == ALL}
        pages = self._filtered(cat=cat)
        result = []
        for s in self.store.stations():
            own = [p for p in pages if p["org"] == s["call"]]
            if cat and not own:
                continue
            result.append({"call": s["call"], "first_heard": iso(s["first_heard"]),
                           "last_heard": iso(s["last_heard"]), "frames": s["frames"],
                           "pages": len(own), "unread": sum(p["status"] == "unread" for p in own),
                           "subscribed": s["call"] not in out_station})
        return sorted(result, key=lambda r: r["last_heard"], reverse=True)

    def page(self, org: str, page_id: int, raw: bool = False,
             mark_read: bool = True) -> dict[str, Any]:
        p = self.store.lpage(org, page_id)
        if p is None or p["deleted_rev"] is not None:
            raise NotFound(f"Seite {org}/{page_id} nicht vorhanden")
        rows = {r["sub"]: r for r in self.store.subpages(org, page_id)}
        decoded = {n: self.codec.decode(r["data"], ax25_src=org) for n, r in rows.items()}
        first = decoded[min(decoded)]
        lang = self.settings["lang"]
        out = self._summary(p)
        out.update({
            "txt": first.get("txt"), "to": first.get("to"), "area": first.get("area"),
            "pos": first.get("pos"), "sym": first.get("sym"), "lnk": first.get("lnk"),
            "ref": first.get("ref"), "src": first.get("src"),
            "exp_min": p["exp_min"], "lang": first.get("lang"),
            "flags": [self._enum_text("flg", f, lang) for f in first.get("flg") or []],
            "pri_name": self._enum_text("pri", out["pri"], lang),
            "blocks": [], "data": [],
        })
        for n in range(1, p["sub_total"] + 1):
            if n not in decoded:
                out["blocks"].append({"k": "missing", "sub": n})
                continue
            for block in decoded[n].get("blk") or []:
                out["blocks"].append(self._block(block, n))
        out["data"] = self._data(first, lang)
        out["dv"] = first.get("dv")
        out["dict_newer"] = isinstance(first.get("dv"), int) and first["dv"] > self.d.version
        # rough time on air of all frames sent back to back (no digipeater path):
        # one TXDELAY, then per frame header byte + AX.25 address/control/pid (16 bytes).
        # Format 2: die echte Funkgröße steht in der Seite (wire_bytes), denn
        # gespeichert ist die entpackte, zusammengesetzte Seite.
        if p["wire_frames"] and p["wire_bytes"]:
            out["airtime_s"] = round(self.txdelay_ms / 1000 + airtime_s(
                p["wire_bytes"], self.baud, 0), 1)
        else:
            frames = [len(r["data"]) + 1 + 16 for r in rows.values()]
            if frames and len(frames) == p["sub_total"]:
                out["airtime_s"] = round(self.txdelay_ms / 1000 + sum(
                    airtime_s(n, self.baud, 0) for n in frames), 1)
        if raw:
            out["raw"] = [{"sub": n, "rev": r["rev"], "bytes": len(r["data"]),
                           "hex": r["data"].hex(), "heard_from": r["heard_from"],
                           "received": iso(r["received_at"]), "decoded": decoded[n]}
                          for n, r in sorted(rows.items())]
        if mark_read and p["status"] == "unread":
            self.store.update_lpage(org, page_id, status="read", updated=0)
        return out

    def _enum_text(self, enum: str, name: Any, lang: str) -> Any:
        entry = self.d.enums[enum].by_name.get(name)
        return entry.text(lang) if entry else name

    def _block(self, block: Any, sub: int) -> dict[str, Any]:
        if not isinstance(block, dict):
            return {"k": "unknown", "sub": sub, "value": block}
        out = {str(k): v for k, v in block.items()}
        out["sub"] = sub
        if "u" in out:
            out["unit"] = self.d.unit_symbol(out["u"])
        if "st" in out:
            out["state"] = self._enum_text("state", out["st"], self.settings["lang"])
        return out

    def _data(self, page: dict[str, Any], lang: str) -> list[dict[str, Any]]:
        dat = page.get("dat")
        if not isinstance(dat, dict):
            return []
        topic = self.d.types.get(page.get("typ"))
        out = []
        for key, value in dat.items():
            entry = topic.by_name.get(key) if topic and isinstance(key, str) else None
            out.append({"key": str(key), "label": entry.text(lang) if entry else str(key),
                        "value": value,
                        "unit": self.d.unit_symbol(entry.spec.get("unit")) if entry else ""})
        return out

    # -- user actions -------------------------------------------------------

    def _existing(self, org: str, page_id: int) -> dict:
        p = self.store.lpage(org, page_id)
        if p is None or p["deleted_rev"] is not None:
            raise NotFound(f"Seite {org}/{page_id} nicht vorhanden")
        return p

    def set_read(self, org: str, page_id: int, read: Any) -> dict[str, Any]:
        self._existing(org, page_id)
        if not isinstance(read, bool):
            raise ListenerError("read: true oder false")
        self.store.update_lpage(org, page_id, status="read" if read else "unread",
                                updated=0 if read else self.store.lpage(org, page_id)["updated"])
        return self._summary(self.store.lpage(org, page_id))

    def set_favorite(self, org: str, page_id: int, favorite: Any) -> dict[str, Any]:
        self._existing(org, page_id)
        if not isinstance(favorite, bool):
            raise ListenerError("favorite: true oder false")
        self.store.update_lpage(org, page_id, favorite=int(favorite))
        return self._summary(self.store.lpage(org, page_id))

    def delete(self, org: str, page_id: int) -> dict[str, Any]:
        """Hide the page until the station sends a newer revision."""
        p = self._existing(org, page_id)
        self.store.update_lpage(org, page_id, deleted_rev=p["rev"], favorite=0)
        self.store.drop_older_subpages(org, page_id, p["rev"] + 1)
        return {"org": org, "id": page_id, "deleted": True, "until_rev": p["rev"] + 1}

    def rxlog(self, limit: int = 200, org: str | None = None, page_id: int | None = None,
              brocast_only: bool = False) -> list[dict[str, Any]]:
        out = []
        for e in self.store.rxlog(limit, org, page_id, brocast_only):
            visible = None
            if e["org"] is not None and e["id"] is not None:
                p = self.store.lpage(e["org"], e["id"])
                visible = bool(p and p["deleted_rev"] is None)
            out.append({
                "time": iso(e["ts"]), "heard_from": e["heard_from"], "dest": e["dest"],
                "org": e["org"], "id": e["id"], "sub": e["sub"], "sub_total": e["sub_total"],
                "rev": e["rev"], "ti": e["ti"], "bytes": e["bytes"], "own": bool(e["own"]),
                "result": e["result"], "text": RESULT_TEXT.get(e["result"], e["result"]),
                "chip": RESULT_CHIP.get(e["result"], (e["result"], "repeat"))[0],
                "kind": RESULT_CHIP.get(e["result"], (e["result"], "repeat"))[1],
                "visible_now": visible,
            })
        return out

    def status(self) -> dict[str, Any]:
        pages = self.store.lpages()
        return {"pages": len(pages), "unread": sum(p["status"] == "unread" for p in pages),
                "alerts": sum(p["alert"] for p in pages if p["status"] == "unread"),
                "stations": len(self.store.stations()),
                "dictionary": self.dictionary_status()}
