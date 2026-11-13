"""Configuration dialog for an installation from the release package.

    py -3 release\\konfig.py            (install.ps1 calls it, the start menu offers it)

Asks a few questions and writes from the *.conf.example templates:
    tbclient.conf, tinybox.conf, brocast/brocastd.conf (listener),
    direwolf/direwolf.conf and tbstart.conf (settings of the start menu).
Only the asked keys are changed, all comments of the templates stay.
An existing file is only replaced after asking. Everything else (chat boards,
rubrics, beacon ...) is set later by hand in the .conf files - see MANUAL.md.
"""

from __future__ import annotations

import configparser
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DW_DIR = ROOT / "direwolf"
START_CONF = ROOT / "tbstart.conf"

CALL_RE = re.compile(r"^[A-Z0-9]{1,2}[0-9][A-Z0-9]{1,4}$")
LOC_RE = re.compile(r"^[A-R]{2}[0-9]{2}([A-X]{2})?$", re.I)


# --- small dialog helpers ----------------------------------------------------

def ask(text: str, default: str = "", check=None, hint: str = "") -> str:
    while True:
        shown = f" [{default}]" if default else ""
        try:
            ans = input(f"  {text}{shown}: ").strip()
        except EOFError:
            ans = ""
        if not ans:
            ans = default
        if check is None or check(ans):
            return ans
        print(f"    -> ungueltig. {hint}")


def yes(text: str, default: bool = True) -> bool:
    ans = ask(f"{text} (j/n)", "j" if default else "n",
              lambda a: a.lower() in ("j", "ja", "y", "yes", "n", "nein", "no"), "Bitte j oder n.")
    return ans.lower() in ("j", "ja", "y", "yes")


def is_call(c: str) -> bool:
    return bool(CALL_RE.match(c.upper()))


def is_call_ssid(c: str) -> bool:
    base, _, ssid = c.upper().partition("-")
    return is_call(base) and (not ssid or (ssid.isdigit() and 0 <= int(ssid) <= 15))


def with_ssid(call: str, ssid: str) -> str:
    return call if ssid in ("", "0") else f"{call}-{ssid}"


# --- editing the templates --------------------------------------------------

def set_keys(text: str, section: str, values: dict[str, str]) -> str:
    """Set key = value inside [section]. A commented-out key ('# key = ...') is
    used and switched on; a missing key is added after the section header.
    An inline comment behind the value stays where it was."""
    lines = text.split("\n")
    head = re.compile(r"^\s*\[([^\]]+)\]")
    start = next((i for i, l in enumerate(lines)
                  if (m := head.match(l)) and m.group(1).strip().lower() == section.lower()), None)
    if start is None:
        lines += ["", f"[{section}]"]
        start = len(lines) - 1
    end = next((i for i in range(start + 1, len(lines)) if head.match(lines[i])), len(lines))
    for key, value in values.items():
        pat = re.compile(rf"^(\s*)(?:[#;]\s*)?{re.escape(key)}(\s*= ?)(.*)$", re.I)
        hit = None
        for i in range(start + 1, end):
            if pat.match(lines[i]) and not lines[i].lstrip().startswith(("#", ";")):
                hit = i
                break
        if hit is None:                    # only then a commented-out line
            hit = next((i for i in range(start + 1, end) if pat.match(lines[i])), None)
        if hit is None:
            lines.insert(start + 1, f"{key} = {value}")
            end += 1
            continue
        line = lines[hit].lstrip()
        if line.startswith(("#", ";")):          # switch a commented-out key on
            line = line[1:].lstrip()
        m = pat.match(line)
        rest = m.group(3)
        new = f"{key}{m.group(2)}{value}"
        cm = re.search(r"(?:^|\s+)[#;]", rest)
        if cm:
            col = len(key) + len(m.group(2)) + cm.end() - 1      # column of the '#'
            new = (new.ljust(col) if len(new) < col else new + " ") + rest[cm.end() - 1:]
        lines[hit] = new
    return "\n".join(lines)


