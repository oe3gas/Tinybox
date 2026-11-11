"""TinyBox client protocol (PLANUNG.md section 12).

A TinyBox client announces itself right after login with one line:

    //CLIENT TB1 v=2026.10.11 caps=CHAT,UI sym=/-

CR93: first the client logs in with the key of its user (Ed25519, prcore/auth.py):

    //AUTH? n=<challenge> box=<mailbox call>           mailbox
    //AUTH sig=<signature> pub=<public key>            client
    //AUTHWAIT fp=7F3A-91C2-44E0                       new key: the sysop releases it
    //ERR auth bad_signature|revoked|too_many_keys|... refused

and only with a released key the mailbox answers with the features both sides know:

    //OK TB1 caps=CHAT,UI

CR93 stage 2: after the login the critical commands come signed, each one on
its own - AX.25 checks no sender, a frame can be slipped into a running link:

    //SEND ... c=<n> sig=<signature>     (also covers subject and text lines)
    //KILL ... c=<n> sig=..
    //SYNC ... k=.. ... c=<n> sig=..     (only with k=, deleting)
    //PROF t=.. ... c=<n> sig=..         (storing; //PROF ? is not signed)

signed: auth.command_message() - the command line without c= and sig=, n, the
login challenge, mailbox and call; n goes up with every signed command of the
login. Unsigned, wrong or an old n: refused (//ERR send sig_missing|sig_bad|
sig_replay, //ERR kill sig_.., //ERR sync sig_.., //PROF ERR sig_..), the text
of a //SEND is read anyway so it never runs as commands. In such a session the
terminal commands that write or delete (S, SP, SB, K, KM, E, N, NH, NL) are
refused: the client does that, signed.

CR99: //TRUST? -> //TRUST <this box>=<key> <trusted box>=<key> ... (public keys,
the client checks other TBClients' certificates with them).

CR94 (Variante B) - the sysop over the radio, only through the client: with cap
ADM (granted only to the sysop call logged in with the key released here) one
console command at a time, signed like the commands above:

    //ADM <console command> c=<n> sig=..   e.g. //ADM STATUS, //ADM REL 12
        -> //ADM> <line> ... //ADMEND ok|unknown|refused

v = client version (date). If the client in this repository is newer, the
answer also has cur=<newest version> and news=<number of the feature bulletin
in the rubric TBNEWS>, see clientnews.py.

From then on the session is in client mode: no prompts, and in a chat board
the client gets machine-readable lines instead of the human text:

    //IN <n> <board> <keep> <last seq>     entered board number n
    //H <unix time> <call>: <text>         history line (boards with history)
    //WHO <call>[=<sym>] ...               who else is in the board (with NUM:
                                           //WHO <n> <call>[=<sym>] ... - member numbers)
    //OUT <board>                          left the board
    #<seq> ...                             chat events, format see chat.py

A client that announces itself again on a session that is still in a board
(it restarted while the AX.25 link stayed up) gets the //IN and //WHO lines
right after the //OK, and nobody is told about a join: it never left. So the
client does not have to guess where it is, and the mailbox command "C <n>" -
chat text inside a board - stays off the air.

Before all that (CR76): right after its connect a TBClient sends

    //TB? CLIENT v=2026.11.07 caps=PROF,HEARD

to whatever station it reached. The TinyBox answers with one line and changes
nothing else (terminal users keep their prompts):

    //TB BOX v=<release> call=<mailbox call>

Another TBClient answers //TB CLIENT v=.. caps=.. (tbclient/peer.py), every other
station ignores the line or calls it an unknown command.

Other client commands:
    //BOARDS              -> //B <n> <board> <keep> <users> <description> ... //BEND
    //RESEND <a>-<b>      (inside a board) events a..b again, only to this client
    //LOST <a>-<b>        (inside a board) events a..b missed, too many to send again:
                          only counted for the receive quote (PLANUNG.md 14.3)
    //SYM <symbol>|-      new APRS symbol; inside a board the others get "=<call> <sym>"
    //HIST max=<n> [since=<unix>] [before=<unix>]   (inside a board) stored lines on
                          request, only to this client: //H ... //HEND <n> <older>
                          (CR13; //IN tells hist=<count> last=<unix> now=<unix>)
    //MOTD                (inside a board) -> //MOTD <crc> <text> | //MOTD -  (CR3;
                          //IN tells motd=<crc>, the client asks only if it changed)
    //MLIST, //GET, //SEND ...   offline mailbox, see clientsync.py
    //FPUT, //FGET        files in a board (CR86, cap BFILE), see chatfile.py;
    //IMGPUT, //IMG       small images in the chat (CR12), see chatimg.py;
                          //IN tells img (8 KB) or img=<max, hex> where allowed

caps: CHAT = chat lines in the format above, UI = the client hears the
mailbox directly and takes chat events from the UI frames to TBCHAT-<n>
instead of I-frames. UI is only granted on radio sessions.
SYNC = offline mailbox commands, SYNC2 = delta sync (//SYNC, //BSYNC, CR26),
Z = message texts may come LZHUF-compressed, IMG = chat images
(both binary, radio sessions only). NUM = member numbers instead of calls in
the chat events (+n call, -n, =n, %n b) and the %Q statistics line (CR33);
//OK then tells q=<frames>/<minutes>/<min frames>/<bar steps>.
SHORT = //SYNC knows short=<bytes>: only personal mail up to that size comes
with its text, everything else only as a header (CR40).

HSEQ = //H history lines carry the event number of the line:
    //H <unix> #<n hex> <call>: <text>
so a comment "~^5 ..." finds its quoted line also in the history (lines
stored before schema 10 come without a number).

PROF = profiles (CR73): name, locator and home BBS of a station, one per call
without SSID (prcore/profile.py has the line format). //OK then tells
prof=<crc> (4 hex digits) or prof=- (no profile stored here); the client
compares it with its own and only sends or fetches when they differ:
    //PROF t=<unix> loc=<loc> home=<bbs> name=<name>   store it (newer one wins)
                          -> //PROF OK <crc>, //PROF ERR <field>, or - if the
                             profile here is newer - //PROF = ... (see below)
    //PROF ?              -> //PROF = <crc> t=<unix> loc=.. home=.. name=.. | //PROF -
    //WHOIS <call>[,<call>...]   profiles of other stations (max. 10)
                          -> //WI <call> loc=.. home=.. name=.. | //WI <call> - ... //WIEND
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from prcore import auth
from prcore import profile as pf
from prcore.release import RELEASE
from prcore.text import isnum

from . import clientnews, clientsync, profiles
from .addressing import base_call

if TYPE_CHECKING:
    from .session import Session

log = logging.getLogger(__name__)

# CR93 (OE3GAS, 09.11.2026: "sofort"): client mode only after the login with the
# user's key. No setting - only the test suite switches it off (tests/__init__.py)
# for the tests that are about something else.
REQUIRE_AUTH = True

PROTO = "TB1"
KNOWN_CAPS = ("CHAT", "UI", "SYNC", "SYNC2", "Z", "IMG", "NUM", "SHORT", "HAVE", "PROF",
              "HSEQ", "ADM", "BFILE", "LOTW")
IMG_COMMANDS = ("IMGPUT", "IMG")
FILE_COMMANDS = ("FPUT", "FGET")          # CR86: files in a board
# APRS symbol: table ('/', '\' or an overlay 0-9/A-Z) + symbol code (any printable)
SYMBOL_RE = re.compile(r"^[/\\0-9A-Z][!-~]$")


@dataclass
class ClientInfo:
    proto: str
    caps: set[str] = field(default_factory=set)
    symbol: str = ""
    version: str = ""          # v= of the client ('' = older client without it)

    @property
    def ui(self) -> bool:
        return "UI" in self.caps


def _parse_args(parts: list[str]) -> dict[str, str]:
    args = {}
    for p in parts:
        key, sep, value = p.partition("=")
        if sep:
            args[key.lower()] = value
    return args


# --- CR93 stage 2: signed commands ------------------------------------------------

SIG_RE = re.compile(r"^c=(\d{1,12})$")


def split_signature(line: str) -> tuple[str, int | None, str | None]:
    """'//KILL 5 c=3 sig=..' -> ('//KILL 5', 3, '..'); without them (line, None, None)."""
    words = line.split()
    if len(words) >= 3 and words[-1].startswith("sig=") and (m := SIG_RE.match(words[-2])):
        return " ".join(words[:-2]), int(m.group(1)), words[-1][4:]
    return line, None, None


def critical(cmd: str, parts: list[str]) -> bool:
    """The commands that need a signature after the login (see module doc)."""
    if cmd in ("SEND", "KILL", "ADM"):
        return True
    if cmd == "PROF":
        return parts[1:] != ["?"]
    if cmd == "SYNC":
        return any(p.lower().startswith("k=") for p in parts[1:])
    return False


def check_signed(s: Session, plain: str, counter: int | None, sig: str | None,
                 payload: list[str] | tuple[str, ...] = ()) -> str | None:
    """None if the command may run, else the reason. Only sessions logged in with
    a key are checked (without REQUIRE_AUTH - tests - there is none)."""
    if not s.auth or s.auth_pub is None:
        return None
    if sig is None or counter is None:
        reason = "sig_missing"
    else:
        try:
            raw = auth.b64d(sig, 64)
        except auth.AuthError:
            raw = None
        msg = auth.command_message(s.cfg.station.mailbox_call, s.call, s.auth_nonce or "",
                                   counter, plain, payload)
        if raw is None or not auth.verify(s.auth_pub, msg, raw):
            reason = "sig_bad"
        elif counter <= s.auth_ctr:
            reason = "sig_replay"
        else:
            s.auth_ctr = counter
            return None
    log.warning("%s: %s refused (%s)", s.call, plain.split()[0][:12], reason)
    return reason


def _refuse(s: Session, cmd: str, reason: str) -> None:
    if cmd == "KILL":
        s.out(f"//ERR kill {reason}", "//KEND")
    elif cmd == "PROF":
        s.out(f"//PROF ERR {reason}")
    elif cmd == "ADM":
        s.out(f"//ADMEND {reason}")
    else:
        s.out(f"//ERR {cmd.lower()} {reason}")


def handle(s: Session, line: str) -> None:
    """One line starting with '//' (in the mailbox or inside a board)."""
    line, counter, sig = split_signature(line.strip())
    parts = line[2:].split()
    if not parts:
        return
    cmd = parts[0].upper()
    if s.client is not None and critical(cmd, parts) and cmd != "SEND":
        # //SEND is checked when its text is in: the lines must be read anyway
        reason = check_signed(s, line, counter, sig)
        if reason:
            _refuse(s, cmd, reason)
            return
    if cmd == "TB?":
        tb_probe(s)
    elif cmd == "CLIENT":
        _client(s, parts[1:])
    elif cmd == "AUTH":
        _auth(s, parts[1:])
    elif cmd in ("LOTW?", "LOTWP") and (s.client is not None
                                        or getattr(s, "_wait_pub", None) is not None):
        _lotw(s, cmd, parts[1:])            # CR113: also while the key waits for the sysop
    elif s.client is None:
        s.out("//ERR not a client session")
    elif cmd == "CERT?":
        _cert(s)
    elif cmd == "TRUST?":
        _trust_list(s)
    elif cmd == "ADM":
        _admin(s, line[2:][3:].strip())
    elif cmd == "BOARDS":
        _boards(s)
    elif cmd == "RESEND":
        _resend(s, parts[1:])
    elif cmd == "LOST":
        _resend(s, parts[1:], replay=False)
    elif cmd == "SYM":
        _symbol(s, parts[1:])
    elif cmd == "HIST":
        _hist(s, parts[1:])
    elif cmd == "MOTD":
        _motd(s)
    elif cmd == "PROF":
        _profile(s, line[2:][4:].strip())
    elif cmd == "WHOIS":
        _whois(s, parts[1:])
    elif cmd == "SEND" and "SYNC" in s.client.caps:
        clientsync.handle(s, cmd, parts[1:],
                          signed=lambda lines: check_signed(s, line, counter, sig, lines))
    elif cmd in clientsync.COMMANDS:
        clientsync.handle(s, cmd, parts[1:])
    elif cmd in IMG_COMMANDS:
        if "IMG" not in s.client.caps:
            s.out(f"//ERR {cmd} needs IMG")
        else:
            img = s.service.chat.images
            (img.put if cmd == "IMGPUT" else img.get)(s, parts[1:])
    elif cmd in FILE_COMMANDS:
        if "BFILE" not in s.client.caps:
            s.out(f"//ERR {cmd} needs BFILE")
        else:
            f = s.service.chat.files
            (f.put if cmd == "FPUT" else f.get)(s, parts[1:])
    else:
        s.out(f"//ERR unknown {cmd}")


def tb_probe(s: Session) -> None:
    """CR76: //TB? [CLIENT v=.. caps=..] - a TBClient asks right after its connect
    what it reached. Only the answer, the session stays as it is (terminal or
    client mode); the client sends //CLIENT afterwards if it wants the chat."""
    # on a line of its own: the prompt before has no CR
    s.out("", f"//TB BOX v={RELEASE} call={s.cfg.station.mailbox_call}")


