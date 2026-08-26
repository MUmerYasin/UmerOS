# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Regression tests for lib/ssl_libs.py security RED finding
========================================================
  - H147: `CertInfo.is_expired` is no longer hard-coded to ``False`` and
          `days_until_expiry` is no longer hard-coded to ``365``. Both now reflect
          the REAL X.509 validity period parsed from the certificate, so expired
          certificates are actually detected (previously an expiry fail-open, same
          family as H111).

Run:  python -m unittest tests.test_ssl_security -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from lib.ssl_libs import CertInfo, CertFormat, CertPurpose, SslManager  # noqa: E402

# cryptography is optional in the source module; the integration tests need it.
try:
    from cryptography import x509 as _x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    _HAVE_CRYPTO = True
except Exception:  # pragma: no cover
    _HAVE_CRYPTO = False


def _make_cert_pem(not_before_dt: datetime, not_after_dt: datetime) -> bytes:
    """Generate a self-signed cert covering the given validity window (UTC)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert = (
        _x509.CertificateBuilder()
        .subject_name(_x509.Name([_x509.NameAttribute(NameOID.COMMON_NAME, "UmerOS Test")]))
        .issuer_name(_x509.Name([_x509.NameAttribute(NameOID.COMMON_NAME, "UmerOS Test")]))
        .public_key(key.public_key())
        .serial_number(_x509.random_serial_number())
        .not_valid_before(not_before_dt)
        .not_valid_after(not_after_dt)
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM)


def _cert_info(not_after: str) -> CertInfo:
    """Build a minimal CertInfo with a controlled not_after for unit tests."""
    return CertInfo(
        path="x.crt", filename="x.crt", format=CertFormat.PEM,
        purpose=CertPurpose.UNKNOWN, subject="", issuer="", serial="",
        not_before="", not_after=not_after, fingerprint_sha256="",
        is_ca=False, is_trusted=False, key_size=0, signature_algorithm="",
    )


class TestCertExpiryEnforced(unittest.TestCase):
    """H147 — expiry logic must be real, not a hard-coded pass."""

    def test_expired_cert_is_detected(self):
        past = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        info = _cert_info(past)
        self.assertTrue(info.is_expired)
        self.assertLess(info.days_until_expiry, 0)

    def test_valid_cert_is_not_expired(self):
        future = (datetime.now(timezone.utc) + timedelta(days=400)).isoformat()
        info = _cert_info(future)
        self.assertFalse(info.is_expired)
        self.assertGreater(info.days_until_expiry, 0)

    def test_empty_validity_is_unknown_not_expired(self):
        info = _cert_info("")
        self.assertFalse(info.is_expired)
        self.assertEqual(info.days_until_expiry, -1)

    def test_naive_datetime_string_parsed_as_utc(self):
        # A naive ISO string must be treated as UTC and still evaluate correctly.
        future = (datetime.now(timezone.utc) + timedelta(days=10)).replace(tzinfo=None).isoformat()
        info = _cert_info(future)
        self.assertFalse(info.is_expired)


@unittest.skipUnless(_HAVE_CRYPTO, "cryptography not available")
class TestCertInspectionParsesRealDates(unittest.TestCase):
    """H147 — _inspect_cert must populate real not_after from the X.509 cert."""

    def test_expired_cert_file_reported_expired(self):
        pem = _make_cert_pem(
            datetime.now(timezone.utc) - timedelta(days=365 * 2),
            datetime.now(timezone.utc) - timedelta(days=1),
        )
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "expired.crt")
            with open(p, "wb") as fh:
                fh.write(pem)
            mgr = SslManager(store_paths=[d])
            info = mgr._inspect_cert(p)
            self.assertIsNotNone(info)
            self.assertNotEqual(info.not_after, "", "not_after must be parsed, not empty")
            self.assertTrue(info.is_expired)
            self.assertLess(info.days_until_expiry, 0)

    def test_valid_cert_file_reported_valid(self):
        pem = _make_cert_pem(
            datetime.now(timezone.utc) - timedelta(days=1),
            datetime.now(timezone.utc) + timedelta(days=365 * 5),
        )
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "valid.crt")
            with open(p, "wb") as fh:
                fh.write(pem)
            mgr = SslManager(store_paths=[d])
            info = mgr._inspect_cert(p)
            self.assertIsNotNone(info)
            self.assertNotEqual(info.not_after, "")
            self.assertFalse(info.is_expired)
            self.assertGreater(info.days_until_expiry, 0)

    def test_expired_cert_counted_in_store_stats(self):
        expired_pem = _make_cert_pem(
            datetime.now(timezone.utc) - timedelta(days=365 * 2),
            datetime.now(timezone.utc) - timedelta(days=1),
        )
        valid_pem = _make_cert_pem(
            datetime.now(timezone.utc) - timedelta(days=1),
            datetime.now(timezone.utc) + timedelta(days=365 * 5),
        )
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "expired.crt"), "wb") as fh:
                fh.write(expired_pem)
            with open(os.path.join(d, "valid.crt"), "wb") as fh:
                fh.write(valid_pem)
            mgr = SslManager(store_paths=[d])
            stats = mgr.get_store_stats()
            self.assertEqual(stats.total_certs, 2)
            self.assertEqual(stats.expired_certs, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
