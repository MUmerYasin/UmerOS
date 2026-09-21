# UmerOS Remediation — Session 74 (H60)

**Expert:** CodeReviewExpert (Kim)
**Date:** 2026-09-21 (continuation of the `dev/` sweep; s70–73 = compatibility/ + core/ + dev/ H59)
**Severity:** 🟡 YELLOW (kept — genuine zero-trust privileged-op gap)

---

## Summary

`dev/core.py` `DeviceManager.sync_to_filesystem()` materializes **real** device special files
(`os.mknod`/`os.mkfifo`/`os.symlink_to`/`os.mkdir`) into the VFS with **no capability/privilege
gate** — a zero-trust gap on the same "privileged op / no gate" axis as H27/H28/H46/H51. H60 adds a
fail-closed `CAP_SYS_ADMIN` gate and a CWE-22 dev-root confinement so sync can never write onto a real
host `/dev` unless authorized.

## Drift-recon (premise check)

- CONFIRMED: the method had zero capability checks.
- The method is currently **latent** — `grep` found 0 callers and 0 tests. So the fix is
  forward-looking hardening, not a hot patch.
- `self.dev_root` (default `/dev`) was **unused** by the method — nodes carry absolute `node.path`
  strings. The standard's "create device nodes only into the UmerOS virtual `/dev`, never a host
  `/dev`" half is therefore enforced via a new **resolved-path dev-root confinement** rather than
  relying on `dev_root` alone.

## Changes

`dev/core.py` — `DeviceManager.sync_to_filesystem()`:
1. **Fail-closed capability gate** — lazy import `from core.capability_gate import gate, CAP_SYS_ADMIN`
   (no import cycle; matches `etc/critical_files.py` / `installer.py` / `initrd/linuxrc.py` style) then
   `gate.require(CAP_SYS_ADMIN)` at method entry. Behaviour:
   - Trust source wired → enforced against `CapabilityManager` (raises `PermissionError` if lacking).
   - No trust source + `strict` → raises `PermissionError` (fail-closed).
   - No trust source + non-strict (default) → permissive, logs a warning (preserves existing
     standalone/CLI/test workflows).
2. **CWE-22 dev-root confinement** — each `node.path` is `Path.resolve()`d and proved a descendant of
   `self.dev_root` via `relative_to`; a node that escapes the UmerOS virtual `/dev` namespace is
   skipped (logged `REFUSED: ... escapes dev root ... (CWE-22); not materialized.`) and never
   materialized.
3. Docstring expanded to state the zero-trust boundary; `# [FIX H60]` tags on the gate + confinement.

## Verification

- `py_compile` clean on `dev/core.py`.
- New `tests/test_dev_manager.py` (**3 cases, all pass**):
  - `test_sync_to_filesystem_gated_fail_closed` — strict + no manager → `PermissionError` raised.
  - `test_sync_to_filesystem_permissive_when_unwired` — default posture → no gate error, returns `int`.
  - `test_sync_to_filesystem_refuses_escaping_node` — escape node → `REFUSED` logged, path never
    created, returns `0`.
- The latent Linux-only `os.mknod` call is intentionally unchanged (UmerOS targets Linux); the
  permissive test uses a `DIRECTORY` node so it stays green on the Windows sandbox.

## Bookkeeping (6 surfaces)

1. ✅ Checkpoint `remediation_progress.md` — H60 box `- [ ]` → `- [x]` + RESOLVED note.
2. ✅ NEXT pointer → **H61** (`DeviceManager` singleton registry lock).
3. ✅ Standard §9 H60 🟡 row — RESOLVED note appended.
4. ✅ MEMORY.md — pointer → session 74; `dev/` folder map `🟢 H59,H60; 🟡 H61`.
5. ✅ Daily log `2026-09-21.md` — Session 74 entry + Next pointer → H61.
6. ✅ This per-session overview.

## Next (H61 — Session 75)

`dev/core.py` `DeviceManager` singleton registry (`self._nodes` / `_by_major` / `_by_name` /
`_symlinks`) has **no `threading.Lock`** — concurrent registration/hotplug could race (💭, low risk in
single-threaded boot). Add a `threading.Lock` guarding the registry mutations (💭-appropriate: small,
defensive). After `dev/`, the YELLOW sweep continues into `drivers/`, `etc/`, and beyond.

## Standing user action (H1)

User must rotate the leaked OpenRouter key + purge git history — not handled by the loop.
