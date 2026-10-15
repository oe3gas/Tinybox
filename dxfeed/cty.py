"""AD1C country file (cty.dat): call -> DXCC entity and continent.

Format (https://www.country-files.com, file cty.dat):

    Austria:                  15:  28:  EU:   47.33:   -13.33:    -1.0:  OE:
        OE,=OE2017A,=4U1A(14)[28];

A header line (8 fields separated by ':') and alias lines up to ';'. An alias
"=CALL" is a full call, anything else a prefix. Overrides in brackets after an
alias: (CQ zone) [ITU zone] <lat/lon> {continent} ~time zone~ - only the
continent is used here. Entities whose primary prefix starts with '*' are DARC
WAE entries (Sicily, Shetland ...), not DXCC; they are skipped so that their
calls fall back to the DXCC entity (IT9 -> Italy).
"""

from __future__ import annotations

import logging
import re
import ssl
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_URL = "https://www.country-files.com/cty/cty.dat"
_OVERRIDE_RE = re.compile(r"\(\d+\)|\[\d+\]|<[^>]*>|\{[A-Z]{2}\}|~[^~]*~")
_CONT_RE = re.compile(r"\{([A-Z]{2})\}")

# portable suffixes that do not change the entity
_SUFFIXES = {"P", "M", "QRP", "A", "B", "AM", "J", "LH", "R", "T", "N"}


@dataclass(frozen=True)
class Entity:
    name: str
    prefix: str         # primary prefix, e.g. OE, VP8, UA9
    cont: str           # EU, AS, AF, NA, SA, OC, AN


class CtyError(Exception):
    pass


class Cty:
    def __init__(self) -> None:
        self.prefixes: dict[str, tuple[Entity, str]] = {}   # prefix -> (entity, continent)
        self.calls: dict[str, tuple[Entity, str]] = {}      # =CALL -> (entity, continent)
        self.max_len = 0
        self.version = ""

    def __len__(self) -> int:
        return len({e.prefix for e, _ in self.prefixes.values()})

    # --- loading -----------------------------------------------------------

    @classmethod
    def from_text(cls, text: str) -> Cty:
        cty = cls()
        for block in text.split(";"):
            block = block.strip()
            if not block:
                continue
            head, _, rest = block.partition("\n")
            fields = [f.strip() for f in head.split(":")]
            if len(fields) < 8:
                continue
            name, cont, prefix = fields[0], fields[3].upper(), fields[7].upper()
            if prefix.startswith("*"):
                continue                                    # WAE only, not DXCC
            ent = Entity(name=name, prefix=prefix, cont=cont)
            aliases = [a.strip() for a in rest.replace("\n", " ").split(",") if a.strip()]
            for alias in aliases + [prefix]:
                m = _CONT_RE.search(alias)
                acont = m.group(1) if m else cont
                key = _OVERRIDE_RE.sub("", alias).strip().upper()
                if not key:
                    continue
                if key.startswith("="):
                    cty.calls[key[1:]] = (ent, acont)
                else:
                    cty.prefixes.setdefault(key, (ent, acont))
                    cty.max_len = max(cty.max_len, len(key))
                if key.startswith("=VERSION"):
                    cty.version = key[1:]
        if not cty.prefixes:
            raise CtyError("cty.dat: no entities found")
        return cty

    @classmethod
    def load(cls, path: str | Path) -> Cty:
        try:
            text = Path(path).read_text(encoding="latin-1")
        except OSError as exc:
            raise CtyError(f"cty.dat not readable: {exc}") from None
        return cls.from_text(text)

    # --- lookup ------------------------------------------------------------

    def lookup(self, call: str) -> tuple[Entity, str] | None:
        """(entity, continent) or None (unknown, maritime mobile ...)."""
        call = call.upper().strip()
        if call in self.calls:
            return self.calls[call]
        base = self._prefix_part(call)
        if base is None:
            return None
        if base in self.calls:
            return self.calls[base]
        for n in range(min(len(base), self.max_len), 0, -1):
            hit = self.prefixes.get(base[:n])
            if hit:
                return hit
        return None

    @staticmethod
    def _prefix_part(call: str) -> str | None:
        """The part of a call that decides the entity.
        OE3GAS/P -> OE3GAS, VP8/G3ABC -> VP8, G3ABC/VP8 -> VP8, X/MM -> None."""
        parts = [p for p in call.split("/") if p]
        if not parts:
            return None
        if any(p in ("MM", "AM") for p in parts[1:]):
            return None                          # maritime / aeronautical mobile
        parts = [p for i, p in enumerate(parts)
                 if i == 0 or (p not in _SUFFIXES and not p.isdigit())]
        if len(parts) == 1:
            return parts[0]
        # two remaining parts: the shorter one is the prefix (VP8/G3ABC, G3ABC/VP8)
        a, b = parts[0], parts[1]
        return a if len(a) <= len(b) else b


def download(target: str | Path, url: str = DEFAULT_URL, *, verify_ssl: bool = True,
             timeout: int = 30) -> Path:
    """Fetch cty.dat, check that it parses, then replace the old file."""
    target = Path(target)
    ctx = ssl.create_default_context()
    if not verify_ssl:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": "TinyBox dxfeed"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        data = resp.read(2_000_000)
    Cty.from_text(data.decode("latin-1"))            # raises CtyError if broken
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(target)
    log.info("cty.dat updated from %s (%d bytes)", url, len(data))
    return target


def is_stale(path: str | Path, max_age_days: int) -> bool:
    try:
        return time.time() - Path(path).stat().st_mtime > max_age_days * 86400
    except OSError:
        return True
