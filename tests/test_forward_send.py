"""F4: TinyBox sends mail to partner mailboxes, both directions in one session,
scheduler, HOLD/REL, directed bulletins. fwdsim plays OE3GAS (and DL0XTC behind it)."""

from __future__ import annotations

import asyncio
import time
import unittest

from fwdsim.harness import tinybox_login
from fwdsim.link import TcpLink as SimTcpLink, tcp_connect
from fwdsim.session import Faults, ForwardSession as SimSession

from tinybox.adapters.forward import ForwardModule
from tinybox.fwd.protocol import ProtocolError, parse_fs, parse_rli_reply
from tinybox.fwd.router import Router
from tinybox.fwd.send import Sender, wire_lines

from tests.test_forward_module import HADDR, free_port, fwd_app, gas, sim_net

BODY = "Test message.\nSecond line."
HOP = "OE3GAS.#OOE.AUT.EU"
REMOTE = "DL0XTC.#BAY.DEU.EU"


def calls(rlines: list[str]) -> list[str]:
    return [x.split("@:")[1].split(".")[0] for x in rlines]


class SendBase(unittest.IsolatedAsyncioTestCase):
    """TinyBox (OE3XTC) with one partner OE3GAS; fwdsim OE3GAS waits on a TCP port."""

    partner_kw: dict = {}

    async def asyncSetUp(self):
        self.net = sim_net()
        self.hop, self.remote = self.net.hop, self.net.remote
        self.faults: Faults | None = None
        self.done: asyncio.Queue = asyncio.Queue()

        async def handle(reader, writer):
            s = SimSession(self.hop, SimTcpLink(reader, writer, "hop<tcp"), "OE3XTC",
                           master=False, faults=self.faults, timeout=5)
            await self.done.put(await s.run())

        self.server = await asyncio.start_server(handle, "127.0.0.1", 0)
        port = self.server.sockets[0].getsockname()[1]
        self.app = fwd_app(gas(port=port, **self.partner_kw))
        self.module = ForwardModule(self.app)
        self.app.forward = self.module

    async def asyncTearDown(self):
        self.server.close()

    def write(self, type: str, to: str, at: str, subject: str, body: str = BODY) -> int:
        return self.app.service.create(from_call="OE1ABC", to_call=to, type=type,
                                       subject=subject, body=body, origin="telnet", at_addr=at)

    async def tinybox_calls(self, faults: Faults | None = None):
        self.faults = faults
        r = await self.module.call("OE3GAS")
        sim = await asyncio.wait_for(self.done.get(), 5)
        await self.net.settle()                          # OE3GAS passes on to DL0XTC
        return r, sim


