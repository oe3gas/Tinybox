#!/usr/bin/env python3
"""Prepare the Feeder-Pi folder on the SD card (or in any folder).

After flashing Raspberry Pi OS Lite with Raspberry Pi Imager, plug the card in
again: Windows shows the boot partition ("bootfs", with config.txt). Then:

    py -3 pi_sd_vorbereiten.py                 # finds the boot partition itself
    py -3 pi_sd_vorbereiten.py --ziel F:\\      # or name it
    py -3 pi_sd_vorbereiten.py --ziel C:\\tmp   # any folder, e.g. for an update by scp

The result is <ziel>\\feederpi\\ with everything the Pi needs:
    install.sh, abholung.sh, systemd/, *.conf    from feederpi/ in this repo
    code/dxfeed/, code/geosphere_*.py            the programs (unchanged)
    code/brocast/brocast-core.yaml               dictionary (DXCC list for dxfeed)
    code/dxfeed.conf                             yours, if it exists here (callsign)
    feederpi.env                                 locator(s) for the forecast
    abholung.pub                                 public key of this PC (created if missing)
    VERSION                                      commit the folder was made from
All text files get Unix line ends (LF). Then on the Pi (via SSH):
    sudo sh /boot/firmware/feederpi/install.sh
Details: feederpi/README.md
"""

from __future__ import annotations

import argparse
import re
import shutil
import string
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pi_abholung import KEY, schluessel_sicherstellen   # noqa: E402

PI_FILES = ["install.sh", "abholung.sh", "README.md", "feederpi.env.example",
            "tmpfiles-feederpi.conf", "journald-feederpi.conf",
            "timesyncd-feederpi.conf", "sshd-feederpi.conf"]
CODE_FILES = ["geosphere_station.py", "geosphere_prognose.py", "geosphere_warnungen.py",
              "dxfeed.conf.example"]
LOC_RE = re.compile(r"^[A-Ra-r]{2}[0-9]{2}([A-Xa-x]{2}([0-9]{2})?)?$")


def boot_partitionen() -> list[Path]:
    """Windows drives that look like a Raspberry Pi boot partition."""
    if sys.platform != "win32":
        return []
    return [Path(f"{b}:\\") for b in string.ascii_uppercase
            if Path(f"{b}:\\config.txt").is_file() and Path(f"{b}:\\cmdline.txt").is_file()]


def locator_aus_bat() -> str:
    """LOCATOR from geosphere_aufgaben_einrichten.bat (what the PC used so far)."""
    bat = HERE / "geosphere_aufgaben_einrichten.bat"
    try:
        m = re.search(r"^set LOCATOR=(\S+)", bat.read_text(encoding="latin-1"), re.M)
    except OSError:
        m = None
    return m.group(1) if m else "JN88BN"


def version() -> str:
    try:
        r = subprocess.run(["git", "-C", str(HERE), "log", "-1", "--format=%H %cs"],
                           capture_output=True, text=True, check=True)
        commit, datum = r.stdout.split()
        dirty = subprocess.run(["git", "-C", str(HERE), "status", "--porcelain", "--",
                                "feederpi", "dxfeed", "geosphere_station.py",
                                "geosphere_prognose.py", "geosphere_warnungen.py"],
                               capture_output=True, text=True).stdout.strip()
        extra = " (mit lokalen Aenderungen)" if dirty else ""
        return f"commit={commit}{extra}\ndate={datum}\n"
    except (OSError, subprocess.CalledProcessError, ValueError):
        return "commit=unbekannt (kein git)\n"


