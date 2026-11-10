"""CR99 (audit TB-06): two TBClients prove their keys to each other - first
contact, known, another key, verified by a certificate - and only a trusted
peer compares or deletes the chat history and gets pictures and files."""

from __future__ import annotations

import asyncio
import dataclasses
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from prcore import auth
from tbclient import core as core_mod
from tbclient import peer as peer_mod
from tbclient.core import ClientCore

from tests.test_tbclient import FakeDirewolf, client_cfg, until


class PeerAuthTests(unittest.TestCase):
    def setUp(self):
        self._old = core_mod.HANDSHAKE_FALLBACK_SEC
        core_mod.HANDSHAKE_FALLBACK_SEC = 0.3

    def tearDown(self):
        core_mod.HANDSHAKE_FALLBACK_SEC = self._old

    def run_pair(self, steps):
        async def scenario():
            dw = FakeDirewolf()
            port = await dw.start()
            with tempfile.TemporaryDirectory() as ta, tempfile.TemporaryDirectory() as tb:
                a = ClientCore(client_cfg(ta, agw_port=port))
                b = ClientCore(dataclasses.replace(client_cfg(tb, agw_port=port), mycall="OE3TEC"))
                tasks = [asyncio.create_task(a.run()), asyncio.create_task(b.run())]
                await asyncio.wait_for(a.port.agw_up.wait(), 5)
                await asyncio.wait_for(b.port.agw_up.wait(), 5)
                await until(lambda: len([c for c in dw.clients if c["calls"]]) == 2)

                async def connect():
                    self.assertTrue(await b.connect("OE3GAS", ch=1))
                    await until(lambda: a.channels[1].peer is not None and
                                b.channels[1].peer is not None and
                                a.channels[1].peer.auth.state and b.channels[1].peer.auth.state)
                    await asyncio.sleep(0.3)

                async def disconnect():
                    b.disconnect(1)
                    await until(lambda: a.channels[1].state == "offline"
                                and b.channels[1].state == "offline")

                await steps(a, b, connect, disconnect, Path(tb))
                for c in (a, b):
                    c.mailbox.close()
                for task in tasks:
                    task.cancel()
            dw.server.close()
        asyncio.run(scenario())

    def test_first_known_changed_accept(self):
        async def steps(a, b, connect, disconnect, tb):
            await connect()
            pa, pb = a.channels[1].peer, b.channels[1].peer
            self.assertEqual((pa.auth.state, pb.auth.state), ("first", "first"))
            self.assertEqual(pa.auth.fp, b.identity.fp)
            self.assertEqual(pa.summary(time.time())["auth"]["dev"], b.identity.device)
            self.assertTrue(b.send_raw("Servus", ch=1))
            await until(lambda: len(a.peerchat.messages("OE3TEC")) == 1)
            await disconnect()
            await connect()
            self.assertEqual(a.channels[1].peer.auth.state, "known")
            await disconnect()
            # another key under OE3TEC (a new PC - or somebody using the call)
            b.identity = auth.Identity(tb / "other.key")
            with self.assertLogs("tbclient", "WARNING"):
                await connect()
            pa = a.channels[1].peer
            self.assertEqual(pa.auth.state, "changed")
            self.assertFalse(pa.trusted)
            # the history is not compared with it, and it gets no pictures of ours
            with self.assertLogs("tbclient.peer", "WARNING"):
                pa.take("//HIST DEL g=abcdef")
            self.assertEqual(len(a.peerchat.messages("OE3TEC")), 1)
            sent = []
            pa._send = sent.append
            pa.img._sent_to_them = lambda h: True
            with mock.patch.object(type(pa.img), "store", mock.PropertyMock(
                    return_value=mock.Mock(get=lambda h: b"x" * 100))):
                pa.img.take("IMG", "abc123")
                self.assertEqual(sent[-1], "//NOIMG abc123")
                pa.auth.state = "known"                       # trusted: it would go out
                pa.img.take("IMG", "abc123")
                self.assertNotEqual(sent[-1], "//NOIMG abc123")
                pa.auth.state = "changed"
            self.assertTrue(pa.auth.accept())                 # the user compared: it is his
            self.assertEqual(pa.auth.state, "known")
            await disconnect()
        self.run_pair(steps)

    def test_verified_by_certificate(self):
        async def steps(a, b, connect, disconnect, tb):
            box = auth.Identity(tb / "box.key")
            a.settings["trust"] = {"at": int(time.time()), "home": "OE3GAS-1",
                                   "keys": {"OE3GAS-1": box.pub}}
            a.settings["peer_keys"] = {"OE3TEC": [{"pub": "x" * 43, "at": 1}]}   # known: another
            b.settings["certs"] = {"OE3GAS-1": auth.make_cert(box, "OE3TEC", b.identity.pub,
                                                              "OE3GAS-1", "20991231")}
            await connect()
            pa = a.channels[1].peer
            self.assertEqual((pa.auth.state, pa.auth.issuer), ("verified", "OE3GAS-1"))
            self.assertTrue(pa.trusted)
            await disconnect()
        self.run_pair(steps)


class OldPeer(unittest.TestCase):
    def test_without_auth_chat_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            core = ClientCore(client_cfg(tmp))
            ch = core.open_channel(2)
            ch.state, ch.target = "online", "OE3TEC"
            ch.link.send_line = lambda line: None
            p = peer_mod.Peer(ch, "v=2026.11.01 caps=PROF,HIST,IMG", "n0nce12345")
            p.start()
            self.assertEqual(p.auth.state, "old")
            self.assertFalse(p.trusted)
            with self.assertLogs("tbclient.peer", "WARNING"):
                self.assertTrue(p.take("//HIST g=abc m=0:0 y=0:0"))

    def test_lines_carry_a_challenge(self):
        self.assertIn(" n=abc", peer_mod.probe_line("abc"))
        self.assertIn("AUTH", peer_mod.answer_line("abc"))


if __name__ == "__main__":
    unittest.main()


class TrustList(unittest.TestCase):
    def test_box_answers_and_client_keeps_it(self):
        from tinybox import keys

        from tests.test_tinybox import login, make_app, type_lines
        with tempfile.TemporaryDirectory() as tmp:
            app = make_app()
            app.cfg.storage = dataclasses.replace(app.cfg.storage, data_dir=Path(tmp))
            other = auth.Identity(Path(tmp) / "o.key")
            keys.trust_add(app.service, "OE5XBL-1", other.pub)
            s, t = login(app, "OE3GAS")
            type_lines(s, "//CLIENT TB1 v=2026.11.10 caps=CHAT", "//TRUST?")
            line = [x for x in t.take().split("\r") if x.startswith("//TRUST ")][0]
            me = keys.this_box(app.service)
            self.assertIn(f"OE3GAS-1={me['pub']}", line)
            self.assertIn(f"OE5XBL-1={other.pub}", line)
            core = ClientCore(client_cfg(tmp))
            core._send = lambda x: None
            core._on_line("//AUTH? n=abc123 box=OE3GAS-1")
            core._on_line(line)
            self.assertEqual(core.trusted_issuer("OE5XBL-1"), other.public)
            self.assertIsNone(core.trusted_issuer("DB0XYZ"))
