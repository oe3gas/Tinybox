"""Link quality per radio connection (PLANUNG.md section 14).

The TinyBox Direwolf fork answers the AGW query 'Q' with one text line of
counters that run from the start of the link, e.g.

    v=1 state=3 i_new=21 i_retry=0 bytes_new=2189 ... srt=1.38 unack=4 age=2405

TinyBox polls that line, keeps the samples of the last 30 minutes and works
with differences: per direction the last 50 frames, at most 30 minutes.

    out  (TinyBox -> station):  i_retry / (i_new + i_retry)
    in   (station -> TinyBox):  (rej_tx + retry_rx) / i_rx

A direction counts only with at least 20 frames in its window. The worse
direction gives the bars (5 = best), each T1 timeout in the window costs one
more bar. No direction with enough frames -> no result yet (grey bars).
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass

FIELDS_INT = ("state", "i_new", "i_retry", "bytes_new", "bytes_retry", "i_rx", "retry_rx",
              "rej_rx", "rej_tx", "t1_exp", "rnr_rx", "rc", "unack")
FIELDS_FLOAT = ("srt", "t1v", "age")


def parse(text: str) -> dict | None:
    """'v=1 ...' -> dict of numbers; None for 'v=1 none' or an unknown format."""
    parts = dict(p.split("=", 1) for p in text.split() if "=" in p)
    if parts.get("v") != "1" or "i_new" not in parts:
        return None
    out: dict = {}
    try:
        for k in FIELDS_INT:
            out[k] = int(parts.get(k, 0))
        for k in FIELDS_FLOAT:
            out[k] = float(parts.get(k, 0))
    except ValueError:
        return None
    return out


@dataclass(frozen=True)
class QualityCfg:
    window_frames: int = 50
    window_sec: float = 30 * 60
    min_frames: int = 20
    steps: tuple[float, ...] = (2.0, 5.0, 10.0, 20.0)   # loss % for 5 / 4 / 3 / 2 bars


@dataclass
class Direction:
    frames: int = 0          # frames in the window
    lost: int = 0            # repeated / missed frames in the window
    enough: bool = False

    @property
    def loss(self) -> float | None:
        """Loss in percent, None without enough frames."""
        if not self.enough:
            return None
        return 100.0 * self.lost / self.frames if self.frames else 0.0


@dataclass
class Result:
    bars: int | None         # 1..5, None = no result yet (grey)
    out: Direction
    inn: Direction
    t1: int                  # T1 timeouts in the window
    rej_rx: int
    rej_tx: int
    retry_rx: int
    i_retry: int
    bytes_new: int
    bytes_retry: int
    srt: float


def _out_frames(c: dict) -> int:
    return c["i_new"] + c["i_retry"]


def _in_frames(c: dict) -> int:
    return c["i_rx"]


class LinkQuality:
    """Samples of one connection and the evaluation."""

    def __init__(self, cfg: QualityCfg | None = None) -> None:
        self.cfg = cfg or QualityCfg()
        self.samples: deque[tuple[float, dict]] = deque()
        self.last: dict | None = None

    def add(self, counters: dict, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        if self.last is not None and counters["i_new"] < self.last["i_new"]:
            self.samples.clear()              # Direwolf restarted the link: start over
        if not self.samples:
            # counters start at 0 when the link starts: that is a sample too
            start = now - counters.get("age", 0.0)
            if now - start <= self.cfg.window_sec:
                self.samples.append((start, {k: 0 for k in FIELDS_INT}))
        self.samples.append((now, counters))
        self.last = counters
        while self.samples and now - self.samples[0][0] > self.cfg.window_sec:
            self.samples.popleft()

    def _base(self, frames_of, now: float) -> tuple[float, dict]:
        """Oldest sample within 30 min that still keeps the window at ~50 frames."""
        cur = frames_of(self.last)
        base = self.samples[-1]
        for t, c in reversed(self.samples):
            if now - t > self.cfg.window_sec:
                break
            base = (t, c)
            if cur - frames_of(c) >= self.cfg.window_frames:
                break
        return base

    def evaluate(self, now: float | None = None) -> Result | None:
        if self.last is None:
            return None
        now = time.monotonic() if now is None else now
        cur = self.last
        to, bo = self._base(_out_frames, now)
        ti, bi = self._base(_in_frames, now)
        d = lambda k, b: cur[k] - b[k]                                   # noqa: E731

        out = Direction(frames=_out_frames(cur) - _out_frames(bo), lost=d("i_retry", bo))
        inn = Direction(frames=_in_frames(cur) - _in_frames(bi),
                        lost=d("rej_tx", bi) + d("retry_rx", bi))
        out.enough = out.frames >= self.cfg.min_frames
        inn.enough = inn.frames >= self.cfg.min_frames
        t1 = cur["t1_exp"] - (bo if to <= ti else bi)["t1_exp"]     # since the older base

        losses = [x.loss for x in (out, inn) if x.loss is not None]
        bars = None
        if losses:
            worst = max(losses)
            bars = 1
            for n, limit in zip((5, 4, 3, 2), self.cfg.steps):
                if worst < limit:
                    bars = n
                    break
            bars = max(1, bars - t1)
        return Result(bars=bars, out=out, inn=inn, t1=t1,
                      rej_rx=d("rej_rx", bo), rej_tx=d("rej_tx", bi), retry_rx=d("retry_rx", bi),
                      i_retry=d("i_retry", bo), bytes_new=d("bytes_new", bo),
                      bytes_retry=d("bytes_retry", bo), srt=cur["srt"])


def bar_text(bars: int | None) -> str:
    """Text form for terminals: '#####' best, '#....' worst, '-----' no result yet."""
    if bars is None:
        return "-----"
    return "#" * bars + "." * (5 - bars)


def kbytes(n: int) -> str:
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)
