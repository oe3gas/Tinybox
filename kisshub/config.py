"""kisshub.conf (INI) -> profile, transport and hub settings."""

from __future__ import annotations

import configparser
import dataclasses
from dataclasses import dataclass
from pathlib import Path

from tinybox.ax25 import kissio

from .hub import HubCfg
from .profiles import PROFILES, Profile, with_init_lines


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class TncCfg:
    profile: Profile
    transport: str = "serial"         # serial | tcp
    device: str = ""
    serial_baud: int = 9600
    host: str = "127.0.0.1"
    port: int = 0
    reconnect_sec: int = 10
    params: dict = dataclasses.field(default_factory=dict)   # KISS command -> value


@dataclass(frozen=True)
class Config:
    tnc: TncCfg
    hub: HubCfg
    log_level: str = "INFO"
    log_file: str = ""


def load(path: str | Path) -> Config:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")
    cp = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
    cp.read(path, encoding="utf-8")

    def get(sec, key, default, kind=str):
        try:
            if kind is int:
                return cp.getint(sec, key, fallback=default)
            if kind is bool:
                return cp.getboolean(sec, key, fallback=default)
            return cp.get(sec, key, fallback=default).strip()
        except ValueError as exc:
            raise ConfigError(f"[{sec}] {key}: {exc}") from None

    name = get("tnc", "profile", "generic").lower()
    if name not in PROFILES:
        raise ConfigError(f"[tnc] profile: '{name}' - use one of {', '.join(PROFILES)}")
    profile = PROFILES[name]
    lines = [x.strip() for x in get("tnc", "init_lines", "").split("|") if x.strip()]
    if lines:
        profile = with_init_lines(profile, lines)
    exit_kiss = get("tnc", "exit_kiss_on_stop", profile.exit_kiss, bool)
    profile = dataclasses.replace(profile, exit_kiss=exit_kiss)

    transport = get("tnc", "transport", "serial").lower()
    if transport not in ("serial", "tcp"):
        raise ConfigError("[tnc] transport: use serial or tcp")
    device = get("tnc", "device", "")
    if transport == "serial" and not device:
        raise ConfigError("[tnc] device: the serial port, e.g. COM3 or /dev/ttyUSB0")
    tport = get("tnc", "port", 0, int)
    if transport == "tcp" and not 1 <= tport <= 65535:
        raise ConfigError("[tnc] port: the TCP port of the TNC")

    send_params = get("kiss", "send_params", True, bool)
    txdelay_ms = get("kiss", "txdelay_ms", 300, int)
    params = {}
    if send_params:
        params = {kissio.CMD_TXDELAY: kissio.ms_to_units(txdelay_ms),
                  kissio.CMD_P: get("kiss", "persist", 63, int),
                  kissio.CMD_SLOTTIME: kissio.ms_to_units(get("kiss", "slottime_ms", 100, int)),
                  kissio.CMD_FULLDUPLEX: 0}
        if not 0 <= params[kissio.CMD_P] <= 255:
            raise ConfigError("[kiss] persist: 0..255")

    tnc = TncCfg(profile=profile, transport=transport, device=device,
                 serial_baud=get("tnc", "serial_baud", profile.serial_baud, int),
                 host=get("tnc", "host", "127.0.0.1"), port=tport,
                 reconnect_sec=get("tnc", "reconnect_sec", 10, int), params=params)
    hub = HubCfg(listen=get("server", "listen", "127.0.0.1"),
                 port=get("server", "port", 8101, int),
                 air_baud=get("kiss", "air_baud", 1200, int),
                 txdelay_sec=txdelay_ms / 1000,
                 max_lead_sec=get("kiss", "max_lead_ms", 1500, int) / 1000,
                 status_every_sec=get("log", "status_every_sec", 600, int))
    if not 1 <= hub.port <= 65535:
        raise ConfigError("[server] port: 1..65535")
    if hub.air_baud < 300:
        raise ConfigError("[kiss] air_baud: at least 300")
    return Config(tnc=tnc, hub=hub, log_level=get("log", "level", "INFO").upper(),
                  log_file=get("log", "file", ""))


def make_transport(t: TncCfg):
    from .transport import SerialTransport, TcpTransport
    if t.transport == "tcp":
        return TcpTransport(t.host, t.port)
    return SerialTransport(t.device, t.serial_baud, t.profile.dtr, t.profile.rts)
