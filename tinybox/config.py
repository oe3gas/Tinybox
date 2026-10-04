"""Load and validate tinybox.conf (INI format)."""

from __future__ import annotations

import configparser
import os
import re
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


@dataclass
class DirewolfCfg:
    agw_host: str
    agw_port: int
    agw_radio_port: int
    reconnect_sec: int
    paclen: int
    max_outstanding: int


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
class ChatCfg:
    enabled: bool = False
    history_lines: int = 20     # max lines replayed when joining a board
    max_line: int = 200         # max characters per chat line
    boards: list[ChatBoard] = field(default_factory=list)

    def board(self, name: str) -> ChatBoard | None:
        name = name.strip().upper()
        return next((b for b in self.boards if b.name == name), None)


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


def _get(cp: configparser.ConfigParser, sec: str, key: str, default, kind=str):
    try:
        if kind is bool:
            return cp.getboolean(sec, key, fallback=default)
        if kind is int:
            return cp.getint(sec, key, fallback=default)
        return cp.get(sec, key, fallback=default)
    except ValueError as exc:
        raise ConfigError(f"[{sec}] {key}: {exc}") from None


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
    )

    direwolf = DirewolfCfg(
        agw_host=_get(cp, "direwolf", "agw_host", "127.0.0.1"),
        agw_port=_get(cp, "direwolf", "agw_port", 8000, int),
        agw_radio_port=_get(cp, "direwolf", "agw_radio_port", 0, int),
        reconnect_sec=_get(cp, "direwolf", "reconnect_sec", 5, int),
        paclen=_get(cp, "direwolf", "paclen", 128, int),
        max_outstanding=_get(cp, "direwolf", "max_outstanding", 4, int),
    )
    _check_port("direwolf", "agw_port", direwolf.agw_port)
    _check_range("direwolf", "paclen", direwolf.paclen, 32, 256)
    _check_range("direwolf", "max_outstanding", direwolf.max_outstanding, 1, 7)
    _check_range("direwolf", "agw_radio_port", direwolf.agw_radio_port, 0, 255)
    _check_range("direwolf", "reconnect_sec", direwolf.reconnect_sec, 1, 3600)

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
    logging_cfg = LoggingCfg(level=level,
                             monitor=_get(cp, "logging", "monitor", True, bool),
                             log_dir=_check_log_dir(log_dir, path.parent) if log_dir else None)

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

    return Config(path=path, station=station, direwolf=direwolf, mailbox=mailbox,
                  telnet=telnet, web=web, console=console, storage=storage, logging=logging_cfg,
                  mqtt=mqtt, brocast=brocast, inbox=inbox, chat=_load_chat(cp))


def _load_chat(cp: configparser.ConfigParser) -> ChatCfg:
    """[chat] general settings, [chat_boards] the fixed boards (set by the sysop).

    [chat_boards]
    TREFF = 7d    Meeting point     (history: last 7 days)
    RUNDE = live  Live only         (nothing is stored)
    """
    chat = ChatCfg(enabled=_get(cp, "chat", "enabled", False, bool),
                   history_lines=_get(cp, "chat", "history_lines", 20, int),
                   max_line=_get(cp, "chat", "max_line", 200, int))
    _check_range("chat", "history_lines", chat.history_lines, 0, 200)
    _check_range("chat", "max_line", chat.max_line, 40, 1000)
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
            chat.boards.append(ChatBoard(name, keep, parts[1].strip() if len(parts) > 1 else ""))
    if chat.enabled and not chat.boards:
        raise ConfigError("[chat] enabled = yes, but [chat_boards] defines no boards")
    return chat
