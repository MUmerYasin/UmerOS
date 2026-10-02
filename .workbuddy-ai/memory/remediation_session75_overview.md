# UmerOS Remediation — Session 75 (H61)

**Expert:** CodeReviewExpert (Kim)
**Date:** 2026-10-02 (continuation of the `dev/` sweep; s70–74 = compatibility/ + core/ + dev/ H59,H60)
**Severity:** 💭 BLUE (nit — low risk in single-threaded boot; lock added defensively)

---

## Summary

`dev/core.py` `DeviceManager` is a process-wide singleton whose registry dicts
(`_nodes` / `_by_major` / `_by_name` / `_symlinks`) were mutated **without a `threading.Lock`**,
and `get_instance()` did an unguarded singleton assignment. H61 adds a registry lock (cheap,
defensive) so concurrent registration/hotplug cannot race/corrupt the registry.

## Drift-recon (premise + severity)

- CONFIRMED: no lock on the registry; `get_instance` unguarded.
- Severity correction: H61 is 💭 (BLUE) in both the standard §9 row and the checkpoint box — the
  folder-map/pointer had wrongly carried it as 🟡. Corrected to 💭 (same drift class as H54/H57).
  Also corrected the parallel `drivers/ H62` 🟡->💭 drift in the folder map while here.

## Changes (`dev/core.py`, `# [FIX H61]`)

1. `import threading` added.
2. `self._lock = threading.Lock()` in `__init__` — guards the registry dicts.
3. `create_node` / `remove_node` — all dict mutations wrapped in `with self._lock:`; the
   duplicate-existence check was moved *inside* the lock to remove a TOCTOU window.
4. `sync_to_filesystem` — snapshots `nodes = list(self._nodes.values())` under the lock, then
   iterates the copy; the lock is **never held across I/O** (`os.mknod` / `os.mkdir`).
5. `get_instance` — **double-checked locking** on a new class-level `cls._instance_lock`
   (guards the singleton assignment race).

## Verification

- `py_compile` clean on `dev/core.py`.
- Extended `tests/test_dev_manager.py` with 3 registry cases (**all 6 tests pass**):
  - `test_registry_lock_present` — `_lock` (instance) + `_instance_lock` (class) are `threading.Lock`.
  - `test_get_instance_is_singleton` — repeated `get_instance()` returns the same object.
  - `test_create_remove_node_functional_under_lock` — CRUD still correct under the lock (create,
    duplicate-refused, remove, gone, remove-again-refused).

## Bookkeeping (6 surfaces)

1. ✅ Checkpoint `remediation_progress.md` — H61 box `- [ ]` → `- [x]` + RESOLVED note.
2. ✅ NEXT pointer → **H62** (`drivers/` tier labels, 💭).
3. ✅ Standard §9 H61 💭 row — RESOLVED note appended.
4. ✅ MEMORY.md — pointer → session 75; folder map `dev/ 🟢 H59,H60; 💭 H61` (also `drivers/ H62`
   🟡→💭 drift corrected).
5. ✅ Daily log `2026-10-02.md` — Session 75 entry + Next pointer → H62.
6. ✅ This per-session overview.

## Status

`dev/` sweep COMPLETE: H59 🟢 (DeviceNode world-writable default), H60 🟢 (`sync_to_filesystem` cap
gate + CWE-22 dev-root confinement), H61 💭 (registry lock). Next YELLOW/💭 sweep: **`drivers/`**
starting at **H62** (0/75 modules carry a tier label, 💭), then H63 (license headers, 🟡), H65
(ctypes dead import, 💭), H66 (capability gating, 🟡), H69 (`from __future__`, 🟡), etc.

## Standing user action (H1)

User must rotate the leaked OpenRouter key + purge git history — not handled by the loop.
