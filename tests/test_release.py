"""PLANUNG 24: release version, update check against GitHub (prcore/release.py) and
the one TBNEWS bulletin per release (tinybox/release.py)."""

from __future__ import annotations

import asyncio
import configparser
import io
import json
import re
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from prcore import release
from tinybox import VERSION as TINYBOX_VERSION
from tinybox import release as tbrelease
from tinybox.config import NEWS_RUBRIC
from tests.test_tinybox import make_app

ROOT = Path(__file__).resolve().parent.parent


def rel(tag: str, body: str = "- neu: Update-Hinweis\n") -> dict:
    return {"tag_name": tag, "html_url": f"https://github.com/oe3gas/Tinybox/releases/tag/{tag}",
            "body": body, "published_at": "2026-11-01T10:00:00Z"}


class FakeGitHub:
    """Stands in for _fetch: counts calls, answers 304 for a known ETag."""

    def __init__(self, release_json: dict | None, error: Exception | None = None) -> None:
        self.release = release_json
        self.error = error
        self.calls: list[str | None] = []

    def __call__(self, etag, timeout, user_agent):
        self.calls.append(etag)
        if self.error is not None:
            raise self.error
        tag = self.release["tag_name"]
        if etag == f'"{tag}"':
            return 304, None, etag
        return 200, self.release, f'"{tag}"'


class VersionTests(unittest.TestCase):
    def test_release_is_semver_and_tinybox_follows(self):
        self.assertIsNotNone(release.parse_version(release.RELEASE))
        self.assertRegex(release.RELEASE, r"^\d+\.\d+\.\d+$")
        self.assertEqual(TINYBOX_VERSION, release.RELEASE)

    def test_parse_and_compare(self):
        p = release.parse_version
        self.assertEqual(p("v1.2.0"), (1, 2, 0))
        self.assertEqual(p("1.2"), (1, 2, 0))
        self.assertIsNone(p("prod-f16d5a3"))
        self.assertIsNone(p("1.2.0-rc1"))
        self.assertIsNone(p("2026.10.24.2"))
        self.assertTrue(release.is_newer("v1.1.0", "1.0.0"))
        self.assertTrue(release.is_newer("v1.10.0", "1.9.0"))       # numbers, not text
        self.assertFalse(release.is_newer("v1.0.0", "1.0.0"))
        self.assertFalse(release.is_newer("v0.9.0", "1.0.0"))
        self.assertFalse(release.is_newer("prod-x", "1.0.0"))

    def test_update_section(self):
        cp = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
        self.assertEqual(release.load_cfg(cp), release.UpdateCfg(True, True))
        cp.read_string("[update]\ncheck = no\nannounce = no ; hint only\n")
        self.assertEqual(release.load_cfg(cp), release.UpdateCfg(False, False))
        cp.read_string("[update]\ncheck = maybe\n")
        with self.assertRaises(ValueError):
            release.load_cfg(cp)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(release.load_cfg_file(Path(tmp) / "missing.conf"),
                             release.UpdateCfg())

    def test_examples_have_the_section(self):
        for name in ("tinybox.conf.example", "tbclient.conf.example",
                     "kisshub.conf.example", "brocast/brocastd.conf.example"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertRegex(text, r"(?m)^\[update\]", name)
            cp = configparser.ConfigParser(inline_comment_prefixes=("#", ";"),
                                           strict=False)
            cp.read_string(text)
            self.assertTrue(release.load_cfg(cp).check, name)


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name) / "release.json"
        self.t = 1_000_000.0

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, gh, **kw):
        return release.check("1.0.0", self.cache, fetch=gh, now=lambda: self.t, **kw)

    def test_newer_release(self):
        gh = FakeGitHub(rel("v1.1.0"))
        r = self.check(gh)
        self.assertTrue(r.newer)
        self.assertEqual(r.latest, "v1.1.0")
        self.assertIn("v1.1.0", r.hint())
        self.assertEqual(json.loads(self.cache.read_text())["etag"], '"v1.1.0"')

    def test_same_release(self):
        r = self.check(FakeGitHub(rel("v1.0.0")))
        self.assertFalse(r.newer)

    def test_once_a_day_then_etag(self):
        gh = FakeGitHub(rel("v1.1.0"))
        self.check(gh)
        self.t += 3600
        r = self.check(gh)                       # from the cache, no request
        self.assertEqual(len(gh.calls), 1)
        self.assertTrue(r.newer)
        self.t += release.DAY
        r = self.check(gh)                       # asks again, with the ETag -> 304
        self.assertEqual(gh.calls, [None, '"v1.1.0"'])
        self.assertTrue(r.newer)                 # 304: the release from the cache

    def test_force(self):
        gh = FakeGitHub(rel("v1.1.0"))
        self.check(gh)
        self.check(gh, force=True)
        self.assertEqual(len(gh.calls), 2)

    def test_offline_is_silent(self):
        gh = FakeGitHub(None, error=urllib.error.URLError("no route"))
        with self.assertNoLogs("prcore.release", level="INFO"):
            self.assertIsNone(self.check(gh))
        self.t += 60
        self.assertIsNone(self.check(gh))        # no new try before the interval
        self.assertEqual(len(gh.calls), 1)

    def test_error_keeps_last_answer(self):
        self.check(FakeGitHub(rel("v1.1.0")))
        self.t += release.DAY
        r = self.check(FakeGitHub(None, error=TimeoutError()))
        self.assertEqual(r.latest, "v1.1.0")

    def test_cache_keeps_other_keys(self):
        self.cache.write_text(json.dumps({"announced": "v1.0.5"}))
        self.check(FakeGitHub(rel("v1.1.0")))
        self.assertEqual(json.loads(self.cache.read_text())["announced"], "v1.0.5")

    def test_broken_cache(self):
        self.cache.write_text("{kaputt")
        self.assertTrue(self.check(FakeGitHub(rel("v1.1.0"))).newer)

    def test_without_cache(self):
        r = release.check("1.0.0", None, fetch=FakeGitHub(rel("v2.0.0")))
        self.assertTrue(r.newer)

    def test_request(self):
        """Real _fetch against a fake urlopen: API URL, User-Agent, ETag, 304."""
        seen = []

        class Resp(io.BytesIO):
            status = 200
            headers = {"ETag": '"abc"'}

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout):
            seen.append(req)
            if req.get_header("If-none-match"):
                raise urllib.error.HTTPError(req.full_url, 304, "Not Modified", {}, None)
            return Resp(json.dumps(rel("v1.1.0")).encode())

        with mock.patch("urllib.request.urlopen", fake_urlopen):
            status, data, etag = release._fetch(None, 5, "TinyBox-test/1.0.0")
            self.assertEqual((status, data["tag_name"], etag), (200, "v1.1.0", '"abc"'))
            self.assertEqual(release._fetch('"abc"', 5, "x")[0], 304)
        self.assertEqual(seen[0].full_url, release.API_URL)
        self.assertEqual(seen[0].get_header("User-agent"), "TinyBox-test/1.0.0")
        self.assertTrue(release.API_URL.startswith("https://api.github.com/"))


