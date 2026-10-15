"""dxfeed - collects DX cluster spots and writes a daily DX digest bulletin.

PLANUNG.md section "DX-Cluster-Feed". No live spots on the air: the collector
stores the spot stream, once a day the digest condenses the last 24 hours into
one bulletin that goes into the TinyBox inbox folder (local only, no @).

    spots.py      parse "DX de ..." lines, band and mode, clean foreign input
    cty.py        AD1C country file (cty.dat): call -> DXCC entity, continent
    store.py      SQLite: spots and connection times (for the coverage note)
    collector.py  telnet client to a DXSpider/CC cluster node, reconnect
    digest.py     relevance filter, one line per DX call, band activity
    config.py     dxfeed.conf (INI)

Only the Python standard library is used.
"""

VERSION = "2026.10.15"
