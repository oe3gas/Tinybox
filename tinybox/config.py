"""Load and validate tinybox.conf (INI format)."""

from __future__ import annotations

import configparser
import logging
import os
import re
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

# Amateur radio callsign as used in AX.25: 3-6 chars, letters and digits,
# at least one digit and one letter, optional SSID 0-15.
CALL_RE = re.compile(
    r"^(?=[A-Z0-9]*[0-9])(?=[A-Z0-9]*[A-Z])[A-Z0-9]{3,6}(-([0-9]|1[0-5]))?$"
)
# Bulletin destination, e.g. ALL, DX, WX
DEST_RE = re.compile(r"^[A-Z0-9]{1,6}$")
NEWS_RUBRIC = "TBNEWS"
MOTD_MAX = 120              # characters of a board's message of the day (CR3)      # system rubric of the client feature bulletin (CR18/CR19)

LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


class ConfigError(Exception):
    """Raised when tinybox.conf is missing or invalid."""


def normalize_call(call: str) -> str:
    return call.strip().upper()


def is_valid_call(call: str) -> bool:
    return bool(CALL_RE.match(call))


def base_call(call: str) -> str:
    """OE3GAS-1 -> OE3GAS"""
    return call.split("-", 1)[0]


@dataclass
class StationCfg:
    mailbox_call: str
    sysop_call: str
    sysop_via_radio: bool
    haddress: str = ""        # hierarchical address, e.g. OE3XTC.#NOE.AUT.EU ('' = call only)
    qth: str = ""             # shown in the R: line
    freq: str = ""            # MHz of the radio port, for the ADIF export (CR44)
    locator: str = ""         # Maidenhead locator, ADIF MY_GRIDSQUARE (CR44)

    @property
    def bbs_call(self) -> str:
        """Mailbox call as it appears in addresses, BIDs and R: lines (no SSID)."""
        return base_call(self.mailbox_call)

    @property
    def address(self) -> str:
        return self.haddress or self.bbs_call


@dataclass
class PartnerCfg:
    """[partner.CALL] - one neighbouring mailbox."""
    call: str                       # mailbox call without SSID (addresses, R: lines)
    transport: str = "agw"          # agw | tcp
    ax25_call: str = ""             # agw: call to connect to / that calls us ('' = call)
    via: list[str] = field(default_factory=list)   # agw: digipeaters / nodes
    host: str = ""                  # tcp: partner's forward port
    port: int = 0
    login: list[str] = field(default_factory=list)  # tcp: lines sent after connecting
    password: str = ""              # tcp: password this partner gives when calling us
    haddress: str = ""
    routes: list[str] = field(default_factory=list)  # personal mail: HR patterns
    areas: list[str] = field(default_factory=list)   # bulletins: flood areas, * = all
    protocol: str = "fbb"           # b1 | fbb | ascii - the most we offer this partner
    timeout: int = 120              # seconds without data
    auto: bool = True               # call by itself when mail waits (default: tcp yes, agw no)
    interval_min: int = 0           # also call every n minutes to fetch mail (0 = only to send)
    window: tuple[int, int] | None = None   # (from, to) minutes of the day, local time
    retry_min: int = 10             # after a failed call wait this long

    def in_window(self, minute_of_day: int) -> bool:
        if self.window is None:
            return True
        a, b = self.window
        return a <= minute_of_day < b if a <= b else (minute_of_day >= a or minute_of_day < b)

    @property
    def radio_call(self) -> str:
        return self.ax25_call or self.call


@dataclass
class ForwardCfg:
    enabled: bool = False     # the optional forward module (adapters/forward.py, from F2)
    bid_days: int = 60        # how long BIDs are remembered; older mail is held
    aliases: dict[str, str] = field(default_factory=dict)   # e.g. ALLOE -> AUT
    listen_host: str = "127.0.0.1"   # incoming TCP forwards (partners call us)
    listen_port: int = 0             # 0 = no incoming TCP forwards
    publish_to_brocast: bool = False # bulletins from partners also go to brocastd
    partners: dict[str, PartnerCfg] = field(default_factory=dict)

    def partner(self, call: str) -> PartnerCfg | None:
        return self.partners.get(base_call(call.strip().upper()))

    def partner_by_radio_call(self, call: str) -> PartnerCfg | None:
        call = call.strip().upper()
        for p in self.partners.values():
            if p.radio_call == call:
                return p
        return None


@dataclass
class DirewolfCfg:
    agw_host: str
    agw_port: int
    agw_radio_port: int
    reconnect_sec: int
    paclen: int
    max_outstanding: int
    # link quality (TinyBox Direwolf fork, AGW 'Q'), PLANUNG.md section 14
    quality_poll_sec: int = 30            # 0 = off
    quality_window_frames: int = 50
    quality_window_min: int = 30
    quality_min_frames: int = 20
    quality_steps: tuple[float, ...] = (5.0, 10.0, 20.0, 35.0, 50.0)
    direwolf_conf: str = ""               # CR70: [agw] direwolf_conf, resolved path or ""


@dataclass(frozen=True)
class RadioCfg:
    """[radio] which way to the radio: Direwolf over AGW or a KISS TNC (PLANUNG.md 15)."""
    interface: str = "agw"          # agw | kiss


@dataclass(frozen=True)
class KissCfg:
    """[kiss] the KISS-TCP server: kisshub (owns the TNC) or Direwolf's KISS port."""
    host: str = "127.0.0.1"
    port: int = 8101                # kisshub; Direwolf's KISS port is 8001
    channel: int = 0                # KISS port number inside the stream
    reconnect_sec: int = 5
    air_baud: int = 1200            # radio bit rate (own transmit time, T1)
    txdelay_ms: int = 300
    status_port: int = 8102         # kisshub's status query (CR41), 0 = off


