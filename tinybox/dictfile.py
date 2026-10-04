"""DICT command: hand out the brocast dictionary as plain text.

The dictionary (brocast-core.yaml) is text, not binary. TinyBox sends it
between two marker lines so that a terminal capture can be imported into
the brocast listener, which checks line count and SHA-256:

    #BROCAST-DICT BEGIN v1 lines=212 sha256=<64 hex>
    ...
    #BROCAST-DICT END

To keep the transfer robust on old terminals the output is pure ASCII:
comment and blank lines are left out, and non-ASCII characters inside
"double quoted" YAML strings become \\uXXXX escapes (same YAML value).
The checksum covers the payload lines joined with LF, without the markers.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

BEGIN = "#BROCAST-DICT BEGIN v{version} lines={lines} sha256={sha}"
END = "#BROCAST-DICT END"
VERSION_RE = re.compile(r"^version:\s*(\d+)\s*(#.*)?$")


class DictError(Exception):
    pass


@dataclass
class DictText:
    version: int
    lines: list[str]
    sha256: str

    def framed(self) -> list[str]:
        return [BEGIN.format(version=self.version, lines=len(self.lines), sha=self.sha256),
                *self.lines, END]


PLAIN_RE = re.compile(r"^(\s*(?:- )?[^\s\"'#][^:\"']*:\s+)([^\s\"'{\[&*!|>%@`#][^#]*?)(\s+#.*)?$")


def _escape(ch: str) -> str:
    return f"\\u{ord(ch):04x}" if ord(ch) <= 0xFFFF else f"\\U{ord(ch):08x}"


def _ascii_line(line: str) -> str:
    """Make a YAML line pure ASCII without changing its value.

    Non-ASCII inside "double quotes" becomes \\uXXXX. A plain (unquoted)
    scalar like `de: Übung` is turned into `de: "\\u00dcbung"` first.
    """
    if not line.isascii():
        m = PLAIN_RE.match(line)
        if m and not m.group(2).isascii():
            value = m.group(2).replace("\\", "\\\\").replace('"', '\\"')
            line = f'{m.group(1)}"{value}"{m.group(3) or ""}'
    out, in_quotes, prev = [], False, ""
    for ch in line:
        if ch == '"' and prev != "\\":
            in_quotes = not in_quotes
        if ord(ch) > 127 and in_quotes:
            out.append(_escape(ch))
        else:
            out.append(ch)
        prev = ch
    return "".join(out)


def prepare(path: Path) -> DictText:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DictError(f"cannot read {path}: {exc}") from None
    lines = []
    version = None
    for line in raw.splitlines():
        stripped = line.rstrip()
        if not stripped.strip() or stripped.lstrip().startswith("#"):
            continue
        m = VERSION_RE.match(stripped)
        if m:
            version = int(m.group(1))
        lines.append(_ascii_line(stripped))
    if version is None:
        raise DictError(f"{path}: no 'version:' line found")
    sha = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
    return DictText(version, lines, sha)
