"""CR123: Prefix raten in the chat board - the client side (box: tinybox/prefixgame.py).

The box sends the game as system events "#<seq> !PR ..." to the whole board;
this keeps the state for the GUI. Commands go as //PR ... to the box, its
answers to us come as //PR OK ... / //PR ERR ...

The countdown: the question carries the seconds; the GUI counts down from the
moment the event arrived (no traffic per second over the air).
"""

from __future__ import annotations

import time

from prcore.text import isnum

KEEP_OVER_SEC = 15 * 60          # a finished game stays visible this long


class PrefixGame:
    def __init__(self, send, mycall) -> None:
        self._send = send            # line -> to the box
        self._mycall = mycall        # () -> own call
        self.g: dict | None = None
        self.err = ""

    def clear(self) -> None:
        self.g, self.err = None, ""

    # --- from the box -------------------------------------------------------------

    def event(self, text: str, now: float | None = None) -> bool:
        """A system text 'PR ...' of the board. True = it was one."""
        if not text.startswith("PR "):
            return False
        now = time.time() if now is None else now
        word, _, rest = text[3:].partition(" ")
        p = rest.split()
        g = self.g
        if word == "OPEN" and len(p) >= 6:
            self.err = ""
            self.g = {"phase": "signup", "starter": p[0], "stage": p[1],
                      "regions": p[2].lstrip("R"), "calls": _int(p[3]), "entities": _int(p[4]),
                      "until": now + _int(p[5]), "secs": _int(p[5]), "scores": {p[0]: 0}, "k": 0, "q": None,
                      "tipped": [], "mytip": "", "res": None, "at": now}
        elif g is None:
            return True                  # a game we did not see begin: wait for the next
        elif word == "IN" and p:
            g["scores"].setdefault(p[0], 0)
        elif word == "GO":
            for c in p:
                g["scores"].setdefault(c, 0)
            g["phase"] = "ask"
        elif word == "Q" and len(p) >= 3:
            k, _, n = p[0].partition("/")
            opts = rest.split(" ", 3)[3].split("|") if len(rest.split(" ", 3)) > 3 else []
            g.update(phase="ask", k=_int(k), calls=_int(n) or g["calls"], tipped=[], mytip="",
                     res=None, q={"call": p[1], "secs": _int(p[2]), "until": now + _int(p[2]),
                                  "options": opts})
        elif word == "TIP" and p:
            if p[0] not in g["tipped"]:
                g["tipped"].append(p[0])
        elif word == "RES" and len(p) >= 2:
            right, scores = [], {}
            for item in p[2:]:
                call, _, sc = item.partition("=")
                if sc.endswith("+"):
                    right.append(call)
                scores[call] = _int(sc.rstrip("+"))
            g.update(phase="wait", scores=scores or g["scores"],
                     res={"k": _int(p[0]), "letter": p[1], "right": right})
        elif word == "END":
            scores = {}
            for item in p:
                call, _, sc = item.partition("=")
                scores[call] = _int(sc)
            best = max(scores.values()) if scores else 0
            g.update(phase="over", scores=scores or g["scores"], at=now,
                     winners=[c for c, n in scores.items() if n == best and best > 0])
        elif word == "STOP":
            g.update(phase="over", stopped=rest or "?", at=now, winners=[])
        return True

    def answer(self, rest: str) -> None:
        """//PR OK ... / //PR ERR ... from the box."""
        word, _, what = rest.partition(" ")
        if word == "ERR":
            self.err = what.strip()
        elif word == "OK":
            self.err = ""
            p = what.split()
            if p and p[0] == "TIP" and len(p) >= 3 and self.g is not None:
                self.g["mytip"] = p[2]

    # --- from the GUI ---------------------------------------------------------------

    def act(self, act: str, arg: str = "") -> bool:
        if act == "start":
            s, _, rest = arg.partition(" ")
            r, _, n = rest.partition(" ")
            r = "".join(c for c in "123" if c in r)
            if s.upper() not in ("NC", "OM", "PRO", "GOD") or not r or not isnum(n):
                return False
            self._send(f"//PR START s={s.upper()} r={r} n={int(n)}")
        elif act == "join":
            self._send("//PR JOIN")
        elif act == "tip":
            letter = arg.strip().upper()
            if letter not in ("A", "B", "C") or self.g is None or self.g["mytip"]:
                return False
            self.g["mytip"] = letter.lower()      # small: sent, not yet confirmed
            self._send(f"//PR {letter}")
        elif act == "go":                       # CR124: the starter ends the signup
            self._send("//PR GO")
        elif act == "stop":
            self._send("//PR STOP")
        elif act == "close":
            if self.g is not None and self.g["phase"] != "over":
                return False
            self.clear()
        else:
            return False
        return True

    def summary(self, now: float | None = None) -> dict | None:
        now = time.time() if now is None else now
        g = self.g
        if g is not None and g["phase"] == "over" and now - g["at"] > KEEP_OVER_SEC:
            self.g = g = None
        if g is None:
            return None
        me = self._mycall()
        return dict(g, me_plays=me in g["scores"], me_starter=me == g["starter"], now=now)


def _int(x: str) -> int:
    try:
        return int(x)
    except (TypeError, ValueError):
        return 0
