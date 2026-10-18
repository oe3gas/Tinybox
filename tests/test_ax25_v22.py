"""AX.25 v2.2: SABME / modulo 128, XID, SREJ, fall back to v2.0 (KISS step K3)."""

from __future__ import annotations

import dataclasses
import unittest

from prcore.ax25 import frame as ax
from prcore.ax25 import xid
from prcore.ax25.link import Ax25Link, LinkCfg, State

from tests.ax25sim import Sim
from tests.test_ax25_link import A_CALL, B_CALL, V20, V22, payload


def make(cfg_a: LinkCfg = V22, cfg_b: LinkCfg = V22, **kw) -> tuple[Ax25Link, Ax25Link, Sim]:
    a = Ax25Link(A_CALL, B_CALL, cfg=cfg_a, peer_v20=kw.pop("peer_v20", False))
    b = Ax25Link(B_CALL, A_CALL, cfg=cfg_b)
    return a, b, Sim(a, b, **kw)


def connect(a: Ax25Link, b: Ax25Link, sim: Sim) -> None:
    a.connect(sim.now)
    # connected, and the XID exchange (if any) is over
    assert sim.run(stop=lambda: a.connected and b.connected and not a._xid_waiting
                   and not sim._air), "no connect"


def send_all(a: Ax25Link, b: Ax25Link, sim: Sim, data: bytes) -> None:
    a.send(data, sim.now)
    ok = sim.run(until=sim.now + 6 * 3600,
                 stop=lambda: a.is_idle and len(sim.rx["B"]) >= len(data))
    assert ok, f"stuck: {len(sim.rx['B'])}/{len(data)}"


class XidCodecTests(unittest.TestCase):
    def test_round_trip(self):
        p = xid.XidParams(srej=True, rej=True, modulo=128, full_duplex=False,
                          n1_rx=256, k_rx=32, t1_ms=3000, n2=10)
        self.assertEqual(xid.decode(xid.encode(p)), p)

    def test_layout(self):
        raw = xid.encode(xid.XidParams(srej=True, modulo=128, k_rx=7))
        self.assertEqual(raw[:2], b"\x82\x80")
        self.assertEqual(int.from_bytes(raw[2:4], "big"), len(raw) - 4)
        self.assertIn(bytes((xid.PI_K_RX, 1, 7)), raw)
        self.assertIn(bytes((xid.PI_CLASSES, 2)) + (0x2100).to_bytes(2, "big"), raw)

    def test_n1_in_bits(self):
        raw = xid.encode(xid.XidParams(n1_rx=128))
        self.assertIn(bytes((xid.PI_N1_RX, 2)) + (1024).to_bytes(2, "big"), raw)

    def test_unknown_parameter_skipped(self):
        p = xid.encode(xid.XidParams(k_rx=4))
        body = p[4:] + bytes((99, 2, 1, 2))                  # PI 99, unknown
        raw = p[:2] + len(body).to_bytes(2, "big") + body
        self.assertEqual(xid.decode(raw).k_rx, 4)

    def test_garbage(self):
        for raw in (b"", b"\x82\x80", b"\x81\x80\x00\x00", b"\x82\x80\x00\x05\x02",
                    b"\x82\x80\x00\x03\x08\x05\x01"):
            with self.assertRaises(xid.XidError, msg=raw):
                xid.decode(raw)

    def test_combine(self):
        mine = xid.XidParams(srej=True, modulo=128, n1_rx=256, k_rx=7, t1_ms=3000, n2=10)
        theirs = xid.XidParams(srej=False, modulo=128, n1_rx=128, k_rx=32, t1_ms=5000, n2=8)
        c = xid.combine(mine, theirs)
        self.assertEqual((c.srej, c.modulo, c.n1_rx, c.k_rx, c.t1_ms, c.n2),
                         (False, 128, 128, 7, 5000, 8))
        self.assertEqual(xid.combine(mine, xid.XidParams()).k_rx, 7)


