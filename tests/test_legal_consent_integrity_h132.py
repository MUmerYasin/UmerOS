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

"""H132 tests — the consent ledger must be tamper-evident (HMAC-signed).

The standard flagged ``legal/consent.py``: the "cryptographic" consent token was
``sha256(disclaimer_key:user:host:machine_id:version:now:full_text)`` — a hash of
**public, attacker-reproducible values**, i.e. not a signature at all.  And
``load_ledger`` never verified integrity, so the ledger was freely editable.

H132 signs each record with **HMAC-SHA256** under a 256-bit key stored in a
sidecar ``<ledger>.key`` file (or the ``UMEROS_CONSENT_KEY`` env var), and
``load_ledger`` now **rejects** any record whose signature does not verify
(fail-closed).
"""

import hashlib
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
    ConsentManager,
    decode_ledger,
    encode_ledger,
    sign_record,
    verify_record,
)


def _read_ledger(ledger: Path) -> dict:
    """Decode the (AES-256-GCM encrypted) ledger file with its sidecar key (H134)."""
    key = bytes.fromhex(Path(str(ledger) + ".key").read_text(encoding="ascii").strip())
    return decode_ledger(ledger.read_bytes(), key)


def _write_ledger(ledger: Path, data: dict) -> None:
    """Re-encode a tampered ledger — keeps a valid envelope so only the HMAC fails."""
    key = bytes.fromhex(Path(str(ledger) + ".key").read_text(encoding="ascii").strip())
    ledger.write_bytes(encode_ledger(data, key))

_KEY_A = b"A" * 32
_KEY_B = b"B" * 32
_FIELDS = {
    "disclaimer_key": "general",
    "user_name": "u",
    "hostname": "h",
    "machine_id": "m",
    "agreed_at": 1.0,
    "disclaimer_version": "v1",
    "status": "GRANTED",
}


class TestHmacSignaturePrimitives(unittest.TestCase):
    """``sign_record`` / ``verify_record`` behave like a real MAC."""

    def test_signature_is_sha256_hex(self):
        sig = sign_record(_FIELDS, _KEY_A)
        self.assertEqual(len(sig), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in sig))

    def test_signature_depends_on_the_key(self):
        self.assertNotEqual(sign_record(_FIELDS, _KEY_A), sign_record(_FIELDS, _KEY_B))

    def test_verify_accepts_matching_key_only(self):
        signed = {**_FIELDS, "consent_token": sign_record(_FIELDS, _KEY_A)}
        self.assertTrue(verify_record(signed, _KEY_A))
        self.assertFalse(verify_record(signed, _KEY_B))

    def test_verify_rejects_missing_or_empty_token(self):
        self.assertFalse(verify_record(_FIELDS, _KEY_A))
        self.assertFalse(verify_record({**_FIELDS, "consent_token": ""}, _KEY_A))

    def test_verify_rejects_any_field_change(self):
        signed = {**_FIELDS, "consent_token": sign_record(_FIELDS, _KEY_A)}
        for field, value in (("user_name", "attacker"), ("status", "REVOKED"),
                             ("machine_id", "other")):
            tampered = {**signed, field: value}
            self.assertFalse(verify_record(tampered, _KEY_A), field)


