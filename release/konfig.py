"""Configuration dialog for an installation from the release package.

    py -3 release\\konfig.py            (install.ps1 calls it, the start menu offers it)

Asks a few questions and writes from the *.conf.example templates:
    tbclient.conf, tinybox.conf, brocast/brocastd.conf (listener),
    direwolf/direwolf.conf or kisshub.conf, and tbstart.conf (settings of the start menu).
The radio is either Direwolf (sound card modem, AGW) or a KISS TNC through kisshub:
for KISS the dialog lists the TNC sections of kisshub.conf.example, the user picks his.
Only the asked keys are changed, all comments of the templates stay.
Values already there (tbclient.conf, tinybox.conf, kisshub.conf, tbstart.conf,
direwolf.conf) are offered as the defaults. An existing file gets the answers
written into it - everything else in it stays (chat boards, rubrics, beacon ...);
building it anew from the template only on request. See MANUAL.md.
"""

from __future__ import annotations

import configparser
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DW_DIR = ROOT / "direwolf"
START_CONF = ROOT / "tbstart.conf"
KISS_EXAMPLE = ROOT / "kisshub.conf.example"
KISS_CONF = ROOT / "kisshub.conf"

CALL_RE = re.compile(r"^[A-Z0-9]{1,2}[0-9][A-Z0-9]{1,4}$")
LOC_RE = re.compile(r"^[A-R]{2}[0-9]{2}([A-X]{2})?$", re.I)


def _isnum(s: str) -> bool:
    """ASCII digits only - isdigit() also accepts '²', int() then fails (CR88)."""
    return s.isascii() and s.isdigit()


# --- small dialog helpers ----------------------------------------------------

def ask(text: str, default: str = "", check=None, hint: str = "", clear: bool = False) -> str:
    """clear=True: an optional value - '-' empties a default that is there."""
    while True:
        shown = f" [{default}]" if default else ""
        if clear and default:
            shown += " (- = leeren)"
        try:
            ans = input(f"  {text}{shown}: ").strip()
        except EOFError:
            ans = ""
        if not ans:
            ans = default
        if clear and ans == "-":
            return ""
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
    return is_call(base) and (not ssid or (_isnum(ssid) and 0 <= int(ssid) <= 15))


def with_ssid(call: str, ssid: str) -> str:
    return call if ssid in ("", "0") else f"{call}-{ssid}"


# --- reading what is there ---------------------------------------------------

def read_conf(path: Path) -> configparser.ConfigParser:
    """The file as ConfigParser - empty if it is missing or cannot be read."""
    cp = configparser.ConfigParser(inline_comment_prefixes=("#", ";"), interpolation=None,
                                   strict=False)
    try:
        if path.is_file():
            cp.read(path, encoding="utf-8")
    except (configparser.Error, OSError, UnicodeDecodeError):
        return configparser.ConfigParser(interpolation=None)
    return cp


def cval(cp: configparser.ConfigParser, section: str, key: str, default: str = "") -> str:
    try:
        return cp.get(section, key, fallback=default).strip() or default
    except configparser.Error:
        return default


def read_direwolf(dw_dir: Path | None) -> dict[str, str]:
    """ADEVICE, MODEM, PTT, MYCALL of an existing direwolf.conf ({} if none)."""
    out: dict[str, str] = {}
    if not dw_dir:
        return out
    try:
        text = (dw_dir / "direwolf.conf").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for line in text.splitlines():
        m = re.match(r"^\s*(ADEVICE|MODEM|PTT|MYCALL)\s+(.+?)\s*$", line, re.I)
        if m and m.group(1).upper() not in out:
            out[m.group(1).upper()] = m.group(2)
    return out


def base_call(c: str) -> str:
    return c.upper().partition("-")[0]


def ssid_of(c: str) -> str:
    return c.upper().partition("-")[2]


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


