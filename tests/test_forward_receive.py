"""F3: TinyBox receives mail from partner mailboxes (fwdsim as the partner).

Runs the fwdsim test cases of milestone F3 in-process over TCP: FBB batch and
W0RLI ASCII, R: lines, loops, old mail, duplicates, form errors, aborts.
"""

from __future__ import annotations

import asyncio
import unittest
from datetime import timedelta

from fwdsim.harness import tinybox_login
from fwdsim.link import tcp_connect
from fwdsim.model import make_rline, utc_now
from fwdsim.protocol import ACCEPT, REJECT
from fwdsim.session import Faults, ForwardSession as SimSession

from tinybox.adapters.brocast import wanted
from tinybox.adapters.forward import ForwardModule
from tinybox.fwd.protocol import Proposal, parse_sid
from tinybox.fwd.receive import Receiver

from tests.test_forward_module import HADDR, free_port, fwd_app, gas, sim_net

BODY = "Test message.\nSecond line."


class ReceiveTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = fwd_app(gas())
        self.module = ForwardModule(self.app)
        self.module.cfg.listen_port = free_port()
        await self.module.start_server()
        self.net = sim_net()
        self.hop, self.remote = self.net.hop, self.net.remote

    async def asyncTearDown(self):
        self.module.server.close()

    async def hop_calls(self, faults: Faults | None = None, timeout: float = 5):
        """OE3GAS calls TinyBox and hands over its queue; returns (fwdsim, TinyBox) results."""
        self.module.last.pop("OE3GAS", None)
        await self.net.settle()                   # DL0XTC -> OE3GAS first
        link = await tcp_connect("127.0.0.1", self.module.listen_port, "OE3GAS>tinybox")
        await tinybox_login(link, "OE3GAS", "geheim", 5)
        r = await SimSession(self.hop, link, "OE3XTC", master=True, faults=faults,
                             timeout=timeout).run()
        for _ in range(50):                       # TinyBox finishes its side
            if "OE3GAS" in self.module.last:
                break
            await asyncio.sleep(0.05)
        return r, self.module.last.get("OE3GAS")

    def got(self, bid: str):
        return self.app.store.get_by_bid(bid)

    # --- T04-T06: delivery -----------------------------------------------------

    async def test_t04_personal_mail(self):
        m = self.hop.create("P", "OE1ABC", HADDR, "T04", BODY)
        r, tb = await self.hop_calls()
        self.assertTrue(r.ok, r.error)
        self.assertTrue(tb.ok, tb.error)
        msg = self.got(m.bid)
        self.assertEqual((msg.type, msg.to_call, msg.from_call, msg.origin, msg.fwd),
                         ("P", "OE1ABC", "OE3GAS", "forward", ""))
        self.assertEqual(msg.body, BODY)
        self.assertEqual(msg.bid_kind, "M")
        calls = [x.split("@:")[1].split(".")[0] for x in msg.rlines.split("\n")]
        self.assertEqual(calls, ["OE3XTC", "OE3GAS"])

    async def test_t05_over_the_hop(self):
        m = self.remote.create("P", "OE1ABC", HADDR, "T05", BODY)
        await self.hop_calls()
        rl = self.got(m.bid).rlines.split("\n")
        self.assertEqual([x.split("@:")[1].split(".")[0] for x in rl],
                         ["OE3XTC", "OE3GAS", "DL0XTC"])

    async def test_t06_bulletins(self):
        a = self.hop.create("B", "ALL", "WW", "T06 WW", BODY)
        b = self.remote.create("B", "ALL", "AUT", "T06 AUT", BODY)
        await self.hop_calls()
        self.assertEqual(self.got(a.bid).type, "B")
        self.assertEqual(self.got(a.bid).bid_kind, "B")
        self.assertIsNotNone(self.got(b.bid))
        # only partner is OE3GAS, where it came from: nothing to forward, not held
        self.assertEqual(self.got(a.bid).fwd, "")
        self.assertEqual(self.app.store.fwd_queue_list(), [])
        self.assertIn(self.got(a.bid).id, [x.id for x in self.app.service.list_for("OE1ABC", False)])

    # --- robustness -----------------------------------------------------------

    async def test_t08_same_bid_twice(self):
        m = self.hop.create("P", "OE1ABC", HADDR, "T08", BODY)
        await self.hop_calls()
        self.net.store.set_queue("OE3GAS", m.id, "OE3XTC", "open")
        r, tb = await self.hop_calls()
        self.assertTrue(r.ok, r.error)
        self.assertEqual(r.sent, {m.bid: REJECT})
        self.assertEqual(tb.rejected, [m.bid])

    async def test_t09_loop_is_held(self):
        fake = make_rline(utc_now() - timedelta(hours=1), HADDR, "Hollabrunn", 9, "9_OE3XTC")
        m = self.hop.create("P", "OE1ABC", HADDR, "T09", BODY, extra_rlines=[fake])
        await self.hop_calls()
        self.assertEqual(self.got(m.bid).fwd, "H")
        self.assertIn("loop", self.got(m.bid).note)

    async def test_t27_old_rline_form_loop(self):
        when = utc_now() - timedelta(hours=1)
        m = self.hop.create("P", "OE1ABC", HADDR, "T27", BODY,
                            extra_rlines=[f"R:{when:%y%m%d/%H%M} 1530@{HADDR}"])
        await self.hop_calls()
        self.assertEqual(self.got(m.bid).fwd, "H")

    async def test_t19_too_old_is_held(self):
        m = self.hop.create("P", "OE1ABC", HADDR, "T19", BODY,
                            when=utc_now() - timedelta(days=400))
        await self.hop_calls()
        self.assertEqual(self.got(m.bid).fwd, "H")

    async def test_t11_ascii_without_f(self):
        m = self.hop.create("P", "OE1ABC", HADDR, "T11", BODY)
        b = self.hop.create("B", "ALL", "WW", "T11 B", BODY)
        r, tb = await self.hop_calls(Faults(sid="[FWDSIM-0.1-HM$]"))
        self.assertTrue(r.ok, r.error)
        self.assertTrue(tb.ok, tb.error)
        self.assertEqual((r.mode, tb.mode), ("rli", "ascii"))
        self.assertEqual(r.sent, {m.bid: ACCEPT, b.bid: ACCEPT})
        self.assertEqual(self.got(m.bid).body, BODY)
        self.assertEqual(self.got(b.bid).bid_kind, "B")

    async def test_t12_b1_in_sid(self):
        m = self.hop.create("P", "OE1ABC", HADDR, "T12", BODY)
        r, _ = await self.hop_calls(Faults(sid="[FWDSIM-0.1-B1FHM$]"))
        self.assertTrue(r.ok, r.error)
        self.assertFalse([x for x in r.transcript if x.startswith("< FA ")])
        self.assertIsNotNone(self.got(m.bid))

    async def test_t13_twelve_messages(self):
        ms = [self.hop.create("P", "OE1ABC", HADDR, f"T13 {i}", BODY) for i in range(12)]
        r, tb = await self.hop_calls()
        self.assertTrue(r.ok, r.error)
        self.assertGreaterEqual(len([x for x in r.transcript if x.startswith("> F>")]), 3)
        self.assertEqual(len(tb.received), 12)
        self.assertTrue(all(self.got(m.bid) for m in ms))

    async def test_t15_abort_in_message(self):
        m = self.hop.create("P", "OE1ABC", HADDR, "T15", BODY + "\n" + "x" * 200)
        _, tb = await self.hop_calls(Faults(abort_after=40))
        self.assertFalse(tb.ok)
        self.assertIsNone(self.got(m.bid))
        r, _ = await self.hop_calls()             # the partner tries again
        self.assertTrue(r.ok, r.error)
        self.assertIsNotNone(self.got(m.bid))

    async def test_t16_form_errors(self):
        for faults in (Faults(fb_fields=6), Faults(bad_checksum=True)):
            m = self.hop.create("P", "OE1ABC", HADDR, "T16", BODY)
            r, tb = await self.hop_calls(faults)
            self.assertFalse(r.ok)
            self.assertFalse(tb.ok)
            self.assertIsNone(self.got(m.bid))
            self.net.store.set_queue("OE3GAS", m.id, "OE3XTC", "done")

    async def test_t16_no_ctrl_z_times_out(self):
        self.app.cfg.forward.partners["OE3GAS"].timeout = 1
        m = self.hop.create("P", "OE1ABC", HADDR, "T16 no ^Z", BODY)
        r, tb = await self.hop_calls(Faults(no_ctrl_z=True), timeout=3)
        self.assertFalse(tb.ok)
        self.assertIn("timeout", tb.error)
        self.assertIsNone(self.got(m.bid))

    async def test_t16_long_subject_and_too_large(self):
        long = self.hop.create("P", "OE1ABC", HADDR, "T16 " + "L" * 100, BODY)
        big = self.hop.create("P", "OE1ABC", HADDR, "T16 big", "\n".join(["y" * 70] * 300))
        r, _ = await self.hop_calls()
        self.assertTrue(r.ok, r.error)
        self.assertLessEqual(len(self.got(long.bid).subject), 80)
        self.assertEqual(r.sent[big.bid], REJECT)
        self.assertIsNone(self.got(big.bid))

    async def test_t24_crlf_latin1(self):
        m = self.hop.create("P", "OE1ABC", HADDR, "T24", "Grüße aus Linz äöü")
        r, _ = await self.hop_calls(Faults(crlf=True, latin1=True))
        self.assertTrue(r.ok, r.error)
        self.assertIn("Grüße", self.got(m.bid).body)

    async def test_t25_ssid_in_at_field(self):
        m = self.hop.create("P", "OE1ABC", "OE3XTC-1.#NOE.AUT.EU", "T25", BODY)
        await self.hop_calls()
        self.assertEqual(self.got(m.bid).fwd, "")

    async def test_t28_ex_and_null_lines(self):
        m = self.hop.create("P", "OE1ABC", HADDR, "T28 ascii", "Zeile 1\n/EX\nZeile 3")
        r1, _ = await self.hop_calls(Faults(sid="[FWDSIM-0.1-H$]", eomb=True, null_lines=True))
        n = self.hop.create("P", "OE1ABC", HADDR, "T28 fbb", BODY)
        r2, _ = await self.hop_calls(Faults(null_lines=True))
        self.assertTrue(r1.ok, r1.error)
        self.assertTrue(r2.ok, r2.error)
        self.assertEqual(self.got(m.bid).body, "Zeile 1\n/EX\nZeile 3")
        self.assertIsNotNone(self.got(n.bid))

    async def test_nts_rejected_in_ascii(self):
        m = self.hop.create("T", "12345", HADDR, "NTS", BODY)
        r, _ = await self.hop_calls(Faults(sid="[FWDSIM-0.1-H$]"))
        self.assertEqual(r.sent.get(m.bid), REJECT)
        self.assertIsNone(self.got(m.bid))

    async def test_known_mid_ascii_without_m_is_held(self):
        m = self.hop.create("P", "OE1ABC", HADDR, "MID", BODY)
        await self.hop_calls()                         # first time: FBB
        self.net.store.set_queue("OE3GAS", m.id, "OE3XTC", "open")
        r, _ = await self.hop_calls(Faults(sid="[FWDSIM-0.1-H$]"))
        self.assertEqual(r.sent.get(m.bid), ACCEPT)
        held = [x for x in self.app.store.list_messages()
                if x.subject == "MID" and x.fwd == "H"]
        self.assertEqual(len(held), 1)
        self.assertIn(m.bid, held[0].note)

    async def test_known_bid_ascii_with_m_rejected(self):
        m = self.hop.create("P", "OE1ABC", HADDR, "MID2", BODY)
        await self.hop_calls()
        self.net.store.set_queue("OE3GAS", m.id, "OE3XTC", "open")
        r, _ = await self.hop_calls(Faults(sid="[FWDSIM-0.1-HM$]"))
        self.assertEqual(r.sent.get(m.bid), REJECT)


