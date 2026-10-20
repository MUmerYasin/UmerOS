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

"""H134 tests — consent identity verification, at-rest encryption, erasure.

The standard flagged ``legal/consent.py``: consent was recorded under the default
``"admin"`` with **no identity verification**, and the recorded PII (user / host /
machine id) was stored unencrypted in a plain JSON ledger (§4.3 privacy).

H134:
  * resolves the consenting identity (explicit ``user_name`` or
    ``getpass.getuser()``) and never fabricates a default privileged account;
  * encrypts the ledger at rest with **AES-256-GCM** (HKDF-SHA256-derived key),
    so PII is not readable in the file;
  * adds ``forget_consent`` / ``erase_all`` erasure hooks.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONSENT_SRC = ROOT / "legal" / "consent.py"

from legal.consent import (  # noqa: E402
    ConsentGateError,
    ConsentManager,
    decode_ledger,
    encode_ledger,
    sign_record,
    load_or_create_ledger_key,
    _LEDGER_MAGIC,
    _resolve_identity,
)

def _no_identity():
    """Context manager: make identity resolution impossible."""
    return (
        mock.patch("legal.consent.getpass.getuser", side_effect=OSError("no user")),
        mock.patch.dict(os.environ, {}, clear=True),
    )


class TestIdentityResolution(unittest.TestCase):
    """Identity comes from a real source — never a fabricated 'admin'."""

    def test_explicit_name_wins(self):
        self.assertEqual(_resolve_identity("alice"), ("alice", True))
        self.assertEqual(_resolve_identity("  bob  "), ("bob", True))

    def test_os_identity_is_used(self):
        name, verified = _resolve_identity(None)
        self.assertTrue(verified)
        self.assertNotEqual(name.lower(), "admin")

    def test_no_identity_is_unauthenticated_not_admin(self):
        p1, p2 = _no_identity()
        with p1, p2:
            name, verified = _resolve_identity(None)
        self.assertEqual(name, "unauthenticated")
        self.assertFalse(verified)
        self.assertNotEqual(name, "admin")

    def test_strict_grant_refuses_without_identity(self):
        p1, p2 = _no_identity()
        with tempfile.TemporaryDirectory() as d, p1, p2:
            mgr = ConsentManager(ledger_path=Path(d) / "c.json")
            with self.assertRaises(ConsentGateError):
                mgr.grant_consent("general", "I AGREE")
            self.assertFalse(mgr.has_consented("general"))

    def test_opt_out_records_unauthenticated(self):
        p1, p2 = _no_identity()
        with tempfile.TemporaryDirectory() as d, p1, p2:
            mgr = ConsentManager(ledger_path=Path(d) / "c.json")
            rec = mgr.grant_consent("general", "I AGREE", require_identity=False)
            self.assertEqual(rec.user_name, "unauthenticated")
            self.assertFalse(rec.identity_verified)

    def test_granted_record_is_marked_verified(self):
        with tempfile.TemporaryDirectory() as d:
            rec = ConsentManager(ledger_path=Path(d) / "c.json").grant_consent(
                "general", "I AGREE")
            self.assertTrue(rec.identity_verified)
            self.assertNotEqual(rec.user_name.lower(), "admin")


class TestLedgerEncryptionAtRest(unittest.TestCase):
    """The on-disk ledger is an authenticated AES-256-GCM envelope."""

    def test_pii_is_not_readable_on_disk(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "c.json"
            rec = ConsentManager(ledger_path=ledger).grant_consent("general", "I AGREE")
            raw = ledger.read_bytes()
            for secret in (rec.user_name, rec.hostname, rec.machine_id):
                self.assertNotIn(secret.encode("utf-8"), raw,
                                 f"{secret!r} leaked in plaintext")

    def test_envelope_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "c.json"
            ConsentManager(ledger_path=ledger).grant_consent("general", "I AGREE")
            env = json.loads(ledger.read_bytes().decode("utf-8"))
            self.assertEqual(env["magic"], _LEDGER_MAGIC)
            self.assertEqual(env["alg"], "AES-256-GCM")
            self.assertIn("nonce", env)
            self.assertIn("ct", env)

    def test_round_trip_and_verify(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "c.json"
            ConsentManager(ledger_path=ledger).grant_consent("general", "I AGREE")
            fresh = ConsentManager(ledger_path=ledger)
            self.assertTrue(fresh.has_consented("general"))
            self.assertEqual(fresh.verify_ledger(), (1, 0))

    def test_wrong_key_cannot_decrypt(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "c.json"
            ConsentManager(ledger_path=ledger).grant_consent("general", "I AGREE")
            Path(str(ledger) + ".key").write_text("cd" * 32, encoding="ascii")
            self.assertFalse(ConsentManager(ledger_path=ledger).has_consented("general"))

    def test_tampered_ciphertext_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "c.json"
            ConsentManager(ledger_path=ledger).grant_consent("general", "I AGREE")
            env = json.loads(ledger.read_bytes().decode("utf-8"))
            ct = bytearray(bytes.fromhex(env["ct"]))
            ct[0] ^= 0xFF
            env["ct"] = bytes(ct).hex()
            ledger.write_bytes(json.dumps(env).encode("utf-8"))
            self.assertFalse(ConsentManager(ledger_path=ledger).has_consented("general"))

    def test_codec_round_trip(self):
        key = b"K" * 32
        records = {"general": {"disclaimer_key": "general", "status": "GRANTED"}}
        blob = encode_ledger(records, key)
        self.assertNotIn(b"GRANTED", blob)  # payload is encrypted
        self.assertEqual(decode_ledger(blob, key), records)

    def test_decode_rejects_wrong_key(self):
        blob = encode_ledger({"a": 1}, b"K" * 32)
        with self.assertRaises(ConsentGateError):
            decode_ledger(blob, b"L" * 32)

    def test_decode_accepts_legacy_plaintext(self):
        # A pre-H134 plaintext ledger must still load (migration path).
        records = {"general": {"disclaimer_key": "general", "status": "GRANTED"}}
        blob = json.dumps(records).encode("utf-8")
        self.assertEqual(decode_ledger(blob, b"K" * 32), records)

    def test_legacy_plaintext_ledger_still_verifies(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "legacy.json"
            key = load_or_create_ledger_key(ledger)
            rec = {"disclaimer_key": "general", "user_name": "legacy", "hostname": "h",
                   "machine_id": "m", "agreed_at": 1.0, "disclaimer_version": "v",
                   "status": "GRANTED", "identity_verified": True}
            rec["consent_token"] = sign_record(rec, key)
            ledger.write_bytes(json.dumps({"general": rec}).encode("utf-8"))
            self.assertTrue(ConsentManager(ledger_path=ledger).has_consented("general"))


class TestErasureHooks(unittest.TestCase):
    """``forget_consent`` / ``erase_all`` implement the right to erasure."""

    def test_forget_consent_removes_one(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "c.json"
            mgr = ConsentManager(ledger_path=ledger)
            mgr.grant_consent("general", "I AGREE")
            mgr.grant_consent("installer", "I AGREE")
            self.assertTrue(mgr.forget_consent("general"))
            self.assertFalse(mgr.forget_consent("general"))  # already gone
            self.assertFalse(mgr.has_consented("general"))
            self.assertTrue(mgr.has_consented("installer"))
            # Persisted: a fresh manager sees only the remaining record.
            self.assertEqual(list(ConsentManager(ledger_path=ledger).list_consents()),
                             ["installer"])

    def test_erase_all_clears_and_persists(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "c.json"
            mgr = ConsentManager(ledger_path=ledger)
            mgr.grant_consent("general", "I AGREE")
            mgr.grant_consent("installer", "I AGREE")
            self.assertEqual(mgr.erase_all(), 2)
            self.assertEqual(mgr.list_consents(), {})
            self.assertEqual(ConsentManager(ledger_path=ledger).list_consents(), {})

    def test_erase_all_can_delete_file(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "c.json"
            mgr = ConsentManager(ledger_path=ledger)
            mgr.grant_consent("general", "I AGREE")
            self.assertEqual(mgr.erase_all(delete_file=True), 1)
            self.assertFalse(ledger.exists())


class TestSourceInvariants(unittest.TestCase):
    """Pin code facts, never cosmetic tags."""

    def test_identity_is_resolved_not_defaulted(self):
        src = CONSENT_SRC.read_text(encoding="utf-8")
        self.assertIn("import getpass", src)
        self.assertIn("_resolve_identity", src)
        self.assertNotIn('or "admin"', src)

    def test_ledger_is_encrypted_at_rest(self):
        src = CONSENT_SRC.read_text(encoding="utf-8")
        self.assertIn("AESGCM", src)
        self.assertIn("encode_ledger", src)
        self.assertIn("decode_ledger", src)
        self.assertIn("_LEDGER_MAGIC", src)

    def test_erasure_hooks_present(self):
        src = CONSENT_SRC.read_text(encoding="utf-8")
        self.assertIn("def forget_consent", src)
        self.assertIn("def erase_all", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
