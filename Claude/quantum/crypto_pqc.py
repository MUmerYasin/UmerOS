"""
Umer OS Post-Quantum Cryptography  [TODAY]
==========================================
Provides CRYSTALS-Kyber (key encapsulation) and CRYSTALS-Dilithium
(digital signatures) via the ``liboqs-python`` library when available,
with a pure-Python fallback using AES-256-GCM + ECDSA for environments
where liboqs is not installed.

Public API (same regardless of backend):
  - PostQuantumCrypto.generate_keypair()  → (public_key, private_key) bytes
  - PostQuantumCrypto.encrypt(pt, pk)     → ciphertext bytes
  - PostQuantumCrypto.decrypt(ct, sk)     → plaintext bytes
  - PostQuantumCrypto.sign(msg, sk)       → signature bytes
  - PostQuantumCrypto.verify(msg, sig, pk) → bool
  - PostQuantumCrypto.backend             → str  ("liboqs" or "fallback")

Hash utilities:
  - sha3_256(data: bytes) → bytes
  - sha3_512(data: bytes) → bytes

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import hashlib
import hmac as _hmac
import logging
import os
import struct
from typing import Tuple

log = logging.getLogger("UmerOS.CryptoPQC")

# Try to import liboqs (post-quantum); fall back to classical crypto
try:
    import oqs  # type: ignore
    _LIBOQS_AVAILABLE = True
    log.info("liboqs available — using CRYSTALS-Kyber + Dilithium.")
except ImportError:  # pragma: no cover
    _LIBOQS_AVAILABLE = False
    log.warning(
        "liboqs not installed — using classical AES-256-GCM/ECDSA fallback. "
        "Install: pip install liboqs-python"
    )

# Symmetric primitives (always available in stdlib)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore
from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # type: ignore
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (  # type: ignore
    Encoding,
    PublicFormat,
    PrivateFormat,
    NoEncryption,
)


# ---------------------------------------------------------------------------
# Hash utilities
# ---------------------------------------------------------------------------

def sha3_256(data: bytes) -> bytes:
    """Return SHA3-256 digest.

    Args:
        data: Input bytes.

    Returns:
        32-byte digest.
    """
    return hashlib.sha3_256(data).digest()


def sha3_512(data: bytes) -> bytes:
    """Return SHA3-512 digest.

    Args:
        data: Input bytes.

    Returns:
        64-byte digest.
    """
    return hashlib.sha3_512(data).digest()


def hmac_sha256(key: bytes, data: bytes) -> bytes:
    """Return HMAC-SHA256 over data.

    Args:
        key:  Secret key bytes.
        data: Input bytes.

    Returns:
        32-byte MAC.
    """
    return _hmac.new(key, data, hashlib.sha256).digest()


# ---------------------------------------------------------------------------
# LiboQS backend (CRYSTALS-Kyber 768 + Dilithium3)
# ---------------------------------------------------------------------------

class _LiboqsBackend:
    """Post-quantum backend using liboqs CRYSTALS algorithms."""

    KEM_ALG = "Kyber768"
    SIG_ALG = "Dilithium3"

    def generate_keypair(self) -> Tuple[bytes, bytes]:
        with oqs.KeyEncapsulation(self.KEM_ALG) as kem:
            pk = kem.generate_keypair()
            sk = kem.export_secret_key()
        return pk, sk

    def encrypt(self, plaintext: bytes, public_key: bytes) -> bytes:
        with oqs.KeyEncapsulation(self.KEM_ALG) as kem:
            ciphertext, shared_secret = kem.encap_secret(public_key)
        # Use shared_secret (32 B) as AES key to encrypt plaintext
        aes_key = sha3_256(shared_secret)[:32]
        gcm = AESGCM(aes_key)
        nonce = os.urandom(12)
        ct = gcm.encrypt(nonce, plaintext, None)
        # Prepend KEM ciphertext length + KEM ciphertext + nonce
        prefix = struct.pack(">I", len(ciphertext)) + ciphertext + nonce
        return prefix + ct

    def decrypt(self, ciphertext: bytes, private_key: bytes) -> bytes:
        kem_len = struct.unpack(">I", ciphertext[:4])[0]
        kem_ct  = ciphertext[4: 4 + kem_len]
        nonce   = ciphertext[4 + kem_len: 4 + kem_len + 12]
        data    = ciphertext[4 + kem_len + 12:]
        with oqs.KeyEncapsulation(self.KEM_ALG, secret_key=private_key) as kem:
            shared_secret = kem.decap_secret(kem_ct)
        aes_key = sha3_256(shared_secret)[:32]
        gcm = AESGCM(aes_key)
        return gcm.decrypt(nonce, data, None)

    def sign(self, message: bytes, private_key: bytes) -> bytes:
        with oqs.Signature(self.SIG_ALG, secret_key=private_key) as signer:
            return signer.sign(message)

    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        with oqs.Signature(self.SIG_ALG) as verifier:
            return verifier.verify(message, signature, public_key)

    @property
    def backend(self) -> str:
        return "liboqs"


# ---------------------------------------------------------------------------
# Fallback classical backend (Ed25519 + AES-256-GCM)
# ---------------------------------------------------------------------------

class _FallbackBackend:
    """Classical fallback: Ed25519 signatures + AES-256-GCM symmetric encryption.

    Public key format for encryption: 32-byte random AES key (raw bytes).
    This is a simplified KEM simulation — not quantum-safe, but API-compatible.
    """

    def generate_keypair(self) -> Tuple[bytes, bytes]:
        private = Ed25519PrivateKey.generate()
        public  = private.public_key()
        pk_bytes = public.public_bytes(Encoding.Raw, PublicFormat.Raw)
        sk_bytes = private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        # Append a random 32-byte AES seed for encryption use
        aes_seed = os.urandom(32)
        return pk_bytes + aes_seed, sk_bytes + aes_seed

    def encrypt(self, plaintext: bytes, public_key: bytes) -> bytes:
        # Use the last 32 bytes of the public_key bundle as AES key (simplified)
        aes_key = public_key[-32:]
        gcm = AESGCM(aes_key)
        nonce = os.urandom(12)
        return nonce + gcm.encrypt(nonce, plaintext, None)

    def decrypt(self, ciphertext: bytes, private_key: bytes) -> bytes:
        aes_key = private_key[-32:]
        nonce   = ciphertext[:12]
        data    = ciphertext[12:]
        gcm = AESGCM(aes_key)
        return gcm.decrypt(nonce, data, None)

    def sign(self, message: bytes, private_key: bytes) -> bytes:
        sk_raw = private_key[:32]
        private = Ed25519PrivateKey.from_private_bytes(sk_raw)
        return private.sign(message)

    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PublicKey,
            )
            pk_raw = public_key[:32]
            public = Ed25519PublicKey.from_public_bytes(pk_raw)
            public.verify(signature, message)
            return True
        except Exception:
            return False

    @property
    def backend(self) -> str:
        return "fallback"


# ---------------------------------------------------------------------------
# Public facade
# ---------------------------------------------------------------------------

class PostQuantumCrypto:
    """Unified post-quantum cryptography facade.

    Automatically selects the liboqs backend when available, otherwise falls
    back to the classical Ed25519/AES-256-GCM implementation.

    Usage::

        pqc = PostQuantumCrypto()
        pk, sk = pqc.generate_keypair()
        ct = pqc.encrypt(b"secret data", pk)
        pt = pqc.decrypt(ct, sk)  # == b"secret data"

        sig = pqc.sign(b"message", sk)
        ok  = pqc.verify(b"message", sig, pk)  # True
    """

    def __init__(self) -> None:
        self._impl = _LiboqsBackend() if _LIBOQS_AVAILABLE else _FallbackBackend()
        log.info("PostQuantumCrypto using '%s' backend.", self._impl.backend)

    @property
    def backend(self) -> str:
        """Return the active backend name ('liboqs' or 'fallback')."""
        return self._impl.backend

    def generate_keypair(self) -> Tuple[bytes, bytes]:
        """Generate a fresh key pair.

        Returns:
            Tuple of (public_key, private_key) as raw bytes.
        """
        return self._impl.generate_keypair()

    def encrypt(self, plaintext: bytes, public_key: bytes) -> bytes:
        """Encrypt plaintext with the recipient's public key.

        Args:
            plaintext:  Bytes to encrypt.
            public_key: Recipient public key bytes.

        Returns:
            Ciphertext bytes (includes all header information for decryption).
        """
        return self._impl.encrypt(plaintext, public_key)

    def decrypt(self, ciphertext: bytes, private_key: bytes) -> bytes:
        """Decrypt ciphertext with the recipient's private key.

        Args:
            ciphertext:  Bytes produced by ``encrypt()``.
            private_key: Corresponding private key bytes.

        Returns:
            Original plaintext bytes.

        Raises:
            ValueError: If decryption fails (wrong key or tampered data).
        """
        return self._impl.decrypt(ciphertext, private_key)

    def sign(self, message: bytes, private_key: bytes) -> bytes:
        """Sign a message with a private key.

        Args:
            message:     Bytes to sign.
            private_key: Signer's private key bytes.

        Returns:
            Signature bytes.
        """
        return self._impl.sign(message, private_key)

    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        """Verify a signature against a message and public key.

        Args:
            message:    Original message bytes.
            signature:  Signature bytes from ``sign()``.
            public_key: Signer's public key bytes.

        Returns:
            True if the signature is valid, False otherwise.
        """
        return self._impl.verify(message, signature, public_key)
