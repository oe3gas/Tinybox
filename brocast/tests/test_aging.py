"""Alterung im Karussell: Alter der Revision statt letzter Bestätigung, "born"."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from brocast import carousel as carousel_mod
from brocast.carousel import Carousel
from brocast.store import Store
from tests.test_daemon import BULLETIN, Clock, make_station

HOUR = 3600
DAY = 86400


class AgingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.clock = Clock()
        self.sent: list[bytes] = []

        async def send(data: bytes) -> bool:
            self.sent.append(data)
            return True

        async def sleep(s: float) -> None:
            pass

        self.st, self.store = make_station(self.clock)
        self.car = Carousel(self.store, send, self.st.cfg.station, "OE3GAS-5", self.clock,
                            mono=lambda: 0.0, sleep=sleep)

    def gap_after_send(self, key: str = "1") -> float:
        row = self.store.get_page("tinybox", key)
        return (row.next_tx - row.last_tx) / 60

    async def test_hourly_confirmation_does_not_reset_the_age(self):
        """Der Fehler bis 25.10.2026: der stündliche Sync setzte t neu, aging griff nie."""
        self.st.cfg.station.aging = [(24, 120)]
        self.st.put("tinybox", "1", BULLETIN)
        await self.car.step()
        for _ in range(26):                          # 26 h lang stündlich bestätigt
            self.clock.t += HOUR
            self.st.put("tinybox", "1", BULLETIN)
            await self.car.step()
        self.assertEqual(self.store.get_page("tinybox", "1").rev, 0)   # keine neue Revision
        self.assertEqual(self.gap_after_send(), 120)

    async def test_born_sets_the_age(self):
        self.st.cfg.station.aging = [(24, 120), (72, 360), (168, 1440)]
        born = int(self.clock.t) - 20 * DAY
        self.st.put("tinybox", "1", {**BULLETIN, "born": born})
        row = self.store.get_page("tinybox", "1")
        self.assertEqual(row.rev_t, born)
        await self.car.step()                        # neue Seite: einmal sofort
        self.assertEqual(len(self.sent), 1)
        for _ in range(len(self.st.cfg.station.repeat_minutes) - 1):  # Staffel 2, 5, 10
            self.clock.t += 60 * 60
            await self.car.step()
        self.assertEqual(self.gap_after_send(), 1440)                 # danach einmal am Tag

    def test_born_is_not_on_air_and_not_content(self):
        self.st.put("tinybox", "1", BULLETIN)
        row = self.store.get_page("tinybox", "1")
        frames_before = self.store.frames(row.pid)
        born = int(self.clock.t) - 5 * DAY
        self.clock.t += HOUR
        res = self.st.put("tinybox", "1", {**BULLETIN, "born": born})
        self.assertFalse(res["changed"])             # nachgeliefert: keine neue Revision
        row = self.store.get_page("tinybox", "1")
        self.assertEqual((row.rev, row.rev_t), (0, born))
        for a, b in zip(frames_before, self.store.frames(row.pid)):
            self.assertNotIn(b"born", b)
            self.assertEqual(len(a), len(b))

    def test_born_in_the_future_counts_as_now(self):
        self.st.put("tinybox", "1", {**BULLETIN, "born": int(self.clock.t) + DAY})
        self.assertEqual(self.store.get_page("tinybox", "1").rev_t, int(self.clock.t))

    def test_born_must_be_unix_seconds(self):
        from brocast.station import BrocastError
        for bad in ("2026-10-05", -1, 1.5, True):
            with self.subTest(bad=bad), self.assertRaises(BrocastError):
                self.st.put("tinybox", "1", {**BULLETIN, "born": bad})

    async def test_old_born_with_zero_rests(self):
        self.st.cfg.station.repeat_minutes = [0]
        self.st.cfg.station.aging = [(24, 120), (168, 0)]
        self.st.put("tinybox", "1", {**BULLETIN, "born": int(self.clock.t) - 10 * DAY})
        await self.car.step()
        self.assertTrue(self.sent)                   # einmal geht sie noch hinaus
        self.assertEqual(self.store.get_page("tinybox", "1").next_tx, carousel_mod.RESTING)

    def test_default_aging(self):
        self.assertEqual(self.st.cfg.station.aging, [(24, 120), (72, 360), (168, 1440)])


class MigrationTests(unittest.TestCase):
    def test_schema_3_gets_rev_t_from_t(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "old.db"
            Store(path).close()
            db = sqlite3.connect(path)               # so tun, als wäre es Schema 3
            db.execute("ALTER TABLE pages DROP COLUMN rev_t")
            db.execute("INSERT INTO pages (provider, pkey, id, rev, t, content, content_hash,"
                       " next_tx) VALUES ('tinybox', '1', 100, 0, 1234, '{}', 'h', 0)")
            db.commit()
            db.close()
            store = Store(path)
            try:
                self.assertEqual(store.get_page("tinybox", "1").rev_t, 1234)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