class TinyBoxCallsTests(unittest.IsolatedAsyncioTestCase):
    async def _call(self, faults: Faults | None = None):
        net = sim_net()
        done: asyncio.Queue = asyncio.Queue()

        async def handle(reader, writer):
            from fwdsim.link import TcpLink as SimTcpLink
            s = SimSession(net.hop, SimTcpLink(reader, writer, "hop<tcp"), "OE3XTC",
                           master=False, faults=faults, timeout=5)
            await done.put(await s.run())

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        m = net.hop.create("P", "OE1ABC", HADDR, "waiting at OE3GAS", BODY)
        app = fwd_app(gas(port=server.sockets[0].getsockname()[1]))
        try:
            r = await ForwardModule(app).call("OE3GAS")
            sim = await asyncio.wait_for(done.get(), 5)
        finally:
            server.close()
        return app, m, r, sim

    async def test_reverse_fbb(self):
        app, m, r, sim = await self._call()
        self.assertTrue(r.ok and sim.ok, (r.error, sim.error))
        self.assertEqual(r.received, [m.bid])
        self.assertIsNotNone(app.store.get_by_bid(m.bid))

    async def test_reverse_ascii(self):
        app, m, r, sim = await self._call(Faults(sid="[FWDSIM-0.1-H$]"))
        self.assertTrue(r.ok and sim.ok, (r.error, sim.error))
        self.assertEqual(r.mode, "ascii")
        self.assertEqual(r.received, [m.bid])
        self.assertEqual(app.store.get_by_bid(m.bid).body, BODY)


