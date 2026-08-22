"""
pytest suite for quantum/crypto_pqc.py — honest post-quantum reporting (H152).

H152: when liboqs is unavailable the facade silently selected a classical
Ed25519/AES-256-GCM backend while still being advertised as "Post-Quantum".
Now the facade exposes `is_post_quantum` (False under the classical fallback)
and an `assert_post_quantum()` guard that security-critical callers can use to
refuse non-PQC operation.
"""

import sys

from pathlib import Path

import pytest

_root_dir = str(Path(__file__).resolve().parent.parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

pqc_mod = pytest.importorskip("quantum.crypto_pqc")
from quantum.crypto_pqc import PostQuantumCrypto  # noqa: E402


def test_pqc_reports_fallback_honestly():
    # In this environment liboqs is absent -> classical fallback, NOT post-quantum.
    p = PostQuantumCrypto()
    assert p.is_post_quantum is False
    assert p.backend == "fallback"
    with pytest.raises(RuntimeError):
        p.assert_post_quantum()


def test_pqc_sign_verify_roundtrip():
    p = PostQuantumCrypto()
    pk, sk = p.generate_keypair()
    sig = p.sign(b"message", sk)
    assert p.verify(b"message", sig, pk) is True
    assert p.verify(b"tampered", sig, pk) is False