def _client(s: Session, parts: list[str]) -> None:
    if not parts or parts[0].upper() != PROTO:
        s.out("", f"//ERR protocol {PROTO} only")
        return
    args = _parse_args(parts[1:])
    wanted = {c.strip().upper() for c in args.get("caps", "").split(",") if c.strip()}
    caps = {c for c in wanted if c in KNOWN_CAPS}
    if s.origin != "radio" or s.service.chat.ui_send is None:
        caps.discard("UI")        # telnet, or no radio link: chat lines come as I-frames
    if s.origin not in ("radio", "axudp") or not hasattr(s.transport, "write_bytes"):
        caps.discard("Z")         # compressed texts are binary: AX.25 only (radio, AXUDP)
        caps.discard("IMG")       # images too (and the raw bytes of an upload)
        caps.discard("BFILE")     # and files (CR86)
    if s.cfg.chat.image_max <= 0:
        caps.discard("IMG")       # the sysop switched images off
    if s.cfg.chat.file_max <= 0:
        caps.discard("BFILE")
    symbol = args.get("sym", "")
    info = ClientInfo(PROTO, caps, symbol if SYMBOL_RE.match(symbol) else "",
                      args.get("v", "")[:20])
    if not REQUIRE_AUTH:              # tests about something else
        _client_ok(s, info)
        return
    # CR93: client mode only after the login with the user's key - also when the
    # client restarted on a link that stayed up: it needs a fresh challenge for
    # its signed commands (stage 2)
    s.client = None
    s.auth, s.auth_pub, s.auth_nonce, s.auth_ctr = False, None, None, 0
    s._client_wait = info
    s._auth_nonce = auth.new_nonce()
    s.out("", f"//AUTH? n={s._auth_nonce} box={s.cfg.station.mailbox_call}")


