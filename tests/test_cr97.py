"""CR97 (audit TB-03, TB-13, TB-17, TB-18, TB-19): what another station can make
us send or keep is bounded."""

from __future__ import annotations

import unittest

from kisshub import linkstats
from prcore.ax25 import frame as ax
from prcore.ax25.link import Ax25Link, LinkCfg
from prcore.kissport import MAX_LINKS, plausible_call
from tbclient.budget import ALL_BYTES, PER_CALL_BYTES, Bucket, SendBudget
from tinybox.session import MAX_PER_CALL, SessionRegistry

from tests.test_prcore_kissport import MYCALL, Port

A_CALL, B_CALL = "OE3ABC", "OE3GAS-1"


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class Budget(unittest.TestCase):                                 # TB-03
    def test_per_call_and_all(self):
        c = Clock()
        b = SendBudget(clock=c)
        self.assertTrue(b.allow("OE1ABC-5", PER_CALL_BYTES - 10))
        with self.assertLogs("tbclient.budget", "WARNING"):
            self.assertFalse(b.allow("OE1ABC", 100))              # same base call
        self.assertTrue(b.allow("OE1XYZ", 100))                   # another station
        c.t += 30 * 60                                            # refilled
        self.assertTrue(b.allow("OE1ABC", 50_000))

    def test_many_made_up_calls_hit_the_total(self):
        b = SendBudget(clock=Clock())
        sent = sum(64 * 1024 for i in range(20) if b.allow(f"OE{i}X", 64 * 1024))
        self.assertLessEqual(sent, ALL_BYTES)

    def test_often(self):
        c = Clock()
        b = SendBudget(clock=c)
        self.assertFalse(b.often("OE1ABC", "Fabc", 2, 3600))
        self.assertFalse(b.often("OE1ABC-1", "Fabc", 2, 3600))
        with self.assertLogs("tbclient.budget", "WARNING"):
            self.assertTrue(b.often("OE1ABC", "Fabc", 2, 3600))
        c.t += 3601
        self.assertFalse(b.often("OE1ABC", "Fabc", 2, 3600))

    def test_bucket(self):
        c = Clock()
        k = Bucket(100, 10, c)
        k.take(100)
        self.assertFalse(k.can(1))
        c.t += 5
        self.assertTrue(k.can(50))


class LinkTable(unittest.TestCase):                              # TB-13
    def test_calls(self):
        for ok in ("OE3GAS", "OE3GAS-15", "DL1ABC", "4X1AB", "K1A"):
            self.assertTrue(plausible_call(ok), ok)
        for bad in ("ABCDEF", "QST", "123456", "OE3GAS-16", "X1", "TOOLONG7"):
            self.assertFalse(plausible_call(bad), bad)

    def test_made_up_call_refused(self):
        p = Port()
        with self.assertLogs("prcore.kissport", "INFO"):
            p.hear(ax.u_frame("SABM", MYCALL, "ABCDEF", pf=True))
        self.assertEqual([f.kind for f in p.sent], ["DM"])
        self.assertEqual(p.links, {})

    def test_bounded_with_eviction_of_silent_links(self):
        p = Port()
        for i in range(MAX_LINKS):
            p.hear(ax.u_frame("SABM", MYCALL, f"OE{i % 10}A{chr(65 + i // 10)}", pf=True))
        self.assertEqual(len(p.links), MAX_LINKS)
        with self.assertLogs("prcore.kissport", "WARNING"):
            p.hear(ax.u_frame("SABM", MYCALL, "OE9ZZZ", pf=True))   # all fresh: refused
        self.assertNotIn("OE9ZZZ", p.links)
        first = next(iter(p.links.values()))
        first.created -= 60                                       # silent for a minute
        with self.assertLogs("prcore.kissport", "WARNING"):
            p.hear(ax.u_frame("SABM", MYCALL, "OE9ZZZ", pf=True))
        self.assertIn("OE9ZZZ", p.links)
        self.assertNotIn(first.remote, p.links)
        self.assertEqual(len(p.links), MAX_LINKS)


