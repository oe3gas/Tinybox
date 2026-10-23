"""dxfeed: spot parser, cty.dat, store, digest, collector (fake cluster, no network)."""

from __future__ import annotations

import asyncio
import tempfile
import time
import unittest
from pathlib import Path

import json
import sys

from dxfeed import cty as ctymod
from dxfeed import dxcc as dxccmod
from dxfeed import mostwanted as mwmod
from dxfeed.collector import Collector, TelnetFilter
from dxfeed.config import ConfigError, load
from dxfeed.digest import DxLine, build, rate, write_inbox
from dxfeed import spots as spots_mod
from dxfeed.spots import band_of, clean_text, mode_of, parse
from dxfeed.store import Store
from tinybox.adapters import inbox

CTY_SAMPLE = """\
Austria:                  15:  28:  EU:   47.33:   -13.33:    -1.0:  OE:
    OE;
Germany:                  14:  28:  EU:   51.00:   -10.00:    -1.0:  DL:
    DA,DB,DC,DD,DF,DG,DH,DJ,DK,DL,DM,DN,DO,DP,DQ,DR;
Italy:                    15:  28:  EU:   42.82:   -12.58:    -1.0:  I:
    I;
Sicily:                   15:  28:  EU:   37.50:   -14.00:    -1.0:  *IT9:
    IT9;
Falkland Islands:         13:  16:  SA:  -51.63:    58.72:     4.0:  VP8:
    VP8;
Mauritius:                39:  53:  AF:  -20.35:   -57.50:    -4.0:  3B8:
    3B8;
Japan:                    25:  45:  AS:   36.40:  -138.38:    -9.0:  JA:
    JA,JE,JF,JG,JH,JI,JJ,JK,JL,JM,JN,JO,JP,JQ,JR,JS,7J,8J,=JD1BMH{OC};
United States:            05:  08:  NA:   37.53:    91.67:     5.0:  K:
    K,N,W,AA;
"""


def cty() -> ctymod.Cty:
    return ctymod.Cty.from_text(CTY_SAMPLE)


CONF = """\
[cluster]
nodes = 127.0.0.1:{port}
login = oe3gas
reconnect_sec = 5
[data]
db = {dir}/dx.db
cty = {dir}/cty.dat
[digest]
exclude = DL OE I K JA
inbox = {dir}/eingang
"""


def make_cfg(d: str, port: int = 7300):
    p = Path(d) / "dxfeed.conf"
    p.write_text(CONF.format(port=port, dir=d), encoding="utf-8")
    return load(p)


class InboxFromTinyboxTests(unittest.TestCase):
    """CR70: the inbox folder is read from tinybox.conf."""

    def test_inbox_from_tinybox_conf(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "tinybox.conf").write_text("[inbox]\ndir = in\n", encoding="utf-8")
            p = Path(d) / "dxfeed.conf"
            p.write_text("[cluster]\nlogin = oe3gas\n", encoding="utf-8")
            cfg = load(p)
            self.assertEqual(cfg.digest.inbox, Path(d) / "in")
            self.assertIn("tinybox.conf", cfg.inbox_source)
            p.write_text("[cluster]\nlogin = oe3gas\n[digest]\ninbox = other\n",
                         encoding="utf-8")
            cfg = load(p)
            self.assertEqual((cfg.digest.inbox, cfg.inbox_source), (Path("other"), "dxfeed.conf"))
            self.assertIn("overrides", cfg.hints[0])
            p.write_text("[tinybox]\nconf = nix.conf\n[cluster]\nlogin = oe3gas\n",
                         encoding="utf-8")
            cfg = load(p)
            self.assertEqual(cfg.digest.inbox, Path("eingang"))
            self.assertIn("not found", cfg.hints[0])


