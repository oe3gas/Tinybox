"""dxfeed.conf (INI) -> settings for collector and digest."""

from __future__ import annotations

import configparser
import dataclasses
import re
from dataclasses import dataclass, field
from pathlib import Path

from .cty import DEFAULT_URL
from .dxcc import DEFAULT_PATH as DICT_PATH
from .mostwanted import DEFAULT_URL as MW_URL
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
    mostwanted: Path = Path("data/mostwanted.json")
    mostwanted_url: str = MW_URL
    mostwanted_update_days: int = 7
    dictionary: Path = DICT_PATH          # brocast dictionary (DXCC list, from v4)


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
    relevance_a: float = 25.0       # score from here: tier A (look now)
    relevance_b: float = 12.0       # score from here: tier B (interesting), below C
    brocast: bool = True            # Brocast: page with the bulletin (PLANUNG 16a)
    brocast_tiers: str = "AB"       # tiers that go over the air
    brocast_max_rows: int = 12
    brocast_min_rows: int = 10      # fill up with the next most relevant (tier C)


@dataclass(frozen=True)
class Config:
    cluster: ClusterCfg
    data: DataCfg = field(default_factory=DataCfg)
    digest: DigestCfg = field(default_factory=DigestCfg)
    log_level: str = "INFO"
    log_file: str = ""
    inbox_source: str = "default"     # CR70: tinybox.conf | dxfeed.conf | default
    hints: tuple[str, ...] = ()


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
        keep_days=max(2, get("data", "keep_days", 7, int)),
        mostwanted=Path(get("data", "mostwanted", "data/mostwanted.json")),
        mostwanted_url=get("data", "mostwanted_url", MW_URL),
        mostwanted_update_days=max(1, get("data", "mostwanted_update_days", 7, int)),
        dictionary=Path(get("data", "dictionary", str(DICT_PATH))))

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
    try:
        rel_a = float(get("digest", "relevance_a", "25") or 25)
        rel_b = float(get("digest", "relevance_b", "12") or 12)
    except ValueError as exc:
        raise ConfigError(f"[digest] relevance_a/relevance_b: {exc}") from None
    if not 0 < rel_b <= rel_a:
        raise ConfigError("[digest] relevance_b must be > 0 and <= relevance_a")
    tiers = "".join(t for t in "ABC" if t in get("digest", "brocast_tiers", "AB").upper())
    if not tiers:
        raise ConfigError("[digest] brocast_tiers: one or more of A B C")
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
        inbox=Path("eingang"),
        relevance_a=rel_a,
        relevance_b=rel_b,
        brocast=get("digest", "brocast", True, bool),
        brocast_tiers=tiers,
        brocast_max_rows=min(40, max(1, get("digest", "brocast_max_rows", 12, int))),
        brocast_min_rows=min(40, max(0, get("digest", "brocast_min_rows", 10, int))))

    # CR70: the inbox folder belongs to tinybox.conf ([inbox] dir); [digest] inbox
    # is only an override
    hints: list[str] = []
    tb_inbox = None
    tb_name = get("tinybox", "conf", "")
    tb_path = Path(tb_name or "tinybox.conf")
    if not tb_path.is_absolute():
        tb_path = path.parent / tb_path
    if tb_path.is_file():
        tb_inbox = tinybox_inbox(tb_path)
    else:
        hints.append(f"[tinybox] conf: {tb_path} not found - inbox from dxfeed.conf "
                     "or the default")
    inbox, source = tb_inbox, f"tinybox.conf {tb_path}"
    if cp.has_option("digest", "inbox") and get("digest", "inbox", ""):
        own = Path(get("digest", "inbox", ""))
        if tb_inbox is not None:
            same = own.resolve() == tb_inbox.resolve()
            hints.append(f"[digest] inbox = {own}: " + ("same as [inbox] dir in tinybox.conf - "
                                                        "can be removed" if same else
                                                        f"overrides {tb_inbox} from tinybox.conf"))
        inbox, source = own, "dxfeed.conf"
    if inbox is None:
        inbox, source = Path("eingang"), "default (no tinybox.conf found)"
    digest = dataclasses.replace(digest, inbox=inbox)

    return Config(cluster=cluster, data=data, digest=digest,
                  log_level=get("log", "level", "INFO").upper(),
                  log_file=get("log", "file", ""), inbox_source=source, hints=tuple(hints))


def tinybox_inbox(tb_conf: Path) -> Path:
    """[inbox] dir of tinybox.conf, relative to that file (as TinyBox reads it)."""
    cp = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
    try:
        cp.read(tb_conf, encoding="utf-8")
    except (configparser.Error, OSError) as exc:
        raise ConfigError(f"[tinybox] conf: {tb_conf} not readable ({exc})") from None
    d = Path(cp.get("inbox", "dir", fallback="eingang").strip() or "eingang")
    return d if d.is_absolute() else tb_conf.parent / d
