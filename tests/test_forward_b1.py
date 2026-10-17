"""F5: compressed forwarding (LZHUF, B1 frames, restart).

LZHUF is checked byte by byte against vectors made with LinBPQ's own C code
(tests/fixtures/lzhuf_vectors.json). The B1 sessions run TinyBox against a
second TinyBox (fwdsim speaks no B1); the real check is against LinBPQ.
"""

from __future__ import annotations

import asyncio
import base64
import json
import random
import unittest
from pathlib import Path

from tinybox.adapters.forward import ForwardModule
from tinybox.config import PartnerCfg
from prcore import lzhuf
from tinybox.fwd import b1
from tinybox.fwd.link import Link, TcpLink
from tinybox.fwd.protocol import ProtocolError, own_sid, parse_fs

from tests.test_forward_module import HADDR, free_port, fwd_app
from tests.test_tinybox import make_app

FIXTURE = Path(__file__).parent / "fixtures" / "lzhuf_vectors.json"
GAS_HADDR = "OE3GAS.#OOE.AUT.EU"


class LzhufTests(unittest.TestCase):
    def test_vectors_from_linbpq(self):
        vectors = json.loads(FIXTURE.read_text())["vectors"]
        self.assertGreaterEqual(len(vectors), 5)
        for name, v in vectors.items():
            if "text_b64" in v:
                text = base64.b64decode(v["text_b64"])
            else:
                text = v["text_repeat"]["chunk"].encode() * v["text_repeat"]["count"]
            want = base64.b64decode(v["b1_b64"])
            with self.subTest(name):
                self.assertEqual(lzhuf.compress_b1(text), want)       # byte-identical to LinBPQ
                self.assertEqual(lzhuf.decompress_b1(want), text)

    def test_crc_and_size_errors(self):
        payload = bytearray(lzhuf.compress_b1(b"Hello hello hello\r\n"))
        payload[8] ^= 0x40
        with self.assertRaises(lzhuf.LzhufError):
            lzhuf.decompress_b1(bytes(payload))
        with self.assertRaises(lzhuf.LzhufError):
            lzhuf.decompress(lzhuf.compress(b"x" * 1000), max_size=100)

    def test_roundtrip_random(self):
        rnd = random.Random(5)
        for n in (1, 59, 60, 61, 2047, 2048, 2049, 12000):
            data = bytes(rnd.choice(b"abc de\r\n") for _ in range(n))
            self.assertEqual(lzhuf.decompress(lzhuf.compress(data)), data)


class MemLink(Link):
    def __init__(self) -> None:
        super().__init__("mem")

    def _write(self, data: bytes) -> None:
        pass

    async def close(self) -> None:
        self.is_closed = True


class FrameTests(unittest.IsolatedAsyncioTestCase):
    async def _read(self, raw: bytes, limit: int = 100_000) -> b1.Received:
        link = MemLink()
        link._feed(raw)
        return await b1.read_frame(link, 1, limit, b1.Received())

    async def test_frame_roundtrip_and_blocks(self):
        payload = lzhuf.compress_b1(bytes(range(256)) * 10)
        raw = b1.frame("Titel äöü", payload)
        self.assertEqual(raw[0], b1.SOH)
        got = await self._read(raw)
        self.assertEqual((got.title, got.offset, bytes(got.data)), ("Titel äöü", 0, payload))

    async def test_restart_frame(self):
        payload = lzhuf.compress_b1(b"line of text\r\n" * 300)
        raw = b1.frame("T", payload, offset=100)
        got = await self._read(raw)
        self.assertEqual(got.offset, 100)
        self.assertEqual(bytes(got.data), payload[:6] + payload[100:])     # 6-byte block first

    async def test_bad_checksum_and_framing(self):
        raw = bytearray(b1.frame("T", lzhuf.compress_b1(b"abc" * 50)))
        raw[-1] ^= 1
        with self.assertRaises(ProtocolError):
            await self._read(bytes(raw))
        with self.assertRaises(ProtocolError):
            await self._read(b"FB P X Y Z 1_X 10\r")

    async def test_lines_and_binary_share_one_stream(self):
        link = MemLink()
        frame = b1.frame("T", lzhuf.compress_b1(b"hi\r\n"))
        link._feed(b"FS +\r" + frame + b"FF\r")
        self.assertEqual(await link.readline(1), "FS +")
        await b1.read_frame(link, 1, 10_000, b1.Received())
        self.assertEqual(await link.readline(1), "FF")

    def test_text_conversion(self):
        data = b1.text_to_bytes(["R:261008/1200Z @:OE3XTC.#NOE.AUT.EU #:1 $:1_OE3XTC"], "a\nb")
        self.assertTrue(data.endswith(b"\r\na\r\nb\r\n"))
        self.assertEqual(b1.bytes_to_text(b"x\r\ny\rz\n"), "x\ny\nz\n")

    def test_fs_and_sid(self):
        self.assertEqual(parse_fs("FS +!1234-", 3), ["+", "!1234", "-"])
        self.assertEqual(parse_fs("FS A99=", 2), ["!99", "="])
        self.assertIn("B1FH$", own_sid("b1"))
        self.assertTrue(own_sid("fbb").endswith("-FH$]"))


