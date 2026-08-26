# UmerOS — Long-term Project Memory

## Standing conventions (CodeReviewExpert / Kim)
- Review-standard-first: after every study, bump `MainTask/Raw Data/Code Review Standards and Process.md` (§1/§4/§7/§9/§11).
- Authoritative sources: `Skills/Context File/umer_os_skills.json` > `MainTask/prompt/*.md` > `MainTask/Raw Data/*.docx` > repo + LICENSE/setup.py.

## Decided
- H7 → GPL-3.0 canonical (sweep Apache-2.0 strays to GPLv3).
- H11 → Flutter (Dart) frontend canonical; backend = Python only; `ui/*.py` retired (H25); UI follows HCI Nielsen-10 (§4.8).

## Resumable remediation loop
- Goal: fix all H1–H307; tests in `tests/`; `# [FIX Hxxx]` comments; resumable via checkpoint.
- Checkpoint: `.workbuddy-ai/memory/remediation_progress.md` (307 items). Maintain by Edit (flip `- [ ]`→`- [x]`), never regenerate.
- Test runner: pytest in venv `C:/Users/MC Raja Jang/.workbuddy-ai/binaries/python/envs/default`. Eg `"<venv>/Scripts/python" -m pytest tests/test_var.py -q`.
- Shared CWE-22 guard: `core/path_guard.py` (`safe_child`, `safe_join`, `PathTraversalError`).
- Shared zero-trust guard: `core/capability_gate.py` (`gate` singleton + `require(cap)`) — bridge to `kernel.capability_manager.CapabilityManager`; fail-closed when wired, permissive-with-warning standalone; `set_strict` to deny.
- Project facts: ~735 Python modules; tests/ split unittest/pytest, NO CI; `security_scan.yml` only workflow; `Old Linux Code/` (~93k) reference-only (excluded from scope).
- Pre-existing broken test to ignore: `tests/test_ai.py` (collection error — `ai.providers` missing `AIConfigManager`); `home` package-shadowing collision (`bin/home.py`/`root/home.py`) — load `home_backup.py` by file path under a unique name in tests.

