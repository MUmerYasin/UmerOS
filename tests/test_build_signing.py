"""[FIX H42] signing gate: fail-closed by default, unsigned only via env opt-out."""
from __future__ import annotations
import os, subprocess, sys, unittest
from pathlib import Path
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

SPEC = Path(_root) / "build" / "UmerOS-GUI.spec"
SIGN = [sys.executable, str(Path(_root) / "build" / "sign_artifact.py")]

class TestSigningGate(unittest.TestCase):
    def test_spec_has_no_hardcoded_dev_path(self):
        src = SPEC.read_text(encoding="utf-8")
        self.assertNotIn("F:\\\\Pension", src)

    def test_missing_artifact_fails_closed(self):
        env = {**os.environ, "UMEROS_ALLOW_UNSIGNED": ""}
        r = subprocess.run(SIGN + ["does-not-exist.exe"], capture_output=True,
                           text=True, env=env)
        self.assertEqual(r.returncode, 1)

    def test_unsigned_opt_out_is_explicit(self):
        dummy = Path(_root) / "dist_dummy.bin"
        dummy.write_bytes(b"MZ")
        self.addCleanup(lambda: dummy.unlink(missing_ok=True))
        env = {**os.environ, "UMEROS_ALLOW_UNSIGNED": "1",
               "UMEROS_SIGN_PFX": "", "UMEROS_SIGN_THUMBPRINT": ""}
        r = subprocess.run(SIGN + [str(dummy)], capture_output=True,
                           text=True, env=env)
        self.assertEqual(r.returncode, 0)          # dev opt-out allowed
        self.assertIn("DO NOT SHIP", r.stderr)

    def test_no_cert_fails_even_for_existing_artifact(self):
        dummy = Path(_root) / "dist_dummy2.bin"
        dummy.write_bytes(b"MZ")
        self.addCleanup(lambda: dummy.unlink(missing_ok=True))
        env = {**os.environ, "UMEROS_ALLOW_UNSIGNED": "",
               "UMEROS_SIGN_PFX": "", "UMEROS_SIGN_THUMBPRINT": ""}
        r = subprocess.run(SIGN + [str(dummy)], capture_output=True,
                           text=True, env=env)
        self.assertEqual(r.returncode, 1)

if __name__ == "__main__":
    unittest.main()
