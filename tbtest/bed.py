"""The testbed folder: tbtest.conf and the files generated from it.

`tbtest init` writes tbtest.conf (once - it may be edited) and generates from it
    tinybox.conf            the test box
    tbclient-testbed.conf   for your own TinyBox client as a guest
Run `tbtest init` again after a change of tbtest.conf.
"""

from __future__ import annotations

import configparser
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DIR = REPO.parent / "tinybox-testbed"
CALL_RE = re.compile(r"^[A-Z0-9]{1,6}(-([0-9]|1[0-5]))?$")
MAX_USERS = 30


def _make_users(n: int) -> list[str]:
    """Fictional calls, OE and DL alternating, all with a TB/TC suffix. Only ever
    used on loopback. The first ten are those of the first testbed version."""
    first = ["OE1TBA", "DL1TBB", "OE3TBC", "DL2TBD", "OE5TBE",
             "DL3TBF", "OE6TBG", "DL4TBH", "OE8TBI", "DL5TBJ"]
    letters = [c for c in "KLMNOPQRTUVWYZ"] + [f"C{c}" for c in "ABCDEFGH"]
    out = list(first)
    i = 0
    while len(out) < n:
        pfx = "OE" if len(out) % 2 == 0 else "DL"
        digit = (len(out) * 7) % 9 + 1
        suf = letters[i]
        out.append(f"{pfx}{digit}T{'B' + suf if len(suf) == 1 else suf}")
        i += 1
    return out[:n]


USERS = _make_users(MAX_USERS)
RUBRIC = "TBTEST"                         # bulletins of the testbed
BOARDS = {"TREFF": "7d    General meeting point",     # pictures allowed
          "TECH": "30d   Technical questions",
          "RUNDE": "live  Live round, nothing is stored"}
PROFILE_NAMES = ("good", "medium", "poor")


class BedError(Exception):
    pass