MAX_KEYS = 5                     # keys per call (devices) that are not revoked
DEVICE_RE = re.compile(r"^[0-9A-F]{8}$")      # keyed hash of the PC name (auth.Identity.device)


def _auth(s: Session, parts: list[str]) -> None:
    """//AUTH sig=<86> pub=<43> [dev=<8 hex>] [cert=<certificate>]: the answer to
    //AUTH? (CR93).

    One key per device (OE3GAS, 10.11.2026): every key of a call is released on
    its own. Released key: client mode. At another TinyBox (stage 3) a valid
    certificate of a home BBS the sysop here trusts (TRUST) does the same. New
    key: proves it holds it (the signature), waits for the sysop (//AUTHWAIT).
    Revoked: refused; more than MAX_KEYS: refused. Every answer starts on a line of
    its own: a prompt written before it would hide it from the client."""
    info, nonce = getattr(s, "_client_wait", None), getattr(s, "_auth_nonce", None)
    args = _parse_args(parts)
    if info is None or nonce is None:
        s.out("", "//ERR auth not_asked")
        return
    s._auth_nonce = None                         # one answer per challenge
    try:
        pub = auth.b64d(args.get("pub", ""), 32)
        sig = auth.b64d(args.get("sig", ""), 64)
    except auth.AuthError:
        s.out("", "//ERR auth syntax")
        return
    box, call = s.cfg.station.mailbox_call, auth.base(s.call)
    if not auth.verify(pub, auth.login_message(box, call, nonce), sig):
        log.warning("%s: client login with a wrong signature", s.call)
        s.out("", "//ERR auth bad_signature")
        return
    store, pub64, fp = s.service.store, auth.b64e(pub), auth.fingerprint(pub)
    dev = args.get("dev", "") if DEVICE_RE.match(args.get("dev", "")) else ""
    row = store.key_get(call, pub64)
    if row is not None and dev and row["device"] != dev:
        store.key_device(row["id"], dev)
    if row is not None and row["status"] == "revoked":
        s.out("", "//ERR auth revoked")
        return
    if row is not None and row["status"] == "active":
        _logged_in(s, info, pub, nonce, "")
        return
    if args.get("cert"):                          # stage 3: a certificate of the home BBS
        issuer, why = _cert_ok(s, args["cert"], call, pub64)
        if not why:
            if row is None or row["status"] != "cert":
                store.key_put(call, pub64, "cert", device=dev,
                              note=f"certificate of {issuer} via {s.call}")
            _logged_in(s, info, pub, nonce, issuer)
            return
        log.warning("%s: certificate not taken (%s)", s.call, why)
    if row is None or row["status"] == "cert":
        # a new device, or its certificate is gone: waits for the sysop
        if row is None and len([k for k in store.keys_of(call)
                                if k["status"] != "revoked"]) >= MAX_KEYS:
            log.warning("%s: new client key %s refused - %d keys already", s.call, fp, MAX_KEYS)
            s.out("", "//ERR auth too_many_keys")
            return
        store.key_put(call, pub64, "pending", device=dev, note=f"from {s.call} via {s.origin}")
        log.warning("%s: new client key %s%s - waits for the sysop (USER OK %s %s)", s.call, fp,
                    f" ({dev})" if dev else "", call, fp[:4])
        s.service.key_waiting(call, fp, s.call, dev)
    s._wait_pub, s._wait_nonce = pub, nonce      # CR113: LoTW may still release it
    s.out("", f"//AUTHWAIT fp={fp}")