class TestGrantedTokenIsASignature(unittest.TestCase):
    """The issued token is an HMAC, not a hash of public values."""

    def test_token_is_hmac_not_plain_hash(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "consent.json"
            rec = ConsentManager(ledger_path=ledger).grant_consent("general", "I AGREE")
            self.assertEqual(len(rec.consent_token), 64)

            from legal.disclaimer import DisclaimerRegistry
            notice = DisclaimerRegistry.get_notice("general")
            old_style = hashlib.sha256(
                (f"{rec.disclaimer_key}:{rec.user_name}:{rec.hostname}:{rec.machine_id}:"
                 f"{rec.disclaimer_version}:{rec.agreed_at}:{notice.full_text}").encode("utf-8")
            ).hexdigest()
            self.assertNotEqual(rec.consent_token, old_style,
                                "token is still a plain public-value hash")

    def test_key_file_is_created(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "consent.json"
            ConsentManager(ledger_path=ledger).grant_consent("general", "I AGREE")
            key_file = Path(str(ledger) + ".key")
            self.assertTrue(key_file.exists())
            self.assertEqual(len(key_file.read_text(encoding="ascii").strip()), 64)


class TestLedgerVerificationOnLoad(unittest.TestCase):
    """``load_ledger`` must verify and reject unverifiable records (fail-closed)."""

    def test_valid_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "consent.json"
            ConsentManager(ledger_path=ledger).grant_consent("general", "I AGREE")
            fresh = ConsentManager(ledger_path=ledger)
            self.assertTrue(fresh.has_consented("general"))
            self.assertEqual(fresh.verify_ledger(), (1, 0))

    def test_tampered_field_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "consent.json"
            ConsentManager(ledger_path=ledger).grant_consent("general", "I AGREE")
            data = _read_ledger(ledger)
            data["general"]["user_name"] = "attacker"
            _write_ledger(ledger, data)

            fresh = ConsentManager(ledger_path=ledger)
            self.assertFalse(fresh.has_consented("general"))
            self.assertEqual(fresh.list_consents(), {})

    def test_flipping_status_to_granted_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "consent.json"
            mgr = ConsentManager(ledger_path=ledger)
            mgr.grant_consent("general", "I AGREE")
            mgr.revoke_consent("general")
            data = _read_ledger(ledger)
            data["general"]["status"] = "GRANTED"  # forge a re-grant
            _write_ledger(ledger, data)
            self.assertFalse(ConsentManager(ledger_path=ledger).has_consented("general"))

    def test_missing_key_rejects_records(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "consent.json"
            ConsentManager(ledger_path=ledger).grant_consent("general", "I AGREE")
            Path(str(ledger) + ".key").unlink()
            self.assertFalse(ConsentManager(ledger_path=ledger).has_consented("general"))

    def test_wrong_key_rejects_records(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "consent.json"
            ConsentManager(ledger_path=ledger).grant_consent("general", "I AGREE")
            Path(str(ledger) + ".key").write_text("cd" * 32, encoding="ascii")
            self.assertFalse(ConsentManager(ledger_path=ledger).has_consented("general"))

    def test_revoke_re_signs_and_stays_verifiable(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "consent.json"
            mgr = ConsentManager(ledger_path=ledger)
            mgr.grant_consent("general", "I AGREE")
            self.assertTrue(mgr.revoke_consent("general"))
            fresh = ConsentManager(ledger_path=ledger)
            self.assertFalse(fresh.has_consented("general"))
            self.assertEqual(fresh.verify_ledger(), (1, 0))

    def test_env_var_key_override(self):
        with tempfile.TemporaryDirectory() as d:
            key_hex = "ab" * 32
            with mock.patch.dict(os.environ, {"UMEROS_CONSENT_KEY": key_hex}):
                ledger = Path(d) / "consent.json"
                rec = ConsentManager(ledger_path=ledger).grant_consent("general", "I AGREE")
                self.assertTrue(verify_record(rec.to_dict(), bytes.fromhex(key_hex)))
                # no sidecar key file is written when the env var supplies it
                self.assertFalse(Path(str(ledger) + ".key").exists())


class TestSourceInvariants(unittest.TestCase):
    """Pin code facts, never cosmetic tags."""

    def test_hmac_is_used(self):
        src = CONSENT_SRC.read_text(encoding="utf-8")
        self.assertIn("import hmac", src)
        self.assertIn("hmac.new(", src)
        self.assertIn("hmac.compare_digest(", src)

    def test_load_ledger_verifies(self):
        src = CONSENT_SRC.read_text(encoding="utf-8")
        self.assertIn("verify_record(rec, key)", src)

    def test_grant_no_longer_hashes_public_values(self):
        src = CONSENT_SRC.read_text(encoding="utf-8")
        self.assertNotIn('hashlib.sha256(payload.encode("utf-8")).hexdigest()', src)

    def test_docstring_describes_tamper_evidence(self):
        src = CONSENT_SRC.read_text(encoding="utf-8")
        self.assertIn("HMAC-SHA256", src)
        self.assertIn("tamper-evident", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
