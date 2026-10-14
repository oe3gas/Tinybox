"""brocastd M1 tests: AX.25/KISS, splitting, station, carousel, ingest API, end to end.

No radio needed: a FakeDirewolf relays KISS frames between connected
programs, the way a shared frequency would.
"""

from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path

import cbor2

from brocast import agw, ax25, frame, kiss, zdict
from brocast import carousel as carousel_mod
from brocast.carousel import AirtimeBudget, Carousel
from brocast.codec import MAX_PAGE_BYTES, BrocastError, Codec
from brocast.config import Config, DirewolfCfg, StationCfg
from brocast.daemon import Daemon
from brocast.ingest import IngestServer
from brocast.splitter import TooLargeError, split
from brocast.station import Station
from brocast.store import Store

ROOT = Path(__file__).resolve().parent.parent
T0 = 1_790_000_000
LONG_TEXT = ("3B8/DL1ABC ist ab 5.10. QRV auf 20 und 17 m in CW und FT8. "
             "Die Aktivität dauert zwei Wochen. QSL via LoTW und ClubLog OQRS. ") * 10


class Clock:
    def __init__(self, t: float = T0):
        self.t = t

    def __call__(self) -> float:
        return self.t


def make_cfg(mode: str = "station", call: str = "OE3GAS-5", **station) -> Config:
    cfg = Config(mode=mode, callsign=call, data_dir=ROOT / "data",
                 dictionary=ROOT / "brocast-core.yaml")
    cfg.direwolf = DirewolfCfg(interface="kiss", host="127.0.0.1", kiss_port=0, reconnect_sec=1)
    cfg.station = StationCfg(ingest_port=0, **station)
    cfg.listener.web_port = 0
    return cfg


def make_station(clock: Clock | None = None, **station) -> tuple[Station, Store]:
    store = Store(":memory:")
    st = Station(make_cfg(**station), Codec(), store, clock or Clock(), zd=zdict.load())
    return st, store


WX = {"typ": "wx", "ti": "Wetter Hollabrunn", "dat": {"temp": 12.5, "hum": 65}}
BULLETIN = {"typ": "text", "ti": "DX-News KW 40", "cat": ["dx"], "exp": 43200,
            "blk": [{"k": "heading", "x": "DX-News"}, {"k": "para", "x": LONG_TEXT}]}
def noise(n: int) -> str:
    """Fester Pseudo-Zufallstext: lässt sich kaum packen, geht über mehrere Frames."""
    out, x = [], 1
    for _ in range(n):
        x = (x * 1103515245 + 12345) % 2 ** 31
        out.append(chr(33 + x % 90))
    return "".join(out)


NOISE_BULLETIN = {"typ": "text", "ti": "Messseite", "cat": ["tech"], "exp": 60,
                  "blk": [{"k": "para", "x": noise(900)}]}


# ---------------------------------------------------------------------------

class ConfigTests(unittest.TestCase):
    def test_shipped_config_loads(self):
        from brocast import config
        cfg = config.load(ROOT / "brocastd.conf")
        self.assertEqual((cfg.mode, cfg.callsign, cfg.direwolf.port, cfg.listener.web_port),
                         ("station", "OE3GAS-5", 8000, 7733))
        self.assertEqual(cfg.direwolf.interface, "agw")
        self.assertEqual(cfg.station.repeat_minutes, [0, 2, 5, 10])
        self.assertEqual(cfg.station.token, "")
        self.assertEqual((cfg.station.burst_frames, cfg.station.burst_gap_s), (4, 3.0))


    def _load(self, text: str):
        import tempfile
        from brocast import config
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "brocastd.conf"
            p.write_text("[brocastd]\nmode = listener\n" + text, encoding="utf-8")
            return config.load(p)

    def test_old_kiss_section_still_works(self):
        cfg = self._load("[kiss]\nport = 8101\nchannel = 1\n")
        self.assertEqual((cfg.direwolf.interface, cfg.direwolf.port, cfg.direwolf.channel),
                         ("kiss", 8101, 1))

    def test_interface_choice(self):
        cfg = self._load("[direwolf]\ninterface = KISS\nkiss_port = 8101\n")
        self.assertEqual((cfg.direwolf.interface, cfg.direwolf.port), ("kiss", 8101))
        self.assertEqual(self._load("").direwolf.describe(), "AGW 127.0.0.1:8000")
        from brocast.config import ConfigError
        with self.assertRaises(ConfigError):
            self._load("[direwolf]\ninterface = serial\n")

    def test_listener_lan(self):
        from brocast.config import ConfigError
        cfg = self._load("")
        self.assertEqual((cfg.listener.web_host, cfg.listener.allow_lan), ("127.0.0.1", False))
        with self.assertRaises(ConfigError):          # LAN only when explicitly allowed
            self._load("[listener]\nweb_host = 0.0.0.0\n")
        cfg = self._load("[listener]\nweb_host = 0.0.0.0\nallow_lan = yes\n"
                         "lan_names = pc2.fritz.box, PC2 ; Kommentar\n")
        self.assertEqual((cfg.listener.web_host, cfg.listener.allow_lan, cfg.listener.lan_names),
                         ("0.0.0.0", True, ("pc2.fritz.box", "PC2")))
        with self.assertRaises(ConfigError):
            self._load("[listener]\nweb_host = pc2\nallow_lan = yes\n")
        with self.assertRaises(ConfigError):
            self._load("[listener]\nallow_lan = vielleicht\n")
        with self.assertRaises(ConfigError):          # ingest API stays on loopback
            self._load("[station]\ningest_host = 0.0.0.0\n[listener]\nallow_lan = yes\n")

    def test_host_allowed(self):
        from brocast.webserver import host_allowed
        names = frozenset({"pc2", "pc2.fritz.box"})
        for host, lan, ok in [("127.0.0.1", False, True), ("localhost", False, True),
                              ("192.168.1.20", False, False),
                              ("192.168.1.20", True, True), ("[fe80::1]", True, True),
                              ("PC2", True, True), ("pc2.fritz.box.", True, True),
                              ("pc2", False, False),
                              ("evil.example", True, False), ("", True, False)]:
            with self.subTest(host=host, lan=lan):
                self.assertEqual(host_allowed(host, lan, names), ok)