def _lotw(s: Session, cmd: str, args: list[str]) -> None:
    """CR113 stage 2: //LOTW? and //LOTWP (tinybox/lotwbox.py)."""
    from . import lotwbox
    if cmd == "LOTW?":
        lotwbox.ask(s)
        return
    if lotwbox.part(s, args) and s.client is None:     # released by LoTW: log in now
        info, pub, nonce = getattr(s, "_client_wait", None), s._wait_pub, s._wait_nonce
        s._wait_pub = s._wait_nonce = None
        if info is not None:
            _logged_in(s, info, pub, nonce, "")


def _logged_in(s: Session, info: ClientInfo, pub: bytes, nonce: str, issuer: str) -> None:
    s._wait_pub = None
    s.auth, s.auth_pub, s.auth_nonce, s.auth_ctr = True, pub, nonce, 0
    s.auth_cert = issuer
    s._client_wait = None
    log.info("%s: client login, key %s%s", s.call, auth.fingerprint(pub),
             f", certificate of {issuer}" if issuer else "")
    _client_ok(s, info)


def _cert_ok(s: Session, text: str, call: str, pub64: str) -> tuple[str, str]:
    """(issuer, '') for a certificate that lets this key log in here, else (issuer, why)."""
    try:
        c = auth.parse_cert(text)
    except auth.AuthError:
        return "", "syntax"
    if c["call"] != call or c["pub"] != pub64:
        return c["issuer"], "for another call or key"
    if c["issuer"] == s.cfg.station.mailbox_call.upper():
        return c["issuer"], "issued here"          # at home only the released key counts
    trusted = s.service.store.trust_get(c["issuer"])
    if trusted is None:
        return c["issuer"], f"{c['issuer']} not trusted here (TRUST)"
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    if not auth.check_cert(c, auth.b64d(trusted["pub"], 32), today):
        return c["issuer"], "expired or wrong signature"
    return c["issuer"], ""


