"""tbtest - the testbed (PLANUNG 27): checksums, chat bookkeeping, the generated
tinybox.conf, the command line, and one short real run against a test box."""

from __future__ import annotations

import asyncio
import random
import socket
import tempfile
import time
import unittest
from pathlib import Path

from tbtest import __main__ as cli
from tbtest import bed as bed_mod
from tbtest import ledger as L
from tbclient import config as ccfg
from tbtest import channel as CH
from tbtest import report
from tbtest.runner import Options, Run
from tinybox import config


def free_ports(n: int, udp: bool) -> list[int]:
    """n free ports in a row (best effort)."""
    kind = socket.SOCK_DGRAM if udp else socket.SOCK_STREAM
    for base in range(23000, 60000, 37):
        ok = True
        for p in range(base, base + n):
            with socket.socket(socket.AF_INET, kind) as s:
                try:
                    s.bind(("127.0.0.1", p))
                except OSError:
                    ok = False
                    break
        if ok:
            return list(range(base, base + n))
    raise unittest.SkipTest("no free ports")


class LedgerTests(unittest.TestCase):
    def test_body_roundtrip_and_tamper(self):
        rng = random.Random(1)
        body = L.make_body(rng, "abcd-OE1TBA-1", 800)
        self.assertEqual(L.check_body(body), ("abcd-OE1TBA-1", True))
        # how a text may come back: CR line ends, blanks at the end of lines
        back = body.replace("\n", "\r\n").replace(".", ".  ", 2) + "\r\n\r\n"
        self.assertEqual(L.check_body(back), ("abcd-OE1TBA-1", True))
        broken = body[:-5] + "X" + body[-4:]
        self.assertEqual(L.check_body(broken), ("abcd-OE1TBA-1", False))
        self.assertEqual(L.check_body("hello\nworld"), (None, False))

    def test_read_by_counts_only_this_run(self):
        led = L.Ledger("r1", random.Random(2))
        m = led.new_msg("OE1TBA", "P", "DL1TBB", "T")
        led.stored(m, 7)
        self.assertEqual([x.id for x in led.unread_for("DL1TBB")], [7])
        self.assertEqual(led.unread_for("OE1TBA"), [])
        self.assertEqual(led.read_by("DL1TBB", m.body), (m.key, True))
        self.assertEqual(led.unread_for("DL1TBB"), [])
        other = L.make_body(random.Random(3), "r0-OE1TBA-1", 100)
        self.assertEqual(led.read_by("DL1TBB", other), (None, False))
        self.assertEqual(led.foreign, 1)
        self.assertEqual(led.key_of_subject(m.subject), m.key)
        v = led.verify(["OE1TBA", "DL1TBB"])
        self.assertEqual((v["private"]["stored"], v["private"]["ok"]), (1, 1))

    def test_chat_expected_and_missing(self):
        led = L.Ledger("r1", random.Random(4))
        t = time.monotonic()
        led.stays = {"A": [L.Stay("TREFF", t - 100, t + 100)],
                     "B": [L.Stay("TREFF", t - 100, t + 100)],
                     "C": [L.Stay("TECH", t - 100, t + 100)],        # other board
                     "D": [L.Stay("TREFF", t - 1, t + 100)]}         # just joined: margin
        k1 = led.chat_key("A")
        led.lines[k1] = L.ChatLine(k1, "A", "TREFF", f"tbt {k1}", t)
        led.chat_heard("A", f"tbt {k1}")                              # own echo
        led.chat_heard("B", f"A: tbt {k1} hi")
        v = led.verify(["A", "B", "C", "D"])
        self.assertEqual((v["chat"]["expected"], v["chat"]["delivered"]), (1, 1))
        k2 = led.chat_key("B")
        led.lines[k2] = L.ChatLine(k2, "B", "TREFF", f"tbt {k2}", t)
        v = led.verify(["A", "B", "C", "D"])
        self.assertEqual(v["chat"]["missing"], [(k2, "A")])