def write_conf(target: Path, template: Path, sections: dict[str, dict[str, str]],
               new_only: dict[str, dict[str, str]] | None = None) -> bool:
    """Write the answers. An existing file gets them written into it (all other
    settings stay); new from the template only if wanted. new_only: keys set only
    in a file new from the template (e.g. brocastd mode = listener - an existing
    station must stay a station)."""
    name = target.relative_to(ROOT)
    fresh = not target.exists()
    if not fresh:
        old = target.read_text(encoding="utf-8")
        text = old
        for sec, vals in sections.items():
            text = set_keys(text, sec, vals)
        if text == old:
            print(f"    {name}: schon so eingestellt - unveraendert.")
            return False
        print(f"  {name} gibt es schon:")
        print("     e  Antworten eintragen, alle anderen Einstellungen bleiben")
        print("     n  neu aus der Vorlage (eigene Einstellungen gehen verloren)")
        print("     b  behalten wie sie ist")
        a = ask("Auswahl", "e", lambda a: a.lower() in ("e", "n", "b"), "e, n oder b.").lower()
        if a == "b":
            print(f"    {name} bleibt unveraendert.")
            return False
        fresh = a == "n"
    if fresh:
        text = template.read_text(encoding="utf-8")
        for sec, vals in {**sections, **(new_only or {})}.items():
            text = set_keys(text, sec, vals)
    target.write_text(text, encoding="utf-8")
    print(f"    geschrieben: {name}")
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


def _pick(title: str, names: list[str], current: str = "") -> str:
    print(f"  {title}:")
    for i, n in enumerate(names):
        print(f"    {i:2}  {n}")
    if _isnum(current) and int(current) < len(names):
        hint = int(current)                 # what direwolf.conf has today
    else:
        hint = next((i for i, n in enumerate(names)
                     if re.search(r"usb|codec|signalink|digirig", n, re.I)), 0)
    return ask("Nummer", str(hint), lambda a: _isnum(a) and int(a) < len(names),
               f"Eine Zahl von 0 bis {len(names) - 1}.")


def choose_audio(current: str = "") -> tuple[str, str]:
    """(ADEVICE value, comment): 'in out' as numbers, the names for the comment line
    (Direwolf takes comments only on lines of their own). current: ADEVICE today."""
    ins, outs = sound_devices()
    if not ins or not outs:
        print("  Soundkarten konnten nicht gelesen werden.")
        print("  Soundkarte: Nummer (0, 1 ...) oder ein Teil des Namens ohne Leerzeichen, z. B. USB.")
        return ask("Soundkarte", current or "USB"), ""
    parts = current.split()
    cur_in = parts[0] if parts else ""
    cur_out = parts[1] if len(parts) > 1 else cur_in
    i = _pick("Eingang (Empfang: Funkgeraet -> PC)", ins, cur_in)
    o = _pick("Ausgang (Senden: PC -> Funkgeraet)", outs, cur_out)
    return f"{i} {o}", f"Eingang {i}: {ins[int(i)]} / Ausgang {o}: {outs[int(o)]}"


def ptt_choice(ptt: str) -> str:
    """The answer of choose_ptt that gives this PTT value (V, C or 'COM5 RTS')."""
    p = ptt.strip().upper()
    if not p:
        return "V"
    if p.startswith("CM108"):
        return "C"
    return p if re.fullmatch(r"COM\d+( -?(RTS|DTR))*", p) else "V"


def choose_ptt(current: str | None = None) -> str:
    """PTT value for direwolf.conf, '' = VOX. current: PTT today (None = no direwolf.conf)."""
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
        return (a in ("C", "V") or (_isnum(a) and 1 <= int(a) <= len(ports))
                or bool(re.fullmatch(r"COM\d+( -?(RTS|DTR))*", a)))

    a = ask("Auswahl", ptt_choice(current or ""), ok,
            "Nummer, C, V oder z. B. COM5 RTS.").strip().upper()
    if a == "V":
        return ""
    if a == "C":
        return "CM108"
    if a.startswith("COM") and " " in a:
        return a
    dev = ports[int(a) - 1][0] if _isnum(a) else a
    line = ask(f"Leitung an {dev}: RTS oder DTR", "RTS", lambda x: x.upper() in ("RTS", "DTR"),
               "RTS oder DTR.").upper()
    return f"{dev} {line}"


