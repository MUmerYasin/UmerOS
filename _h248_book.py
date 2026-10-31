"""H248 bookkeeping: flip the checkpoint box + append RESOLVED to both surfaces."""
from __future__ import annotations

import io

CK = r".workbuddy-ai/memory/remediation_progress.md"
STD = r"MainTask/Raw Data/Code Review Standards and Process.md"

NOTE = (
    "\u2705 RESOLVED (session 231): **Premise TRUE on all three counts - and the third "
    "hid a logic bug, not just a tuning issue.** (a) \"AI-driven\" was false: the class "
    "shipped a 4-entry static deny-table and nothing else; the only place a model is "
    "mentioned at all is the commented-out dead code, which itself admits "
    "\"heuristic rule-based AI simulation\". (b) `_trigger_quarantine` really did only "
    "call `log.critical` - and the dead code even carries the unimplemented hook "
    "(`# Hook: ... this would call sandbox.revoke_all_permissions(pid)`). (c) The rules "
    "flagged ordinary behaviour. **Two defects the row did not name:** (i) an "
    "already-quarantined PID answered **True** (\"safe\") on its next innocuous action, "
    "so the quarantine was not even sticky - one call later the monitor had forgotten "
    "it; (ii) `self.lock` was constructed and never used. **Remedy:** the monitor now "
    "relabels honestly (class docstring, module docstring and the GUI string all say "
    "heuristic rules / no model) and quarantine became a real, observable control: "
    "`_trigger_quarantine` records the PID and **revokes every capability the process "
    "holds in the attached `SecuritySandbox`**, so `check_permission` starts denying "
    "(measured: `{'read','write','network'}` -> `set()`, `check_permission(7,'write')` "
    "True -> False). The stored record states the outcome - `revoked N capability/ies`, "
    "or `no sandbox attached - capabilities NOT revoked`, or `PID not registered in "
    "sandbox` - so `quarantine_reason()` cannot imply an isolation that never happened. "
    "Quarantine is sticky, per-PID, idempotent, and reversible via `release()`, which "
    "restores the exact revoked set additively; `quarantined_pids`, `is_quarantined` and "
    "`quarantine_reason` make it inspectable. **False positives tuned with severity "
    "tiers:** `BLOCK` pairs (`text_editor`+`network_access`, `calculator`+"
    "`kernel_module_load`, `media_player`+`process_injection`) are impossible for the "
    "program class and quarantine on the first hit regardless of threshold, while the "
    "row's named false positive `(\"game\",\"filesystem_write_system\")` is downgraded to "
    "`WARN`, needing `strike_threshold` (3) hits inside `strike_window` (300 s). Strikes "
    "deliberately do **not** reset on a clean action - otherwise an attacker interleaves "
    "innocuous calls to stay under the threshold - but they *do* decay after the window, "
    "so a legitimate long session cannot accumulate its way into quarantine. Rules are "
    "extensible via `add_rule` (severity validated) and replaceable via `rules=`; "
    "`suspicious_patterns` survives as a read-only view of the BLOCK pairs. `RLock` "
    "replaces the unused `Lock` because `analyze_action` calls `_trigger_quarantine` "
    "while holding it. Pinned by `tests/test_behavioural_monitor_h248.py` (**28 "
    "passed**): honest labelling (class docstring, module docstring, GUI string, "
    "live-region scan), capability revocation measured through `check_permission`, the "
    "self-describing record in all three sandbox states, stickiness, per-PID scoping, "
    "sorted `quarantined_pids`, idempotency, release-and-restore, the WARN tier (allowed "
    "twice, quarantined on the third), BLOCK unaffected by `strike_threshold=99`, clean "
    "actions not resetting strikes, decay after the window, 20 clean iterations never "
    "flagging, rule add/promote/demote/replace, case-insensitive names, and "
    "resource-as-capability-name. Non-vacuity confirmed by **10 mutations, all caught** "
    "- revocation removed, stickiness removed, release not restoring, the game rule "
    "restored to `BLOCK`, threshold ignored, decay disabled, `BLOCK` made to obey the "
    "threshold, the no-sandbox detail falsified, the AI docstring restored, the GUI "
    "string reverted; each mutant asserted to differ from the original and both files "
    "restored with matching sha256. One defect found in the *test*, not the source: "
    "`inspect.getsource(AIBehavioralMonitor)` runs to **EOF** here because everything "
    "after the class is commented out and `tokenize` skips comment tokens, so no DEDENT "
    "ever arrives - it silently picked up the dead code's \"AI-driven\" string; replaced "
    "with an explicit live-region slice. Regression: **6153 testcases, 0 errors, 95 "
    "skipped, 6 failed** - the 5 known `test_legal_pii_h137` plus the pre-existing "
    "external `tests/test_layer_reachability.py` drift (`examples/__init__.py`), neither "
    "attributable to this row; the +28 delta is exactly the new file. Next: **H249** - "
    "\U0001F7E1 `security/sandbox.py:128` `verify_signature` computes "
    "`sha3_512(payload)` and compares it to an expected string: integrity-with-shared-"
    "secret, not a signature. Say **'continues'** for H249."
)


def read(path: str) -> str:
    with io.open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def write(path: str, text: str) -> None:
    with io.open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


# ---------------------------------------------------------------------------
# 1. standard §9
# ---------------------------------------------------------------------------
std = read(STD)
std_lines = std.split("\n")
assert "\r" not in std

row_idx = [i for i, l in enumerate(std_lines) if l.startswith("| H248 | \U0001F7E1 |")]
assert len(row_idx) == 1, "H248 row not unique in §9"
ri = row_idx[0]
row_text = std_lines[ri]
assert row_text.rstrip().endswith("|")

if "RESOLVED (session 231)" in std_lines[ri + 1]:
    print("§9: already applied, skipping")
else:
    assert std_lines[ri + 1].strip() == "", "placeholder line not blank"
    std_lines[ri + 1] = "  " + NOTE
    std_new = "\n".join(std_lines)
    assert std_new != std
    assert std_new.count("RESOLVED (session 231)") == 1
    write(STD, std_new)
    print("§9: RESOLVED note inserted at line %d" % (ri + 2))

# ---------------------------------------------------------------------------
# 2. checkpoint
# ---------------------------------------------------------------------------
ck = read(CK)
ck_lines = ck.split("\n")
assert "\r" not in ck

trunc = [i for i, l in enumerate(ck_lines) if l.startswith("- [ ] H248 | YELLOW |")]
assert len(trunc) == 1, "checkpoint H248 row not unique"
ti = trunc[0]

full = "- [x] " + row_text[2:].replace("| \U0001F7E1 |", "| YELLOW |", 1)
assert full.startswith("- [x] H248 | YELLOW | `security/security.py")
assert "Replace with a real model or relabel heuristic" in full, "remedy column lost"
ck_lines[ti] = full + "   " + NOTE

ck_new = "\n".join(ck_lines)
assert ck_new != ck
assert ck_lines[ti].startswith("- [x] H248 | YELLOW | `security/security.py")
assert ck_new.count("- [x] H248") == 1
assert "- [ ] H248" not in ck_new
write(CK, ck_new)
print("checkpoint: row %d ticked (%d -> %d bytes)" % (ti + 1, len(ck), len(ck_new)))
