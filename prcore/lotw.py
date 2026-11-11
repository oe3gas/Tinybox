"""LoTW as anchor of trust (CR113): the own key, confirmed with the LoTW certificate.

Whoever has an LoTW callsign certificate of the ARRL (TQSL, .p12) can confirm his
TinyBox key with it - the highest trust in our chain: the ARRL has checked the
licence, the callsign is in the certificate (subject attribute AROcallsign, OID
1.3.6.1.4.1.12348.1.1, as in tqsllib).

Not derived, counter-signed: the Ed25519 key is made as always (prcore/auth.py),
then the LoTW key signs ONCE, on the user's own PC

    TINYBOX-LOTW1|<base call>|<Ed25519 public key, base64url>|<YYYYMMDD>

The .p12 and its password never leave the PC and are not stored. What is kept
and later goes to the home BBS (once, about 2 KB) is the proof:

    {"v": 1, "call", "pub", "date", "alg" (rsa-sha256 | ecdsa-sha256), "sig",
     "certs": [leaf, intermediates ...] (DER, base64), "until" (leaf not after)}

The BBS checks the chain up to an ARRL root it trusts (verify(), roots = the
sysop's list - the ARRL certificates are not public, so the sysop takes them from
a .p12 and compares the fingerprint), the callsign, the signature, the validity.
A revocation by the ARRL after issuing cannot be seen offline: the proof counts
only until the LoTW certificate ends.

Needs the `cryptography` package (RSA, PKCS#12, X.509) - without it, no LoTW.
"""

from __future__ import annotations

import base64
import datetime as _dt
import hashlib

from .text import isnum

CALLSIGN_OID = "1.3.6.1.4.1.12348.1.1"        # AROcallsign (tqsllib)
DXCC_OID = "1.3.6.1.4.1.12348.1.4"            # dxccEntity
PREFIX = b"TINYBOX-LOTW1|"
MAX_P12 = 64 * 1024
MAX_CERTS = 5


class LotwError(ValueError):
    pass


def available() -> bool:
    try:
        import cryptography.hazmat.primitives.serialization.pkcs12  # noqa: F401
        return True
    except ImportError:
        return False


def _need():
    if not available():
        raise LotwError("the Python package 'cryptography' is missing - "
                        "install it: py -3 -m pip install cryptography")


def message(call: str, pub: str, date: str) -> bytes:
    return PREFIX + f"{call}|{pub}|{date}".encode("ascii")


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _attr(name, oid: str) -> str:
    from cryptography.x509 import ObjectIdentifier
    vals = name.get_attributes_for_oid(ObjectIdentifier(oid))
    return str(vals[0].value).strip().upper() if vals else ""


def _not_after(cert) -> _dt.datetime:
    t = getattr(cert, "not_valid_after_utc", None)
    return t if t is not None else cert.not_valid_after.replace(tzinfo=_dt.timezone.utc)


def _not_before(cert) -> _dt.datetime:
    t = getattr(cert, "not_valid_before_utc", None)
    return t if t is not None else cert.not_valid_before.replace(tzinfo=_dt.timezone.utc)


def fingerprint(cert) -> str:
    from cryptography.hazmat.primitives import serialization
    h = hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest().upper()
    return ":".join(h[i:i + 2] for i in range(0, 32, 2))      # first 16 bytes, readable


def describe(cert) -> dict:
    return {"call": _attr(cert.subject, CALLSIGN_OID), "dxcc": _attr(cert.subject, DXCC_OID),
            "subject": cert.subject.rfc4514_string(), "issuer": cert.issuer.rfc4514_string(),
            "from": _not_before(cert).strftime("%Y-%m-%d"),
            "until": _not_after(cert).strftime("%Y-%m-%d"), "fp": fingerprint(cert)}


def _sign(key, data: bytes) -> tuple[str, bytes]:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
    if isinstance(key, rsa.RSAPrivateKey):
        return "rsa-sha256", key.sign(data, padding.PKCS1v15(), hashes.SHA256())
    if isinstance(key, ec.EllipticCurvePrivateKey):
        return "ecdsa-sha256", key.sign(data, ec.ECDSA(hashes.SHA256()))
    raise LotwError("the key in the .p12 is neither RSA nor EC")


def _check_sig(cert, alg: str, sig: bytes, data: bytes) -> bool:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
    pub = cert.public_key()
    try:
        if alg == "rsa-sha256" and isinstance(pub, rsa.RSAPublicKey):
            pub.verify(sig, data, padding.PKCS1v15(), hashes.SHA256())
            return True
        if alg == "ecdsa-sha256" and isinstance(pub, ec.EllipticCurvePublicKey):
            pub.verify(sig, data, ec.ECDSA(hashes.SHA256()))
            return True
    except InvalidSignature:
        return False
    return False


def load_p12(data: bytes, password: str):
    """(key, leaf certificate, [other certificates]) - or LotwError in plain words."""
    _need()
    from cryptography.hazmat.primitives.serialization import pkcs12
    if not data or len(data) > MAX_P12:
        raise LotwError("that is not a .p12 file of TQSL")
    pw = password.encode("utf-8") if password else None
    try:
        key, cert, more = pkcs12.load_key_and_certificates(data, pw)
    except ValueError:
        if pw is None:                         # TQSL without a password: try "" as well
            try:
                key, cert, more = pkcs12.load_key_and_certificates(data, b"")
            except ValueError:
                raise LotwError("cannot open the .p12 - wrong password?") from None
        else:
            raise LotwError("cannot open the .p12 - wrong password?") from None
    if key is None or cert is None:
        raise LotwError("the .p12 has no private key with its certificate - in TQSL use "
                        "'Save Callsign Certificate' (not only the public part)")
    return key, cert, list(more or [])


