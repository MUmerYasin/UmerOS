"""
Umer OS Security Module
- Quantum-resistant encryption (LWE-based demo)
- AI-driven firewall (simple packet filter)
- Secure boot verification stub
"""

import hashlib
import os
from quantum_sim import generate_lwe_keypair

class QuantumSafeCrypto:
    def __init__(self):
        self.private_key, self.public_key = generate_lwe_keypair()

    def encrypt(self, plaintext: bytes) -> bytes:
        # Simulate LWE encryption: xor with hash of public key (just for demo)
        key_hash = hashlib.sha256(self.public_key).digest()
        ciphertext = bytes(a ^ b for a, b in zip(plaintext, key_hash * (len(plaintext) // len(key_hash) + 1)))
        return ciphertext

    def decrypt(self, ciphertext: bytes) -> bytes:
        # Decryption is symmetric in this mock; real Kyber would be different.
        return self.encrypt(ciphertext)  # XOR is its own inverse

class AIFirewall:
    def __init__(self):
        self.rules = []  # (ip, port, action)
        self.blocked_ips = set()

    def analyze_packet(self, src_ip, dst_port):
        """AI-based heuristic: if port 22 and not in rules, block."""
        if dst_port == 22 and src_ip not in self.blocked_ips:
            # Simulate AI decision
            print(f"[Firewall] Blocking suspicious SSH from {src_ip}")
            self.blocked_ips.add(src_ip)
            return "DROP"
        return "ALLOW"

    def add_rule(self, rule):
        self.rules.append(rule)

class SecureBoot:
    @staticmethod
    def verify_kernel_hash(expected_hash):
        """Check kernel integrity."""
        try:
            with open("umer_kernel.py", "rb") as f:
                kernel_data = f.read()
            actual_hash = hashlib.sha256(kernel_data).hexdigest()
            return actual_hash == expected_hash
        except Exception:
            return False

if __name__ == "__main__":
    crypto = QuantumSafeCrypto()
    msg = b"Umer OS secret"
    enc = crypto.encrypt(msg)
    dec = crypto.decrypt(enc)
    print(f"Original: {msg}")
    print(f"Encrypted: {enc.hex()}")
    print(f"Decrypted: {dec}")
    fw = AIFirewall()
    print(fw.analyze_packet("192.168.1.100", 22))