class HandshakeTests(unittest.TestCase):
    def test_v22_to_v22(self):
        a, b, sim = make()
        connect(a, b, sim)
        self.assertEqual(sim.kinds("A")[:2], ["SABME", "XID"])
        self.assertEqual(sim.kinds("B")[:2], ["UA", "XID"])
        for link in (a, b):
            self.assertEqual((link.modulo, link.k, link.srej_on, link.peer_version),
                             (128, 7, True, "2.2"), link.mycall)
        self.assertEqual(sim.events["A"][0], ("connected", "outgoing"))

    def test_v22_calls_v20_station(self):
        """DM to SABME -> SABM; the caller learns the station speaks v2.0."""
        a, b, sim = make(V22, V20)
        connect(a, b, sim)
        self.assertEqual(sim.kinds("A")[:2], ["SABME", "SABM"])
        self.assertEqual(sim.kinds("B")[:2], ["DM", "UA"])
        self.assertEqual((a.modulo, a.peer_version, a.peer_v20), (8, "2.0", True))
        self.assertEqual(sim.events["A"], [("connected", "outgoing")])
        send_all(a, b, sim, payload(1000))
        self.assertEqual(bytes(sim.rx["B"]), payload(1000))

    def test_silent_v20_station(self):
        """A station that ignores SABME: after sabme_tries SABMEs it gets a SABM."""
        a, b, sim = make(V22, V20, drop=lambda f, s: f.kind == "SABME")
        connect(a, b, sim)
        self.assertEqual(sim.kinds("A")[:3], ["SABME", "SABME", "SABM"])
        self.assertEqual(a.modulo, 8)

    def test_known_v20_station_gets_sabm_first(self):
        a, b, sim = make(V22, V20, peer_v20=True)
        connect(a, b, sim)
        self.assertEqual(sim.kinds("A")[0], "SABM")

    def test_v20_caller_to_v22_mailbox(self):
        a, b, sim = make(V20, V22)
        connect(a, b, sim)
        self.assertEqual((a.modulo, b.modulo, b.peer_version), (8, 8, "2.0"))

    def test_xid_lost_means_rej_only(self):
        a, b, sim = make(drop=lambda f, s: f.kind == "XID" and s == "B")
        a.connect(0)
        sim.run(stop=lambda: a.connected and b.connected)
        sim.run(until=sim.now + 20)
        self.assertFalse(a.srej_on)
        self.assertTrue(b.srej_on)        # B answered, A never heard it: B may ask SREJ...
        send_all(a, b, sim, payload(2000))
        self.assertEqual(bytes(sim.rx["B"]), payload(2000))

    def test_xid_repeated_after_loss(self):
        lost = []
        a, b, sim = make(drop=lambda f, s: f.kind == "XID" and s == "B" and not lost
                         and not lost.append(1))
        connect(a, b, sim)
        self.assertEqual(sim.kinds("A").count("XID"), 2)
        self.assertTrue(a.srej_on and b.srej_on)

    def test_xid_lower_limits_win(self):
        small = dataclasses.replace(V22, srej=False, maxframe_ext=3, max_rx_info=64)
        a, b, sim = make(V22, small)
        connect(a, b, sim)
        self.assertEqual((a.k, a.n1, a.srej_on), (3, 64, False))
        a.send(payload(500), sim.now)
        sim.run(stop=lambda: a.is_idle)
        sizes = {len(f.info) for _, s, f in sim.sent if s == "A" and f.is_i}
        self.assertEqual(max(sizes), 64)
        self.assertEqual(bytes(sim.rx["B"]), payload(500))

    def test_reestablish_keeps_modulo_128(self):
        a, b, sim = make()
        connect(a, b, sim)
        a.receive(ax.s_frame("RR", A_CALL, B_CALL, 99, modulo=128), sim.now)  # bad N(R)
        self.assertEqual(a.pop_output()[0].kind, "SABME")
        self.assertEqual(a.state, State.AWAITING_V22_CONNECTION)