def write_conf(target: Path, template: Path, sections: dict[str, dict[str, str]]) -> bool:
    if target.exists() and not yes(f"{target.relative_to(ROOT)} gibt es schon - neu erstellen?", False):
        print(f"    {target.relative_to(ROOT)} bleibt unveraendert.")
        return False
    text = template.read_text(encoding="utf-8")
    for sec, vals in sections.items():
        text = set_keys(text, sec, vals)
    target.write_text(text, encoding="utf-8")
    print(f"    geschrieben: {target.relative_to(ROOT)}")
    return True


def direwolf_conf(call: str, adevice: str, baud: str, ptt: str, note: str = "") -> str:
    lines = [
        "# direwolf.conf - erstellt von release/konfig.py (TinyBox-Release).",
        "# Vollstaendige Beschreibung: Direwolf User Guide. Nach Aenderungen Direwolf neu starten.",
        "",
        *([f"# {note}", "# (Windows-Nummern - nach Umstecken von USB-Geraeten pruefen,",
           "#  Direwolf zeigt beim Start die Liste der Geraete)"] if note else []),
        f"ADEVICE {adevice}",
        "ACHANNELS 1",
        "CHANNEL 0",
        f"MYCALL {call}",
        f"MODEM {baud}",
    ]
    lines.append(f"PTT {ptt}" if ptt else "# PTT: keine Angabe = VOX bzw. Funkgeraet schaltet selbst")
    if baud == "9600":
        lines.append("TXDELAY 20")
    lines += ["", "AGWPORT 8000", "KISSPORT 8001", ""]
    return "\n".join(lines)


# --- sound cards and COM ports (Windows) ---------------------------------------

def sound_devices() -> tuple[list[str], list[str]]:
    """(inputs, outputs) in the order of Windows (winmm) - the numbers Direwolf
    takes in ADEVICE. Empty lists outside Windows or on any error."""
    if sys.platform != "win32":
        return [], []
    try:
        import ctypes
        from ctypes import wintypes

        class CAPS(ctypes.Structure):            # WAVEINCAPSW / WAVEOUTCAPSW (+ dwSupport)
            _fields_ = [("wMid", wintypes.WORD), ("wPid", wintypes.WORD),
                        ("vDriverVersion", wintypes.UINT), ("szPname", wintypes.WCHAR * 32),
                        ("dwFormats", wintypes.DWORD), ("wChannels", wintypes.WORD),
                        ("wReserved1", wintypes.WORD), ("dwSupport", wintypes.DWORD)]

        winmm = ctypes.windll.winmm
        out: list[list[str]] = []
        for num, caps in ((winmm.waveInGetNumDevs, winmm.waveInGetDevCapsW),
                          (winmm.waveOutGetNumDevs, winmm.waveOutGetDevCapsW)):
            names = []
            for i in range(num()):
                c = CAPS()
                names.append(c.szPname if caps(i, ctypes.byref(c), ctypes.sizeof(c)) == 0
                             else f"(Geraet {i})")
            out.append(names)
        return out[0], out[1]
    except Exception:
        return [], []


def com_ports() -> list[tuple[str, str]]:
    """[(COM3, description), ...] - pyserial if there, else the registry."""
    try:
        from serial.tools import list_ports
        ports = [(p.device, p.description or "") for p in list_ports.comports()]
    except Exception:
        ports = []
        if sys.platform == "win32":
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DEVICEMAP\SERIALCOMM") as k:
                    i = 0
                    while True:
                        try:
                            name, value, _ = winreg.EnumValue(k, i)
                        except OSError:
                            break
                        ports.append((str(value), name.rsplit("\\", 1)[-1]))
                        i += 1
            except OSError:
                pass
    return sorted(ports, key=lambda p: (len(p[0]), p[0]))


def _pick(title: str, names: list[str]) -> str:
    print(f"  {title}:")
    for i, n in enumerate(names):
        print(f"    {i:2}  {n}")
    hint = next((i for i, n in enumerate(names)
                 if re.search(r"usb|codec|signalink|digirig", n, re.I)), 0)
    return ask("Nummer", str(hint), lambda a: a.isdigit() and int(a) < len(names),
               f"Eine Zahl von 0 bis {len(names) - 1}.")


