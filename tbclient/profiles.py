"""Profiles in the client (CR73): the own one and those of the others.

Own profile (name, locator, home BBS): typed in the web GUI, kept in the
client's settings and given to the TinyBox. The TinyBox keeps the binding
copy (one per call without SSID); //OK prof=<crc> tells what it has, so the
profile goes on the air only when the two differ. The newer one wins (t =
time of the last change): a change in the terminal (NL JN88EP) comes back
to the client, a change in the client goes to the TinyBox.

Profiles of the others: fetched with //WHOIS for the stations in the board,
kept for a week (settings["profiles"]), shown in the member list with the
distance from the own locator.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from prcore import aprs
from prcore import profile as pf

if TYPE_CHECKING:
    from .core import ClientCore

STALE_SEC = 7 * 86400        # profiles of others: fetched again after a week
SNOOZE_SEC = 7 * 86400       # "Later" on the invitation: asked again after a week
CACHE_MAX = 300              # profiles of others kept at most
WHOIS_MAX = 10               # calls per //WHOIS (limit of the TinyBox)


def base(call: str) -> str:
    return call.upper().split("-", 1)[0]


class Profiles:
    def __init__(self, core: ClientCore) -> None:
        self.core = core
        self.error = ""                       # field the TinyBox refused (//PROF ERR)
        self.box_crc: str | None = None       # prof= of the last //OK (None: not known)
        self._asked: set[str] = set()         # //WHOIS sent in this connection
        self._queue: list[str] = []           # calls for the next //WHOIS
        self._flush_planned = False

    # --- own profile ----------------------------------------------------------------

    @property
    def mine(self) -> dict:
        """{'name', 'loc', 'home', 't'}. Before the first entry the locator of
        tbclient.conf ([station] locator) is the proposal, with t = 0."""
        p = self.core.settings.get("profile")
        if isinstance(p, dict):
            return {"name": p.get("name", ""), "loc": p.get("loc", ""),
                    "home": p.get("home", ""), "t": int(p.get("t", 0))}
        return {"name": "", "loc": self.core.cfg.locator, "home": "", "t": 0}

    @property
    def ready(self) -> bool:
        """Connected to a TinyBox that knows profiles."""
        return self.core.state == "online" and "PROF" in self.core.caps

    def set(self, name: str, loc: str, home: str) -> str:
        """From the GUI. Returns '' or the field that is wrong."""
        try:
            fields = pf.check(name, loc, home)
        except pf.ProfileError as exc:
            return str(exc)
        self._store({**fields, "t": int(time.time())})
        self.core.settings.pop("prof_snooze", None)
        self.core._save_settings()
        self.error = ""
        if self.ready:
            self._send_mine()
        self.core._touch()
        return ""

    def later(self) -> None:
        """'Later' on the invitation."""
        self.core.settings["prof_snooze"] = int(time.time()) + SNOOZE_SEC
        self.core._save_settings()
        self.core._touch()

    @property
    def ask(self) -> bool:
        """Show the invitation: connected, name or locator missing, not snoozed."""
        return self.ready and not pf.complete(self.mine) \
            and time.time() > self.core.settings.get("prof_snooze", 0)

    def _store(self, p: dict) -> None:
        self.core.settings["profile"] = {f: p.get(f, "") for f in pf.FIELDS} | {"t": int(p["t"])}
        self.core._save_settings()

    def _send_mine(self) -> None:
        self.core._send(f"//PROF {pf.encode(self.mine)}")

    # --- protocol --------------------------------------------------------------------

    def on_ok(self, rest: str) -> None:
        """//OK ... prof=<crc>|-: what the TinyBox has. Equal: nothing on the air."""
        self._asked.clear()
        if "PROF" not in self.core.caps:
            self.box_crc = None
            return
        box = next((w[5:] for w in rest.split() if w.startswith("prof=")), None)
        self.box_crc = box
        mine = self.mine
        if box is None or box == pf.crc(mine):
            return
        if box == "-":
            if not pf.empty(mine) and self.core.settings.get("profile") is not None:
                self._send_mine()             # only what the user really entered
        else:
            self.core._send("//PROF ?")       # who is newer? the answer has t=

    def on_line(self, rest: str) -> None:
        """//PROF OK <crc> | ERR <field> | = <crc> t=.. loc=.. | -"""
        word, _, more = rest.partition(" ")
        if word == "OK":
            self.box_crc, self.error = more.strip(), ""
            self.core.console.append("*** profile stored at the TinyBox")
        elif word == "ERR":
            self.error = more.strip()
            self.core.console.append(f"*** the TinyBox refused the profile ({self.error})")
        elif word == "-":
            self.box_crc = "-"
            if not pf.empty(self.mine) and self.core.settings.get("profile") is not None:
                self._send_mine()
        elif word == "=":
            crc, _, fields = more.partition(" ")
            box = pf.decode(fields)
            mine = self.mine
            if self.core.settings.get("profile") is None or box["t"] >= mine["t"]:
                try:                          # the TinyBox has the newer one: take it
                    checked = pf.check(box["name"], box["loc"], box["home"])
                except pf.ProfileError:
                    return
                self._store({**checked, "t": box["t"]})
                self.box_crc = crc
                self.core.console.append("*** profile taken from the TinyBox")
            else:
                self._send_mine()             # ours is newer
        self.core._touch()

    def on_whois(self, rest: str) -> None:
        """//WI <call> loc=.. home=.. name=..  or  //WI <call> -"""
        call, _, fields = rest.partition(" ")
        if not call:
            return
        cache = self.core.settings.setdefault("profiles", {})
        entry = {"at": int(time.time())}
        if fields.strip() != "-":
            p = pf.decode(fields)
            entry |= {f: p[f] for f in pf.FIELDS}
        cache[base(call)] = entry
        if len(cache) > CACHE_MAX:
            for old in sorted(cache, key=lambda c: cache[c].get("at", 0))[:len(cache) - CACHE_MAX]:
                del cache[old]

    def on_whois_end(self) -> None:
        self.core._save_settings()
        self.core._touch()

    # --- profiles of the others --------------------------------------------------------

    def want(self, calls) -> None:
        """Stations seen in the board: fetch the unknown or old profiles, a
        moment later and together (one //WHOIS for a whole //WHO line)."""
        if not self.ready:
            return
        cache = self.core.settings.get("profiles", {})
        now = time.time()
        me = base(self.core.cfg.mycall)
        for c in calls:
            b = base(c)
            if b == me or b in self._asked or b.startswith("TBCHAT"):
                continue
            if now - cache.get(b, {}).get("at", 0) > STALE_SEC:
                self._asked.add(b)
                self._queue.append(b)
        if self._queue and not self._flush_planned:
            self._flush_planned = True
            asyncio.get_event_loop().call_later(0.5, self._flush)

    def _flush(self) -> None:
        self._flush_planned = False
        queue, self._queue = self._queue, []
        if not self.ready:
            self._asked.difference_update(queue)
            return
        for i in range(0, len(queue), WHOIS_MAX):
            self.core._send("//WHOIS " + ",".join(queue[i:i + WHOIS_MAX]))

    def link_lost(self) -> None:
        self._asked.clear()
        self._queue = []
        self.box_crc = None

    # --- for the GUI ------------------------------------------------------------------

    def snapshot(self, calls) -> dict:
        mine = self.mine
        here = aprs.locator_to_latlon(mine["loc"] or self.core.cfg.locator or "")
        cache = self.core.settings.get("profiles", {})
        others = {}
        for c in calls:
            p = cache.get(base(c))
            if not p or pf.empty(p):
                continue
            row = {"name": p.get("name", ""), "loc": p.get("loc", ""), "home": p.get("home", "")}
            there = aprs.locator_to_latlon(row["loc"]) if row["loc"] else None
            if here and there:
                km, deg = aprs.distance_bearing(here, there)
                row["km"], row["deg"] = round(km), round(deg)
            others[c] = row
        return {"profile": {f: mine[f] for f in pf.FIELDS}, "profile_set": "profile" in self.core.settings,
                "profile_err": self.error, "profile_ask": self.ask, "profile_box": self.ready,
                "profiles": others}
