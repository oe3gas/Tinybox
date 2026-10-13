"""Offline mailbox of the TinyBox client (PLANUNG.md 12.8, C3).

Commands of a client session with the cap SYNC. Every answer ends with an
end line, so the client knows when it is complete. Lines are plain text;
only the message texts may come compressed (cap Z, radio only).

    //MLIST [after=<id>] [max=<n>]   own personal mail (to or from me), oldest first
        -> //M <header> ... //MEND <n> <more>      more = headers left after max
    //RUBRICS                   bulletin rubrics with count and highest number
        -> //RU <rubric> <count> <max id> ... //RUEND
           with [rubrics] in tinybox.conf (CR19) also the accepted rubrics
           without bulletins (0 0), and before //RUEND:
           //RU <rubric> : <description>     one per accepted rubric with a text
           //RU + ALL WX ...                 where users may write, in the sysop's order
           (old clients take only lines with 4 fields and a number - they skip these)
    //BLIST <rubric>=<after> ... [max=<n>]  bulletins newer than <after>, oldest first
        -> //M <header> ... //MEND <n> <more>
    //GET <id> [<id> ...]       message texts (at most MAX_GET)
        -> //MSG <id> <n lines> + n lines        plain text
           //ZMSG <id> <n bytes> + n bytes       LZHUF (as FBB B1: CRC + length + data)
           //NOMSG <id>                          gone or not yours
           //GEND
    //PART <id> <offset> <max bytes>   a piece of one long text (cap Z, radio):
        -> //P <id> <Z|T> <offset> <total> <n> + n bytes     (or //NOMSG <id>)
           Z = piece of the LZHUF data, T = piece of the UTF-8 text. The client
           asks piece by piece with pauses, so a long text never blocks the channel.
    //SEND <P|B> <to>[,<to>...][@<at>] <n> [mid=<id>] [bid=<bid>]
        + subject line + n text lines (sent without waiting)
        -> //SENT <id> [<id> ...]  or  //ERR send <reason>
        CR27: several recipients = one message each (same text, own number and
        MID); the text goes over the air once. Nothing is stored if one of the
        recipients is invalid.
    //KILL <id> ...             delete own mail  -> //K <id> ok|<reason> ... //KEND
    //READ <id> ...             read in the client -> status Y   -> //REND

Header:  <id> <P|B> <N|Y> <fwd|-> <size> <from> <to> <at|-> <bid|-> <unix time> <subject>

mid= is a unique id made by the client: if the //SENT answer got lost and the
client sends the same message again, the TinyBox answers with the old number
instead of storing it twice.

Delta sync (cap SYNC2, CR26, PLANUNG.md 12.9) - one request for everything,
only what changed since the client's last sync (change counter seq, store.py):

    //SYNC seq=<n> [k=<id>,..] [r=<id>,..] [max=<bytes>] [want=<bytes>]
        -> //K <id> ok|<reason>          for k= (own mail deleted here)
           //M <header>                  new or content changed since n
           //S <id> <N|Y> <fwd|->        only status/flag changed since n
           //D <id> <id> ...             deleted (or no longer visible) since n
           //MSG <id> <n lines> + lines  texts of new mail, oldest first, up to want= bytes
           //SYNCEND <more> seq=<m>      more = headers left (ask again with seq=<m>)
        r= marks mail read (status Y), no answer line. seq=0 = everything.
        //ERR seq: the TinyBox cannot serve this seq (database newer than the
        client, or tombstones purged): the client starts over with seq=0.
    //BSYNC seq=<n> h=<hash> <rubric>=<after> ... [max=<bytes>] [want=<bytes>]
        -> //RL <rubric> ...             (only if the list changed: h= differs)
           //RU <rubric> : <description> (only then)
           //RU + <rubric> ...           (only then; where users may write)
           //RN <rubric>=<count> ...     bulletins per rubric (always, one line)
           //M <header>                  bulletins of the given rubrics with a higher
                                         number, or content replaced since n
                                         (n=0: only the number counts, the client
                                         knows no seq yet and its after= is right)
           //D <id> ...                  deleted in these rubrics since n
           //MSG ...                     texts up to want=
           //BSYNCEND <more> seq=<m> h=<hash>
        more > 0: ask again with seq=<m> and the after= grown by this page. Every
        page moves after= or seq= on, so the exchange always comes to an end.
    With cap Z (radio) an answer over ZSYNC_MIN bytes comes as one LZHUF block:
        //ZSYNC <n bytes> + n bytes      containing the text lines above (all plain)
"""

