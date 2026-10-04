"""Dictionary over the air: packed parts, collecting, checks, trust, install."""

from __future__ import annotations

import copy
import shutil
import tempfile
import unittest
import zlib
from pathlib import Path

import cbor2

from brocast import dicttransfer, frame
from brocast.daemon import DICT_DATA, Daemon
from brocast.dictionary import Dictionary
from brocast.listener import ListenerError
from tests.test_daemon import T0, Clock, make_cfg

HERE = Path(__file__).resolve().parent
V1 = HERE / "data" / "brocast-core-v1.yaml"
ST = "OE3GAS-5"


def v2() -> Dictionary:
    return Dictionary.load()                     # the shipped dictionary (version >= 2)


class BuildTests(unittest.TestCase):
    def test_frames_fit_and_reassemble(self):
        d = v2()
        frames = dicttransfer.build_frames(d, 25, 0, T0)
        self.assertLess(len(frames), 20)          # ~15 instead of ~50 as text
        self.assertTrue(all(len(f) <= 240 for f in frames))
        parts = [dicttransfer.part_of(cbor2_page(f)) for f in frames]
        self.assertEqual([p["n"] for p in parts], list(range(1, len(frames) + 1)))
        new = dicttransfer.assemble([p["chunk"] for p in parts], parts[0]["zlen"],
                                    d.version, d.hash4.hex())
        self.assertEqual(new.hash4, d.hash4)

    def test_announcement_is_no_part(self):
        self.assertIsNone(dicttransfer.part_of({"typ": "dict", "dat": {"version": 2}}))

    def test_wrong_hash_or_length(self):
        d = v2()
        data = dicttransfer.payload(d)
        with self.assertRaisesRegex(dicttransfer.TransferError, "Prüfsumme"):
            dicttransfer.assemble([data], len(data), d.version, "00000000")
        with self.assertRaisesRegex(dicttransfer.TransferError, "Bytes empfangen"):
            dicttransfer.assemble([data[:-1]], len(data), d.version, d.hash4.hex())

    def test_zip_bomb_is_refused(self):
        bomb = zlib.compress(b"\0" * (2 * 1024 * 1024), 9)
        with self.assertRaisesRegex(dicttransfer.TransferError, "größer"):
            dicttransfer.assemble([bomb], len(bomb), 2, "00000000")


def cbor2_page(data: bytes) -> dict:
    """Decode like a listener with dictionary v1 would (raw numbers in dat)."""
    from brocast.codec import Codec
    return Codec(Dictionary.load(V1)).decode(data, defaults=False)


