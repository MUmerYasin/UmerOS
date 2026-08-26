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
Regression tests for quantum/ RED findings H215/H216/H217/H221.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import unittest
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)


class TestCryptoPqcHeader(unittest.TestCase):
    """[FIX H215] canonical licence tag / [FIX H216] honest docstring."""

    def test_canonical_license_tag(self):
        src = (Path(_root) / "quantum" / "crypto_pqc.py").read_text(encoding="utf-8")
        self.assertIn("License: GPL-3.0\n", src)
        self.assertNotIn("(GNU General Public License Version 3)", src)

    def test_docstring_states_fallback_not_quantum_safe(self):
        src = (Path(_root) / "quantum" / "crypto_pqc.py").read_text(encoding="utf-8")
        self.assertIn("NOT quantum-safe", src)
        self.assertIn("is_post_quantum", src)


class TestAuthAtRest(unittest.TestCase):
    """[FIX H217] provider credentials encrypted at rest."""

    def setUp(self) -> None:
        import tempfile
        from quantum.cloud.auth import AuthManager
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mgr = AuthManager()
        os.environ["UMEROS_QUANTUM_AUTH_KEY"] = "unit-test-passphrase"
        self.addCleanup(os.environ.pop, "UMEROS_QUANTUM_AUTH_KEY", None)
        self.path = str(Path(self.tmp.name) / "creds.json")

    def test_saved_file_is_encrypted_envelope(self):
        from quantum.cloud.auth import AuthCredentials
        self.mgr.set_credentials("ibmq", AuthCredentials(api_key="supersecret", provider="ibmq"))
        self.mgr.save_to_file("ibmq", self.path)
        raw = Path(self.path).read_text(encoding="utf-8")
        self.assertNotIn("supersecret", raw)
        data = json.loads(raw)
        self.assertEqual(data.get("enc"), "aes256gcm")
        # mode tightened where the OS supports it
        if os.name == "posix":
            self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o600)

    def test_round_trip_and_plaintext_refusal(self):
        from quantum.cloud.auth import AuthCredentials
        self.mgr.set_credentials("ibmq", AuthCredentials(api_key="k2", provider="ibmq"))
        self.mgr.save_to_file("ibmq", self.path)
        loaded = self.mgr.load_from_file("ibmq", self.path)
        self.assertEqual(loaded.api_key, "k2")
        Path(self.path).write_text(json.dumps({"api_key": "plain"}), encoding="utf-8")
        with self.assertRaises(ValueError):
            self.mgr.load_from_file("ibmq", self.path)


if __name__ == "__main__":
    unittest.main()
