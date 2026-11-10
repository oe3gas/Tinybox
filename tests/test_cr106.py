"""CR106: mail notice but an empty inbox, the sync hangs in "connecting".

The login answers //AUTHWAIT and //ERR auth came behind the terminal prompt and
never reached the client: no client mode, no notice, and the sync waited 90 s
in "connecting" (Abort: another 30 s)."""

from __future__ import annotations

import asyncio
import dataclasses
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from prcore import auth
from tbclient.core import ClientCore
from tinybox import clientproto
from tinybox.adapters import agw as tb_agw
from tests.test_chat import chat_app
from tests.test_mailsync import FakeTransport, mail, type_lines
from tests.test_tbclient import FakeDirewolf, client_cfg, until
from tinybox.session import Session


def run(key: str | None):
    """Box with 4 mails for OE3GAS; the client connects, then Sync. Returns
    (auth, sync status, inbox count, seconds of the sync)."""
    async def scenario():
        dw = FakeDirewolf()
        port = await dw.start()
        app = chat_app()
        app.cfg.direwolf = dataclasses.replace(app.cfg.direwolf, agw_port=port, reconnect_sec=1)
        adapter = tb_agw.AgwAdapter(app)
        app.agw = adapter
        t1 = asyncio.create_task(adapter.run())
        await asyncio.wait_for(adapter.connected.wait(), 5)
        for i in range(4):
            mail(app, "OE3TEC", "OE3GAS", f"Nr {i}", f"Text {i}")
        with tempfile.TemporaryDirectory() as tmp:
            core = ClientCore(client_cfg(tmp, agw_port=port, sync_chunk=256, sync_pause=0.05))
            if key == "active":
                app.service.store.key_put("OE3GAS", core.identity.pub, "active")
            elif key == "other":
                app.service.store.key_put("OE3GAS", auth.b64e(b"\1" * 32), "active")
            t2 = asyncio.create_task(core.run())
            await asyncio.wait_for(core.link.agw_up.wait(), 5)
            await core.connect()
            await until(lambda: core.auth["state"] not in ("", "asking") or core.caps, 10)
            await until(lambda: not core.sync.running, 10)        # a login sync
            t0 = time.monotonic()
            core.sync.start("mail")
            await until(lambda: not core.sync.running, 20)
            out = (dict(core.auth), dict(core.sync.status), len(core.mailbox.folder("inbox")),
                   time.monotonic() - t0)
            core.mailbox.close()
            t2.cancel()
        t1.cancel()
        dw.server.close()
        return out
    with mock.patch.object(clientproto, "REQUIRE_AUTH", True):
        return asyncio.run(scenario())


class LoginAnswers(unittest.TestCase):
    def test_released_key_fetches(self):
        a, st, n, _ = run("active")
        self.assertEqual((a["state"], st["error"], n), ("ok", "", 4))

    def test_key_waits_for_sysop(self):
        a, st, n, secs = run(None)
        self.assertEqual(a["state"], "wait")
        self.assertIn("waits for the sysop", st["error"])
        self.assertIn(a["fp"], st["error"])
        self.assertEqual(n, 0)
        self.assertLess(secs, 5)                   # at once, not after 90 s

    def test_other_key_refused(self):
        a, st, _, secs = run("other")
        self.assertEqual((a["state"], a["reason"]), ("refused", "other_key"))
        self.assertIn("other_key", st["error"])
        self.assertLess(secs, 5)


class BoxNoPrompt(unittest.TestCase):
    def test_answers_on_their_own_line(self):
        with mock.patch.object(clientproto, "REQUIRE_AUTH", True):
            app = chat_app()
            t = FakeTransport()
            s = Session("OE3GAS", app.service, app.cfg, t, origin="radio")
            s.start()
            t.take()
            type_lines(s, "//CLIENT TB1 caps=CHAT,SYNC")
            out = t.take()
            self.assertNotIn(">", out.replace("//AUTH?", ""))      # no prompt while logging in
            with tempfile.TemporaryDirectory() as tmp:
                ident = auth.Identity(Path(tmp) / "identity.key")
                box = app.cfg.station.mailbox_call
                type_lines(s, f"//AUTH sig={ident.sign_login(box, 'OE3GAS', s._auth_nonce)} "
                              f"pub={ident.pub}")
            lines = t.take().replace("\r", "\n").split("\n")
            self.assertTrue(any(x.startswith("//AUTHWAIT fp=") for x in lines), lines)


class ClientOldBox(unittest.TestCase):
    def test_answer_after_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            core = ClientCore(client_cfg(tmp))
            core._on_line("TinyBox (A,B,C,F,H,J,K,L,R,S,V,?) > //AUTHWAIT fp=1234-5678-9ABC")
            self.assertEqual(core.auth["state"], "wait")
            core._on_line("TinyBox (A,B,C,F,H,J,K,L,R,S,V,?) > //ERR auth other_key")
            self.assertEqual((core.auth["state"], core.auth["reason"]), ("refused", "other_key"))
            core.mailbox.close()

    def test_abort_while_waiting_for_login(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp))
                core.chan.state = "online"           # online, but no client mode yet
                core.chan.target = core.home
                self.assertTrue(core.sync.start("mail"))
                await asyncio.sleep(0.5)
                core.sync.abort()
                t0 = time.monotonic()
                await until(lambda: not core.sync.running, 5)
                self.assertLess(time.monotonic() - t0, 2)
                self.assertEqual(core.sync.status["step"], "aborted")
                core.chan.state = "offline"
                core.mailbox.close()
        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
