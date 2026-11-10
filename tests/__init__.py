"""TinyBox tests. This file marks 'tests' as a package - do not delete.

CR93: the client login with a key is tested in tests/test_cr93.py; all other
tests talk to the mailbox in client mode without it.
CR92: the limits for guests (terminal sessions without a key) are tested in
tests/test_cr92.py; the other tests write bulletins from terminal sessions."""

from tinybox import clientproto, rights

clientproto.REQUIRE_AUTH = False
rights.GUEST_LIMITS = False
