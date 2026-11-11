"""CR110: the status bar - phase, activity and link per channel, finished jobs
fade out green, modem TX/RX (tbclient/activity.py)."""

from __future__ import annotations

import tempfile
import time
import unittest

from tbclient import activity, budget
from tbclient import peer as peer_mod
from tbclient.core import ClientCore

from tests.test_tbclient import client_cfg


def bar(core, n=1):
    return next(c for c in activity.build(core)["chans"] if c["n"] == n)


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.core = ClientCore(client_cfg(self._tmp.name))
        self.ch = self.core.chan
        self.ch.link.send_line = lambda line: None
        self.ch.link.send_bytes = lambda data: None

    def tearDown(self):
        self._tmp.cleanup()

    def box_online(self):
        self.ch.state, self.ch.mode = "online", "tinybox"
        self.core.handshake_done = True


class BoxPhase(Base):
    def test_from_connect_to_board(self):
        c, ch = self.core, self.ch
        ch.state = "connecting"
        self.assertEqual(bar(c)["phase"]["t"], "Connecting …")
        self.box_online()
        self.assertEqual(bar(c)["phase"]["t"], "Signing in …")       # //CLIENT sent
        c.auth["state"] = "asking"                                   # //AUTH? .. //AUTH
        self.assertEqual(bar(c)["phase"]["t"], "Signing in …")
        c.auth["state"] = "wait"                                     # //AUTHWAIT
        self.assertEqual(bar(c)["phase"]["t"], "Wait 4 sysop")
        c.auth["state"] = "ok"                                       # //OK
        self.assertEqual(bar(c)["phase"]["t"], "Client mode")
        c.board = {"n": 1, "name": "TREFF"}
        self.assertEqual(bar(c)["phase"]["t"], "In board TREFF")
        ch.state = "disconnecting"
        self.assertEqual(bar(c)["phase"]["t"], "Disconnecting …")

    def test_refused_is_red(self):
        self.box_online()
        self.core.auth.update(state="refused", reason="revoked")
        p = bar(self.core)["phase"]
        self.assertEqual((p["t"], p["c"]), ("Login refused: revoked", "red"))

    def test_failed_connect(self):
        self.ch.state, self.ch.ended = "offline", {"kind": "failed"}
        self.assertEqual(bar(self.core)["phase"]["t"], "Not reached")


class BoxActivity(Base):
    def setUp(self):
        super().setUp()
        self.box_online()
        self.core.auth["state"] = "ok"

    def ids(self):
        return [x["id"] for x in bar(self.core)["act"]]

    def test_sync_runs_then_fades_green(self):
        s = self.core.sync.status
        s.update(running=True, scope="mail", step="texts 3-5 of 12", done=5, total=12)
        a = bar(self.core)["act"][0]
        self.assertEqual((a["id"], a["p"], a["busy"]), ("sync", 42, True))
        s.update(running=False, step="done", ended=time.time())
        done = bar(self.core)["act"]
        self.assertEqual([(x["t"], x["c"]) for x in done], [("Mail sync ✓", "done")])
        self.assertLess(done[0]["age"], 1)
        tr = activity.tracker_of(self.core)
        key = (1, "sync")
        chip_, _t = tr.done[key]
        tr.done[key] = (chip_, time.time() - activity.FADE_SEC - 1)   # 6 s later
        self.assertEqual(bar(self.core)["act"], [])

    def test_failed_sync_is_red_not_green(self):
        s = self.core.sync.status
        s.update(running=True, scope="bulletins", step="rubrics")
        bar(self.core)
        s.update(running=False, step="failed", error="no answer", ended=time.time())
        a = bar(self.core)["act"]
        self.assertEqual([(x["t"], x["c"]) for x in a], [("Bulletin sync failed: no answer", "red")])

    def test_no_green_when_the_link_is_gone(self):
        self.core.sync.status.update(running=True, scope="mail", step="x")
        bar(self.core)
        self.core.sync.status["running"] = False
        self.ch.state = "offline"
        self.assertEqual(bar(self.core)["act"], [])

    def test_transfers_and_held_lines(self):
        c = self.core
        c.images.upload = {"hash": "a" * 16, "size": 4000, "sent": 1000, "state": "sending"}
        c.bfiles.loading["b" * 16] = {"done": 10, "total": 100, "error": ""}
        c._hold = ["x", "y"]
        c.asking["cert"] = time.time()
        c.asking["adm"] = time.time()
        c.profiles.busy_at = time.time()
        c.board = {"n": 1, "name": "T", "loading": True}
        self.assertEqual(self.ids(), ["hist", "Picture-up", f"File-dn-{'b' * 16}", "held", "prof",
                                      "cert", "adm"])
        self.assertEqual(bar(c)["act"][1]["p"], 25)

    def test_answers_clear_the_waiting_chips(self):
        c = self.core
        c.asking["trust"] = c.asking["cert"] = time.time()
        c._control("//TRUST box=-")
        c._control("//CERT -")
        self.assertNotIn("trust", c.asking)
        self.assertNotIn("cert", c.asking)

    def test_link_chips(self):
        c = self.core
        self.ch.outstanding = 3
        c.board = {"n": 1, "name": "T"}
        c.caps = {"UI"}
        c.quality[c.cfg.mycall] = 4
        self.ch.link.kind = "agw"
        self.assertEqual([x["t"] for x in bar(c)["link"]],
                         ["Queue 3", "Chat via UI", "Link ▮▮▮▮▯"])


