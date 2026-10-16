"""dxfeed.conf (INI) -> settings for collector and digest."""

from __future__ import annotations

import configparser
import re
from dataclasses import dataclass, field
from pathlib import Path

from .cty import DEFAULT_URL
from .spots import BAND_ORDER, clean_call

VALID_RE = re.compile(r"^\d+[mhd]$", re.IGNORECASE)
RUBRIC_RE = re.compile(r"^[A-Z0-9]{1,6}$")

DEFAULT_EXCLUDE = (
    # Europe: the entities that are on the air every day
    "DL F G GM GW GI EI I EA CT ON PA LX HB OE OK OM SP HA S5 9A E7 YU Z3 LZ YO "
    "ER SV OZ SM LA OH ES YL LY UR EU UA UA2 "
    # elsewhere: very common from Europe
    "K VE JA UA9")
DEFAULT_BANDS = "160m 80m 60m 40m 30m 20m 17m 15m 12m 10m 6m 4m 2m 70cm"
# on these bands every DXCC counts: 2m/70cm DX from here is mostly Europe
DEFAULT_ALL_DXCC_BANDS = "2m 70cm"


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class ClusterCfg:
    nodes: tuple[tuple[str, int], ...]
    login: str
    skimmer: bool = False
    init: tuple[str, ...] = ()
    idle_timeout_sec: int = 900
    reconnect_sec: int = 30
    reconnect_max_sec: int = 600


@dataclass(frozen=True)
class DataCfg:
    db: Path = Path("data/dxfeed.db")
    cty: Path = Path("data/cty.dat")
    cty_url: str = DEFAULT_URL
    cty_update_days: int = 14
    ssl_verify: bool = True
    keep_days: int = 7


@dataclass(frozen=True)
class DigestCfg:
    to: str = "DX"
    hours: int = 24
    spotter_continents: frozenset[str] = frozenset({"EU"})
    exclude: frozenset[str] = frozenset(DEFAULT_EXCLUDE.split())
    bands: tuple[str, ...] = tuple(DEFAULT_BANDS.split())
    all_dxcc_bands: frozenset[str] = frozenset(DEFAULT_ALL_DXCC_BANDS.split())
    min_spotters: int = 2
    max_lines: int = 30
    max_bytes: int = 3000
    valid: str = "7d"
    inbox: Path = Path("eingang")


@dataclass(frozen=True)
class Config:
    cluster: ClusterCfg
    data: DataCfg = field(default_factory=DataCfg)
    digest: DigestCfg = field(default_factory=DigestCfg)
    log_level: str = "INFO"
    log_file: str = ""


def parse_nodes(text: str) -> tuple[tuple[str, int], ...]:
    out = []
    for item in text.replace(",", " ").split():
        host, sep, port = item.rpartition(":")
        if not sep or not host or not port.isdigit() or not 0 < int(port) < 65536:
            raise ConfigError(f"[cluster] nodes: '{item}' - format host:port")
        out.append((host, int(port)))
    if not out:
        raise ConfigError("[cluster] nodes: at least one host:port needed")
    return tuple(out)


def load(path: str | Path) -> Config:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"config file not found: {path} (copy dxfeed.conf.example)")
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

    login = clean_call(get("cluster", "login", ""))
    if not login:
        raise ConfigError("[cluster] login: please enter your callsign")
    init = tuple(c.strip() for c in get("cluster", "init", "").split("|") if c.strip())
    cluster = ClusterCfg(
        nodes=parse_nodes(get("cluster", "nodes", "dxc.hamserve.uk:7300")),
        login=login,
        skimmer=get("cluster", "skimmer", False, bool),
        init=init,
        idle_timeout_sec=max(60, get("cluster", "idle_timeout_sec", 900, int)),
        reconnect_sec=max(5, get("cluster", "reconnect_sec", 30, int)),
        reconnect_max_sec=max(30, get("cluster", "reconnect_max_sec", 600, int)))

    data = DataCfg(
        db=Path(get("data", "db", "data/dxfeed.db")),
        cty=Path(get("data", "cty", "data/cty.dat")),
        cty_url=get("data", "cty_url", DEFAULT_URL),
        cty_update_days=max(1, get("data", "cty_update_days", 14, int)),
        ssl_verify=get("data", "ssl_verify", True, bool),
        keep_days=max(2, get("data", "keep_days", 7, int)))

    to = get("digest", "to", "DX").upper()
    if not RUBRIC_RE.match(to):
        raise ConfigError(f"[digest] to: '{to}' - 1-6 letters/digits, no @ (local only)")
    bands = tuple(b.lower() for b in get("digest", "bands", DEFAULT_BANDS).split())
    all_dxcc = tuple(b.lower() for b in get("digest", "all_dxcc_bands",
                                            DEFAULT_ALL_DXCC_BANDS).split())
    for key, lst in (("bands", bands), ("all_dxcc_bands", all_dxcc)):
        unknown = [b for b in lst if b not in BAND_ORDER]
        if unknown:
            raise ConfigError(f"[digest] {key}: unknown {' '.join(unknown)} "
                              f"(known: {' '.join(BAND_ORDER)})")
    valid = get("digest", "valid", "7d")
    if valid and not VALID_RE.match(valid):
        raise ConfigError(f"[digest] valid: '{valid}' - e.g. 36h, 7d, empty = keep")
    digest = DigestCfg(
        to=to,
        hours=min(168, max(1, get("digest", "hours", 24, int))),
        spotter_continents=frozenset(get("digest", "spotter_continents", "EU").upper().split()),
        exclude=frozenset(get("digest", "exclude", DEFAULT_EXCLUDE).upper().split()),
        bands=bands,
        all_dxcc_bands=frozenset(all_dxcc),
        min_spotters=max(1, get("digest", "min_spotters", 2, int)),
        max_lines=max(5, get("digest", "max_lines", 30, int)),
        max_bytes=max(800, get("digest", "max_bytes", 3000, int)),
        valid=valid,
        inbox=Path(get("digest", "inbox", "eingang")))

    return Config(cluster=cluster, data=data, digest=digest,
                  log_level=get("log", "level", "INFO").upper(),
                  log_file=get("log", "file", ""))
