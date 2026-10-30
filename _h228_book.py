"""H228 bookkeeping -- replace the truncated H228 checkpoint line."""
from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path(".workbuddy-ai/memory/remediation_progress.md")
lines = TARGET.read_text(encoding="utf-8").splitlines(keepends=True)

idx = None
for i, line in enumerate(lines):
    if line.startswith("- [ ] H228"):
        idx = i
        break

if idx is None:
    print("ABORT: H228 pending line not found")
    sys.exit(1)

NEW = (
    "- [x] H228 | YELLOW | `root/mail.py:220` `RootMailForwarder.ensure` | **Home dir created "
    "with default umask perms (~0755), not 0700** - `self.home.mkdir(parents=True, "
    "exist_ok=True)` then only `.forward` is `chmod 0o600`; if `ensure()` runs on a missing home "
    "(e.g. before `RootHomeManager.ensure()`), the `/root` parent is left "
    "world-readable/executable. | Create the home with `mode=0o700` (`os.makedirs(path, "
    "mode=0o700)` then re-`chmod` after, since umask strips it) or require the caller to have "
    "bootstrapped it with `RootHomeManager.ensure()`. **RESOLVED (session 214, REAL FIX + "
    "DRIFT-CORRECTED).** Drift-recon: premise **TRUE**; the `mkdir` was at **line 220**, not "
    "`:207`. `Path.mkdir()` with no `mode=` creates the directory at `0o777 & ~umask` -- 0755 "
    "under the usual umask -- so the admin home really was world-readable *and* "
    "world-executable. Two adjacent details surfaced: (a) the `.forward` chmod block was dead "
    "code dressed up as portability -- `os_chmod = getattr(self.path, \"chmod\", None)` is "
    "always a bound method, so the `import os` branch never ran, and the `import stat` above it "
    "was unused; (b) `.forward` was created under the default umask and chmod-ed afterwards, "
    "leaving a window in which a file naming an off-host delivery address was world-readable. "
    "Fix: new `HOME_MODE = 0o700` / `FORWARD_MODE = 0o600` module constants; `ensure()` now "
    "calls `_ensure_home()` -- `mkdir(parents=True, exist_ok=True, mode=HOME_MODE)` followed by "
    "an explicit `os.chmod(self.home, HOME_MODE)`, because `mkdir`'s mode is filtered through "
    "the umask, and an **existing** directory is tightened too (matching the sibling "
    "`RootHomeManager.ensure`, which chmods unconditionally) -- and `_write_forward()` -- "
    "`os.open(path, O_WRONLY|O_CREAT|O_TRUNC, FORWARD_MODE)` so the file never exists at a wider "
    "mode, re-chmod-ed for the pre-existing-file case since `os.open`'s mode only applies on "
    "creation. `import os` promoted to module level (it was imported ad hoc inside the "
    "never-taken branch); the unused `import stat` and the `getattr` dance deleted. A chmod "
    "failure is logged, not raised (a filesystem without POSIX permissions is still usable and "
    "`RootSafetyAuditor` reports the mode). Pinned by `tests/test_root_mail_home_mode_h228.py` "
    "(13 passed, 4 POSIX-only skips on Windows): source invariants -- `HOME_MODE == 0o700`, "
    "`FORWARD_MODE == 0o600`, **every** `mkdir` in the module carries an explicit `mode=` and "
    "that argument is exactly `HOME_MODE` (AST), `os.open` is given `FORWARD_MODE` as its third "
    "argument (AST), `os.chmod(self.home, HOME_MODE)` present, the `getattr` dance gone, `os` "
    "imported at module level; behaviour -- a missing home is created and ends at 0700, an "
    "existing 0755 home is tightened to 0700, `.forward` ends at 0600, a pre-existing 0644 "
    "`.forward` is re-tightened on rewrite, content is exactly `# test\\nadmin@example.com\\n`, "
    "rewrite replaces the previous entry, an empty address still raises `ValueError`, and "
    "`root` still trips the loop detector. `tests/test_root.py` + H226 + the new file 148 "
    "passed / 15 skipped. Next: **H229** -- 💭 `root/passwd.py:136` `PasswdManager.write` "
    "writes the `.bak` copy with default umask perms (world-readable copy of `/etc/passwd`).\n"
)

lines[idx] = NEW
TARGET.write_text("".join(lines), encoding="utf-8")
print(f"OK: replaced line {idx + 1} with the H228 resolved entry.")
