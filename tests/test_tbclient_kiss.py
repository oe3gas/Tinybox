"""CR46: the client over kisshub with its own AX.25 layer 2 - against the
TinyBox (KISS adapter) and client to client, incoming connects included.

A fake kisshub fans every frame out to all other KISS-TCP clients, as kisshub
does with frames its clients send ("the air" for stations on one PC).
"""

from __future__ import annotations

import asyncio
import dataclasses
import tempfile
import unittest
from pathlib import Path

from tinybox import config
from tinybox.adapters import kiss as kissadapter
from prcore import kiss

from tbclient import config as ccfg
from tbclient import core as core_mod
from tbclient.core import ClientCore
from tests.test_chat import chat_app
from tests.test_kiss_adapter import FAST
from tests.test_tbclient import until
from tests.test_tinybox import type_lines, login


class FakeHub:
    def __init__(self) -> None:
        self.clients: list[asyncio.StreamWriter] = []

    async def start(self) -> int:
        self.server = await asyncio.start_server(self._conn, "127.0.0.1", 0)
        return self.server.sockets[0].getsockname()[1]

    async def _conn(self, r, w) -> None:
        self.clients.append(w)
        dec = kiss.Decoder()
        try:
            while chunk := await r.read(4096):
                for port, cmd, data in dec.feed(chunk):
                    if cmd != kiss.CMD_DATA:
                        continue
                    for other in self.clients:
                        if other is not w and not other.is_closing():
                            other.write(kiss.encode(data, port))
        except (ConnectionError, OSError):
            pass
        finally:
            self.clients.remove(w)

    def close(self) -> None:
        for w in self.clients:
            w.close()
        self.server.close()


def kiss_client(tmp: str, port: int, call: str, **kw) -> ClientCore:
    kw = {"ax25_t1_max": 2.0, **kw}
    cfg = dataclasses.replace(
        ccfg.Config(), mycall=call, tinybox_call="OE3GAS-1", data_dir=Path(tmp), link="kiss",
        kiss_port=port, kiss_status_port=0, kiss_air_baud=115200, kiss_txdelay_ms=0,
        ax25_t1_min=0.3, ax25_t2=0.05, ax25_t3=30.0, ax25_n2=5,
        sync_on_login=False, **kw)
    return ClientCore(cfg)