class UnitTests(unittest.TestCase):
    def setUp(self):
        self.app = fwd_app(gas())
        self.rx = Receiver(self.app.service, "OE3GAS")
        self.rx.mode = "fbb"

    def prop(self, **kw):
        base = dict(kind="FB", type="P", from_call="OE3GAS", at_addr=HADDR, to_call="OE1ABC",
                    bid="1_OE3GAS", size=100)
        base.update(kw)
        return Proposal(**base)

    def test_answers(self):
        self.assertEqual(self.rx.answer(self.prop()), "+")
        self.assertEqual(self.rx.answer(self.prop(type="T")), "-")
        self.assertEqual(self.rx.answer(self.prop(to_call="NO CALL")), "-")
        self.assertEqual(self.rx.answer(self.prop(at_addr="BAD..ADDR")), "+")   # taken, held
        self.assertEqual(self.rx.answer(self.prop(size=10**6)), "-")
        self.assertEqual(self.rx.answer(self.prop(), {"1_OE3GAS"}), "-")

    def test_store_and_duplicate(self):
        p = self.prop()
        msg_id = self.rx.store(p, "Hello", "R:261007/1200Z @:OE3GAS.#OOE.AUT.EU #:1 $:1_OE3GAS\n\nText")
        msg = self.app.store.get(msg_id)
        self.assertEqual(msg.body, "Text")
        self.assertEqual(len(msg.rlines.split("\n")), 2)
        self.assertEqual(self.rx.answer(p), "-")                  # FBB: known BID
        self.rx.mode = "ascii"
        self.rx.peer_sid = parse_sid("[X-1-H$]")
        self.assertEqual(self.rx.answer(p), "+")                  # known MID, no M: held
        self.rx.peer_sid = parse_sid("[X-1-HM$]")
        self.assertEqual(self.rx.answer(p), "-")

    def test_bad_address_is_held_not_lost(self):
        p = self.prop(at_addr="OE3XTC.@NOE.AUT.EU", bid="6_OE3GAS")   # seen from LinBPQ
        self.assertEqual(self.rx.answer(p), "+")
        msg = self.app.store.get(self.rx.store(p, "B2 Test", "Text\n\n"))
        self.assertEqual((msg.fwd, msg.at_addr, msg.body), ("H", "", "Text"))
        self.assertIn("OE3XTC.@NOE.AUT.EU", msg.note)

    def test_forwarded_bulletins_and_brocast(self):
        self.rx.store(self.prop(type="B", to_call="ALL", at_addr="WW", bid="7_OE3GAS"),
                      "News", "Text")
        msg = self.app.store.get_by_bid("7_OE3GAS")
        self.assertFalse(wanted(msg, self.app))                   # default: not on the air
        self.app.cfg.forward.publish_to_brocast = True
        self.assertTrue(wanted(msg, self.app))


if __name__ == "__main__":
    unittest.main()
