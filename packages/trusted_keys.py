"""
Umer OS — Package signing trust store (chain-of-trust anchor)  [H13]
====================================================================

This module is the *authoritative* source of which Ed25519 public keys are
trusted to sign ``.umerpkg`` archives.

Why this exists
---------------
`umer_pkg.py` used to claim ".umerpkg archives are *Signed*", but the code only
computed a SHA3-256 *integrity* hash — no signature, no trusted key. That is
overstated cryptography (see H13, and the related H132/H138/H154 family): anyone
who can write the archive can overwrite the hash and fully impersonate a
package.  H13 requires a real signature **and** a pinned chain-of-trust, both
fail-closed.

Trust model
-----------
* The trust store is a fixed map ``key_id -> Ed25519 public key (raw 32 bytes)``.
* A package is accepted by ``umer_pkg`` ONLY when its signature verifies against
  a key present in the trust store (refuse if the key id is unknown / untrusted).
* The canonical production anchor is ``umer-release`` — its public key is pinned
  below.  The matching *private* release key is held OFFLINE (never committed);
  this module intentionally contains only public material.
* Operators / CI may pin additional signing keys at runtime via
  :func:`pin_trusted_key` (e.g. a per-developer staging key).  Tests pin a
  throwaway ``umer-test-dev`` key the same way.

Author:  Umer OS Project
License: GPL-3.0
"""

from __future__ import annotations

from typing import Dict, Union

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

# [FIX H13] Canonical UmerOS release public key (Ed25519, raw 32 bytes).
# The corresponding private key is generated OFFLINE and must never be committed
# to the repository.  This is the root of the package chain-of-trust.
UMER_RELEASE_PUBLIC_KEY: bytes = (
    b"\xca#\xb5P\x03\xa1\x11\xd9q\x893\xb2\xb5\xb0]\x15\xb4\x94\x88\xcb&\x80"
    b"Q8[\x9bp\xa8\x97\x9dY@"
)


def _load_public(raw: Union[bytes, bytearray, Ed25519PublicKey]) -> Ed25519PublicKey:
    """Coerce raw bytes (or an existing object) into an ``Ed25519PublicKey``."""
    if isinstance(raw, Ed25519PublicKey):
        return raw
    return Ed25519PublicKey.from_public_bytes(bytes(raw))


def _load_private(raw: Union[bytes, bytearray, Ed25519PrivateKey]) -> Ed25519PrivateKey:
    """Coerce raw bytes (or an existing object) into an ``Ed25519PrivateKey``."""
    if isinstance(raw, Ed25519PrivateKey):
        return raw
    return Ed25519PrivateKey.from_private_bytes(bytes(raw))


# [FIX H13] The live, mutable trust store.  Starts with only the release anchor.
# ``UmerPackageManager`` snapshots this at construction time; mutating it (via
# :func:`pin_trusted_key`) affects managers built afterwards.
TRUSTED_PUBLIC_KEYS: Dict[str, bytes] = {
    "umer-release": UMER_RELEASE_PUBLIC_KEY,
}


def pin_trusted_key(key_id: str, public_key: Union[bytes, bytearray, Ed25519PublicKey]) -> None:
    """Pin an additional trusted signing key into the global trust store.

    Args:
        key_id:     Stable identifier (e.g. ``"umer-staging"``, ``"umer-test-dev"``).
        public_key: ``Ed25519PublicKey`` or raw 32-byte public key material.
    """
    TRUSTED_PUBLIC_KEYS[key_id] = _load_public(public_key).public_bytes_raw()


def unpin_trusted_key(key_id: str) -> None:
    """Remove a previously pinned key (never removes the canonical release anchor)."""
    if key_id == "umer-release":
        raise ValueError("Refusing to unpin the canonical 'umer-release' anchor.")
    TRUSTED_PUBLIC_KEYS.pop(key_id, None)


def get_trusted_keys() -> Dict[str, bytes]:
    """Return a shallow copy of the current trust store (key_id -> raw pubkey)."""
    return dict(TRUSTED_PUBLIC_KEYS)


def is_trusted(key_id: str) -> bool:
    """True if ``key_id`` is currently present in the trust store."""
    return key_id in TRUSTED_PUBLIC_KEYS