@dataclass(frozen=True)
class Ax25Cfg:
    """[ax25] TinyBox's own AX.25 layer 2, used with interface = kiss."""
    version: str = "2.2"            # 2.2 = SABME first, fall back to 2.0; 2.0 = SABM only
    paclen: int = 128               # info bytes per I frame
    maxframe: int = 4               # window with modulo 8 (1..7)
    maxframe_ext: int = 7           # window with modulo 128 (v2.2)
    srej: bool = True
    n2: int = 10
    t1_min_sec: float = 3.0
    t1_max_sec: float = 30.0
    t2_sec: float = 1.5
    t3_sec: float = 300.0
    srt_init_sec: float = 2.5


@dataclass
class MailboxCfg:
    welcome_enabled: bool
    welcome_text: str
    third_party: bool
    max_users: int
    max_msg_bytes: int
    idle_timeout_min: int
    bulletin_expire_days: int


@dataclass
class TelnetCfg:
    enabled: bool
    host: str
    port: int


@dataclass
class WebCfg:
    enabled: bool
    host: str
    port: int


@dataclass
class ConsoleCfg:
    enabled: bool
    monitor: bool


@dataclass
class StorageCfg:
    data_dir: Path


@dataclass
class LoggingCfg:
    level: str
    monitor: bool
    log_dir: Path | None  # None = no log file
    debug: list[str] = field(default_factory=list)  # components on DEBUG (CR32)
    keep_days: int = 14                             # older daily files are deleted


@dataclass
class MqttCfg:
    enabled: bool
    host: str
    port: int
    tls: bool
    client_id: str
    username: str
    password_file: str
    topic_root: str


DEFAULT_RUBRICS = {
    "ALL": "all", "DX": "dx", "WX": "wx", "WETTER": "wx", "KEPS": "keps", "AMSAT": "amsat",
    "CONTES": "contest", "TEST": "contest", "NOTFUN": "notfunk", "EMCOM": "notfunk",
    "SOTA": "sota", "POTA": "pota", "TECH": "tech", "TNC": "tech", "FLOHMA": "sale",
    "SALE": "sale", "RUNDE": "net", "NET": "net", "CLUB": "club", "OEVSV": "club",
    "WARN": "notfunk",
}


@dataclass
class BrocastCfg:
    dict_file: Path | None = None   # None = DICT command answers "not available"
    publish: bool = False           # report bulletins to brocastd (ingest API)
    ingest_host: str = "127.0.0.1"
    ingest_port: int = 8090
    ingest_path: str = "/api/v1"
    token: str = ""
    max_bytes: int = 4096           # longer bulletins are cut, with a hint
    destinations: list[str] = field(default_factory=list)   # empty = all bulletins
    rubrics: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_RUBRICS))
    sync_min: int = 60              # full sync interval
    alert_destinations: list[str] = field(default_factory=lambda: ["WARN"])  # -> warning pages


@dataclass
class InboxCfg:
    enabled: bool = False
    directory: Path = Path("eingang")
    poll_sec: int = 10


# Chat board name, e.g. TREFF, DX, RUNDE
BOARD_RE = re.compile(r"^[A-Z0-9]{1,8}$")
KEEP_RE = re.compile(r"^(\d+)([HD])$")
MAX_KEEP_HOURS = 365 * 24


@dataclass
class ChatBoard:
    name: str
    keep_hours: int        # 0 = live only, nothing is stored
    description: str = ""
    motd: str = ""         # [chat_motd] (CR3): shown when entering the board
    noimg: bool = False    # "noimg" after the keep time: no images here (CR12)

    @property
    def images(self) -> bool:
        """Images in this board? Never in a live board (nothing is stored there)."""
        return not self.live and not self.noimg

    @property
    def motd_crc(self) -> str:
        """Short check value: the client fetches the text only when it changed."""
        return f"{zlib.crc32(self.motd.encode('utf-8')) & 0xFFFF:04x}" if self.motd else ""

    @property
    def live(self) -> bool:
        return self.keep_hours == 0

    @property
    def keep_label(self) -> str:
        if self.live:
            return "live"
        if self.keep_hours % 24 == 0 and self.keep_hours >= 48:
            return f"{self.keep_hours // 24}d"
        return f"{self.keep_hours}h"


@dataclass
class ClientCfg:
    mail_notify: bool = True    # UI frame to TBMAIL when private mail arrives (PLANUNG 12, C1)


@dataclass
class BeaconCfg:
    """[beacon] a UI frame from the mailbox call every interval_min minutes; with
    mail_list the calls with new private mail are appended (CR48)."""
    enabled: bool = False
    interval_min: int = 30
    dest: str = "BEACON"
    path: list[str] = field(default_factory=list)   # digipeaters, e.g. WIDE1-1
    text: str = "TinyBox {call} - connect for mail and chat"
    mail_list: bool = True
    first_after_sec: int = 60     # the first one this long after the start


@dataclass
class ChatCfg:
    enabled: bool = False
    history_lines: int = 20     # max lines per history request (/H n, //HIST)
    max_line: int = 200         # max characters per chat line
    image_max: int = 8192       # max bytes of a chat image (CR12), 0 = no images at all
    boards: list[ChatBoard] = field(default_factory=list)

    def image_limit(self, board: ChatBoard) -> int:
        """Max image bytes in this board, 0 = images not allowed there."""
        return self.image_max if self.image_max > 0 and board.images else 0

    def board(self, name: str) -> ChatBoard | None:
        name = name.strip().upper()
        return next((b for b in self.boards if b.name == name), None)


