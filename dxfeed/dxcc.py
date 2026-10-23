"""The DXCC list of the brocast dictionary (enums.dxcc, from version 4).

dxfeed finds the DX entity in AD1C's cty.dat (primary prefix and name). The
dictionary gives it the ADIF DXCC number for the brocast page, and the Club
Log prefix for the Most Wanted rank where Club Log writes it differently
(1A0 for 1A, IS0 for IS, KL7 for KL ...).

The dictionary is the one source: brocast/brocast-core.yaml in this repo
(built by brocast/tools/build_dxcc.py). It needs PyYAML, which brocastd needs
anyway. Without it dxfeed still works: the page carries the entity name as
text and the Most Wanted rank is looked up by the AD1C prefix.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "brocast" / "brocast-core.yaml"


@dataclass(frozen=True)
class Dxcc:
    code: int           # ADIF DXCC number
    prefix: str         # AD1C primary prefix (dictionary name)
    name: str
    cont: str
    clublog: str        # Club Log prefix (Most Wanted list)


class DxccList:
    def __init__(self, entries: list[Dxcc], version: int = 0) -> None:
        self.version = version
        self.by_prefix = {e.prefix: e for e in entries}
        self.by_name = {e.name.lower(): e for e in entries}

    def __len__(self) -> int:
        return len(self.by_prefix)

    def find(self, prefix: str, name: str = "") -> Dxcc | None:
        """By the AD1C primary prefix, else by the entity name (same spelling as cty.dat)."""
        return self.by_prefix.get(prefix.upper()) or self.by_name.get(name.lower())

    @classmethod
    def from_mapping(cls, data: dict) -> DxccList:
        entries = []
        for code, spec in ((data.get("enums") or {}).get("dxcc") or {}).items():
            if not isinstance(code, int) or not isinstance(spec, dict) or spec.get("del"):
                continue
            prefix = str(spec.get("name", "")).upper()
            entries.append(Dxcc(code=code, prefix=prefix, name=str(spec.get("en", prefix)),
                                cont=str(spec.get("cont", "")),
                                clublog=str(spec.get("cl", prefix)).upper()))
        return cls(entries, int(data.get("version") or 0))


def load_or_none(path: str | Path = DEFAULT_PATH) -> DxccList | None:
    try:
        import yaml
    except ImportError:
        log.info("PyYAML missing - brocast page without DXCC numbers")
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            lst = DxccList.from_mapping(yaml.safe_load(fh) or {})
    except (OSError, ValueError, yaml.YAMLError) as exc:
        log.warning("brocast dictionary %s not readable: %s", path, exc)
        return None
    if not lst:
        log.info("brocast dictionary %s has no DXCC list (version < 4)", path)
        return None
    return lst
