# UmerOS Remediation Progress  (resumable loop)

Started: 2026-08-22  |  Source of truth: `MainTask/Raw Data/Code Review Standards and Process.md` (v1.43, H1-H307)
Totals: 66 RED blockers - 152 YELLOW suggestions - 89 BLUE nits = 307 hotspots

## How to resume (human-in-the-loop checkpoint)
- This file is the single source of fix-status. Each session: read it, find the first `[ ]` under the
  current priority, fix that hotspot in the codebase WITH an explanatory `# [FIX Hxxx]` comment,
  add/extend the matching `tests/test_*.py`, then flip its box to `[x]` and update NEXT.
- Generated ONCE from the standard; thereafter maintained by Edit. Do NOT regenerate (would reset status).

## Strategy (priority order)
1. RED blockers first, clustered by root cause (highest leverage):
   - path-traversal (CWE-22): H185,H186,H195,H265,H266,H282,H303(done)
   - fail-open: H129,H146,H196,H305(done)  + dummy-crypto: H111,H152,H154
   - cap-gate (wire CapabilityManager): H227,H233,H267,H273,H281,H283,H296,H304(var, deferred)
   - untrusted input / RCE: H37,H64,H83,H91,H92,H93,H98,H99,H101,H110,H112,H128,H130,H131,H135,
     H156,H157,H166,H167,H168,H177,H178,H184,H187,H194,H197,H198,H205,H206,H207,H208,H215,H216,
     H217,H221,H244,H245,H246
2. YELLOW suggestions - cross-cutting families (H7 licence sweep, per-file baseline, etc.)
3. BLUE nits - tests, docstrings, lazy-import hoist

## NEXT (where to pick up)
**path-traversal cluster CLOSED (2026-08-22):** H185,H186,H194,H195,H265,H266,H282 fixed via the
shared `core/path_guard.py` guard (`safe_child`/`safe_join`/`PathTraversalError`) + `filter="data"`
on `extractall`; 33 new tests green; harness unblocked by repairing `packages/__init__.py`,
`tmp/__init__.py` + 7 `tmp/*.py` relative imports. (H303 done earlier, Session 1.)

**fail-open + dummy-crypto cluster CLOSED (2026-08-22, session 3):** H129 (legal audit fail-closed),
H146 (lib ssl CA-trust fail-closed — X.509 DER fingerprint compare), H111 (kernel CryptoEngine real
AES-GCM + HMAC sign/verify, no dummy `True`), H152 (quantum PQC honest `is_post_quantum` + assert),
H154 (OTA fail-closed sig verify, no hardcoded fake sig), H196/H197 (packages full-payload
SHA3-256 integrity hash, fail-closed; POSIX arcnames so build/verify match cross-platform).
Source fixes across `kernel/umer_kernel.py`, `lib/ssl_libs.py`, `quantum/crypto_pqc.py`,
`cloud/ota_updater/update_system.py`, `packages/umer_pkg.py`, `legal/licenses.py`. New/extended
tests: `test_packages.py`, `test_ssl.py`, `test_legal_scan.py`, `test_crypto_engine.py`,
`test_pqc.py`. `srv/*` sibling imports converted to relative (H271 smell) to unblock `test_srv.py`.
`cryptography`+`numpy` installed into the test venv. Full set: **59 passed**.

## NEXT (where to pick up)
**fail-open + dummy-crypto cluster CLOSED (2026-08-22, session 3)** — see above.

**cap-gate cluster CLOSED (2026-08-22, session 5/6):** all 8 hotspots wired to the shared
zero-trust bridge `core/capability_gate.py` (`gate` + `require(cap)`): **H227** (root passwd), **H233**
(sbin execute), **H267** (srv backup restore rmtree), **H273** (srv apply_profile chmod), **H281** (tmp
reaper), **H283** (tmp enforce_permissions chmod), **H296** (usr privileged FS — sendmail/misc_data/
bsd_compat/games_data/xml managers), **H304** (var managers — directory/spool/log). Every gated entry
point carries a `# [FIX Hxxx]` comment and uses the permissive-when-unwired / fail-closed-when-wired
pattern so CLI/tests do not regress. `tests/test_cap_gate.py` now proves (a) gate-level allow/deny,
(b) strict-mode deny, (c) per-module fail-closed integration for all 8 modules, and (d) a positive
allow-when-held integration (var spool actually writes under a temp var_path). `test_cap_gate.py` +
`test_var.py` = 32 passed, **0 regressions** from this work.

Two fixes were needed to land H296 cleanly (both genuine bugs, now recorded):
  * `usr/man_page.py` referenced an **undefined `ManPageStatus` enum** → `NameError` crashed
    `import usr` and blocked the H296 integration tests. Added the missing `IntEnum` (MISSING/PARSED).
  * `GamesDataManager.add_game_data` was **never gated** (only `remove_game_data` was) — added the
    `# [FIX H296]` `gate.require(CAP_FS_ADMIN)` as its first statement.

## NEXT (where to pick up)
**Full `pytest tests/` is currently blocked by 6 PRE-EXISTING collection errors** (unrelated to the
cap-gate cluster; 0 regressions from this work). They must be fixed so the whole suite collects:
  * `tests/quantum/test_circuit.py`, `test_circuit_library.py`, `test_gates.py` — quantum test modules
    fail to collect (depend on a missing/renamed module; see H120 hard-dep on `umer_kernel1.py`).
  * `tests/test_dc_v2.py` — `FileNotFoundError: UmerOS/quantum/dynamic_circuits_v2.py` (missing source).
  * `tests/test_sbin.py` — `ImportError: cannot import 'IfconfigCommand' from 'network'`.
  * `tests/test_sources.py` — `ImportError: cannot import 'SourcesManager' from 'manager'` (fragile
    sys.path import hack, H261 family — `from manager import` resolves to `legal/manager.py`).
Fix these wiring/import bugs, then proceed to the **full YELLOW/BLUE sweep**. Outstanding **H7 licence
sweep** (`Licence: Apache 2.0`→`License: GPL-3.0`) in opt/config.py, opt/var.py, opt/package.py,
srv/backup.py, packages/umer_pkg.py, tmp/tmpfs.py headers (note `srv/backup.py` still carries
`Licence: Apache 2.0` at line 16 — not yet fixed).

## Checklist

### RED

