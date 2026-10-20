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

"""H148 tests — ``lib/ssl_libs.py`` tier label + real X.509 parsing.

The standard flagged ``lib/ssl_libs.py`` as a "simplified" string-parsed
simulation that shipped as if production-ready: a loose ``CA:TRUE`` substring
heuristic for ``is_ca``, hardcoded ``key_size`` / ``signature_algorithm``
defaults, and no real parsing (💭 H148).

Drift-recon showed trust and expiry were already hardened (H146/H147), and
``is_ca`` already parses BasicConstraints.  The residual real gaps were:

* the module carried no tier label (it should be ``[EXPERIMENTAL]``), and
* ``subject``/``issuer``/``serial``/``key_size``/``signature_algorithm`` were
  still text-grep / hardcoded rather than parsed from the X.509 certificate.

These tests pin the resulting behaviour: real parsing via ``cryptography`` with
a documented heuristic fallback when it is unavailable.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SSL_SRC = ROOT / "lib" / "ssl_libs.py"

from lib.ssl_libs import CertFormat, CertPurpose, SslManager  # noqa: E402

try:
    from cryptography import x509 as _x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    _HAVE_CRYPTO = True
except Exception:  # pragma: no cover
    _HAVE_CRYPTO = False


def _name(cn: str):
    return _x509.Name([_x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def _build(key, cn="UmerOS Test", *, is_ca=False, eku=None, san=None) -> bytes:
    now = datetime.now(timezone.utc)
    b = (
        _x509.CertificateBuilder()
        .subject_name(_name(cn))
        .issuer_name(_name(cn))
        .public_key(key.public_key())
        .serial_number(_x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(_x509.BasicConstraints(ca=is_ca, path_length=None), critical=True)
    )
    if eku:
        b = b.add_extension(_x509.ExtendedKeyUsage(eku), critical=False)
    if san:
        b = b.add_extension(
            _x509.SubjectAlternativeName([_x509.DNSName(s) for s in san]), critical=False)
    return b.sign(key, hashes.SHA256()).public_bytes(serialization.Encoding.PEM)


def _write(d: str, name: str, data: bytes) -> str:
    p = os.path.join(d, name)
    with open(p, "wb") as fh:
        fh.write(data)
    return p


class TestTierLabel(unittest.TestCase):
    """The module must declare its maturity tier (H148)."""

    def test_module_docstring_carries_experimental_tier(self):
        src = SSL_SRC.read_text(encoding="utf-8")
        head = src[:1200]
        self.assertIn("[EXPERIMENTAL]", head)
        self.assertIn("Tier: [EXPERIMENTAL]", src)


@unittest.skipUnless(_HAVE_CRYPTO, "cryptography not available")
class TestRealX509Parsing(unittest.TestCase):
    """_inspect_cert must read real fields from the X.509 certificate (H148)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.mgr = SslManager(store_paths=[self.dir])

    def tearDown(self):
        self._tmp.cleanup()

    def test_rsa_ca_cert_fields(self):
        pem = _build(rsa.generate_private_key(public_exponent=65537, key_size=2048),
                     cn="UmerOS Root CA", is_ca=True)
        info = self.mgr._inspect_cert(_write(self.dir, "root.crt", pem))
        self.assertIsNotNone(info)
        self.assertEqual(info.key_size, 2048)
        self.assertIn("CN=UmerOS Root CA", info.subject)
        self.assertIn("CN=UmerOS Root CA", info.issuer)
        self.assertTrue(info.serial)
        self.assertTrue(all(c in "0123456789abcdef" for c in info.serial))
        self.assertTrue(info.is_ca)
        self.assertEqual(info.purpose, CertPurpose.CA)
        self.assertTrue(info.signature_algorithm)
        self.assertIn("rsa", info.signature_algorithm.lower())

    def test_server_cert_purpose_and_san(self):
        pem = _build(rsa.generate_private_key(public_exponent=65537, key_size=2048),
                     cn="example.test", is_ca=False,
                     eku=[ExtendedKeyUsageOID.SERVER_AUTH],
                     san=["example.test", "www.example.test"])
        info = self.mgr._inspect_cert(_write(self.dir, "server.crt", pem))
        self.assertFalse(info.is_ca)
        self.assertEqual(info.purpose, CertPurpose.SERVER)
        self.assertIn("example.test", info.san)
        self.assertIn("www.example.test", info.san)

    def test_ec_key_size_parsed(self):
        pem = _build(ec.generate_private_key(ec.SECP256R1()), cn="EC Test")
        info = self.mgr._inspect_cert(_write(self.dir, "ec.crt", pem))
        self.assertEqual(info.key_size, 256)

    def test_client_auth_purpose(self):
        pem = _build(rsa.generate_private_key(public_exponent=65537, key_size=2048),
                     cn="client", eku=[ExtendedKeyUsageOID.CLIENT_AUTH])
        info = self.mgr._inspect_cert(_write(self.dir, "client.crt", pem))
        self.assertEqual(info.purpose, CertPurpose.CLIENT)


class TestHeuristicFallback(unittest.TestCase):
    """Unparseable inputs must not crash — metadata is simply unknown."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.mgr = SslManager(store_paths=[self.dir])

    def tearDown(self):
        self._tmp.cleanup()

    def test_unparseable_cert_yields_empty_validity(self):
        path = _write(self.dir, "bogus.crt", b"not a certificate at all\n")
        info = self.mgr._inspect_cert(path)
        self.assertIsNotNone(info)
        self.assertEqual(info.not_after, "")
        self.assertFalse(info.is_expired)
        self.assertEqual(info.san, [])

    def test_load_x509_returns_none_for_bogus(self):
        path = _write(self.dir, "bogus.pem", b"-----BEGIN CERTIFICATE-----\nnope\n")
        self.assertIsNone(self.mgr._load_x509(path, CertFormat.PEM))


class TestSourceInvariants(unittest.TestCase):
    """Pin code facts (never cosmetic tags)."""

    def test_inspect_cert_uses_real_key_meta(self):
        src = SSL_SRC.read_text(encoding="utf-8")
        self.assertIn("self._key_meta(cert)", src)
        # The hardcoded defaults must no longer be passed to the CertInfo ctor.
        self.assertNotIn("key_size=2048,\n", src)

    def test_parsing_helpers_present(self):
        src = SSL_SRC.read_text(encoding="utf-8")
        for helper in ("_load_x509", "_name_str", "_key_meta", "_purpose_of", "_san_of"):
            self.assertIn(f"def {helper}", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
