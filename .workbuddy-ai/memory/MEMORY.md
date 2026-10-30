# UmerOS — Long-term Project Memory

## Conventions
- Backend = Python only; GPL-3.0 canonical (`Licence`→`License`, `Version 3`→`v3`).
- Source authority: `Skills/Context File/umer_os_skills.json` > `MainTask/prompt/*.md` > `MainTask/Raw Data/*.docx` > repo + LICENSE/setup.py.
- **Drift-recon first** — verify the row's premise against live repo state before editing; most premises are stale/overstated. Trust `Read` over `Grep`.
- Never batch multiple `Edit` calls on one file; use assert-first `pathlib` appliers (`text.count(old) == 1`).
- Bookkeeping per study (5 surfaces): checkpoint box + RESOLVED + NEXT pointer, standard §9 note, this file's pointer, daily `YYYY-MM-DD.md`, delete scratch scripts.

## Loop mechanics
- Severity source of truth: standard §9 rows (🔴/🟡/💭). **🔴 RED loop COMPLETE** (s112, 39/39, `MainTask/Raw Data/RED Loop Prompt.md`); 8 real fixes there: H184, H194, H245, H246, H265/H266, H267, H268.
- Checkpoint `.workbuddy-ai/memory/remediation_progress.md` (307 items; flip `- [ ]`→`- [x]`, append RESOLVED, **never regenerate**). Per-folder H-number map lives there + standard §9, not here.
- **Files that revert externally:** `RED Loop Prompt.md` (loses checklist boxes) and standard §9 (a 🟢-removal was undone, 736→673→973 lines). Write standard §9 + MEMORY **first**; treat the checklist as rebuildable.
- **An external process re-saves sources and strips cosmetic `[FIX Hxxx]` tags.** Rule: source-invariant tests pin *code facts* (gate calls, method names), never the tag. Do not re-add tags.
- H1 (user action): rotate the leaked OpenRouter key + purge git history.

## Test runner
- `"C:/Users/MC Raja Jang/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe" -m pytest tests/ legal/ opt/ sources/ srv/ tmp/ --junitxml=… -q` (venv path has a space — quote it).
- **`mkdir -p /f/umeros_tmp` FIRST**, then `TMP=F:/umeros_tmp TEMP=F:/umeros_tmp`. A TMP inside the project → 15 false failures (`legal/licenses.py` skips dot-prefixed path components; `mnt/fstab.py` whitespace-splits, so the space in `F:\Pension Person Details` corrupts offsets). Use `--junitxml` — basetemp cleanup trips the safe-delete guard.
- If a full run collapses to **1 node**, check `import requests` first (`quantum/providers/ibm_provider.py`; missing → collection error aborts the run).
- Baseline: ~5660 testcase nodes / 0 errors / 83 skipped.
- Guards: `core/path_guard.py` (`safe_child`/`safe_join`), `core/capability_gate.py` (`gate.require`). ~735 Python modules; `Old Linux Code/` (~93k) out of scope.
- `tests/test_ai*.py` collect fine (old "broken" note stale). `home` package-shadow: load `home_backup.py` by path under a unique module name.

## Status
- **Pointer: `sbin/` in progress — H232 ✅, H233 ✅, H234 ✅, next H235.** H234 (💭 mount/filesystem hardening): new `sbin/path_policy.py` (`normalise`/`require_under`/`validate_source`/`require_loop_device`/`harden_mount_options`), wired into 6 commands; `HARDEN_PAIRS` asserted equal to `mnt.mount_ops._HARDEN_PAIRS` rather than imported. `tests/test_sbin_path_policy_h234.py` (77).
  - **Drift note:** the row's `_SUPERBLOCKS` is in `maintenance.py`, and `filesystem.py` has **no** in-memory state at all; the `nosuid,nodev,noexec` strings in `mount.py` were only seed data, never enforced.
  - **Lessons:** a gate on a façade is not a gate on the classes behind it — look for a second entry point (H233: 7 duplicated `SbinCommand` bases × 45 commands bypassed `SbinManager.execute`; fixed with `__init_subclass__ = install_guard`). When adding `gate.require()` to something called in a loop, check for warning spam (63 identical PERMISSIVE lines from one `_selftest`); call it only when `gate.enforcing`. Heredocs mangle `\r\n` at line ends into `/r/n` — **always** use the Write tool for applier scripts, never `cat > file << EOF`.
  - H226 ✅ 9 `root/*.py` + README (row's "Apache-2.0/`Licence`" framing stale — real defect was spelled-out `Version 3`). H228 ✅ home 0700 + `.forward` 0600 via `os.open`. H229 ✅ `.bak` 0600; **real bug: `os.write` is text-mode on Windows → corrupted CRLF backups; fixed with `O_BINARY` in `passwd._write_backup` and `mail._write_forward`**. H230 ✅ `ensure` refuses symlinked path before chmod. H231 ✅ `validate_name` + `_dotfile_path` containment (row missed `ensure_private_file`, the 2nd write primitive).
- `quantum/` COMPLETE (H152, H215–H225). H225 added `quantum/tls.py` — one strict TLS policy (`CERT_REQUIRED` + `check_hostname` + TLS1.2 floor + optional `UMEROS_TLS_CAFILE`, fail-closed) used by all **22** provider REST call sites.
- Done: `build cloud compatibility core dev drivers etc feedback fs home initrd installer kernel legal lib liboqs media mnt network opt packages proc quantum root`.
- Remaining: `sbin` H232–235, `scripts` H236–239, `sdk` H240–243, `security` H244–258, `sources` H259–264, `srv` H265–277, `tmp` H278–287, `tools` H288–295, `ui` H90, `usr` H296–302, `var` H303–307.
- ⚠ H62 regression: `drivers/` has 0/75 `[TODAY]` labels (boot 23, bin 44, kernel 6, core 1, etc 81 still fine). Re-apply on request.

## Known-unrelated failures (do NOT re-investigate)
- 5 × `tests/test_legal_pii_h137` (external re-save put PII into `legal/creator_accounts.example.json`; flip-flops between runs), 1 × `tests/test_lib_pam_h150` (docstring marker lost; absent since s214), 1 × `tests/test_media_license_h160` (external `media/network/` package added post-completion; absent since s212).
- **External additions keep landing mid-session** and go stale against pinned counts. Precedent (s200, reused s218): if the new module is *scanner-compliant*, bump the pinned count and note the timestamp — don't "fix" the folder. Seen: `media/network/` (s206), `network/softbus/softbus_manager.py` @ 2026-10-30 15:18 (s218, count 9→10 in `test_network_license_h181.py`).
- Order-dependent flakes: `test_compatibility.py` (`test_selftest_passes`; the `setx` failure appeared s208, gone s209), `test_opt_selftest_h192.py::test_package_selftests_run_their_children`.
