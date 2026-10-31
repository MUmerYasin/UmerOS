"""H250 mutation harness.

Each mutant must (a) actually differ from the original and (b) be CAUGHT by the
named test.  The restore is hash-verified, and every `write()` takes its path
(H249 lesson: a missing argument there left a mutant in the tree).
"""
from __future__ import annotations

import hashlib
import io
import pathlib
import subprocess
import sys

FW = r"security/firewall.py"
NOTICES = r"THIRD_PARTY_NOTICES.md"
PY = r"C:/Users/MC Raja Jang/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe"
CLS = "tests/test_firewall_h250.py::"

# (name, path, old, new, test node)
MUTANTS = [
    (
        "sticky_precheck_removed",
        FW,
        "            if src_ip in self.blocked_ips:\n                return self.DROP\n",
        "            if False:  # mutant: no sticky pre-check\n                return self.DROP\n",
        "TestDropIsSticky::test_a_blocked_source_is_dropped_on_other_ports_too",
    ),
    (
        # Faithful to the original defect, and it takes BOTH edits: the fix is
        # belt-and-braces (sticky pre-check *and* a clean heuristic condition),
        # so removing either one alone still drops the packet.
        "fail_open_restored",
        FW,
        (
            "            if src_ip in self.blocked_ips:\n                return self.DROP\n",
            "            if dst_port in self.heuristic_ports:\n",
        ),
        (
            "            if False:  # mutant: no sticky pre-check\n                return self.DROP\n",
            "            if dst_port in self.heuristic_ports and src_ip not in self.blocked_ips:\n",
        ),
        "TestDropIsSticky::test_every_packet_of_a_denied_flow_is_dropped",
    ),
    (
        "rules_never_consulted",
        FW,
        "            for ip, port, action in self.rules:\n",
        "            for ip, port, action in ():  # mutant: rules ignored\n",
        "TestRulesAreConsulted::test_an_allow_rule_overrides_the_heuristic",
    ),
    (
        "drop_rule_never_drops",
        FW,
        "                if action == self.DROP:\n",
        "                if False:  # mutant: DROP rules inert\n",
        "TestRulesAreConsulted::test_a_drop_rule_works_on_a_port_the_heuristic_ignores",
    ),
    (
        "add_rule_accepts_anything",
        FW,
        "        if not isinstance(ip, str) or not ip:\n",
        "        if False:  # mutant: no ip validation\n",
        "TestRuleValidation::test_a_malformed_rule_is_refused",
    ),
    (
        "action_not_normalised",
        FW,
        "        stored: Rule = (ip, port, action.upper())\n",
        "        stored: Rule = (ip, port, action)\n",
        "TestRuleValidation::test_a_valid_rule_is_stored_in_normalised_form",
    ),
    (
        "unblock_does_nothing",
        FW,
        "            self.blocked_ips.discard(src_ip)\n",
        "            pass  # mutant: block not cleared\n",
        "TestDropIsSticky::test_unblock_lifts_the_block",
    ),
    (
        "heuristic_ignores_config",
        FW,
        "            if dst_port in self.heuristic_ports:\n",
        "            if dst_port == 22:  # mutant: config ignored\n",
        "TestHeuristic::test_the_heuristic_ports_are_configurable",
    ),
    (
        "clear_rules_does_nothing",
        FW,
        "            self.rules.clear()\n",
        "            pass  # mutant: rules kept\n",
        "TestRulesAreConsulted::test_clear_rules_empties_the_table",
    ),
    (
        "class_docstring_claims_ai",
        FW,
        '    """Heuristic packet deny-list. Not AI, and not a firewall.\n',
        '    """AI-driven firewall.\n',
        "TestLabelsMatchTheCode::test_the_class_does_not_call_itself_ai",
    ),
    (
        "print_reintroduced",
        FW,
        '                    log.warning("Deny rule dropped %s -> port %s.", src_ip, dst_port)\n',
        '                    print(f"dropped {src_ip} -> {dst_port}")\n',
        "TestLabelsMatchTheCode::test_the_module_does_not_print",
    ),
    (
        "notices_section_removed",
        NOTICES,
        "**No DeepSeek source is vendored.**",
        "**Provenance.**",
        "TestLabelsMatchTheCode::test_the_provenance_question_is_answered_in_the_notices_file",
    ),
]


def read(path: str) -> str:
    with io.open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def write(path: str, text: str) -> None:
    with io.open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def convert(block: str, eol: str) -> str:
    return block.replace("\r\n", "\n").replace("\n", eol)


def run_test(node: str) -> bool:
    # A stale .pyc can make pytest run the *baseline* code against a mutant,
    # producing a false "MISSED". Drop the cache and forbid writing a new one.
    for cache in (pathlib.Path("security/__pycache__"), pathlib.Path("tests/__pycache__")):
        if cache.is_dir():
            for entry in cache.glob("*.pyc"):
                entry.unlink()
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
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )
    return proc.returncode == 0


def main() -> int:
    paths = sorted({m[1] for m in MUTANTS})
    baseline = {p: read(p) for p in paths}
    eol = {p: ("\r\n" if "\r\n" in baseline[p] else "\n") for p in paths}
    baseline_hash = {p: hashlib.sha256(t.encode()).hexdigest() for p, t in baseline.items()}
    for path in paths:
        print("baseline %-24s %s" % (path, baseline_hash[path][:16]))

    print("\n-- baseline (unmutated) --")
    failures = 0
    for name, _path, _old, _new, node in MUTANTS:
        if not run_test(node):
            print("  !! %-32s already failing before mutation" % node)
            failures += 1

    print("\n-- mutants --")
    for name, path, old_raw, new_raw, node in MUTANTS:
        # A mutant may carry one replacement or a list of them.
        if isinstance(old_raw, (list, tuple)):
            pairs = list(zip(old_raw, new_raw))
        else:
            pairs = [(old_raw, new_raw)]
        text = baseline[path]
        ok = True
        for old_s, new_s in pairs:
            old = convert(old_s, eol[path])
            new = convert(new_s, eol[path])
            count = text.count(old)
            if count != 1:
                print("  !! %-32s anchor matched %d times" % (name, count))
                failures += 1
                ok = False
                break
            text = text.replace(old, new)
        if not ok:
            continue
        mutant = text
        if mutant == baseline[path]:
            print("  !! %-32s NO-OP mutant" % name)
            failures += 1
            continue
        write(path, mutant)
        try:
            still_passes = run_test(node)
        finally:
            write(path, baseline[path])
            if read(path) != baseline[path]:
                print("  !! RESTORE FAILED for %s" % path)
                return 2
        verdict = "MISSED  <-- BAD" if still_passes else "caught"
        print("  %-32s %s  (%s)" % (name, verdict, node.split("::")[-1]))
        if still_passes:
            failures += 1

    for path in paths:
        digest = hashlib.sha256(read(path).encode()).hexdigest()
        assert digest == baseline_hash[path], "not restored: %s" % path
    print("\nfiles restored, hashes match")
    print("FAILURES: %d" % failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
