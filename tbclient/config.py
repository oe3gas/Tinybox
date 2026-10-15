"""tbclient.conf (INI). Missing values take the defaults below."""

from __future__ import annotations

import configparser
import re
from dataclasses import dataclass
from pathlib import Path

CALL_RE = re.compile(r"^[A-Z0-9]{1,6}(-([0-9]|1[0-5]))?$")


class ConfigError(Exception):
    pass


@dataclass
class Config:
    mycall: str = ""
    tinybox_call: str = "OE3GAS-1"
    link: str = "agw"                 # agw = radio via Direwolf, telnet = TinyBox test port
    ui: str = "auto"                  # auto | yes | no  (chat events as UI frames)
    auto_connect: bool = False
    telnet_host: str = "127.0.0.1"
    telnet_port: int = 6300
    agw_host: str = "127.0.0.1"
    agw_port: int = 8000
    radio_port: int = 0
    web_host: str = "0.0.0.0"
    web_port: int = 7744
    data_dir: Path = Path("data/tbclient")
    sync_chunk: int = 1024            # bytes per request of a mailbox sync (radio)
    sync_pause: float = 5.0           # seconds between two requests (radio)
    sync_short: int = 256             # personal mail up to this size comes with its text (CR40)
    sync_on_login: bool = True        # sync the headers after every login (CR40)
    img_rate: int = 100               # net bytes/s of the link, for the time estimate
    img_target: int = 4096            # the picture is shrunk to about this many bytes ("normal")


def _strip(value: str) -> str:
    return value.split("#", 1)[0].split(";", 1)[0].strip()


def load(path: str | Path) -> Config:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"{path} not found - copy tbclient.conf.example to {path.name}")
    cp = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
    cp.read(path, encoding="utf-8")

    def get(section: str, key: str, default: str) -> str:
        return _strip(cp.get(section, key, fallback=default)) or default

    cfg = Config()
    cfg.mycall = get("station", "mycall", "").upper()
    cfg.tinybox_call = get("tinybox", "call", cfg.tinybox_call).upper()
    cfg.link = get("tinybox", "link", cfg.link).lower()
    cfg.ui = get("tinybox", "ui", cfg.ui).lower()
    cfg.auto_connect = get("tinybox", "auto_connect", "no").lower() in ("yes", "true", "1", "on")
    cfg.telnet_host = get("tinybox", "telnet_host", cfg.telnet_host)
    cfg.telnet_port = int(get("tinybox", "telnet_port", str(cfg.telnet_port)))
    cfg.agw_host = get("direwolf", "agw_host", cfg.agw_host)
    cfg.agw_port = int(get("direwolf", "agw_port", str(cfg.agw_port)))
    cfg.radio_port = int(get("direwolf", "radio_port", str(cfg.radio_port)))
    cfg.web_host = get("web", "host", cfg.web_host)
    cfg.web_port = int(get("web", "port", str(cfg.web_port)))
    data_dir = Path(get("storage", "data_dir", str(cfg.data_dir)))
    cfg.data_dir = data_dir if data_dir.is_absolute() else path.parent / data_dir

    cfg.sync_chunk = int(get("sync", "chunk_bytes", str(cfg.sync_chunk)))
    cfg.sync_pause = float(get("sync", "pause_sec", str(cfg.sync_pause)))
    if not 128 <= cfg.sync_chunk <= 8192:
        raise ConfigError("[sync] chunk_bytes must be 128 ... 8192")
    if not 0 <= cfg.sync_pause <= 120:
        raise ConfigError("[sync] pause_sec must be 0 ... 120")
    cfg.sync_short = int(get("sync", "short_bytes", str(cfg.sync_short)))
    if not 0 <= cfg.sync_short <= 8192:
        raise ConfigError("[sync] short_bytes must be 0 ... 8192")
    cfg.sync_on_login = get("sync", "on_login", "yes").lower() in ("yes", "true", "1", "on")
    # piece_bytes / pause_sec of older versions are ignored: the picture goes to
    # Direwolf in one go, the AX.25 window (MAXFRAME/EMAXFRAME) paces it
    cfg.img_rate = int(get("images", "bytes_per_sec", str(cfg.img_rate)))
    cfg.img_target = int(get("images", "target_bytes", str(cfg.img_target)))
    if not 10 <= cfg.img_rate <= 100000:
        raise ConfigError("[images] bytes_per_sec must be 10 ... 100000")
    if not 1024 <= cfg.img_target <= 16320:
        raise ConfigError("[images] target_bytes must be 1024 ... 16320")

    for name, call in (("[station] mycall", cfg.mycall), ("[tinybox] call", cfg.tinybox_call)):
        if not CALL_RE.match(call):
            raise ConfigError(f"{name}: invalid call {call!r}")
    if cfg.link not in ("agw", "telnet"):
        raise ConfigError("[tinybox] link must be agw or telnet")
    if cfg.ui not in ("auto", "yes", "no"):
        raise ConfigError("[tinybox] ui must be auto, yes or no")
    return cfg