class SrejTests(unittest.TestCase):
    def drop_once(self, *ns: int):
        left = set(ns)

        def drop(f, sender):
            if sender == "A" and f.is_i and f.ns in left:
                left.discard(f.ns)
                return True
            return False
        return drop

    def test_one_lost_frame_one_srej_one_repeat(self):
        a, b, sim = make(drop=self.drop_once(1))
        connect(a, b, sim)
        send_all(a, b, sim, payload(6 * 128))
        self.assertEqual(bytes(sim.rx["B"]), payload(6 * 128))
        self.assertEqual((b.c["srej_tx"], a.c["srej_rx"]), (1, 1))
        self.assertEqual(a.c["i_retry"], 1)                  # only the lost one again
        self.assertEqual(b.c["rej_tx"] - b.c["srej_tx"], 0)  # no REJ
        srej = [f for _, s, f in sim.sent if s == "B" and f.kind == "SREJ"]
        self.assertEqual([f.nr for f in srej], [1])

    def test_two_gaps(self):
        a, b, sim = make(drop=self.drop_once(1, 3))
        connect(a, b, sim)
        send_all(a, b, sim, payload(7 * 128))
        self.assertEqual(bytes(sim.rx["B"]), payload(7 * 128))
        srej = [f.nr for _, s, f in sim.sent if s == "B" and f.kind == "SREJ"]
        self.assertEqual(sorted(srej), [1, 3])
        self.assertEqual(a.c["i_retry"], 2)

    def test_lost_srej_repaired_by_poll(self):
        dropped = {"i": False, "srej": False}

        def drop(f, sender):
            if sender == "A" and f.is_i and f.ns == 2 and not dropped["i"]:
                dropped["i"] = True
                return True
            if sender == "B" and f.kind == "SREJ" and not dropped["srej"]:
                dropped["srej"] = True
                return True
            return False

        a, b, sim = make(drop=drop)
        connect(a, b, sim)
        send_all(a, b, sim, payload(6 * 128))
        self.assertEqual(bytes(sim.rx["B"]), payload(6 * 128))
        self.assertGreaterEqual(a.c["t1_exp"], 1)

    def test_sequence_numbers_wrap_at_128(self):
        for loss in (0.0, 0.1):
            with self.subTest(loss=loss):
                a, b, sim = make(loss=loss, seed=3)
                connect(a, b, sim)
                data = payload(200 * 128)                     # 200 frames > 128
                send_all(a, b, sim, data)
                self.assertEqual(bytes(sim.rx["B"]), data)


class EfficiencyTests(unittest.TestCase):
    """SREJ must repeat clearly less than Go-Back-N on a lossy channel."""

    @staticmethod
    def share_new(cfg: LinkCfg, loss: float, seeds=range(1, 9)) -> float:
        total_new = total = 0
        for seed in seeds:
            a = Ax25Link(A_CALL, B_CALL, cfg=cfg)
            b = Ax25Link(B_CALL, A_CALL, cfg=cfg)
            sim = Sim(a, b, loss=loss, seed=seed)
            connect(a, b, sim)
            send_all(a, b, sim, payload(3000, seed))
            assert bytes(sim.rx["B"]) == payload(3000, seed)
            total_new += a.c["bytes_new"]
            total += a.c["bytes_new"] + a.c["bytes_retry"]
        return total_new / total

    def test_srej_beats_rej(self):
        for loss in (0.1, 0.2):
            with self.subTest(loss=loss):
                v20 = self.share_new(V20, loss)
                v22 = self.share_new(V22, loss)
                self.assertGreater(v22, v20 + 0.05, f"v2.0 {v20:.0%}, v2.2 {v22:.0%}")


if __name__ == "__main__":
    unittest.main()


class SrejAnswerTests(unittest.TestCase):
    """Field test PK-232 / Direwolf, 17.10.2026: Direwolf answers our poll with
    SREJ F=1 when it misses a frame. That is the answer to the poll."""

    def setUp(self):
        self.box = Ax25Link(A_CALL, B_CALL, cfg=V22, now=0)
        self.t = 0.0
        self.rx(ax.u_frame("SABME", A_CALL, B_CALL, command=True, pf=True))
        self.box.send(payload(self.box.n1 + 30), self.t)      # two I frames: 0 and 1
        self.assertEqual(self.box.vs, 2)
        self.out()

    def rx(self, f):
        self.box.receive(ax.Frame.decode(f.encode(), self.box.modulo), self.t)

    def out(self):
        return self.box.pop_output()

    def poll(self):
        """Run the clock until the box polls (T1 expired)."""
        while self.box.state != State.TIMER_RECOVERY:
            self.t = self.box.next_deadline()
            self.box.tick(self.t)
        return self.out()

    def test_srej_f1_ends_timer_recovery_and_repeats_the_frame(self):
        polls = self.poll()
        self.assertTrue(any(f.kind == "RR" and f.command and f.pf for f in polls))
        self.rx(ax.s_frame("SREJ", A_CALL, B_CALL, 0, command=False, pf=True, modulo=128))
        sent = self.out()
        self.assertEqual(self.box.state, State.CONNECTED)
        self.assertEqual(self.box.rc, 0)
        self.assertEqual([f.ns for f in sent if f.is_i], [0])
        self.assertIsNotNone(self.box.t1_at)                  # frames 0, 1 still open

    def test_srej_f1_acknowledges_below_nr(self):
        self.poll()
        self.rx(ax.s_frame("SREJ", A_CALL, B_CALL, 1, command=False, pf=True, modulo=128))
        self.assertEqual(self.box.va, 1)                      # frame 0 acknowledged
        self.assertEqual([f.ns for f in self.out() if f.is_i], [1])

    def test_srej_without_f_acknowledges_nothing(self):
        self.rx(ax.s_frame("SREJ", A_CALL, B_CALL, 1, command=False, pf=False, modulo=128))
        self.assertEqual(self.box.va, 0)

    def test_retry_backoff_is_capped(self):
        """T1 on retries grows to 8 x SRT at most (unless t1_max is lower)."""
        self.poll()
        intervals, last = [], self.t
        for _ in range(6):
            self.t = self.box.next_deadline()
            intervals.append(self.t - last)
            last = self.t
            self.box.tick(self.t)
            self.out()
        cap = min(self.box.cfg.t1_max_sec, 8 * self.box.srt)
        self.assertTrue(all(i <= cap + 1.0 for i in intervals), intervals)


