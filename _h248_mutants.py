"""H248 mutation harness.

Each mutant must (a) actually differ from the original and (b) be CAUGHT by
the named test.  A mutant that reconstructs the original byte-for-byte proves
nothing (the H240/H241 lesson).
"""
from __future__ import annotations

import hashlib
import io
import subprocess
import sys

SEC = r"security/security.py"
GUI = r"ui/umeros_gui.py"
PY = r"C:/Users/MC Raja Jang/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe"
CLS = "tests/test_behavioural_monitor_h248.py::"


def read(path: str) -> str:
    with io.open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def write(path: str, text: str) -> None:
    with io.open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def crlf(block: str) -> str:
    return block.replace("\r\n", "\n").replace("\n", "\r\n")


# (name, path, old, new, test node)
MUTANTS = [
    (
        "quarantine_does_not_revoke",
        SEC,
        crlf("            revoked, detail = self._revoke_capabilities(pid)\n"),
        crlf("            revoked, detail = set(), 'mutant: nothing revoked'\n"),
        "TestQuarantineIsReal::test_a_block_hit_revokes_the_process_capabilities",
    ),
    (
        "quarantine_not_sticky",
        SEC,
        crlf("            if pid in self._quarantined:\n                return False\n"),
        crlf("            if False:  # mutant: not sticky\n                return False\n"),
        "TestQuarantineIsReal::test_quarantine_is_sticky",
    ),
    (
        "release_does_not_restore",
        SEC,
        crlf("                self._sandbox.grant_permission(pid, capability)\n"),
        crlf("                pass  # mutant: capabilities not restored\n"),
        "TestRelease::test_release_restores_the_revoked_capabilities",
    ),
    (
        "game_rule_back_to_block",
        SEC,
        crlf('        ("game", "filesystem_write_system"): WARN,\n'),
        crlf('        ("game", "filesystem_write_system"): BLOCK,\n'),
        "TestFalsePositiveIsTuned::test_a_game_writing_system_files_is_not_a_block_rule",
    ),
    (
        "warn_ignores_threshold",
        SEC,
        crlf("            if count < self._strike_threshold:\n"),
        crlf("            if True:  # mutant: threshold ignored\n"),
        "TestFalsePositiveIsTuned::test_a_game_may_write_a_few_times_before_quarantine",
    ),
    (
        "strikes_never_decay",
        SEC,
        crlf("            if time.monotonic() - last > self._strike_window:\n"),
        crlf("            if False:  # mutant: strikes never decay\n"),
        "TestFalsePositiveIsTuned::test_strikes_decay_after_the_window",
    ),
    (
        "block_obeys_threshold",
        SEC,
        crlf("            if severity == self.BLOCK:\n"),
        crlf("            if False:  # mutant: block now needs strikes too\n"),
        "TestFalsePositiveIsTuned::test_an_impossible_combination_still_blocks_on_the_first_hit",
    ),
    (
        "no_sandbox_detail_lies",
        SEC,
        crlf('            return set(), "no sandbox attached - capabilities NOT revoked"\n'),
        crlf('            return set(), "revoked 0 capability/ies"\n'),
        "TestQuarantineIsReal::test_without_a_sandbox_the_record_says_nothing_was_revoked",
    ),
    (
        "class_docstring_claims_ai",
        SEC,
        crlf('    """Heuristic, rule-based behavioural monitor - **not** a trained model.\n'),
        crlf('    """AI-driven anomaly detection for real-time threat mitigation.\n'),
        "TestTheLabelIsHonest::test_the_class_docstring_does_not_claim_a_model",
    ),
    (
        "gui_claim_restored",
        GUI,
        '"• AIBehavioralMonitor — heuristic anomaly rules (no model)"',
        '"• AIBehavioralMonitor — anomaly detection"',
        "TestTheLabelIsHonest::test_the_gui_no_longer_sells_it_as_anomaly_detection",
    ),
]


def run_test(node: str) -> bool:
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
    baseline = {SEC: read(SEC), GUI: read(GUI)}
    baseline_hash = {p: hashlib.sha256(t.encode()).hexdigest() for p, t in baseline.items()}
    for path, digest in baseline_hash.items():
        print("baseline %-22s %s" % (path, digest[:16]))

    print("\n-- baseline (unmutated) --")
    failures = 0
    for name, _path, _old, _new, node in MUTANTS:
        if not run_test(node):
            print("  !! %-32s already failing before mutation" % node)
            failures += 1

    print("\n-- mutants --")
    for name, path, old, new, node in MUTANTS:
        text = baseline[path]
        count = text.count(old)
        if count != 1:
            print("  !! %-32s anchor matched %d times" % (name, count))
            failures += 1
            continue
        mutant = text.replace(old, new)
        if mutant == baseline[path]:
            print("  !! %-32s NO-OP mutant (byte-identical)" % name)
            failures += 1
            continue
        write(path, mutant)
        try:
            still_passes = run_test(node)
        finally:
            write(path, baseline[path])
            assert read(path) == baseline[path], "restore failed for %s" % path
        verdict = "MISSED  <-- BAD" if still_passes else "caught"
        print("  %-32s %s  (%s)" % (name, verdict, node.split("::")[-1]))
        if still_passes:
            failures += 1

    for path, digest in baseline_hash.items():
        assert hashlib.sha256(read(path).encode()).hexdigest() == digest, "not restored: %s" % path
    print("\nfiles restored, hashes match")
    print("FAILURES: %d" % failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
