# Cap-gate Remediation Cluster — CLOSED (Session 5/6, 2026-08-22)

## What was done
Finished wiring the **cap-gate** remediation family (H227, H233, H267, H273, H281, H283, H296, H304)
behind the shared zero-trust bridge `core/capability_gate.py` (`gate` + `gate.require(cap)`).

- **H296 — `/usr` privileged FS**: gated every privileged `os.symlink` / `os.unlink` / `open('w')` /
  `shutil.rmtree` entry point in `usr/sendmail_manager.py`, `usr/misc_data_manager.py`,
  `usr/bsd_compat_manager.py`, `usr/games_data_manager.py`, `usr/xml_manager.py` — each now
  `gate.require(CAP_FS_ADMIN)` as its first statement (`# [FIX H296]`).
- **H304 — `/var` managers**: gated privileged FHS mutations in `var/directory_manager.py` (10 methods),
  `var/spool_manager.py` (write/clear mailbox, set cron user, cleanup), `var/log_manager.py`
  (write/rotate/compress) — `gate.require(CAP_FS_ADMIN)` (`# [FIX H304]`).

Each gated site stays **permissive-with-warning when no `CapabilityManager` is wired** (CLI/tests keep
working) and becomes **fail-closed when the running kernel wires one**; `set_strict(True)` denies with
no trust source.

## Two genuine bugs fixed while landing H296
1. `usr/man_page.py` referenced an **undefined `ManPageStatus` enum** → `NameError` crashed
   `import usr` and blocked the integration tests. Added the missing `IntEnum` (MISSING/PARSED).
2. `GamesDataManager.add_game_data` was **never gated** (only `remove_game_data` was). Added the
   `# [FIX H296]` gate.

## Tests
Extended `tests/test_cap_gate.py`:
- gate-level allow/deny for `CAP_FS_ADMIN`; strict-mode deny;
- parametrised **per-module fail-closed integration** across all 8 modules (usr managers built via
  `__new__` to avoid their real `/usr` `mkdir` side effect; var managers built with a temp `var_path`);
- a positive **allow-when-held integration** (var spool actually writes under a temp dir).

`test_cap_gate.py` + `test_var.py` = **32 passed**. Full `pytest tests/` run shows **0 regressions**
from this work.

## Pre-existing blockers discovered (NOT caused by this work)
The full `pytest tests/` collection is currently broken by **6 pre-existing errors** in *other* test
modules — the next cluster to fix:
- `tests/quantum/test_circuit.py`, `test_circuit_library.py`, `test_gates.py` (quantum test collect failures)
- `tests/test_dc_v2.py` → `FileNotFoundError: UmerOS/quantum/dynamic_circuits_v2.py` (missing source)
- `tests/test_sbin.py` → `ImportError: cannot import 'IfconfigCommand' from 'network'`
- `tests/test_sources.py` → `ImportError: cannot import 'SourcesManager' from 'manager'` (H261 fragile import)

## Bookkeeping
- `remediation_progress.md`: H296 + H304 flipped to `[x]`; NEXT updated.
- `MEMORY.md`: usr/ (H296 FIXED) + var/ (H304 FIXED) folder-map annotations; DONE/NEXT updated.
- `2026-08-22.md`: appended a cap-gate closure session section.

## NEXT
Fix the 6 collection errors so the whole suite collects → then the full **YELLOW/BLUE sweep**; the
outstanding **H7 licence sweep** (`Licence: Apache 2.0`→`License: GPL-3.0`) in opt/config.py,
opt/var.py, opt/package.py, srv/backup.py, packages/umer_pkg.py, tmp/tmpfs.py (note `srv/backup.py`
still carries `Licence: Apache 2.0` at line 16).
