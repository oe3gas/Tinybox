"""python -m tbstart - the control console (CR138). Started by TinyBox-Start.bat.

    TinyBox-Start.bat            console with the programs from tbstart.conf
    TinyBox-Start.bat 4          profile 4 for this run (autostart): 1 client only,
                                 2 + TinyBox, 3 + brocast, 4 all
    python -m tbstart --plain    line stream without keys (also when not in a console)
    python -m tbstart --no-pull  no "git pull" before the start
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from prcore import dailylog, release
from prcore.text import isnum

from . import VERSION, board, programs, term
from .supervisor import LOCK, Supervisor

ROOT = Path(__file__).resolve().parent.parent
FETCH_EVERY = 6 * 3600          # s between looks for a new version on GitHub
FRAME = 0.25                    # s between two pictures of the board
SELF = ("tbstart/", "prcore/")  # changed by git pull = the console starts itself anew


def git(root: Path, *args: str, timeout: float = 120) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def has_git(root: Path) -> bool:
    return (root / ".git").exists() and shutil.which("git") is not None


def pull(root: Path, say) -> list[str] | None:
    """git pull --ff-only. The changed files, [] = up to date, None = no update."""
    if not has_git(root):
        return None
    say("Hole Updates von GitHub (git pull) ...")
    try:
        before = git(root, "rev-parse", "HEAD").stdout.strip()
        res = git(root, "pull", "--ff-only", "--quiet")
    except (OSError, subprocess.TimeoutExpired) as exc:
        say(f"  kein Update möglich ({exc}) - starte die vorhandene Version")
        return None
    if res.returncode != 0:
        say("  kein Update möglich (offline oder lokale Änderungen) - "
            "starte die vorhandene Version")
        for ln in (res.stderr or "").splitlines()[:3]:
            say("  " + ln)
        return None
    after = git(root, "rev-parse", "HEAD").stdout.strip()
    if before == after:
        say("  schon aktuell")
        return []
    for ln in git(root, "log", "--format=  %h %s", "-n", "15", f"{before}..{after}") \
            .stdout.splitlines():
        say(ln)
    changed = git(root, "diff", "--name-only", before, after).stdout.split()
    if any(f.endswith("requirements.txt") for f in changed):
        say("  Python-Pakete werden aktualisiert ...")
        subprocess.run([sys.executable, "-m", "pip", "install", "--user",
                        "--disable-pip-version-check", "-q", "-r",
                        str(root / "release" / "requirements.txt")])
    return changed


def newer_on_github(root: Path) -> int:
    """Commits on GitHub that are not here yet (git fetch); 0 if none or unknown."""
    if not has_git(root):
        return 0
    try:
        if git(root, "fetch", "-q", timeout=60).returncode != 0:
            return 0
        out = git(root, "rev-list", "--count", "HEAD..@{u}").stdout.strip()
        return int(out or 0)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return 0


def version_line(root: Path) -> str:
    cli = "?"
    try:
        m = re.search(r'^VERSION = "(.*)"', (root / "tbclient" / "__init__.py")
                      .read_text(encoding="utf-8"), re.MULTILINE)
        cli = m.group(1) if m else "?"
    except OSError:
        pass
    stand = ""
    if has_git(root):
        try:
            stand = " · Stand " + git(root, "log", "-1", "--format=%h %cs").stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
    return f"Release {release.RELEASE} · Client {cli}{stand}"


def own_log(root: Path) -> tuple[logging.Logger, str]:
    log = logging.getLogger("tbstart")
    log.propagate = False
    log.setLevel(logging.INFO)
    try:
        (root / "logs").mkdir(exist_ok=True)
        handler = dailylog.DailyFileHandler(
            root / "logs", prefix="tbstart-",
            legend=("# tbstart log (CR138) - every line of every program, [tag] in front",))
    except OSError:
        return log, "(keine Logdatei)"
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    log.addHandler(handler)
    return log, str(handler.path.relative_to(root) if handler.path else "")


def run_konfig(root: Path) -> bool:
    konfig = root / "release" / "konfig.py"
    if not konfig.is_file():
        return False
    subprocess.call([sys.executable, str(konfig)], cwd=root)
    return True


class Console:
    def __init__(self, root: Path, args) -> None:
        self.root, self.args = root, args
        self.settings = programs.apply_profile(programs.start_settings(root), args.profile)
        self.log, self.log_path = own_log(root)
        self.plain = args.plain or not term.is_tty()
        sink = self._print if self.plain else None
        self.sup = Supervisor(programs.programs(root, self.settings), sink=sink, log=self.log)
        self.ui = board.UI()
        self.quit = False
        self.reexec = False
        self.busy = False               # update or restart all in progress
        self.update_hint = ""
        self.browser_opened = args.no_browser or self.plain
        self.sup.on_first_up = self._first_up
        self.keys: term.Keys | None = None

    # --- output ---

    def _print(self, run, channel: str, text: str) -> None:
        if not text.startswith("["):
            tag = run.prog.tag if run else "tbstart"
            text = f"[{tag}{'!' if channel == 'err' else ''}] {text}"
        print(text, flush=True)

    def head(self) -> str:
        prof = self.args.profile
        p = f" · Profil {prof} ({programs.PROFILES[prof]})" if prof in programs.PROFILES else ""
        return f"{socket.gethostname()} · Release {release.RELEASE} · {self.root}{p}"

    def draw(self) -> None:
        w, h = shutil.get_terminal_size(fallback=(100, 32))
        lines = board.render(self.sup, self.ui, w, h - 1, self.head(), self.log_path,
                             self.update_hint)
        sys.stdout.write("\x1b[H" + "\r\n".join(x + "\x1b[K" for x in lines) + "\x1b[J")
        sys.stdout.flush()

    # --- events ---

    def _first_up(self, run) -> None:
        if run.prog.key == "tbclient" and not self.browser_opened and run.prog.url:
            self.browser_opened = True
            webbrowser.open(run.prog.url)

    def selected(self):
        if self.ui.selected is None:
            self.ui.say("erst ein Programm wählen (1-%d)" % len(self.sup.runs))
            return None
        return self.sup.runs[self.ui.selected]

    def handle(self, key: str) -> None:
        ui, sup = self.ui, self.sup
        if isnum(key) and 1 <= int(key) <= len(sup.runs):
            ui.selected = int(key) - 1
        elif key == "a":
            ui.selected, ui.only_errors = None, False
        elif key == "e":
            ui.only_errors = not ui.only_errors
        elif key == "up":
            board.move_error(sup, ui, -1)
        elif key == "down":
            board.move_error(sup, ui, +1)
        elif key in ("q", "\x03"):
            self.quit = True
        elif key == "R":
            if not self.busy:
                ui.say("alle Programme werden neu gestartet ...")
                sup.restart_all()
        elif key == "u":
            if not self.busy:
                threading.Thread(target=self.update, daemon=True).start()
        elif key == "k":
            self.konfig()
        elif key in ("s", "x", "r", "d", "w"):
            run = self.selected()
            if run is None:
                return
            name = run.prog.name
            if key == "s":
                if not run.prog.active:
                    ui.say(f"{name} ist deaktiviert - mit d aktivieren")
                else:
                    sup.start(run)
            elif key == "x":
                ui.say(f"{name} wird gestoppt ...")
                sup.stop(run)
            elif key == "r":
                ui.say(f"{name} wird neu gestartet ...")
                sup.restart(run)
            elif key == "d":
                active = not run.prog.active
                try:
                    programs.set_active(self.root, run.prog.key, active)
                except OSError as exc:
                    ui.say(f"tbstart.conf nicht geschrieben: {exc}")
                    return
                sup.set_active(run, active)
                ui.say(f"{name} {'aktiviert' if active else 'deaktiviert'} (tbstart.conf)")
            elif key == "w":
                url = run.login_url or run.prog.url
                if url:
                    webbrowser.open(url)
                    ui.say(f"Browser: {url.split('?')[0]}")
                else:
                    ui.say(f"{name} hat keine Web-GUI")

    def update(self) -> None:
        """u: stop all, git pull, start again (the console itself anew if it changed)."""
        self.busy = True
        try:
            self.ui.say("Update: Programme werden gestoppt ...", 60)
            self.sup.stop_all(self.sup.note)
            changed = pull(self.root, self.sup.note)
            self.update_hint = ""
            if changed and any(f.startswith(SELF) for f in changed):
                self.ui.say("die Steuerkonsole selbst wurde erneuert - startet neu ...", 60)
                self.reexec = self.quit = True
                return
            self.ui.say("Update fertig - Programme starten wieder" if changed
                        else "kein neuer Stand - Programme starten wieder")
            self.sup.start_all()
        finally:
            self.busy = False

    def konfig(self) -> None:
        if not (self.root / "release" / "konfig.py").is_file():
            self.ui.say("kein Konfigurationsdialog in dieser Installation")
            return
        self.leave_screen()
        print("Konfigurationsdialog - die Programme laufen weiter.\n")
        run_konfig(self.root)
        input("\nEnter = zurück zur Steuerkonsole ")
        self.settings = programs.apply_profile(programs.start_settings(self.root),
                                               self.args.profile)
        new = {p.key: p for p in programs.programs(self.root, self.settings)}
        with LOCK:
            for r in self.sup.runs:
                if r.prog.key in new:
                    r.prog = new[r.prog.key]
        self.enter_screen()
        self.ui.say("Konfiguration gelesen - R startet alles mit ihr neu", 15)

    def watch_github(self) -> None:
        while not self.quit:
            n = newer_on_github(self.root)
            self.update_hint = f"Neuer Stand auf GitHub ({n} Änderungen) - u holt ihn" if n \
                else ""
            for _ in range(FETCH_EVERY):
                if self.quit:
                    return
                time.sleep(1)

    # --- screen ---

    def enter_screen(self) -> None:
        sys.stdout.write("\x1b[?1049h\x1b[?25l\x1b[2J")
        sys.stdout.flush()
        if self.keys is None:
            self.keys = term.Keys()
        else:
            self.keys.reopen()

    def leave_screen(self) -> None:
        if self.keys is not None:
            self.keys.close()
        sys.stdout.write("\x1b[?25h\x1b[?1049l")
        sys.stdout.flush()

    # --- main loop ---

    def run(self) -> int:
        warn = term.bind_children_to_window()
        if warn:
            self.sup.note("Warnung: " + warn)
        self.sup.note(f"Steuerkonsole {VERSION} - {version_line(self.root)}")
        if not self.settings["exists"]:
            self.sup.note("tbstart.conf fehlt - nur TBClient aktiv (k = Konfiguration)")
        self.sup.start_all(first=True)
        if not self.args.no_pull:
            threading.Thread(target=self.watch_github, daemon=True).start()
        if self.plain:
            return self.run_plain()
        self.enter_screen()
        try:
            while not self.quit:
                for key in self.keys.read():
                    self.handle(key)
                self.sup.tick()
                self.draw()
                time.sleep(FRAME)
        except KeyboardInterrupt:
            pass
        finally:
            self.leave_screen()
        self.shutdown(lambda t: print("  " + t, flush=True))
        return 0

    def run_plain(self) -> int:
        try:
            while not self.quit:
                self.sup.tick()
                time.sleep(FRAME)
        except KeyboardInterrupt:
            pass
        self.shutdown(self.sup.note)
        return 0

    def shutdown(self, say) -> None:
        """q / Ctrl+C: stop every program and report each one (also in the day log).
        A second Ctrl+C ends the rest hard at once."""
        def report(text: str) -> None:
            say(text)
            if say != self.sup.note:          # note() writes the log itself
                self.log.info("[tbstart] %s %s", time.strftime("%H:%M:%S"), text)

        report("Steuerkonsole: Programme werden beendet ...")
        try:
            self.sup.stop_all(report)
        except KeyboardInterrupt:
            report("Abbruch - die übrigen Programme werden hart beendet ...")
            for r in self.sup.runs:
                if r.alive():
                    r.proc.kill()
                    report(f"{r.prog.name}: hart beendet")
        left = [r.prog.name for r in self.sup.runs if r.alive()]
        report("Noch aktiv: " + ", ".join(left) if left
               else "Alle Programme beendet - Steuerkonsole Ende.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tbstart", description="TinyBox Steuerkonsole (CR138)")
    ap.add_argument("profile", nargs="?", default="",
                    help="1-4: profile for this run (1 client, 2 + TinyBox, 3 + brocast, 4 all)")
    ap.add_argument("--plain", action="store_true", help="line stream, no board, no keys")
    ap.add_argument("--no-pull", action="store_true", help="no git pull before the start")
    ap.add_argument("--no-browser", action="store_true", help="do not open the client page")
    args = ap.parse_args(argv)
    root = ROOT
    os.chdir(root)
    term.set_title("TinyBox Steuerkonsole")
    term.enable_ansi()
    print(f"TinyBox Steuerkonsole {VERSION} - {version_line(root)}", flush=True)

    if not args.no_pull:
        changed = pull(root, lambda t: print(t, flush=True))
        if changed and any(f.startswith(SELF) for f in changed):
            print("Die Steuerkonsole selbst wurde erneuert - starte sie neu ...", flush=True)
            return subprocess.call([sys.executable, "-m", "tbstart", "--no-pull",
                                    *([args.profile] if args.profile else [])], cwd=root)

    if not (root / programs.START_CONF).is_file() and term.is_tty() \
            and (root / "release" / "konfig.py").is_file():
        answer = input("tbstart.conf fehlt. Konfigurationsdialog jetzt starten? (j/n) [j] ")
        if not answer.strip().lower().startswith("n"):
            run_konfig(root)

    console = Console(root, args)
    code = console.run()
    if console.reexec:
        return subprocess.call([sys.executable, "-m", "tbstart", "--no-pull",
                                *([args.profile] if args.profile else [])], cwd=root)
    return code


if __name__ == "__main__":
    sys.exit(main())
