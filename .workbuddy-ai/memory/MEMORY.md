# UmerOS — Long-term Project Memory

## Standing conventions (CodeReviewExpert / Kim)
- Review-standard-first: after every study, bump `MainTask/Raw Data/Code Review Standards and Process.md` (§1/§4/§7/§9/§11).
- Authoritative sources: `Skills/Context File/umer_os_skills.json` > `MainTask/prompt/*.md` > `MainTask/Raw Data/*.docx` > repo + LICENSE/setup.py.

## Decided
- H7 → GPL-3.0 canonical (sweep Apache-2.0 strays to GPLv3).
- H11 → Flutter (Dart) frontend canonical; backend = Python only; `ui/*.py` retired (H25); UI follows HCI Nielsen-10 (§4.8).

## Resumable remediation loop
- Goal: fix all H1–H307; tests in `tests/`; `# [FIX Hxxx]` comments; resumable via checkpoint.
- Checkpoint: `.workbuddy-ai/memory/remediation_progress.md` (307 items: 66 RED / 152 YELLOW / 89 BLUE). GENERATED ONCE; maintain by Edit, never regenerate.
- Test runner: pytest in venv `C:/Users/MC Raja Jang/.workbuddy-ai/binaries/python/envs/default`. Eg `"<venv>/Scripts/python" -m pytest tests/test_var.py -q`.
- Shared CWE-22 guard: `core/path_guard.py` (`safe_child`, `safe_join`, `PathTraversalError`).
- Shared zero-trust guard: `core/capability_gate.py` (`gate` singleton + `require(cap)`) — bridge to `kernel.capability_manager.CapabilityManager`; fail-closed when wired, permissive-with-warning standalone; `set_strict` to deny.
- DONE: var/ (H303,H305,H306,H307 — session 1); path-traversal cluster (H185,H186,H194,H195,H265,H266,H282 — session 2) + unblocked harness; **fail-open + dummy-crypto cluster** (H129,H146,H111,H152,H154,H196,H197 — session 3) + srv/* relative-import repair (H271 smell) + `cryptography`/`numpy` in venv; 59 remediation tests green. **cap-gate cluster CLOSED (session 5/6, 8/8):** H227,H233,H267,H273,H281,H283,H296,H304 all wired behind `core/capability_gate.py` (`gate.require(cap)`, fail-closed-when-wired / permissive-when-unwired); also fixed undefined `ManPageStatus` enum in `usr/man_page.py` (import-time NameError) and gated the missed `GamesDataManager.add_game_data`. 32 tests green in test_cap_gate.py + test_var.py. **collection-error cluster CLOSED (session 7, 6/6):** quantum `get_gate` KeyError + gate aliases + `inverse_qft_circuit`/`grover_circuit` (H261); `test_dc_v2.py` hardpath fix (H262); `sources`/`sbin` relative-import + remove `sys.path` self-injection (H261); `test_sbin.py`/`test_sources.py` collect. Full `pytest tests/` now **1742 collected, 0 errors, 0 regressions**. **mount-path cap-gate cluster CLOSED (session 10, 2/2):** H156 (media — gated at `media/mount_ops.py` mount/unmount/remount chokepoint, transitively covers `auto_mount._handle_hotplug` + `udisks2.UDisks2Client.mount`) and H166 (mnt — `MountManager.mount`/`umount`/`remount`, `MountPointManager.create`/`remove`, `Fstab.write_file`) both wired behind `core/capability_gate.py` requiring `CAP_FS_ADMIN`. 9 new integration tests in `tests/test_cap_gate.py` (+133 passed with test_media.py).
- NEXT: **ALL PRE-EXISTING FAILING TESTS ARE NOW GREEN.** Full `pytest tests/` = **1688 passed, 54 skipped, 0 failures, 0 errors**. Two clusters reconciled: **quantum** (user-chosen "rewrite tests to lib", 140 passing — session on H303 follow-up) and **bin/proc** (session 8: 5 genuine lib bugs fixed — `BracketTestCommand` exit-2, `DateCommand` argv parsing, `TarCommand`/`GunzipCommand` return codes, `CpioCommand` copy-out, `procfs._resolve` bare `proc`, `filesystems.get` bare names, `LoadAvgTracker` seed + test↔lib drift + POSIX-only skips). Next: **full YELLOW/BLUE sweep** (H1–H307 non-test gaps, zero-trust gating on un-gated privileged paths, remaining H7 folder strays H183/H200/H269/H278, baseline smells). **H7 mini-sweep DONE (2026-08-22, session 9):** the 6 directed files (opt/config.py, opt/var.py, opt/package.py, srv/backup.py, packages/umer_pkg.py, tmp/tmpfs.py) normalized to canonical `License: GPL-3.0`. **Mount-path cap-gate cluster CLOSED (2026-08-24, session 10):** H156 (media) + H166 (mnt) wired behind `core/capability_gate.py` (`CAP_FS_ADMIN`); 9 new integration tests; full suite green (1688 passed / 54 skipped). **Fail-open zero-trust gate cluster CLOSED (2026-08-24, session 11):** H17 (`security/security.py` `SecureBoot.verify_image`/`verify_bytes` — default now fail-closed strict mode; unknown components denied in BOTH strict and dev modes) and H51 (`compatibility/container.py` `ZeroTrustContainer.execute_binary` — capability `query("HARDWARE")` now gates execution, returns False on denial instead of running unconditionally). 8 new tests (3 H17 in test_security.py + 5 H51 in new tests/test_zero_trust_container.py); full suite green (1703 passed / 54 skipped, 0 failures, 0 errors).
- Project facts: ~735 Python modules; tests/ split unittest/pytest, NO CI; `security_scan.yml` only workflow; `Old Linux Code/` (~93k) reference-only (excluded from scope).

## Folder scope map — hotspots by folder (full detail in standard §9)
- boot/ 🔴 H27/H28/H29; 🟡 H30–H34
- bin/ 🔴 H37; 🟡 H6/H35/H36/H38–H40
- build/ 🔴 H42; 🟡 H41/H43–H45
- cloud/ 🔴 H46/H154(FIXED); 🟡 H47–H49
- compatibility/ 🟡 H50/H52–H54  (H51 FIXED — zero-trust exec capability-gated)
- core/ 🟡 H55/H56/H57
- dev/ 🟡 H59/H60/H61
- drivers/ 🔴 H64; 🟡 H62/H63/H66/H69
- etc/ 🔴 H73; 🟡 H70/H71/H72
- examples/ 💭 H74/H75
- feedback/ 🟡 H76–H79 (broken pkg)
- fs/ 🟡 H80/H81/H82
- home/ 🔴 H83; 🟡 H84–H88
- HostFiles/ 🟡 H89/H90
- initrd/ 🔴 H91/H92/H93; 🟡 H94/H95/H97
- installer/ 🔴 H98/H99/H101; 🟡 H100/H102–H109
- kernel/ 🔴 H110/H111(FIXED)/H112; 🟡 H113–H127
- legal/ 🔴 H128/H129(FIXED)/H130/H131/H135; 🟡 H132/H136/H138/H139/H140/H141; 💭 H137
- lib/ 🔴 H3/H146(FIXED)/H147; 🟡 H148/H149/H150
- liboqs/ 🟡 H151; 💭 H155
- media/ 🔴 H157; 🟡 H158–H160; 💭 H161–H165  (H156 FIXED — mount path capability-gated)
- mnt/ 🔴 H167/H168; 🟡 H169–H171/H176; 💭 H172–H175  (H166 FIXED — mount ops capability-gated)
- network/ 🔴 H177/H178; 🟡 H179/H180; 💭 H181/H182
- opt/ 🔴 H184/H185/H186/H187 (H185/H186 FIXED); 🟡 H188–H193/H200; 💭 H183
- packages/ 🔴 H194/H195/H196(FIXED)/H197(FIXED)/H198 (H194/H195 FIXED); 🟡 H199/H201/H204
- proc/ 🔴 H205/H206/H207/H208; 🟡 H209/H210/H211; 💭 H212/H213/H214
- quantum/ 🔴 H215/H216/H217/H221/H152(FIXED); 🟡 H218/H219/H220; 💭 H222–H225
- root/ 🟡 H226/H228; 💭 H229/H230/H231  (H227 FIXED — passwd write gated)
- sbin/ 🟡 H232; 💭 H234/H235  (H233 FIXED — execute gated)
- scripts/ 🟡 H236/H237; 💭 H238/H239
- sdk/ 🟡 H240/H241; 💭 H242/H243
- security/ 🔴 H244/H245/H246; 🟡 H247–H254; 💭 H255–H258  (H17 FIXED — SecureBoot fail-closed)
- sources/ 🟡 H259/H260/H261/H262; 💭 H263/H264
- srv/ 🔴 H265/H266/H268 (H265/H266 FIXED; sibling imports now relative — H271); 🟡 H269/H270/H272/H273 (H267/H273 FIXED — capability-gated); 💭 H274–H277
- tmp/ 🟡 H278/H279/H280/H282 (H282 FIXED); 💭 H284–H287  (H281/H283 FIXED — capability-gated)
- tools/ 🟡 H288–H292; 💭 H293–H295
- usr/ 🟡 H297/H298/H299/H300; 💭 H301/H302  (H296 FIXED — privileged FS capability-gated)
- var/ 🔴 H303 (FIXED); 🟡 H305/H306 (FIXED); 💭 H307 (FIXED)  (H304 FIXED — managers capability-gated)
