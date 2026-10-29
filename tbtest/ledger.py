"""What was sent, what must arrive - and what did (end-to-end check).

Messages: every message carries a marker line with its key and the checksum of
the rest of the text:

    TBTEST <key> <sha>          key = <run>-<call>-<n>, e.g. k3f-OE1TBA-7

The reader recomputes the checksum. Personal mail must reach its addressee,
bulletins (rubric TBTEST) every other user. Only keys of this run count -
older messages in the box are ignored.

Chat: every line is "tbt <key>". A user in a board must get every line sent
while he was there (with a margin at join and leave, the lines are on their
way). Pictures: the reference in the chat line carries the hash; whoever
fetches a picture compares it with what was sent.
"""

from __future__ import annotations

import hashlib
import random
import re
import time
from dataclasses import dataclass, field

MARK_RE = re.compile(r"^TBTEST (\S+) ([0-9a-f]{12})\s*$")
CHAT_RE = re.compile(r"\btbt (\S+-\S+-c\d+)")
MARGIN = 2.0                 # seconds after join / before leave a line may still miss

WORDS = ("antenna dipole yagi feeder balun coax ladder line ground radial vertical loop "
         "packet radio node digipeater mailbox bulletin forward beacon frequency band "
         "propagation skip sunspot aurora contest log qsl report signal noise filter "
         "modem tnc kiss direwolf agw frame window retry ack timer channel duplex "
         "relay repeater crystal oscillator mixer amplifier tube transistor solder "
         "morse key paddle sidetone weather station locator square grid sota pota").split()

SIZES = (60, 250, 800, 2000, 4000, 7000)      # body sizes in bytes (max_msg_bytes 8192)


def norm(text: str) -> str:
    """The text as it may come back: line ends, trailing blanks, empty last lines."""
    lines = [ln.rstrip() for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lines).strip("\n")


def checksum(text: str) -> str:
    return hashlib.sha256(norm(text).encode("utf-8")).hexdigest()[:12]


def make_body(rng: random.Random, key: str, size: int) -> str:
    lines, n = [], 0
    while n < size:
        line = " ".join(rng.choice(WORDS) for _ in range(rng.randint(3, 11)))
        line = line[:1].upper() + line[1:] + "."
        lines.append(line)
        n += len(line) + 1
    text = "\n".join(lines)
    return f"TBTEST {key} {checksum(text)}\n{text}"


def check_body(body: str) -> tuple[str | None, bool]:
    """(key, checksum right) of a message text; key None = no testbed message."""
    text = norm(body)
    first, _, rest = text.partition("\n")
    m = MARK_RE.match(first)
    if m is None:
        # the marker may follow other lines (e.g. a "To:" line of a multi-address mail)
        for i, line in enumerate(text.split("\n")):
            m = MARK_RE.match(line)
            if m:
                rest = "\n".join(text.split("\n")[i + 1:])
                break
        else:
            return None, False
    return m.group(1), checksum(rest) == m.group(2)


@dataclass
class Msg:
    key: str
    sender: str
    type: str                     # P | B
    to: str                       # call or rubric
    subject: str
    body: str
    size: int
    via: str                      # T terminal / C client
    id: int | None = None         # number in the box
    sent_at: float = 0.0
    readers: dict = field(default_factory=dict)    # call -> True (ok) / False (corrupt)
    killed: bool = False


@dataclass
class ChatLine:
    key: str
    sender: str
    board: str
    text: str
    sent_at: float
    echo_at: float | None = None  # the sender saw it come back (clients)
    image: str = ""               # hash of a picture, if the line carries one


@dataclass
class Stay:
    board: str
    joined: float
    left: float | None = None


