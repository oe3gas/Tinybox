"""CQ contest - battleships with a radio touch (CR122), the rules for both sides.

The board: 8 x 8 grid squares (4-character Maidenhead locators, 2 x 1 degrees)
around a center square - the TinyBox where the clients meet, or the inviting
TBClient in a direct connection. The center is column 4, row 4 from the top
(8 has no middle). Both sides work the board out from the center alone.

Each player hides 5 contest stations, one per square at most. The station gets
a callsign of 4-5 characters that fits its square (DL1AB, S57DT, OE3A ...).
A move is "CQ <square>". A station there answers - it is worked; otherwise the
CQ goes unanswered. Propagation hint (on by default): no station there, but one
not yet worked in a neighbouring square - "QRZ? weak sigs" (a worked station is
in the log and gives no hint any more).

Who calls first: the one who invited. The game ends only after a move of the
second player (the round is played out): whoever has all 5 wins; both 5 - the
distance of the worked stations decides (km from the center), equal - a draw.

Lines (after "//CT "):
    NEW h=<0|1> [c=<loc>]       invitation; without c the other side says the center
    OK c=<loc> h=<0|1>          accepted, the center and the hint rule for both
    NO                          declined (the invited TBClient asks its user first)
    READY <hash>                stations placed: sha256 over placement and salt, 16 hex
    CQ <loc>                    a move
    R <loc> <call> <serial>     the station answers (5NN is not sent)
    R <loc> NIL | WEAK          no answer / weak signals next door
    END <loc:call,...> <salt>   at the end both lay their stations open; the other
                                side checks the hash and every answer of the game
    RESIGN
    PAUSE / RESUME              no calls until RESUME (either side may resume)

Nobody can cheat through the GUI (the client answers, not the user); the check
at the end also finds two game states that drifted apart. A game is a plain
dict (JSON, kept in the settings of the client); Game wraps it, and every
method returns the lines to send (without "//CT ").
"""

from __future__ import annotations

import hashlib
import math
import os
import random
import re
import time

from prcore.text import isnum

N = 8
CENTER = (3, 3)                      # row, column of the center square
STATIONS = 5
CALL_RE = re.compile(r"^[A-Z0-9]{3,6}$")

# Country per square, 2 x 1 degrees: rows lat 40..55 north (row 0 = 40-41 N),
# columns lon 0..28 east in steps of 2. Sea squares belong to the nearest coast.
_COUNTRY_ROWS = [
    "EA EA EA I  I  I  I  I  ZA SV SV SV TA TA TA",   # 40
    "EA EA EA I  I  I  I  I  ZA Z3 LZ SV TA TA TA",   # 41
    "EA EA F  F  I  I  I  9A 4O Z3 LZ LZ LZ LZ LZ",   # 42
    "F  F  F  F  I  I  I  9A E7 YU YU LZ LZ LZ LZ",   # 43
    "F  F  F  I  I  I  I  9A E7 E7 YU YO YO YO YO",   # 44
    "F  F  F  I  I  I  I  9A 9A YU YO YO YO YO YO",   # 45
    "F  F  F  HB HB I  OE S5 HG HG YO YO YO YO ER",   # 46
    "F  F  F  HB HB OE OE OE HG HG HG YO YO YO ER",   # 47
    "F  F  F  F  DL DL DL OE OE OM OM UT UT ER UT",   # 48
    "F  F  F  DL DL DL OK OK OK OM SP UT UT UT UT",   # 49
    "F  F  ON DL DL DL OK OK SP SP SP SP UT UT UT",   # 50
    "G  ON ON DL DL DL DL SP SP SP SP SP UT UT UT",   # 51
    "G  PA PA DL DL DL DL SP SP SP SP SP EW EW EW",   # 52
    "G  PA PA DL DL DL DL SP SP SP SP SP EW EW EW",   # 53
    "G  G  PA DL DL DL DL SP SP SP UA LY LY EW EW",   # 54
    "G  G  OZ OZ OZ OZ OZ SM SM SM LY LY LY EW EW",   # 55
]
COUNTRY = [row.split() for row in _COUNTRY_ROWS]
LAT0, LON0 = 40, 0

