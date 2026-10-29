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
            self.assertEqual(set(cfg.axudp.peers), set(bed_mod.USERS))
            self.assertEqual(cfg.axudp.peers["DL1TBB"].port, bed.user_port + 1)
            self.assertGreaterEqual(cfg.mailbox.max_users, 10)
            self.assertFalse(cfg.update.check)
            self.assertFalse(cfg.brocast.publish)
            bed.check_box_conf()
            # tbtest.conf edited: tinybox.conf no longer fits until init again
            text = bed.conf_path.read_text(encoding="utf-8").replace("10193", "10293")
            bed.conf_path.write_text(text, encoding="utf-8")
            with self.assertRaises(bed_mod.BedError):
                bed_mod.Bed.load(Path(d)).check_box_conf()
            bed2, new = bed_mod.init(Path(d))
            self.assertFalse(new)                  # the edited tbtest.conf is kept
            self.assertEqual(bed2.box_port, 10293)
            bed2.check_box_conf()

    def test_bad_conf(self):
        with tempfile.TemporaryDirectory() as d:
            bed_mod.init(Path(d))
            p = Path(d) / "tbtest.conf"
            p.write_text(p.read_text(encoding="utf-8").replace("DL1TBB", "OE1TBA-2"),
                         encoding="utf-8")
            with self.assertRaises(bed_mod.BedError):
                bed_mod.Bed.load(Path(d))


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

    def test_short_run_passes(self):
        udp = free_ports(3, udp=True)
        tcp = free_ports(3, udp=False)
        with tempfile.TemporaryDirectory() as d:
            bed = bed_mod.Bed(Path(d), box_port=udp[0], user_port=udp[1], air_port=tcp[0],
                              web_port=tcp[1], telnet_port=tcp[2],
                              users=bed_mod.USERS[:2])
            bed.save()
            bed, _ = bed_mod.init(Path(d))
            opt = Options(users=2, terminals=1, duration=60, rounds=6, think=(0.1, 0.4),
                          chat_stay=(2.0, 3.0), seed=7, timeout=20)
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