class AsciiNotesTests(unittest.TestCase):
    def test_markdown_and_umlauts(self):
        text = ("## Neu in v1.1.0\r\n\r\n* **Update-Prüfung** für alle Module\n"
                "* siehe [Handbuch](https://x/y) – `MANUAL.md`\n")
        out = release.ascii_notes(text)
        out.encode("ascii")
        self.assertEqual(out, "Neu in v1.1.0\n\n- Update-Pruefung fuer alle Module\n"
                              "- siehe Handbuch - MANUAL.md")

    def test_short(self):
        out = release.ascii_notes("\n".join(f"- Punkt {i}" for i in range(30)))
        self.assertLessEqual(len([x for x in out.split("\n") if x and x != "..."]), 8)
        self.assertTrue(out.endswith("..."))
        self.assertLess(len(release.ascii_notes("x" * 2000)), 600)


class AnnounceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = make_app()
        self.app.cfg.storage.data_dir = Path(self.tmp.name)
        self.notice = tbrelease.UpdateNotice(self.app)

    def tearDown(self):
        self.app.store.close()
        self.tmp.cleanup()

    def result(self, tag, current="1.0.0", body="- Update-Hinweis\n"):
        return release._result(rel(tag, body), current)

    def news(self):
        return [m for m in self.app.store.list_messages()
                if m.replace_key and m.replace_key.startswith(tbrelease.KEY_PREFIX)]

    def test_one_bulletin_per_release(self):
        with self.assertLogs("tinybox.release", level="WARNING"):
            self.notice.handle(self.result("v1.1.0"))
        self.notice.handle(self.result("v1.1.0"))          # next day: same release
        msgs = self.news()
        self.assertEqual(len(msgs), 1)
        m = msgs[0]
        self.assertEqual((m.to_call, m.type), (NEWS_RUBRIC, "B"))
        self.assertIn("v1.1.0", m.subject)
        self.assertIn("https://github.com/oe3gas/Tinybox/releases/tag/v1.1.0", m.body)
        m.body.encode("ascii")
        self.assertLess(len(m.body), 800)

    def test_not_again_after_restart_or_delete(self):
        self.notice.handle(self.result("v1.1.0"))
        self.app.store.delete(self.news()[0].id)            # sysop deleted it
        again = tbrelease.UpdateNotice(self.app)            # restart
        again.handle(self.result("v1.1.0"))
        self.assertEqual(self.news(), [])

    def test_newer_release_replaces(self):
        self.notice.handle(self.result("v1.1.0"))
        self.notice.handle(self.result("v1.2.0"))
        msgs = self.news()
        self.assertEqual([m.replace_key for m in msgs], ["release:v1.2.0"])

    def test_current_release_no_bulletin(self):
        self.notice.handle(self.result("v1.0.0"))
        self.assertEqual(self.news(), [])
        self.assertFalse(self.notice.status()["newer"])

    def test_announce_off_and_by_hand(self):
        import dataclasses
        self.app.cfg.update = dataclasses.replace(self.app.cfg.update, announce=False)
        r = self.result("v1.1.0")
        self.notice.handle(r)
        self.assertEqual(self.news(), [])
        self.assertFalse(self.notice.status()["announced"])
        n = self.notice.announce(r, force=True)             # UPDATE NEWS
        self.assertIsNotNone(n)
        self.assertTrue(self.notice.status()["announced"])

    def test_never_over_brocast(self):
        """TBNEWS stays local: brocastd never gets the release bulletin."""
        from tinybox.adapters import brocast
        self.notice.handle(self.result("v1.1.0"))
        self.assertFalse(brocast.wanted(self.news()[0], self.app))


