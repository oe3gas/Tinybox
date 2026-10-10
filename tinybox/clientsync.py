"""Offline mailbox of the TinyBox client (PLANUNG.md 12.8, C3).

Commands of a client session with the cap SYNC. Every answer ends with an
end line, so the client knows when it is complete. Lines are plain text;
only the message texts may come compressed (cap Z, radio only).

    //MLIST                     own personal mail (to or from me)
        -> //M <header> ... //MEND <n>
    //RUBRICS                   bulletin rubrics with count and highest number
        -> //RU <rubric> <count> <max id> ... //RUEND
    //BLIST <rubric>=<after> ...  bulletins of these rubrics newer than <after>
        -> //M <header> ... //MEND <n>
    //GET <id> [<id> ...]       message texts (at most MAX_GET)
        -> //MSG <id> <n lines> + n lines        plain text
           //ZMSG <id> <n bytes> + n bytes       LZHUF (as FBB B1: CRC + length + data)
           //NOMSG <id>                          gone or not yours
           //GEND
    //SEND <P|B> <to>[@<at>] <n> [mid=<id>] [bid=<bid>]
        + subject line + n text lines (sent without waiting)
        -> //SENT <id>  or  //ERR send <reason>
    //KILL <id> ...             delete own mail  -> //K <id> ok|<reason> ... //KEND
    //READ <id> ...             read in the client -> status Y   -> //REND

Header:  <id> <P|B> <N|Y> <fwd|-> <size> <from> <to> <at|-> <bid|-> <unix time> <subject>

mid= is a unique id made by the client: if the //SENT answer got lost and the
client sends the same message again, the TinyBox answers with the old number
instead of storing it twice.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from .service import ServiceError
from .store import Message

if TYPE_CHECKING:
    from .session import Session

log = logging.getLogger(__name__)

MAX_GET = 20
MAX_IDS = 100
MAX_SEND_LINES = 2000
MID_RE = re.compile(r"^[0-9A-Za-z-]{8,40}$")
RUBRIC_RE = re.compile(r"^([A-Z0-9]{1,6})=(\d{1,9})$")
COMMANDS = ("MLIST", "RUBRICS", "BLIST", "GET", "SEND", "KILL", "READ")


def _epoch(iso: str) -> int:
    try:
        return int(datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S")
                   .replace(tzinfo=timezone.utc).timestamp())
    except ValueError:
        return 0


def header(m: Message) -> str:
    return (f"//M {m.id} {m.type} {m.status} {m.fwd or '-'} {m.size} {m.from_call} "
            f"{m.to_call} {m.at_addr or '-'} {m.bid or '-'} {_epoch(m.created)} "
            f"{' '.join(m.subject.split())}")


def _ids(parts: list[str]) -> list[int] | None:
    parts = ",".join(parts).replace(",", " ").split()
    if not parts or len(parts) > MAX_IDS or not all(p.isdigit() for p in parts):
        return None
    return [int(p) for p in parts]


def handle(s: Session, cmd: str, parts: list[str]) -> None:
    if "SYNC" not in s.client.caps:
        s.out(f"//ERR {cmd} needs SYNC")
        return
    {"MLIST": _mlist, "RUBRICS": _rubrics, "BLIST": _blist, "GET": _get,
     "SEND": _send, "KILL": _kill, "READ": _read}[cmd](s, parts)


def _visible(s: Session) -> list[Message]:
    return s.service.list_for(s.call, sysop=False)


def _mlist(s: Session, parts: list[str]) -> None:
    rows = [header(m) for m in _visible(s) if m.type == "P"]
    _write(s, rows + [f"//MEND {len(rows)}"], f"//MLIST: {len(rows)} header(s)")


def _rubrics(s: Session, parts: list[str]) -> None:
    count: dict[str, list[int]] = {}
    for m in _visible(s):
        if m.type == "B":
            c = count.setdefault(m.to_call, [0, 0])
            c[0] += 1
            c[1] = max(c[1], m.id)
    s.out(*[f"//RU {r} {n} {mx}" for r, (n, mx) in sorted(count.items())], "//RUEND")


def _blist(s: Session, parts: list[str]) -> None:
    after: dict[str, int] = {}
    for p in parts:
        m = RUBRIC_RE.match(p.upper())
        if not m:
            s.out("//ERR blist")
            return
        after[m.group(1)] = int(m.group(2))
    rows = [header(m) for m in _visible(s)
            if m.type == "B" and m.to_call in after and m.id > after[m.to_call]]
    _write(s, rows + [f"//MEND {len(rows)}"], f"//BLIST: {len(rows)} header(s)")


def _get(s: Session, parts: list[str]) -> None:
    ids = _ids(parts)
    if ids is None or len(ids) > MAX_GET:
        s.out("//ERR get", "//GEND")
        return
    z = "Z" in s.client.caps and hasattr(s.transport, "write_bytes")
    plain = comp = 0
    for msg_id in ids:
        msg = s.service.store.get(msg_id)
        if msg is None or not s.service.can_see(msg, s.call, False):
            s.transport.write(f"//NOMSG {msg_id}\r")
            continue
        body = msg.body.replace("\r", "")
        raw = body.encode("utf-8")
        plain += len(raw)
        if z and len(raw) > 64:
            from .fwd import lzhuf              # only the codec, not the forward module
            data = lzhuf.compress_b1(raw)
            if len(data) < len(raw):
                s.transport.write(f"//ZMSG {msg_id} {len(data)}\r")
                s.transport.write_bytes(data)
                comp += len(data)
                continue
        lines = body.split("\n")
        comp += len(raw)
        s.transport.write("".join(x + "\r" for x in [f"//MSG {msg_id} {len(lines)}", *lines]))
    s.transport.write("//GEND\r")
    log.info("%s > //GET %s: %d bytes text, %d on air", s.call, ids, plain, comp)


def _send(s: Session, parts: list[str]) -> None:
    from .commands import SEND_RE
    args = {k.lower(): v for k, _, v in (p.partition("=") for p in parts[3:]) if v}
    n = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else -1
    if len(parts) < 3 or parts[0].upper() not in ("P", "B") or not 0 <= n <= MAX_SEND_LINES:
        s.out("//ERR send usage")      # without a valid count we cannot skip the text
        return
    kind, target = parts[0].upper(), parts[1]

    def done(lines: list[str]) -> None:
        m = SEND_RE.match(target + (f" ${args['bid']}" if args.get("bid") else ""))
        mid = args.get("mid", "")
        if m is None or (mid and not MID_RE.match(mid)):
            s.out("//ERR send invalid_value")
            return
        try:
            msg_id = s.service.create(
                from_call=s.call, to_call=m.group("to"), type=kind, subject=lines[0],
                body="\n".join(lines[1:]), origin=s.origin, at_addr=m.group("at") or "",
                bid=m.group("bid"), msgid=f"tbc-{mid}" if mid else None)
        except ServiceError as exc:
            s.out(f"//ERR send {exc.code} {exc}".rstrip())
            return
        s.out(f"//SENT {msg_id}")

    s.collect(n + 1, done)


def _kill(s: Session, parts: list[str]) -> None:
    ids = _ids(parts)
    if ids is None:
        s.out("//ERR kill", "//KEND")
        return
    rows = []
    for msg_id in ids:
        msg = s.service.store.get(msg_id)
        if msg is None:
            rows.append(f"//K {msg_id} ok")          # already gone: fine for the client
            continue
        if msg.type != "P":
            rows.append(f"//K {msg_id} not_allowed")  # bulletins are deleted only locally
            continue
        try:
            s.service.delete(msg_id, s.call, False)
            rows.append(f"//K {msg_id} ok")
        except ServiceError as exc:
            rows.append(f"//K {msg_id} {exc.code}")
    s.out(*rows, "//KEND")


def _read(s: Session, parts: list[str]) -> None:
    for msg_id in _ids(parts) or []:
        try:
            s.service.read(msg_id, s.call, False)
        except ServiceError:
            pass
    s.out("//REND")


def _write(s: Session, rows: list[str], summary: str) -> None:
    """Many header lines: written in one go, one line in the monitor log."""
    s.transport.write("".join(r + "\r" for r in rows))
    log.info("%s > %s", s.call, summary)
