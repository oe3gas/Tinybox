"""CR117: picture upload - progress bar and TX in the top bar follow the sending.

Before: when Direwolf answered the first 'Y' with 0, the bar jumped to the end
at once and stood there; own I-frames updated the TX time but pushed no
snapshot, the queue poll neither - the GUI saw nothing for long stretches."""

import asyncio
import tempfile
import unittest

from tbclient import activity, images
from tbclient.core import ClientCore
from tbclient.radio import RawFrame
from tests.test_tbclient import client_cfg, until

WEBP = b"RIFF\x20\x00\x00\x00WEBPVP8 " + bytes(range(256)) * 20      # 5132 bytes


def online(core):
    core.state = "online"
    core.caps = {"IMG"}
    core.board = {"n": 1, "name": "Treff", "keep": "7d", "img": 8192}


class UploadProgressTests(unittest.TestCase):
    def setUp(self):
        self._poll = images.POLL_SEC
        images.POLL_SEC = 0.05

    def tearDown(self):
        images.POLL_SEC = self._poll

    def test_zero_answer_does_not_jump_to_the_end(self):
        """'Y' says 0 (no answer usable): the bar follows the own frames on the air,
        at most 95 % until //IMGOK."""
        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp))
                sent: list = []
                core.link.send_line = lambda t: sent.append(t)
                core.link.send_bytes = lambda b: sent.append(b)

                async def outstanding():
                    return 0
                core.link.outstanding = outstanding
                online(core)
                h = core.send_image(WEBP, "BEHV6nWB2yk8pyo0", "", "")
                await until(lambda: len(sent) == 1)
                core._on_line(f"//IMGGO {h} 0")
                await until(lambda: core.images.upload["state"] == "sending")
                await asyncio.sleep(0.2)
                self.assertEqual(core.images.upload["sent"], 0)       # not at the end
                for _ in range(10):                                   # 10 own frames, 256 B
                    core._on_frame(RawFrame(src="OE3GAS", dest="OE3GAS-1", control=0x00,
                                            info=b"x" * 256))
                await until(lambda: core.images.upload["sent"] == 2560)
                for _ in range(20):                                   # retries: capped
                    core._on_frame(RawFrame(src="OE3GAS", dest="OE3GAS-1", control=0x00,
                                            info=b"x" * 256))
                await until(lambda: core.images.upload["sent"] == len(WEBP) * 95 // 100)
                core._on_line(f"//IMGOK {h}")
                await until(lambda: core.images.upload["state"] == "done")
                self.assertEqual(core.images.upload["sent"], len(WEBP))
        asyncio.run(scenario())

    def test_waiting_frames_move_the_bar(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp))
                core.link.send_line = lambda t: None
                core.link.send_bytes = lambda b: None
                left = [20]

                async def outstanding():
                    return left[0]
                core.link.outstanding = outstanding
                online(core)
                h = core.send_image(WEBP, "BEHV6nWB2yk8pyo0", "", "")
                await asyncio.sleep(0.05)
                core._on_line(f"//IMGGO {h} 0")
                await until(lambda: core.images.upload["state"] == "sending")
                v = core.version
                left[0] = 10
                await until(lambda: core.images.upload["sent"] == len(WEBP) // 2)
                self.assertGreater(core.version, v)                   # a snapshot for the GUI
                core._on_line(f"//IMGOK {h}")
                await until(lambda: core.images.upload["state"] == "done")
        asyncio.run(scenario())


class TxChipTests(unittest.TestCase):
    def test_own_frame_pushes_a_snapshot(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp))
                v = core.version
                core._on_frame(RawFrame(src="OE3GAS", dest="OE3GAS-1", control=0x00, info=b"x"))
                self.assertGreater(core.version, v)
                self.assertGreater(core.tx_at, 0)
                v = core.version
                core._on_frame(RawFrame(src="OE3GAS", dest="OE3GAS-1", control=0x02, info=b"x"))
                self.assertEqual(core.version, v)                     # at most every 0.5 s
        asyncio.run(scenario())

    def test_waiting_frames_keep_tx_lit(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp))
                c = core.chan
                c.state = "online"
                c.outstanding = 7
                m = activity.build(core)["modem"]
                self.assertEqual(m["txq"], 7)
                self.assertEqual(m["tx"], 0.0)
        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
