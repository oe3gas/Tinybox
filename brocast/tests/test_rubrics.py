"""Rubric index: providers declare their rubrics (TinyBox [rubrics]) via the
ingest sync, the station sends them as an index page (typ index), the
listener knows the rubrics before their first page and drops removed ones."""

from __future__ import annotations

import unittest

from brocast import fragment, frame, zdict
from brocast.codec import Codec
from brocast.listener import Listener
from brocast.station import INDEX_KEY, INDEX_PROVIDER, BrocastError
from brocast.store import Store
from tests.test_daemon import BULLETIN, Clock, make_station

ST = "OE3GAS-5"
RUBRICS = [{"name": "ALL", "cat": "all", "desc": "To everybody"},
           {"name": "WX", "cat": "wx", "desc": "Wetter und Warnungen"},
           {"name": "FUCHS", "cat": "FUCHS", "desc": "Fuchsjagd"}]


class StationIndexTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.st, self.store = make_station(self.clock)

    def index(self):
        return self.store.get_page(INDEX_PROVIDER, INDEX_KEY)

    def test_sync_without_rubrics_leaves_them_alone(self):
        res = self.st.sync("tinybox", {"1": BULLETIN})
        self.assertNotIn("rubrics", res)
        self.assertIsNone(self.index())

    def test_declared_rubrics_become_an_index_page(self):
        res = self.st.sync("tinybox", {}, RUBRICS)
        self.assertEqual(res["rubrics"]["count"], 3)
        self.assertEqual(res["rubrics"]["index"]["changed"], True)
        content = self.st.index_content()
        self.assertEqual(content["typ"], "index")
        # dictionary rubrics as numbers, own rubric as text; description beside it
        self.assertEqual(content["dat"][0], [[0, "To everybody"], [2, "Wetter und Warnungen"],
                                             ["FUCHS", "Fuchsjagd"]])
        self.assertEqual(self.st.rubrics()[2], {"provider": "tinybox", "name": "FUCHS",
                                                "cat": "FUCHS", "desc": "Fuchsjagd"})

    def test_same_list_no_new_revision(self):
        self.st.sync("tinybox", {}, RUBRICS)
        self.clock.t += 3600
        res = self.st.sync("tinybox", {}, list(RUBRICS))
        self.assertEqual((res["rubrics"]["index"]["changed"], res["rubrics"]["index"]["rev"]),
                         (False, 0))

    def test_changed_list_new_revision_and_empty_list_withdraws(self):
        self.st.sync("tinybox", {}, RUBRICS)
        res = self.st.sync("tinybox", {}, RUBRICS[:2])
        self.assertEqual(res["rubrics"]["index"]["rev"], 1)
        res = self.st.sync("tinybox", {}, [])
        self.assertIsNone(res["rubrics"]["index"])
        self.assertEqual(self.index().state, "withdrawn")

    def test_two_providers_are_merged(self):
        self.st.sync("tinybox", {}, RUBRICS)
        self.st.sync("wx", {}, [{"name": "WX", "cat": "wx"}, {"name": "SOTA", "cat": "sota"}])
        self.assertEqual([e[0] for e in self.st.index_content()["dat"][0]], [0, 2, "FUCHS", 7])

    def test_bad_rubrics(self):
        for bad in ("nix", [{"cat": "wx"}], [{"name": "X", "cat": "x" * 21}],
                    [{"name": "", "cat": "wx"}]):
            with self.subTest(bad=bad), self.assertRaises(BrocastError):
                self.st.sync("tinybox", {}, bad)
        with self.assertRaises(BrocastError):
            self.st.sync(INDEX_PROVIDER, {}, [])

    def test_description_is_cut(self):
        self.st.sync("tinybox", {}, [{"name": "ALL", "cat": "all", "desc": "x" * 100}])
        self.assertEqual(len(self.st.index_content()["dat"][0][0][1]), 60)


