"""Client keys and trusted TinyBoxen (CR93) - the actions behind the sysop
console (USER, TRUST) and the sysop web GUI (Keys), in one place.

    user keys     released at this box (active), waiting (pending), revoked, or
                  known through a certificate of a trusted home BBS (cert)
    trusted boxes other TinyBoxen whose certificates count here: their
                  mailbox call and public key, entered by the sysop after he
                  compared the fingerprint with the other sysop
    this box      its own key (data/box.key): it signs the certificates of the
                  users released here - its public key goes to the other sysops
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from prcore import auth

if TYPE_CHECKING:
    from .service import MessageService

log = logging.getLogger(__name__)

USER_ACTIONS = ("OK", "REVOKE", "DEL")


class KeysError(ValueError):
    pass


def _fp(pub64: str) -> str:
    try:
        return auth.fingerprint(auth.b64d(pub64, 32))
    except auth.AuthError:
        return "????-????-????"


def users(svc: MessageService) -> list[dict]:
    return [{"call": r["call"], "status": r["status"], "fp": _fp(r["pub"]),
             "changed": r["changed"], "note": r["note"]} for r in svc.store.key_list()]


def user_action(svc: MessageService, word: str, call: str) -> str:
    """OK | REVOKE | DEL for the key of call. Returns the text for the sysop."""
    call = auth.base(call)
    row = svc.store.key_get(call)
    if row is None:
        raise KeysError(f"{call}: no client key.")
    fp = _fp(row["pub"])
    if word == "OK":
        svc.store.key_status(call, "active")
        log.info("sysop: client key of %s released (%s)", call, fp)
        return f"{call}: key {fp} released - the next login is in client mode."
    if word == "REVOKE":
        svc.store.key_status(call, "revoked")
        log.info("sysop: client key of %s revoked (%s)", call, fp)
        return f"{call}: key {fp} revoked. A new key needs USER OK again."
    if word == "DEL":
        svc.store.key_delete(call)
        log.info("sysop: client key of %s deleted (%s)", call, fp)
        return f"{call}: key {fp} deleted."
    raise KeysError(f"unknown action {word}")


def this_box(svc: MessageService) -> dict:
    ident = svc.box_identity()
    return {"box": svc.cfg.station.mailbox_call.upper(), "pub": ident.pub, "fp": ident.fp}


def trusted(svc: MessageService) -> list[dict]:
    return [{"box": r["box"], "pub": r["pub"], "fp": _fp(r["pub"]), "added": r["added"],
             "note": r["note"]} for r in svc.store.trust_list()]


def trust_add(svc: MessageService, box: str, pub: str) -> str:
    box = box.strip().upper()
    if not (3 <= len(box) <= 9 and box.replace("-", "").isalnum() and box.isascii()):
        raise KeysError(f"{box}: not a mailbox call.")
    if box == svc.cfg.station.mailbox_call.upper():
        raise KeysError("That is this box itself.")
    try:
        fp = auth.fingerprint(auth.b64d(pub.strip(), 32))
    except auth.AuthError:
        raise KeysError("Not a public key (43 characters, from TRUST at the other box).") \
            from None
    svc.store.trust_put(box, pub.strip())
    log.info("sysop: TinyBox %s trusted (key %s)", box, fp)
    return f"{box}: trusted, key {fp} - its users log in here with their certificate."


def trust_del(svc: MessageService, box: str) -> str:
    box = box.strip().upper()
    if not svc.store.trust_delete(box):
        raise KeysError(f"{box}: not trusted here.")
    log.info("sysop: TinyBox %s no longer trusted", box)
    return f"{box}: no longer trusted."
