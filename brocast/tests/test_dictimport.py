"""Dictionary import (text from TinyBox DICT), announcement page, live reload."""

from __future__ import annotations

import copy
import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from brocast import dictimport
from brocast.codec import Codec
from brocast.daemon import Daemon
from brocast.dictionary import Dictionary
from brocast.listener_api import ListenerApi
from tests.test_daemon import ROOT, T0, http, make_cfg

# Import tests always start from the frozen version 1 (tests/data), so they keep
# working whatever version the shipped brocast-core.yaml has.
V1_PATH = Path(__file__).resolve().parent / "data" / "brocast-core-v1.yaml"
BASE = Dictionary.load(V1_PATH)


def framed(data: dict, version: int | None = None, noise: bool = True,
           crlf: bool = False) -> str:
    """What a terminal capture of TinyBox's DICT command looks like."""
    lines = [l.rstrip() for l in yaml.safe_dump(data, allow_unicode=False, sort_keys=False)
             .splitlines() if l.strip()]
    sha = hashlib.sha256("\n".join(lines).encode()).hexdigest()
    v = data["version"] if version is None else version
    body = [f"#BROCAST-DICT BEGIN v{v} lines={len(lines)} sha256={sha}", *lines, "#BROCAST-DICT END"]
    if noise:
        body = ["*** CONNECTED to OE3GAS-1", "TinyBox (A,B,H,...) > DICT",
                "brocast dictionary v2, ... Save this output", *body,
                "Dictionary sent.", "TinyBox (A,B,H,...) >"]
    return ("\r\n" if crlf else "\n").join(body)


def v2() -> dict:
    data = copy.deepcopy(BASE.raw)
    data["version"] = 2
    data["types"]["wx"][14] = {"name": "vis", "type": "uint", "unit": "km", "de": "Sichtweite"}
    data["enums"]["cat"][13] = {"name": "fox", "de": "Fuchsjagd", "en": "Fox hunt"}
    return data


class ExtractTests(unittest.TestCase):
    def test_capture_with_noise_and_crlf(self):
        version, lines = dictimport.extract(framed(v2(), crlf=True))
        self.assertEqual(version, 2)
        self.assertTrue(lines[0].startswith("dictionary:"))

    def test_missing_markers(self):
        with self.assertRaisesRegex(dictimport.ImportError_, "Startmarke"):
            dictimport.extract("hello\nworld")
        text = framed(v2()).replace("#BROCAST-DICT END", "")
        with self.assertRaisesRegex(dictimport.ImportError_, "Endmarke"):
            dictimport.extract(text)

    def test_lost_line_and_changed_text(self):
        text = framed(v2(), noise=False).split("\n")
        with self.assertRaisesRegex(dictimport.ImportError_, "Zeilen"):
            dictimport.extract("\n".join(text[:5] + text[6:]))
        changed = framed(v2()).replace("Sichtweite", "Sichtweitx")
        with self.assertRaisesRegex(dictimport.ImportError_, "Prüfsumme"):
            dictimport.extract(changed)

    def test_text_from_request(self):
        import base64
        raw = framed(v2()).encode("latin-1")
        self.assertIn("BEGIN", dictimport.text_from_request(
            {"data_b64": base64.b64encode(raw).decode()}))
        with self.assertRaises(dictimport.ImportError_):
            dictimport.text_from_request({"data_b64": "%%%"})


class RunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name) / "brocast-core.yaml"
        shutil.copy(ROOT / "brocast-core.yaml", self.target)

    def tearDown(self):
        self.tmp.cleanup()

    def test_dry_run_does_not_write(self):
        before = self.target.read_bytes()
        res = dictimport.run(framed(v2()), BASE, self.target, dry_run=True)
        self.assertTrue(res.ok and not res.installed)
        self.assertEqual(res.added, {"Liste cat": 1, "Thema wx": 1})
        self.assertEqual(self.target.read_bytes(), before)

    def test_install_and_backup(self):
        res = dictimport.run(framed(v2()), BASE, self.target)
        self.assertTrue(res.installed)
        self.assertEqual(Dictionary.load(self.target).version, 2)
        self.assertTrue((self.target.parent / "brocast-core.v1.bak.yaml").exists())
        # same data as sent (comments and formatting do not matter)
        self.assertEqual(Dictionary.load(self.target).hash4, Dictionary(v2()).hash4)

    def test_renumbering_rejected(self):
        bad = v2()
        bad["types"]["wx"][0]["name"] = "temperatur"
        with self.assertRaisesRegex(dictimport.ImportError_, "umgedeutet"):
            dictimport.run(framed(bad), BASE, self.target)
        bad = v2()
        del bad["enums"]["unit"][22]
        with self.assertRaisesRegex(dictimport.ImportError_, "entfernt"):
            dictimport.run(framed(bad), BASE, self.target)

    def test_not_newer(self):
        res = dictimport.run(framed(copy.deepcopy(BASE.raw)), BASE, self.target)
        self.assertIn("bereits installiert", res.message)
        older = copy.deepcopy(BASE.raw)
        older["types"]["wx"][15] = {"name": "x", "type": "uint"}
        with self.assertRaisesRegex(dictimport.ImportError_, "nicht neuer"):
            dictimport.run(framed(older), BASE, self.target)

    def test_marker_version_must_match(self):
        with self.assertRaisesRegex(dictimport.ImportError_, "Startmarke nennt"):
            dictimport.run(framed(v2(), version=3), BASE, self.target)

    def test_invalid_yaml(self):
        lines = ["dictionary: x", "version: 2", "envelope: [1, 2"]
        sha = hashlib.sha256("\n".join(lines).encode()).hexdigest()
        text = "\n".join([f"#BROCAST-DICT BEGIN v2 lines=3 sha256={sha}", *lines, "#BROCAST-DICT END"])
        with self.assertRaisesRegex(dictimport.ImportError_, "kein gültiges"):
            dictimport.run(text, BASE, self.target)


class DaemonImportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dict_path = Path(self.tmp.name) / "brocast-core.yaml"
        shutil.copy(V1_PATH, self.dict_path)

    async def asyncTearDown(self):
        self.tmp.cleanup()

    def daemon(self, mode="listener", call="", **st):
        cfg = make_cfg(mode, call, **st)
        cfg.dictionary = self.dict_path
        return Daemon(cfg, db_path=":memory:")

    async def test_import_reloads_live(self):
        d = self.daemon()
        res = d.import_dictionary({"text": framed(v2())}, dry_run=False)
        self.assertTrue(res["installed"])
        self.assertEqual(d.codec.d.version, 2)
        self.assertEqual(d.listener.d.version, 2)
        self.assertIn("vis", d.codec.d.types["wx"].by_name)        # new field usable at once
        self.assertFalse(d.listener.status()["dictionary"]["outdated"])

    async def test_station_announces_dictionary(self):
        st = self.daemon("station", "OE3GAS-5", dict_source="Mailbox OE3GAS-1, Befehl DICT")
        st.announce_dictionary()
        row = st.store.get_page("brocastd", "dictionary")
        page = Codec().decode(st.store.frames(row.pid)[0])
        self.assertEqual(page["typ"], "dict")
        self.assertEqual(page["dat"]["source"], "Mailbox OE3GAS-1, Befehl DICT")
        st.announce_dictionary()                                     # idempotent
        self.assertEqual(st.store.get_page("brocastd", "dictionary").rev, 0)

    async def test_listener_shows_source_and_hides_page(self):
        li = self.daemon()
        codec = Codec()
        ann = {"id": 30, "t": T0, "typ": "dict", "dv": 2, "ti": "Dictionary v2",
               "dat": {"version": 2, "hash": "abcd1234", "source": "Mailbox OE3GAS-1, Befehl DICT"}}
        from brocast import frame
        li.on_frame(0, frame.build("OE3GAS-5", codec.encode(ann)))
        status = li.listener.status()["dictionary"]
        self.assertTrue(status["outdated"])
        self.assertEqual(status["source"]["text"], "Mailbox OE3GAS-1, Befehl DICT")
        self.assertEqual(li.listener.list_pages(), [])               # not shown as a page
        entry = li.listener.rxlog()[0]
        self.assertEqual((entry["result"], entry["chip"]), ("dictionary_new", "Neuer Inhalt"))

    async def test_api(self):
        d = self.daemon()
        api = ListenerApi(d.listener, "127.0.0.1", 0, d.status, dict_import=d.import_dictionary)
        await api.start()
        try:
            hdr = {"X-Brocast-Client": "1"}
            status, res = await http(api.port, "POST", "/api/v1/dictionary/import",
                                     {"text": framed(v2()), "dry_run": True}, hdr)
            self.assertEqual((status, res["installed"]), (200, False))
            status, res = await http(api.port, "POST", "/api/v1/dictionary/import",
                                     {"text": "kein Mitschnitt"}, hdr)
            self.assertEqual(status, 400)
            self.assertIn("Startmarke", res["message"])
            status, _ = await http(api.port, "POST", "/api/v1/dictionary/import",
                                   {"text": framed(v2())})            # no client header
            self.assertEqual(status, 403)
        finally:
            await api.close()


if __name__ == "__main__":
    unittest.main()