def choose_audio() -> tuple[str, str]:
    """(ADEVICE value, comment): 'in out' as numbers, the names for the comment line
    (Direwolf takes comments only on lines of their own)."""
    ins, outs = sound_devices()
    if not ins or not outs:
        print("  Soundkarten konnten nicht gelesen werden.")
        print("  Soundkarte: Nummer (0, 1 ...) oder ein Teil des Namens ohne Leerzeichen, z. B. USB.")
        return ask("Soundkarte", "USB"), ""
    i = _pick("Eingang (Empfang: Funkgeraet -> PC)", ins)
    o = _pick("Ausgang (Senden: PC -> Funkgeraet)", outs)
    return f"{i} {o}", f"Eingang {i}: {ins[int(i)]} / Ausgang {o}: {outs[int(o)]}"


def choose_ptt() -> str:
    """PTT value for direwolf.conf, '' = VOX."""
    ports = com_ports()
    print("  PTT (Sendertastung):")
    for i, (dev, desc) in enumerate(ports, 1):
        print(f"    {i:2}  {dev:7} {desc}")
    if not ports:
        print("        (keine COM-Schnittstelle gefunden)")
    print("     C  CM108/CM119-Soundkarte mit PTT-Ausgang (z. B. Digirig Lite)")
    print("     V  VOX / das Funkgeraet bzw. Interface schaltet selbst")
    print("        oder direkt eingeben, z. B. COM5 RTS")

    def ok(a: str) -> bool:
        a = a.strip().upper()
        return (a in ("C", "V") or (a.isdigit() and 1 <= int(a) <= len(ports))
                or bool(re.fullmatch(r"COM\d+( -?(RTS|DTR))*", a)))

    a = ask("Auswahl", "V", ok, "Nummer, C, V oder z. B. COM5 RTS.").strip().upper()
    if a == "V":
        return ""
    if a == "C":
        return "CM108"
    if a.startswith("COM") and " " in a:
        return a
    dev = ports[int(a) - 1][0] if a.isdigit() else a
    line = ask(f"Leitung an {dev}: RTS oder DTR", "RTS", lambda x: x.upper() in ("RTS", "DTR"),
               "RTS oder DTR.").upper()
    return f"{dev} {line}"


# --- the dialog -------------------------------------------------------------

