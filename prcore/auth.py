"""Signatures for TinyBox (CR93 login and signed commands, later CR90/CR94): Ed25519 (RFC 8032).

Authentication, not encryption - what is signed stays readable, as amateur
radio requires. Keys and signatures travel as base64url without padding:

    public key  32 bytes -> 43 characters
    signature   64 bytes -> 86 characters
    fingerprint SHA-256 of the public key, first 6 bytes: "7F3A-91C2-44E0"

The `cryptography` package is used when it is installed (fast, constant time).
Without it a small pure-Python implementation after the reference code of
RFC 8032 section 6 takes over, so TinyBox and the client still need no extra
packages; tests/test_cr93.py checks both against the RFC test vectors. The pure
code is not constant time - which matters for signing on a machine others can
time precisely, not over a radio link.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from pathlib import Path

from .text import isnum

try:                                                      # the fast path
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (Ed25519PrivateKey,
                                                                   Ed25519PublicKey)
    HAVE_CRYPTOGRAPHY = True
except ImportError:                                       # pragma: no cover - depends on host
    HAVE_CRYPTOGRAPHY = False


class AuthError(ValueError):
    pass


def b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64d(text: str, size: int) -> bytes:
    """Decode exactly `size` bytes, or AuthError."""
    try:
        if not text.isascii() or len(text) != (size * 4 + 2) // 3:
            raise ValueError
        data = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except (ValueError, TypeError):
        raise AuthError("not a key or signature") from None
    if len(data) != size:
        raise AuthError("not a key or signature")
    return data


# --- pure Python Ed25519 (RFC 8032, 6. Ed25519 Python illustration) -------------

_p = 2 ** 255 - 19
_q = 2 ** 252 + 27742317777372353535851937790883648493
_d = -121665 * pow(121666, _p - 2, _p) % _p
_I = pow(2, (_p - 1) // 4, _p)


def _inv(x: int) -> int:
    return pow(x, _p - 2, _p)


def _recover_x(y: int, sign: int) -> int | None:
    if y >= _p:
        return None
    x2 = (y * y - 1) * _inv(_d * y * y + 1)
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_p + 3) // 8, _p)
    if (x * x - x2) % _p != 0:
        x = x * _I % _p
    if (x * x - x2) % _p != 0:
        return None
    if (x & 1) != sign:
        x = _p - x
    return x


_gy = 4 * _inv(5) % _p
_gx = _recover_x(_gy, 0)
_G = (_gx, _gy, 1, _gx * _gy % _p)


def _add(P, Q):
    A, B = (P[1] - P[0]) * (Q[1] - Q[0]) % _p, (P[1] + P[0]) * (Q[1] + Q[0]) % _p
    C, D = 2 * P[3] * Q[3] * _d % _p, 2 * P[2] * Q[2] % _p
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F % _p, G * H % _p, F * G % _p, E * H % _p)


def _mul(s: int, P):
    Q = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            Q = _add(Q, P)
        P = _add(P, P)
        s >>= 1
    return Q


def _equal(P, Q) -> bool:
    return (P[0] * Q[2] - Q[0] * P[2]) % _p == 0 and (P[1] * Q[2] - Q[1] * P[2]) % _p == 0


def _compress(P) -> bytes:
    zinv = _inv(P[2])
    x, y = P[0] * zinv % _p, P[1] * zinv % _p
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _decompress(s: bytes):
    y = int.from_bytes(s, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    return None if x is None else (x, y, 1, x * y % _p)


def _h(m: bytes) -> int:
    return int.from_bytes(hashlib.sha512(m).digest(), "little")


def _secret_expand(secret: bytes) -> tuple[int, bytes]:
    h = hashlib.sha512(secret).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def _py_public(secret: bytes) -> bytes:
    a, _ = _secret_expand(secret)
    return _compress(_mul(a, _G))


def _py_sign(secret: bytes, msg: bytes) -> bytes:
    a, prefix = _secret_expand(secret)
    A = _compress(_mul(a, _G))
    r = _h(prefix + msg) % _q
    R = _compress(_mul(r, _G))
    k = _h(R + A + msg) % _q
    return R + int.to_bytes((r + k * a) % _q, 32, "little")


def _py_verify(public: bytes, msg: bytes, sig: bytes) -> bool:
    A = _decompress(public)
    R = _decompress(sig[:32])
    if A is None or R is None:
        return False
    s = int.from_bytes(sig[32:], "little")
    if s >= _q:
        return False
    k = _h(sig[:32] + public + msg) % _q
    return _equal(_mul(s, _G), _add(R, _mul(k, A)))


# --- the interface ---------------------------------------------------------------

def public_key(secret: bytes) -> bytes:
    if len(secret) != 32:
        raise AuthError("a secret key is 32 bytes")
    if HAVE_CRYPTOGRAPHY:
        from cryptography.hazmat.primitives import serialization
        return Ed25519PrivateKey.from_private_bytes(secret).public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return _py_public(secret)


def sign(secret: bytes, msg: bytes) -> bytes:
    if HAVE_CRYPTOGRAPHY:
        return Ed25519PrivateKey.from_private_bytes(secret).sign(msg)
    return _py_sign(secret, msg)


def verify(public: bytes, msg: bytes, sig: bytes) -> bool:
    if len(public) != 32 or len(sig) != 64:
        return False
    if HAVE_CRYPTOGRAPHY:
        try:
            Ed25519PublicKey.from_public_bytes(public).verify(sig, msg)
            return True
        except (InvalidSignature, ValueError):
            return False
    return _py_verify(public, msg, sig)


def fingerprint(public: bytes) -> str:
    """'7F3A-91C2-44E0': to compare by voice or on paper (48 bits)."""
    h = hashlib.sha256(public).hexdigest()[:12].upper()
    return f"{h[:4]}-{h[4:8]}-{h[8:]}"


def login_message(box: str, call: str, nonce: str) -> bytes:
    """What a client signs to log in (CR93): the challenge, for this mailbox and
    this call - a recorded answer is good for nothing else."""
    return f"TINYBOX-AUTH1|{base(box)}|{base(call)}|{nonce}".encode("ascii")


def command_message(box: str, call: str, nonce: str, counter: int, line: str,
                    payload: list[str] | tuple[str, ...] = ()) -> bytes:
    """What a client signs for a critical command (CR93 stage 2): the command line
    (spaces as one), its number in this login and the lines that follow it (subject
    and text of //SEND) - bound to the login challenge, the mailbox and the call."""
    text = (f"TINYBOX-CMD1|{base(box)}|{base(call)}|{nonce}|{counter}|"
            + " ".join(line.split()))
    if payload:
        text += "\n" + "\n".join(payload)
    return text.encode("utf-8")


# --- certificates (CR93 stage 3) ---------------------------------------------------
#
# The home BBS confirms the key of a user with its own key (box.key):
#
#     TBC1:<call>:<user key>:<issuer>:<valid until YYYYMMDD>:<signature of the issuer>
#
# signed: "TINYBOX-CERT1|<call>|<user key>|<issuer>|<until>". call = base call, issuer
# = mailbox call of the home BBS (with SSID). Another TinyBox whose sysop trusts
# that issuer (TRUST, after comparing its fingerprint) lets the user log in with
# it. About 165 bytes, sent only at the login at another box.

CERT_DAYS = 180              # valid this long
CERT_RENEW_DAYS = 60         # the client fetches a new one at home when fewer are left


def cert_message(call: str, pub: str, issuer: str, until: str) -> bytes:
    return f"TINYBOX-CERT1|{base(call)}|{pub}|{issuer.upper()}|{until}".encode("ascii")


def make_cert(issuer_key: Identity, call: str, pub: str, issuer: str, until: str) -> str:
    sig = b64e(sign(issuer_key.secret, cert_message(call, pub, issuer, until)))
    return f"TBC1:{base(call)}:{pub}:{issuer.upper()}:{until}:{sig}"


def parse_cert(text: str) -> dict:
    """The fields of a certificate (not checked against any key), or AuthError."""
    parts = text.strip().split(":")
    if len(parts) != 6 or parts[0] != "TBC1":
        raise AuthError("not a certificate")
    _, call, pub, issuer, until, sig = parts
    b64d(pub, 32)
    raw = b64d(sig, 64)
    if not (isnum(until) and len(until) == 8) \
            or not (call.isascii() and call.isalnum() and 3 <= len(call) <= 6) \
            or not (issuer.isascii() and 3 <= len(issuer) <= 9
                    and issuer.replace("-", "").isalnum()):
        raise AuthError("not a certificate")
    return {"call": call.upper(), "pub": pub, "issuer": issuer.upper(), "until": until,
            "sig": raw}


def check_cert(cert: dict, issuer_pub: bytes, today: str) -> bool:
    """Signature of the issuer right and not expired (today = YYYYMMDD)."""
    return cert["until"] >= today and verify(
        issuer_pub, cert_message(cert["call"], cert["pub"], cert["issuer"], cert["until"]),
        cert["sig"])


def peer_message(signer: str, other: str, nonce: str) -> bytes:
    """What a TBClient signs for another TBClient (CR99): the other one's challenge,
    with both calls - a recorded answer is good for no other connection."""
    return f"TINYBOX-PEER1|{base(signer)}|{base(other)}|{nonce}".encode("ascii")


def base(call: str) -> str:
    return call.strip().upper().split("-", 1)[0]


def new_nonce() -> str:
    return b64e(os.urandom(16))


# --- the key of a station: one file, the same on every device -------------------

class Identity:
    """data/<program>/identity.key - 32 random bytes as base64url, one line. The
    key belongs to the call, not to the PC: copy the file to use it elsewhere."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.secret = self._load_or_create()
        self.public = public_key(self.secret)

    def _load_or_create(self) -> bytes:
        try:
            text = self.path.read_text(encoding="ascii", errors="replace").strip()
        except FileNotFoundError:
            text = None
        if text is not None:
            try:
                return b64d(text, 32)
            except AuthError:
                # never replaced silently: the sysop released exactly this key
                raise AuthError(f"{self.path} is damaged - put the copy back, or delete it "
                                "for a new key (the sysop then releases that one)") from None
        secret = os.urandom(32)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as f:
            f.write(b64e(secret) + "\n")
        os.replace(tmp, self.path)
        return secret

    @property
    def pub(self) -> str:
        return b64e(self.public)

    @property
    def fp(self) -> str:
        return fingerprint(self.public)

    @property
    def device(self) -> str:
        """A short mark of this PC for the sysop's key list (one key per device):
        8 hex characters, keyed hash of the computer name with the secret key - the
        name itself never goes on air and cannot be found out by trying names."""
        import socket
        name = socket.gethostname().encode("utf-8", "replace")
        return hmac.new(self.secret, b"TINYBOX-DEV1|" + name,
                        hashlib.sha256).hexdigest()[:8].upper()

    def sign_login(self, box: str, call: str, nonce: str) -> str:
        return b64e(sign(self.secret, login_message(box, call, nonce)))

    def sign_peer(self, me: str, other: str, nonce: str) -> str:
        return b64e(sign(self.secret, peer_message(me, other, nonce)))

    def sign_command(self, box: str, call: str, nonce: str, counter: int, line: str,
                     payload: list[str] | tuple[str, ...] = ()) -> str:
        return b64e(sign(self.secret, command_message(box, call, nonce, counter, line, payload)))
