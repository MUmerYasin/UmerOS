#!/usr/bin/env python3
"""
Umer OS VPN Tunnel Stub

Provides an encrypted tunnel interface (WireGuard-style) using the
CryptoEngine from Stage 4. Currently a simulation; the API is designed
so a real kernel-level tunnel can be plugged in later.
"""

import os


class VPNTunnel:
    """Simulated encrypted network tunnel."""

    def __init__(self, crypto_engine):
        self.crypto = crypto_engine
        self.connected = False
        self.peer_address = None
        self.session_key = None

    def connect(self, peer: str, port: int = 51820):
        """Establish an encrypted tunnel to a peer."""
        self.peer_address = f"{peer}:{port}"
        self.session_key = self.crypto.random_bytes(32)
        self.connected = True
        print(f"[VPN] Tunnel established to {self.peer_address}")
        print(f"[VPN] Session key: {self.session_key[:8].hex()}…")

    def send(self, data: bytes) -> bytes:
        """Encrypt and 'send' data through the tunnel."""
        if not self.connected:
            raise ConnectionError("VPN tunnel not connected.")
        nonce, ciphertext = self.crypto.encrypt(data)
        print(f"[VPN] Sent {len(data)}B -> {len(ciphertext)}B encrypted to {self.peer_address}")
        return ciphertext

    def receive(self, nonce: bytes, ciphertext: bytes) -> bytes:
        """'Receive' and decrypt data from the tunnel."""
        if not self.connected:
            raise ConnectionError("VPN tunnel not connected.")
        plaintext = self.crypto.decrypt(nonce, ciphertext)
        print(f"[VPN] Received {len(ciphertext)}B -> {len(plaintext)}B decrypted")
        return plaintext

    def disconnect(self):
        print(f"[VPN] Tunnel to {self.peer_address} closed.")
        self.connected = False
        self.peer_address = None
        self.session_key = None