def gas_app(port: int):
    """A second TinyBox playing OE3GAS, partner OE3XTC over TCP with B1."""
    app = make_app()
    st = app.cfg.station
    st.mailbox_call, st.sysop_call, st.haddress, st.qth = "OE3GAS-1", "OE3GAS", GAS_HADDR, "Linz"
    app.cfg.forward.enabled = True
    p = PartnerCfg(call="OE3XTC", transport="tcp", host="127.0.0.1", port=port,
                   login=["OE3GAS", "geheim"], haddress=HADDR, routes=["WW"],
                   areas=["WW", "EU", "AUT"], protocol="b1", timeout=5)
    app.cfg.forward.partners = {"OE3XTC": p}
    return app


def write(app, to, at, subject, body, type="P"):
    return app.service.create(from_call="OE1ABC", to_call=to, type=type, subject=subject,
                              body=body, origin="telnet", at_addr=at)


class B1SessionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from tests.test_forward_module import gas
        self.xtc = fwd_app(gas(protocol="b1", timeout=5))           # TinyBox OE3XTC
        self.xtc_mod = ForwardModule(self.xtc)
        self.xtc.forward = self.xtc_mod
        self.xtc_mod.cfg.listen_port = free_port()
        await self.xtc_mod.start_server()
        self.gas = gas_app(self.xtc_mod.listen_port)                  # TinyBox OE3GAS
        self.gas_mod = ForwardModule(self.gas)
        self.gas.forward = self.gas_mod

    async def asyncTearDown(self):
        self.xtc_mod.server.close()

    async def gas_calls(self):
        r = await self.gas_mod.call("OE3XTC")
        for _ in range(50):
            if "OE3GAS" in self.xtc_mod.last:
                break
            await asyncio.sleep(0.05)
        return r, self.xtc_mod.last.pop("OE3GAS", None)

    async def test_both_directions_compressed(self):
        rnd = random.Random(1)
        big = "\n".join(" ".join(rnd.choice(["packet", "radio", "73", "de", "OE3XTC"])
                                 for _ in range(12)) for _ in range(90))
        a = write(self.gas, "OE1ABC", HADDR, "to TinyBox", big)
        write(self.gas, "ALL", "WW", "bulletin", "Hallo Grüße\nzweite Zeile", type="B")
        b = write(self.xtc, "OE3GAS", GAS_HADDR, "to OE3GAS", "Antwort\n/EX\nEnde")
        r, x = await self.gas_calls()
        self.assertTrue(r.ok and x.ok, (r.error, x and x.error))
        self.assertEqual((r.mode, x.mode), ("b1", "b1"))
        got = self.xtc.store.get_by_bid(self.gas.store.get(a).bid)
        self.assertEqual(got.body, big)
        self.assertEqual(got.subject, "to TinyBox")
        self.assertEqual([l.split("@:")[1].split(".")[0] for l in got.rline_list],
                         ["OE3XTC", "OE3GAS"])
        bull = [m for m in self.xtc.store.list_messages() if m.subject == "bulletin"][0]
        self.assertEqual(bull.body, "Hallo Grüße\nzweite Zeile")
        back = self.gas.store.get_by_bid(self.xtc.store.get(b).bid)
        self.assertEqual(back.body, "Antwort\n/EX\nEnde")
        self.assertEqual(self.xtc.store.get(b).fwd, "F")

    async def test_restart_after_abort(self):
        rnd = random.Random(2)
        body = "\n".join("".join(rnd.choice("abcdefghij klmnop") for _ in range(70))
                         for _ in range(100))                      # compresses badly: many blocks
        msg_id = write(self.gas, "OE1ABC", HADDR, "restart me", body)
        bid = self.gas.store.get(msg_id).bid
        original = TcpLink.write_raw
        cut = {"armed": True}

        def broken(link, data):                                    # first try: only 600 bytes
            if cut["armed"] and data[:1] == bytes([b1.SOH]):
                cut["armed"] = False
                link.writer.write(data[:600])
                link.writer.transport.abort()
                return
            original(link, data)

        TcpLink.write_raw = broken
        try:
            r1, x1 = await self.gas_calls()
        finally:
            TcpLink.write_raw = original
        self.assertFalse(x1.ok)
        part = self.xtc.store.partial_get("OE3GAS", bid)
        self.assertIsNotNone(part)
        self.assertGreater(len(part[0]), 100)
        self.assertIsNone(self.xtc.store.get_by_bid(bid))
        self.gas.store.fwd_set(msg_id, "OE3XTC", "open")           # still to send
        r2, x2 = await self.gas_calls()
        self.assertTrue(r2.ok and x2.ok, (r2.error, x2 and x2.error))
        self.assertEqual(self.xtc.store.get_by_bid(bid).body, body)
        self.assertIsNone(self.xtc.store.partial_get("OE3GAS", bid))


if __name__ == "__main__":
    unittest.main()
