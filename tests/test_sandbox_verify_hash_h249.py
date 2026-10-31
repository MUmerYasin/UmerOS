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

"""H249 - `verify_signature` was a keyless hash compare, not signing.

The row was: ``SecuritySandbox.verify_signature`` computes
``sha3_512(payload)`` and compares it to a caller-supplied string. There is no
key, so it is not a signature - callers who assumed cryptographic signing got
integrity-with-no-secret at best.

The fix renames it to ``verify_hash`` (honest), adds a real shared-secret
``verify_hmac`` (authenticity, labelled symmetric), and keeps
``verify_signature`` only as a warning alias so nothing breaks silently.

The decisive test is the pairing: the *same* forgery that defeats
``verify_hash`` (rewrite the payload, rewrite the digest) fails against
``verify_hmac``, which is exactly the difference between "integrity" and
"authenticity".
"""
from __future__ import annotations

import hashlib
import hmac
import pathlib
import unittest

from security.sandbox import SecuritySandbox

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
KEY = b"shared-secret-key-for-tests"


def _live_sandbox_source() -> str:
    """Return the live ``SecuritySandbox`` source, excluding the dead code.

    ``inspect.getsource`` is unusable here: everything after the class is
    commented out and ``tokenize`` skips comment tokens, so no DEDENT arrives
    and the "class source" would run to EOF (H248 lesson).
    """
    text = (PROJECT_ROOT / "security" / "sandbox.py").read_text(encoding="utf-8")
    start = text.index("class SecuritySandbox:")
    end = text.index("\n# -----", start)
    return text[start:end]


class _Base(unittest.TestCase):
    def setUp(self):
        self.sandbox = SecuritySandbox()
        self.sandbox.register_process(1, "app")
        self.payload = b"MZ fake executable payload"
        self.digest = hashlib.sha3_512(self.payload).hexdigest()
        self.tag = hmac.new(KEY, self.payload, hashlib.sha3_512).hexdigest()


# ---------------------------------------------------------------------------
# verify_hash: integrity, and nothing more
# ---------------------------------------------------------------------------

class TestVerifyHash(_Base):

    def test_accepts_the_matching_digest(self):
        self.assertTrue(self.sandbox.verify_hash(1, self.payload, self.digest))

    def test_rejects_a_wrong_digest(self):
        self.assertFalse(self.sandbox.verify_hash(1, self.payload, "0" * 128))

    def test_rejects_a_non_string_digest_without_raising(self):
        for bad in (None, b"00" * 64, 12345, ["0" * 128]):
            self.assertFalse(self.sandbox.verify_hash(1, self.payload, bad))

    def test_the_digest_is_over_the_payload_not_the_pid(self):
        """The old dead code hashed the PID; a PID digest must not verify a payload."""
        pid_digest = hashlib.sha3_512(b"1").hexdigest()
        self.assertFalse(self.sandbox.verify_hash(1, self.payload, pid_digest))

    def test_different_payloads_produce_different_digests(self):
        other = hashlib.sha3_512(b"different").hexdigest()
        self.assertFalse(self.sandbox.verify_hash(1, self.payload, other))

    def test_a_keyless_digest_cannot_prove_authorship(self):
        """The honest limitation, stated as a test rather than hidden.

        Whoever can rewrite the payload can also rewrite the digest it is
        checked against - so this proves integrity against accident, not
        authenticity against an attacker.
        """
        forged = b"MZ forged payload"
        forged_digest = hashlib.sha3_512(forged).hexdigest()
        self.assertTrue(
            self.sandbox.verify_hash(1, forged, forged_digest),
            "a keyless digest match cannot distinguish who produced the bytes",
        )


# ---------------------------------------------------------------------------
# verify_hmac: authenticity, with a shared secret
# ---------------------------------------------------------------------------

