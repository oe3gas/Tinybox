"""The status bar of the client (CR110): what is going on, per channel, right now.

Each channel gets three groups of chips, made from the state the core keeps anyway:

    phase     one chip - Connecting (SABM .. UA), Signing in (//CLIENT .. //OK),
              Wait 4 sysop (//AUTHWAIT), In board, Disconnecting; with another
              TBClient: Probing, Checking key, Verified / Known / First contact /
              Other key / Wrong signature / Older client
    activity  what runs: mail and bulletin sync, history, pictures and files up
              and down, profiles, certificate, sysop command, lines held back;
              with a TBClient: history compare, delivering, serving, ping, speed
              test, chess, heard list
    link      queue (frames waiting in Direwolf), chat via UI or I-frames, link
              quality; with a TBClient: the send budget and the quality both ways

A chip: {"id", "t" (text), "c" (blue | amber | red | grey | done), "busy",
"p" (0..100 or None), "fin" (a job that ends)}. When a "fin" chip is gone while
the channel is still up, the Tracker keeps it for FADE_SEC as "done" (green):
the GUI lets it fade out over that time (age = seconds since it ended).

The modem chips in the top bar (Direwolf/KISS up, TX, RX) come from the same
snapshot: seconds since the last own and the last other frame or byte; TX also
stays lit while frames wait to go out (txq, CR117).
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from . import budget

if TYPE_CHECKING:
    from .channels import Channel
    from .core import ClientCore

FADE_SEC = 5.0              # a finished job: green, fading out
ASK_SEC = 120               # an asked answer (certificate, trust, ADM) is waited for this long
SYNC_FAIL_SEC = 30          # a failed sync stays red this long
BUSY_SEC = 60               # profiles, heard list: waited for at most
IO_SEC = 2.0                # TX/RX lit after the last byte or frame

SYNC_NAME = {"mail": "Mail sync", "bulletins": "Bulletin sync", "login": "Sync after login",
             "fetch": "Fetching texts", "send": "Sending mail"}
PEER_STATE = {"verified": ("✓ Verified by {issuer}", "blue"), "known": ("✓ Known key", "blue"),
              "first": ("First contact – key stored", "blue"),
              "changed": ("Other key – check it!", "red"),
              "bad": ("Wrong signature", "red"), "old": ("Older client – no key check", "grey")}


def chip(id: str, text: str, color: str = "blue", *, busy: bool = False, p: float | None = None,
         fin: bool = False, done: str = "") -> dict:
    out = {"id": id, "t": text, "c": color, "busy": busy, "fin": fin}
    if p is not None:
        out["p"] = max(0, min(100, round(p)))
    if done:
        out["dt"] = done
    return out


def _pct(done: int, total: int) -> float | None:
    return done * 100 / total if total > 0 else None


def _bytes(done: int, total: int) -> str:
    return f"{done}/{total} B" if total else f"{done} B"


def bars(n: int | None) -> str:
    return "▮" * n + "▯" * (5 - n) if n is not None else "–"


# --- phase --------------------------------------------------------------------------

def _tries(c: "Channel", phases: tuple[str, ...]) -> str:
    """CR112: " · SABM 3/10" while the link is in one of these phases (Direwolf fork
    or our own AX.25), else ""."""
    l2 = c.link.l2()
    if not l2 or l2.get("phase") not in phases or not l2.get("rc"):
        return ""
    return f" · {l2['phase'].upper()} {l2['rc']}" + (f"/{l2['n2']}" if l2.get("n2") else "")


def phase(core: "ClientCore", c: "Channel", mono: float) -> dict:
    st = c.state
    if st == "connecting":
        return chip("phase", "Connecting" + (_tries(c, ("sabm", "sabme")) or " …"), busy=True)
    if st == "disconnecting":
        return chip("phase", "Disconnecting" + (_tries(c, ("disc",)) or " …"), "amber", busy=True)
    if st == "offline":
        if "retry-out" in (c.reason or "") or "no answer" in (c.reason or ""):   # CR112 (8)
            return chip("phase", "Retry-out (no answer)", "red")
        failed = (c.ended or {}).get("kind") == "failed"
        return chip("phase", "Not reached" if failed else "Offline", "red" if failed else "grey")
    if core.chan is c and c.mode == "tinybox":
        a = core.auth.get("state", "")
        if not core.handshake_done:
            return chip("phase", "Connected", "grey")
        if a == "wait":
            return chip("phase", "Wait 4 sysop", "amber", busy=True)
        if a == "refused":
            return chip("phase", "Login refused" + (f": {core.auth.get('reason')}"
                                                    if core.auth.get("reason") else ""), "red")
        if a == "ok" or core.caps:
            if core.board:
                return chip("phase", f"In board {core.board.get('name', '')}")
            return chip("phase", "Client mode")
        return chip("phase", "Signing in …", busy=True)
    if c.peer is not None:
        s = c.peer.auth.state
        if not s:
            return chip("phase", "Checking key …", busy=True)
        text, color = PEER_STATE.get(s, (s, "grey"))
        return chip("phase", text.format(issuer=c.peer.auth.issuer or "?"), color)
    if c.probed and not c.mode and mono < c._probe_until:
        return chip("phase", "Probing …", busy=True)
    if c.mode == "terminal":
        return chip("phase", "Terminal", "grey")
    return chip("phase", "Connected", "grey")


# --- activity -----------------------------------------------------------------------

def _box_activity(core: "ClientCore", now: float) -> list[dict]:
    out: list[dict] = []
    s = core.sync.status
    if s.get("running"):
        name = SYNC_NAME.get(s.get("scope", ""), "Sync")
        step = s.get("step", "")
        out.append(chip("sync", f"{name} · {step}" if step else name, busy=True,
                        p=_pct(s.get("done", 0), s.get("total", 0)), fin=True,
                        done=f"{name} ✓"))
    elif s.get("step") in ("failed", "cancelled") and now - s.get("ended", 0) < SYNC_FAIL_SEC:
        name = SYNC_NAME.get(s.get("scope", ""), "Sync")
        out.append(chip("sync", f"{name} failed" + (f": {s['error']}" if s.get("error") else ""),
                        "red"))
    b = core.board or {}
    if b.get("loading"):
        out.append(chip("hist", "Loading history", busy=True, fin=True, done="History ✓"))
    peer_wants = {x for x in (getattr(ch.peer.img, "_want", None) for ch in core.channels.values()
                              if ch.peer is not None) if x}
    for store, word in ((core.images, "Picture"), (core.bfiles, "File")):
        up = store.upload
        if up and up.get("state") in ("waiting", "sending"):
            name = f" {up['name']}" if up.get("name") else ""
            out.append(chip(f"{word}-up", f"{word} ↑{name} {_bytes(up.get('sent', 0), up.get('size', 0))}",
                            busy=up["state"] == "sending", p=_pct(up.get("sent", 0), up.get("size", 0)),
                            fin=True, done=f"{word} ↑ sent ✓"))
        elif up and up.get("state") == "error":
            out.append(chip(f"{word}-up", f"{word} ↑ failed" +
                            (f": {up['error']}" if up.get("error") else ""), "red"))
        for h, ld in store.loading.items():
            if ld.get("error") or h in peer_wants:
                continue
            out.append(chip(f"{word}-dn-{h}", f"{word} ↓ {_bytes(ld.get('done', 0), ld.get('total', 0))}",
                            busy=True, p=_pct(ld.get("done", 0), ld.get("total", 0)), fin=True,
                            done=f"{word} ↓ ✓"))
    for call, u in core.uploads.items():                 # pictures others are sending
        out.append(chip(f"rx-img-{call}", f"Picture from {call} {_bytes(u.get('got', 0), u['size'])}",
                        "grey", busy=True, p=_pct(u.get("got", 0), u["size"]), fin=True,
                        done=f"Picture from {call} ✓"))
    if core._hold:
        out.append(chip("held", f"Lines held ({len(core._hold)})", "amber"))
    if core.profiles.busy_at and now - core.profiles.busy_at < BUSY_SEC:
        out.append(chip("prof", "Profiles", busy=True, fin=True, done="Profiles ✓"))
    for key, text in (("cert", "Certificate"), ("trust", "Trusted boxes"), ("adm", "Sysop command")):
        t = core.asking.get(key)
        if t and now - t < ASK_SEC:
            out.append(chip(key, text, busy=True, fin=True, done=f"{text} ✓"))
    return out


def _peer_activity(core: "ClientCore", c: "Channel", now: float, mono: float) -> list[dict]:
    p = c.peer
    out: list[dict] = []
    if p.hist_wait:
        out.append(chip("phist", "History compare", busy=True, fin=True, done="History ✓"))
    if p.pending:
        out.append(chip("deliver", f"Delivering {len(p.pending)}", busy=True, fin=True,
                        done="Delivered ✓"))
    for word, part, store in (("Picture", p.img, core.images.loading),
                              ("File", p.files, core.file_loading)):
        h = part._want
        if h:
            ld = store.get(h, {})
            if not ld.get("error"):
                out.append(chip(f"p{word}-dn", f"{word} ↓ {_bytes(ld.get('done', 0), ld.get('total', 0))}",
                                busy=True, p=_pct(ld.get("done", 0), ld.get("total", 0)), fin=True,
                                done=f"{word} ↓ ✓"))
    if p.serving:
        sv = p.serving                                     # CR117: progress from AGW 'Y'
        done = sv.get("done", 0)
        out.append(chip("serve", f"Serving {sv['what']} to {c.target} "
                                 f"({_bytes(done, sv['bytes']) if done else str(sv['bytes']) + ' B'})",
                        busy=True, p=_pct(done, sv["bytes"]) if sv.get("start") else None, fin=True,
                        done=f"{p.serving['what'].capitalize()} sent ✓"))
    f = p.fun
    if f._ping is not None:
        out.append(chip("ping", "Ping …", busy=True))
    elif f.pings and now - f.pong_at < FADE_SEC:
        out.append({**chip("ping-r", f"Ping {f.pings[-1]:.1f} s", "done"),
                    "age": round(now - f.pong_at, 1)})
    st = f.st or {}
    if st.get("state") == "running" and now - st.get("at", 0) < 600:
        out.append(chip("st", "Speed test …", busy=True))
    elif st.get("state") == "done" and now - st.get("end", 0) < FADE_SEC:
        out.append({**chip("st-r", f"Speed ↑ {st.get('out')} ↓ {st.get('in')} B/s", "done"),
                    "age": round(now - st["end"], 1)})
    g = f.game if "FUN" in p.caps else None
    if g and not g.get("result"):
        out.append(chip("chess", "Chess · your move", "amber") if f._my_turn()
                   else chip("chess", "Chess · their move", "grey"))
    if p.heard_wait and now - p.heard_wait < BUSY_SEC:
        out.append(chip("heard", "Heard there …", busy=True, fin=True, done="Heard list ✓"))
    return out


# --- link ---------------------------------------------------------------------------

def _link(core: "ClientCore", c: "Channel", mono: float) -> list[dict]:
    out: list[dict] = []
    kind = c.link.kind
    if c.state != "online":
        return out
    if kind == "axudp":
        out.append(chip("via", "AXUDP", "grey"))
    elif kind == "telnet":
        out.append(chip("via", "Telnet test port", "grey"))
    if c.outstanding is not None:
        out.append(chip("queue", f"Queue {c.outstanding}", "amber" if c.outstanding >= 7 else "grey"))
    l2 = c.link.l2()                                       # CR112: retries, version, window
    if l2 and l2.get("phase") == "recovery":
        rc, n2 = l2.get("rc", 0), l2.get("n2", 0)
        out.append(chip("retry", f"Retry {rc}" + (f"/{n2}" if n2 else ""),
                        "red" if n2 and rc >= n2 - 2 else "amber", busy=True))
    if l2 and l2.get("mod") and kind not in ("telnet",):
        out.append(chip("l2", ("v2.2" if l2["mod"] == 128 else "v2.0") +
                        (f" · k={l2['k']}" if l2.get("k") else ""), "grey"))
    ld = core.load
    if ld and time.time() - ld.get("at", 0) < 120 and kind not in ("axudp", "telnet"):
        out.append(chip("load", f"Channel {ld['load']} %",
                        "red" if ld["load"] >= 70 else "amber" if ld["load"] >= 40 else "grey"))
    if core.chan is c and c.mode == "tinybox":
        if core.board and kind not in ("axudp", "telnet"):
            out.append(chip("chatvia", "Chat via UI" if "UI" in core.caps else "Chat via I-frames",
                            "grey"))
        q = core.quality.get(core.cfg.mycall)
        if q is not None and kind not in ("axudp", "telnet"):
            out.append(chip("q", f"Link {bars(q)}", "red" if q <= 1 else "grey"))
    if c.peer is not None:
        if budget.of(core).slowed(c.target):
            out.append(chip("budget", "Budget: answers slowed", "amber"))
        q = c.peer.quality_summary(mono) or {}
        if "out" in q:
            t = "?" if q.get("tentative") else ""
            out.append(chip("pq", f"↑ {bars(q['out']['bars'])} ↓ {bars(q['in']['bars'])}{t}", "grey"))
    return out


# --- the finished jobs ----------------------------------------------------------------

class Tracker:
    """Remembers the chips of the last snapshot; a finished job (fin) stays as
    "done" for FADE_SEC. Also when the bytes of a link last moved (TX/RX)."""

    def __init__(self) -> None:
        self.last: dict[tuple[int, str], dict] = {}
        self.done: dict[tuple[int, str], tuple[dict, float]] = {}
        self.io: dict[int, tuple[int, int, float, float]] = {}   # n -> rx, tx, rx_at, tx_at

    def step(self, n: int, chips: list[dict], alive: bool, now: float) -> list[dict]:
        ids = {c["id"] for c in chips}
        for key in [k for k in self.last if k[0] == n and k[1] not in ids]:
            old = self.last.pop(key)
            if alive and old.get("fin") and old["c"] != "red":
                self.done[key] = (chip(key[1], old.get("dt") or old["t"] + " ✓", "done"), now)
        for c in chips:
            self.last[(n, c["id"])] = c
            self.done.pop((n, c["id"]), None)
        if not alive:
            for key in [k for k in self.done if k[0] == n]:
                del self.done[key]
        out = []
        for key, (c, t) in list(self.done.items()):
            if now - t >= FADE_SEC:
                del self.done[key]
            elif key[0] == n:
                out.append({**c, "age": round(now - t, 1)})
        return out

    def bytes_moved(self, n: int, rx: int, tx: int, now: float) -> tuple[float, float]:
        orx, otx, rat, tat = self.io.get(n, (rx, tx, 0.0, 0.0))
        if rx != orx:
            rat = now
        if tx != otx:
            tat = now
        self.io[n] = (rx, tx, rat, tat)
        return rat, tat

    def forget(self, alive: set[int]) -> None:
        for d in (self.last, self.done):
            for key in [k for k in d if k[0] not in alive]:
                del d[key]
        for n in [n for n in self.io if n not in alive]:
            del self.io[n]


def tracker_of(core) -> Tracker:
    t = getattr(core, "_activity", None)
    if t is None:
        t = core._activity = Tracker()
    return t


def build(core: "ClientCore") -> dict:
    """For the snapshot: {"chans": [{n, label, peer, phase, act, link}], "modem": {...}}."""
    now, mono = time.time(), time.monotonic()
    tr = tracker_of(core)
    chans = []
    rx_at, tx_at = core.rx_at, core.tx_at
    txq = 0                                   # CR117: frames still to go out, all channels
    for n, c in sorted(core.channels.items()):
        if not n:
            continue
        alive = c.state == "online"
        act: list[dict] = []
        if alive and core.chan is c and c.mode == "tinybox":
            act = _box_activity(core, now)
        elif alive and c.peer is not None:
            act = _peer_activity(core, c, now, mono)
        fading = [x for x in act if x["c"] == "done"]
        act = [x for x in act if x["c"] != "done"]
        act += tr.step(n, act, alive, now) + fading
        r, _t = tr.bytes_moved(n, c.link.rx_bytes, c.link.tx_bytes, now)
        rx_at = max(rx_at, r)
        # CR117: bytes handed over or frames waiting are not TX - that is the queue
        # chip; TX is the PTT (fork) or, without it, an own frame on the air
        if c.outstanding:
            txq += c.outstanding
        chans.append({"n": n, "label": c.label or c.target, "state": c.state,
                      "kind": "box" if core.chan is c and c.mode == "tinybox"
                      else "peer" if c.peer is not None else "term",
                      "phase": phase(core, c, mono), "act": act, "link": _link(core, c, mono)})
    tr.forget(set(core.channels))
    if core.dcd_on:                                        # CR112: the fork's DCD
        rx_at = now
    rs = core.radio_state()
    port = core.port
    fork = getattr(port, "fork", None) or {}
    ld = core.load if core.load and now - core.load.get("at", 0) < 120 else {}
    return {"chans": chans,
            "modem": {"via": rs.get("via", ""), "up": rs.get("up"),
                      "rx": round(now - rx_at, 1) if rx_at else None,
                      "tx": round(now - tx_at, 1) if tx_at else None, "io": IO_SEC,
                      "txq": txq,
                      # CR117: the PTT itself (fork events) - None: no PTT signal known
                      "ptt": bool(core.ptt_on) if getattr(port, "events", False) else None,
                      "fork": fork.get("version", ""), "features": fork.get("features", []),
                      "events": bool(getattr(port, "events", False)),
                      "load": ld.get("load"), "load_tx": ld.get("tx")}}

