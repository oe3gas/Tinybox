#!/usr/bin/env python3
"""Fetch the finished bulletins from the Feeder-Pi into the TinyBox inbox.

The Feeder-Pi (feederpi/README.md) runs dxfeed and the GeoSphere jobs and puts
their bulletin files into its outbox. This script runs on the TinyBox PC, every
5 minutes from the Windows task scheduler (pi_abholung_einrichten.bat):

    pyw -3 pi_abholung.py --host 10.0.0.20 --log logs\\pi_abholung.log
    py  -3 pi_abholung.py --host 10.0.0.20 --test      # only show what is waiting

Over SSH (user "abholer", own key ~/.ssh/tinybox_feederpi) the Pi only allows
"list", "bundle" and "ack" (feederpi/abholung.sh). One run = two connections:
1. "bundle": all finished *.txt files as one tar stream,
2. write each file as NAME.abholung.tmp into the inbox, rename it to NAME.txt
   (TinyBox only reads *.txt, so it never sees a half-written file),
3. "ack NAME ...": the Pi moves the fetched files to abgeholt/.
If step 3 fails, the next run fetches the same files again; they carry a
Replace: key, so TinyBox replaces the bulletin instead of doubling it.

The inbox folder is [inbox] dir from tinybox.conf next to this script
(default: eingang). Only the Python standard library and Windows' own OpenSSH
client (ssh.exe, part of Windows 10/11) are needed.
"""

from __future__ import annotations

import argparse
import configparser
import io
import os
import re
import shutil
import socket
import subprocess
import sys
import tarfile
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEY = Path.home() / ".ssh" / "tinybox_feederpi"
STATE = HERE / "data" / "pi_abholung.state"
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}\.txt$")
MAX_FILE = 512 * 1024                 # a bulletin is a few KB; anything bigger is wrong
MAX_TOTAL = 32 * 1024 * 1024
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)   # pyw: no console flashing up


class AbholFehler(Exception):
    """Connection or protocol problem (the run is retried in 5 minutes)."""


def ssh_programm(name: str = "ssh") -> str:
    """ssh.exe / ssh-keygen.exe: PATH first, then the Windows OpenSSH folder."""
    found = shutil.which(name)
    if found:
        return found
    root = os.environ.get("SystemRoot", r"C:\Windows")
    # Sysnative: a 32-bit Python does not see System32\OpenSSH otherwise
    for sub in ("Sysnative", "System32"):
        p = Path(root) / sub / "OpenSSH" / f"{name}.exe"
        if p.is_file():
            return str(p)
    raise AbholFehler(f"{name} nicht gefunden - Windows: Einstellungen > Optionale Features > "
                      "OpenSSH-Client")


def schluessel_sicherstellen(key: Path = KEY) -> Path:
    """Create the key pair for the Pi (no passphrase: the scheduler runs unattended;
    the Pi only lets this key fetch bulletins). Returns the public key file."""
    pub = key.with_name(key.name + ".pub")
    if key.is_file() and pub.is_file():
        return pub
    key.parent.mkdir(parents=True, exist_ok=True)
    kommentar = f"tinybox-abholung@{socket.gethostname()}"
    subprocess.run([ssh_programm("ssh-keygen"), "-q", "-t", "ed25519", "-N", "",
                    "-C", kommentar, "-f", str(key)], check=True)
    print(f"Neuer SSH-Schluessel fuer den Feeder-Pi: {key}")
    return pub


def eingang_ordner() -> Path:
    """[inbox] dir of tinybox.conf next to this script, as TinyBox reads it."""
    conf = HERE / "tinybox.conf"
    d = Path("eingang")
    if conf.is_file():
        cp = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
        cp.read(conf, encoding="utf-8")
        d = Path(cp.get("inbox", "dir", fallback="eingang").strip() or "eingang")
    return d if d.is_absolute() else HERE / d


def ssh(args, befehl: list[str], timeout: int = 60) -> bytes:
    cmd = [ssh_programm(), "-i", str(args.key), "-p", str(args.port),
           "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
           "-o", "ConnectTimeout=15", "-o", "ServerAliveInterval=10",
           "-o", "ServerAliveCountMax=3", "-o", "StrictHostKeyChecking=accept-new",
           "-o", "LogLevel=ERROR", f"{args.user}@{args.host}", *befehl]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=NO_WINDOW)
    except subprocess.TimeoutExpired:
        raise AbholFehler(f"Pi {args.host} antwortet nicht ({timeout} s)") from None
    if r.returncode != 0:
        msg = r.stderr.decode("utf-8", "replace").strip().splitlines()
        raise AbholFehler(f"ssh {befehl[0]} an {args.host}: "
                          f"{msg[-1] if msg else 'Fehlercode %d' % r.returncode}")
    return r.stdout


