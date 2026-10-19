"""Frame-Format 2: Fragmente bauen, zusammensetzen, und was bei Verlust passiert.

Dazu die Alterung im Karussell (alte Revisionen seltener wiederholen) und das
Preset-Wörterbuch für die Kompression.
"""

from __future__ import annotations

import unittest
import zlib
from pathlib import Path

import cbor2

from brocast import fragment, frame, zdict
from brocast.codec import BrocastError, Codec
from brocast.splitter import TooLargeError, split

ROOT = Path(__file__).resolve().parent.parent
T0 = 1_790_000_000
CALL = "OE3GAS-5"


def noise(n: int, seed: int = 1) -> str:
    """Fester Pseudo-Zufallstext (lässt sich kaum packen)."""
    out, x = [], seed
    for _ in range(n):
        x = (x * 1103515245 + 12345) % 2 ** 31
        out.append(chr(33 + x % 90))
    return "".join(out)


def rundspruch(times: int = 1) -> str:
    return ("Der Rundspruch der Ortsstelle Hollabrunn beginnt am Freitag um 19:00 Uhr "
            "auf 144,9625 MHz. Danach ist Clubabend, alle Teilnehmer sind willkommen. "
            "Wer einen Vortrag halten moechte, moege sich bitte melden. 73 ") * times


