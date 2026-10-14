"""AX.25 layer 2 for the KISS mode (docs/kiss-mode-konzept.md, PLANUNG.md section 15).

    frame.py   codec for all AX.25 v2.2 frame types (modulo 8 and 128)
    kissio.py  KISS framing, parameter commands, KISS-TCP client

Later steps add the link state machine (K2/K3) and the KISS adapter (K4).
"""