# --- CR94 (Variante B): the sysop over the radio, through the client ------------------

ADMIN_MAX_LINES = 60


def admin_allowed(s: Session) -> bool:
    """Only the sysop's own call, logged in with the key released here (not via a
    certificate of another box) - the radio call alone gives nothing."""
    if not s.auth or s.auth_cert or s.auth_pub is None \
            or not s.service.is_sysop_call(s.call):
        return False
    row = s.service.store.key_get(auth.base(s.call), auth.b64e(s.auth_pub))
    return row is not None and row["status"] == "active"


def _admin(s: Session, command: str) -> None:
    """//ADM <console command> c=.. sig=..: one sysop console command (signed, see
    handle()). Answer: //ADM> <line> ... //ADMEND [ok|refused|unknown]."""
    from prcore.text import visible

    from .adapters.sysop import MonitorFilter, SysopConsole
    if not admin_allowed(s):
        log.warning("%s: admin command refused (not the sysop with his released key)", s.call)
        s.out("//ADMEND refused")
        return
    lines: list[str] = []
    console = SysopConsole(s.service.app, MonitorFilter(False), lines.append)
    console.out = lambda *xs: lines.extend(xs)
    log.warning("%s: admin command over %s: %s", s.call, s.origin, visible(command)[:80])
    try:
        known = console.remote(command)
    except Exception:
        log.exception("admin command %r failed", command)
        lines.append("Internal error.")
        known = True
    out = [f"//ADM> {visible(x).rstrip()}" for chunk in lines
           for x in re.split(r"[\r\n]+", str(chunk)) if x.strip()]
    s.out(*out[:ADMIN_MAX_LINES], "//ADMEND " + ("ok" if known else "unknown"))


