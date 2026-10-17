"""AX.25 v2.2 frame codec (KISS step K1, docs/kiss-mode-konzept.md)."""

from __future__ import annotations

import random
import unittest

from prcore.ax25 import frame as ax
from prcore.ax25.frame import AX25Error, Frame

ME, YOU = "OE3GAS-1", "OE3ABC"

# addresses worked out by hand from the spec (character << 1, SSID byte 0x60 | ...)
DEST_CMD = bytes((0x9E, 0x8A, 0x66, 0x8E, 0x82, 0xA6, 0xE2))   # OE3GAS-1, C=1
SRC_CMD_LAST = bytes((0x9E, 0x8A, 0x66, 0x82, 0x84, 0x86, 0x61))  # OE3ABC, C=0, last


class AddressTests(unittest.TestCase):
    def test_encode_by_hand(self):
        self.assertEqual(ax.encode_address(ME, last=False, high_bit=True), DEST_CMD)
        self.assertEqual(ax.encode_address(YOU, last=True, high_bit=False), SRC_CMD_LAST)

    def test_decode(self):
        self.assertEqual(ax.decode_address(DEST_CMD), (ME, True, False))
        self.assertEqual(ax.decode_address(SRC_CMD_LAST), (YOU, False, True))

    def test_ssid_range_and_bad_calls(self):
        self.assertEqual(ax.split_call("oe3gas-15"), ("OE3GAS", 15))
        for bad in ("OE3GAS-16", "TOOLONGX", "", "OE3-GAS-1", "OE3GÄS", "OE3GAS-x"):
            with self.assertRaises(AX25Error, msg=bad):
                ax.encode_address(bad, last=True, high_bit=False)


class EncodeByHandTests(unittest.TestCase):
    """Complete frames against bytes worked out by hand - not just round trips."""

    def test_sabm_with_poll(self):
        f = ax.u_frame("SABM", ME, YOU, pf=True)
        self.assertEqual(f.encode(), DEST_CMD + SRC_CMD_LAST + bytes((0x3F,)))

    def test_i_frame_modulo_8(self):
        f = ax.i_frame(ME, YOU, ns=2, nr=5, info=b"hi")
        self.assertEqual(f.encode(), DEST_CMD + SRC_CMD_LAST + bytes((0xA4, 0xF0)) + b"hi")

    def test_i_frame_modulo_128(self):
        f = ax.i_frame(ME, YOU, ns=100, nr=127, info=b"x", poll=True, modulo=128)
        self.assertEqual(f.encode()[14:], bytes((0xC8, 0xFF, 0xF0)) + b"x")

    def test_s_frames(self):
        rej = ax.s_frame("REJ", ME, YOU, nr=7, pf=True)              # response, F
        self.assertEqual(rej.encode()[14:], bytes((0xF9,)))
        rr = ax.s_frame("RR", ME, YOU, nr=3, pf=True, modulo=128)
        self.assertEqual(rr.encode()[14:], bytes((0x01, 0x07)))
        srej = ax.s_frame("SREJ", ME, YOU, nr=64, modulo=128)
        self.assertEqual(srej.encode()[14:], bytes((0x0D, 0x80)))

    def test_response_bits(self):
        raw = ax.u_frame("UA", ME, YOU, command=False, pf=True).encode()
        self.assertEqual(raw[6] & 0x80, 0)          # destination C = 0
        self.assertEqual(raw[13] & 0x80, 0x80)      # source C = 1
        self.assertEqual(raw[14], 0x73)             # UA with F

    def test_all_u_codes(self):
        expected = {"SABME": 0x6F, "SABM": 0x2F, "DISC": 0x43, "DM": 0x0F, "UA": 0x63,
                    "FRMR": 0x87, "UI": 0x03, "XID": 0xAF, "TEST": 0xE3}
        for kind, code in expected.items():
            raw = Frame(kind, ME, YOU).encode()
            self.assertEqual(raw[14], code, kind)

    def test_digipeater_path(self):
        f = ax.ui_frame("TBCHAT-1", ME, b"x", path=["OE3XWR", "WIDE2-1"])
        f.repeated = [True, False]
        raw = f.encode()
        self.assertEqual(len(raw), 7 * 4 + 2 + 1)
        self.assertEqual(raw[13] & 0x01, 0)          # source is not last any more
        self.assertEqual(raw[20] & 0x81, 0x80)       # first digi: H set, not last
        self.assertEqual(raw[27] & 0x81, 0x01)       # second digi: H clear, last