def parse_size(sec: str, key: str, value: str) -> int:
    """'8k' -> 8192, '4096' -> 4096, '0' / 'no' / 'off' -> 0 (CR12 image_max)."""
    v = str(value).strip().lower()
    if v in ("0", "no", "off", "none", ""):
        return 0
    m = re.match(r"^(\d+)\s*(k|kb)?$", v)
    if not m:
        raise ConfigError(f"[{sec}] {key}: '{value}' must be a number of bytes, e.g. 8k or 8192")
    return int(m.group(1)) * (1024 if m.group(2) else 1)


def parse_keep(value: str) -> int:
    """'live' -> 0, '12h' -> 12, '7d' -> 168 (hours)."""
    value = value.strip().upper()
    if value == "LIVE":
        return 0
    m = KEEP_RE.match(value)
    if not m:
        raise ValueError(f"'{value}' must be live, <n>h or <n>d")
    hours = int(m.group(1)) * (24 if m.group(2) == "D" else 1)
    if not 1 <= hours <= MAX_KEEP_HOURS:
        raise ValueError(f"'{value}' must be between 1h and 365d")
    return hours


@dataclass
class Rubric:
    """[rubrics] (CR19): bulletin rubrics set by the sysop. Users, scripts and
    MQTT write bulletins only to ALL and the accepted ones; forwarding takes only
    those (unknown ones go to the sysop, see fwd/receive.py). No [rubrics] = free."""
    name: str
    description: str = ""
    accepted: bool = True        # "NAME = -" = refused
    expire_days: int | None = None   # "NAME = desc | 7": own validity in days (CR40),
                                     # None = [mailbox] bulletin_expire_days, 0 = forever


@dataclass
class Config:
    path: Path
    station: StationCfg
    direwolf: DirewolfCfg
    mailbox: MailboxCfg
    telnet: TelnetCfg
    web: WebCfg
    console: ConsoleCfg
    storage: StorageCfg
    logging: LoggingCfg
    mqtt: MqttCfg
    brocast: BrocastCfg = None  # type: ignore[assignment]  # set by load()
    inbox: InboxCfg = None  # type: ignore[assignment]  # set by load()
    chat: ChatCfg = field(default_factory=ChatCfg)
    rubrics: list[Rubric] = field(default_factory=list)
    forward: ForwardCfg = field(default_factory=ForwardCfg)
    client: ClientCfg = field(default_factory=ClientCfg)
    beacon: BeaconCfg = field(default_factory=BeaconCfg)
    radio: RadioCfg = field(default_factory=RadioCfg)
    kiss: KissCfg = field(default_factory=KissCfg)
    ax25: Ax25Cfg = field(default_factory=Ax25Cfg)
    # CR70: where the radio values came from, old keys still in the file, and the
    # LinkCfg fields set in tinybox.conf (they win over kisshub's values)
    sources: dict = field(default_factory=dict)
    hints: list = field(default_factory=list)
    kiss_fixed: frozenset = frozenset()


def _get(cp: configparser.ConfigParser, sec: str, key: str, default, kind=str):
    try:
        if kind is bool:
            return cp.getboolean(sec, key, fallback=default)
        if kind is int:
            return cp.getint(sec, key, fallback=default)
        if kind is float:
            return cp.getfloat(sec, key, fallback=default)
        return cp.get(sec, key, fallback=default)
    except ValueError as exc:
        raise ConfigError(f"[{sec}] {key}: {exc}") from None


def _steps(value: str) -> tuple[float, ...]:
    """quality_steps: five rising loss limits in % up to which 5 / 4 / 3 / 2 / 1
    bars are shown; above the last one a single red bar."""
    try:
        steps = tuple(float(x) for x in value.replace(";", ",").split(","))
    except ValueError:
        steps = ()
    if len(steps) != 5 or list(steps) != sorted(steps) or steps[0] <= 0:
        raise ConfigError("[agw] quality_steps: five rising numbers, e.g. 5, 10, 20, 35, 50")
    return steps


def _require_call(sec: str, key: str, value) -> str:
    if not value:
        raise ConfigError(f"[{sec}] {key} is missing")
    call = normalize_call(value)
    if not is_valid_call(call):
        raise ConfigError(f"[{sec}] {key}: '{value}' is not a valid callsign")
    return call


def _check_port(sec: str, key: str, port: int) -> None:
    if not 1 <= port <= 65535:
        raise ConfigError(f"[{sec}] {key}: {port} is not a valid TCP port")


def _check_range(sec: str, key: str, value: int, lo: int, hi: int) -> None:
    if not lo <= value <= hi:
        raise ConfigError(f"[{sec}] {key}: {value} must be between {lo} and {hi}")


def _debug_components(value: str) -> list[str]:
    """[logging] debug = agw,forward - these components go to DEBUG while the
    rest stays on level (CR32). DEBUG everywhere drowns the file in traffic."""
    from .logsetup import COMPONENTS
    names = [n.strip().lower() for n in value.replace(";", ",").split(",") if n.strip()]
    unknown = [n for n in names if n not in COMPONENTS and n != "all"]
    if unknown:
        raise ConfigError(f"[logging] debug: unknown component '{unknown[0]}' "
                          f"(known: {', '.join(COMPONENTS)}, all)")
    return names


def _check_log_dir(value: str, base: Path) -> Path:
    """The log directory must already exist and be writable."""
    log_dir = Path(value)
    if not log_dir.is_absolute():
        log_dir = base / log_dir
    if not log_dir.is_dir():
        raise ConfigError(f"[logging] log_dir: directory does not exist: {log_dir}")
    probe = log_dir / f".tinybox_write_test_{os.getpid()}"
    try:
        probe.write_text("x", encoding="ascii")
        probe.unlink()
    except OSError as exc:
        raise ConfigError(f"[logging] log_dir: not writable: {log_dir} ({exc})") from None
    return log_dir