def sign_binding(p12: bytes, password: str, call: str, pub: str,
                 now: _dt.datetime | None = None) -> dict:
    """The proof for call and the Ed25519 key pub, signed with the LoTW key."""
    from cryptography.hazmat.primitives import serialization
    key, cert, more = load_p12(p12, password)
    now = now or _dt.datetime.now(_dt.timezone.utc)
    info = describe(cert)
    if not info["call"]:
        raise LotwError("this certificate has no callsign - is it really one of LoTW?")
    if info["call"] != call:
        raise LotwError(f"the LoTW certificate is for {info['call']}, the client runs as {call}")
    if not _not_before(cert) <= now <= _not_after(cert):
        raise LotwError(f"the LoTW certificate is not valid now ({info['from']} .. {info['until']})")
    date = now.strftime("%Y%m%d")
    alg, sig = _sign(key, message(call, pub, date))
    der = [cert.public_bytes(serialization.Encoding.DER)]
    der += [c.public_bytes(serialization.Encoding.DER) for c in more[:MAX_CERTS - 1]]
    proof = {"v": 1, "call": call, "pub": pub, "date": date, "alg": alg, "sig": _b64(sig),
             "certs": [_b64(d) for d in der], "until": info["until"]}
    verify(proof, roots=None, now=now)               # our own check before keeping it
    return proof


def _certs(proof: dict) -> list:
    from cryptography import x509
    out = []
    for text in proof.get("certs", [])[:MAX_CERTS]:
        try:
            out.append(x509.load_der_x509_certificate(base64.b64decode(text, validate=True)))
        except (ValueError, TypeError):
            raise LotwError("a certificate in the proof is damaged") from None
    if not out:
        raise LotwError("no certificate in the proof")
    return out


def _issued_by(cert, issuer) -> bool:
    if cert.issuer != issuer.subject:
        return False
    try:
        cert.verify_directly_issued_by(issuer)
        return True
    except Exception:                    # wrong signature, unsupported algorithm ...
        return False


def verify(proof: dict, roots: list | None, now: _dt.datetime | None = None) -> dict:
    """Checks a proof. roots = trusted ARRL certificates (x509 objects); None = only
    the proof itself (signature, callsign, validity, the chain inside the proof) -
    that is what the client checks before it keeps it. Returns describe(leaf)."""
    _need()
    now = now or _dt.datetime.now(_dt.timezone.utc)
    if not isinstance(proof, dict) or proof.get("v") != 1:
        raise LotwError("not a LoTW proof (v=1)")
    call, pub, date = str(proof.get("call", "")), str(proof.get("pub", "")), str(proof.get("date", ""))
    if not (call and pub and len(date) == 8 and isnum(date)):
        raise LotwError("the proof is incomplete")
    chain = _certs(proof)
    leaf = chain[0]
    info = describe(leaf)
    if info["call"] != call:
        raise LotwError(f"the certificate is for {info['call']}, the proof for {call}")
    try:
        sig = base64.b64decode(str(proof.get("sig", "")), validate=True)
    except (ValueError, TypeError):
        raise LotwError("the signature is damaged") from None
    if not _check_sig(leaf, str(proof.get("alg", "")), sig, message(call, pub, date)):
        raise LotwError("the signature does not fit")
    if not _not_before(leaf) <= now <= _not_after(leaf):
        raise LotwError(f"the LoTW certificate is not valid now (until {info['until']})")
    for lower, upper in zip(chain, chain[1:]):       # the chain as it came
        if not _issued_by(lower, upper):
            raise LotwError("the certificates in the proof do not form a chain")
    if roots is not None:
        top = chain[-1]
        if not any(_issued_by(top, r) or top == r for r in roots):
            raise LotwError("the chain does not end at a trusted ARRL certificate")
    info["chain"] = [describe(c)["subject"] for c in chain[1:]]
    return info


# --- over the air (CR113): compact, each binary field base64url once ---------------
#
#   2.<call>.<Ed25519 key>.<YYYYMMDD>.<alg>.<sig>.<until>.<cert>[,<cert> ...]
#
# Normally only the callsign certificate: the TinyBox has the ARRL ones (LOTW ADD
# from the same kind of .p12). It answers "more" if it cannot close the chain -
# then the client sends all of them (full=True).

WIRE_V = "2"


def _u(text: str) -> str:
    return base64.urlsafe_b64encode(base64.b64decode(text)).decode().rstrip("=")


def _s(text: str) -> str:
    return base64.b64encode(base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))).decode()


def wire_encode(proof: dict, full: bool = False) -> str:
    certs = proof.get("certs", [])
    certs = certs if full else certs[:1]
    return ".".join([WIRE_V, proof["call"], proof["pub"], proof["date"], proof["alg"],
                     _u(proof["sig"]), proof.get("until", ""), ",".join(_u(c) for c in certs)])


def wire_decode(text: str) -> dict:
    """The proof dict (as kept by the client) from the over-the-air form."""
    parts = text.split(".")
    if len(parts) != 8 or parts[0] != WIRE_V:
        raise LotwError("not a LoTW proof")
    _, call, pub, date, alg, sig, until, certs = parts
    try:
        return {"v": 1, "call": call, "pub": pub, "date": date, "alg": alg, "sig": _s(sig),
                "until": until, "certs": [_s(c) for c in certs.split(",") if c][:MAX_CERTS]}
    except (ValueError, TypeError):
        raise LotwError("the proof is damaged") from None