class KissClientTests(unittest.TestCase):
    def setUp(self):
        self._old = core_mod.HANDSHAKE_FALLBACK_SEC
        core_mod.HANDSHAKE_FALLBACK_SEC = 0.3

    def tearDown(self):
        core_mod.HANDSHAKE_FALLBACK_SEC = self._old

    def test_config(self):
        cfg = ccfg.load(Path(__file__).resolve().parent.parent / "tbclient.conf.example")
        self.assertEqual((cfg.kiss_port, cfg.kiss_status_port, cfg.ax25_version), (8101, 8102, "2.2"))

    def test_chat_with_tinybox_over_kiss(self):
        async def scenario():
            hub = FakeHub()
            port = await hub.start()
            app = chat_app()
            app.cfg.radio = config.RadioCfg(interface="kiss")
            app.cfg.kiss = config.KissCfg(port=port, reconnect_sec=1, air_baud=1_000_000,
                                          txdelay_ms=0, status_port=0)
            app.cfg.ax25 = dataclasses.replace(app.cfg.ax25, paclen=128, n2=5, **FAST)
            adapter = kissadapter.KissAdapter(app)
            app.agw = adapter
            t1 = asyncio.create_task(adapter.run())
            await asyncio.wait_for(adapter.connected.wait(), 5)
            term, tt = login(app, "OE3XYZ")
            type_lines(term, "C TREFF")
            with tempfile.TemporaryDirectory() as tmp:
                core = kiss_client(tmp, port, "OE3TEC")
                t2 = asyncio.create_task(core.run())
                await asyncio.wait_for(core.port.agw_up.wait(), 5)
                self.assertTrue(core.snapshot()["radio"]["up"])
                self.assertEqual(core.snapshot()["radio"]["via"], "kiss")
                self.assertTrue(await core.connect("OE3GAS-1"))
                await until(lambda: core.boards, 10)
                self.assertEqual(core.chan.mode, "tinybox")
                self.assertIn("IMG", core.caps)                 # radio: pictures allowed
                self.assertTrue(core.join(1))
                await until(lambda: core.board is not None)
                core.say("ueber KISS")
                await until(lambda: "OE3TEC: ueber KISS" in tt.buf)
                type_lines(term, "Antwort")
                await until(lambda: any(m.get("text") == "Antwort" for m in core.messages))
                # the monitor shows our own frames too
                mon = [e for _, _, e in core.snapshot(0)["term"]]
                self.assertTrue(any(e["src"] == "OE3TEC" and e["dst"] == "OE3GAS-1" for e in mon))
                self.assertTrue(any(e["typ"].startswith("SABM") for e in mon))
                # CR50: what the TinyBox sends besides text is marked
                kinds = {e["kind"] for e in mon}
                self.assertIn("proto", kinds)                 # //OK, //BOARDS ...
                self.assertIn("chat", kinds)                  # UI to TBCHAT-1
                self.assertFalse(any(e["text"].startswith("\ufffd") for e in mon))
                core.disconnect()
                await until(lambda: core.state == "offline", 10)
                row = core.logbook.rows()[0]
                self.assertEqual((row["call"], row["via"], row["ended"]), ("OE3GAS-1", "kiss", "user"))
                self.assertGreater(row["rx"], 100)
                t2.cancel()
            t1.cancel()
            hub.close()
        asyncio.run(scenario())

    def test_client_to_client_and_incoming(self):
        async def scenario():
            hub = FakeHub()
            port = await hub.start()
            with tempfile.TemporaryDirectory() as ta, tempfile.TemporaryDirectory() as tb:
                a = kiss_client(ta, port, "OE3GAS", ax25_t1_max=0.4)
                b = kiss_client(tb, port, "OE3TEC")
                tasks = [asyncio.create_task(a.run()), asyncio.create_task(b.run())]
                await asyncio.wait_for(a.port.agw_up.wait(), 5)
                await asyncio.wait_for(b.port.agw_up.wait(), 5)
                await asyncio.sleep(0.1)
                # nobody there: no answer after the retries
                self.assertTrue(await a.connect("OE3NIX", ch=3))
                await until(lambda: a.channels[3].state == "offline", 15)
                self.assertEqual(a.channels[3].ended["kind"], "failed")
                # b calls a: a takes it in its first free channel, as a terminal
                self.assertTrue(await b.connect("OE3GAS", ch=2))
                await until(lambda: b.channels[2].state == "online", 5)
                await until(lambda: any(c.incoming and c.state == "online"
                                        for c in a.channels.values()), 5)
                ca = next(c for c in a.channels.values() if c.incoming)
                self.assertEqual((ca.n, ca.target, ca.mode), (1, "OE3TEC", "terminal"))
                self.assertGreater(ca.act_n, 0)                  # the chip blinks
                await until(lambda: b.channels[2].mode == "terminal", 5)
                self.assertTrue(b.send_raw("Hallo Gerhard", ch=2))
                await until(lambda: any(x == "Hallo Gerhard" for _, k, x in ca.term if k == "rx"))
                self.assertTrue(a.send_raw("73 Tom", ch=ca.n))
                await until(lambda: any(x == "73 Tom" for _, k, x in b.channels[2].term
                                        if k == "rx"))
                # a releases: b sees "remote", a "user"
                a.disconnect(ca.n)
                await until(lambda: b.channels[2].state == "offline" and ca.state == "offline", 10)
                self.assertEqual((ca.ended["kind"], b.channels[2].ended["kind"]), ("user", "remote"))
                for t in tasks:
                    t.cancel()
            hub.close()
        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
