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
from .radio import RawFrame, aprs_symbol

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
        self.messages: list[dict] = []
        self.pending: list[dict] = []
        self.pending_reacts: dict[tuple[int, str], float] = {}   # own reactions not echoed yet
        self.console: deque[str] = deque(maxlen=200)
        self.heard: dict[str, str] = {}           # call -> APRS symbol from a beacon
        self.heard_at: dict[str, float] = {}      # call -> last frame heard (any kind)
        self.mail: dict | None = None             # {"count": n, "at": unix} - C1 notice
        self.tinybox_direct_at = 0.0
        self.unwrap = proto.Unwrapper()
        self.seen: set[int] = set()
        self._next_hist = -10_000_000
        self.version = 0
        self._changed = asyncio.Event()
        self._hs_task: asyncio.Task | None = None
        # UI frames are sent at once, I-frames wait in a queue: the UI frame of
        # our own join can overtake the //IN line. Keep such events until //IN.
        self._joining: int | None = None
        self._early: list[proto.Event] = []

    # --- settings --------------------------------------------------------

    def _load_settings(self) -> dict:
        try:
            return json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_settings(self) -> None:
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(json.dumps(self.settings, indent=1), encoding="utf-8")

    @property
    def my_symbol(self) -> str:
        return self.settings.get("symbol", "")

    def set_symbol(self, symbol: str) -> bool:
        if symbol and not SYMBOL_RE.match(symbol):
            return False
        self.settings["symbol"] = symbol
        self._save_settings()
        if self.state == "online" and self.caps:     # tell the TinyBox (next join shows it)
            self.handshake_done = False
            self._handshake()
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
        sym = f" sym={self.my_symbol}" if self.my_symbol else ""
        self._send(f"//CLIENT {PROTO} caps={caps}{sym}")

    def _on_line(self, line: str) -> None:
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
            if self.board is None and any(b["n"] == last for b in self.boards):
                self.join(last)                  # back into the last board
        elif cmd == "IN":
            parts = rest.split()
            if len(parts) >= 4:
                self._clear_board()
                self.board = {"n": int(parts[0]), "name": parts[1], "keep": parts[2]}
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
                self._next_hist += 1
                self._add({"id": self._next_hist, "seq": -1, "kind": "line",
                                      "call": m.group(2), "text": m.group(3),
                                      "time": int(m.group(1)), "history": True,
                                      "reactions": {}})
        elif cmd == "WHO":
            for item in rest.split():
                call, _, sym = item.partition("=")
                self.members[call] = sym
        elif cmd == "OUT":
            self._clear_board()
            self.settings.pop("board", None)
            self._save_settings()
        elif cmd == "ERR":
            self.console.append(line)
        # //CLIENT etc. echoed by a terminal: ignore

    def _mail_notice(self, text: str) -> None:
        """UI frame to TBMAIL: '<call> <n> new' (sent by the TinyBox, C1)."""
        m = re.match(r"^([A-Z0-9]{1,6})(?:-\d{1,2})? (\d+) new$", text.strip())
        if m and m.group(1) == self.cfg.mycall.split("-")[0]:
            self._set_mail(int(m.group(2)))
            self.console.append(f"*** mail notice: {m.group(2)} new")

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
        self.board = None
        self.members = {}
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
        if before is not None and pos > before + 1 and pos - before - 1 <= MAX_GAP:
            first, last = (before + 1) % 256, (pos - 1) % 256
            self._send(f"//RESEND {first:X}-{last:X}")
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
        elif ev.kind == "leave":
            self.members.pop(ev.call, None)
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
            "mail": self.mail,
            "heard": [{"call": c, "symbol": self.heard.get(c, ""), "ago": int(now - t)}
                      for c, t in sorted(self.heard_at.items(), key=lambda kv: -kv[1])[:30]
                      if c not in self.members and c != self.cfg.tinybox_call],
            "symbols": {c: self.symbol_of(c) for c in calls if self.symbol_of(c)},
            "my_symbol": self.my_symbol,
            "messages": self.messages, "pending": [p["text"] for p in self.pending],
            "pending_reacts": [f"{seq}:{e}" for seq, e in self.pending_reacts],
            "console": list(self.console)[-80:],
        }

    async def run(self) -> None:
        if self.cfg.auto_connect:
            asyncio.get_event_loop().call_later(2, lambda: asyncio.ensure_future(self.connect()))
        await self.link.run()
