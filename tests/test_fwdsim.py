"""Tests for the forward test tool fwdsim (no radio, no TinyBox needed)."""

from __future__ import annotations

import asyncio
import struct
import unittest
from pathlib import Path

from fwdsim import agw as fagw
from fwdsim.agw import AgwClient, Frame
from fwdsim.config import Config
from fwdsim.harness import Harness
from fwdsim.model import addr_call, route_score, split_wire_text
from fwdsim.net import SimNet, make_standin
from fwdsim.protocol import (ACCEPT, LATER, REJECT, ProtocolError, checksum, parse_fs,
                             parse_proposal, parse_sid)
from fwdsim.runner import run_cases
from fwdsim.scenarios import CASES
from fwdsim.session import ForwardSession
from fwdsim.store import Store


class ProtocolTests(unittest.TestCase):
    def test_sid(self):
        s = parse_sid("[FBB-7.04j-ABFHM$]")
        self.assertEqual(s.author, "FBB")
        self.assertTrue(s.fbb and s.bid and s.hier)
        b1 = parse_sid("[BPQ-6.0.24.1-B1FIHJM$]")
        self.assertEqual(b1.features["B"], "1")
        self.assertIsNone(parse_sid("OE3GAS BBS>"))

    def test_checksum_and_proposal(self):
        line = "FB P OE3GAS OE3XTC.#NOE.AUT.EU OE1ABC 12_OE3GAS 345"
        p = parse_proposal(line)
        self.assertEqual((p.type, p.bid, p.size), ("P", "12_OE3GAS", 345))
        cs = int(checksum([line]), 16)
        self.assertEqual((sum((line + "\r").encode()) + cs) % 256, 0)
        with self.assertRaises(ProtocolError):
            parse_proposal("FB P OE3GAS WW ALL 12_OE3GAS")

    def test_w0rli_syntax(self):
        from fwdsim.protocol import parse_rli_response, parse_send_cmd
        s = parse_sid("[ZFJ-H$]")                       # AUTHOR_DATA is optional
        self.assertEqual((s.author, s.version), ("ZFJ", ""))
        self.assertTrue(s.hier and s.bid)
        self.assertEqual(parse_sid("[FBB-7.0-10-ABFHM$]").version, "7.0-10")
        p = parse_send_cmd("SB WANT @ ALLSCV < N6ZFJ $2345_N6QMY")
        self.assertEqual((p.type, p.to_call, p.at_addr, p.from_call, p.bid),
                         ("B", "WANT", "ALLSCV", "N6ZFJ", "2345_N6QMY"))
        p = parse_send_cmd("SP WA2ABC@N2AAA < N9AAA")      # '@' without blanks, no BID
        self.assertEqual((p.at_addr, p.bid), ("N2AAA", ""))
        self.assertIsNone(parse_send_cmd("SX 5"))
        self.assertEqual(parse_rli_response("OK #32190"), ACCEPT)
        self.assertEqual(parse_rli_response("NO duplicate bid"), REJECT)
        self.assertEqual(parse_rli_response("L"), LATER)
        self.assertIsNone(parse_rli_response(">"))
        from fwdsim.model import rline_call
        self.assertEqual(rline_call("R:930101/0000 1530@KA6FUB.#NOCAL.CA.USA.NOAM"), "KA6FUB")
        self.assertEqual(rline_call("R:930108/1729 @:N6QMY.#NOCAL.CA.USA.NA Fremont #:1114"),
                         "N6QMY")

    def test_fs(self):
        self.assertEqual(parse_fs("FS +-=", 3), [ACCEPT, REJECT, LATER])
        self.assertEqual(parse_fs("FS Y!120N", 3), [ACCEPT, ACCEPT, REJECT])
        with self.assertRaises(ProtocolError):
            parse_fs("FS +", 2)

    def test_addresses_ignore_ssid(self):
        self.assertEqual(addr_call("OE3XTC-1.#NOE.AUT.EU"), "OE3XTC")
        self.assertEqual(route_score("OE1ABC.#WIE.AUT.EU", "AUT.EU"), 2)
        self.assertEqual(route_score("DL0XTC.#BAY.DEU.EU", "DL0XTC"), 100)
        self.assertEqual(route_score("X.Y", "WW"), 0.5)

    def test_wire_text(self):
        r, body = split_wire_text("R:261006/1200Z @:OE3GAS.#OOE.AUT.EU\n\nHello\nWorld")
        self.assertEqual(len(r), 1)
        self.assertEqual(body, "Hello\nWorld")


class HopTests(unittest.IsolatedAsyncioTestCase):
    async def test_internal_hop_writes_rlines(self):
        cfg, store = Config(), Store()
        net = SimNet(cfg, store)
        m = net.remote.create("P", "OE1ABC", "OE3XTC.#NOE.AUT.EU", "via hop", "text")
        await net.settle()
        at_hop = net.hop.find(bid=m.bid)
        self.assertEqual(len(at_hop), 1)
        self.assertEqual(net.hop.pending(cfg.tinybox.call)[0].bid, m.bid)
        self.assertEqual(len(at_hop[0].rlines), 2)


class StubRunTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_cases_against_stand_in(self):
        cfg, store = Config(), Store()
        cfg.wait_for_tinybox = 5
        h = Harness(cfg, store, stub=True, use_agw=False, stub_timeout=2)
        await h.start()
        lines: list[str] = []
        try:
            passed, failed, _ = await run_cases(h, list(CASES), out=lines.append)
        finally:
            await h.stop()
        self.assertEqual(failed, 0, "\n".join(lines))
        self.assertGreaterEqual(passed, 20)


class FakeDirewolf:
    """Connects AGW clients with each other, like two stations on one channel."""

    def __init__(self) -> None:
        self.writers: dict[str, asyncio.StreamWriter] = {}

    def _send(self, call: str, f: Frame) -> None:
        w = self.writers.get(call)
        if w is not None:
            w.write(f.pack())

    async def handle(self, reader, writer) -> None:
        try:
            while True:
                f = await fagw.read_frame(reader)
                if f.kind == "R":
                    writer.write(Frame("R", data=struct.pack("<hhhh", 1, 0, 7, 0)).pack())
                elif f.kind == "X":
                    self.writers[f.call_from] = writer
                    writer.write(Frame("X", call_from=f.call_from, data=b"\x01").pack())
                elif f.kind in ("C", "v"):
                    a, b = f.call_from, f.call_to
                    if b in self.writers:
                        self._send(a, Frame("C", call_from=b, call_to=a, data=b"*** CONNECTED"))
                        self._send(b, Frame("C", call_from=a, call_to=b, data=b"*** CONNECTED"))
                    else:
                        self._send(a, Frame("d", call_from=b, call_to=a))
                elif f.kind == "D":
                    self._send(f.call_to, Frame("D", pid=0xF0, call_from=f.call_from,
                                                call_to=f.call_to, data=f.data))
                elif f.kind == "d":
                    self._send(f.call_to, Frame("d", call_from=f.call_from, call_to=f.call_to))
                elif f.kind == "Y":
                    writer.write(Frame("Y", call_from=f.call_from, call_to=f.call_to,
                                       data=struct.pack("<I", 0)).pack())
        except (asyncio.IncompleteReadError, ConnectionError):
            pass


class AgwTests(unittest.IsolatedAsyncioTestCase):
    async def test_forward_over_agw(self):
        dw = FakeDirewolf()
        server = await asyncio.start_server(dw.handle, "127.0.0.1", 0)
        cfg, store = Config(), Store()
        cfg.agw.port = server.sockets[0].getsockname()[1]
        cfg.agw.paclen = 64
        net = SimNet(cfg, store)
        standin = make_standin(cfg, store)
        done: asyncio.Queue = asyncio.Queue()

        async def incoming(link):
            s = ForwardSession(standin, link, cfg.hop.call, master=False, timeout=5)
            await done.put(await s.run())

        tb = AgwClient(cfg.agw, cfg.tinybox.ax25_call, incoming)
        hop = AgwClient(cfg.agw, cfg.hop_ax25_call)
        await tb.start()
        await hop.start()
        try:
            m = net.hop.create("P", "OE1ABC", cfg.tinybox.haddress, "over AGW",
                               "\n".join(["line of text"] * 30))
            link = await hop.connect(cfg.tinybox.ax25_call, timeout=5)
            r = await ForwardSession(net.hop, link, cfg.tinybox.call, master=True,
                                     timeout=5).run()
            slave = await asyncio.wait_for(done.get(), 10)
            self.assertTrue(r.ok, r.error)
            self.assertTrue(slave.ok, slave.error)
            self.assertEqual(len(standin.find(bid=m.bid)), 1)
        finally:
            await hop.stop()
            await tb.stop()
            server.close()



class FwdsimConfigTests(unittest.TestCase):
    """CR70: fwdsim takes the TinyBox values from tinybox.conf."""

    def test_values_from_tinybox_conf(self):
        import tempfile
        from fwdsim import config as fcfg
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "tinybox.conf").write_text(
                "[station]\nmailbox_call = OE3GAS-1\nhaddress = OE3GAS.#NOE.AUT.EU\n"
                "[telnet]\nport = 6400\n[storage]\ndata_dir = daten\n", encoding="utf-8")
            (Path(d) / "direwolf.conf").write_text("AGWPORT 8010\nPACLEN 256\nEMAXFRAME 6\n",
                                                   encoding="utf-8")
            p = Path(d) / "fwdsim.conf"
            p.write_text(f"[tinybox]\nconf = tinybox.conf\ntelnet_port = 6500\n"
                         f"[agw]\ndirewolf_conf = {d}\n", encoding="utf-8")
            cfg = fcfg.load(p)
            t = cfg.tinybox
            self.assertEqual((t.call, t.ax25_call, t.haddress), ("OE3GAS", "OE3GAS-1",
                                                                 "OE3GAS.#NOE.AUT.EU"))
            self.assertEqual(t.telnet_port, 6500)                 # fwdsim.conf overrides
            self.assertEqual(Path(t.db), Path(d) / "daten" / "tinybox.db")
            self.assertEqual((cfg.agw.port, cfg.agw.paclen, cfg.agw.max_outstanding),
                             (8010, 256, 6))
            self.assertIn("telnet_port", cfg.hints[0])

if __name__ == "__main__":
    unittest.main()
