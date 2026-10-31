"""H249 applier: `verify_signature` is a keyless hash compare, not signing.

Premise (drift-recon): TRUE.
  * `verify_signature` computes `sha3_512(payload)` and compares it to a
    caller-supplied string - no key, so it proves integrity at most.
  * The method docstring says "Verifies the cryptographic signature", and the
    log lines say "CODE SIGNING FAILED" / "Code signature verified".
  * Only `tests/test_security.py` calls it (2 tests); no production callers.
  * No HMAC helper exists to reuse (`security/hmac_utils.py` is listed in
    `__init__._try_import` but the module is absent).

Fix: rename to `verify_hash` (honest), add a real shared-secret
`verify_hmac` (authenticity, labelled symmetric), and keep `verify_signature`
only as a warning alias so no caller breaks silently.
"""
from __future__ import annotations

import io

SB = "security/sandbox.py"
TS = "tests/test_security.py"


def read(path: str) -> str:
    with io.open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def write(path: str, text: str) -> None:
    with io.open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def crlf(block: str) -> str:
    return block.replace("\r\n", "\n").replace("\n", "\r\n")


sb = read(SB)
original = sb

# 1. hoist the hmac import (two methods now need it) + warnings for the alias.
old = "\r\nimport hashlib\r\nimport logging\r\nimport os\r\n"
new = "\r\nimport hashlib\r\nimport hmac as _hmac\r\nimport logging\r\nimport os\r\nimport warnings\r\n"
assert sb.count(old) == 1, "import block anchor"
sb = sb.replace(old, new)

# 2. module docstring: name the two honest operations.
old = "  * ``verify_signature`` — SHA3-512 payload hash equality.\r\n"
new = (
    "  * ``verify_hash`` — SHA3-512 payload hash equality (integrity; no key,\r\n"
    "    so it says nothing about *who* produced the payload);\r\n"
    "  * ``verify_hmac`` — HMAC-SHA3-512 tag over the payload (authenticity via\r\n"
    "    a shared secret - symmetric, not asymmetric code signing).\r\n"
)
assert sb.count(old) == 1, "module docstring bullet anchor"
sb = sb.replace(old, new)

# 3. replace the method body.
START = (
    "\n    def verify_signature(self, pid: int, executable_payload: bytes, "
    "expected_hash: str) -> bool:\r\n"
)
assert sb.count(START) == 1, "live verify_signature anchor"
start = sb.index(START) + 1
END_ANCHOR = "        return is_valid\r\n"
end = sb.index(END_ANCHOR, start) + len(END_ANCHOR)
region = sb[start:end]
assert "# " not in region, "must not span dead code"
assert "sha3_512" in region and "compare_digest" in region

NEW = crlf('''    def verify_hash(self, pid: int, executable_payload: bytes, expected_hash: str) -> bool:
        """Return True when the payload's SHA3-512 digest matches *expected_hash*.

        This is an **integrity** check, not a signature: no key is involved, so
        anyone who can rewrite the payload can also rewrite the digest it is
        compared against. Use :meth:`verify_hmac` when you need to establish
        *who* produced the payload.
        """
        if not isinstance(expected_hash, str):
            return False
        computed_hash = hashlib.sha3_512(executable_payload).hexdigest()
        # Constant-time comparison to prevent timing attacks
        is_valid = _hmac.compare_digest(computed_hash, expected_hash)

        if not is_valid:
            log.critical("INTEGRITY CHECK FAILED: PID %d payload hash mismatch!", pid)
        else:
            log.info("Payload hash verified for PID %d.", pid)

        return is_valid

    def verify_hmac(
        self, pid: int, executable_payload: bytes, signature: str, key: bytes
    ) -> bool:
        """Verify an HMAC-SHA3-512 tag over *executable_payload*.

        Unlike :meth:`verify_hash`, this really does establish authenticity: an
        attacker who rewrites the payload cannot recompute the tag without the
        key. It is **symmetric** - sender and verifier hold the same secret -
        so it is not asymmetric code signing, and it is documented that way
        rather than called one.

        Args:
            pid: Process the payload belongs to (used for logging only).
            executable_payload: The bytes that were tagged.
            signature: Hex HMAC-SHA3-512 tag.
            key: Non-empty shared secret.

        Returns:
            True when the tag matches.

        Raises:
            ValueError: If *key* is empty or not bytes. A missing secret is a
                caller error, and returning False would hide it.
        """
        if not isinstance(key, (bytes, bytearray)) or not key:
            raise ValueError("verify_hmac requires a non-empty bytes key")
        if not isinstance(signature, str):
            return False
        expected = _hmac.new(bytes(key), executable_payload, hashlib.sha3_512).hexdigest()
        is_valid = _hmac.compare_digest(expected, signature)

        if not is_valid:
            log.critical("AUTHENTICITY CHECK FAILED: PID %d HMAC mismatch!", pid)
        else:
            log.info("HMAC verified for PID %d.", pid)

        return is_valid

    def verify_signature(self, pid: int, executable_payload: bytes, expected_hash: str) -> bool:
        """Deprecated alias of :meth:`verify_hash`. This is **not** signing.

        Kept so existing callers keep working. It performs the same keyless
        digest comparison, which proves nothing about who produced the payload;
        use :meth:`verify_hmac` for that.
        """
        warnings.warn(
            "SecuritySandbox.verify_signature() is a keyless hash comparison, "
            "not signature verification; use verify_hash() for integrity or "
            "verify_hmac() for authenticity.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.verify_hash(pid, executable_payload, expected_hash)
''')

sb = sb[:start] + NEW + sb[end:]

assert sb != original
assert "\n    def verify_hash" in sb
assert "\n    def verify_hmac" in sb
assert "Verifies the cryptographic signature" not in sb, "the lie must be gone"
assert "CODE SIGNING FAILED" not in sb
assert sb.count("\n    def verify_signature") == 1, "only the deprecated alias remains"
assert sb.count("\nimport hmac as _hmac\r\n") == 1
write(SB, sb)
print("sandbox.py: %d -> %d chars" % (len(original), len(sb)))

# ---------------------------------------------------------------------------
# 4. tests/test_security.py: point the two tests at the honest name
# ---------------------------------------------------------------------------
ts = read(TS)
ts_original = ts

old = "    def test_verify_signature(self):\r\n"
new = "    def test_verify_hash(self):\r\n"
assert ts.count(old) == 1, "test name anchor 1"
ts = ts.replace(old, new)

old = "    def test_verify_signature_bad_hash(self):\r\n"
new = "    def test_verify_hash_rejects_a_bad_digest(self):\r\n"
assert ts.count(old) == 1, "test name anchor 2"
ts = ts.replace(old, new)

old = "self.sandbox.verify_signature("
new = "self.sandbox.verify_hash("
assert ts.count(old) == 2, "two call sites"
ts = ts.replace(old, new)

assert ts != ts_original
assert "verify_signature" not in ts
write(TS, ts)
print("test_security.py: %d -> %d chars" % (len(ts_original), len(ts)))

# ---------------------------------------------------------------------------
# 5. verify
# ---------------------------------------------------------------------------
for path in (SB, TS):
    raw = open(path, "rb").read()
    lf, crlf_count = raw.count(b"\n"), raw.count(b"\r\n")
    assert lf == crlf_count, "%s has %d bare LF" % (path, lf - crlf_count)
    compile(raw, path, "exec")
    print("%s: %d lines, CRLF intact, compiles" % (path, crlf_count))

print("OK")