class RejFlood(unittest.TestCase):                               # TB-18
    def connected(self):
        a = Ax25Link(A_CALL, B_CALL, cfg=LinkCfg(version="2.0"))
        a.connect(0.0)
        a.receive(ax.Frame("UA", A_CALL, B_CALL, command=False, pf=True), 0.5)
        a.pop_output()
        a.pop_events()
        a.send(b"x" * 600, 1.0)                                   # a few I frames out
        a.tick(1.0)
        return a

    def i_sent(self, a):
        return sum(1 for f in a.pop_output() if f.kind == "I")

    def test_rej_flood_does_not_repeat_the_window(self):
        a = self.connected()
        first = self.i_sent(a)
        self.assertGreater(first, 1)
        t = 2.0
        a.receive(ax.Frame("REJ", A_CALL, B_CALL, command=False, nr=0), t)
        a.tick(t)
        again = self.i_sent(a)
        self.assertEqual(again, first)                            # a real REJ: once
        sent = 0
        for k in range(50):                                       # the flood, 50 ms apart
            t += 0.05
            a.receive(ax.Frame("REJ", A_CALL, B_CALL, command=False, nr=0), t)
            a.tick(t)
            sent += self.i_sent(a)
        # without CR97: 50 windows again; now at most one per half round trip
        self.assertLessEqual(sent, 3 * first)
        self.assertGreaterEqual(a.rej_ignored, 45)

    def test_endless_rej_ends_the_link(self):
        a = self.connected()
        self.i_sent(a)
        t = 2.0
        for k in range(40):                                       # one REJ per second
            t += 1.5
            a.receive(ax.Frame("REJ", A_CALL, B_CALL, command=False, nr=0), t)
            a.tick(t)
            a.pop_output()
        self.assertIn(("disconnected", "retryout"), a.pop_events())


class Sessions(unittest.TestCase):                               # TB-17
    def test_one_call_cannot_take_every_slot(self):
        reg = SessionRegistry(max_users=5)
        mk = lambda call, sysop=False: type("S", (), {"call": call, "sysop": sysop})()
        for ssid in range(MAX_PER_CALL):
            self.assertTrue(reg.add(mk(f"OE1ABC-{ssid}")))
        self.assertFalse(reg.add(mk("OE1ABC-9")))
        self.assertTrue(reg.add(mk("OE3GAS")))
        self.assertTrue(reg.add(mk("OE1ABC-8", sysop=True)))      # the sysop always

    def test_full_mailbox_makes_room_only_when_somebody_wants_in(self):
        import time

        class S:
            def __init__(self, call, chat, idle):
                self.call, self.sysop, self.idle_exempt = call, False, chat
                self.last_input = time.monotonic() - idle
                self.closed, self.said = False, []

            def out(self, text):
                self.said.append(text)

            def close(self):
                self.closed = True

        reg = SessionRegistry(max_users=3, idle_sec=600)
        reader = S("OE1AAA", True, 3 * 3600)                     # parked in a board for 3 h
        newer = S("OE1BBB", True, 20 * 60)                       # parked 20 min
        busy = S("OE1CCC", False, 5 * 3600)                      # not in a board: own timeout
        for x in (reader, newer, busy):
            self.assertTrue(reg.add(x))
        self.assertFalse(reader.closed)                          # nobody waiting: all stay
        with self.assertLogs("tinybox.monitor", "INFO"):
            self.assertTrue(reg.add(S("OE3GAS", False, 0)))      # somebody wants in
        self.assertEqual((reader.closed, newer.closed, busy.closed), (True, False, False))
        self.assertTrue(reader.said)
        newer.last_input = time.monotonic() - 60                 # just typed
        self.assertFalse(reg.add(S("OE3XYZ", False, 0)))         # nobody silent long enough


class HubStats(unittest.TestCase):                               # TB-19
    def test_bounded(self):
        s = linkstats.LinkStats()
        for i in range(linkstats.MAX_LINKS + 300):
            call = f"OE{i % 10}{chr(65 + i // 260 % 26)}{chr(65 + i // 10 % 26)}{chr(65 + i % 26)}"
            raw = ax.u_frame("SABM", "OE3GAS", call, pf=True).encode()
            s.frame(raw, float(i), tx=False, wall=1000.0 + i)
        self.assertLessEqual(len(s.links), linkstats.MAX_LINKS)
        self.assertLessEqual(len(s.heard), linkstats.MAX_HEARD)
        st = s.status(5000.0)
        self.assertLessEqual(len(st["links"]), linkstats.STATUS_LINKS)
        self.assertEqual(st["links_total"], len(s.links))


if __name__ == "__main__":
    unittest.main()