class _Radio:
    """CR70: read one value from its new place, else from the old one (with a hint)."""

    def __init__(self, cp: configparser.ConfigParser) -> None:
        self.cp = cp
        self.hints: list[str] = []
        self.sources: dict[str, str] = {}

    def has(self, sec: str, key: str) -> bool:
        return self.cp.has_option(sec, key)

    def pick(self, places: list[tuple[str, str]], default, kind=str):
        """First place that is set wins; the later places are the old names."""
        for i, (sec, key) in enumerate(places):
            if self.cp.has_option(sec, key):
                if i:
                    new = f"[{places[0][0]}] {places[0][1]}"
                    self.hints.append(f"[{sec}] {key} is the old name - use {new}")
                return _get(self.cp, sec, key, default, kind)
        return default

    def old(self, sec: str, key: str, default, kind, now: str, value_now=None):
        """An old key that now has another owner: still read, as an override."""
        if not self.cp.has_option(sec, key):
            return default, False
        value = _get(self.cp, sec, key, default, kind)
        same = value_now is not None and value == value_now
        self.hints.append(f"[{sec}] {key} = {value}: "
                          + (f"same as {now} - can be removed" if same
                             else f"overrides {now} - remove it to use that"))
        return value, True


def _load_radio(cp: configparser.ConfigParser, base: Path) -> tuple:
    """[radio], [agw], [kiss], [ax25] (CR70). Old [direwolf] keys are still read."""
    from prcore import direwolfconf
    r = _Radio(cp)
    radio = RadioCfg(interface=_get(cp, "radio", "interface", "agw").strip().lower())
    if radio.interface not in ("agw", "kiss"):
        raise ConfigError(f"[radio] interface: '{radio.interface}' - use agw or kiss")

    # --- AGW: Direwolf; its values come from direwolf.conf ---------------------------
    dw = None
    dw_path = _get(cp, "agw", "direwolf_conf", "").strip()
    if dw_path:
        p = Path(dw_path.strip('"'))
        if not p.is_absolute() and not p.exists():
            p = base / p
        try:
            dw = direwolfconf.read(p)
        except direwolfconf.DirewolfConfError as exc:
            raise ConfigError(f"[agw] direwolf_conf: {exc}") from None
    agw_port_default = dw.agw_port if dw and dw.agw_port else 8000
    agw_port = r.pick([("agw", "port"), ("direwolf", "agw_port")], agw_port_default, int)
    r.sources["agw_port"] = ("tinybox.conf" if r.has("agw", "port") or r.has("direwolf", "agw_port")
                             else "direwolf.conf" if dw and dw.agw_port else "default")
    # paclen / window for AGW: direwolf.conf, then [ax25], old [direwolf] keys win
    paclen = dw.paclen if dw and dw.paclen else 256     # Direwolf's own default
    window = (dw.emaxframe or dw.maxframe) if dw else None
    window = min(7, window) if window else 4
    r.sources["agw_paclen"] = "direwolf.conf" if dw and dw.paclen else "default"
    r.sources["agw_window"] = ("direwolf.conf" if dw and (dw.emaxframe or dw.maxframe)
                               else "default")
    if radio.interface == "agw":
        if r.has("ax25", "paclen"):
            paclen, r.sources["agw_paclen"] = _get(cp, "ax25", "paclen", paclen, int), "[ax25]"
        if r.has("ax25", "maxframe"):
            window, r.sources["agw_window"] = _get(cp, "ax25", "maxframe", window, int), "[ax25]"
    src_now = "direwolf.conf" if dw else "the default"
    v, ok = r.old("direwolf", "paclen", paclen, int, f"PACLEN from {src_now}", paclen)
    if ok:
        paclen, r.sources["agw_paclen"] = v, "[direwolf] paclen"
    v, ok = r.old("direwolf", "max_outstanding", window, int,
                  f"EMAXFRAME/MAXFRAME from {src_now}", window)
    if ok:
        window, r.sources["agw_window"] = v, "[direwolf] max_outstanding"

    def q(key: str, default, kind=int):
        return r.pick([("agw", key), ("direwolf", key)], default, kind)

    direwolf = DirewolfCfg(
        agw_host=r.pick([("agw", "host"), ("direwolf", "agw_host")], "127.0.0.1"),
        agw_port=agw_port,
        agw_radio_port=r.pick([("agw", "channel"), ("direwolf", "agw_radio_port")], 0, int),
        reconnect_sec=q("reconnect_sec", 5),
        paclen=paclen, max_outstanding=window,
        quality_poll_sec=q("quality_poll_sec", 30),
        quality_window_frames=q("quality_window_frames", 50),
        quality_window_min=q("quality_window_min", 30),
        quality_min_frames=q("quality_min_frames", 20),
        quality_steps=_steps(q("quality_steps", "5, 10, 20, 35, 50", str)),
        direwolf_conf=str(dw.path) if dw else "",
    )
    _check_port("agw", "port", direwolf.agw_port)
    _check_range("agw", "paclen (PACLEN / [ax25] paclen)", direwolf.paclen, 32, 256)
    _check_range("agw", "window (EMAXFRAME / [ax25] maxframe)", direwolf.max_outstanding, 1, 7)
    _check_range("agw", "channel", direwolf.agw_radio_port, 0, 255)
    _check_range("agw", "reconnect_sec", direwolf.reconnect_sec, 1, 3600)
    _check_range("agw", "quality_poll_sec", direwolf.quality_poll_sec, 0, 3600)
    _check_range("agw", "quality_window_frames", direwolf.quality_window_frames, 5, 1000)
    _check_range("agw", "quality_window_min", direwolf.quality_window_min, 1, 1440)
    _check_range("agw", "quality_min_frames", direwolf.quality_min_frames, 1,
                 direwolf.quality_window_frames)

    # --- KISS: kisshub; its values come from kisshub's status ------------------------
    port = _get(cp, "kiss", "port", 8101, int)
    _check_port("kiss", "port", port)
    fixed: set[str] = set()
    host, _ = r.old("kiss", "host", "127.0.0.1", str, "the fixed 127.0.0.1", "127.0.0.1")
    status_port, _ = r.old("kiss", "status_port", port + 1, int, "port + 1", port + 1)
    channel, _ = r.old("kiss", "channel", 0, int, "the fixed 0", 0)
    air_baud, ok = r.old("kiss", "air_baud", 1200, int, "the kisshub value")
    if ok:
        fixed.add("air_baud")
    txdelay_ms, ok = r.old("kiss", "txdelay_ms", 300, int, "the kisshub value")
    if ok:
        fixed.add("txdelay_sec")
    kiss = KissCfg(host=host.strip(), port=port, channel=channel,
                   reconnect_sec=_get(cp, "kiss", "reconnect_sec", 5, int),
                   air_baud=air_baud, txdelay_ms=txdelay_ms, status_port=status_port)
    _check_range("kiss", "channel", kiss.channel, 0, 15)
    _check_range("kiss", "reconnect_sec", kiss.reconnect_sec, 1, 3600)
    _check_range("kiss", "air_baud", kiss.air_baud, 300, 1_000_000)
    # kisshub does, with its own limit. VARA needs ~2700 ms (measured 18.10.2026)
    _check_range("kiss", "txdelay_ms", kiss.txdelay_ms, 0, 10000)
    _check_range("kiss", "status_port", kiss.status_port, 0, 65535)

    # [ax25]: only overrides. Without it the 1200 Bd values until kisshub tells its own.
    for key in ("paclen", "maxframe", "maxframe_ext", "n2", "t1_min_sec", "t1_max_sec",
                "t2_sec", "t3_sec"):
        if r.has("ax25", key):
            fixed.add(key)
    ax25 = Ax25Cfg(
        version=_get(cp, "ax25", "version", "2.2").strip(),
        paclen=_get(cp, "ax25", "paclen", 256, int),
        maxframe=_get(cp, "ax25", "maxframe", 4, int),
        maxframe_ext=_get(cp, "ax25", "maxframe_ext", 7, int),
        srej=_get(cp, "ax25", "srej", True, bool),
        n2=_get(cp, "ax25", "n2", 10, int),
        t1_min_sec=_get(cp, "ax25", "t1_min_sec", 3.0, float),
        t1_max_sec=_get(cp, "ax25", "t1_max_sec", 30.0, float),
        t2_sec=_get(cp, "ax25", "t2_sec", 1.5, float),
        t3_sec=_get(cp, "ax25", "t3_sec", 300.0, float),
        srt_init_sec=_get(cp, "ax25", "srt_init_sec", 2.5, float),
    )
    if ax25.version not in ("2.0", "2.2"):
        raise ConfigError(f"[ax25] version: '{ax25.version}' - use 2.0 or 2.2")
    _check_range("ax25", "paclen", ax25.paclen, 16, 256)
    _check_range("ax25", "maxframe", ax25.maxframe, 1, 7)
    _check_range("ax25", "maxframe_ext", ax25.maxframe_ext, 1, 127)
    _check_range("ax25", "n2", ax25.n2, 1, 50)
    for key in ("t1_min_sec", "t1_max_sec", "t2_sec", "t3_sec", "srt_init_sec"):
        if not 0 <= getattr(ax25, key) <= 3600:
            raise ConfigError(f"[ax25] {key}: must be between 0 and 3600 seconds")
    if not 0 < ax25.t1_min_sec <= ax25.t1_max_sec:
        raise ConfigError("[ax25] t1_min_sec must be above 0 and not above t1_max_sec")
    if radio.interface == "kiss":
        r.sources["kiss"] = ("kisshub status" + (f", tinybox.conf: {', '.join(sorted(fixed))}"
                                                 if fixed else "")
                             if kiss.status_port > 0 else "tinybox.conf (status_port 0)")
    if dw:
        r.sources["direwolf.conf"] = dw.describe(direwolf.agw_radio_port)
    return direwolf, radio, kiss, ax25, r, frozenset(fixed)


