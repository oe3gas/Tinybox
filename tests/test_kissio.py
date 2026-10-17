"""KISS framing and KISS-TCP client (KISS step K1, docs/kiss-mode-konzept.md)."""

from __future__ import annotations

import asyncio
import unittest

from prcore.ax25 import frame as ax
from prcore import kiss
from prcore.kiss import FEND, FESC, TFEND, TFESC


class EncodeTests(unittest.TestCase):
    def test_escaping(self):
        raw = kiss.encode(bytes((0x01, FEND, 0x02, FESC, 0x03)))
        self.assertEqual(raw, bytes((FEND, 0x00, 0x01, FESC, TFEND, 0x02, FESC, TFESC,
                                     0x03, FEND)))

    def test_port_in_type_byte(self):
        self.assertEqual(kiss.encode(b"x", port=3)[1], 0x30)

    def test_params(self):
        self.assertEqual(kiss.encode_param(kiss.CMD_TXDELAY, kiss.ms_to_units(300)),
                         bytes((FEND, 0x01, 30, FEND)))
        self.assertEqual(kiss.encode_param(kiss.CMD_P, 63, port=1),
                         bytes((FEND, 0x12, 63, FEND)))
        self.assertEqual(kiss.encode_return(), bytes((FEND, 0xFF, FEND)))
        self.assertEqual(kiss.ms_to_units(5000), 255)

    def test_invalid(self):
        for call in (lambda: kiss.encode(b"", port=16),
                     lambda: kiss.encode_param(kiss.CMD_DATA, 1),
                     lambda: kiss.encode_param(kiss.CMD_P, 256)):
            with self.assertRaises(kiss.KissError):
                call()


class DecoderTests(unittest.TestCase):
    def test_round_trip_split_anywhere(self):
        frames = [bytes(range(256)), b"\xc0\xc0\xdb\xdb", b"plain"]
        stream = b"".join(kiss.encode(f, port=i) for i, f in enumerate(frames))
        for cut in range(1, len(stream)):
            dec = kiss.Decoder()
            got = dec.feed(stream[:cut]) + dec.feed(stream[cut:])
            self.assertEqual(got, [(i, 0, f) for i, f in enumerate(frames)], f"cut {cut}")

    def test_noise_before_first_fend_and_empty_frames(self):
        dec = kiss.Decoder()
        got = dec.feed(b"cmd:KISS ON\r" + bytes((FEND, FEND, FEND)) + kiss.encode(b"ok"))
        self.assertEqual(got, [(0, 0, b"ok")])

    def test_parameter_frames_reported(self):
        dec = kiss.Decoder()
        got = dec.feed(kiss.encode_param(kiss.CMD_SLOTTIME, 10) + kiss.encode_return())
        self.assertEqual(got, [(0, kiss.CMD_SLOTTIME, b"\x0a"),
                               (0, kiss.CMD_RETURN, b"")])

    def test_oversized_frame_dropped_then_resync(self):
        dec = kiss.Decoder(max_frame=16)
        got = dec.feed(bytes((FEND,)) + b"x" * 40 + kiss.encode(b"next"))
        self.assertEqual(got, [(0, 0, b"next")])
        self.assertEqual(dec.dropped, 1)


class FakeKissServer:
    """A KISS-TCP server like kisshub or Direwolf: records and can push frames."""

    def __init__(self) -> None:
        self.received: list[tuple[int, int, bytes]] = []
        self.writer: asyncio.StreamWriter | None = None
        self.got = asyncio.Event()
        self.connected = asyncio.Event()

    async def handle(self, reader, writer) -> None:
        self.writer = writer
        self.connected.set()
        dec = kiss.Decoder()
        while chunk := await reader.read(4096):
            self.received.extend(dec.feed(chunk))
            self.got.set()
        writer.close()


class TcpClientTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fake = FakeKissServer()
        self.server = await asyncio.start_server(self.fake.handle, "127.0.0.1", 0)
        port = self.server.sockets[0].getsockname()[1]
        self.frames: list[ax.Frame] = []
        self.client = kiss.KissTcpClient(
            "127.0.0.1", port, lambda p, data: self.frames.append(ax.Frame.decode(data)),
            reconnect_sec=0.05)
        self.task = asyncio.create_task(self.client.run())
        await asyncio.wait_for(self.client.connected.wait(), 2)
        await asyncio.wait_for(self.fake.connected.wait(), 2)

    async def asyncTearDown(self):
        self.task.cancel()
        self.server.close()
        await self.server.wait_closed()

    async def test_send_and_receive(self):
        sabm = ax.u_frame("SABM", "OE3GAS-1", "OE3ABC", pf=True).encode()
        self.assertTrue(self.client.send(sabm))
        await asyncio.wait_for(self.fake.got.wait(), 2)
        self.assertEqual(self.fake.received, [(0, 0, sabm)])

        ua = ax.u_frame("UA", "OE3ABC", "OE3GAS-1", command=False, pf=True).encode()
        self.fake.writer.write(kiss.encode_param(kiss.CMD_P, 63)    # ignored
                               + kiss.encode(b"\x00", port=1)         # other port
                               + kiss.encode(ua))
        for _ in range(100):
            if self.frames:
                break
            await asyncio.sleep(0.01)
        self.assertEqual([f.kind for f in self.frames], ["UA"])
        self.assertEqual(self.client.rx_frames, 1)

    async def test_send_while_down_returns_false_then_reconnects(self):
        self.fake.connected.clear()
        self.fake.writer.close()
        for _ in range(100):
            if not self.client.connected.is_set():
                break
            await asyncio.sleep(0.01)
        self.assertFalse(self.client.send(b"x" * 16))
        await asyncio.wait_for(self.client.connected.wait(), 2)
        self.assertTrue(self.client.send(ax.ui_frame("TBCHAT-1", "OE3GAS-1", b"hi").encode()))

    async def test_bad_frame_does_not_stop_the_link(self):
        self.fake.writer.write(kiss.encode(b"garbage") +
                               kiss.encode(ax.ui_frame("X", "OE3ABC", b"ok").encode()))
        for _ in range(100):
            if self.frames:
                break
            await asyncio.sleep(0.01)
        self.assertEqual(self.frames[0].info, b"ok")
        self.assertTrue(self.client.connected.is_set())


if __name__ == "__main__":
    unittest.main()
