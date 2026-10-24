"""Parse DX cluster spot lines, derive band and mode, clean foreign input.

A spot line from DXSpider or CC Cluster looks like this:

    DX de OE3GAS:     14025.0  VP8ABC       CW 599 tnx                 1234Z
    DX de DK9IP-#:     7012.0  JA1ABC       CW 12 dB 26 WPM CQ          0712Z JN48

Everything coming from the cluster is untrusted input from the internet. It
ends up in a bulletin that is sent over AX.25, so only printable ASCII with a
length limit survives (clean_text), and calls must look like calls.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

SPOT_RE = re.compile(
    r"^DX de\s+(?P<spotter>[A-Za-z0-9/#-]{3,20}):?\s+"
    r"(?P<freq>\d{3,8}(?:\.\d{1,3})?)\s+"
    r"(?P<dx>[A-Za-z0-9/]{3,16})\s*"
    r"(?P<comment>.*?)\s*"
    r"(?P<time>\d{4})Z"
    r"(?:\s+\S{0,8})?\s*$")

SSID_RE = re.compile(r"-[0-9#]{1,3}$")
CALL_RE = re.compile(r"^(?=.*[A-Z])(?=.*\d)[A-Z0-9]+(?:/[A-Z0-9]+){0,2}$")
MAX_COMMENT = 40

# (band, from kHz, to kHz) - amateur bands seen in cluster spots
BANDS = (
    ("160m", 1800, 2000), ("80m", 3500, 4000), ("60m", 5250, 5450),
    ("40m", 7000, 7300), ("30m", 10100, 10150), ("20m", 14000, 14350),
    ("17m", 18068, 18168), ("15m", 21000, 21450), ("12m", 24890, 24990),
    ("10m", 28000, 29700), ("6m", 50000, 54000), ("4m", 70000, 71000),
    ("2m", 144000, 148000), ("70cm", 430000, 440000),
)
BAND_ORDER = [b[0] for b in BANDS]

# keywords in the spot comment, first match wins (FT8 before FT4 etc. does not
# matter: whole words only)
MODE_WORDS = (
    ("FT8", "FT8"), ("FT4", "FT4"), ("CW", "CW"), ("SSB", "SSB"), ("USB", "SSB"),
    ("LSB", "SSB"), ("RTTY", "RTTY"), ("PSK31", "PSK"), ("PSK63", "PSK"),
    ("PSK", "PSK"), ("JS8", "JS8"), ("SSTV", "SSTV"), ("Q65", "Q65"),
    ("MSK144", "MSK"), ("FM", "FM"), ("AM", "AM"), ("OLIVIA", "OLIVIA"),
    ("VARA", "VARA"), ("JT65", "JT65"), ("WSPR", "WSPR"),
)
_MODE_RE = re.compile(r"\b(" + "|".join(w for w, _ in MODE_WORDS) + r")\b")
_MODE_MAP = dict(MODE_WORDS)

# usual FT8 / FT4 dial frequencies (kHz); a spot within 3 kHz above is FT8/FT4
FT8_DIAL = (1840, 3573, 5357, 7074, 10136, 14074, 18100, 21074, 24915, 28074, 50313,
            144174, 432174)
FT4_DIAL = (3575.5, 7047.5, 10140, 14080, 18104, 21140, 24919, 28180, 50318, 144170)

# IARU region 1 band plan, roughly: CW-only and phone segments (kHz). Phone also
# up to the band edge used in region 2 (80 m to 4000, 40 m to 7300): DX from the
# Americas is spotted there by European stations too.
CW_SEGMENTS = ((1800, 1838), (3500, 3570), (7000, 7040), (10100, 10130),
               (14000, 14070), (18068, 18095), (21000, 21070), (24890, 24915),
               (28000, 28070), (50000, 50100), (70000, 70100), (144000, 144150),
               (432000, 432100))
# narrow-band digital segments (RTTY, PSK, Olivia ...) outside the FT8/FT4 dials
DIGI_SEGMENTS = ((1838, 1843), (3570, 3600), (5351, 5366), (7040, 7060), (10130, 10150),
                 (14070, 14101), (18095, 18111), (21070, 21151), (24915, 24931),
                 (28070, 28300))
PHONE_SEGMENTS = ((1843, 2000), (3600, 4000), (5366, 5450), (7060, 7300), (14101, 14350),
                  (18111, 18168), (21151, 21450), (24931, 24990), (28300, 29700),
                  (50100, 50500), (70100, 70500), (144150, 144400), (432100, 432400))
FM_SEGMENTS = ((29510, 29700), (51000, 54000), (145000, 148000), (433000, 440000))
DIGI = "DIGI"          # mode name for the digital segments (dictionary: free text)


@dataclass(frozen=True)
class Spot:
    spotter: str        # without the skimmer mark "-#"
    freq: float         # kHz
    dx: str
    comment: str
    hhmm: str           # time from the spot line (UTC), only informative
    skimmer: bool       # spotter was a CW skimmer (RBN, "-#")
    band: str           # "" = outside the amateur bands
    mode: str           # "" = unknown


def clean_text(text: str, limit: int = MAX_COMMENT) -> str:
    """Printable ASCII only, single spaces, at most limit characters."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = "".join(c if 32 <= ord(c) < 127 else " " for c in text)
    return " ".join(text.split())[:limit].rstrip()


def clean_call(call: str) -> str | None:
    call = call.strip().upper()
    if len(call) > 16 or not CALL_RE.match(call):
        return None
    return call


def band_of(freq_khz: float) -> str:
    for name, lo, hi in BANDS:
        if lo <= freq_khz <= hi:
            return name
    return ""


def mode_of(freq_khz: float, comment: str) -> str:
    m = _MODE_RE.search(comment.upper())
    if m:
        return _MODE_MAP[m.group(1)]
    for dial in FT8_DIAL:
        if dial <= freq_khz <= dial + 3:
            return "FT8"
    for dial in FT4_DIAL:
        if dial <= freq_khz <= dial + 3:
            return "FT4"
    for lo, hi in CW_SEGMENTS:              # upper edge belongs to the next segment
        if lo <= freq_khz < hi:
            return "CW"
    for lo, hi in DIGI_SEGMENTS:
        if lo <= freq_khz < hi:
            return DIGI
    for lo, hi in FM_SEGMENTS:              # before phone: 29.6 MHz FM lies in the 10 m phone part
        if lo <= freq_khz <= hi:
            return "FM"
    for lo, hi in PHONE_SEGMENTS:
        if lo <= freq_khz <= hi:
            return "SSB"
    return ""


def parse(line: str) -> Spot | None:
    """One line from the cluster -> Spot, or None (not a spot / implausible)."""
    m = SPOT_RE.match(line.strip())
    if not m:
        return None
    raw_spotter = m.group("spotter").upper()
    skimmer = "#" in raw_spotter
    spotter = clean_call(SSID_RE.sub("", raw_spotter))     # OE3GAS-2, DK9IP-#
    dx = clean_call(m.group("dx"))
    if not spotter or not dx:
        return None
    try:
        freq = float(m.group("freq"))
    except ValueError:
        return None
    if not 1000 <= freq <= 500000:          # 1 MHz ... 500 MHz in kHz
        return None
    comment = clean_text(m.group("comment"))
    return Spot(spotter=spotter, freq=freq, dx=dx, comment=comment,
                hhmm=m.group("time"), skimmer=skimmer, band=band_of(freq),
                mode=mode_of(freq, comment))
