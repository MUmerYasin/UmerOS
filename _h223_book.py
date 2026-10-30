"""H223 bookkeeping -- replace the truncated H223 checkpoint line."""
from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path(".workbuddy-ai/memory/remediation_progress.md")
lines = TARGET.read_text(encoding="utf-8").splitlines(keepends=True)

idx = None
for i, line in enumerate(lines):
    if line.startswith("- [ ] H223"):
        idx = i
        break

if idx is None:
    print("ABORT: H223 pending line not found")
    sys.exit(1)

NEW = (
    "- [x] H223 | BLUE | `quantum/quantum_sim.py:20` | **H7 Apache-2.0 header stray "
    "(2nd in quantum/)** - second docstring `License: GPL-3.0 (GNU General Public License "
    "Version 3)` stray inside the `quantum/` package (same as H215). | Replace with "
    "canonical GPL-3.0 header. **RESOLVED (session 210, DRIFT-CORRECTED -- the s102 "
    "resolution was non-canonical).** Drift-recon: the row's premise is **fully stale** -- "
    "there is no second stray header anywhere in `quantum/quantum_sim.py`; line 20 is the "
    "`TODAY:` section label inside the single module docstring, and `GNU General Public "
    "License Version 3` appears nowhere in the file. Session 102 had already canonicalized "
    "line 33 -- but it landed on the **short form** `License: GPL-3.0` with no parenthetical, "
    "whereas the repo-wide canonical form (pinned by `tests/test_etc_license_headers.py`, "
    "`tests/test_fs_baseline.py`, `tests/test_feedback_license.py`: `CANON = \"License: "
    "GPL-3.0 (GNU General Public License v3)\"`) includes it. A package scan showed "
    "`quantum_sim.py` was one of only two `quantum/` modules carrying the short form "
    "(the other, `crypto_pqc.py`, is **deliberately** pinned to it by "
    "`tests/test_quantum_security.py::TestCryptoPqcHeader::test_canonical_license_tag`, so it "
    "was left untouched), while `cli.py`, `qkd.py`, `qrng.py`, `cloud/auth.py` and "
    "`liboqs_integration.py` already carry the canonical line. Fix: `quantum_sim.py:33` "
    "`License: GPL-3.0` -> `License: GPL-3.0 (GNU General Public License v3)`. Nothing else "
    "changed -- the GPL comment header block (L1-12), the `Author:  Umer OS Project` trailer "
    "and the docstring body are untouched. Pinned by "
    "`tests/test_quantum_sim_header_h223.py` (16 passed): canonical line present, bare short "
    "form gone, no spelled-out `Version 3`, no British `Licence:`, Author trailer present, GPL "
    "comment header block present; **no stray duplicate** (exactly 1 `License:` line, exactly "
    "1 `Author:` line, line 20 is not a header, exactly 1 module docstring via AST); section 1 "
    "baseline (compiles, `from __future__ import annotations` is the first post-docstring "
    "statement, module imports and exposes `QuantumCircuitSimulator`); and package consistency "
    "(the other already-canonical quantum modules stay canonical, and `crypto_pqc.py` keeps its "
    "pinned short form). Next: **H224** -- 💭 `quantum/backend.py:291` `IBMBackend.__init__` "
    "exception text may leak token/URL.\n"
)

lines[idx] = NEW
TARGET.write_text("".join(lines), encoding="utf-8")
print(f"OK: replaced line {idx + 1} with the H223 resolved entry.")
