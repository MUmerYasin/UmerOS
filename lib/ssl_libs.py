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
SSL/TLS Certificate and Key Management for UmerOS /lib/ssl
==========================================================
Manages the /lib/ssl and /usr/lib/ssl certificate stores, CA bundles,
private keys, and certificate chains.

/lib/ssl contains SSL/TLS support files
(CA certificates, root certificates, intermediate bundles) used by
the dynamic linker and system-wide crypto libraries.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_CA_PATHS = [
    "/lib/ssl",
    "/usr/lib/ssl",
    "/etc/ssl",
    "/etc/pki/tls/certs",
]

_DEFAULT_CA_BUNDLE = "ca-certificates.crt"

_CERT_EXTENSIONS = {".pem", ".crt", ".cer", ".der", ".p12", ".pfx", ".key"}
_KEY_EXTENSIONS = {".key", ".pem"}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

class CertFormat(Enum):
    PEM = auto()
    DER = auto()
    PKCS12 = auto()
    UNKNOWN = auto()


class CertPurpose(Enum):
    CA = "ca"
    SERVER = "server"
    CLIENT = "client"
    CODE_SIGNING = "code_signing"
    EMAIL = "email"
    UNKNOWN = "unknown"


@dataclass
class CertInfo:
    """Metadata about a certificate file."""
    path: str
    filename: str
    format: CertFormat
    purpose: CertPurpose
    subject: str
    issuer: str
    serial: str
    not_before: str
    not_after: str
    fingerprint_sha256: str
    is_ca: bool
    is_trusted: bool
    key_size: int
    signature_algorithm: str
    san: list[str] = field(default_factory=list)

    @property
    def is_expired(self) -> bool:
        """Check expiry — simplified: returns False if parsing fails."""
        if not self.not_after:
            return False
        # Simplified check — in production use datetime parsing
        return False

    @property
    def days_until_expiry(self) -> int:
        """Estimated days until expiry — simplified."""
        return 365  # Placeholder


@dataclass
class KeyInfo:
    """Metadata about a private key file."""
    path: str
    filename: str
    format: CertFormat
    key_size: int
    encrypted: bool
    algorithm: str


@dataclass
class CaBundleInfo:
    """Metadata about a CA certificate bundle."""
    path: str
    format: CertFormat
    cert_count: int
    fingerprints: list[str]
    last_modified: float


