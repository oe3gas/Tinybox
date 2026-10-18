"""kisshub.conf (INI) -> profile, transport and hub settings."""

from __future__ import annotations

import configparser
import dataclasses
from dataclasses import dataclass
from pathlib import Path

from prcore import direwolfconf, kiss

from .hub import HubCfg
from .profiles import PROFILES, TUNNEL_MODES, Profile, ax25_recommendation, with_init_lines

# CR70: [ax25] in kisshub.conf may override the recommendation of the profile
AX25_KEYS = {"paclen": (int, 16, 256), "maxframe": (int, 1, 7), "maxframe_ext": (int, 1, 127),
             "n2": (int, 1, 50), "t1_min_sec": (float, 0.1, 3600), "t1_max_sec": (float, 0.1, 3600),
             "t2_sec": (float, 0, 3600), "t3_sec": (float, 0, 3600)}


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
    trace: bool = False               # [log] trace: every byte to/from the TNC in hex
    hints: tuple[str, ...] = ()       # CR70: old keys still in the file, shown at start
    direwolf: str = ""                # CR70: what was read from direwolf.conf


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
    tunnel = get("tnc", "vara_tunnel", profile.tunnel).lower()
    if tunnel not in TUNNEL_MODES:
        raise ConfigError(f"[tnc] vara_tunnel: use {', '.join(TUNNEL_MODES)}")
    bundle_ms = get("tnc", "vara_bundle_ms", profile.bundle_ms, int)
    bundle_max = get("tnc", "vara_bundle_max", profile.bundle_max, int)
    if not 0 <= bundle_ms <= 2000:
        raise ConfigError("[tnc] vara_bundle_ms: 0 (off) .. 2000")
    if not 100 <= bundle_max <= 5000:
        raise ConfigError("[tnc] vara_bundle_max: 100 .. 5000 (VARA's limit)")
    if bundle_ms and tunnel == "no":
        raise ConfigError("[tnc] vara_bundle_ms: only with the VARA tunnel (vara_tunnel)")
    profile = dataclasses.replace(profile, exit_kiss=exit_kiss, tunnel=tunnel,
                                  bundle_ms=bundle_ms, bundle_max=bundle_max)

    hints: list[str] = []
    dw = None
    if profile.reads_direwolf_conf:
        dpath = get("tnc", "direwolf_conf", "")
        if not dpath:
            raise ConfigError("[tnc] direwolf_conf: the Direwolf folder or its direwolf.conf "
                              "(profile direwolf)")
        try:
            dw = direwolfconf.read(dpath)
        except direwolfconf.DirewolfConfError as exc:
            raise ConfigError(f"[tnc] direwolf_conf: {exc}") from None
    dch = dw.channel(0) if dw else None

    transport = get("tnc", "transport", "tcp" if profile.tcp_port else "serial").lower()
    if transport not in ("serial", "tcp"):
        raise ConfigError("[tnc] transport: use serial or tcp")
    device = get("tnc", "device", "")
    if transport == "serial" and not device:
        raise ConfigError("[tnc] device: the serial port, e.g. COM3 or /dev/ttyUSB0")
    tport_default = (dw.kiss_port if dw and dw.kiss_port else profile.tcp_port)
    tport = get("tnc", "port", tport_default, int)
    if transport == "tcp" and not 1 <= tport <= 65535:
        raise ConfigError("[tnc] port: the TCP port of the TNC")

    send_params = get("kiss", "send_params", profile.kiss_params, bool)
    if send_params and not profile.kiss_params:
        raise ConfigError(f"[kiss] send_params: must be no with profile {profile.name} - "
                          "VARA reads KISS commands 1 and 2 as its frame types and would "
                          "send them on the air")
    # CR70: radio values - profile, then direwolf.conf, then kisshub.conf [kiss]
    sources: dict[str, str] = {}

    def radio(key: str, profile_value: int, dw_value: int | None) -> int:
        if cp.has_option("kiss", key):
            sources[key] = "kisshub.conf"
            return get("kiss", key, profile_value, int)
        if dw_value is not None:
            sources[key] = "direwolf.conf"
            return dw_value
        sources[key] = f"profile {profile.name}"
        return profile_value

    air_baud = radio("air_baud", profile.air_baud, dch.baud if dch else None)
    txdelay_ms = radio("txdelay_ms", profile.txdelay_ms, dch.txdelay_ms if dch else None)
    max_lead_ms = radio("max_lead_ms", profile.max_lead_ms, None)
    ax25 = ax25_recommendation(profile)
    if dw:                                   # Direwolf's own AX.25 values as the hint
        if dw.paclen:
            ax25["paclen"] = dw.paclen
        if dw.maxframe:
            ax25["maxframe"] = dw.maxframe
        if dw.emaxframe:
            ax25["maxframe_ext"] = dw.emaxframe
    sources["ax25"] = "direwolf.conf" if dw else f"profile {profile.name}"
    if cp.has_section("ax25"):
        for key in cp.options("ax25"):
            if key not in AX25_KEYS:
                raise ConfigError(f"[ax25] {key}: unknown - use {', '.join(AX25_KEYS)}")
            kind, lo, hi = AX25_KEYS[key]
            value = get("ax25", key, 0, int) if kind is int else _float(cp, key)
            if not lo <= value <= hi:
                raise ConfigError(f"[ax25] {key}: {lo}..{hi}")
            ax25[key] = value
        if cp.options("ax25"):
            sources["ax25"] += " + kisshub.conf [ax25]"
    params = {}
    if send_params:
        params = {kiss.CMD_TXDELAY: kiss.ms_to_units(txdelay_ms),
                  kiss.CMD_P: get("kiss", "persist", 63, int),
                  kiss.CMD_SLOTTIME: kiss.ms_to_units(get("kiss", "slottime_ms", 100, int)),
                  kiss.CMD_FULLDUPLEX: 0}
        if not 0 <= params[kiss.CMD_P] <= 255:
            raise ConfigError("[kiss] persist: 0..255")

    tnc = TncCfg(profile=profile, transport=transport, device=device,
                 serial_baud=get("tnc", "serial_baud", profile.serial_baud, int),
                 host=get("tnc", "host", "127.0.0.1"), port=tport,
                 reconnect_sec=get("tnc", "reconnect_sec", 10, int), params=params)
    port = get("server", "port", 8101, int)
    # CR70: host fixed 127.0.0.1, status on port + 1; the old keys still work
    for key, default in (("listen", "127.0.0.1"), ("status_port", str(port + 1))):
        if cp.has_option("server", key):
            hints.append(f"[server] {key} = {get('server', key, '')}: "
                         + ("same as the default - can be removed"
                            if get("server", key, "") == default
                            else f"overrides the default {default}"))
    hub = HubCfg(listen=get("server", "listen", "127.0.0.1"),
                 port=port,
                 air_baud=air_baud,
                 txdelay_sec=txdelay_ms / 1000,
                 max_lead_sec=max_lead_ms / 1000,
                 status_every_sec=get("log", "status_every_sec", 600, int),
                 status_port=get("server", "status_port", port + 1, int),
                 profile=profile.name, sources=sources, ax25=ax25,
                 links_file=get("log", "links_file", "kisshub-links.jsonl"),
                 vara_monitor=get("vara", "monitor", False, bool),
                 vara_host=get("vara", "host", get("tnc", "host", "127.0.0.1")),
                 vara_cmd_port=get("vara", "cmd_port", 8300, int),
                 sn_window_sec=get("vara", "sn_window_ms", 1500, int) / 1000)
    if not 1 <= hub.port <= 65535:
        raise ConfigError("[server] port: 1..65535")
    if not 0 <= hub.status_port <= 65535:
        raise ConfigError("[server] status_port: 0 (off) or 1..65535")
    if hub.vara_monitor and not profile.name.startswith("vara"):
        raise ConfigError("[vara] monitor: only with profile vara-fm or vara-hf")
    if not 1 <= hub.vara_cmd_port <= 65535:
        raise ConfigError("[vara] cmd_port: 1..65535")
    if hub.air_baud < 300:
        raise ConfigError("[kiss] air_baud: at least 300")
    if not 0 <= txdelay_ms <= 10000:
        raise ConfigError("[kiss] txdelay_ms: 0..10000")
    return Config(tnc=tnc, hub=hub, log_level=get("log", "level", "INFO").upper(),
                  log_file=get("log", "file", ""), trace=get("log", "trace", False, bool),
                  hints=tuple(hints), direwolf=dw.describe() if dw else "")


