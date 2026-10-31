"""H247 mutation harness.

Each mutant must (a) actually differ from the original and (b) be CAUGHT by
the named test.  A mutant that reconstructs the original byte-for-byte is a
no-op and proves nothing (the H240/H241 lesson).
"""
from __future__ import annotations

import hashlib
import io
import subprocess
import sys

SEC = r"security/security.py"
PY = r"C:/Users/MC Raja Jang/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe"
TESTFILE = "tests/test_ipc_replay_h247.py"
CLS = "tests/test_ipc_replay_h247.py::"


def read() -> str:
    with io.open(SEC, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def write(text: str) -> None:
    with io.open(SEC, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


VERIFY_BODY = (
    "        if not isinstance(signature, str):\r\n"
    "            return False\r\n"
    "        expected = self._mac(msg)\r\n"
    "        # Constant-time compare FIRST: never remember an unauthenticated MAC.\r\n"
    "        if not _hmac.compare_digest(expected, signature):\r\n"
    "            return False\r\n"
    "        return self._remember(signature)\r\n"
)

MUTANTS = [
    (
        "no_replay_check",
        "        return self._remember(signature)\r\n",
        "        return True\r\n",
        "TestReplayIsRefused::test_a_replayed_message_is_refused",
    ),
    (
        "remember_before_compare",
        VERIFY_BODY,
        "        if not isinstance(signature, str):\r\n"
        "            return False\r\n"
        "        self._remember(signature)\r\n"
        "        expected = self._mac(msg)\r\n"
        "        return _hmac.compare_digest(expected, signature)\r\n",
        "TestReplayIsRefused::test_forged_macs_cannot_evict_genuine_ones_from_the_cache",
    ),
    (
        "rotate_keeps_cache",
        "            self._seen.clear()\r\n",
        "            pass  # mutant: cache kept\r\n",
        "TestReplayCacheLifecycle::test_rotate_key_forgets_everything",
    ),
    (
        "no_future_timestamp_check",
        "        if age > float(ttl) or age < -float(ttl):\r\n",
        "        if age > float(ttl):\r\n",
        "TestEnvelope::test_an_envelope_stamped_in_the_future_is_refused",
    ),
    (
        "no_stale_check",
        "        if age > float(ttl) or age < -float(ttl):\r\n",
        "        if age < -float(ttl):\r\n",
        "TestEnvelope::test_a_stale_envelope_is_refused",
    ),
    (
        "envelope_replay_check_removed",
        "        return self._remember(nonce)\r\n",
        "        return True\r\n",
        "TestEnvelope::test_a_replayed_envelope_is_refused",
    ),
    (
        "docstring_sha3_512_restored",
        '    """Signs and verifies IPC messages with HMAC-SHA3-256 and blocks replays.',
        '    """Signs and verifies IPC messages with HMAC-SHA3-512 and blocks replays.',
        "TestClaimsMatchTheCode::test_the_class_docstring_names_the_digest_actually_used",
    ),
    (
        "no_memory_cap",
        "        if len(self._seen) >= self._max_entries:\r\n",
        "        if False:  # mutant: no cap\r\n",
        "TestReplayCacheLifecycle::test_memory_stays_bounded_under_a_flood",
    ),
    (
        "entries_never_expire",
        "        for key in [k for k, seen in self._seen.items() if seen <= cutoff]:\r\n"
        "            del self._seen[key]\r\n",
        "        pass  # mutant: entries never expire\r\n",
        "TestReplayCacheLifecycle::test_an_expired_entry_is_forgotten",
    ),
]


def run_test(node: str) -> bool:
    """Return True when the test passes."""
    proc = subprocess.run(
        [PY, "-m", "pytest", CLS + node, "-q", "--no-header", "-p", "no:cacheprovider"],
        capture_output=True,
        text=True,
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
    baseline = read()
    baseline_hash = hashlib.sha256(baseline.encode()).hexdigest()
    print("baseline sha256 %s (%d bytes)" % (baseline_hash[:16], len(baseline)))

    # The named tests must pass on the unmutated file.
    print("\n-- baseline (unmutated) --")
    failures = 0
    for name, _old, _new, node in MUTANTS:
        ok = run_test(node)
        if not ok:
            print("  !! %-32s test already failing before mutation" % node)
            failures += 1

    print("\n-- mutants --")
    for name, old, new, node in MUTANTS:
        text = baseline
        count = text.count(old)
        if count != 1:
            print("  !! %-32s anchor matched %d times" % (name, count))
            failures += 1
            continue
        mutant = text.replace(old, new)
        if mutant == baseline:
            print("  !! %-32s NO-OP mutant (byte-identical)" % name)
            failures += 1
            continue
        write(mutant)
        try:
            still_passes = run_test(node)
        finally:
            write(baseline)
            assert read() == baseline, "restore failed!"
        verdict = "MISSED  <-- BAD" if still_passes else "caught"
        print("  %-32s %s  (%s)" % (name, verdict, node.split("::")[-1]))
        if still_passes:
            failures += 1

    final_hash = hashlib.sha256(read().encode()).hexdigest()
    assert final_hash == baseline_hash, "file not restored"
    print("\nfile restored, sha256 %s" % final_hash[:16])
    print("FAILURES: %d" % failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
