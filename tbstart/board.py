"""The status board: what the console window shows (CR138).

Three zones as in start_eb200.py (MoniScope): the programs, the latest lines,
the latest error block. render() is a pure function of the state - it returns
the lines with ANSI colours, the console only writes them.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from . import supervisor as sv

RESET = "\x1b[0m"
GREY, RED, GREEN, YELLOW, CYAN, WHITE = "\x1b[90m", "\x1b[91m", "\x1b[92m", "\x1b[93m", \
    "\x1b[96m", "\x1b[97;1m"
SELECT = "\x1b[48;5;24m"
BLUE = "\x1b[94m"
ANSI = re.compile(r"\x1b\[[0-9;]*m")

STATE_COLOR = {sv.RUNNING: GREEN, sv.STARTING: YELLOW, sv.WAITING: YELLOW,
               sv.RESTARTING: YELLOW, sv.STOPPING: YELLOW, sv.FAILED: RED, sv.MISSING: RED,
               sv.EXTERNAL: CYAN, sv.OFF: GREY, sv.STOPPED: GREY, sv.ENDED: GREY,
               sv.READY: GREY}

KEYS1 = ("1-{n} wählen  a alle  s start  x stopp  r neu  R alle neu  d aus/ein  w Web-GUI")
KEYS2 = "e nur Fehler  ↑/↓ Fehler blättern  u Update  k Konfiguration  q beenden"


@dataclass
class UI:
    selected: int | None = None       # index into sup.runs
    only_errors: bool = False
    err_pos: dict = field(default_factory=dict)     # program key -> index of the block
    notice: str = ""
    notice_until: float = 0.0

    def say(self, text: str, seconds: float = 8.0) -> None:
        self.notice, self.notice_until = text, time.monotonic() + seconds


def vlen(text: str) -> int:
    return len(ANSI.sub("", text))


def fit(text: str, width: int) -> str:
    """Cut or pad to exactly width visible characters, colours kept."""
    out, n, i = [], 0, 0
    while i < len(text) and n < width:
        m = ANSI.match(text, i)
        if m:
            out.append(m.group(0))
            i = m.end()
            continue
        out.append(text[i])
        n += 1
        i += 1
    s = "".join(out)
    if "\x1b[" in s:
        s += RESET
    return s + " " * (width - n)


def c(color: str, text: str) -> str:
    return f"{color}{text}{RESET}" if text else text


def duration(seconds: float) -> str:
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m{s % 60:02d}s"
    return f"{s // 3600}h{(s % 3600) // 60:02d}m"


def port_text(r: sv.Run) -> str:
    p = r.prog
    if not p.port:
        return "–"
    mark = ""
    if r.alive() or r.state == sv.EXTERNAL:
        mark = " ✓" if r.port_ok or r.state == sv.EXTERNAL else " ✗"
    return f"{p.port_label} :{p.port}{mark}"


COLS = ((" Nr", 4), ("Programm", 10), ("Rolle", 11), ("Zustand", 12), ("Port", 14),
        ("PID", 7), ("Laufzeit", 9), ("Fehler", 6))


def row(r: sv.Run, selected: bool, now: float) -> str:
    state = r.state
    if state == sv.ENDED and r.exit_code is not None:
        state = f"beendet ({r.exit_code})"
    pid = str(r.pid) if r.pid else "–"
    up = duration(now - r.started) if r.alive() else "–"
    cells = [f"{r.nr:>3}", r.prog.name, r.prog.role or "–", state, port_text(r), pid, up,
             str(len(r.errors))]
    color = STATE_COLOR.get(r.state, "")
    parts = []
    for (_, w), text, i in zip(COLS, cells, range(len(cells))):
        cell = fit(text, w - 1) + " "
        if i == 3:
            cell = c(color, cell)
        elif i == 4 and r.port_ok is False and r.alive():
            cell = c(RED, cell)
        elif i == 4 and (r.port_ok or r.state == sv.EXTERNAL):
            cell = c(GREEN if r.port_ok else CYAN, cell)
        parts.append(cell)
    text = "".join(parts)
    if r.note:
        text += c(GREY, r.note)
    if selected:
        text = SELECT + text.replace(RESET, RESET + SELECT)
    return text


def zone3_target(sup: sv.Supervisor, ui: UI) -> sv.Run | None:
    if ui.selected is not None:
        return sup.runs[ui.selected]
    with_errors = [r for r in sup.runs if r.errors]
    return max(with_errors, key=lambda r: r.errors[-1][0]) if with_errors else None


def error_block(sup: sv.Supervisor, ui: UI) -> tuple[sv.Run | None, int, list]:
    r = zone3_target(sup, ui)
    if r is None or not r.errors:
        return r, -1, []
    pos = ui.err_pos.get(r.prog.key, len(r.errors) - 1)
    pos = max(0, min(pos, len(r.errors) - 1))
    return r, pos, r.errors[pos][1]


def move_error(sup: sv.Supervisor, ui: UI, delta: int) -> None:
    """↑ older block, ↓ newer block."""
    r, pos, _ = error_block(sup, ui)
    if r is not None and pos >= 0:
        ui.err_pos[r.prog.key] = max(0, min(pos + delta, len(r.errors) - 1))


def wanted(entry: tuple, sup: sv.Supervisor, ui: UI) -> bool:
    _, tag, channel, text = entry
    if ui.selected is not None and tag != sup.runs[ui.selected].prog.tag:
        return False
    if ui.only_errors:
        return channel == "err" or "[ERROR]" in text or "[WARN]" in text \
            or text.startswith("Traceback")
    return True


def bar(left: str, right: str, width: int, a: str = "├", b: str = "┤") -> str:
    inner = width - 2
    text = f"─ {left} " if left else ""
    tail = f" {right} ─" if right else ""
    fill = max(0, inner - vlen(text) - vlen(tail))
    return fit(a + text + "─" * fill + tail + b, width)


def render(sup: sv.Supervisor, ui: UI, width: int, height: int, head: str,
           log_path: str = "", update_hint: str = "") -> list[str]:
    width, height = max(60, width), max(20, height)
    inner = width - 2
    now = time.monotonic()
    with sv.LOCK:
        runs = list(sup.runs)
        rows = [row(r, ui.selected == i, now) for i, r in enumerate(runs)]
        msgs = [e for e in sup.messages if wanted(e, sup, ui)]
        target, pos, block = error_block(sup, ui)
        nerr = len(target.errors) if target is not None else 0

    def line(text: str) -> str:
        return "│" + fit(" " + text, inner) + "│"

    out = [bar(c(WHITE, "TinyBox Steuerkonsole") + "  " + head, time.strftime("%H:%M:%S"),
               width, "┌", "┐")]
    out.append(line(c(GREY, "".join(fit(n, w) for n, w in COLS))))
    out += [line(t) for t in rows]

    err_h = 6 if height >= 30 else 4
    fixed = len(out) + 1 + 1 + err_h + 1 + 3
    k = max(2, height - fixed)
    title2 = "Letzte Meldungen"
    if ui.selected is not None:
        title2 += " – Filter: " + c(WHITE, f"{runs[ui.selected].nr} {runs[ui.selected].prog.name}")
    if ui.only_errors:
        title2 += " – nur Fehler"
    out.append(bar(title2, "", width))
    shown = msgs[-k:]
    for _, tag, channel, text in shown:
        if not text.startswith("["):
            text = f"[{tag}{'!' if channel == 'err' else ''}] {text}"
        if "[ERROR]" in text or text.startswith("Traceback"):
            text = c(RED, text)
        elif "[WARN]" in text or channel == "err":
            text = c(YELLOW, text)
        out.append(line(text))
    out += [line("")] * (k - len(shown))

    if target is None:
        title3 = "Letzter Fehler – keiner"
    else:
        title3 = f"Letzter Fehler – {target.nr} {target.prog.name}"
        title3 += f" ({pos + 1} von {nerr})" if nerr else " – keiner"
    out.append(bar(title3, "", width))
    body = block[-err_h:] if len(block) > err_h else block
    out += [line(c(RED, t)) for t in body]
    out += [line("")] * (err_h - len(body))
    out.append(bar("", "", width, "└", "┘"))

    out.append(fit(" " + KEYS1.format(n=len(runs)), width))
    hint = "      " + c(BLUE, update_hint) if update_hint else ""
    out.append(fit(" " + KEYS2 + hint, width))
    if ui.notice and now < ui.notice_until:
        out.append(fit(" " + c(YELLOW, ui.notice), width))
    else:
        out.append(fit(" " + c(GREY, f"Log: {log_path}"), width))
    return out
