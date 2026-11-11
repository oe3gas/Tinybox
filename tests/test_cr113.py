"""CR113: LoTW as anchor of trust - the client signs its key with the .p12 of TQSL.

The certificates here are made up like LoTW ones (root -> intermediate -> callsign
certificate with the AROcallsign attribute); the real ARRL ones are not public."""

from __future__ import annotations

import asyncio
import base64
import datetime as dt
import json
import tempfile
import unittest

from prcore import auth, lotw

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID
    HAVE = True
except ImportError:                      # pragma: no cover
    HAVE = False

NOW = dt.datetime(2026, 11, 11, 12, 0, tzinfo=dt.timezone.utc)


def _name(cn, call=None):
    attrs = [x509.NameAttribute(NameOID.COMMON_NAME, cn)]
    if call:
        attrs.append(x509.NameAttribute(x509.ObjectIdentifier(lotw.CALLSIGN_OID), call))
        attrs.append(x509.NameAttribute(x509.ObjectIdentifier(lotw.DXCC_OID), "206"))
    return x509.Name(attrs)


def _cert(subject, issuer, key, issuer_key, ca, start, end):
    b = (x509.CertificateBuilder().subject_name(subject).issuer_name(issuer)
         .public_key(key.public_key()).serial_number(x509.random_serial_number())
         .not_valid_before(start).not_valid_after(end)
         .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True))
    return b.sign(issuer_key, hashes.SHA256())


def make_lotw(call="OE3GAS", start=NOW - dt.timedelta(days=100), end=NOW + dt.timedelta(days=900)):
    k_root = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    k_int = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    k_leaf = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    root = _cert(_name("Test LoTW Root CA"), _name("Test LoTW Root CA"), k_root, k_root, True,
                 NOW - dt.timedelta(days=3000), NOW + dt.timedelta(days=3000))
    inter = _cert(_name("Test LoTW Production CA"), root.subject, k_int, k_root, True,
                  NOW - dt.timedelta(days=2000), NOW + dt.timedelta(days=2000))
    leaf = _cert(_name(call, call), inter.subject, k_leaf, k_int, False, start, end)
    return k_leaf, leaf, inter, root


def p12_of(key, leaf, chain, password=b"geheim", legacy=False):
    if password and legacy:                       # like older TQSL exports (3DES, SHA1)
        enc = (serialization.PrivateFormat.PKCS12.encryption_builder()
               .kdf_rounds(2048).key_cert_algorithm(pkcs12.PBES.PBESv1SHA1And3KeyTripleDESCBC)
               .hmac_hash(hashes.SHA1()).build(password))
    elif password:
        enc = serialization.BestAvailableEncryption(password)
    else:
        enc = serialization.NoEncryption()
    return pkcs12.serialize_key_and_certificates(b"OE3GAS", key, leaf, chain, enc)