class AgwTests(unittest.TestCase):
    def test_header(self):
        raw = agw.pack("K", 2, b"\x00abc")
        self.assertEqual(len(raw), 36 + 4)
        self.assertEqual(agw.unpack_header(raw[:36]), (2, "K", 4))


class AX25KissTests(unittest.TestCase):
    def test_ui_frame_roundtrip(self):
        f = ax25.UIFrame(dest="BROCST", src="OE3GAS-5", info=b"\x10abc", path=["WIDE1-1"])
        back = ax25.UIFrame.decode(f.encode())
        self.assertEqual((back.dest, back.src, back.path, back.info, back.pid),
                         ("BROCST", "OE3GAS-5", ["WIDE1-1"], b"\x10abc", 0xF0))

    def test_address_bits(self):
        raw = ax25.UIFrame(dest="BROCST", src="OE3GAS-5", info=b"x").encode()
        self.assertEqual(raw[6], 0xE0)                 # dest: C bit, SSID 0, not last
        self.assertEqual(raw[13], 0x60 | (5 << 1) | 1)  # src: SSID 5, last address

    def test_non_ui_rejected(self):
        raw = bytearray(ax25.UIFrame(dest="OE3GAS-1", src="OE1ABC", info=b"x").encode())
        raw[14] = 0x3F                                   # SABM
        with self.assertRaises(ax25.AX25Error):
            ax25.UIFrame.decode(bytes(raw))

    def test_bad_address(self):
        for call in ("OE3GASX1", "OE3GAS-16", "OE3GAS-X"):
            with self.subTest(call=call), self.assertRaises(ax25.AX25Error):
                ax25.encode_address(call, last=True, high_bit=False)

    def test_kiss_escaping_and_partial_reads(self):
        data = bytes([0xC0, 0xDB, 0x01, 0xC0])
        wire = kiss.encode(data, channel=1)
        dec = kiss.Decoder()
        self.assertEqual(dec.feed(wire[:3]), [])
        self.assertEqual(dec.feed(wire[3:]), [(1, data)])

    def test_brocast_frame_filter(self):
        good = frame.build("OE3GAS-5", b"\xa0")
        self.assertEqual(frame.parse(good).fmt, frame.FORMAT_PAGE)
        fragments = frame.build("OE3GAS-5", b"\xa0", None, frame.header(2, 0x3))
        parsed = frame.parse(fragments)
        self.assertEqual((parsed.fmt, parsed.packed, parsed.zdict_gen), (2, True, 1))
        aprs = ax25.UIFrame(dest="APDW16", src="OE3GAS-5", info=b"!4812.34N/").encode()
        self.assertIsNone(frame.parse(aprs))
        self.assertIsNone(frame.unknown_format(aprs))

    def test_unknown_frame_format_is_named(self):
        """Ein künftiges Format soll als brocast erkannt, aber nicht gelesen werden."""
        future = ax25.UIFrame(dest="BROCST", src="OE3GAS-5", info=b"\x90\xa0").encode()
        self.assertIsNone(frame.parse(future))
        self.assertEqual(frame.unknown_format(future), 9)

    def test_largest_page_fits_n1(self):
        info_len = 1 + MAX_PAGE_BYTES
        self.assertLessEqual(info_len, frame.MAX_INFO)