class RoundTripTests(unittest.TestCase):
    def assertRoundTrip(self, f: Frame) -> Frame:
        back = Frame.decode(f.encode(), modulo=f.modulo)
        for name in ("kind", "dest", "src", "command", "pf", "info", "path"):
            self.assertEqual(getattr(back, name), getattr(f, name), f"{f.kind}.{name}")
        if f.is_i:
            self.assertEqual((back.ns, back.nr, back.pid), (f.ns, f.nr, f.pid))
        if f.is_s:
            self.assertEqual(back.nr, f.nr)
        return back

    def test_every_kind_both_modulos_both_pf(self):
        for modulo in (8, 128):
            for pf in (False, True):
                for cmd in (True, False):
                    for seq in (0, modulo - 1, modulo // 2 + 1):
                        self.assertRoundTrip(ax.i_frame(ME, YOU, seq, modulo - 1 - seq,
                                                        b"\x00\xc0\xdb data",
                                                        poll=pf, modulo=modulo))
                        for kind in ax.S_CODES:
                            self.assertRoundTrip(ax.s_frame(kind, ME, YOU, seq, command=cmd,
                                                            pf=pf, modulo=modulo))
                    for kind in ax.U_CODES:
                        info = b"payload" if kind in ax.WITH_INFO else b""
                        f = ax.u_frame(kind, ME, YOU, command=cmd, pf=pf, info=info)
                        f.modulo = modulo
                        self.assertRoundTrip(f)

    def test_eight_digipeaters(self):
        digis = [f"DIGI{i}" for i in range(8)]
        f = ax.i_frame(ME, YOU, 1, 2, b"x", path=digis)
        f.repeated = [True] * 8
        back = self.assertRoundTrip(f)
        self.assertEqual(back.repeated, [True] * 8)
        self.assertTrue(back.fully_repeated)
        self.assertEqual(back.reply_path(), list(reversed(digis)))

    def test_not_yet_repeated(self):
        f = ax.u_frame("SABM", ME, YOU, path=["OE3XWR"])
        back = Frame.decode(f.encode())
        self.assertFalse(back.fully_repeated)

    def test_v1_frame_has_no_command_flag(self):
        raw = bytearray(ax.u_frame("UI", ME, YOU).encode() + b"")
        raw[13] |= 0x80                     # both C bits set = old v1 frame
        self.assertIsNone(Frame.decode(bytes(raw)).command)

    def test_pid_kept(self):
        f = ax.ui_frame("APRS", YOU, b"!4830.00N/01600.00E-", pid=0xCF)
        self.assertEqual(Frame.decode(f.encode()).pid, 0xCF)

    def test_same_bytes_differ_by_modulo(self):
        """The link state decides: the same I frame bytes read differently."""
        raw = ax.i_frame(ME, YOU, 3, 4, b"ab", modulo=128).encode()
        m128 = Frame.decode(raw, modulo=128)
        self.assertEqual((m128.ns, m128.nr, m128.info), (3, 4, b"ab"))
        m8 = Frame.decode(raw, modulo=8)
        self.assertEqual(m8.kind, "I")
        self.assertNotEqual(m8.info, b"ab")


class InvalidTests(unittest.TestCase):
    def test_encode_rejects(self):
        cases = [
            ax.i_frame(ME, YOU, 8, 0, b""),                          # ns too big (mod 8)
            ax.i_frame(ME, YOU, 0, 128, b"", modulo=128),            # nr too big
            ax.u_frame("SABM", ME, YOU, info=b"x"),                  # SABM with info
            ax.ui_frame(ME, YOU, b"", path=[f"D{i}" for i in range(9)]),
            Frame("XXX", ME, YOU),
            Frame("UI", ME, YOU, command=None),
            Frame("I", ME, YOU, modulo=16),
        ]
        for f in cases:
            with self.assertRaises(AX25Error, msg=str(f.kind)):
                f.encode()

    def test_decode_rejects(self):
        good = ax.u_frame("SABM", ME, YOU).encode()
        cases = [
            b"",
            good[:14],                                         # no control field
            good[:10],
            DEST_CMD + DEST_CMD + DEST_CMD,                    # never a last address
            good + b"x",                                       # SABM with info
            DEST_CMD + SRC_CMD_LAST + bytes((0x27,)),          # unknown U code
            ax.ui_frame(ME, YOU, b"").encode()[:15],           # UI without PID
            DEST_CMD + SRC_CMD_LAST + bytes((0x01,)),          # mod 128 S, 2nd byte missing
        ]
        for i, raw in enumerate(cases):
            with self.assertRaises(AX25Error, msg=f"case {i}"):
                Frame.decode(raw, modulo=128 if i == 7 else 8)

    def test_random_garbage_never_crashes(self):
        """Frames from the air are untrusted: only AX25Error, never anything else."""
        rnd = random.Random(4711)
        good = [ax.i_frame(ME, YOU, 1, 2, b"hello", path=["OE3XWR"]).encode(),
                ax.u_frame("SABME", ME, YOU).encode()]
        for _ in range(5000):
            if rnd.random() < 0.5:
                raw = bytes(rnd.randrange(256) for _ in range(rnd.randrange(40)))
            else:
                raw = bytearray(rnd.choice(good))
                for _ in range(rnd.randrange(1, 4)):
                    raw[rnd.randrange(len(raw))] = rnd.randrange(256)
                raw = bytes(raw[:rnd.randrange(len(raw) + 1)])
            for modulo in (8, 128):
                try:
                    Frame.decode(raw, modulo)
                except AX25Error:
                    pass


class TextTests(unittest.TestCase):
    def test_monitor_line(self):
        f = ax.i_frame(ME, YOU, 2, 5, b"hello", poll=True, path=["OE3XWR"])
        f.repeated = [True]
        self.assertEqual(str(f), "OE3ABC>OE3GAS-1,OE3XWR*: I s=2 r=5 P C len=5")


if __name__ == "__main__":
    unittest.main()
