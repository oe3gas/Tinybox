"""prcore/axudp.py: AX.25 over UDP (PLANUNG.md section 25, step 1)."""

from __future__ import annotations

import asyncio
import unittest

from prcore import axudp
from prcore.ax25 import frame as ax
from prcore.axudp import AxudpEndpoint, AxudpError, Peer, PeerTable, parse_addr, parse_peers

BOX, CLIENT = "OE3GAS-1", "OE3GAS"


def sabm(dest: str = BOX, src: str = CLIENT, path=None) -> bytes:
    return ax.u_frame("SABM", dest, src, pf=True, path=path).encode()


class FcsTests(unittest.TestCase):
    def test_check_value(self):
        self.assertEqual(axudp.fcs16(b"123456789"), 0x906E)     # CRC-16/X.25

    def test_round_trip(self):
        raw = sabm()
        dg = axudp.encode(raw)
        self.assertEqual(len(dg), len(raw) + 2)
        self.assertEqual(dg[-2:], axudp.fcs16(raw).to_bytes(2, "little"))
        self.assertEqual(axudp.decode(dg), raw)

    def test_wrong_fcs(self):
        dg = bytearray(axudp.encode(sabm()))
        dg[3] ^= 0x01
        with self.assertRaisesRegex(AxudpError, "FCS"):
            axudp.decode(bytes(dg))

    def test_sizes(self):
        with self.assertRaises(AxudpError):
            axudp.decode(b"\x00" * 10)
        with self.assertRaises(AxudpError):
            axudp.encode(b"\x00" * 5)
        with self.assertRaises(AxudpError):
            axudp.encode(b"\x00" * (axudp.MAX_FRAME + 1))


class PeerTests(unittest.TestCase):
    def test_addr(self):
        self.assertEqual(parse_addr("127.0.0.1:10094"), ("127.0.0.1", 10094))
        self.assertEqual(parse_addr("127.0.0.1"), ("127.0.0.1", axudp.DEFAULT_PORT))
        self.assertEqual(parse_addr("[::1]:93"), ("::1", 93))
        self.assertEqual(parse_addr("::1"), ("::1", axudp.DEFAULT_PORT))
        for bad in ("box.example:93", "127.0.0.1:x", "127.0.0.1:0", "[::1]93"):
            with self.subTest(bad=bad), self.assertRaises(AxudpError):
                parse_addr(bad)

    def test_parse_mapping_and_lines(self):
        a = parse_peers({"oe3gas": "127.0.0.1:10094", "OE3XAB-7": "44.143.0.1"})
        b = parse_peers(["OE3GAS 127.0.0.1:10094   # client on PC1",
                         "", "; comment", "OE3XAB-7 = 44.143.0.1"])
        self.assertEqual(a, b)
        self.assertEqual(a["OE3GAS"], Peer("OE3GAS", "127.0.0.1", 10094))
        self.assertEqual(a["OE3XAB-7"].addr, ("44.143.0.1", 10093))

    def test_parse_errors(self):
        for bad in (["OE3GAS"], ["TOOLONGCALL 127.0.0.1"], ["OE3GAS-16 127.0.0.1"],
                    ["OE3GAS 1.2.3.4", "oe3gas 1.2.3.5"]):
            with self.subTest(bad=bad), self.assertRaises(AxudpError):
                parse_peers(bad)

    def test_route_ssid_first(self):
        t = PeerTable(parse_peers({"OE3GAS": "127.0.0.1:1", "OE3GAS-1": "127.0.0.1:2"}))
        self.assertEqual(t.route("OE3GAS-1").port, 2)
        self.assertEqual(t.route("oe3gas-9").port, 1)
        self.assertEqual(t.route("OE3GAS-0").port, 1)
        self.assertIsNone(t.route("OE1ABC"))

    def test_sender_needs_ip_and_call(self):
        t = PeerTable(parse_peers({"OE3GAS": "127.0.0.1:1", "OE3XAB-7": "44.143.0.1"}))
        self.assertIsNotNone(t.sender("127.0.0.1", "OE3GAS-9"))     # any SSID
        self.assertIsNotNone(t.sender("::ffff:127.0.0.1", "OE3GAS"))
        self.assertIsNone(t.sender("127.0.0.2", "OE3GAS"))          # wrong IP
        self.assertIsNone(t.sender("127.0.0.1", "OE1ABC"))          # call not that peer's
        self.assertIsNotNone(t.sender("44.143.0.1", "OE3XAB-7"))
        self.assertIsNone(t.sender("44.143.0.1", "OE3XAB-8"))       # only that SSID
        self.assertIsNone(t.sender("not an ip", "OE3GAS"))