class ConsoleTests(unittest.TestCase):
    def setUp(self):
        from tinybox.adapters.sysop import MonitorFilter, SysopConsole
        self.tmp = tempfile.TemporaryDirectory()
        self.app = make_app()
        self.app.cfg.storage.data_dir = Path(self.tmp.name)
        self.app.stop_event = asyncio.Event()
        self.app.update = tbrelease.UpdateNotice(self.app)
        self.output: list[str] = []
        self.console = SysopConsole(self.app, MonitorFilter(True), self.output.append)
        self.console.start()

    def tearDown(self):
        self.app.store.close()
        self.tmp.cleanup()

    def run_cmd(self, line: str) -> str:
        self.output.clear()
        self.console.handle_line(line)
        return "".join(self.output)

    def test_help(self):
        self.assertIn("UPDATE NEWS", self.run_cmd("H"))

    def test_update_asks_github(self):
        r = release._result(rel("v1.1.0"), "1.0.0")

        async def go():
            with mock.patch.object(release, "check", return_value=r) as chk:
                self.output.clear()
                self.console.handle_line("UPDATE")
                for _ in range(50):
                    await asyncio.sleep(0.01)
                    if "new release" in "".join(self.output):
                        break
                return chk.call_args

        args = asyncio.run(go())
        out = "".join(self.output)
        self.assertIn("Asking GitHub", out)
        self.assertIn("new release v1.1.0", out)
        self.assertIn("bulletin for it is out", out)
        self.assertTrue(args.kwargs.get("force"))
        self.assertIn("new release v1.1.0", self.run_cmd("STATUS"))

    def test_update_news_without_result(self):
        self.assertIn("no newer release known", self.run_cmd("UPDATE NEWS"))


if __name__ == "__main__":
    unittest.main()


class OtherProgramsTests(unittest.TestCase):
    """tbclient, kisshub and brocastd read [update] and take the results."""

    def test_client_banner_state(self):
        from tbclient.core import ClientCore
        from tests.test_tbclient import client_cfg

        async def go():
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp))
                v = core.version
                core.on_release(release._result(rel("v1.0.0"), "1.0.0"))
                self.assertIsNone(core.snapshot()["release"])
                core.on_release(release._result(rel("v1.1.0"), "1.0.0"))
                snap = core.snapshot()
                self.assertEqual(snap["release"]["latest"], "v1.1.0")
                self.assertGreater(core.version, v)          # the long poll wakes up
                n = core.version
                core.on_release(release._result(rel("v1.1.0"), "1.0.0"))
                self.assertEqual(core.version, n)            # same release: no change

        asyncio.run(go())

    def test_client_config(self):
        from tbclient import config as ccfg
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "tbclient.conf"
            p.write_text("[station]\nmycall = OE3GAS\n[update]\ncheck = no\n", encoding="utf-8")
            self.assertFalse(ccfg.load(p).update_check)
            self.assertTrue(ccfg.load(ROOT / "tbclient.conf.example").update_check)

    def test_kisshub_config(self):
        from kisshub import config as hubconfig
        cfg = hubconfig.load(ROOT / "kisshub.conf.example")
        self.assertTrue(cfg.update_check)
        self.assertEqual(cfg.data_dir, ROOT / "data")

    def test_kisshub_logs_once(self):
        from kisshub.__main__ import release_logger
        on_result = release_logger()
        r = release._result(rel("v1.1.0"), "1.0.0")
        with self.assertLogs("kisshub", level="WARNING") as cm:
            on_result(r)
            on_result(r)
            on_result(release._result(rel("v1.0.0"), "1.0.0"))
        self.assertEqual(len(cm.records), 1)

    def test_brocastd(self):
        import sys
        sys.path.insert(0, str(ROOT / "brocast"))
        from brocast import config as bcfg
        self.assertIs(bcfg.release_module(), release)
        cfg = bcfg.load(ROOT / "brocast" / "brocastd.conf.example")
        self.assertTrue(cfg.update_check)
