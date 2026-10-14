"""AX.25 link state machine, v2.0 part (KISS step K2, docs/kiss-mode-konzept.md).

These tests pin the v2.0 behaviour (LinkCfg(version="2.0")); the transfer tests
run with both versions. v2.2 specifics: tests/test_ax25_v22.py.
"""

from __future__ import annotations

import dataclasses
import random
import unittest

from tinybox import linkq
from tinybox.ax25 import frame as ax
from tinybox.ax25.link import Ax25Link, LinkCfg, State

from tests.ax25sim import Sim, pair

A_CALL, B_CALL = "OE3ABC", "OE3GAS-1"
V20 = LinkCfg(version="2.0")
V22 = LinkCfg(version="2.2")


def payload(n: int, seed: int = 0) -> bytes:
    rnd = random.Random(seed)
    return bytes(rnd.randrange(256) for _ in range(n))


def connect(sim: Sim) -> None:
    a = sim.links["A"]
    a.connect(sim.now)
    assert sim.run(stop=lambda: a.connected and sim.links["B"].connected), "no connect"


class TransferTests(unittest.TestCase):
    def transfer(self, loss: float, seed: int, n_ab: int = 4000, n_ba: int = 1500,
                 cfg: LinkCfg = V20) -> Sim:
        a, b = pair(cfg)
        sim = Sim(a, b, loss=loss, seed=seed)
        connect(sim)
        data_ab, data_ba = payload(n_ab, seed), payload(n_ba, seed + 100)
        a.send(data_ab, sim.now)
        b.send(data_ba, sim.now)
        done = sim.run(until=sim.now + 4 * 3600, stop=lambda: (
            len(sim.rx["B"]) >= n_ab and len(sim.rx["A"]) >= n_ba and a.is_idle and b.is_idle))
        self.assertTrue(done, f"transfer stuck (loss {loss}, seed {seed}): "
                              f"{len(sim.rx['B'])}/{n_ab}, {len(sim.rx['A'])}/{n_ba}, "
                              f"A {a.state.name}, B {b.state.name}")
        self.assertEqual(bytes(sim.rx["B"]), data_ab)
        self.assertEqual(bytes(sim.rx["A"]), data_ba)
        a.disconnect(sim.now)
        sim.run(stop=lambda: a.state == b.state == State.DISCONNECTED)
        self.assertIn(("disconnected", "local"), sim.events["A"])
        self.assertIn(("disconnected", "remote"), sim.events["B"])
        return sim

    def test_clean_channel(self):
        sim = self.transfer(0.0, 1, cfg=V20)
        a, b = sim.links["A"], sim.links["B"]
        for link in (a, b):
            self.assertEqual((link.c["i_retry"], link.c["rej_rx"], link.c["rej_tx"]),
                             (0, 0, 0), link.mycall)
        self.assertEqual(a.c["i_new"], 4000 // 128 + 1)
        self.assertEqual(sim.event_names("A")[0], ("connected", "outgoing"))
        self.assertEqual(sim.event_names("B")[0], ("connected", "incoming"))
        self.assertEqual(sim.kinds("A")[0], "SABM")
        self.assertEqual(sim.kinds("B")[0], "UA")

    def test_ten_percent_loss(self):
        for cfg in (V20, V22):
            for seed in range(1, 6):
                with self.subTest(version=cfg.version, seed=seed):
                    sim = self.transfer(0.10, seed, cfg=cfg)
                    self.assertGreater(sim.links["A"].c["i_retry"], 0)

    def test_thirty_percent_loss(self):
        for cfg in (V20, V22):
            for seed in range(1, 6):
                with self.subTest(version=cfg.version, seed=seed):
                    self.transfer(0.30, seed, n_ab=2000, n_ba=600, cfg=cfg)

    def test_window_sizes_and_immediate_acks(self):
        for k in (1, 7):
            for t2 in (0.0, 1.5):
                with self.subTest(k=k, t2=t2):
                    self.transfer(0.15, 7, n_ab=1500, n_ba=500,
                                  cfg=LinkCfg(version="2.0", maxframe=k, t2_sec=t2))

    def test_t2_groups_acknowledgements(self):
        """B answers a window of 4 I frames with ONE RR, not four."""
        a, b = pair(V20)
        sim = Sim(a, b)
        connect(sim)
        a.send(payload(4 * 128), sim.now)
        sim.run(stop=lambda: a.is_idle)
        self.assertEqual(sim.kinds("B").count("RR"), 1)


class LossRecoveryTests(unittest.TestCase):
    def test_lost_i_frame_gives_one_rej(self):
        lost = []

        def drop(f, sender):
            if sender == "A" and f.is_i and f.ns == 1 and not lost:
                lost.append(f)
                return True
            return False

        a, b = pair(V20)
        sim = Sim(a, b, drop=drop)
        connect(sim)
        data = payload(4 * 128)
        a.send(data, sim.now)
        sim.run(stop=lambda: a.is_idle and len(sim.rx["B"]) == len(data))
        self.assertEqual(bytes(sim.rx["B"]), data)
        self.assertEqual((b.c["rej_tx"], a.c["rej_rx"]), (1, 1))
        self.assertEqual(a.c["i_retry"], 3)            # Go-Back-N: ns 1, 2, 3 again
        self.assertEqual(a.c["t1_exp"], 0)              # REJ, not the timer, fixed it

    def test_lost_last_frame_recovered_by_t1_poll(self):
        a, b = pair(V20)
        dropped = []
        sim = Sim(a, b, drop=lambda f, s: s == "A" and f.is_i and not dropped
                  and not dropped.append(1))
        connect(sim)
        a.send(b"only one frame", sim.now)
        sim.run(stop=lambda: a.is_idle)
        self.assertEqual(bytes(sim.rx["B"]), b"only one frame")
        self.assertEqual(a.c["t1_exp"], 1)
        self.assertIn("RR", sim.kinds("A"))             # the poll (RR command, P=1)

    def test_retryout_when_channel_dies(self):
        a, b = pair(LinkCfg(version="2.0", n2=3))
        dead = []
        sim = Sim(a, b, drop=lambda f, s: bool(dead))
        connect(sim)
        dead.append(1)
        a.send(b"into the void", sim.now)
        sim.run(stop=lambda: a.state == State.DISCONNECTED)
        self.assertEqual(sim.event_names("A")[-1], ("disconnected", "retryout"))
        self.assertEqual(a.c["t1_exp"], 4)              # first expiry + N2 polls
        self.assertLess(sim.now, 300)

    def test_nobody_answers(self):
        a = Ax25Link(A_CALL, B_CALL, cfg=LinkCfg(version="2.0", n2=2))
        sim = Sim(a, Ax25Link(B_CALL, A_CALL, cfg=V20), drop=lambda f, s: True)
        a.connect(0.0)
        sim.run(stop=lambda: a.state == State.DISCONNECTED)
        self.assertEqual(sim.kinds("A"), ["SABM"] * 3)
        self.assertEqual(sim.event_names("A"), [("disconnected", "timeout")])

    def test_t1_backs_off_and_srt_learns(self):
        a, b = pair(V20)
        sim = Sim(a, b)
        connect(sim)
        a.send(payload(2000), sim.now)
        sim.run(stop=lambda: a.is_idle)
        # 4 frames of 128 bytes at 1200 Bd + the RR: a few seconds round trip
        self.assertGreater(a.srt, 1.0)
        self.assertLess(a.srt, 8.0)
        a.rc = 3
        a._select_t1(sim.now, measured=False)
        self.assertEqual(a.t1v, min(30.0, max(3.0, a.srt * 16)))


class BusyTests(unittest.TestCase):
    def test_rnr_stops_and_rr_resumes(self):
        a, b = pair(V20)
        sim = Sim(a, b)
        connect(sim)
        b.set_busy(True, sim.now)
        a.send(payload(10 * 128), sim.now)
        sim.run(until=sim.now + 60)
        got = len(sim.rx["B"])
        self.assertEqual(got, 0)                        # everything sent was dropped
        self.assertTrue(a.peer_busy)
        self.assertGreater(a.c["rnr_rx"], 0)
        b.set_busy(False, sim.now)
        sim.run(stop=lambda: a.is_idle)
        self.assertEqual(bytes(sim.rx["B"]), payload(10 * 128))


class EdgeTests(unittest.TestCase):
    def frame(self, kind, **kw):
        kw.setdefault("command", True)
        return ax.Frame(kind, B_CALL, A_CALL, **kw)

    def connected_b(self) -> Ax25Link:
        b = Ax25Link(B_CALL, A_CALL, cfg=V20)
        b.receive(self.frame("SABM", pf=True), 0.0)
        b.pop_output()
        b.pop_events()
        return b

    def test_disconnected_answers_dm(self):
        b = Ax25Link(B_CALL, A_CALL, cfg=V20)
        b.receive(self.frame("DISC", pf=True), 0.0)
        b.receive(self.frame("I", pf=True, info=b"x"), 0.0)
        b.receive(self.frame("RR", pf=False), 0.0)      # no poll: no answer
        out = b.pop_output()
        self.assertEqual([(f.kind, f.pf, f.command) for f in out],
                         [("DM", True, False), ("DM", True, False)])

    def test_sabme_refused_with_version_20(self):
        b = Ax25Link(B_CALL, A_CALL, cfg=V20)
        b.receive(self.frame("SABME", pf=True), 0.0)
        self.assertEqual([f.kind for f in b.pop_output()], ["DM"])
        self.assertEqual(b.state, State.DISCONNECTED)

    def test_dm_refuses_our_connect(self):
        a = Ax25Link(A_CALL, B_CALL, cfg=V20)
        a.connect(0.0)
        a.receive(ax.Frame("DM", A_CALL, B_CALL, command=False, pf=True), 1.0)
        self.assertEqual(a.pop_events(), [("disconnected", "refused")])

    def test_remote_disc(self):
        b = self.connected_b()
        b.receive(self.frame("DISC", pf=True), 1.0)
        self.assertEqual([f.kind for f in b.pop_output()], ["UA"])
        self.assertEqual(b.pop_events(), [("disconnected", "remote")])

    def test_nr_error_reestablishes(self):
        b = self.connected_b()
        b.receive(self.frame("RR", nr=5, command=False), 1.0)    # acks what we never sent
        self.assertEqual([f.kind for f in b.pop_output()], ["SABM"])
        self.assertEqual(b.state, State.AWAITING_CONNECTION)
        b.receive(self.frame("UA", command=False, pf=True), 2.0)
        self.assertEqual(b.pop_events(), [("reset", "reestablished")])
        self.assertEqual(b.state, State.CONNECTED)

    def test_duplicate_i_frame_counted_not_delivered(self):
        b = self.connected_b()
        b.receive(self.frame("I", ns=0, info=b"one"), 1.0)
        b.receive(self.frame("I", ns=0, info=b"one"), 2.0)       # A did not get our RR
        self.assertEqual([e for e in b.pop_events()], [("data", b"one")])
        self.assertEqual((b.c["retry_rx"], b.c["rej_tx"], b.c["i_rx"]), (1, 0, 2))

    def test_poll_gets_final(self):
        b = self.connected_b()
        b.receive(self.frame("RR", pf=True), 1.0)
        out = b.pop_output()
        self.assertEqual([(f.kind, f.command, f.pf) for f in out], [("RR", False, True)])

    def test_test_frame_echoed(self):
        b = self.connected_b()
        b.receive(self.frame("TEST", pf=True, info=b"ping"), 1.0)
        f = b.pop_output()[0]
        self.assertEqual((f.kind, f.command, f.info), ("TEST", False, b"ping"))

    def test_t3_idle_poll_keeps_link(self):
        a, b = pair(LinkCfg(version="2.0", t3_sec=60))
        sim = Sim(a, b)
        connect(sim)
        sim.run(until=sim.now + 200)
        self.assertTrue(a.connected and b.connected)
        self.assertGreaterEqual([k for k in sim.kinds("A") if k == "RR"].__len__(), 2)

    def test_digipeater_path_is_used(self):
        a = Ax25Link(A_CALL, B_CALL, path=["OE3XWR"], cfg=V20)
        a.connect(0.0)
        f = a.pop_output()[0]
        self.assertEqual(f.path, ["OE3XWR"])
        self.assertGreaterEqual(a.t1v, 2 * 2 * 2.5)      # two hops: longer start T1

    def test_counters_match_link_quality_format(self):
        b = self.connected_b()
        c = b.counters(10.0)
        missing = set(linkq.FIELDS_INT) | set(linkq.FIELDS_FLOAT)
        self.assertFalse(missing - set(c), missing - set(c))
        line = " ".join(f"{k}={v}" for k, v in c.items())
        self.assertEqual(linkq.parse(line)["state"], int(State.CONNECTED))


class FuzzTests(unittest.TestCase):
    def test_random_frames_never_crash(self):
        """Any sequence of well-formed frames from the air: no exception, sane state."""
        rnd = random.Random(1)
        kinds = list(ax.KINDS)
        for i in range(300):
            link = Ax25Link(B_CALL, A_CALL, cfg=V20 if i % 2 else V22)
            now = 0.0
            for _ in range(60):
                now += rnd.random() * 5
                kind = rnd.choice(kinds)
                m = link.modulo
                info = b"x" * rnd.randrange(3) if kind in ax.WITH_INFO else b""
                if kind == "XID" and rnd.random() < 0.5:
                    info = bytes((0x82, 0x80, 0, rnd.randrange(12))) + bytes(
                        rnd.randrange(256) for _ in range(rnd.randrange(14)))
                f = ax.Frame(kind, B_CALL, A_CALL, command=rnd.random() < 0.6,
                             pf=rnd.random() < 0.3, ns=rnd.randrange(m), nr=rnd.randrange(m),
                             info=info, modulo=m)
                link.receive(f, now)
                if rnd.random() < 0.3:
                    link.send(b"y" * rnd.randrange(300), now)
                deadline = link.next_deadline()
                if deadline is not None and rnd.random() < 0.5:
                    now = max(now, deadline)
                    link.tick(now)
                for out in link.pop_output():
                    out.encode()                          # everything we send is valid
                link.pop_events()
                self.assertLessEqual(link.unacked, link.k)
                m = link.modulo
                self.assertTrue(0 <= link.va < m and 0 <= link.vs < m and 0 <= link.vr < m)


if __name__ == "__main__":
    unittest.main()
