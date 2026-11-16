"""Refactoring R5 (prepares CR125): the code never takes [station] sysop_call itself,
but one of the four views of StationCfg - sysops, sysop_mail_to, local_sysop, sysop_text."""

from __future__ import annotations

import unittest

from tests.test_tinybox import make_app


class SysopViews(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.st = self.app.cfg.station

    def test_one_sysop_mail_and_local_go_to_sysop(self):
        call = self.st.sysop_call
        self.assertEqual(self.st.sysops, (call,))
        self.assertEqual((self.st.sysop_mail_to, self.st.local_sysop, self.st.sysop_text),
                         ("SYSOP", "SYSOP", call))     # CR125

    def test_every_ssid_of_the_sysop_is_sysop(self):
        base = self.st.sysop_call.split("-")[0]
        svc = self.app.service
        for call in (base, f"{base}-1", f"{base.lower()}-15"):
            self.assertTrue(svc.is_sysop_call(call), call)
        self.assertFalse(svc.is_sysop_call("OE9ZZZ"))

    def test_s_sysop_goes_to_the_sysop_mail_address(self):
        svc = self.app.service
        self.assertEqual(svc.check_send("OE3ABC", "SYSOP", "P", False),
                         self.st.sysop_mail_to.split("-")[0])


if __name__ == "__main__":
    unittest.main()
