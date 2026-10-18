"""fwdsim.conf (INI). Every value has a default, the file is optional."""

from __future__ import annotations

import configparser
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BbsCfg:
    call: str
    haddress: str
    qth: str
    bid_start: int


@dataclass
class TinyboxCfg:
    call: str = "OE3XTC"                       # mailbox call without SSID (addresses, R: lines)
    haddress: str = "OE3XTC.#NOE.AUT.EU"
    ax25_call: str = "OE3XTC-1"                # mailbox_call from tinybox.conf (on the air)
    forward_host: str = "127.0.0.1"            # TinyBox incoming forward port (fwdsim calls)
    forward_port: int = 0                      # 0 = TinyBox has none
    forward_password: str = ""                 # TinyBox asks Callsign: / Password:
    telnet_host: str = "127.0.0.1"             # to enter test mail into TinyBox
    telnet_port: int = 6300
    telnet_user: str = "OE3XTC"
    db: str = ""                               # tinybox.db for read-only checks, "" = none


@dataclass
class AgwCfg:
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 8000
    radio_port: int = 0
    paclen: int = 128
    max_outstanding: int = 4
    via: list[str] = field(default_factory=list)   # digipeaters/nodes to TinyBox


@dataclass
class Config:
    db: str = "data/fwdsim.db"
    tcp_listen_host: str = "127.0.0.1"
    tcp_listen_port: int = 6311                # TinyBox calls OE3GAS here
    hop_ax25_call: str = "OE3GAS"              # call OE3GAS uses on the air (may carry an SSID)
    timeout_tcp: float = 30
    timeout_radio: float = 300
    wait_for_tinybox: float = 120              # how long a test waits for TinyBox to call
    hop: BbsCfg = field(default_factory=lambda: BbsCfg(
        "OE3GAS", "OE3GAS.#OOE.AUT.EU", "Linz", 0))
    remote: BbsCfg = field(default_factory=lambda: BbsCfg(
        "DL0XTC", "DL0XTC.#BAY.DEU.EU", "Muenchen", 0))
    tinybox: TinyboxCfg = field(default_factory=TinyboxCfg)
    agw: AgwCfg = field(default_factory=AgwCfg)
    base_dir: Path = field(default_factory=Path.cwd)
    sources: dict = field(default_factory=dict)   # CR70: value -> where it came from
    hints: list = field(default_factory=list)

    @property
    def db_path(self) -> Path:
        p = Path(self.db)
        return p if p.is_absolute() else self.base_dir / p


def load(path: str | Path | None) -> Config:
    cfg = Config()
    if path is None or not Path(path).exists():
        return cfg
    path = Path(path)
    cfg.base_dir = path.resolve().parent
    cp = configparser.ConfigParser(inline_comment_prefixes=(";", "#"))
    cp.read(path, encoding="utf-8")

    def get(sec, key, default, kind=str):
        if not cp.has_option(sec, key):
            return default
        raw = cp.get(sec, key).strip()
        if kind is bool:
            return raw.lower() in ("1", "yes", "true", "on")
        if kind is list:
            return [x.upper() for x in raw.replace(",", " ").split()]
        return kind(raw) if raw != "" else default

    cfg.db = get("fwdsim", "db", cfg.db)
    cfg.tcp_listen_host = get("fwdsim", "tcp_listen_host", cfg.tcp_listen_host)
    cfg.tcp_listen_port = get("fwdsim", "tcp_listen_port", cfg.tcp_listen_port, int)
    cfg.hop_ax25_call = get("fwdsim", "hop_ax25_call", cfg.hop_ax25_call).upper()
    cfg.timeout_tcp = get("fwdsim", "timeout_tcp", cfg.timeout_tcp, float)
    cfg.timeout_radio = get("fwdsim", "timeout_radio", cfg.timeout_radio, float)
    cfg.wait_for_tinybox = get("fwdsim", "wait_for_tinybox", cfg.wait_for_tinybox, float)
    for sec, b in (("hop", cfg.hop), ("remote", cfg.remote)):
        b.call = get(sec, "call", b.call).upper()
        b.haddress = get(sec, "haddress", b.haddress).upper()
        b.qth = get(sec, "qth", b.qth)
        b.bid_start = get(sec, "bid_start", b.bid_start, int)
    t = cfg.tinybox
    a = cfg.agw
    _from_tinybox(cfg, cp, path)            # CR70: tinybox.conf / direwolf.conf first
    for key in ("call", "haddress", "ax25_call", "telnet_port", "db"):
        if cp.has_option("tinybox", key) and cfg.sources.get(key, "").startswith("tinybox.conf"):
            cfg.hints.append(f"[tinybox] {key}: overrides the value from tinybox.conf")
            cfg.sources[key] = "fwdsim.conf"
    for key in ("port", "paclen", "max_outstanding"):
        if cp.has_option("agw", key) and cfg.sources.get(f"agw_{key}") == "direwolf.conf":
            cfg.hints.append(f"[agw] {key}: overrides the value from direwolf.conf")
    t.call = get("tinybox", "call", t.call).upper()
    t.haddress = get("tinybox", "haddress", t.haddress).upper()
    t.ax25_call = get("tinybox", "ax25_call", t.ax25_call).upper()
    t.forward_host = get("tinybox", "forward_host", t.forward_host)
    t.forward_port = get("tinybox", "forward_port", t.forward_port, int)
    t.forward_password = get("tinybox", "forward_password", t.forward_password)
    t.telnet_host = get("tinybox", "telnet_host", t.telnet_host)
    t.telnet_port = get("tinybox", "telnet_port", t.telnet_port, int)
    t.telnet_user = get("tinybox", "telnet_user", t.telnet_user).upper()
    t.db = get("tinybox", "db", t.db)
    a.enabled = get("agw", "enabled", a.enabled, bool)
    a.host = get("agw", "host", a.host)
    a.port = get("agw", "port", a.port, int)
    a.radio_port = get("agw", "channel", get("agw", "radio_port", a.radio_port, int), int)
    a.paclen = get("agw", "paclen", a.paclen, int)
    a.max_outstanding = get("agw", "max_outstanding", a.max_outstanding, int)
    a.via = get("agw", "via", a.via, list)
    return cfg


