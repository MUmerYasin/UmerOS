"""H249 mutation harness.

Each mutant must (a) actually differ from the original and (b) be CAUGHT by
the named test.
"""
from __future__ import annotations

import hashlib
import io
import subprocess
import sys

SB = r"security/sandbox.py"
PY = r"C:/Users/MC Raja Jang/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe"
CLS = "tests/test_sandbox_verify_hash_h249.py::"


def read(path: str) -> str:
    with io.open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def write(path: str, text: str) -> None:
    with io.open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def crlf(block: str) -> str:
    return block.replace("\r\n", "\n").replace("\n", "\r\n")


MUTANTS = [
    (
        "hash_over_the_pid_not_the_payload",
        crlf("        computed_hash = hashlib.sha3_512(executable_payload).hexdigest()\n"),
        crlf("        computed_hash = hashlib.sha3_512(str(pid).encode()).hexdigest()\n"),
        "TestVerifyHash::test_the_digest_is_over_the_payload_not_the_pid",
    ),
    (
        "verify_hash_always_true",
        crlf("        is_valid = _hmac.compare_digest(computed_hash, expected_hash)\n"),
        crlf("        is_valid = True  # mutant\n"),
        "TestVerifyHash::test_rejects_a_wrong_digest",
    ),
    (
        "verify_hash_no_type_guard",
        crlf("        if not isinstance(expected_hash, str):\n            return False\n"),
        crlf("        if False:  # mutant: no type guard\n            return False\n"),
        "TestVerifyHash::test_rejects_a_non_string_digest_without_raising",
    ),
    (
        "hmac_ignores_the_key",
        crlf("        expected = _hmac.new(bytes(key), executable_payload, hashlib.sha3_512).hexdigest()\n"),
        crlf('        expected = _hmac.new(b"", executable_payload, hashlib.sha3_512).hexdigest()\n'),
        "TestVerifyHmac::test_accepts_a_matching_tag",
    ),
    (
        "hmac_accepts_an_empty_key",
        crlf('        if not isinstance(key, (bytes, bytearray)) or not key:\n            raise ValueError("verify_hmac requires a non-empty bytes key")\n'),
        crlf('        if False:  # mutant: no key validation\n            raise ValueError("verify_hmac requires a non-empty bytes key")\n'),
        "TestVerifyHmac::test_an_empty_key_is_a_caller_error",
    ),
    (
        "alias_warns_the_wrong_category",
        crlf("            DeprecationWarning,\n"),
        crlf("            UserWarning,\n"),
        "TestDeprecatedAlias::test_the_alias_warns_that_it_is_not_signing",
    ),
    (
        "alias_does_not_delegate",
        crlf("        return self.verify_hash(pid, executable_payload, expected_hash)\n"),
        crlf("        return True  # mutant: no delegation\n"),
        "TestDeprecatedAlias::test_the_alias_still_returns_the_same_answer",
    ),
    (
        "code_signing_log_claim_restored",
        crlf('            log.critical("INTEGRITY CHECK FAILED: PID %d payload hash mismatch!", pid)\n'),
        crlf('            log.critical("CODE SIGNING FAILED: PID %d hash mismatch!", pid)\n'),
        "TestLabelsMatchTheCode::test_the_live_class_no_longer_claims_code_signing",
    ),
    (
        "timing_unsafe_hmac_compare",
        crlf("        is_valid = _hmac.compare_digest(expected, signature)\n"),
        crlf("        is_valid = expected == signature  # mutant: timing-unsafe\n"),
        "TestLabelsMatchTheCode::test_both_comparisons_are_constant_time",
    ),
    (
        "module_docstring_reverted",
        crlf("  * ``verify_hash`` — SHA3-512 payload hash equality (integrity; no key,\n"),
        crlf("  * ``verify_signature`` — SHA3-512 payload hash equality.\n"),
        "TestLabelsMatchTheCode::test_the_module_docstring_names_both_operations_honestly",
    ),
]


def run_test(node: str) -> bool:
    proc = subprocess.run(
        [PY, "-m", "pytest", CLS + node, "-q", "--no-header", "-p", "no:cacheprovider"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=r"F:/Pension Person Details/UmerOS",
        env={
            "TMP": "F:/umeros_tmp",
            "TEMP": "F:/umeros_tmp",
            "SYSTEMROOT": r"C:\Windows",
            "PATH": r"C:\Windows\System32",
        },
    )
    return proc.returncode == 0


def main() -> int:
    baseline = read(SB)
    baseline_hash = hashlib.sha256(baseline.encode()).hexdigest()
    print("baseline %s (%d chars)" % (baseline_hash[:16], len(baseline)))

    print("\n-- baseline (unmutated) --")
    failures = 0
    for name, _old, _new, node in MUTANTS:
        if not run_test(node):
            print("  !! %-34s already failing before mutation" % node)
            failures += 1

    print("\n-- mutants --")
    for name, old, new, node in MUTANTS:
        count = baseline.count(old)
        if count != 1:
            print("  !! %-34s anchor matched %d times" % (name, count))
            failures += 1
            continue
        mutant = baseline.replace(old, new)
        if mutant == baseline:
            print("  !! %-34s NO-OP mutant" % name)
            failures += 1
            continue
        write(mutant)
        try:
            still_passes = run_test(node)
        finally:
            write(baseline)
            assert read(SB) == baseline, "restore failed"
        verdict = "MISSED  <-- BAD" if still_passes else "caught"
        print("  %-34s %s  (%s)" % (name, verdict, node.split("::")[-1]))
        if still_passes:
            failures += 1

    assert hashlib.sha256(read(SB).encode()).hexdigest() == baseline_hash, "not restored"
    print("\nfile restored, hash matches")
    print("FAILURES: %d" % failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
