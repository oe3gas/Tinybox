"""Import a dictionary that was fetched as text, e.g. with TinyBox's DICT command.

The text may be a whole terminal capture (prompts, welcome text, CR/LF):
only the part between the marker lines counts.

    #BROCAST-DICT BEGIN v2 lines=212 sha256=<64 hex>
    ...YAML...
    #BROCAST-DICT END

Checks before anything is installed:
  1. markers found, line count and SHA-256 match (transfer intact)
  2. the YAML is a valid dictionary
  3. it is newer than the installed one
  4. it only adds entries: every number keeps its name (spec rule
     "eine vergebene Nummer wird nie umgedeutet")
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .dictionary import Dictionary, DictionaryError, Table

BEGIN_RE = re.compile(r"#BROCAST-DICT BEGIN v(\d+) lines=(\d+) sha256=([0-9a-f]{64})")
END_MARK = "#BROCAST-DICT END"


class ImportError_(ValueError):
    """The text cannot be imported (message is shown to the user)."""


@dataclass
class ImportResult:
    ok: bool
    message: str
    installed: bool = False
    old_version: int | None = None
    new_version: int | None = None
    added: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "message": self.message, "installed": self.installed,
                "old_version": self.old_version, "new_version": self.new_version,
                "added": self.added}


def text_from_request(body: Any) -> str:
    """Body {"text": ...} (pasted) or {"data_b64": ...} (uploaded file, any encoding)."""
    if not isinstance(body, dict):
        raise ImportError_("Objekt mit 'text' oder 'data_b64' erwartet")
    if isinstance(body.get("text"), str):
        return body["text"]
    if isinstance(body.get("data_b64"), str):
        try:
            raw = base64.b64decode(body["data_b64"], validate=True)
        except (binascii.Error, ValueError):
            raise ImportError_("Datei konnte nicht gelesen werden (base64)") from None
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin-1")     # old terminals; the payload itself is ASCII
    raise ImportError_("Objekt mit 'text' oder 'data_b64' erwartet")


def extract(text: str) -> tuple[int, list[str]]:
    """-> (announced version, payload lines). Raises ImportError_ on any mismatch."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    begin = None
    for i, line in enumerate(lines):
        m = BEGIN_RE.search(line)
        if m:
            begin, version, count, sha = i, int(m.group(1)), int(m.group(2)), m.group(3)
    if begin is None:
        raise ImportError_("Startmarke #BROCAST-DICT BEGIN nicht gefunden – "
                           "ist das der Mitschnitt des DICT-Befehls?")
    end = next((i for i in range(begin + 1, len(lines)) if END_MARK in lines[i]), None)
    if end is None:
        raise ImportError_("Endmarke #BROCAST-DICT END fehlt – die Übertragung ist unvollständig")
    payload = [l.rstrip() for l in lines[begin + 1:end] if l.strip()]
    if len(payload) != count:
        raise ImportError_(f"{len(payload)} statt {count} Zeilen empfangen – bitte DICT erneut abrufen")
    if hashlib.sha256("\n".join(payload).encode("utf-8")).hexdigest() != sha:
        raise ImportError_("Prüfsumme stimmt nicht – Text wurde bei der Übertragung verändert")
    return version, payload


def _compare(old: Table, new: Table | None, where: str, added: dict[str, int]) -> None:
    if new is None:
        raise ImportError_(f"{where} fehlt im neuen Dictionary")
    for num, entry in old.by_num.items():
        other = new.by_num.get(num)
        if other is None or other.name != entry.name:
            raise ImportError_(f"{where}: Nummer {num} ({entry.name}) würde umgedeutet oder "
                               "entfernt – das ist nicht erlaubt")
        old_cols = entry.spec.get("cols")
        if isinstance(old_cols, list):          # rows (ab v4): Spalten nur hinten anhängen
            new_cols = other.spec.get("cols") or []
            if [c.get("name") for c in new_cols[:len(old_cols)]] != [c.get("name") for c in old_cols]:
                raise ImportError_(f"{where}: Spalten von {entry.name} würden umgestellt – "
                                   "neue Spalten nur am Ende")
    extra = len(new.by_num) - len(old.by_num)
    if extra:
        added[where] = extra


def check(old: Dictionary, new: Dictionary) -> dict[str, int]:
    """Only additions allowed. Returns the number of new entries per table."""
    added: dict[str, int] = {}
    _compare(old.envelope, new.envelope, "Umschlag", added)
    _compare(old.blocks, new.blocks, "Bausteine", added)
    for name, table in old.enums.items():
        _compare(table, new.enums.get(name), f"Liste {name}", added)
    for name, table in old.types.items():
        _compare(table, new.types.get(name), f"Thema {name}", added)
    for name, table in new.enums.items():
        if name not in old.enums:
            added[f"Liste {name}"] = len(table.by_num)
    for name, table in new.types.items():
        if name not in old.types:
            added[f"Thema {name}"] = len(table.by_num)
    return added


def run(text: str, current: Dictionary, target: Path, dry_run: bool = False) -> ImportResult:
    version, payload = extract(text)
    try:
        data = yaml.safe_load("\n".join(payload))
        new = Dictionary(data)
    except (yaml.YAMLError, DictionaryError, KeyError, TypeError, ValueError) as exc:
        raise ImportError_(f"kein gültiges Dictionary: {exc}") from None
    if new.version != version:
        raise ImportError_(f"Startmarke nennt v{version}, der Inhalt ist v{new.version}")
    result = ImportResult(ok=True, message="", old_version=current.version,
                          new_version=new.version)
    if new.version == current.version and new.hash4 == current.hash4:
        result.message = f"Version {new.version} ist bereits installiert."
        return result
    if new.version <= current.version:
        raise ImportError_(f"Version {new.version} ist nicht neuer als die installierte "
                           f"Version {current.version}")
    result.added = check(current, new)
    n = sum(result.added.values())
    entries = f"{n} neuer Eintrag" if n == 1 else f"{n} neue Einträge"
    if dry_run:
        result.message = (f"Prüfung erfolgreich: Version {current.version} → {new.version}, "
                          f"{entries}. Noch nicht installiert.")
        return result
    install("\n".join(payload) + "\n", target, current.version)
    result.installed = True
    result.message = f"Dictionary Version {new.version} installiert ({entries})."
    return result


def install(text: str, target: Path, old_version: int) -> None:
    """Write atomically, keep the previous file as <name>.v<old>.bak.yaml."""
    target = Path(target)
    tmp = target.with_name(target.name + ".new")
    tmp.write_text(text, encoding="utf-8")
    if target.exists():
        backup = target.with_name(f"{target.stem}.v{old_version}.bak{target.suffix}")
        if backup.exists():
            backup.unlink()
        os.replace(target, backup)
    os.replace(tmp, target)