@dataclass
class Bed:
    dir: Path
    box_call: str = "OE3TBX-1"
    sysop_call: str = "OE3TBS"           # nobody of the users: no sysop rights for them
    box_port: int = 10193                # AXUDP of the test box
    channel_port: int = 10192            # AXUDP: the simulated channel (relay)
    user_port: int = 10201               # AXUDP of user 1, user n: + n - 1
    air_port: int = 10190                # TCP: dummy radio port (swallows everything)
    web_port: int = 8180                 # sysop web GUI of the test box
    telnet_port: int = 6400              # telnet port of the test box (manual tests)
    users: list[str] = field(default_factory=lambda: list(USERS))
    # [radio] the simulated channel
    air_baud: int = 1200                 # 0 = no channel, frames pass at once
    txdelay_ms: int = 300
    persist: int = 63
    slottime_ms: int = 100
    mix: dict = field(default_factory=lambda: {"good": 0.5, "medium": 0.3, "poor": 0.2})
    hidden: float = 0.2
    quality: dict = field(default_factory=dict)    # call -> (profile or "", hidden or None)
    # AX.25 over AXUDP (box and users) for the slow channel
    ax_paclen: int = 256
    ax_maxframe: int = 4
    ax_t1_sec: float = 6.0
    ax_n2: int = 10
    # [guest] your own TinyBox client
    guest_call: str = "OE3GAS"
    guest_port: int = 10240
    guest_web: int = 7745
    guest_quality: str = "good"

    # --- paths -------------------------------------------------------------------------

    @property
    def conf_path(self) -> Path:
        return self.dir / "tbtest.conf"

    @property
    def box_conf(self) -> Path:
        return self.dir / "tinybox.conf"

    @property
    def guest_conf(self) -> Path:
        return self.dir / "tbclient-testbed.conf"

    @property
    def runs(self) -> Path:
        return self.dir / "runs"

    def user_dir(self, call: str) -> Path:
        return self.dir / "users" / call

    def port_of(self, call: str) -> int:
        return self.user_port + self.users.index(call)

    # --- tbtest.conf -------------------------------------------------------------------

    def save(self) -> None:
        mix = ", ".join(f"{k} {round(v * 100)}%" for k, v in self.mix.items())
        quality = "\n".join(
            f"{c} = " + " ".join(w for w in (p, "hidden" if h else "visible" if h is False
                                             else "") if w)
            for c, (p, h) in self.quality.items())
        text = f"""# tbtest - testbed for TinyBox. Written by `tbtest init`, may be edited;
# after a change run `tbtest init` again (it writes tinybox.conf and
# tbclient-testbed.conf anew). Everything runs on 127.0.0.1 - the calls are
# fictional and never go on the air.

[testbed]
box_call     = {self.box_call}      # the test box (mailbox_call)
sysop_call   = {self.sysop_call}        # sysop of the test box - none of the users
box_port     = {self.box_port}         # UDP: AXUDP of the test box
channel_port = {self.channel_port}         # UDP: the simulated channel - box and users talk through it
user_port    = {self.user_port}         # UDP: AXUDP of user 1, the next users +1, +2 ...
air_port     = {self.air_port}         # TCP: dummy radio port of box and clients (swallows every frame)
web_port     = {self.web_port}          # sysop web GUI of the test box: http://127.0.0.1:{self.web_port}/
telnet_port  = {self.telnet_port}          # telnet port of the test box (for manual tests)

[users]
# 1 to {MAX_USERS} calls; `tbtest run -u n` takes the first n
calls = {", ".join(self.users)}

[radio]
# The simulated channel in the AXUDP path: one shared half-duplex frequency.
air_baud    = {self.air_baud}         # 0 = no channel: frames pass at once (`tbtest run --air 0` too)
txdelay_ms  = {self.txdelay_ms}
persist     = {self.persist}           # p-persistence 0..255 (KISS default 63)
slottime_ms = {self.slottime_ms}
# Quality of the users: frame loss for a 256-byte frame, each direction:
# good 1 %, medium 8 %, poor 25 %. hidden = does not hear the other users (and they
# do not hear him): collisions at the box. Shares, shuffled with the seed of the run:
mix    = {mix}
hidden = {round(self.hidden * 100)}%
# AX.25 over AXUDP of box, users and guest - for the slow channel
paclen   = {self.ax_paclen}
maxframe = {self.ax_maxframe}
t1_sec   = {self.ax_t1_sec:g}
n2       = {self.ax_n2}

[quality]
# Fixed quality for single calls (wins over mix/hidden), e.g.
#   OE1TBA = poor hidden
#   DL1TBB = good visible
{quality}

[guest]
# Your own TinyBox client: tbclient.bat -c <testbed>\\tbclient-testbed.conf
call    = {self.guest_call}       # your call in the testbed (the sysop is {self.sysop_call}, not you)
port    = {self.guest_port}        # UDP: AXUDP of your client
web     = {self.guest_web}         # its web GUI: http://127.0.0.1:{self.guest_web}/
quality = {self.guest_quality}         # good | medium | poor, optional "hidden"
"""
        self.conf_path.write_text(text, encoding="utf-8")

    @classmethod
    def load(cls, folder: Path) -> "Bed":
        bed = cls(Path(folder))
        if not bed.conf_path.is_file():
            raise BedError(f"{bed.conf_path} not found - run `tbtest init` first")
        cp = configparser.ConfigParser(inline_comment_prefixes=("#", ";"), interpolation=None)
        cp.optionxform = str                       # calls in [quality] stay upper case
        cp.read(bed.conf_path, encoding="utf-8")

        def sec(name: str):
            return cp[name] if cp.has_section(name) else {}

        def num(section, key: str, default, kind=int):
            try:
                v = section.get(key, None)
                return default if v is None or not str(v).strip() else kind(str(v).strip())
            except ValueError:
                raise BedError(f"tbtest.conf: {key} is not a number") from None

        t = sec("testbed")
        bed.box_call = t.get("box_call", bed.box_call).strip().upper()
        bed.sysop_call = t.get("sysop_call", bed.sysop_call).strip().upper()
        for key in ("box_port", "channel_port", "user_port", "air_port", "web_port",
                    "telnet_port"):
            setattr(bed, key, num(t, key, getattr(bed, key)))
        if cp.has_section("users"):
            calls = cp["users"].get("calls", "")
            bed.users = [c.strip().upper() for c in calls.replace(",", " ").split() if c.strip()]
        r = sec("radio")
        bed.air_baud = num(r, "air_baud", bed.air_baud)
        bed.txdelay_ms = num(r, "txdelay_ms", bed.txdelay_ms)
        bed.persist = num(r, "persist", bed.persist)
        bed.slottime_ms = num(r, "slottime_ms", bed.slottime_ms)
        bed.ax_paclen = num(r, "paclen", bed.ax_paclen)
        bed.ax_maxframe = num(r, "maxframe", bed.ax_maxframe)
        bed.ax_t1_sec = num(r, "t1_sec", bed.ax_t1_sec, float)
        bed.ax_n2 = num(r, "n2", bed.ax_n2)
        if r.get("mix", "").strip():
            bed.mix = parse_mix(r.get("mix"))
        if r.get("hidden", "").strip():
            bed.hidden = parse_pct(r.get("hidden"), "hidden")
        if cp.has_section("quality"):
            bed.quality = {k.strip().upper(): parse_quality(v, k)
                           for k, v in cp["quality"].items() if v.strip()}
        g = sec("guest")
        bed.guest_call = g.get("call", bed.guest_call).strip().upper()
        bed.guest_port = num(g, "port", bed.guest_port)
        bed.guest_web = num(g, "web", bed.guest_web)
        bed.guest_quality = (g.get("quality", bed.guest_quality) or "good").strip().lower()
        bed.check()
        return bed

    def check(self) -> None:
        for c in [self.box_call, self.sysop_call, self.guest_call, *self.users]:
            if not CALL_RE.match(c):
                raise BedError(f"tbtest.conf: '{c}' is not a callsign")
        if not 1 <= len(self.users) <= MAX_USERS:
            raise BedError(f"tbtest.conf: 1 to {MAX_USERS} users, not {len(self.users)}")
        bases = [u.split("-")[0] for u in self.users]
        if len(set(bases)) != len(bases):
            raise BedError("tbtest.conf: every user needs a call of his own (not only SSIDs)")
        others = {self.sysop_call.split("-")[0], self.box_call.split("-")[0]}
        if others & set(bases):
            raise BedError("tbtest.conf: box and sysop call must not be user calls")
        if self.guest_call.split("-")[0] in set(bases) | {self.box_call.split("-")[0]}:
            raise BedError("tbtest.conf: [guest] call must not be a user or the box")
        udp = [self.box_port, self.channel_port, self.guest_port,
               *range(self.user_port, self.user_port + len(self.users))]
        tcp = [self.air_port, self.web_port, self.telnet_port, self.guest_web]
        if any(not 1024 <= p <= 65535 for p in udp + tcp):
            raise BedError("tbtest.conf: ports must be between 1024 and 65535")
        if len(set(udp)) != len(udp) or len(set(tcp)) != len(tcp):
            raise BedError("tbtest.conf: a port is used twice")
        if self.air_baud not in (0, 300, 1200, 2400, 4800, 9600):
            raise BedError("tbtest.conf: air_baud 0, 300, 1200, 2400, 4800 or 9600")
        if not 0 <= self.persist <= 255:
            raise BedError("tbtest.conf: persist 0 ... 255")
        if not 0 <= self.txdelay_ms <= 5000 or not 10 <= self.slottime_ms <= 1000:
            raise BedError("tbtest.conf: txdelay_ms 0 ... 5000, slottime_ms 10 ... 1000")
        if not 32 <= self.ax_paclen <= 256 or not 1 <= self.ax_maxframe <= 127 \
                or not 0.2 <= self.ax_t1_sec <= 60 or not 1 <= self.ax_n2 <= 50:
            raise BedError("tbtest.conf [radio]: paclen 32-256, maxframe 1-127, "
                           "t1_sec 0.2-60, n2 1-50")
        parse_quality(self.guest_quality, "[guest] quality")

    # --- generated files ---------------------------------------------------------------

    def peers(self) -> list[str]:
        """Box peers: every user and the guest - all reached through the channel."""
        return [f"{c} 127.0.0.1:{self.channel_port}" for c in [*self.users, self.guest_call]]

    def box_conf_text(self, air_baud: int | None = None, absolute: bool = False) -> str:
        """tinybox.conf. air_baud: another channel than tbtest.conf for one run
        (`run --air`) - then written into the run folder with absolute paths."""
        air = self.air_baud if air_baud is None else air_baud
        data = (self.dir / "data") if absolute else "data"
        logs = (self.dir / "logs") if absolute else "logs"
        boards = "\n".join(f"{name:<5} = {rest}" for name, rest in BOARDS.items())
        return f"""# TinyBox of the testbed - GENERATED by `tbtest init` from tbtest.conf.
# Changes here are lost with the next `tbtest init`.
# The users come in over AXUDP, through tbtest's simulated channel. The radio port
# is tbtest's dummy radio on {self.air_port}: it swallows every frame, nothing goes on
# the air.

[station]
mailbox_call    = {self.box_call}
sysop_call      = {self.sysop_call}
sysop_via_radio = no
qth             = Testbed

[radio]
interface = kiss

[kiss]
port        = {self.air_port}
status_port = 0               # no kisshub status: the dummy radio has none

[mailbox]
welcome_enabled      = yes
welcome_text         = TinyBox testbed - local only, no radio.
third_party          = yes
max_users            = 50
max_msg_bytes        = 8192
idle_timeout_min     = 30
bulletin_expire_days = 30
ask_profile          = yes

[telnet]
enabled = yes
host    = 127.0.0.1
port    = {self.telnet_port}

[axudp]
enabled = yes
listen  = 127.0.0.1
port    = {self.box_port}
peers   = {", ".join(self.peers())}
paclen       = {self.ax_paclen}
maxframe_ext = {self.ax_maxframe}
t1_sec       = {self.ax_t1_sec:g}
n2           = {self.ax_n2}
air_baud     = {air}            # the channel's air time: T1 after the own frames,
txdelay_ms   = {self.txdelay_ms if air else 0}             # frames heard pause T1 (half duplex)

[web]
enabled = yes
host    = 127.0.0.1
port    = {self.web_port}

[console]
enabled = no
monitor = yes
color   = no

[storage]
data_dir = {data}

[logging]
level     = INFO
monitor   = yes
log_dir   = {logs}
keep_days = 14
debug     =

[brocast]
dict_file =
publish   = no

[inbox]
enabled = no

[beacon]
enabled = no

[update]
check    = no
announce = no

[client]
mail_notify = yes

[chat]
enabled       = yes
history_lines = 20
max_line      = 200
image_max     = 8k

[chat_boards]
{boards}

[rubrics]
ALL    = To everybody
{RUBRIC} = Testbed bulletins

[forward]
enabled = no

[mqtt]
enabled = no
"""

    def guest_conf_text(self) -> str:
        return f"""# Your TinyBox client in the testbed - GENERATED by `tbtest init` from tbtest.conf
# ([guest]). Start it while `tbtest run` (or `tbtest box`) is running:
#     tbclient.bat -c {self.dir / "tbclient-testbed.conf"}
# then open http://127.0.0.1:{self.guest_web}/ - it does not touch your own client's data.
# The home box {self.box_call} is reached over AXUDP through the simulated channel
# (quality "{self.guest_quality}"). The client always needs a radio port as well: here it is
# tbtest's dummy radio, which swallows everything - nothing goes on the air.

[station]
mycall  = {self.guest_call}
locator =

[tinybox]
call           = {self.box_call}
ui             = no
auto_connect   = no
axudp          = 127.0.0.1:{self.channel_port}
axudp_port     = {self.guest_port}
axudp_paclen   = {self.ax_paclen}
axudp_maxframe = {self.ax_maxframe}
axudp_t1_sec   = {self.ax_t1_sec:g}
axudp_n2       = {self.ax_n2}
axudp_air_baud   = {self.air_baud}
axudp_txdelay_ms = {self.txdelay_ms if self.air_baud else 0}

[radio]
interface = kiss

[kiss]
port        = {self.air_port}
status_port = 0

[web]
host = 127.0.0.1
port = {self.guest_web}

[console]
color = auto

[sync]
chunk_bytes = 1024
pause_sec   = 5
on_login    = yes
short_bytes = 256

[images]
target_bytes = 2048

[storage]
data_dir = guest

[update]
check = no
"""

    def make_dirs(self) -> None:
        for sub in ("data", "logs", "users", "runs", "guest"):
            (self.dir / sub).mkdir(parents=True, exist_ok=True)

    def write_generated(self) -> None:
        self.make_dirs()
        self.box_conf.write_text(self.box_conf_text(), encoding="utf-8")
        self.guest_conf.write_text(self.guest_conf_text(), encoding="utf-8")

    def check_generated(self) -> None:
        """tinybox.conf must still fit tbtest.conf (peers, ports)."""
        if not self.box_conf.is_file():
            raise BedError(f"{self.box_conf} not found - run `tbtest init`")
        if self.box_conf.read_text(encoding="utf-8") != self.box_conf_text():
            raise BedError("tinybox.conf does not match tbtest.conf - run `tbtest init` "
                           "(it writes tinybox.conf anew)")
        self.make_dirs()                     # the box needs logs/ to exist

    # old names
    write_box_conf = write_generated
    check_box_conf = check_generated