# '#' = a digit, the rest of the call are letters (4-5 characters in all)
PATTERNS = {
    "F": ["F#"], "G": ["G#", "M#"], "ON": ["ON#"], "PA": ["PA#", "PD#"],
    "DL": ["DL#", "DK#", "DJ#", "DO#", "DF#"], "OZ": ["OZ#"], "SM": ["SM#", "SA#"],
    "UA": ["UA2"], "LY": ["LY#"], "EW": ["EW#"], "SP": ["SP#", "SQ#", "SN#"],
    "OK": ["OK#", "OL#"], "OM": ["OM#"], "OE": ["OE#"], "HB": ["HB9"],
    "I": ["I#", "IK#", "IZ#"], "S5": ["S5#"], "9A": ["9A#"], "E7": ["E7#"],
    "YU": ["YU#", "YT#"], "HG": ["HG#", "HA#"], "YO": ["YO#", "YP#"],
    "UT": ["UT#", "UR#", "US#"], "ER": ["ER#"], "LZ": ["LZ#"], "Z3": ["Z3#"],
    "4O": ["4O#"], "ZA": ["ZA#"], "SV": ["SV#"], "TA": ["TA#"], "EA": ["EA#", "EB#"],
}
# squares with more than one country, and the Austrian districts
SQUARE_PATTERNS = {
    "JN47": ["HB9", "OE9", "DL#"], "JN57": ["OE7", "DL#"], "JN67": ["OE2", "DL#"],
    "JN77": ["OE6"], "JN78": ["OE5", "OE3", "OK#"], "JN87": ["HG#", "OE4"],
    "JN88": ["OE3", "OE1", "OK#", "OM#"], "JN66": ["OE8", "I#", "S5#"],
    "JN86": ["HG#", "S5#", "9A#"], "JN68": ["DL#", "OE5"], "JN58": ["DL#"],
}


# --- the board ---------------------------------------------------------------------

def _xy(loc: str) -> tuple[int, int] | None:
    """'JN88' -> (98, 138): square numbers east and north, 0..179."""
    loc = (loc or "").strip().upper()[:4]
    if len(loc) != 4 or not ("A" <= loc[0] <= "R" and "A" <= loc[1] <= "R"
                             and isnum(loc[2:])):
        return None
    return (ord(loc[0]) - 65) * 10 + int(loc[2]), (ord(loc[1]) - 65) * 10 + int(loc[3])


def _loc(x: int, y: int) -> str:
    return f"{chr(65 + x // 10)}{chr(65 + y // 10)}{x % 10}{y % 10}"


def valid_center(loc: str) -> bool:
    return _xy(loc) is not None


def squares(center: str) -> list[str]:
    """The 64 squares row by row, north first; [] for a bad center."""
    xy = _xy(center)
    if xy is None:
        return []
    cx, cy = xy
    cy = min(max(cy, N - 1 - CENTER[0]), 179 - CENTER[0])   # stay on the globe
    return [_loc((cx - CENTER[1] + c) % 180, cy + CENTER[0] - r)
            for r in range(N) for c in range(N)]


def _ll(loc: str) -> tuple[float, float]:
    x, y = _xy(loc)
    return y - 90 + 0.5, x * 2 - 180 + 1.0


def km(a: str, b: str) -> int:
    (la1, lo1), (la2, lo2) = _ll(a), _ll(b)
    t = math.pi / 180
    h = math.sin((la2 - la1) * t / 2) ** 2 + \
        math.cos(la1 * t) * math.cos(la2 * t) * math.sin((lo2 - lo1) * t / 2) ** 2
    return round(12742 * math.asin(math.sqrt(min(1.0, h))))


