"""Forwarding with other mailboxes (optional module, [forward] enabled = yes).

protocol.py  SID, FBB proposals, checksums, W0RLI S commands
link.py      line links over TCP and over the AGW adapter
router.py    which partner gets which message
session.py   one forward session (F2: handshake, everything offered is deferred)

The entry point is tinybox/adapters/forward.py. The core never imports this
package, so TinyBox runs unchanged without it.
"""