from __future__ import annotations

import logging
import re
import time
import zlib
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from . import logsetup
from .config import base_call
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
COMMANDS = ("MLIST", "RUBRICS", "BLIST", "GET", "PART", "SEND", "KILL", "READ",
            "SYNC", "BSYNC")
MAX_PART = 8192
ZSYNC_MIN = 200           # a delta answer this long goes as one LZHUF block (cap Z)
HEADER_BYTES = 90         # rough size of one //M line, for paging by max=


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
    if cmd in ("SYNC", "BSYNC") and "SYNC2" not in s.client.caps:
        s.out(f"//ERR {cmd} needs SYNC2")
        return
    started = time.monotonic()
    {"MLIST": _mlist, "RUBRICS": _rubrics, "BLIST": _blist, "GET": _get, "PART": _part,
     "SEND": _send, "KILL": _kill, "READ": _read, "SYNC": _sync, "BSYNC": _bsync}[cmd](s, parts)
    slow = logsetup.ms_if_slow(started)
    if slow:
        log.debug("//%s took %s", cmd, slow)


def _paging(parts: list[str]) -> tuple[list[str], int, int | None] | None:
    """Takes after=/max= out of parts. Returns (rest, after, max) or None."""
    rest, after, limit = [], 0, None
    for p in parts:
        key, sep, value = p.partition("=")
        if sep and key in ("after", "max"):     # lower case: a rubric may be called MAX
            if not value.isdigit():
                return None
            if key == "after":
                after = int(value)
            else:
                limit = max(1, int(value))
        else:
            rest.append(p)
    return rest, after, limit


def _page(s: Session, msgs: list[Message], limit: int | None, what: str) -> None:
    msgs = sorted(msgs, key=lambda m: m.id)
    more = 0 if limit is None else max(0, len(msgs) - limit)
    rows = [header(m) for m in (msgs if limit is None else msgs[:limit])]
    _write(s, rows + [f"//MEND {len(rows)} {more}"], f"//{what}: {len(rows)} header(s)")


def _visible(s: Session) -> list[Message]:
    return s.service.list_for(s.call, sysop=False)


def _mlist(s: Session, parts: list[str]) -> None:
    pg = _paging(parts)
    if pg is None:
        s.out("//ERR mlist")
        return
    _, after, limit = pg
    _page(s, [m for m in _visible(s) if m.type == "P" and m.id > after], limit, "MLIST")


def _rubric_counts(s: Session) -> dict[str, list[int]]:
    """rubric -> [count, highest id] of the bulletins the caller may see, plus the
    writable rubrics without bulletins (0 0)."""
    count: dict[str, list[int]] = {}
    for m in _visible(s):
        if m.type == "B":
            c = count.setdefault(m.to_call, [0, 0])
            c[0] += 1
            c[1] = max(c[1], m.id)
    for name in s.service.writable_rubrics():   # empty: no [rubrics], every rubric is free
        count.setdefault(name, [0, 0])
    return count


def _rubric_static(s: Session, names: list[str]) -> list[str]:
    """Descriptions and writable rubrics: the part of the list that rarely changes."""
    svc = s.service
    writable = svc.writable_rubrics()
    rows = []
    for name in writable:
        desc = " ".join(svc.rubric_description(name).split())
        if desc:
            rows.append(f"//RU {name} : {desc}")
    if writable:
        rows.append("//RU + " + " ".join(writable))
    return rows


def _rubrics(s: Session, parts: list[str]) -> None:
    count = _rubric_counts(s)
    rows = [f"//RU {r} {n} {mx}" for r, (n, mx) in sorted(count.items())]
    s.out(*rows, *_rubric_static(s, sorted(count)), "//RUEND")


def _blist(s: Session, parts: list[str]) -> None:
    pg = _paging(parts)
    after: dict[str, int] = {}
    for p in pg[0] if pg else ["?"]:
        m = RUBRIC_RE.match(p.upper())
        if not m:
            s.out("//ERR blist")
            return
        after[m.group(1)] = int(m.group(2))
    _page(s, [m for m in _visible(s)
              if m.type == "B" and m.to_call in after and m.id > after[m.to_call]],
          pg[2], "BLIST")