def _from_tinybox(cfg: Config, cp: configparser.ConfigParser, path: Path) -> None:
    """CR70: [tinybox] conf = tinybox.conf gives mailbox call, haddress, telnet
    port and the database; [agw] direwolf_conf gives AGW port, PACLEN, window.
    The keys in fwdsim.conf stay as overrides."""
    t, a = cfg.tinybox, cfg.agw
    name = cp.get("tinybox", "conf", fallback="").strip()
    if name:
        p = Path(name)
        p = p if p.is_absolute() else path.parent / p
        if not p.is_file():
            cfg.hints.append(f"[tinybox] conf: {p} not found - fwdsim.conf values only")
        else:
            tb = configparser.ConfigParser(inline_comment_prefixes=(";", "#"))
            tb.read(p, encoding="utf-8")
            src = f"tinybox.conf {p}"
            mbx = tb.get("station", "mailbox_call", fallback="").strip().upper()
            if mbx:
                t.ax25_call, cfg.sources["ax25_call"] = mbx, src
                base = mbx.split("-")[0]
                t.call, cfg.sources["call"] = base, src
                t.telnet_user = base
            had = tb.get("station", "haddress", fallback="").strip().upper()
            if had:
                t.haddress, cfg.sources["haddress"] = had, src
            tp = tb.get("telnet", "port", fallback="").strip()
            if tp.isdigit():
                t.telnet_port, cfg.sources["telnet_port"] = int(tp), src
            data = Path(tb.get("storage", "data_dir", fallback="data").strip() or "data")
            data = data if data.is_absolute() else p.parent / data
            t.db, cfg.sources["db"] = str(data / "tinybox.db"), src
    dwp = cp.get("agw", "direwolf_conf", fallback="").strip().strip('"')
    if dwp:
        import sys
        root = Path(__file__).resolve().parents[1]
        if str(root) not in sys.path:
            sys.path.append(str(root))
        from prcore import direwolfconf
        q = Path(dwp)
        q = q if q.is_absolute() or q.exists() else path.parent / q
        try:
            dw = direwolfconf.read(q)
        except direwolfconf.DirewolfConfError as exc:
            cfg.hints.append(f"[agw] direwolf_conf: {exc}")
            return
        if dw.agw_port:
            a.port, cfg.sources["agw_port"] = dw.agw_port, "direwolf.conf"
        if dw.paclen:
            a.paclen, cfg.sources["agw_paclen"] = dw.paclen, "direwolf.conf"
        window = dw.emaxframe or dw.maxframe
        if window:
            a.max_outstanding, cfg.sources["agw_max_outstanding"] = min(7, window), "direwolf.conf"
