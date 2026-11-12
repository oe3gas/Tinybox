"""Prefix raten in a chat board (CR123, PLANUNG 31; rules in prcore/prefixgame.py).

The box names a made-up call and three entities A, B, C; whoever plays tips
one. One game per board at a time. Commands of a board member - a TBClient
sends //PR ..., a terminal user types /PR ...:

    PR START s=<NC|OM|PRO|GOD> r=<1|2|3 combined, e.g. 12> n=<calls 1-50>
    PR JOIN              play along (a chat line "mit" or "join" does the same)
    PR A | B | C         the tip - only to the box, nobody else sees it
    PR STOP              only the one who started

Answers only to the sender: //PR OK START|JOIN|STOP, //PR OK TIP <k> <letter>,
//PR ERR busy|no_game|no_board|bad|no_pool|not_open|not_player|late|twice|not_starter.

The game itself goes to everybody in the board as system events (#<seq> !PR ...),
so older clients show readable text; terminals get human text:

    PR OPEN <starter> <stage> R<regions> <calls> <entities> <signup sec>
    PR IN <call>                 plays (in the signup, or from the next call on)
    PR GO <call> ...             signup over, the players
    PR Q <k>/<n> <call> <sec> <A>|<B>|<C>      the question; the client counts down
    PR TIP <call>                has tipped (without the letter)
    PR RES <k> <letter> <call>=<score>[+] ...  the right answer, + = right this time
    PR END <call>=<score> ...    the game is over
    PR STOP <reason>             called off (by <call> | no_players)

The time goes over the air once with the question; the box's clock decides and
takes tips GRACE_SEC longer (the frames need their time). The answer comes when
every player still in the board has tipped, at the latest after TIP_SEC + GRACE_SEC.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING, Callable

from prcore import prefixgame as pg

if TYPE_CHECKING:
    from .session import Session

log = logging.getLogger(__name__)

SIGNUP_SEC = 60
TIP_SEC = 30
GRACE_SEC = 5
PAUSE_SEC = 5
MAX_CALLS = 50
JOIN_WORDS = ("MIT", "JOIN")
LETTERS = "ABC"

_games: dict[str, "Game"] = {}       # board name -> running game


def _later(delay: float, fn: Callable[[], None]):
    """Runs fn after delay seconds (tests replace this)."""
    try:
        return asyncio.get_running_loop().call_later(delay, fn)
    except RuntimeError:
        return None


schedule = _later
rng_factory: Callable[[], random.Random] = random.Random


class Game:
    def __init__(self, hub, board: str, starter: str, stage: str, regions: str,
                 calls: int, pool: list[pg.Entity], rng: random.Random) -> None:
        self.hub, self.board, self.starter = hub, board, starter
        self.stage, self.regions, self.calls = stage, regions, calls
        self.pool, self.rng = pool, rng
        self.scores: dict[str, int] = {starter: 0}
        self.phase = "signup"            # signup | ask | wait | over
        self.k = 0
        self.q: pg.Question | None = None
        self.tips: dict[str, int] = {}
        self.late: set[str] = set()       # joined during this question: from the next one
        self.used: set[int] = set()
        self.timer = None

    # --- output -------------------------------------------------------------

    def emit(self, text: str, human: str | None) -> None:
        self.hub._deliver(self.board, "!PR " + text, human, sender=None)

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

    def players_here(self) -> list[str]:
        here = self.present()
        return [c for c in self.scores if c in here]

    def _table(self, right: set[str] = frozenset()) -> str:
        return " ".join(f"{c}={n}{'+' if c in right else ''}" for c, n in self._ranked())

    def _ranked(self) -> list[tuple[str, int]]:
        return sorted(self.scores.items(), key=lambda kv: -kv[1])

    # --- the course of a game --------------------------------------------------

    def open(self) -> None:
        reg = "+".join(self.regions)
        self.emit(f"OPEN {self.starter} {self.stage} R{self.regions} {self.calls} "
                  f"{len(self.pool)} {SIGNUP_SEC}",
                  f"Prefix raten: {self.starter} starts {pg.STAGE_NAME[self.stage]}, IARU R{reg}, "
                  f"{self.calls} calls from {len(self.pool)} entities. "
                  f"Play along: /PR JOIN or 'mit' ({SIGNUP_SEC} s)")
        self._set_timer(SIGNUP_SEC, self.go)

    def join(self, call: str) -> str:
        if call in self.scores:
            return "twice"
        self.scores[call] = 0
        if self.phase == "ask":
            self.late.add(call)
        self.emit(f"IN {call}", f"Prefix raten: {call} plays along.")
        return ""

    def go(self) -> None:
        players = self.players_here()
        if not players:
            self.stop("no_players")
            return
        self.emit("GO " + " ".join(players),
                  "Prefix raten: " + ", ".join(players) + " - here we go!")
        self.ask()

    def ask(self) -> None:
        if not self.players_here():
            self.stop("no_players")
            return
        self.k += 1
        self.q = pg.question(self.pool, self.used, self.rng)
        self.tips, self.late, self.phase = {}, set(), "ask"
        names = [e.name for e in self.q.options]
        self.emit(f"Q {self.k}/{self.calls} {self.q.call} {TIP_SEC} " + "|".join(names),
                  f"Prefix raten {self.k}/{self.calls}: {self.q.call}?  " +
                  "  ".join(f"{LETTERS[i]} {n}" for i, n in enumerate(names)) +
                  f"  ({TIP_SEC} s, /PR A|B|C)")
        self._set_timer(TIP_SEC + GRACE_SEC, self.resolve)

    def tip(self, call: str, letter: str) -> str:
        if self.phase != "ask" or self.q is None:
            return "late"
        if call not in self.scores:
            return "not_player"
        if call in self.late:
            return "late"
        if call in self.tips:
            return "twice"
        i = LETTERS.find(letter)
        if not 0 <= i < len(self.q.options):
            return "bad"
        self.tips[call] = i
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
        letter, name = LETTERS[q.right], q.options[q.right].name
        self.emit(f"RES {self.k} {letter} {self._table(right)}",
                  f"Prefix raten {self.k}: {q.call} is {letter} {name}. " +
                  ", ".join(f"{c} {n}" for c, n in self._ranked()))
        if self.k >= self.calls:
            self.end()
        else:
            self._set_timer(PAUSE_SEC, self.ask)

    def end(self) -> None:
        self._cancel()
        self.phase = "over"
        ranked = self._ranked()
        best = ranked[0][1] if ranked else 0
        winners = [c for c, n in ranked if n == best]
        self.emit("END " + self._table(),
                  "Prefix raten over: " + ", ".join(f"{c} {n}" for c, n in ranked) +
                  (f" - winner {' and '.join(winners)}" if best else ""))
        _games.pop(self.board, None)
        log.info("prefix game in %s over: %s", self.board, self._table())

    def stop(self, reason: str) -> None:
        self._cancel()
        self.phase = "over"
        human = "nobody plays" if reason == "no_players" else reason
        self.emit(f"STOP {reason}", f"Prefix raten called off ({human}).")
        _games.pop(self.board, None)


# --- commands ------------------------------------------------------------------

_HUMAN_ERR = {
    "busy": "A game is already running in this board.",
    "no_game": "No Prefix raten game in this board.",
    "no_board": "Join a board first.",
    "bad": "Usage: /PR START s=NC|OM|PRO|GOD r=123 n=10, /PR JOIN, /PR A|B|C, /PR STOP",
    "no_pool": "No entities for these regions and this stage.",
    "not_open": "The game is over.",
    "not_player": "You do not play - /PR JOIN first.",
    "late": "Too late for this call.",
    "twice": "Already done.",
    "not_starter": "Only the one who started can stop the game.",
}


def _answer(s: "Session", ok: str = "", err: str = "", human: str = "") -> None:
    if s.client is not None:
        s.out(f"//PR OK {ok}" if not err else f"//PR ERR {err}")
    elif err:
        s.out(_HUMAN_ERR.get(err, err))
    elif human:
        s.out(human)


def _start(s: "Session", args: list[str]) -> None:
    board = s.chat_board
    if board in _games:
        _answer(s, err="busy")
        return
    kv = dict(a.partition("=")[::2] for a in args if "=" in a)
    stage = pg.stage_of(kv.get("s", "OM"))
    regions = "".join(sorted(set(kv.get("r", "123")) & set("123")))
    try:
        calls = int(kv.get("n", "10"))
    except ValueError:
        calls = 0
    if stage is None or not regions or not 1 <= calls <= MAX_CALLS:
        _answer(s, err="bad")
        return
    rng = rng_factory()
    pool = pg.pool(pg.entities(), stage, regions, rng)
    if len(pool) < 3:
        _answer(s, err="no_pool")
        return
    g = Game(s.service.chat, board, s.call, stage, regions, calls, pool, rng)
    _games[board] = g
    _answer(s, ok="START")
    g.open()
    log.info("%s: prefix game in %s (%s R%s, %s calls, %s entities)", s.call, board,
             stage, regions, calls, len(pool))


def command(s: "Session", rest: str) -> None:
    """One PR command of a board member (//PR from a client, /PR from a terminal)."""
    p = rest.split()
    board = s.chat_board
    if board is None:
        _answer(s, err="no_board")
        return
    word = p[0].upper() if p else ""
    if word == "START":
        _start(s, p[1:])
        return
    g = _games.get(board)
    if word not in ("JOIN", "MIT", "STOP") and not (len(word) == 1 and word in LETTERS):
        _answer(s, err="bad")
        return
    if g is None:
        _answer(s, err="no_game")
        return
    if word in ("JOIN", "MIT"):
        err = g.join(s.call)
        _answer(s, ok="JOIN", err=err, human="You play along.")
    elif word == "STOP":
        if s.call != g.starter:
            _answer(s, err="not_starter")
            return
        _answer(s, ok="STOP")
        g.stop(f"by {s.call}")
    else:
        k = g.k
        err = g.tip(s.call, word)
        _answer(s, ok=f"TIP {k} {word}", err=err, human=f"Tip {word} noted.")


def chat_line(s: "Session", text: str) -> bool:
    """A chat line "mit" / "join" while a game runs in the board: play along
    instead of chat. True = taken."""
    g = _games.get(s.chat_board or "")
    if g is None or text.strip().upper() not in JOIN_WORDS:
        return False
    if s.call in g.scores:
        return False                   # already plays: an ordinary chat line
    g.join(s.call)
    return True


def game_in(board: str) -> Game | None:
    return _games.get(board)