def _trust_list(s: Session) -> None:
    """//TRUST?: this box's key and the boxes its sysop trusts - the client checks
    with them the certificates of other TBClients (CR99). Public keys only."""
    from . import keys
    me = keys.this_box(s.service)
    parts = [f"{me['box']}={me['pub']}"] + [f"{r['box']}={r['pub']}"
                                            for r in keys.trusted(s.service)][:20]
    s.out("//TRUST " + " ".join(parts))


def _cert(s: Session) -> None:
    """//CERT?: the certificate of this box for the key the user logged in with -
    only at his home BBS (the key released here, not via a certificate)."""
    row = s.service.store.key_get(auth.base(s.call), auth.b64e(s.auth_pub)) \
        if s.auth_pub is not None else None
    if not s.auth or row is None or row["status"] != "active":
        s.out("//CERT -")
        return
    until = (datetime.now(timezone.utc) + timedelta(days=auth.CERT_DAYS)).strftime("%Y%m%d")
    box = s.cfg.station.mailbox_call.upper()
    level = ""
    lw = (row.get("lotw") or "").replace("-", "")         # CR113: confirmed with LoTW
    if lw and lw >= datetime.now(timezone.utc).strftime("%Y%m%d"):
        level, until = "lotw", min(until, lw)              # not longer than the LoTW one
    s.out("//CERT " + auth.make_cert(s.service.box_identity(), s.call, row["pub"], box, until,
                                     level))
    log.info("%s: certificate issued, valid until %s%s", s.call, until,
             ", LoTW" if level else "")


def _client_ok(s: Session, info: ClientInfo) -> None:
    s.client = info
    caps = info.caps
    # newer client available (CR18): tell the version and the feature bulletin
    extra = ""
    cur = clientnews.client_version()
    if cur and clientnews.version_key(s.client.version) < clientnews.version_key(cur):
        extra = f" cur={cur}"
        if s.service.client_news_id:
            extra += f" news={s.service.client_news_id}"
    if "NUM" in caps:                 # CR33: how the TinyBox turns the counters into bars
        extra += " " + s.service.chat.quality_config()
    if "ADM" in caps and not admin_allowed(s):
        caps.discard("ADM")           # CR94: only the sysop with his own released key
    if "PROF" in caps:                # CR73: the client sends or fetches only on a change
        extra += f" prof={pf.crc(profiles.get(s.service.store, s.call))}"
    # the human prompt is still on the line: start the answer on a fresh line
    s.out("", f"//OK {PROTO} caps={','.join(sorted(caps))}{extra}")
    if s.chat_board is not None:
        # The session is still in a board: the client restarted while the AX.25
        # link stayed up (Direwolf keeps it, so the mailbox never saw a connect
        # and sent no welcome). Without this the client believes it is in no
        # board and sends the mailbox command "C <n>" - which is chat text in a
        # board and would go to everybody. //IN says where it is, and the others
        # hear nothing.
        from . import chatcmd          # local import avoids a cycle
        chatcmd.resync_client(s)


def _profile_line(p: dict) -> str:
    return f"//PROF = {pf.crc(p)} {pf.encode(p)}"


