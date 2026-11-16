"""brocast – compact page protocol over AX.25 packet radio (CBOR + dictionary).

brocast is one of the four programs of the TinyBox package (PLANUNG 17.4): it runs on
its own, but uses the shared basics in prcore/, which always comes along (repo, release
package, NanoPi build). This is the one place that makes prcore importable when
brocastd is started from its own folder (brocast/, as brocastd.bat and the systemd
unit do) - every module below may simply "from prcore import ...".
"""

import sys as _sys
from pathlib import Path as _Path

_root = _Path(__file__).resolve().parents[2]          # the TinyBox folder around brocast/
if (_root / "prcore" / "__init__.py").is_file() and str(_root) not in _sys.path:
    _sys.path.append(str(_root))

from .codec import BrocastError, Codec, CriticalKeyError
from .dictionary import Dictionary, DictionaryError

__all__ = ["BrocastError", "Codec", "CriticalKeyError", "Dictionary", "DictionaryError"]