class V20DigiTests(unittest.TestCase):
    """Known v2.0 digis (TM-D710E): modulo 128 I frames are dropped there,
    so links over them use v2.0 (bug 18.10.2026, OE3GAS-2 via OE3XTC-5)."""

    DIGI = "OE3XTC-5"
    CFG = dataclasses.replace(V22, v20_digis=frozenset({"OE3XTC-5"}))

    def make(self, cfg_a, cfg_b, path):
        a = Ax25Link(A_CALL, B_CALL, path=path, cfg=cfg_a)
        b = Ax25Link(B_CALL, A_CALL, path=list(reversed(path)), cfg=cfg_b)
        return a, b, Sim(a, b)

    def test_incoming_sabme_over_v20_digi_gets_dm(self):
        """Direwolf calls with SABME, the mailbox says DM -> SABM, modulo 8."""
        a, b, sim = self.make(V22, self.CFG, [self.DIGI])
        connect(a, b, sim)
        self.assertEqual(sim.kinds("A")[:2], ["SABME", "SABM"])
        self.assertEqual(sim.kinds("B")[:2], ["DM", "UA"])
        self.assertEqual((a.modulo, b.modulo), (8, 8))
        send_all(a, b, sim, payload(500))
        self.assertEqual(bytes(sim.rx["B"]), payload(500))

    def test_outgoing_over_v20_digi_calls_with_sabm(self):
        a, b, sim = self.make(self.CFG, V22, [self.DIGI])
        connect(a, b, sim)
        self.assertEqual(sim.kinds("A")[0], "SABM")
        self.assertEqual(a.modulo, 8)

    def test_other_digi_keeps_v22(self):
        a, b, sim = self.make(V22, self.CFG, ["OE3XYZ-2"])
        connect(a, b, sim)
        self.assertEqual((a.modulo, b.modulo), (128, 128))

    def test_direct_keeps_v22(self):
        a, b, sim = self.make(V22, self.CFG, [])
        connect(a, b, sim)
        self.assertEqual(b.modulo, 128)

    def test_v20_digi_anywhere_in_the_path(self):
        a, b, sim = self.make(V22, self.CFG, ["OE3XYZ-2", self.DIGI])
        connect(a, b, sim)
        self.assertEqual(b.modulo, 8)

    def test_parse_calls(self):
        from prcore.ax25.link import parse_calls
        self.assertEqual(parse_calls("oe3xtc-5, OE1ABC-0  oe3xyz"),
                         frozenset({"OE3XTC-5", "OE1ABC", "OE3XYZ"}))
        self.assertEqual(parse_calls(""), frozenset())

    def test_short_frames_over_v20_digi(self):
        """The TM-D710E also drops 256-byte I frames: 128 at most over it."""
        cfg = dataclasses.replace(self.CFG, paclen=256)
        a, b, sim = self.make(V22, cfg, [self.DIGI])
        connect(a, b, sim)
        b.send(payload(1000), sim.now)
        sim.run(until=sim.now + 3600, stop=lambda: b.is_idle and len(sim.rx["A"]) >= 1000)
        self.assertEqual(bytes(sim.rx["A"]), payload(1000))
        sizes = [len(f.info) for _, s, f in sim.sent if s == "B" and f.is_i]
        self.assertTrue(sizes and max(sizes) == 128, sizes)

    def test_full_frames_elsewhere(self):
        cfg = dataclasses.replace(self.CFG, paclen=256)
        a, b, sim = self.make(V22, cfg, ["OE3XYZ-2"])
        connect(a, b, sim)
        self.assertEqual(b.n1, 256)
