"""The chat board the client is in: join and leave, history, MOTD, members, events.
Part of ClientCore (Refactoring R2): a mixin, so the methods keep working on the core's
state; tbclient/core.py puts the parts together."""

from __future__ import annotations

import asyncio
import logging
import re
import time

from prcore import chatimg               # the image reference in a chat line (CR12)
from prcore.text import isnum

from . import proto

log = logging.getLogger(__name__)

MAX_MESSAGES = 300        # chat lines kept per board
MAX_GAP = 32              # event numbers missed at most before they are asked again


class BoardMixin:
    HIST_MODES = ("missed", "none", "10", "20")

    HIST_MISSED_MAX = 20

    def join(self, n: int) -> bool:
        if not self.handshake_done or not any(b["n"] == n for b in self.boards):
            return False
        self.send_line(f"/J {n}" if self.board else f"C {n}")
        self._joining, self._early = n, []
        return True

    @property
    def history_mode(self) -> str:
        m = self.settings.get("history", "missed")
        return m if m in self.HIST_MODES else "missed"

    def set_history_mode(self, mode: str) -> bool:
        if mode not in self.HIST_MODES:
            return False
        self.settings["history"] = mode
        self.save_settings()
        self.changed()
        return True

    def _history_on_join(self, in_line: str) -> None:
        """//IN ... hist=<n> last=<unix> now=<unix>: ask for the history the way the
        user wants it. A TinyBox without hist= sends the history by itself."""
        args = dict(re.findall(r"\b(hist|last|now)=(\d+)", in_line))
        if "hist" not in args:
            return
        if "now" in args:
            self.clock_off = int(args["now"]) - int(time.time())
        count, last = int(args["hist"]), int(args.get("last", 0))
        self.board.update(hist=count, hist_last=last, older=count, loading=False)
        mode = self.history_mode
        if not count or mode == "none":
            return
        if mode == "missed":
            since = self.tset.get("seen", {}).get(self.board["name"])
            if since and last <= since:
                return                                    # nothing new since the last visit
            self._ask_history(self.HIST_MISSED_MAX, since=since)
        else:
            self._ask_history(int(mode))

    @staticmethod
    def _img_limit(in_line: str) -> int:
        """//IN ... img | img=<hex>: images allowed here, max bytes (0 = none, CR12)."""
        m = re.search(r"(?:^| )img(?:=([0-9a-fA-F]{1,5}))?(?= |$)", in_line)
        if not m:
            return 0
        return int(m.group(1), 16) if m.group(1) else 8192

    @staticmethod
    def _file_limit(in_line: str) -> int:
        """//IN ... file=<hex>: files allowed here, max bytes as sent (CR86)."""
        m = re.search(r"(?:^| )file=([0-9a-fA-F]{1,5})(?= |$)", in_line)
        return int(m.group(1), 16) if m else 0

    def _motd_on_join(self, in_line: str) -> None:
        """//IN ... motd=<crc> (CR3): the text is fetched only when it is new."""
        m = re.search(r"\bmotd=([0-9a-f]{4})\b", in_line)
        name = self.board["name"]
        if not m:
            self.board["motd"] = ""
            return
        known = self.tset.get("motd", {}).get(name)
        if known and known.get("crc") == m.group(1):
            self.board["motd"] = known.get("text", "")
        else:
            self.board["motd"] = ""
            self.send_line("//MOTD")

    def _add_history(self, lines: list[tuple], older: bool) -> None:
        """History lines (oldest first) into the chat. Ordered by time, always before
        the live events (ids >= 0); within the same second an older page goes in
        front of what is shown, a newer one behind it."""
        new = []
        for x in lines:                          # inclusive limits: drop what is here
            if len(x) == 3:
                x = (*x, None)
            if x[:3] not in self._hist_keys:     # (time, call, text), with or without number
                self._hist_keys.add(x[:3])
                new.append(x)
        lines = new
        if older:
            self._hist_lo -= len(lines)
            k0 = self._hist_lo
        else:
            k0 = self._hist_hi
            self._hist_hi += len(lines)
        for i, (t, call, text, qseq) in enumerate(lines):
            m = {"id": -(2 ** 50) + t * 1000 + k0 + i, "seq": -1, "kind": "line",
                 "call": call, "text": text, "time": t - self.clock_off,
                 "history": True, "srv_time": t, "reactions": {}}
            if qseq is not None:
                m["qseq"] = qseq                 # its event number: quotes find it (HSEQ)
            self._add(m)

    # --- history on request (CR13) ---------------------------------------------

    def _ask_history(self, n: int, since: int | None = None, before: int | None = None) -> None:
        self.board["loading"] = True
        self._hist_buf, self._hist_older = [], before is not None
        self.send_line(f"//HIST max={n}" + (f" since={since}" if since else "")
                   + (f" before={before}" if before else ""))

    def load_history(self, n: int) -> bool:
        """Button "load 10 / load all": older lines than the ones shown."""
        b = self.board
        if not b or "hist" not in b or b.get("loading") or not b.get("older"):
            return False
        loaded = [m["srv_time"] for m in self.messages if "srv_time" in m]
        # inclusive on the TinyBox side; lines we already have are dropped (_hist_keys)
        before = min(loaded) if loaded else (b.get("hist_last") or None)
        self._ask_history(max(1, min(n, 200)), before=before)
        self.changed()
        return True

    def leave(self) -> None:
        if self.board:
            self.send_line("/Q")

    def say(self, text: str) -> bool:
        text = text.replace("\r", " ").replace("\n", " ").strip()
        if not self.board or not text or text.startswith("/"):
            return False
        self.send_line(text[:200])
        self.pending.append({"text": text[:200], "at": time.time()})
        self.changed()
        return True

    def react(self, seq: int, emoji: str) -> bool:
        if not self.board or not re.match(r"^[!-~]{1,8}$", emoji) or not 0 <= seq < 256:
            return False
        self.send_line(f"/R {seq:X} {emoji}")
        # show it at once (CR8); the echo from the TinyBox confirms it
        for m in reversed(self.messages):
            if m.get("seq") == seq and m["kind"] == "line":
                calls = m["reactions"].setdefault(emoji, [])
                if self.cfg.mycall not in calls:
                    calls.append(self.cfg.mycall)
                    self.pending_reacts[(seq, emoji)] = time.time()
                break
        self.changed()
        return True

    # --- the lines of the TinyBox about boards (tbclient/core.py _CONTROL) --------------

    def _c_board(self, cmd: str, rest: str, line: str) -> None:
        parts = rest.split(" ", 4)
        if len(parts) >= 4 and isnum(parts[0]):
            if self._boards_tmp is None:
                self._boards_tmp = []
            self._boards_tmp.append({"n": int(parts[0]), "name": parts[1], "keep": parts[2],
                                     "users": int(parts[3]) if isnum(parts[3]) else 0,
                                     "desc": parts[4] if len(parts) > 4 else ""})

    def _c_boards_end(self, cmd: str, rest: str, line: str) -> None:
        self.boards = self._boards_tmp or []
        self._boards_tmp = None
        last = self.tset.get("board")
        if self.board is None and any(b["n"] == last for b in self.boards) \
                and not self.sync.own_connect:   # a sync-only connection stays out
            self.join(last)                  # back into the last board

    def _c_in(self, cmd: str, rest: str, line: str) -> None:
        parts = rest.split()
        # CR98: "//IN <n> <name> <keep> <last hex|->" - anything else is not a join
        if len(parts) >= 4 and isnum(parts[0]) and \
                (parts[3] == "-" or re.fullmatch(r"[0-9A-Fa-f]{1,4}", parts[3])):
            self._clear_board()
            self.board = {"n": int(parts[0]), "name": parts[1], "keep": parts[2],
                          "img": self._img_limit(rest), "file": self._file_limit(rest)}
            self._history_on_join(rest)
            self._motd_on_join(rest)
            last = None if parts[3] == "-" else int(parts[3], 16)
            self.unwrap.reset(last)
            early = self._early if self._joining == self.board["n"] else []
            self._joining, self._early = None, []
            if early:     # after the //H and //WHO lines, which come next
                asyncio.get_event_loop().call_soon(self._replay_early, early, last)
            if self.tset.get("board") != self.board["n"]:
                self.tset["board"] = self.board["n"]
                self.save_settings()

    def _c_hist(self, cmd: str, rest: str, line: str) -> None:
        # HSEQ: "//H <unix> #<n> <call>: <text>" - the event number for quotes
        m = re.match(r"^(\d+) (?:#([0-9A-F]{1,2}) )?([A-Z0-9-]+): ?(.*)$", rest)
        if m and self.board:
            line = (int(m.group(1)), m.group(3), m.group(4),
                    int(m.group(2), 16) if m.group(2) else None)
            if self._hist_buf is not None:
                self._hist_buf.append(line)          # answer to //HIST: until //HEND
            else:
                self._add_history([line], older=False)   # older TinyBox: right away

    def _c_hist_end(self, cmd: str, rest: str, line: str) -> None:
        p = rest.split()
        if self.board and len(p) == 2 and isnum(p[1]):
            self._add_history(self._hist_buf or [], older=self._hist_older)
            self._hist_buf = None
            self.board["older"] = int(p[1])
            self.board["loading"] = False

    def _c_motd(self, cmd: str, rest: str, line: str) -> None:
        crc, _, text = rest.partition(" ")
        if self.board:
            motds = self.tset.setdefault("motd", {})
            if crc == "-":
                motds.pop(self.board["name"], None)
            else:
                motds[self.board["name"]] = {"crc": crc, "text": text}
            self.save_settings()
            self.board["motd"] = text if crc != "-" else ""
            self.changed()

    def _c_who(self, cmd: str, rest: str, line: str) -> None:
        """//WHO - 'n call[=sym] ...' (NUM) or 'call[=sym] ...'"""
        num = 0
        for item in rest.split():
            if isnum(item):
                num = int(item)
                continue
            call, _, sym = item.partition("=")
            self.members[call] = sym
            if num:
                self._set_number(num, call)
                num = 0
        self.profiles.want(self.members)         # CR73: names and locators

    def _c_out(self, cmd: str, rest: str, line: str) -> None:
        self._clear_board()
        self.tset.pop("board", None)
        self.save_settings()

    def _replay_early(self, events: list[proto.Event], last: int | None) -> None:
        for ev in events:
            if last is None or 0 < (ev.seq - last) % 256 < 128:
                self._event(ev)
        self.changed()

    def _clear_board(self) -> None:
        if self.board:                       # everything up to now was seen (CR13)
            seen = self.tset.setdefault("seen", {})
            seen[self.board["name"]] = int(time.time()) + self.clock_off
            self.save_settings()
        self._hist_keys = set()
        self._hist_buf, self._hist_lo, self._hist_hi = None, 0, 0
        self.prefix.clear()                          # CR123: the game belongs to the board
        self.board = None
        self.members = {}
        self.numbers = {}
        self.quality = {}
        self.linkq = {}
        self.messages = []
        self.uploads = {}
        self.seen = set()
        self.unwrap = proto.Unwrapper()
        self.pending_reacts = {}

    def _event(self, ev: proto.Event) -> None:
        if not self.board:
            return
        before = self.unwrap.last
        pos = self.unwrap.unwrap(ev.seq)
        if pos in self.seen:
            return                                   # UI + I-frame, or a resend
        self.seen.add(pos)
        if before is not None and pos > before + 1 and not self.prefix.watching():
            # CR128: while others play, the game events are not for us - a gap then is
            # no loss (a chat line lost in that time is not fetched again)
            first, last = (before + 1) % 256, (pos - 1) % 256
            if pos - before - 1 <= MAX_GAP:
                self.send_line(f"//RESEND {first:X}-{last:X}")
            else:                 # too many to fetch: only tell, for the receive quote
                self.send_line(f"//LOST {first:X}-{last:X}")
        now = int(time.time())
        if ev.kind == "line":
            self._add({"id": pos, "seq": ev.seq, "kind": "line", "call": ev.call,
                       "text": ev.text, "time": now, "reactions": {}})
            if chatimg.parse_ref(ev.text):          # the picture is here: no "uploading"
                self.uploads.pop(ev.call, None)
            if ev.call == self.cfg.mycall:
                for p in self.pending:
                    if p["text"] == ev.text:
                        self.pending.remove(p)
                        break
        elif ev.kind == "join":
            self.members[ev.call] = ev.symbol
            self.profiles.want([ev.call])
            if ev.num:
                self._set_number(ev.num, ev.call)
            item = {"id": pos, "seq": ev.seq, "kind": "join", "call": ev.call, "time": now}
            if ev.symbol == proto.TERMINAL_SYM:          # CR120: the others should know
                item["terminal"] = True
            self._add(item)
        elif ev.kind == "symbol":                    # nothing to show, only the avatars
            call = ev.call or self.numbers.get(ev.num, "")
            if call in self.members:
                self.members[call] = ev.symbol
        elif ev.kind == "leave":
            call = ev.call or self.numbers.pop(ev.num, "")
            if not call:
                return                               # number unknown: nothing to remove
            self.numbers = {n: c for n, c in self.numbers.items() if c != call}
            self.members.pop(call, None)
            self.quality.pop(call, None)
            self.linkq.pop(call, None)
            self._add({"id": pos, "seq": ev.seq, "kind": "leave", "call": call, "time": now})
        elif ev.kind == "react":
            for m in reversed(self.messages):
                if m.get("seq") == ev.ref and m["kind"] == "line":
                    calls = m["reactions"].setdefault(ev.text, [])
                    if ev.call not in calls:
                        calls.append(ev.call)
                    break
            if ev.call == self.cfg.mycall:
                self.pending_reacts.pop((ev.ref, ev.text), None)
        elif ev.kind == "upload":                    # CR30: a picture is going up
            if ev.call != self.cfg.mycall:
                self.uploads[ev.call] = {"size": ev.ref, "at": now, "got": 0}
        elif ev.kind == "quality":                   # bars next to the avatars (14.4)
            self.quality = {}
            for who, b in (ev.bars or {}).items():
                call = self.numbers.get(who, "") if isinstance(who, int) else who
                if call:
                    self.quality[call] = b
        elif ev.kind == "system":
            pr = self.prefix.event(ev.text)              # CR123: Prefix raten
            item = {"id": pos, "seq": ev.seq, "kind": "system", "text": ev.text, "time": now}
            if pr:
                item["pr"] = True
                if self.prefix.watching():               # CR128: not for spectators' eyes
                    item["pr_watch"] = True
            self._add(item)

    def _set_number(self, num: int, call: str) -> None:
        """Member numbers are reused: a new holder pushes the old one out."""
        self.numbers = {n: c for n, c in self.numbers.items() if c != call and n != num}
        self.numbers[num] = call

    def _qstat(self, line: str) -> None:
        """%Q: the numbers behind the bars of every member with data (CR33)."""
        stats = proto.parse_qstat(line)
        if stats is None:
            return
        self.linkq = {}
        for num, rec in stats.items():
            call = self.numbers.get(num)
            if call:
                rec = dict(rec, call=call, at=int(time.time()))
                self.linkq[call] = rec
                self.quality[call] = rec["bars"]       # the bars come with it
        self.changed()

    def _add(self, msg: dict) -> None:
        self.chan.act_n += 1                     # CR45: the chip blinks in the background
        self.messages.append(msg)
        self.messages.sort(key=lambda m: m["id"])
        del self.messages[:-MAX_MESSAGES]

    def _expire_reacts(self, now: float) -> None:
        """Own reactions that never came back within 2 min are taken back."""
        for (seq, emoji), at in list(self.pending_reacts.items()):
            if now - at < 120:
                continue
            del self.pending_reacts[(seq, emoji)]
            for m in reversed(self.messages):
                if m.get("seq") == seq and m["kind"] == "line":
                    calls = m["reactions"].get(emoji, [])
                    if self.cfg.mycall in calls:
                        calls.remove(self.cfg.mycall)
                    if not calls:
                        m["reactions"].pop(emoji, None)
                    break

    def symbol_of(self, call: str) -> str:
        if call == self.cfg.mycall and self.my_symbol:
            return self.my_symbol
        sym = self.members.get(call)
        if sym == proto.TERMINAL_SYM:                    # CR120: a marker, no APRS symbol
            sym = ""
        return sym or self.heard.get(call, "")

    def terminal_members(self) -> list[str]:
        """CR120: the members without a TinyBox client (they see the chat as text)."""
        return sorted(c for c, s in self.members.items() if s == proto.TERMINAL_SYM)
