"""Test cases T01-T25 (see the concept, section "Test-Tool fwdsim").

Every case returns a list of checks. A check with ok=None was skipped
(e.g. no tinybox.db to look into). Cases marked manual only print what to do.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Awaitable, Callable

from .harness import Harness
from .model import make_rline, rline_call, utc_now
from .protocol import REJECT
from .session import Faults, SessionResult


@dataclass
class Check:
    name: str
    ok: bool | None
    detail: str = ""


@dataclass
class Case:
    id: str
    title: str
    since: str
    func: Callable[[Harness], Awaitable[list[Check]]] | None = None
    manual: str = ""


CASES: dict[str, Case] = {}


def case(id: str, title: str, since: str):
    def deco(func):
        CASES[id] = Case(id, title, since, func)
        return func
    return deco


def manual(id: str, title: str, since: str, how: str) -> None:
    CASES[id] = Case(id, title, since, None, how)


# --- check helpers ---------------------------------------------------------------

def session_ok(r: SessionResult | None, what: str = "session") -> Check:
    if r is None:
        return Check(what, False, "no session within the waiting time")
    return Check(what, r.ok, r.error or f"mode {r.mode}, sent {r.sent}, received {r.received}")


def calls(rlines: list[str]) -> list[str]:
    return [rline_call(x) for x in rlines]


def count(name: str, items: list | None, want: int) -> Check:
    if items is None:
        return Check(name, None, "no tinybox.db configured (--tinybox-db)")
    return Check(name, len(items) == want, f"found {len(items)}, expected {want}")


def path(name: str, items: list | None, want: list[str]) -> Check:
    if items is None:
        return Check(name, None, "no tinybox.db configured")
    if not items:
        return Check(name, False, "message not found")
    got = calls(items[0]["rlines"])
    return Check(name, got == want, f"R: lines {got}, expected {want}")


def field_is(name: str, items: list | None, key: str, want) -> Check:
    if items is None:
        return Check(name, None, "no tinybox.db configured")
    if not items:
        return Check(name, False, "message not found")
    got = items[0].get(key)
    return Check(name, got == want, f"{key} = {got!r}, expected {want!r}")


def hop_msgs(h: Harness, subject: str) -> list[dict]:
    return [{"rlines": m.rlines, "status": m.status} for m in h.hop.find(subject=subject)]


def remote_msgs(h: Harness, subject: str) -> list[dict]:
    return [{"rlines": m.rlines, "status": m.status} for m in h.remote.find(subject=subject)]


BODY = "Test message from fwdsim.\nSecond line."


# --- TinyBox -> network ----------------------------------------------------------

@case("T01", "TinyBox -> P an OE3GAS", "F4")
async def t01(h: Harness) -> list[Check]:
    s = h.tag("T01")
    await h.target.submit("P", h.hop.call, h.hop.haddr, s, BODY)
    r = await h.target_calls_hop()
    got = hop_msgs(h, s)
    return [session_ok(r), count("OE3GAS has it once", got, 1),
            path("R: lines", got, [h.hop.call, h.target.call])]


@case("T02", "TinyBox -> P an DL0XTC ueber den Hop", "F4")
async def t02(h: Harness) -> list[Check]:
    s = h.tag("T02")
    await h.target.submit("P", "DL1ABC", h.remote.haddr, s, BODY)
    r = await h.target_calls_hop()
    got = remote_msgs(h, s)
    return [session_ok(r), count("DL0XTC has it once", got, 1),
            path("R: lines", got, [h.remote.call, h.hop.call, h.target.call])]


@case("T03", "TinyBox -> Bulletin @WW", "F4")
async def t03(h: Harness) -> list[Check]:
    s = h.tag("T03")
    await h.target.submit("B", "ALL", "WW", s, BODY)
    r = await h.target_calls_hop()
    return [session_ok(r), count("OE3GAS has it once", hop_msgs(h, s), 1),
            count("DL0XTC has it once", remote_msgs(h, s), 1)]


# --- network -> TinyBox ----------------------------------------------------------

@case("T04", "OE3GAS -> P an OE3XTC", "F3")
async def t04(h: Harness) -> list[Check]:
    m = h.hop.create("P", "OE1ABC", h.target.haddr, h.tag("T04"), BODY)
    r = await h.hop_calls_target()
    got = h.target.find(bid=m.bid)
    return [session_ok(r), count("in TinyBox once", got, 1),
            field_is("type P", got, "type", "P"), field_is("origin", got, "origin", "forward"),
            path("R: lines", got, [h.target.call, h.hop.call])]


@case("T05", "DL0XTC -> P an OE3XTC ueber OE3GAS", "F3")
async def t05(h: Harness) -> list[Check]:
    m = h.remote.create("P", "OE1ABC", h.target.haddr, h.tag("T05"), BODY)
    r = await h.hop_calls_target()
    got = h.target.find(bid=m.bid)
    return [session_ok(r), count("in TinyBox once", got, 1),
            path("R: lines", got, [h.target.call, h.hop.call, h.remote.call])]


@case("T06", "Bulletins @WW (OE3GAS) und @AUT (DL0XTC)", "F3")
async def t06(h: Harness) -> list[Check]:
    a = h.hop.create("B", "ALL", "WW", h.tag("T06", "WW"), BODY)
    b = h.remote.create("B", "ALL", "AUT", h.tag("T06", "AUT"), BODY)
    r = await h.hop_calls_target()
    ga, gb = h.target.find(bid=a.bid), h.target.find(bid=b.bid)
    return [session_ok(r), count("@WW in TinyBox", ga, 1), field_is("@WW is B", ga, "type", "B"),
            count("@AUT in TinyBox", gb, 1)]


@case("T07", "Reverse Forward: beide Richtungen in einer Sitzung", "F4")
async def t07(h: Harness) -> list[Check]:
    m = h.hop.create("P", "OE1ABC", h.target.haddr, h.tag("T07", "to TinyBox"), BODY)
    s = h.tag("T07", "to OE3GAS")
    await h.target.submit("P", h.hop.call, h.hop.haddr, s, BODY)
    r = await h.target_calls_hop()
    return [session_ok(r),
            Check("OE3GAS received", bool(r and r.received), str(r.received if r else "")),
            Check("OE3GAS sent in the same session", bool(r and r.sent.get(m.bid)),
                  str(r.sent if r else "")),
            count("TinyBox has OE3GAS's mail", h.target.find(bid=m.bid), 1),
            count("OE3GAS has TinyBox's mail", hop_msgs(h, s), 1)]


# --- robustness ------------------------------------------------------------------

@case("T08", "Dieselbe BID zweimal", "F3")
async def t08(h: Harness) -> list[Check]:
    m = h.hop.create("P", "OE1ABC", h.target.haddr, h.tag("T08"), BODY)
    r1 = await h.hop_calls_target()
    h.store.set_queue(h.hop.call, m.id, h.target.call, "open")      # offer it again
    r2 = await h.hop_calls_target()
    return [session_ok(r1, "first session"), session_ok(r2, "second session"),
            Check("second offer rejected with '-'", r2.sent.get(m.bid) == REJECT,
                  f"answer {r2.sent.get(m.bid)!r}"),
            count("stored once", h.target.find(bid=m.bid), 1)]


@case("T09", "Schleife: R:-Zeile von OE3XTC", "F3")
async def t09(h: Harness) -> list[Check]:
    fake = make_rline(utc_now() - timedelta(hours=1), h.target.haddr, "Hollabrunn", 9,
                      f"9_{h.target.call}")
    m = h.hop.create("P", "OE1ABC", h.target.haddr, h.tag("T09"), BODY, extra_rlines=[fake])
    r = await h.hop_calls_target()
    got = h.target.find(bid=m.bid)
    return [session_ok(r), field_is("held (H)", got, "fwd", "H")]


@case("T10", "Split Horizon: Bulletin nicht zurueck an OE3GAS", "F4")
async def t10(h: Harness) -> list[Check]:
    m = h.hop.create("B", "ALL", "WW", h.tag("T10"), BODY)
    await h.hop_calls_target()
    r = await h.target_calls_hop(wait=min(h.cfg.wait_for_tinybox, 30))
    if r is None:
        return [Check("not offered back", True, "TinyBox did not call (nothing to send)")]
    return [Check("not offered back", m.bid not in r.proposed_to_us,
                  f"offered: {r.proposed_to_us}")]


@case("T11", "SID ohne F -> MBL/RLI-ASCII", "F3")
async def t11(h: Harness) -> list[Check]:
    m = h.hop.create("P", "OE1ABC", h.target.haddr, h.tag("T11"), BODY)
    r = await h.hop_calls_target(Faults(sid="[FWDSIM-0.1-HM$]"))
    return [session_ok(r), Check("ASCII mode", r.mode == "rli", f"mode {r.mode}"),
            count("in TinyBox", h.target.find(bid=m.bid), 1)]


@case("T12", "SID mit B1 -> TinyBox bleibt bei ASCII", "F3")
async def t12(h: Harness) -> list[Check]:
    m = h.hop.create("P", "OE1ABC", h.target.haddr, h.tag("T12"), BODY)
    r = await h.hop_calls_target(Faults(sid="[FWDSIM-0.1-B1FHM$]"))
    fa = [x for x in r.transcript if x.startswith("< FA ")]
    return [session_ok(r), Check("no compressed proposals (FA)", not fa, str(fa[:2])),
            count("in TinyBox", h.target.find(bid=m.bid), 1)]


@case("T13", "12 Nachrichten in mehreren Bloecken", "F3")
async def t13(h: Harness) -> list[Check]:
    ms = [h.hop.create("P", "OE1ABC", h.target.haddr, h.tag("T13", str(i)), BODY)
          for i in range(12)]
    r = await h.hop_calls_target()
    blocks = [x for x in r.transcript if x.startswith("> F>")]
    found = [h.target.find(bid=m.bid) for m in ms]
    checks = [session_ok(r), Check("at least 3 blocks", len(blocks) >= 3, f"{len(blocks)} blocks")]
    if any(f is None for f in found):
        checks.append(Check("all 12 in TinyBox", None, "no tinybox.db configured"))
    else:
        n = sum(1 for f in found if len(f) == 1)
        checks.append(Check("all 12 in TinyBox", n == 12, f"{n} of 12"))
    return checks


@case("T14", "OE3GAS antwortet FS +-=", "F4")
async def t14(h: Harness) -> list[Check]:
    s = [h.tag("T14", str(i)) for i in (1, 2, 3)]
    for x in s:
        await h.target.submit("P", h.hop.call, h.hop.haddr, x, BODY)
    r1 = await h.target_calls_hop(Faults(fs="+-="))
    first = [len(hop_msgs(h, x)) for x in s]
    r2 = await h.target_calls_hop()
    second = [len(hop_msgs(h, x)) for x in s]
    return [session_ok(r1, "first session"),
            Check("after 1st: only '+' arrived", first == [1, 0, 0], str(first)),
            session_ok(r2, "second session"),
            Check("after 2nd: '=' arrived, '-' not again", second == [1, 0, 1], str(second))]


@case("T15", "Abbruch mitten in einer Nachricht", "F3")
async def t15(h: Harness) -> list[Check]:
    m = h.hop.create("P", "OE1ABC", h.target.haddr, h.tag("T15"), BODY + "\n" + "x" * 200)
    await h.hop_calls_target(Faults(abort_after=40))
    after_abort = h.target.find(bid=m.bid)
    r = await h.hop_calls_target()
    return [count("nothing stored after abort", after_abort, 0), session_ok(r, "retry"),
            count("stored once after retry", h.target.find(bid=m.bid), 1)]


@case("T16", "Formfehler", "F3")
async def t16(h: Harness) -> list[Check]:
    checks: list[Check] = []
    for label, faults in (("FB with 6 fields", Faults(fb_fields=6)),
                          ("wrong F> checksum", Faults(bad_checksum=True)),
                          ("no Ctrl-Z", Faults(no_ctrl_z=True))):
        m = h.hop.create("P", "OE1ABC", h.target.haddr, h.tag("T16", label), BODY)
        r = await h.hop_calls_target(faults)
        checks.append(Check(f"{label}: session ended with error", not r.ok, r.error or "no error"))
        checks.append(count(f"{label}: nothing stored", h.target.find(bid=m.bid), 0))
        h.drop_queue(m.bid)
    m = h.hop.create("P", "OE1ABC", h.target.haddr, "T16 " + h.run_id + " " + "L" * 100, BODY)
    await h.hop_calls_target()
    got = h.target.find(bid=m.bid)
    if got is None:
        checks.append(Check("subject 100 chars", None, "no tinybox.db configured"))
    else:
        ok = not got or len(got[0]["subject"]) <= 80
        checks.append(Check("subject 100 chars: cut to 80 or rejected", ok,
                            f"stored {len(got[0]['subject'])} chars" if got else "rejected"))
    h.drop_queue(m.bid)
    m = h.hop.create("P", "OE1ABC", h.target.haddr, h.tag("T16", "too large"),
                     "\n".join(["y" * 70] * 300))                  # about 21 kB
    r = await h.hop_calls_target()
    checks.append(Check("too large: rejected", r.sent.get(m.bid) == REJECT,
                        f"answer {r.sent.get(m.bid)!r}"))
    checks.append(count("too large: not stored", h.target.find(bid=m.bid), 0))
    h.drop_queue(m.bid)
    return checks


manual("T17", "Fremder Call sendet eine SID", "F3",
       "Mit einem Terminalprogramm unter einem Call, der kein Partner ist, zu TinyBox "
       "verbinden und eine SID wie [FBB-7.0-FHM$] tippen. Erwartet: normale User-Sitzung, "
       "keine Forward-Antwort.")


@case("T18", "TinyBox -> P an unbekannte Adresse", "F4")
async def t18(h: Harness) -> list[Check]:
    s = h.tag("T18")
    await h.target.submit("P", "OE9ZZZ", "OE9ZZZ.#XYZ.ZZZ.ZZ", s, BODY)
    r = await h.target_calls_hop(wait=min(h.cfg.wait_for_tinybox, 60))
    local = h.target.find(subject=s)
    at_hop = hop_msgs(h, s)
    held_local = bool(local) and local[0].get("fwd") == "H"
    held_hop = bool(at_hop) and at_hop[0]["status"] == "H"
    if local is None and not at_hop:
        return [Check("held at TinyBox or default route", None,
                      "no tinybox.db configured and nothing arrived at OE3GAS")]
    return [Check("held at TinyBox or sent on the default route", held_local or held_hop,
                  f"TinyBox: {local}, OE3GAS: {at_hop}, session: {r.error if r else 'none'}")]


@case("T19", "Nachricht aelter als bid_days", "F3")
async def t19(h: Harness) -> list[Check]:
    old = utc_now() - timedelta(days=400)
    m = h.hop.create("P", "OE1ABC", h.target.haddr, h.tag("T19"), BODY, when=old)
    r = await h.hop_calls_target()
    return [session_ok(r), field_is("held (H)", h.target.find(bid=m.bid), "fwd", "H")]


@case("T20", "Prompt-Falle: Knoten-Text mit '>'", "F4")
async def t20(h: Harness) -> list[Check]:
    s = h.tag("T20")
    await h.target.submit("P", h.hop.call, h.hop.haddr, s, BODY)
    r = await h.target_calls_hop(Faults(prompt_trap=True))
    return [session_ok(r), count("OE3GAS has it", hop_msgs(h, s), 1)]


manual("T21", "Neustart mit voller Warteschlange", "F4",
       "Mehrere Mails an OE3GAS in TinyBox schreiben, TinyBox vor dem Forward beenden und neu "
       "starten, dann 'fwdsim run T01' bzw. 'fwdsim list OE3GAS': jede Mail genau einmal.")
manual("T22", "User eingeloggt waehrend einer Forward-Sitzung", "F3",
       "Per Telnet als User einloggen und L/R benutzen, gleichzeitig 'fwdsim run T13'. "
       "Erwartet: beide Sitzungen laufen ohne Fehler.")
manual("T23", "Fremd-Bulletin bei publish_to_brocast = no", "F3",
       "In tinybox.conf publish_to_brocast = no, 'fwdsim run T06', dann im brocast-Listener "
       "pruefen: die beiden T06-Bulletins erscheinen nicht.")


@case("T24", "CR LF und Latin-1-Umlaute", "F3")
async def t24(h: Harness) -> list[Check]:
    m = h.hop.create("P", "OE1ABC", h.target.haddr, h.tag("T24"),
                     "Gruesse: Grüße aus Linz äöü")
    r = await h.hop_calls_target(Faults(crlf=True, latin1=True))
    got = h.target.find(bid=m.bid)
    if got is None:
        return [session_ok(r), Check("umlauts intact", None, "no tinybox.db configured")]
    ok = bool(got) and "Grüße" in got[0]["body"]
    return [session_ok(r), Check("umlauts intact", ok, repr(got[0]["body"][:60]) if got else "missing")]


@case("T26", "ASCII-Modus mit Reverse Forward (F>)", "F4")
async def t26(h: Harness) -> list[Check]:
    m = h.hop.create("P", "OE1ABC", h.target.haddr, h.tag("T26", "to TinyBox"), BODY)
    s = h.tag("T26", "to OE3GAS")
    await h.target.submit("P", h.hop.call, h.hop.haddr, s, BODY)
    r = await h.hop_calls_target(Faults(sid="[FWDSIM-0.1-H$]"))
    return [session_ok(r), Check("ASCII mode", r.mode == "rli", f"mode {r.mode}"),
            count("TinyBox got OE3GAS's mail", h.target.find(bid=m.bid), 1),
            Check("F> sent by OE3GAS", "> F>" in r.transcript, ""),
            count("OE3GAS got TinyBox's mail via F>", hop_msgs(h, s), 1)]


@case("T27", "Altes R:-Format (nnn@BBS) mit eigenem Call", "F3")
async def t27(h: Harness) -> list[Check]:
    when = utc_now() - timedelta(hours=1)
    old = f"R:{when:%y%m%d/%H%M} 1530@{h.target.haddr}"
    m = h.hop.create("P", "OE1ABC", h.target.haddr, h.tag("T27"), BODY, extra_rlines=[old])
    r = await h.hop_calls_target()
    return [session_ok(r), field_is("held (H) as loop", h.target.find(bid=m.bid), "fwd", "H")]


@case("T28", "Ende mit /EX und ';'-Nullzeilen (Feature I)", "F3")
async def t28(h: Harness) -> list[Check]:
    m = h.hop.create("P", "OE1ABC", h.target.haddr, h.tag("T28", "ascii"),
                     "Zeile 1\n/EX\nZeile 3")
    r1 = await h.hop_calls_target(Faults(sid="[FWDSIM-0.1-H$]", eomb=True, null_lines=True))
    n = h.hop.create("P", "OE1ABC", h.target.haddr, h.tag("T28", "fbb"), BODY)
    r2 = await h.hop_calls_target(Faults(null_lines=True))
    got = h.target.find(bid=m.bid)
    checks = [session_ok(r1, "ASCII session"), count("ASCII: delivered", got, 1),
              session_ok(r2, "FBB session"), count("FBB: delivered", h.target.find(bid=n.bid), 1)]
    if got:
        checks.append(Check("body line /EX kept as text", "/EX" in got[0]["body"],
                            repr(got[0]["body"])))
    return checks


@case("T25", "@-Feld mit SSID wird erkannt", "F3")
async def t25(h: Harness) -> list[Check]:
    at = h.target.call + "-1." + h.target.haddr.split(".", 1)[1]
    m = h.hop.create("P", "OE1ABC", at, h.tag("T25"), BODY)
    r = await h.hop_calls_target()
    got = h.target.find(bid=m.bid)
    checks = [session_ok(r), count("delivered", got, 1)]
    if got:
        checks.append(Check("not held", got[0].get("fwd") != "H", f"fwd {got[0].get('fwd')!r}"))
    return checks