class SpotTests(unittest.TestCase):
    def test_parse_dxspider_line(self):
        s = parse("DX de OE3GAS:     14025.0  VP8ABC       CW 599 tnx QSO           1234Z")
        self.assertEqual((s.spotter, s.freq, s.dx, s.hhmm), ("OE3GAS", 14025.0, "VP8ABC", "1234"))
        self.assertEqual((s.band, s.mode, s.skimmer), ("20m", "CW", False))
        self.assertEqual(s.comment, "CW 599 tnx QSO")

    def test_parse_skimmer_with_locator_and_ssid(self):
        s = parse("DX de DK9IP-#:     7012.0  JA1ABC       CW 12 dB 26 WPM CQ      0712Z JN48")
        self.assertTrue(s.skimmer)
        self.assertEqual((s.spotter, s.dx, s.band), ("DK9IP", "JA1ABC", "40m"))
        s = parse("DX de OE3GAS-2:   21074.0  3B8XY        FT8 -12dB               1105Z")
        self.assertEqual((s.spotter, s.mode), ("OE3GAS", "FT8"))

    def test_reject_garbage(self):
        for line in ("OE3GAS de NODE 15-Oct-2026 1923Z >",
                     "DX de OE3GAS:  14025.0  ABCDEF  no digit in call  1234Z",
                     "DX de OE3GAS:  99.0  VP8ABC  too low  1234Z",
                     "WWV de VE7CC <18>:   SFI=120, A=5, K=1"):
            self.assertIsNone(parse(line), line)

    def test_comment_is_cleaned(self):
        s = parse("DX de OE3GAS:  14200.0  VP8ABC  héllo\x1b[31m " + "x" * 80 + "  1234Z")
        self.assertTrue(all(32 <= ord(c) < 127 for c in s.comment))
        self.assertLessEqual(len(s.comment), 40)
        self.assertEqual(clean_text("Grüße  aus\tOE"), "Grue aus OE")

    def test_band_and_mode(self):
        self.assertEqual(band_of(50313), "6m")
        self.assertEqual(band_of(13999), "")
        self.assertEqual(mode_of(14074.5, ""), "FT8")
        self.assertEqual(mode_of(7047.6, ""), "FT4")
        self.assertEqual(mode_of(14010, ""), "CW")
        self.assertEqual(mode_of(14195, ""), "SSB")
        self.assertEqual(mode_of(14195, "rtty contest"), "RTTY")
        self.assertEqual(mode_of(10145, ""), "")
        self.assertEqual((band_of(144300), band_of(432200)), ("2m", "70cm"))
        self.assertEqual(mode_of(144174.5, ""), "FT8")
        self.assertEqual(mode_of(144050, ""), "CW")
        self.assertEqual(mode_of(432200, ""), "SSB")


class CtyTests(unittest.TestCase):
    def test_lookup(self):
        c = cty()
        self.assertEqual(c.lookup("OE3GAS")[0].name, "Austria")
        self.assertEqual(c.lookup("DK9IP")[0].prefix, "DL")
        self.assertEqual(c.lookup("IT9ABC")[0].prefix, "I")            # WAE entry skipped
        self.assertEqual(c.lookup("VP8/G3ABC")[0].prefix, "VP8")
        self.assertEqual(c.lookup("G3ABC/VP8")[0].prefix, "VP8")
        self.assertEqual(c.lookup("OE3GAS/P")[0].prefix, "OE")
        self.assertIsNone(c.lookup("OE3GAS/MM"))
        self.assertIsNone(c.lookup("ZZ9ZZ"))

    def test_exact_call_with_continent_override(self):
        ent, cont = cty().lookup("JD1BMH")
        self.assertEqual((ent.prefix, cont), ("JA", "OC"))
        self.assertEqual(cty().lookup("JA1ABC")[1], "AS")

    def test_broken_file(self):
        with self.assertRaises(ctymod.CtyError):
            ctymod.Cty.from_text("nothing useful here;")


