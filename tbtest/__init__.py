"""tbtest - testbed for TinyBox (PLANUNG.md section 27).

1 to 10 simulated users work with a TinyBox of their own, all over AXUDP on
this PC: terminal users type mailbox commands like a human, client users run
the real TinyBox client core (tbclient). Nothing goes on the air - the test
box and the clients get a "radio" that swallows every frame (box.Air).

    testbed folder (default: ../tinybox-testbed next to the repo)
        tbtest.conf      users, ports - written by `tbtest init`
        tinybox.conf     the test box - written by `tbtest init`
        data/            the test box's database
        logs/            the test box's log files
        users/<CALL>/    data of the client users
        runs/<time>/     one folder per run: report.txt, result.json, tinybox.out

tbtest does not import the tinybox package: the box runs as its own process
and is tested from outside, like fwdsim does it.
"""

VERSION = "2026.10.29"