def abholen(args) -> list[str]:
    """One run: fetch, write, acknowledge. Returns the fetched file names."""
    daten = ssh(args, ["bundle"], timeout=120)
    if not daten:
        return []
    if len(daten) > MAX_TOTAL:
        raise AbholFehler(f"Paket zu gross ({len(daten)} Bytes)")
    eingang = args.eingang
    eingang.mkdir(parents=True, exist_ok=True)
    geholt: list[str] = []
    verworfen: list[str] = []          # acknowledged too, so they do not come back
    try:
        tf = tarfile.open(fileobj=io.BytesIO(daten), mode="r:")
    except tarfile.TarError as e:
        raise AbholFehler(f"kein gueltiges tar vom Pi ({e})") from None
    with tf:
        for m in tf.getmembers():
            # only plain files with a plain name: never a path, link or device
            if not m.isfile() or not NAME_RE.match(m.name) or m.size > MAX_FILE:
                protokoll(args, f"verworfen (kein normales Bulletin): {m.name!r}")
                if NAME_RE.match(m.name):
                    verworfen.append(m.name)
                continue
            fh = tf.extractfile(m)
            if fh is None:
                continue
            tmp = eingang / (m.name[:-4] + ".abholung.tmp")
            tmp.write_bytes(fh.read())
            os.replace(tmp, eingang / m.name)
            geholt.append(m.name)
    erledigt = geholt + verworfen
    for i in range(0, len(erledigt), 50):                # keep the command line short
        ssh(args, ["ack", *erledigt[i:i + 50]])
    return geholt


def protokoll(args, text: str) -> None:
    zeile = f"{datetime.now():%Y-%m-%d %H:%M:%S} pi_abholung: {text}"
    if args.log:
        try:
            Path(args.log).parent.mkdir(parents=True, exist_ok=True)
            with open(args.log, "a", encoding="utf-8") as fh:
                fh.write(zeile + "\n")
        except OSError:
            pass
    if sys.stdout is not None:                           # pyw has no console
        print(zeile)


def zustand(neu: str) -> str:
    """Remember ok/fehler between runs: report an outage once, not every 5 minutes."""
    try:
        alt = STATE.read_text(encoding="ascii").strip()
    except OSError:
        alt = ""
    if alt != neu:
        try:
            STATE.parent.mkdir(parents=True, exist_ok=True)
            STATE.write_text(neu + "\n", encoding="ascii")
        except OSError:
            pass
    return alt


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Bulletins vom Feeder-Pi in den TinyBox-Eingang holen")
    ap.add_argument("--host", required=True, help="IP-Adresse oder Name des Feeder-Pi")
    ap.add_argument("--user", default="abholer", help="SSH-Benutzer auf dem Pi (Standard abholer)")
    ap.add_argument("--port", type=int, default=22)
    ap.add_argument("--key", type=Path, default=KEY, help=f"privater Schluessel (Standard {KEY})")
    ap.add_argument("--eingang", type=Path, default=None,
                    help="Zielordner (Standard: [inbox] dir aus tinybox.conf, sonst eingang)")
    ap.add_argument("--log", metavar="DATEI", help="Meldungen zusaetzlich in diese Datei")
    ap.add_argument("--test", action="store_true",
                    help="nur Verbindung pruefen und wartende Dateien zeigen, nichts abholen")
    args = ap.parse_args(argv)
    args.eingang = args.eingang or eingang_ordner()

    try:
        if not args.key.is_file():
            raise AbholFehler(f"Schluessel {args.key} fehlt - pi_abholung_einrichten.bat "
                              "oder pi_sd_vorbereiten.bat legt ihn an")
        if args.test:
            namen = ssh(args, ["list"]).decode("ascii", "replace").split()
            print(f"Verbindung zu {args.user}@{args.host} in Ordnung.")
            print(f"Eingang der TinyBox: {args.eingang}")
            print(f"Wartend am Pi: {len(namen)} Datei(en)")
            for n in namen:
                print("  " + n)
            return 0
        geholt = abholen(args)
    except AbholFehler as e:
        if args.test:
            print(f"FEHLER {e}")
            return 1
        if zustand("fehler") != "fehler":
            protokoll(args, f"FEHLER {e} (weitere Fehlversuche werden nicht gemeldet)")
        return 1
    if zustand("ok") == "fehler":
        protokoll(args, f"Verbindung zu {args.host} wieder in Ordnung")
    if geholt:
        protokoll(args, f"{len(geholt)} abgeholt nach {args.eingang}: {', '.join(geholt)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