def _profile(s: Session, rest: str) -> None:
    """//PROF ? (fetch) or //PROF t=.. loc=.. home=.. name=.. (store, CR73)."""
    store = s.service.store
    mine = profiles.get(store, s.call)
    if rest == "?":
        s.out(_profile_line(mine) if mine else "//PROF -")
        return
    new = pf.decode(rest)
    try:
        fields = pf.check(new["name"], new["loc"], new["home"])
    except pf.ProfileError as exc:
        s.out(f"//PROF ERR {exc}")
        return
    if mine and mine["t"] > new["t"]:
        # changed here after the client's change (e.g. NL in the terminal): the
        # newer one wins - the client takes ours instead
        s.out(_profile_line(mine))
        return
    saved = profiles.save(store, s.call, fields, changed=new["t"] or None)
    s.out(f"//PROF OK {pf.crc(saved)}")


def _whois(s: Session, parts: list[str]) -> None:
    """//WHOIS call[,call...]: profiles of other stations (who is in the board)."""
    calls = []
    for c in " ".join(parts).replace(",", " ").upper().split():
        b = base_call(c)
        if pf.CALL_RE.match(b) and b not in calls:
            calls.append(b)
    if not calls or len(calls) > profiles.WHOIS_MAX:
        s.out("//ERR whois")
        return
    known = s.service.store.profiles_get(calls)
    rows = []
    for c in calls:
        p = known.get(c)
        rows.append(f"//WI {c} {pf.encode(p, with_time=False)}" if p and not pf.empty(p)
                    else f"//WI {c} -")
    s.out(*rows, "//WIEND")


def _iso(unix: str) -> str | None:
    if not isnum(unix):
        return None
    return datetime.fromtimestamp(int(unix), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _motd(s: Session) -> None:
    """//MOTD: text of the current board's message of the day (CR3)
    -> //MOTD <crc> <text>, or //MOTD - without one."""
    board = s.service.chat.cfg.chat.board(s.chat_board or "")
    if board is None:
        s.out("//ERR motd")
        return
    s.out(f"//MOTD {board.motd_crc} {board.motd}" if board.motd else "//MOTD -")


def _hist(s: Session, parts: list[str]) -> None:
    """//HIST max=n [since=unix] [before=unix]: history lines on request (CR13)."""
    from .chatcmd import history_rows
    hub = s.service.chat
    board = hub.cfg.chat.board(s.chat_board or "")
    args = _parse_args(parts)
    if board is None or not isnum(args.get("max", "")):
        s.out("//ERR hist")
        return
    lines, older = hub.history_page(board, int(args["max"]),
                                    after_iso=_iso(args.get("since", "")),
                                    before_iso=_iso(args.get("before", "")))
    s.out(*history_rows(lines, seq="HSEQ" in s.client.caps), f"//HEND {len(lines)} {older}")


def _symbol(s: Session, parts: list[str]) -> None:
    """//SYM <symbol>  ("-" = none): new APRS symbol, the board sees it at once."""
    sym = parts[0] if parts else ""
    if sym == "-":
        sym = ""
    if sym and not SYMBOL_RE.match(sym):
        s.out("//ERR sym")
        return
    if sym != s.client.symbol:
        s.client.symbol = sym
        s.service.chat.symbol_changed(s)


def _boards(s: Session) -> None:
    hub = s.service.chat
    rows = []
    if hub.enabled and s.origin != "sysop":
        for i, b in enumerate(hub.boards, 1):
            rows.append(f"//B {i} {b.name} {b.keep_label} {len(hub.members(b.name))} "
                        f"{b.description}".rstrip())
    s.out(*rows, "//BEND")


def _resend(s: Session, parts: list[str], replay: bool = True) -> None:
    m = re.match(r"^([0-9A-Fa-f]{1,2})-([0-9A-Fa-f]{1,2})$", parts[0] if parts else "")
    if s.chat_board is None or not m:
        s.out("//ERR resend" if replay else "//ERR lost")
        return
    first, last = int(m.group(1), 16), int(m.group(2), 16)
    if s.ui_rx is not None:                 # missed UI frames: receive quote (14.3)
        s.ui_rx.missed(first, last)
    if replay:
        lines = s.service.chat.replay(s.chat_board, first, last,
                                      legacy="NUM" not in s.client.caps)
        if lines:
            s.out(*lines)
