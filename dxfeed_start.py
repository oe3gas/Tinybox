#!/usr/bin/env python3
"""Start dxfeed from the TinyBox folder, whatever the current directory is.

For the Windows task scheduler (schtasks cannot set a start folder) and pyw:
    pyw -3 C:\\Tinybox\\dxfeed_start.py digest --tinybox
Relative paths in dxfeed.conf (data/, eingang, logs/) refer to this folder.
"""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.chdir(HERE)
sys.path.insert(0, str(HERE))

from dxfeed.__main__ import run      # noqa: E402

if __name__ == "__main__":
    sys.exit(run(["-c", "dxfeed.conf", *sys.argv[1:]]))
