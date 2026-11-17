"""Start, watch, stop and restart the programs (CR138).

Every program runs as a child process with its own stdout/stderr pipe, in its own
process group: Ctrl+C in the console window reaches only the console, which then
stops the programs one by one - cleanly (CTRL_BREAK_EVENT on Windows, SIGINT
elsewhere; the Python programs treat it like Ctrl+C, prcore/stopsignal.py), hard
only after STOP_WAIT seconds.

Threads, not asyncio: msvcrt (keys) and the pipes of the children are blocking.
All state changes run under LOCK; the console only reads it.
"""

from __future__ import annotations

import collections
import os
import re
import signal
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field

from .programs import Program

LOCK = threading.RLock()

STOP_WAIT = 10.0          # s for a clean stop, then kill
RESTART_DELAY = 15.0      # s after an unexpected end (as the *_dauerbetrieb.bat)
MAX_ATTEMPTS = 5          # then "Fehler", no more restarts
STABLE_AFTER = 600.0      # s running = the attempt counter starts again
MODEM_WAIT = 20.0         # s the others wait for the AGW/KISS port of the modem
NO_PORT_RUNNING = 4.0     # s alive without a port to check = "läuft"
CHECK_EVERY = 2.0         # s between port checks
RESTART_EXIT = 3          # TinyBox RESTART (sysop console / web GUI)
CONFIG_EXIT = 2           # config error: restarting would not help

ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
HEADER = re.compile(r"^\[[\w-]+!?\] \d\d:\d\d:\d\d")     # "[tinyb] 11:20:42 ..."
LOGIN = re.compile(r"http://127\.0\.0\.1:\d+/login\?token=\S+")
MAX_BLOCK = 40
JOIN_WITHIN = 0.5      # s: error starts this close together are one block
MAX_BLOCKS = 50

# Direwolf only warns and carries on when the sound card or the PTT port is not there
# (e.g. microHAM USB Device Router not started): no match for ADEVICE -> Windows
# default device, PTT port cannot be opened -> no PTT. The console used to show
# "läuft" anyway (AGW port open). These lines mark Direwolf yellow (CR139).
DIREWOLF_PROBLEMS = (
    (re.compile(r'"(?P<dev>[^"]*)" doesn\'t match any of the input devices'),
     'Audio-Eingang "{dev}" nicht gefunden - Windows-Standardgerät'),
    (re.compile(r'"(?P<dev>[^"]*)" doesn\'t match any of the output devices'),
     'Audio-Ausgang "{dev}" nicht gefunden - Windows-Standardgerät'),
    (re.compile(r"Invalid input \(receive\) audio device number (?P<dev>-?\d+)"),
     "Audio-Eingang Nr. {dev} gibt es nicht"),
    (re.compile(r"Invalid output \(transmit\) audio device number (?P<dev>-?\d+)"),
     "Audio-Ausgang Nr. {dev} gibt es nicht"),
    (re.compile(r"Could not open audio device for (?P<dev>input|output)"),
     "Audio-Gerät ({dev}) lässt sich nicht öffnen"),
    (re.compile(r"can't open device (?P<dev>\S+) for channel \d+ PTT control"),
     "PTT-Port {dev} lässt sich nicht öffnen - kein Senden"),
)


def direwolf_problem(line: str) -> str | None:
    """The short warning for a Direwolf start line, or None."""
    for pattern, text in DIREWOLF_PROBLEMS:
        m = pattern.search(line)
        if m:
            return text.format(dev=m.group("dev"))
    return None

# states (shown as they are)
OFF, READY, WAITING, STARTING, RUNNING = "aus", "bereit", "wartet", "startet", "läuft"
STOPPING, STOPPED, ENDED, RESTARTING = "stoppt", "gestoppt", "beendet", "Neustart"
FAILED, MISSING, EXTERNAL = "Fehler", "fehlt", "extern"


@dataclass
class Run:
    """The runtime state of one program."""
    prog: Program
    nr: int
    state: str = READY
    proc: subprocess.Popen | None = None
    started: float = 0.0
    exit_code: int | None = None
    port_ok: bool | None = None
    attempts: int = 0
    restart_at: float | None = None
    wait_until: float | None = None
    stopping: bool = False
    killed: bool = False                         # the last stop needed kill()
    note: str = ""
    login_url: str | None = None
    warnings: list = field(default_factory=list)   # Direwolf: sound card/PTT missing
    errors: list = field(default_factory=list)     # blocks: [time, [lines]]
    _block: list | None = None

    @property
    def pid(self) -> int | None:
        return self.proc.pid if self.proc is not None and self.proc.poll() is None else None

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None


