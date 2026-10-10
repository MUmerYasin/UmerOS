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
    """canonical licence tag /  honest docstring."""

    def test_canonical_license_tag(self):
        src = (Path(_root) / "quantum" / "crypto_pqc.py").read_text(encoding="utf-8")
        self.assertIn("License: GPL-3.0\n", src)
        self.assertNotIn("(GNU General Public License Version 3)", src)

    def test_docstring_states_fallback_not_quantum_safe(self):
        src = (Path(_root) / "quantum" / "crypto_pqc.py").read_text(encoding="utf-8")
        self.assertIn("NOT quantum-safe", src)
        self.assertIn("is_post_quantum", src)


class TestAuthAtRest(unittest.TestCase):
    """provider credentials encrypted at rest."""

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


class TestServerPosture(unittest.TestCase):
    """H221: quantum_server network posture — CORS allowlist, bearer auth, loopback bind."""

    def test_allowed_origins_defaults_to_loopback_not_wildcard(self):
        import quantum.quantum_server as qs
        os.environ.pop("UMEROS_QS_ALLOWED_ORIGINS", None)
        origins = qs._allowed_origins()
        self.assertNotIn("*", origins)
        self.assertTrue(
            all(o.startswith(("http://127.0.0.1", "http://localhost")) for o in origins)
        )

    def test_allowed_origins_env_override(self):
        import quantum.quantum_server as qs
        os.environ["UMEROS_QS_ALLOWED_ORIGINS"] = "https://app.example.com, https://x.test"
        self.addCleanup(os.environ.pop, "UMEROS_QS_ALLOWED_ORIGINS", None)
        self.assertEqual(
            qs._allowed_origins(), ["https://app.example.com", "https://x.test"]
        )

    def test_auth_dependency_denies_wrong_token(self):
        from fastapi import HTTPException
        import quantum.quantum_server as qs
        os.environ["UMEROS_QS_TOKEN"] = "sekret"
        self.addCleanup(os.environ.pop, "UMEROS_QS_TOKEN", None)
        with self.assertRaises(HTTPException) as cm:
            qs._auth_dependency("Bearer nope")
        self.assertEqual(cm.exception.status_code, 401)
        self.assertIsNone(qs._auth_dependency("Bearer sekret"))

    def test_auth_dependency_open_when_no_token(self):
        import quantum.quantum_server as qs
        os.environ.pop("UMEROS_QS_TOKEN", None)
        self.assertIsNone(qs._auth_dependency(None))

    def test_endpoint_requires_bearer_when_token_set(self):
        from fastapi.testclient import TestClient
        import quantum.quantum_server as qs
        os.environ["UMEROS_QS_TOKEN"] = "sekret"
        self.addCleanup(os.environ.pop, "UMEROS_QS_TOKEN", None)
        client = TestClient(qs.app)
        self.assertEqual(client.get("/health").status_code, 401)
        ok = client.get("/health", headers={"Authorization": "Bearer sekret"})
        self.assertNotEqual(ok.status_code, 401)

    def test_main_refuses_remote_bind_without_token(self):
        import subprocess
        env = dict(os.environ)
        env["UMEROS_QS_HOST"] = "0.0.0.0"
        env.pop("UMEROS_QS_TOKEN", None)
        proc = subprocess.run(
            [sys.executable, "-m", "quantum.quantum_server"],
            cwd=_root, env=env, capture_output=True, text=True, timeout=60,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Refusing to expose", proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
