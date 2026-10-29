"""The testbed folder: tbtest.conf, the generated tinybox.conf, the folders.

`tbtest init` writes both files. tbtest.conf may be edited (ports, calls);
tinybox.conf is generated from it - run `tbtest init` again after a change.
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
MAX_USERS = 10

# Fictional calls, OE and DL alternating. Only ever used on loopback.
USERS = ["OE1TBA", "DL1TBB", "OE3TBC", "DL2TBD", "OE5TBE",
         "DL3TBF", "OE6TBG", "DL4TBH", "OE8TBI", "DL5TBJ"]

RUBRIC = "TBTEST"                         # bulletins of the testbed
BOARDS = {"TREFF": "7d    General meeting point",     # pictures allowed
          "TECH": "30d   Technical questions",
          "RUNDE": "live  Live round, nothing is stored"}


class BedError(Exception):
    pass


@dataclass
class Bed:
    dir: Path
    box_call: str = "OE3TBX-1"
    sysop_call: str = "OE3TBS"           # nobody of the users: no sysop rights for them
    box_port: int = 10193                # AXUDP of the test box
    user_port: int = 10201               # AXUDP of user 1, user n: + n - 1
    air_port: int = 10190                # TCP: tbtest's "radio" (swallows everything)
    web_port: int = 8180                 # sysop web GUI of the test box
    telnet_port: int = 6400              # telnet port of the test box (manual tests)
    users: list[str] = field(default_factory=lambda: list(USERS))

    # --- paths -------------------------------------------------------------------------

    @property
    def conf_path(self) -> Path:
        return self.dir / "tbtest.conf"

    @property
    def box_conf(self) -> Path:
        return self.dir / "tinybox.conf"

    @property
    def runs(self) -> Path:
        return self.dir / "runs"

    def user_dir(self, call: str) -> Path:
        return self.dir / "users" / call

    def port_of(self, call: str) -> int:
        return self.user_port + self.users.index(call)

    # --- tbtest.conf -------------------------------------------------------------------

    def save(self) -> None:
        text = f"""# tbtest - testbed for TinyBox. Written by `tbtest init`, may be edited;
# after a change run `tbtest init` again (it writes tinybox.conf anew).
# Everything runs on 127.0.0.1 - the calls are fictional and never go on the air.

[testbed]
box_call    = {self.box_call}      # the test box (mailbox_call)
sysop_call  = {self.sysop_call}        # sysop of the test box - none of the users
box_port    = {self.box_port}         # UDP: AXUDP of the test box
user_port   = {self.user_port}         # UDP: AXUDP of user 1, the next users +1, +2 ...
air_port    = {self.air_port}         # TCP: the dummy radio of tbtest (swallows every frame)
web_port    = {self.web_port}          # sysop web GUI of the test box: http://127.0.0.1:{self.web_port}/
telnet_port = {self.telnet_port}          # telnet port of the test box (for manual tests)

