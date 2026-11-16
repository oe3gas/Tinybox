"""Console colours for brocastd: prcore/termcolor.py (PLANUNG 17.4).

Only a thin layer: the names brocast uses, plus the file formatter.
"""

from __future__ import annotations

import logging

from prcore.termcolor import (HEAD, OK, ConsoleFormatter, check_mode, console_handler, kv,  # noqa: F401
                              kv_block)
from prcore.text import visible


class FileFormatter(logging.Formatter):
    """Log file lines with received text made harmless (CR95, TB-12)."""

    def format(self, record: logging.LogRecord) -> str:
        return visible(super().format(record))


__all__ = ["HEAD", "OK", "ConsoleFormatter", "FileFormatter", "check_mode", "console_handler",
           "kv", "kv_block", "visible"]
