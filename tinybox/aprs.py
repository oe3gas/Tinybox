"""APRS in plain language for the monitors (CR55).

decode() takes one UI frame and explains it part by part, for people who want
to learn how APRS is built. The result is a dict for the web GUIs:

    title   what kind of packet this is ("Mic-E position report")
    dest    what the destination field is here: a device ID from the device
            list, payload (Mic-E: the latitude) or a free word (BEACON)
    path    one explanation per digipeater entry, path_note sums them up
    segs    the info field cut into parts; the parts put together give the
            info field again (as the monitor shows it). Each part has a role
            (colour), a key (which plain-text chip belongs to it), a label, a
            meaning and - where something is computed - the calculation
    chips   the plain-text line under the monitor line; a chip with the same
            key as a part belongs to it (hover shows the pair)
    mice    for Mic-E: the six characters of the destination field explained
    lat/lon position, if there is one (for the map link)
    text    all chips as one string (the filter searches it)

Telemetry (T#...) is scaled with the PARM/UNIT/EQNS/BITS messages heard
earlier from the same station; TelemetryMemory keeps them.

The device list comes from aprs-deviceid (CC BY-SA 2.0), the symbol names
from the client's symbol set; both are in aprs_data.json.
"""

from __future__ import annotations

import calendar
import json
import math
import re
import time
from pathlib import Path

_DATA_FILE = Path(__file__).with_name("aprs_data.json")
_data: dict | None = None

PID_NO_L3 = 0xF0
# first characters of the info field this module understands
TYPES = {
    "!": "position without timestamp, no messaging",
    "=": "position without timestamp, station accepts messages",
    "/": "position with timestamp, no messaging",
    "@": "position with timestamp, station accepts messages",
    "`": "Mic-E, current GPS fix",
    "'": "Mic-E, old GPS fix (or Kenwood)",
    "\x1c": "Mic-E (old format)",
    "\x1d": "Mic-E (old format)",
    ">": "status report",
    ":": "message (to one station, a group or a bulletin)",
    "T": "telemetry values",
    "}": "third-party packet: a packet inside a packet",
    ";": "object (something placed on the map, not the sender itself)",
    ")": "item (like an object, shorter form)",
    "_": "weather report without position",
    "<": "station capabilities",
    "?": "query",
    "$": "raw GPS data (NMEA)",
}

MICE_STD = {7: "M0 Off Duty", 6: "M1 En Route", 5: "M2 In Service", 4: "M3 Returning",
            3: "M4 Committed", 2: "M5 Special", 1: "M6 Priority", 0: "Emergency"}

MAX_TELEMETRY_CALLS = 200


# ---------------------------------------------------------------- data tables

def data() -> dict:
    global _data
    if _data is None:
        try:
            _data = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _data = {"tocalls": [], "mice": [], "micelegacy": [], "symbols": {}}
        # most specific pattern first: more fixed characters wins
        _data["tocalls"].sort(key=lambda e: -sum(c not in "?n*" for c in e[0]))
    return _data


def _tocall_match(pattern: str, call: str) -> bool:
    if pattern.endswith("*"):
        pattern = pattern[:-1]
        if len(call) < len(pattern):
            return False
        call = call[:len(pattern)]
    if len(pattern) != len(call):
        return False
    for p, c in zip(pattern, call):
        if p == "?":
            continue
        if p == "n":
            if not c.isdigit():
                return False
        elif p != c:
            return False
    return True


def device_of(tocall: str) -> str:
    """'Microsat WX3in1 Plus 2.0' for APMI06; '' if not in the list."""
    base = tocall.split("-")[0]
    for pattern, name in data()["tocalls"]:
        if _tocall_match(pattern, base):
            return name
    return ""


def symbol_name(table: str, code: str) -> str:
    syms = data()["symbols"]
    if table in "/\\":
        return syms.get(table + code, "")
    if table.isdigit() or "A" <= table <= "Z" or "a" <= table <= "j":
        over = str("abcdefghij".index(table)) if "a" <= table <= "j" else table
        base = syms.get("\\" + code, "")
        return f"{base} (overlay {over})" if base else ""
    return ""


def _sym_table_text(table: str) -> str:
    if table == "/":
        return "/ = primary table"
    if table == "\\":
        return "\\ = alternate table"
    return f"{table} = alternate table with overlay character {table}"


# ---------------------------------------------------------------- helpers

def _clean(s: str) -> str:
    """Like the monitor shows text: no line breaks, '.' for unprintable bytes."""
    s = s.replace("\r", " ").replace("\n", " ")
    return "".join(c if c.isprintable() else "." for c in s)


def _dm(value: float, pos: str, neg: str, width: int) -> str:
    hemi = pos if value >= 0 else neg
    value = abs(value)
    deg = int(value)
    minutes = (value - deg) * 60
    if round(minutes, 2) >= 60:
        deg, minutes = deg + 1, 0.0
    return f"{deg:0{width}d}°{minutes:05.2f}′ {hemi}"


def lat_text(lat: float) -> str:
    return _dm(lat, "N", "S", 2)


def lon_text(lon: float) -> str:
    return _dm(lon, "E", "W", 3)


def _lc(name: str) -> str:
    return name[:1].lower() + name[1:]


def _b91(s: str) -> int:
    v = 0
    for c in s:
        v = v * 91 + ord(c) - 33
    return v


def locator_to_latlon(loc: str) -> tuple[float, float] | None:
    """Centre of a Maidenhead locator (4 or 6 characters)."""
    loc = loc.strip().upper()
    if not re.fullmatch(r"[A-R]{2}\d{2}([A-X]{2})?", loc):
        return None
    lon = (ord(loc[0]) - 65) * 20 - 180 + int(loc[2]) * 2
    lat = (ord(loc[1]) - 65) * 10 - 90 + int(loc[3])
    if len(loc) == 6:
        lon += (ord(loc[4]) - 65) * (2 / 24) + 1 / 24
        lat += (ord(loc[5]) - 65) * (1 / 24) + 1 / 48
    else:
        lon += 1
        lat += 0.5
    return lat, lon


