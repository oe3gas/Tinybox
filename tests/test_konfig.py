"""release/konfig.py: the values there today are the defaults; Enter keeps everything."""

import builtins
import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SRC = Path(__file__).resolve().parent.parent


def load_konfig(root: Path):
    spec = importlib.util.spec_from_file_location("konfig_under_test", SRC / "release" / "konfig.py")
    k = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(k)
    k.ROOT, k.DW_DIR, k.START_CONF = root, root / "direwolf", root / "tbstart.conf"
    k.KISS_EXAMPLE, k.KISS_CONF = root / "kisshub.conf.example", root / "kisshub.conf"
    return k


class KonfigDefaults(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)
        for f in ("tbclient.conf.example", "tinybox.conf.example", "kisshub.conf.example"):
            shutil.copy(SRC / f, self.d / f)
        self.dw = self.d / "dw"
        self.dw.mkdir()
        (self.dw / "direwolf.exe").write_text("x")
        (self.dw / "direwolf.conf").write_text("ADEVICE USB\nMYCALL OE3GAS\nMODEM 9600\n"
                                               "PTT COM5 RTS\nAGWPORT 8000\n")
        box = (SRC / "tinybox.conf.example").read_text(encoding="utf-8")
        box = box.replace("qth          =  ", "qth          = Hollabrunn", 1)
        (self.d / "tinybox.conf").write_text(box + "\n[chat_boards]\nmeinboard = Test\n",
                                             encoding="utf-8")
        cli = (SRC / "tbclient.conf.example").read_text(encoding="utf-8")
        cli = cli.replace("mycall       = OE3GAS  ", "mycall       = OE3GAS-12", 1)
        cli = cli.replace("locator      =         ", "locator      = JN88EP  ", 1)
        cli = cli.replace("# direwolf_conf = C:\\direwolf ", f"direwolf_conf = {self.dw}", 1)
        (self.d / "tbclient.conf").write_text(cli, encoding="utf-8")
        (self.d / "tbstart.conf").write_text(
            f"# meins\n[start]\ndirewolf = yes\ndirewolf_dir = {self.dw}\n"
            "direwolf_exe = direwolf.exe\ntinybox = yes\nbrocast = no\ntbclient = no\n"
            "dxfeed = yes\n", encoding="utf-8")

    def run_dialog(self, *answers):
        it = iter(answers)
        prompts = []

        def fake_input(prompt=""):
            prompts.append(prompt)
            return next(it, "")
        k = load_konfig(self.d)
        with mock.patch.object(builtins, "input", fake_input), \
                mock.patch.object(builtins, "print"):
            k.main()
        return prompts

    def test_enter_everywhere_offers_and_keeps_todays_values(self):
        prompts = "\n".join(self.run_dialog())
        for shown in ("Rufzeichen (ohne SSID) [OE3GAS]", "Locator (leer = keiner) [JN88EP]",
                      "[Hollabrunn]", "TinyBox (Mailbox) betreiben? (j/n) [j]",
                      "Clients mit SSID [OE3GAS-12]", f"Ordner deines Direwolf [{self.dw}]"):
            self.assertIn(shown, prompts)
        box = (self.d / "tinybox.conf").read_text(encoding="utf-8")
        self.assertIn("meinboard = Test", box, "own settings stay")
        self.assertIn("qth          = Hollabrunn", box)
        cli = (self.d / "tbclient.conf").read_text(encoding="utf-8")
        self.assertIn("mycall       = OE3GAS-12", cli)
        start = (self.d / "tbstart.conf").read_text(encoding="utf-8")
        self.assertIn("dxfeed = yes", start)
        self.assertIn("tbclient = no", start)
        self.assertIn("# meins", start)
        self.assertIn("MODEM 9600", (self.dw / "direwolf.conf").read_text())

    def test_dash_empties_an_optional_value(self):
        self.run_dialog("", "-")
        cli = (self.d / "tbclient.conf").read_text(encoding="utf-8")
        self.assertRegex(cli, r"(?m)^locator\s*=\s*#")


if __name__ == "__main__":
    unittest.main()