def payload(body: str, z: bool) -> tuple[str, bytes]:
    """What goes on air for one text: ('Z', LZHUF data) if that is smaller,
    else ('T', UTF-8 text)."""
    raw = body.replace("\r", "").encode("utf-8")
    if z and len(raw) > 64:
        from .fwd import lzhuf              # only the codec, not the forward module
        data = lzhuf.compress_b1(raw)
        if len(data) < len(raw):
            return "Z", data
    return "T", raw


def _part(s: Session, parts: list[str]) -> None:
    if ("Z" not in s.client.caps or not hasattr(s.transport, "write_bytes")
            or len(parts) != 3 or not all(p.isdigit() for p in parts)):
        s.out("//ERR part")
        return
    msg_id, offset, size = (int(p) for p in parts)
    msg = s.service.store.get(msg_id)
    if msg is None or not s.service.can_see(msg, s.call, False):
        s.out(f"//NOMSG {msg_id}")
        return
    kind, data = payload(msg.body, True)
    piece = data[offset:offset + min(max(size, 1), MAX_PART)]
    s.transport.write(f"//P {msg_id} {kind} {offset} {len(data)} {len(piece)}\r")
    s.transport.write_bytes(piece)
    log.info("> //PART %d: %d-%d of %d bytes (%s)", msg_id, offset,
             offset + len(piece), len(data), kind)


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
        kind, data = payload(body, z)
        plain += len(body.encode("utf-8"))
        if kind == "Z":
            s.transport.write(f"//ZMSG {msg_id} {len(data)}\r")
            s.transport.write_bytes(data)
            comp += len(data)
            continue
        raw = data
        lines = body.split("\n")
        comp += len(raw)
        s.transport.write("".join(x + "\r" for x in [f"//MSG {msg_id} {len(lines)}", *lines]))
    s.transport.write("//GEND\r")
    log.info("> //GET %s: %d bytes text, %d on air", ids, plain, comp)


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
        ids = []
        try:
            tos = s.service.check_send_list(s.call, m.group("to"), kind, False, m.group("bid"))
            body = s.service.multi_to_line(tos) + "\n".join(lines[1:])
            for to in tos:
                # the same mid sent again answers with the old numbers (see above);
                # a single recipient keeps the old msgid form
                msgid = (f"tbc-{mid}" if len(tos) == 1 else f"tbc-{mid}-{to}") if mid else None
                ids.append(s.service.create(
                    from_call=s.call, to_call=to, type=kind, subject=lines[0],
                    body=body, origin=s.origin, at_addr=m.group("at") or "",
                    bid=m.group("bid"), msgid=msgid))
        except ServiceError as exc:
            if not ids:
                s.out(f"//ERR send {exc.code} {exc}".rstrip())
                return
        s.out("//SENT " + " ".join(map(str, ids)))

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


# --- delta sync (SYNC2) -------------------------------------------------------------

def _sync_args(parts: list[str]) -> tuple[dict[str, str], list[str]] | None:
    """key=value arguments (lower case keys) and the rest. None on a bad number."""
    args, rest = {}, []
    for p in parts:
        key, sep, value = p.partition("=")
        if sep and key in ("seq", "max", "want", "h", "k", "r"):
            if key in ("seq", "max", "want") and not value.isdigit():
                return None
            args[key] = value
        else:
            rest.append(p)
    return args, rest


def _seq_ok(s: Session, seq: int) -> bool:
    """False: the TinyBox cannot tell what changed since seq (client starts over)."""
    store = s.service.store
    if seq > store.sync_seq():                   # the database was set up anew
        return False
    return seq == 0 or seq >= store.gone_floor()