def port_open(port: int | None, timeout: float = 0.25) -> bool:
    if not port:
        return False
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def is_error_start(line: str) -> bool:
    return "[ERROR]" in line or line.startswith("Traceback (most recent call last)")


class Supervisor:
    def __init__(self, progs: list[Program], sink=None, log=None) -> None:
        self.runs = [Run(p, i) for i, p in enumerate(progs, 1)]
        for r in self.runs:
            r.state = READY if r.prog.active else OFF
        self.messages: collections.deque = collections.deque(maxlen=1000)
        self.sink = sink            # (run, channel, text) -> None, e.g. print in plain mode
        self.log = log              # logging.Logger for the console's own day file
        self._last_check = 0.0
        self.on_first_up = None     # (run) -> None: TBClient up -> open the browser

    # --- lines from the programs -----------------------------------------

    def line(self, run: Run | None, channel: str, text: str) -> None:
        text = ANSI.sub("", text.rstrip("\r\n"))
        tag = run.prog.tag if run else "tbstart"
        new_warning = None
        with LOCK:
            self.messages.append((time.time(), tag, channel, text))
            if run is not None:
                problem = direwolf_problem(text) if run.prog.key == "direwolf" else None
                self._watch_errors(run, text, problem is not None)
                if problem and problem not in run.warnings:
                    run.warnings.append(problem)
                    new_warning = problem
                m = LOGIN.search(text)
                if m:
                    run.login_url = m.group(0)
        if self.log is not None:
            shown = text if text.startswith("[") else f"[{tag}{'!' if channel == 'err' else ''}] {text}"
            self.log.info("%s", shown)
        if self.sink is not None:
            self.sink(run, channel, text)
        if new_warning is not None:
            self.note(f"[WARN] {run.prog.name}: {new_warning}")

    def note(self, text: str) -> None:
        """A line of the console itself."""
        self.line(None, "out", f"[tbstart] {time.strftime('%H:%M:%S')} {text}")

    def _watch_errors(self, run: Run, text: str, problem: bool = False) -> None:
        start = problem or is_error_start(text)
        if start and run._block is not None and run.errors \
                and time.time() - run.errors[-1][0] < JOIN_WITHIN:
            run._block.append(text)       # [ERROR] on stdout + its traceback on stderr:
        elif start:                      # two pipes, either may come first - one block
            run._block = [text]
            run.errors.append([time.time(), run._block])
            del run.errors[:-MAX_BLOCKS]
        elif run._block is not None and text and not HEADER.match(text):
            if len(run._block) < MAX_BLOCK:
                run._block.append(text)       # traceback lines after [ERROR]
        else:
            run._block = None

    def _pump(self, run: Run, proc: subprocess.Popen, stream, channel: str) -> None:
        for raw in iter(stream.readline, b""):
            self.line(run, channel, raw.decode("utf-8", "replace"))
        stream.close()

    # --- start / stop ------------------------------------------------------

    def start(self, run: Run, first: bool = False) -> None:
        """Start one program now (if it is not running already)."""
        with LOCK:
            if run.alive():
                return
            run.wait_until = run.restart_at = None
            if run.prog.missing:
                if run.state != MISSING:
                    self.note(f"{run.prog.name} startet nicht: {run.prog.detail or run.prog.missing}")
                run.state, run.note = MISSING, run.prog.missing
                return
            if first and run.prog.port and port_open(run.prog.port):
                run.state, run.note = EXTERNAL, "läuft schon außerhalb der Konsole"
                return
            # stdin: a pipe nobody writes to. Not DEVNULL - on Windows NUL counts as a
            # console (isatty() is True), TinyBox would start its sysop console on it
            # and read empty lines in a loop ("Unknown command").
            env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8",
                       **run.prog.env)
            kw: dict = {}
            if os.name == "nt":
                # own group: Ctrl+C in the window reaches only the console, and
                # CTRL_BREAK_EVENT reaches only this program. No CREATE_NO_WINDOW: the
                # child must share our console, else the Ctrl+Break cannot reach it.
                kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                kw["start_new_session"] = True
            try:
                proc = subprocess.Popen(run.prog.cmd, cwd=run.prog.cwd, env=env,
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, **kw)
            except OSError as exc:
                run.state, run.note = FAILED, f"Start fehlgeschlagen: {exc}"
                return
            run.proc, run.started, run.exit_code = proc, time.monotonic(), None
            run.state, run.note, run.port_ok, run.stopping = STARTING, "", None, False
            run.killed = False
            run._block = None
            run.warnings = []
        for stream, channel in ((proc.stdout, "out"), (proc.stderr, "err")):
            threading.Thread(target=self._pump, args=(run, proc, stream, channel),
                             daemon=True).start()
        self.note(f"{run.prog.name} gestartet (PID {proc.pid})")

    def _signal_stop(self, run: Run) -> None:
        proc = run.proc
        if proc is None or proc.poll() is not None:
            return
        try:
            if os.name == "nt":
                proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(proc.pid, signal.SIGINT)
        except (OSError, ValueError):
            proc.terminate()

    def stop(self, run: Run, wait: bool = False) -> None:
        """Stop cleanly, after STOP_WAIT hard. wait=False: in the background."""
        with LOCK:
            run.wait_until = run.restart_at = None
            if not run.alive():
                if run.state in (WAITING, RESTARTING, FAILED, EXTERNAL, MISSING, ENDED):
                    run.state = STOPPED if run.prog.active else OFF
                    run.note = ""
                return
            run.stopping, run.state = True, STOPPING
        self._signal_stop(run)
        if wait:
            self._finish_stop(run)
        else:
            threading.Thread(target=self._finish_stop, args=(run,), daemon=True).start()

    def _finish_stop(self, run: Run, timeout: float = STOP_WAIT) -> None:
        proc = run.proc
        if proc is None:
            return
        try:
            proc.wait(timeout)
        except subprocess.TimeoutExpired:
            self.note(f"{run.prog.name} reagiert nicht - hart beendet")
            run.killed = True
            proc.kill()
            try:
                proc.wait(3)
            except subprocess.TimeoutExpired:
                pass
        self.tick()

    def restart(self, run: Run) -> None:
        def go():
            self.stop(run, wait=True)
            with LOCK:
                run.attempts = 0
            if run.prog.active:
                self.start(run)
        threading.Thread(target=go, daemon=True).start()

    def start_all(self, first: bool = False) -> None:
        """Modem first (Direwolf/kisshub), the others when its port is open."""
        now = time.monotonic()
        modems = [r for r in self.runs if r.prog.active and r.prog.modem]
        for r in modems:
            self.start(r, first)
        waiting = any(r.alive() for r in modems)
        for r in self.runs:
            if r.prog.active and not r.prog.modem and not r.alive():
                if waiting:
                    with LOCK:
                        r.state, r.wait_until, r.note = WAITING, now + MODEM_WAIT, \
                            "wartet auf das Modem"
                else:
                    self.start(r, first)

    def restart_all(self) -> None:
        def go():
            self.stop_all()
            with LOCK:
                for r in self.runs:
                    r.attempts = 0
            self.start_all()
        threading.Thread(target=go, daemon=True).start()

    def stop_all(self, say=None) -> None:
        """Signal all at once, then wait - modem last, the others need it to hang up.
        say(text): one line per program when it has ended (q / Ctrl+C, update)."""
        say = say or (lambda text: None)
        others = [r for r in self.runs if not r.prog.modem]
        modems = [r for r in self.runs if r.prog.modem]
        for group in (others, modems):
            busy = [(r, r.proc) for r in group if r.alive()]   # proc before stop(): tick()
            for r in group:                                    # may clear it at any time
                if not r.alive() and not any(r is b for b, _ in busy) and r.prog.active:
                    say(f"{r.prog.name}: lief nicht ({r.state}) - nichts zu beenden")
                self.stop(r, wait=False)
            for r, proc in busy:
                say(f"{r.prog.name}: wird beendet (PID {proc.pid}) ...")
            self._await_end(busy, say)
        self.tick()

    def _await_end(self, busy: list[tuple[Run, subprocess.Popen]], say) -> None:
        """Wait until every program has ended (the stop threads kill after STOP_WAIT)
        and say so, one line each, in the order they end."""
        t0 = time.monotonic()
        pending = list(busy)
        while pending:
            for r, proc in list(pending):
                if proc.poll() is not None:
                    pending.remove((r, proc))
                    how = "hart beendet" if r.killed else "sauber beendet"
                    say(f"{r.prog.name}: {how} (Exit {proc.returncode}, "
                        f"{time.monotonic() - t0:.1f} s)")
            if pending and time.monotonic() - t0 > STOP_WAIT + 5:
                for r, proc in pending:
                    say(f"{r.prog.name}: endet nicht - läuft evtl. noch (PID {proc.pid})")
                return
            time.sleep(0.05)

    # --- the clock -----------------------------------------------------------

    def tick(self) -> None:
        """Called several times a second: ends, restarts, waiting, port checks."""
        now = time.monotonic()
        due: list[Run] = []
        with LOCK:
            check = now - self._last_check >= CHECK_EVERY
            if check:
                self._last_check = now
            modem_up = any(r.alive() and r.port_ok for r in self.runs if r.prog.modem)
            for r in self.runs:
                if r.proc is not None and r.proc.poll() is not None:
                    self._ended(r, now)
                if r.state == WAITING and r.wait_until is not None \
                        and (modem_up or now >= r.wait_until):
                    due.append(r)
                if r.state == RESTARTING and r.restart_at is not None and now >= r.restart_at:
                    due.append(r)
                if r.state == RESTARTING and r.restart_at is not None:
                    left = max(0, int(r.restart_at - now + 0.99))
                    r.note = f"Neustart in {left} s ({r.attempts} von {MAX_ATTEMPTS})"
                if r.alive() and r.state == RUNNING and r.attempts \
                        and now - r.started >= STABLE_AFTER:
                    r.attempts = 0
        for r in due:
            self.start(r)
        if check:
            for r in self.runs:
                if r.alive() and r.prog.port:
                    ok = port_open(r.prog.port)
                    first = False
                    with LOCK:
                        r.port_ok = ok
                        if ok and r.state == STARTING:
                            r.state, first = RUNNING, True
                    if first and self.on_first_up is not None:
                        self.on_first_up(r)
        with LOCK:
            for r in self.runs:
                if r.alive() and r.state == STARTING and not r.prog.port \
                        and now - r.started >= NO_PORT_RUNNING:
                    r.state = RUNNING

    def _ended(self, r: Run, now: float) -> None:
        code = r.proc.returncode
        r.proc = None                         # handled once
        r.exit_code, r.port_ok = code, None
        if r.stopping:
            r.state, r.note, r.stopping = (STOPPED if r.prog.active else OFF), "", False
            self.note(f"{r.prog.name} gestoppt")
            return
        if code == RESTART_EXIT and r.prog.key == "tinybox":
            self.note("TinyBox RESTART")
            r.state, r.restart_at = RESTARTING, now
            return
        if code == 0:
            r.state, r.note = ENDED, "von selbst beendet (Exit 0)"
            self.note(f"{r.prog.name} hat sich beendet (Exit 0) - kein Neustart")
            return
        if code == CONFIG_EXIT:
            r.state, r.note = FAILED, "Konfigurationsfehler (Exit 2) - siehe Meldungen"
            self.note(f"{r.prog.name}: Konfigurationsfehler - kein Neustart")
            return
        r.attempts += 1
        if r.attempts > MAX_ATTEMPTS:
            r.state, r.note = FAILED, f"aufgegeben nach {MAX_ATTEMPTS} Versuchen (Exit {code})"
            self.note(f"{r.prog.name}: aufgegeben nach {MAX_ATTEMPTS} Neustarts")
            return
        r.state, r.restart_at = RESTARTING, now + RESTART_DELAY
        r.note = f"Neustart in {int(RESTART_DELAY)} s ({r.attempts} von {MAX_ATTEMPTS})"
        self.note(f"{r.prog.name} unerwartet beendet (Exit {code}) - {r.note}")

    def set_active(self, run: Run, active: bool) -> None:
        with LOCK:
            run.prog.active = active
            if not active and not run.alive():
                run.state, run.note = OFF, ""
        if active:
            self.start(run)
        else:
            self.stop(run)