class SplitterTests(unittest.TestCase):
    def setUp(self):
        self.codec = Codec()
        self.page = {**BULLETIN, "id": 142, "rev": 0, "t": T0}

    def test_small_page_is_not_split(self):
        frames = split(self.codec, {"id": 1, "t": T0, "typ": "text", "ti": "kurz"})
        self.assertEqual(len(frames), 1)
        self.assertNotIn("sub", self.codec.decode(frames[0]))

    def test_long_page(self):
        frames = split(self.codec, self.page)
        self.assertGreater(len(frames), 3)
        pages = [self.codec.decode(f) for f in frames]
        for n, (f, p) in enumerate(zip(frames, pages), start=1):
            self.assertLessEqual(len(f), MAX_PAGE_BYTES)
            self.assertEqual(p["sub"], [n, len(frames)])
            self.assertEqual(p["ti"], "DX-News KW 40")     # every subpage has the title
        text = " ".join(b["x"] for p in pages for b in p["blk"] if b["k"] == "para")
        self.assertEqual(text.split(), LONG_TEXT.split())   # nothing lost

    def test_parts_start_new_subpages(self):
        parts = [[{"k": "heading", "x": "DX"}, {"k": "para", "x": "kurz"}],
                 [{"k": "heading", "x": "Contest"}],
                 [],
                 [{"k": "heading", "x": "Club"}]]
        base = {"id": 30, "rev": 0, "t": T0, "typ": "text", "ti": "Magazin", "src": ["x"]}
        pages = [self.codec.decode(f) for f in split(self.codec, base, parts=parts)]
        self.assertEqual([p["sub"] for p in pages], [[1, 3], [2, 3], [3, 3]])
        self.assertEqual([p["blk"][0]["x"] for p in pages], ["DX", "Contest", "Club"])
        self.assertEqual(["src" in p for p in pages], [True, False, False])

    def test_single_part_like_blk(self):
        parts = [[{"k": "para", "x": "kurz"}]]
        frames = split(self.codec, {"id": 1, "t": T0, "typ": "text"}, parts=parts)
        self.assertEqual(len(frames), 1)
        self.assertNotIn("sub", self.codec.decode(frames[0]))

    def test_too_many_subpages(self):
        with self.assertRaises(TooLargeError):
            split(self.codec, self.page, max_subpages=2)

    def test_multiline_text_is_cut_at_line_breaks(self):
        """A table-like bulletin (weather report) must not be cut inside a line,
        and "Rel. Feuchte" is no sentence end."""
        lines = [f"  Wert {i:02d} Rel. Feuchte   {30 + i} %   (Max. Böe {i}.5 m/s)" for i in range(14)]
        page = {"id": 1, "t": T0, "typ": "text", "ti": "Wetter",
                "blk": [{"k": "para", "x": "\n".join(lines)}]}
        pages = [self.codec.decode(f) for f in split(self.codec, page)]
        self.assertGreater(len(pages), 1)
        got = [line for p in pages for b in p["blk"] for line in b["x"].split("\n")]
        self.assertEqual(got, lines)                        # whole lines, indentation kept

    def test_abbreviation_is_no_sentence_end(self):
        from brocast.splitter import _cut
        head, tail = _cut("Wind max. 40 km/h, z. B. in Böen. Danach ruhig und weiter so", 40)
        self.assertEqual(head, "Wind max. 40 km/h, z. B. in Böen.")

    def test_unsplittable_block(self):
        page = {"id": 1, "t": T0, "typ": "text",
                "blk": [{"k": "table", "rows": [["x" * 50] * 3] * 3}]}
        with self.assertRaises(TooLargeError):
            split(self.codec, page)


