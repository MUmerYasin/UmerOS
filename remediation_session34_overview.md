# Remediation Session 34 — Y5 (host subprocess audit) + carried-over verification

**Date:** 2026-09-04
**Expert:** CodeReviewExpert (Kim)
**Scope:** YELLOW hotspot H5; verification of carried-over Session-24 RED items (H3, H147).

---

## What changed

### H5 — `subprocess` to host with arg lists (YELLOW, standard §9)
Guidance: *"Keep list-form, no `shell=True`; sandbox on Windows host."*

1. **`bin/boolean_ops.py` — `EnvCommand.execute`** (host-exec path)
   - The `env` command performs arbitrary host command execution via
     `subprocess.run(real_args, env=env)`. This is now gated behind
     `CAP_SYS_ADMIN` through `core.capability_gate`.
   - **Critical detail:** `gate.require(CAP_SYS_ADMIN)` is placed **before** the
     `try/except` block. `PermissionError` is a subclass of `OSError`, so placing
     it inside the try would have been silently swallowed by the existing
     `except OSError` handler (returning 126) — defeating the fail-closed intent.
   - Behaviour: permissive when no `CapabilityManager` is wired (standalone CLI /
     unit tests still work), fail-closed under `set_strict(True)` or a wired
     manager. `# [FIX H5]`.

2. **`etc/issue_motd.py` — host-info probes**
   - `who` / `uptime -p` / `last` calls consolidated into a single
     `_run_host_readonly(cmd)` helper backed by an explicit
     `_HOST_INFO_ALLOWLIST` (`who`, `uptime`, `last`).
   - The helper refuses any command whose `cmd[0]` is not allowlisted and returns
     `None` on a Windows host (POSIX tools unavailable) — satisfying the
     "sandbox on Windows host" requirement. Graceful fallback strings preserved.
   - `# [FIX H5]`.

### Carried-over Session-24 verification (was written during the 429 outage, unverified)
- **H147** (`lib/ssl_libs.py`): cert-expiry enforcement is real — `is_expired` /
  `days_until_expiry` / `_inspect_cert` / `check_trust` / `_check_is_ca` all carry
  `# [FIX H147]`.
- **H3** (`lib/security.py`): `PASSWORD = "password"` is the PAM module-**type**
  label, not a hardcoded credential — clarified with `# [FIX H3]`.
- Both confirmed by `tests/test_ssl_security.py` → **7/7 OK**.

---

## Tests added / run
- **New:** `tests/test_host_subprocess_security.py` (6 cases)
  - `TestEnvCommandHostExecGated`: fail-closed under strict mode; gate consulted
    when unwired (permissive, no real exec of a missing binary).
  - `TestIssueMotdHostAllowlist`: allowlist accepts `who`/`uptime`/`last`; refuses
    `rm -rf /` and `sh -c`; empty refused; Windows-host guard.
- `tests/test_bin.py` → **243 OK (43 skipped)** — no regression from the `env` gate.
- `tests/test_ssl_security.py` → **7/7 OK** (H147/H3 carry-over verified).

---

## Bookkeeping (4 surfaces)
- ✅ Checkpoint `remediation_progress.md`: H5 `- [ ]` → `- [x]`; NEXT pointer → H6/H55.
- ✅ Standard §9: H5 🟡 → 🟢 with `[FIXED (session 34)]` note.
- ✅ `MEMORY.md`: consolidated; folder map RED→🟢 for lib/media/mnt/opt/packages/
  quantum/security + H4/H5/H42/H72/H227/H233; added Sessions 24–34 status.
- ✅ Daily log `2026-09-04.md` written.

**All RED blockers (H1–H307) are confirmed CLOSED.** YELLOW sweep is in progress.

---

## Next
**H6 / H55** — converge `core/command.py` base `Command.execute` signature
(`execute(*args) -> Any` vs `execute(args=None) -> int`) so every `bin/*` subclass
agrees on the contract. Say **"continues"**.
