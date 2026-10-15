"""Beacon of the mailbox (CR48): a UI frame from the mailbox call every
[beacon] interval_min minutes, e.g.

    fm OE3GAS-1 to BEACON <UI>: TinyBox OE3GAS-1 - connect for mail and chat - Mail for: OE1ABC OE3TEC

With mail_list = yes the calls that have new (unread) private mail here are
appended - as the classic BBS "Mail for:" beacon. Only local mail counts (not
mail waiting to be forwarded or held). A frame carries at most MAX_INFO bytes:
calls that do not fit are counted ("+3").

{call} in the text is the mailbox call, {qth} the place of [station] qth.
"""

from __future__ import annotations

import asyncio
import logging

from .config import base_call

log = logging.getLogger(__name__)

MAX_INFO = 256            # info bytes of one UI frame (AX.25 default N1)
MAIL_PREFIX = "Mail for:"


def mail_calls(service) -> list[str]:
    """Calls (without SSID) with unread local private mail, sorted."""
    return sorted({base_call(m.to_call) for m in service.store.list_messages()
                   if m.type == "P" and m.status == "N" and m.fwd == ""})


def beacon_text(cfg, service) -> str:
    """The text of the next beacon ('' = nothing to send)."""
    b, st = cfg.beacon, cfg.station
    try:
        text = b.text.format(call=st.mailbox_call, qth=st.qth)
    except (KeyError, IndexError, ValueError):
        text = b.text                              # a brace in the text: as it is
    calls = mail_calls(service) if b.mail_list else []
    if not calls:
        return text[:MAX_INFO]
    head = (text + " - " if text else "") + MAIL_PREFIX
    out = head
    for i, call in enumerate(calls):
        rest = len(calls) - i - 1
        more = f" +{rest}" if rest else ""
        if len((out + " " + call + more).encode("utf-8")) > MAX_INFO:
            return (out + f" +{len(calls) - i}")[:MAX_INFO]
        out += " " + call
    return out


class Beacon:
    def __init__(self, app) -> None:
        self.app = app
        self.sent = 0
        self.last_text = ""

    def send_now(self) -> str:
        """Send one beacon at once (also the console command BEACON). Returns
        the text, '' if there was nothing to send or no radio."""
        text = beacon_text(self.app.cfg, self.app.service)
        agw = getattr(self.app, "agw", None)
        if not text or agw is None or not agw.connected.is_set():
            return ""
        b = self.app.cfg.beacon
        agw.send_ui(b.dest, text, b.path)
        self.sent += 1
        self.last_text = text
        log.info("beacon to %s%s: %s", b.dest, f" via {','.join(b.path)}" if b.path else "", text)
        return text

    async def run(self) -> None:
        b = self.app.cfg.beacon
        await asyncio.sleep(b.first_after_sec)
        while True:
            try:
                self.send_now()
            except Exception:                    # a beacon must never stop the mailbox
                log.exception("beacon not sent")
            await asyncio.sleep(b.interval_min * 60)
