"""CR112: the Direwolf fork's extensions in the client - 'F' (what it can), 'E'
(PTT, DCD, link state and retries, level per frame), 'O' (own frames), 'Q' v=3,
the reason in 'd'; and the same phase/retries from our own AX.25 (KISS)."""

from __future__ import annotations

import dataclasses
import tempfile
import time
import unittest

from prcore import linkq
from tbclient import activity
from tbclient.core import ClientCore
from tbclient.links import AgwLink, AgwPort, disc_reason, l2_from

from tests.test_tbclient import client_cfg

Q3 = ("v=3 state=3 i_new=1 i_retry=0 bytes_new=181 bytes_retry=0 i_rx=0 retry_rx=0 rej_rx=0 "
      "rej_tx=0 t1_exp=0 rnr_rx=0 srt=1.40 t1v=2.80 rc=0 unack=0 age=14 bytes_rx=0 "
      "tx_busy_ms=2881 baud=1200 n2=10 mod=128 k=32 n1=256 srej=2 load=8 load_tx=5")


def bar(core, n=1):
    return next(c for c in activity.build(core)["chans"] if c["n"] == n)


class Parsing(unittest.TestCase):
    def test_q_v3(self):
        q = linkq.parse(Q3)
        self.assertEqual((q["v"], q["n2"], q["mod"], q["k"], q["load"]), (3, 10, 128, 32, 8))
        self.assertIsNone(linkq.parse("v=3 none"))

    def test_l2_and_reason(self):
        self.assertEqual(l2_from({"state": "5", "rc": "3", "n2": "10", "mod": "128", "k": "32"}),
                         {"phase": "sabme", "rc": 3, "n2": 10, "mod": 128, "k": 32})
        self.assertIsNone(l2_from({}))
        self.assertEqual(disc_reason(b"*** DISCONNECTED RETRYOUT With OE3BBB\r"),
                         "retry-out (no answer)")
        self.assertEqual(disc_reason(b"*** DISCONNECTED From Station OE3BBB\r"), "disconnected")


class Fork(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        cfg = dataclasses.replace(client_cfg(self._tmp.name), link="agw")
        self.core = ClientCore(cfg)
        self.port = self.core.port
        self.assertIsInstance(self.port, AgwPort)
        self.ch = self.core.chan
        self.link = self.ch.link
        self.assertIsInstance(self.link, AgwLink)
        self.link.target = self.ch.target = "OE3BBB"
        self.port.links["OE3BBB"] = self.link
        self.me = self.core.cfg.mycall

    def tearDown(self):
        self._tmp.cleanup()

    def ev(self, text, cfrom="", cto=""):
        self.port._dispatch("E", cfrom, cto, text.encode())

    def test_features(self):
        self.port._dispatch("F", "", "", b"fork=2026.11.11 features=Q3,O,E,F,LVL,LOAD")
        self.assertTrue(self.port.q_supported)
        self.assertEqual(self.port.fork["version"], "2026.11.11")
        self.port._dispatch("E", "", "", b"")
        self.assertTrue(self.port.events)
        self.assertEqual(activity.build(self.core)["modem"]["fork"], "2026.11.11")

    def test_sabm_tries_and_retry_out(self):
        self.link.active = True
        self.ch.state = "connecting"
        self.ev("link ch=0 state=5 rc=3 n2=10 mod=128 k=32", self.me, "OE3BBB")
        self.assertEqual(bar(self.core)["phase"]["t"], "Connecting · SABME 3/10")
        self.ev("link ch=0 state=1 rc=4 n2=10 mod=8 k=4", self.me, "OE3BBB")
        self.assertEqual(bar(self.core)["phase"]["t"], "Connecting · SABM 4/10")
        # 'd' with the reason: red
        states = []
        self.link.on_state = lambda st, why: states.append((st, why))
        self.link.on_agw("d", b"*** DISCONNECTED RETRYOUT With OE3BBB\r")
        self.assertEqual(states[-1], ("offline", "retry-out (no answer)"))
        self.ch.state, self.ch.reason = "offline", "retry-out (no answer)"
        p = bar(self.core)["phase"]
        self.assertEqual((p["t"], p["c"]), ("Retry-out (no answer)", "red"))

    def test_recovery_version_and_load(self):
        self.link.active = self.link.online = True
        self.ch.state, self.ch.mode = "online", "terminal"
        self.ev("link ch=0 state=4 rc=8 n2=10 mod=128 k=32", self.me, "OE3BBB")
        self.ev("dcd ch=0 on=1 load=45 load_tx=5")
        texts = {x["id"]: (x["t"], x["c"]) for x in bar(self.core)["link"]}
        self.assertEqual(texts["retry"], ("Retry 8/10", "red"))
        self.assertEqual(texts["l2"], ("v2.2 · k=32", "grey"))
        self.assertEqual(texts["load"], ("Channel 45 %", "amber"))

    def test_ptt_dcd_light_tx_rx(self):
        self.ev("ptt ch=0 on=1 load=3 load_tx=3")
        m = activity.build(self.core)["modem"]
        self.assertEqual(m["tx"], 0)
        self.ev("ptt ch=0 on=0 load=3 load_tx=3")
        self.ev("dcd ch=0 on=1 load=4 load_tx=3")
        m = activity.build(self.core)["modem"]
        self.assertEqual(m["rx"], 0)
        self.assertEqual(m["load"], 4)

    def test_level_goes_to_the_monitor_frame(self):
        from prcore.ax25.frame import ui_frame
        raw = ui_frame("CQ", "OE1ABC", b"hello").encode()
        self.port._dispatch("K", "OE1ABC", "CQ", b"\x00" + raw)
        self.ev("rx ch=0 lvl=45 mark=12 space=9 fix=1 fec=0", "OE1ABC", "CQ")
        n, entry = self.core.monitor[-1]
        self.assertEqual((entry["lvl"], entry["fix"]), (45, 1))
        self.assertEqual(self.core.levels["OE1ABC"]["lvl"], 45)

    def test_own_frames_raw_replace_t(self):
        from prcore.ax25.frame import ui_frame
        self.port._dispatch("O", "", "", b"")
        self.assertTrue(self.port.own_frames)
        n0 = self.core.monitor_n
        raw = ui_frame("CQ", self.me, b"own").encode()
        self.port._dispatch("O", self.me, "CQ", b"\x00" + raw)
        self.assertEqual(self.core.monitor_n, n0 + 1)
        self.assertGreater(self.core.tx_at, time.time() - 2)
        self.port._dispatch("T", self.me, "CQ", b" 1:Fm X To CQ <UI pid=F0 Len=3 >[19:17:25]\rown\r\0")
        self.assertEqual(self.core.monitor_n, n0 + 1)          # 'T' not twice


class KissL2(unittest.TestCase):
    def test_own_ax25_gives_the_same(self):
        from tbclient.kisslink import KissLink

        class Ax:
            state, rc, modulo, k = 1, 2, 8, 4

            class cfg:
                n2 = 10
        link = KissLink.__new__(KissLink)
        link.ax, link.active = Ax(), True
        self.assertEqual(link.l2(), {"phase": "sabm", "rc": 2, "n2": 10, "mod": 8, "k": 4})


if __name__ == "__main__":
    unittest.main()