def load(path: str | Path) -> Config:
    path = Path(path).resolve()
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")

    cp = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
    try:
        cp.read(path, encoding="utf-8")
    except configparser.Error as exc:
        raise ConfigError(str(exc)) from None

    station = StationCfg(
        mailbox_call=_require_call("station", "mailbox_call",
                                   _get(cp, "station", "mailbox_call", None)),
        sysop_call=_require_call("station", "sysop_call",
                                 _get(cp, "station", "sysop_call", None)),
        sysop_via_radio=_get(cp, "station", "sysop_via_radio", False, bool),
        qth=_get(cp, "station", "qth", "").strip(),
        freq=_get(cp, "station", "freq", "").strip(),
        locator=_get(cp, "station", "locator", "").strip().upper(),
    )
    if station.freq:
        try:
            float(station.freq)
        except ValueError:
            raise ConfigError("[station] freq: MHz, e.g. 144.800") from None
    haddress = _get(cp, "station", "haddress", "").strip()
    if haddress:
        from .addressing import AddressError, addr_call, normalize
        try:
            haddress = normalize(haddress)
        except AddressError:
            raise ConfigError(f"[station] haddress: '{haddress}' is not a valid "
                              "hierarchical address (e.g. OE3XTC.#NOE.AUT.EU)") from None
        if addr_call(haddress) != station.bbs_call:
            raise ConfigError(f"[station] haddress must start with {station.bbs_call} "
                              "(the mailbox call without SSID)")
        station.haddress = haddress

    direwolf, radio, kiss, ax25, rad, kiss_fixed = _load_radio(cp, path.parent)

    mailbox = MailboxCfg(
        welcome_enabled=_get(cp, "mailbox", "welcome_enabled", True, bool),
        welcome_text=_get(cp, "mailbox", "welcome_text", ""),
        third_party=_get(cp, "mailbox", "third_party", True, bool),
        max_users=_get(cp, "mailbox", "max_users", 3, int),
        max_msg_bytes=_get(cp, "mailbox", "max_msg_bytes", 8192, int),
        idle_timeout_min=_get(cp, "mailbox", "idle_timeout_min", 10, int),
        bulletin_expire_days=_get(cp, "mailbox", "bulletin_expire_days", 30, int),
    )
    _check_range("mailbox", "max_users", mailbox.max_users, 1, 50)
    _check_range("mailbox", "max_msg_bytes", mailbox.max_msg_bytes, 256, 65536)
    _check_range("mailbox", "idle_timeout_min", mailbox.idle_timeout_min, 1, 240)
    _check_range("mailbox", "bulletin_expire_days", mailbox.bulletin_expire_days, 0, 3650)

    telnet = TelnetCfg(
        enabled=_get(cp, "telnet", "enabled", True, bool),
        host=_get(cp, "telnet", "host", "127.0.0.1"),
        port=_get(cp, "telnet", "port", 6300, int),
    )
    _check_port("telnet", "port", telnet.port)
    if telnet.host not in LOOPBACK_HOSTS:
        raise ConfigError("[telnet] host must be a loopback address (127.0.0.1)")

    web = WebCfg(
        enabled=_get(cp, "web", "enabled", True, bool),
        host=_get(cp, "web", "host", "127.0.0.1"),
        port=_get(cp, "web", "port", 8080, int),
    )
    _check_port("web", "port", web.port)
    if web.host not in LOOPBACK_HOSTS:
        raise ConfigError("[web] host must be a loopback address (127.0.0.1)")
    if web.enabled and telnet.enabled and web.port == telnet.port:
        raise ConfigError("[web] port and [telnet] port must differ")

    console = ConsoleCfg(
        enabled=_get(cp, "console", "enabled", True, bool),
        monitor=_get(cp, "console", "monitor", True, bool),
    )

    data_dir = Path(_get(cp, "storage", "data_dir", "data"))
    if not data_dir.is_absolute():
        data_dir = path.parent / data_dir
    storage = StorageCfg(data_dir=data_dir)

    level = _get(cp, "logging", "level", "INFO").upper()
    if level not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
        raise ConfigError(f"[logging] level: unknown level '{level}'")
    log_dir = _get(cp, "logging", "log_dir", "").strip()
    keep_days = _get(cp, "logging", "keep_days", 14, int)
    _check_range("logging", "keep_days", keep_days, 0, 3650)
    logging_cfg = LoggingCfg(level=level,
                             monitor=_get(cp, "logging", "monitor", True, bool),
                             log_dir=_check_log_dir(log_dir, path.parent) if log_dir else None,
                             debug=_debug_components(_get(cp, "logging", "debug", "")),
                             keep_days=keep_days)

    mqtt = MqttCfg(
        enabled=_get(cp, "mqtt", "enabled", False, bool),
        host=_get(cp, "mqtt", "host", "127.0.0.1"),
        port=_get(cp, "mqtt", "port", 8883, int),
        tls=_get(cp, "mqtt", "tls", True, bool),
        client_id=_get(cp, "mqtt", "client_id", "tinybox"),
        username=_get(cp, "mqtt", "username", ""),
        password_file=_get(cp, "mqtt", "password_file", ""),
        topic_root=_get(cp, "mqtt", "topic_root", f"tinybox/{station.mailbox_call}"),
    )
    _check_port("mqtt", "port", mqtt.port)

    brocast = BrocastCfg()
    dict_file = _get(cp, "brocast", "dict_file", "").strip()
    if dict_file:
        p = Path(dict_file)
        brocast.dict_file = p if p.is_absolute() else path.parent / p
    brocast.publish = _get(cp, "brocast", "publish", False, bool)
    url = _get(cp, "brocast", "ingest_url", "http://127.0.0.1:8090/api/v1").strip()
    parsed = urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname not in LOOPBACK_HOSTS:
        raise ConfigError("[brocast] ingest_url must be http://127.0.0.1:<port>/... "
                          "(brocastd runs on the same PC)")
    brocast.ingest_host = parsed.hostname
    brocast.ingest_port = parsed.port or 80
    brocast.ingest_path = parsed.path.rstrip("/") or "/api/v1"
    brocast.token = _get(cp, "brocast", "token", "").strip()
    brocast.max_bytes = _get(cp, "brocast", "max_bytes", 4096, int)
    _check_range("brocast", "max_bytes", brocast.max_bytes, 256, 65536)
    brocast.sync_min = _get(cp, "brocast", "sync_min", 60, int)
    _check_range("brocast", "sync_min", brocast.sync_min, 1, 1440)
    alerts = _get(cp, "brocast", "alert_destinations", "WARN").replace(",", " ").split()
    brocast.alert_destinations = [normalize_call(d) for d in alerts]
    dests = _get(cp, "brocast", "destinations", "").replace(",", " ").split()
    brocast.destinations = [normalize_call(d) for d in dests]
    for item in _get(cp, "brocast", "rubrics", "").replace(",", " ").split():
        if ":" not in item:
            raise ConfigError(f"[brocast] rubrics: '{item}' must look like DEST:rubric")
        dest, rubric = item.split(":", 1)
        brocast.rubrics[normalize_call(dest)] = rubric.strip()

    inbox_dir = Path(_get(cp, "inbox", "dir", "eingang").strip() or "eingang")
    inbox = InboxCfg(enabled=_get(cp, "inbox", "enabled", False, bool),
                     directory=inbox_dir if inbox_dir.is_absolute() else path.parent / inbox_dir,
                     poll_sec=_get(cp, "inbox", "poll_sec", 10, int))
    _check_range("inbox", "poll_sec", inbox.poll_sec, 1, 3600)

    forward = ForwardCfg(enabled=_get(cp, "forward", "enabled", False, bool),
                         bid_days=_get(cp, "forward", "bid_days", 60, int))
    _check_range("forward", "bid_days", forward.bid_days, 1, 3650)
    for item in _get(cp, "forward", "aliases", "").replace(",", " ").split():
        if ":" not in item:
            raise ConfigError(f"[forward] aliases: '{item}' must look like ALIAS:AREA")
        alias, area = item.split(":", 1)
        forward.aliases[alias.strip().upper()] = area.strip().upper()
    forward.publish_to_brocast = _get(cp, "forward", "publish_to_brocast", False, bool)
    forward.listen_host = _get(cp, "forward", "listen_host", "127.0.0.1").strip()
    forward.listen_port = _get(cp, "forward", "listen_port", 0, int)
    if forward.listen_port:
        _check_port("forward", "listen_port", forward.listen_port)
        if telnet.enabled and forward.listen_port == telnet.port:
            raise ConfigError("[forward] listen_port and [telnet] port must differ")
    for sec in cp.sections():
        if sec.lower().startswith("partner."):
            p = _load_partner(cp, sec)
            forward.partners[p.call] = p
    if forward.enabled and not station.haddress:
        raise ConfigError("[forward] enabled = yes needs [station] haddress "
                          "(e.g. OE3XTC.#NOE.AUT.EU)")
    if (forward.listen_port and forward.listen_host not in LOOPBACK_HOSTS
            and any(p.transport == "tcp" and not p.password
                    for p in forward.partners.values())):
        raise ConfigError("[forward] listen_host is reachable from outside: every TCP "
                          "partner needs a password")

    return Config(path=path, station=station, direwolf=direwolf, mailbox=mailbox,
                  telnet=telnet, web=web, console=console, storage=storage, logging=logging_cfg,
                  mqtt=mqtt, brocast=brocast, inbox=inbox, chat=_load_chat(cp), rubrics=_load_rubrics(cp),
                  forward=forward, radio=radio, kiss=kiss, ax25=ax25,
                  sources=rad.sources, hints=rad.hints, kiss_fixed=kiss_fixed,
                  client=ClientCfg(mail_notify=_get(cp, "client", "mail_notify", True, bool)),
                  beacon=_load_beacon(cp))


