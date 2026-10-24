"""TinyBox tests.  Run from E:\\Tinybox:  python -m unittest -v"""

from __future__ import annotations

import asyncio
import dataclasses
import tempfile
import unittest
from pathlib import Path

from tinybox import config
from tinybox.app import App
from tinybox.adapters import telnet
from tinybox.service import ServiceError
from tinybox.session import Session

ROOT = Path(__file__).resolve().parent.parent


def make_app(**mailbox_overrides) -> App:
    # the template from the repo, not the PC-specific tinybox.conf
    cfg = config.load(ROOT / "tinybox.conf.example")
    cfg.logging.monitor = False
    # the profile questions after the login (CR73) only where a test wants them
    mailbox_overrides.setdefault("ask_profile", False)
    cfg.mailbox = dataclasses.replace(cfg.mailbox, **mailbox_overrides)
    return App.create(cfg, db_path=":memory:")


class FakeTransport:
    def __init__(self) -> None:
        self.buf = ""
        self.closed = False

    def write(self, text: str) -> None:
        self.buf += text

    def close(self) -> None:
        self.closed = True

    def abort_output(self) -> None:
        pass

    def take(self) -> str:
        out, self.buf = self.buf, ""
        return out


def login(app: App, call: str) -> tuple[Session, FakeTransport]:
    t = FakeTransport()
    s = Session(call, app.service, app.cfg, t, origin="telnet",
                sysop=app.service.is_sysop_call(call))
    s.start()
    return s, t


def type_lines(s: Session, *lines: str) -> None:
    for line in lines:
        s.handle_line(line)