class ListenerIndexTests(unittest.TestCase):
    """The index page over the air (frame format 2) and what the listener does with it."""

    def setUp(self):
        self.clock = Clock()
        self.codec = Codec()
        self.zd = zdict.load()
        self.st, self.sstore = make_station(self.clock)
        self.st.zd = self.zd
        self.store = Store(":memory:")
        self.li = Listener(self.store, self.codec, self.clock)
        self.asm = fragment.Assembler(self.zd)

    def on_air(self, provider: str, key: str) -> str:
        """Send a station page to the listener like the daemon would."""
        row = self.sstore.get_page(provider, key)
        result = "none"
        for payload in self.sstore.frames(row.pid):
            data = frame.build(ST, payload, None, row.hdr)
            parsed = frame.parse(data)
            feed = self.asm.feed(ST, parsed.payload, parsed.flags, len(data))
            if feed.status == "page":
                page = self.codec.decode(feed.page, ax25_src=ST, defaults=False)
                result = self.li.on_page(page, feed.page, ST)
        return result

    def declare(self, rubrics, provider="tinybox"):
        self.st.sync(provider, {}, rubrics)
        return self.on_air(INDEX_PROVIDER, INDEX_KEY)

    def keys(self, rows):
        return [r["key"] for r in rows]

    def test_index_page_is_not_a_page_but_announces_rubrics(self):
        self.assertEqual(self.declare(RUBRICS), "index")
        self.assertEqual(self.li.list_pages(), [])
        rubrics = {r["key"]: r for r in self.li.all_rubrics()}
        self.assertEqual((rubrics["x:fuchs"]["name"], rubrics["x:fuchs"]["desc"],
                          rubrics["x:fuchs"]["stations"]), ("FUCHS", "Fuchsjagd", [ST]))
        self.assertEqual(rubrics["wx"]["desc"], "Wetter und Warnungen")
        # the empty rubric shows up in the overview, with its description
        cats = {c["key"]: c for c in self.li.categories()}
        self.assertEqual((cats["x:fuchs"]["total"], cats["x:fuchs"]["desc"],
                          cats["x:fuchs"]["declared"]), (0, "Fuchsjagd", True))
        self.assertEqual(self.li.categories(station=ST)[0]["declared"], True)
        self.assertEqual(self.li.categories(station="OE1XYZ-5"), [])

    def test_repeat_and_old_revision(self):
        self.declare(RUBRICS)
        self.clock.t += 7200
        self.assertEqual(self.on_air(INDEX_PROVIDER, INDEX_KEY), "index_same")
        self.assertEqual(self.store.station_rubrics(ST)[0]["seen"], int(self.clock()))
        old = self.sstore.frames(self.sstore.get_page(INDEX_PROVIDER, INDEX_KEY).pid)
        self.assertEqual(self.declare(RUBRICS[:2]), "index")
        # an older revision heard afterwards changes nothing
        data = frame.build(ST, old[0], None, 32)
        parsed = frame.parse(data)
        feed = self.asm.feed(ST, parsed.payload, parsed.flags, len(data))
        page = self.codec.decode(feed.page, ax25_src=ST, defaults=False)
        self.assertEqual(self.li.on_page(page, feed.page, ST), "index_old")
        self.assertNotIn("x:fuchs", self.keys(self.li.all_rubrics()))

    def test_removed_rubric_goes_with_its_last_page(self):
        self.declare(RUBRICS)
        self.st.put("tinybox", "7", {**BULLETIN, "cat": ["FUCHS"]})
        self.assertEqual(self.on_air("tinybox", "7"), "new")
        self.li.set_optouts([{"station": "*", "cat": "FUCHS"}])
        self.assertEqual(self.declare(RUBRICS[:2]), "index")
        # still there: a page carries it – but marked as withdrawn by the station
        cats = {c["key"]: c for c in self.li.categories()}
        self.assertEqual((cats["x:fuchs"]["withdrawn"], cats["x:fuchs"]["declared"]),
                         (True, False))
        self.assertEqual(self.li.optouts(), [{"station": "*", "cat": "x:fuchs"}])
        self.st.delete("tinybox", "7")
        self.assertEqual(self.on_air("tinybox", "7"), "withdrawn")
        self.li.housekeeping()
        self.assertNotIn("x:fuchs", self.keys(self.li.all_rubrics()))
        self.assertEqual(self.li.optouts(), [])        # the opt-out line went with it

    def test_withdrawn_index_clears_the_announcement(self):
        self.declare(RUBRICS)
        self.st.sync("tinybox", {}, [])                # TinyBox without [rubrics] again
        self.assertEqual(self.on_air(INDEX_PROVIDER, INDEX_KEY), "index")
        self.assertEqual(self.store.station_rubrics(ST), [])
        self.assertNotIn("x:fuchs", self.keys(self.li.all_rubrics()))

    def test_opted_out_empty_rubric_stays_out_of_the_overview(self):
        self.declare(RUBRICS)
        self.li.set_optouts([{"station": "*", "cat": "FUCHS"}])
        self.assertNotIn("x:fuchs", self.keys(self.li.categories()))
        self.assertIn("x:fuchs", self.keys(self.li.all_rubrics()))   # matrix: can re-select

    def test_old_stored_index_pages_are_dropped(self):
        self.store.save_lpage({"org": ST, "id": 99, "rev": 0, "t": int(self.clock()),
                               "typ": "index", "ti": "Rubriken", "cats": "[]", "cat_key": "all",
                               "pri": 0, "alert": 0, "exp_min": None, "sub_total": 1,
                               "wire_frames": 0, "wire_bytes": 0, "status": "unread",
                               "updated": 0, "favorite": 0, "deleted_rev": None,
                               "first_seen": 0, "last_seen": int(self.clock()), "search": ""})
        self.assertEqual(self.li.housekeeping(), 1)


if __name__ == "__main__":
    unittest.main()
