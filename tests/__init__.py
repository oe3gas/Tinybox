"""TinyBox tests. This file marks 'tests' as a package - do not delete.

CR93: the client login with a key is tested in tests/test_cr93.py; all other
tests talk to the mailbox in client mode without it."""

from tinybox import clientproto

clientproto.REQUIRE_AUTH = False
