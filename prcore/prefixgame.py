"""Prefix raten (CR123, PLANUNG 31): the rules, for the box (and tests).

The game list prefixraten.csv (next to this file) has one row per DXCC entity
with a unique prefix: display text, pattern for the calls, IARU region, the
stages it belongs to. A round takes the entities of the chosen stage and
regions; with fewer than MIN_POOL it fills up from the next weaker stage
(DX-God -> Pro -> OM -> Newcomer), the rarest first, only up to MIN_POOL. If
even that is not enough, the round plays with fewer - the box says how many.

Pattern: letters/digits fixed, [A-R] / [1-57] one character of the class,
# a digit 0-9; several patterns separated by commas (one is picked). A suffix
of 1-3 random letters follows.
"""

from __future__ import annotations

import csv
import random
import re
from dataclasses import dataclass
from pathlib import Path

DATA_FILE = Path(__file__).with_name("prefixraten.csv")
MIN_POOL = 50

STAGES = ("NC", "OM", "PRO", "GOD")                 # weakest first
STAGE_NAME = {"NC": "Newcomer", "OM": "OM", "PRO": "Pro", "GOD": "DX-God"}
_STAGE_ALIAS = {"NC": "NC", "NEWCOMER": "NC", "OM": "OM", "PRO": "PRO",
                "GOD": "GOD", "DXGOD": "GOD", "DX-GOD": "GOD"}
# rarity order of the rank ranges (deleted entities count as the rarest)
_RARITY = {"geloescht": 0, "1-34": 1, "35-68": 2, "69-102": 3, "103-204": 4, "205-340": 5}


@dataclass(frozen=True)
class Entity:
    dxcc: int
    name: str              # shown as answer A/B/C
    patterns: tuple[str, ...]
    region: str            # "1", "2", "3"
    stages: frozenset[str]
    rarity: int


def stage_of(word: str) -> str | None:
    return _STAGE_ALIAS.get(word.strip().upper())


def load(path: Path | str = DATA_FILE) -> list[Entity]:
    names = {v: k for k, v in STAGE_NAME.items()}
    out = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            pats = tuple(p.strip() for p in r["muster"].split(",") if p.strip())
            stages = frozenset(names[x.strip()] for x in r["stufen"].split(",")
                               if x.strip() in names)
            if not pats or not stages or r["iaru"] not in ("1", "2", "3"):
                continue
            out.append(Entity(int(r["dxcc"]), r["anzeige"].strip(), pats, r["iaru"],
                              stages, _RARITY.get(r["rangbereich"], 5)))
    return out


_cache: list[Entity] | None = None


def entities() -> list[Entity]:
    global _cache
    if _cache is None:
        _cache = load()
    return _cache


def pool(ents: list[Entity], stage: str, regions: str, rng: random.Random,
         min_n: int = MIN_POOL) -> list[Entity]:
    """The entities of a round (see the module text)."""
    inreg = [e for e in ents if e.region in regions]
    chosen = [e for e in inreg if stage in e.stages]
    have = {e.dxcc for e in chosen}
    i = STAGES.index(stage)
    while len(chosen) < min_n and i > 0:
        i -= 1
        cand = [e for e in inreg if STAGES[i] in e.stages and e.dxcc not in have]
        rng.shuffle(cand)
        cand.sort(key=lambda e: e.rarity)            # stable: random within a range
        for e in cand[:min_n - len(chosen)]:
            chosen.append(e)
            have.add(e.dxcc)
    return chosen


_TOKEN = re.compile(r"\[[^\]]+\]|#|.")


def _chars(body: str) -> list[str]:
    out, j = [], 0
    while j < len(body):
        if j + 2 < len(body) and body[j + 1] == "-":
            out += [chr(c) for c in range(ord(body[j]), ord(body[j + 2]) + 1)]
            j += 3
        else:
            out.append(body[j])
            j += 1
    return out


def make_call(e: Entity, rng: random.Random) -> str:
    pat = rng.choice(e.patterns)
    s = ""
    for tok in _TOKEN.findall(pat):
        if tok == "#":
            s += rng.choice("0123456789")
        elif tok.startswith("["):
            s += rng.choice(_chars(tok[1:-1]))
        else:
            s += tok
    return s + "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
                       for _ in range(rng.randint(1, 3)))


@dataclass
class Question:
    call: str
    options: list[Entity]        # A, B, C
    right: int                   # index of the right one


def question(pl: list[Entity], used: set[int], rng: random.Random) -> Question:
    """A call of an entity not used in this game yet (all used: any), and two
    other entities of the pool as wrong answers."""
    fresh = [e for e in pl if e.dxcc not in used] or pl
    e = rng.choice(fresh)
    used.add(e.dxcc)
    others = [x for x in pl if x.dxcc != e.dxcc and x.name != e.name]
    wrong = rng.sample(others, min(2, len(others)))
    opts = wrong + [e]
    rng.shuffle(opts)
    return Question(make_call(e, rng), opts, opts.index(e))
