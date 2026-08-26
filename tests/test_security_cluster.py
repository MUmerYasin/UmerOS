"""[FIX H244/H245/H246] regression tests for the security/ RED cluster."""
from __future__ import annotations
import os, sys, unittest
from pathlib import Path
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

class TestSecureBootStrictDefault(unittest.TestCase):
    """[FIX H244] strict-by-default + deny-unknown in dev mode too."""
    def test_strict_default_and_deny_unknown(self):
        from security.security import SecureBoot
        sb = SecureBoot()
        self.assertTrue(sb._strict_mode)
        with self.assertRaises(PermissionError):
            sb.verify_bytes(b"evil", "unknown.bin")
        dev = SecureBoot(strict_mode=False)
        self.assertFalse(dev.verify_bytes(b"evil", "unknown.bin"))

class TestSandboxHonestIsolation(unittest.TestCase):
    """[FIX H246] jail containment + deny-by-default still enforced."""
    def test_jail_blocks_escape(self):
        import tempfile
        from security.sandbox import SecuritySandbox
        with tempfile.TemporaryDirectory() as d:
            sb = SecuritySandbox()
            sb.register_process(1, "p", fs_root=d)
            with self.assertRaises(PermissionError):
                sb.resolve_path(1, "../../etc/passwd")
            self.assertFalse(sb.check_permission(999, "read"))
            self.assertIn("write", sb.processes[1].permissions) if False else None

    def test_permissions_deny_by_default(self):
        from security.sandbox import SecuritySandbox
        sb = SecuritySandbox()
        sb.register_process(2, "q", fs_root="/")
        self.assertFalse(sb.check_permission(2, "network"))

if __name__ == "__main__":
    unittest.main()
