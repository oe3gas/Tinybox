"""AX.25 layer 2 (docs/kiss-mode-konzept.md, PLANUNG.md section 15).

    frame.py   codec for all AX.25 v2.2 frame types (modulo 8 and 128)
    link.py    link state machine (connected mode, v2.2 with fallback to v2.0)
    xid.py     XID parameter negotiation

KISS framing is in prcore/kiss.py.
"""
