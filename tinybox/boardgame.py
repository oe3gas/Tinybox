"""Games in a chat board - the frame every board game uses (Refactoring R3).

One game per board at a time, whatever game it is (GAMES). A game speaks to the board
as system events "#<seq> !<EVENT> ..." through ChatHub.deliver, and to terminals as
human text; it keeps its own timer.

    BoardGame   one game in one board: events, timer, who is here
    QuizGame    a quiz on top: signup -> question -> tips -> answer -> ... -> end,
                scores, the statistics for the leaderboards (games.py, CR126)

Who gets what (CR128): only TinyBox clients play - a terminal user cannot. Who does
not play sees only THAT a game runs: the PUBLIC events (start, players, end) go to the
whole board, everything else (questions, tips, answers, scores) only to the players -
as I-frame or the one UI frame, which spectators' clients hide. Terminals get a line
at the start and one at the end.

A quiz only brings its questions and its texts (prefixgame.py: Prefix raten). The
events of a quiz, with <EVENT> = PR for Prefix raten:

    OPEN <starter> <stage> R<regions> <calls> <entities> <signup sec> <tip sec>
    IN <call> | GO <call> ... | Q <k>/<n> <call> <sec> <A>|<B>|<C> | TIP <call>
    RES <k> <letter> <right>/<asked> <call>=<score>[+] ...
    END <call>=<right>/<asked> ... | ALL <call>=<games>/<quote %> ... | STOP <reason>
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

from prcore.calls import base_call

from . import games

log = logging.getLogger(__name__)

GAMES: dict[str, "BoardGame"] = {}     # board name -> the game running in it


def _later(delay: float, fn: Callable[[], None]):
    """Runs fn after delay seconds (tests replace schedule)."""
    try:
        return asyncio.get_running_loop().call_later(delay, fn)
    except RuntimeError:
        return None


schedule = _later


def game_in(board: str) -> "BoardGame | None":
    return GAMES.get(board)


class BoardGame:
    EVENT = ""                 # the word after '!' in the events, e.g. 'PR'

    def __init__(self, hub, board: str, starter: str) -> None:
        self.hub, self.board, self.starter = hub, board, starter
        self.timer = None

    def begin(self) -> None:
        GAMES[self.board] = self

    def finish(self) -> None:
        self._cancel()
        if GAMES.get(self.board) is self:
            del GAMES[self.board]

    def emit(self, text: str, human: str | None,
             audience: Callable | None = None) -> None:
        self.hub.deliver(self.board, f"!{self.EVENT} {text}", human, sender=None,
                         audience=audience)

    def _set_timer(self, delay: float, fn: Callable[[], None]) -> None:
        self._cancel()
        self.timer = schedule(delay, fn)

    def _cancel(self) -> None:
        if self.timer is not None:
            try:
                self.timer.cancel()
            except Exception:
                pass
            self.timer = None

    def present(self) -> set[str]:
        return {m.call for m in self.hub.members(self.board)}


class QuizGame(BoardGame):
    """Signup, then `calls` questions with three options each; a tip per player and
    question, the answer when all have tipped or the time is up."""
    PUBLIC = ("OPEN", "GO", "END", "STOP")      # CR128: the rest only to the players
    TITLE = ""                 # 'Prefix raten' - in the human texts
    STORE = ""                 # the game in the leaderboards (games.py)
    LETTERS = "ABC"
    SIGNUP_SEC = 60
    GRACE_SEC = 5              # tips are taken this much longer (the frames need their time)
    PAUSE_SEC = 5              # between the answer and the next question

    def __init__(self, hub, board: str, starter: str, calls: int, tip_sec: int) -> None:
        super().__init__(hub, board, starter)
        self.calls, self.tip_sec = calls, tip_sec
        self.scores: dict[str, int] = {starter: 0}
        self.stat: dict[str, dict] = {starter: {"asked": 0, "tries": 0, "hits": 0}}   # CR126
        self.asked_now: set[str] = set()
        self.phase = "signup"            # signup | ask | wait | over
        self.k = 0
        self.q = None                    # the question: .options, .right (index)
        self.tips: dict[str, int] = {}
        self.late: set[str] = set()       # joined during this question: from the next one

    # --- what a quiz brings ---------------------------------------------------------

    def open_event(self) -> tuple[str, str]:
        """(event, human text) of the start."""
        raise NotImplementedError

    def next_question(self):
        """A new question: an object with .options and .right."""
        raise NotImplementedError

    def question_event(self) -> tuple[str, str]:
        """(event without 'Q <k>/<n> ', human text) of self.q."""
        raise NotImplementedError

    def answer_text(self) -> str:
        """The right answer of self.q for the human text: 'OE3XYZ is B Austria'."""
        raise NotImplementedError

    # --- who plays ------------------------------------------------------------------

    def emit(self, text: str, human: str | None, audience: Callable | None = None) -> None:
        """CR128: an event that is not PUBLIC goes only to the players."""
        if audience is None and text.split(" ", 1)[0] not in self.PUBLIC:
            audience = self.is_player
        super().emit(text, human, audience)

    def is_player(self, s) -> bool:
        return s.call in self.scores

    def players_here(self) -> list[str]:
        here = self.present()
        return [c for c in self.scores if c in here]

    def _table(self, right: set[str] = frozenset()) -> str:
        return " ".join(f"{c}={n}{'+' if c in right else ''}" for c, n in self._ranked())

    def _ranked(self) -> list[tuple[str, int]]:
        return sorted(self.scores.items(), key=lambda kv: -kv[1])

    # --- the course of a game -------------------------------------------------------

    def open(self) -> None:
        self.begin()
        self.emit(*self.open_event())
        self._set_timer(self.SIGNUP_SEC, self.go)

    def join(self, call: str) -> str:
        if call in self.scores:
            return "twice"
        self.scores[call] = 0
        self.stat[call] = {"asked": 0, "tries": 0, "hits": 0}
        if self.phase == "ask":
            self.late.add(call)
        # in the signup everybody sees who is in (it is the invitation), later only players
        self.emit(f"IN {call}", None, (lambda s: True) if self.phase == "signup" else None)
        return ""

    def go(self) -> None:
        players = self.players_here()
        if not players:
            self.stop("no_players")
            return
        self.emit("GO " + " ".join(players), None)    # terminals: start and end only
        self.ask()

    def ask(self) -> None:
        if not self.players_here():
            self.stop("no_players")
            return
        self.k += 1
        self.q = self.next_question()
        self.tips, self.late, self.phase = {}, set(), "ask"
        self.asked_now = set(self.players_here())
        for c in self.asked_now:
            self.stat[c]["asked"] += 1
        event, human = self.question_event()
        self.emit(f"Q {self.k}/{self.calls} {event}", human)
        self._set_timer(self.tip_sec + self.GRACE_SEC, self.resolve)

    def tip(self, call: str, letter: str) -> str:
        if self.phase != "ask" or self.q is None:
            return "late"
        if call not in self.scores:
            return "not_player"
        if call in self.late:
            return "late"
        if call in self.tips:
            return "twice"
        i = self.LETTERS.find(letter)
        if not 0 <= i < len(self.q.options):
            return "bad"
        self.tips[call] = i
        self.stat[call]["tries"] += 1
        self.emit(f"TIP {call}", None)
        waiting = [c for c in self.players_here() if c not in self.tips and c not in self.late]
        if not waiting:
            self.resolve()
        return ""

    def resolve(self) -> None:
        if self.phase != "ask" or self.q is None:
            return
        self._cancel()
        q, self.phase = self.q, "wait"
        right = {c for c, i in self.tips.items() if i == q.right}
        for c in right:
            self.scores[c] += 1
            self.stat[c]["hits"] += 1
        n_right, n_asked = len(right & self.asked_now), len(self.asked_now)
        self.emit(f"RES {self.k} {self.LETTERS[q.right]} {n_right}/{n_asked} {self._table(right)}",
                  f"{self.TITLE} {self.k}: {self.answer_text()}, {n_right} of {n_asked} right. " +
                  ", ".join(f"{c} {n}" for c, n in self._ranked()))
        if self.k >= self.calls:
            self.end()
        else:
            self._set_timer(self.PAUSE_SEC, self.ask)

    def end(self) -> None:
        self.phase = "over"
        ranked = self._ranked()
        best = ranked[0][1] if ranked else 0
        winners = [c for c, n in ranked if n == best]
        # CR128: who did not play does not care for the results - terminals get one line
        self.emit("END " + " ".join(f"{c}={n}/{self.stat[c]['asked']}" for c, n in ranked),
                  f"{self.TITLE} is over.")
        self.finish()
        self._record(winners if best else [])
        log.info("%s in %s over: %s", self.TITLE, self.board, self._table())

    def _record(self, winners: list[str]) -> None:
        """CR126: the finished game into the scores of the box, then everybody's totals."""
        played = [c for c in self.scores if self.stat[c]["asked"]]
        if not played:
            return
        store = self.hub.store
        games.record(store, self.STORE, [dict(self.stat[c], call=c, wins=int(c in winners))
                                         for c in played])
        rows = {r["call"]: r for r in games.ranked(store, self.STORE)}
        tot = []
        for c in played:
            r = rows.get(base_call(c))
            if r:
                tot.append(f"{c}={r['games']}/{r['quote']}")
        if tot:
            self.emit("ALL " + " ".join(tot), None)

    def stop(self, reason: str) -> None:
        self.phase = "over"
        human = "nobody plays" if reason == "no_players" else reason
        self.emit(f"STOP {reason}", f"{self.TITLE} called off ({human}).")
        self.finish()
