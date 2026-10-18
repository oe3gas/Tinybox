"""Read the values TinyBox, client, kisshub and brocastd need from direwolf.conf
(CR70: direwolf.conf is the one place for them when Direwolf is the modem).

Over AGW they cannot be asked: Direwolf answers 'g' (port capabilities) with
fixed values (server.c: "Fake it to keep application happy").

    dw = read("E:\\direwolf")              # folder (-> direwolf.conf in it) or file
    dw.agw_port, dw.kiss_port              # AGWPORT / KISSPORT (None if not set)
    ch = dw.channel(0)                     # the radio channel
    ch.baud, ch.txdelay_ms, ch.paclen, ch.maxframe, ch.emaxframe ...

direwolf.conf: one directive per line, '#' starts a comment, names are not
case sensitive. CHANNEL n switches the channel the following MODEM, TXDELAY,
PERSIST, SLOTTIME lines belong to (ADEVICE n starts radio n with channels
2n, 2n+1). PACLEN, MAXFRAME, EMAXFRAME, FRACK, RETRY are global. Values not
in the file are None - the caller keeps its own default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

FILE_NAME = "direwolf.conf"


class DirewolfConfError(Exception):
    pass


@dataclass
class Channel:
    baud: int | None = None          # MODEM <baud> ...
    txdelay_ms: int | None = None    # TXDELAY <10 ms units>
    persist: int | None = None       # PERSIST 0..255
    slottime_ms: int | None = None   # SLOTTIME <10 ms units>


@dataclass
class DirewolfConf:
    path: Path
    agw_port: int | None = None
    kiss_port: int | None = None
    paclen: int | None = None
    maxframe: int | None = None      # window modulo 8
    emaxframe: int | None = None     # window modulo 128
    frack_sec: int | None = None     # Direwolf's T1 (only shown: Direwolf does AX.25 over AGW)
    retry: int | None = None         # Direwolf's N2
    channels: dict[int, Channel] = field(default_factory=dict)

    def channel(self, n: int = 0) -> Channel:
        """The values of radio channel n (empty Channel if not described)."""
        return self.channels.get(n, Channel())

    def describe(self, n: int = 0) -> str:
        c = self.channel(n)
        parts = [f"{k} {v}" for k, v in (
            ("AGWPORT", self.agw_port), ("KISSPORT", self.kiss_port), ("MODEM", c.baud),
            ("TXDELAY", f"{c.txdelay_ms} ms" if c.txdelay_ms is not None else None),
            ("PACLEN", self.paclen), ("MAXFRAME", self.maxframe),
            ("EMAXFRAME", self.emaxframe), ("FRACK", self.frack_sec), ("RETRY", self.retry))
            if v is not None]
        return f"{self.path}: " + (", ".join(parts) or "no values found")


def resolve(path: str | Path) -> Path:
    """A folder means the direwolf.conf in it; a file is taken as it is."""
    p = Path(str(path).strip().strip('"'))
    if p.is_dir():
        p = p / FILE_NAME
    return p


def _int(word: str) -> int | None:
    try:
        return int(word)
    except ValueError:
        return None


def parse(text: str, path: Path = Path(FILE_NAME)) -> DirewolfConf:
    dw = DirewolfConf(path=path)
    chan = 0
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        words = line.split()
        key, args = words[0].upper(), words[1:]
        first = _int(args[0]) if args else None
        if key.startswith("ADEVICE") and args:
            # ADEVICE (first radio, channel 0) or ADEVICE<n>: radio n, channels 2n, 2n+1
            n = _int(key[7:]) if len(key) > 7 else 0
            chan = 2 * n if n is not None else chan
        elif key == "CHANNEL" and first is not None:
            chan = first
        elif key == "MODEM" and first is not None:
            dw.channels.setdefault(chan, Channel()).baud = first
        elif key == "TXDELAY" and first is not None:
            dw.channels.setdefault(chan, Channel()).txdelay_ms = first * 10
        elif key == "PERSIST" and first is not None:
            dw.channels.setdefault(chan, Channel()).persist = first
        elif key == "SLOTTIME" and first is not None:
            dw.channels.setdefault(chan, Channel()).slottime_ms = first * 10
        elif key == "AGWPORT" and first is not None:
            dw.agw_port = first
        elif key == "KISSPORT" and first is not None:
            dw.kiss_port = first
        elif key == "PACLEN" and first is not None:
            dw.paclen = first
        elif key == "MAXFRAME" and first is not None:
            dw.maxframe = first
        elif key == "EMAXFRAME" and first is not None:
            dw.emaxframe = first
        elif key == "FRACK" and first is not None:
            dw.frack_sec = first
        elif key == "RETRY" and first is not None:
            dw.retry = first
    return dw


def read(path: str | Path) -> DirewolfConf:
    """Raise DirewolfConfError when the file is not there or unreadable."""
    p = resolve(path)
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise DirewolfConfError(f"direwolf.conf not readable: {p} ({exc.strerror or exc})") \
            from None
    return parse(text, p)
