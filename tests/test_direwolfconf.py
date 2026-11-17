"""CR70: values from direwolf.conf (prcore.direwolfconf)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from prcore import direwolfconf as dwc

SAMPLE = """\
# Direwolf on PC2
ADEVICE  plughw:1,0
ACHANNELS 1
CHANNEL 0
MYCALL OE3GAS-10
MODEM 1200        # AFSK
TXDELAY 30
PERSIST 63
SLOTTIME 10
AGWPORT 8000
KISSPORT 8001
paclen 128
MAXFRAME 4
EMAXFRAME 7
FRACK 4
RETRY 10
ADEVICE1 plughw:2,0
MODEM 9600
TXDELAY 15
"""


class DirewolfConfTests(unittest.TestCase):
    def test_parse(self):
        dw = dwc.parse(SAMPLE)
        self.assertEqual((dw.agw_port, dw.kiss_port), (8000, 8001))
        self.assertEqual((dw.paclen, dw.maxframe, dw.emaxframe, dw.frack_sec, dw.retry),
                         (128, 4, 7, 4, 10))
        c0 = dw.channel(0)
        self.assertEqual((c0.baud, c0.txdelay_ms, c0.persist, c0.slottime_ms),
                         (1200, 300, 63, 100))
        c2 = dw.channel(2)                       # ADEVICE1 -> channels 2, 3
        self.assertEqual((c2.baud, c2.txdelay_ms), (9600, 150))
        self.assertIsNone(dw.channel(5).baud)
        self.assertIn("MODEM 1200", dw.describe())

    def test_folder_or_file(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "direwolf.conf").write_text("KISSPORT 9001\n", encoding="utf-8")
            self.assertEqual(dwc.read(d).kiss_port, 9001)
            self.assertEqual(dwc.read(Path(d) / "direwolf.conf").kiss_port, 9001)
            self.assertEqual(dwc.read(f'"{d}"').kiss_port, 9001)
            with self.assertRaises(dwc.DirewolfConfError):
                dwc.read(Path(d) / "nothing.conf")

    def test_audio_and_ptt(self):
        """CR140: ADEVICE (in, out) per radio and PTT per channel, as written."""
        dw = dwc.parse('ADEVICE "Microham USB" "Line 2 (VAC)"\nCHANNEL 0\nPTT COM20 RTS\n'
                       'ADEVICE1 plughw:2,0  # one name: in and out\nPTT GPIO 25\n')
        self.assertEqual(dw.audio(0), ("Microham USB", "Line 2 (VAC)"))
        self.assertEqual(dw.audio(1), ("Microham USB", "Line 2 (VAC)"))
        self.assertEqual(dw.audio(2), ("plughw:2,0", "plughw:2,0"))
        self.assertIsNone(dw.audio(4))
        self.assertEqual((dw.channel(0).ptt, dw.channel(2).ptt), ("COM20 RTS", "GPIO 25"))
        self.assertIsNone(dwc.parse("MODEM 1200\n").channel(0).ptt)

    def test_empty(self):
        dw = dwc.parse("# nothing\n\n")
        self.assertIsNone(dw.agw_port)
        self.assertIn("no values found", dw.describe())


if __name__ == "__main__":
    unittest.main()
