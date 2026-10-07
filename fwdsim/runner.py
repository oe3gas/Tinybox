"""Runs test cases and prints a report."""

from __future__ import annotations

import logging
import time

from .harness import Harness
from .scenarios import CASES, Check

log = logging.getLogger("fwdsim.run")


def _mark(ok: bool | None) -> str:
    return {True: "PASS", False: "FAIL", None: "SKIP"}[ok]


async def run_cases(h: Harness, ids: list[str], out=print) -> tuple[int, int, int]:
    """Returns (passed, failed, skipped) counted per case."""
    passed = failed = skipped = 0
    target = "stand-in (fwdsim)" if h.target.kind == "stub" else f"TinyBox {h.target.call}"
    out(f"fwdsim run {h.run_id} against {target}"
        f"{' over AGW' if h.use_agw else ' over TCP'}")
    out("")
    for cid in ids:
        c = CASES[cid]
        if c.func is None:
            out(f"{c.id}  MANUAL  {c.title}  (ab {c.since})")
            out(f"      {c.manual}")
            skipped += 1
            continue
        t0 = time.monotonic()
        try:
            checks = await c.func(h)
        except Exception as exc:          # a broken case must not stop the run
            log.exception("%s crashed", cid)
            checks = [Check("case ran", False, f"{type(exc).__name__}: {exc}")]
        dt = time.monotonic() - t0
        states = [x.ok for x in checks]
        if False in states:
            verdict, failed = "FAIL", failed + 1
        elif all(s is None for s in states):
            verdict, skipped = "SKIP", skipped + 1
        else:
            verdict, passed = "PASS", passed + 1
        out(f"{c.id}  {verdict:6}  {c.title}  (ab {c.since}, {dt:.1f} s)")
        for x in checks:
            out(f"      [{_mark(x.ok)}] {x.name}: {x.detail}")
    out("")
    out(f"{passed} passed, {failed} failed, {skipped} skipped/manual")
    return passed, failed, skipped
