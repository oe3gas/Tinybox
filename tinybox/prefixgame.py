"""Prefix raten in a chat board (CR123, PLANUNG 31; rules in prcore/prefixgame.py).

The box names a made-up call and three entities A, B, C; whoever plays tips
one. One game per board at a time. Commands of a board member - a TBClient
sends //PR ..., a terminal user types /PR ...:

    PR START s=<NC|OM|PRO|GOD> r=<1|2|3 combined, e.g. 12> n=<calls 1-50> [t=<5-30 s>]
    PR JOIN              play along (a chat line "mit" or "join" does the same)
    PR GO                only the one who started: end the signup now (CR124)
    PR A | B | C         the tip - only to the box, nobody else sees it
    PR STOP              only the one who started

Answers only to the sender: //PR OK START|JOIN|GO|STOP, //PR OK TIP <k> <letter>,
//PR ERR busy|no_game|no_board|bad|no_pool|not_open|not_player|late|twice|not_starter.

The game itself goes to everybody in the board as system events (#<seq> !PR ...),
so older clients show readable text; terminals get human text:

    PR OPEN <starter> <stage> R<regions> <calls> <entities> <signup sec> <tip sec>
    PR IN <call>                 plays (in the signup, or from the next call on)
    PR GO <call> ...             signup over, the players
    PR Q <k>/<n> <call> <sec> <A>|<B>|<C>      the question; the client counts down
    PR TIP <call>                has tipped (without the letter)
    PR RES <k> <letter> <right>/<asked> <call>=<score>[+] ...  the right answer, + = right
                                 this time; right/asked: how many of the players asked
    PR END <call>=<right>/<asked> ...   the game is over (CR126)
    PR ALL <call>=<games>/<quote %> ... all games of the players on this box (CR126)
    PR STOP <reason>             called off (by <call> | no_players)

The time goes over the air once with the question; the box's clock decides and
takes tips GRACE_SEC longer (the frames need their time). The answer comes when
every player still in the board has tipped, at the latest after the tip time + GRACE_SEC.
The tip time is chosen at the start, TIP_MIN..TIP_SEC (CR126). A finished game goes
into the scores of the box (games.py); one called off does not.

The course of the game is the quiz of boardgame.py (Refactoring R3); this module
brings the questions (prcore/prefixgame.py) and the texts.
"""

from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING, Callable

from prcore import prefixgame as pg

from . import boardgame
from .boardgame import QuizGame

if TYPE_CHECKING:
    from .session import Session

log = logging.getLogger(__name__)

TIP_SEC = 30                      # the most and the default (CR126)
TIP_MIN = 5
MAX_CALLS = 50
JOIN_WORDS = ("MIT", "JOIN")
LETTERS = QuizGame.LETTERS

rng_factory: Callable[[], random.Random] = random.Random


class Game(QuizGame):
    EVENT, TITLE, STORE = "PR", "Prefix raten", "prefix"

    def __init__(self, hub, board: str, starter: str, stage: str, regions: str,
                 calls: int, pool: list[pg.Entity], rng: random.Random,
                 tip_sec: int = TIP_SEC) -> None:
        super().__init__(hub, board, starter, calls, tip_sec)
        self.stage, self.regions = stage, regions
        self.pool, self.rng = pool, rng
        self.used: set[int] = set()

    def open_event(self) -> tuple[str, str]:
        reg = "+".join(self.regions)
        return (f"OPEN {self.starter} {self.stage} R{self.regions} {self.calls} "
                f"{len(self.pool)} {self.SIGNUP_SEC} {self.tip_sec}",
                f"Prefix raten: {self.starter} starts {pg.STAGE_NAME[self.stage]}, IARU R{reg}, "
                f"{self.calls} calls from {len(self.pool)} entities, {self.tip_sec} s per call. "
                f"Play along: /PR JOIN or 'mit' ({self.SIGNUP_SEC} s)")

    def next_question(self) -> pg.Question:
        return pg.question(self.pool, self.used, self.rng)

    def question_event(self) -> tuple[str, str]:
        names = [pg.label(e, self.stage) for e in self.q.options]
        return (f"{self.q.call} {self.tip_sec} " + "|".join(names),
                f"Prefix raten {self.k}/{self.calls}: {self.q.call}?  " +
                "  ".join(f"{LETTERS[i]} {n}" for i, n in enumerate(names)) +
                f"  ({self.tip_sec} s, /PR A|B|C)")

    def answer_text(self) -> str:
        q = self.q
        return f"{q.call} is {LETTERS[q.right]} {pg.label(q.options[q.right], self.stage)}"


# --- commands ------------------------------------------------------------------

_HUMAN_ERR = {
    "busy": "A game is already running in this board.",
    "no_game": "No Prefix raten game in this board.",
    "no_board": "Join a board first.",
    "bad": "Usage: /PR START s=NC|OM|PRO|GOD r=123 n=10 t=30, /PR JOIN, /PR GO, /PR A|B|C, /PR STOP",
    "no_pool": "No entities for these regions and this stage.",
    "not_open": "The signup is over.",
    "not_player": "You do not play - /PR JOIN first.",
    "late": "Too late for this call.",
    "twice": "Already done.",
    "not_starter": "Only the one who started the game can do that.",
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
    if boardgame.game_in(board) is not None:
        _answer(s, err="busy")
        return
    kv = dict(a.partition("=")[::2] for a in args if "=" in a)
    stage = pg.stage_of(kv.get("s", "OM"))
    regions = "".join(sorted(set(kv.get("r", "123")) & set("123")))
    try:
        calls = int(kv.get("n", "10"))
        tip = int(kv.get("t", str(TIP_SEC)))
    except ValueError:
        calls = tip = 0
    if stage is None or not regions or not 1 <= calls <= MAX_CALLS or not TIP_MIN <= tip <= TIP_SEC:
        _answer(s, err="bad")
        return
    rng = rng_factory()
    pool = pg.pool(pg.entities(), stage, regions, rng)
    if len(pool) < 3:
        _answer(s, err="no_pool")
        return
    g = Game(s.service.chat, board, s.call, stage, regions, calls, pool, rng, tip)
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
    g = game_in(board)
    if word not in ("JOIN", "MIT", "STOP", "GO") and not (len(word) == 1 and word in LETTERS):
        _answer(s, err="bad")
        return
    if g is None:
        _answer(s, err="no_game")
        return
    if word in ("JOIN", "MIT"):
        err = g.join(s.call)
        _answer(s, ok="JOIN", err=err, human="You play along.")
    elif word == "GO":                  # CR124: all there - the starter ends the signup
        if s.call != g.starter:
            _answer(s, err="not_starter")
        elif g.phase != "signup":
            _answer(s, err="not_open")
        else:
            _answer(s, ok="GO")
            g._cancel()
            g.go()
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
    g = game_in(s.chat_board or "")
    if g is None or text.strip().upper() not in JOIN_WORDS:
        return False
    if s.call in g.scores:
        return False                   # already plays: an ordinary chat line
    g.join(s.call)
    return True


def game_in(board: str) -> Game | None:
    """The Prefix raten game running in board (None: none, or another game)."""
    g = boardgame.game_in(board)
    return g if isinstance(g, Game) else None
