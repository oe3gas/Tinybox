"""The console window: ANSI on, keys without Enter, lifetime of the children (CR138).

Windows: VT mode and UTF-8 for the window, msvcrt for the keys, a job object with
KILL_ON_JOB_CLOSE (closing the window ends every program - no orphans on the
ports). Elsewhere (NanoPi over SSH, tests): termios cbreak and select.
"""

from __future__ import annotations

import os
import sys

try:
    import msvcrt                                  # Windows only
except ImportError:
    msvcrt = None


def is_tty() -> bool:
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


def enable_ansi() -> bool:
    """VT processing and UTF-8 output on Windows; True if the board can be drawn."""
    if not sys.stdout.isatty():
        return False
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if os.name != "nt":
        return True
    try:
        import ctypes
        k = ctypes.windll.kernel32
        k.SetConsoleOutputCP(65001)
        handle = k.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not k.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(k.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        return False


def set_title(text: str) -> None:
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleTitleW(text)
        except Exception:
            pass
    elif sys.stdout.isatty():
        sys.stdout.write(f"\x1b]0;{text}\x07")


def bind_children_to_window() -> str:
    """Windows: put this process into a job that kills all members when the last
    handle closes - the children inherit it. '' = ok, else a warning text."""
    if os.name != "nt":
        return ""
    try:
        import ctypes
        from ctypes import wintypes
        k = ctypes.windll.kernel32

        class BASIC(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                        ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD),
                        ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t),
                        ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t),
                        ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class IO(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint64) for n in
                        ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                         "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class EXTENDED(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", BASIC), ("IoInfo", IO),
                        ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        k.CreateJobObjectW.restype = wintypes.HANDLE
        job = k.CreateJobObjectW(None, None)
        if not job:
            return "kein Job-Objekt - Programme enden beim Schließen des Fensters nicht mit"
        info = EXTENDED()
        info.BasicLimitInformation.LimitFlags = 0x2000          # KILL_ON_JOB_CLOSE
        if not k.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
            return "Job-Objekt ohne KILL_ON_JOB_CLOSE"
        k.GetCurrentProcess.restype = wintypes.HANDLE
        if not k.AssignProcessToJobObject(job, k.GetCurrentProcess()):
            return "Job-Zuordnung fehlgeschlagen - Programme enden beim Schließen nicht mit"
        bind_children_to_window.job = job       # keep the handle open for our lifetime
        return ""
    except Exception as exc:                    # pragma: no cover - Windows only
        return f"Job-Objekt: {exc}"


class Keys:
    """Keys without Enter: '1', 'r', 'up', 'down' ... - empty list when none."""

    def __init__(self) -> None:
        self._old = None
        if msvcrt is None and sys.stdin.isatty():
            import termios
            import tty
            self._old = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())

    def close(self) -> None:
        if self._old is not None:
            import termios
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._old)
            self._old = None

    def reopen(self) -> None:
        if msvcrt is None and sys.stdin.isatty() and self._old is None:
            self.__init__()

    def read(self) -> list[str]:
        out: list[str] = []
        if msvcrt is not None:
            while msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch in ("\x00", "\xe0"):              # arrow keys: two characters
                    code = msvcrt.getwch()
                    out.append({"H": "up", "P": "down"}.get(code, ""))
                else:
                    out.append(ch)
            return [k for k in out if k]
        if self._old is None:
            return out
        import select
        while select.select([sys.stdin], [], [], 0)[0]:
            ch = os.read(sys.stdin.fileno(), 1).decode("latin-1")
            if ch == "\x1b":
                seq = os.read(sys.stdin.fileno(), 2).decode("latin-1") \
                    if select.select([sys.stdin], [], [], 0.05)[0] else ""
                out.append({"[A": "up", "[B": "down"}.get(seq, ""))
            else:
                out.append(ch)
        return [k for k in out if k]
