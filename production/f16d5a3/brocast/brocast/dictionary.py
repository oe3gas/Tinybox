"""Load the brocast dictionary (YAML) and offer lookups in both directions.

The dictionary gives every number on the air its meaning: name, data type,
unit, scaling, default and display text. Only the numbers are transmitted.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cbor2
import yaml

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "brocast-core.yaml"


class DictionaryError(ValueError):
    """The dictionary file is inconsistent."""


@dataclass(frozen=True)
class Entry:
    """One numbered entry: a key or an enum value."""

    num: int
    name: str
    spec: dict[str, Any]

    def text(self, lang: str = "de") -> str:
        return str(self.spec.get(lang) or self.spec.get("en") or self.spec.get("sym") or self.name)


@dataclass
class Table:
    """Numbers <-> names for one namespace (envelope, blocks, an enum, a topic)."""

    title: str
    by_num: dict[int, Entry] = field(default_factory=dict)
    by_name: dict[str, Entry] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, title: str, mapping: dict[Any, dict[str, Any]]) -> "Table":
        table = cls(title)
        for num, spec in (mapping or {}).items():
            if not isinstance(num, int):
                raise DictionaryError(f"{title}: Key {num!r} ist keine Ganzzahl")
            name = spec.get("name")
            if not name:
                raise DictionaryError(f"{title}: Eintrag {num} hat keinen Namen")
            name = str(name)
            if num in table.by_num or name in table.by_name:
                raise DictionaryError(f"{title}: doppelter Eintrag {num} / {name}")
            entry = Entry(num, name, spec)
            table.by_num[num] = entry
            table.by_name[name] = entry
        return table

    def num(self, value: int | str) -> int:
        """Accept a name or a number, return the number."""
        if isinstance(value, bool):
            raise DictionaryError(f"{self.title}: ungültiger Wert {value!r}")
        if isinstance(value, int):
            return value
        try:
            return self.by_name[value].num
        except KeyError:
            raise DictionaryError(f"{self.title}: unbekannter Name {value!r}") from None

    def name(self, num: int) -> str | int:
        """Return the name for a number, or the number itself if unknown."""
        entry = self.by_num.get(num)
        return entry.name if entry else num


class Dictionary:
    def __init__(self, data: dict[str, Any]):
        self.raw = data
        self.name: str = data.get("dictionary", "?")
        self.version: int = int(data["version"])
        self.envelope = Table.from_mapping("envelope", data["envelope"])
        self.blocks = Table.from_mapping("block_keys", data["block_keys"])
        self.enums = {
            name: Table.from_mapping(f"enum {name}", mapping)
            for name, mapping in (data.get("enums") or {}).items()
        }
        self.types = {
            name: Table.from_mapping(f"type {name}", mapping)
            for name, mapping in (data.get("types") or {}).items()
        }
        self._check()
        # Identifies this exact dictionary: first 4 bytes of SHA-256 over
        # its canonical CBOR form (see spec, section "Versionierung").
        self.hash4 = hashlib.sha256(cbor2.dumps(data, canonical=True)).digest()[:4]

    @classmethod
    def load(cls, path: str | Path = DEFAULT_PATH) -> "Dictionary":
        with open(path, encoding="utf-8") as fh:
            return cls(yaml.safe_load(fh))

    def _check(self) -> None:
        for num in self.envelope.by_num:
            if not 0 <= num <= 23:
                raise DictionaryError(f"Umschlag-Key {num} liegt außerhalb 0..23")
        for num in self.blocks.by_num:
            if not -24 <= num <= -1:
                raise DictionaryError(f"Baustein-Key {num} liegt außerhalb -1..-24")
        for table in (self.envelope, self.blocks, *self.types.values()):
            for entry in table.by_num.values():
                enum = entry.spec.get("enum")
                if enum and enum not in self.enums:
                    raise DictionaryError(f"{table.title}: Enum {enum!r} fehlt")
                unit = entry.spec.get("unit")
                if unit and table is not self.envelope and table is not self.blocks:
                    if unit not in self.enums["unit"].by_name:
                        raise DictionaryError(f"{table.title}: Einheit {unit!r} fehlt")
        for name in self.types:
            if name not in self.enums["typ"].by_name:
                raise DictionaryError(f"Themen-Dictionary {name!r} hat keinen typ")

    def typ_entry(self, typ: int) -> Entry | None:
        return self.enums["typ"].by_num.get(typ)

    def topic(self, typ: int) -> Table | None:
        """The dat-namespace of a page type, if the dictionary defines one."""
        entry = self.typ_entry(typ)
        return self.types.get(entry.name) if entry else None

    def unit_symbol(self, unit_name: str | None) -> str:
        if not unit_name:
            return ""
        entry = self.enums["unit"].by_name.get(unit_name)
        return str(entry.spec.get("sym", unit_name)) if entry else unit_name
