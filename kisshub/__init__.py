"""kisshub - owns the KISS TNC and shares it over KISS-TCP (KISS step K7).

docs/kiss-mode-konzept.md section 4, PLANUNG.md section 15.

    TNC --serial/TCP-- kisshub --KISS-TCP 127.0.0.1:8001--+-- TinyBox
                                                          +-- brocastd

    profiles.py   how to wake each TNC and put it into KISS (PK-232, TM-D710, ...)
    transport.py  serial port (pyserial, two threads) or TCP to the TNC
    tnc.py        wake + init dialog in terminal mode, then KISS framing
    hub.py        KISS-TCP server, clients, paced send queue with priorities
"""

VERSION = "2026.10.14"