class StationTests(unittest.TestCase):
    def test_put_new_page(self):
        st, _ = make_station()
        res = st.put("wx", "hollabrunn", WX)
        self.assertEqual((res["id"], res["rev"], res["changed"], res["subpages"]), (24, 0, True, 1))

    def test_put_is_idempotent(self):
        clock = Clock()
        st, store = make_station(clock)
        st.put("wx", "hollabrunn", WX)
        clock.t += 600
        res = st.put("wx", "hollabrunn", dict(WX))
        self.assertEqual((res["rev"], res["changed"]), (0, False))
        self.assertEqual(store.get_page("wx", "hollabrunn").t, T0 + 600)   # t confirmed

    def test_changed_content_new_revision(self):
        st, _ = make_station()
        st.put("wx", "hollabrunn", WX)
        res = st.put("wx", "hollabrunn", {**WX, "dat": {"temp": 13.0, "hum": 60}})
        self.assertEqual((res["id"], res["rev"], res["changed"]), (24, 1, True))

    def test_ids_are_not_reused(self):
        st, _ = make_station()
        a = st.put("tinybox", "1_OE3GAS", BULLETIN)["id"]
        st.delete("tinybox", "1_OE3GAS")
        b = st.put("tinybox", "2_OE3GAS", BULLETIN)["id"]
        self.assertNotEqual(a, b)

    def test_fixed_id(self):
        st, _ = make_station()
        self.assertEqual(st.put("redaktion", "index", {"typ": "index", "id": 1})["id"], 1)
        with self.assertRaisesRegex(BrocastError, "vergeben"):
            st.put("redaktion", "andere", {"typ": "text", "id": 1})

    def test_managed_fields_rejected(self):
        st, _ = make_station()
        for field in ("rev", "t", "org", "sub", "dv"):
            with self.subTest(field=field), self.assertRaises(BrocastError):
                st.put("wx", "a", {**WX, field: 1})

    def test_bad_names(self):
        st, _ = make_station()
        for provider, key in (("Tiny Box", "a"), ("wx", "../x"), ("", "a")):
            with self.subTest(provider=provider, key=key), self.assertRaises(BrocastError):
                st.put(provider, key, WX)

    def test_delete_sends_withdrawn_revision(self):
        st, store = make_station()
        st.put("wx", "a", WX)
        res = st.delete("wx", "a")
        self.assertEqual((res["rev"], res["state"]), (1, "withdrawn"))
        page = Codec().decode(store.frames(store.get_page("wx", "a").pid)[0])
        self.assertEqual(page["flg"], ["withdrawn"])

    def test_sync_withdraws_missing(self):
        st, store = make_station()
        st.put("tinybox", "1_A", BULLETIN)
        st.put("tinybox", "2_A", BULLETIN)
        res = st.sync("tinybox", {"2_A": BULLETIN, "3_A": BULLETIN, "4_A": {"typ": "nix"}})
        self.assertEqual(res["withdrawn"], ["1_A"])
        self.assertIn("4_A", res["errors"])
        self.assertEqual(store.get_page("tinybox", "1_A").state, "withdrawn")

    def test_parts_via_station(self):
        st, _ = make_station(wire_format=1)          # "parts" gibt es nur im Format 1
        magazin = json.loads((ROOT / "test" / "magazin.json").read_text(encoding="utf-8"))
        self.assertEqual(st.put("test", "magazin", magazin)["subpages"], 3)
        with self.assertRaises(BrocastError):
            st.put("test", "x", {**magazin, "blk": []})
        with self.assertRaises(BrocastError):
            st.put("test", "y", {"typ": "text", "parts": [{"k": "para"}]})

    def test_same_page_needs_fewer_frames_in_format_2(self):
        magazin = json.loads((ROOT / "test" / "magazin.json").read_text(encoding="utf-8"))
        old, _ = make_station(wire_format=1)
        new, _ = make_station(wire_format=2)
        before = old.put("test", "magazin", magazin)
        after = new.put("test", "magazin", magazin)
        self.assertEqual((before["wire"], after["wire"]), (1, 2))
        self.assertTrue(after["packed"])
        self.assertLess(after["subpages"], before["subpages"])
        self.assertLess(sum(after["bytes"]), sum(before["bytes"]))
        self.assertLess(after["airtime_s"], before["airtime_s"])

    def test_default_exp_from_typ(self):
        st, store = make_station()
        st.put("wx", "a", WX)
        self.assertEqual(store.get_page("wx", "a").exp_min, 60)


class CarouselTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.clock = Clock()
        self.sent: list[bytes] = []
        self.online = True

        self.mono = 0.0                 # fake monotonic time, advanced by sleep()
        self.sent_at: list[float] = []
        self.waits: list[float] = []

        async def send(data: bytes) -> bool:
            if self.online:
                self.sent.append(data)
                self.sent_at.append(self.mono)
            return self.online

        async def sleep(s: float) -> None:
            self.waits.append(s)
            self.mono += s

        self.st, self.store = make_station(self.clock)
        self.car = Carousel(self.store, send, self.st.cfg.station, "OE3GAS-5", self.clock,
                            mono=lambda: self.mono, sleep=sleep)

    async def test_new_page_goes_out_at_once_then_with_gaps(self):
        self.st.put("wx", "a", {**WX, "exp": 1440})
        await self.car.step()
        self.assertEqual(len(self.sent), 1)
        self.assertIsNotNone(frame.parse(self.sent[0]))
        await self.car.step()
        self.assertEqual(len(self.sent), 1)               # not again right away
        for gap in (2, 5, 10, 30, 30):
            self.clock.t += gap * 60
            await self.car.step()
        self.assertEqual(len(self.sent), 6)

    def test_gap_grows_with_the_age_of_the_revision(self):
        cfg = self.st.cfg.station
        cfg.aging = [(24, 120), (168, 0)]
        self.assertEqual(self.car.gap_min(1), 2)                  # Staffel repeat_minutes
        self.assertEqual(self.car.gap_min(5, age_s=0), 30)        # danach max_interval_min
        self.assertEqual(self.car.gap_min(5, age_s=25 * 3600), 120)      # älter als 24 h
        self.assertEqual(self.car.gap_min(5, age_s=8 * 86400), 0)        # älter als 7 Tage: Pause

    async def test_old_page_rests_until_a_new_revision(self):
        cfg = self.st.cfg.station
        cfg.repeat_minutes, cfg.aging = [0], [(24, 0)]
        self.st.put("tinybox", "1_A", {**BULLETIN, "exp": 43200})
        await self.car.step()
        self.assertEqual(self.sent_pages_count(), 1)
        self.clock.t += 25 * 3600                                 # Revision ist alt geworden
        await self.car.step()
        self.assertEqual(self.sent_pages_count(), 2)              # dieses Mal noch
        row = self.store.get_page("tinybox", "1_A")
        self.assertEqual(row.next_tx, carousel_mod.RESTING)
        self.clock.t += 10 * 86400
        await self.car.step()
        self.assertEqual(self.sent_pages_count(), 2)              # ruht, nichts mehr auf Funk
        self.st.put("tinybox", "1_A", {**BULLETIN, "exp": 43200,
                                       "blk": [{"k": "para", "x": "Neuer Inhalt"}]})
        await self.car.step()
        self.assertEqual(self.sent_pages_count(), 3)              # neue Revision weckt die Seite

    def sent_pages_count(self) -> int:
        return self.car.sent_pages

    async def test_transmission_log(self):
        import tempfile
        from brocast.txlog import TxLog
        with tempfile.TemporaryDirectory() as tmp:
            self.car.txlog = TxLog(Path(tmp), "OE3GAS-5")
            n = self.st.put("tinybox", "12", BULLETIN)["subpages"]
            await self.car.step()
            self.st.delete("tinybox", "12")
            await self.car.step()
            files = list(Path(tmp).glob("Sendeprotokoll_*.txt"))
            self.assertEqual(len(files), 1)
            lines = files[0].read_text(encoding="utf-8").splitlines()
            entries = [l for l in lines if not l.startswith("#")]
            self.assertEqual(len(entries), n + 1)
            self.assertIn("OE3GAS-5", entries[0])
            self.assertIn("tinybox/12", entries[0])
            self.assertIn("DX-News KW 40", entries[0])
            self.assertIn(f" 1/{n}", entries[0])
            self.assertIn("[zurückgezogen]", entries[-1])
            self.assertTrue(entries[0][:20].endswith("Z"))          # UTC

    async def test_subpages_back_to_back(self):
        n = self.st.put("tinybox", "1_A", BULLETIN)["subpages"]
        await self.car.step()
        self.assertEqual(len(self.sent), n)

    async def test_split_into_transmissions(self):
        cfg = self.st.cfg.station
        cfg.burst_frames, cfg.burst_gap_s = 2, 3.0
        n = self.st.put("tinybox", "1_A", NOISE_BULLETIN)["subpages"]
        self.assertGreater(n, 2)
        await self.car.step()
        self.assertEqual(len(self.sent), n)
        self.assertEqual(len(self.waits), -(-n // 2) - 1)
        # each pause = computed time on air of the block (TXDELAY once) + gap
        block = frame.burst_airtime_s([len(f) for f in self.sent[:2]], cfg.baud, cfg.txdelay_ms)
        self.assertAlmostEqual(self.waits[0], block + 3.0, places=6)
        # frames 1+2 handed over together, frame 3 only after the pause
        self.assertEqual(self.sent_at[0], self.sent_at[1])
        self.assertAlmostEqual(self.sent_at[2] - self.sent_at[1], block + 3.0, places=6)

    async def test_split_off(self):
        self.st.cfg.station.burst_frames = 0
        n = self.st.put("tinybox", "1_A", BULLETIN)["subpages"]
        await self.car.step()
        self.assertEqual((len(self.sent), self.waits), (n, []))

    async def test_gap_also_between_pages(self):
        self.st.cfg.station.burst_frames = 4
        self.st.put("wx", "a", WX)
        await self.car.step()
        self.mono += 0.5                                # first transmission still on air
        self.st.put("wx", "b", WX)
        await self.car.step()
        self.assertEqual(self.waits, [])                # joins the running transmission
        self.mono += 30                                 # long over, gap passed
        self.st.put("wx", "c", WX)
        await self.car.step()
        self.assertEqual(self.waits, [])
        self.st.put("wx", "d", WX)
        self.mono += 0.05
        self.car._burst_end = self.mono - 1             # just ended: gap not yet over
        await self.car.step()
        self.assertEqual(len(self.waits), 1)
        self.assertAlmostEqual(self.waits[0], 2.0, places=6)

    def _agw_queue(self, answers: list[int | None]) -> None:
        """Direwolf's transmit queue as seen over AGW: one answer per query."""
        self.queries = 0

        async def queue_len():
            self.queries += 1
            return answers.pop(0) if answers else 0
        self.car.queue_len = queue_len

    async def test_agw_waits_for_empty_queue(self):
        from brocast import carousel as c
        cfg = self.st.cfg.station
        cfg.burst_frames, cfg.burst_gap_s = 2, 3.0
        self._agw_queue([2, 1, 0])          # channel busy: Direwolf still holds the block
        self.st.put("tinybox", "1_A", NOISE_BULLETIN)
        await self.car.step()
        # two polls with 0.5 s, then last frame on air + margin + gap
        last = frame.airtime_s(len(self.sent[1]), cfg.baud, 0)
        self.assertEqual(self.waits[:2], [c.QUEUE_POLL_S, c.QUEUE_POLL_S])
        self.assertAlmostEqual(self.waits[2], last + c.TX_MARGIN_S + 3.0, places=6)
        self.assertAlmostEqual(self.sent_at[2] - self.sent_at[1],
                               2 * c.QUEUE_POLL_S + last + c.TX_MARGIN_S + 3.0, places=6)

    async def test_agw_no_answer_falls_back_to_computed(self):
        cfg = self.st.cfg.station
        cfg.burst_frames, cfg.burst_gap_s = 2, 3.0
        self._agw_queue([None] * 20)
        self.st.put("tinybox", "1_A", NOISE_BULLETIN)
        await self.car.step()
        block = frame.burst_airtime_s([len(f) for f in self.sent[:2]], cfg.baud, cfg.txdelay_ms)
        self.assertAlmostEqual(self.waits[0], block + 3.0, places=6)

    async def test_agw_long_over_no_pause(self):
        self.st.cfg.station.burst_frames = 4
        self._agw_queue([])
        self.st.put("wx", "a", WX)
        await self.car.step()
        self.mono += 600                    # ten minutes later: queue empty, long over
        self.st.put("wx", "b", WX)
        await self.car.step()
        self.assertEqual((self.queries, self.waits), (1, []))

    def test_airtime_one_txdelay_per_transmission(self):
        lens = [270] * 8
        one = frame.airtime_s(270, 1200, 0)
        self.assertAlmostEqual(frame.tx_airtime_s(lens, 1200, 300, 4), 2 * 0.3 + 8 * one)
        self.assertAlmostEqual(frame.tx_airtime_s(lens, 1200, 300, 0), 0.3 + 8 * one)

    async def test_withdrawn_sent_then_removed(self):
        self.st.put("wx", "a", WX)
        await self.car.step()
        self.st.delete("wx", "a")
        for _ in range(3):
            await self.car.step()
            self.clock.t += 120
        self.assertIsNone(self.store.get_page("wx", "a"))
        self.assertEqual(len(self.sent), 4)

    async def test_airtime_budget(self):
        self.st.cfg.station.airtime_percent = 1          # 6 s per 10 min
        self.car.budget = AirtimeBudget(1, 600)
        for i in range(10):
            self.st.put("wx", f"s{i}", WX)
        await self.car.step()
        self.assertLess(len(self.sent), 10)
        self.clock.t += 601
        await self.car.step()
        self.assertGreater(len(self.sent), 6)

    async def test_emergency_ignores_budget(self):
        self.car.budget = AirtimeBudget(0.01, 600)
        self.st.put("wx", "a", WX)
        await self.car.step()
        self.st.put("notfunk", "b", {"typ": "alert", "pri": "emergency", "ti": "Notfall"})
        await self.car.step()
        self.assertEqual(len(self.sent), 2)

    async def test_expired_page_removed(self):
        self.st.put("wx", "a", {**WX, "exp": 10})
        self.clock.t += 11 * 60
        await self.car.step()
        self.assertIsNone(self.store.get_page("wx", "a"))

    async def test_offline_keeps_page_due(self):
        self.online = False
        self.st.put("wx", "a", WX)
        await self.car.step()
        self.assertEqual(self.store.get_page("wx", "a").tx_count, 0)
        self.online = True
        await self.car.step()
        self.assertEqual(len(self.sent), 1)


async def http(port: int, method: str, path: str, body: object = None,
               headers: dict[str, str] | None = None) -> tuple[int, object]:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    data = b"" if body is None else json.dumps(body).encode()
    hdrs = {"Host": f"127.0.0.1:{port}", "Content-Length": str(len(data))}
    if body is not None:
        hdrs["Content-Type"] = "application/json"
    hdrs.update(headers or {})
    head = f"{method} {path} HTTP/1.1\r\n" + "".join(f"{k}: {v}\r\n" for k, v in hdrs.items())
    writer.write(head.encode() + b"\r\n" + data)
    await writer.drain()
    raw = await reader.read()
    writer.close()
    status = int(raw.split(b" ", 2)[1])
    return status, json.loads(raw.split(b"\r\n\r\n", 1)[1])


class IngestTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.st, self.store = make_station()
        self.server = IngestServer(self.st, "127.0.0.1", 0, token="")
        await self.server.start()
        self.port = self.server.port

    async def asyncTearDown(self):
        await self.server.close()

    async def test_put_get_delete(self):
        status, res = await http(self.port, "PUT", "/api/v1/pages/tinybox/24657_OE3GAS",
                                 NOISE_BULLETIN)
        self.assertEqual(status, 200)
        self.assertGreater(res["subpages"], 1)
        status, res = await http(self.port, "GET", "/api/v1/pages/tinybox/24657_OE3GAS")
        self.assertEqual((status, res["key"]), (200, "24657_OE3GAS"))
        status, res = await http(self.port, "DELETE", "/api/v1/pages/tinybox/24657_OE3GAS")
        self.assertEqual((status, res["state"]), (200, "withdrawn"))

    async def test_errors(self):
        cases = [
            ("PUT", "/api/v1/pages/wx/a", {"typ": "wx", "dat": {"sonne": 1}}, {}, 400),
            ("GET", "/api/v1/pages/wx/fehlt", None, {}, 404),
            ("PATCH", "/api/v1/pages/wx/a", None, {}, 405),
            ("GET", "/api/v1/status", None, {"Host": "evil.example:80"}, 403),
            ("PUT", "/api/v1/pages/wx/a", WX, {"Content-Type": "text/plain"}, 415),
            ("PUT", "/api/v1/pages/tinybox/x",                  # mehr als max_subpages
             {**BULLETIN, "blk": [{"k": "para", "x": noise(14000)}]}, {}, 413),
        ]
        for method, path, body, headers, expected in cases:
            with self.subTest(method=method, path=path):
                status, _ = await http(self.port, method, path, body, headers)
                self.assertEqual(status, expected)

    async def test_token(self):
        self.server.token = "geheim"
        status, _ = await http(self.port, "GET", "/api/v1/status")
        self.assertEqual(status, 401)
        status, _ = await http(self.port, "GET", "/api/v1/status",
                               headers={"X-Brocast-Token": "geheim"})
        self.assertEqual(status, 200)

    async def test_sync_and_validate_and_dictionary(self):
        status, res = await http(self.port, "PUT", "/api/v1/pages/tinybox",
                                 {"pages": {"1_A": BULLETIN}})
        self.assertEqual((status, list(res["pages"])), (200, ["1_A"]))
        status, res = await http(self.port, "POST", "/api/v1/validate", WX)
        self.assertEqual((status, res["subpages"]), (200, 1))
        self.assertEqual(self.store.list_pages(), self.store.list_pages("tinybox"))  # dry run
        status, res = await http(self.port, "GET", "/api/v1/dictionary")
        self.assertIn("wx", res["types"])
        self.assertNotIn("formreply", res["enums"]["typ"])


class ReceiveLogTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.d = Daemon(make_cfg("listener", ""), db_path=":memory:")
        self.codec = Codec()

    def send(self, page, src="OE3GAS-5"):
        self.d.on_frame(0, frame.build(src, self.codec.encode(page)))

    async def test_results_are_logged(self):
        page = {"id": 24, "rev": 0, "t": T0, "typ": "text", "ti": "Test"}
        self.send(page)
        self.send(page)                                         # carousel repeat
        self.send({**page, "rev": 1})
        self.d.on_frame(0, ax25.UIFrame(dest="APDW16", src="OE3XYZ-9", info=b"!4812.34N").encode())
        self.d.on_frame(0, frame.build("OE3GAS-5", b"\xff\xff"))  # broken CBOR
        log = self.d.listener.rxlog()
        self.assertEqual([e["result"] for e in log], ["error", "foreign", "updated", "repeat", "new"])
        self.assertEqual(log[1]["heard_from"], "OE3XYZ-9")
        self.assertEqual(log[1]["dest"], "APDW16")
        self.assertTrue(log[3]["visible_now"])
        self.assertIn("schon vorhanden", log[3]["text"])
        self.assertEqual([e["chip"] for e in log],
                         ["Nicht dekodierbar", "anderer Frame", "Neuer Inhalt", "Wiederholung",
                          "Neuer Inhalt"])
        self.assertEqual(log[3]["kind"], "repeat")
        only = self.d.listener.rxlog(brocast_only=True)
        self.assertNotIn("foreign", [e["result"] for e in only])
        self.assertEqual(len(self.d.listener.rxlog(org="OE3GAS-5", page_id=24)), 3)

    async def test_log_is_pruned(self):
        for i in range(20):
            self.send({"id": i + 1, "t": T0, "typ": "text"})
        self.d.store.prune_rxlog(keep=5)
        self.assertEqual(len(self.d.listener.rxlog()), 5)

    async def test_airtime_estimate(self):
        page = {"id": 24, "rev": 0, "t": T0, "typ": "text", "ti": "Test"}
        self.send(page)
        self.assertGreater(self.d.listener.page("OE3GAS-5", 24)["airtime_s"], 0.3)


class FakeDirewolf:
    """KISS and AGW server that relays every frame to all other clients, like
    the air. AGW: 'R' version, 'k' raw frames on, 'K' send, 'y' queue length."""

    def __init__(self):
        self.clients: list[list] = []            # [writer, "kiss"|"agw", raw_on]
        self.frames: list[bytes] = []
        self.queue = 0                           # answer to 'y'
        self.y_queries = 0

    async def start(self) -> int:
        self.server = await asyncio.start_server(self._kiss_client, "127.0.0.1", 0)
        self.agw_server = await asyncio.start_server(self._agw_client, "127.0.0.1", 0)
        self.agw_port = self.agw_server.sockets[0].getsockname()[1]
        return self.server.sockets[0].getsockname()[1]

    def _relay(self, sender, channel: int, data: bytes) -> None:
        self.frames.append(data)
        for other, proto, raw_on in self.clients:
            if other is sender:
                continue
            if proto == "kiss":
                other.write(kiss.encode(data, channel))
            elif raw_on:
                other.write(agw.pack("K", channel, b"\x00" + data))

    async def _kiss_client(self, reader, writer):
        self.clients.append([writer, "kiss", False])
        dec = kiss.Decoder()
        while chunk := await reader.read(4096):
            for channel, data in dec.feed(chunk):
                self._relay(writer, channel, data)

    async def _agw_client(self, reader, writer):
        entry = [writer, "agw", False]
        self.clients.append(entry)
        try:
            while True:
                port, kind, length = agw.unpack_header(await reader.readexactly(agw.HEADER.size))
                data = await reader.readexactly(length) if length else b""
                if kind == "k":
                    entry[2] = not entry[2]
                elif kind == "R":
                    writer.write(agw.pack("R", 0, (1).to_bytes(4, "little") + (7).to_bytes(4, "little")))
                elif kind == "y":
                    self.y_queries += 1
                    writer.write(agw.pack("y", port, self.queue.to_bytes(4, "little")))
                elif kind == "K":
                    self._relay(writer, port, data[1:])
        except asyncio.IncompleteReadError:
            pass

    async def close(self):
        for w, _, _ in self.clients:
            w.close()
        self.server.close()
        self.agw_server.close()


class EndToEndTests(unittest.IsolatedAsyncioTestCase):
    async def test_station_to_listener_kiss(self):
        dw = await self._run("kiss", "kiss", burst_frames=0)     # no real pauses here
        self.assertEqual(dw.y_queries, 0)

    async def test_station_to_listener_format_1(self):
        """Das alte Format (eine Seite je Frame) muss weiter durchgehen."""
        await self._run("kiss", "kiss", burst_frames=0, wire_format=1)

    async def test_station_agw_listener_kiss_with_pauses(self):
        # fast "radio" so the real pauses stay short: 2 frames per block, 0.1 s gap.
        # NOISE_BULLETIN lässt sich kaum packen, geht also über mehrere Frames.
        dw = await self._run("agw", "kiss", page=NOISE_BULLETIN, burst_frames=2,
                             burst_gap_s=0.1, baud=1_000_000, dict_broadcast_hours=0)
        self.assertGreater(dw.y_queries, 0)                       # pauses via Direwolf's queue

    async def test_listener_over_agw(self):
        await self._run("kiss", "agw", burst_frames=0)

    async def _run(self, st_iface: str, li_iface: str, page: dict | None = None,
                   **station) -> "FakeDirewolf":
        dw = FakeDirewolf()
        port = await dw.start()
        st_cfg = make_cfg("station", "OE3GAS-5", **station)
        li_cfg = make_cfg("listener", "")
        for cfg, iface in ((st_cfg, st_iface), (li_cfg, li_iface)):
            cfg.direwolf.interface = iface
            cfg.direwolf.kiss_port, cfg.direwolf.agw_port = port, dw.agw_port
        station = Daemon(st_cfg, db_path=":memory:")
        listener = Daemon(li_cfg, db_path=":memory:")
        tasks = [asyncio.create_task(station.run()), asyncio.create_task(listener.run())]
        try:
            for _ in range(50):
                if station.link.connected.is_set() and listener.link.connected.is_set() \
                        and station.ingest.server:
                    break
                await asyncio.sleep(0.05)
            sent = page or BULLETIN
            status, res = await http(station.ingest.port, "PUT",
                                     "/api/v1/pages/tinybox/24657_OE3GAS", sent)
            self.assertEqual(status, 200)
            # Format 2 setzt die Fragmente beim Empfänger zu einer Seite zusammen,
            # Format 1 legt jede Unterseite einzeln ab
            rows_expected = 1 if res["wire"] == 2 else res["subpages"]
            self.assertGreater(res["subpages"], 1 if page is NOISE_BULLETIN else 0)
            for _ in range(100):
                if len(listener.store.received()) == rows_expected:
                    break
                await asyncio.sleep(0.05)
            rows = listener.store.received()
            self.assertEqual(len(rows), rows_expected)
            self.assertEqual({r["org"] for r in rows}, {"OE3GAS-5"})
            self.assertEqual(rows[0]["sub_total"], rows_expected)
            got = Codec().decode(rows[0]["data"])
            self.assertEqual(got["ti"], sent["ti"])
            self.assertEqual(got["blk"][0]["x"], sent["blk"][0]["x"])     # Inhalt kam heil an
            # the station shows its own pages in its own listener
            self.assertEqual(len(station.store.received()), rows_expected)
            self.assertEqual(station.rx_pages, 0)          # but did not "receive" them
            # the listener API shows the assembled page
            status, shown = await http(listener.web.port, "GET",
                                       f"/api/v1/pages/OE3GAS-5/{res['id']}")
            self.assertEqual((status, shown["ti"], shown["sub_present"]),
                             (200, sent["ti"], rows_expected))
            if res["wire"] == 2:
                # die echte Funkgröße, nicht die der entpackten Seite
                self.assertEqual(shown["wire_frames"], res["subpages"])
                self.assertGreaterEqual(shown["wire_bytes"], sum(res["bytes"]))
                self.assertGreater(shown["airtime_s"], 0)
            # an APRS packet on the same frequency is ignored by the listener
            self.assertEqual(listener.rx_errors, 0)
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await dw.close()
        return dw


if __name__ == "__main__":
    unittest.main()
