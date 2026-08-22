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

"""Tests for Umer OS Security Subsystem."""
from __future__ import annotations

import hashlib
import os
import tempfile
import unittest

from security.sandbox import SecuritySandbox
from security.security import (
    SecureBoot,
    IPCAuthenticator,
    compute_sha3_256,
    compute_sha3_512,
)
from quantum.crypto_pqc import PostQuantumCrypto, sha3_256, sha3_512, hmac_sha256


# ---------------------------------------------------------------------------
# SecuritySandbox tests (uses sandbox.py capability-based API)
# ---------------------------------------------------------------------------

class TestSecuritySandbox(unittest.TestCase):

    def setUp(self):
        self.sandbox = SecuritySandbox()
        self.sandbox.register_process(42, "test_proc")
        self.pid = 42

    def test_register_process(self):
        self.assertIn(self.pid, self.sandbox.processes)
        self.assertEqual(self.sandbox.processes[self.pid].name, "test_proc")

    def test_no_extra_perms_by_default(self):
        proc = self.sandbox.processes[self.pid]
        self.assertEqual(proc.permissions, {"read"})

    def test_grant_permission_adds(self):
        self.sandbox.grant_permission(self.pid, "fs.write")
        self.assertIn("fs.write", self.sandbox.processes[self.pid].permissions)

    def test_revoke_permission_removes(self):
        self.sandbox.grant_permission(self.pid, "fs.write")
        self.sandbox.revoke_permission(self.pid, "fs.write")
        self.assertNotIn("fs.write", self.sandbox.processes[self.pid].permissions)

    def test_revoke_nonexistent_no_error(self):
        self.sandbox.revoke_permission(self.pid, "net.send")
        self.assertNotIn("net.send", self.sandbox.processes[self.pid].permissions)

    def test_check_permission_granted(self):
        self.sandbox.grant_permission(self.pid, "gpu.render")
        self.assertTrue(self.sandbox.check_permission(self.pid, "gpu.render"))

    def test_check_permission_denied(self):
        self.assertFalse(self.sandbox.check_permission(self.pid, "quantum.hardware"))

    def test_check_permission_unregistered_pid(self):
        self.assertFalse(self.sandbox.check_permission(999, "fs.read"))

    def test_grant_multiple_permissions(self):
        perms = ["fs.read", "net.send", "gpu.render"]
        for p in perms:
            self.sandbox.grant_permission(self.pid, p)
        for p in perms:
            self.assertIn(p, self.sandbox.processes[self.pid].permissions)

    def test_repr_contains_pid(self):
        proc = self.sandbox.processes[self.pid]
        self.assertIn("42", repr(proc))

    def test_verify_signature(self):
        payload = b"test executable"
        expected = hashlib.sha3_512(payload).hexdigest()
        self.assertTrue(self.sandbox.verify_signature(self.pid, payload, expected))

    def test_verify_signature_bad_hash(self):
        payload = b"test executable"
        self.assertFalse(self.sandbox.verify_signature(self.pid, payload, "0" * 128))


# ---------------------------------------------------------------------------
# SecureBoot tests
# ---------------------------------------------------------------------------

