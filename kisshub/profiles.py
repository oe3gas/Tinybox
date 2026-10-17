"""TNC profiles: how to reach the command prompt and switch into KISS.

A profile is data, not code: a list of wake steps (tried in order until one
gets an answer) and a list of init steps (each one must get its answer).
kisshub.conf can replace the init lines without touching code.

PK-232 / PK-232MBX - taken from pk232py (oe3gas/pk232py), measured on three
devices there (firmware 30.DEC.88, 01.AUG.91, 13.SEP.95):
    - serial 8N1, no XON/XOFF and no RTS/CTS on the port, DTR and RTS HIGH
      (P54.2: with DTR/RTS low the TNC did not answer, PuTTY with them high did)
    - wake chain (serial_manager.py, P43/P54): '*' (autobaud after power-up),
      CR, Ctrl-C + CR (COMMAND character, leaves Converse), XON + CR (a stray
      XOFF stops the TNC's own output), host mode exit (recovery frame +
      HOST OFF frame), and here also the KISS exit C0 FF C0 - after a hub run
      the TNC may still be in KISS
    - KISS init after TRM section 4.7.1 (pk232py comm/kiss.py), plus VHF ON and
      HBAUD 1200 (modes/packet_vhf.py): the 1200 Bd Bell 202 modem.
      EXPERT ON first (Gerhard, 14.10.2026): some of the commands are expert
      commands - without it the PK-232 answers "?EXPERT command" and ignores them.
      Order checked by Gerhard on the device; RESTART after AWLEN/PARITY (TRM) is
      not needed
      Tested on the air 14.10.2026 with device A, firmware Release 13.SEP.95
      (VHF, 1200 Bd). Other devices / firmware not yet.

Kenwood TM-D710: the TNC must be in packet mode (TNC key on the panel), then
"KISS ON" + "RESTART" in terminal mode. TH-D74 / TH-D75: KISS is switched on in
the radio's menu - nothing to send. TNC2 with a pure KISS EPROM: nothing to send.
All Kenwood/TNC2 lines are from the manuals and still to be tried (K9/K10).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

CR = b"\r"
CMD_PROMPT = b"cmd:"
KISS_EXIT = bytes((0xC0, 0xFF, 0xC0))

# PK-232 Host Mode frames (pk232py comm/constants.py)
PK_HOST_OFF = bytes((0x01, 0x4F, ord("H"), ord("O"), ord("N"), 0x17))
PK_RECOVERY = bytes((0x01, 0x01, 0x4F, ord("G"), ord("G"), 0x17))
CTRL_C = b"\x03"
XON = b"\x11"


@dataclass(frozen=True)
class Step:
    """Send `send`, then wait up to `timeout` s until one of `expect` arrives.
    Empty `expect`: just wait `timeout` (e.g. the line that enters KISS)."""
    send: bytes
    expect: tuple[bytes, ...] = (CMD_PROMPT,)
    timeout: float = 3.0
    note: str = ""


def line(text: str, timeout: float = 3.0, expect: tuple[bytes, ...] = (CMD_PROMPT,)) -> Step:
    return Step(text.encode("ascii") + CR, expect, timeout, text)


@dataclass(frozen=True)
class Profile:
    name: str
    serial_baud: int = 9600
    dtr: bool = True
    rts: bool = True
    wake: tuple[Step, ...] = ()        # empty: the TNC is in KISS by itself
    init: tuple[Step, ...] = ()
    exit_kiss: bool = True             # C0 FF C0 when kisshub stops
    exit_lines: tuple[Step, ...] = ()  # sent after leaving KISS
    settle_sec: float = 1.0            # after the last init line, before KISS frames
    notes: str = ""
    display: str = ""                  # name for status displays, e.g. "PK-232"
    kiss_params: bool = True           # send TXDELAY/P/SlotTime ([kiss] send_params default)
    tunnel: str = "no"                 # VARA: no | connected | all (see VARA_FM)


PK232 = Profile(
    name="pk232", display="PK-232",
    serial_baud=9600,
    wake=(
        Step(b"*", (CMD_PROMPT, b"AEA", b"PK-232", b"Copyright"), 2.0, "autobaud '*'"),
        Step(CR, (CMD_PROMPT,), 1.5, "CR"),
        Step(CTRL_C + CR, (CMD_PROMPT,), 2.0, "Ctrl-C (Converse)"),
        Step(XON + CR, (CMD_PROMPT,), 2.0, "XON (stopped by XOFF)"),
        Step(KISS_EXIT + b"\x00" * 2, (), 2.0, "leave KISS"),
        Step(CR, (CMD_PROMPT,), 2.0, "CR after leaving KISS"),
        Step(PK_RECOVERY + PK_HOST_OFF, (), 1.0, "leave Host Mode"),
        Step(CR, (CMD_PROMPT,), 2.0, "CR after leaving Host Mode"),
    ),
    init=(
        # order and content checked on the device by Gerhard (14.10.2026):
        # EXPERT ON first (RAWHDLC, HPOLL, PPERSIST need it); VHF ON and HBAUD 1200
        # are the power-on defaults, sent anyway to be sure; RESTART not needed
        line("EXPERT ON"),
        line("VHF ON"),
        line("HBAUD 1200"),
        line("AWLEN 8"),
        line("PARITY 0"),
        line("CONMODE TRANS"),
        line("TRACE OFF"),
        line("HID OFF"),
        line("BEACON EVERY 0"),
        line("PACKET"),
        line("RAWHDLC ON"),
        line("HPOLL OFF"),
        line("PPERSIST ON"),
        # KISS ON gives no cmd: of its own on the device (17.10.2026): until then
        # every answer was one step late, so KISS ON only matched the cmd: of
        # PPERSIST; after a wake via 'CR after leaving KISS' the answers were in
        # step and the init failed at KISS ON. So: just its echo.
        line("KISS ON", timeout=1.0, expect=()),
        line("HOST ON", timeout=1.5, expect=()),       # from here on: KISS, no prompt
    ),
    exit_kiss=True,
    exit_lines=(line("KISS OFF"),),                    # leave it as pk232py expects it
    notes="PK-232/PK-232MBX, VHF port 1200 Bd",
)

TM_D710 = Profile(
    name="tm-d710", display="TM-D710",
    serial_baud=9600,
    wake=(Step(CR, (CMD_PROMPT,), 2.0, "CR"),
          Step(KISS_EXIT + CR, (CMD_PROMPT,), 3.0, "leave KISS")),
    init=(line("KISS ON"), line("RESTART", timeout=2.0, expect=())),
    exit_kiss=True,
    notes="Kenwood TM-D710: TNC key -> packet mode first",
)

TH_D74 = Profile(name="th-d74", display="TH-D74", serial_baud=9600, exit_kiss=False,
                 notes="Kenwood TH-D74: KISS on in the menu")
TH_D75 = Profile(name="th-d75", display="TH-D75", serial_baud=9600, exit_kiss=False,
                 notes="Kenwood TH-D75: KISS on in the menu")
TNC2_KISS = Profile(name="tnc2-kiss", display="TNC2", serial_baud=9600, exit_kiss=False,
                    notes="TNC2 with pure KISS EPROM")
GENERIC = Profile(name="generic", display="KISS TNC", exit_kiss=False, notes="already in KISS")


# VARA FM / VARA HF (EA5HVK): KISS-TCP on port 8100 ("KISS interface" in VARA Setup).
# Not a transparent TNC: VARA takes the AX.25 header apart and accepts UI frames
# only - SABM/SABME/I/RR are refused with "Wrong KISS frame" (tested 17.10.2026).
# Frame type 2 ("Generic Data", C0 02 ... C0, up to 5000 bytes) carries any bytes,
# so kisshub tunnels the other frames in it (TUNNEL_MAGIC + the AX.25 frame) and
# unpacks them on the other side; TinyBox and the client do not notice. Both
# stations need kisshub with the tunnel. VARA does its own channel access (DCD,
# persistence 0.3): no KISS parameters are sent.
#   tunnel = connected   UI frames as normal type 0 (readable for any VARA KISS
#                        user), everything else through type 2
#   tunnel = all         every frame through type 2
VARA_FM = Profile(name="vara-fm", display="VARA FM", exit_kiss=False, kiss_params=False,
                  tunnel="connected", settle_sec=0.2,
                  notes="VARA FM KISS-TCP (port 8100), connected mode tunnelled in type 2")
VARA_HF = dataclasses.replace(VARA_FM, name="vara-hf", display="VARA HF",
                              notes="VARA HF KISS-TCP (port 8100), connected mode tunnelled in type 2")

PROFILES = {p.name: p for p in (PK232, TM_D710, TH_D74, TH_D75, TNC2_KISS, GENERIC,
                                VARA_FM, VARA_HF)}
TUNNEL_MODES = ("no", "connected", "all")


def with_init_lines(p: Profile, lines: list[str]) -> Profile:
    """kisshub.conf 'init_lines': replace the init. The last line enters KISS and
    gets no prompt back."""
    steps = [line(t) for t in lines[:-1]]
    if lines:
        steps.append(line(lines[-1], timeout=1.5, expect=()))
    return dataclasses.replace(p, init=tuple(steps))
