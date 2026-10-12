"""AGW adapter tests against a simulated Direwolf (no radio needed)."""

from __future__ import annotations

import asyncio
import dataclasses
import sqlite3
import struct
import unittest

from tinybox.adapters import agw
from tinybox.adapters.agw import Frame

from tests.test_tinybox import make_app

MYCALL = "OE3GAS-1"


class FakeDirewolf:
    """Speaks just enough AGWPE to test TinyBox."""

    def __init__(self) -> None:
        self.frames: list[Frame] = []
        self.writer: asyncio.StreamWriter | None = None
        self.registrations = 0
        self.registered = asyncio.Event()
        self.disconnected = asyncio.Event()
        self.outstanding = 0  # value reported in 'Y' replies

    async def handle(self, reader, writer) -> None:
        self.writer = writer
        try:
            while True:
                f = await agw.read_frame(reader)
                self.frames.append(f)
                if f.kind == "R":
                    self.send(Frame("R", data=struct.pack("<hhhh", 1, 0, 7, 0)))
                elif f.kind == "X":
                    self.send(Frame("X", call_from=f.call_from, data=b"\x01"))
                    self.registrations += 1
                    self.registered.set()
                elif f.kind == "Y":
                    self.send(Frame("Y", call_from=f.call_from, call_to=f.call_to,
                                    data=struct.pack("<I", self.outstanding)))
                elif f.kind == "d":
                    self.send(Frame("d", call_from=f.call_to, call_to=f.call_from,
                                    data=b"*** DISCONNECTED\r"))
                    self.disconnected.set()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass

    def send(self, frame: Frame) -> None:
        self.writer.write(frame.pack())

    def connect(self, remote: str) -> None:
        self.send(Frame("C", call_from=remote, call_to=MYCALL,
                        data=f"*** CONNECTED To Station {remote}\r".encode()))

    def data(self, remote: str, text: str) -> None:
        self.send(Frame("D", pid=0xF0, call_from=remote, call_to=MYCALL, data=text.encode()))

    def output_for(self, remote: str) -> str:
        return b"".join(f.data for f in self.frames
                        if f.kind == "D" and f.call_to == remote).decode()


