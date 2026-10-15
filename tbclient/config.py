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
    locator: str = ""                 # Maidenhead locator, ADIF MY_GRIDSQUARE (CR44)
    tinybox_call: str = "OE3GAS-1"
    link: str = "agw"                 # agw = Direwolf, kiss = kisshub (CR46), telnet = test port
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
    # CR46: link = kiss - kisshub and the client's own AX.25 layer 2
    kiss_host: str = "127.0.0.1"
    kiss_port: int = 8101
    kiss_channel: int = 0
    kiss_status_port: int = 8102      # kisshub's status (which TNC), 0 = off
    kiss_air_baud: int = 1200
    kiss_txdelay_ms: int = 300
    ax25_version: str = "2.2"
    ax25_paclen: int = 128
    ax25_maxframe: int = 4
    ax25_maxframe_ext: int = 7
    ax25_srej: bool = True
    ax25_n2: int = 10
    ax25_t1_min: float = 3.0
    ax25_t1_max: float = 30.0
    ax25_t2: float = 1.5
    ax25_t3: float = 300.0


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
    cfg.locator = get("station", "locator", "").upper()
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

    cfg.kiss_host = get("kiss", "host", cfg.kiss_host)
    cfg.kiss_port = int(get("kiss", "port", str(cfg.kiss_port)))
    cfg.kiss_channel = int(get("kiss", "channel", str(cfg.kiss_channel)))
    cfg.kiss_status_port = int(get("kiss", "status_port", str(cfg.kiss_status_port)))
    cfg.kiss_air_baud = int(get("kiss", "air_baud", str(cfg.kiss_air_baud)))
    cfg.kiss_txdelay_ms = int(get("kiss", "txdelay_ms", str(cfg.kiss_txdelay_ms)))
    cfg.ax25_version = get("ax25", "version", cfg.ax25_version)
    cfg.ax25_paclen = int(get("ax25", "paclen", str(cfg.ax25_paclen)))
    cfg.ax25_maxframe = int(get("ax25", "maxframe", str(cfg.ax25_maxframe)))
    cfg.ax25_maxframe_ext = int(get("ax25", "maxframe_ext", str(cfg.ax25_maxframe_ext)))
    cfg.ax25_srej = get("ax25", "srej", "yes").lower() in ("yes", "true", "1", "on")
    cfg.ax25_n2 = int(get("ax25", "n2", str(cfg.ax25_n2)))
    cfg.ax25_t1_min = float(get("ax25", "t1_min_sec", str(cfg.ax25_t1_min)))
    cfg.ax25_t1_max = float(get("ax25", "t1_max_sec", str(cfg.ax25_t1_max)))
    cfg.ax25_t2 = float(get("ax25", "t2_sec", str(cfg.ax25_t2)))
    cfg.ax25_t3 = float(get("ax25", "t3_sec", str(cfg.ax25_t3)))
    if cfg.ax25_version not in ("2.0", "2.2"):
        raise ConfigError("[ax25] version must be 2.0 or 2.2")
    if not 16 <= cfg.ax25_paclen <= 256:
        raise ConfigError("[ax25] paclen must be 16 ... 256")
    if not 1 <= cfg.ax25_maxframe <= 7 or not 1 <= cfg.ax25_maxframe_ext <= 127:
        raise ConfigError("[ax25] maxframe must be 1 ... 7, maxframe_ext 1 ... 127")
    if not 300 <= cfg.kiss_air_baud <= 115200:
        raise ConfigError("[kiss] air_baud must be 300 ... 115200")

    for name, call in (("[station] mycall", cfg.mycall), ("[tinybox] call", cfg.tinybox_call)):
        if not CALL_RE.match(call):
            raise ConfigError(f"{name}: invalid call {call!r}")
    if cfg.link not in ("agw", "kiss", "telnet"):
        raise ConfigError("[tinybox] link must be agw, kiss or telnet")
    if cfg.ui not in ("auto", "yes", "no"):
        raise ConfigError("[tinybox] ui must be auto, yes or no")
    return cfg