- [ ] H1 | RED | `settings.local.json` | Live OpenRouter API key committed in plaintext
- [ ] H2 | RED | `initrd/ai_helper.py:166` | `eval(line)` on user history (suppressed B307)
- [ ] H3 | RED | `lib/security.py:72` | Hardcoded default `PASSWORD="password"`
- [ ] H12 | RED | `ai/` self-healing (design) | AI hot-patch path, if enabled, applies generated code
- [ ] H17 | RED | `security/security.py` → `SecureBoot.verify_image` (also planned `secu | Signature/trust verification is **fail-open**: `verify_image` returns `True` when there is no trust-store entr
- [ ] H18 | RED | `ai/umer_ai.py:LocalAIAssistant.query` (→ `OnlineProvider`) | The assistant delegates to `OnlineProvider` (POSTs the user prompt to an external API) **without** an `AIGover
- [ ] H21 | RED | `ai/umer_ai.py:SelfHealingEngine` + `ai/self_healing.py:SelfHealingSer | Self-healing generates patch *code strings*; FUTURE is LLM auto-apply. TODAY's stubs are comment-only (safe), 
- [ ] H27 | RED | `boot/bootloader.py:147` (`verify_kernel`) | Kernel integrity check returns `True` when the image is **missing** ("Permissive during prototype phase") and 
- [ ] H28 | RED | `boot/efi_system.py:524-533` (`is_binary_trusted`) | Secure Boot trust returns `True` when state is `DISABLED` or `SETUP_MODE` and never consults `dbx` (forbidden 
- [ ] H29 | RED | `boot/init.py:27` (`display_waiver`) | The EULA/"I AGREE" liability waiver is **auto-accepted** when stdin is not a TTY ("[Non-interactive mode: Auto
- [ ] H37 | RED | `bin/user_commands.py:268-273,233,245` | `LoginCommand` auth bypass: `-f`/`-F` set `opts["skip_auth"]=True`; `skip_auth` then skips `_authenticate` (`i
- [ ] H42 | RED | `build/UmerOS-GUI.spec:36,29` | **No code signing**: `codesign_identity=None` on the frozen binary — breaks the zero-trust signed-artifact man
- [ ] H46 | RED | `cloud/ota_updater/update_system.py:48-60` | **Fail-open OTA signature verification.** `verify_and_apply` returns `True` and **applies the update even when
- [ ] H51 | RED | `compatibility/container.py:12-23` | **Fail-open zero-trust capability gate.** `ZeroTrustContainer.execute_binary` calls `self.capabilities.check(s
- [ ] H64 | RED | `drivers/driver_service.py:61-94, 259, 323` | **Static-secret / weak-default auth gap.** When OIDC env vars are unset, `verify_oauth_token` validates JWTs w
- [ ] H83 | RED | `home/home_backup.py:66-79` (`restore_backup`) | **Unsafe tar restore — arbitrary file write + data loss.** `restore_backup` does `shutil.rmtree(str(user_home)
- [ ] H91 | RED | `initrd/ai_helper.py:166` (`_load_history`) | **`eval()` on a "trusted" boot history log — re-locates the known H2 into the early-boot path.** `_load_histor
- [ ] H92 | RED | `initrd/linuxrc.py:302-320` (`_drop_to_root`), `initrd/pivot_root.py`, | **No capability gating on the most privileged boot operations.** `_drop_to_root` calls `os.seteuid(0)` wheneve
- [ ] H93 | RED | `initrd/builder.py:342-360` (`_unpack_to_dir`) | **CPIO entry-name path traversal (arbitrary file write).** `_unpack_to_dir` writes `dest = target / rel` where
- [ ] H98 | RED | `installer/__init__.py:1`, `installer/install.py`, `installer/installe | **Two divergent `UmerInstaller` classes + wrong package re-export.** `__init__.py` does `from .install import 
- [ ] H99 | RED | `installer/install.py:45-52` (`display_waiver`) | **Fail-open legal-consent gate.** `display_waiver` returns `True` in `dry_run` mode (the *default* `dry_run=Tr
- [ ] H101 | RED | `installer/installer.py:350-381` (`rollback`), auto-called at L430/L43 | **Unguarded `shutil.rmtree` rollback (data-loss risk).** `rollback()` does `shutil.rmtree(self._install_root)`
- [ ] H110 | RED | `kernel/umer_kernel.py:674-676` | **Live kernel wires no-op placeholder stubs for `MemoryManager`, `IPCBus`, `CapabilityManager`** (`type('X', (
- [x] H111 | RED | `kernel/umer_kernel.py:429-434` (`CryptoEngine`) | **Dummy crypto — `verify` returns `True` unconditionally, `sign` returns `b"dummy_signature"`** (`encrypt` onl
- [ ] H112 | RED | `kernel/umer_kernel.py:436-441` (`SecuritySandbox.register_process`) | **`register_process` only stores `{name, fs_root}` and `print`s; performs no sandboxing / fs_root enforcement*
- [ ] H128 | RED | `legal/licenses.py:8-13,72-73` + `README.md:40` | **License framework contradicts the adopted H7 → GPL-3.0 canonical decision** — `licenses.py` docstring + `get
- [x] H129 | RED | `legal/licenses.py:100-119` | **Fail-open license compliance audit** — `scan_directory` counts any file containing "Licence"/"License"/"Copy
- [ ] H130 | RED | `legal/licenses.py:72-73` | **`get_license_text(name)` silently returns Apache-2.0 text for any unknown name, incl. "GPL-3.0"** — there is
- [ ] H131 | RED | `legal/consent.py:173-189` | **`require_consent_interactive` fails OPEN** — auto-grants in `dry_run` (L173-175) and, in any non-interactive
- [ ] H135 | RED | `legal/cli.py:101-105` + `test_legal.py:229` | **`consent` CLI subcommand hardcodes `user_response="I AGREE"`** → `python -m legal.cli consent` auto-grants c
- [x] H146 | RED | `lib/ssl_libs.py:414-427,225-245` | **CA trust verification is fail-open** — `_check_is_trusted` returns `True` whenever ANY `ca-certificates.crt`
- [ ] H147 | RED | `lib/ssl_libs.py:82-92` | **Certificate expiry is never enforced** — `CertInfo.is_expired` unconditionally returns `False` (L83-87) and 
- [x] H152 | RED | `quantum/crypto_pqc.py:36-46` | **Silent classical-crypto fallback** - when `liboqs-python` is missing, PQC sign/verify silently falls back to
- [x] H154 | RED | `cloud/ota_updater/update_system.py:33` | **Hardcoded fake PQC signature** - `simulated_dilithium_sig_abc123` is used in a "verify signature" step, rein
- [ ] H156 | RED | `media/mount_ops.py`, `media/auto_mount.py`, `media/udisks2.py` | **No `CapabilityManager` gate on the privileged mount path** - `mount_ops.mount`, `auto_mount._handle_hotplug`
- [ ] H157 | RED | `media/auto_mount.py:_do_mount` (L282-284) | **Removable media auto-mounted `rw` without `noexec,nodev,nosuid`** - builds options from empty `policy.defaul
- [ ] H166 | RED | `mnt/mount_ops.py`, `mnt/mount_point.py`, `mnt/fstab.py` | **No `CapabilityManager` gate on privileged mount ops** - `MountManager.mount`/`umount`/`remount`, `MountPoint
- [ ] H167 | RED | `mnt/mount_point.py:remove(force=True)` (L279-315) | **`shutil.rmtree` on a non-symlink-checked path -> TOCTOU arbitrary delete** - `remove(force=True)` rmtrees a 
- [ ] H168 | RED | `mnt/fstab.py:write_file` (L334) | **Un-gated privileged `/etc/fstab` write + drops comments/header** - `write_file` writes `/etc/fstab` with no 
- [ ] H177 | RED | `network/` (all egress) | **No `CapabilityManager` gate on ANY network egress** - `DNSResolver.resolve*`/`resolve_all`/`reverse_lookup`,
- [ ] H178 | RED | `network/http_client.py:227` `_validate_url` | **SSRF - egress client omits internal-range blocking** - only scheme in {http,https} + netloc presence are val
- [ ] H184 | RED | `opt/` (all privileged ops) | **No `CapabilityManager` gate on ANY privileged `/opt` op** - `OptManager.install/remove/update`, `OptPackage.
- [x] H185 | RED | `opt/var.py:189` `write_file` / `opt/config.py:73` `install_config` | **Path traversal via unvalidated `filename`/`config_file`/`package_name` in file writes** - `VarOptManager.wri
- [x] H186 | RED | `opt/manager.py:208` `remove` / `opt/package.py:346` `remove_package`  | **Path traversal via unvalidated `name`/`provider` in `shutil.rmtree`** - `rmtree(self.opt_root / provider / n
- [ ] H187 | RED | `opt/package.py:161,185` `create_launcher_script`/`create_wrapper_scri | **Command injection in generated launcher/wrapper scripts** - writes `exec {command} {' '.join(args)} "$@"` an
- [x] H194 | RED | `packages/umer_pkg.py:357,363` `_install_single`/`tarfile.extractall` | **Tar-slip path traversal on install** - members filtered only by naive string-prefix `m.name.startswith("file
- [x] H195 | RED | `packages/umer_pkg.py:347,510` `_install_single`/`build` | **Untrusted manifest `name`/`version` → attacker-controlled paths** - `dest = os.path.join(install_dir, manife
- [x] H196 | RED | `packages/umer_pkg.py:250,268` `_verify_hash` | **"Signed" archives overstated; verification fails OPEN** - docstring advertises "Signed .umerpkg archives" bu
- [x] H197 | RED | `packages/umer_pkg.py:250,277` `_verify_hash` | **Integrity check ignores the `files/` payload** - `_verify_hash` hashes only `manifest.json` bytes, contradic
- [ ] H198 | RED | `packages/umer_pkg.py:285,390,414` `install`/`remove`/`update` | **No `CapabilityManager` gate on privileged ops** - docstring claims "system-wide requires admin grant" but th
- [ ] H205 | RED | `proc/procfs.py:177` + `proc/nodes.py:95` `ProcFileSystem.write`/`Proc | **Write path has no authorization — only per-file read-only `mode`** - `procfs.write` delegates straight to `n
- [ ] H206 | RED | `proc/sysctl_fs.py:26-225` `register_sysctl_entries` | **`/proc/sys/*` mutation gated by nothing** - ~60 writable sysctl params (kernel.hostname/panic_timeout/hung_t
- [ ] H207 | RED | `proc/pid_entries.py:258` `oom_score_adj` | **Per-PID `oom_score_adj` writable with no cap gate** - `write=lambda text, p=pid: adapter.oom_adj.__setitem__
- [ ] H208 | RED | `proc/system_files.py:524` `smp_affinity` | **`/proc/irq/<n>/smp_affinity` writable with no cap gate** - `write=lambda text, i=irq: adapter.irq_affinity._
- [ ] H215 | RED | `quantum/crypto_pqc.py:22` | **H7 Apache-2.0 header stray** - docstring line `Licence: Apache 2.0` (British spelling) in a UmerOS file that
- [ ] H216 | RED | `quantum/crypto_pqc.py` `PostQuantumCrypto` | **Silent classical-crypto downgrade advertised as Post-Quantum** - when `import oqs` fails, the facade silentl
- [ ] H217 | RED | `quantum/cloud/auth.py:278-288` `AuthManager.save_to_file` | **Provider credentials persisted as plaintext JSON** - `path.write_text(json.dumps(creds.to_dict()…))` writes 
- [ ] H221 | RED | `quantum/quantum_server.py:76-82,490-494` FastAPI app | **Unauthenticated network surface, wildcard CORS, binds 0.0.0.0** - `CORSMiddleware(allow_origins=["*"], allow
- [ ] H244 | RED | `security/security.py:45,83-93,111-117` `SecureBoot` | **Fail-open secure boot (allow-unknown default)** - `strict_mode=False` by default, so `verify_image`/`verify_
- [ ] H245 | RED | `security/antivirus/api_server.py:6,113-137` `create_app`/`web.run_app | **Unauthenticated AV API with destructive endpoints** - aiohttp server on `127.0.0.1:9095` has NO authn/authz;
- [ ] H246 | RED | `security/sandbox.py:35-104` `SecuritySandbox` | **SecuritySandbox provides no real isolation (masquerades as zero-trust)** - processes/permissions live in an 
- [x] H265 | RED | `srv/backup.py:153-154` `restore_backup`/`_extract_archive` | **Tar extraction without `filter=` (CVE-2007-4559 path traversal)** - `tarfile.open(archive_path, "r:*")` then
- [x] H266 | RED | `srv/backup.py:157` `restore_backup` | **Zip extraction without `filter=` (zip-slip)** - `zipf.extractall(temp_dir)` with no `filter=`; `zipfile` doe
- [x] H267 | RED | `srv/backup.py:181` `restore_backup` | **Destructive `shutil.rmtree` with no capability gate** - when `overwrite=True`, the destination folder is `sh
- [ ] H268 | RED | `srv/hierarchy.py:275-290` `delete_service_tree` | **Destructive `shutil.rmtree` gated only by `force=True`, no capability check** - `if not force: raise Permiss
- [x] H303 | RED | `var/directory_manager.py:77,87,94,184,106,212`, `var/spool_manager.py | **Path-traversal → arbitrary FS delete/write/RCE (CWE-22)** - `name`/`username`/`directory`/`filename` are joi
### YELLOW

- [ ] H4 | YELLOW | `bin/user_commands.py:169-185` | `su`-like `[sh,"-c",command]` as other user; `_exec_shell` is a stub returning 0
- [ ] H5 | YELLOW | `bin/boolean_ops.py:411`, `etc/issue_motd.py` | `subprocess` to host with arg lists
- [ ] H6 | YELLOW | `core/command.py` vs `bin/*` | Base `execute(*args)->Any` contradicts `execute(args=None)->int`
- [ ] H7 | YELLOW | LICENSE/setup.py/README (GPL-3.0) vs `developer_guide.md` & master pro | License inconsistency: 3 sources say GPL-3.0, 2 say Apache-2.0
- [ ] H8 | YELLOW | `bin/` (~30+) | Broad `except Exception`/`except:` swallow errors
- [ ] H9 | YELLOW | CI | Only `security_scan.yml` runs (Bandit/Safety/Trivy/ZAP); **no test execution**, no Ruff/Mypy/pre-commit/covera
- [ ] H11 | YELLOW | UI: prior Kivy (`setup.py`/README) vs **decided Flutter (Dart)** | UI tech was inconsistent (Kivy in code, Flutter in blueprint). **Decided 2026-08-20: Flutter (Dart) canonical*
- [ ] H13 | YELLOW | `security/`/package signing (design) | `.umerpkg` signing + chain-of-trust must hold
- [ ] H14 | YELLOW | `README.md` (Project Structure, code examples, Project Statistics) | README documents a **different, aspirational** layout (`kernel/ipc.py`, `kernel/hal.py`, `quantum/simulator.py
- [ ] H15 | YELLOW | `requirements.txt` (dependencies) | (a) `g4f>=0.4.0` — free GPT-4o via reverse-engineered endpoints, supply-chain + ToS risk; (b) floating `>=` pi
- [ ] H16 | YELLOW | `tests/` (harness) | Framework split: top-level `test_*.py` + `run_*.py` use `unittest`; `tests/quantum/` uses **pytest** (`pytest.
- [ ] H19 | YELLOW | `ai/assistant.py`, `ai/self_healing.py`, `ai/resource_predictor.py` | (a) `assistant.py`/`self_healing.py` violate the per-file baseline — no type hints, no docstrings, no `logging
- [ ] H20 | YELLOW | `ai/providers.py` (header), `ai/resource_predictor.py` (header) | Module docstrings declare `Licence: Apache 2.0` while the repo is **GPL-3.0** (LICENSE/setup.py/README). Exten
- [ ] H22 | YELLOW | `setup.py:15` (`kivy>=2.3.0` in `install_requires`) + `README.md` (≈7  | Kivy still declared/described as **the** UI even though **Flutter (Dart) is canonical** (decided 2026-08-20, H
- [ ] H23 | YELLOW | `ui/flutter_ui/lib/src/core/desktop_shell.dart` (`_DesktopGrid`, `_Glo | The **same app registry is hardcoded in three widgets** (e.g. `:448` `_DesktopApp('Power & Idle', …)` appears 
- [ ] H24 | YELLOW | `ui/flutter_ui/lib/src/core/desktop_shell.dart:287` "CPUIdle & Governo | User-facing labels use **OS-internal jargon** — violates HCI #2 (match the real world / plain language). "CPUI
- [ ] H25 | YELLOW | `ui/*.py` (`fluidic_ui.py` CLI shell, `umer_de.py` Tkinter DE, `theme. | Legacy **Python/Tkinter** UI is superseded by the Flutter/Dart frontend (`ui/flutter_ui/`). `fluidic_ui.py` la
- [ ] H26 | YELLOW | `ui/flutter_ui/lib/src/widgets/*` (Dock, DraggableWindow, LaunchPad, C | **a11y gaps:** custom widgets lack `Semantics` labels for screen readers; the only test is a mount smoke test 
- [ ] H30 | YELLOW | `boot/__init__.py:71`, `__main__.py:29`, `boot_manager.py:21`, `bootlo | 10 `boot/` modules declare `Licence: Apache 2.0` headers — contradicts GPL-3.0 (LICENSE/setup.py/README). Exte
- [ ] H31 | YELLOW | `boot/` (19 of 20 modules) | Only `bootloader.py` carries a `[TODAY]` tier label; the other 19 modules (`kernel_image`, `grub_manager`, `sy
- [ ] H32 | YELLOW | `boot/uefi_stub.c` (33 lines) + `boot/init.py:33` | The only C file is a `printf` placeholder with **no real UEFI binding and no `ctypes` bridge** from Python, ye
- [ ] H33 | YELLOW | `boot/bootloader.py:153` (SHA3-256) vs `boot/efi_system.py:82` (SHA-25 | Inconsistent hashing: kernel verified with SHA3-256, EFI binaries with SHA-256, while the design mandate (§4.2
- [ ] H34 | YELLOW | `boot/__main__.py` (CLI) + `boot/demo_boot.py` (imports) + `boot/init. | `python -m boot` is a hand-rolled CLI that doesn't follow the `core/command.py` `execute(args=None)->int` cont
- [ ] H35 | YELLOW | `bin/` (27 of 44 command modules) | Command-interface contract drift: `def execute(self, *args)` instead of the adopted `def execute(self, args=No
- [ ] H36 | YELLOW | `bin/user_commands.py:169-185,187-199` | `SuCommand`: `_exec_command` spawns `subprocess.run([sh,"-c",command], env=env, user=user_info.pw_uid, group=u
- [ ] H38 | YELLOW | `bin/usr_cmds.py:3045` + `bin/usr_commands.py:1938` | `ChageCommand` is **defined in two different modules** (and likely `whoami`/`id`/`groups` share this pattern) 
- [ ] H39 | YELLOW | `bin/` (~30+) | Broad `except Exception`/`except:` swallow real errors across command modules (already tracked as H8)
- [ ] H40 | YELLOW | `bin/` (0 of 44 modules) | **No `bin/` module carries a `[TODAY]/[EXPERIMENTAL]/[FUTURE]` tier label** — every command file violates the 
- [ ] H41 | YELLOW | `build/UmerOS-GUI.spec:5` | The PyInstaller build **freezes `ui/umeros_gui.py` — the legacy Tkinter GUI that H25 already retired** as supe
- [ ] H43 | YELLOW | `build/UmerOS-GUI.spec:5` | **Hardcoded absolute Windows path** `F:\Pension Person Details\UmerOS\ui\umeros_gui.py` — non-portable, machin
- [ ] H44 | YELLOW | `build/UmerOS-GUI.spec:8-15` + repo root | `datas=[]`/`binaries=[]`/`hiddenimports=[]`/`excludes=[]` + `optimize=0` — no assets/runtime deps declared, un
- [ ] H47 | YELLOW | `cloud/ota_updater/update_system.py` (whole module) | Skips the per-file baseline: no `from __future__ import annotations`, no `logging` (uses `print`), no `try/exc
- [ ] H48 | YELLOW | `cloud/ota_updater/update_system.py:22` | Hardcoded `update_url = "https://updates.umeros.dev/latest"` — a simulated domain baked into code; no pinned/v
- [ ] H49 | YELLOW | `cloud/ota_updater/update_system.py:2-12,48` | **Misleading docs / overstated security.** Docstring claims "Verify cryptographic signature" and "Uses the Cry
- [ ] H50 | YELLOW | `compatibility/container_engine.py:30` | `Licence: Apache 2.0` header in `container_engine.py` — contradicts canonical GPL-3.0 (extends H7/H20/H30). Th
- [ ] H52 | YELLOW | `compatibility/container_engine.py:269,348,435` | Foreign binaries launched **unsandboxed.** `LinuxCompat.launch` (L269) / `WineShim.run` (L348) / `AndroidConta
- [ ] H53 | YELLOW | `compatibility/container.py` + `compatibility/syscall_shim.py` (both f | These two files skip the per-file baseline: `print` instead of `logging`, no `from __future__ import annotatio
- [ ] H55 | YELLOW | `core/command.py:30` | **Root cause of the H6 contract drift.** The base `Command.execute` signature is `execute(self, *args: Any) ->
- [ ] H56 | YELLOW | `core/command.py:25-28` | The base `Command` declares a `privileges: List[str]` field ("Required privileges (e.g. ["user"], ["root"])") 
- [ ] H59 | YELLOW | `dev/core.py:69` (`DeviceNode.mode` default) + `dev/*_device.py` | The base `DeviceNode` dataclass defaults to `mode=0o666` (world **read+write**), and a long list of device nod
- [ ] H60 | YELLOW | `dev/core.py:211-237` (`DeviceManager.sync_to_filesystem`) | **Privileged VFS mutation with no capability gate.** `sync_to_filesystem()` calls `os.mknod`/`os.mkfifo`/`os.s
- [ ] H63 | YELLOW | `drivers/` (0 of 75 modules) | **No `drivers/` module carries a license header at all** (no GPLv3, no Apache). Per H7 the canonical license i
- [ ] H66 | YELLOW | `drivers/*` (whole subsystem) | **No capability gating on privileged driver operations.** MMIO/port I/O/DMA (`device_io.py`), PCI region claim
- [ ] H69 | YELLOW | `drivers/` (19 of 75 modules) | **19/75 modules lack `from __future__ import annotations`** (incl. `driver_service.py`, `device.py`, `bus.py`,
- [ ] H71 | YELLOW | `etc/` (license headers) | **License inconsistency.** 28/81 modules carry GPLv3/GPL-3.0 (✓ canonical per H7), but **6/81 say `Licence: Ap
- [ ] H72 | YELLOW | `etc/pam_config.py:255-257, 1258-1264` | **Weak-auth detector is non-blocking (fail-open).** `_WEAK_PATTERNS` flags `auth sufficient pam_permit.so` and
- [ ] H73 | YELLOW | `etc/sudoers.py:40-98` (+ whole `etc/` config-writer subsystem) | **Privileged `/etc` writes with no capability gate.** `SudoersManager` writes `/etc/sudoers` + `/etc/sudoers.d
- [ ] H76 | YELLOW | `feedback/__init__.py:33-43` | **Broken package — imports 5 non-existent modules.** `from collector/tracker/channels/gfdl/manager import ...`
- [ ] H77 | YELLOW | `feedback/__init__.py:21`, `feedback/models.py:14` | **License inconsistency — `Licence: Apache 2.0`** on both files (violates H7 GPL-3.0 canonical; adds 2 more Ap
- [ ] H80 | YELLOW | `fs/vfs.py:69-71, write_file`, `fs/qfs.py:QFS.write_file/delete_file/s | **No capability gating on VFS/QFS mutations.** Every filesystem-mutating entry point (`VirtualFileSystem.write
- [ ] H81 | YELLOW | `fs/qfs.py:27`, `fs/vfs.py` (whole), `fs/__init__.py` (whole) | **License header split + per-file baseline gap.** `qfs.py:27` says `Licence: Apache 2.0` (H7 GPL-3.0 canonical
- [ ] H84 | YELLOW | `home/*` (all managers: `self.home_path / username`) | **Systemic path traversal via unvalidated `username` (and `message.id`/`name`/`subdir`).** Almost every `home/
- [ ] H85 | YELLOW | `home/home_manager.py` (create_home/remove_home), `home_ssh.py` (gener | **No capability gating on privileged `/home` mutations.** Creating/removing a home, generating SSH keys, appen
- [ ] H86 | YELLOW | `home/user_profile.py:157-179` (`_generate_profile`/`_generate_bashrc` | **Shell-injection via unsanitized profile values.** `set_env`/`add_alias` store arbitrary `value`/`command` an
- [ ] H87 | YELLOW | `home/home_ssh.py:54-86` (`generate_key`), `:94-108` (`add_authorized_ | **Fake SSH keys + unsanitized `authorized_keys` append.** `generate_key` returns a fabricated PEM/ssh string b
- [ ] H90 | YELLOW | `ui/umer_de.py:19-38, 41-49` (`HostBridge.extract_and_open`/`open_in_h | **Host-integration bridge writes VFS content to the real host disk (and auto-opens it) with a weak basename.**
- [ ] H94 | YELLOW | `initrd/ai_helper.py:155`, `initrd/__main__.py:66` | **Dynamic `__import__` by name.** `_try_import(name)` returns `__import__(name)` (name from a fixed `("qiskit"
- [ ] H95 | YELLOW | `initrd/` (all 17 modules) | **License inconsistency — `Licence: Apache 2.0` on all 17 files** (violates H7 GPL-3.0 canonical; adds 17 Apac
- [ ] H97 | YELLOW | `initrd/builder.py:290/305`, `initrd/ai_helper.py:133/135/243`, `initr | **Hash strength below the design mandate.** Image hashes (`hashlib.sha256(raw)`/`sha256(final_bytes)`), AI ent
- [ ] H100 | YELLOW | `installer/installer.py:385-404` (`run(consent_override=...)`) | **Unguarded programmatic EULA bypass.** `run(consent_override=True)` skips `show_eula()` entirely ("for testin
- [ ] H102 | YELLOW | `installer/installer.py` (`backup_bootloader`/`copy_os_files`/`install | **No capability gating on privileged install ops.** The installer writes to `/opt/umer_os`, `/opt/umer_backup`
- [ ] H103 | YELLOW | `installer/installer.py:258-295` (`copy_os_files`) | **No `_safe_join` / `..` canonicalization on copy destinations.** `dst_path = os.path.join(dst, os.path.relpat
- [ ] H104 | YELLOW | `installer/installer.py:25`, `installer/install.py` (no header), `inst | **License inconsistency (H7).** `installer.py` declares `Licence: Apache 2.0` (non-canonical); `install.py` an
- [ ] H106 | YELLOW | `installer/install.py:76-100` (`UmerInstaller.install`) | **`install.py` is a dead/legacy stub.** Its `install()` prints "Real installation would happen here" and never
- [ ] H108 | YELLOW | `installer/installer.py:258-295` (`copy_os_files`), whole install pipe | **No integrity/signature verification of installed OS files.** The installer copies whatever is at `source_dir
- [ ] H109 | YELLOW | `installer/installer.py:6-12` (EULA docstring), `:226-254` (`backup_bo | **Over-promised legal contract vs stub implementation.** The EULA/docstring lists 5 "non-negotiable" requireme
- [ ] H113 | YELLOW | `kernel/shell_commands.py:1211` (`SudoCommand`), `:1229` (`SuCommand`) | **`sudo` sets `ctx.shell.current_user="root"` and re-dispatches with no authentication / capability check; `su
- [ ] H114 | YELLOW | `kernel/shell_commands.py:1399,1635` (`kill`/`shutdown`) + `mount`/`mo | **Privileged commands run un-gated** — `kill` calls `scheduler.terminate(pid)`, `shutdown` calls `request_shut
- [ ] H115 | YELLOW | `kernel/umer_kernel.py:864` (`capabilities.register(init_pid)`) + `sch | **Capability lifecycle unwired.** `init` is "registered" but no caps are ever granted/checked for any task; `s
- [ ] H116 | YELLOW | `kernel/umer_kernel.py:1040-1052` (`start_gui_shell`) | **GUI launched via `subprocess.Popen([sys.executable, "ui/launch_gui.py"], stdin=PIPE)`** with mode piped to s
- [ ] H117 | YELLOW | `kernel/ipc_bus.py:297-315` (`try_receive`) + `send`/`broadcast` | **`try_receive` explicitly skips HMAC verification; `send`/`broadcast` have no capability gate.** Latent: once
- [ ] H118 | YELLOW | `kernel/cred.py:116-118,126` (`Credentials.is_root`) | **`is_root()` (euid==0) bypasses capability checks** (`return self.is_root() or cap in self.caps`). Root is om
- [ ] H119 | YELLOW | `kernel/cgroup.py:87` (`CGroupManager.check_memory_limit`) | **Returns `True` (allow) when a PID is not in any cgroup** — implicit allow / fail-open-leaning resource gate 
- [ ] H127 | YELLOW | `kernel/umer_kernel.py:808` (`panic`) | **`panic()` calls `self.taint.add("TAINT_KERNEL_PANIC")` — a string NOT in `KernelTaint._FLAG_INDEX`** (define
- [ ] H132 | YELLOW | `legal/consent.py:131-132,77-89` | **"Cryptographic" consent token is forgeable** — `consent_token = sha256(public values)` with **no key/HMAC/as
- [ ] H133 | YELLOW | `legal/consent.py:35` | **`DEFAULT_LEDGER_PATH` is a hardcoded developer Windows path** (`F:/Pension Person Details/UmerOS/var/lib/ume
- [ ] H134 | YELLOW | `legal/consent.py:126` | **Consent recorded under default `"admin"`** with no identity verification; PII (username/host/machine_id/time
- [ ] H136 | YELLOW | `legal/contributors.py:37,89,109-112` | **`verify_dco` is decorative** — `dco_signed` defaults `True` (L37/L89) and `add_contributor` never verifies a
- [ ] H138 | YELLOW | `legal/maintainers.py:44-45` | **Maintainer "cryptographic" PQC/PGP fingerprints are hardcoded static literals** (`DILITHIUM5:...`, `4A9F...`
- [ ] H139 | YELLOW | `legal/safety_check.py:66,103-104` | **`verify_safety` defaults `is_safe=True`** and only flips to `False` on <500 MB free or a *CRITICAL*-level ba
- [ ] H140 | YELLOW | `legal/test_legal.py:120-121` | **Test 4 asserts `verify_dco("Antigravity AI / DeepMind Team")` is `True`, but that name is NOT in the roster*
- [ ] H141 | YELLOW | `legal/test_legal.py:229` (+ gaps) | **Tests encode the fail-open `consent` CLI as expected** (L229) and don't cover `require_consent_interactive`'
- [ ] H149 | YELLOW | `lib/` (23 modules) + `lib/README.md:138` | **Largest Apache-2.0 cluster in the repo** — ~23 `lib/` files carry `Licence: Apache 2.0` headers and `README.
- [ ] H151 | YELLOW | `liboqs/` (vendored, no `.gitmodules`) | **Vendored OQS C library is UNPINNED** - no `.gitmodules` at repo root, so it can silently drift from upstream
- [ ] H153 | YELLOW | `kernel/pqcrypto_.py` | **Commented-out `pqcrypto` example + divergent pure-Python backend** - the real PQC path is commented out and 
- [ ] H158 | YELLOW | `media/permissions.py` | **Authz layer exists but is unwired** - `MountPermissionManager`/`GroupPolicy` are never consulted before moun
- [ ] H159 | YELLOW | `media/fstab.py:FstabManager.add` | **`add()` skips `validate()`** (detect-but-don't-fail-closed, H72/H170 family) and `make_removable_entry` omit
- [ ] H160 | YELLOW | `media/` (5 modules + 7 files) | **License inconsistency (H7)** - 5 `media/` modules carry `Licence: Apache 2.0` and 7 files have **no header a
- [ ] H169 | YELLOW | `mnt/fstab.py:make_user_mount`, `mnt/user_mount.py` | **User mounts add `nosuid`+`nodev` but NOT `noexec`** (and `MountManager` never auto-applies `noexec,nosuid,no
- [ ] H170 | YELLOW | `mnt/validation.py:MntValidator` | **Findings advisory-only** - `MountManager.mount()` never consults `MntValidator` (detect-but-don't-fail-close
- [ ] H171 | YELLOW | `mnt/user_mount.py:_save_mtab` (L135) | **`/etc/mtab` clobber** - `_save_mtab` rewrites the ENTIRE `/etc/mtab` from a partial in-memory list (`open(pa
- [ ] H176 | YELLOW | `mnt/` (6 modules + `__init__.py`) | **License strays (H7)** - `mount_ops.py`/`fstab.py`/`mount_point.py`/`user_mount.py`/`audit.py`/`validation.py
- [ ] H179 | YELLOW | `network/vpn_tunnel.py:92` `_xor_frame` | **"Encryption" fallback is reversible XOR, not crypto** - default `VPNTunnel()` (no crypto_engine) frames with
- [ ] H180 | YELLOW | `network/dns_resolver.py` | **DNS answers unauthenticated** - `DNSResolver` uses the host resolver (no DoH/DNSSEC); `DNSOverHTTPS` exists 
- [ ] H183 | YELLOW | `opt/` (14 files) | **H7 license strays** - `env`/`fhs`/`hierarchy`/`var` say `Licence: Apache 2.0` (British spelling, like mnt H1
- [ ] H188 | YELLOW | `opt/env.py:251` `write_profile_d` / `opt/integration.py:222` `generat | **Shell-injection in generated PATH/profile snippets** - discovered `bin_path` (a filesystem path) is interpol
- [ ] H189 | YELLOW | `opt/package.py:59-60` `_setup_paths` | **`OptPackage` hardcodes real `/etc/opt` and `/var/opt`** - `etc_path`/`var_path` = `Path("/etc/opt")`/... and
- [ ] H193 | YELLOW | `opt/integration.py:391` `OptServiceManager.start_service` | **Service manager executes discovered scripts without validation** - `discover_services` picks any `.sh`/exten
- [ ] H199 | YELLOW | `packages/umer_pkg.py:435` `update` | **Lexicographic version comparison** - `if manifest.version <= current:` compares version *strings*, not semve
- [ ] H200 | YELLOW | `packages/umer_pkg.py:20` / `packages/repository.py` / `packages/__ini | **H7 license strays** - `umer_pkg.py` docstring says `Licence: Apache 2.0` (British spelling, like mnt H176 / 
- [ ] H201 | YELLOW | `packages/umer_pkg.py:323,326` `_find_in_registry` | **Fuzzy `startswith(name)` match** - `fname.startswith(name) and fname.endswith(".umerpkg")` can select the wr
- [ ] H204 | YELLOW | `packages/umer_pkg.py:357,516` `_install_single`/`build` | **Symlink/hardlink members + no permission `filter`** - extraction without `filter=` also materializes symlink
- [ ] H209 | YELLOW | `proc/system_files.py:103,105,107,115,129,131` + `proc/sysctl_fs.py:10 | **Silent no-op writes behind `rw` mode** - several `/proc/sys/kernel/*` entries (ctrl-alt-del, acct, printk, s
- [ ] H210 | YELLOW | `proc/sysctl_fs.py:12,89,93` hostname/domainname | **Docstring/impl mismatch + trailing-newline persisted** - docstring claims sysctl persisted by `SysctlRegistr
- [ ] H211 | YELLOW | `proc/pid_entries.py:150` `status` / `:33` `environ` | **Fabricated capability mask + fake env** - `status` hardcodes `CapEff: 0000003fffffffff` (full caps) when `ui
- [ ] H218 | YELLOW | `quantum/cloud/auth.py:69-109` `_http_request` | **No TLS certificate pinning on provider auth** - provider OAuth2/REST calls go through `urllib.request.urlope
- [ ] H219 | YELLOW | `quantum/qkd.py:354-383` `key_reconciliation` | **Toy/wrong QKD error reconciliation** - the function simply flips Bob's bits to match Alice (`reconciled_bob[
- [ ] H220 | YELLOW | `quantum/qrng.py` `QRNG`/`QuantumEntropy` | **Simulator, not a true entropy source** - `get_random_bytes`/`_extract_entropy` derive "random" bytes from a 
- [ ] H226 | YELLOW | `root/` (9 `.py` modules + README.md) | **H7 Apache-2.0 header stray cluster** — 9 `.py` files each carry a docstring `Licence: Apache 2.0` line AND `
- [x] H227 | YELLOW | `root/passwd.py:131-143` `PasswdManager.write` + `passwd.py:175-190` ` | **Privileged `/etc/passwd` rewrite with no `CapabilityManager` gate** — `write()` backs up + overwrites `/etc/
- [ ] H228 | YELLOW | `root/mail.py:207` `RootMailForwarder.ensure` | **Home dir created with default umask perms (~0755), not 0700** — `self.home.mkdir(parents=True, exist_ok=True
- [ ] H232 | YELLOW | `sbin/` (all 9 `.py` modules) | **Missing GPL-3.0 license header in every module** - grep across all 9 files found ZERO `GPL`/`Apache`/`Copyri
- [ ] H236 | YELLOW | `scripts/` (both `install_deps.py` + `test_endpoint.py`) | **Missing GPL-3.0 license header (both files)** - grep found zero `GPL`/`Apache`/`Copyright`/`Licence`/`Licens
- [ ] H237 | YELLOW | `scripts/test_endpoint.py:17-26` `generate_test_jwt` | **Test JWT shares the production `test-secret` (HS256)** - `secret = "test-secret"` is hardcoded and is the **
- [ ] H240 | YELLOW | `sdk/` (all 3 `.py` modules) | **Missing GPL-3.0 license header in every module** - grep across all 3 files found ZERO `GPL`/`Apache`/`Copyri
- [ ] H241 | YELLOW | `sdk/build_tool.py:23-67,69-88` `BuildTool.scaffold`/`package` | **Unvalidated `app_name` interpolated into VFS path** - `base = f"/sdk/projects/{app_name}"` is built from the
- [ ] H247 | YELLOW | `security/security.py:22,138-154` `IPCAuthenticator` | **Anti-replay claimed but not implemented** - the module/docstring advertises Anti-Replay Protection yet live 
- [ ] H248 | YELLOW | `security/security.py:163-185` `AIBehavioralMonitor` | **Decorative AI anomaly monitor + cosmetic quarantine** - `analyze_action` matches a hardcoded 4-entry rule se
- [ ] H249 | YELLOW | `security/sandbox.py:89-104` `verify_signature` | **Mislabeled code signing is just a hash equality** - `verify_signature` computes `sha3_512(payload)` and comp
- [ ] H250 | YELLOW | `security/firewall.py:1-16` `AIFirewall` | **Toy AI firewall (masquerading)** - `analyze_packet` only blocks `dst_port==22` (SSH) by source IP; there is 
- [ ] H251 | YELLOW | `security/antivirus/quarantine.py:67-134` `quarantine_file`/`restore_f | **Restore trusts stored path (arbitrary write) + quarantine deletes original** - `restore_file` writes back to
- [ ] H252 | YELLOW | `security/antivirus/heuristics.py:55-69` `analyze` | **Unbounded file read (memory DoS) + Windows-centric coverage** - `analyze` does `content = f.read()` with no 
- [ ] H253 | YELLOW | `security/antivirus/signatures.py:46-85,98-115` `_load_builtin_signatu | **Fake signature DB + silent JSON-error swallow** - builtins include obviously placeholder hashes (Zeus sha256
- [ ] H254 | YELLOW | `security/` (all 14 `.py` modules) | **Missing GPL-3.0 header in every module** - grep found ZERO `GPL`/`Apache`/`Copyright`/`Licence`/`License`/`S
- [ ] H259 | YELLOW | `sources/` (8 of 9 modules: `__init__`, `bibliography`, `signals`, `gl | **Apache-2.0 licence strays (H7)** - every one of these 8 module docstrings declares `Licence: Apache 2.0`, co
- [ ] H260 | YELLOW | `sources/test_sources.py` | **Missing GPL-3.0 header (H7 missing-header variant)** - grep found ZERO `GPL`/`Apache`/`Copyright`/`Licence`/
- [ ] H261 | YELLOW | `sources/*.py` (all modules) + `__init__.py:30-35`, `test_sources.py:1 | **Fragile absolute intra-package imports via sys.path hack** - modules import siblings by bare absolute name (
- [ ] H262 | YELLOW | `sources/source_tree.py:25,47-51` + `manager.py:34` | **Hardcoded dev-machine default + `__init__`-time mkdir side effect** - `DEFAULT_SRC_ROOT = Path("F:/Pension P
- [ ] H269 | YELLOW | `srv/` (9 of 10 modules: `__init__`, `service`, `permissions`, `protoc | **Apache-2.0 licence strays (H7)** - each module docstring declares `Licence: Apache 2.0`, conflicting with th
- [ ] H270 | YELLOW | `srv/fhs.py:51`, `srv/backup.py:37`, `srv/manager.py:49,57-71` | **Hardcoded Windows dev paths + `__init__`-time mkdir side effects** - `DEFAULT_SRV_ROOT = Path("F:/Pension Pe
- [ ] H271 | YELLOW | `srv/*.py` (all modules) + `__init__.py:30-32`, `test_srv.py:16-21` | **Fragile absolute intra-package imports via sys.path hack** - modules import siblings by bare absolute name (
- [ ] H272 | YELLOW | `srv/protocols.py:211-226` `generate_nfs_export_line`/`generate_samba_ | **Unvalidated interpolation into `/etc/exports` / `smb.conf` (config-injection)** - the functions build `f"{cl
- [x] H273 | YELLOW | `srv/permissions.py:139-171` `apply_profile` (+ `audit_service` 173-22 | **POSIX perm mutation/audit with no `CapabilityManager` gate** - `apply_profile` performs real `os.chmod` (POS
- [ ] H278 | YELLOW | `tmp/` (10 of 11 modules: `__init__`, `fhs`, `hierarchy`, `secure_io`, | **Apache-2.0 licence strays (H7)** - each of these 10 module docstrings declares `Licence: Apache 2.0`, confli
- [ ] H279 | YELLOW | `tmp/fhs.py:50`, `tmp/hierarchy.py:47-58,80-96`, `tmp/manager.py:42-51 | **Hardcoded Windows dev path + `__init__`-time mkdir side effects** - `DEFAULT_TMP_ROOT = Path("F:/Pension Per
- [ ] H280 | YELLOW | `tmp/*.py` (all modules) + `__init__.py:34-35`, `test_tmp.py:19-22` | **Fragile absolute intra-package imports via sys.path hack** - modules import siblings by bare absolute name (
- [x] H281 | YELLOW | `tmp/reaper.py:86-202` `clean_by_age`/`clean_on_boot`/`clean_by_quota` | **Destructive reaper with no capability gate and no `tmp_root` containment** - the reaper `unlink()`s/`rmdir()
- [x] H282 | YELLOW | `tmp/tmpfs.py:129-138` `sync_to_disk` | **Path traversal on virtual-file name (arbitrary write)** - `sync_to_disk` writes `dest = target_path / name` 
- [x] H283 | YELLOW | `tmp/permissions.py:116-142` `enforce_permissions` | **Privileged `os.chmod` with no capability gate** - sets `os.chmod(tmp_root, 0o1777)` + socket dirs to `0o1777
- [ ] H288 | YELLOW | `tools/installer.py:21` | **Destructive `shutil.rmtree` with no capability gate** - `install_umer_os` does `shutil.rmtree(dst)` (where `
- [ ] H289 | YELLOW | `tools/installer.py:13` | **Hardcoded default install root `/umer_os`** - `install_umer_os(target_dir="/umer_os")` bakes a Unix absolute
- [ ] H290 | YELLOW | `tools/installer.py:16-22` | **CWD-relative source resolution (wrong-dir copy / fail-open)** - `src` names (`"kernel"`, `"quantum"`, ...) a
- [ ] H291 | YELLOW | `tools/installer.py:1-3` | **Missing GPL-3.0 header + `from __future__` (H7 missing-header variant)** - the file opens with only `import 
- [ ] H292 | YELLOW | `tools/installer.py:10` | **Interactive `input()` EULA with no GPL alignment / real consent** - `show_license()` prints an "AS IS" EULA 
- [x] H296 | YELLOW | `usr/sendmail_manager.py:185,195`, `usr/misc_data_manager.py:672,686-7 | **Privileged FS ops with no capability gate (cap-gate family)** - `os.symlink`(`/usr/lib/sendmail`)+`os.unlink
- [ ] H297 | YELLOW | `usr/misc_data_manager.py:589`, `usr/bsd_compat_manager.py:101`, `usr/ | **Construction-time `mkdir` side effects at system paths** - managers call `BASE_DIR.mkdir(parents=True, exist
- [ ] H298 | YELLOW | `usr/sendmail_manager.py`, `usr/misc_data_manager.py`, `usr/bsd_compat | **Fail-open broad `except Exception` around privileged ops** - privileged symlink/unlink/write/`rmtree` are wr
- [ ] H299 | YELLOW | `usr/` (58 of 61 modules) | **H7 missing GPL-3.0 header cluster (largest in the tree)** - only `kernel_source_manager.py`, `rpm_manager.py
- [ ] H300 | YELLOW | `usr/sendmail_manager.py`, `usr/misc_data_manager.py`, `usr/*` | **Hardcoded absolute `/usr/...` system paths** - class constants bake in `/usr/lib/sendmail`, `/usr/sbin/sendm
- [x] H304 | YELLOW | `var/directory_manager.py`, `var/spool_manager.py`, `var/log_manager.p | **Privileged FS ops with no capability gate (cap-gate family)** - `write_text`/`append`/`unlink`/`rename`/`shu
- [x] H305 | YELLOW | `var/directory_manager.py:81,97,117,130,154,188,218,229,240,259,273,29 | **Fail-open broad `except Exception`** - privileged write/unlink/rmtree/rename are wrapped in `except Exceptio
- [x] H306 | YELLOW | `var/directory_manager.py:14`, `var/spool_manager.py:13`, `var/log_man | **H7 Apache-2.0 strays (wrong licence declared)** - 3 of 4 modules declare `Licence: Apache 2.0`, conflicting 
### BLUE

- [ ] H10 | BLUE | `kernel/umer_kernel.py:1717` | Commented `exec(chat_code,…)` AI-exec feature
- [ ] H45 | BLUE | `build/UmerOS-GUI.spec:1`, `build/__init__.py` | Spec has no license header / tier label (extends H7/H30/H40); `build/__init__.py` is a 0-byte empty marker (ha
- [ ] H54 | BLUE | `compatibility/container.py` (`ZeroTrustContainer`) vs `compatibility/ | Two divergent "container" models: the real, used `ContainerEngine`/`ContainerInstance`, and the unused `ZeroTr
- [ ] H57 | BLUE | `core/command.py` (whole module) | No tier label (should be `[TODAY]` — it is the live command base) and no license header (consistent with `bin/
- [ ] H58 | BLUE | `dev/` (0 of 43 modules) | **No `dev/` module carries a `[TODAY]/[EXPERIMENTAL]/[FUTURE]` tier label** — every `/dev` filesystem module v
- [ ] H61 | BLUE | `dev/core.py` (`DeviceManager` singleton, `self._nodes`) | The central device registry is a process-wide singleton dict accessed via `create_node`/`remove_node`/`get_nod
- [ ] H62 | BLUE | `drivers/` (0 of 75 modules) | **No `drivers/` module carries a `[TODAY]/[EXPERIMENTAL]/[FUTURE]` tier label** — every kernel-driver module v
- [ ] H65 | BLUE | `drivers/device_io.py:12`, `drivers/irq.py:11` | `import ctypes` is present in both files but **never called** (no `CDLL`/`cast`/`POINTER`/`byref`) — dead impo
- [ ] H67 | BLUE | `drivers/crypto.py:328, 1441` | Registers **weak algos** (DES FIPS 46-3, MD5) and implements ciphers in **pure Python** (not constant-time → t
- [ ] H68 | BLUE | `drivers/device_registry.py:13, 25, 42` (+ other driver registries) | `DEVICE_REGISTRY` global dict is mutated by `device_register`/`device_unregister` with **no `threading.Lock`**
- [ ] H70 | BLUE | `etc/` (0 of 81 modules) | **No `etc/` module carries a `[TODAY]/[EXPERIMENTAL]/[FUTURE]` tier label** — every FHS `/etc` config-manager 
- [ ] H74 | BLUE | `examples/` (both modules) | **`examples/` is the smallest folder (2 files, 62 LOC) and models the wrong baseline.** No tier label on eithe
- [ ] H75 | BLUE | `examples/run_demo.py:14-15, 11-12` | **The demo exercises privileged surfaces without modeling zero-trust.** `demo()` calls `HAL.init_device(1)`/`H
- [ ] H78 | BLUE | `feedback/` (0 of 2 modules) | **No `feedback/` module carries a tier label** — same recurring §4.4 gap as every other folder (0/2 here)
- [ ] H79 | BLUE | `feedback/models.py:71-83, 113-118` | **PII stored without consent/erasure modeling.** `FeedbackEntry` persists `submitter_name` + `submitter_contac
- [ ] H82 | BLUE | `fs/qfs.py:580-583`, `fs/qfs.py:84` | **Encapsulation + hash-strength notes.** (a) `QFS.snapshot()` reads private `self._store._refs` directly (L580
- [ ] H88 | BLUE | `home/` (all 10 files) | **Full per-file baseline missing.** 0/10 carry a `[TODAY]/[EXPERIMENTAL]/[FUTURE]` tier label, 0/10 have a lic
- [ ] H89 | BLUE | `HostFiles/welcome_copy.txt`, `HostFiles/chat_log.txt` | **Non-code asset folder — duplication + mislabeling (low risk).** `HostFiles/` is 3 plain-text files (~347 B):
- [ ] H96 | BLUE | `initrd/` (0 of 17 modules) | **No `initrd/` module carries a `[TODAY]/[EXPERIMENTAL]/[FUTURE]` tier label** — every early-boot module viola
- [ ] H105 | BLUE | `installer/install.py` (whole file) | **`install.py` skips the per-file baseline.** Uses `print` (not `logging`), no `from __future__ import annotat
- [ ] H107 | BLUE | `installer/installer.py:89`, `:181`, `:193` | **Lazy stdlib imports inside methods.** `import datetime as _dt` (in `InstallLogger.record`), `import multipro
- [ ] H120 | BLUE | `kernel/umer_kernel.py:668-669` | **Hard dependency on `umer_kernel1.py`** ("the enhanced one from umer_kernel1.py" for `AIResourceManager`/`Qua
- [ ] H121 | BLUE | `kernel/bootloader.py:1-16` | **Duplicated file header** — `#!/usr/bin/env python3` + module docstring defined **three times** (active L7-16
- [ ] H122 | BLUE | `kernel/gui.py` | **Kivy (Tkinter-style) GUI prototype inside `kernel/`** — contradicts the Flutter-canonical decision (H11/H25)
- [ ] H123 | BLUE | `kernel/container_engine.py`, `installer.py`, `umer_ai.py`, `qfs.py`,  | **Off-baseline toy/REPL modules** — `print`/`input()`, no `from __future__`/logging/license/tier, divergent fr
- [ ] H124 | BLUE | `kernel/pqcrypto_.py`, `kernel/onnxruntime_.py` | **Reference/demo snippets that execute at import** — `pqcrypto_.py` runs `kyber1024.generate_keypair()` at top
- [ ] H125 | BLUE | `kernel/requirements.txt` | **Dependency drift** — lists `kivy>=2.2.0` (not Flutter, H11/H15) + `cryptography` (unused: the live `CryptoEn
- [ ] H126 | BLUE | `kernel/modules/dev/udev_rules.py:61,175` + `device_manager.py:122` | **`udev_rules` docstring advertises a `RUN` action (execute program) but `apply_actions` does NOT implement it
- [ ] H137 | BLUE | `legal/contributors.py:49`, `maintainers.py:42`, `donations.py:49-143` | **Real personal PII / financial data hardcoded in source** — `mumeryasin123456789@gmail.com` in `contributors.
- [ ] H142 | BLUE | `legal/donations.py:25-29,174-183` | **`DonationTier` enum labels mismatch code thresholds** — enum SILVER "$50+"/BACKER "$10+" but code uses `>=50
- [ ] H143 | BLUE | `legal/contributors.py:20-26`, `disclaimer.py:86` | **`ContributorRole(str)` subclasses `str` but is used as a constant container** — should be `enum.Enum`; discl
- [ ] H144 | BLUE | `legal/licenses.py:96-97`, `README.md:131`, all `legal/` files | **Minor:** `scan_directory` reads only 2 KB + `errors="ignore"`; `sys.path.insert` import hack in `__init__.py
- [ ] H145 | BLUE | `legal/__init__.py:32-33,35-75` | **Relative imports rely on `sys.path.insert(0, _this_dir)`** (`from disclaimer import ...` instead of `from .d
- [ ] H148 | BLUE | `lib/ssl_libs.py` (whole module) | **`ssl_libs.py` is a "simplified" string-parsed simulation** with no `cryptography`/OpenSSL use; `is_ca` heuri
- [ ] H150 | BLUE | `lib/security.py:116-118` | **`pam_permit.so` ("Always permit") is registered as a stock PAM module** (realistic FHS, but) if the `securit
- [ ] H155 | BLUE | `liboqs/` (Python runtime integration) | **Vendored `liboqs/` is dead/unwired** - the live UmerOS PQC stack does not import the C library; the §4.2 man
- [ ] H161 | BLUE | `media/` (`device_info`/`cleanup`/`hotplug`/`mount_manager`) | **`_selftest()` conformance broken** - 3 crash on `__main__` (`device_info`/`cleanup`/`hotplug`) and 1 is non-
- [ ] H162 | BLUE | `media/cleanup.py:72` | **`__import__("re")` anti-pattern** - imports `re` via `__import__` instead of a top-level `import re`; cleanu
- [ ] H163 | BLUE | `media/filesystem.py:FsType` | **`NVME` enum value does not exist** (referenced but undefined) + `EXT4` is duplicated; latent `AttributeError
- [ ] H164 | BLUE | `media/mount_ops.py:_real_unmount` | **Dead code + lazy flag bug** - `_real_unmount` is unreachable/dead and a related lazy flag is never reset; ha
- [ ] H165 | BLUE | `media/auto_mount.py:user_mode` | **`user_mode` is decorative** and auto-mount proceeds with no user consent (contrast §4.2 consent mandate); co
- [ ] H172 | BLUE | `mnt/mount_ops.py:_enforce_user` | **Dead flag** - `_enforce_user` ctor param is stored but never consulted.
- [ ] H173 | BLUE | `mnt/fstab.py:_parse_line` (L377) | **Uncaught `ValueError`** - `int()` on `dump`/`pass_num` has no `try/except` -> a malformed fstab aborts the p
- [ ] H174 | BLUE | `mnt/fstab.py:to_string` (L327) | **Drops comments/header** - serializes only entries, losing `_comments`/`_header` (round-trip data loss, H168 
- [ ] H175 | BLUE | `mnt/mount_ops.py:mount/umount` | **Shell-shaped command-string logging** - builds `f"{cmd} ..."` strings only logged (not executed); misleading
- [ ] H181 | BLUE | `network/` (6 files) | **H7 header missing + `__init__` no `from __future__`** - no license headers in any of the 6 files (contrast m
- [ ] H182 | BLUE | `network/` (all modules) | **No `_selftest()` in any module** - contrast mnt/ where all 7 were functional; reduces regression safety for 
- [ ] H190 | BLUE | `opt/package.py:257` `verify_integrity` | **`verify_integrity` mislabeled** - only checks subdirectory existence, yet `OptManager.verify` surfaces it as
- [ ] H191 | BLUE | `opt/config.py` / `opt/manager.py` / `opt/package.py` / `opt/integrati | **Missing `from __future__ import annotations`** - only `env`/`fhs`/`hierarchy`/`var` have it; the rest of the
- [ ] H192 | BLUE | `opt/config.py` / `opt/manager.py` / `opt/package.py` / `opt/integrati | **No `_selftest()` in 10 modules** - only `env`/`fhs`/`hierarchy`/`var` have functional ones; `test_opt.py` is
- [ ] H202 | BLUE | `packages/repository.py` / `packages/__init__.py` | **Missing `from __future__ import annotations`** - only `umer_pkg.py` has it; `repository.py` + `__init__.py` 
- [ ] H203 | BLUE | `packages/repository.py` / `packages/umer_pkg.py` | **No `_selftest()` + `print` instead of logging** - `repository.py:33` uses `print("[REPO] …")` in `__init__`;
- [ ] H212 | BLUE | `proc/` (all 24 modules) | **Strong dangerous-call hygiene** - grep across all 24 files found ZERO `subprocess`/`eval`/`exec`/`shell=True
- [ ] H213 | BLUE | `proc/` (all modules) | **Missing GPL-3.0 license headers** - spot-checked modules (procfs, nodes, sysctl_fs, pid_entries, kernel_adap
- [ ] H214 | BLUE | `proc/modules.py` / `proc/mounts.py` | **Graceful simulated fallback** - both read real host `/proc/modules` & `/proc/mounts` via `utils._read_file` 
- [ ] H222 | BLUE | `quantum/cli.py:480,495,502` `--token`/`-t` | **Provider token passed as plaintext argv** - `backends`/`execute`/`jobs` accept `--token` (and docstrings sho
- [ ] H223 | BLUE | `quantum/quantum_sim.py:20` | **H7 Apache-2.0 header stray (2nd in quantum/)** - second docstring `Licence: Apache 2.0` stray inside the `qu
- [ ] H224 | BLUE | `quantum/backend.py:291` `IBMBackend.__init__` | **Exception text may leak token/URL** - `print(f"IBM Backend init warning: {e}")` can surface token/endpoint d
- [ ] H225 | BLUE | `quantum/quantum_sim.py` + `quantum/cloud/session.py` | **Provider REST tokens sent in clear, no TLS pinning** - IBM `Bearer {access_token}`, IonQ `apiKey {api_key}`,
- [ ] H229 | BLUE | `root/passwd.py:136` `PasswdManager.write` | **`.bak` copy uses default umask perms** — `bak.write_bytes(self.path.read_bytes())` writes the backup with th
- [ ] H230 | BLUE | `root/home.py:384-393` `RootHomeManager.ensure` | **`os.chmod` follows symlinks + CLI takes an arbitrary path** — `ensure()` does `if not root.exists(): root.mk
- [ ] H231 | BLUE | `root/dotfiles.py:232,240-283` `register_template`/`ensure` | **Template name path traversal** — `register_template(name, content)` stores an arbitrary name and `ensure()` 
- [x] H233 | BLUE | `sbin/sbin_manager.py` `SbinManager.execute` + all command `execute()` | **No `CapabilityManager` gate or audit logging on privileged-simulated ops** - `SbinManager.execute(command, a
- [ ] H234 | BLUE | `sbin/mount.py` + `sbin/filesystem.py` | **Privileged ops simulated against in-memory tables; real wiring must harden** - `MountCommand`/`UmountCommand
- [ ] H235 | BLUE | `sbin/boot.py` + `sbin/maintenance.py` (`MktempCommand`) | **Commands masquerade as functional privileged tools; only `mktemp` does a real (safe) write** - `HaltCommand`
- [ ] H238 | BLUE | `scripts/test_endpoint.py:10-14,28-39` `start_app`/`main` | **Fixed `time.sleep(3)` readiness wait + forged-token bypass** - `start_app()` blocks 3s then assumes the serv
- [ ] H239 | BLUE | `scripts/install_deps.py:6` `main` | **Unpinned `pip install -r requirements.txt` (supply-chain) + buffered output** - `subprocess.run([sys.executa
- [ ] H242 | BLUE | `sdk/build_tool.py:33-47` `BuildTool.scaffold` | **Caller-supplied `custom_app_code` written verbatim** - when `custom_app_code` is passed, `scaffold` writes i
- [ ] H243 | BLUE | `sdk/` (`__init__.py`, `app_template.py`, `build_tool.py`) | **Baseline gaps: no `from __future__`, no `__all__`, no `_selftest()`** - `__init__.py` is a bare `from .app_t
- [ ] H255 | BLUE | `security/antivirus/realtime.py:28-146,118-139` `RealtimeMonitor` | **Real-time is polling** - the monitor re-walks watched dirs every 2s comparing `mtime` snapshots; it is not F
- [ ] H256 | BLUE | `security/security.py:190-877`,`sandbox.py:108-293` | **Large commented-out dead code + unused imports** - `security.py` (~700 lines) and `sandbox.py` (~200 lines) 
- [ ] H257 | BLUE | `security/tls_utils.py:42-120,199` `create_ssl_context`/`run_uvicorn_s | **Doc/policy mismatches** - `create_ssl_context` docstring says TLS 1.3-first but defaults `min_version=TLSv1_
- [ ] H258 | BLUE | `security/crypto_engine.py:32-84` `CryptoEngine` | **Ephemeral master key + honest PQC placeholder + print** - `sign`/`verify` are HMAC-SHA512 labelled Dilithium
- [ ] H263 | BLUE | `sources/source_tree.py:17` | **Unused `shutil` import** - `import shutil` is never referenced (the module uses `os`/`Path`/`open`/`os.walk`
- [ ] H264 | BLUE | `sources/signals.py:88-89` + `README.md:18` | **Doc overclaim: "inter-process dispatching"** - `SignalDispatcher` is an in-process, in-memory simulated call
- [ ] H274 | BLUE | `srv/protocols.py:64-78` `WWWServiceHandler.start_test_server` | **Localhost test HTTP server, no auth** - binds `socketserver.TCPServer(("127.0.0.1", port), ...)` (good, loop
- [ ] H275 | BLUE | `srv/test_srv.py` | **Missing GPL-3.0 header (H7 missing-header variant)** - grep found ZERO `GPL`/`Apache`/`Copyright`/`Licence`/
- [ ] H276 | BLUE | `srv/service.py:15` | **Unused `import json`** - `import json` is declared but never referenced in the module (serialisation is abse
- [ ] H277 | BLUE | `srv/permissions.py:38` | **Unused `from typing import ... Tuple`** - `Tuple` is imported from `typing` but never referenced in the modu
- [ ] H284 | BLUE | `tmp/test_tmp.py` | **Missing GPL-3.0 header (H7 missing-header variant)** - grep found ZERO `GPL`/`Apache`/`Copyright`/`Licence`/
- [ ] H285 | BLUE | `tmp/hierarchy.py:26`, `tmp/reaper.py:24`, `tmp/manager.py:16`, `tmp/t | **Dead imports** - `import shutil` is unused in `hierarchy.py`/`reaper.py`/`manager.py`/`test_tmp.py` (only `s
- [ ] H286 | BLUE | `tmp/lockfile.py:59-63` `is_pid_alive` | **Lazy `ctypes` Win32 PID check** - on Windows, `is_pid_alive` does `import ctypes` + `ctypes.windll.kernel32.
- [ ] H287 | BLUE | `tmp/manager.py:167-174` `get_default_tmp_manager` | **Hidden init side effect via global singleton** - the module-level `_global_tmp_manager` is created lazily on
- [ ] H293 | BLUE | `tools/installer.py:22` | **`copytree` fails open (silent partial install)** - a missing source subtree is skipped by the `if os.path.ex
- [ ] H294 | BLUE | `tools/installer.py:12,17` | **`logging` used without configuration (dropped records)** - `logging.info(...)` is called with no `logging.ba
- [ ] H295 | BLUE | `tools/installer.py` (whole module) | **Per-file baseline gaps (no docstring/`__all__`/type hints)** - the module has no module docstring/`__all__`,
- [ ] H301 | BLUE | `usr/lib_manager.py`, `usr/sbin_manager.py`, `usr/rpm_manager.py`, `us | **SIMULATED privileged/kernel-surface modules masquerade as functional** - the privileged FHS managers (`lib`/
- [ ] H302 | BLUE | `usr/` (many modules) | **Per-file baseline gaps + no tests** - many modules lack `from __future__ import annotations`/module docstrin
- [x] H307 | BLUE | `var/` (whole package) | **No tests + minor baseline smells** - `var/` ships **no `_selftest()`/test module** (contrast `srv`/`tmp` whi
