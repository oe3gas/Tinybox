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

    for name, call in (("[station] mycall", cfg.mycall), ("[tinybox] call", cfg.tinybox_call)):
        if not CALL_RE.match(call):
            raise ConfigError(f"{name}: invalid call {call!r}")
    if cfg.link not in ("agw", "telnet"):
        raise ConfigError("[tinybox] link must be agw or telnet")
    if cfg.ui not in ("auto", "yes", "no"):
        raise ConfigError("[tinybox] ui must be auto, yes or no")
    return cfg
