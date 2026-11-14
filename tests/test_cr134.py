"""CR134: terminal UI of the box - prompt mark for clients, MY... commands, VERsion, TSF."""

from __future__ import annotations

import tempfile
import unittest

from prcore import tbproto
from tbclient.core import ClientCore
from tinybox import commands, texts
from tinybox.clientproto import ClientInfo
from tests.test_tbclient import client_cfg
from tests.test_tinybox import login, make_app, type_lines


class CommandWordTests(unittest.TestCase):
    def test_abbreviations(self):
        for typed, full in (("myn", "MYNAME"), ("MYNAME", "MYNAME"), ("myl", "MYLOC"),
                            ("myloc", "MYLOC"), ("myh", "MYHOMEBBS"), ("myhome", "MYHOMEBBS"),
                            ("ver", "VERSION"), ("Version", "VERSION"), ("L", "L")):
            self.assertEqual(commands.command_word(typed), full, typed)

    def test_too_short_or_old(self):
        for typed in ("my", "ve", "v", "n", "nl", "nh", "mylocx"):
            self.assertEqual(commands.command_word(typed), "", typed)


class TerminalTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()

    def test_old_commands_gone(self):
        s, t = login(self.app, "OE3ABC")
        t.take()
        for line in ("N Hans", "NL JN88", "NH OE3XSR", "V"):
            type_lines(s, line)
            self.assertIn(texts.UNKNOWN_CMD, t.take(), line)

    def test_version_and_profile(self):
        s, t = login(self.app, "OE3ABC")
        t.take()
        type_lines(s, "ver")
        self.assertIn("TinyBox ", t.take())
        type_lines(s, "myl jn88ep")
        self.assertIn("locator JN88EP", t.take())

    def test_prompt_after_help(self):
        s, t = login(self.app, "OE3ABC")
        t.take()
        type_lines(s, "?")
        out = t.take()
        self.assertTrue(out.endswith(texts.PROMPT), out[-60:])
        self.assertNotIn(",V,", texts.PROMPT)

    def test_list_header_tsf(self):
        self.assertIn(" TSF ", texts.LIST_HEADER)


class PromptMarkTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()

    def _client(self, caps):
        s, t = login(self.app, "OE3ABC")
        t.take()
        s.client = ClientInfo("TB1", set(caps))
        return s, t

    def test_mark_instead_of_prompt(self):
        s, t = self._client({"CHAT", "PRM"})
        type_lines(s, "?")
        out = t.take()
        self.assertIn(tbproto.PROMPT_MARK, out)
        self.assertNotIn(texts.PROMPT, out)

    def test_no_mark_after_protocol_lines(self):
        s, t = self._client({"CHAT", "PRM"})
        type_lines(s, "//BOARDS")
        self.assertNotIn(tbproto.PROMPT_MARK + "\r", t.take())

    def test_older_client_gets_nothing(self):
        s, t = self._client({"CHAT"})
        type_lines(s, "?")
        out = t.take()
        self.assertNotIn(tbproto.PROMPT_MARK, out)
        self.assertNotIn(texts.PROMPT, out)

    def test_waiting_for_the_sysop(self):
        s, t = login(self.app, "OE3ABC")
        t.take()
        s._client_wait = ClientInfo("TB1", {"CHAT", "PRM"})   # //AUTHWAIT: no client mode yet
        type_lines(s, "L")
        self.assertIn(tbproto.PROMPT_MARK, t.take())


class ClientSideTests(unittest.TestCase):
    def test_mark_shows_prompt_in_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            core = ClientCore(client_cfg(tmp))
            core._on_line(tbproto.PROMPT_MARK)
            self.assertEqual(core.chan.term[-1][1:], ("rx", tbproto.TERM_PROMPT))
            core.mailbox.close()

    def test_confirmed_after_waiting(self):      # CR133
        with tempfile.TemporaryDirectory() as tmp:
            core = ClientCore(client_cfg(tmp))
            core._on_line("//AUTHWAIT fp=1234-5678-9ABC")
            self.assertIn("still has to confirm", core.console[-1])
            core._on_line("//OK TB1 caps=CHAT")
            self.assertTrue(core.auth.get("confirmed"))
            core.mailbox.close()


if __name__ == "__main__":
    unittest.main()
