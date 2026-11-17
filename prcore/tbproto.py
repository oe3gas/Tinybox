"""The client protocol TB1 between TBClient and TinyBox - what both sides must agree on,
in one place (Refactoring R1).

    //CLIENT TB1 v=<version> caps=<cap,cap,...> [sym=<APRS symbol>]
    //OK caps=<the caps the box grants> ...

The box grants a cap only if it knows it (CAPS) and the link allows it (UI only over
radio, the binary caps only over AX.25). Which command a cap unlocks is in the command
table of the box (tinybox/clientproto.py COMMANDS); the client's handlers of the
answers are in tbclient/core.py (_CONTROL).

Signed commands (CR93 stage 2): after the login with a key, the critical commands carry
" c=<counter> sig=<signature>" at the end of the line - needs_signature() says which.
"""

from __future__ import annotations

import re

PROTO = "TB1"

# Every cap the box knows - and the client offers (order: as the client sends them).
CAPS = {
    "CHAT": "board chat (//IN, //WHO, events)",
    "UI": "board events as UI frames (radio only)",
    "SYNC": "mailbox sync (//MLIST, //GET, //SEND ...)",
    "SYNC2": "delta sync (//SYNC, //BSYNC)",
    "SHORT": "short texts come with the headers (CR40)",
    "NUM": "member numbers in the events (CR33)",
    "HAVE": "//HAVE: what the client already has",
    "PROF": "station profiles (//PROF, //WHOIS, CR73)",
    "HSEQ": "event numbers in the history (//H)",
    "ADM": "sysop commands over the client (//ADM, CR94)",
    "LOTW": "key release via LoTW (CR113)",
    "CT": "CQ contest against the box (CR122)",
    "CTR": "CQ contest between two clients through the box (CR122)",
    "PR": "Prefix raten in the board (CR123)",
    "GAMES": "leaderboards (CR126)",
    "GAME": "signed game results (CR127)",
    "PRM": "//P after a terminal command: the client shows the prompt (CR134)",
    "CMD": "//CMD <line>: a mailbox command also inside a board (CR130)",
    "FC": "//GETFC [locator] -> //FC: the weather forecast, compact (CR72)",
    "Z": "compressed texts (binary: AX.25 only)",
    "IMG": "images in a board (binary)",
    "BFILE": "files in a board (binary, CR86)",
}

# CR134: in client mode the box does not send its prompt over the air - after a
# command typed in the terminal only this short mark; the client shows TERM_PROMPT
PROMPT_MARK = "//P"
TERM_PROMPT = "TinyBox (A,B,C,F,H,J,K,L,R,S,?) >"

# what a client offers: CHAT, UI where it wants UI frames, the rest, the binary ones on AX.25
UI_CAP = "UI"
BINARY_CAPS = ("Z", "IMG", "BFILE")
CLIENT_CAPS = tuple(c for c in CAPS if c not in (UI_CAP, *BINARY_CAPS))


def client_caps(ui: bool, binary: bool) -> str:
    """The caps= value of //CLIENT: 'CHAT,UI,SYNC,...' (UI right after CHAT)."""
    caps = list(CLIENT_CAPS)
    if ui:
        caps.insert(1, UI_CAP)
    if binary:
        caps += BINARY_CAPS
    return ",".join(caps)


# --- signed commands (CR93 stage 2) ------------------------------------------------

SIG_RE = re.compile(r"^c=(\d{1,12})$")


def needs_signature(cmd: str, parts: list[str]) -> bool:
    """The commands that need a signature after the login. parts = the words of the
    line without '//' (parts[0] is the command)."""
    if cmd in ("SEND", "KILL", "ADM"):
        return True
    if cmd == "PROF":
        return parts[1:] != ["?"]
    if cmd == "SYNC":
        return any(p.lower().startswith("k=") for p in parts[1:])
    if cmd == "GAME":                       # CR127: a result counts only signed
        return len(parts) > 1 and parts[1].upper() == "RES"
    return False


def with_signature(line: str, counter: int, sig: str) -> str:
    """'//KILL 5' -> '//KILL 5 c=3 sig=..'"""
    return f"{line} c={counter} sig={sig}"


def split_signature(line: str) -> tuple[str, int | None, str | None]:
    """'//KILL 5 c=3 sig=..' -> ('//KILL 5', 3, '..'); without them (line, None, None)."""
    words = line.split()
    if len(words) >= 3 and words[-1].startswith("sig=") and (m := SIG_RE.match(words[-2])):
        return " ".join(words[:-2]), int(m.group(1)), words[-1][4:]
    return line, None, None