def _float(cp: configparser.ConfigParser, key: str) -> float:
    try:
        return cp.getfloat("ax25", key)
    except ValueError as exc:
        raise ConfigError(f"[ax25] {key}: {exc}") from None


def radio_lines(cfg: Config) -> list[str]:
    """CR70: where each radio value came from - shown at every start."""
    h = cfg.hub
    src = h.sources
    lines = [f"radio: air_baud {h.air_baud} ({src.get('air_baud')}), "
             f"txdelay {round(h.txdelay_sec * 1000)} ms ({src.get('txdelay_ms')}), "
             f"max_lead {round(h.max_lead_sec * 1000)} ms ({src.get('max_lead_ms')})",
             "AX.25 recommendation for TinyBox/client: "
             + ", ".join(f"{k} {v}" for k, v in h.ax25.items()) + f" ({src.get('ax25')})"]
    if not h.status_port:
        lines.append("status query off ([server] status_port = 0) - TinyBox and client "
                     "keep their own values")
    if cfg.direwolf:
        lines.insert(0, f"direwolf.conf {cfg.direwolf}")
    lines += [f"hint: {x}" for x in cfg.hints]
    return lines


def make_transport(t: TncCfg):
    from .transport import SerialTransport, TcpTransport
    if t.transport == "tcp":
        return TcpTransport(t.host, t.port)
    return SerialTransport(t.device, t.serial_baud, t.profile.dtr, t.profile.rts)
