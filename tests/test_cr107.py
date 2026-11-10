"""CR107: the same features between two clients and in a chat board - the Python
side (the rest is the web GUI: shout-out, stickers, comments, reactions, links,
alert, board map, direct connection, tick, mail when the other one is gone)."""

from __future__ import annotations

import tempfile
import unittest

from tbclient.core import ClientCore

from tests.test_tbclient import client_cfg


class BoardMap(unittest.TestCase):
    def test_profiles_carry_positions(self):
        with tempfile.TemporaryDirectory() as tmp:
            core = ClientCore(client_cfg(tmp))
            core.settings["profiles"] = {"OE3TEC": {"name": "Tobias", "loc": "JN88EF",
                                                    "home": "", "at": 1}}
            snap = core.profiles.snapshot(["OE3TEC"])
            ll = snap["profiles"]["OE3TEC"]["ll"]
            self.assertAlmostEqual(ll[0], 48.23, delta=0.1)
            self.assertAlmostEqual(ll[1], 16.38, delta=0.1)


class PeerLinesAreText(unittest.TestCase):
    def test_comment_and_reaction_go_into_the_history(self):
        """~^m1 and ~*y2 are ordinary chat lines: stored, compared, sent again."""
        from pathlib import Path

        from tbclient import peerchat
        with tempfile.TemporaryDirectory() as d:
            s = peerchat.PeerChat(Path(d) / "p.db")
            s.add("OE3TEC", "rx", "Servus")
            s.add("OE3TEC", "tx", "~^y1 Hallo zurueck")
            s.add("OE3TEC", "tx", "~*y1 :+1")
            self.assertEqual([m["text"] for m in s.messages("OE3TEC")],
                             ["Servus", "~^y1 Hallo zurueck", "~*y1 :+1"])
            self.assertEqual(s.state("OE3TEC")["tx"][0], 2)


if __name__ == "__main__":
    unittest.main()
