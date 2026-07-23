#!/usr/bin/env python3
"""VPN tunnel abstraction for UmerOS.

TODAY:
    Provides a safe simulation interface for encrypted tunnel flows and can use
    a supplied crypto engine object.

EXPERIMENTAL:
    A real WireGuard wrapper lives in ``network_stack.VPNClient``.
"""

from __future__ import annotations

import logging
import secrets
from typing import Any, Optional

log = logging.getLogger("UmerOS.Network.VPN")


class VPNTunnel:
    """Simulated encrypted network tunnel.

    The fallback mode does not provide real encryption. It is intentionally
    labeled as simulation so UmerOS never claims cryptographic protection that
    is not actually present.
    """

    def __init__(self, crypto_engine: Optional[Any] = None) -> None:
        """Initialize the tunnel.

        Args:
            crypto_engine: Optional object with ``random_bytes``, ``encrypt``,
                and ``decrypt`` methods.
        """
        self.crypto = crypto_engine
        self.connected = False
        self.peer_address: str | None = None
        self.session_key: bytes | None = None

    def connect(self, peer: str, port: int = 51820) -> bool:
        """Establish a simulated tunnel to a peer."""
        if not peer.strip():
            raise ValueError("peer must not be empty")
        self.peer_address = f"{peer.strip()}:{port}"
        self.session_key = self._random_bytes(32)
        self.connected = True
        log.info("VPN tunnel connected to %s", self.peer_address)
        return True

    def send(self, data: bytes) -> bytes:
        """Encrypt or frame data for transport through the tunnel."""
        self._require_connected()
        if self.crypto and hasattr(self.crypto, "encrypt"):
            encrypted = self.crypto.encrypt(data)
            if isinstance(encrypted, tuple):
                _nonce, ciphertext = encrypted
                return ciphertext
            return encrypted
        return self._xor_frame(data)

    def receive(self, ciphertext: bytes, nonce: bytes | None = None) -> bytes:
        """Decrypt or unframe data received from the tunnel."""
        self._require_connected()
        if self.crypto and hasattr(self.crypto, "decrypt"):
            if nonce is not None:
                return self.crypto.decrypt(nonce, ciphertext)
            return self.crypto.decrypt(ciphertext)
        return self._xor_frame(ciphertext)

    def disconnect(self) -> None:
        """Close the simulated tunnel and erase session material."""
        log.info("VPN tunnel disconnected from %s", self.peer_address)
        self.connected = False
        self.peer_address = None
        self.session_key = None

    def status(self) -> dict:
        """Return tunnel status."""
        return {
            "connected": self.connected,
            "peer": self.peer_address,
            "mode": "crypto-engine" if self.crypto else "simulation",
        }

    def _random_bytes(self, length: int) -> bytes:
        """Get random bytes from the crypto engine or the standard library."""
        if self.crypto and hasattr(self.crypto, "random_bytes"):
            return self.crypto.random_bytes(length)
        return secrets.token_bytes(length)

    def _xor_frame(self, data: bytes) -> bytes:
        """Simulation-only reversible frame transform."""
        if not self.session_key:
            raise ConnectionError("VPN tunnel has no session key")
        key = self.session_key
        return bytes(byte ^ key[index % len(key)] for index, byte in enumerate(data))

    def _require_connected(self) -> None:
        """Raise when the tunnel is not connected."""
        if not self.connected:
            raise ConnectionError("VPN tunnel not connected")
