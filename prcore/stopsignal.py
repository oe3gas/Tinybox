"""Clean stop from the control console (CR138).

The control console (tbstart) starts every program in its own process group and
stops it with CTRL_BREAK_EVENT (Windows) or SIGINT (elsewhere). Python's default
for SIGBREAK ends the process at once, without any finally block - the program
could not hang up its connections or close its database. install() makes
Ctrl+Break behave like Ctrl+C: KeyboardInterrupt, the program's normal way out.
"""

from __future__ import annotations

import signal


def install() -> None:
    """Ctrl+Break = Ctrl+C. Call once in main(), before asyncio.run()."""
    sigbreak = getattr(signal, "SIGBREAK", None)        # Windows only
    if sigbreak is not None:
        try:
            signal.signal(sigbreak, signal.default_int_handler)
        except (ValueError, OSError):                   # not the main thread
            pass
