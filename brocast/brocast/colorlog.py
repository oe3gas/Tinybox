"""Console colours for brocastd: prcore/termcolor.py of the TinyBox repo.

brocast sits in the TinyBox folder and normally finds prcore there. Copied on its
own, it falls back to plain text with the same [WARN]/[ERROR] tags.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
if (_root / "prcore" / "termcolor.py").is_file() and str(_root) not in sys.path:
    sys.path.append(str(_root))

try:
    from prcore.termcolor import HEAD, OK, ConsoleFormatter, check_mode, console_handler
except ImportError:                                   # brocast without the TinyBox repo
    OK: dict = {}
    HEAD: dict = {}

    class ConsoleFormatter(logging.Formatter):        # type: ignore[no-redef]
        def __init__(self, tag: str, color: bool = False, context: str = "",
                     datefmt: str = "%H:%M:%S") -> None:
            super().__init__(datefmt=datefmt)
            self.tag = tag

        def format(self, record: logging.LogRecord) -> str:
            level = ("[ERROR] " if record.levelno >= logging.ERROR else
                     "[WARN] " if record.levelno >= logging.WARNING else "")
            text = f"{self.tag} {self.formatTime(record, self.datefmt)} {level}{record.getMessage()}"
            if record.exc_info:
                text += "\n" + self.formatException(record.exc_info)
            return text

    def check_mode(value: str) -> str:                # type: ignore[no-redef]
        return "no"

    def console_handler(tag: str, mode: str = "auto", context: str = "",
                        stream=None) -> logging.StreamHandler:   # type: ignore[no-redef]
        handler = logging.StreamHandler(stream or sys.stdout)
        handler.setFormatter(ConsoleFormatter(tag))
        return handler

__all__ = ["HEAD", "OK", "ConsoleFormatter", "check_mode", "console_handler"]
