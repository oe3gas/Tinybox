"""R9: prcore/agwport.py - the shared AGW connection loop of TinyBox and client."""

from __future__ import annotations

import asyncio
import logging
import unittest

from prcore import agwport
from prcore.agw import Frame, read_frame


class Probe(agwport.AgwClient):
    def __init__(self, port: int) -> None:
        super().__init__(logging.getLogger("test.agwport"))
        self.port, self.events, self.frames = port, [], []
        self.up = asyncio.Event()

    def agw_address(self):
        return "127.0.0.1", self.port, 0.05

    def agw_opened(self):
        self.events.append("opened")
        self.write_frame(Frame("R"))
        self.up.set()

    def agw_frame(self, f):
        if f.kind == "B":
            raise ValueError("one bad frame")
        self.frames.append(f.kind)

    def agw_closed(self):
        self.events.append("closed")
        self.up.clear()


class AgwClientTests(unittest.TestCase):
    def test_reconnects_and_survives_a_bad_frame(self):
        async def scenario():
            seen = []

            async def handle(reader, writer):
                seen.append((await read_frame(reader)).kind)      # 'R' after connect
                for kind in ("B", "K", "y"):
                    writer.write(Frame(kind).pack())
                await writer.drain()
                await asyncio.sleep(0.1)
                writer.close()                                     # Direwolf goes away

            server = await asyncio.start_server(handle, "127.0.0.1", 0)
            probe = Probe(server.sockets[0].getsockname()[1])
            task = asyncio.create_task(probe.run())
            for _ in range(100):
                if probe.events.count("opened") >= 2:
                    break
                await asyncio.sleep(0.05)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            server.close()
            return probe, seen

        with self.assertLogs("test.agwport", logging.INFO) as logs:
            probe, seen = asyncio.run(scenario())
        self.assertGreaterEqual(probe.events.count("opened"), 2)      # reconnected
        self.assertEqual(probe.events[-1], "closed")                   # cancel cleans up too
        self.assertEqual(probe.frames[:2], ["K", "y"])                 # after the bad 'B'
        self.assertEqual(seen[:2], ["R", "R"])
        text = "\n".join(logs.output)
        self.assertIn("error handling AGW frame 'B'", text)
        self.assertIn("AGW connection lost", text)
        self.assertFalse(probe.write_frame(Frame("R")))                # no link: not sent

    def test_not_reachable_warns_once(self):
        async def scenario():
            probe = Probe(1)                                           # nothing listens
            task = asyncio.create_task(probe.run())
            await asyncio.sleep(0.4)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        with self.assertLogs("test.agwport", logging.DEBUG) as logs:
            asyncio.run(scenario())
        errors = [r for r in logs.records if r.levelno == logging.ERROR]
        self.assertEqual(len(errors), 1)
        self.assertGreater(len(logs.records), 1)                       # the rest quietly

    def test_parse_hw(self):
        """CR140: the fork's 'A' answer, values with blanks up to the end of the line."""
        hw = agwport.parse_hw(b"v=1\nadev0_in=Mikrofon (USB Audio CODEC)\nadev0_in_ok=0\n"
                              b"ptt0=COM20 RTS\nrubbish\n")
        self.assertEqual(hw, {"v": "1", "adev0_in": "Mikrofon (USB Audio CODEC)",
                              "adev0_in_ok": "0", "ptt0": "COM20 RTS"})
        self.assertEqual(agwport.parse_hw(b""), {})

    def test_parse_fork(self):
        self.assertEqual(agwport.parse_fork(b"fork=2026-11-15 features=Q,O,E"),
                         {"version": "2026-11-15", "features": ["E", "O", "Q"]})
        self.assertEqual(agwport.parse_fork(b""), {"version": "", "features": []})


if __name__ == "__main__":
    unittest.main()
