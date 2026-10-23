"""Club Log DXCC Most Wanted list: how rare a DXCC entity is, and the relevance score.

Club Log ranks all 340 DXCC entities by how rarely they appear in the logs its
users upload (rank 1 = most wanted). The list is fetched as JSON from
mostwanted.php?api=1 and kept as a file next to cty.dat (refreshed like it).
Accepted shapes, so a change on the Club Log side does not break the digest:

    {"1": "P5", "2": "3Y/B", ...}      rank -> prefix (the Club Log API)
    {"P5": 1, "3Y/B": 2, ...}          prefix -> rank
    ["P5", "3Y/B", ...]                list in rank order

Entities are matched by their primary prefix (cty.dat uses the same ones,
compared in upper case). A missing list or an unknown entity gets
UNKNOWN_RANK - the middle of the list - so the digest still works, just
without the rarity weighting.

Relevance (PLANUNG.md section 16a):
    rarity = 1 + 9 * ((341 - rank) / 340) ** 2       1 (common) ... 10 (rank 1)
    score  = rarity * log2(1 + spotters)
Rarity beats the number of spotters: 5 spotters for Bouvet (rank ~2) give
about 26, 10 spotters for Argentina (rank ~330) about 3.5.
"""

from __future__ import annotations

import json
import logging
import math
import ssl
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_URL = "https://clublog.org/mostwanted.php?api=1"
ENTITIES = 340
UNKNOWN_RANK = 170
TIERS = ("A", "B", "C")


class MostWantedError(Exception):
    pass


def parse(text: str) -> dict[str, int]:
    """JSON text -> {PREFIX: rank}. Raises MostWantedError if it is not a list."""
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise MostWantedError(f"most wanted list: no JSON ({exc})") from None
    out: dict[str, int] = {}
    if isinstance(data, list):
        items = [(i + 1, p) for i, p in enumerate(data)]
    elif isinstance(data, dict):
        items = []
        for k, v in data.items():
            if str(k).strip().isdigit() and isinstance(v, str):
                items.append((int(k), v))                    # rank -> prefix
            elif isinstance(v, int) or (isinstance(v, str) and v.strip().isdigit()):
                items.append((int(v), str(k)))               # prefix -> rank
    else:
        items = []
    for rank, prefix in items:
        prefix = str(prefix).strip().upper()
        if prefix and 1 <= rank <= 1000 and prefix not in out:
            out[prefix] = rank
    if len(out) < 100:
        raise MostWantedError(f"most wanted list: only {len(out)} entities")
    return out


class MostWanted:
    def __init__(self, ranks: dict[str, int], source: str = "") -> None:
        self.ranks = ranks
        self.source = source

    def __len__(self) -> int:
        return len(self.ranks)

    def rank(self, prefix: str) -> int | None:
        return self.ranks.get(prefix.upper()) if prefix else None

    @classmethod
    def load(cls, path: str | Path) -> MostWanted:
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            raise MostWantedError(f"most wanted list not readable: {exc}") from None
        return cls(parse(text), str(path))


def load_or_none(path: str | Path) -> MostWanted | None:
    try:
        return MostWanted.load(path)
    except MostWantedError as exc:
        log.info("%s - relevance without rarity (all entities rank %d)", exc, UNKNOWN_RANK)
        return None


def download(target: str | Path, url: str = DEFAULT_URL, *, verify_ssl: bool = True,
             timeout: int = 30) -> Path:
    """Fetch the list, check that it parses, then replace the old file."""
    target = Path(target)
    ctx = ssl.create_default_context()
    if not verify_ssl:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": "TinyBox dxfeed"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        data = resp.read(500_000)
    n = len(parse(data.decode("utf-8", "replace")))        # raises if broken
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(target)
    log.info("most wanted list updated from %s (%d entities)", url, n)
    return target


# ---------------------------------------------------------------------------
# relevance
# ---------------------------------------------------------------------------

def rarity(rank: int | None) -> float:
    """1.0 (rank 340, every day on the air) ... 10.0 (rank 1)."""
    r = UNKNOWN_RANK if rank is None else min(ENTITIES, max(1, rank))
    return 1 + 9 * ((ENTITIES + 1 - r) / ENTITIES) ** 2


def score(rank: int | None, spotters: int) -> float:
    return rarity(rank) * math.log2(1 + max(0, spotters))


def tier(value: float, a: float, b: float) -> str:
    return "A" if value >= a else "B" if value >= b else "C"