class Ledger:
    def __init__(self, run: str, rng: random.Random) -> None:
        self.run = run
        self.rng = rng
        self.msgs: dict[str, Msg] = {}
        self._n: dict[str, int] = {}
        self.lines: dict[str, ChatLine] = {}
        self.stays: dict[str, list[Stay]] = {}       # call -> his stays in boards
        self.heard: dict[str, dict[str, float]] = {}  # call -> chat key -> when
        self.images: dict[str, bytes] = {}            # hash -> data sent
        self.img_checks: dict[str, dict[str, bool]] = {}   # hash -> call -> ok
        self.foreign = 0                              # testbed keys of other runs seen
        self.client_calls: set[str] = set()           # clients see their own lines come back

    # --- messages --------------------------------------------------------------------

    def _next(self, call: str) -> int:
        self._n[call] = self._n.get(call, 0) + 1
        return self._n[call]

    def new_msg(self, sender: str, type: str, to: str, via: str) -> Msg:
        n = self._next(sender)
        key = f"{self.run}-{sender}-{n}"
        size = self.rng.choice(SIZES)
        body = make_body(self.rng, key, size)
        subject = f"tbt {self.run} {sender}#{n}"
        m = Msg(key, sender, type, to, subject, body, len(body.encode()), via)
        self.msgs[key] = m
        return m

    def stored(self, m: Msg, msg_id: int) -> None:
        m.id, m.sent_at = msg_id, time.monotonic()

    def is_ours(self, key: str | None) -> bool:
        return bool(key) and key.startswith(self.run + "-") and key in self.msgs

    def key_of_subject(self, subject: str) -> str | None:
        m = re.match(r"^tbt (\S+) (\S+)#(\d+)", subject.strip())
        if m is None or m.group(1) != self.run:
            return None
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    def read_by(self, call: str, body: str) -> tuple[str | None, bool]:
        """A user read a text. Returns (key, ok); key None if not ours."""
        key, ok = check_body(body)
        if key is None:
            return None, False
        if not self.is_ours(key):
            self.foreign += 1
            return None, False
        if ok and norm(body).split("\n", 1)[-1] != norm(self.msgs[key].body).split("\n", 1)[-1]:
            ok = False                                 # same checksum, other text: impossible
        self.msgs[key].readers[call] = ok
        return key, ok

    def unread_for(self, call: str) -> list[Msg]:
        """Stored messages this user still has to verify."""
        out = []
        for m in self.msgs.values():
            if m.id is None or m.killed or call in m.readers:
                continue
            if m.type == "P" and m.to == call:
                out.append(m)
            elif m.type == "B" and m.sender != call:
                out.append(m)
        return out

    def killable(self, call: str) -> list[Msg]:
        return [m for m in self.msgs.values()
                if m.type == "P" and m.to == call and m.id is not None and not m.killed
                and m.readers.get(call)]

    # --- chat ------------------------------------------------------------------------

    def chat_key(self, call: str) -> str:
        return f"{self.run}-{call}-c{self._next(call + '/c')}"

    def joined(self, call: str, board: str) -> None:
        self.stays.setdefault(call, []).append(Stay(board, time.monotonic()))

    def left(self, call: str) -> None:
        stays = self.stays.get(call)
        if stays and stays[-1].left is None:
            stays[-1].left = time.monotonic()

    def said(self, call: str, board: str, text: str, key: str, image: str = "") -> ChatLine:
        line = ChatLine(key, call, board, text, time.monotonic(), image=image)
        self.lines[key] = line
        return line

    def chat_heard(self, call: str, text: str) -> str | None:
        m = CHAT_RE.search(text)
        if m is None:
            return None
        key = m.group(1)
        line = self.lines.get(key)
        if line is None:
            return None
        now = time.monotonic()
        if call == line.sender:
            if line.echo_at is None:
                line.echo_at = now
        else:
            self.heard.setdefault(call, {}).setdefault(key, now)
        return key

    def close_stays(self) -> None:
        now = time.monotonic()
        for stays in self.stays.values():
            for s in stays:
                if s.left is None:
                    s.left = now

    # --- the result --------------------------------------------------------------------

    def verify(self, users: list[str]) -> dict:
        self.close_stays()
        p = [m for m in self.msgs.values() if m.type == "P" and m.id is not None]
        b = [m for m in self.msgs.values() if m.type == "B" and m.id is not None]
        not_stored = [m.key for m in self.msgs.values() if m.id is None]
        p_ok = [m for m in p if m.readers.get(m.to) is True]
        p_bad = [m for m in p if m.readers.get(m.to) is False]
        p_missing = [m for m in p if m.to not in m.readers]
        b_expected = sum(1 for m in b for u in users if u != m.sender)
        b_ok = sum(1 for m in b for u, ok in m.readers.items() if ok and u != m.sender)
        b_bad = [(m.key, u) for m in b for u, ok in m.readers.items() if not ok]
        b_missing = [(m.key, u) for m in b for u in users
                     if u != m.sender and u not in m.readers]
        # chat: who had to get which line
        expected, missing = 0, []
        for line in self.lines.values():
            for call, stays in self.stays.items():
                if call == line.sender:
                    continue
                inside = any(s.board == line.board and s.joined + MARGIN <= line.sent_at
                             and line.sent_at + MARGIN <= (s.left or line.sent_at)
                             for s in stays)
                if not inside:
                    continue
                expected += 1
                if line.key not in self.heard.get(call, {}):
                    missing.append((line.key, call))
        delays = sorted(t - self.lines[k].sent_at for c in self.heard.values()
                        for k, t in c.items() if k in self.lines)
        echo_missing = [ln.key for ln in self.lines.values() if ln.echo_at is None
                        and ln.sender in self.client_calls]
        img_checks = [(h, c, ok) for h, cs in self.img_checks.items() for c, ok in cs.items()]
        return {
            "private": {"stored": len(p), "ok": len(p_ok), "corrupt": [m.key for m in p_bad],
                        "missing": [m.key for m in p_missing]},
            "bulletins": {"stored": len(b), "expected_reads": b_expected, "ok": b_ok,
                          "corrupt": b_bad, "missing": b_missing},
            "not_stored": not_stored,
            "killed": sum(1 for m in self.msgs.values() if m.killed),
            "chat": {"lines": len(self.lines), "expected": expected,
                     "delivered": expected - len(missing), "missing": missing,
                     "echo_missing": echo_missing,
                     "delay_ms": _quantiles([d * 1000 for d in delays])},
            "images": {"sent": len(self.images), "checked": len(img_checks),
                       "ok": sum(1 for *_, ok in img_checks if ok),
                       "bad": [(h, c) for h, c, ok in img_checks if not ok]},
            "foreign_keys": self.foreign,
        }



def _quantiles(values: list[float]) -> dict:
    if not values:
        return {}
    v = sorted(values)
    pick = lambda q: v[min(len(v) - 1, int(q * (len(v) - 1) + 0.5))]   # noqa: E731
    return {"n": len(v), "min": round(v[0], 1), "avg": round(sum(v) / len(v), 1),
            "p95": round(pick(0.95), 1), "max": round(v[-1], 1)}
