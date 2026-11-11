"""CR121: one call, one connection. AX.25 cannot tell two stations with the same
call apart (QTerm and the TBClient both as OE3NIX over one Direwolf, 11.11.2026):
the box reset the link on every SABME, the other one acked with old numbers,
the box re-established - a ping-pong on the air for minutes.

The TinyBox (refuse_reconnect): a SABM(E) on a running link gets DM and the
link ends; an N(R) error ends it with DISC. The client keeps the standard."""

from __future__ import annotations

import dataclasses
import unittest

from prcore.ax25 import frame as ax
from prcore.ax25.link import LinkCfg, State

from tests.ax25sim import Sim, pair

A_CALL, B_CALL = "OE3NIX", "OE3GAS-1"
BOX = LinkCfg(version="2.2", refuse_reconnect=True)
STD = LinkCfg(version="2.2")


def connected():
    a, b = pair(STD, BOX)
    sim = Sim(a, b)
    a.connect(sim.now)
    assert sim.run(stop=lambda: a.connected and b.connected)
    b.pop_events()
    return a, b, sim


class RefuseReconnectTests(unittest.TestCase):
    def test_sabme_while_connected_gets_dm(self):
        a, b, sim = connected()
        b.receive(ax.u_frame("SABME", B_CALL, "OE3ABC", command=True, pf=True), sim.now)
        out = b.pop_output()
        self.assertEqual([(f.kind, f.pf) for f in out], [("DM", True)])
        self.assertEqual(b.state, State.DISCONNECTED)
        self.assertIn(("disconnected", "reconnect"), b.pop_events())
        # the next SABME is a fresh connect
        b.receive(ax.u_frame("SABME", B_CALL, "OE3ABC", command=True, pf=True), sim.now)
        self.assertEqual(b.pop_output()[0].kind, "UA")
        self.assertIn(("connected", "incoming"), b.pop_events())

    def test_sabm_while_connected_gets_dm(self):
        a, b, sim = connected()
        b.receive(ax.u_frame("SABM", B_CALL, "OE3ABC", command=True, pf=True), sim.now)
        self.assertEqual(b.pop_output()[0].kind, "DM")
        self.assertEqual(b.state, State.DISCONNECTED)

    def test_nr_error_ends_with_disc(self):
        a, b, sim = connected()
        b.receive(ax.s_frame("RR", B_CALL, "OE3ABC", 99, modulo=128), sim.now)   # never sent
        self.assertEqual(b.pop_output()[0].kind, "DISC")
        self.assertEqual(b.state, State.AWAITING_RELEASE)
        self.assertIn(("nr_error", "OE3ABC"), b.pop_events())

    def test_standard_link_still_resets(self):
        a, b = pair(STD, STD)
        sim = Sim(a, b)
        a.connect(sim.now)
        sim.run(stop=lambda: a.connected and b.connected)
        b.pop_events()
        b.receive(ax.u_frame("SABME", B_CALL, "OE3ABC", command=True, pf=True), sim.now)
        self.assertEqual(b.pop_output()[0].kind, "UA")
        self.assertEqual(b.state, State.CONNECTED)
        self.assertIn(("reset", "remote"), b.pop_events())

    def test_box_adapters_refuse(self):
        from tests.test_tinybox import make_app
        from tinybox.adapters import axudp, kiss
        cfg = make_app().cfg
        self.assertTrue(kiss.link_cfg(cfg).refuse_reconnect)
        self.assertTrue(axudp.axudp_link_cfg(cfg).refuse_reconnect)
        self.assertFalse(dataclasses.replace(STD).refuse_reconnect)


if __name__ == "__main__":
    unittest.main()
