#!/usr/bin/env python3
"""
Umer OS Security Subsystem
Quantum-resistant encryption placeholder (AES-256) and AI firewall simulation.
"""

import hashlib
import os
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

class QuantumSafeCrypto:
    """Placeholder for quantum-resistant encryption (NIST standards)."""
    def __init__(self):
        # In a full implementation, use CRYSTALS-Kyber / Dilithium.
        # Here we use AES-256 with a random key for demonstration.
        self.key = os.urandom(32)

    def encrypt(self, plaintext: str) -> str:
        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(self.key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        # Pad plaintext to multiple of 16
        padded = plaintext.encode() + b"\x00" * (16 - len(plaintext) % 16)
        ciphertext = encryptor.update(padded) + encryptor.finalize()
        return base64.b64encode(iv + ciphertext).decode()

    def decrypt(self, encoded: str) -> str:
        raw = base64.b64decode(encoded)
        iv, ct = raw[:16], raw[16:]
        cipher = Cipher(algorithms.AES(self.key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        padded = decryptor.update(ct) + decryptor.finalize()
        return padded.rstrip(b"\x00").decode()

class AIFirewall:
    """Simulates an AI-driven firewall that learns and blocks threats."""
    def __init__(self):
        self.blocked_ips = set()
        self.threat_log = []

    def analyze_packet(self, src_ip: str, payload: str):
        """Simple rule: block if payload contains 'malware' (simulate AI detection)."""
        if "malware" in payload.lower():
            self.blocked_ips.add(src_ip)
            self.threat_log.append(f"Blocked {src_ip} - malware pattern detected")
            print(f"[FIREWALL] Blocked malicious traffic from {src_ip}")
        else:
            print(f"[FIREWALL] Allowed normal traffic from {src_ip}")

def demo():
    crypto = QuantumSafeCrypto()
    msg = "Umer OS secret data"
    encrypted = crypto.encrypt(msg)
    decrypted = crypto.decrypt(encrypted)
    print(f"Original: {msg}")
    print(f"Encrypted (base64): {encrypted}")
    print(f"Decrypted: {decrypted}")

    firewall = AIFirewall()
    firewall.analyze_packet("192.168.1.10", "Hello server")
    firewall.analyze_packet("10.0.0.5", "This contains malware payload")
    print("Blocked IPs:", firewall.blocked_ips)

if __name__ == "__main__":
    print("Security Subsystem Demo")
    demo()