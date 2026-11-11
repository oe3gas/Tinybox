"""Who is on the other end (CR76) and what two TBClients do together (CR78).

CR76 - right after an outgoing connect the client sends one line to whatever
station it reached:

    //TB? CLIENT v=<version> caps=PROF,HEARD

    TinyBox     -> //TB BOX v=<release> call=<mailbox>   (session unchanged)
    TBClient    -> //TB CLIENT v=<version> caps=PROF,HEARD
    any other   -> nothing, or "unknown command" - the channel is a terminal

A TinyBox then gets the //CLIENT handshake if no other TinyBox is in client
mode (CR45: one at a time), else the channel stays a terminal. An older
TinyBox without //TB? is still found by its "Welcome to TinyBox" line.

CR78 - two TBClients ("peers") are both terminals, with a few extras on top.
Their lines start with // and never show up as text in the terminal:

    //PROF loc=.. home=.. name=..   own profile, sent once after the //TB lines
                                    (if both know PROF and it is not empty)
    //HEARD?                        "who do you hear?" (button in the terminal)
    //HEARD <call>=<min> ...        answer: up to 10 stations, minutes ago
                                    ("//HEARD -" = nobody)

Clock: //TB? and //TB CLIENT carry t=<unix time> of the sender; the other side
shows how far the two clocks are apart (a few seconds are the air time).
Pictures: peerimg.py, files: peerfile.py.

The other side's version is compared with the own one: a newer client over
there is mentioned in the terminal.

Chat history (peerchat.py) - both sides know HIST:

    //HIST g=<gen> m=<n>:<hash> y=<n>:<hash>   right after the start: generation,
                                    my sent stream (m) and my received stream (y)
    //HM <n> <unix> <text>          a line of mine the other side is missing (lost
                                    at the last disconnect), sent again
    //HIST CLR g=<gen>              the histories differ: both delete, new generation
    //HIST DEL g=<gen>              the other one deleted its history (button):
                                    delete too, note "chat history removed"

Each side checks only its own sent stream against what the other reports (the
sender has the whole chain); a different generation means: both delete.

Link quality: no lines on the air. Each side has the counters of its own link
(Direwolf fork 'Q' over AGW, the own AX.25 over KISS/AXUDP) - they give both
directions (prcore/linkq.py), polled every 30 s by the core.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from prcore import aprs, linkq
from prcore import profile as pf
from prcore.text import isnum

from .peerauth import PeerAuth
from .peerchat import new_gen
from .peerfile import PeerFiles
from .peerfun import PeerFun
from .peerimg import PeerImages

from . import VERSION, budget

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .channels import Channel

PEER_CAPS = ("PROF", "HEARD", "HIST", "IMG", "FILE", "FUN", "AUTH")
HEARD_MAX = 10              # stations in one //HEARD line
RESEND_MAX = 10             # lines sent again at most (//HM); more missing = both delete


def probe_line(nonce: str = "") -> str:
    return (f"//TB? CLIENT v={VERSION} caps={','.join(PEER_CAPS)} t={int(time.time())}"
            + (f" n={nonce}" if nonce else ""))


def answer_line(nonce: str = "") -> str:
    return (f"//TB CLIENT v={VERSION} caps={','.join(PEER_CAPS)} t={int(time.time())}"
            + (f" n={nonce}" if nonce else ""))


def _args(text: str) -> dict[str, str]:
    out = {}
    for part in text.split():
        key, eq, value = part.partition("=")
        if eq:
            out[key.lower()] = value
    return out


def version_key(v: str) -> tuple:
    return tuple(int(x) if isnum(x) else 0 for x in v.split("."))


class Peer:
    """The TBClient on the other end of one channel."""

    def __init__(self, ch: "Channel", args: str, my_nonce: str = "") -> None:
        a = _args(args)
        self.ch = ch
        self.version = a.get("v", "")[:20]
        # clock: their time when they sent the line - ours now; the line took a
        # moment on the air, so a few seconds are no difference (CLOCK_SAME)
        t = a.get("t", "")
        self.clock_off = int(t) - int(time.time()) if isnum(t) else None
        self.caps = {c.strip().upper() for c in a.get("caps", "").split(",") if c.strip()}
        self.prof: dict | None = None
        self.heard: list[tuple[str, int]] | None = None   # (call, minutes ago)
        self.heard_at = 0
        self.asked = False
        self.quality = linkq.LinkQuality()
        self.q_at = 0                       # last counters (time), 0 = none yet
        self.q_none = False                 # the link gives no counters (Direwolf without fork)
        self._snap: tuple[int, str] | None = None   # own sent stream when //HIST went out
        self.img = PeerImages(self)          # pictures straight from the sender (peerimg.py)
        self.files = PeerFiles(self)         # files, LZHUF (peerfile.py)
        self.fun = PeerFun(self)             # ping, speed test, chess (peerfun.py)
        self.pending: list[int] = []         # sent lines (numbers) not acknowledged yet
        # CR110 (status bar): what is under way with the other client
        self.hist_wait = False               # //HIST sent, theirs not here yet
        self.heard_wait = 0.0                # //HEARD? sent at (0 = answered)
        self.serving: dict | None = None     # {"what", "bytes", "at"}: sent on their request
        their = a.get("n", "")
        self.auth = PeerAuth(self, my_nonce, their if 8 <= len(their) <= 32 and
                             their.replace("-", "").replace("_", "").isalnum() else "")

    @property
    def newer(self) -> bool:
        return version_key(self.version) > version_key(VERSION)

    def start(self) -> None:
        """Both sides know each other: tell it, send the own profile."""
        ch = self.ch
        ch.term_line("sys", f"*** {ch.target}: TBClient {self.version or '?'}")
        ch.core.console.append(f"[{ch.n}] *** {ch.target}: TBClient {self.version}")
        if self.newer:
            ch.term_line("sys", f"*** {ch.target} runs a newer tbclient ({self.version}, "
                                f"here {VERSION})")
        mine = ch.core.profiles.mine
        if "PROF" in self.caps and ch.core.settings.get("profile") is not None \
                and not pf.empty(mine):
            self._send(f"//PROF {pf.encode(mine, with_time=False)}")
        if "AUTH" in self.caps and self.auth.their_nonce:
            self.auth.send()                     # CR99: who we are; history after theirs
        else:
            self.auth._set("old")

    def trusted_now(self) -> None:
        """CR99: the other one's key is good - now the history is compared."""
        if self.hist:
            self._snap = self.store.state(self.call)["tx"]
            self.hist_wait = True
            self._send(self.store.hist_line(self.call))

    @property
    def trusted(self) -> bool:
        return self.auth.trusted

    # --- chat history (peerchat.py) --------------------------------------------------

    @property
    def hist(self) -> bool:
        return "HIST" in self.caps and self.ch.core.peerchat is not None

    @property
    def store(self):
        return self.ch.core.peerchat

    @property
    def call(self) -> str:
        return self.ch.target.upper()

    def text(self, direction: str, text: str) -> None:
        """A chat line typed here (tx) or from the other side (rx)."""
        text = text.rstrip()
        if self.hist and text:
            n = self.store.add(self.call, direction, text)
            if direction == "tx":
                self.pending.append(n)          # the tick comes when AX.25 has it

    def outstanding(self, waiting: int | None) -> None:
        """From the core's poll: nothing waiting any more = every line sent on
        this connection has arrived (AX.25 acknowledged it)."""
        if waiting == 0 and self.serving and time.monotonic() - self.serving["at"] > 2:
            self.serving = None                  # CR110: all of it is over there
            self.ch.core._touch()
        if waiting == 0 and self.pending and self.hist:
            self.store.delivered(self.call, self.pending)
            self.pending = []
            self.ch.core._touch()

    def serve(self, what: str, nbytes: int) -> None:
        """CR110: bytes go out because the other one asked (picture, file, speed test)."""
        self.serving = {"what": what, "bytes": nbytes, "at": time.monotonic()}

    def clear_history(self) -> None:
        """The button: delete here, the other side deletes too (now or at the next connect)."""
        gen = new_gen()
        self.store.clear(self.call, gen)
        self.store.note(self.call, "chat history removed")
        if self.ch.state == "online" and self.hist:
            self._send(f"//HIST DEL g={gen}")
        self.ch.core._touch()

    def _on_hist(self, rest: str) -> None:
        word, _, more = rest.partition(" ")
        a = _args(rest)
        gen = a.get("g", "")
        if word.upper() not in ("CLR", "DEL"):
            self.hist_wait = False
        if not self.hist or not gen:
            return
        if word.upper() in ("CLR", "DEL"):
            self.store.clear(self.call, gen)
            self.store.note(self.call, "chat history removed" + (
                f" by {self.ch.target}" if word.upper() == "DEL" else " (not the same on both sides)"))
            return
        mine = self.store.state(self.call)
        if gen != mine["gen"]:                   # deleted on one side, or never the same
            had = self.store.clear(self.call, max(gen, mine["gen"]))
            if had:
                self.store.note(self.call, "chat history removed (not the same on both sides)")
            return
        try:                                     # y = what they received of mine
            yn, yh = a.get("y", "0:0").split(":", 1)
            yn = int(yn)
        except ValueError:
            return
        snap_n = (self._snap or mine["tx"])[0]
        here = self.store.chain_at(self.call, "tx", yn)
        if yn >= snap_n:
            ok = here == yh                      # the same (or they got lines sent since)
            missing = []
        else:
            ok = here == yh and snap_n - yn <= RESEND_MAX
            missing = self.store.since(self.call, "tx", yn, snap_n) if ok else []
            ok = ok and len(missing) == snap_n - yn
        if not ok:
            gen = new_gen()
            self.store.clear(self.call, gen)
            self.store.note(self.call, "chat history removed (not the same on both sides)")
            self._send(f"//HIST CLR g={gen}")
            return
        for n, t, text in missing:               # lost at the last disconnect: again
            self._send(f"//HM {n} {t} {text}")
            self.pending.append(n)

    def _on_hm(self, rest: str) -> None:
        """//HM <n> <unix> <text>: a line of theirs that did not arrive last time."""
        parts = rest.split(" ", 2)
        if not self.hist or len(parts) < 3 or not isnum(parts[0]) or not isnum(parts[1]):
            return
        if int(parts[0]) == self.store.state(self.call)["rx"][0] + 1:
            self.store.add(self.call, "rx", parts[2].rstrip(), int(parts[1]))
            self.ch.term_line("sys", f"*** delivered again: {parts[2]}")

    # --- link quality (no lines on the air) -----------------------------------------

    def add_counters(self, counters: dict | None, now: float) -> None:
        if counters is None:
            self.q_none = self.q_at == 0
            return
        self.q_none = False
        self.q_at = now
        self.quality.add(counters, now)

    def quality_summary(self, now: float) -> dict | None:
        if self.q_at == 0:
            return {"none": self.q_none}
        r = self.quality.evaluate(now)
        if r is None:
            return {"none": False}
        last = self.quality.last or {}
        busy = last.get("tx_busy_ms", 0)
        steps = self.quality.cfg.steps

        def side(d):
            return {"frames": d.frames, "lost": d.lost, "loss": d.loss, "bars": d.bars(steps),
                    "tent": d.frames > 0 and not d.enough}   # few frames: repeats count
        return {"bars": r.bars, "tentative": r.tentative, "out": side(r.out), "in": side(r.inn),
                "t1": r.t1, "rej_rx": r.rej_rx, "rej_tx": r.rej_tx, "srt": r.srt,
                "rate": round(last.get("bytes_new", 0) * 1000 / busy) if busy else None,
                "age": round(now - self.q_at)}

    def _send(self, line: str) -> None:
        self.ch.core.console.append(f"[{self.ch.n}]> {line}")
        self.ch.link.send_line(line)

    def take(self, line: str) -> bool:
        """A // line from the peer: True = handled (not shown as text)."""
        word, _, rest = line[2:].partition(" ")
        word = word.upper()
        if word == "PROF":
            self._on_prof(rest)
        elif word == "HEARD?":
            if not budget.of(self.ch.core).often(self.call, "HEARD?", 2, 60):   # CR97 (TB-03)
                self._send(self._heard_line())
        elif word == "HEARD":
            self._on_heard(rest)
        elif word == "PAUTH":
            self.auth.take(rest)
        elif word in ("HIST", "HM"):
            if not self.trusted:                 # CR99 (TB-06): not with an unproven key
                log.warning("%s: //%s ignored - key not trusted (%s)", self.call, word,
                            self.auth.state or "none")
            elif word == "HIST":
                self._on_hist(rest)
            else:
                self._on_hm(rest)
        elif word in ("IMG", "I", "NOIMG"):
            if not self.img.take(word, rest):
                return False
        elif word in ("FGET", "F", "NOFILE"):
            if not self.files.take(word, rest):
                return False
        elif word in ("PING", "PONG", "ST", "STR", "CHESS"):
            if not self.fun.take(word, rest):
                return False
        else:
            return False
        self.ch.core._touch()
        return True

    # --- profile ---------------------------------------------------------------------

    def _on_prof(self, text: str) -> None:
        p = pf.decode(text)
        try:
            checked = pf.check(p["name"], p["loc"], p["home"])
        except pf.ProfileError:
            return
        self.prof = checked
        cache = self.ch.core.settings.setdefault("profiles", {})   # as //WI (CR73)
        cache[self.ch.target.upper().split("-", 1)[0]] = {"at": int(time.time()), **checked}
        self.ch.core._save_settings()
        row = self.profile_row()
        text = ", ".join(x for x in (row.get("name"), row.get("loc"),
                                      f"{row['km']} km {_dir(row['deg'])}" if "km" in row else "",
                                      f"home BBS {row['home']}" if row.get("home") else "") if x)
        self.ch.term_line("sys", f"*** {self.ch.target}: {text}")

    def profile_row(self) -> dict:
        if not self.prof:
            return {}
        row = dict(self.prof)
        mine = self.ch.core.profiles.mine
        here = aprs.locator_to_latlon(mine["loc"] or self.ch.core.cfg.locator or "")
        there = aprs.locator_to_latlon(row["loc"]) if row.get("loc") else None
        if here and there:
            km, deg = aprs.distance_bearing(here, there)
            row["km"], row["deg"] = round(km), round(deg)
            row["here"], row["there"] = here, there            # the little map (CR78)
            row["myloc"] = mine["loc"] or self.ch.core.cfg.locator
        return row

    # --- heard list ------------------------------------------------------------------

    def ask_heard(self) -> bool:
        if "HEARD" not in self.caps or self.ch.state != "online":
            return False
        self.asked = True
        self.heard_wait = time.time()
        self._send("//HEARD?")
        self.ch.term_line("sys", f"*** asking {self.ch.target} who it hears ...")
        self.ch.core._touch()
        return True

    def _heard_line(self) -> str:
        now = time.time()
        core = self.ch.core
        skip = {self.ch.target, core.cfg.mycall}
        calls = sorted(((c, t) for c, t in core.heard_at.items() if c not in skip),
                       key=lambda ct: -ct[1])[:HEARD_MAX]
        if not calls:
            return "//HEARD -"
        return "//HEARD " + " ".join(f"{c}={int((now - t) // 60)}" for c, t in calls)

    def _on_heard(self, text: str) -> None:
        heard = []
        for part in text.split():
            call, eq, mins = part.partition("=")
            if eq and isnum(mins):
                heard.append((call.upper()[:9], int(mins)))
        self.heard, self.heard_at = heard, int(time.time())
        self.heard_wait = 0.0
        if heard:
            self.ch.term_line("sys", f"*** {self.ch.target} hears: " + ", ".join(
                f"{c} ({m} min)" if m else f"{c} (now)" for c, m in heard))
        else:
            self.ch.term_line("sys", f"*** {self.ch.target} has heard nobody yet")

    # --- for the GUI ------------------------------------------------------------------

    def summary(self, now: float) -> dict:
        return {"v": self.version, "newer": self.newer, "caps": sorted(self.caps),
                "prof": self.profile_row(), "heard": self.heard, "heard_at": self.heard_at,
                "hist": self.hist, "img": self.img.ok, "file": self.files.ok,
                "clock": self.clock_off, "q": self.quality_summary(now),
                "fun": self.fun.summary() if "FUN" in self.caps else None,
                "auth": self.auth.summary()}


def _dir(deg: float) -> str:
    return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][round((deg % 360) / 45) % 8]
