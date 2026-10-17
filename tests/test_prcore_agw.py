"""prcore/agw.py: the AGW frame header shared by TinyBox, client and fwdsim."""

from __future__ import annotations

import asyncio
import unittest

from prcore import agw


def _read(data: bytes) -> agw.Frame:
    """read_frame() on a stream holding exactly these bytes."""
    async def go() -> agw.Frame:
        r = asyncio.StreamReader()
        r.feed_data(data)
        r.feed_eof()
        return await agw.read_frame(r)
    return asyncio.run(go())


class AgwCodecTest(unittest.TestCase):
    def test_roundtrip(self) -> None:
        f = agw.Frame("D", 1, agw.PID_NO_L3, "oe3gas-1", "OE3TEC", b"hello")
        raw = f.pack()
        self.assertEqual(len(raw), agw.HEADER.size + 5)
        back = _read(raw)
        self.assertEqual(back, agw.Frame("D", 1, 0xF0, "OE3GAS-1", "OE3TEC", b"hello"))

    def test_too_large_is_a_connection_error(self) -> None:
        raw = agw.HEADER.pack(0, b"D", 0, b"A", b"B", agw.MAX_DATA + 1, 0)
        with self.assertRaises(agw.AgwProtocolError):
            _read(raw)
        self.assertTrue(issubclass(agw.AgwProtocolError, ConnectionError))

    def test_closed_stream(self) -> None:
        with self.assertRaises(asyncio.IncompleteReadError):
            _read(b"\0" * 10)

    def test_via_data(self) -> None:
        data = agw.via_data(["OE3XHR", "OE1XDS-10"])
        self.assertEqual(data[0], 2)
        self.assertEqual(len(data), 1 + 20)
        self.assertEqual(agw.decode_call(data[1:11]), "OE3XHR")
        self.assertEqual(agw.decode_call(data[11:21]), "OE1XDS-10")


if __name__ == "__main__":
    unittest.main()
