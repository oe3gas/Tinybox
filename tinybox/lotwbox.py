"""LoTW at the TinyBox (CR113 stage 2): the ARRL certificates the sysop trusts, and
the proof a client sends for its key (prcore/lotw.py has the format and the checks).

Protocol (cap LOTW, in client mode or while the key waits for the sysop):

    //LOTW?                     -> //LOTW until=<YYYY-MM-DD>   this key is confirmed
                                   //LOTW -                    not (yet)
                                   //LOTW off                  this box cannot check LoTW
    //LOTWP <i>/<n> <chunk>     the proof (prcore.lotw.wire_encode: normally only the
                                callsign certificate, every binary field base64url
                                once) in n lines of at most CHUNK characters; after
                                the last one
                             -> //LOTW ok until=<YYYY-MM-DD>
                                //LOTW more                 chain not closed with the
                                                            ARRL certificates here: send
                                                            all certificates
                                //LOTW err <reason>

Live over the air (OE3GAS, 11.11.2026) the first form - JSON in base64url with the
whole chain - took 45 lines, 9.4 KB, 75 s at 1200 Bd; the compact one with only
the callsign certificate about 11 lines, 2.2 KB.

The proof is bound to the key the client logged in with (call and Ed25519 key in
it, signed with the LoTW key) - nobody can use it for another key, so the upload
needs no signature of its own. A released key keeps its status and gets the LoTW
mark; a waiting key counts at once only with [client] lotw_release = yes.

ARRL certificates: the sysop takes them from a .p12 of TQSL (or a .pem/.der/.cer)
- LOTW ADD <file> [password] at the console - and compares the fingerprint.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from prcore import auth, lotw
from prcore.text import isnum

if TYPE_CHECKING:
    from .session import Session
    from .store import Store

log = logging.getLogger(__name__)

CHUNK = 200
MAX_CHUNKS = 64                       # 12.8 KB - a proof is about 3-6 KB
MAX_FILE = 64 * 1024


class LotwBoxError(ValueError):
    pass


def fp_of(der: bytes) -> str:
    return hashlib.sha256(der).hexdigest().upper()


def roots(store: Store) -> list:
    if not lotw.available():
        return []
    from cryptography import x509
    out = []
    for r in store.lotw_roots():
        try:
            out.append(x509.load_der_x509_certificate(r["der"]))
        except ValueError:
            log.warning("LoTW: stored ARRL certificate %s is damaged", r["fp"][:16])
    return out


def ready(store: Store) -> bool:
    return lotw.available() and bool(store.lotw_roots())


def certs_in_file(data: bytes, password: str = "") -> list:
    """The CA certificates in a .p12, .pem, .der or .cer file (x509 objects)."""
    if not lotw.available():
        raise LotwBoxError("the Python package 'cryptography' is missing")
    from cryptography import x509
    from cryptography.hazmat.primitives.serialization import pkcs12
    found = []
    if b"-----BEGIN CERTIFICATE-----" in data:
        found = x509.load_pem_x509_certificates(data)
    else:
        try:
            found = [x509.load_der_x509_certificate(data)]
        except ValueError:
            for pw in ([password.encode()] if password else []) + [None, b""]:
                try:
                    _, cert, more = pkcs12.load_key_and_certificates(data, pw)
                    found = [c for c in [cert, *(more or [])] if c is not None]
                    break
                except ValueError:
                    continue
            else:
                raise LotwBoxError("not a certificate file (.p12 needs its password)") from None
    ca = []
    for c in found:
        try:
            bc = c.extensions.get_extension_for_class(x509.BasicConstraints).value
            if bc.ca:
                ca.append(c)
        except x509.ExtensionNotFound:
            pass
    if not ca:
        raise LotwBoxError("no CA certificate in the file (only a callsign certificate?)")
    return ca


def add_file(store: Store, path: str, password: str = "") -> list[str]:
    """LOTW ADD: the CA certificates of the file become trusted. Lines for the sysop."""
    from cryptography.hazmat.primitives import serialization
    p = Path(path.strip().strip('"'))
    try:
        data = p.read_bytes()[:MAX_FILE + 1]
    except OSError as exc:
        raise LotwBoxError(f"{p}: {exc.strerror or exc}") from None
    if len(data) > MAX_FILE:
        raise LotwBoxError(f"{p}: too large for a certificate file")
    out = []
    for c in certs_in_file(data, password):
        der = c.public_bytes(serialization.Encoding.DER)
        fp = fp_of(der)
        new = store.lotw_root_put(fp, c.subject.rfc4514_string(), der)
        info = lotw.describe(c)
        out.append(f"{'added' if new else 'known'}: {info['subject']} (until {info['until']})")
        out.append(f"   fingerprint {fp_pretty(fp)}")
        if new:
            log.warning("sysop: LoTW certificate trusted - %s, %s", info["subject"], fp[:32])
    return out


def fp_pretty(fp: str) -> str:
    return " ".join(fp[i:i + 4] for i in range(0, 32, 4))


def key_row(s: Session) -> dict | None:
    pub = s.auth_pub if s.auth_pub is not None else getattr(s, "_wait_pub", None)
    if pub is None:
        return None
    return s.service.store.key_get(auth.base(s.call), auth.b64e(pub))


def ask(s: Session) -> None:
    row = key_row(s)
    if not ready(s.service.store):
        s.out("//LOTW off")
    elif row and row.get("lotw") and row["lotw"] >= _today():
        s.out(f"//LOTW until={row['lotw']}")
    else:
        s.out("//LOTW -")


def _today() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def part(s: Session, args: list[str]) -> bool:
    """//LOTWP i/n chunk. Returns True when the key became released by it (the
    caller then completes the login)."""
    if len(args) != 2 or "/" not in args[0]:
        s.out("//LOTW err syntax")
        return False
    i, _, n = args[0].partition("/")
    if not (isnum(i) and isnum(n)) or not 1 <= int(i) <= int(n) <= MAX_CHUNKS \
            or len(args[1]) > CHUNK:
        s.out("//LOTW err syntax")
        return False
    i, n = int(i), int(n)
    buf = getattr(s, "_lotw_buf", None)
    if i == 1:
        buf = s._lotw_buf = []
    if buf is None or len(buf) != i - 1:
        s._lotw_buf = None
        s.out("//LOTW err order")
        return False
    buf.append(args[1])
    if i < n:
        return False
    s._lotw_buf = None
    return _check(s, "".join(buf))


def _check(s: Session, text: str) -> bool:
    store = s.service.store
    row = key_row(s)
    if row is None:
        s.out("//LOTW err no key")
        return False
    if not ready(store):
        s.out("//LOTW off")
        return False
    try:
        if text.startswith(lotw.WIRE_V + "."):          # compact, since 2026.11.11.10
            proof = lotw.wire_decode(text)
        else:                                            # the first form: JSON, base64url
            proof = json.loads(base64.urlsafe_b64decode(text + "=" * (-len(text) % 4)))
    except (ValueError, binascii.Error):                 # LotwError is a ValueError too
        s.out("//LOTW err damaged")
        return False
    if not isinstance(proof, dict) or proof.get("pub") != row["pub"] \
            or proof.get("call") != auth.base(s.call):
        log.warning("%s: LoTW proof for another key or call refused", s.call)
        s.out("//LOTW err not for this key")
        return False
    try:
        info = lotw.verify(proof, roots(store))
    except lotw.LotwError as exc:
        if "trusted ARRL" in str(exc) and len(proof.get("certs", [])) == 1:
            s.out("//LOTW more")                         # only the callsign one came
            return False
        log.warning("%s: LoTW proof refused - %s", s.call, exc)
        s.out(f"//LOTW err {exc}")
        return False
    store.key_lotw(row["id"], info["until"])
    released = False
    if row["status"] in ("pending", "cert") and s.cfg.client.lotw_release:
        store.key_status(row["id"], "active")
        released = True
    log.warning("%s: key %s confirmed with LoTW (until %s)%s", s.call,
                auth.fingerprint(auth.b64d(row["pub"], 32)), info["until"],
                " - released by lotw_release" if released else "")
    s.out(f"//LOTW ok until={info['until']}")
    return released
