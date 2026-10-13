"""Encode and decode brocast pages.

A page in Python is a dict with readable names, e.g.::

    {"id": 7, "rev": 42, "t": 1790000000, "typ": "wx",
     "pos": [48.12345, 16.12345],
     "dat": {"temp": 12.5, "hum": 65}}

`encode` turns it into compact CBOR with integer keys (deterministic
encoding, RFC 8949 section 4.2). `decode` does the reverse.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import cbor2

from .dictionary import Dictionary, DictionaryError, Table

CALLSIGN = re.compile(r"([A-Z0-9]{1,4}/)?[A-Z0-9]{3,8}(/[A-Z0-9]{1,4})?(-[0-9]{1,2})?")
POS_FACTOR = 100_000          # degrees * 10^5, about 1 m
MAX_UINT = 2**64 - 1
MAX_PAGE_BYTES = 240          # one page = one AX.25 frame (spec: "Seitengröße")


class BrocastError(ValueError):
    """A page is invalid for this dictionary."""


class CriticalKeyError(BrocastError):
    """The page lists a key in crit that this client does not understand."""


# ---------------------------------------------------------------------------
# value converters, keyed by the "type" field of a dictionary entry
# ---------------------------------------------------------------------------

def _uint(value: Any, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_UINT:
        raise BrocastError(f"{what}: nicht-negative Ganzzahl erwartet, nicht {value!r}")
    return value


def _callsign(value: Any, what: str) -> str:
    if not isinstance(value, str) or not CALLSIGN.fullmatch(value):
        raise BrocastError(f"{what}: ungültiges Rufzeichen {value!r}")
    return value


def _time_to_wire(value: Any, what: str) -> int:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise BrocastError(f"{what}: Zeit ohne Zeitzone, bitte UTC angeben")
        return int(value.timestamp())
    return _uint(value, what)


def _pos_to_wire(value: Any, what: str) -> list[int]:
    if not isinstance(value, (list, tuple)) or not 2 <= len(value) <= 4:
        raise BrocastError(f"{what}: [lat, lon, ?Höhe, ?Unschärfe] erwartet")
    lat, lon = float(value[0]), float(value[1])
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise BrocastError(f"{what}: Koordinaten außerhalb des Bereichs")
    out = [round(lat * POS_FACTOR), round(lon * POS_FACTOR)]
    out += [int(round(v)) for v in value[2:]]
    return out


def _pos_from_wire(value: Any) -> Any:
    if isinstance(value, list) and len(value) >= 2 and all(isinstance(v, int) for v in value):
        return [value[0] / POS_FACTOR, value[1] / POS_FACTOR, *value[2:]]
    return value


def _pageref_to_wire(value: Any, what: str) -> list[Any]:
    if not isinstance(value, (list, tuple)) or not 2 <= len(value) <= 3:
        raise BrocastError(f"{what}: [Rufzeichen, id, ?rev] erwartet")
    out = [_callsign(value[0], what), _uint(value[1], what)]
    if len(value) == 3:
        out.append(_uint(value[2], what))
    return out


def _scaled_to_wire(value: Any, spec: dict[str, Any], what: str) -> Any:
    scale = spec.get("scale")
    kind = spec.get("type", "any")
    if scale is not None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise BrocastError(f"{what}: Zahl erwartet, nicht {value!r}")
        value = round(value / 10**scale)
    if kind == "uint":
        return _uint(value, what)
    if kind == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise BrocastError(f"{what}: Ganzzahl erwartet, nicht {value!r}")
    return value


def _scaled_from_wire(value: Any, spec: dict[str, Any]) -> Any:
    scale = spec.get("scale")
    if scale is not None and isinstance(value, int) and not isinstance(value, bool):
        return round(value * 10**scale, max(0, -scale))
    return value


# ---------------------------------------------------------------------------
# encoder
# ---------------------------------------------------------------------------

class Codec:
    def __init__(self, dictionary: Dictionary | None = None):
        self.d = dictionary or Dictionary.load()

    # -- public API ---------------------------------------------------------

    def encode(self, page: dict[str, Any]) -> bytes:
        """Named page -> CBOR bytes (at most MAX_PAGE_BYTES)."""
        data = cbor2.dumps(self.to_wire(page), canonical=True)
        if len(data) > MAX_PAGE_BYTES:
            raise BrocastError(
                f"Seite hat {len(data)} Bytes, erlaubt sind {MAX_PAGE_BYTES}; "
                "lange Inhalte in Unterseiten (sub) teilen")
        return data

    def decode(self, data: bytes, ax25_src: str | None = None,
               defaults: bool = True) -> dict[str, Any]:
        """CBOR bytes -> named page. ax25_src fills a missing org."""
        try:
            wire = cbor2.loads(data)
        except Exception as exc:  # cbor2 raises several types
            raise BrocastError(f"kein gültiges CBOR: {exc}") from exc
        return self.from_wire(wire, ax25_src=ax25_src, defaults=defaults)

    # -- named -> wire ------------------------------------------------------

    def to_wire(self, page: dict[str, Any]) -> dict[int, Any]:
        env = self.d.envelope
        page = dict(page)
        page.setdefault("dv", self.d.version)
        out: dict[int, Any] = {}

        typ_num = self._enum("typ", page.get("typ"), "typ") if "typ" in page else None

        for key, value in page.items():
            if isinstance(key, int):          # raw extension key, passed through
                out[key] = value
                continue
            entry = env.by_name.get(key)
            if entry is None:
                raise BrocastError(f"unbekanntes Umschlag-Feld {key!r}")
            if key == "dat":
                out[entry.num] = self._dat_to_wire(value, typ_num)
            else:
                out[entry.num] = self._value_to_wire(value, entry.spec, key)

        for entry in env.by_num.values():
            if entry.spec.get("required") and entry.num not in out:
                raise BrocastError(f"Pflichtfeld {entry.name!r} fehlt")
        return out

    def _enum(self, enum: str, value: Any, what: str) -> int:
        try:
            return self.d.enums[enum].num(value)
        except DictionaryError as exc:
            raise BrocastError(f"{what}: {exc}") from None

    def _enum_or_text(self, spec: dict[str, Any], value: Any, what: str) -> int | str:
        """Dictionary name/number, or free text where the entry allows it (cat)."""
        table = self.d.enums[spec["enum"]]
        limit = spec.get("free_text")
        if limit and isinstance(value, str) and value not in table.by_name:
            text = value.strip()
            if not 1 <= len(text) <= limit:
                raise BrocastError(f"{what}: eigener Name muss 1..{limit} Zeichen haben")
            return text
        return self._enum(spec["enum"], value, what)

    def _value_to_wire(self, value: Any, spec: dict[str, Any], what: str) -> Any:
        kind = spec.get("type", "any")
        if kind == "uint":
            return _uint(value, what)
        if kind == "int":
            if isinstance(value, bool) or not isinstance(value, int):
                raise BrocastError(f"{what}: Ganzzahl erwartet")
            return value
        if kind == "tstr":
            if not isinstance(value, str):
                raise BrocastError(f"{what}: Text erwartet")
            if "max" in spec and len(value) > spec["max"]:
                raise BrocastError(f"{what}: länger als {spec['max']} Zeichen")
            return value
        if kind == "callsign":
            return _callsign(value, what)
        if kind == "time":
            return _time_to_wire(value, what)
        if kind == "enum":
            return self._enum(spec["enum"], value, what)
        if kind == "enums":
            return [self._enum_or_text(spec, v, what) for v in value]
        if kind == "subpage":
            if (not isinstance(value, (list, tuple)) or len(value) != 2
                    or not all(isinstance(v, int) and not isinstance(v, bool) for v in value)
                    or not 1 <= value[0] <= value[1]):
                raise BrocastError(f"{what}: [n, gesamt] mit 1 <= n <= gesamt erwartet")
            return list(value)
        if kind == "bits":
            if isinstance(value, int) and not isinstance(value, bool):
                return _uint(value, what)
            bits = 0
            for name in value:
                bits |= 1 << self._enum(spec["enum"], name, what)
            return bits
        if kind == "position":
            return _pos_to_wire(value, what)
        if kind == "pageref":
            return _pageref_to_wire(value, what)
        if kind == "pagerefs":
            return [_pageref_to_wire(v, what) for v in value]
        if kind == "blocks":
            return [self._block_to_wire(b, f"{what}[{i}]") for i, b in enumerate(value)]
        return value  # any

    def _block_to_wire(self, block: dict[str, Any], what: str) -> dict[int, Any]:
        out: dict[int, Any] = {}
        for key, value in block.items():
            if isinstance(key, int):
                out[key] = value
                continue
            entry = self.d.blocks.by_name.get(key)
            if entry is None:
                raise BrocastError(f"{what}: unbekannter Baustein-Key {key!r}")
            out[entry.num] = self._value_to_wire(value, entry.spec, f"{what}.{key}")
        return out

    def _dat_to_wire(self, dat: dict[Any, Any], typ_num: int | None) -> dict[int, Any]:
        topic = self.d.topic(typ_num) if typ_num is not None else None
        out: dict[int, Any] = {}
        for key, value in dat.items():
            if isinstance(key, int):
                out[key] = value
                continue
            entry = topic.by_name.get(key) if topic else None
            if entry is None:
                raise BrocastError(f"dat: Feld {key!r} ist für diesen typ nicht definiert")
            out[entry.num] = _scaled_to_wire(value, entry.spec, f"dat.{key}")
        return out

    # -- wire -> named ------------------------------------------------------

    def from_wire(self, wire: Any, ax25_src: str | None = None,
                  defaults: bool = True) -> dict[str, Any]:
        if not isinstance(wire, dict):
            raise BrocastError("Seite ist keine CBOR-Map")
        env = self.d.envelope

        crit = wire.get(env.by_name["crit"].num, [])
        for key in crit if isinstance(crit, list) else []:
            if key not in env.by_num:
                raise CriticalKeyError(f"Seite verlangt unbekannten Key {key}")

        typ_num = wire.get(env.by_name["typ"].num)
        page: dict[Any, Any] = {}
        for num, value in wire.items():
            entry = env.by_num.get(num)
            if entry is None:
                page[num] = value              # unknown key, kept raw
            elif entry.name == "dat":
                page["dat"] = self._dat_from_wire(value, typ_num)
            else:
                page[entry.name] = self._value_from_wire(value, entry.spec)

        for entry in env.by_num.values():
            if entry.spec.get("required") and entry.name not in page:
                raise BrocastError(f"Pflichtfeld {entry.name!r} fehlt")

        if defaults:
            self._apply_defaults(page, typ_num, ax25_src)
        return page

    def _value_from_wire(self, value: Any, spec: dict[str, Any]) -> Any:
        kind = spec.get("type", "any")
        if kind == "enum":
            return self.d.enums[spec["enum"]].name(value)
        if kind == "enums" and isinstance(value, list):
            return [self.d.enums[spec["enum"]].name(v) for v in value]
        if kind == "bits" and isinstance(value, int):
            table = self.d.enums[spec["enum"]]
            return [table.name(bit) for bit in range(value.bit_length()) if value >> bit & 1]
        if kind == "position":
            return _pos_from_wire(value)
        if kind == "blocks" and isinstance(value, list):
            return [self._block_from_wire(b) for b in value]
        return value

    def _block_from_wire(self, block: Any) -> Any:
        if not isinstance(block, dict):
            return block
        out: dict[Any, Any] = {}
        for num, value in block.items():
            entry = self.d.blocks.by_num.get(num)
            if entry is None:
                out[num] = value
            else:
                out[entry.name] = self._value_from_wire(value, entry.spec)
        return out

    def _dat_from_wire(self, dat: Any, typ_num: Any) -> Any:
        topic = self.d.topic(typ_num) if isinstance(typ_num, int) else None
        if not isinstance(dat, dict) or topic is None:
            return dat
        out: dict[Any, Any] = {}
        for num, value in dat.items():
            entry = topic.by_num.get(num)
            if entry is None:
                out[num] = value
            else:
                out[entry.name] = _scaled_from_wire(value, entry.spec)
        return out

    def _apply_defaults(self, page: dict[Any, Any], typ_num: Any,
                        ax25_src: str | None) -> None:
        typ_spec = {}
        if isinstance(typ_num, int) and (entry := self.d.typ_entry(typ_num)):
            typ_spec = entry.spec
        for entry in self.d.envelope.by_num.values():
            if entry.name in page or "default" not in entry.spec:
                continue
            default = entry.spec["default"]
            if default == "@ax25_src":
                if ax25_src:
                    page[entry.name] = ax25_src
            elif default == "@typ":
                if entry.name in typ_spec:
                    page[entry.name] = typ_spec[entry.name]
            else:
                page[entry.name] = self._value_from_wire(default, entry.spec)

    # -- display ------------------------------------------------------------

    def describe(self, page: dict[Any, Any], lang: str = "de") -> list[str]:
        """Human-readable lines using the dictionary's long texts."""
        env = self.d.envelope
        lines: list[str] = []
        typ_entry = self.d.enums["typ"].by_name.get(page.get("typ"))
        topic = self.d.types.get(typ_entry.name) if typ_entry else None

        for entry in env.by_num.values():
            if entry.name not in page or entry.name in ("dat", "blk"):
                continue
            value = page[entry.name]
            if value == []:
                continue
            if entry.name == "flg":
                table = self.d.enums["flg"]
                value = ", ".join(table.by_name[v].text(lang) if v in table.by_name else str(v)
                                  for v in value)
            elif entry.name == "sub" and isinstance(value, list) and len(value) == 2:
                value = f"{value[0]}/{value[1]}"
            elif entry.name == "cat" and isinstance(value, list):
                table = self.d.enums["cat"]
                value = ", ".join(table.by_name[v].text(lang) if v in table.by_name
                                  else f"{v} (eigene)" for v in value)
            elif entry.name == "t" and isinstance(value, int):
                value = datetime.fromtimestamp(value, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            elif entry.spec.get("type") == "enum":
                enum = self.d.enums[entry.spec["enum"]].by_name.get(value)
                value = enum.text(lang) if enum else value
            elif entry.name == "pos" and isinstance(value, list):
                value = f"{value[0]:.5f}° {'N' if value[0] >= 0 else 'S'}, " \
                        f"{value[1]:.5f}° {'E' if value[1] >= 0 else 'W'}"
            unit = f" {entry.spec['unit']}" if entry.spec.get("unit") else ""
            lines.append(f"{entry.text(lang)}: {value}{unit}")

        dat = page.get("dat")
        if isinstance(dat, dict):
            for key, value in dat.items():
                entry = topic.by_name.get(key) if topic and isinstance(key, str) else None
                if entry is None:
                    lines.append(f"  [{key}]: {value}")
                    continue
                unit = self.d.unit_symbol(entry.spec.get("unit"))
                lines.append(f"  {entry.text(lang)}: {value}{' ' + unit if unit else ''}")

        for block in page.get("blk") or []:
            lines.extend(self._describe_block(block, lang))
        for key, value in page.items():
            if isinstance(key, int):
                lines.append(f"[unbekannt {key}]: {value!r}")
        return lines

    def _describe_block(self, block: Any, lang: str) -> list[str]:
        if not isinstance(block, dict):
            return [f"  {block!r}"]
        kind = block.get("k")
        text = block.get("x", "")
        if kind == "heading":
            return ["", f"## {text}"]
        if kind == "sep":
            return ["-" * 40]
        if kind == "list":
            return [f"  • {row}" for row in block.get("rows", [])]
        if kind == "value":
            unit = self.d.unit_symbol(block.get("u"))
            state = f" [{block['st']}]" if block.get("st") not in (None, "ok") else ""
            return [f"  {block.get('n', '')}: {block.get('v')}{' ' + unit if unit else ''}{state}"]
        if kind == "link":
            href = block.get("href", [])
            return [f"  → {text} ({'/'.join(str(x) for x in href)})"]
        if kind == "note":
            return [f"  ! {text}"]
        if kind == "table":
            sc = block.get("sc")

            def zelle(c):      # sc skaliert alle Zahlenzellen (wie bei series)
                if isinstance(c, (int, float)) and not isinstance(c, bool) and isinstance(sc, int):
                    return f"{c * 10 ** sc:g}"
                return "-" if c is None else str(c)
            rows = [block.get("hdr", [])] + list(block.get("rows", []))
            return ["  " + " | ".join(zelle(c) for c in row) for row in rows if row]
        return [f"  {text}" if text else f"  {block}"]