def page(blocks: list[dict], **env) -> dict:
    return {"id": 46, "rev": 0, "t": T0, "typ": "text", "ti": "Rundspruch Hollabrunn",
            "cat": ["club"], "exp": 1440, "src": ["TinyBox", "OE3GAS"], "blk": blocks, **env}


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.c = Codec()
        self.z = zdict.load()

    def frames(self, built: fragment.Built) -> list[int]:
        return [len(frame.build(CALL, p, None, built.hdr)) for p in built.payloads]

    def test_short_page_is_one_fragment_without_sub(self):
        built = fragment.build(self.c, page([{"k": "para", "x": "Kurz."}]), self.z)
        self.assertEqual(built.fragments, 1)
        head, rest = fragment.read_payload(built.payloads[0])
        self.assertNotIn(fragment.ENV_SUB, head)         # kein sub: spart Bytes
        self.assertTrue(rest)                            # Blockliste hängt hinten dran

    def test_envelope_only_once(self):
        """Der Titel darf nur im ersten Fragment stehen."""
        built = fragment.build(self.c, page([{"k": "para", "x": noise(600)}]), self.z)
        self.assertGreater(built.fragments, 1)
        first, _ = fragment.read_payload(built.payloads[0])
        later, _ = fragment.read_payload(built.payloads[1])
        self.assertIn(8, first)                          # 8 = ti
        self.assertEqual(set(later), {fragment.ENV_ID, fragment.ENV_REV, fragment.ENV_SUB})

    def test_all_fragments_fit_into_one_frame(self):
        built = fragment.build(self.c, page([{"k": "para", "x": noise(2000)}]), self.z)
        self.assertTrue(all(len(p) + frame.HDR_LEN <= frame.MAX_INFO for p in built.payloads))

    def test_fragments_are_filled_up(self):
        """Alle Fragmente bis auf das letzte sind randvoll."""
        built = fragment.build(self.c, page([{"k": "para", "x": noise(2000)}]), self.z)
        for payload in built.payloads[:-1]:
            self.assertEqual(len(payload) + frame.HDR_LEN, frame.MAX_INFO)

    def test_fewer_frames_and_bytes_than_format_1(self):
        p = page([{"k": "heading", "x": "Rundspruch"},
                  {"k": "para", "x": rundspruch(3)},
                  {"k": "para", "x": "Mehr dazu in der Mailbox OE3GAS-1: R 46"}])
        old = split(self.c, p)
        new = fragment.build(self.c, p, self.z)
        old_bytes = sum(len(frame.build(CALL, f)) for f in old)
        new_bytes = sum(self.frames(new))
        self.assertLess(new.fragments, len(old))
        self.assertLess(new_bytes, old_bytes // 2)       # mehr als die Hälfte gespart

    def test_compression_can_be_switched_off(self):
        p = page([{"k": "para", "x": rundspruch(3)}])
        packed = fragment.build(self.c, p, self.z)
        plain = fragment.build(self.c, p, None)
        self.assertTrue(packed.packed)
        self.assertFalse(plain.packed)
        self.assertLess(packed.blob_sent, plain.blob_sent)
        self.assertEqual(packed.blob_raw, plain.blob_raw)
        self.assertLessEqual(packed.fragments, plain.fragments)

    def test_header_byte_carries_format_and_generation(self):
        built = fragment.build(self.c, page([{"k": "para", "x": rundspruch(2)}]), self.z)
        parsed = frame.parse(frame.build(CALL, built.payloads[0], None, built.hdr))
        self.assertEqual((parsed.fmt, parsed.packed, parsed.zdict_gen),
                         (frame.FORMAT_FRAGMENT, True, self.z.gen))

    def test_tiny_page_is_not_packed(self):
        """Wo der Gewinn unter MIN_GAIN liegt, wird nicht gepackt (kein Aufschlag)."""
        built = fragment.build(self.c, page([{"k": "para", "x": "Kurz."}]), self.z)
        self.assertFalse(built.packed)
        self.assertEqual(built.blob_raw, built.blob_sent)

    def test_too_much_content(self):
        with self.assertRaises(TooLargeError):
            fragment.build(self.c, page([{"k": "para", "x": noise(20000)}]), self.z,
                           max_fragments=40)

    def test_page_without_id(self):
        p = page([{"k": "para", "x": "x"}])
        del p["id"]
        with self.assertRaises(BrocastError):
            fragment.build(self.c, p, self.z)


class AssembleTests(unittest.TestCase):
    def setUp(self):
        self.c = Codec()
        self.z = zdict.load()
        self.a = fragment.Assembler(self.z)

    def send(self, p: dict, assembler: fragment.Assembler | None = None,
             zd: object | None = ..., drop: tuple[int, ...] = ()) -> list[fragment.Feed]:
        built = fragment.build(self.c, p, self.z if zd is ... else zd)
        out = []
        for n, payload in enumerate(built.payloads, start=1):
            if n in drop:
                continue
            data = frame.build(CALL, payload, None, built.hdr)
            parsed = frame.parse(data)
            out.append((assembler or self.a).feed(CALL, parsed.payload, parsed.flags, len(data)))
        return out

    def roundtrip(self, p: dict, **kw) -> dict:
        feeds = self.send(p, **kw)
        self.assertEqual(feeds[-1].status, "page", feeds[-1].note)
        return self.c.decode(feeds[-1].page, ax25_src=CALL, defaults=False)

    def test_one_fragment(self):
        p = page([{"k": "para", "x": "Kurz und gut."}])
        self.assertEqual(self.roundtrip(p), {**p, "dv": self.c.d.version})

    def test_many_fragments(self):
        # echter Text plus etwas Unpackbares: so entstehen mehrere Fragmente
        p = page([{"k": "heading", "x": "Rundspruch"},
                  {"k": "para", "x": rundspruch(1) + noise(500)},
                  {"k": "note", "st": "info", "x": "Alle Angaben ohne Gewähr"}])
        feeds = self.send(p)
        self.assertGreater(len(feeds), 2)
        self.assertEqual([f.status for f in feeds[:-1]], ["fragment"] * (len(feeds) - 1))
        back = self.c.decode(feeds[-1].page, ax25_src=CALL, defaults=False)
        self.assertEqual(back["blk"], p["blk"])
        self.assertEqual(back["ti"], p["ti"])
        self.assertEqual(feeds[-1].fragments, len(feeds))

    def test_table_and_series_survive(self):
        p = page([{"k": "table", "sc": -1, "hdr": ["Station", "°C", "Wind m/s"],
                   "rows": [["Retz", 112, 31], ["Krems", 121, 25], ["Horn", 98, 40]]},
                  {"k": "series", "n": "Temperatur 24 h", "u": "Cel", "sc": -1, "dt": 7200,
                   "v": [111, 90, 85, 72, 37, 90, 138, 155, 160, 147, 116, 79]}],
                 typ="text")
        self.assertEqual(self.roundtrip(p)["blk"], p["blk"])

    def test_without_compression(self):
        p = page([{"k": "para", "x": rundspruch(4)}])
        self.assertEqual(self.roundtrip(p, zd=None)["blk"], p["blk"])

    def test_missing_fragment_leaves_page_incomplete(self):
        p = page([{"k": "para", "x": noise(700)}])
        feeds = self.send(p, drop=(2,))
        self.assertTrue(all(f.status == "fragment" for f in feeds), [f.status for f in feeds])
        self.assertEqual(len(self.a.pending), 1)
        self.assertEqual(self.a.assembled, 0)

    def test_repeat_completes_a_page(self):
        """Eine Wiederholung im nächsten Karussell-Lauf füllt die Lücke."""
        p = page([{"k": "para", "x": noise(700)}])
        self.send(p, drop=(2,))
        feeds = self.send(p)
        self.assertIn("page", [f.status for f in feeds])         # Lücke gefüllt
        self.assertIn("repeat", [f.status for f in feeds])       # Teil 1 kam doppelt
        self.assertEqual(self.a.assembled, 1)

    def test_new_revision_drops_old_parts(self):
        first = page([{"k": "para", "x": noise(700)}])
        self.send(first, drop=(2,))
        second = page([{"k": "para", "x": noise(700, seed=9)}], rev=1)
        feeds = self.send(second)
        self.assertEqual(feeds[-1].status, "page")
        self.assertEqual(self.a.pending, {})                    # nichts bleibt liegen

    def test_old_fragments_expire(self):
        now = [T0]
        a = fragment.Assembler(self.z, ttl=60, clock=lambda: now[0])
        self.send(page([{"k": "para", "x": noise(700)}]), assembler=a, drop=(2,))
        self.assertEqual(len(a.pending), 1)
        self.assertEqual(a.waiting()[0]["station"], CALL)
        now[0] += 3600
        self.send(page([{"k": "para", "x": noise(700)}], id=47), assembler=a, drop=(2,))
        self.assertEqual(len(a.pending), 1)                     # die alte ist verfallen
        self.assertEqual(a.dropped, 1)

    def test_too_many_half_pages(self):
        a = fragment.Assembler(self.z, max_pending=2)
        for page_id in (50, 51, 52, 53):
            self.send(page([{"k": "para", "x": noise(700)}], id=page_id), assembler=a, drop=(2,))
        self.assertLessEqual(len(a.pending), 2)

    def test_other_dictionary_generation_is_refused(self):
        p = page([{"k": "para", "x": rundspruch(2)}])
        built = fragment.build(self.c, p, self.z)
        self.assertTrue(built.packed)
        other = frame.header(frame.FORMAT_FRAGMENT, frame.flags_for(True, 7)) & 0xF
        fed = self.a.feed(CALL, built.payloads[0], other, 100)
        self.assertEqual(fed.status, "zdict")
        self.assertIn("Wörterbuch", fed.note)

    def test_broken_data_is_dropped(self):
        p = page([{"k": "para", "x": rundspruch(2)}])
        built = fragment.build(self.c, p, self.z)
        self.assertTrue(built.packed)
        broken = built.payloads[0][:-4] + b"\x00\x00\x00\x00"
        fed = self.a.feed(CALL, broken, built.hdr & 0xF, 100)
        self.assertEqual(fed.status, "bad")

    def test_garbage_is_no_crash(self):
        for data in (b"", b"\xff\xff\xff", b"\xa1\x01\x18", cbor2.dumps([1, 2, 3])):
            fed = self.a.feed(CALL, data, 0, 20)
            self.assertEqual(fed.status, "bad", data)

    def test_fragment_without_first_part_waits(self):
        p = page([{"k": "para", "x": noise(700)}])
        feeds = self.send(p, drop=(1,))
        self.assertTrue(all(f.status == "fragment" for f in feeds))
        self.assertEqual(self.a.assembled, 0)


class ZDictTests(unittest.TestCase):
    def test_shipped_dictionary_matches_its_hash(self):
        z = zdict.load()
        self.assertTrue(z.ok, z.problem)
        self.assertEqual(len(z.data), 32 * 1024)
        self.assertEqual(z.gen, zdict.ZDICT_GEN)

    def test_roundtrip(self):
        z = zdict.load()
        raw = rundspruch(2).encode("utf-8")
        packed = z.compress(raw)
        self.assertLess(len(packed), len(raw) // 2)
        self.assertEqual(z.decompress(packed), raw)

    def test_wrong_file_is_noticed(self):
        z = zdict.load(expect_sha256="0" * 64)
        self.assertFalse(z.ok)
        self.assertIsNone(z.compress(b"egal"))
        with self.assertRaises(zlib.error):
            z.decompress(b"egal")

    def test_short_data_is_not_packed(self):
        z = zdict.load()
        self.assertIsNone(z.compress(b"ja"))             # Gewinn zu klein


if __name__ == "__main__":
    unittest.main()
