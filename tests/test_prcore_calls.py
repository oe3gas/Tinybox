"""prcore/calls.py: one place for normalizing and checking callsigns (Refactoring R6)."""

from __future__ import annotations

import unittest

from prcore import calls


class Normalize(unittest.TestCase):
    def test_normalize_call(self):
        self.assertEqual(calls.normalize_call(" oe3gas-1 "), "OE3GAS-1")
        self.assertEqual(calls.normalize_call(None), "")

    def test_norm_call_drops_ssid_0(self):
        self.assertEqual(calls.norm_call("oe3gas-0 "), "OE3GAS")
        self.assertEqual(calls.norm_call("OE3GAS-10"), "OE3GAS-10")

    def test_base_call(self):
        for call in ("OE3GAS", "oe3gas", " OE3GAS-1", "oe3gas-15"):
            self.assertEqual(calls.base_call(call), "OE3GAS", call)
        self.assertEqual(calls.base_call(None), "")

    def test_base_call_is_case_blind(self):
        """Before R6, tinybox.config.base_call kept the case - sysop, keys and bans
        compare base calls, so 'oe3gas' and 'OE3GAS' must be the same station."""
        self.assertEqual(calls.base_call("oe3gas-2"), calls.base_call("OE3GAS"))


class Checks(unittest.TestCase):
    def test_ax25_call(self):
        for ok in ("OE3GAS", "OE3GAS-15", "BEACON", "APRS", "A", "ID-0"):
            self.assertTrue(calls.is_ax25_call(ok), ok)
        for bad in ("", "OE3GAS-16", "TOOLONG1", "OE3GAS-", "oe3gas", "OE3GÄS", "OE3GAS\n",
                    "OE3GAS-00"):
            self.assertFalse(calls.is_ax25_call(bad), repr(bad))

    def test_valid_call(self):
        for ok in ("OE3GAS", "OE3GAS-1", "K1A", "4X1AB-15"):
            self.assertTrue(calls.is_valid_call(ok), ok)
        for bad in ("BEACON", "123456", "OE", "OE3GAS-16", "OE3GAS\n", "oe3gas"):
            self.assertFalse(calls.is_valid_call(bad), repr(bad))

    def test_base_call_re(self):
        self.assertTrue(calls.BASE_CALL_RE.match("OE3GAS"))
        self.assertFalse(calls.BASE_CALL_RE.match("OE3GAS-1"))

    def test_plausible_call(self):
        for ok in ("OE3GAS", "dl1abc-7", "4X1AB", "2E0ABC", "3DA0RU", "K1A"):
            self.assertTrue(calls.plausible_call(ok), ok)
        for bad in ("ABCDEF", "QST", "123456", "70CM", "QO100", "10M"):
            self.assertFalse(calls.plausible_call(bad), bad)


if __name__ == "__main__":
    unittest.main()
