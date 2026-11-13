"""CR127: the results of chess and CQ contest games, signed, to the TinyBox.

A game counts on the leaderboard of the box only when both players report it and
the reports match (tinybox/gamereport.py). Both clients know the game id (the one
who invites makes it and sends it along) and the course of the game, so they
come to the same hash. Finished games wait in the settings ("game_reports") and
go out signed at the next login at the home box; reports the box keeps as
pending are asked for again (//GAME ST) at every login.

Games against the TinyBox itself and games without an id (older client on the
other side) are not reported.
"""

from __future__ import annotations

import hashlib
import os
import time

KEEP = 100                     # remembered reports
SENT_STATES = ("sent", "pending")


def new_id() -> str:
    return os.urandom(8).hex()


def chess_hash(moves: list[str]) -> str:
    return hashlib.sha256(("chess|" + " ".join(moves)).encode()).hexdigest()[:16]


def contest_hash(state: dict) -> tuple[str, int]:
    """Over the course of a CQ contest, the same on both sides: the commitments of
    the placements and the calls of both, the inviting side first."""
    mine = [m[0] for m in state.get("mc", [])]
    theirs = [t[0] for t in state.get("tc", [])]
    a, b = (mine, theirs) if state.get("first") else (theirs, mine)
    ha, hb = (state.get("hm", ""), state.get("ht", "")) if state.get("first") else \
        (state.get("ht", ""), state.get("hm", ""))
    text = "contest|" + ha + "|" + hb + "|" + ",".join(a) + "|" + ",".join(b)
    return hashlib.sha256(text.encode()).hexdigest()[:16], len(a) + len(b)


NOTE = {"counted": "📊 result counted on the leaderboard of the box",
        "pending": "📊 result reported - it counts when {vs} reports it too",
        "mismatch": "📊 result NOT counted: {vs} reported something else",
        "limit": "📊 result not counted: 50 games of you two today already",
        "nokey": "📊 result not counted: no released key at the box",
        "unsigned": "📊 result not counted: no released key at the box",
        "expired": "📊 result not counted: {vs} did not report it within 7 days",
        "old": "📊 result not counted: older than 7 days",
        "dup": "📊 result was reported already",
        "self": "📊 result not counted", "bad": "📊 result not counted"}


class Reports:
    def __init__(self, core) -> None:
        self.core = core
        self._asked = False            # pending ones asked for in this login

    @property
    def items(self) -> list[dict]:
        return self.core.settings.setdefault("game_reports", [])

    def _save(self) -> None:
        del self.items[:-KEEP]
        self.core._save_settings()
        self.core._touch()

    def add(self, game: str, gid: str, vs: str, result: str, h: str, n: int) -> None:
        if not gid or result not in ("win", "loss", "draw"):
            return
        if any(r["id"] == gid for r in self.items):
            return
        self.items.append({"g": game, "id": gid, "vs": vs.upper(), "r": result, "h": h, "n": n,
                           "t": int(time.time()), "st": "queued"})
        self._save()
        self.flush()

    def on_login(self) -> None:
        self._asked = False
        self.flush()

    def flush(self) -> None:
        c = self.core
        if c.state != "online" or "GAME" not in c.caps or not getattr(c, "at_home", True):
            return
        for r in self.items:
            if r["st"] == "queued":
                line = (f"//GAME RES g={r['g']} id={r['id']} vs={r['vs']} r={r['r']} h={r['h']} "
                        f"n={r['n']} t={r['t']}")
                c._send(c.signed(line))
                r["st"] = "sent"
            elif r["st"] == "pending" and not self._asked:
                c._send(f"//GAME ST {r['id']}")
        self._asked = True
        self._save()

    def answer(self, rest: str) -> None:
        """//GAME OK <id> <status> / //GAME ERR <id> <reason>."""
        p = rest.split()
        if len(p) < 3:
            return
        r = next((x for x in self.items if x["id"] == p[1]), None)
        if r is None:
            return
        st = p[2] if p[0] == "OK" else ("unknown" if p[2] == "unknown" else p[2])
        if st == r["st"]:
            return
        if st == "unknown" and r["st"] in SENT_STATES:
            r["st"] = "queued"                  # the box forgot it: once more
            self._save()
            return
        r["st"] = st
        note = NOTE.get(st)
        if note and getattr(self.core, "peerchat", None) is not None:
            self.core.peerchat.note(r["vs"], note.format(vs=r["vs"]))
        self._save()

    def summary(self) -> dict:
        n = {"counted": 0, "waiting": 0, "not": 0}
        for r in self.items:
            if r["st"] == "counted":
                n["counted"] += 1
            elif r["st"] in ("queued", "sent", "pending"):
                n["waiting"] += 1
            elif r["st"] != "dup":
                n["not"] += 1
        return n
