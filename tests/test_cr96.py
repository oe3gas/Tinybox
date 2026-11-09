"""CR96 (audit TB-05, TB-16): received pictures and files - only what was asked
for, never more than allowed, never over what is stored, no programs."""

from __future__ import annotations

import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tbclient import filecheck
from tbclient.images import ImageStore
from tbclient.peerfile import FILE_MAX, FileStore, PeerFiles
from tbclient.peerimg import PEER_IMG_MAX, PeerImages
from tinybox import chatimg as box_chatimg

from tests.test_chatimg import JPEG, WEBP, client, h6, img_app
from tests.test_tinybox import type_lines


def zipped(name: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(name, b"x")
    return buf.getvalue()


class FileCheck(unittest.TestCase):
    def test_names(self):
        for n in ("setup.exe", "run.BAT", "x.ps1", "Rechnung.pdf.exe", "a.lnk", "m.docm",
                  "evil.exe.", "s.sh", "t.js"):
            self.assertIsNotNone(filecheck.name_verdict(n), n)
        for n in ("bild.jpg", "log.adi", "plan.pdf", "notes.txt", "archiv.zip", "README"):
            self.assertIsNone(filecheck.name_verdict(n), n)

    def test_content(self):
        for data in (b"MZ\x90\x00", b"\x7fELF\x02", b"#!/bin/sh\nrm -rf", b"\xcf\xfa\xed\xfe",
                     zipped("tool/setup.exe"), b"PK\x03\x04broken"):
            self.assertIsNotNone(filecheck.content_verdict(data), data[:8])
        for data in (b"%PDF-1.7", JPEG, WEBP, b"Hallo 73", zipped("doc/readme.txt")):
            self.assertIsNone(filecheck.content_verdict(data), data[:8])


class Stores(unittest.TestCase):
    def test_received_never_replaces(self):
        with tempfile.TemporaryDirectory() as d:
            for store in (ImageStore(Path(d) / "i"), FileStore(Path(d) / "f")):
                self.assertTrue(store.put("abc123", b"first"))
                self.assertFalse(store.put("abc123", b"evil"))
                self.assertEqual(store.get("abc123"), b"first")
                self.assertTrue(store.put("abc123", b"mine", own=True))
                self.assertEqual(store.get("abc123"), b"mine")


def fake_peer(tmp: str, history=()):
    expected = []
    disconnected = []
    splitter = SimpleNamespace(expect=lambda n, done, progress=None: expected.append((n, done)))
    core = SimpleNamespace(
        images=SimpleNamespace(loading={}, store=ImageStore(Path(tmp) / "img")),
        files=FileStore(Path(tmp) / "files"), file_loading={},
        peerchat=SimpleNamespace(messages=lambda call: list(history)), _touch=lambda: None)
    ch = SimpleNamespace(core=core, state="online", n=1,
                         link=SimpleNamespace(splitter=splitter, kind="agw"),
                         disconnect=lambda: disconnected.append(True))
    peer = SimpleNamespace(ch=ch, call="OE3GAS", caps={"IMG", "FILE"}, _send=lambda line: None)
    return peer, core, expected, disconnected


class PeerPush(unittest.TestCase):                               # TB-05
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_unasked_picture_is_swallowed_not_stored(self):
        peer, core, expected, _ = fake_peer(self.tmp.name)
        core.images.store.put(h6(WEBP), WEBP)                      # a board picture
        pi = PeerImages(peer)
        with self.assertLogs("tbclient.peerimg", "WARNING"):
            pi.take("I", f"{h6(WEBP)} 0 {len(JPEG)}")
        [(n, done)] = expected
        self.assertEqual(n, len(JPEG))                              # bytes taken off the line
        done(JPEG)
        self.assertEqual(core.images.store.get(h6(WEBP)), WEBP)    # nothing replaced
        self.assertEqual(core.images.loading, {})

    def test_too_big_drops_the_link(self):
        peer, core, expected, disconnected = fake_peer(self.tmp.name)
        pi = PeerImages(peer)
        pi._want = "abcdef"
        with self.assertLogs("tbclient.peerimg", "WARNING"):
            pi.take("I", f"abcdef 0 {PEER_IMG_MAX + 1}")
        self.assertEqual((expected, disconnected), ([], [True]))

    def test_unasked_file_and_big_raw_file(self):
        peer, core, expected, disconnected = fake_peer(self.tmp.name)
        pf = PeerFiles(peer)
        with self.assertLogs("tbclient.peerfile", "WARNING"):
            pf.take("F", "abcdef r 100")
        self.assertEqual(len(expected), 1)
        self.assertEqual(core.file_loading, {})                     # no entry for strangers
        pf._want = "abcdef"
        with self.assertLogs("tbclient.peerfile", "WARNING"):
            pf.take("F", f"abcdef r {FILE_MAX + 8}")                # 'r' is limited too
        self.assertEqual(disconnected, [True])

    def test_program_file_refused_before_and_after(self):
        exe = b"MZ" + b"\x00" * 200
        h = h6(exe)
        offer = {"dir": "rx", "text": f"~%{h} {len(exe)} {len(exe)} tool.exe"}
        peer, core, expected, _ = fake_peer(self.tmp.name, [offer])
        pf = PeerFiles(peer)
        self.assertFalse(pf.fetch(h))                               # by its name
        self.assertIn("program", core.file_loading[h]["error"])
        # offered under a harmless name: the content gives it away
        offer["text"] = f"~%{h} {len(exe)} {len(exe)} bild.jpg"
        core.file_loading.clear()
        pf._want = h
        pf.take("F", f"{h} r {len(exe)}")
        with self.assertLogs("tbclient.peerfile", "WARNING"):
            expected[-1][1](exe)
        self.assertFalse(core.files.has(h))
        self.assertIn("Windows program", core.file_loading[h]["error"])


class BoxUpload(unittest.TestCase):                              # TB-16
    def setUp(self):
        self.app = img_app()

    def test_foreign_station_cannot_take_over_an_upload(self):
        victim, vt = client(self.app, "OE3GAS")
        evil, et = client(self.app, "OE1EVL")
        vt.take()                                                    # "OE1EVL joined"
        h = h6(WEBP)
        type_lines(victim, f"//IMGPUT {h} {len(WEBP)}")
        self.assertTrue(vt.take().startswith(f"//IMGGO {h} 0"))
        victim.feed_raw(WEBP[:100])
        with self.assertLogs("tinybox.chatimg", "WARNING"):
            type_lines(evil, f"//IMGPUT {h} {len(JPEG)}")          # other size, other station
        self.assertIn("//ERR img busy", et.take())
        vt.take()
        victim.feed_raw(WEBP[100:])
        self.assertIn(f"//IMGOK {h}", vt.take())
        self.assertEqual(self.app.store.image_get(h), WEBP)

    def test_collision_with_a_stored_picture(self):
        victim, vt = client(self.app, "OE3GAS")
        h = h6(WEBP)
        self.app.store.image_put(h, JPEG)                           # "same" short hash
        with mock.patch.object(box_chatimg, "image_hash", lambda data: h):
            self.app.store._db.execute("DELETE FROM chat_images")   # not there yet at PUT
            type_lines(victim, f"//IMGPUT {h} {len(WEBP)}")
            vt.take()
            self.app.store.image_put(h, JPEG)                       # arrives in between
            with self.assertLogs("tinybox.chatimg", "WARNING"):
                victim.feed_raw(WEBP)
        self.assertIn("//ERR img collision", vt.take())
        self.assertEqual(self.app.store.image_get(h), JPEG)        # nothing replaced


if __name__ == "__main__":
    unittest.main()