# --- KISS: TNC profiles of kisshub ---------------------------------------------

def kiss_profiles() -> list[tuple[str, dict[str, str]]]:
    """(name, keys) of every TNC section in kisshub.conf.example, 'base' resolved -
    the same reading as kisshub -l. Direwolf sections are left out: Direwolf is the
    other choice of this dialog (AGW). modem73 only if its exe is there (it is not in
    the repo, so not in the release package)."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from kisshub import profiles as kp
    cp = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
    cp.read(KISS_EXAMPLE, encoding="utf-8")
    out = []
    for name in kp.names(cp):
        keys = kp.merged(cp, name)
        typ = keys.get("type", "").strip()
        if typ == "direwolf":
            continue
        if typ == "modem73" and not (ROOT / keys.get("exe", "modem73.exe").strip()).is_file():
            continue
        out.append((name, {k: v.strip() for k, v in keys.items()}))
    return out


def kiss_port() -> str:
    """kisshub's KISS-TCP port ([server] port) - what TinyBox, client and brocast use."""
    cp = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
    cp.read(KISS_EXAMPLE, encoding="utf-8")
    return cp.get("server", "port", fallback="8101").strip() or "8101"


def choose_com(default: str) -> str:
    """A COM port from the list, a number of the list or typed in (COM7, /dev/ttyUSB0)."""
    ports = com_ports()
    print("  Serielle Schnittstelle (PC <-> TNC):")
    for i, (dev, desc) in enumerate(ports, 1):
        print(f"    {i:2}  {dev:7} {desc}")
    if not ports:
        print("        (keine COM-Schnittstelle gefunden - direkt eingeben, z. B. COM7)")
    if ports and default not in [p[0] for p in ports]:
        default = ports[0][0]

    def ok(a: str) -> bool:
        a = a.strip()
        return ((_isnum(a) and 1 <= int(a) <= len(ports)) or bool(re.fullmatch(r"(?i)COM\d+", a))
                or a.startswith("/dev/"))

    a = ask("Schnittstelle", default, ok, "Nummer aus der Liste oder z. B. COM7.").strip()
    return ports[int(a) - 1][0] if _isnum(a) else (a.upper() if a.upper().startswith("COM") else a)


def choose_kiss(call: str, current: configparser.ConfigParser | None = None
                ) -> tuple[str, dict[str, str]] | None:
    """(profile name, keys to set in its section) - None if kisshub.conf.example cannot be read.
    current: kisshub.conf of today - its profile and values are the defaults."""
    try:
        profs = kiss_profiles()
    except Exception as exc:              # noqa: BLE001 - the dialog must go on
        print(f"  kisshub.conf.example konnte nicht gelesen werden: {exc}")
        return None
    if not profs:
        print("  In kisshub.conf.example ist kein TNC-Profil.")
        return None
    print("  TNC-Profile (kisshub.conf.example):")
    for i, (name, k) in enumerate(profs, 1):
        print(f"    {i:2}  {name:14} {k.get('notes', '')}")
    cur = current if current is not None else configparser.ConfigParser()
    cur_name = cval(cur, "kisshub", "profile")
    nr = next((i for i, (n, _) in enumerate(profs, 1) if n == cur_name), 1)
    a = ask("Nummer deines TNC", str(nr), lambda a: _isnum(a) and 1 <= int(a) <= len(profs),
            f"Eine Zahl von 1 bis {len(profs)}.")
    name, k = profs[int(a) - 1]
    if cur.has_section(name):                 # the values of today's kisshub.conf
        k = {**k, **{key: v.strip() for key, v in cur.items(name) if v.strip()}}
    print(f"    gewaehlt: {name} ({k.get('display', name)})")
    if k.get("hint"):
        print(f"    Hinweis: {k['hint']}")
    values: dict[str, str] = {}
    typ = k.get("type", "tnc")
    if k.get("transport", "serial") == "serial":
        values["device"] = choose_com(k.get("device", ""))
        values["serial_baud"] = ask("Baudrate PC <-> TNC", k.get("serial_baud", "9600"), _isnum,
                                    "Eine Zahl, z. B. 9600.")
    elif typ == "vara":
        values["host"] = ask("Rechner, auf dem VARA laeuft", k.get("host", "127.0.0.1"),
                             lambda a: bool(a) and " " not in a, "IP-Adresse oder Name.")
    if typ == "modem73":
        values["callsign"] = call
        print("  PTT fuer modem73:")
        values["com_port"] = choose_com(k.get("com_port", ""))
    return name, values


