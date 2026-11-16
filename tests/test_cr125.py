"""CR125: up to 5 sysops, all equal - mail to SYSOP, every sysop reads it."""

from __future__ import annotations

import configparser
import tempfile
import unittest
from pathlib import Path

from tinybox import config
from tinybox.adapters.sysop import SysopConsole
from tinybox.adapters.sysop import MonitorFilter
from tinybox.service import ServiceError
from tests.test_tinybox import ROOT, login, make_app, type_lines


def load_with(sysops: str) -> config.Config:
    cp = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
    cp.read(ROOT / "tinybox.conf.example", encoding="utf-8")
    cp.set("station", "sysop_call", sysops)
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "tinybox.conf"
        with p.open("w", encoding="utf-8") as f:
            cp.write(f)
        return config.load(p)


class ConfigTests(unittest.TestCase):
    def test_list_comma_or_space_doubles_once(self):
        st = load_with("oe3gas, OE3TEC-7 oe1abc OE3GAS-2").station
        self.assertEqual(st.sysops, ("OE3GAS", "OE3TEC-7", "OE1ABC"))
        self.assertEqual(st.sysop_text, "OE3GAS, OE3TEC-7, OE1ABC")
        self.assertEqual(load_with("OE3GAS").station.sysops, ("OE3GAS",))

    def test_at_most_five_and_only_calls(self):
        with self.assertRaisesRegex(config.ConfigError, "at most 5"):
            load_with("OE1AAA OE1BBB OE1CCC OE1DDD OE1EEE OE1FFF")
        with self.assertRaisesRegex(config.ConfigError, "'SYSOP' is not a valid callsign"):
            load_with("OE3GAS, SYSOP")
        with self.assertRaisesRegex(config.ConfigError, "sysop_call is missing"):
            load_with(" ")


class TwoSysops(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.app.cfg.station.sysop_call = "OE3GAS, OE3TEC"
        self.svc = self.app.service

    def test_every_listed_call_is_sysop_and_sysop_itself(self):
        for call in ("OE3GAS", "OE3TEC-9", "SYSOP"):
            self.assertTrue(self.svc.is_sysop_call(call), call)
        self.assertFalse(self.svc.is_sysop_call("OE1ABC"))
        with self.assertRaises(ServiceError):
            self.svc.ban("OE3TEC-3")

    def test_mail_to_sysop_is_one_mailbox_for_all(self):
        s, t = login(self.app, "OE1ABC-5")
        type_lines(s, "S SYSOP", "Hallo", "Text", "/EX")
        m = [m for m in self.app.store.list_messages() if m.to_call == "SYSOP"]
        self.assertEqual(len(m), 1)
        msg_id = m[0].id
        for call in ("OE3GAS", "OE3TEC-2"):
            self.assertIn(msg_id, [x.id for x in self.svc.unread_for(call)], call)
            self.assertIn(msg_id, [x.id for x in self.svc.list_for(call, False, mine=True)])
        self.assertNotIn(msg_id, [x.id for x in self.svc.list_for("OE1XYZ", False)])
        self.svc.read(msg_id, "OE3TEC", False)               # one reads it ...
        self.assertEqual(self.svc.unread_for("OE3GAS"), [])  # ... read for all

    def test_sysop_is_local_no_at(self):
        with self.assertRaises(ServiceError):
            self.svc.create(from_call="OE1ABC", to_call="SYSOP", type="P", subject="x",
                            body="y", origin="telnet", at_addr="OE3XTC.#NOE.AUT.EU")

    def test_system_mail_goes_to_sysop(self):
        self.svc.sysop_call_on_air("OE3TEC-1", "radio")
        mails = [m for m in self.app.store.list_messages() if m.type == "P"]
        self.assertEqual([m.to_call for m in mails], ["SYSOP"])
        self.assertEqual(len(self.svc.unread_for("OE3TEC")), 1)

    def test_local_sysop_writes_as_the_box_admin_as_himself(self):
        out: list[str] = []
        console = SysopConsole(self.app, MonitorFilter(False), out.append)
        self.assertEqual(console.by, "SYSOP")
        mid = self.svc.create(from_call="SYSOP", to_call="ALL", type="B", subject="s",
                              body="b", origin="sysop", sysop=True)
        self.assertEqual(self.app.store.get(mid).from_call,
                         self.app.cfg.station.bbs_call)          # a real call as author
        adm = SysopConsole(self.app, MonitorFilter(False), out.append, by="OE3TEC")
        self.assertEqual((adm.by, adm.session.call), ("OE3TEC", "OE3TEC"))


if __name__ == "__main__":
    unittest.main()
