"""CR48: beacon of the mailbox - text, "Mail for:" list, path, console command."""

from __future__ import annotations

import asyncio
import dataclasses
import unittest

from tinybox import beacon, config
from tinybox.adapters import agw as agwmod
from tinybox.ax25 import frame as ax
from tests.test_tinybox import ROOT, make_app


class FakeRadio:
    def __init__(self) -> None:
        self.connected = asyncio.Event()
        self.connected.set()
        self.sent: list[tuple[str, str, list]] = []

    def send_ui(self, dest, text, path=None):
        self.sent.append((dest, text, list(path or [])))


def mail(app, to, type="P"):
    return app.service.create(from_call="OE3XYZ", to_call=to, type=type, subject="s",
                              body="b", origin="telnet")


class BeaconTests(unittest.TestCase):
    def app(self, **kw):
        app = make_app()
        app.cfg.beacon = dataclasses.replace(config.BeaconCfg(), enabled=True, **kw)
        return app

    def test_config(self):
        cfg = config.load(ROOT / "tinybox.conf.example")
        self.assertFalse(cfg.beacon.enabled)
        self.assertEqual((cfg.beacon.dest, cfg.beacon.interval_min), ("BEACON", 30))
        self.assertEqual(cfg.beacon.text, "TinyBox {call} - connect for mail and chat")

    def test_text_without_and_with_mail(self):
        app = self.app()
        self.assertEqual(beacon.beacon_text(app.cfg, app.service),
                         "TinyBox OE3GAS-1 - connect for mail and chat")
        mail(app, "OE3TEC-9")
        mail(app, "OE1ABC")
        mail(app, "OE3TEC")                       # same call, other SSID: once
        mail(app, "ALL", type="B")                # bulletins do not count
        self.assertEqual(beacon.beacon_text(app.cfg, app.service),
                         "TinyBox OE3GAS-1 - connect for mail and chat - Mail for: OE1ABC OE3TEC")
        app.cfg.beacon = dataclasses.replace(app.cfg.beacon, mail_list=False)
        self.assertNotIn("Mail for", beacon.beacon_text(app.cfg, app.service))

    def test_read_mail_and_empty_text(self):
        app = self.app(text="")
        self.assertEqual(beacon.beacon_text(app.cfg, app.service), "")
        i = mail(app, "OE3TEC")
        self.assertEqual(beacon.beacon_text(app.cfg, app.service), "Mail for: OE3TEC")
        app.service.read(i, "OE3TEC", sysop=False)           # read: not new any more
        self.assertEqual(beacon.beacon_text(app.cfg, app.service), "")

    def test_too_many_calls(self):
        app = self.app()
        for n in range(60):
            mail(app, f"OE{n % 10}A{n:02d}")
        text = beacon.beacon_text(app.cfg, app.service)
        self.assertLessEqual(len(text.encode()), beacon.MAX_INFO)
        self.assertRegex(text, r" \+\d+$")

    def test_send_now_and_console(self):
        app = self.app(path=["WIDE1-1"])
        app.agw = FakeRadio()
        mail(app, "OE3TEC")
        b = app.beacon = beacon.Beacon(app)
        self.assertIn("Mail for: OE3TEC", b.send_now())
        self.assertEqual(app.agw.sent[0][0], "BEACON")
        self.assertEqual(app.agw.sent[0][2], ["WIDE1-1"])
        app.agw.connected.clear()
        self.assertEqual(b.send_now(), "")                    # no radio: nothing
        from tinybox.adapters import sysop
        out = []
        console = sysop.SysopConsole.__new__(sysop.SysopConsole)
        console.app, console.out = app, lambda *lines: out.extend(lines)
        app.agw.connected.set()
        console.cmd_beacon("")
        self.assertTrue(out[0].startswith("Beacon to BEACON: TinyBox OE3GAS-1"))
        self.assertIn("every 30 min, 2 sent", out[1])

    def test_agw_ui_with_path(self):
        app = make_app()
        ad = agwmod.AgwAdapter(app)
        sent = []
        ad.send = sent.append
        ad.send_ui("BEACON", "hallo", ["WIDE1-1", "WIDE2-1"])
        f = sent[0]
        self.assertEqual((f.kind, f.call_to), ("V", "BEACON"))
        self.assertEqual(f.data[0], 2)
        self.assertEqual(f.data[1:11].rstrip(b"\0"), b"WIDE1-1")
        self.assertEqual(f.data[21:], b"hallo")
        ad.send_ui("BEACON", "direkt")
        self.assertEqual(sent[1].kind, "M")

    def test_kiss_ui_path(self):
        f = ax.ui_frame("BEACON", "OE3GAS-1", b"x", path=["WIDE1-1"])
        dest, src, path, _ = ax.peek(f.encode())
        self.assertEqual((dest, src, path), ("BEACON", "OE3GAS-1", ["WIDE1-1"]))

    def test_bad_config(self):
        import tempfile
        from pathlib import Path
        base = (ROOT / "tinybox.conf.example").read_text(encoding="utf-8")
        for old, new in (("interval_min = 30", "interval_min = 1"),
                         ("path         =   ", "path = A B C"),
                         ("dest         = BEACON", "dest = NO_GOOD")):
            self.assertIn(old, base)
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp) / "t.conf"
                p.write_text(base.replace(old, new, 1), encoding="utf-8")
                with self.assertRaises(config.ConfigError) as ctx:
                    config.load(p)
                self.assertIn("[beacon]", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
