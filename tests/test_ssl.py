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
pytest suite for lib/ssl_libs.py — CA trust verification (H146).

Locks the fail-closed behaviour of SslManager._check_is_trusted: a certificate
is trusted ONLY if its fingerprint actually appears in a CA bundle in a
configured store.  Previously any certificate was trusted as long as *some*
ca-certificates.crt file existed anywhere (fail-open).
"""

import os
import sys
import tempfile

from pathlib import Path

import pytest

_root_dir = str(Path(__file__).resolve().parent.parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from lib.ssl_libs import SslManager  # noqa: E402


def _self_signed_pem() -> bytes:
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    from datetime import datetime

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test CA")]))
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test CA")]))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime(2020, 1, 1))
        .not_valid_after(datetime(2030, 1, 1))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM)


def test_check_is_trusted_fail_closed_on_unknown_cert():
    ca_pem = _self_signed_pem()
    other_pem = _self_signed_pem()  # different key -> different fingerprint
    with tempfile.TemporaryDirectory() as d:
        bundle = os.path.join(d, "ca-certificates.crt")
        with open(bundle, "w", encoding="utf-8") as fh:
            fh.write(ca_pem.decode())

        mgr = SslManager(store_paths=[d])

        # A cert that IS in the bundle must be trusted.
        ca_cert = mgr._inspect_cert(bundle)
        assert ca_cert is not None
        assert mgr._check_is_trusted(ca_cert) is True

        # A cert that is NOT in the bundle must NOT be trusted, even though a
        # bundle file exists in the store (this is the old fail-open bug).
        other_path = os.path.join(d, "other.crt")
        with open(other_path, "w", encoding="utf-8") as fh:
            fh.write(other_pem.decode())
        other_cert = mgr._inspect_cert(other_path)
        assert mgr._check_is_trusted(other_cert) is False


def test_check_is_trusted_no_bundle_returns_false():
    with tempfile.TemporaryDirectory() as d:
        # Empty store, no CA bundle present.
        mgr = SslManager(store_paths=[d])
        # Build a CertInfo with an arbitrary fingerprint directly.
        from lib.ssl_libs import CertInfo
        from lib.ssl_libs import CertFormat, CertPurpose

        cert = CertInfo(
            path="x.crt", filename="x.crt", format=CertFormat.PEM,
            purpose=CertPurpose.UNKNOWN, subject="", issuer="", serial="",
            not_before="", not_after="", fingerprint_sha256="deadbeef",
            is_ca=False, is_trusted=False, key_size=0,
            signature_algorithm="",
        )
        assert mgr._check_is_trusted(cert) is False


# ---------------------------------------------------------------------------
# [FIX H147] Expiry enforcement + fail-closed check_trust
# ---------------------------------------------------------------------------

def _cert_pem(not_before: "datetime", not_after: "datetime", cn: str = "Test CA") -> bytes:
    """Build a real self-signed X.509 cert with the requested validity."""
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM)


def _write(path: str, pem: bytes) -> str:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(pem.decode())
    return path


def test_expired_cert_is_detected():
    """[FIX H147] is_expired must reflect real notAfter, not a constant False."""
    from datetime import datetime, timedelta, timezone
    from lib.ssl_libs import CertInfo, CertFormat, CertPurpose

    past = CertInfo(
        path="p.crt", filename="p.crt", format=CertFormat.PEM,
        purpose=CertPurpose.UNKNOWN, subject="", issuer="", serial="",
        not_before=(datetime.now(timezone.utc) - timedelta(days=800)).isoformat(),
        not_after=(datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
        fingerprint_sha256="ff", is_ca=False, is_trusted=False, key_size=0,
        signature_algorithm="",
    )
    future = CertInfo(
        path="f.crt", filename="f.crt", format=CertFormat.PEM,
        purpose=CertPurpose.UNKNOWN, subject="", issuer="", serial="",
        not_before=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        not_after=(datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        fingerprint_sha256="fe", is_ca=False, is_trusted=False, key_size=0,
        signature_algorithm="",
    )
    assert past.is_expired is True
    assert past.days_until_expiry < 0
    assert future.is_expired is False
    assert 0 <= future.days_until_expiry <= 31


def test_check_trust_rejects_expired_certificate(tmp_path):
    """[FIX H147] An expired certificate is never trusted — even in-store."""
    from datetime import datetime, timedelta

    expired = _cert_pem(datetime(2020, 1, 1), datetime(2021, 1, 1))
    path = _write(str(tmp_path / "expired.crt"), expired)

    store = tmp_path / "store"
    store.mkdir()
    _write(str(store / "ca-certificates.crt"), expired)   # even IN the bundle

    mgr = SslManager(store_paths=[str(store)])
    result = mgr.check_trust(path)
    assert result["trusted"] is False
    assert "expired" in str(result["reason"]).lower()


def test_check_trust_ca_shortcut_requires_bundle_membership(tmp_path):
    """[FIX H147] CA:TRUE alone no longer grants trust (old fail-open shortcut)."""
    from datetime import datetime, timedelta

    valid = _cert_pem(
        datetime.utcnow() - timedelta(days=1),
        datetime.utcnow() + timedelta(days=365),
    )
    path = _write(str(tmp_path / "ca.crt"), valid)
    # NOTE: no bundle anywhere in this store.
    mgr = SslManager(store_paths=[str(tmp_path / "empty")])
    result = mgr.check_trust(path)
    assert result["trusted"] is False
    assert "bundle" in str(result["reason"]).lower() or "validity" in str(result["reason"]).lower()


def test_check_trust_positive_path_in_store(tmp_path):
    """[FIX H147] Positive case still works: in-bundle, unexpired -> trusted."""
    from datetime import datetime, timedelta

    pem = _cert_pem(
        datetime.utcnow() - timedelta(days=1),
        datetime.utcnow() + timedelta(days=365),
    )
    store = tmp_path / "store"
    store.mkdir()
    bundle = _write(str(store / "ca-certificates.crt"), pem)
    mgr = SslManager(store_paths=[str(store)])
    result = mgr.check_trust(bundle)
    assert result["trusted"] is True
