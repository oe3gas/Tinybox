"""prcore - packet radio basics shared by TinyBox, tbclient, kisshub and fwdsim
(PLANUNG.md section 17.1).

    ax25/       AX.25 v2.2 frames (frame.py), link state machine (link.py), XID (xid.py)
    kiss.py     KISS framing, parameter commands, KISS-TCP client
    aprs.py     APRS decoder in plain language (aprs_data.json: devices, symbols)
    aprsstats.py  APRS statistics of the heard stations
    chatimg.py  image reference in a chat line (format, hash, size code)
    lzhuf.py    LZHUF codec (FBB B1 forwarding, mail sync)

Rule: prcore never imports from tinybox, tbclient, kisshub or brocast.
"""