class ConfigTests(unittest.TestCase):
    def test_sample_config_loads(self):
        cfg = config.load(ROOT / "tinybox.conf.example")
        self.assertEqual(cfg.station.mailbox_call, "OE3GAS-1")
        self.assertTrue(cfg.mailbox.third_party)
        self.assertEqual(cfg.storage.data_dir, ROOT / "data")

    def test_callsigns(self):
        for ok in ("OE3GAS", "OE3GAS-1", "W1AW", "9A1AA", "DL0BN-15"):
            self.assertTrue(config.is_valid_call(ok), ok)
        for bad in ("ALL", "OE3GAS-16", "TOOLONG1", "OE3 GAS", "12345", ""):
            self.assertFalse(config.is_valid_call(bad), bad)

    def test_bad_config(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.conf"
            p.write_text("[station]\nmailbox_call = NOCALL\nsysop_call = OE3GAS\n")
            with self.assertRaises(config.ConfigError):
                config.load(p)
            p.write_text("[station]\nmailbox_call = OE3GAS-1\nsysop_call = OE3GAS\n"
                         "[telnet]\nhost = 0.0.0.0\n")
            with self.assertRaises(config.ConfigError):
                config.load(p)


class LogDirTests(unittest.TestCase):
    BASE = "[station]\nmailbox_call = OE3GAS-1\nsysop_call = OE3GAS\n[logging]\n"

    def test_no_log_dir_means_no_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.conf"
            p.write_text(self.BASE + "log_dir =\n")
            self.assertIsNone(config.load(p).logging.log_dir)

    def test_relative_existing_dir(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "logs").mkdir()
            p = Path(d) / "t.conf"
            p.write_text(self.BASE + "log_dir = logs\n")
            self.assertEqual(config.load(p).logging.log_dir, Path(d).resolve() / "logs")
            self.assertEqual(list((Path(d) / "logs").iterdir()), [])  # probe removed

    def test_missing_dir_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.conf"
            p.write_text(self.BASE + "log_dir = nothere\n")
            with self.assertRaisesRegex(config.ConfigError, "does not exist"):
                config.load(p)


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()

    def test_send_list_read_kill(self):
        s, t = login(self.app, "OE1ABC")
        self.assertIn("No new messages", t.take())
        type_lines(s, "S OE3GAS", "Sked tonight", "Hi Gerhard,", "", "80m at 20z?", "/EX")
        self.assertIn("Msg 1 saved.", t.take())

        g, gt = login(self.app, "OE3GAS-7")  # any SSID of the sysop call
        self.assertIn("You have 1 new message(s).", gt.take())
        type_lines(g, "L")
        listing = gt.take()
        self.assertIn("Sked tonight", listing)
        created = self.app.store.get(1).created  # e.g. 2026-09-28T09:15:00Z
        self.assertIn(f"{created[2:4]}{created[5:7]}{created[8:10]} {created[11:16]}", listing)
        type_lines(g, "R 1")
        out = gt.take()
        self.assertIn("80m at 20z?", out)
        self.assertEqual(self.app.store.get(1).status, "Y")
        self.assertEqual(self.app.store.get(1).body, "Hi Gerhard,\n\n80m at 20z?")

        type_lines(g, "KM")
        self.assertIn("Msg 1 killed.", gt.take())
        self.assertIsNone(self.app.store.get(1))

    def test_ctrl_z_and_cancel(self):
        s, t = login(self.app, "OE1ABC")
        type_lines(s, "SB ALL", "Net", "Tonight 20:00\x1a")
        self.assertIn("saved", t.take())
        self.assertEqual(self.app.store.get(1).body, "Tonight 20:00")
        type_lines(s, "S OE3GAS", "x", "text", "/AB")
        self.assertIn("cancelled", t.take())
        self.assertEqual(len(self.app.store.list_messages()), 1)

    def test_privacy(self):
        self.app.service.create(from_call="OE1ABC", to_call="OE3GAS", type="P",
                                subject="secret", body="x", origin="radio")
        s, t = login(self.app, "OE5XYZ")
        type_lines(s, "L")
        self.assertIn("No messages.", t.take())
        type_lines(s, "R 1")
        self.assertIn("No such message: 1", t.take())
        type_lines(s, "K 1")
        self.assertIn("No such message: 1", t.take())

    def test_bulletin_visible_but_not_deletable(self):
        self.app.service.create(from_call="OE1ABC", to_call="ALL", type="B",
                                subject="bulletin", body="x", origin="radio")
        s, t = login(self.app, "OE5XYZ")
        type_lines(s, "R 1")
        self.assertIn("bulletin", t.take())
        type_lines(s, "K 1")
        self.assertIn("Not allowed.", t.take())

    def test_invalid_input(self):
        s, t = login(self.app, "OE1ABC")
        type_lines(s, "XYZ", "R", "R abc", "S", "S ALL", "E 1 TO OE1ABC")
        out = t.take()
        self.assertIn("Unknown command", out)
        self.assertIn("Usage: R n", out)
        self.assertIn("Usage: S call", out)
        self.assertIn("Invalid callsign: ALL", out)
        self.assertIn("Not allowed.", out)

    def test_too_large(self):
        app = make_app(max_msg_bytes=256)
        s, t = login(app, "OE1ABC")
        type_lines(s, "S OE3GAS", "big", "x" * 200, "y" * 200)
        self.assertIn("too long", t.take())
        self.assertEqual(app.store.list_messages(), [])

    def test_sysop_edit(self):
        self.app.service.create(from_call="OE1ABC", to_call="OE3GAS", type="P",
                                subject="old", body="x", origin="radio")
        s, t = login(self.app, "OE3GAS")
        type_lines(s, "E 1 SUBJ new subject", "E 1 TO OE1XYZ", "E 1 STATUS Q")
        out = t.take()
        self.assertIn("Msg 1 updated.", out)
        self.assertIn("Invalid value", out)
        m = self.app.store.get(1)
        self.assertEqual((m.subject, m.to_call), ("new subject", "OE1XYZ"))

    def test_bye_and_jlog(self):
        s, t = login(self.app, "OE1ABC")
        type_lines(s, "J")
        self.assertIn("OE1ABC", t.take())
        type_lines(s, "B")
        self.assertIn("73", t.take())
        self.assertTrue(t.closed and s.closed)


class ServiceTests(unittest.TestCase):
    def test_third_party_off(self):
        app = make_app(third_party=False)
        with self.assertRaises(ServiceError):
            app.service.check_send("OE1ABC", "OE5XYZ", "P", sysop=False)
        with self.assertRaises(ServiceError):
            app.service.check_send("OE1ABC", "ALL", "B", sysop=False)
        app.service.check_send("OE1ABC", "OE3GAS", "P", sysop=False)  # to sysop: ok
        app.service.check_send("OE3GAS", "ALL", "B", sysop=True)

    def test_msgid_dedup_and_events(self):
        app = make_app()
        seen = []
        app.bus.subscribe("*", lambda name, data: seen.append(name))
        a = app.service.create(from_call="OE1ABC", to_call="ALL", type="B", subject="s",
                               body="b", origin="mqtt", msgid="abc-123")
        b = app.service.create(from_call="OE1ABC", to_call="ALL", type="B", subject="s",
                               body="b", origin="mqtt", msgid="abc-123")
        self.assertEqual(a, b)
        self.assertEqual(seen, ["message.created"])
        self.assertEqual(app.store.get(a).origin, "mqtt")

    def test_numbers_not_reused(self):
        app = make_app()
        a = app.service.create(from_call="OE1ABC", to_call="OE3GAS", type="P",
                               subject="s", body="b", origin="radio")
        app.service.delete(a, "OE3GAS", sysop=True)
        b = app.service.create(from_call="OE1ABC", to_call="OE3GAS", type="P",
                               subject="s", body="b", origin="radio")
        self.assertGreater(b, a)


class TelnetTests(unittest.TestCase):
    def test_end_to_end(self):
        async def scenario() -> str:
            app = make_app()
            app.cfg.telnet = dataclasses.replace(app.cfg.telnet, port=0)
            server = await asyncio.start_server(
                lambda r, w: telnet.TelnetConnection(app, r, w).run(), "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.write(b"oe1abc\r\nS OE3GAS\r\nHello\r\nTest via telnet\r\n/EX\r\nL\r\nB\r\n")
            await writer.drain()
            data = await asyncio.wait_for(reader.read(), 5)
            writer.close()
            server.close()
            await server.wait_closed()
            return data.decode("utf-8", "replace")

        out = asyncio.run(scenario())
        self.assertIn("hello OE1ABC", out)
        self.assertIn("Msg 1 saved.", out)
        self.assertIn("Hello", out)
        self.assertIn("73, bye", out)


if __name__ == "__main__":
    unittest.main()


class PagingTests(unittest.TestCase):
    """CR40 (was CR29): long terminal output starts with a hint that A aborts
    it, then goes out in full - no pages, no question."""

    def setUp(self):
        self.app = make_app()
        for i in range(23):
            self.app.service.create(from_call="OE3TEC", to_call="OE1ABC", type="P",
                                    subject=f"Nr {i}", body="x", origin="telnet")

    def test_hint_then_everything(self):
        s, t = login(self.app, "OE1ABC")
        t.take()
        type_lines(s, "L")
        out = t.take()
        self.assertTrue(out.startswith("*** 24 lines follow - send A to abort\r"))
        self.assertIn("Nr 22", out)
        self.assertIn("Nr 0", out)
        self.assertTrue(out.endswith("> "))
        self.assertNotIn("More", out)

    def test_abort_and_short_output(self):
        s, t = login(self.app, "OE1ABC")
        t.take()
        aborted = []
        t.abort_output = lambda: aborted.append(1)
        type_lines(s, "L", "A")
        out = t.take()
        self.assertEqual(aborted, [1])                       # the queue is dropped
        self.assertIn("Output aborted.", out)
        type_lines(s, "J")                                   # short: no hint
        self.assertNotIn("lines follow", t.take())
        type_lines(s, "B")                                   # bye still arrives
        self.assertIn("73", t.take())

    def test_not_for_clients(self):
        s, t = login(self.app, "OE1ABC")
        type_lines(s, "//CLIENT TB1 caps=CHAT")
        t.take()
        type_lines(s, "L")
        out = t.take()
        self.assertIn("Nr 0", out)
        self.assertNotIn("lines follow", out)