def parse_pct(text: str, what: str) -> float:
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*%?\s*", str(text))
    if m is None or float(m.group(1)) > 100:
        raise BedError(f"tbtest.conf: {what}: a share like 20%")
    return float(m.group(1)) / 100


def parse_mix(text: str) -> dict[str, float]:
    """'good 50%, medium 30%, poor 20%' -> {'good': .5, ...}"""
    out = {}
    for part in text.split(","):
        words = part.split()
        if len(words) != 2 or words[0].lower() not in PROFILE_NAMES:
            raise BedError(f"tbtest.conf: mix '{part.strip()}': e.g. good 50%")
        out[words[0].lower()] = parse_pct(words[1], "mix")
    if abs(sum(out.values()) - 1) > 0.011:
        raise BedError("tbtest.conf: mix must add up to 100%")
    return out


def parse_quality(text: str, what: str) -> tuple[str, bool | None]:
    """'poor hidden' -> ('poor', True); 'visible' -> ('', False)."""
    prof, hid = "", None
    for w in text.lower().split():
        if w in PROFILE_NAMES:
            prof = w
        elif w == "hidden":
            hid = True
        elif w == "visible":
            hid = False
        else:
            raise BedError(f"tbtest.conf: {what}: '{w}' - good, medium, poor, hidden, visible")
    return prof, hid


def resolve_dir(arg: str | None) -> Path:
    """-D, else TBTEST_DIR, else ../tinybox-testbed next to the repo."""
    if arg:
        return Path(arg).expanduser().resolve()
    env = os.environ.get("TBTEST_DIR", "").strip()
    return Path(env).expanduser().resolve() if env else DEFAULT_DIR


def init(folder: Path, force: bool = False) -> tuple[Bed, bool]:
    """Create the testbed folder. An existing tbtest.conf is kept (it may have been
    edited) unless force; the generated files are always written anew. A tbtest.conf
    of the first version (10 users, no [radio]) is renewed, keeping its ports.
    Returns (bed, new)."""
    folder.mkdir(parents=True, exist_ok=True)
    bed = Bed(folder)
    new = force or not bed.conf_path.is_file()
    if not new and "[radio]" not in bed.conf_path.read_text(encoding="utf-8"):
        old = Bed.load(folder)
        old.users = list(USERS)
        old.save()
        new = True
    elif new:
        bed.save()
    bed = Bed.load(folder)
    bed.write_generated()
    return bed, new
