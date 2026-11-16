"""prcore/conf.py: declared config sections and the shared ConfigError (Refactoring R7)."""

from __future__ import annotations

import configparser
import unittest
from dataclasses import dataclass

from prcore import conf
from tinybox import config, reload


@dataclass
class Demo:
    on: bool = conf.setting(True, live=True)
    n: int = conf.setting(3, lo=1, hi=5)
    ratio: float = conf.setting(0.5, key="share")
    name: str = conf.setting("x", check=lambda v: None if v.isalpha() else "letters only")


def cp(text: str) -> configparser.ConfigParser:
    c = configparser.ConfigParser()
    c.read_string(text)
    return c


class DeclaredSections(unittest.TestCase):
    def test_defaults_and_values(self):
        self.assertEqual(conf.load_section(cp("[d]\n"), "d", Demo), Demo())
        d = conf.load_section(cp("[d]\non = no\nn = 5\nshare = 0.25\nname = abc\n"), "d", Demo)
        self.assertEqual((d.on, d.n, d.ratio, d.name), (False, 5, 0.25, "abc"))

    def test_errors_name_section_and_key(self):
        for text, msg in (("n = 9", r"\[d\] n: 9 must be between 1 and 5"),
                          ("n = x", r"\[d\] n: "),
                          ("name = a1", r"\[d\] name: letters only")):
            with self.assertRaisesRegex(conf.ConfigError, msg):
                conf.load_section(cp("[d]\n" + text + "\n"), "d", Demo)

    def test_live_and_declared(self):
        self.assertEqual(conf.live_fields(Demo), {"on"})
        self.assertEqual(conf.declared(Demo)[2], ("share", 0.5, None, None, False))

    def test_one_error_class_everywhere(self):
        from tbclient import config as ccfg
        from kisshub import config as kcfg
        from dxfeed import config as dcfg
        self.assertIs(config.ConfigError, conf.ConfigError)
        self.assertIs(ccfg.ConfigError, conf.ConfigError)
        self.assertIs(kcfg.ConfigError, conf.ConfigError)
        self.assertIs(dcfg.ConfigError, conf.ConfigError)

    def test_tinybox_mailbox_is_declared_and_live(self):
        self.assertEqual(reload.LIVE["mailbox"],
                         {f for f in config.MailboxCfg.__dataclass_fields__})
        with self.assertRaisesRegex(config.ConfigError, r"\[telnet\] port: 0 is not a valid TCP port"):
            conf.load_section(cp("[telnet]\nport = 0\n"), "telnet", config.TelnetCfg)


if __name__ == "__main__":
    unittest.main()


class ClientConfigNumbersTests(unittest.TestCase):
    """R7: a typo in a number of tbclient.conf is a ConfigError naming the key."""

    def load(self, text: str):
        import tempfile
        from pathlib import Path
        from tbclient import config as ccfg
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "tbclient.conf"
            p.write_text("[station]\nmycall = OE3GAS\n" + text, encoding="utf-8")
            return ccfg.load(p)

    def test_typo_names_the_key(self):
        from tbclient.config import ConfigError
        with self.assertRaisesRegex(ConfigError, r"\[web\] port: '77x4' is not a number"):
            self.load("[web]\nport = 77x4\n")
        with self.assertRaisesRegex(ConfigError, "not a number"):
            self.load("[agw]\nport = abc\n")
        self.assertEqual(self.load("[web]\nport = 7755\n").web_port, 7755)