class SendTests(SendBase):
    async def test_t01_personal_to_partner(self):
        msg_id = self.write("P", "OE3GAS", HOP, "T01")
        r, sim = await self.tinybox_calls()
        self.assertTrue(r.ok and sim.ok, (r.error, sim.error))
        got = self.hop.find(subject="T01")
        self.assertEqual(len(got), 1)
        self.assertEqual(calls(got[0].rlines), ["OE3GAS", "OE3XTC"])
        self.assertEqual(got[0].body, BODY)
        self.assertEqual(self.app.store.get(msg_id).fwd, "F")
        self.assertEqual(self.app.store.fwd_queue_list(), [])

    async def test_t02_over_the_hop(self):
        self.write("P", "DL1ABC", REMOTE, "T02")
        await self.tinybox_calls()
        got = self.remote.find(subject="T02")
        self.assertEqual(len(got), 1)
        self.assertEqual(calls(got[0].rlines), ["DL0XTC", "OE3GAS", "OE3XTC"])

    async def test_t03_bulletin_ww(self):
        self.write("B", "ALL", "WW", "T03")
        await self.tinybox_calls()
        self.assertEqual(len(self.hop.find(subject="T03")), 1)
        self.assertEqual(len(self.remote.find(subject="T03")), 1)

    async def test_t07_both_directions(self):
        m = self.hop.create("P", "OE1ABC", HADDR, "T07 to TinyBox", BODY)
        self.write("P", "OE3GAS", HOP, "T07 to OE3GAS")
        r, sim = await self.tinybox_calls()
        self.assertTrue(r.ok and sim.ok, (r.error, sim.error))
        self.assertEqual(r.received, [m.bid])
        self.assertEqual(len(self.hop.find(subject="T07 to OE3GAS")), 1)

    async def test_t10_not_back_to_sender(self):
        m = self.hop.create("B", "ALL", "WW", "T10", BODY)
        r, sim = await self.tinybox_calls()              # fetched in reverse
        self.assertEqual(r.received, [m.bid])
        r, sim = await self.tinybox_calls()
        self.assertNotIn(m.bid, sim.proposed_to_us)

    async def test_t14_fs_plus_minus_later(self):
        ids = [self.write("P", "OE3GAS", HOP, f"T14 {i}") for i in (1, 2, 3)]
        await self.tinybox_calls(Faults(fs="+-="))
        first = [len(self.hop.find(subject=f"T14 {i}")) for i in (1, 2, 3)]
        self.assertEqual(first, [1, 0, 0])
        self.assertEqual([self.app.store.get(i).fwd for i in ids], ["F", "F", "$"])
        await self.tinybox_calls()
        second = [len(self.hop.find(subject=f"T14 {i}")) for i in (1, 2, 3)]
        self.assertEqual(second, [1, 0, 1])
        self.assertEqual(self.app.store.fwd_queue_list(), [])

    async def test_many_messages_in_blocks(self):
        for i in range(12):
            self.write("P", "OE3GAS", HOP, f"many {i}")
        r, sim = await self.tinybox_calls()
        self.assertTrue(r.ok and sim.ok, (r.error, sim.error))
        self.assertEqual(sum(1 for v in r.sent.values() if v == "done"), 12)
        self.assertEqual(len(sim.received), 12)
        self.assertEqual(sorted(m.subject for m in self.hop.messages()),
                         sorted(f"many {i}" for i in range(12)))      # titles intact

    async def test_t20_prompt_trap(self):
        self.write("P", "OE3GAS", HOP, "T20")
        r, sim = await self.tinybox_calls(Faults(prompt_trap=True))
        self.assertTrue(r.ok, r.error)
        self.assertEqual(len(self.hop.find(subject="T20")), 1)

    async def test_subject_79_and_ex_line(self):
        self.write("P", "OE3GAS", HOP, "S" * 60, "a\n/EX\nb")
        msg = self.app.store.list_messages()[0]
        self.app.store.update_field(msg.id, "subject", "S" * 90)
        await self.tinybox_calls()
        got = self.hop.find(bid=msg.bid)[0]
        self.assertEqual(len(got.subject), 79)
        self.assertIn("/EX", got.body)

    async def test_ascii_partner_both_directions(self):
        m = self.hop.create("P", "OE1ABC", HADDR, "ascii to TinyBox", BODY)
        self.write("P", "OE3GAS", HOP, "ascii to OE3GAS")
        self.write("B", "ALL", "WW", "ascii bulletin")
        r, sim = await self.tinybox_calls(Faults(sid="[FWDSIM-0.1-H$]"))
        self.assertTrue(r.ok and sim.ok, (r.error, sim.error))
        self.assertEqual((r.mode, sim.mode), ("ascii", "rli"))
        self.assertEqual(len(self.hop.find(subject="ascii to OE3GAS")), 1)
        self.assertEqual(len(self.hop.find(subject="ascii bulletin")), 1)
        self.assertEqual(r.received, [m.bid])


