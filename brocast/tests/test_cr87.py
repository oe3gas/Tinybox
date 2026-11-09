"""CR87 (Audit TB-01): a page with a wrongly typed envelope value must be rejected,
never crash brocastd - also not via a poisoned database or a forged dictionary."""

from __future__ import annotations

import asyncio
import unittest
from unittest import mock

import cbor2

from brocast import daemon as daemon_mod
from brocast import frame
from brocast.codec import BrocastError, Codec, valid_exp
from brocast.daemon import Daemon
from brocast.listener import Listener
from brocast.store import Store
from tests.test_daemon import Clock, make_cfg

ST = "OE3GAS-5"
EXP = 5                                    # envelope key of exp (brocast-core.yaml)


def page_bytes(codec: Codec) -> bytes:
    """A valid page; the tests replace single wire keys - what an attacker sends."""
    wire = codec.to_wire({"id": 7, "rev": 0, "t": 1_800_000_000, "typ": "text", "ti": "x"})
    return cbor2.dumps(wire, canonical=True)


class CodecRejectsWrongTypes(unittest.TestCase):
    def setUp(self):
        self.codec = Codec()

    def test_exp_as_text_is_rejected(self):          # the PoC of TB-01
        data = cbor2.dumps({**cbor2.loads(page_bytes(self.codec)), EXP: "abc"})
        with self.assertRaises(BrocastError):
            self.codec.decode(data, defaults=False)

    def test_other_envelope_types(self):
        env = self.codec.d.envelope.by_name
        bad = {
            "t": "1800000000", "id": -1, "rev": 2**64 - 1, "org": "not a call",
            "ti": 42, "sub": [3, 2], "flg": "x", "pri": [1], "cat": {"a": 1},
            "lnk": "OE3GAS", "pos": ["48", 16],
        }
        for name, value in bad.items():
            with self.subTest(field=name):
                data = cbor2.dumps({**cbor2.loads(page_bytes(self.codec)),
                                    env[name].num: value})
                with self.assertRaises(BrocastError):
                    self.codec.decode(data, defaults=False)

    def test_valid_page_still_decodes(self):
        data = cbor2.dumps({**cbor2.loads(page_bytes(self.codec)), EXP: 90})
        self.assertEqual(self.codec.decode(data, defaults=False)["exp"], 90)

    def test_valid_exp(self):
        self.assertEqual(valid_exp(60), 60)
        for bad in ("60", 0, -5, True, 2**40, 1.5, None):
            self.assertIsNone(valid_exp(bad), bad)


class ListenerSurvivesBadData(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.codec = Codec()
        self.store = Store(":memory:")
        self.li = Listener(self.store, self.codec, self.clock)

    def rx(self, page_id=24, **fields):
        page = {"id": page_id, "rev": 0, "t": int(self.clock()), "typ": "text", "ti": "x", **fields}
        data = self.codec.encode(page)
        return self.li.on_page(self.codec.decode(data, defaults=False), data, ST)

    def test_poisoned_database_row_is_removed_not_fatal(self):
        """A row written by brocastd before CR87: housekeeping must heal it on its own."""
        self.rx(24)
        self.rx(25)
        self.store.db.execute("UPDATE lpages SET exp_min = 'abc' WHERE id = 24")
        self.assertEqual(len(self.li.list_pages()), 2)      # the list must not crash either
        self.li.housekeeping()
        self.assertEqual([p["id"] for p in self.li.list_pages()], [25])

    def test_forged_dictionary_exp_is_ignored(self):
        """exp from the typ entry of a dictionary that came over the air (TB-04)."""
        self.codec.d.enums["typ"].by_name["text"].spec["exp"] = "abc"
        try:
            self.assertEqual(self.rx(26), "new")
            self.assertIsNone(self.store.lpage(ST, 26)["exp_min"])
            self.li.housekeeping()
        finally:
            self.codec.d.enums["typ"].by_name["text"].spec["exp"] = 1440


class DaemonSurvives(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.d = Daemon(make_cfg("listener", ""), db_path=":memory:")
        self.codec = Codec()

    async def test_poc_frame_over_the_air(self):
        data = cbor2.dumps({**cbor2.loads(page_bytes(self.codec)), EXP: "abc"})
        self.d.on_frame(0, frame.build(ST, data))           # must not raise
        self.assertEqual(self.d.listener.list_pages(), [])
        self.assertEqual(self.d.rx_errors, 1)
        self.d.listener.housekeeping()                      # and nothing poisoned

    async def test_housekeeping_loop_keeps_running(self):
        calls = []

        def boom():
            calls.append(1)
            raise RuntimeError("kaputt")

        sleeps = []

        async def fake_sleep(_s):
            sleeps.append(1)
            if len(sleeps) >= 2:
                raise asyncio.CancelledError

        with mock.patch.object(self.d.listener, "housekeeping", boom), \
                mock.patch.object(daemon_mod.asyncio, "sleep", fake_sleep), \
                self.assertLogs("brocastd", "ERROR"):
            with self.assertRaises(asyncio.CancelledError):
                await self.d._housekeeping()
        self.assertEqual(len(calls), 2)                     # second run after the error


if __name__ == "__main__":
    unittest.main()
