"""CR89 (audit TB-10, TB-11, TB-20a/b): the forward queue cannot be blocked, no
Ctrl-Z injection, restart data of another proposal are not used, a session
cannot be held open."""

from __future__ import annotations

import asyncio
import time
import unittest
from types import SimpleNamespace

from tinybox import addressing
from tinybox.addressing import BID_RE
from tinybox.fwd.protocol import Proposal, ProtocolError
from tinybox.fwd.receive import Receiver
from tinybox.fwd.send import Sender, wire_lines
from tinybox.fwd.session import MAX_NULL_LINES, ForwardSession, SessionResult

from tests.test_forward_module import fwd_app, gas


def new_msg(app, **kw):
    args = dict(from_call="OE1ABC", to_call="ALL", type="B", subject="x", body="x",
                origin="telnet", at_addr="WW")
    args.update(kw)
    return app.service.create(**args)


class Bid(unittest.TestCase):
    def setUp(self):
        self.app = fwd_app(gas())

    def test_announced_bids_do_not_take_the_bid_away(self):        # TB-10
        nxt = self.app.store.get(new_msg(self.app)).id + 1
        for n in range(nxt, nxt + 5):                               # a partner claims them
            self.app.store.bid_add(addressing.make_bid(n, "OE3XTC"), "forward")
        for _ in range(5):
            m = self.app.store.get(new_msg(self.app))
            self.assertTrue(m.bid and BID_RE.match(m.bid), m.bid)
            self.assertNotEqual(m.bid, addressing.make_bid(m.id, "OE3XTC"))

    def test_random_bid(self):
        seen = {addressing.random_bid("OE3XTC-1") for _ in range(200)}
        self.assertGreater(len(seen), 190)
        for b in seen:
            self.assertRegex(b, r"^[A-Z][A-Z0-9]{4}_OE3XTC$")
        self.assertLessEqual(len(addressing.random_bid("DL0ABCD")), 12)

    def test_old_message_without_bid_gets_one_and_queue_goes_on(self):
        msg_id = new_msg(self.app)
        self.app.store.fwd_enqueue(msg_id, "OE3GAS")
        self.app.store._db.execute("UPDATE messages SET bid = NULL WHERE id = ?", (msg_id,))
        tx = Sender(self.app.service, "OE3GAS")
        [m] = tx.pending()
        self.assertTrue(BID_RE.match(m.bid))
        self.assertEqual(len(tx.fb_line(tx.proposal(m)).split()), 7)
        self.assertEqual(self.app.store.get(msg_id).bid, m.bid)

    def test_unusable_message_is_skipped(self):
        bad, good = new_msg(self.app), new_msg(self.app)
        for i in (bad, good):
            self.app.store.fwd_enqueue(i, "OE3GAS")
        self.app.store._db.execute("UPDATE messages SET from_call = '' WHERE id = ?", (bad,))
        tx = Sender(self.app.service, "OE3GAS")
        with self.assertLogs("tinybox.forward", "ERROR"):
            self.assertEqual([m.id for m in tx.pending()], [good])
        self.assertEqual(self.app.store.fwd_states(bad)["OE3GAS"], "rejected")


class CtrlZ(unittest.TestCase):                                     # TB-11
    def setUp(self):
        self.app = fwd_app(gas())

    def test_strip(self):
        self.assertEqual(addressing.strip_controls("a\x1ab\x1b[2Jc\td\ne\x00"), "ab[2Jc\td\ne")

    def test_received_text_has_no_ctrl_z(self):
        rx = Receiver(self.app.service, "OE3GAS")
        rx.mode = "fbb"
        p = Proposal("FA", "B", "OE1ABC", "WW", "ALL", "77_OE3GAS", 40)
        msg_id = rx.store(p, "Hallo\x1a", "Text\x1a\nFB P X Y Z 1_X 10\nF>\n")
        m = self.app.store.get(msg_id)
        self.assertNotIn("\x1a", m.subject + m.body)

    def test_nothing_goes_out(self):
        m = self.app.store.get(new_msg(self.app, subject="S\x1a", body="a\x1a\nb"))
        self.assertFalse(any("\x1a" in x for x in wire_lines(m)))
        from prcore import lzhuf
        self.assertNotIn(b"\x1a", lzhuf.decompress(Sender.payload(m, crc=False), 10000))


class Restart(unittest.TestCase):                                   # TB-20a
    def setUp(self):
        self.app = fwd_app(gas())
        self.s = ForwardSession("OE3XTC-1", gas(), None, master=False, transport="tcp",
                                service=self.app.service)

    def test_restart_data_of_another_proposal_dropped(self):
        st = self.app.store
        st.partial_put("OE3GAS", "9_OE3GAS", b"x" * 100, size=500)
        same = Proposal("FA", "B", "OE1ABC", "WW", "ALL", "9_OE3GAS", 500)
        other = Proposal("FA", "B", "OE1ABC", "WW", "ALL", "9_OE3GAS", 640)
        self.assertEqual(self.s._restart_answer(same), "!100")
        self.assertEqual(self.s._restart_answer(other), "+")
        self.assertIsNone(st.partial_get("OE3GAS", "9_OE3GAS"))

    def test_old_rows_without_size_are_not_used(self):
        self.app.store.partial_put("OE3GAS", "9_OE3GAS", b"x" * 100)     # size 0
        p = Proposal("FA", "B", "OE1ABC", "WW", "ALL", "9_OE3GAS", 500)
        self.assertEqual(self.s._restart_answer(p), "+")


class FakeLink:
    def __init__(self, lines, gap=0.0):
        self.lines, self.gap = list(lines), gap

    async def readline(self, timeout):
        if not self.lines:
            await asyncio.sleep(timeout)
            raise asyncio.TimeoutError
        if self.gap > timeout:
            await asyncio.sleep(timeout)
            raise asyncio.TimeoutError
        await asyncio.sleep(self.gap)
        return self.lines.pop(0)


def session(link, timeout=1, max_min=60):
    s = ForwardSession.__new__(ForwardSession)
    s.p = SimpleNamespace(call="OE3GAS", timeout=timeout, max_session_min=max_min)
    s.link = link
    s.r = SessionResult("OE3GAS", True, "tcp")
    s._deadline = time.monotonic() + max_min * 60
    return s


class HoldOpen(unittest.IsolatedAsyncioTestCase):                   # TB-20b
    async def test_null_lines_do_not_extend_the_timeout(self):
        s = session(FakeLink([";"] * 100, gap=0.15), timeout=0.5)
        t0 = time.monotonic()
        with self.assertRaises(asyncio.TimeoutError):
            await s._command()
        self.assertLess(time.monotonic() - t0, 1.0)

    async def test_too_many_null_lines(self):
        s = session(FakeLink([";"] * (MAX_NULL_LINES + 5) + ["FF"]), timeout=5)
        with self.assertRaisesRegex(ProtocolError, "in a row"):
            await s._command()

    async def test_a_few_null_lines_are_fine(self):
        s = session(FakeLink([";", "", "; hello", "FF"]), timeout=5)
        self.assertEqual(await s._command(), "FF")

    async def test_session_has_an_end(self):
        s = session(FakeLink(["FB x"] * 1000, gap=0.05), timeout=5)
        s._deadline = time.monotonic() + 0.3
        with self.assertRaisesRegex(ProtocolError, "session longer"):
            for _ in range(1000):
                await s._command()


if __name__ == "__main__":
    unittest.main()
