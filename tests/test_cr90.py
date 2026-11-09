"""CR90 step 1 (audit TB-02): two stations under one call are noticed - the real
partner answers what it hears from us with DM (or a second UA) - and then what
the forward session did is not trusted."""

from __future__ import annotations

import unittest

from prcore.ax25 import frame as ax

from tinybox.adapters.forward import SPOOF_NOTE, ForwardModule
from tinybox.fwd.session import SessionResult
from tinybox.linkguard import LinkGuard

from tests.test_forward_module import fwd_app, gas

ME, PARTNER = "OE3XTC-1", "OE3GAS-5"


def u(kind, dest=ME, src=PARTNER, **kw) -> bytes:
    return ax.u_frame(kind, dest, src, **kw).encode()


class Guard(unittest.TestCase):
    def setUp(self):
        self.g = LinkGuard()

    def test_we_called_one_ua_is_the_answer(self):
        self.g.watch(PARTNER, ME, we_called=True)
        self.g.heard(u("UA", command=False))
        self.assertEqual(self.g.result(PARTNER), "")

    def test_second_ua_and_dm(self):
        self.g.watch(PARTNER, ME, we_called=True)
        with self.assertLogs("tinybox.forward", "WARNING"):
            for k in ("UA", "UA", "DM"):
                self.g.heard(u(k, command=False))
        self.assertEqual(self.g.result(PARTNER), "unexpected UA, DM")

    def test_incoming_any_ua_counts(self):
        self.g.watch(PARTNER, ME, we_called=False)
        with self.assertLogs("tinybox.forward", "WARNING"):
            self.g.heard(u("UA", command=False))
        self.assertEqual(self.g.result(PARTNER), "unexpected UA")

    def test_ignored(self):
        self.g.watch(PARTNER, ME, we_called=False)
        self.g.heard(u("DM", dest="OE1ABC"))                  # not to us
        self.g.heard(u("DM", src="OE3GAS-6"))                 # another SSID
        self.g.heard(ax.i_frame(ME, PARTNER, 0, 0, b"hello").encode())
        self.g.heard(u("DISC"))
        self.g.heard(b"\x00garbage")
        self.g.stop(PARTNER)                                  # our DISC goes out
        self.g.heard(u("DM", command=False))                  # its answer to it
        self.assertEqual(self.g.result(PARTNER), "")

    def test_frames_without_watch_cost_nothing(self):
        self.g.heard(u("DM"))
        self.assertEqual(self.g.result(PARTNER), "")


class Suspect(unittest.TestCase):
    def test_sent_offered_again_received_held(self):
        partner = gas(transport="agw", ax25_call=PARTNER)
        app = fwd_app(partner)
        module = ForwardModule(app)
        svc, store = app.service, app.store
        sent = svc.create(from_call="OE1ABC", to_call="ALL", type="B", subject="out",
                          body="x", origin="telnet", at_addr="WW")
        store.fwd_enqueue(sent, "OE3GAS")
        store.fwd_set(sent, "OE3GAS", "done")
        svc.set_fwd_state(sent, "F")
        got = svc.create(from_call="OE1XYZ", to_call="ALL", type="B", subject="in",
                         body="y", origin="forward", at_addr="WW", bid="55_OE3GAS")
        r = SessionResult("OE3GAS", True, "agw")
        r.sent[store.get(sent).bid] = "done"
        r.received.append("55_OE3GAS")
        with self.assertLogs("tinybox.forward", "WARNING"):
            module._suspect(partner, r, "DM")
        self.assertEqual(store.fwd_states(sent)["OE3GAS"], "open")
        self.assertEqual(store.get(sent).fwd, "$")
        held = store.get(got)
        self.assertEqual(held.fwd, "H")
        self.assertTrue(held.note.startswith(SPOOF_NOTE))
        self.assertIn("two stations", r.error)
        self.assertTrue(any("two stations" in m.subject for m in store.list_messages()
                            if m.to_call == app.cfg.station.sysop_call))


if __name__ == "__main__":
    unittest.main()
