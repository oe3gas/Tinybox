"""fwdsim - forward test partner for TinyBox.

Simulates two partner mailboxes under the club call OE3XTC:

    OE3XTC-11  OE3XTC-11.#OOE.AUT.EU   direct partner of TinyBox, end point and hop
    OE3XTC-22  OE3XTC-22.#BAY.DEU.EU   "German" BBS, reachable only via OE3XTC-11

fwdsim tests TinyBox as a black box over TCP or AGW/Direwolf, exactly like a
real partner would. It does not import anything from the tinybox package.
"""

VERSION = "0.1.0"
SOFTWARE = "FWDSIM"