@dataclass
class SslStoreStats:
    """Summary statistics for the SSL store."""
    total_certs: int
    total_keys: int
    total_bundles: int
    trusted_certs: int
    expired_certs: int
    ca_certs: int
    store_paths: list[str]


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class SslManager:
    """
    Manages /lib/ssl and /usr/lib/ssl certificate stores.

    Provides operations for listing, validating, and managing SSL/TLS
    certificates, private keys, and CA bundles following FHS layout.

    Usage::

        ssl = SslManager()
        stats = ssl.get_store_stats()
        certs = ssl.list_certificates()
        trust = ssl.check_trust("example.crt")
    """

    def __init__(self, store_paths: Optional[list[str]] = None) -> None:
        self._store_paths = store_paths or _DEFAULT_CA_PATHS
        self._cert_cache: dict[str, CertInfo] = {}

    def get_store_stats(self) -> SslStoreStats:
        """Get summary statistics of all SSL stores."""
        certs = self.list_certificates()
        keys = self.list_keys()
        bundles = self.list_ca_bundles()
        return SslStoreStats(
            total_certs=len(certs),
            total_keys=len(keys),
            total_bundles=len(bundles),
            trusted_certs=sum(1 for c in certs if c.is_trusted),
            expired_certs=sum(1 for c in certs if c.is_expired),
            ca_certs=sum(1 for c in certs if c.is_ca),
            store_paths=[p for p in self._store_paths if os.path.isdir(p)],
        )

    def list_certificates(self) -> list[CertInfo]:
        """List all certificates across all store paths."""
        certs: list[CertInfo] = []
        seen: set[str] = set()

        for store_path in self._store_paths:
            if not os.path.isdir(store_path):
                continue
            for root, _dirs, files in os.walk(store_path):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    ext = os.path.splitext(fname)[1].lower()
                    if ext in _CERT_EXTENSIONS and fpath not in seen:
                        seen.add(fpath)
                        info = self._inspect_cert(fpath)
                        if info:
                            certs.append(info)
        return certs

    def list_keys(self) -> list[KeyInfo]:
        """List all private keys across all store paths."""
        keys: list[KeyInfo] = []
        seen: set[str] = set()

        for store_path in self._store_paths:
            if not os.path.isdir(store_path):
                continue
            for root, _dirs, files in os.walk(store_path):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    ext = os.path.splitext(fname)[1].lower()
                    if ext in _KEY_EXTENSIONS and fpath not in seen:
                        seen.add(fpath)
                        info = self._inspect_key(fpath)
                        if info:
                            keys.append(info)
        return keys

    def list_ca_bundles(self) -> list[CaBundleInfo]:
        """List CA certificate bundles."""
        bundles: list[CaBundleInfo] = []

        for store_path in self._store_paths:
            if not os.path.isdir(store_path):
                continue
            # Look for the main CA bundle file
            bundle_path = os.path.join(store_path, _DEFAULT_CA_BUNDLE)
            if os.path.isfile(bundle_path):
                bundles.append(self._inspect_bundle(bundle_path))

            # Also check for hashed symlinks (update-ca-certificates style)
            cert_dir = os.path.join(store_path, "certs")
            if os.path.isdir(cert_dir):
                for fname in os.listdir(cert_dir):
                    fpath = os.path.join(cert_dir, fname)
                    if os.path.isfile(fpath) and not os.path.islink(fpath):
                        bundles.append(self._inspect_bundle(fpath))
        return bundles

    def check_trust(self, cert_path: str) -> dict[str, object]:
        """
        Check if a certificate is trusted by any CA in the store.

        Simplified implementation — checks if the cert's issuer
        matches any CA cert's subject in the store.
        """
        cert = self._inspect_cert(cert_path)
        if cert is None:
            return {"trusted": False, "reason": "Could not parse certificate"}

        if cert.is_ca:
            return {"trusted": True, "reason": "Certificate is a CA root"}

        # Check if issuer matches any stored CA
        ca_certs = [c for c in self.list_certificates() if c.is_ca]
        for ca in ca_certs:
            if ca.subject and cert.issuer and ca.subject == cert.issuer:
                return {"trusted": True, "reason": f"Signed by CA: {ca.subject}"}

        return {"trusted": False, "reason": "No matching CA found in store"}

    def get_cert_chain(self, cert_path: str) -> list[str]:
        """Attempt to trace the certificate chain to a root CA."""
        chain: list[str] = [cert_path]
        cert = self._inspect_cert(cert_path)
        if cert is None:
            return chain

        current_issuer = cert.issuer
        visited: set[str] = {cert_path}

        for _ in range(10):  # Max chain depth
            if not current_issuer:
                break
            # Find issuer in store
            found = False
            for ca in self.list_certificates():
                if ca.is_ca and ca.subject == current_issuer and ca.path not in visited:
                    chain.append(ca.path)
                    visited.add(ca.path)
                    current_issuer = ca.issuer
                    found = True
                    if ca.subject == ca.issuer:  # Self-signed root
                        return chain
                    break
            if not found:
                break

        return chain

    def compute_fingerprint(self, cert_path: str, algo: str = "sha256") -> str:
        """Compute a certificate fingerprint."""
        try:
            with open(cert_path, "rb") as f:
                data = f.read()
            h = hashlib.new(algo)
            h.update(data)
            return h.hexdigest()
        except (OSError, ValueError):
            return ""

    def search_certs(self, query: str) -> list[CertInfo]:
        """Search certificates by subject, issuer, or filename."""
        query_lower = query.lower()
        return [
            c for c in self.list_certificates()
            if query_lower in c.subject.lower()
            or query_lower in c.issuer.lower()
            or query_lower in c.filename.lower()
        ]

    def _inspect_cert(self, path: str) -> Optional[CertInfo]:
        """Parse a certificate file and extract metadata."""
        if path in self._cert_cache:
            return self._cert_cache[path]

        filename = os.path.basename(path)
        ext = os.path.splitext(filename)[1].lower()

        fmt = CertFormat.PEM
        if ext == ".der":
            fmt = CertFormat.DER
        elif ext in (".p12", ".pfx"):
            fmt = CertFormat.PKCS12

        # Simplified metadata extraction — in production use OpenSSL/cryptography
        info = CertInfo(
            path=path,
            filename=filename,
            format=fmt,
            purpose=CertPurpose.UNKNOWN,
            subject=self._extract_field(path, "subject"),
            issuer=self._extract_field(path, "issuer"),
            serial=self._extract_field(path, "serial"),
            not_before="",
            not_after="",
            # [FIX H146] Use the canonical X.509 DER fingerprint (or a
            # whitespace-normalised PEM-block hash) so it compares directly with
            # the bundle fingerprints computed in _bundle_fingerprints.
            fingerprint_sha256=self._fingerprint_pem_cert(
                (Path(path).read_bytes() if Path(path).exists() else b"")
            ),
            is_ca=self._check_is_ca(path),
            is_trusted=False,
            key_size=2048,
            signature_algorithm="SHA256withRSA",
        )

        # Check if trusted
        trust_result = self._check_is_trusted(info)
        info.is_trusted = trust_result

        self._cert_cache[path] = info
        return info

    def _inspect_key(self, path: str) -> Optional[KeyInfo]:
        """Parse a private key file and extract metadata."""
        filename = os.path.basename(path)
        ext = os.path.splitext(filename)[1].lower()

        encrypted = False
        key_size = 0
        try:
            with open(path, "r") as f:
                first_lines = [f.readline() for _ in range(5)]
            content = "".join(first_lines)
            encrypted = "ENCRYPTED" in content.upper() or "Proc-Type: 4,ENCRYPTED" in content
            # Extract key size from header if present
            if "RSA" in content:
                for part in content.split():
                    if part.isdigit() and int(part) >= 1024:
                        key_size = int(part)
                        break
        except (OSError, UnicodeDecodeError):
            pass

        return KeyInfo(
            path=path,
            filename=filename,
            format=CertFormat.PEM if ext == ".pem" else CertFormat.PEM,
            key_size=key_size or 2048,
            encrypted=encrypted,
            algorithm="RSA",
        )

    def _inspect_bundle(self, path: str) -> CaBundleInfo:
        """Inspect a CA bundle file."""
        cert_count = 0
        fingerprints: list[str] = []
        try:
            with open(path, "r") as f:
                content = f.read()
            # Count PEM certificates
            cert_count = content.count("-----BEGIN CERTIFICATE-----")
        except (OSError, UnicodeDecodeError):
            pass

        return CaBundleInfo(
            path=path,
            format=CertFormat.PEM,
            cert_count=cert_count,
            fingerprints=fingerprints,
            last_modified=os.path.getmtime(path) if os.path.isfile(path) else 0,
        )

    def _extract_field(self, path: str, field: str) -> str:
        """Extract a field from a PEM certificate using simple parsing."""
        try:
            with open(path, "r") as f:
                content = f.read(4096)
            # Simple string search for common fields
            for line in content.split("\n"):
                line = line.strip()
                if field == "subject" and line.startswith("Subject:"):
                    return line.split(":", 1)[1].strip()
                if field == "issuer" and line.startswith("Issuer:"):
                    return line.split(":", 1)[1].strip()
                if field == "serial" and line.startswith("Serial Number:"):
                    return line.split(":", 1)[1].strip()
        except (OSError, UnicodeDecodeError):
            pass
        return ""

    def _check_is_ca(self, path: str) -> bool:
        """Check if a certificate is a CA by looking for CA extensions."""
        try:
            with open(path, "r") as f:
                content = f.read(8192)
            # Look for basicConstraints CA=TRUE
            return "CA:TRUE" in content or "basicConstraints" in content
        except (OSError, UnicodeDecodeError):
            return False

    def _check_is_trusted(self, cert: CertInfo) -> bool:
        """[FIX H146] Fail-closed CA-trust verification.

        A certificate is trusted only if its SHA-256 fingerprint actually
        appears among the certificates contained in a CA bundle in a configured
        store.  The previous implementation returned ``True`` whenever *any*
        ``ca-certificates.crt`` file existed anywhere — an attacker-presented
        certificate was trusted as long as a bundle was present on the system, a
        fail-open trust decision.  Now we compare real fingerprints and default
        to NOT trusted.
        """
        if not cert or not cert.fingerprint_sha256:
            return False
        target = cert.fingerprint_sha256
        for store_path in self._store_paths:
            bundle = os.path.join(store_path, _DEFAULT_CA_BUNDLE)
            if not os.path.isfile(bundle):
                continue
            for fp in self._bundle_fingerprints(bundle):
                if fp == target:  # fingerprints are not secret — direct compare OK
                    return True
        return False

    @staticmethod
    def _fingerprint_pem_cert(raw: bytes) -> str:
        """Canonical SHA-256 fingerprint of a single PEM certificate.

        Uses the X.509 DER fingerprint (cryptography) when available — the
        standard, byte-order-independent cert identity.  Falls back to a
        whitespace-normalised PEM-block hash so candidate certs and bundle
        entries are always compared on identical bytes (the previous code
        hashed the whole file for the candidate but only the BEGIN→END block
        for the bundle, so a single trailing newline made them diverge).
        """
        try:
            from cryptography import x509
            from cryptography.hazmat.primitives import hashes

            return x509.load_pem_x509_certificate(raw).fingerprint(
                hashes.SHA256()
            ).hex()
        except Exception:
            pass
        text = raw.decode("utf-8", errors="ignore")
        marker = "-----BEGIN CERTIFICATE-----"
        end = "-----END CERTIFICATE-----"
        i = text.find(marker)
        j = text.find(end, i) if i != -1 else -1
        if i != -1 and j != -1:
            block = text[i:j + len(end)].strip()
        else:
            block = text.strip()
        return hashlib.sha256(block.encode("utf-8")).hexdigest()

    def _bundle_fingerprints(self, bundle_path: str) -> list[str]:
        """Return SHA-256 fingerprints of each cert block in a CA bundle.

        Used by :meth:`_check_is_trusted` to compare a candidate cert against
        the real contents of the trust store (fail-closed).  Each entry is
        fingerprinted with :meth:`_fingerprint_pem_cert` so it is directly
        comparable to a candidate's ``fingerprint_sha256``.
        """
        try:
            with open(bundle_path, "rb") as fh:
                raw = fh.read()
        except OSError:
            return []
        text = raw.decode("utf-8", errors="ignore")
        fps: list[str] = []
        marker = "-----BEGIN CERTIFICATE-----"
        end = "-----END CERTIFICATE-----"
        start = 0
        while True:
            i = text.find(marker, start)
            if i == -1:
                break
            j = text.find(end, i)
            if j == -1:
                break
            block = text[i:j + len(end)].encode("utf-8")
            fps.append(self._fingerprint_pem_cert(block))
            start = j + 1
        return fps


# ---------------------------------------------------------------------------
#  Self-test
# ---------------------------------------------------------------------------

def _selftest():
    """Run a basic self-test for this module."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = SslManager(store_paths=[tmpdir])
        stats = mgr.get_store_stats()
        assert hasattr(stats, 'total_certs'), "stats should have total_certs"

    print("selftest OK")
    return True


if __name__ == "__main__":
    _selftest()
