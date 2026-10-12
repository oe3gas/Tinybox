"""Client logic: connection, handshake, chat state. The web GUI reads
snapshot() and calls the actions (connect, join, say, react ...)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections import deque
from pathlib import Path

from . import VERSION, proto
from .config import Config
from .links import AgwLink, TelnetLink
from .mailstore import MailStore
from .radio import RawFrame, aprs_symbol
from .sync import Syncer

log = logging.getLogger(__name__)

PROTO = "TB1"
HANDSHAKE_FALLBACK_SEC = 6
DIRECT_VALID_SEC = 30 * 60
MAX_MESSAGES = 300
MAX_GAP = 32
SYMBOL_RE = re.compile(r"^[/\\0-9A-Z][!-~]$")


class ClientCore:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        cls = AgwLink if cfg.link == "agw" else TelnetLink
        self.link = cls(cfg, self._on_state, self._on_line, self._on_frame)
        self.settings_path = cfg.data_dir / "settings.json"
        self.settings = self._load_settings()
        self.state = "offline"
        self.reason = ""
        self.caps: set[str] = set()
        self.handshake_done = False
        self.boards: list[dict] = []
        self._boards_tmp: list[dict] | None = None
        self.board: dict | None = None
        self.members: dict[str, str] = {}         # call -> symbol sent with the join
        self.quality: dict[str, int | None] = {}  # call -> bars 1..5 (None = no result yet)
        self.messages: list[dict] = []
        self.pending: list[dict] = []
        self.pending_reacts: dict[tuple[int, str], float] = {}   # own reactions not echoed yet
        self.console: deque[str] = deque(maxlen=200)
        self.heard: dict[str, str] = {}           # call -> APRS symbol from a beacon
        self.heard_at: dict[str, float] = {}      # call -> last frame heard (any kind)
        self.mail: dict | None = None             # {"count": n, "at": unix} - C1 notice
        self.sysmsg: dict | None = None           # system message (shutdown) from the TinyBox
        self.tinybox_direct_at = 0.0
        self.channel_busy_at = 0.0                # last frame not between us and the TinyBox
        self.unwrap = proto.Unwrapper()
        self.seen: set[int] = set()
        self._hist_buf: list[tuple[int, str, str]] | None = None   # //H lines of a //HIST
        self._hist_older = False                  # the running //HIST asks for older lines
        self._hist_lo = self._hist_hi = 0         # orders history lines of the same second
        self._hist_keys: set[tuple] = set()       # (time, call, text) already shown
        self.clock_off = 0                        # TinyBox time - own time (from //IN now=)
        self.version = 0
        self._changed = asyncio.Event()
        self._hs_task: asyncio.Task | None = None
        # UI frames are sent at once, I-frames wait in a queue: the UI frame of
        # our own join can overtake the //IN line. Keep such events until //IN.
        self._joining: int | None = None
        self._early: list[proto.Event] = []
        # offline mailbox (C3)
        self.mailbox = MailStore(cfg.data_dir / "mailbox.db", cfg.mycall)
        self.sync = Syncer(self, self.mailbox)

    # --- settings --------------------------------------------------------

    def _load_settings(self) -> dict:
        try:
            return json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_settings(self) -> None:
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(json.dumps(self.settings, indent=1), encoding="utf-8")

    # --- newer client version (CR18) ---------------------------------------------

    @staticmethod
    def version_key(v: str) -> tuple[int, ...]:
        return tuple(int(p) for p in re.findall(r"\d+", v or ""))

    def _update_info(self, ok_line: str) -> None:
        """//OK ... cur=<newest version> news=<feature bulletin>: remember it, so
        the hint stays after disconnecting. A TinyBox without cur= means: up to date."""
        cur = re.search(r"\bcur=(\S+)", ok_line)
        news = re.search(r"\bnews=(\d+)", ok_line)
        info = None
        if cur and self.version_key(cur.group(1)) > self.version_key(VERSION):
            info = {"cur": cur.group(1), "news": int(news.group(1)) if news else None}
            self.console.append(f"*** newer client available: {info['cur']} (this is {VERSION})")
        if info != self.settings.get("update"):
            if info:
                self.settings["update"] = info
            else:
                self.settings.pop("update", None)
            self._save_settings()

    @property
    def update(self) -> dict | None:
        info = self.settings.get("update")
        if info and self.version_key(info.get("cur", "")) > self.version_key(VERSION):
            return info
        return None                      # meanwhile updated

    def open_news(self) -> bool:
        """'Read about new features': fetch the rubric TBNEWS and the bulletin."""
        self.mailbox.subscribe("TBNEWS", True)
        if not self.sync.running:
            self.sync.start("bulletins")
        return True

    @property
    def my_symbol(self) -> str:
        return self.settings.get("symbol", "")

    def set_symbol(self, symbol: str) -> bool:
        if symbol and not SYMBOL_RE.match(symbol):
            return False
        self.settings["symbol"] = symbol
        self._save_settings()
        if self.state == "online" and self.caps:     # the board sees it at once (CR7)
            self._send(f"//SYM {symbol or '-'}")
        self._touch()
        return True

    # --- change notification (long poll) -------------------------------------

    def _touch(self) -> None:
        self.version += 1
        self._changed.set()
        self._changed = asyncio.Event()

    async def wait_change(self, since: int, timeout: float) -> None:
        if since != self.version:
            return
        ev = self._changed
        try:
            await asyncio.wait_for(ev.wait(), timeout)
        except asyncio.TimeoutError:
            pass

    # --- actions from the GUI -------------------------------------------------

    async def connect(self) -> None:
        if self.state == "offline":
            await self.link.connect()

    def disconnect(self) -> None:
        if self.state != "offline":
            self.link.disconnect()

    def join(self, n: int) -> bool:
        if not self.handshake_done or not any(b["n"] == n for b in self.boards):
            return False
        self._send(f"/J {n}" if self.board else f"C {n}")
        self._joining, self._early = n, []
        return True

    # --- history on request (CR13) ---------------------------------------------

    HIST_MODES = ("missed", "none", "10", "20")
    HIST_MISSED_MAX = 20

    @property
    def history_mode(self) -> str:
        m = self.settings.get("history", "missed")
        return m if m in self.HIST_MODES else "missed"

    def set_history_mode(self, mode: str) -> bool:
        if mode not in self.HIST_MODES:
            return False
        self.settings["history"] = mode
        self._save_settings()
        self._touch()
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
            since = self.settings.get("seen", {}).get(self.board["name"])
            if since and last <= since:
                return                                    # nothing new since the last visit
            self._ask_history(self.HIST_MISSED_MAX, since=since)
        else:
            self._ask_history(int(mode))

    def _motd_on_join(self, in_line: str) -> None:
        """//IN ... motd=<crc> (CR3): the text is fetched only when it is new."""
        m = re.search(r"\bmotd=([0-9a-f]{4})\b", in_line)
        name = self.board["name"]
        if not m:
            self.board["motd"] = ""
            return
        known = self.settings.get("motd", {}).get(name)
        if known and known.get("crc") == m.group(1):
            self.board["motd"] = known.get("text", "")
        else:
            self.board["motd"] = ""
            self._send("//MOTD")

    def _add_history(self, lines: list[tuple[int, str, str]], older: bool) -> None:
        """History lines (oldest first) into the chat. Ordered by time, always before
        the live events (ids >= 0); within the same second an older page goes in
        front of what is shown, a newer one behind it."""
        new = []
        for x in lines:                          # inclusive limits: drop what is here
            if x not in self._hist_keys:
                self._hist_keys.add(x)
                new.append(x)
        lines = new
        if older:
            self._hist_lo -= len(lines)
            k0 = self._hist_lo
        else:
            k0 = self._hist_hi
            self._hist_hi += len(lines)
        for i, (t, call, text) in enumerate(lines):
            self._add({"id": -(2 ** 50) + t * 1000 + k0 + i, "seq": -1, "kind": "line",
                       "call": call, "text": text, "time": t - self.clock_off,
                       "history": True, "srv_time": t, "reactions": {}})

    def _ask_history(self, n: int, since: int | None = None, before: int | None = None) -> None:
        self.board["loading"] = True
        self._hist_buf, self._hist_older = [], before is not None
        self._send(f"//HIST max={n}" + (f" since={since}" if since else "")
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
        self._touch()
        return True

    def leave(self) -> None:
        if self.board:
            self._send("/Q")

    def say(self, text: str) -> bool:
        text = text.replace("\r", " ").replace("\n", " ").strip()
        if not self.board or not text or text.startswith("/"):
            return False
        self._send(text[:200])
        self.pending.append({"text": text[:200], "at": time.time()})
        self._touch()
        return True

    def react(self, seq: int, emoji: str) -> bool:
        if not self.board or not re.match(r"^[!-~]{1,8}$", emoji) or not 0 <= seq < 256:
            return False
        self._send(f"/R {seq:X} {emoji}")
        # show it at once (CR8); the echo from the TinyBox confirms it
        for m in reversed(self.messages):
            if m.get("seq") == seq and m["kind"] == "line":
                calls = m["reactions"].setdefault(emoji, [])
                if self.cfg.mycall not in calls:
                    calls.append(self.cfg.mycall)
                    self.pending_reacts[(seq, emoji)] = time.time()
                break
        self._touch()
        return True

    def _send(self, line: str) -> None:
        self.console.append("> " + line)
        self.link.send_line(line)

    # --- link callbacks ---------------------------------------------------------

    def _on_state(self, state: str, reason: str) -> None:
        self.state, self.reason = state, reason
        if state == "online":
            self.handshake_done = False
            self._hs_task = asyncio.ensure_future(self._handshake_fallback())
        if state == "offline":
            self.handshake_done = False
            self.caps = set()
            self._clear_board()
            self.pending.clear()
            self.sync.link_lost()
            self.sysmsg = None                   # a shutdown warning is over now
            if self._hs_task:
                self._hs_task.cancel()
        self.console.append(f"*** {state}" + (f" ({reason})" if reason else ""))
        self._touch()

    async def _handshake_fallback(self) -> None:
        await asyncio.sleep(HANDSHAKE_FALLBACK_SEC)
        if self.state == "online" and not self.handshake_done:
            self._handshake()

    def _want_ui(self) -> bool:
        if self.link.kind != "agw" or self.cfg.ui == "no":
            return False
        if self.cfg.ui == "yes":
            return True
        return time.time() - self.tinybox_direct_at < DIRECT_VALID_SEC

    def _handshake(self) -> None:
        if self.handshake_done:
            return
        self.handshake_done = True          # sent; //OK confirms the caps
        caps = "CHAT,UI" if self._want_ui() else "CHAT"
        caps += ",SYNC,SYNC2" + (",Z" if self.link.kind == "agw" else "")
        sym = f" sym={self.my_symbol}" if self.my_symbol else ""
        self._send(f"//CLIENT {PROTO} v={VERSION} caps={caps}{sym}")

    def _on_line(self, line: str) -> None:
        if self.sync.take(line):                 # mailbox sync answers and texts
            return
        line = line.rstrip()
        if not line:
            return
        if line.startswith("//"):
            self._control(line)
        elif line.startswith("#") and (ev := proto.parse_event(line)) is not None:
            self._event(ev)
        else:
            self.console.append(line)
            m = re.match(r"^You have (\d+) new message", line)
            if m or line.startswith("No new messages"):
                self._set_mail(int(m.group(1)) if m else 0)
            if not self.handshake_done and line.startswith("Welcome to TinyBox"):
                asyncio.get_event_loop().call_later(1.0, self._handshake)
        self._touch()

    def _on_frame(self, f: RawFrame) -> None:
        if f.src == self.cfg.tinybox_call and f.direct:
            self.tinybox_direct_at = time.time()
        if {f.src, f.dest} != {self.cfg.mycall, self.cfg.tinybox_call}:
            self.channel_busy_at = time.monotonic()     # others use the frequency
        if f.src != self.cfg.mycall and not f.src.startswith("TBCHAT"):
            self.heard_at[f.src] = time.time()
            if len(self.heard_at) > 200:          # forget the oldest
                del self.heard_at[min(self.heard_at, key=self.heard_at.get)]
        if not f.is_ui:
            return
        sym = aprs_symbol(f.info)
        if sym:
            self.heard[f.src] = sym
            self._touch()
        if f.src == self.cfg.tinybox_call and f.dest == "TBMAIL":
            self._mail_notice(f.info.decode("utf-8", "replace"))
            return
        if f.src != self.cfg.tinybox_call or "UI" not in self.caps:
            return
        ev = proto.parse_event(f.info.decode("utf-8", "replace"))
        if ev is None:
            return
        if self._joining is not None and f.dest == f"TBCHAT-{self._joining}":
            self._early = (self._early + [ev])[-20:]
        elif self.board and f.dest == f"TBCHAT-{self.board['n']}":
            self._event(ev)
            self._touch()

    # --- protocol lines -------------------------------------------------------------

    def _control(self, line: str) -> None:
        cmd, _, rest = line[2:].partition(" ")
        if cmd == "OK":
            m = re.search(r"caps=(\S*)", rest)
            self.caps = set(filter(None, (m.group(1) if m else "").split(",")))
            self.console.append(f"*** client mode, caps: {','.join(sorted(self.caps)) or '-'}")
            self._update_info(rest)
            self._send("//BOARDS")
        elif cmd == "B":
            parts = rest.split(" ", 4)
            if len(parts) >= 4 and parts[0].isdigit():
                if self._boards_tmp is None:
                    self._boards_tmp = []
                self._boards_tmp.append({"n": int(parts[0]), "name": parts[1], "keep": parts[2],
                                         "users": int(parts[3]) if parts[3].isdigit() else 0,
                                         "desc": parts[4] if len(parts) > 4 else ""})
        elif cmd == "BEND":
            self.boards = self._boards_tmp or []
            self._boards_tmp = None
            last = self.settings.get("board")
            if self.board is None and any(b["n"] == last for b in self.boards) \
                    and not self.sync.own_connect:   # a sync-only connection stays out
                self.join(last)                  # back into the last board
        elif cmd == "IN":
            parts = rest.split()
            if len(parts) >= 4:
                self._clear_board()
                self.board = {"n": int(parts[0]), "name": parts[1], "keep": parts[2]}
                self._history_on_join(rest)
                self._motd_on_join(rest)
                last = None if parts[3] == "-" else int(parts[3], 16)
                self.unwrap.reset(last)
                early = self._early if self._joining == self.board["n"] else []
                self._joining, self._early = None, []
                if early:     # after the //H and //WHO lines, which come next
                    asyncio.get_event_loop().call_soon(self._replay_early, early, last)
                if self.settings.get("board") != self.board["n"]:
                    self.settings["board"] = self.board["n"]
                    self._save_settings()
        elif cmd == "H":
            m = re.match(r"^(\d+) ([A-Z0-9-]+): ?(.*)$", rest)
            if m and self.board:
                line = (int(m.group(1)), m.group(2), m.group(3))
                if self._hist_buf is not None:
                    self._hist_buf.append(line)          # answer to //HIST: until //HEND
                else:
                    self._add_history([line], older=False)   # older TinyBox: right away
        elif cmd == "HEND":
            p = rest.split()
            if self.board and len(p) == 2 and p[1].isdigit():
                self._add_history(self._hist_buf or [], older=self._hist_older)
                self._hist_buf = None
                self.board["older"] = int(p[1])
                self.board["loading"] = False
        elif cmd == "MOTD":
            crc, _, text = rest.partition(" ")
            if self.board:
                motds = self.settings.setdefault("motd", {})
                if crc == "-":
                    motds.pop(self.board["name"], None)
                else:
                    motds[self.board["name"]] = {"crc": crc, "text": text}
                self._save_settings()
                self.board["motd"] = text if crc != "-" else ""
                self._touch()
        elif cmd == "WHO":
            for item in rest.split():
                call, _, sym = item.partition("=")
                self.members[call] = sym
        elif cmd == "OUT":
            self._clear_board()
            self.settings.pop("board", None)
            self._save_settings()
        elif cmd == "SYS":
            # //SYS <seconds left> <text>  (-1 = shutdown called off)
            left, _, text = rest.partition(" ")
            if re.match(r"^-?\d+$", left):
                self.sysmsg = {"text": text, "left": int(left), "at": int(time.time())}
                self.console.append("*** " + text)
        elif cmd == "ERR":
            self.console.append(line)
        # //CLIENT etc. echoed by a terminal: ignore

    def _mail_notice(self, text: str) -> None:
        """UI frame to TBMAIL: '<call> <n> new' (sent by the TinyBox, C1)."""
        m = re.match(r"^([A-Z0-9]{1,6})(?:-\d{1,2})? (\d+) new$", text.strip())
        if m and m.group(1) == self.cfg.mycall.split("-")[0]:
            self._set_mail(int(m.group(2)))
            self.console.append(f"*** mail notice: {m.group(2)} new")

    def after_sync(self) -> None:
        """Everything is fetched now: the notice of new mail is done."""
        if self.mail and self.mail["count"] and not self.sync.status["error"]:
            self.mail = {"count": 0, "at": self.mail["at"]}

    def _set_mail(self, count: int) -> None:
        old = self.mail["count"] if self.mail else 0
        self.mail = {"count": count, "at": int(time.time()) if count != old else
                     (self.mail or {}).get("at", int(time.time()))}
        self._touch()

    def _replay_early(self, events: list[proto.Event], last: int | None) -> None:
        for ev in events:
            if last is None or 0 < (ev.seq - last) % 256 < 128:
                self._event(ev)
        self._touch()

    def _clear_board(self) -> None:
        if self.board:                       # everything up to now was seen (CR13)
            seen = self.settings.setdefault("seen", {})
            seen[self.board["name"]] = int(time.time()) + self.clock_off
            self._save_settings()
        self._hist_keys = set()
        self._hist_buf, self._hist_lo, self._hist_hi = None, 0, 0
        self.board = None
        self.members = {}
        self.quality = {}
        self.messages = []
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
        if before is not None and pos > before + 1:
            first, last = (before + 1) % 256, (pos - 1) % 256
            if pos - before - 1 <= MAX_GAP:
                self._send(f"//RESEND {first:X}-{last:X}")
            else:                 # too many to fetch: only tell, for the receive quote
                self._send(f"//LOST {first:X}-{last:X}")
        now = int(time.time())
        if ev.kind == "line":
            self._add({"id": pos, "seq": ev.seq, "kind": "line", "call": ev.call,
                       "text": ev.text, "time": now, "reactions": {}})
            if ev.call == self.cfg.mycall:
                for p in self.pending:
                    if p["text"] == ev.text:
                        self.pending.remove(p)
                        break
        elif ev.kind == "join":
            self.members[ev.call] = ev.symbol
            self._add({"id": pos, "seq": ev.seq, "kind": "join", "call": ev.call, "time": now})
        elif ev.kind == "symbol":                    # nothing to show, only the avatars
            if ev.call in self.members:
                self.members[ev.call] = ev.symbol
        elif ev.kind == "leave":
            self.members.pop(ev.call, None)
            self.quality.pop(ev.call, None)
            self._add({"id": pos, "seq": ev.seq, "kind": "leave", "call": ev.call, "time": now})
        elif ev.kind == "react":
            for m in reversed(self.messages):
                if m.get("seq") == ev.ref and m["kind"] == "line":
                    calls = m["reactions"].setdefault(ev.text, [])
                    if ev.call not in calls:
                        calls.append(ev.call)
                    break
            if ev.call == self.cfg.mycall:
                self.pending_reacts.pop((ev.ref, ev.text), None)
        elif ev.kind == "quality":                   # bars next to the avatars (14.4)
            self.quality = dict(ev.bars or {})
        elif ev.kind == "system":
            self._add({"id": pos, "seq": ev.seq, "kind": "system", "text": ev.text,
                       "time": now})

    def _add(self, msg: dict) -> None:
        self.messages.append(msg)
        self.messages.sort(key=lambda m: m["id"])
        del self.messages[:-MAX_MESSAGES]

    # --- for the GUI -------------------------------------------------------------------

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
        return self.members.get(call) or self.heard.get(call, "")

    def snapshot(self) -> dict:
        calls = {self.cfg.mycall, *self.members}
        calls.update(m["call"] for m in self.messages if m.get("call"))
        now = time.time()
        self.pending = [p for p in self.pending if now - p["at"] < 120]
        self._expire_reacts(now)
        return {
            "version": self.version, "client_version": VERSION,
            "mycall": self.cfg.mycall, "tinybox": self.cfg.tinybox_call,
            "link": self.link.kind, "state": self.state, "reason": self.reason,
            "client": self.handshake_done and bool(self.caps or self.boards),
            "ui": "UI" in self.caps,
            "boards": self.boards, "board": self.board,
            "members": sorted(self.members),
            "quality": self.quality,
            "mail": self.mail,
            "sysmsg": self.sysmsg,
            "heard": [{"call": c, "symbol": self.heard.get(c, ""), "ago": int(now - t)}
                      for c, t in sorted(self.heard_at.items(), key=lambda kv: -kv[1])[:30]
                      if c not in self.members and c != self.cfg.tinybox_call],
            "symbols": {c: self.symbol_of(c) for c in calls if self.symbol_of(c)},
            "my_symbol": self.my_symbol,
            "messages": self.messages, "pending": [p["text"] for p in self.pending],
            "clock_off": self.clock_off,     # TinyBox time - own time (quotes, CR14)
            "pending_reacts": [f"{seq}:{e}" for seq, e in self.pending_reacts],
            "console": list(self.console)[-80:],
            "mailbox": self.mailbox.summary(),
            "sync": self.sync.status,
            "update": self.update,
            "history_mode": self.history_mode,
        }

    async def run(self) -> None:
        if self.cfg.auto_connect:
            asyncio.get_event_loop().call_later(2, lambda: asyncio.ensure_future(self.connect()))
        await self.link.run()
