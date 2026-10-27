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

Late fetch (PC was off, network down): the jobs on the Pi write one file per
topic and overwrite it on the next run, so nothing piles up. But TinyBox counts
"Valid:" from the moment it reads the file. So the age of each file (its time
stamp on the Pi) is taken off "Valid:" here; a file whose validity is already
over is not delivered at all, only acknowledged (it is gone from the Pi then).
An outage is logged once; if it lasts longer than --warnen-nach, a WARNUNG
line follows once, and the run after it reports how long it took.

The inbox folder is [inbox] dir from tinybox.conf next to this script
(default: eingang). Only the Python standard library and Windows' own OpenSSH
client (ssh.exe, part of Windows 10/11) are needed.
"""

from __future__ import annotations

import argparse
import configparser
import io
import json
import math
import os
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEY = Path.home() / ".ssh" / "tinybox_feederpi"
STATE = HERE / "data" / "pi_abholung.state"
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}\.txt$")
MAX_FILE = 512 * 1024                 # a bulletin is a few KB; anything bigger is wrong
MAX_TOTAL = 32 * 1024 * 1024
VALID_RE = re.compile(rb"^(Valid:[ \t]*)(\d+)[ \t]*([mhdMHD])[ \t]*$", re.MULTILINE)
UNIT_MIN = {"m": 1, "h": 60, "d": 1440}
MIN_AGE_ADJUST = 120                  # younger files keep their Valid: as written
WARN_MIN = 60                         # default for --warnen-nach
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


def gueltigkeit_anpassen(daten: bytes, alter_sek: float) -> bytes | None:
    """Take the age of the file off its "Valid:" header.

    Returns the (possibly changed) content, or None if the validity is already
    over. Files without "Valid:" (or still younger than 2 minutes) are returned
    unchanged. Only the header part (up to the first blank line) is touched."""
    kopf, sep, rest = daten.replace(b"\r\n", b"\n").partition(b"\n\n")
    if not sep:
        return daten                                     # TinyBox rejects it anyway
    m = VALID_RE.search(kopf)
    if not m:
        return daten
    gueltig = int(m.group(2)) * UNIT_MIN[m.group(3).decode().lower()]
    alter_min = max(alter_sek, 0) / 60                   # Pi clock ahead: age 0
    if alter_min >= gueltig:
        return None
    if alter_sek < MIN_AGE_ADJUST:
        return daten
    rest_min = max(math.floor(gueltig - alter_min), 1)
    kopf = kopf[:m.start()] + m.group(1) + b"%dm" % rest_min + kopf[m.end():]
    return kopf + sep + rest


def abholen(args, jetzt: float | None = None) -> list[str]:
    """One run: fetch, write, acknowledge. Returns the fetched file names."""
    jetzt = time.time() if jetzt is None else jetzt
    daten = ssh(args, ["bundle"], timeout=120)
    if not daten:
        return []
    if len(daten) > MAX_TOTAL:
        raise AbholFehler(f"Paket zu gross ({len(daten)} Bytes)")
    eingang = args.eingang
    eingang.mkdir(parents=True, exist_ok=True)
    geholt: list[str] = []
    verworfen: list[str] = []          # acknowledged too, so they do not come back
    abgelaufen: list[str] = []         # validity over before it got here
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
            inhalt = gueltigkeit_anpassen(fh.read(), jetzt - m.mtime)
            if inhalt is None:
                abgelaufen.append(m.name)
                continue
            tmp = eingang / (m.name[:-4] + ".abholung.tmp")
            tmp.write_bytes(inhalt)
            os.replace(tmp, eingang / m.name)
            geholt.append(m.name)
    if abgelaufen:
        protokoll(args, f"{len(abgelaufen)} nicht zugestellt (Gueltigkeit schon vorbei): "
                        + ", ".join(abgelaufen))
    erledigt = geholt + verworfen + abgelaufen
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


def zustand_lesen() -> dict:
    """State between runs: status ok/fehler, time of the last good run, warned yet."""
    try:
        text = STATE.read_text(encoding="ascii").strip()
    except OSError:
        return {}
    try:
        z = json.loads(text)
        return z if isinstance(z, dict) else {}
    except ValueError:
        return {"status": text}                          # old format: just ok/fehler


def zustand_schreiben(z: dict) -> None:
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(z) + "\n", encoding="ascii")
    except OSError:
        pass


def dauer(sek: float) -> str:
    m = int(sek // 60)
    return f"{m} min" if m < 120 else f"{m // 60} h {m % 60:02d} min"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Bulletins vom Feeder-Pi in den TinyBox-Eingang holen")
    ap.add_argument("--host", required=True, help="IP-Adresse oder Name des Feeder-Pi")
    ap.add_argument("--user", default="abholer", help="SSH-Benutzer auf dem Pi (Standard abholer)")
    ap.add_argument("--port", type=int, default=22)
    ap.add_argument("--key", type=Path, default=KEY, help=f"privater Schluessel (Standard {KEY})")
    ap.add_argument("--eingang", type=Path, default=None,
                    help="Zielordner (Standard: [inbox] dir aus tinybox.conf, sonst eingang)")
    ap.add_argument("--log", metavar="DATEI", help="Meldungen zusaetzlich in diese Datei")
    ap.add_argument("--warnen-nach", type=int, default=WARN_MIN, metavar="MIN",
                    help=f"WARNUNG ins Protokoll, wenn so lange nichts abgeholt werden konnte "
                         f"(Standard {WARN_MIN})")
    ap.add_argument("--test", action="store_true",
                    help="nur Verbindung pruefen und wartende Dateien zeigen, nichts abholen")
    args = ap.parse_args(argv)
    args.eingang = args.eingang or eingang_ordner()

    z = zustand_lesen()
    jetzt = time.time()
    try:
        if not args.key.is_file():
            raise AbholFehler(f"Schluessel {args.key} fehlt - pi_abholung_einrichten.bat "
                              "oder pi_sd_vorbereiten.bat legt ihn an")
        if args.test:
            namen = ssh(args, ["list"]).decode("ascii", "replace").split()
            print(f"Verbindung zu {args.user}@{args.host} in Ordnung.")
            print(f"Eingang der TinyBox: {args.eingang}")
            if z.get("letzte_ok"):
                print(f"Letzte erfolgreiche Abholung: "
                      f"{datetime.fromtimestamp(z['letzte_ok']):%Y-%m-%d %H:%M}")
            print(f"Wartend am Pi: {len(namen)} Datei(en)")
            for n in namen:
                print("  " + n)
            return 0
        geholt = abholen(args, jetzt)
    except AbholFehler as e:
        if args.test:
            print(f"FEHLER {e}")
            return 1
        if z.get("status") != "fehler":
            protokoll(args, f"FEHLER {e} (weitere Fehlversuche werden nicht gemeldet)")
            z["status"], z["seit"], z["gewarnt"] = "fehler", jetzt, False
        seit = z.get("letzte_ok") or z.get("seit") or jetzt
        if not z.get("gewarnt") and jetzt - seit >= args.warnen_nach * 60:
            protokoll(args, f"WARNUNG seit {dauer(jetzt - seit)} nichts vom Pi {args.host} "
                            f"abgeholt ({e}). Wetter/DX in der TinyBox laufen ab; ein Neustart "
                            "des Pi loescht, was dort wartet.")
            z["gewarnt"] = True
        zustand_schreiben(z)
        return 1
    if z.get("status") == "fehler":
        weg = jetzt - (z.get("letzte_ok") or z.get("seit") or jetzt)
        protokoll(args, f"Verbindung zu {args.host} wieder in Ordnung "
                        f"(letzte Abholung vor {dauer(weg)})")
    zustand_schreiben({"status": "ok", "letzte_ok": jetzt})
    if geholt:
        protokoll(args, f"{len(geholt)} abgeholt nach {args.eingang}: {', '.join(geholt)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
