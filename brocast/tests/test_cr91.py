"""CR91 (audit TB-04): a new dictionary may only add - it must not change what an
existing number means - and one installed without a person is not sent on."""

from __future__ import annotations

import copy
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from brocast import dictimport, dicttransfer, frame
from brocast.daemon import DICT_DATA, Daemon
from brocast.dictionary import Dictionary
from tests.test_daemon import T0, Clock, make_cfg
from tests.test_dictimport import BASE, v2 as v2_data
from tests.test_dicttransfer import V1, v2

PARTNER = "OE1ABC-5"


def changed(edit) -> Dictionary:
    data = v2_data()
    edit(data)
    return Dictionary(data)


class Check(unittest.TestCase):
    def assertRejected(self, edit, pattern="umgedeutet"):
        with self.assertRaisesRegex(dictimport.ImportError_, pattern):
            dictimport.check(BASE, changed(edit))

    def test_reinterpretations_rejected(self):
        wx = BASE.types["wx"]
        temp = next(n for n, e in wx.by_num.items() if e.name == "temp")
        scaled = next(n for n, e in wx.by_num.items() if "scale" in e.spec)
        unit = next(n for n, e in wx.by_num.items() if "unit" in e.spec)
        other_unit = next(e.name for e in BASE.enums["unit"].by_num.values()
                          if e.name != wx.by_num[unit].spec["unit"])
        cases = {
            "scale": lambda d: d["types"]["wx"][scaled].__setitem__("scale", 100),
            "unit": lambda d: d["types"]["wx"][unit].__setitem__("unit", other_unit),
            "type": lambda d: d["types"]["wx"][temp].__setitem__("type", "tstr"),
            "exp": lambda d: next(e for e in d["enums"]["typ"].values() if "exp" in e)
            .__setitem__("exp", 1),
            "envelope max": lambda d: next(e for e in d["envelope"].values() if "max" in e)
            .__setitem__("max", 5000),
            "new key": lambda d: d["types"]["wx"][temp].__setitem__("scale", 7),
        }
        for name, edit in cases.items():
            with self.subTest(name):
                self.assertRejected(edit)

    def test_allowed_changes(self):
        def texts(d):
            for e in d["types"]["wx"].values():
                e["de"] = e.get("de", "") + " (neu formuliert)"
                e["en"] = "new wording"
        self.assertIn("Liste cat", dictimport.check(BASE, changed(texts)))

    def test_shipped_history_is_accepted(self):
        """v1 -> the shipped version: src was 'any' and got its type (allowed)."""
        dictimport.check(Dictionary.load(V1), v2())

    def test_dxcc_may_be_marked_deleted(self):
        old = Dictionary.load()
        data = copy.deepcopy(old.raw)
        data["version"] = old.version + 1
        num, entry = next((n, e) for n, e in data["enums"]["dxcc"].items() if not e.get("del"))
        entry["del"] = True
        dictimport.check(old, Dictionary(data))
        entry["del"] = False
        undo = Dictionary(copy.deepcopy(data))
        data["enums"]["dxcc"][num]["del"] = True
        with self.assertRaisesRegex(dictimport.ImportError_, "umgedeutet"):
            dictimport.check(Dictionary(data), undo)            # deleted stays deleted


class NotSentOn(unittest.TestCase):
    """A station receives v2 from a trusted station: installed, but not relayed."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        path = Path(self.tmp.name) / "brocast-core.yaml"
        shutil.copy(V1, path)
        cfg = make_cfg("station", "OE3GAS-5", dict_broadcast_hours=6)
        cfg.dictionary = path
        self.d = Daemon(cfg, clock=Clock(), db_path=":memory:")
        self.d.listener.set_settings({"dict_trusted": [PARTNER]})

    def data_page(self):
        row = self.d.store.get_page(*DICT_DATA)
        return row is not None and row.state == "active"

    def receive(self):
        for f in dicttransfer.build_frames(v2(), 25, 0, T0):
            self.d.on_frame(0, frame.build(PARTNER, f))

    def test_auto_installed_is_held(self):
        self.receive()
        self.assertEqual(self.d.codec.d.hash4, v2().hash4)          # installed
        self.assertTrue(self.d.listener.dictionary_status()["relay_held"])
        self.d.broadcast_dictionary()
        self.assertFalse(self.data_page())                          # not sent on

    def test_sysop_button_releases(self):
        self.receive()
        self.d.carousel = mock.Mock()
        res = self.d.broadcast_dictionary_now()
        self.assertTrue(res["ok"], res)
        self.assertTrue(self.data_page())
        self.assertFalse(self.d.listener.dictionary_status()["relay_held"])

    def test_released_by_hand_is_sent_on(self):
        self.d.listener.set_settings({"dict_trusted": []})
        self.receive()                                              # waits for release
        self.d.listener.install_ready_dictionary()
        self.assertFalse(self.d.listener.dictionary_status()["relay_held"])
        self.assertTrue(self.data_page())


if __name__ == "__main__":
    unittest.main()