class PeerBar(Base):
    def setUp(self):
        super().setUp()
        self.ch.state, self.ch.mode, self.ch.target = "online", "terminal", "OE3TEC"
        self.core.detach() if self.core.chan is self.ch else None

    def peer(self):
        p = peer_mod.Peer(self.ch, "v=2026.11.11 caps=PROF,HEARD,HIST,IMG,FILE,FUN,AUTH n=abcdefgh12")
        self.ch.peer = p
        return p

    def test_probing_then_key_check(self):
        self.ch.mode, self.ch.probed = "", True
        self.ch._probe_until = time.monotonic() + 60
        self.assertEqual(bar(self.core)["phase"]["t"], "Probing …")
        p = self.peer()
        self.assertEqual(bar(self.core)["phase"]["t"], "Checking key …")
        p.auth.state, p.auth.issuer = "verified", "OE3GAS-1"
        self.assertEqual(bar(self.core)["phase"]["t"], "✓ Verified by OE3GAS-1")
        p.auth.state = "changed"
        self.assertEqual(bar(self.core)["phase"]["c"], "red")

    def test_peer_activity(self):
        p = self.peer()
        p.auth.state = "known"
        p.hist_wait = True
        p.pending = [4, 5]
        p.serve("picture", 2100)
        p.heard_wait = time.time()
        ids = [x["id"] for x in bar(self.core)["act"]]
        self.assertEqual(ids, ["phist", "deliver", "serve", "heard"])
        p._on_hist("g=x m=0:0 y=0:0")          # their //HIST came: compare over
        self.assertFalse(p.hist_wait)
        p.serving["at"] -= 10
        p.outstanding(0)                        # all of it acknowledged
        self.assertIsNone(p.serving)
        self.assertEqual(p.pending, [])
        done = [x["t"] for x in bar(self.core)["act"] if x["c"] == "done"]
        self.assertEqual(sorted(done), ["Delivered ✓", "History ✓", "Picture sent ✓"])

    def test_budget_slowed(self):
        self.peer().auth.state = "known"
        budget.of(self.core).often("OE3TEC-5", "HEARD?", 0, 60)      # held back
        self.assertIn("Budget: answers slowed", [x["t"] for x in bar(self.core)["link"]])


class Modem(Base):
    def test_tx_rx_ages(self):
        m = activity.build(self.core)["modem"]
        self.assertIsNone(m["rx"])
        self.core.rx_at = time.time() - 1
        self.ch.state, self.ch.outstanding = "online", 2
        m = activity.build(self.core)["modem"]
        self.assertLess(m["rx"], 2)
        self.assertLess(m["tx"], 0.5)          # frames waiting = sending

    def test_in_the_snapshot(self):
        self.assertIn("activity", self.core.snapshot())


if __name__ == "__main__":
    unittest.main()