class TestVerifyHmac(_Base):

    def test_accepts_a_matching_tag(self):
        self.assertTrue(self.sandbox.verify_hmac(1, self.payload, self.tag, KEY))

    def test_rejects_the_wrong_key(self):
        self.assertFalse(
            self.sandbox.verify_hmac(1, self.payload, self.tag, b"wrong-key")
        )

    def test_rejects_a_tampered_payload(self):
        self.assertFalse(
            self.sandbox.verify_hmac(1, b"MZ forged payload", self.tag, KEY)
        )

    def test_rejects_a_plain_digest_used_as_a_tag(self):
        """Proves the key is actually in the computation."""
        self.assertFalse(self.sandbox.verify_hmac(1, self.payload, self.digest, KEY))

    def test_rejects_a_non_string_tag_without_raising(self):
        for bad in (None, b"00" * 64, 12345):
            self.assertFalse(self.sandbox.verify_hmac(1, self.payload, bad, KEY))

    def test_an_empty_key_is_a_caller_error(self):
        for bad_key in (b"", bytearray(), None, "text-key"):
            with self.subTest(key=repr(bad_key)):
                with self.assertRaises(ValueError):
                    self.sandbox.verify_hmac(1, self.payload, self.tag, bad_key)

    def test_the_same_forgery_that_defeats_verify_hash_fails_here(self):
        """The decisive pairing: integrity vs authenticity on one attack."""
        forged = b"MZ forged payload"
        forged_digest = hashlib.sha3_512(forged).hexdigest()

        # Keyless check is satisfied by the forgery...
        self.assertTrue(self.sandbox.verify_hash(1, forged, forged_digest))
        # ...the keyed check is not, because the attacker lacks the key.
        self.assertFalse(self.sandbox.verify_hmac(1, forged, self.tag, KEY))

    def test_a_bytearray_key_is_accepted(self):
        self.assertTrue(
            self.sandbox.verify_hmac(1, self.payload, self.tag, bytearray(KEY))
        )


# ---------------------------------------------------------------------------
# The deprecated alias
# ---------------------------------------------------------------------------

class TestDeprecatedAlias(_Base):

    def test_the_alias_still_returns_the_same_answer(self):
        with self.assertWarns(DeprecationWarning):
            self.assertTrue(self.sandbox.verify_signature(1, self.payload, self.digest))
        with self.assertWarns(DeprecationWarning):
            self.assertFalse(self.sandbox.verify_signature(1, self.payload, "0" * 128))

    def test_the_alias_warns_that_it_is_not_signing(self):
        with self.assertWarns(DeprecationWarning) as caught:
            self.sandbox.verify_signature(1, self.payload, self.digest)
        message = str(caught.warning).lower()
        self.assertIn("not signature verification", message)
        self.assertIn("verify_hmac", message)

    def test_the_alias_docstring_says_it_is_not_signing(self):
        doc = (SecuritySandbox.verify_signature.__doc__ or "").lower()
        self.assertIn("not", doc)
        self.assertIn("signing", doc)
        self.assertIn("verify_hash", doc)


# ---------------------------------------------------------------------------
# The label matches the code
# ---------------------------------------------------------------------------

class TestLabelsMatchTheCode(unittest.TestCase):

    def test_the_live_class_no_longer_claims_code_signing(self):
        live = _live_sandbox_source()
        self.assertNotIn("CODE SIGNING FAILED", live)
        self.assertNotIn("Code signature verified", live)
        self.assertNotIn("Verifies the cryptographic signature", live)

    def test_the_new_docstring_is_not_a_patch_note(self):
        """No "IMPROVED:" self-congratulation on the renamed method.

        (``resolve_path`` still carries that prefix; it is a different row's
        cosmetics, so this is scoped to the method under study.)
        """
        live = _live_sandbox_source()
        block = live[live.index("def verify_hash") : live.index("def verify_hmac")]
        self.assertNotIn("IMPROVED", block)

    def test_the_live_class_offers_both_operations(self):
        live = _live_sandbox_source()
        self.assertIn("def verify_hash", live)
        self.assertIn("def verify_hmac", live)

    def test_verify_signature_survives_only_as_the_deprecated_alias(self):
        live = _live_sandbox_source()
        self.assertEqual(live.count("def verify_signature"), 1)
        # The one survivor must be the alias: it warns and delegates.
        index = live.index("def verify_signature")
        tail = live[index:]
        self.assertIn("warnings.warn", tail)
        self.assertIn("self.verify_hash(", tail)

    def test_both_comparisons_are_constant_time(self):
        live = _live_sandbox_source()
        self.assertGreaterEqual(live.count("compare_digest"), 2)

    def test_the_module_docstring_names_both_operations_honestly(self):
        import security.sandbox as mod

        doc = mod.__doc__ or ""
        self.assertIn("verify_hash", doc)
        self.assertIn("verify_hmac", doc)
        self.assertIn("integrity", doc)
        self.assertIn("authenticity", doc)
        self.assertNotIn("``verify_signature`` —", doc)


if __name__ == "__main__":
    unittest.main()
