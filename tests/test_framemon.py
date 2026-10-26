"""CR52: frame monitor of the TinyBox web GUI."""

from __future__ import annotations

import asyncio
import logging
import unittest

from tinybox import framemon, logsetup
from tinybox.adapters.web import Hub, HubLogHandler
from prcore.ax25 import frame as ax


class EntryTests(unittest.TestCase):
    def test_kinds(self):
        e = framemon.entry(ax.ui_frame("TBCHAT-1", "OE3GAS-1", b"%Q OE3TEC 4").encode(),
                           tx=True, mycall="OE3GAS-1")
        self.assertEqual((e["typ"], e["kind"], e["tx"]), ("UI", "quality", True))
        e = framemon.entry(ax.ui_frame("ID", "OE3GAS-1", b"TinyBox").encode(),
                           tx=True, mycall="OE3GAS-1")
        self.assertEqual(e["kind"], "beacon")
        e = framemon.entry(ax.ui_frame("TBMAIL", "OE3GAS-1", b"OE3TEC 1 new").encode(),
                           tx=True, mycall="OE3GAS-1")
        self.assertEqual(e["kind"], "mail")

    def test_i_frames_mod8_and_mod128(self):
        f = ax.i_frame("OE3TEC", "OE3GAS-1", 3, 5, b"Hallo\r", path=["OE1XAR"])
        e = framemon.entry(f.encode(), tx=False, mycall="X")
        self.assertEqual((e["typ"], e["text"], e["via"], e["kind"]), ("I 3,5", "Hallo", ["OE1XAR"], ""))
        f = ax.i_frame("OE3TEC", "OE3GAS-1", 70, 5, b"//SYNC 1\r", modulo=128)
        for mod in (True, None):                      # known link, or guessed from the PID
            e = framemon.entry(f.encode(), tx=True, mycall="X", mod128=mod)
            self.assertEqual((e["typ"], e["text"], e["kind"]), ("I 70,5", "//SYNC 1", "proto"))
        e = framemon.entry(ax.s_frame("REJ", "OE3TEC", "OE3GAS-1", nr=100, modulo=128).encode(),
                           tx=False, mycall="X")
        self.assertEqual(e["typ"], "REJ 100")

    def test_paclen_and_hex(self):
        payload = bytes(range(256))[:64]               # binary, like a picture upload
        for mod in (False, True):
            f = ax.i_frame("OE3TEC", "OE3GAS-1", 8 if mod else 1, 2, payload,
                           modulo=128 if mod else 8)
            e = framemon.entry(f.encode(), tx=False, mycall="X", mod128=mod)
            self.assertEqual((e["len"], e["hex"]), (64, payload.hex()))
        e = framemon.entry(ax.ui_frame("APRS", "OE3TEC", b"!48").encode(), tx=False, mycall="X")
        self.assertEqual((e["len"], e["hex"]), (3, "213438"))
        e = framemon.entry(ax.s_frame("RR", "OE3TEC", "OE3GAS-1", nr=4).encode(),
                           tx=False, mycall="X")
        self.assertNotIn("len", e)                     # no payload, no [n]
        self.assertNotIn("hex", e)

    def test_garbage_and_no_listener(self):
        self.assertIsNone(framemon.entry(b"\x01\x02", tx=False, mycall="X"))
        framemon.emit(b"\x01\x02", tx=False, mycall="X")          # no handler: nothing


class HubTests(unittest.TestCase):
    def test_frames_and_session_text_reach_the_hub(self):
        loop = asyncio.new_event_loop()
        try:
            hub = Hub()
            handler = HubLogHandler(hub, loop)
            framemon.flog.addHandler(handler)
            mon = logging.getLogger("tinybox.monitor")
            mon.addHandler(handler)
            old = mon.level
            mon.setLevel(logging.INFO)
            try:
                framemon.emit(ax.ui_frame("TBCHAT-1", "OE3GAS-1", b"#1 hi").encode(),
                              tx=True, mycall="OE3GAS-1")
                with logsetup.session_context("#7 OE3TEC"):
                    mon.info("> %s", "Welcome")
            finally:
                framemon.flog.removeHandler(handler)
                mon.removeHandler(handler)
                mon.setLevel(old)
            items = list(hub.backlog)
            self.assertEqual(items[0]["type"], "frame")
            self.assertEqual((items[0]["dst"], items[0]["kind"]), ("TBCHAT-1", "chat"))
            self.assertIn({"call": "OE3TEC", "dir": ">", "text": "Welcome"},
                          [{k: i.get(k) for k in ("call", "dir", "text")} for i in items])
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
