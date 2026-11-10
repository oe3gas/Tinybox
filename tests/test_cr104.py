"""CR104: connection log newest connect first, even if the rows were written
in a different order (a row is written when the connection ends)."""

import tempfile
import unittest
from pathlib import Path

from tbclient.logbook import Logbook


def row(call, start):
    return {"call": call, "via": "agw", "start": start, "end": start, "secs": 10,
            "rx": 1, "tx": 1, "ended": "remote", "freq": ""}


class LogOrder(unittest.TestCase):
    def test_by_connect_time(self):
        with tempfile.TemporaryDirectory() as d:
            lb = Logbook(Path(d) / "connlog.db")
            # written at the end of each connection: 23:16 ends before 23:02
            for s in ("2026-11-07T23:16:00Z", "2026-11-07T23:01:00Z", "2026-11-07T23:05:00Z",
                      "2026-11-07T23:02:00Z", "2026-11-07T23:03:00Z"):
                lb.add(row("OE3GAS-1", s))
            got = [r["start"][11:16] for r in lb.rows()]
            self.assertEqual(got, ["23:16", "23:05", "23:03", "23:02", "23:01"])
            self.assertEqual(len(lb.rows(2)), 2)
            lb.close()


if __name__ == "__main__":
    unittest.main()