class FakeTransport:
    def __init__(self):
        self.sent: list[tuple[bytes, tuple]] = []

    def sendto(self, data, addr):
        self.sent.append((data, addr))

    def is_closing(self):
        return False


class EndpointTests(unittest.TestCase):
    def setUp(self):
        self.got: list[bytes] = []
        peers = parse_peers({"OE3GAS": "127.0.0.1:10094", "OE3XWR": "127.0.0.5:93"})
        self.ep = AxudpEndpoint("127.0.0.1", 0, peers, lambda port, data: self.got.append(data))

    def test_send_needs_socket(self):
        self.assertFalse(self.ep.send(sabm(CLIENT, BOX)))

    def test_send_routes_by_dest_and_digi(self):
        self.ep._transport = FakeTransport()
        self.assertTrue(self.ep.send(sabm(CLIENT, BOX)))
        self.assertFalse(self.ep.send(sabm("OE1ABC", BOX)))            # no peer
        self.assertTrue(self.ep.send(sabm("OE1ABC", BOX, path=["OE3XWR"])))   # via digi
        sent = self.ep._transport.sent
        self.assertEqual([a for _, a in sent], [("127.0.0.1", 10094), ("127.0.0.5", 93)])
        self.assertEqual(axudp.decode(sent[0][0]), sabm(CLIENT, BOX))
        self.assertEqual(self.ep.dropped["no_route"], 1)
        self.assertEqual(self.ep.tx_frames, 2)

    def test_receive_filters(self):
        good = axudp.encode(sabm())
        self.ep.received(good, ("127.0.0.1", 10094))
        self.ep.received(good, ("127.0.0.9", 10094))                   # stranger IP
        self.ep.received(axudp.encode(sabm(src="OE1ABC")), ("127.0.0.1", 10094))  # spoofed
        bad = bytearray(good)
        bad[-1] ^= 0xFF
        self.ep.received(bytes(bad), ("127.0.0.1", 10094))
        self.ep.received(b"junk", ("127.0.0.1", 10094))
        self.assertEqual(self.got, [sabm()])
        self.assertEqual(self.ep.dropped, {"fcs": 1, "stranger": 2, "garbage": 1,
                                           "no_route": 0})


class SocketTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_endpoints_over_loopback(self):
        got_box: list[bytes] = []
        got_client: list[bytes] = []
        box = AxudpEndpoint("127.0.0.1", 0, {}, lambda p, d: got_box.append(d))
        client = AxudpEndpoint("127.0.0.1", 0, {}, lambda p, d: got_client.append(d))
        await box.open()
        await client.open()
        try:
            self.assertTrue(box.connected.is_set())
            box.table = PeerTable({CLIENT: Peer(CLIENT, "127.0.0.1", client.local_port)})
            client.table = PeerTable({BOX: Peer(BOX, "127.0.0.1", box.local_port)})
            self.assertTrue(client.send(sabm()))
            ua = ax.u_frame("UA", CLIENT, BOX, command=False, pf=True).encode()
            for _ in range(50):
                if got_box:
                    break
                await asyncio.sleep(0.01)
            self.assertEqual(got_box, [sabm()])
            self.assertTrue(box.send(ua))
            for _ in range(50):
                if got_client:
                    break
                await asyncio.sleep(0.01)
            self.assertEqual(got_client, [ua])
        finally:
            box.close()
            client.close()
        self.assertFalse(box.connected.is_set())


if __name__ == "__main__":
    unittest.main()
