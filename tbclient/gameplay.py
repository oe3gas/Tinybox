"""The games with the box and through it: CQ contest, Prefix raten, results and
leaderboards (CR122, CR123, CR126, CR127).
Part of ClientCore (Refactoring R2): a mixin, so the methods keep working on the core's
state; tbclient/core.py puts the parts together."""

from __future__ import annotations

import logging

from prcore.calls import AX25_CALL_RE

from .contest import ContestSlot

log = logging.getLogger(__name__)


class GamesMixin:
    def contest_act(self, act: str, arg: str = "", to: str = "") -> bool:
        """CR122: the CQ contest against the TinyBox of the chat channel - or,
        with to=<call>, against another client of that box (handed on by it)."""
        offline_ok = act in ("close", "decline", "place", "random")
        if to:
            to = to.upper().split("-")[0]
            if not AX25_CALL_RE.match(to) or to == self.cfg.mycall.upper().split("-")[0]:
                return False
            if not offline_ok and (self.state != "online" or "CTR" not in self.caps):
                return False
            return self._relay_slot(to).act(act, arg)
        if not offline_ok and (self.state != "online" or "CT" not in self.caps):
            return False
        return self.box_contest.act(act, arg)

    def games_act(self, act: str, arg: str = "") -> bool:
        """CR126: leaderboards - top (arg: game or empty) / close."""
        if act == "close":
            self.leaderboard.close()
        elif act == "top" and self.state == "online" and "GAMES" in self.caps:
            self.leaderboard.ask(arg.strip().lower())
        else:
            return False
        self.changed()
        return True

    def prefix_act(self, act: str, arg: str = "") -> bool:
        """CR123: Prefix raten in the board (start / join / tip / stop / close)."""
        if act != "close" and (self.state != "online" or "PR" not in self.caps
                               or not self.board):
            return False
        ok = self.prefix.act(act, arg)
        self.changed()
        return ok

    def _relay_slot(self, call: str) -> ContestSlot:
        """The game with <call> through the TinyBox of the chat channel."""
        box = self.target.split("-")[0]
        key = f"rel:{box}:{call}"
        slot = self.relay_contests.get(key)
        if slot is None:
            slot = ContestSlot(self, lambda: key, lambda: call,
                               lambda line: self.send_line(f"//CTR {call} {line[5:]}"), lambda: "",
                               lambda text: self.console.append("*** " + text))
            self.relay_contests[key] = slot
        return slot

    def _relay_summary(self) -> list[dict]:
        box = self.target.split("-")[0]
        prefix = f"rel:{box}:"
        for key in self.settings.get("contest", {}):
            if key.startswith(prefix):
                self._relay_slot(key[len(prefix):])
        out = []
        for key, slot in sorted(self.relay_contests.items()):
            if key.startswith(prefix) and (slot.state is not None or slot.err):
                out.append({"call": key[len(prefix):], "game": slot.summary(), "err": slot.err})
        return out

    # --- the lines of the TinyBox about games (tbclient/core.py _CONTROL) ---------------

    def _c_ct(self, cmd: str, rest: str, line: str) -> None:
        """//CT - CR122: the box plays the CQ contest"""
        self.box_contest.take(rest)

    def _c_game(self, cmd: str, rest: str, line: str) -> None:
        """//GAME - CR127: the box answers a result"""
        self.reports.answer(rest)

    def _c_games(self, cmd: str, rest: str, line: str) -> None:
        """//GAMES - CR126: leaderboards"""
        self.leaderboard.line(rest)
        self.changed()

    def _c_pr(self, cmd: str, rest: str, line: str) -> None:
        """//PR - CR123: the box answers a Prefix raten command"""
        self.prefix.answer(rest)
        self.changed()

    def _c_ctr(self, cmd: str, rest: str, line: str) -> None:
        """//CTR - CR122: another client, handed on by the box"""
        call, _, line = rest.partition(" ")
        call = call.upper()
        if AX25_CALL_RE.match(call) and line:
            self._relay_slot(call).take(line)