class _Answer:
    """Collects the lines of a delta answer; texts are pushed while want= allows."""

    def __init__(self, s: Session, args: dict[str, str]) -> None:
        self.s = s
        self.rows: list[str] = []
        self.texts: list[Message] = []
        self.limit = int(args["max"]) if "max" in args else None
        self.want = int(args.get("want", "0"))
        self.z = "Z" in s.client.caps and hasattr(s.transport, "write_bytes")

    def push_texts(self, msgs: list[Message]) -> None:
        """Texts of new messages, oldest first, while they fit into want= bytes.
        Mail the caller wrote himself is skipped (the client has the text)."""
        left = self.want
        for m in sorted(msgs, key=lambda m: m.id):
            if m.size > left or m.size == 0 or m.from_call.upper() == self.s.call.upper():
                continue
            self.texts.append(m)
            left -= m.size

    def send(self, end: str, summary: str) -> None:
        s = self.s
        text_rows = []
        for m in self.texts:
            lines = m.body.replace("\r", "").split("\n")
            text_rows += [f"//MSG {m.id} {len(lines)}", *lines]
        rows = self.rows + text_rows + [end]
        plain = "".join(r + "\r" for r in rows)
        raw = plain.encode("utf-8")
        if self.z and len(raw) > ZSYNC_MIN:
            from .fwd import lzhuf
            data = lzhuf.compress_b1(raw)
            if len(data) < len(raw):
                s.transport.write(f"//ZSYNC {len(data)}\r")
                s.transport.write_bytes(data)
                log.info("%s > %s: %d bytes, %d on air (Z)", s.call, summary, len(raw), len(data))
                return
        if self.z and self.texts:                    # single texts compressed as in //GET
            rows = self.rows[:]
            s.transport.write("".join(r + "\r" for r in rows))
            for m in self.texts:
                body = m.body.replace("\r", "")
                kind, data = payload(body, True)
                if kind == "Z":
                    s.transport.write(f"//ZMSG {m.id} {len(data)}\r")
                    s.transport.write_bytes(data)
                else:
                    lines = body.split("\n")
                    s.transport.write("".join(x + "\r" for x in [f"//MSG {m.id} {len(lines)}",
                                                                 *lines]))
            s.transport.write(end + "\r")
            log.info("%s > %s: %d bytes", s.call, summary, len(raw))
            return
        s.transport.write(plain)
        log.info("%s > %s: %d bytes", s.call, summary, len(raw))


def _page_by_bytes(rows: list[tuple[int, str, Message | None]], limit: int | None
                   ) -> tuple[list[tuple[int, str, Message | None]], int]:
    """rows: (seq, line, message or None) in seq order. Cuts after about `limit`
    bytes (never in the middle of a seq). Returns (page, rows left)."""
    if limit is None:
        return rows, 0
    size, page = 0, []
    for i, row in enumerate(rows):
        size += len(row[1]) + 1
        if size > limit and page and row[0] != page[-1][0]:
            return page, len(rows) - i
        page.append(row)
    return page, 0


def _sync(s: Session, parts: list[str]) -> None:
    parsed = _sync_args(parts)
    if parsed is None or "seq" not in parsed[0]:
        s.out("//ERR sync")
        return
    args, _ = parsed
    seq = int(args["seq"])
    if not _seq_ok(s, seq):
        s.out("//ERR seq")
        return
    ans = _Answer(s, args)
    svc, store = s.service, s.service.store
    kills = _ids(args["k"].split(",")) if args.get("k") else []
    reads = _ids(args["r"].split(",")) if args.get("r") else []
    for msg_id in kills or []:
        msg = store.get(msg_id)
        if msg is None:
            ans.rows.append(f"//K {msg_id} ok")
        elif msg.type != "P":
            ans.rows.append(f"//K {msg_id} not_allowed")
        else:
            try:
                svc.delete(msg_id, s.call, False)
                ans.rows.append(f"//K {msg_id} ok")
            except ServiceError as exc:
                ans.rows.append(f"//K {msg_id} {exc.code}")
    for msg_id in reads or []:
        try:
            svc.read(msg_id, s.call, False)
        except ServiceError:
            pass
    known = set(kills or []) | set(reads or [])
    me = base_call(s.call)

    def mine(to: str, frm: str) -> bool:
        return base_call(to) == me or base_call(frm) == me

    rows: list[tuple[int, str, Message | None]] = []
    for m in store.changed_since(seq):
        if m.type != "P" or not mine(m.to_call, m.from_call) or m.id in known:
            continue
        if not svc.can_see(m, s.call, False):
            rows.append((m.seq, f"//D {m.id}", None))
        elif m.cseq > seq:
            rows.append((m.seq, header(m), m))
        else:
            rows.append((m.seq, f"//S {m.id} {m.status} {m.fwd or '-'}", None))
    for msg_id, gseq, typ, to, frm in (store.gone_since(seq) if seq else []):   # 0: knows nothing
        if typ == "P" and mine(to, frm) and msg_id not in known:
            rows.append((gseq, f"//D {msg_id}", None))
    rows.sort(key=lambda r: r[0])
    page, more = _page_by_bytes(rows, ans.limit)
    _emit(ans, page)
    end_seq = page[-1][0] if more else store.sync_seq()
    ans.send(f"//SYNCEND {more} seq={end_seq}",
             f"//SYNC seq={seq}: {len(page)} change(s), {len(ans.texts)} text(s)")


