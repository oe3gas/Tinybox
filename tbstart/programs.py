"""Which programs the station has, and how each one is started (CR138).

The list comes from tbstart.conf (section [start], written by release/konfig.py)
and the programs' own .conf files: port for the port check, role, web address.
Nothing here starts a process - that is supervisor.py.
"""

from __future__ import annotations

import configparser
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

START_CONF = "tbstart.conf"

# key in tbstart.conf -> default when the key is missing
DEFAULTS = {"direwolf": False, "kisshub": False, "tinybox": False,
            "tbclient": True, "brocast": False, "dxfeed": False}

PROFILES = {"1": "nur TBClient", "2": "TBClient + TinyBox", "3": "TBClient + brocast",
            "4": "alle"}


@dataclass
class Program:
    key: str                    # key in tbstart.conf
    name: str                   # shown in the console
    tag: str                    # short tag in front of every line
    cmd: list[str]
    cwd: Path
    active: bool                # tbstart.conf: yes
    port: int | None = None     # checked by a TCP connect to 127.0.0.1
    port_label: str = ""        # "AGW", "KISS", "Web"
    role: str = ""
    url: str | None = None      # w: open in the browser
    modem: bool = False         # Direwolf/kisshub: the others wait for its port
    missing: str = ""           # why it cannot start (file missing) - short, for the row
    detail: str = ""            # the same with the full path, for the lines below
    env: dict = field(default_factory=dict)


def read_conf(path: Path) -> configparser.ConfigParser:
    cp = configparser.ConfigParser(inline_comment_prefixes=("#", ";"), interpolation=None,
                                   strict=False)
    if path.is_file():
        try:
            cp.read(path, encoding="utf-8")
        except (configparser.Error, UnicodeDecodeError):
            pass
    return cp


def value(cp: configparser.ConfigParser, section: str, key: str, default: str = "") -> str:
    try:
        return cp.get(section, key, fallback=default).strip() or default
    except configparser.Error:
        return default


def as_int(text: str, default: int | None) -> int | None:
    try:
        return int(text)
    except (TypeError, ValueError):
        return default


def yes(text: str) -> bool:
    return text.strip().lower() in ("yes", "ja", "on", "true", "1")


def start_settings(root: Path) -> dict:
    """tbstart.conf [start]: which programs are active, Direwolf folder/exe."""
    cp = read_conf(root / START_CONF)
    s = {k: (yes(value(cp, "start", k)) if cp.has_option("start", k) else d)
         for k, d in DEFAULTS.items()}
    s["direwolf_dir"] = value(cp, "start", "direwolf_dir", str(root / "direwolf"))
    s["direwolf_exe"] = value(cp, "start", "direwolf_exe", "direwolf-tinybox.exe")
    s["kisshub_profile"] = value(cp, "start", "kisshub_profile")
    s["exists"] = (root / START_CONF).is_file()
    return s


def apply_profile(settings: dict, profile: str) -> dict:
    """TinyBox-Start.bat 1-4 (autostart): only for this run, not saved."""
    if profile in PROFILES:
        settings = dict(settings, tbclient=True, tinybox=profile in ("2", "4"),
                        brocast=profile in ("3", "4"))
    return settings


def agw_port(direwolf_conf: Path) -> int:
    if direwolf_conf.is_file():
        try:
            text = direwolf_conf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        m = re.search(r"^\s*AGWPORT\s+(\d+)", text, re.MULTILINE | re.IGNORECASE)
        if m:
            return int(m.group(1))
    return 8000