def distance_bearing(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    """Great-circle distance in km and bearing from a to b in degrees."""
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    d = 2 * 6371.0 * math.asin(math.sqrt(math.sin((la2 - la1) / 2) ** 2 +
                                         math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2))
    y = math.sin(lo2 - lo1) * math.cos(la2)
    x = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(lo2 - lo1)
    return d, (math.degrees(math.atan2(y, x)) + 360) % 360


class _Out:
    """Collects parts and chips while a packet is taken apart."""

    def __init__(self, prefix: str = ""):
        self.segs: list[dict] = []
        self.chips: list[dict] = []
        self.prefix = prefix              # keys of an inner (third-party) packet
        self.lat: float | None = None
        self.lon: float | None = None
        self.title = ""
        self.device = ""
        self.mice: dict | None = None

    def seg(self, raw: str, role: str, key: str, label: str, mean: str = "", calc: str = "") -> None:
        if raw:
            self.segs.append({"t": _clean(raw), "r": role, "k": self.prefix + key,
                              "label": label, "mean": mean, "calc": calc})

    def chip(self, text: str, role: str, key: str) -> None:
        if text:
            self.chips.append({"t": text, "r": role, "k": self.prefix + key})


# ---------------------------------------------------------------- telemetry memory

class TelemetryMemory:
    """PARM / UNIT / EQNS / BITS per station: the names, units and scaling of
    its telemetry, announced as messages to itself."""

    def __init__(self) -> None:
        self.calls: dict[str, dict] = {}

    def take(self, call: str, kind: str, text: str) -> None:
        m = self.calls.setdefault(call.upper(), {})
        if kind == "PARM":
            m["parm"] = [x.strip() for x in text.split(",")]
        elif kind == "UNIT":
            m["unit"] = [x.strip() for x in text.split(",")]
        elif kind == "EQNS":
            try:
                m["eqns"] = [float(x) for x in text.split(",")]
            except ValueError:
                pass
        elif kind == "BITS":
            bits, _, title = text.partition(",")
            m["bits"] = bits.strip()
            m["title"] = title.strip()
        m["at"] = time.strftime("%H:%M:%S")
        if len(self.calls) > MAX_TELEMETRY_CALLS:
            del self.calls[min(self.calls, key=lambda c: self.calls[c].get("at", ""))]

    def get(self, call: str) -> dict:
        return self.calls.get(call.upper(), {})


# ---------------------------------------------------------------- path

_ALIAS = re.compile(r"^(WIDE|TRACE|[A-Z]{2})(\d)(?:-(\d{1,2}))?$")


def explain_path(path: list[str], repeated: list[bool]) -> tuple[list[dict], str, list[str]]:
    """One note per digipeater entry, a summary and warnings."""
    rows: list[dict] = []
    relayed = 0
    left = 0
    warnings: list[str] = []
    for call, h in zip(path, repeated):
        m = _ALIAS.match(call)
        if m:
            n, rest = int(m.group(2)), int(m.group(3) or 0)
            word = "WIDEn-N" if m.group(1) == "WIDE" else f"{m.group(1)}n-N (regional)"
            if h or rest == 0:
                note = f"{word} alias, all {n} hop(s) used up" if n else f"{word} alias, used"
            else:
                note = f"{word} alias: {rest} more hop(s) allowed (asked for {n})"
                left += rest
            if n >= 3:
                warnings.append(f"{call}: a long path ({n} hops) - recommended are 2 for mobiles, 1 or none for fixed stations")
        elif h:
            relayed += 1
            note = "relayed it" + (f" (hop {relayed})" if len(path) > 1 else "")
        else:
            note = "asked to relay it - has not done so yet"
        rows.append({"call": call + ("*" if h else ""), "note": note})
    if not path:
        summary = "No path: the sender asked nobody to relay it. You hear it directly (or an iGate gated it)."
    elif relayed == 0 and not any(repeated):
        summary = "Nobody has relayed it yet: you hear the sender directly."
    else:
        summary = f"Relayed {relayed} time(s) so far; " + (
            f"{left} hop(s) still allowed." if left else "no hops left - it will not travel further.")
    return rows, summary, warnings


# ---------------------------------------------------------------- positions

def _uncompressed(body: str, out: _Out) -> int | None:
    """ddmm.mmN/dddmm.mmE> - returns the length used (19) or None."""
    m = re.match(r"^(\d{2}[\d ]{2}\.[\d ]{2})([NS])(.)(\d{3}[\d ]{2}\.[\d ]{2})([EW])(.)", body)
    if not m:
        return None
    lat_s, ns, table, lon_s, ew, code = m.groups()
    amb = lat_s.count(" ")
    lat = int(lat_s[:2]) + float(lat_s[2:].replace(" ", "0")) / 60
    lon = int(lon_s[:3]) + float(lon_s[3:].replace(" ", "0")) / 60
    lat, lon = (lat if ns == "N" else -lat), (lon if ew == "E" else -lon)
    out.lat, out.lon = lat, lon
    amb_note = f" (position ambiguity: {amb} digit(s) blanked)" if amb else ""
    out.seg(lat_s + ns, "pos", "pos", "Latitude", lat_text(lat) + amb_note, "ddmm.mm + N/S")
    out.seg(table, "sym", "sym", "Symbol table", _sym_table_text(table))
    out.seg(lon_s + ew, "pos", "pos", "Longitude", lon_text(lon), "dddmm.mm + E/W")
    name = symbol_name(table, code)
    out.seg(code, "sym", "sym", "Symbol code", f"{table}{code} = {name}" if name else
            f"{table}{code} - not assigned in the symbol set", "")
    out.chip(f"{lat_text(lat)} {lon_text(lon)}", "pos", "pos")
    out.chip(_lc(name) if name else f"symbol {table}{code} ⚠ unassigned", "sym" if name else "warn", "sym")
    return 19


def _compressed(body: str, out: _Out) -> int | None:
    """/YYYYXXXX$csT - returns the length used (13) or None."""
    if len(body) < 13:
        return None
    table, la, lo, code, c, s, t = body[0], body[1:5], body[5:9], body[9], body[10], body[11], body[12]
    if not (table in "/\\" or "A" <= table <= "Z" or "a" <= table <= "j"):
        return None
    if not all("!" <= ch <= "{" for ch in la + lo):
        return None
    lat = 90 - _b91(la) / 380926
    lon = -180 + _b91(lo) / 190463
    out.lat, out.lon = lat, lon
    tab = table if table in "/\\" or "A" <= table <= "Z" else str("abcdefghij".index(table))
    out.seg(table, "sym", "sym", "Symbol table", _sym_table_text(tab), "compressed format: table first")
    out.seg(la, "pos", "pos", "Latitude (compressed)", lat_text(lat), f"base-91 {_b91(la)} → 90 − {_b91(la)}/380926")
    out.seg(lo, "pos", "pos", "Longitude (compressed)", lon_text(lon), f"base-91 {_b91(lo)} → −180 + {_b91(lo)}/190463")
    name = symbol_name(tab if tab in "/\\" else table, code)
    out.seg(code, "sym", "sym", "Symbol code", f"{tab}{code} = {name}" if name else f"{tab}{code} - not assigned in the symbol set")
    out.chip(f"{lat_text(lat)} {lon_text(lon)}", "pos", "pos")
    out.chip(_lc(name) if name else f"symbol {tab}{code} ⚠ unassigned", "sym" if name else "warn", "sym")
    cst = c + s + t
    if c == " ":
        out.seg(cst, "move", "cs", "Course/speed field", "empty (space): no course, speed or altitude", "")
    else:
        tt = ord(t) - 33
        if (tt >> 3) & 3 == 2:                                   # from a GGA sentence: altitude
            ft = 1.002 ** ((ord(c) - 33) * 91 + ord(s) - 33)
            out.seg(cst, "alt", "alt", "Altitude (compressed)", f"{ft * 0.3048:.0f} m ({ft:.0f} ft)", "1.002^cs feet")
            out.chip(f"{ft * 0.3048:.0f} m", "alt", "alt")
        elif c == "{":
            rng = 2 * 1.08 ** (ord(s) - 33)
            out.seg(cst, "move", "cs", "Radio range", f"{rng * 1.609:.0f} km", "2 × 1.08^s miles")
            out.chip(f"range {rng * 1.609:.0f} km", "move", "cs")
        elif "!" <= c <= "z":
            course = (ord(c) - 33) * 4
            kn = 1.08 ** (ord(s) - 33) - 1
            out.seg(cst, "move", "cs", "Course and speed", f"{kn * 1.852:.0f} km/h, course {course}°",
                    f"course ({ord(c)}−33)·4 · speed 1.08^({ord(s)}−33) − 1 = {kn:.0f} kn")
            out.chip(f"{kn * 1.852:.0f} km/h → {course}°", "move", "cs")
    return 13


def _position(body: str, out: _Out, home) -> int | None:
    n = _uncompressed(body, out)
    if n is None:
        n = _compressed(body, out)
    return n


# ---------------------------------------------------------------- weather

_WX = {  # letter: (digits, label, converter)
    "c": (3, "Wind direction", lambda v: f"from {v}°"),
    "s": (3, "Wind speed", lambda v: f"{v * 1.609:.0f} km/h ({v} mph)"),
    "g": (3, "Gust", lambda v: f"{v * 1.609:.0f} km/h ({v} mph)"),
    "t": (3, "Temperature", lambda v: f"{(v - 32) * 5 / 9:.1f} °C ({v} °F)"),
    "r": (3, "Rain last hour", lambda v: f"{v * 0.254:.1f} mm"),
    "p": (3, "Rain last 24 h", lambda v: f"{v * 0.254:.1f} mm"),
    "P": (3, "Rain since midnight", lambda v: f"{v * 0.254:.1f} mm"),
    "h": (2, "Humidity", lambda v: f"{v or 100} %"),
    "b": (5, "Air pressure", lambda v: f"{v / 10:.1f} hPa"),
    "L": (3, "Sun radiation", lambda v: f"{v} W/m²"),
    "l": (3, "Sun radiation", lambda v: f"{v + 1000} W/m²"),
    "s#": (3, "Snow", lambda v: f"{v * 2.54:.0f} cm"),
    "#": (3, "Rain counter", lambda v: f"{v}"),
}
_WX_CHIP = {"g": "gust", "t": "", "r": "rain 1 h", "p": "rain 24 h", "P": "rain today", "h": "humidity",
            "b": "", "L": "sun", "l": "sun", "#": "rain counter", "c": "wind from", "s": "wind"}


def _weather(text: str, out: _Out, first: str = "") -> int:
    """Weather fields after the wind (g t r p P h b L l s # ...) - returns the length used.
    first = "cs" for a report without position: there c and s are the wind."""
    i = 0
    letters = set("gtrpPhbLls#") | set(first)
    while i < len(text) and text[i] in letters:
        letter = text[i]
        digits, label, conv = _WX["s#" if letter == "s" and "s" not in first else letter]
        value = text[i + 1:i + 1 + digits]
        if not (re.fullmatch(r"-?\d+", value) or (value and set(value) <= set(". "))) or len(value) != digits:
            run = re.match(r"-?\d*", text[i + 1:]).group(0)
            if not run:
                break
            raw = letter + run
            out.seg(raw, "warn", f"wx{letter}", f"{label} - malformed",
                    f"the format wants {letter} + {digits} digits", f"got {len(run)} digit(s)")
            out.chip(f"{label.lower()} ⚠ invalid", "warn", f"wx{letter}")
            i += len(raw)
            continue
        raw = letter + value
        if set(value) <= set(". "):
            out.seg(raw, "wx", f"wx{letter}", label, "no data (sensor missing)")
        else:
            v = int(value)
            out.seg(raw, "wx", f"wx{letter}", label, conv(v),
                    {"t": f"({v} − 32) × 5/9", "b": "tenths of hPa", "h": "h00 means 100 %"}.get(letter, ""))
            word = _WX_CHIP.get(letter, label.lower())
            out.chip((word + " " if word else "") + conv(v).split(" (")[0], "wx", f"wx{letter}")
        i += len(raw)
    return i


# ---------------------------------------------------------------- comment helpers

def _comment(text: str, out: _Out, label: str = "Comment") -> None:
    """Free text; an altitude /A=nnnnnn in it gets a part of its own."""
    m = re.search(r"/A=(-?\d{5,6})", text)
    if not m:
        out.seg(text, "text", "cmt", label, "free text")
        free = text
    else:
        before, after = text[:m.start()], text[m.end():]
        out.seg(before, "text", "cmt", label, "free text")
        ft = int(m.group(1))
        out.seg(m.group(0), "alt", "alt", "Altitude", f"{ft * 0.3048:.0f} m ({ft} ft)", "/A= then feet, 6 digits")
        out.chip(f"{ft * 0.3048:.0f} m", "alt", "alt")
        out.seg(after, "text", "cmt", label, "free text")
        free = before + " " + after
    if free.strip():
        out.chip("\u201c" + _clean(" ".join(free.split())) + "\u201d", "text", "cmt")


def _extension(text: str, out: _Out, weather: bool) -> int:
    """Data extension right after the position: course/speed, PHG, RNG, DFS."""
    m = re.match(r"^(\d{3}|\.\.\.| {3})/(\d{3}|\.\.\.| {3})", text)
    if m:
        a, b = m.groups()
        if weather:
            d, v = (int(a) if a.isdigit() else None), (int(b) if b.isdigit() else None)
            out.seg(m.group(0), "wx", "wind", "Wind", (f"from {d}°, " if d is not None else "") +
                    (f"{v * 1.609:.0f} km/h ({v} mph)" if v is not None else "speed unknown"),
                    "direction°/speed mph")
            out.chip("wind calm" if v == 0 else f"wind {d}° {v * 1.609:.0f} km/h" if v is not None else "wind ?",
                     "wx", "wind")
        else:
            c, sp = int(a) if a.isdigit() else 0, int(b) if b.isdigit() else 0
            out.seg(m.group(0), "move", "move", "Course and speed",
                    f"course {c}°, {sp * 1.852:.0f} km/h ({sp} kn)", "ddd/sss: course°/speed knots")
            out.chip(f"{sp * 1.852:.0f} km/h → {c}°" if sp else f"standing (course {c}°)", "move", "move")
        return 7
    m = re.match(r"^PHG(\d)(\d)(\d)(\d)", text)
    if m:
        p, h, g, d = (int(x) for x in m.groups())
        dirs = ["omni"] + [f"{x}°" for x in range(45, 361, 45)]
        out.seg(m.group(0), "move", "phg", "Power, height, gain, direction",
                f"{p * p} W, {10 * 2 ** h} ft above average terrain, {g} dBi, {dirs[d] if d < 9 else '?'}",
                f"P={p}→{p}² W · H={h}→10·2^{h} ft · G={g} dB · D={d}")
        out.chip(f"PHG {p * p} W {g} dBi {dirs[d] if d < 9 else ''}".strip(), "move", "phg")
        return 7
    m = re.match(r"^RNG(\d{4})", text)
    if m:
        out.seg(m.group(0), "move", "phg", "Radio range", f"{int(m.group(1)) * 1.609:.0f} km", "miles")
        out.chip(f"range {int(m.group(1)) * 1.609:.0f} km", "move", "phg")
        return 7
    return 0


# ---------------------------------------------------------------- the types

def _timestamp(ts: str, out: _Out, now: float) -> None:
    if ts.endswith("z") and ts[:6].isdigit():
        day, hh, mm = int(ts[:2]), int(ts[2:4]), int(ts[4:6])
        g = time.gmtime(now)
        year, mon = g.tm_year, g.tm_mon
        try:
            sent = calendar.timegm((year, mon, day, hh, mm, 0))
            if sent > now + 86400:                       # day of the previous month
                year, mon = (year, mon - 1) if mon > 1 else (year - 1, 12)
                sent = calendar.timegm((year, mon, day, hh, mm, 0))
        except (ValueError, OverflowError):
            out.seg(ts, "warn", "time", "Timestamp - unreadable", "")
            return
        delta = (now - sent) / 60
        off = 15 < abs(delta) < 60 * 24 * 20
        note = ""
        if off:
            h, mi = divmod(int(abs(delta)), 60)
            note = f" - the sender's clock is about {h} h {mi} min {'behind' if delta > 0 else 'ahead'}"
        local = time.strftime("%H:%M", time.localtime(sent))
        out.seg(ts, "time", "time", "Timestamp", f"day {day}, {hh:02d}:{mm:02d} UTC = {local} local{note}",
                "DDHHMM + z (UTC)")
        out.chip(f"sent {local} local" + (" ⚠ clock off" if off else ""), "warn" if off else "time", "time")
    elif ts.endswith("h") and ts[:6].isdigit():
        out.seg(ts, "time", "time", "Timestamp", f"{ts[:2]}:{ts[2:4]}:{ts[4:6]} UTC", "HHMMSS + h (UTC)")
        out.chip(f"sent {ts[:2]}:{ts[2:4]} UTC", "time", "time")
    elif ts.endswith("/") and ts[:6].isdigit():
        out.seg(ts, "time", "time", "Timestamp", f"day {ts[:2]}, {ts[2:4]}:{ts[4:6]} sender's local time", "DDHHMM + / (local)")
        out.chip(f"sent {ts[2:4]}:{ts[4:6]} (their time)", "time", "time")
    else:
        out.seg(ts, "warn", "time", "Timestamp - unreadable", "")


def _pos_report(text: str, out: _Out, home, now: float) -> bool:
    kind = text[0]
    out.seg(kind, "type", "type", "Data type", f"{kind} = {TYPES[kind]}")
    body = text[1:]
    if kind in "/@":
        _timestamp(body[:7], out, now)
        body = body[7:]
    out.title = "Position report" + (" with timestamp" if kind in "/@" else "")
    out.chip("Position", "type", "type")
    n = _position(body, out, home)
    if n is None:
        out.seg(body, "warn", "cmt", "Not readable", "this does not follow the position format")
        return True
    rest = body[n:]
    weather = bool(out.segs) and any(s["k"] == out.prefix + "sym" and s["t"] == "_" for s in out.segs) \
        and n == 19
    if weather:
        out.title = "Weather report"
        for c in out.chips:
            if c["k"] == out.prefix + "type":
                c["t"] = "Weather"
    used = _extension(rest, out, weather)
    rest = rest[used:]
    if weather:
        rest = rest[_weather(rest, out):]
    if rest:
        _comment(rest, out)
    return True


def _mice(dest: str, text: str, out: _Out, home) -> bool:
    call = dest.split("-")[0]
    if len(call) != 6 or len(text) < 4:
        return False
    digits, bits, cells = [], [], []
    for i, ch in enumerate(call):
        if ch.isdigit():
            d, b = int(ch), 0
        elif "A" <= ch <= "J":
            d, b = ord(ch) - 65, 2          # custom bit
        elif "P" <= ch <= "Y":
            d, b = ord(ch) - 80, 1          # standard bit
        elif ch == "K":
            d, b = None, 2
        elif ch == "L":
            d, b = None, 0
        elif ch == "Z":
            d, b = None, 1
        else:
            return False
        if i >= 3 and b == 2:
            return False
        digits.append(d)
        bits.append(b)
    amb = sum(d is None for d in digits)
    dg = [d if d is not None else 0 for d in digits]
    lat = dg[0] * 10 + dg[1] + (dg[2] * 10 + dg[3] + (dg[4] * 10 + dg[5]) / 100) / 60
    north, plus100, west = bits[3] == 1, bits[4] == 1, bits[5] == 1
    if not north:
        lat = -lat
    abc = bits[:3]
    if all(b != 2 for b in abc):
        code = (abc[0] << 2) | (abc[1] << 1) | abc[2]
        msg = MICE_STD[code]
        msg_note = f"bits A B C = {abc[0]} {abc[1]} {abc[2]} → {msg}"
    elif all(b != 1 for b in abc):
        code = ((abc[0] > 0) << 2) | ((abc[1] > 0) << 1) | (abc[2] > 0)
        msg = "Emergency" if code == 0 else f"C{7 - code} Custom-{7 - code}"
        msg_note = f"custom bits → {msg}"
    else:
        msg, msg_note = "unknown (mixed bits)", "standard and custom bits mixed"
    names = ["msg A", "msg B", "msg C", "N/S", "lon +100", "E/W"]
    for i, ch in enumerate(call):
        if i < 3:
            bit = f"{'ABC'[i]} = {1 if bits[i] else 0}" + (" (custom)" if bits[i] == 2 else "")
        elif i == 3:
            bit = "North" if north else "South"
        elif i == 4:
            bit = "lon +100°" if plus100 else "lon +0°"
        else:
            bit = "West" if west else "East"
        cells.append({"pos": f"pos {i + 1}", "ch": ch, "d": "␣" if digits[i] is None else str(digits[i]),
                      "bit": bit, "what": names[i]})

    b = [ord(c) for c in text]
    d = b[1] - 28 + (100 if plus100 else 0)
    if 180 <= d <= 189:
        d -= 80
    elif 190 <= d <= 199:
        d -= 190
    m = b[2] - 28
    if m >= 60:
        m -= 60
    h = b[3] - 28
    if not (0 <= d <= 179 and 0 <= m <= 59 and 0 <= h <= 99):
        return False
    lon = d + (m + h / 100) / 60
    if west:
        lon = -lon
    if len(text) < 9:                           # cut off: only the position is left
        out.lat, out.lon = lat, lon
        out.title = "Mic-E position report (cut off)"
        out.seg(text[0], "type", "type", "Data type", f"{text[0]} = {TYPES.get(text[0], 'Mic-E')}")
        out.seg(text[1:4], "pos", "lon", "Longitude", lon_text(lon), "bytes − 28: degrees, minutes, hundredths")
        out.seg(text[4:], "warn", "cut", "Cut off", "speed, course and symbol are missing",
                "a Mic-E info field has at least 9 bytes")
        out.chip("Mic-E position", "type", "type")
        out.chip(lat_text(lat), "pos", "dest")
        out.chip(lon_text(lon), "pos", "lon")
        out.chip(msg, "warn" if msg == "Emergency" else "stat", "dest")
        out.chip("⚠ packet cut off", "warn", "cut")
        out.mice = {"cells": cells, "sum": f"→ {lat_text(lat)} · {msg_note}"}
        return True
    sp, dc, se = b[4] - 28, b[5] - 28, b[6] - 28
    knots = sp * 10 + dc // 10
    if knots >= 800:
        knots -= 800
    course = (dc % 10) * 100 + se
    if course >= 400:
        course -= 400
    code_c, table = text[7], text[8]

    out.lat, out.lon = lat, lon
    out.title = "Mic-E position report"
    lat_s = lat_text(lat) + (f" (ambiguity: {amb} digit(s) blanked)" if amb else "")
    out.seg(text[0], "type", "type", "Data type", f"{text[0]} = {TYPES.get(text[0], 'Mic-E')}".replace("\x1c", "^\\").replace("\x1d", "^]"))
    out.seg(text[1:4], "pos", "lon", "Longitude", lon_text(lon),
            f"{text[1]!r} {b[1]}−28{' +100' if plus100 else ''} = {d}° · {text[2]!r} {b[2]}−28 → {m}′ · "
            f"{text[3]!r} {b[3]}−28 = .{h:02d}")
    out.seg(text[4:7], "move", "move", "Speed and course",
            f"{knots} kn = {knots * 1.852:.0f} km/h, course {course}°",
            f"speed ({b[4]}−28)·10 + ⌊({b[5]}−28)/10⌋ (−800 if ≥ 800) · course ({dc} mod 10)·100 + ({b[6]}−28) (−400 if ≥ 400)")
    name = symbol_name(table, code_c)
    out.seg(code_c, "sym", "sym", "Symbol code", (f"{table}{code_c} = {name}" if name else f"{table}{code_c} - not assigned"),
            "in Mic-E the code comes before the table")
    out.seg(table, "sym", "sym", "Symbol table", _sym_table_text(table))

    rest = text[9:]
    dev = ""
    prefix = suffix = ""
    tail = rest.rstrip(" ")
    trail = rest[len(tail):]
    if rest[:1] in ("`", "'"):
        prefix = rest[0]
        for suf, nm in data()["mice"]:
            if rest.endswith(suf) and len(rest) >= len(suf) + 1:
                suffix, dev, tail, trail = suf, nm, rest, ""
                break
            if tail.endswith(suf) and len(tail) >= len(suf) + 1:
                suffix, dev = suf, nm
                break
    elif rest[:1] in (">", "]"):
        prefix = rest[0]
        best = ""
        for pre, suf, nm in data()["micelegacy"]:
            if pre == prefix and (not suf or (tail.endswith(suf) and len(tail) >= 2)):
                if suf and len(suf) >= len(suffix):
                    suffix, dev = suf, nm
                elif not suffix and not best:
                    best = nm
        dev = dev or best
    mid = tail[len(prefix):len(tail) - len(suffix)] if suffix else rest[len(prefix):]
    if prefix:
        out.seg(prefix, "dev", "dev", "Device prefix",
                {"`": "new Mic-E: the device is named by the last two characters",
                 "'": "new Mic-E (no messaging): the device is named by the last characters",
                 ">": "legacy Kenwood handheld", "]": "legacy Kenwood mobile radio"}[prefix])
    alt_m = re.match(r"^([!-{]{3})}", mid)
    if alt_m:
        v = _b91(alt_m.group(1)) - 10000
        out.seg(alt_m.group(0), "alt", "alt", "Altitude", f"{v} m",
                f"base-91 '{alt_m.group(1)}' = {_b91(alt_m.group(1))} − 10000; '}}' ends it")
        mid = mid[4:]
    if mid:
        out.seg(mid, "text", "cmt", "Comment", "free text")
    if suffix:
        out.seg(suffix + trail, "dev", "dev", "Device suffix", dev, "from the device list (Mic-E section)")
    elif trail and not mid:
        out.seg(trail, "text", "cmt", "Comment", "free text")
    out.device = dev

    out.chip("Mic-E position", "type", "type")
    out.chip(lat_text(lat), "pos", "dest")
    out.chip(lon_text(lon), "pos", "lon")
    out.chip(f"{knots * 1.852:.0f} km/h → {course}°" if knots else f"standing (course {course}°)", "move", "move")
    if alt_m:
        out.chip(f"{_b91(alt_m.group(1)) - 10000} m", "alt", "alt")
    out.chip(msg, "warn" if msg == "Emergency" else "stat", "dest")
    out.chip(_lc(name) if name else f"symbol {table}{code_c} ⚠ unassigned", "sym" if name else "warn", "sym")
    if dev:
        out.chip(dev, "dev", "dev")
    if mid.strip():
        out.chip("“" + _clean(mid.strip()) + "”", "text", "cmt")
    out.mice = {"cells": cells, "sum": f"→ {lat_text(lat)} · {msg_note}"}
    return True


def _message(src: str, text: str, out: _Out, memory: TelemetryMemory | None) -> bool:
    if len(text) < 11 or text[10] != ":":
        return False
    to = text[1:10]
    body = text[11:]
    target = to.strip()
    out.seg(":", "type", "type", "Data type", ": = " + TYPES[":"])
    who = "a bulletin to everyone" if target.startswith("BLN") else \
        "an announcement" if target.startswith("NWS") else f"for {target}"
    out.seg(to + ":", "stat", "to", "Addressee", f"{target} - always 9 characters, filled with spaces",
            "the real recipient of APRS lives here, not in the destination field")
    m = re.fullmatch(r"(PARM|UNIT|EQNS|BITS)\.(.*)", body)
    if m:
        kind, rest = m.groups()
        if memory is not None and target:
            memory.take(target, kind, rest)
        meaning = {"PARM": "names of the telemetry channels", "UNIT": "units of the telemetry channels",
                   "EQNS": "scaling a·x² + b·x + c for the 5 analog channels",
                   "BITS": "which bit value means 'active', then the project title"}[kind]
        out.title = "Telemetry definition"
        out.seg(kind + ".", "tlm", "tdef", f"{kind} definition", meaning,
                "sent to itself so that programs can read its T# values")
        out.seg(rest, "tlm", "tval", "Values", rest)
        out.chip(f"Telemetry {kind.lower()} for {target}", "type", "type")
        out.chip(rest, "tlm", "tval")
        return True
    am = re.fullmatch(r"(ack|rej)(\w{1,5})", body)
    if am:
        out.title = "Message acknowledgement" if am.group(1) == "ack" else "Message rejected"
        out.seg(body, "stat", "ack", "Answer", f"{am.group(1)} for message no. {am.group(2)}")
        out.chip(f"{am.group(1)} no. {am.group(2)} to {target}", "type", "type")
        return True
    num = ""
    nm = re.search(r"\{([A-Za-z0-9]{1,5})(\}[A-Za-z0-9]{0,5})?$", body)
    if nm:
        num = nm.group(0)
        body = body[:nm.start()]
    out.title = "Bulletin" if target.startswith("BLN") else "Message"
    out.seg(body, "text", "cmt", "Text", "free text")
    if num:
        out.seg(num, "stat", "num", "Message number", f"no. {nm.group(1)}: the receiver answers with ack{nm.group(1)}",
                "{ + up to 5 characters")
    out.chip(f"Message {who}" if not target.startswith(("BLN", "NWS")) else who.capitalize(), "type", "type")
    out.chip(f"to {target}", "stat", "to")
    out.chip("“" + _clean(body.strip()) + "”", "text", "cmt")
    if num:
        out.chip(f"no. {nm.group(1)}, wants an ack", "stat", "num")
    return True


def _telemetry(src: str, text: str, out: _Out, memory: TelemetryMemory | None) -> bool:
    m = re.match(r"^T#([^,]{1,5}),(.*)$", text)
    if not m:
        return False
    seq, rest = m.groups()
    meta = memory.get(src) if memory is not None else {}
    parm, unit, eqns = meta.get("parm", []), meta.get("unit", []), meta.get("eqns", [])
    out.title = "Telemetry" + (f": {meta['title']}" if meta.get("title") else "")
    out.seg("T#" + seq, "type", "type", "Data type + sequence", f"T = telemetry, report no. {seq.lstrip('0') or '0'}")
    out.chip(f"Telemetry #{seq.lstrip('0') or '0'}", "type", "type")
    fields = rest.split(",")
    scaled = False
    for i, f in enumerate(fields[:5]):
        key = f"a{i + 1}"
        name = parm[i] if i < len(parm) and parm[i] else f"A{i + 1}"
        try:
            x = float(f)
        except ValueError:
            out.seg("," + f, "warn", key, f"A{i + 1} - not a number", f)
            continue
        if len(eqns) >= 3 * (i + 1):
            a, b, c = eqns[3 * i:3 * i + 3]
            v = a * x * x + b * x + c
            u = unit[i] if i < len(unit) else ""
            vs = f"{v:.2f}".rstrip("0").rstrip(".")
            calc = f"{a:g}·{f}² + {b:g}·{f} + {c:g}" if a else f"{f} × {b:g}" + (f" + {c:g}" if c else "")
            out.seg("," + f, "tlm", key, f"A{i + 1} {name}", f"{vs} {u}".strip(), calc)
            if a or b or c:
                out.chip(f"{name} {vs} {u}".strip(), "tlm", key)
            scaled = True
        else:
            out.seg("," + f, "tlm", key, f"A{i + 1} {name}", f"raw value {f}", "no EQNS heard yet: not scaled")
            out.chip(f"{name} {f}", "tlm", key)
    if len(fields) > 5:
        bits = ",".join(fields[5:])
        sense = meta.get("bits", "11111111")
        names = parm[5:13] if len(parm) > 5 else []
        on = []
        for j, ch in enumerate(bits[:8]):
            if ch in "01" and j < len(sense) and ch == sense[j]:
                on.append(names[j] if j < len(names) and names[j] else f"B{j + 1}")
        out.seg("," + bits, "stat", "bits", "Digital bits",
                ("active: " + ", ".join(on)) if on else "nothing active",
                f"BITS {sense}: the bit value that means 'active'")
        out.chip(("active: " + ", ".join(on)) if on else "bits: nothing active", "stat", "bits")
    if scaled:
        out.chip(f"scaled with PARM/UNIT/EQNS from {meta.get('at', '?')}", "text", "meta")
    elif memory is not None:
        out.chip("raw values - no PARM/EQNS heard from this station yet", "text", "meta")
    return True


def _object(text: str, out: _Out, home, now: float) -> bool:
    if text[0] == ";":
        if len(text) < 18:
            return False
        name, live, ts, body = text[1:10], text[10], text[11:18], text[18:]
        out.seg(";", "type", "type", "Data type", "; = " + TYPES[";"])
        out.seg(name, "stat", "name", "Object name", f"“{name.strip()}” - always 9 characters")
        out.seg(live, "stat", "live", "State", "* = alive" if live == "*" else "_ = deleted (killed)")
        _timestamp(ts, out, now)
        out.title = "Object" + (" (deleted)" if live == "_" else "")
    else:
        m = re.match(r"^\)([^!_]{3,9})([!_])", text)
        if not m:
            return False
        name, live = m.groups()
        body = text[m.end():]
        out.seg(")", "type", "type", "Data type", ") = " + TYPES[")"])
        out.seg(name, "stat", "name", "Item name", f"“{name}”")
        out.seg(live, "stat", "live", "State", "! = alive" if live == "!" else "_ = deleted (killed)")
        out.title = "Item" + (" (deleted)" if live == "_" else "")
    out.chip(out.title, "type", "type")
    out.chip(f"“{name.strip()}”", "stat", "name")
    n = _position(body, out, home)
    if n is None:
        out.seg(body, "warn", "cmt", "Not readable", "this does not follow the position format")
        return True
    rest = body[n:]
    rest = rest[_extension(rest, out, False):]
    if rest:
        _comment(rest, out)
    return True


def _weather_only(text: str, out: _Out) -> bool:
    if len(text) < 9 or not text[1:9].isdigit():
        return False
    out.title = "Weather report without position"
    out.seg("_", "type", "type", "Data type", "_ = " + TYPES["_"])
    out.seg(text[1:9], "time", "time", "Timestamp", f"{text[1:3]}-{text[3:5]} {text[5:7]}:{text[7:9]}", "MMDDHHMM")
    out.chip("Weather", "type", "type")
    rest = text[9:]
    used = _weather(rest, out, first="cs")
    if rest[used:]:
        out.seg(rest[used:], "text", "cmt", "Rest", "software and station type, free text")
    return True


def _third_party(text: str, out: _Out, home, now, memory) -> bool:
    m = re.match(r"^\}([A-Za-z0-9-]{1,9})>([A-Za-z0-9-]{1,9})((?:,[A-Za-z0-9*-]{1,10})*):", text)
    if not m:
        return False
    src, dst, path = m.group(1), m.group(2), m.group(3)
    inner = text[m.end():]
    out.title = "Third-party packet"
    out.seg("}", "type", "type", "Data type", "} = " + TYPES["}"])
    via_inet = "TCPIP" in path or "TCPXX" in path
    gate = re.search(r",([A-Z0-9-]+)\*", path)
    out.seg(text[1:m.end()], "tp", "inner", "Inner header",
            f"from {src} to {dst}" + (", came over the internet (TCPIP)" if via_inet else "") +
            (f", put on the air by {gate.group(1)}" if gate else ""),
            "same order as on the air: from>to,path:")
    out.chip("Third party: internet → radio" if via_inet else "Third party", "type", "type")
    out.chip(f"from {src}" + (f" via iGate {gate.group(1)}" if gate else ""), "tp", "inner")
    sub = _Out("i.")
    sub.title = ""
    if inner and _decode_info(src, dst, inner, sub, home, now, memory):
        out.segs += sub.segs
        out.chips += sub.chips
        out.lat, out.lon = sub.lat, sub.lon
        if sub.title:
            out.title = f"Third-party packet: {sub.title.lower()}"
    else:
        out.seg(inner, "text", "cmt", "Inner info field", "not readable as APRS")
    return True


def _decode_info(src: str, dest: str, text: str, out: _Out, home, now: float,
                 memory: TelemetryMemory | None) -> bool:
    kind = text[0]
    if kind in "!=/@":
        return _pos_report(text, out, home, now)
    if kind in "`'\x1c\x1d":
        return _mice(dest, text, out, home)
    if kind == ">":
        out.title = "Status report"
        out.seg(">", "type", "type", "Data type", "> = " + TYPES[">"])
        body = text[1:]
        if re.match(r"^\d{6}z", body):
            _timestamp(body[:7], out, now)
            body = body[7:]
        out.chip("Status", "type", "type")
        if body:
            out.seg(body, "text", "cmt", "Status text", "free text")
            out.chip("“" + _clean(body.strip()) + "”", "text", "cmt")
        return True
    if kind == ":":
        return _message(src, text, out, memory)
    if kind == "T":
        return _telemetry(src, text, out, memory)
    if kind == "}":
        return _third_party(text, out, home, now, memory)
    if kind in ";)":
        return _object(text, out, home, now)
    if kind == "_":
        return _weather_only(text, out)
    if kind in "<?$":
        out.title = {"<": "Station capabilities", "?": "Query", "$": "Raw GPS data"}[kind]
        out.seg(kind, "type", "type", "Data type", f"{kind} = {TYPES[kind]}")
        out.seg(text[1:], "text", "cmt", "Content", "free text")
        out.chip(out.title, "type", "type")
        return True
    return False


def decode(dest: str, src: str, path: list[str], repeated: list[bool] | None, info: bytes, *,
           memory: TelemetryMemory | None = None, home: tuple[float, float] | None = None,
           now: float | None = None) -> dict | None:
    """Explain one UI frame as APRS; None if it is not APRS."""
    if not info:
        return None
    text = info.decode("latin-1")
    if text[0] not in TYPES:
        return None
    now = time.time() if now is None else now
    repeated = list(repeated) if repeated is not None else [False] * len(path)
    out = _Out()
    try:
        ok = _decode_info(src, dest, text, out, home, now, memory)
    except (ValueError, IndexError):
        ok = False
    if not ok:
        if text[0] in "`'\x1c\x1d" or text[0] == "T":
            return None                       # a stray backtick or 'T...' text: not APRS
        out = _Out()
        out.title = "APRS packet (not fully readable)"
        out.seg(text[0], "type", "type", "Data type", f"{text[0]} = {TYPES[text[0]]}")
        out.seg(text[1:], "warn", "cmt", "Not readable", "does not follow the format of this type")
        out.chip(out.title, "warn", "type")

    mice = out.mice
    base = dest.split("-")[0]
    if mice:
        mode = "payload"
        note = ("Not a recipient and not a device: in Mic-E these six characters are data - "
                "the latitude plus three message bits and three flags.")
        dev = out.device
    else:
        dev = device_of(dest)
        if base.startswith("AP"):
            mode = "device"
            note = (f"Not a recipient. {base} is a device ID from the device list (tocalls): {dev}."
                    if dev and dev != "Unknown Unknown" else
                    f"Not a recipient. {base} is a generic or unlisted device ID (tocall).")
            if dev == "Unknown Unknown":
                dev = ""
        else:
            mode = "other"
            note = f"Not a recipient: a free word in the destination field ({base}), not from the device list."
        if dev:
            out.chip(dev, "dev", "dest")
    if home and out.lat is not None:
        dist, brg = distance_bearing(home, (out.lat, out.lon))
        out.chip(f"{dist:.0f} km, {brg:.0f}° from you", "pos", "dist")
    rows, summary, warnings = explain_path(path, repeated)
    for w in warnings:
        out.chip("⚠ long path", "warn", "path")
        break
    result = {
        "title": out.title,
        "dest": {"mode": mode, "note": note, "device": dev},
        "path": rows, "path_note": summary, "warnings": warnings,
        "segs": out.segs, "chips": out.chips,
        "text": " ".join(c["t"] for c in out.chips),
    }
    if mice:
        result["mice"] = mice
    if out.lat is not None:
        result["lat"], result["lon"] = round(out.lat, 5), round(out.lon, 5)
    return result