def country(loc: str) -> str:
    """Country code of a square ('' outside the table)."""
    lat, lon = _ll(loc)
    r, c = int(lat - LAT0), int((lon - LON0) // 2)
    if 0 <= r < len(COUNTRY) and 0 <= c < len(COUNTRY[r]):
        return COUNTRY[r][c]
    return ""


def label(loc: str) -> str:
    """What the board shows next to the locator: the prefix of the country."""
    pats = SQUARE_PATTERNS.get(loc) or PATTERNS.get(country(loc)) or []
    return pats[0].rstrip("#") if pats else ""


def callsign(loc: str, rng: random.Random | None = None, fallback: str = "OE#") -> str:
    """A contest call of 4-5 characters that fits the square."""
    rng = rng or random.SystemRandom()
    pats = SQUARE_PATTERNS.get(loc) or PATTERNS.get(country(loc)) or [fallback]
    pat = rng.choice(pats).replace("#", str(rng.randrange(10)))
    n = max(1, rng.choice((4, 5)) - len(pat))
    return pat + "".join(chr(65 + rng.randrange(26)) for _ in range(n))


def neighbours(board: list[str], loc: str) -> list[str]:
    if loc not in board:
        return []
    i = board.index(loc)
    r, c = divmod(i, N)
    return [board[(r + dr) * N + c + dc] for dr in (-1, 0, 1) for dc in (-1, 0, 1)
            if (dr or dc) and 0 <= r + dr < N and 0 <= c + dc < N]


def placement_text(stations: dict[str, str]) -> str:
    return ",".join(f"{loc}:{stations[loc]}" for loc in sorted(stations))


def commit(stations: dict[str, str], salt: str) -> str:
    return hashlib.sha256(f"{placement_text(stations)}|{salt}".encode()).hexdigest()[:16]


def parse_placement(text: str) -> dict[str, str] | None:
    out = {}
    for item in text.split(","):
        loc, sep, call = item.partition(":")
        loc, call = loc.upper(), call.upper()
        if not sep or _xy(loc) is None or not CALL_RE.match(call):
            return None
        out[loc] = call
    return out


def answer(stations: dict[str, str], board: list[str], hints: bool, loc: str,
           worked: set[str] | frozenset = frozenset()) -> str:
    """'<call>' if a station is there, else 'WEAK' or 'NIL'. A station the caller
    has worked already gives no hint any more (it is in the log - only the ones
    still to find are heard next door)."""
    if loc in stations:
        return stations[loc]
    if hints and any(n in stations and n not in worked for n in neighbours(board, loc)):
        return "WEAK"
    return "NIL"


def _args(parts: list[str]) -> dict[str, str]:
    return {k.lower(): v for k, s, v in (p.partition("=") for p in parts) if s}


# --- one game ----------------------------------------------------------------------

def new_state(center: str, hints: bool, first: bool, opp: str) -> dict:
    return {"v": 1, "c": center.upper()[:4] if center else "", "h": bool(hints),
            "first": first, "opp": opp, "st": "setup", "me": {}, "salt": "", "hm": "",
            "ht": "", "tready": False, "mc": [], "pend": "", "tc": [], "ser": 0,
            "res": "", "reveal": None, "check": "", "sent_end": False, "acc": not first,
            "pause": "",
            "at": int(time.time())}


class Game:
    """Wraps the game dict; every action returns the lines to send."""

    def __init__(self, state: dict, rng: random.Random | None = None) -> None:
        self.s = state
        self.rng = rng or random.SystemRandom()

    # --- what is what
    @property
    def board(self) -> list[str]:
        return squares(self.s["c"])

    def worked(self) -> int:
        return sum(1 for m in self.s["mc"] if m[1] == "QSO")

    def lost(self) -> int:
        return sum(1 for t in self.s["tc"] if t[1] == "QSO")

    def ready(self) -> bool:
        return bool(self.s["hm"])

    def my_turn(self) -> bool:
        s = self.s
        if s["st"] != "play" or s["pend"] or s.get("pause"):
            return False
        return len(s["mc"]) == len(s["tc"]) if s["first"] else len(s["tc"]) > len(s["mc"])

    def their_turn(self) -> bool:
        s = self.s
        if s["st"] != "play":
            return False
        mine = len(s["mc"]) + (1 if s["pend"] else 0)
        return mine > len(s["tc"]) if s["first"] else mine == len(s["tc"])

    def distance(self, calls: list) -> int:
        return sum(km(self.s["c"], x[0]) for x in calls if x[1] == "QSO")

    # --- setup
    def toggle(self, loc: str) -> bool:
        s = self.s
        loc = loc.upper()
        if s["st"] != "setup" or self.ready() or loc not in self.board:
            return False
        if loc in s["me"]:
            del s["me"][loc]
        elif len(s["me"]) < STATIONS:
            s["me"][loc] = callsign(loc, self.rng)
        else:
            return False
        return True

    def random_place(self) -> bool:
        if self.s["st"] != "setup" or self.ready() or len(self.board) < STATIONS:
            return False
        locs = self.rng.sample(self.board, STATIONS)
        self.s["me"] = {loc: callsign(loc, self.rng) for loc in locs}
        return True

    def set_ready(self) -> list[str]:
        s = self.s
        if s["st"] != "setup" or self.ready() or len(s["me"]) != STATIONS or not s["c"]:
            return []
        s["salt"] = os.urandom(4).hex()
        s["hm"] = commit(s["me"], s["salt"])
        self._maybe_start()
        return [f"READY {s['hm']}"]

    def _maybe_start(self) -> None:
        if self.s["st"] == "setup" and self.ready() and self.s["tready"]:
            self.s["st"] = "play"

    # --- play
    def cq(self, loc: str) -> list[str]:
        loc = loc.upper()
        s = self.s
        if not self.my_turn() or loc not in self.board or any(m[0] == loc for m in s["mc"]):
            return []
        s["pend"] = loc
        return [f"CQ {loc}"]

    def pause(self, on: bool) -> list[str]:
        s = self.s
        if s["st"] != "play" or bool(s.get("pause")) == on:
            return []
        s["pause"] = "me" if on else ""
        return ["PAUSE" if on else "RESUME"]

    def resign(self) -> list[str]:
        s = self.s
        if s["st"] == "end":
            return []
        s["st"], s["res"] = "end", "resigned"
        return ["RESIGN"] + self._reveal()

    def _reveal(self) -> list[str]:
        s = self.s
        if s["sent_end"] or not s["hm"]:
            return []
        s["sent_end"] = True
        return [f"END {placement_text(s['me'])} {s['salt']}"]

    def _check_end(self) -> list[str]:
        s = self.s
        if s["st"] != "play" or s["pend"] or len(s["mc"]) != len(s["tc"]):
            return []
        a, b = self.worked(), self.lost()
        if a < STATIONS and b < STATIONS:
            return []
        if a == b:
            da, db = self.distance(s["mc"]), self.distance(s["tc"])
            s["res"] = "win" if da > db else "loss" if da < db else "draw"
            s["tie"] = [da, db]
        else:
            s["res"] = "win" if a > b else "loss"
        s["st"] = "end"
        return self._reveal()

    # --- lines from the other side
    def take(self, rest: str) -> list[str]:
        p = rest.split()
        if not p:
            return []
        word, s = p[0].upper(), self.s
        if word == "OK":
            a = _args(p[1:])
            if s["st"] == "setup" and valid_center(a.get("c", "")) and (not s["me"] or s["c"]):
                if not s["c"]:
                    s["c"] = a["c"].upper()[:4]
                s["h"] = a.get("h", "1") != "0"
                s["acc"] = True
            return []
        if word == "READY" and len(p) == 2 and len(p[1]) == 16 and s["st"] in ("setup", "invited"):
            s["ht"], s["tready"] = p[1].lower(), True
            self._maybe_start()
            return []
        if word == "CQ" and len(p) == 2:
            loc = p[1].upper()
            if not self.their_turn() or loc not in self.board or any(t[0] == loc for t in s["tc"]):
                return []
            worked = {t[0] for t in s["tc"] if t[1] == "QSO"}
            a = answer(s["me"], self.board, s["h"], loc, worked)
            if a in ("NIL", "WEAK"):
                s["tc"].append([loc, a])
                out = [f"R {loc} {a}"]
            else:
                s["ser"] = s["ser"] or self.rng.randrange(100, 300)
                s["ser"] += 1
                s["tc"].append([loc, "QSO", a, s["ser"]])
                out = [f"R {loc} {a} {s['ser']:03d}"]
            return out + self._check_end()
        if word == "R" and len(p) >= 3 and p[1].upper() == s["pend"]:
            loc, what = p[1].upper(), p[2].upper()
            if what in ("NIL", "WEAK"):
                s["mc"].append([loc, what])
            elif len(p) == 4 and isnum(p[3]) and len(p[3]) <= 4 and CALL_RE.match(what):
                s["mc"].append([loc, "QSO", what, int(p[3])])
            else:
                return []
            s["pend"] = ""
            return self._check_end()
        if word in ("PAUSE", "RESUME"):
            if s["st"] == "play":
                s["pause"] = "them" if word == "PAUSE" else ""
            return []
        if word == "RESIGN":
            if s["st"] != "end":
                s["st"], s["res"] = "end", "they resigned"
            return self._reveal()
        if word == "END" and len(p) == 3:
            stations = parse_placement(p[1])
            if stations is None or s["reveal"] is not None:
                return []
            s["reveal"] = stations
            s["check"] = "ok" if self._verify(stations, p[2]) else "bad"
            out = []
            if s["st"] != "end":         # their end came first (or the states drifted)
                out = self._check_end()
                if s["st"] != "end":
                    s["st"], s["res"] = "end", s["res"] or "ended"
            return out + self._reveal()
        return []

    def _verify(self, stations: dict[str, str], salt: str) -> bool:
        s, board = self.s, self.board
        if len(stations) != STATIONS or any(loc not in board for loc in stations) \
                or commit(stations, salt) != s["ht"]:
            return False
        worked: set[str] = set()
        for m in s["mc"]:                      # in the order of the game
            want = answer(stations, board, s["h"], m[0], worked)
            if m[1] == "QSO":
                worked.add(m[0])
            got = m[2] if m[1] == "QSO" else m[1]
            if want != got:
                return False
        return True

    # --- a simple opponent (the TinyBox): next to a hit or a weak signal first
    def pick(self) -> str:
        s, board = self.s, self.board
        called = {m[0] for m in s["mc"]}
        free = [loc for loc in board if loc not in called]
        if not free:
            return ""
        nil_near = {n for m in s["mc"] if m[1] == "NIL" and s["h"] for n in neighbours(board, m[0])}
        near = [n for m in s["mc"] if m[1] == "WEAK" for n in neighbours(board, m[0])
                if n not in called and n not in nil_near]
        if near and self.rng.random() < 0.8:
            return self.rng.choice(near)
        # with hints: a "no answer" also says the squares around it are empty
        better = [loc for loc in free if loc not in nil_near] if s["h"] else free
        return self.rng.choice(better or free)

    # --- for the web GUI
    def summary(self) -> dict:
        s = self.s
        board = self.board
        return {**{k: s[k] for k in ("c", "h", "first", "opp", "st", "me", "mc", "pend", "tc",
                                     "res", "reveal", "check")},
                "tie": s.get("tie"), "ready": self.ready(), "tready": s["tready"],
                "acc": s.get("acc", True), "pause": s.get("pause", ""),
                "my_turn": self.my_turn(), "worked": self.worked(), "lost": self.lost(),
                "km": self.distance(s["mc"]),
                "cells": [{"l": loc, "p": label(loc), "km": km(s["c"], loc)} for loc in board]}