class StoreTests(unittest.TestCase):
    def test_coverage_merges_sessions(self):
        with tempfile.TemporaryDirectory() as d:
            st = Store(Path(d) / "dx.db")
            a = st.session_start("n1", 1000)
            st.session_alive(a, 5000)
            b = st.session_start("n1", 4000)          # overlaps the first one
            st.session_alive(b, 7000)
            c = st.session_start("n2", 9000)
            st.session_alive(c, 20000)
            self.assertEqual(st.coverage(2000, 10000), (7000 - 2000) + (10000 - 9000))
            st.close()

    def test_prune(self):
        with tempfile.TemporaryDirectory() as d:
            st = Store(Path(d) / "dx.db")
            s = parse("DX de OE3GAS:  14025.0  VP8ABC  CW  1234Z")
            st.add(s, 1000)
            st.add(s, 10 * 86400)
            self.assertEqual(st.prune(7, now=10 * 86400), 1)
            self.assertEqual(len(st.last(10)), 1)
            st.close()


def fill(st: Store, c: ctymod.Cty, base: float) -> None:
    lines = [
        # VP8ABC: 3 EU spotters on 2 bands -> shown
        (0, "DX de OE3GAS:   14025.0  VP8ABC  CW 599  0900Z"),
        (600, "DX de DK9IP:    14026.0  VP8ABC  CW  0910Z"),
        (7200, "DX de I2XYZ:    18080.0  VP8ABC  FT8  1100Z"),
        # 3B8XY: 2 EU spotters -> shown
        (3600, "DX de OE1ABC:   21074.0  3B8XY   FT8  1000Z"),
        (3700, "DX de DL1ABC:   21075.0  3B8XY   FT8  1001Z"),
        # VP8ZZZ: only one spotter -> counted, not shown
        (100, "DX de OE3GAS:   14030.0  VP8ZZZ  CW  0901Z"),
        # spotted only from NA -> not relevant, but in the total
        (200, "DX de W1AW:     14030.0  3B8AA   CW  0902Z"),
        # common entity (DL) -> excluded
        (300, "DX de OE3GAS:   14030.0  DL1XX   CW  0903Z"),
        # 70cm with one spotter -> counted, not shown
        (400, "DX de OE3GAS:  432200.0  3B8BB   SSB 0904Z"),
        # 160m spotted by AF -> neither relevant nor in band activity
        (450, "DX de 3B8XX:     1830.0  VP8AA   CW  0905Z"),
    ]
    for off, line in lines:
        s = parse(line)
        st.add(s, base + off, c.lookup(s.dx), c.lookup(s.spotter))
    sid = st.session_start("n", base - 60)
    st.session_alive(sid, base + 86400)
    st.commit()


class DigestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = make_cfg(self.tmp.name)
        self.st = Store(self.cfg.data.db)
        self.base = 1792054800.0                       # 2026-10-14 05:00 local-ish
        fill(self.st, cty(), self.base)

    def tearDown(self):
        self.st.close()
        self.tmp.cleanup()

    def digest(self, **over):
        cfg = self.cfg.digest
        if over:
            import dataclasses
            cfg = dataclasses.replace(cfg, **over)
        since, until = self.base - 60, self.base + 86340
        return build(self.st.spots(since, until), cfg, since, until,
                     self.st.coverage(since, until), "test:7300")

    def test_table_and_filters(self):
        d = self.digest()
        lines = d.text.splitlines()
        rows = [l for l in lines if l[2:].startswith(("VP8", "3B8", "DL1"))]
        # alphabetical; without the Most Wanted list every row is tier C, rank "-"
        self.assertEqual([r.split()[1] for r in rows], ["3B8XY", "VP8ABC"])
        self.assertIn("20 17", rows[1])
        self.assertIn("CW FT8", rows[1])
        self.assertTrue(rows[1].startswith("C "))
        self.assertTrue(rows[1].rstrip().endswith(" 3   -"))
        self.assertIn("2 Rufzeichen mit weniger als 2 Spottern", d.text)
        self.assertIn("10 Spots gesamt, davon 7 relevant", d.text)
        self.assertIn("(auf 2m 70cm alle)", d.text)
        self.assertNotIn("Achtung", d.text)
        self.assertTrue(all(len(l) < 80 for l in lines))
        self.assertTrue(d.subject.startswith("DX-Zusammenfassung "))

    def test_band_activity(self):
        d = self.digest()
        self.assertIn('eigenes Bulletin "DX-Bandaktivitaet"', d.text)
        self.assertTrue(d.act.subject.startswith("DX-Bandaktivitaet "))
        act = d.act.text
        self.assertRegex(act, r"20m\s+4\s+4\s+0\s+0\s+0 09z")   # W1AW is NA -> not counted
        self.assertRegex(act, r"70cm\s+1\s+0\s+1\s+0\s+0 09z")  # SSB
        self.assertRegex(act, r"160m\s+0\n")                # AF spotter not counted

    def test_vhf_counts_every_entity(self):
        c = cty()
        for sp in ("OE3GAS", "OE1ABC", "DK9IP"):
            for line in (f"DX de {sp}:  144300.0  DL0ABC  SSB tropo  1200Z",
                         f"DX de {sp}:  432174.0  OE5XYZ  -12 dB  1201Z",
                         f"DX de {sp}:   14200.0  DL0HF   SSB  1202Z"):
                s = parse(line)
                self.st.add(s, self.base + 2000, c.lookup(s.dx), c.lookup(s.spotter))
        rows = {l.split()[1]: l for l in self.digest().text.splitlines() if l[2:4] in ("DL", "OE")}
        self.assertIn("DL0ABC", rows)
        self.assertIn(" 2m ", rows["DL0ABC"])
        self.assertIn("70cm", rows["OE5XYZ"])
        self.assertIn("FT8", rows["OE5XYZ"])
        self.assertNotIn("DL0HF", rows)                    # HF: DL still excluded

    def test_byte_limit_drops_rows(self):
        c = cty()
        for i in range(60):
            for sp in ("OE3GAS", "DK9IP"):
                s = parse(f"DX de {sp}:  28020.0  VP8A{i:02d}  CW  1200Z")
                self.st.add(s, self.base + 1000 + i, c.lookup(s.dx), c.lookup(s.spotter))
        d = self.digest(max_lines=100, max_bytes=1500)
        self.assertLessEqual(len(d.text.encode()), 1500)
        self.assertIn("weitere mit 2+ Spottern nicht gezeigt", d.text)

    def test_coverage_warning(self):
        since, until = self.base - 60, self.base + 2 * 86400
        d = build(self.st.spots(since, until), self.cfg.digest, since, until,
                  self.st.coverage(since, until))
        self.assertIn("Achtung: Cluster nur", d.text)

    def test_no_spots_no_bulletin(self):
        self.assertIsNone(build([], self.cfg.digest, 0, 86400, 0))

    def test_inbox_file_is_accepted_by_tinybox(self):
        d = self.digest()
        files = write_inbox(self.cfg.digest.inbox, d, self.cfg.digest)
        self.assertEqual(len(files), 2)                     # stations + band activity
        b, a = (inbox.parse(f.read_bytes()) for f in files)
        self.assertEqual((b.to, b.subject, b.valid_min), ("DX", d.subject, 7 * 1440))
        self.assertTrue(b.replace.startswith("dxfeed-2"))
        self.assertTrue(a.replace.startswith("dxfeed-act-"))
        self.assertEqual((a.to, a.subject), ("DX", d.act.subject))
        self.assertIsNone(b.sender)
        self.assertEqual(list(Path(self.cfg.digest.inbox).glob("*.tmp")), [])


def mw_sample(**ranks) -> mwmod.MostWanted:
    """A Most Wanted list: the given prefixes at the given ranks, the rest filler."""
    data = {str(r): p for p, r in ranks.items()}
    filler = (f"X{i}" for i in range(400))
    for r in range(1, 341):
        data.setdefault(str(r), next(filler))
    return mwmod.MostWanted(mwmod.parse(json.dumps(data)))