async def start(app):
    dw = FakeDirewolf()
    server = await asyncio.start_server(dw.handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    app.cfg.direwolf = dataclasses.replace(app.cfg.direwolf, agw_port=port, reconnect_sec=1)
    adapter = agw.AgwAdapter(app)
    task = asyncio.create_task(adapter.run())
    await asyncio.wait_for(dw.registered.wait(), 5)
    return dw, server, adapter, task


async def stop(server, task, dw=None):
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    if dw is not None and dw.writer is not None:
        dw.writer.close()
    server.close()
    await server.wait_closed()
    await asyncio.sleep(0)


class AgwTests(unittest.TestCase):
    def test_frame_roundtrip(self):
        raw = Frame("D", 0, 0xF0, "OE3GAS-1", "OE1ABC", b"hello\r").pack()
        self.assertEqual(len(raw), 36 + 6)
        port, kind, pid, cf, ct, length, _ = agw.HEADER.unpack(raw[:36])
        self.assertEqual((kind, pid, agw._call(cf), agw._call(ct), length),
                         (b"D", 0xF0, "OE3GAS-1", "OE1ABC", 6))

    def test_session_over_agw(self):
        async def scenario():
            app = make_app()
            dw, server, adapter, task = await start(app)
            dw.connect("OE1ABC-7")
            await asyncio.sleep(0.1)
            dw.data("OE1ABC-7", "S OE3GAS\rHello\rLine one\r/EX\rL\rB\r")
            await asyncio.wait_for(dw.disconnected.wait(), 5)
            await asyncio.sleep(0.1)
            await stop(server, task, dw)
            return app, dw, adapter

        app, dw, adapter = asyncio.run(scenario())
        out = dw.output_for("OE1ABC-7")
        self.assertIn("hello OE1ABC-7", out)
        self.assertIn("Msg 1 saved.", out)
        self.assertIn("73, bye", out)
        msg = app.store.get(1)
        self.assertEqual((msg.from_call, msg.origin, msg.body), ("OE1ABC-7", "radio", "Line one"))
        xs = [f for f in dw.frames if f.kind == "X"]
        self.assertEqual(xs[0].call_from, MYCALL)
        for f in dw.frames:
            if f.kind == "D":
                self.assertLessEqual(len(f.data), app.cfg.direwolf.paclen)
                self.assertEqual(f.pid, 0xF0)
        self.assertEqual(len(app.registry), 0)
        self.assertEqual(adapter.conns, {})

    def test_no_sysop_over_radio(self):
        async def scenario():
            app = make_app()
            dw, server, adapter, task = await start(app)
            dw.connect("OE3GAS")
            await asyncio.sleep(0.1)
            dw.data("OE3GAS", "E 1 SUBJ x\rB\r")
            await asyncio.wait_for(dw.disconnected.wait(), 5)
            await stop(server, task, dw)
            return dw

        out = asyncio.run(scenario()).output_for("OE3GAS")
        self.assertNotIn("SYSOP", out)
        self.assertIn("Not allowed.", out)

    def test_abort_drops_queued_output(self):
        async def scenario():
            app = make_app()
            for i in range(30):
                app.service.create(from_call="OE1ABC", to_call="ALL", type="B",
                                   subject=f"Bulletin number {i + 1}", body="x", origin="radio")
            dw, server, adapter, task = await start(app)
            dw.outstanding = 99  # Direwolf "busy": nothing gets acknowledged
            dw.connect("OE5XYZ")
            await asyncio.sleep(0.1)
            dw.data("OE5XYZ", "L\r")
            await asyncio.sleep(0.3)
            queued = len(adapter.conns["OE5XYZ"].queue)
            dw.data("OE5XYZ", "A\r")            # pager (CR29): rest skipped
            await asyncio.sleep(0.1)
            dw.data("OE5XYZ", "A\r")            # command A: queued output dropped
            await asyncio.sleep(0.1)
            dw.outstanding = 0
            dw.data("OE5XYZ", "B\r")
            await asyncio.wait_for(dw.disconnected.wait(), 5)
            await stop(server, task, dw)
            return dw, queued

        dw, queued = asyncio.run(scenario())
        out = dw.output_for("OE5XYZ")
        self.assertGreater(queued, 2)                   # one page (CR29) in several frames
        self.assertIn("Output aborted.", out)
        self.assertNotIn("Bulletin number 1\r", out)  # oldest row was never sent
        self.assertIn("73, bye", out)

    def test_internal_error_keeps_connection(self):
        """Bug 2026-10-04: an exception while saving (/EX) propagated out of
        AgwAdapter.run(), disconnected the user and silently killed the radio link."""
        async def scenario():
            app = make_app()
            calls = {"n": 0}
            real_add = app.store.add_message

            def flaky_add(**kw):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise sqlite3.OperationalError("database is locked")
                return real_add(**kw)

            app.store.add_message = flaky_add
            dw, server, adapter, task = await start(app)
            dw.connect("OE3GAS")
            await asyncio.sleep(0.1)
            dw.data("OE3GAS", "S OE3TEC\rEine Mail für Tobi\rThe quick brown fox\r/EX\r")
            await asyncio.sleep(0.3)
            still_connected = "OE3GAS" in adapter.conns
            dw.data("OE3GAS", "S OE3TEC\rZweiter Versuch\rText\r/EX\rB\r")
            await asyncio.wait_for(dw.disconnected.wait(), 5)
            await stop(server, task, dw)
            return dw, still_connected, task

        dw, still_connected, task = asyncio.run(scenario())
        out = dw.output_for("OE3GAS")
        self.assertTrue(still_connected)
        self.assertIn("Internal error", out)
        self.assertIn("Msg 1 saved.", out)
        self.assertIn("73, bye", out)

    def test_reconnect_after_direwolf_restart(self):
        async def scenario():
            app = make_app()
            dw, server, adapter, task = await start(app)
            dw.registered.clear()
            dw.writer.close()  # Direwolf goes away
            await asyncio.wait_for(dw.registered.wait(), 5)
            await stop(server, task, dw)
            return dw

        self.assertEqual(asyncio.run(scenario()).registrations, 2)


if __name__ == "__main__":
    unittest.main()
