"""CR88 (audit TB-09/TB-20c/TB-23): hostile input must never crash a parser or a
session, and str.isdigit() must not come back into the code."""

from __future__ import annotations

import asyncio
import re
import unittest
from pathlib import Path
from types import SimpleNamespace

from prcore import profile
from prcore.text import isnum, to_int
from tbclient.links import LineSplitter
from tinybox import commands
from tinybox.fwd.protocol import ProtocolError, parse_proposal
from tinybox.fwd.session import ForwardSession, SessionResult

ROOT = Path(__file__).resolve().parent.parent
TRICKY = ["²", "¹²³", "٣", "३", "①", "𝟓", "1²", "", " 1", "+1", "1_000", "-1"]


class IsNum(unittest.TestCase):
    def test_only_ascii_digits(self):
        self.assertTrue(isnum("0123456789"))
        for s in TRICKY:
            self.assertFalse(isnum(s), repr(s))

    def test_to_int(self):
        self.assertEqual(to_int("42"), 42)
        self.assertIsNone(to_int("²"))
        self.assertEqual(to_int("٣", -1), -1)

    def test_no_isdigit_in_the_code(self):
        """Every number check goes through isnum() (or the local _isnum of the
        stand-alone parts brocast/dxfeed). Tests may use isdigit()."""
        allowed = re.compile(r"return s\.isascii\(\) and s\.isdigit\(\)")
        call = re.compile(r"[\w)\]]\.isdigit\(\)")
        found = []
        for path in ROOT.rglob("*.py"):
            rel = path.relative_to(ROOT).as_posix()
            if "/tests/" in f"/{rel}" or path.name.startswith("test_") or "/." in f"/{rel}":
                continue
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if call.search(line) and not allowed.search(line):
                    found.append(f"{rel}:{n}: {line.strip()}")
        self.assertEqual(found, [], "use prcore.text.isnum() instead of .isdigit()")


class Parsers(unittest.TestCase):
    def test_forward_proposal_with_unicode_size(self):        # TB-20c
        for size in ("²", "٣٣", "1²"):
            with self.assertRaises(ProtocolError):
                parse_proposal(f"FB P OE3GAS OE3XYZ OE1ABC 123_OE3GAS {size}")

    def test_bbs_number_lists(self):
        for s in ("²", "٣", "1 ²", "①,2"):
            self.assertIsNone(commands._numbers(s), repr(s))
        self.assertEqual(commands._numbers("1, 2 3"), [1, 2, 3])

    def test_profile_with_unicode_time(self):
        out = profile.decode(profile.encode({"t": 1, "name": "x", "loc": "", "home": ""})
                             .replace("1", "²", 1))
        self.assertIsInstance(out["t"], int)


class LineSplitterGoesOn(unittest.TestCase):
    def test_error_in_one_line_keeps_the_others(self):
        got = []

        def on_line(line):
            if line == "boom":
                raise ValueError("bad line")
            got.append(line)

        sp = LineSplitter(on_line)
        with self.assertLogs("tbclient.links", "ERROR"):
            sp.feed(b"one\rboom\rtwo\r")
        self.assertEqual(got, ["one", "two"])


class ForwardSessionEndsCleanly(unittest.IsolatedAsyncioTestCase):
    async def test_unexpected_error_ends_the_session(self):
        closed = []

        class Link:
            async def drain(self):
                pass

            async def close(self):
                closed.append(True)

        s = ForwardSession.__new__(ForwardSession)
        s.p = SimpleNamespace(call="OE3XYZ", timeout=10, max_session_min=60)
        s.master = True
        s.in_message = False
        s.on_end = None
        s.link = Link()
        s.r = SessionResult("OE3XYZ", True, "agw")

        async def broken():
            int("²")

        s._master = broken
        with self.assertLogs("tinybox.forward", "ERROR"):
            r = await s.run()
        self.assertIn("internal error", r.error)
        self.assertEqual(closed, [True])


if __name__ == "__main__":
    unittest.main()
