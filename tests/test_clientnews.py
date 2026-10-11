"""CR18: newest client version and its feature bulletin (tinybox/clientnews.py),
the hint in the //OK answer and in the client."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from tbclient import VERSION
from tbclient.core import ClientCore
from tinybox import clientnews
from tests.test_tbclient import client_cfg
from tests.test_tinybox import login, make_app, type_lines


def fake_client(tmp: str, version: str, features: str | None = "Chat\nMailbox\n") -> Path:
    d = Path(tmp) / "tbclient"
    d.mkdir(exist_ok=True)
    (d / "__init__.py").write_text(f'"""x"""\n\nVERSION = "{version}"\n', encoding="utf-8")
    if features is not None:
        (d / "FEATURES.txt").write_text(features, encoding="utf-8")
    return d


class VersionTests(unittest.TestCase):
    def test_repo_client_version_is_a_date(self):
        self.assertEqual(clientnews.client_version(), VERSION)
        self.assertRegex(VERSION, r"^20\d\d\.\d{1,2}\.\d{1,2}(\.\d+)?$")
        self.assertTrue((clientnews.CLIENT_DIR / "FEATURES.txt").is_file())

    def test_order(self):
        k = clientnews.version_key
        self.assertLess(k(""), k("0.1"))
        self.assertLess(k("0.1"), k("2026.10.11"))
        self.assertLess(k("2026.10.11"), k("2026.10.11.2"))
        self.assertLess(k("2026.9.30"), k("2026.10.1"))       # numbers, not text

    def test_missing_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(clientnews.client_version(Path(tmp) / "nothing"), "")


class BulletinTests(unittest.TestCase):
    def test_create_keep_renew(self):
        app = make_app()
        with tempfile.TemporaryDirectory() as tmp:
            d = fake_client(tmp, "2026.10.11")
            first = clientnews.ensure_bulletin(app, d)
            m = app.store.get(first)
            self.assertEqual((m.type, m.to_call, m.at_addr), ("B", "TBNEWS", ""))
            self.assertEqual(m.subject, "TinyBox client 2026.10.11: features")
            self.assertEqual(clientnews.ensure_bulletin(app, d), first)   # unchanged
            fake_client(tmp, "2026.10.12", "Chat\nMailbox\nStickers\n")
            second = clientnews.ensure_bulletin(app, d)
            self.assertGreater(second, first)            # new number -> clients fetch it
            self.assertIsNone(app.store.get(first))
            self.assertIn("Stickers", app.store.get(second).body)

    def test_no_features_file(self):
        app = make_app()
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(clientnews.ensure_bulletin(app, fake_client(tmp, "1", None)))

    def test_fixed_bulletin_does_not_expire_by_age(self):
        app = make_app()
        app.cfg.mailbox = app.cfg.mailbox.__class__(**{**app.cfg.mailbox.__dict__,
                                                      "bulletin_expire_days": 1})
        news = clientnews.ensure_bulletin(app)
        other = app.service.create(from_call="OE3ABC", to_call="ALL", type="B",
                                   subject="old", body="x", origin="telnet")
        app.store._db.execute("UPDATE messages SET created = '2000-01-01T00:00:00Z'")
        app.store._db.commit()
        app.service.purge_expired()
        self.assertIsNotNone(app.store.get(news))
        self.assertIsNone(app.store.get(other))


class HandshakeTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.app.service.client_news_id = clientnews.ensure_bulletin(self.app)

    def ok_line(self, client_line):
        s, t = login(self.app, "OE3ABC")
        t.take()
        type_lines(s, client_line)
        return next(x for x in t.take().split("\r") if x.startswith("//OK"))

    def test_old_client_gets_version_and_bulletin(self):
        line = self.ok_line("//CLIENT TB1 v=2026.1.1 caps=CHAT")
        self.assertEqual(line, f"//OK TB1 caps=CHAT cur={VERSION} "
                               f"news={self.app.service.client_news_id}")
        # a client from before CR18 sends no v= at all: also "older"
        self.assertIn(f"cur={VERSION}", self.ok_line("//CLIENT TB1 caps=CHAT"))

    def test_current_client_gets_nothing_extra(self):
        self.assertEqual(self.ok_line(f"//CLIENT TB1 v={VERSION} caps=CHAT"), "//OK TB1 caps=CHAT")
        self.assertEqual(self.ok_line("//CLIENT TB1 v=2099.1.1 caps=CHAT"), "//OK TB1 caps=CHAT")


class ClientHintTests(unittest.TestCase):
    def test_hint_from_ok_line(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp, link="telnet"))
                core.link.send_line = lambda line: None
                self.assertIsNone(core.snapshot()["update"])
                core._control("//OK TB1 caps=CHAT cur=2099.1.1 news=42")
                self.assertEqual(core.snapshot()["update"], {"cur": "2099.1.1", "news": 42})
                # kept after a restart of the client (settings file)
                again = ClientCore(client_cfg(tmp, link="telnet"))
                self.assertEqual(again.update, {"cur": "2099.1.1", "news": 42})
                # TinyBox without cur= (or an older one): up to date, hint gone
                core._control("//OK TB1 caps=CHAT")
                self.assertIsNone(core.snapshot()["update"])
                core._control(f"//OK TB1 caps=CHAT cur={VERSION}")
                self.assertIsNone(core.update)
        asyncio.run(scenario())

    def test_handshake_sends_version(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp, link="telnet"))
                sent = []
                core.link.send_line = sent.append
                core._handshake()
                self.assertTrue(sent[0].startswith(f"//CLIENT TB1 v={VERSION} caps="), sent)
        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
