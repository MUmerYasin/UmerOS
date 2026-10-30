"""H229 bookkeeping -- replace the truncated H229 checkpoint line."""
from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path(".workbuddy-ai/memory/remediation_progress.md")
lines = TARGET.read_text(encoding="utf-8").splitlines(keepends=True)

idx = None
for i, line in enumerate(lines):
    if line.startswith("- [ ] H229"):
        idx = i
        break

if idx is None:
    print("ABORT: H229 pending line not found")
    sys.exit(1)

NEW = (
    "- [x] H229 | BLUE | `root/passwd.py:141-142` `PasswdManager.write` | **`.bak` copy uses "
    "default umask perms** - `bak.write_bytes(self.path.read_bytes())` writes the backup with "
    "the process umask (potentially world-readable), exposing `/etc/passwd` contents "
    "(names/shells/GECOS; not hashes, since shadow). | Write the backup with `mode=0o600` (and "
    "place it under a restricted dir). **RESOLVED (session 215, REAL FIX + DRIFT-CORRECTED).** "
    "Drift-recon: premise **TRUE**; the two lines were at **141-142**, not `:136`. "
    "`Path.write_bytes` creates the file at `0o666 & ~umask` -- 0644 under the usual umask -- so "
    "`/etc/passwd.bak` sat world-readable beside a file that is world-readable by design. Fix: "
    "(1) new `BACKUP_MODE = 0o600` / `PASSWD_MODE = 0o644` module constants; (2) `write()` now "
    "delegates to a new `_write_backup()`, which opens the copy with "
    "`os.open(..., BACKUP_MODE)` and re-chmods it (`os.open`'s mode argument only applies on "
    "creation, so a pre-existing wide `.bak` is tightened too); (3) the backup stays beside its "
    "source -- a restore is then a rename and the conventional `/etc/passwd.bak` path keeps it "
    "auditable -- so the file mode, not the directory, is the control (the row's \"restricted "
    "dir\" alternative was rejected deliberately: relocating the backup would break the "
    "conventional restore path for no additional confidentiality); (4) the silent "
    "`except OSError: pass` around the passwd chmod now logs at WARNING, because a silently "
    "failed chmod on an account database is worth knowing about; (5) the hardcoded `0o644` "
    "became `PASSWD_MODE`. **A real bug was found and fixed while writing the tests:** "
    "`os.write` runs descriptors in **text mode on Windows**, so the byte-for-byte copy rewrote "
    "every `\\n` as `\\r\\n` and turned a CRLF source into `\\r\\r\\n` -- the backup was corrupt. "
    "Fixed with `getattr(os, \"O_BINARY\", 0)` in the open flags (no-op on POSIX), and the same "
    "fix was applied to `root/mail.py::_write_forward` from H228 for the same reason. Pinned by "
    "`tests/test_root_passwd_backup_h229.py` (13 passed, 4 POSIX-only skips on Windows): source "
    "invariants -- `BACKUP_MODE == 0o600`, `PASSWD_MODE == 0o644`, `_write_backup` present, **no** "
    "`write_bytes` call remains (AST, so the explanatory docstring is allowed), `os.open` is "
    "given `BACKUP_MODE` as its third argument (AST), `self.path.chmod(PASSWD_MODE)` used and no "
    "hardcoded `chmod(0o644)`, the chmod-failure warning present, `gate.require(CAP_SYS_ADMIN)` "
    "still there (H227 must not regress), `O_BINARY` present; behaviour -- the backup is created "
    "at the sibling `<path>.bak`, it is **byte-identical** to the source (this is the test that "
    "caught the Windows newline corruption), it ends at 0600, a pre-existing 0644 `.bak` is "
    "tightened and refreshed, `/etc/passwd` itself ends at 0644, no backup is written when the "
    "file is missing, `backup=False` skips it, and the read/write roundtrip still works. "
    "`test_root.py` + H226 + H228 + H229 + `test_cap_gate.py` 196 passed / 18 skipped. Next: "
    "**H230** -- 💭 `root/home.py:384-393` `RootHomeManager.ensure` chmods through a symlink and "
    "the CLI accepts an arbitrary path.\n"
)

lines[idx] = NEW
TARGET.write_text("".join(lines), encoding="utf-8")
print(f"OK: replaced line {idx + 1} with the H229 resolved entry.")