def _load_beacon(cp: configparser.ConfigParser) -> BeaconCfg:
    """[beacon] (CR48)."""
    b = BeaconCfg(enabled=_get(cp, "beacon", "enabled", False, bool),
                  interval_min=_get(cp, "beacon", "interval_min", 30, int),
                  dest=normalize_call(_get(cp, "beacon", "dest", "BEACON") or "BEACON"),
                  path=[normalize_call(c) for c in
                        _get(cp, "beacon", "path", "").replace(",", " ").split()],
                  text=_get(cp, "beacon", "text", BeaconCfg.text).strip(),
                  mail_list=_get(cp, "beacon", "mail_list", True, bool),
                  first_after_sec=_get(cp, "beacon", "first_after_sec", 60, int))
    _check_range("beacon", "interval_min", b.interval_min, 5, 1440)
    _check_range("beacon", "first_after_sec", b.first_after_sec, 0, 3600)
    if len(b.path) > 2:
        raise ConfigError("[beacon] path: at most 2 digipeaters")
    for c in [b.dest, *b.path]:             # AX.25 addresses: BEACON, WIDE1-1 are fine
        if not re.match(r"^[A-Z0-9]{1,6}(-([0-9]|1[0-5]))?$", c):
            raise ConfigError(f"[beacon] invalid call {c!r}")
    if not b.text and not b.mail_list:
        raise ConfigError("[beacon] text is empty and mail_list = no: nothing to send")
    return b


