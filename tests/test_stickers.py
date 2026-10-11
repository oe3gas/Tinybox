"""CR11: sticker set of the client - over the air only [STK]NAME."""

from __future__ import annotations

import json
import re
import unittest

from tbclient import web


class StickerSet(unittest.TestCase):
    def test_names_files_served(self):
        data = json.loads((web.STATIC / "stickers" / "stickers.json").read_text(encoding="utf-8"))
        names = [s["name"] for s in data["stickers"]]
        self.assertEqual(len(names), len(set(names)))
        for s in data["stickers"]:
            self.assertRegex(s["name"], r"^[A-Z0-9]{1,4}$")
            self.assertTrue((web.STATIC / "stickers" / s["file"]).is_file(), s["file"])
            self.assertIn(f"/stickers/{s['file']}", web.FILES)
        self.assertIn("/stickers/stickers.json", web.FILES)
        self.assertEqual(web.TYPES[".webp"], "image/webp")
        self.assertTrue(all(len(f"[STK]{n}") <= 9 for n in names))


if __name__ == "__main__":
    unittest.main()
