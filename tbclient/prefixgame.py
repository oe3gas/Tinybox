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
                      "tipped": [], "mytip": "", "res": None, "at": now,
                      "tip": _int(p[6]) if len(p) > 6 else 30,          # CR126: seconds per call
                      "log": [], "asked": {}, "totals": {}}
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
            n_right = n_asked = None
            items = p[2:]
            if items and "=" not in items[0] and "/" in items[0]:      # CR126: right/asked
                a, _, b = items[0].partition("/")
                n_right, n_asked = _int(a), _int(b)
                items = items[1:]
            for item in items:
                call, _, sc = item.partition("=")
                if sc.endswith("+"):
                    right.append(call)
                scores[call] = _int(sc.rstrip("+"))
            g.update(phase="wait", scores=scores or g["scores"],
                     res={"k": _int(p[0]), "letter": p[1], "right": right,
                          "n_right": len(right) if n_right is None else n_right, "n_asked": n_asked})
            q = g.get("q") or {}
            i = "ABC".find(p[1])
            if q and 0 <= i < len(q.get("options", [])) and not any(x["k"] == _int(p[0]) for x in g["log"]):
                g["log"].append({"k": _int(p[0]), "call": q["call"], "name": q["options"][i],
                                 "right": len(right) if n_right is None else n_right,
                                 "asked": n_asked})
        elif word == "END":
            scores, asked = {}, {}
            for item in p:
                call, _, sc = item.partition("=")
                a, _, b = sc.partition("/")                  # CR126: right/asked
                scores[call] = _int(a)
                if b:
                    asked[call] = _int(b)
            g["asked"] = asked
            best = max(scores.values()) if scores else 0
            g.update(phase="over", scores=scores or g["scores"], at=now,
                     winners=[c for c, n in scores.items() if n == best and best > 0])
        elif word == "ALL":                               # CR126: totals on the box
            for item in p:
                call, _, v = item.partition("=")
                a, _, b = v.partition("/")
                g["totals"][call] = {"games": _int(a), "quote": _int(b)}
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
        if act == "start":                       # "<stage> <regions> <calls> [<tip sec>]"
            w = arg.split()
            if len(w) < 3:
                return False
            s, r, n = w[0], "".join(c for c in "123" if c in w[1]), w[2]
            t = w[3] if len(w) > 3 else "30"
            if s.upper() not in ("NC", "OM", "PRO", "GOD") or not r or not isnum(n) or not isnum(t):
                return False
            self._send(f"//PR START s={s.upper()} r={r} n={int(n)} t={int(t)}")
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
        return dict(g, me_plays=me in g["scores"], me_starter=me == g["starter"], now=now, self=me)


def _int(x: str) -> int:
    try:
        return int(x)
    except (TypeError, ValueError):
        return 0


class Leaderboard:
    """CR126: the leaderboards of the box (//GAMES TOP [game])."""

    def __init__(self, send) -> None:
        self._send = send
        self.want: str | None = None      # None: nothing open, "" = all games, else the game
        self.data: dict | None = None     # {"game": "" | name, "games": {game: {...}}, "done"}
        self._buf: dict | None = None
        self.err = ""

    def ask(self, game: str = "") -> None:
        self.want, self.err = game, ""
        self._buf = {"game": game, "games": {}}
        self._send("//GAMES TOP" + (f" {game}" if game else ""))

    def close(self) -> None:
        self.want = self.data = self._buf = None

    def line(self, rest: str) -> None:
        """One //GAMES ... line from the box."""
        p = rest.split()
        if not p:
            return
        if p[0] == "ERR":
            self.err = p[1] if len(p) > 1 else "?"
            return
        b = self._buf
        if b is None:
            return
        if p[0] == "G" and len(p) >= 4:
            b["games"][p[1]] = {"total": _int(p[2]), "players": _int(p[3]), "rows": [], "me": None}
        elif p[0] in ("R", "ME") and len(p) >= 6 and p[1] in b["games"]:
            row = {"rank": _int(p[2]), "call": p[3], "games": _int(p[4]), "quote": _int(p[5])}
            if len(p) > 6:
                h, _, t = p[6].partition("/")
                row.update(hits=_int(h), tries=_int(t))
            if p[0] == "R":
                b["games"][p[1]]["rows"].append(row)
            else:
                b["games"][p[1]]["me"] = row
        elif p[0] == "END":
            self.data, self._buf = b, None

    def summary(self) -> dict | None:
        if self.want is None:
            return None
        return {"want": self.want, "data": self.data, "err": self.err}