def _load_partner(cp: configparser.ConfigParser, sec: str) -> PartnerCfg:
    """[partner.OE3GAS]  transport = agw | tcp, see tinybox.conf.example"""
    from .addressing import AddressError, normalize
    call = normalize_call(sec.split(".", 1)[1])
    if not is_valid_call(call) or "-" in call:
        raise ConfigError(f"[{sec}]: '{call}' must be a callsign without SSID")

    def words(key: str) -> list[str]:
        return [w.upper() for w in _get(cp, sec, key, "").replace(",", " ").split()]

    p = PartnerCfg(call=call,
                   transport=_get(cp, sec, "transport", "agw").strip().lower(),
                   ax25_call=normalize_call(_get(cp, sec, "ax25_call", "")),
                   via=words("via"),
                   host=_get(cp, sec, "host", "").strip(),
                   port=_get(cp, sec, "port", 0, int),
                   login=[x.strip() for x in _get(cp, sec, "login", "").split("|") if x.strip()],
                   password=_get(cp, sec, "password", "").strip(),
                   routes=words("routes"), areas=words("areas"),
                   protocol=_get(cp, sec, "protocol", "fbb").strip().lower(),
                   timeout=_get(cp, sec, "timeout", 120, int))
    transport_default_auto = p.transport == "tcp"     # no unattended calls over the air by default
    p.auto = _get(cp, sec, "auto", transport_default_auto, bool)
    p.interval_min = _get(cp, sec, "interval_min", 0, int)
    p.retry_min = _get(cp, sec, "retry_min", 10, int)
    _check_range(sec, "interval_min", p.interval_min, 0, 10080)
    _check_range(sec, "retry_min", p.retry_min, 1, 1440)
    window = _get(cp, sec, "window", "").strip()
    if window:
        m = re.match(r"^(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})$", window)
        if not m or int(m.group(1)) > 23 or int(m.group(3)) > 24 \
                or int(m.group(2)) > 59 or int(m.group(4)) > 59:
            raise ConfigError(f"[{sec}] window must look like 22:00-06:00")
        p.window = (int(m.group(1)) * 60 + int(m.group(2)), int(m.group(3)) * 60 + int(m.group(4)))
    if p.transport not in ("agw", "tcp"):
        raise ConfigError(f"[{sec}] transport must be agw or tcp")
    if p.protocol not in ("b1", "fbb", "ascii"):
        raise ConfigError(f"[{sec}] protocol must be b1, fbb or ascii")
    if p.ax25_call and not is_valid_call(p.ax25_call):
        raise ConfigError(f"[{sec}] ax25_call: '{p.ax25_call}' is not a valid callsign")
    for v in p.via:
        if not is_valid_call(v):
            raise ConfigError(f"[{sec}] via: '{v}' is not a valid callsign")
    if p.transport == "tcp":
        if not p.host:
            raise ConfigError(f"[{sec}] transport = tcp needs host")
        _check_port(sec, "port", p.port)
    _check_range(sec, "timeout", p.timeout, 10, 3600)
    try:
        p.haddress = normalize(_get(cp, sec, "haddress", "").strip()) or call
    except AddressError as exc:
        raise ConfigError(f"[{sec}] haddress: '{exc}' is not a valid address") from None
    return p