def programs(root: Path, settings: dict, python: str = sys.executable) -> list[Program]:
    """All programs of this installation, in start order. A program whose files are
    not installed (dxfeed is not in the release package) is left out."""
    py = [python, "-m"]
    out: list[Program] = []

    dw_dir = Path(settings["direwolf_dir"])
    dw_exe = dw_dir / settings["direwolf_exe"]
    dw = Program("direwolf", "Direwolf", "dwolf", [str(dw_exe), "-c", "direwolf.conf"], dw_dir,
                 settings["direwolf"], agw_port(dw_dir / "direwolf.conf"), "AGW", "Modem",
                 modem=True)
    if not dw_exe.is_file():
        dw.missing = f"{dw_exe.name} fehlt - k: Pfad einstellen"
        dw.detail = (f"{dw_exe} gibt es nicht. Mitgeliefert liegt Direwolf in direwolf\\ des "
                     "Installationsordners; ein eigener Direwolf: Taste k (Konfiguration) "
                     "oder direwolf_dir/direwolf_exe in tbstart.conf")
    elif not (dw_dir / "direwolf.conf").is_file():
        dw.missing = "direwolf.conf fehlt - k: Konfiguration"
        dw.detail = f"{dw_dir / 'direwolf.conf'} gibt es nicht"
    if settings["direwolf"] or dw_exe.is_file():
        out.append(dw)

    if (root / "kisshub").is_dir():
        cp = read_conf(root / "kisshub.conf")
        prof = settings["kisshub_profile"] or value(cp, "kisshub", "profile")
        out.append(Program("kisshub", "kisshub", "kisshb", py + ["kisshub", "-c", "kisshub.conf"],
                           root, settings["kisshub"],
                           as_int(value(cp, "server", "port"), 8101), "KISS", prof or "TNC",
                           modem=True, missing=_need(root, "kisshub.conf")))

    if (root / "tinybox").is_dir():
        cp = read_conf(root / "tinybox.conf")
        web = yes(value(cp, "web", "enabled", "yes"))
        port = as_int(value(cp, "web", "port"), 8080) if web else None
        out.append(Program("tinybox", "TinyBox", "tinyb", py + ["tinybox", "-c", "tinybox.conf"],
                           root, settings["tinybox"], port, "Web" if port else "",
                           value(cp, "station", "mailbox_call"),
                           f"http://127.0.0.1:{port}/" if port else None,
                           missing=_need(root, "tinybox.conf"),
                           env={"TINYBOX_LAUNCHER": "1"}))   # RESTART: exit code 3

    if (root / "tbclient").is_dir():
        cp = read_conf(root / "tbclient.conf")
        port = as_int(value(cp, "web", "port"), 7744)
        out.append(Program("tbclient", "TBClient", "tbcli", py + ["tbclient", "-c", "tbclient.conf"],
                           root, settings["tbclient"], port, "Web",
                           value(cp, "station", "mycall"), f"http://127.0.0.1:{port}/",
                           missing=_need(root, "tbclient.conf")))

    bro = root / "brocast"
    if (bro / "brocast").is_dir():
        cp = read_conf(bro / "brocastd.conf")
        mode = value(cp, "brocastd", "mode", "listener").lower()
        listener = mode != "station"
        port = as_int(value(cp, "listener", "web_port"), 7733) if listener else None
        out.append(Program("brocast", "brocastd", "brocst",
                           py + ["brocast.daemon", "-c", "brocastd.conf"], bro,
                           settings["brocast"], port, "Web" if port else "",
                           "Listener" if listener else "Station",
                           f"http://127.0.0.1:{port}/" if port else None,
                           missing=_need(bro, "brocastd.conf")))

    if (root / "dxfeed" / "__main__.py").is_file():
        out.append(Program("dxfeed", "dxfeed", "dxfeed",
                           py + ["dxfeed", "-c", "dxfeed.conf", "collect"], root,
                           settings["dxfeed"], role="Sammler",
                           missing=_need(root, "dxfeed.conf")))
    return out


def _need(folder: Path, name: str) -> str:
    return "" if (folder / name).is_file() else f"{name} fehlt"


def set_active(root: Path, key: str, active: bool) -> None:
    """d: write key = yes/no into tbstart.conf [start], keeping comments and order."""
    path = root / START_CONF
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    new = f"{key} = {'yes' if active else 'no'}"
    section, start_at, done = "", None, False
    for i, line in enumerate(lines):
        m = re.match(r"\s*\[([^\]]+)\]", line)
        if m:
            section = m.group(1).strip().lower()
            if section == "start":
                start_at = i
            continue
        if section == "start" and re.match(rf"\s*{re.escape(key)}\s*=", line):
            lines[i], done = new, True
            break
    if not done:
        if start_at is None:
            lines += ["[start]", new]
        else:
            lines.insert(start_at + 1, new)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