## Remediation DONE (session clusters)
- Session 1: var/ H303,H305,H306,H307.
- Session 2: path-traversal H185,H186,H194,H195,H265,H266,H282 (+ unblocked harness).
- Session 3: fail-open + dummy-crypto H129,H146,H111,H152,H154,H196,H197; srv/* relative-import (H271 smell); cryptography/numpy in venv.
- Session 5/6 (cap-gate, 8/8): H227,H233,H267,H273,H281,H283,H296,H304 behind `core/capability_gate.py`; fixed undefined `ManPageStatus` in `usr/man_page.py`; gated `GamesDataManager.add_game_data`.
- Session 7 (collection errors, 6/6): quantum `get_gate` KeyError + gate aliases + `inverse_qft_circuit`/`grover_circuit`; `test_dc_v2.py` hardpath; `sources`/`sbin` relative-import + drop `sys.path` self-injection. Full suite: 1742 collected, 0 errors.
- Session 8: reconciled quantum tests (rewrite to lib, 140 passing) + bin/proc 5 genuine lib bugs.
- Session 9 (H7 mini-sweep): opt/config.py, opt/var.py, opt/package.py, srv/backup.py, packages/umer_pkg.py, tmp/tmpfs.py → GPL-3.0.
- Session 10 (mount-path cap-gate, 2/2): H156 media + H166 mnt → `CAP_FS_ADMIN`.
- Session 11 (fail-open zero-trust, 2): H17 SecureBoot fail-closed + H51 ZeroTrustContainer.execute_binary gated. 8 tests.
- Session 12 (proc/srv priv-write cap-gate, 5/5): H205,H206,H207,H208 (`/proc` writes) + H268 (`srv/hierarchy.delete_service_tree`) → `CAP_FS_ADMIN`/`CAP_SYS_ADMIN`. 11 tests.
- Session 18 (home tar-restore): H83 `home/home_backup.py` `restore_backup` fail-closed (`CAP_HOME_ADMIN`, `filter='data'`, member pre-scan, non-destructive snapshot-restore, checksum verify). 9 tests. Full suite 1720 passed / 54 skipped (excl. test_ai.py).
- Session 19 (etc/ priv-write cap-gate): H73 — `sudoers.py`/`critical_files.py`/`passwd_group.py` gated behind `CAP_FS_ADMIN`; reject blanket `NOPASSWD` (`user==ALL` or `command==ALL`); cross-platform host-`/etc` guard; removed hardcoded `umer ALL=(ALL) NOPASSWD: ALL`. Incidental BOM strip in `etc/pam_config.py`. 12 tests (`tests/test_etc_sudoers.py`). Full suite 1743 passed / 54 skipped / 0 failures / 0 errors (excl. test_ai.py).
- Session 20 (installer/ priv-write + fail-open + data-loss cluster): H98 (dead `install.py` stub deleted; `__init__.py` re-exports real `installer.py`); H99 (fail-open `display_waiver` removed with stub; `show_eula` already fail-closed); H100 (`consent_override` EULA bypass now requires `CAP_INSTALL`); H101 (`rollback()` guarded by cross-platform `_is_safe_install_root` — refuses `/` + system dirs, requires `CAP_FS_ADMIN`); H102 (privileged install pipeline + writers gated `CAP_FS_ADMIN`); H103 (`copy_os_files` uses `_safe_join` to reject escapes + skips dotfiles). 17 new security tests + 29 existing green; full suite pending.
- Session 21 (initrd/ eval + traversal + boot-op cap-gate): H2/H91 (`initrd/ai_helper.py` `_load_history` `eval()` → `ast.literal_eval`, non-literal lines dropped fail-closed); H93 (`initrd/builder.py` `_unpack_to_dir` CPIO traversal → `core.path_guard.safe_join`, escapes skipped fail-closed); H92 (`initrd/linuxrc.py` `_drop_to_root` `os.seteuid(0)` gated behind `CAP_SYS_ADMIN`, fail-closed when a manager wired / strict — `pivot_root`/`mount`/`chroot_into` are simulated VFS ops, no real privilege). 8 new security tests in `tests/test_initrd.py` (TestAIHelperHistorySafety/TestBuilderCpioTraversal/TestDropToRootCapGate); initrd module 86 passed, 0 failures.
- Session 22 (kernel/ dummy-manager + dummy-crypto + decorative-sandbox cluster): H110 (`umer_kernel.py` `__init__` now wires the REAL `MemoryManager`/`IPCBus`/`CapabilityManager` instead of no-op `type(...)` placeholders; SYSTEM_PID=0 omnipotent, init granted a minimal cap set — the correct wiring was commented out at L1622-1624); H111 (`CryptoEngine` confirmed real: HMAC-SHA256 sign/verify fail-closed + AES-256-GCM encrypt/decrypt — table bumped to 🟢, code was fixed session 3); H112 (`SecuritySandbox.register_process` now enforces `fs_root` containment via `core.path_guard.safe_join`, fail-closed, raises `SecurityViolation` on escape — no longer a print-only decorative gate). 16 new security tests in `tests/test_kernel_security.py` (TestKernelManagersWired/TestCryptoEngineReal/TestSecuritySandboxEnforcement); full suite 1447 passed / 0 failures / 0 errors (excl. pre-existing `test_ai.py` collection error).

## Folder scope map — hotspots (🟢 fixed / 🟡 yellow / 💭 nit / 🔴 red; blurbs in standard §9)
- boot/ 🟢 H27,H28,H29; 🟡 H30–H34
- bin/ 🟢 H37; 🟡 H6,H35,H36,H38–H40
- build/ 🔴 H42; 🟡 H41,H43–H45
- cloud/ 🟢 H46,H154; 🟡 H47–H49
- compatibility/ 🟡 H50,H52–H54 (H51 🟢)
- core/ 🟡 H55,H56,H57
- dev/ 🟡 H59,H60,H61
- drivers/ 🟢 H64; 🟡 H62,H63,H66,H69; 💭 H65
- etc/ 🟢 H73; 🟡 H70,H71,H72
- examples/ 💭 H74,H75
- feedback/ 🟡 H76–H79
- fs/ 🟡 H80,H81,H82
- home/ 🟢 H83; 🟡 H84–H88
- HostFiles/ 🟡 H89,H90
- initrd/ 🟢 H2,H91,H92,H93; 🟡 H94,H95,H97
- installer/ 🟢 H98,H99,H100,H101,H102,H103; 🟡 H104–H109
- kernel/ 🟢 H110,H111,H112; 🟡 H113–H127
- legal/ 🔴 H128,H130,H131,H135 (H129 🟢); 🟡 H132,H136–H141; 💭 H137
- lib/ 🔴 H3,H147 (H146 🟢); 🟡 H148,H149,H150
- liboqs/ 🟡 H151; 💭 H155
- media/ 🔴 H157 (H156 🟢); 🟡 H158–H160; 💭 H161–H165
- mnt/ 🔴 H167,H168 (H166 🟢); 🟡 H169–H171,H176; 💭 H172–H175
- network/ 🟢 H177,H178; 🟡 H179,H180; 💭 H181,H182
- opt/ 🔴 H184,H187 (H185,H186 🟢); 🟡 H188–H193,H200; 💭 H183
- packages/ 🔴 H198 (H194,H195,H196,H197 🟢); 🟡 H199,H201,H204
- proc/ 🟢 H205,H206,H207,H208; 🟡 H209,H210,H211; 💭 H212–H214
- quantum/ 🔴 H215,H216,H217,H221 (H152 🟢); 🟡 H218,H219,H220; 💭 H222–H225
- root/ 🟡 H226,H228 (H227 🟢); 💭 H229,H230,H231
- sbin/ 🟡 H232; 💭 H234,H235 (H233 🟢)
- scripts/ 🟡 H236,H237; 💭 H238,H239
- sdk/ 🟡 H240,H241; 💭 H242,H243
- security/ 🔴 H244,H245,H246 (H17 🟢); 🟡 H247–H254; 💭 H255–H258
- sources/ 🟡 H259,H260,H261,H262; 💭 H263,H264
- srv/ 🟢 H265,H266,H267,H268,H271,H273; 🟡 H269,H270,H272; 💭 H274–H277
- tmp/ 🟡 H278,H279,H280 (H281,H282,H283 🟢); 💭 H284–H287
- tools/ 🟡 H288–H292; 💭 H293–H295
- usr/ 🟡 H297,H298,H299,H300 (H296 🟢); 💭 H301,H302
- var/ 🟢 H303,H304,H305,H306,H307
