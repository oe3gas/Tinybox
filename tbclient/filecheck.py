"""Is a received file a program? (CR96) - moved to prcore/filecheck.py (CR86: the
TinyBox checks board files with the same rules)."""

from prcore.filecheck import (BLOCKED_EXT, MAGIC, content_verdict, name_verdict,  # noqa: F401
                              verdict)
