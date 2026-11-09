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
    from prcore.termcolor import (HEAD, OK, ConsoleFormatter, check_mode, console_handler, kv,
                                  kv_block)
    from prcore.text import visible
except ImportError:                                   # brocast without the TinyBox repo
    import unicodedata as _ud

    def visible(text: str, keep: str = "\n\t") -> str:     # type: ignore[no-redef]
        """Same as prcore.text.visible (CR95, TB-12): escapes terminal controls."""
        def bad(ch: str) -> bool:
            n = ord(ch)
            return (n < 0x20 or 0x7F <= n <= 0x9F or
                    (n > 0x9F and _ud.category(ch) in ("Cf", "Zl", "Zp", "Co", "Cs", "Cn")))
        return "".join((f"\\x{ord(c):02x}" if ord(c) < 0x100 else f"\\u{ord(c):04x}")
                       if c not in keep and bad(c) else c for c in text)

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
            text = (f"{self.tag} {self.formatTime(record, self.datefmt)} {level}"
                    f"{visible(record.getMessage())}")
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

    def kv(log: logging.Logger, label: str, value, note: str = "", url: bool = False,
           level: int = logging.INFO) -> None:              # type: ignore[no-redef]
        text = f"{label + ':':<23} {value}"
        log.log(level, "%s", text + (f"  {note}" if note else ""))

    def kv_block(log: logging.Logger, items) -> None:       # type: ignore[no-redef]
        for item in items:
            if item is None:
                log.info("")
            elif isinstance(item, str):
                log.info("%s", item)
            else:
                kv(log, *item)



class FileFormatter(logging.Formatter):
    """Log file lines with received text made harmless (CR95, TB-12)."""

    def format(self, record: logging.LogRecord) -> str:
        return visible(super().format(record))


__all__ = ["HEAD", "OK", "ConsoleFormatter", "FileFormatter", "check_mode", "console_handler",
           "kv", "kv_block", "visible"]