class BedTests(unittest.TestCase):
    def test_init_writes_a_valid_tinybox_conf(self):
        with tempfile.TemporaryDirectory() as d:
            bed, new = bed_mod.init(Path(d))
            self.assertTrue(new)
            cfg = config.load(bed.box_conf)
            self.assertEqual(cfg.station.mailbox_call, "OE3TBX-1")
            self.assertEqual(cfg.radio.interface, "kiss")
            self.assertEqual(cfg.kiss.port, bed.air_port)
            self.assertTrue(cfg.axudp.enabled)
            self.assertEqual(set(cfg.axudp.peers), set(bed_mod.USERS) | {"OE3GAS"})
            self.assertEqual(len(bed_mod.USERS), 30)
            # everybody is reached through the simulated channel
            self.assertEqual({p.port for p in cfg.axudp.peers.values()}, {bed.channel_port})
            self.assertEqual((cfg.axudp.maxframe_ext, cfg.axudp.t1_sec), (4, 6.0))
            self.assertEqual((cfg.axudp.air_baud, cfg.axudp.txdelay_ms), (1200, 300))
            self.assertGreaterEqual(cfg.mailbox.max_users, 31)
            self.assertFalse(cfg.update.check)
            self.assertFalse(cfg.brocast.publish)
            bed.check_box_conf()
            # the guest's client conf is a valid tbclient.conf for the testbed
            g = ccfg.load(bed.guest_conf)
            self.assertEqual((g.mycall, g.tinybox_call), ("OE3GAS", "OE3TBX-1"))
            self.assertEqual((g.axudp_port, g.axudp_listen), (bed.channel_port, bed.guest_port))
            self.assertEqual((g.axudp_maxframe, g.axudp_t1_sec), (4, 6.0))
            self.assertEqual((g.axudp_air_baud, g.axudp_txdelay_ms), (1200, 300))
            from tbclient.kisslink import axudp_link_cfg
            lc = axudp_link_cfg(g)
            self.assertEqual((lc.air_baud, lc.txdelay_sec, lc.maxframe_ext, lc.t1_max_sec),
                             (1200, 0.3, 4, 24.0))
            self.assertEqual((g.link, g.kiss_port, g.web_port), ("kiss", bed.air_port, 7745))
            self.assertEqual(g.data_dir, Path(d).resolve() / "guest")
            # tbtest.conf edited: tinybox.conf no longer fits until init again
            text = bed.conf_path.read_text(encoding="utf-8").replace("10193", "10293")
            bed.conf_path.write_text(text, encoding="utf-8")
            with self.assertRaises(bed_mod.BedError):
                bed_mod.Bed.load(Path(d)).check_box_conf()
            bed2, new = bed_mod.init(Path(d))
            self.assertFalse(new)                  # the edited tbtest.conf is kept
            self.assertEqual(bed2.box_port, 10293)
            bed2.check_box_conf()

    def test_quality_section_and_old_conf(self):
        with tempfile.TemporaryDirectory() as d:
            bed, _ = bed_mod.init(Path(d))
            p = bed.conf_path
            p.write_text(p.read_text(encoding="utf-8").replace(
                "[quality]\n", "[quality]\nOE1TBA = poor hidden\nDL1TBB = visible\n"),
                encoding="utf-8")
            b = bed_mod.Bed.load(Path(d))
            self.assertEqual(b.quality, {"OE1TBA": ("poor", True), "DL1TBB": ("", False)})
            self.assertEqual(b.mix, {"good": 0.5, "medium": 0.3, "poor": 0.2})
            # a tbtest.conf of the first version (no [radio]) is renewed, ports kept
            p.write_text("[testbed]\nbox_port = 10393\n[users]\ncalls = OE1TBA, DL1TBB\n",
                         encoding="utf-8")
            b, new = bed_mod.init(Path(d))
            self.assertTrue(new)
            self.assertEqual((b.box_port, len(b.users), b.air_baud), (10393, 30, 1200))

    def test_bad_conf(self):
        with tempfile.TemporaryDirectory() as d:
            bed_mod.init(Path(d))
            p = Path(d) / "tbtest.conf"
            p.write_text(p.read_text(encoding="utf-8").replace("DL1TBB", "OE1TBA-2"),
                         encoding="utf-8")
            with self.assertRaises(bed_mod.BedError):
                bed_mod.Bed.load(Path(d))