def _emit(ans: _Answer, page: list[tuple[int, str, Message | None]]) -> None:
    """Header/status lines into the answer; //D ids joined into one line."""
    gone = []
    new = []
    for _, line, m in page:
        if line.startswith("//D "):
            gone.append(line[4:])
        else:
            ans.rows.append(line)
        if m is not None:
            new.append(m)
    if gone:
        ans.rows.append("//D " + " ".join(gone))
    ans.push_texts(new)


def _bsync(s: Session, parts: list[str]) -> None:
    parsed = _sync_args(parts)
    if parsed is None or "seq" not in parsed[0]:
        s.out("//ERR bsync")
        return
    args, rest = parsed
    seq = int(args["seq"])
    if not _seq_ok(s, seq):
        s.out("//ERR seq")
        return
    after: dict[str, int] = {}
    for p in rest:
        m = RUBRIC_RE.match(p.upper())
        if not m:
            s.out("//ERR bsync")
            return
        after[m.group(1)] = int(m.group(2))
    ans = _Answer(s, args)
    store = s.service.store
    count = _rubric_counts(s)
    names = sorted(count)
    static = _rubric_static(s, names)
    ident = "\n".join(static + [" ".join(names)])
    h = f"{zlib.crc32(ident.encode('utf-8')) & 0xFFFF:04x}"
    if args.get("h") != h:
        ans.rows.append("//RL " + " ".join(names))
        ans.rows += static
    ans.rows.append("//RN " + " ".join(f"{r}={c[0]}" for r, c in sorted(count.items())))
    # Two kinds of bulletins, each with its own marker for the next round:
    #   backlog  what the client has never seen (id > after=), in id order. Its
    #            after= grows with every page, so the backlog shrinks by itself.
    #   changed  what it has, with the content replaced after seq. Only its own
    #            seq says anything here: with seq=0 the client knows nothing
    #            about seq, and its after= is the whole truth.
    # The backlog goes first, the changed ones behind it in cseq order, so that
    # every page moves one of the two markers on. Without that the client asks
    # again with the very same request - for ever.
    backlog, changed = [], []
    for m in _visible(s):
        if m.type != "B" or m.to_call not in after:
            continue
        if m.id > after[m.to_call]:
            backlog.append(m)
        elif seq and m.cseq > seq:
            changed.append(m)
    backlog.sort(key=lambda m: m.id)
    changed.sort(key=lambda m: m.cseq)
    order = backlog + changed
    page, more = _page_by_bytes([(i, header(m), m) for i, m in enumerate(order)], ans.limit)
    gone = [str(i) for i, _, typ, to, _ in (store.gone_since(seq) if seq else [])
            if typ == "B" and to in after]
    if gone:
        ans.rows.append("//D " + " ".join(gone))
    for _, line, _ in page:
        ans.rows.append(line)
    ans.push_texts([m for _, _, m in page if m is not None])
    if not more:
        end_seq = store.sync_seq()
    elif len(page) > len(backlog):            # changed ones went out as well
        end_seq = order[len(page) - 1].cseq   # everything up to here is through
    else:
        end_seq = seq                         # still in the backlog: after= moves on
    ans.send(f"//BSYNCEND {more} seq={end_seq} h={h}",
             f"//BSYNC seq={seq}: {len(page)} header(s), {len(ans.texts)} text(s)")


def _write(s: Session, rows: list[str], summary: str) -> None:
    """Many header lines: written in one go, one line in the monitor log."""
    s.transport.write("".join(r + "\r" for r in rows))
    log.info("%s > %s", s.call, summary)
