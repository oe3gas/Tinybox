"""GeoSphere scripts: certificate check is on (decision 20.10.2026, no network)."""

from __future__ import annotations

import ssl
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import geosphere_station as station                              # noqa: E402
import geosphere_warnungen as warnungen                          # noqa: E402


class TlsTests(unittest.TestCase):
    def test_check_is_on(self):
        for mod in (station, warnungen):
            with self.subTest(mod=mod.__name__):
                self.assertTrue(mod.SSL_PRUEFEN)

    def test_context_verifies_without_extra_packages(self):
        for mod in (station, warnungen):
            with self.subTest(mod=mod.__name__), \
                    mock.patch.dict(sys.modules, {"truststore": None, "certifi": None}):
                ctx = mod.ssl_kontext()
                self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
                self.assertTrue(ctx.check_hostname)

    def test_certificate_error_is_recognized(self):
        err = urllib.error.URLError(ssl.SSLCertVerificationError(1, "certificate verify failed"))
        for mod in (station, warnungen):
            with self.subTest(mod=mod.__name__):
                self.assertTrue(mod.tls_fehler(err))
                self.assertFalse(mod.tls_fehler(urllib.error.URLError("timed out")))


if __name__ == "__main__":
    unittest.main()
