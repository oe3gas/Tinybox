"""Client keys and trusted TinyBoxen (CR93) - the actions behind the sysop
console (USER, TRUST) and the sysop web GUI (Keys), in one place.

    user keys     one per device and call: released at this box (active),
                  waiting (pending), revoked, or known through a certificate of
                  a trusted home BBS (cert)
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
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return [{"id": r["id"], "call": r["call"], "status": r["status"], "fp": _fp(r["pub"]),
             "device": r["device"], "changed": r["changed"], "note": r["note"],
             "lotw": r["lotw"] if r.get("lotw") and r["lotw"] >= today else ""}   # CR113
            for r in svc.store.key_list()]


def _norm_fp(text: str) -> str:
    return text.upper().replace("-", "")


def pick(svc: MessageService, word: str, call: str, sel: str = "") -> dict:
    """The key of call an action means: by its fingerprint (the first characters
    are enough, with or without '-'), or the only one that fits. One key per
    device - so with several keys the sysop names the one."""
    call = auth.base(call)
    rows = svc.store.keys_of(call)
    if not rows:
        raise KeysError(f"{call}: no client key.")
    fits = {"OK": lambda r: r["status"] != "active", "REVOKE": lambda r: r["status"] != "revoked"}
    cand = [r for r in rows if fits.get(word, lambda r: True)(r)]
    if sel:
        cand = [r for r in rows if _norm_fp(_fp(r["pub"])).startswith(_norm_fp(sel))]
    if len(cand) == 1:
        return cand[0]
    listed = ", ".join(f"{_fp(r['pub'])} {r['status']}" + (f" ({r['device']})" if r["device"] else "")
                       for r in (cand or rows))
    if not cand:
        raise KeysError(f"{call}: no key fits ({listed}).")
    raise KeysError(f"{call} has several keys - add the fingerprint, e.g. USER {word} {call} "
                    f"{_fp(cand[0]['pub'])[:4]}: {listed}")


def user_action(svc: MessageService, word: str, call: str, sel: str = "",
                key_id: int | None = None) -> str:
    """OK | REVOKE | DEL for one key (by call + fingerprint, or by its id from the
    web GUI). Returns the text for the sysop."""
    row = svc.store.key_by_id(key_id) if key_id is not None else pick(svc, word, call, sel)
    if row is None:
        raise KeysError("no such key.")
    call, fp, kid = row["call"], _fp(row["pub"]), row["id"]
    dev = f" ({row['device']})" if row["device"] else ""
    if word == "OK":
        svc.store.key_status(kid, "active")
        log.info("sysop: client key of %s released (%s%s)", call, fp, dev)
        return f"{call}: key {fp}{dev} released - its next login is in client mode."
    if word == "REVOKE":
        svc.store.key_status(kid, "revoked")
        log.info("sysop: client key of %s revoked (%s%s)", call, fp, dev)
        return f"{call}: key {fp}{dev} revoked - the other keys of {call} stay."
    if word == "DEL":
        svc.store.key_delete(kid)
        log.info("sysop: client key of %s deleted (%s%s)", call, fp, dev)
        return f"{call}: key {fp}{dev} deleted (its next login waits again)."
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