# --- the dialog -------------------------------------------------------------

def main() -> int:
    # what is there today - the defaults of every question
    cli = read_conf(ROOT / "tbclient.conf")
    box = read_conf(ROOT / "tinybox.conf")
    start = read_conf(START_CONF)
    khub = read_conf(KISS_CONF)
    bro_conf = ROOT / "brocast" / "brocastd.conf"
    found = [p.relative_to(ROOT).as_posix() for p in
             (ROOT / "tbclient.conf", ROOT / "tinybox.conf", bro_conf, KISS_CONF, START_CONF)
             if p.is_file()]

    print()
    print("=" * 66)
    print("  TinyBox - Konfiguration")
    print("  Enter uebernimmt den Vorschlag in [eckigen Klammern].")
    if found:
        print("  Vorschlaege = die Werte von heute aus: " + ", ".join(found))
    print("=" * 66)
    print()
    print("Station")
    old_my = cval(cli, "station", "mycall").upper()
    old_call = base_call(cval(box, "station", "sysop_call") or old_my)
    call = ask("Dein Rufzeichen (ohne SSID)", old_call if is_call(old_call) else "", is_call,
               "Zum Beispiel OE3ABC.").upper()
    locator = ask("Locator (leer = keiner)",
                  cval(cli, "station", "locator") or cval(box, "station", "locator"),
                  lambda a: not a or LOC_RE.match(a), "Zum Beispiel JN88EP.", clear=True).upper()
    qth = ask("QTH / Ortsname (leer = keiner)", cval(box, "station", "qth"),
              lambda a: "#" not in a and ";" not in a, "Ohne # und ;.", clear=True)

    print()
    print("Was soll auf diesem PC laufen? (Der TBClient ist immer dabei.)")

    def was_on(key: str, conf: Path) -> bool:
        if start.has_option("start", key):
            return cval(start, "start", key).lower() in ("yes", "ja", "j", "true", "1", "on")
        return conf.is_file()

    use_box = yes("Eine eigene TinyBox (Mailbox) betreiben?", was_on("tinybox", ROOT / "tinybox.conf"))
    use_bro = yes("brocast-Listener (Teletext-Seiten ueber Funk empfangen)?",
                  was_on("brocast", bro_conf))

    print()
    print("TBClient")
    my = ask("Rufzeichen des Clients mit SSID",
             old_my if old_my and base_call(old_my) == call and is_call_ssid(old_my) else call,
             is_call_ssid, "Zum Beispiel OE3ABC-12.").upper()

    box_call = ""
    old_box = cval(box, "station", "mailbox_call").upper()
    if use_box:
        print()
        print("TinyBox")
        old_ssid = ssid_of(old_box) if base_call(old_box) == call else ""
        box_ssid = ask("SSID der Mailbox (1-15)", old_ssid if _isnum(old_ssid) else "1",
                       lambda a: _isnum(a) and 1 <= int(a) <= 15, "Eine Zahl von 1 bis 15.")
        box_call = with_ssid(call, box_ssid)
        if box_call == my:
            print(f"    Hinweis: Client und Mailbox duerfen nicht dasselbe Rufzeichen haben ({my}).")
            my = ask("Anderes Rufzeichen fuer den Client", f"{call}-12", is_call_ssid).upper()
        freq = ask("Frequenz des Funkports in MHz (leer = keine)", cval(box, "station", "freq"),
                   lambda a: not a or re.fullmatch(r"\d+(\.\d+)?", a), "Zum Beispiel 144.800.",
                   clear=True)
        target_box = box_call
    else:
        freq = ""
        old_target = cval(cli, "tinybox", "call").upper()
        target_box = ask("Rufzeichen deiner Heimat-TinyBox",
                         old_target if is_call_ssid(old_target) else "", is_call_ssid,
                         "Zum Beispiel OE3XYZ-1.").upper()

    print()
    print("Funkanbindung")
    print("   1  Direwolf - Soundkarten-Modem (Interface wie SignaLink, Digirig ...)")
    print("   2  KISS - TNC oder Funkgeraet mit eingebautem TNC, VARA, modem73 (ueber kisshub)")
    iface = cval(cli, "radio", "interface").lower()
    was_kiss = iface == "kiss" if iface else was_on("kisshub", KISS_CONF)
    mode = ask("Auswahl", "2" if was_kiss else "1", lambda a: a in ("1", "2"), "1 oder 2.")
    kiss = None
    if mode == "2":
        print()
        print("KISS-TNC (kisshub)")
        kiss = choose_kiss(call, khub)
        if kiss is None:
            print("    -> weiter mit Direwolf.")
            mode = "1"
    start_dw = False
    dw_dir: Path | None = None
    dw_exe = "direwolf-tinybox.exe"
    agw: dict[str, str] = {}
    if mode == "1":
        print()
        print("Direwolf (Modem fuer die Soundkarte)")
        bundled = (DW_DIR / "direwolf-tinybox.exe").is_file()
        if bundled:
            print(f"  Mitgeliefert: {DW_DIR / 'direwolf-tinybox.exe'}")
        else:   # e.g. a git clone without the release package: no direwolf\ folder
            print(f"  Kein mitgelieferter Direwolf gefunden ({DW_DIR / 'direwolf-tinybox.exe'}"
                  " fehlt).")
        old_dir = Path(cval(start, "start", "direwolf_dir")) if cval(start, "start", "direwolf_dir") \
            else None
        old_exe = cval(start, "start", "direwolf_exe")
        own_old = old_dir is not None and old_dir.resolve() != DW_DIR.resolve()
        start_dw = yes("Direwolf beim Start automatisch mitstarten?",
                       was_on("direwolf", DW_DIR / "direwolf.conf") if start.has_section("start")
                       else True)
        dw_dir = DW_DIR
        dw_exe = "direwolf-tinybox.exe"
        if start_dw:
            if not bundled or not yes("Mitgelieferten Direwolf verwenden?", not own_old):
                dw_dir = Path(ask("Ordner deines Direwolf",
                                  str(old_dir) if own_old else r"C:\direwolf",
                                  lambda a: Path(a).is_dir(), "Ordner gibt es nicht."))
                exe_default = old_exe if own_old and old_exe else "direwolf.exe"
                dw_exe = ask("Programmdatei darin", exe_default,
                             lambda a: (dw_dir / a).is_file(), "Datei gibt es dort nicht.")
            dwc = dw_dir / "direwolf.conf"
            dw_old = read_direwolf(dw_dir)
            if dw_old:
                print(f"  {dwc} heute: ADEVICE {dw_old.get('ADEVICE', '?')}, "
                      f"MODEM {dw_old.get('MODEM', '?')}, PTT {dw_old.get('PTT', 'keine (VOX)')}")
            if not dwc.exists() or yes(f"{dwc} gibt es schon - neu erstellen?", False):
                adev, adev_note = choose_audio(dw_old.get("ADEVICE", ""))
                old_baud = dw_old.get("MODEM", "1200").split()[0]
                baud = ask("Baudrate (1200 oder 9600)",
                           old_baud if old_baud in ("1200", "9600") else "1200",
                           lambda a: a in ("1200", "9600"), "1200 oder 9600.")
                ptt = choose_ptt(dw_old.get("PTT") if dw_old else None)
                dw_dir.mkdir(parents=True, exist_ok=True)
                dwc.write_text(direwolf_conf(call, adev, baud, ptt, adev_note), encoding="utf-8")
                print(f"    geschrieben: {dwc}")
            elif dw_old.get("MYCALL", "").upper() not in ("", call) \
                    and base_call(dw_old["MYCALL"]) != call:
                text = dwc.read_text(encoding="utf-8", errors="replace")
                dwc.write_text(re.sub(r"(?im)^(\s*MYCALL\s+)\S+", rf"\g<1>{call}", text, count=1),
                               encoding="utf-8")
                print(f"    {dwc}: MYCALL {dw_old['MYCALL']} -> {call}")
        else:
            old_own = cval(cli, "agw", "direwolf_conf") or cval(box, "agw", "direwolf_conf")
            if old_own.lower().endswith(".conf"):
                old_own = str(Path(old_own).parent)
            own = ask("Ordner der direwolf.conf deines eigenen Direwolf (leer = keiner)",
                      old_own if old_own and (Path(old_own) / "direwolf.conf").is_file() else "",
                      lambda a: not a or (Path(a) / "direwolf.conf").is_file(),
                      "Dort liegt keine direwolf.conf.", clear=True)
            dw_dir = Path(own) if own else None
        # CR70: the programs read AGWPORT, MODEM, PACLEN ... from direwolf.conf
        if dw_dir and (dw_dir / "direwolf.conf").is_file():
            agw["direwolf_conf"] = str(dw_dir)
    if kiss:
        radio = {"radio": {"interface": "kiss"}, "kiss": {"port": kiss_port()}}
    else:
        radio = {"radio": {"interface": "agw"}, **({"agw": agw} if agw else {})}

    print()
    print("Konfigurationsdateien")
    if kiss:
        name, values = kiss
        write_conf(KISS_CONF, KISS_EXAMPLE, {"kisshub": {"profile": name}, name: values})
    write_conf(ROOT / "tbclient.conf", ROOT / "tbclient.conf.example", {
        "station": {"mycall": my, "locator": locator},
        "tinybox": {"call": target_box},
        **radio,
    })
    if use_box:
        write_conf(ROOT / "tinybox.conf", ROOT / "tinybox.conf.example", {
            "station": {"mailbox_call": box_call, "sysop_call": call, "qth": qth,
                        "freq": freq, "locator": locator},
            **radio,
        }, new_only={
            # a listener takes no pages from the TinyBox (only a brocast station does)
            "brocast": {"publish": "no"},
        })
    if use_bro:
        write_conf(bro_conf, ROOT / "brocast" / "brocastd.conf.example", dict(radio), new_only={
            "brocastd": {"mode": "listener", "callsign": ""},
        })

    values = {"direwolf": "yes" if start_dw else "no",
              "direwolf_dir": str(dw_dir or DW_DIR), "direwolf_exe": dw_exe,
              "kisshub": "yes" if kiss else "no",
              "kisshub_profile": kiss[0] if kiss else "",
              "tinybox": "yes" if use_box else "no",
              "brocast": "yes" if use_bro else "no"}
    if START_CONF.is_file():        # keep tbclient/dxfeed lines (key d) and comments
        text = set_keys(START_CONF.read_text(encoding="utf-8"), "start", values)
    else:
        text = ("# Einstellungen der Steuerkonsole (TinyBox-Start.bat), erstellt von release/konfig.py\n"
                "# yes/no je Programm; die Taste d in der Steuerkonsole aendert sie auch.\n"
                "[start]\n" + "".join(f"{k} = {v}\n" for k, v in values.items()))
    START_CONF.write_text(text, encoding="utf-8")
    print(f"    geschrieben: {START_CONF.relative_to(ROOT)}")
    print()
    print("Fertig. Weitere Einstellungen (Chat-Boards, Bake, Rubriken ...) direkt in den")
    print(".conf-Dateien - Beschreibung in MANUAL.md. Erneut aufrufen: Steuerkonsole, Taste k.")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nAbgebrochen - nichts weiter geaendert.")
        sys.exit(1)
