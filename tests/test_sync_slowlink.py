"""Lauf 5 (18.10.2026): a long mail over VARA FM is still being sent when the
120 s idle timer of the sync runs out - the sync must keep waiting for //SENT
while own frames are not yet acknowledged, and give up only when nothing of
ours is on the way any more."""

from __future__ import annotations

import asyncio
import unittest

from tbclient import sync as sync_mod


class _Link:
    def __init__(self, outstanding):
        self.values = list(outstanding)

    async def outstanding(self) -> int:
        return self.values.pop(0) if self.values else 0


class _Core:
    state = "online"

    def __init__(self, link):
        self.link = link


def make(outstanding):
    s = sync_mod.Syncer.__new__(sync_mod.Syncer)     # only what _next needs
    s.core = _Core(_Link(outstanding))
    s.queue = asyncio.Queue()
    return s


class SlowLinkTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._idle = sync_mod.IDLE_SEC
        sync_mod.IDLE_SEC = 0.05

    def tearDown(self):
        sync_mod.IDLE_SEC = self._idle

    async def test_waits_while_own_frames_are_on_their_way(self):
        s = make([5, 3, 1])                    # three idle periods with data still going out
        asyncio.get_running_loop().call_later(0.17, s.queue.put_nowait, ("line", "//SENT 42"))
        self.assertEqual(await s._next(), ("line", "//SENT 42"))

    async def test_gives_up_when_nothing_is_on_the_way(self):
        s = make([0])
        with self.assertRaises(sync_mod.SyncError):
            await s._next()


if __name__ == "__main__":
    unittest.main()