def _load_rubrics(cp: configparser.ConfigParser) -> list[Rubric]:
    """[rubrics]  NAME = description  (accepted)   NAME = - [note]  (refused).
    Optional "| days" at the end: own validity of the rubric's bulletins (CR40).
    Lenient: a wrong line is only logged, TinyBox still starts."""
    rubrics: list[Rubric] = []
    if not cp.has_section("rubrics"):
        return rubrics
    for key, value in cp.items("rubrics", raw=True):
        if key in cp.defaults():
            continue
        name = key.strip().upper()
        if not DEST_RE.match(name):
            logging.getLogger(__name__).warning(
                "[rubrics] %s: a rubric name has 1-6 letters/digits - ignored", key)
            continue
        value = value.strip()
        days: int | None = None
        if "|" in value:                         # "NAME = description | 7" (CR40)
            value, _, tail = value.rpartition("|")
            value, tail = value.strip(), tail.strip().lower().removesuffix("d").strip()
            if tail.isdigit() and int(tail) <= 3650:
                days = int(tail)
            else:
                logging.getLogger(__name__).warning(
                    "[rubrics] %s: '| %s' is no number of days (0-3650) - ignored", key, tail)
        refused = value == "-" or value.startswith("- ") or value.startswith("-\t")
        desc = value[1:].strip() if refused else value
        if any(r.name == name for r in rubrics):
            continue
        rubrics.append(Rubric(name, desc, not refused, days))
    return rubrics


def _load_chat(cp: configparser.ConfigParser) -> ChatCfg:
    """[chat] general settings, [chat_boards] the fixed boards (set by the sysop).

    [chat_boards]
    TREFF = 7d    Meeting point     (history: last 7 days)
    RUNDE = live  Live only         (nothing is stored)
    """
    chat = ChatCfg(enabled=_get(cp, "chat", "enabled", False, bool),
                   history_lines=_get(cp, "chat", "history_lines", 20, int),
                   max_line=_get(cp, "chat", "max_line", 200, int),
                   image_max=parse_size("chat", "image_max", _get(cp, "chat", "image_max", "8k")))
    _check_range("chat", "history_lines", chat.history_lines, 0, 200)
    _check_range("chat", "max_line", chat.max_line, 40, 1000)
    if chat.image_max:
        _check_range("chat", "image_max", chat.image_max, 1024, 16320)
    if cp.has_section("chat_boards"):
        for key, value in cp.items("chat_boards", raw=True):
            if key in cp.defaults():
                continue
            name = key.strip().upper()
            if not BOARD_RE.match(name):
                raise ConfigError(f"[chat_boards] {key}: board name must be 1-8 letters/digits")
            parts = value.split(None, 1)
            if not parts:
                raise ConfigError(f"[chat_boards] {name}: missing live, <n>h or <n>d")
            try:
                keep = parse_keep(parts[0])
            except ValueError as exc:
                raise ConfigError(f"[chat_boards] {name}: {exc}") from None
            desc = parts[1].strip() if len(parts) > 1 else ""
            noimg = False                      # CR12: "noimg" right after the keep time
            if desc.split(None, 1)[:1] and desc.split(None, 1)[0].lower() == "noimg":
                noimg = True
                desc = desc[5:].strip()
            chat.boards.append(ChatBoard(name, keep, desc, noimg=noimg))
    if chat.enabled and not chat.boards:
        raise ConfigError("[chat] enabled = yes, but [chat_boards] defines no boards")
    if cp.has_section("chat_motd"):            # CR3: message of the day per board
        for key, value in cp.items("chat_motd", raw=True):
            if key in cp.defaults():
                continue
            board = chat.board(key)
            text = " ".join(value.split())
            if board is None:
                logging.getLogger(__name__).warning(
                    "[chat_motd] %s: no such board in [chat_boards] - ignored", key)
            elif len(text) > MOTD_MAX:
                raise ConfigError(f"[chat_motd] {board.name}: at most {MOTD_MAX} characters")
            else:
                board.motd = text
    return chat