[users]
# 1 to {MAX_USERS} calls; `tbtest run -u n` takes the first n
calls = {", ".join(self.users)}
"""
        self.conf_path.write_text(text, encoding="utf-8")

    @classmethod
    def load(cls, folder: Path) -> "Bed":
        bed = cls(Path(folder))
        if not bed.conf_path.is_file():
            raise BedError(f"{bed.conf_path} not found - run `tbtest init` first")
        cp = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
        cp.read(bed.conf_path, encoding="utf-8")
        t = cp["testbed"] if cp.has_section("testbed") else {}
        bed.box_call = t.get("box_call", bed.box_call).strip().upper()
        bed.sysop_call = t.get("sysop_call", bed.sysop_call).strip().upper()
        for key in ("box_port", "user_port", "air_port", "web_port", "telnet_port"):
            try:
                setattr(bed, key, int(t.get(key, getattr(bed, key))))
            except ValueError:
                raise BedError(f"tbtest.conf: {key} is not a number") from None
        if cp.has_section("users"):
            calls = cp["users"].get("calls", "")
            bed.users = [c.strip().upper() for c in calls.replace(",", " ").split() if c.strip()]
        bed.check()
        return bed

    def check(self) -> None:
        for c in [self.box_call, self.sysop_call, *self.users]:
            if not CALL_RE.match(c):
                raise BedError(f"tbtest.conf: '{c}' is not a callsign")
        if not 1 <= len(self.users) <= MAX_USERS:
            raise BedError(f"tbtest.conf: 1 to {MAX_USERS} users, not {len(self.users)}")
        bases = [u.split("-")[0] for u in self.users]
        if len(set(bases)) != len(bases):
            raise BedError("tbtest.conf: every user needs a call of his own (not only SSIDs)")
        if self.sysop_call.split("-")[0] in bases or self.box_call.split("-")[0] in bases:
            raise BedError("tbtest.conf: box and sysop call must not be user calls")
        ports = [self.box_port, self.air_port, self.web_port, self.telnet_port,
                 *range(self.user_port, self.user_port + len(self.users))]
        if any(not 1024 <= p <= 65535 for p in ports):
            raise BedError("tbtest.conf: ports must be between 1024 and 65535")
        udp = [self.box_port, *range(self.user_port, self.user_port + len(self.users))]
        tcp = [self.air_port, self.web_port, self.telnet_port]
        if len(set(udp)) != len(udp) or len(set(tcp)) != len(tcp):
            raise BedError("tbtest.conf: a port is used twice")

    # --- tinybox.conf ------------------------------------------------------------------

    def box_conf_text(self) -> str:
        peers = ", ".join(f"{u} 127.0.0.1:{self.port_of(u)}" for u in self.users)
        boards = "\n".join(f"{name:<5} = {rest}" for name, rest in BOARDS.items())
        return f"""# TinyBox of the testbed - GENERATED by `tbtest init` from tbtest.conf.
# Changes here are lost with the next `tbtest init`.
# Radio: KISS to tbtest's dummy radio on {self.air_port} - it swallows every frame,
# nothing goes on the air. The users come in over AXUDP.

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
max_users            = 20
max_msg_bytes        = 8192
idle_timeout_min     = 10
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
peers   = {peers}

[web]
enabled = yes
host    = 127.0.0.1
port    = {self.web_port}

[console]
enabled = no
monitor = yes
color   = no

[storage]
data_dir = data

[logging]
level     = INFO
monitor   = yes
log_dir   = logs
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

    def make_dirs(self) -> None:
        for sub in ("data", "logs", "users", "runs"):
            (self.dir / sub).mkdir(parents=True, exist_ok=True)

    def write_box_conf(self) -> None:
        self.make_dirs()
        self.box_conf.write_text(self.box_conf_text(), encoding="utf-8")

    def check_box_conf(self) -> None:
        """tinybox.conf must still fit tbtest.conf (peers, ports)."""
        if not self.box_conf.is_file():
            raise BedError(f"{self.box_conf} not found - run `tbtest init`")
        if self.box_conf.read_text(encoding="utf-8") != self.box_conf_text():
            raise BedError("tinybox.conf does not match tbtest.conf - run `tbtest init` "
                           "(it writes tinybox.conf anew)")
        self.make_dirs()                     # the box needs logs/ to exist


def resolve_dir(arg: str | None) -> Path:
    """-D, else TBTEST_DIR, else ../tinybox-testbed next to the repo."""
    if arg:
        return Path(arg).expanduser().resolve()
    env = os.environ.get("TBTEST_DIR", "").strip()
    return Path(env).expanduser().resolve() if env else DEFAULT_DIR


def init(folder: Path, force: bool = False) -> tuple[Bed, bool]:
    """Create the testbed folder. An existing tbtest.conf is kept (it may have been
    edited) unless force; tinybox.conf is always written anew. Returns (bed, new)."""
    folder.mkdir(parents=True, exist_ok=True)
    bed = Bed(folder)
    new = force or not bed.conf_path.is_file()
    if new:
        bed.save()
    bed = Bed.load(folder)
    bed.write_box_conf()
    return bed, new