class SlaveSendTests(unittest.IsolatedAsyncioTestCase):
    """The partner calls; TinyBox hands over its mail in the same session."""

    async def asyncSetUp(self):
        self.app = fwd_app(gas())
        self.module = ForwardModule(self.app)
        self.module.cfg.listen_port = free_port()
        await self.module.start_server()
        self.net = sim_net()

    async def asyncTearDown(self):
        self.module.server.close()

    async def hop_calls(self, faults=None):
        link = await tcp_connect("127.0.0.1", self.module.listen_port, "OE3GAS>tinybox")
        await tinybox_login(link, "OE3GAS", "geheim", 5)
        return await SimSession(self.net.hop, link, "OE3XTC", master=True, faults=faults,
                                timeout=5).run()

    def write(self, subject):
        return self.app.service.create(from_call="OE1ABC", to_call="OE3GAS", type="P",
                                       subject=subject, body=BODY, origin="telnet", at_addr=HOP)

    async def test_fbb_reverse(self):
        self.write("to OE3GAS (fbb)")
        r = await self.hop_calls()
        self.assertTrue(r.ok, r.error)
        self.assertEqual(len(self.net.hop.find(subject="to OE3GAS (fbb)")), 1)

    async def test_t26_ascii_reverse(self):
        m = self.net.hop.create("P", "OE1ABC", HADDR, "T26 to TinyBox", BODY)
        self.write("T26 to OE3GAS")
        r = await self.hop_calls(Faults(sid="[FWDSIM-0.1-H$]"))
        self.assertTrue(r.ok, r.error)
        self.assertEqual(r.mode, "rli")
        self.assertIn("> F>", r.transcript)
        self.assertEqual(len(self.net.hop.find(subject="T26 to OE3GAS")), 1)
        self.assertIsNotNone(self.app.store.get_by_bid(m.bid))


class SchedulerTests(SendBase):
    async def test_calls_when_mail_waits(self):
        self.assertEqual(self.module.tick(), [])          # nothing queued
        self.write("P", "OE3GAS", HOP, "sched")
        self.assertEqual(self.module.tick(), ["OE3GAS"])
        await asyncio.wait_for(self.done.get(), 5)
        for _ in range(50):
            if self.app.store.fwd_queue_list() == []:
                break
            await asyncio.sleep(0.05)
        self.assertEqual(len(self.hop.find(subject="sched")), 1)
        self.assertEqual(self.module.tick(), [])          # done, nothing left

    async def test_due_rules(self):
        p = self.app.cfg.forward.partners["OE3GAS"]
        now = time.monotonic()
        self.assertFalse(self.module.due(p, now, 600))     # nothing queued, no interval
        p.interval_min = 30
        self.assertTrue(self.module.due(p, now, 600))      # never called yet
        self.module.last_call["OE3GAS"] = now
        self.assertFalse(self.module.due(p, now + 60, 600))
        self.assertTrue(self.module.due(p, now + 1801, 600))
        p.window = (22 * 60, 6 * 60)                       # 22:00-06:00
        self.assertFalse(self.module.due(p, now + 1801, 600))
        self.assertTrue(self.module.due(p, now + 1801, 23 * 60))
        self.assertTrue(self.module.due(p, now + 1801, 5 * 60))
        self.module.failed_at["OE3GAS"] = now + 1800
        self.assertFalse(self.module.due(p, now + 1801, 23 * 60))   # retry_min
        p.auto = False
        self.module.failed_at.clear()
        self.assertFalse(self.module.due(p, now + 1801, 23 * 60))

    async def test_later_waits_retry_min(self):
        p = self.app.cfg.forward.partners["OE3GAS"]
        msg_id = self.write("P", "OE3GAS", HOP, "later")
        self.app.store.fwd_set(msg_id, "OE3GAS", "later")
        now = time.monotonic()
        self.module.last_call["OE3GAS"] = now
        self.assertFalse(self.module.due(p, now + 60, 600))
        self.assertTrue(self.module.due(p, now + p.retry_min * 60, 600))

    async def test_unreachable_partner_waits(self):
        self.server.close()
        await self.server.wait_closed()
        self.app.cfg.forward.partners["OE3GAS"].port = free_port()
        self.write("P", "OE3GAS", HOP, "nobody home")
        self.module.tick()
        for _ in range(50):
            if "OE3GAS" in self.module.failed_at:
                break
            await asyncio.sleep(0.05)
        self.assertIn("OE3GAS", self.module.failed_at)
        self.assertEqual(self.module.tick(), [])          # retry_min not over


