"""prcore/kissport.py: the KISS port shared by TinyBox and client (routing,
strangers, incoming connects), without a network: frames go straight in and out."""

from __future__ import annotations

import unittest

from prcore.ax25 import frame as ax
from prcore.ax25.frame import Frame
from prcore.ax25.link import LinkCfg
from prcore.kissport import KissPort, norm_call

MYCALL = "OE3GAS-1"


class Port(KissPort):
    def __init__(self, accept: bool = True) -> None:
        super().__init__(MYCALL.lower() + " ", "127.0.0.1", 1, LinkCfg())
        self.accept = accept
        self.sent: list[Frame] = []
        self.heard: list[tuple | None] = []
        self.events: list[tuple[str, str, object]] = []
        self.kiss.send = lambda raw: True           # type: ignore[method-assign]

    def on_transmit(self, f: Frame, raw: bytes) -> None:
        self.sent.append(Frame.decode(raw))

    def on_heard(self, data, peeked, target) -> None:
        self.heard.append(peeked)

    def accept_incoming(self, link) -> bool:
        return self.accept

    def on_link_event(self, link, name, arg) -> None:
        self.events.append((link.remote, name, arg))

    def hear(self, f: Frame) -> None:
        self._on_kiss(0, f.encode())


class KissPortTest(unittest.TestCase):
    def test_norm_call(self) -> None:
        self.assertEqual(norm_call(" oe3gas-0"), "OE3GAS")
        self.assertEqual(Port().mycall, MYCALL)

    def test_incoming_connect_accepted(self) -> None:
        p = Port()
        p.hear(ax.u_frame("SABM", MYCALL, "OE3TEC", pf=True))
        self.assertEqual([(f.kind, f.dest) for f in p.sent], [("UA", "OE3TEC")])
        self.assertIn("OE3TEC", p.links)
        self.assertEqual(p.events, [("OE3TEC", "connected", "incoming")])

    def test_incoming_connect_refused_gets_dm(self) -> None:
        p = Port(accept=False)
        p.hear(ax.u_frame("SABM", MYCALL, "OE3TEC", pf=True))
        self.assertEqual([(f.kind, f.dest, f.pf) for f in p.sent], [("DM", "OE3TEC", True)])
        self.assertEqual((p.links, p.events), ({}, []))

    def test_stranger_gets_dm(self) -> None:
        p = Port()
        p.hear(ax.i_frame(MYCALL, "OE3TEC", 0, 0, b"hello", poll=True))
        self.assertEqual([f.kind for f in p.sent], ["DM"])
        self.assertEqual(p.links, {})

    def test_frames_for_others_and_unrepeated_path_ignored(self) -> None:
        p = Port()
        p.hear(ax.u_frame("SABM", "OE1XYZ", "OE3TEC", pf=True))
        p.hear(ax.u_frame("SABM", MYCALL, "OE3TEC", pf=True, path=["OE3XHR"]))
        self.assertEqual((p.sent, p.links), ([], {}))
        self.assertEqual(len(p.heard), 2)                # the monitor still hears both

    def test_garbage_reaches_the_monitor_only(self) -> None:
        p = Port()
        p._on_kiss(0, b"\x01\x02")
        self.assertEqual((p.heard, p.sent), ([None], []))

    def test_outgoing_link_and_disconnect_forgets_it(self) -> None:
        p = Port()
        link = p.open_link("oe3tec")
        link.connect(p.now())
        p.service(link)
        self.assertEqual(p.sent[-1].kind, "SABME")        # v2.2 first
        p.hear(ax.u_frame("DM", MYCALL, "OE3TEC", command=False, pf=True))
        self.assertEqual(p.sent[-1].kind, "SABM")         # falls back to v2.0
        p.hear(ax.u_frame("UA", MYCALL, "OE3TEC", command=False, pf=True))
        self.assertIn(("OE3TEC", "connected", "outgoing"), p.events)
        self.assertIn("OE3TEC", p.v20)                    # next time SABM at once
        link.disconnect(p.now())
        p.service(link)
        p.hear(ax.u_frame("UA", MYCALL, "OE3TEC", command=False, pf=True))
        self.assertEqual(p.links, {})
        self.assertEqual(p.events[-1][:2], ("OE3TEC", "disconnected"))


if __name__ == "__main__":
    unittest.main()
