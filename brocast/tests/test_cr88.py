"""CR88 (audit TB-09): single frames must not break the page list or block brocastd."""

from __future__ import annotations

import unittest

import cbor2

from brocast.codec import BrocastError, Codec
from brocast.listener import Listener, iso, iso_ms
from brocast.store import Store
from tests.test_daemon import Clock

ST = "OE3GAS-5"
T, SUB = 4, 23                             # envelope keys (brocast-core.yaml)


class TB09(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.codec = Codec()
        self.store = Store(":memory:")
        self.li = Listener(self.store, self.codec, self.clock)

    def wire(self):
        return cbor2.dumps(self.codec.to_wire({"id": 9, "rev": 0, "t": int(self.clock()),
                                               "typ": "text", "ti": "x"}))

    def test_absurd_times_rejected(self):
        for bad in (2**40, 2**62, -1, 1e300, float("inf"), "1800000000"):
            with self.subTest(t=bad), self.assertRaises(BrocastError):
                self.codec.decode(cbor2.dumps({**cbor2.loads(self.wire()), T: bad}),
                                  defaults=False)

    def test_page_from_the_future_is_ignored(self):
        data = cbor2.dumps({**cbor2.loads(self.wire()), T: int(self.clock()) + 3 * 86400})
        self.assertEqual(self.li.on_page(self.codec.decode(data, defaults=False), data, ST),
                         "future")
        self.assertEqual(self.li.list_pages(), [])

    def test_huge_subpage_count_rejected(self):
        for bad in ([1, 10**6], [1, 2**62], [2, 1], [0, 1]):
            data = cbor2.dumps({**cbor2.loads(self.wire()), SUB: bad})
            with self.subTest(sub=bad), self.assertRaises(BrocastError):
                self.codec.decode(data, defaults=False)

    def test_page_list_survives_a_bad_row(self):
        data = self.wire()
        self.li.on_page(self.codec.decode(data, defaults=False), data, ST)
        self.store.db.execute("UPDATE lpages SET t = ?", (2**40,))
        self.li.list_pages()                                 # must not raise

    def test_iso_never_raises(self):
        for bad in (2**40, -2**62, float("inf"), "x"):
            self.assertIsNone(iso(bad))
            self.assertIsNone(iso_ms(bad))
        self.assertTrue(iso(0).startswith("1970"))


if __name__ == "__main__":
    unittest.main()