@unittest.skipUnless(HAVE, "needs cryptography")
class Sign(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key, cls.leaf, cls.inter, cls.root = make_lotw()
        cls.pub = auth.b64e(b"\x07" * 32)

    def proof(self, **kw):
        p12 = p12_of(self.key, self.leaf, [self.inter, self.root], **kw)
        return lotw.sign_binding(p12, "geheim" if kw.get("password", b"geheim") else "",
                                 "OE3GAS", self.pub, now=NOW)

    def test_sign_and_verify_up_to_the_root(self):
        p = self.proof()
        self.assertEqual((p["call"], p["pub"], p["date"], p["alg"]),
                         ("OE3GAS", self.pub, "20261111", "rsa-sha256"))
        self.assertEqual(len(p["certs"]), 3)
        info = lotw.verify(p, roots=[self.root], now=NOW)
        self.assertEqual((info["call"], info["dxcc"]), ("OE3GAS", "206"))
        # the .p12 and the password are not in the proof
        self.assertNotIn("geheim", json.dumps(p))

    def test_legacy_and_no_password(self):
        self.assertEqual(self.proof(legacy=True)["call"], "OE3GAS")
        self.assertEqual(self.proof(password=None)["call"], "OE3GAS")

    def test_wrong_password(self):
        p12 = p12_of(self.key, self.leaf, [self.inter])
        with self.assertRaisesRegex(lotw.LotwError, "password"):
            lotw.sign_binding(p12, "falsch", "OE3GAS", self.pub, now=NOW)

    def test_other_call_refused(self):
        p12 = p12_of(self.key, self.leaf, [self.inter])
        with self.assertRaisesRegex(lotw.LotwError, "OE3GAS, the client runs as OE1ABC"):
            lotw.sign_binding(p12, "geheim", "OE1ABC", self.pub, now=NOW)

    def test_expired_refused(self):
        k, leaf, inter, _ = make_lotw(end=NOW - dt.timedelta(days=1))
        with self.assertRaisesRegex(lotw.LotwError, "not valid now"):
            lotw.sign_binding(p12_of(k, leaf, [inter]), "geheim", "OE3GAS", self.pub, now=NOW)

    def test_tampered_or_foreign(self):
        p = self.proof()
        bad = dict(p, pub=auth.b64e(b"\x08" * 32))         # another key slipped in
        with self.assertRaisesRegex(lotw.LotwError, "signature"):
            lotw.verify(bad, roots=[self.root], now=NOW)
        _, _, _, other_root = make_lotw()
        with self.assertRaisesRegex(lotw.LotwError, "trusted ARRL"):
            lotw.verify(p, roots=[other_root], now=NOW)
        with self.assertRaisesRegex(lotw.LotwError, "not valid now"):
            lotw.verify(p, roots=[self.root], now=NOW + dt.timedelta(days=1000))

    def test_not_a_p12(self):
        with self.assertRaisesRegex(lotw.LotwError, "cannot open"):
            lotw.sign_binding(b"\x30\x03\x02\x01\x00", "", "OE3GAS", self.pub)


@unittest.skipUnless(HAVE, "needs cryptography")
class Client(unittest.TestCase):
    def setUp(self):
        from tbclient.core import ClientCore
        from tests.test_tbclient import client_cfg
        self._tmp = tempfile.TemporaryDirectory()
        self.core = ClientCore(client_cfg(self._tmp.name))
        call = auth.base(self.core.cfg.mycall)
        k = dt.datetime.now(dt.timezone.utc)
        self.key, self.leaf, self.inter, self.root = make_lotw(
            call, start=k - dt.timedelta(days=10), end=k + dt.timedelta(days=500))
        self.p12 = p12_of(self.key, self.leaf, [self.inter])

    def tearDown(self):
        self._tmp.cleanup()

    def test_sign_keep_forget(self):
        c = self.core
        self.assertEqual(c.lotw_status()["state"], "none")
        st = c.lotw_sign(self.p12, "geheim")
        self.assertEqual(st["state"], "ok")
        self.assertEqual(c.snapshot()["lotw"]["state"], "ok")
        kept = (c.cfg.data_dir / "lotw.json").read_text()
        self.assertNotIn("geheim", kept)
        self.assertNotIn(base64.b64encode(self.p12).decode()[:40], kept)
        c.lotw_forget()
        self.assertEqual(c.lotw_status()["state"], "none")

    def test_tells_the_tinybox_once(self):
        c = self.core
        sent = []
        c._send = sent.append
        c.lotw_sign(self.p12, "geheim")
        c._lotw_ask()
        c._lotw_ask()                                    # once per connection
        self.assertEqual(sent, ["//LOTW?"])
        c._lotw_answer("-")                              # the box does not know it
        lines = [x for x in sent if x.startswith("//LOTWP ")]
        self.assertTrue(lines and lines[-1].startswith(f"//LOTWP {len(lines)}/{len(lines)} "))
        self.assertTrue(all(len(x) <= 220 for x in lines))
        c._lotw_answer("ok until=2028-01-01")
        self.assertEqual(c.lotw_status()["box"]["state"], "ok")
        c._lotw_answer("err the chain does not end at a trusted ARRL certificate")
        self.assertIn("trusted ARRL", c.lotw_status()["box"]["error"])

    def test_web_only_from_this_pc(self):
        from tbclient.web import PEER, WebServer
        srv = WebServer(self.core)
        body = json.dumps({"data": base64.b64encode(self.p12).decode(), "password": "geheim"}).encode()

        def post(peer):
            h = {"content-type": "application/json", "x-tbclient": "1", PEER: peer}
            return asyncio.run(srv._route("POST", "/api/lotw", {}, h, body))
        st, payload, _ = post("192.168.1.20")[:3]
        self.assertEqual(st, 403)
        self.assertIn("this PC", payload["error"])
        st, payload, _ = post("127.0.0.1")[:3]
        self.assertEqual((st, payload["lotw"]["state"]), (200, "ok"))


if __name__ == "__main__":
    unittest.main()
