"""M2 tests: listener logic (page states, subscriptions, limits) and its JSON API."""

from __future__ import annotations

import asyncio
import unittest

from brocast.codec import Codec
from brocast.listener import Listener, ListenerError, NotFound
from brocast.listener_api import ListenerApi
from brocast.splitter import split
from brocast.store import Store
from tests.test_daemon import LONG_TEXT, T0, Clock, http

ST = "OE3GAS-5"


class Base(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.codec = Codec()
        self.store = Store(":memory:")
        self.li = Listener(self.store, self.codec, self.clock)

    def rx(self, page_id=24, rev=0, src=ST, subs=None, **fields):
        """Receive a page (all subpages, or only those listed in subs)."""
        page = {"id": page_id, "rev": rev, "t": int(self.clock()), "typ": "text",
                "ti": f"Seite {page_id}", **fields}
        frames = split(self.codec, page)
        results = []
        for n, data in enumerate(frames, start=1):
            if subs is None or n in subs:
                results.append(self.li.on_page(self.codec.decode(data, defaults=False),
                                               data, src))
        return results[-1] if len(results) == 1 else results

    def visible(self):
        return [(p["org"], p["id"]) for p in self.li.list_pages()]


class PageStateTests(Base):
    def test_new_page_is_unread_and_opening_marks_read(self):
        self.assertEqual(self.rx(), "new")
        self.assertEqual(self.li.list_pages()[0]["status"], "unread")
        self.li.page(ST, 24)
        self.assertEqual(self.li.list_pages()[0]["status"], "read")

    def test_peek_does_not_mark_read(self):
        self.rx()
        self.li.page(ST, 24, mark_read=False)
        self.assertEqual(self.li.list_pages()[0]["status"], "unread")

    def test_new_revision_unread_and_updated(self):
        self.rx()
        self.li.page(ST, 24)
        self.clock.t += 60
        self.assertEqual(self.rx(rev=1, ti="neu"), "updated")
        p = self.li.list_pages()[0]
        self.assertEqual((p["status"], p["updated"], p["ti"], p["rev"]), ("unread", True, "neu", 1))
        self.li.page(ST, 24)
        self.assertFalse(self.li.list_pages()[0]["updated"])

    def test_repeat_and_old_revision(self):
        self.rx(rev=2)
        self.assertEqual(self.rx(rev=2), "repeat")
        self.assertEqual(self.rx(rev=1), "old")

    def test_subpages_assembled_and_missing_marked(self):
        blk = [{"k": "para", "x": LONG_TEXT}]
        results = self.rx(blk=blk, subs={1, 3})
        self.assertEqual(results, ["new", "subpage"])
        page = self.li.page(ST, 24)
        self.assertGreater(page["sub_total"], 3)
        self.assertEqual(page["sub_present"], 2)
        kinds = [b["k"] for b in page["blocks"]]
        self.assertEqual(kinds[:3], ["para", "missing", "para"])
        self.assertEqual(page["blocks"][1]["sub"], 2)

    def test_new_revision_drops_old_subpages(self):
        self.rx(blk=[{"k": "para", "x": LONG_TEXT}])
        self.rx(rev=1, ti="kurz")
        self.assertEqual(len(self.store.subpages(ST, 24)), 1)
        self.assertEqual(self.li.page(ST, 24)["sub_total"], 1)

    def test_withdrawn_removes_whole_page(self):
        self.rx(blk=[{"k": "para", "x": LONG_TEXT}])
        self.assertEqual(self.rx(rev=1, flg=["withdrawn"]), "withdrawn")
        self.assertEqual(self.visible(), [])
        self.assertEqual(self.store.subpages(ST, 24), [])

    def test_user_delete_until_newer_revision(self):
        self.rx()
        self.li.delete(ST, 24)
        self.assertEqual(self.visible(), [])
        self.assertEqual(self.rx(), "deleted")              # carousel repeat
        self.assertEqual(self.visible(), [])
        self.assertEqual(self.rx(rev=1), "new")
        p = self.li.list_pages()[0]
        self.assertEqual((p["rev"], p["status"], p["updated"]), (1, "unread", False))

    def test_actions_on_missing_page(self):
        for action in (lambda: self.li.page(ST, 99), lambda: self.li.delete(ST, 99),
                       lambda: self.li.set_read(ST, 99, True)):
            with self.assertRaises(NotFound):
                action()

    def test_mark_unread_and_favorite(self):
        self.rx()
        self.li.page(ST, 24)
        self.assertEqual(self.li.set_read(ST, 24, False)["status"], "unread")
        self.assertTrue(self.li.set_favorite(ST, 24, True)["favorite"])
        with self.assertRaises(ListenerError):
            self.li.set_favorite(ST, 24, "ja")


class DictionaryVersionTests(Base):
    def test_current_version_is_fine(self):
        self.rx()
        self.assertFalse(self.li.status()["dictionary"]["outdated"])
        self.assertFalse(self.li.page(ST, 24)["dict_newer"])

    def test_newer_version_heard(self):
        v = self.li.d.version                                        # installed version
        self.rx(page_id=1)
        self.rx(page_id=2, src="OE3XYZ-5", dv=v + 1)
        d = self.li.status()["dictionary"]
        self.assertEqual((d["outdated"], d["local"], d["newest_heard"], d["heard_from"]),
                         (True, v, v + 1, "OE3XYZ-5"))
        self.assertTrue(self.li.page("OE3XYZ-5", 2)["dict_newer"])   # page still shown
        self.rx(page_id=3, src="OE1ABC-5", dv=v + 2)
        self.rx(page_id=4, src="OE3XYZ-5", dv=v + 1)                 # lower: keeps newest
        self.assertEqual(self.li.status()["dictionary"]["newest_heard"], v + 2)


class AnnouncementCleanupTests(Base):
    def test_old_dictionary_pages_removed(self):
        self.store.save_lpage({"org": ST, "id": 28, "rev": 0, "t": T0, "typ": "dict",
                               "ti": "Dictionary v1", "cats": "[]", "cat_key": "all",
                               "pri": 0, "alert": 0, "exp_min": 10080, "sub_total": 1,
                               "status": "unread", "updated": 0, "favorite": 0,
                               "deleted_rev": None, "first_seen": T0, "last_seen": T0,
                               "search": ""})
        self.li.housekeeping()
        self.assertEqual(self.visible(), [])


class ExpiryAndLimitTests(Base):
    def test_expired_page_removed_favorite_kept(self):
        self.rx(page_id=1, exp=10)
        self.rx(page_id=2, exp=10)
        self.li.set_favorite(ST, 2, True)
        self.clock.t += 11 * 60
        self.assertEqual(self.li.housekeeping(), 1)
        self.assertEqual(self.visible(), [(ST, 2)])
        self.assertTrue(self.li.list_pages()[0]["expired"])

    def test_default_exp_from_typ(self):
        self.rx(typ="dx")                                  # dx: 30 min
        self.clock.t += 31 * 60
        self.li.housekeeping()
        self.assertEqual(self.visible(), [])

    def test_max_age(self):
        self.li.set_settings({"max_age_days": 1})
        self.rx(exp=100_000)
        self.clock.t += 2 * 86400
        self.li.housekeeping()
        self.assertEqual(self.visible(), [])

    def test_limit_per_rubric_evicts_oldest_read_first(self):
        self.li.set_settings({"max_pages_per_cat": 3})
        for i in range(1, 4):
            self.rx(page_id=i, cat=["dx"])
            self.clock.t += 60
        self.li.page(ST, 2)                                # read
        self.li.set_favorite(ST, 1, True)
        self.rx(page_id=4, cat=["dx"])
        self.assertEqual(sorted(i for _, i in self.visible()), [1, 3, 4])
        self.rx(page_id=5, cat=["wx"])                     # other rubric: no effect
        self.assertEqual(len(self.visible()), 4)

    def test_limit_total(self):
        self.li.set_settings({"max_pages_total": 10})
        for i in range(1, 13):
            self.rx(page_id=i, cat=["dx" if i % 2 else "wx"])
            self.clock.t += 60
        self.assertEqual(sorted(i for _, i in self.visible()), list(range(3, 13)))

    def test_settings_validation(self):
        for bad in ({"max_pages_total": 0}, {"lang": "fr"}, {"x": 1},
                    {"alert_sound": "ja"}, {"max_age_days": True}, []):
            with self.subTest(bad=bad), self.assertRaises(ListenerError):
                self.li.set_settings(bad)
        self.assertEqual(self.li.set_settings({"lang": "en"})["lang"], "en")


class SubscriptionTests(Base):
    def test_optout_station(self):
        self.li.set_optouts([{"station": "OE3XYZ-5", "cat": "*"}])
        self.assertEqual(self.rx(src="OE3XYZ-5"), "blocked")
        self.assertEqual(self.rx(src=ST), "new")

    def test_optout_rubric_all_stations(self):
        self.li.set_optouts([{"station": "*", "cat": "sale"}])
        self.assertEqual(self.rx(page_id=1, cat=["sale"]), "blocked")
        self.assertEqual(self.rx(page_id=2, cat=["sale", "tech"]), "new")  # one rubric left

    def test_optout_station_rubric(self):
        self.li.set_optouts([{"station": "OE3XYZ-5", "cat": "dx"}])
        self.assertEqual(self.rx(page_id=1, src="OE3XYZ-5", cat=["dx"]), "blocked")
        self.assertEqual(self.rx(page_id=2, src=ST, cat=["dx"]), "new")

    def test_alert_always_passes(self):
        self.li.set_optouts([{"station": ST, "cat": "*"}])
        self.assertEqual(self.rx(typ="alert", ti="Unwetter"), "new")
        self.assertEqual(self.rx(page_id=25, pri="emergency"), "new")
        self.assertTrue(all(p["alert"] for p in self.li.list_pages()))

    def test_cannot_opt_out_of_everything(self):
        with self.assertRaises(ListenerError):
            self.li.set_optouts([{"station": "*", "cat": "*"}])

    def test_new_station_is_received(self):
        self.assertEqual(self.rx(src="OE1NEU-5"), "new")
        self.assertEqual(self.li.stations()[0]["call"], "OE1NEU-5")
        self.assertTrue(self.li.stations()[0]["subscribed"])


class RubricAndSearchTests(Base):
    def test_custom_rubrics_merge_case_insensitive(self):
        self.rx(page_id=1, src="OE3GAS-5", cat=["Fuchsjagd"])
        self.rx(page_id=2, src="OE3XYZ-5", cat=["fuchsjagd"])
        self.rx(page_id=3, cat=["dx"])
        self.rx(page_id=4)
        cats = {c["key"]: c for c in self.li.categories()}
        self.assertEqual(cats["x:fuchsjagd"]["total"], 2)
        self.assertTrue(cats["x:fuchsjagd"]["custom"])
        self.assertEqual(cats["all"]["name"], "Allgemein")
        self.assertEqual(cats["dx"]["name"], "DX")
        self.assertEqual(len(self.li.list_pages(cat="Fuchsjagd")), 2)

    def test_page_in_two_rubrics(self):
        self.rx(cat=["dx", "contest"])
        self.assertEqual({c["key"] for c in self.li.categories()}, {"dx", "contest"})
        self.assertEqual(len(self.li.list_pages(cat="contest")), 1)

    def test_views_station_and_rubric(self):
        self.rx(page_id=1, src="OE3GAS-5", cat=["dx"])
        self.rx(page_id=2, src="OE3XYZ-5", cat=["wx"])
        self.assertEqual([c["key"] for c in self.li.categories(station="OE3XYZ-5")], ["wx"])
        self.assertEqual([s["call"] for s in self.li.stations(cat="dx")], ["OE3GAS-5"])
        self.assertEqual(len(self.li.list_pages(station="OE3GAS-5", cat="dx")), 1)

    def test_search(self):
        self.rx(page_id=1, blk=[{"k": "para", "x": "3B8 ist QRV auf 20 m"}])
        self.rx(page_id=2, typ="wx", dat={"temp": 12.5})
        self.assertEqual([p["id"] for p in self.li.list_pages(q="3b8 qrv")], [1])
        self.assertEqual([p["id"] for p in self.li.list_pages(q="12.5")], [2])

    def test_weather_data_with_labels(self):
        self.rx(typ="wx", dat={"temp": 12.5, "qnh": 1013.2})
        data = {d["key"]: d for d in self.li.page(ST, 24)["data"]}
        self.assertEqual((data["temp"]["label"], data["temp"]["value"], data["temp"]["unit"]),
                         ("Lufttemperatur", 12.5, "°C"))

    def test_raw_view(self):
        self.rx()
        raw = self.li.page(ST, 24, raw=True)["raw"]
        self.assertEqual(raw[0]["sub"], 1)
        self.assertTrue(raw[0]["hex"].startswith("a"))      # CBOR map


class ListenerApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.base = Base()
        self.base.setUp()
        self.api = ListenerApi(self.base.li, "127.0.0.1", 0)
        await self.api.start()
        self.port = self.api.port
        self.base.rx(page_id=24, cat=["dx"])
        self.base.rx(page_id=25, typ="wx", dat={"temp": 12.5})

    async def asyncTearDown(self):
        await self.api.close()

    async def call(self, method, path, body=None, client=True):
        headers = {"X-Brocast-Client": "1"} if client else {}
        return await http(self.port, method, "/api/v1" + path, body, headers)

    async def test_reading(self):
        status, cats = await self.call("GET", "/categories")
        self.assertEqual((status, {c["key"] for c in cats}), (200, {"dx", "all"}))
        status, pages = await self.call("GET", "/pages?cat=dx")
        self.assertEqual([p["id"] for p in pages], [24])
        status, page = await self.call("GET", f"/pages/{ST}/25")
        self.assertEqual(page["data"][0]["label"], "Lufttemperatur")
        status, pages = await self.call("GET", "/pages?unread=1")
        self.assertEqual([p["id"] for p in pages], [24])
        status, st = await self.call("GET", "/status")
        self.assertEqual((st["pages"], st["unread"]), (2, 1))

    async def test_actions(self):
        status, res = await self.call("POST", f"/pages/{ST}/24/favorite", {"favorite": True})
        self.assertEqual((status, res["favorite"]), (200, True))
        status, res = await self.call("POST", f"/pages/{ST}/24/read", {"read": True})
        self.assertEqual(res["status"], "read")
        status, _ = await self.call("DELETE", f"/pages/{ST}/24")
        self.assertEqual(status, 200)
        status, _ = await self.call("GET", f"/pages/{ST}/24")
        self.assertEqual(status, 404)

    async def test_settings_and_subscriptions(self):
        status, s = await self.call("PUT", "/settings", {"max_pages_per_cat": 50})
        self.assertEqual((status, s["max_pages_per_cat"]), (200, 50))
        status, _ = await self.call("PUT", "/settings", {"max_pages_per_cat": "viel"})
        self.assertEqual(status, 400)
        status, s = await self.call("PUT", "/subscriptions",
                                    {"optout": [{"station": "*", "cat": "Fuchsjagd"}]})
        self.assertEqual(s["optout"], [{"station": "*", "cat": "x:fuchsjagd"}])

    async def test_write_needs_client_header(self):
        status, _ = await self.call("DELETE", f"/pages/{ST}/24", client=False)
        self.assertEqual(status, 403)
        status, _ = await self.call("GET", "/pages", client=False)    # reading is fine
        self.assertEqual(status, 200)

    async def test_gui_files_with_security_headers(self):
        for path, ctype in (("/", "text/html"), ("/app.js", "text/javascript"),
                            ("/app.css", "text/css")):
            with self.subTest(path=path):
                reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
                writer.write(f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{self.port}\r\n\r\n".encode())
                await writer.drain()
                raw = (await reader.read()).decode("utf-8")
                writer.close()
                head = raw.split("\r\n\r\n", 1)[0]
                self.assertIn("200 OK", head)
                self.assertIn(f"Content-Type: {ctype}", head)
                self.assertIn("script-src 'self'", head)
                self.assertIn("X-Frame-Options: DENY", head)

    async def test_gui_never_uses_innerhtml(self):
        from brocast.listener_api import WEB_DIR
        js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
        for bad in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
            self.assertNotIn(bad, js)

    async def test_rubrics_for_matrix(self):
        status, rubrics = await self.call("GET", "/rubrics")
        keys = [r["key"] for r in rubrics]
        self.assertEqual(keys[:2], ["all", "dx"])
        self.assertIn("sale", keys)                     # dictionary rubric without pages

    async def test_bad_requests(self):
        for method, path, expected in (("GET", f"/pages/{ST}/abc", 404),
                                       ("GET", "/unbekannt", 404),
                                       ("PATCH", "/settings", 405)):
            with self.subTest(path=path):
                status, _ = await self.call(method, path)
                self.assertEqual(status, expected)


if __name__ == "__main__":
    unittest.main()


class DxSummaryViewTests(Base):
    """Dictionary v4: the data block becomes page data with display texts."""

    def test_data_block_with_texts(self):
        self.rx(page_id=412, typ="dxsum", cat=["dx"], blk=[{"k": "data", "v": {
            "end": T0, "calls": 2, "st": [["A", "6O2M", "T5", 13, 40, 300, 10, 0, 0, 64, 128, ["RTTY"]],
                                         ["B", "X1ABC", "Neuland", 3]]}}])
        page = self.li.page(ST, 412)
        self.assertEqual(page["blocks"], [])                    # der Datenblock ist keine Anzeige
        data = {d["key"]: d for d in page["data"]}
        st = data["st"]
        self.assertEqual(st["cols"][:3], ["tier", "call", "dxcc"])
        self.assertEqual(st["texts"]["dxcc"]["T5"]["t"], "Somalia")
        self.assertEqual(st["texts"]["dxcc"]["T5"]["cont"], "AF")
        self.assertNotIn("Neuland", st["texts"]["dxcc"])        # Text bleibt Text
        self.assertEqual(st["texts"]["om"]["RTTY"]["t"], "RTTY")
        self.assertEqual(st["bits"]["cw"][0], "160m")
        self.assertEqual(st["bits"]["cw"][13], "70cm")
        self.assertEqual(data["calls"]["value"], 2)