class RelevanceTests(unittest.TestCase):
    def test_parse_accepts_three_shapes(self):
        prefixes = [f"P{i}" for i in range(150)]
        by_rank = {str(i + 1): p for i, p in enumerate(prefixes)}
        by_prefix = {p: i + 1 for i, p in enumerate(prefixes)}
        for data in (by_rank, by_prefix, prefixes):
            ranks = mwmod.parse(json.dumps(data))
            self.assertEqual((ranks["P0"], ranks["P149"]), (1, 150))
        with self.assertRaises(mwmod.MostWantedError):
            mwmod.parse('{"1": "P5"}')                       # far too short
        with self.assertRaises(mwmod.MostWantedError):
            mwmod.parse("<html>maintenance</html>")

    def test_rarity_beats_spotters(self):
        bouvet = mwmod.score(2, 5)          # 5 spotters, rank 2
        lu = mwmod.score(330, 10)           # 10 spotters, rank 330
        self.assertAlmostEqual(bouvet, 25.8, delta=0.2)
        self.assertAlmostEqual(lu, 3.5, delta=0.1)
        self.assertEqual((mwmod.tier(bouvet, 25, 12), mwmod.tier(lu, 25, 12)), ("A", "C"))
        self.assertEqual(mwmod.rarity(None), mwmod.rarity(mwmod.UNKNOWN_RANK))
        self.assertEqual(mwmod.rarity(1), 10.0)
        self.assertAlmostEqual(mwmod.rarity(340), 1.0, places=3)

    def test_case_and_missing_file(self):
        mw = mw_sample(**{"3Y/B": 2})
        self.assertEqual(mw.rank("3y/b"), 2)
        self.assertIsNone(mw.rank("ZZZ"))
        self.assertIsNone(mwmod.load_or_none("/nonexistent/mostwanted.json"))