class ListenerTests(unittest.TestCase):
    """A listener with dictionary v1 receives the packed v2."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "brocast-core.yaml"
        shutil.copy(V1, self.path)
        cfg = make_cfg("listener", "")
        cfg.dictionary = self.path
        self.clock = Clock()
        self.li = Daemon(cfg, clock=self.clock, db_path=":memory:")
        self.frames = dicttransfer.build_frames(v2(), 25, 0, T0)

    def tearDown(self):
        self.tmp.cleanup()

    def rx(self, data: bytes, src: str = ST) -> str:
        self.li.on_frame(0, frame.build(src, data))
        return self.li.listener.rxlog()[0]["result"]

    def status(self) -> dict:
        return self.li.listener.dictionary_status()

    def test_collect_over_two_rounds_then_confirm(self):
        missing = {3, 7}
        for n, f in enumerate(self.frames, start=1):
            if n not in missing:
                self.assertEqual(self.rx(f), "dict_part")
        radio = self.status()["radio"]
        self.assertEqual((radio["have"], radio["total"]), (len(self.frames) - 2, len(self.frames)))
        self.assertEqual(self.rx(self.frames[0]), "dict_have")     # second round: repeat
        self.assertEqual(self.rx(self.frames[2]), "dict_part")
        self.assertEqual(self.rx(self.frames[6]), "dict_ready")    # complete, not trusted
        self.assertEqual(self.li.codec.d.version, 1)               # nothing installed yet
        self.assertEqual(self.status()["ready"]["station"], ST)
        res = self.li.listener.install_ready_dictionary()
        self.assertTrue(res["installed"])
        self.assertEqual(self.li.codec.d.hash4, v2().hash4)
        self.assertEqual(Dictionary.load(self.path).hash4, v2().hash4)   # written as YAML
        self.assertTrue((self.path.parent / "brocast-core.v1.bak.yaml").exists())
        self.assertIsNone(self.status()["ready"])
        self.assertEqual(self.rx(self.frames[0]), "dict_current")  # from now on: up to date

    def test_trusted_station_installs_at_once(self):
        self.li.listener.set_settings({"dict_trusted": ["oe3gas-5"]})
        results = [self.rx(f) for f in self.frames]
        self.assertEqual(results[-1], "dict_installed")
        self.assertEqual(self.li.codec.d.version, v2().version)

    def test_other_station_is_not_trusted(self):
        self.li.listener.set_settings({"dict_trusted": ["OE1ABC-5"]})
        results = [self.rx(f, src="OE3XYZ-5") for f in self.frames]
        self.assertEqual(results[-1], "dict_ready")
        self.assertEqual(self.li.codec.d.version, 1)

    def test_tampered_part_is_dropped(self):
        bad = cbor2.loads(self.frames[1])
        chunk = bad[20][3]
        bad[20][3] = bytes([chunk[0] ^ 0xFF]) + chunk[1:]
        frames = list(self.frames)
        frames[1] = cbor2.dumps(bad, canonical=True)
        results = [self.rx(f) for f in frames]
        self.assertEqual(results[-1], "dict_bad")
        self.assertEqual(self.li.codec.d.version, 1)
        self.assertIsNone(self.status()["ready"])

    def test_renumbering_is_refused(self):
        data = copy.deepcopy(v2().raw)
        data["types"]["wx"][0]["name"] = "temperatur"              # number 0 re-used
        evil = Dictionary(data)
        results = [self.rx(f, src="OE9EVL-5") for f in dicttransfer.build_frames(evil, 30, 0, T0)]
        self.assertEqual(results[-1], "dict_bad")

    def test_install_without_ready_dictionary(self):
        with self.assertRaises(ListenerError):
            self.li.listener.install_ready_dictionary()

    def test_trusted_setting_is_checked(self):
        with self.assertRaises(ListenerError):
            self.li.listener.set_settings({"dict_trusted": ["kein call"]})


class StationTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.st = Daemon(make_cfg("station", ST), clock=self.clock, db_path=":memory:")

    def test_broadcast_is_idempotent_and_scheduled(self):
        self.st.broadcast_dictionary()
        row = self.st.store.get_page(*DICT_DATA)
        n = len(self.st.store.frames(row.pid))
        self.assertGreater(n, 5)
        self.st.broadcast_dictionary()                               # same dictionary: no change
        self.assertEqual(self.st.store.get_page(*DICT_DATA).rev, row.rev)
        gap = self.st.carousel.schedules[DICT_DATA]
        self.assertEqual((gap(1), gap(2), gap(5)), (15, 24 * 60, 24 * 60))
        self.assertIsNone(row.exp_min)                              # never expires

    def test_switched_off_withdraws(self):
        self.st.broadcast_dictionary()
        self.st.cfg.station.dict_broadcast_hours = 0
        self.st.broadcast_dictionary()
        self.assertEqual(self.st.store.get_page(*DICT_DATA).state, "withdrawn")

    def test_send_now_button(self):
        self.st.broadcast_dictionary()
        row = self.st.store.get_page(*DICT_DATA)
        self.st.store.mark_sent(row.pid, int(self.clock()), int(self.clock()) + 86400)
        self.clock.t += 600
        res = self.st.broadcast_dictionary_now()
        self.assertTrue(res["ok"], res)
        row = self.st.store.get_page(*DICT_DATA)
        self.assertEqual((row.next_tx, row.tx_count), (int(self.clock()), 0))   # due now, 15 min again
        self.st.cfg.station.dict_broadcast_hours = 0
        self.assertFalse(self.st.broadcast_dictionary_now()["ok"])

    def test_send_now_needs_station(self):
        li = Daemon(make_cfg("listener", ""), clock=self.clock, db_path=":memory:")
        self.assertFalse(li.broadcast_dictionary_now()["ok"])

    def test_announcement_tells_the_interval(self):
        """The yellow bar can say: comes over the air every 24 h (no call sign needed)."""
        self.st.cfg.station.dict_source = "Mailbox OE3GAS-1, Befehl DICT"
        self.st.announce_dictionary()
        row = self.st.store.get_page("brocastd", "dictionary")
        data = self.st.store.frames(row.pid)[0]
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "brocast-core.yaml"
        shutil.copy(V1, path)
        cfg = make_cfg("listener", "")
        cfg.dictionary = path
        li = Daemon(cfg, clock=self.clock, db_path=":memory:")
        li.on_frame(0, frame.build(ST, data))
        src = li.listener.dictionary_status()["source"]
        self.assertEqual((src["air_hours"], src["station"], src["text"]),
                         (24, ST, "Mailbox OE3GAS-1, Befehl DICT"))

    def test_own_parts_are_ignored(self):
        """The station hears its own frames in its own listener: same version, nothing to do."""
        frames = dicttransfer.build_frames(self.st.codec.d, 25, 0, T0)
        self.st.on_frame(0, frame.build("OE1ABC-5", frames[0]))
        self.assertEqual(self.st.listener.rxlog()[0]["result"], "dict_current")


if __name__ == "__main__":
    unittest.main()