class ChannelTests(unittest.TestCase):
    def test_frame_loss_and_profiles(self):
        self.assertAlmostEqual(CH.frame_loss(0.25, 256), 0.25, places=3)
        self.assertLess(CH.frame_loss(0.25, 16), 0.03)        # an RR gets through
        self.assertEqual(CH.frame_loss(0, 256), 0)
        calls = [f"OE1T{c}{c}" for c in "ABCDEFGHIJ"]
        q = CH.assign_profiles(calls, {"good": 0.5, "medium": 0.3, "poor": 0.2}, 0.2,
                               {"OE1TAA": ("poor", False)}, random.Random(1))
        names = [p.name for p, _ in q.values()]
        self.assertEqual(sorted(set(names)), ["good", "medium", "poor"])
        self.assertEqual(q["OE1TAA"], (CH.PROFILES["poor"], False))
        self.assertIn(sum(1 for _, h in q.values() if h), (1, 2))

    def collide(self, hidden: bool) -> int:
        """Two users hand a frame to their TNC at the same moment. Returns how
        many reach the box."""
        from prcore import axudp
        from prcore.ax25 import frame as ax

        async def scenario():
            loop = asyncio.get_running_loop()
            got = []

            class Box(asyncio.DatagramProtocol):
                def datagram_received(self, data, addr):
                    got.append(data)
            box_t, _ = await loop.create_datagram_endpoint(Box, local_addr=("127.0.0.1", 0))
            box_port = box_t.get_extra_info("sockname")[1]
            port = free_ports(1, udp=True)[0]
            ch = CH.Channel(port, air_baud=1200, txdelay_ms=50, persist=255, slottime_ms=20)
            ch.add(CH.Station("OE3TBX-1", ("127.0.0.1", box_port), is_box=True))
            ch.add(CH.Station("OE1TBA", ("127.0.0.1", 9), CH.PROFILES["good"], hidden))
            ch.add(CH.Station("DL1TBB", ("127.0.0.1", 9), CH.PROFILES["good"], False))
            for st in ch.stations.values():
                st.profile = CH.Profile("none", 0.0)
            await ch.start()
            for src in ("OE1TBA", "DL1TBB"):
                f = ax.ui_frame("OE3TBX-1", src, b"x" * 40)
                ch.received(axudp.encode(f.encode()), ("127.0.0.1", 9))
            await asyncio.sleep(1.5)
            ch.close()
            box_t.close()
            return len(got), ch.summary()
        n, summary = asyncio.run(scenario())
        return n

    def test_axudp_hear_mode(self):
        """With air time the endpoint passes on frames of other stations from a peer's
        address (channel busy) - never a frame for its own call from a stranger."""
        from prcore import axudp
        from prcore.ax25 import frame as ax
        got = []
        peers = {"OE3TBX-1": axudp.Peer("OE3TBX-1", "127.0.0.1", 10192)}
        ep = axudp.AxudpEndpoint("127.0.0.1", 0, peers, lambda p, f: got.append(f),
                                 hear="OE1TBA")
        dg = lambda d, s: axudp.encode(ax.ui_frame(d, s, b"hi").encode())   # noqa: E731
        ep.received(dg("OE1TBA", "OE3TBX-1"), ("127.0.0.1", 10192))   # the box to me
        ep.received(dg("OE3TBX-1", "DL1TBB"), ("127.0.0.1", 10192))   # another user: heard
        ep.received(dg("OE1TBA", "DL1TBB"), ("127.0.0.1", 10192))     # stranger to me: no
        ep.received(dg("OE3TBX-1", "DL1TBB"), ("10.0.0.9", 10192))    # other address: no
        self.assertEqual((len(got), ep.heard, ep.dropped["stranger"]), (2, 1, 2))
        plain = axudp.AxudpEndpoint("127.0.0.1", 0, peers, lambda p, f: got.append(f))
        plain.received(dg("OE3TBX-1", "DL1TBB"), ("127.0.0.1", 10192))
        self.assertEqual(plain.dropped["stranger"], 1)               # without air time

    def test_hidden_stations_collide_at_the_box(self):
        self.assertEqual(self.collide(hidden=False), 2)        # carrier sense: one waits
        self.assertEqual(self.collide(hidden=True), 0)         # nobody hears the other