class BrocastPageTests(unittest.TestCase):
    """The page in the header Brocast: - checked with the real brocast codec."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "brocast"))
        from brocast import Codec
        from brocast import fragment, zdict
        cls.codec, cls.fragment = Codec(), fragment
        cls.zd = zdict.load()
        cls.dxcc = dxccmod.load_or_none()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = make_cfg(self.tmp.name)
        self.st = Store(self.cfg.data.db)
        self.base = 1792054800.0
        fill(self.st, cty(), self.base)
        c = cty()
        for sp in ("OE3GAS", "DK9IP"):                       # 3B8XY also on 40m RTTY
            s = parse(f"DX de {sp}:   7040.0  3B8XY  RTTY  1300Z")
            self.st.add(s, self.base + 5000, c.lookup(s.dx), c.lookup(s.spotter))
        self.since, self.until = self.base - 60, self.base + 86340

    def tearDown(self):
        self.st.close()
        self.tmp.cleanup()

    def build(self, mw, dxcc="default"):
        dx = self.dxcc if dxcc == "default" else dxcc
        return build(self.st.spots(self.since, self.until), self.cfg.digest, self.since,
                     self.until, self.st.coverage(self.since, self.until), "", mw, dx)

    @classmethod
    def data(cls, page):
        """The dxsum data (dictionary v4: block k data)."""
        self_blk = page["blk"]
        assert page["typ"] == "dxsum" and self_blk[0]["k"] == "data"
        return self_blk[0]["v"]

    def test_only_relevant_tiers_go_over_the_air(self):
        d = self.build(mw_sample(VP8=50, **{"3B8": 300}))     # VP8 rare, 3B8 common
        dat = self.data(d.page)
        self.assertEqual([r[1] for r in dat["st"]], ["VP8ABC"])    # 3B8XY is tier C
        tier, call, ent, sp, mw, t0, t1, cw, ssb, ft8, oth, om = dat["st"][0]
        self.assertEqual((tier, ent, sp, mw), ("B", 141, 3, 50))     # Falkland = ADIF 141
        bit = {b: 1 << i for i, b in enumerate(spots_mod.BAND_ORDER)}
        self.assertEqual((cw, ssb, ft8, oth, om), (bit["20m"], 0, bit["17m"], 0, None))
        self.assertEqual(dat["end"], int(self.until))
        self.assertEqual(t0 - t1, 120)                      # 0900 .. 1100
        self.assertEqual((dat["tiers"], dat["calls"]), ("AB", 4))   # 4 DX calls, 2 shown
        # the mailbox text still shows both, tier C included, alphabetically
        rows = [l for l in d.text.splitlines() if l[2:].startswith(("VP8", "3B8"))]
        self.assertEqual([(r[0], r.split()[1]) for r in rows], [("C", "3B8XY"), ("B", "VP8ABC")])

    def test_activity_names_the_other_modes(self):
        d = self.build(None)
        act = self.data(d.act.page)["act"]
        rows = {r[0]: r for r in act}
        self.assertEqual(rows["40m"][1:], [0, 0, 0, 2, 10, [("RTTY", 2)]])
        self.assertNotIn("160m", rows)                     # bands without spots stay off air
        self.assertRegex(d.act.text, r"40m\s+2\s+0\s+0\s+0\s+2 10z\s+RTTY 2")
        # without the list: the most relevant by spotters, all tiers
        st = self.data(d.page)
        self.assertEqual([r[1] for r in st["st"]], ["3B8XY", "VP8ABC"])
        self.assertEqual(st["st"][0][10:], [1 << spots_mod.BAND_ORDER.index("40m"), ["RTTY"]])
        self.assertEqual(st["tiers"], "")                  # not rated

    def test_without_dictionary_the_entity_goes_as_text(self):
        d = self.build(mw_sample(VP8=50), dxcc=None)
        self.assertEqual(self.data(d.page)["st"][0][2], "Falkland Islands")
        self.codec.to_wire({**d.page, "id": 412, "t": int(self.until)})   # still valid

    def test_clublog_prefix_for_the_rank(self):
        """Club Log writes 1A0 where AD1C writes 1A: the DXCC list maps it."""
        line = DxLine(call="1A0C", name="Sov Mil Order of Malta", prefix="1A",
                      spotters={"A", "B", "C", "D", "E", "F"})   # 9.85 x log2(7) = 27.6
        rate([line], self.cfg.digest, mw_sample(**{"1A0": 3}), self.dxcc)
        self.assertEqual((line.dxcc, line.rank, line.tier), (246, 3, "A"))
        rate([line], self.cfg.digest, mw_sample(**{"1A0": 3}), None)
        self.assertEqual((line.dxcc, line.rank), (None, None))   # without the list: no match

    def test_codec_and_frames(self):
        c = cty()                                            # 12 stations, 6 bands each
        for i in range(12):
            for sp in ("OE3GAS", "DK9IP", "I2XYZ"):
                for f in (1830, 3510, 7074, 14025, 21074, 28400):
                    s = parse(f"DX de {sp}: {f}.0  VP8D{i:02d}  {'SSB' if f == 28400 else ''}  1200Z")
                    self.st.add(s, self.base + 9000 + i, c.lookup(s.dx), c.lookup(s.spotter))
        d = self.build(mw_sample(VP8=5))
        self.assertEqual(len(self.data(d.page)["st"]), 12)
        for page in (d.page, d.act.page):
            page = {**page, "id": 412, "rev": 0, "t": int(self.until)}
            built = self.fragment.build(self.codec, page, self.zd)
            self.assertLessEqual(built.fragments, 2)
            back = self.codec.from_wire(self.codec.to_wire(page))
            self.assertEqual(back["typ"], "dxsum")
            self.assertEqual(back["cat"], ["dx"])
        back = self.codec.from_wire(self.codec.to_wire({**d.page, "id": 412, "t": 1}))
        self.assertEqual(back["blk"][0]["v"]["st"][0][2], "VP8")      # number -> name

    def test_inbox_file_carries_the_page(self):
        d = self.build(mw_sample(VP8=50))
        files = write_inbox(self.cfg.digest.inbox, d, self.cfg.digest)
        pages = [json.loads(inbox.parse(f.read_bytes()).brocast) for f in files]
        self.assertEqual([p["ti"] for p in pages], [d.page["ti"], d.act.page["ti"]])
        self.assertTrue(all(p["typ"] == "dxsum" for p in pages))
        off = build(self.st.spots(self.since, self.until),
                    __import__("dataclasses").replace(self.cfg.digest, brocast=False),
                    self.since, self.until, 86400, "", None)
        self.assertIsNone(off.page)
        self.assertIsNone(off.act.page)


class TelnetFilterTests(unittest.TestCase):
    def test_strips_commands_and_refuses_options(self):
        tf = TelnetFilter()
        out = tf.feed(b"lo\xff\xfd\x18gin:\xff\xfb\x01 \xff\xfa\x18\x01\xff\xf0x\xff\xff")
        self.assertEqual(out, b"login: x\xff")
        self.assertEqual(tf.take_replies(), b"\xff\xfc\x18\xff\xfe\x01")


class CollectorTests(unittest.TestCase):
    def test_fake_cluster_session(self):
        received: list[bytes] = []

        async def node(reader, writer):
            writer.write(b"\xff\xfd\x18Please enter your call: ")
            await writer.drain()
            received.append(await reader.readline())
            writer.write(b"Hello OE3GAS\r\n"
                         b"DX de OE3GAS:     14025.0  VP8ABC       CW 599     1234Z\r\n"
                         b"DX de DK9IP-#:    14026.0  VP8ABC       CW 20 dB   1235Z\r\n"
                         b"DX de DL1ABC:     21074.0  3B8XY  \x07 FT8 -10     1236Z\r\n"
                         + b"x" * 3000 + b"\r\n")
            await writer.drain()
            await asyncio.sleep(0.3)
            received.append(await asyncio.wait_for(reader.read(200), 1))
            writer.close()

        async def main(d):
            server = await asyncio.start_server(node, "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            cfg = make_cfg(d, port)
            st = Store(cfg.data.db)
            col = Collector(cfg, st, cty())
            with self.assertRaises(ConnectionError):
                await col.session("127.0.0.1", port)
            server.close()
            rows = st.last(10)
            cov = st.coverage(time.time() - 60, time.time() + 1)
            st.close()
            return col, rows, cov

        with tempfile.TemporaryDirectory() as d:
            col, rows, cov = asyncio.run(main(d))
        self.assertEqual(received[0].strip().split(b"\xff\xfc\x18")[-1], b"OE3GAS")
        self.assertIn(b"unset/skimmer", received[1])
        self.assertEqual([r["dx"] for r in rows], ["VP8ABC", "3B8XY"])
        self.assertEqual(rows[0]["dx_name"], "Falkland Islands")
        self.assertEqual(rows[1]["sp_cont"], "EU")
        self.assertEqual(col.dropped, 1)                       # skimmer spot
        self.assertGreaterEqual(cov, 0)


class ConfigTests(unittest.TestCase):
    def test_login_required_and_local_only(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.conf"
            p.write_text("[cluster]\nlogin =\n", encoding="utf-8")
            with self.assertRaises(ConfigError):
                load(p)
            p.write_text("[cluster]\nlogin = OE3GAS\n[digest]\nto = DX@OEDX\n", encoding="utf-8")
            with self.assertRaises(ConfigError):
                load(p)
            p.write_text("[cluster]\nlogin = OE3GAS\n", encoding="utf-8")
            cfg = load(p)
            self.assertEqual(cfg.cluster.nodes, (("dxc.hamserve.uk", 7300),))
            self.assertEqual(cfg.digest.to, "DX")

    def test_example_config_loads(self):
        root = Path(__file__).resolve().parent.parent
        text = (root / "dxfeed.conf.example").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.conf"
            p.write_text(text.replace("login         =", "login         = OE3GAS"),
                         encoding="utf-8")
            cfg = load(p)
            self.assertIn("VE", cfg.digest.exclude)


if __name__ == "__main__":
    unittest.main()
