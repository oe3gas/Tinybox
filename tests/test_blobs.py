"""R10: tinybox/blobs.py - half uploads shared by chat images and board files."""

from __future__ import annotations

import time
import unittest
from unittest import mock

from tinybox import blobs


class UploadsTests(unittest.TestCase):
    def test_owner_resume_and_new_start(self):
        u = blobs.Uploads()
        p = u.begin("h1", "OE1ABC", 10, "z")
        u._chunk("h1", b"abcd")
        self.assertIsNone(u.begin("h1", "OE3XYZ", 10, "z"))         # CR96: not his
        self.assertEqual(u.owner("h1"), "OE1ABC")
        self.assertEqual(u.begin("h1", "OE1ABC", 10, "z").have, 4)    # resume
        self.assertEqual(u.begin("h1", "OE1ABC", 10, "r").have, 0)    # other packing: anew
        self.assertEqual(u.begin("h1", "OE1ABC", 12, "r").have, 0)    # other size: anew
        self.assertIsNot(p, u.get("h1"))

    def test_finish_only_for_the_owner(self):
        u = blobs.Uploads()
        u.begin("h1", "OE1ABC", 3)
        u._chunk("h1", b"xyz")
        self.assertIsNone(u.finish("h1", "OE3XYZ"))
        self.assertIsNotNone(u.get("h1"))
        self.assertEqual(bytes(u.finish("h1", "OE1ABC").data), b"xyz")
        self.assertIsNone(u.get("h1"))

    def test_purge_after_ttl(self):
        u = blobs.Uploads(ttl=10)
        u.begin("old", "A", 5)
        u.begin("new", "A", 5)
        u.get("old").last = time.monotonic() - 11
        self.assertEqual(u.purge(), 1)
        self.assertEqual((u.get("old"), u.get("new") is not None), (None, True))

    def test_send_from_offset(self):
        s = mock.Mock()
        self.assertEqual(blobs.send_from(s, "//I h 2 5", b"abcde", 2), 3)
        s.transport.write.assert_called_once_with("//I h 2 5\r")
        s.transport.write_bytes.assert_called_once_with(b"cde")


if __name__ == "__main__":
    unittest.main()