def main() -> int:
    print()
    print("=" * 66)
    print("  TinyBox - Konfiguration")
    print("  Enter uebernimmt den Vorschlag in [eckigen Klammern].")
    print("=" * 66)
    print()
    print("Station")
    call = ask("Dein Rufzeichen (ohne SSID)", "", is_call, "Zum Beispiel OE3ABC.").upper()
    locator = ask("Locator (leer = keiner)", "", lambda a: not a or LOC_RE.match(a),
                  "Zum Beispiel JN88EP.").upper()
    qth = ask("QTH / Ortsname (leer = keiner)", "", lambda a: "#" not in a and ";" not in a,
              "Ohne # und ;.")

    print()
    print("Was soll auf diesem PC laufen? (Der TBClient ist immer dabei.)")
    use_box = yes("Eine eigene TinyBox (Mailbox) betreiben?", False)
    use_bro = yes("brocast-Listener (Teletext-Seiten ueber Funk empfangen)?", False)

    print()
    print("TBClient")
    my = ask("Rufzeichen des Clients mit SSID", call, is_call_ssid, "Zum Beispiel OE3ABC-12.").upper()

    box_call = ""
    if use_box:
        print()
        print("TinyBox")
        box_ssid = ask("SSID der Mailbox (1-15)", "1",
                       lambda a: a.isdigit() and 1 <= int(a) <= 15, "Eine Zahl von 1 bis 15.")
        box_call = with_ssid(call, box_ssid)
        if box_call == my:
            print(f"    Hinweis: Client und Mailbox duerfen nicht dasselbe Rufzeichen haben ({my}).")
            my = ask("Anderes Rufzeichen fuer den Client", f"{call}-12", is_call_ssid).upper()
        freq = ask("Frequenz des Funkports in MHz (leer = keine)", "",
                   lambda a: not a or re.fullmatch(r"\d+(\.\d+)?", a), "Zum Beispiel 144.800.")
        target_box = box_call
    else:
        freq = ""
        target_box = ask("Rufzeichen deiner Heimat-TinyBox", "", is_call_ssid,
                         "Zum Beispiel OE3XYZ-1.").upper()

    print()
    print("Direwolf (Modem fuer die Soundkarte)")
    print(f"  Mitgeliefert: {DW_DIR / 'direwolf-tinybox.exe'}")
    start_dw = yes("Direwolf beim Start automatisch mitstarten?", True)
    dw_dir = DW_DIR
    dw_exe = "direwolf-tinybox.exe"
    if start_dw:
        if not yes("Mitgelieferten Direwolf verwenden?", True):
            dw_dir = Path(ask("Ordner deines Direwolf", r"C:\direwolf",
                              lambda a: Path(a).is_dir(), "Ordner gibt es nicht."))
            dw_exe = ask("Programmdatei darin", "direwolf.exe",
                         lambda a: (dw_dir / a).is_file(), "Datei gibt es dort nicht.")
        dwc = dw_dir / "direwolf.conf"
        if not dwc.exists() or yes(f"{dwc} gibt es schon - neu erstellen?", False):
            adev, adev_note = choose_audio()
            baud = ask("Baudrate (1200 oder 9600)", "1200", lambda a: a in ("1200", "9600"),
                       "1200 oder 9600.")
            ptt = choose_ptt()
            dw_dir.mkdir(parents=True, exist_ok=True)
            dwc.write_text(direwolf_conf(call, adev, baud, ptt, adev_note), encoding="utf-8")
            print(f"    geschrieben: {dwc}")
    else:
        own = ask("Ordner der direwolf.conf deines eigenen Direwolf (leer = keiner)", "",
                  lambda a: not a or (Path(a) / "direwolf.conf").is_file(),
                  "Dort liegt keine direwolf.conf.")
        dw_dir = Path(own) if own else None
    # CR70: the programs read AGWPORT, MODEM, PACLEN ... from direwolf.conf
    agw = {"channel": "0"}
    if dw_dir and (dw_dir / "direwolf.conf").is_file():
        agw["direwolf_conf"] = str(dw_dir)

    print()
    print("Konfigurationsdateien")
    write_conf(ROOT / "tbclient.conf", ROOT / "tbclient.conf.example", {
        "station": {"mycall": my, "locator": locator},
        "tinybox": {"call": target_box},
        "radio": {"interface": "agw"},
        "agw": agw,
    })
    if use_box:
        write_conf(ROOT / "tinybox.conf", ROOT / "tinybox.conf.example", {
            "station": {"mailbox_call": box_call, "sysop_call": call, "qth": qth,
                        "freq": freq, "locator": locator},
            "radio": {"interface": "agw"},
            "agw": agw,
            # a listener takes no pages from the TinyBox (only a brocast station does)
            "brocast": {"publish": "no"},
        })
    if use_bro:
        write_conf(ROOT / "brocast" / "brocastd.conf", ROOT / "brocast" / "brocastd.conf.example", {
            "brocastd": {"mode": "listener", "callsign": ""},
            "radio": {"interface": "agw"},
            "agw": agw,
        })

    cp = configparser.ConfigParser()
    cp["start"] = {"direwolf": "yes" if start_dw else "no",
                   "direwolf_dir": str(dw_dir or DW_DIR), "direwolf_exe": dw_exe,
                   "tinybox": "yes" if use_box else "no",
                   "brocast": "yes" if use_bro else "no"}
    with START_CONF.open("w", encoding="utf-8") as f:
        f.write("# Einstellungen des Startmenues (TinyBox-Start.bat), erstellt von release/konfig.py\n")
        cp.write(f)
    print(f"    geschrieben: {START_CONF.relative_to(ROOT)}")
    print()
    print("Fertig. Weitere Einstellungen (Chat-Boards, Bake, Rubriken ...) direkt in den")
    print(".conf-Dateien - Beschreibung in MANUAL.md. Erneut aufrufen: Startmenue, Punkt K.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nAbgebrochen - nichts weiter geaendert.")
        sys.exit(1)