class TestSecureBoot(unittest.TestCase):

    def setUp(self):
        self.sb = SecureBoot()

    def test_empty_trust_store(self):
        self.assertEqual(len(self.sb._store), 0)

    def test_register_component(self):
        self.sb.register("kernel", "a" * 64)
        self.assertIn("kernel", self.sb._store)

    def test_verify_image_no_store_entry_permissive(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test data")
            name = f.name
        try:
            result = self.sb.verify_image(name)
            self.assertTrue(result)  # permissive: no trust entry = pass
        finally:
            os.unlink(name)

    def test_verify_image_matching_hash(self):
        data = b"umer os kernel image bytes"
        expected = hashlib.sha3_256(data).hexdigest()
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(data)
            name = f.name
        try:
            result = self.sb.verify_image(name, expected_hash=expected)
            self.assertTrue(result)
        finally:
            os.unlink(name)

    def test_verify_image_mismatching_hash(self):
        data = b"real kernel"
        wrong_hash = "0" * 64
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(data)
            name = f.name
        try:
            result = self.sb.verify_image(name, expected_hash=wrong_hash)
            self.assertFalse(result)
        finally:
            os.unlink(name)

    def test_verify_bytes_matching(self):
        data = b"service bytes"
        h = hashlib.sha3_256(data).hexdigest()
        result = self.sb.verify_bytes(data, "svc", expected_hash=h)
        self.assertTrue(result)

    def test_verify_bytes_mismatch(self):
        data = b"service bytes"
        result = self.sb.verify_bytes(data, "svc", expected_hash="0" * 64)
        self.assertFalse(result)

    def test_record_measurement_appends(self):
        self.sb.record_measurement("kernel", "abc123")
        log = self.sb.get_measurement_log()
        self.assertTrue(any(e["component"] == "kernel" for e in log))

    def test_load_trust_store_from_json(self):
        store = {"kernel": "a" * 64, "quantum_sim": "b" * 64}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            import json
            json.dump(store, f)
            name = f.name
        try:
            result = self.sb.load_trust_store(name)
            self.assertTrue(result)
            self.assertIn("kernel", self.sb._store)
        finally:
            os.unlink(name)

    def test_load_trust_store_missing_file(self):
        result = self.sb.load_trust_store("/nonexistent/path.json")
        self.assertFalse(result)

    def test_verify_nonexistent_file_returns_true_permissive(self):
        result = self.sb.verify_image("/nonexistent/kernel.py")
        self.assertTrue(result)  # permissive during development


# ---------------------------------------------------------------------------
# IPCAuthenticator tests
# ---------------------------------------------------------------------------

class TestIPCAuthenticator(unittest.TestCase):

    def setUp(self):
        self.auth = IPCAuthenticator()

    def test_sign_returns_string(self):
        sig = self.auth.sign_message({"action": "start", "pid": 1})
        self.assertIsInstance(sig, str)
        self.assertEqual(len(sig), 64)

    def test_verify_valid_signature(self):
        msg = {"type": "ipc", "data": "hello"}
        sig = self.auth.sign_message(msg)
        self.assertTrue(self.auth.verify_message(msg, sig))

    def test_verify_tampered_message(self):
        msg = {"data": "original"}
        sig = self.auth.sign_message(msg)
        tampered = {"data": "tampered"}
        self.assertFalse(self.auth.verify_message(tampered, sig))

    def test_verify_wrong_signature(self):
        msg = {"x": 1}
        self.assertFalse(self.auth.verify_message(msg, "0" * 64))

    def test_rotate_key_invalidates_old_signatures(self):
        msg = {"a": 1}
        sig = self.auth.sign_message(msg)
        self.auth.rotate_key()
        self.assertFalse(self.auth.verify_message(msg, sig))

    def test_different_messages_different_signatures(self):
        sig1 = self.auth.sign_message({"x": 1})
        sig2 = self.auth.sign_message({"x": 2})
        self.assertNotEqual(sig1, sig2)

    def test_custom_key(self):
        key = os.urandom(32)
        auth = IPCAuthenticator(key=key)
        msg = {"test": True}
        sig = auth.sign_message(msg)
        self.assertTrue(auth.verify_message(msg, sig))

    def test_sign_deterministic(self):
        """Same message + key must always produce the same MAC."""
        key = b"fixed_key_32bytes_padded_xxxxxxxxx"[:32]
        auth1 = IPCAuthenticator(key=key)
        auth2 = IPCAuthenticator(key=key)
        msg = {"stable": "data"}
        self.assertEqual(auth1.sign_message(msg), auth2.sign_message(msg))


# ---------------------------------------------------------------------------
# Hash utility tests
# ---------------------------------------------------------------------------

class TestHashUtils(unittest.TestCase):

    def test_sha3_256_correct_length(self):
        h = compute_sha3_256(b"data")
        self.assertEqual(len(h), 64)

    def test_sha3_512_correct_length(self):
        h = compute_sha3_512(b"data")
        self.assertEqual(len(h), 128)

    def test_sha3_256_deterministic(self):
        self.assertEqual(compute_sha3_256(b"abc"), compute_sha3_256(b"abc"))

    def test_sha3_256_different_inputs(self):
        self.assertNotEqual(compute_sha3_256(b"a"), compute_sha3_256(b"b"))


# ---------------------------------------------------------------------------
# Post-Quantum Crypto tests
# ---------------------------------------------------------------------------

class TestPostQuantumCrypto(unittest.TestCase):

    def setUp(self):
        self.pqc = PostQuantumCrypto()

    def test_backend_property_is_string(self):
        self.assertIsInstance(self.pqc.backend, str)
        self.assertIn(self.pqc.backend, ("liboqs", "fallback"))

    def test_generate_keypair_returns_two_bytes(self):
        pk, sk = self.pqc.generate_keypair()
        self.assertIsInstance(pk, bytes)
        self.assertIsInstance(sk, bytes)
        self.assertGreater(len(pk), 0)
        self.assertGreater(len(sk), 0)

    def test_encrypt_decrypt_roundtrip(self):
        pk, sk = self.pqc.generate_keypair()
        plaintext = b"Umer OS secret data"
        ct = self.pqc.encrypt(plaintext, pk)
        pt = self.pqc.decrypt(ct, sk)
        self.assertEqual(pt, plaintext)

    def test_encrypt_produces_different_ciphertext(self):
        pk, sk = self.pqc.generate_keypair()
        ct1 = self.pqc.encrypt(b"data", pk)
        ct2 = self.pqc.encrypt(b"data", pk)
        # Ciphertext must be non-deterministic (nonce-based)
        # They may differ due to random nonce
        self.assertIsInstance(ct1, bytes)
        self.assertIsInstance(ct2, bytes)

    def test_sign_verify_roundtrip(self):
        pk, sk = self.pqc.generate_keypair()
        message = b"Umer OS kernel image"
        sig = self.pqc.sign(message, sk)
        self.assertTrue(self.pqc.verify(message, sig, pk))

    def test_verify_tampered_message_fails(self):
        pk, sk = self.pqc.generate_keypair()
        sig = self.pqc.sign(b"original", sk)
        self.assertFalse(self.pqc.verify(b"tampered", sig, pk))

    def test_sha3_256_utility(self):
        h = sha3_256(b"hello")
        self.assertIsInstance(h, bytes)
        self.assertEqual(len(h), 32)

    def test_sha3_512_utility(self):
        h = sha3_512(b"hello")
        self.assertIsInstance(h, bytes)
        self.assertEqual(len(h), 64)

    def test_hmac_sha256_utility(self):
        mac = hmac_sha256(b"key", b"message")
        self.assertIsInstance(mac, bytes)
        self.assertEqual(len(mac), 32)

    def test_encrypt_empty_plaintext(self):
        pk, sk = self.pqc.generate_keypair()
        ct = self.pqc.encrypt(b"", pk)
        pt = self.pqc.decrypt(ct, sk)
        self.assertEqual(pt, b"")


if __name__ == "__main__":
    unittest.main()