class CliTests(unittest.TestCase):
    def test_parsers(self):
        self.assertEqual(cli.parse_time("90s"), 90)
        self.assertEqual(cli.parse_time("10m"), 600)
        self.assertEqual(cli.parse_time("1h"), 3600)
        self.assertEqual(cli.parse_range("2-10"), (2.0, 10.0))
        self.assertEqual(cli.parse_range("5"), (5.0, 5.0))
        self.assertEqual(cli.parse_funcs("all"), list(cli.FUNCS))
        self.assertEqual(cli.parse_funcs("read,conn"), ["conn", "read"])
        with self.assertRaises(Exception):
            cli.parse_funcs("conn,fly")


class RunTests(unittest.TestCase):
    """One short run: a real test box process, one terminal and one client user."""

    def bed(self, d: str) -> bed_mod.Bed:
        udp = free_ports(5, udp=True)
        tcp = free_ports(4, udp=False)
        bed = bed_mod.Bed(Path(d), box_port=udp[0], channel_port=udp[1], guest_port=udp[2],
                          user_port=udp[3], air_port=tcp[0], web_port=tcp[1],
                          telnet_port=tcp[2], guest_web=tcp[3], users=bed_mod.USERS[:2])
        bed.save()
        return bed_mod.init(Path(d))[0]

    def test_short_run_on_the_simulated_channel(self):
        """9600 Bd so it stays short; good quality for both, nobody hidden."""
        with tempfile.TemporaryDirectory() as d:
            bed = self.bed(d)
            bed.hidden, bed.mix = 0.0, {"good": 1.0}
            opt = Options(users=2, terminals=1, duration=120, rounds=3, think=(0.2, 0.5),
                          chat_stay=(3.0, 4.0), seed=3, timeout=60, air=9600,
                          funcs=["send", "read", "chat"])
            result = asyncio.run(Run(bed, opt, bed.runs / "r", quiet=True).run())
            text = report.text(result)
            self.assertEqual(report.failures(result), [], text)
            ch = result["channel"]
            self.assertEqual(ch["air_baud"], 9600)
            self.assertGreater(ch["busy_pct"], 0)
            self.assertIn("Simulated channel:", text)
            box = next(r for r in ch["stations"] if r["box"])
            self.assertGreater(box["frames"], 0)

    def test_short_run_passes(self):
        with tempfile.TemporaryDirectory() as d:
            bed = self.bed(d)
            opt = Options(users=2, terminals=1, duration=60, rounds=6, think=(0.1, 0.4),
                          chat_stay=(2.0, 3.0), seed=7, timeout=20, air=0)
            run = Run(bed, opt, bed.runs / "t", quiet=True)
            result = asyncio.run(run.run())
            text = report.text(result)
            self.assertEqual(report.failures(result), [], text)
            self.assertIn("RESULT: PASSED", text)
            self.assertEqual(result["air"]["not_ui"], 0)
            self.assertTrue((bed.runs / "t" / "result.json").is_file())
            self.assertTrue((bed.runs / "t" / "tinybox.out").is_file())


if __name__ == "__main__":
    unittest.main()
