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
Regression tests for kernel/ security RED findings
==================================================
  - H110: real ``MemoryManager`` / ``IPCBus`` / ``CapabilityManager`` are wired
          into ``UmerKernel`` (replaces the no-op ``type(...)`` placeholders that
          left zero-trust gating, signed IPC and real memory accounting inert).
  - H111: ``CryptoEngine`` is real (fail-closed ``verify``, AES-256-GCM
          encrypt/decrypt) — not the dummy backdoor that returned ``True``
          unconditionally and a constant signature.
  - H112: ``SecuritySandbox.register_process`` enforces ``fs_root`` containment
          (fail-closed via ``core.path_guard.safe_join``) instead of being a
          decorative gate that only ``print``ed.

Run:  python -m unittest tests.test_kernel_security -v
"""
from __future__ import annotations

import logging
import unittest

from kernel.memory_manager import MemoryManager
from kernel.ipc_bus import IPCBus
from kernel.capability_manager import CapabilityManager, SYSTEM_PID, CAP_FS_ADMIN
from kernel.umer_kernel import (
    CryptoEngine, SecuritySandbox, SecurityViolation, UmerKernel,
)

# Keep the real subsystems' noisy INFO logging out of the test output.
logging.disable(logging.CRITICAL)


# ---------------------------------------------------------------------------
# H110 — real subsystems must be wired into the kernel
# ---------------------------------------------------------------------------

class TestKernelManagersWired(unittest.TestCase):
    """The kernel must use the REAL subsystems, not placeholder stubs."""

    def setUp(self):
        self.kernel = UmerKernel()

    def test_memory_manager_is_real(self):
        self.assertIsInstance(self.kernel.memory, MemoryManager)
        self.assertEqual(type(self.kernel.memory).__module__, "kernel.memory_manager")

    def test_ipc_bus_is_real(self):
        self.assertIsInstance(self.kernel.ipc, IPCBus)
        self.assertEqual(type(self.kernel.ipc).__module__, "kernel.ipc_bus")

    def test_capability_manager_is_real(self):
        self.assertIsInstance(self.kernel.capabilities, CapabilityManager)
        self.assertEqual(type(self.kernel.capabilities).__module__, "kernel.capability_manager")

    def test_system_pid_is_omnipotent(self):
        # With the real CapabilityManager wired, the kernel (PID 0) holds all caps
        # — proof the zero-trust manager is live, not the no-op stub.
        self.assertTrue(self.kernel.capabilities.query(SYSTEM_PID, CAP_FS_ADMIN))

    def test_memory_stats_are_real(self):
        stats = self.kernel.memory.stats()
        self.assertIn("total_pages", stats)
        self.assertGreater(stats["total_pages"], 0)


# ---------------------------------------------------------------------------
# H111 — CryptoEngine must not be a dummy fail-open backdoor
# ---------------------------------------------------------------------------

class TestCryptoEngineReal(unittest.TestCase):
    def setUp(self):
        self.ce = CryptoEngine()

    def test_verify_rejects_tampered_data(self):
        data = b"trusted-artifact"
        sig = self.ce.sign(data)
        self.assertTrue(self.ce.verify(data, sig))
        self.assertFalse(self.ce.verify(data + b"x", sig))   # tamper -> reject

    def test_verify_rejects_wrong_signature(self):
        self.assertFalse(self.ce.verify(b"x", b"not-a-real-sig"))

    def test_sign_is_key_bound(self):
        other = CryptoEngine()
        data = b"payload"
        sig = self.ce.sign(data)
        # A verifier using its OWN (different) key must NOT validate the signature.
        self.assertFalse(other.verify(data, sig))

    def test_encrypt_decrypt_roundtrip(self):
        nonce, ct = self.ce.encrypt(b"secret-bytes")
        self.assertEqual(self.ce.decrypt((nonce, ct)), b"secret-bytes")

    def test_sign_not_constant(self):
        # Different instances (different keys) must produce different signatures.
        self.assertNotEqual(CryptoEngine().sign(b"p"), CryptoEngine().sign(b"p"))


# ---------------------------------------------------------------------------
# H112 — register_process must enforce fs_root containment (fail-closed)
# ---------------------------------------------------------------------------

class TestSecuritySandboxEnforcement(unittest.TestCase):
    def setUp(self):
        self.sb = SecuritySandbox()
        self.sb.register_process(2000, "umer-chat", fs_root="/user")

    def test_register_stores_normalized_fs_root(self):
        import os as _os
        self.assertEqual(
            self.sb.processes[2000]["fs_root"], _os.path.normpath("/user")
        )

    def test_in_root_path_allowed(self):
        # Must not raise, and the resolved path stays inside the fs_root.
        resolved = self.sb.check_path(2000, "docs/notes.txt")
        self.assertTrue(str(resolved).endswith("notes.txt"))

    def test_escape_denied(self):
        with self.assertRaises(SecurityViolation):
            self.sb.check_path(2000, "../etc/passwd")
        self.assertFalse(self.sb.is_path_allowed(2000, "../etc/passwd"))

    def test_nested_escape_denied(self):
        with self.assertRaises(SecurityViolation):
            self.sb.check_path(2000, "a/../../etc/shadow")

    def test_empty_fs_root_rejected(self):
        with self.assertRaises(ValueError):
            self.sb.register_process(3000, "bad", fs_root="")

    def test_unregistered_pid_denied(self):
        with self.assertRaises(SecurityViolation):
            self.sb.check_path(9999, "anything.txt")


if __name__ == "__main__":
    unittest.main()
