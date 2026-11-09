"""CR98 (audit follow-up of CR88): a broad fuzz run over the line parsers of the
client, the TinyBox and the shared code. Whatever comes over the air, no
exception may escape - a parser either takes the line or ignores it.

Seeded, so a failure can be repeated: FUZZ_SEED / FUZZ_N in the environment.
"""

from __future__ import annotations

import asyncio
import os
import random
import tempfile
import unittest

from prcore import aprs, profile
from prcore.chatimg import parse_ref
from tbclient import proto
from tbclient.core import ClientCore
from tinybox.fwd.protocol import ProtocolError, parse_proposal
from tinybox.session import Session

from tests.test_tbclient import client_cfg
from tests.test_tinybox import FakeTransport, make_app

SEED = int(os.environ.get("FUZZ_SEED", "98"))
N = int(os.environ.get("FUZZ_N", "1500"))

WORDS = ["//OK", "//B", "//BEND", "//IN", "//H", "//HEND", "//MOTD", "//WHO", "//PROF", "//WI",
         "//WIEND", "//OUT", "//SYS", "//ERR", "//MSG", "//P", "//ZSYNC", "//M", "//MEND",
         "//S", "//D", "//K", "//KEND", "//SENT", "//HAVE", "//RU", "//I", "//IMGGO", "//IMGOK",
         "//NOIMG", "//TB", "//TB?", "//F", "//FGET", "//IMG", "//ST", "//STR", "//PING",
         "//HEARD?", "//HEARD", "//HIST", "//HM", "//CHESS", "#", "#1", "#FF", "%Q", "~#", "~%",
         "~Q", "~^", "C", "L", "R", "K", "S", "SP", "SB", "B", "I", "/H", "/W", "/Q", "FB", "FA",
         "FS", "FF", "FQ", "F>", ";", "[TINYB-1-B1FHM$]", "SID", "R:", "/EX", "\x1a"]
TOKENS = ["0", "1", "-1", "²", "٣", "①", "99999999999999999999", "1e9", "nan", "", " ",
          "OE3GAS", "OE3GAS-15", "ABCDEF-99", "abc123", "ffffff", "zz", "-", "=", "a=b", "q=1/2/3/",
          "caps=", "caps=,,,", "v=", "t=", "t=²", "‮", "\x1b[2J", "ä" * 300, "x" * 2000,
          "\x00", "\t", "/", "//", "#", "~#a1b2c350LEHV6nWB2yk8pyo0ad", "~%a1b2c3 10 10 a.exe",
          "seq=", "seq=²", "more=1", "h=", "k=1", "r=1", "max=0", "want=-5", ":", "1:2", "@", "!"]


def lines(rnd: random.Random, n: int):
    for _ in range(n):
        k = rnd.randrange(6)
        parts = [rnd.choice(WORDS)] + [rnd.choice(TOKENS) for _ in range(rnd.randrange(k + 1))]
        sep = rnd.choice([" ", " ", " ", "", "  "])
        yield sep.join(parts)


class ClientLines(unittest.IsolatedAsyncioTestCase):
    async def test_core_and_peer(self):
        rnd = random.Random(SEED)
        with tempfile.TemporaryDirectory() as tmp:
            core = ClientCore(client_cfg(tmp, link="telnet"))
            core.link.send_line = lambda text: None
            ch = core.open_channel(2)
            ch.state = "online"
            ch.link.send_line = lambda text: None
            ch.link.send_bytes = lambda data: None
            for i, line in enumerate(lines(rnd, N)):
                with self.subTest(i=i, line=line[:80]):
                    core._on_line(line)                 # the TinyBox in client mode
                    ch.incoming = bool(i % 2)
                    ch.probed = not ch.incoming
                    ch._on_line(line)                   # another station / a TBClient
                    proto.parse_event(line)
                await asyncio.sleep(0)


class SharedParsers(unittest.TestCase):
    def test_parsers(self):
        rnd = random.Random(SEED + 1)
        for i, line in enumerate(lines(rnd, N)):
            with self.subTest(i=i, line=line[:80]):
                profile.decode(line)
                parse_ref(line)
                try:
                    parse_proposal(line)
                except ProtocolError:
                    pass
                aprs.decode("APRS", "OE3GAS", [], None, line.encode("utf-8", "replace"))


class BoxSession(unittest.TestCase):
    def test_session_in_every_state(self):
        rnd = random.Random(SEED + 2)
        app = make_app()
        with self.assertLogs("tinybox", "INFO"):
            for client in (False, True):
                t = FakeTransport()
                s = Session("OE3GAS", app.service, app.cfg, t, origin="radio")
                s.start()
                if client:
                    s.handle_line("//CLIENT TB1 v=2026.11.09 caps=CHAT,SYNC,SYNC2,Z,IMG,HSEQ")
                errors = []
                orig = s._handle_line

                def guarded(line, orig=orig):
                    try:
                        orig(line)
                    except Exception as exc:            # what the catch-all would hide
                        errors.append((line, repr(exc)))
                        raise
                s._handle_line = guarded
                for line in lines(rnd, N):
                    if s.closed:
                        s = Session("OE3GAS", app.service, app.cfg, FakeTransport(), origin="radio")
                        s.start()
                        orig = s._handle_line
                        s._handle_line = guarded
                    try:
                        s.handle_line(line)
                    except Exception as exc:
                        errors.append((line, repr(exc)))
                self.assertEqual(errors[:5], [], f"{len(errors)} errors")


if __name__ == "__main__":
    unittest.main()
