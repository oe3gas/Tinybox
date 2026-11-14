"""One log file per calendar day: <prefix>2026-10-13.log, append mode, no renaming,
old days deleted after keep_days. Shared by TinyBox (tinybox/logsetup.py, CR32) and the
client (R13)."""

from __future__ import annotations

import contextlib
import logging
import re
from datetime import date, timedelta
from pathlib import Path

SUFFIX = ".log"
MAX_BYTES = 20 * 1024 * 1024    # per day; then <prefix>2026-10-13.2.log


class DailyFileHandler(logging.Handler):
    """One file per calendar day, append mode, no renaming.

    Not TimedRotatingFileHandler: that renames the file it is writing to, and
    on Windows a file that is open cannot be renamed - in continuous operation
    over midnight that fails exactly where the log would have to say so."""

    def __init__(self, log_dir: Path, keep_days: int = 14, max_bytes: int = MAX_BYTES, *,
                 prefix: str, legend: tuple[str, ...] = ()) -> None:
        super().__init__()
        self.prefix, self.legend = prefix, legend
        self.log_dir = Path(log_dir)
        self.keep_days = keep_days
        self.max_bytes = max_bytes
        self._day: date | None = None
        self._part = 1
        self._stream = None
        self.path: Path | None = None
        self._open(date.today())
        self.purge()

    # --- file handling ---

    def _path_for(self, day: date, part: int) -> Path:
        tail = "" if part <= 1 else f".{part}"
        return self.log_dir / f"{self.prefix}{day:%Y-%m-%d}{tail}{SUFFIX}"

    def _open(self, day: date) -> None:
        self._close()
        self._day, self._part = day, 1
        while (path := self._path_for(day, self._part)).exists() \
                and path.stat().st_size >= self.max_bytes:
            self._part += 1                       # today is full already: next part
        self.path = path
        fresh = not path.exists() or path.stat().st_size == 0
        self._stream = open(path, "a", encoding="utf-8", errors="replace")
        if fresh:
            for line in self.legend:
                self._stream.write(line + "\n")
            self._stream.flush()

    def _close(self) -> None:
        if self._stream is not None:
            with contextlib.suppress(Exception):
                self._stream.close()
        self._stream = None

    def _roll_if_needed(self) -> None:
        today = date.today()
        if today != self._day:                    # the day changed: new file
            self._open(today)
            self.purge()
            return
        if self._stream is not None and self._stream.tell() >= self.max_bytes:
            self._part += 1                       # emergency brake: .2, .3, ...
            self._close()
            self.path = self._path_for(self._day, self._part)
            self._stream = open(self.path, "a", encoding="utf-8", errors="replace")
            for line in self.legend:
                self._stream.write(line + "\n")

    def purge(self) -> int:
        """Delete log files older than keep_days. Logs never go into the repo,
        so the folder may as well tidy itself up."""
        if self.keep_days <= 0:
            return 0
        oldest = date.today() - timedelta(days=self.keep_days)
        gone = 0
        for path in self.log_dir.glob(f"{self.prefix}*{SUFFIX}"):
            found = re.match(rf"{re.escape(self.prefix)}(\d{{4}})-(\d{{2}})-(\d{{2}})", path.name)
            if not found:
                continue
            try:
                day = date(*(int(p) for p in found.groups()))
            except ValueError:
                continue
            if day < oldest:
                with contextlib.suppress(OSError):
                    path.unlink()
                    gone += 1
        return gone

    # --- logging.Handler ---

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._roll_if_needed()
            if self._stream is None:
                return
            self._stream.write(self.format(record) + "\n")
            self._stream.flush()                  # after a crash the last line counts
        except Exception:                         # a broken log must not stop the program
            self.handleError(record)

    def close(self) -> None:
        self._close()
        super().close()

    # --- for LOG MARK and LOG BUNDLE ---

    def write_raw(self, text: str) -> None:
        self._roll_if_needed()
        if self._stream is not None:
            self._stream.write(text + "\n")
            self._stream.flush()

    def size(self) -> int:
        try:
            return self.path.stat().st_size if self.path else 0
        except OSError:
            return 0

    def tail(self, lines: int) -> list[str]:
        if self.path is None or not self.path.exists():
            return []
        with open(self.path, encoding="utf-8", errors="replace") as fh:
            return [line.rstrip("\n") for line in fh.readlines()[-lines:]]