class RestartTests(SendBase):
    async def test_t21_restart_with_full_queue(self):
        """The queue lives in the database: after a restart every message goes out once."""
        import tempfile
        from pathlib import Path
        from tinybox.app import App
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "tinybox.db"
            app1 = App.create(self.app.cfg, db_path=str(db))
            ForwardModule(app1)
            for i in range(3):
                app1.service.create(from_call="OE1ABC", to_call="OE3GAS", type="P",
                                    subject=f"T21 {i}", body=BODY, origin="telnet", at_addr=HOP)
            app1.store.close()                                   # "TinyBox stopped"
            app2 = App.create(self.app.cfg, db_path=str(db))     # restart
            module = ForwardModule(app2)
            app2.forward = module
            self.assertEqual(len(app2.store.fwd_pending("OE3GAS")), 3)
            await module.call("OE3GAS")
            await asyncio.wait_for(self.done.get(), 5)
            await module.call("OE3GAS")                          # second call: nothing again
            await asyncio.wait_for(self.done.get(), 5)
            app2.store.close()
        self.assertEqual([len(self.hop.find(subject=f"T21 {i}")) for i in range(3)], [1, 1, 1])


class HoldReleaseTests(SendBase):
    async def test_hold_and_release(self):
        msg_id = self.write("P", "OE3GAS", HOP, "hold me")
        self.module.hold(msg_id)
        self.assertEqual(self.app.store.get(msg_id).fwd, "H")
        self.assertEqual(self.app.store.fwd_pending("OE3GAS"), [])
        self.assertEqual(self.module.release(msg_id), "$")
        self.assertEqual([m.id for m in self.app.store.fwd_pending("OE3GAS")], [msg_id])
        r, _ = await self.tinybox_calls()
        self.assertEqual(self.app.store.get(msg_id).fwd, "F")

    async def test_release_local_and_no_route(self):
        local = self.write("P", "OE1XYZ", "", "local")
        self.module.hold(local)
        self.assertEqual(self.module.release(local), "")
        self.app.cfg.forward.partners["OE3GAS"].routes = ["AUT.EU"]
        far = self.write("P", "W1AW", "W1AW.#WMA.MA.USA.NOAM", "T18 far away")
        self.assertEqual(self.app.store.get(far).fwd, "H")          # T18: no route -> held
        self.assertEqual(self.module.release(far), "H")


class UnitTests(unittest.TestCase):
    def test_parse_fs(self):
        self.assertEqual(parse_fs("FS +-=", 3), ["+", "-", "="])
        self.assertEqual(parse_fs("FS YNLRH", 5), ["+", "-", "=", "-", "+"])
        for bad, n in (("FS +-", 3), ("FS +x", 2), ("XX +", 1)):
            with self.assertRaises(ProtocolError):
                parse_fs(bad, n)

    def test_rli_reply(self):
        self.assertEqual([parse_rli_reply(x) for x in ("OK", "NO", "LATER", "REJECT", ">")],
                         ["+", "-", "=", "-", None])

    def test_wire_and_send_cmd(self):
        app = fwd_app(gas())
        p_id = app.service.create(from_call="OE1ABC", to_call="OE3GAS", type="P", subject="s",
                                  body="x\n/EX", origin="telnet", at_addr=HOP)
        b_id = app.service.create(from_call="OE1ABC", to_call="ALL", type="B", subject="b",
                                  body="y", origin="telnet", at_addr="WW")
        p, b = app.store.get(p_id), app.store.get(b_id)
        lines = wire_lines(p)
        self.assertTrue(lines[1].startswith("R:"))
        self.assertEqual(lines[-1], "'/EX'")
        self.assertEqual(Sender.send_cmd(p), f"SP OE3GAS @ {HOP} < OE1ABC")      # MID: no $
        self.assertEqual(Sender.send_cmd(b), f"SB ALL @ WW < OE1ABC ${b.bid}")

    def test_directed_bulletin(self):
        app = fwd_app(gas(), gas(call="DL0XTC", routes=["DEU.EU"], areas=["DEU"]))
        r = Router(app.cfg.forward, HADDR)
        mk = lambda at: app.store.get(app.service.create(
            from_call="OE1ABC", to_call="ALL", type="B", subject="x", body="x",
            origin="telnet", at_addr=at))
        self.assertEqual(r.targets(mk("FRA.EU")), ["OE3GAS"])            # directed, default WW
        self.assertEqual(r.targets(mk("DEU.EU")), ["DL0XTC"])            # directed to Germany
        self.assertEqual(sorted(r.targets(mk("WW"))), ["OE3GAS"])        # flood (areas)
        self.assertEqual(r.targets(mk("AUT")), ["OE3GAS"])               # our own area: flood


if __name__ == "__main__":
    unittest.main()
