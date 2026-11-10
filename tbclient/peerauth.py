"""Who is really on the other end - TBClient to TBClient (CR99, audit TB-06).

Both clients have their own key (CR93, one per device) and usually a certificate
of their home BBS. After the //TB lines (each carries a challenge n=<random>):

    //PAUTH sig=<86> pub=<43> dev=<8 hex> [cert=<certificate of the home BBS>]

    signed: "TINYBOX-PEER1|<own call>|<call of the other>|<challenge of the other>"

The other side checks the signature, then how far it trusts the key:

    verified  the certificate is right and its issuer is trusted here - the own
              home BBS or a box that one trusts (//TRUST?, core.trusted_issuer)
    known     the key was seen from this call before (stored, like SSH)
    first     first contact with this call: key stored (trust on first use)
    changed   another key than the known ones and no valid certificate - could be
              a new device of the other, or somebody using the call: warning,
              the user decides (accept)
    bad       wrong signature
    old       the other client does not know AUTH (older version)

Only verified, known and first sync the chat history (//HIST, //HM), may
delete it, and get our pictures and files. Everything else: chat only.
Single chat lines stay unsigned (bytes per line); the rest risk of slipped-in
lines is the same as in a chat board (TB-07).
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from prcore import auth

if TYPE_CHECKING:
    from .peer import Peer

log = logging.getLogger(__name__)

TRUSTED = ("verified", "known", "first")
KEYS_PER_CALL = 5            # devices of one call remembered
CALLS_MAX = 300


class PeerAuth:
    def __init__(self, peer: "Peer", my_nonce: str, their_nonce: str) -> None:
        self.peer = peer
        self.my_nonce = my_nonce
        self.their_nonce = their_nonce
        self.state = ""
        self.pub = ""
        self.dev = ""
        self.issuer = ""
        self.sent = False

    @property
    def core(self):
        return self.peer.ch.core

    @property
    def trusted(self) -> bool:
        return self.state in TRUSTED

    @property
    def fp(self) -> str:
        try:
            return auth.fingerprint(auth.b64d(self.pub, 32)) if self.pub else ""
        except auth.AuthError:
            return ""

    # --- our answer ------------------------------------------------------------------

    def send(self) -> None:
        if self.sent or not self.their_nonce:
            return
        self.sent = True
        me, ident = self.core.cfg.mycall, self.core.identity
        cert = self.core.own_cert()
        self.peer._send(f"//PAUTH sig={ident.sign_peer(me, self.peer.call, self.their_nonce)} "
                        f"pub={ident.pub} dev={ident.device}" + (f" cert={cert}" if cert else ""))

    # --- theirs ----------------------------------------------------------------------

    def take(self, rest: str) -> None:
        args = dict(p.split("=", 1) for p in rest.split() if "=" in p)
        try:
            pub = auth.b64d(args.get("pub", ""), 32)
            sig = auth.b64d(args.get("sig", ""), 64)
        except auth.AuthError:
            return self._set("bad")
        if not self.my_nonce or not auth.verify(
                pub, auth.peer_message(self.peer.call, self.core.cfg.mycall, self.my_nonce), sig):
            log.warning("%s: peer login with a wrong signature", self.peer.call)
            return self._set("bad")
        self.my_nonce = ""                        # one answer per challenge
        self.pub = auth.b64e(pub)
        dev = args.get("dev", "")
        self.dev = dev if len(dev) == 8 and all(c in "0123456789ABCDEF" for c in dev) else ""
        issuer = self._cert_issuer(args.get("cert", ""))
        known = self._known()
        if issuer:
            self.issuer = issuer
            self._remember()
            return self._set("verified")
        if self.pub in known:
            self._remember()
            return self._set("known")
        if not known:
            self._remember()
            return self._set("first")
        log.warning("%s: peer with another key (%s) than the known ones", self.peer.call, self.fp)
        self._set("changed")

    def accept(self) -> bool:
        """The user takes the new key (a new device of the other)."""
        if self.state != "changed" or not self.pub:
            return False
        self._remember()
        self._set("known")
        return True

    def _cert_issuer(self, text: str) -> str:
        if not text:
            return ""
        try:
            c = auth.parse_cert(text)
        except auth.AuthError:
            return ""
        if c["call"] != auth.base(self.peer.call) or c["pub"] != self.pub:
            return ""
        key = self.core.trusted_issuer(c["issuer"])
        if key is None:
            return ""
        today = time.strftime("%Y%m%d", time.gmtime())
        return c["issuer"] if auth.check_cert(c, key, today) else ""

    # --- the keys seen from other calls (settings.json, peer_keys) --------------------

    def _store(self) -> dict:
        s = self.core.settings.get("peer_keys")
        if not isinstance(s, dict):
            s = self.core.settings["peer_keys"] = {}
        return s

    def _known(self) -> list[str]:
        rows = self._store().get(auth.base(self.peer.call), [])
        return [r.get("pub") for r in rows if isinstance(r, dict)]

    def _remember(self) -> None:
        s = self._store()
        call = auth.base(self.peer.call)
        rows = [r for r in s.get(call, []) if isinstance(r, dict) and r.get("pub") != self.pub]
        rows.append({"pub": self.pub, "dev": self.dev, "at": int(time.time())})
        s[call] = rows[-KEYS_PER_CALL:]
        if len(s) > CALLS_MAX:                   # forget the calls not seen for the longest
            for old in sorted(s, key=lambda c: max((r.get("at", 0) for r in s[c]), default=0))[
                    :len(s) - CALLS_MAX]:
                del s[old]
        self.core._save_settings()

    def _set(self, state: str) -> None:
        was = self.trusted
        self.state = state
        ch = self.peer.ch
        text = {"verified": f"key verified by {self.issuer}",
                "known": "known key", "first": "first contact - key stored",
                "changed": "ANOTHER KEY than before - history, pictures and files paused "
                           "(a new device? compare the fingerprint, then accept)",
                "bad": "wrong signature - chat only", "old": "older client, no key check - "
                                                          "chat only"}[state]
        ch.term_line("sys", f"*** {ch.target}: {text}" + (f" ({self.fp})" if self.fp else ""))
        if self.trusted and not was:
            self.peer.trusted_now()
        self.core._touch()

    def summary(self) -> dict:
        return {"state": self.state, "fp": self.fp, "dev": self.dev, "issuer": self.issuer}