def lf(path: Path) -> None:
    """Unix line ends for every text file (the Pi's sh chokes on CRLF)."""
    for f in [path] if path.is_file() else path.rglob("*"):
        if f.is_file():
            data = f.read_bytes()
            if b"\0" not in data and b"\r\n" in data:
                f.write_bytes(data.replace(b"\r\n", b"\n"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Feeder-Pi-Ordner fuer die SD-Karte erstellen")
    ap.add_argument("--ziel", type=Path,
                    help="Boot-Partition der SD-Karte oder beliebiger Ordner "
                         "(Standard: die gefundene Boot-Partition)")
    ap.add_argument("--locator", default=None,
                    help="Locator(s) fuer die Prognose, mehrere mit Komma "
                         "(Standard: aus geosphere_aufgaben_einrichten.bat)")
    ap.add_argument("--ohne-dxfeed-conf", action="store_true",
                    help="dxfeed.conf dieses PCs nicht mitnehmen (nur die Vorlage)")
    args = ap.parse_args(argv)

    ziel = args.ziel
    if ziel is None:
        kandidaten = boot_partitionen()
        if len(kandidaten) != 1:
            print("Boot-Partition nicht eindeutig gefunden"
                  + (f" ({', '.join(map(str, kandidaten))})" if kandidaten else "")
                  + " - bitte mit --ziel angeben, z. B. --ziel F:\\")
            return 1
        ziel = kandidaten[0]
    if not ziel.is_dir():
        print(f"{ziel} gibt es nicht")
        return 1
    locator = (args.locator or locator_aus_bat()).upper()
    for loc in locator.split(","):
        if not LOC_RE.match(loc):
            print(f"Locator {loc!r} ungueltig (z. B. JN88BN)")
            return 1

    dest = ziel / "feederpi"
    if dest.exists():
        shutil.rmtree(dest)
    (dest / "code").mkdir(parents=True)

    src = HERE / "feederpi"
    for name in PI_FILES:
        shutil.copy2(src / name, dest / name)
    shutil.copytree(src / "systemd", dest / "systemd")
    shutil.copytree(HERE / "dxfeed", dest / "code" / "dxfeed",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in CODE_FILES:
        shutil.copy2(HERE / name, dest / "code" / name)
    # dictionary of this PC (brocastd may have imported a newer one than the repo's)
    (dest / "code" / "brocast").mkdir()
    shutil.copy2(HERE / "brocast" / "brocast-core.yaml", dest / "code" / "brocast" / "brocast-core.yaml")

    hinweise = []
    conf = HERE / "dxfeed.conf"
    if conf.is_file() and not args.ohne_dxfeed_conf:
        text = conf.read_text(encoding="utf-8", errors="replace")
        shutil.copy2(conf, dest / "code" / "dxfeed.conf")
        if not re.search(r"^\s*login\s*=\s*[A-Za-z0-9]", text, re.M):
            hinweise.append("dxfeed.conf ohne Rufzeichen ([cluster] login) - dxfeed bleibt am Pi aus")
        if "\\" in text:
            hinweise.append("dxfeed.conf enthaelt Windows-Pfade (\\) - am Pi in "
                            "/opt/tinybox/dxfeed.conf pruefen")
    else:
        hinweise.append("keine dxfeed.conf mitgenommen: am Pi /opt/tinybox/dxfeed.conf "
                        "anpassen ([cluster] login = Rufzeichen)")

    env = (src / "feederpi.env.example").read_text(encoding="utf-8")
    env = re.sub(r"^LOCATOR=.*$", f"LOCATOR={locator}", env, flags=re.M)
    (dest / "feederpi.env").write_text(env, encoding="utf-8", newline="\n")

    pub = schluessel_sicherstellen()
    shutil.copy2(pub, dest / "abholung.pub")
    (dest / "VERSION").write_text(version() + f"built={datetime.now():%Y-%m-%d %H:%M}\n",
                                  encoding="utf-8", newline="\n")
    lf(dest)

    groesse = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file())
    print(f"Fertig: {dest}  ({groesse // 1024} KB)")
    print(f"  Locator(s):     {locator}")
    print(f"  PC-Schluessel:  {KEY} (oeffentlicher Teil als abholung.pub)")
    for h in hinweise:
        print(f"  HINWEIS: {h}")
    print()
    print("Weiter: Karte auswerfen, in den Pi stecken, starten, per SSH anmelden, dann")
    print("  sudo sh /boot/firmware/feederpi/install.sh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
