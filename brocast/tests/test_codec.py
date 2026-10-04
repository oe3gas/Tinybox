"""Tests for the brocast codec and dictionary (no radio needed)."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path

import cbor2

from brocast import BrocastError, Codec, CriticalKeyError, Dictionary, DictionaryError
from brocast.__main__ import DEMO_PAGE

ROOT = Path(__file__).resolve().parent.parent
# Reference bytes from the spec document, section "Beispiel: Wetterseite".
DEMO_HEX = ("a80001010702182a041a6ab13b8005183c06010c821a00496e391a00189a3914"
            "a800187d011841021927940319010e0418240518360600070c")


V1_PATH = Path(__file__).resolve().parent / "data" / "brocast-core-v1.yaml"


class DictionaryTests(unittest.TestCase):
    def test_loads_core_dictionary(self):
        d = Dictionary.load()
        self.assertGreaterEqual(d.version, 2)
        self.assertEqual(d.envelope.num("typ"), 6)
        self.assertEqual(d.blocks.num("k"), -1)
        self.assertEqual(d.envelope.num("sub"), 23)
        self.assertNotIn(12, d.enums["typ"].by_num)   # Pull/Anfrage entfällt
        self.assertEqual(len(d.hash4), 4)

    def test_v1_is_frozen(self):
        """Version 1 is in use on the air: the reference copy must never change."""
        d = Dictionary.load(V1_PATH)
        self.assertEqual(d.version, 1)
        self.assertEqual(d.hash4.hex(), "1b082f65",
                         "Dictionary v1 wurde verändert – Änderungen bitte als neue Version")

    def test_current_version_only_adds(self):
        """The shipped dictionary may only add entries to version 1 (no renumbering)."""
        from brocast import dictimport
        added = dictimport.check(Dictionary.load(V1_PATH), Dictionary.load())
        self.assertIn("Thema wx", added)

    def test_v2_weather_fields(self):
        codec = Codec()
        page = {"id": 30, "t": 1790000000, "typ": "wx",
                "dat": {"temp": 21.3, "tmin": -6.3, "tmax": 22.9, "gmax": 10.8,
                        "ptnd": -0.4, "r10m": 0.0, "qff": 1028.5, "gust10": 4.1}}
        back = codec.decode(codec.encode(page))
        self.assertEqual(back["dat"], page["dat"])

    def test_all_short_keys_fit_in_one_byte(self):
        d = Dictionary.load()
        for num in list(d.envelope.by_num) + list(d.blocks.by_num):
            self.assertEqual(len(cbor2.dumps(num)), 1, num)

    def test_duplicate_entry_is_rejected(self):
        d = Dictionary.load()
        data = dict(d.raw)
        data["envelope"] = dict(data["envelope"])
        data["envelope"][23] = {"name": "id", "type": "uint"}
        with self.assertRaises(DictionaryError):
            Dictionary(data)

    def test_envelope_key_outside_range_is_rejected(self):
        d = Dictionary.load()
        data = dict(d.raw)
        data["envelope"] = dict(data["envelope"])
        data["envelope"][24] = {"name": "extra", "type": "uint"}
        with self.assertRaises(DictionaryError):
            Dictionary(data)


class EncodeTests(unittest.TestCase):
    def setUp(self):
        self.codec = Codec()

    def test_weather_page_matches_spec(self):
        data = Codec(Dictionary.load(V1_PATH)).encode(DEMO_PAGE)   # example uses v1
        self.assertEqual(len(data), 57)
        self.assertEqual(data.hex(), DEMO_HEX)

    def test_encoding_is_deterministic(self):
        shuffled = dict(reversed(list(DEMO_PAGE.items())))
        self.assertEqual(self.codec.encode(shuffled), self.codec.encode(DEMO_PAGE))

    def test_dv_is_added_automatically(self):
        wire = cbor2.loads(self.codec.encode(DEMO_PAGE))
        self.assertEqual(wire[0], self.codec.d.version)

    def test_missing_required_field(self):
        page = dict(DEMO_PAGE)
        del page["t"]
        with self.assertRaisesRegex(BrocastError, "'t'"):
            self.codec.encode(page)

    def test_unknown_named_field(self):
        with self.assertRaises(BrocastError):
            self.codec.encode({**DEMO_PAGE, "farbe": "rot"})

    def test_unknown_dat_field(self):
        with self.assertRaises(BrocastError):
            self.codec.encode({**DEMO_PAGE, "dat": {"sonnenschein": 3}})

    def test_id_must_be_number(self):
        with self.assertRaises(BrocastError):
            self.codec.encode({**DEMO_PAGE, "id": "WX"})

    def test_title_too_long(self):
        with self.assertRaises(BrocastError):
            self.codec.encode({**DEMO_PAGE, "ti": "x" * 41})

    def test_special_callsigns(self):
        for call in ("OE3GAS", "OE3GAS-10", "OE3GAS/MM", "DL/OE3GAS/P", "OE3GAS/P-9", "OE50XYZ"):
            with self.subTest(call=call):
                page = self.codec.decode(self.codec.encode({**DEMO_PAGE, "org": call}))
                self.assertEqual(page["org"], call)
        for call in ("oe3gas", "AB", "OE3GAS--1", ""):
            with self.subTest(call=call), self.assertRaises(BrocastError):
                self.codec.encode({**DEMO_PAGE, "org": call})

    def test_datetime_time(self):
        when = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
        page = self.codec.decode(self.codec.encode({**DEMO_PAGE, "t": when}))
        self.assertEqual(page["t"], int(when.timestamp()))

    def test_naive_datetime_rejected(self):
        with self.assertRaises(BrocastError):
            self.codec.encode({**DEMO_PAGE, "t": datetime(2026, 9, 28, 12, 0)})

    def test_negative_temperature(self):
        page = self.codec.decode(self.codec.encode({**DEMO_PAGE, "dat": {"temp": -7.3}}))
        self.assertEqual(page["dat"]["temp"], -7.3)


class DecodeTests(unittest.TestCase):
    def setUp(self):
        self.codec = Codec()

    def test_roundtrip_weather(self):
        page = self.codec.decode(bytes.fromhex(DEMO_HEX))
        self.assertEqual(page["typ"], "wx")
        self.assertEqual(page["id"], 7)
        self.assertEqual(page["pos"], [48.12345, 16.12345])
        self.assertEqual(page["dat"]["qnh"], 1013.2)
        self.assertEqual(page["dat"]["wspd"], 3.6)
        self.assertEqual(page["dat"]["r24h"], 1.2)

    def test_defaults(self):
        page = self.codec.decode(bytes.fromhex(DEMO_HEX), ax25_src="OE3GAS-10")
        self.assertEqual(page["org"], "OE3GAS-10")
        self.assertEqual(page["pri"], "routine")
        self.assertEqual(page["lang"], "de")
        self.assertEqual(page["flg"], [])
        self.assertEqual(page["sym"], "/_")

    def test_exp_default_from_typ(self):
        page = {k: v for k, v in DEMO_PAGE.items() if k != "exp"}
        decoded = self.codec.decode(self.codec.encode({**page, "typ": "dx", "dat": {}}))
        self.assertEqual(decoded["exp"], 30)

    def test_no_defaults(self):
        page = self.codec.decode(bytes.fromhex(DEMO_HEX), defaults=False)
        self.assertNotIn("pri", page)
        self.assertNotIn("org", page)

    def test_flags(self):
        data = self.codec.encode({**DEMO_PAGE, "flg": ["test", "reply_wanted"]})
        self.assertEqual(cbor2.loads(data)[7], 0b1010)
        self.assertEqual(self.codec.decode(data)["flg"], ["test", "reply_wanted"])

    def test_unknown_keys_are_kept(self):
        wire = cbor2.loads(bytes.fromhex(DEMO_HEX))
        wire[300] = "Community-Erweiterung"
        wire[20][40] = 99
        page = self.codec.decode(cbor2.dumps(wire, canonical=True))
        self.assertEqual(page[300], "Community-Erweiterung")
        self.assertEqual(page["dat"][40], 99)

    def test_unknown_critical_key_rejects_page(self):
        wire = cbor2.loads(bytes.fromhex(DEMO_HEX))
        wire[300] = 1
        wire[22] = [300]
        with self.assertRaises(CriticalKeyError):
            self.codec.decode(cbor2.dumps(wire))

    def test_known_critical_key_is_fine(self):
        wire = cbor2.loads(bytes.fromhex(DEMO_HEX))
        wire[22] = [12]
        self.assertIn("pos", self.codec.decode(cbor2.dumps(wire)))

    def test_garbage(self):
        with self.assertRaises(BrocastError):
            self.codec.decode(b"\xff\x00")
        with self.assertRaises(BrocastError):
            self.codec.decode(cbor2.dumps([1, 2, 3]))


class BlockAndLinkTests(unittest.TestCase):
    def setUp(self):
        self.codec = Codec()

    def test_blocks_roundtrip(self):
        page = {
            "id": 1, "t": 1790000000, "typ": "index", "ti": "OE3 Startseite",
            "blk": [
                {"k": "heading", "x": "Wetter"},
                {"k": "value", "n": "Temperatur", "v": 125, "u": "Cel", "sc": -1, "st": "ok"},
                {"k": "link", "x": "Wetter Tulln", "href": ["OE3GAS-10", 7]},
                {"k": "note", "x": "Übung am Samstag", "st": "info"},
            ],
            "lnk": [["OE3GAS-10", 7], ["OE3XSR", 12, 3]],
            "cat": ["wx", "notfunk"],
        }
        data = self.codec.encode(page)
        wire = cbor2.loads(data)
        self.assertEqual(wire[19][0], {-1: 1, -2: "Wetter"})
        decoded = self.codec.decode(data)
        self.assertEqual(decoded["blk"][1]["u"], "Cel")
        self.assertEqual(decoded["blk"][2]["href"], ["OE3GAS-10", 7])
        self.assertEqual(decoded["cat"], ["wx", "notfunk"])
        self.assertEqual(decoded["lnk"][1], ["OE3XSR", 12, 3])

    def test_subpage(self):
        page = {"id": 142, "t": 1790000000, "typ": "text", "ti": "DX-News KW 40",
                "sub": [2, 5], "blk": [{"k": "para", "x": "QSL via LoTW."}]}
        data = self.codec.encode(page)
        self.assertEqual(cbor2.loads(data)[23], [2, 5])
        decoded = self.codec.decode(data)
        self.assertEqual(decoded["sub"], [2, 5])
        self.assertIn("Unterseite: 2/5", "\n".join(self.codec.describe(decoded)))

    def test_invalid_subpage(self):
        for sub in ([0, 5], [6, 5], [1], "1/5", [True, 2]):
            with self.subTest(sub=sub), self.assertRaises(BrocastError):
                self.codec.encode({"id": 1, "t": 1, "typ": "text", "sub": sub})

    def test_custom_category(self):
        data = self.codec.encode({"id": 1, "t": 1, "typ": "text", "cat": ["dx", "Fuchsjagd"]})
        self.assertEqual(cbor2.loads(data)[18], [1, "Fuchsjagd"])
        decoded = self.codec.decode(data)
        self.assertEqual(decoded["cat"], ["dx", "Fuchsjagd"])
        self.assertIn("Fuchsjagd (eigene)", "\n".join(self.codec.describe(decoded)))

    def test_custom_category_length(self):
        for cat in ("", "x" * 21):
            with self.subTest(cat=cat), self.assertRaises(BrocastError):
                self.codec.encode({"id": 1, "t": 1, "typ": "text", "cat": [cat]})

    def test_page_must_fit_one_frame(self):
        page = {"id": 1, "t": 1790000000, "typ": "text",
                "blk": [{"k": "para", "x": "a" * 230}]}
        with self.assertRaisesRegex(BrocastError, "Unterseiten"):
            self.codec.encode(page)
        page["blk"][0]["x"] = "a" * 200
        self.assertLessEqual(len(self.codec.encode(page)), 240)

    def test_unknown_block_kind_rejected(self):
        with self.assertRaises(BrocastError):
            self.codec.encode({"id": 1, "t": 1, "typ": "text", "blk": [{"k": "bild"}]})

    def test_describe_uses_long_texts(self):
        lines = self.codec.describe(self.codec.decode(bytes.fromhex(DEMO_HEX)))
        text = "\n".join(lines)
        self.assertIn("Seitentyp: Wetter", text)
        self.assertIn("Luftdruck (QNH): 1013.2 hPa", text)
        self.assertIn("Windgeschwindigkeit: 3.6 m/s", text)


try:
    import pycddl
except ImportError:  # optional
    pycddl = None


@unittest.skipIf(pycddl is None, "pycddl nicht installiert")
class CddlTests(unittest.TestCase):
    def test_demo_page_matches_schema(self):
        schema = (ROOT / "brocast.cddl").read_text(encoding="utf-8")
        # pycddl rejects optional trailing array members although RFC 8610
        # allows them; use equivalent occurrence ranges for the check.
        schema = schema.replace("[int, int, ? int, ? uint]", "[2*4 int]")
        schema = schema.replace("[callsign, uint / tstr, ? uint]",
                                "[2*3 (callsign / uint / tstr)]")
        pycddl.Schema(schema).validate_cbor(Codec().encode(DEMO_PAGE))


if __name__ == "__main__":
    unittest.main()
