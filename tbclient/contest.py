"""CR122: the CQ contest in the TBClient - against another TBClient or the TinyBox.

The rules and the lines are in prcore/contest.py. One slot per opponent: the
game dict lives in the settings ("contest" -> key), so it goes on after a
restart or the next connect. Key: the call of the other TBClient, or
"box:<call>" for the TinyBox. An invitation of another TBClient waits for
the user (st "invited": accept -> //CT OK, decline -> //CT NO). The client answers the CQ calls of the other
side itself, from its own placement - the user only calls.
"""

from __future__ import annotations

import time
from typing import Callable

from prcore import contest

from . import gamereport

PREFIX = "//CT "


def my_center(core) -> str:
    """The own square: from the profile, else the locator in tbclient.conf."""
    mine = core.profiles.mine                       # a property
    loc = (mine.get("loc") or core.cfg.locator or "")[:4].upper()
    return loc if contest.valid_center(loc) else ""


class ContestSlot:
    def __init__(self, core, key: Callable[[], str], opp: Callable[[], str],
                 send: Callable[[str], None], center: Callable[[], str],
                 note: Callable[[str], None] | None = None) -> None:
        self._core = core               # the ClientCore, or a function that gives it
        self._key, self._opp, self._send_line, self._center = key, opp, send, center
        self._note = note or (lambda text: None)
        self.err = ""                    # last //CT ERR of the TinyBox

    @property
    def core(self):
        return self._core() if callable(self._core) else self._core

    # --- storage
    @property
    def state(self) -> dict | None:
        return self.core.settings.get("contest", {}).get(self._key())

    def _save(self, state: dict | None) -> None:
        games = self.core.settings.setdefault("contest", {})
        if state is None:
            games.pop(self._key(), None)
        else:
            games[self._key()] = state
        if len(games) > 30:                 # forget the oldest games
            for k in sorted(games, key=lambda k: games[k].get("at", 0))[:-30]:
                del games[k]
        self.core._save_settings()
        self.core._touch()

    def _send(self, lines: list[str]) -> None:
        for line in lines:
            self._send_line(PREFIX + line)

    def _done(self, before: str, g: contest.Game) -> None:
        s = g.s
        if before != "end" and s["st"] == "end":
            res = {"win": "gewonnen", "loss": "verloren", "draw": "unentschieden",
                   "resigned": "aufgegeben", "they resigned": f"{s['opp']} hat aufgegeben - gewonnen"}
            self._note(f"📻 CQ Contest: {res.get(s['res'], 'vorbei')} "
                       f"({g.worked()}:{g.lost()})")
            self._report(s)

    def _report(self, s: dict) -> None:
        """CR127: a game against another TBClient goes to the leaderboard of the box."""
        result = {"win": "win", "loss": "loss", "draw": "draw", "resigned": "loss",
                  "they resigned": "win"}.get(s["res"])
        reports = getattr(self.core, "reports", None)
        if not s.get("gid") or result is None or reports is None or self._key().startswith("box:"):
            return
        h, n = gamereport.contest_hash(s)
        reports.add("contest", s["gid"], self._opp(), result, h, n)

    # --- from the GUI
    def act(self, act: str, arg: str = "") -> bool:
        if act == "new":
            hints = arg != "0"
            center = self._center()
            if center and not contest.valid_center(center):
                return False
            self.err = ""
            state = contest.new_state(center, hints, first=True, opp=self._opp())
            gid = "" if self._key().startswith("box:") else gamereport.new_id()   # CR127
            if gid:
                state["gid"] = gid
            self._save(state)
            self._send([f"NEW h={1 if hints else 0}" + (f" c={center}" if center else "")
                        + (f" id={gid}" if gid else "")])
            self._note(f"📻 neuer CQ Contest mit {self._opp()} - Stationen setzen")
            return True
        state = self.state
        if state is None:
            return False
        if act in ("accept", "decline") and state["st"] == "invited":
            if act == "accept":
                state["st"] = "setup"
                self._save(state)
                self._send([f"OK c={state['c']} h={1 if state['h'] else 0}"])
            else:
                self._save(None)
                self._send(["NO"])
                self._note("📻 CQ Contest abgelehnt")
            return True
        if act == "close":
            if state["st"] == "invited":
                self._save(None)
                self._send(["NO"])
                return True
            if state["st"] != "end":
                self._send(contest.Game(state).resign())
            self._save(None)
            return True
        g = contest.Game(state)
        before = state["st"]
        if act == "place":
            ok = g.toggle(arg)
            lines: list[str] = []
        elif act == "random":
            ok, lines = g.random_place(), []
        elif act == "ready":
            lines = g.set_ready()
            ok = bool(lines)
        elif act == "cq":
            lines = g.cq(arg)
            ok = bool(lines)
        elif act in ("pause", "resume"):
            lines = g.pause(act == "pause")
            ok = bool(lines)
        elif act == "resign":
            lines = g.resign()
            ok = bool(lines)
        else:
            return False
        if ok:
            self._save(state)
            self._send(lines)
            self._done(before, g)
        return ok

    # --- from the other side
    def take(self, rest: str) -> None:
        p = rest.split()
        if not p:
            return
        word = p[0].upper()
        if word == "ERR":
            self.err = " ".join(p[1:])[:40]
            state = self.state
            if state is not None and state["st"] == "setup" and not state["c"]:
                self._save(None)                 # the box does not play
            self.core._touch()
            return
        if word == "NEW":
            a = {k.lower(): v for k, s, v in (x.partition("=") for x in p[1:]) if s}
            center = a.get("c", "").upper()[:4] or self._center()
            if not contest.valid_center(center):
                self._send(["RESIGN"])           # no locator here: no game
                return
            hints = a.get("h", "1") != "0"
            state = contest.new_state(center, hints, first=False, opp=self._opp())
            state["st"] = "invited"              # the user accepts or declines first
            gid = a.get("id", "").lower()
            if len(gid) == 16 and all(ch in "0123456789abcdef" for ch in gid):
                state["gid"] = gid                # CR127: the id of the game for the box
            self._save(state)
            self._note(f"📻 {self._opp()} lädt zum CQ Contest ein")
            return
        if word == "NO":
            state = self.state
            if state is not None and state["first"] and state["st"] == "setup":
                self._save(None)
                self.err = f"{self._opp()} hat den CQ Contest abgelehnt."
                self._note(f"📻 {self._opp()} hat den CQ Contest abgelehnt")
            return
        state = self.state
        if state is None:
            return
        g = contest.Game(state)
        before = state["st"]
        lines = g.take(rest)
        state["at"] = int(time.time())
        self._save(state)
        self._send(lines)
        self._done(before, g)

    def summary(self) -> dict | None:
        state = self.state
        return None if state is None else contest.Game(state).summary()
