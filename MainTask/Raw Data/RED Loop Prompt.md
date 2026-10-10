# UmerOS — 🔴 RED Remediation Loop (resumable)

**Started:** 2026-10-09

**Source of truth:** `MainTask/Raw Data/Code Review Standards and Process.md` §9 (rows whose **Severity == 🔴**).

**Scope:** ALL 39 🔴-severity hotspots.

**Backend language:** **Python only.**  **Tests:** `F:\Pension Person Details\UmerOS\tests`

**Project root:** `F:\Pension Person Details\UmerOS`

---

## 0. How to run this loop (read me first)

1. Read this file. Find the entry named in **§NEXT** (or the first `- [ ]` in the checklist).
2. **Drift-recon FIRST:** verify the item's premise against the LIVE repo (scoped `Grep`/`Glob`/`Read`).

   Many premises are stale/overstated — if the defect is already fixed, mark it RESOLVED with evidence and move on.
3. If it is a real defect: fix it **in Python only**, with an explanatory `# [FIX Hxxx]` comment.
4. Add/extend the matching `tests/test_*.py` under `tests/` and run it green (see §2).
5. Bookkeeping (see §3): flip `- [ ]` → `- [x]`, add a RESOLVED note, update **§NEXT**,

   update the standard's §9 row, append to the daily log.
6. Do **ONE** item, then stop. The user types **"continues"** to resume at **§NEXT**.

## 1. Standing rules

- **Backend = Python only.** No other backend language is permitted (C/ASM only for boot stubs, behind `ctypes`).
- Do **NOT** batch multiple `Edit` calls on the **same** file in one message (they race). Use an assert-first

  Python `pathlib` script for multi-line same-file edits (`text.count(old) == 1` guard before writing).
- **Trust `Read` over `Grep`** for authoritative file state. Recursive `Glob`/broad `Grep` can time out — scope them.
- Shared guards: `core/path_guard.py` (`safe_child`/`safe_join`/`PathTraversalError`);

  `core/capability_gate.py` (`gate` / `require(cap)` / `CAP_SYS_ADMIN` …, fail-closed when a manager is wired).
- Internet / R\&D is allowed whenever it helps.
- Severity legend: 🔴 must be resolved before approval · 🟡 should be resolved or waived · 💭 discretionary.

## 2. Test runner

- venv (QUOTE the path — it has a space): `"C:/Users/MC Raja Jang/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe"`
- stdlib `unittest` / `pytest>=8`. Run e.g. `python -m pytest tests/test_xxx.py -q`.
- Pre-existing broken test to SKIP: `tests/test_ai.py` (collection error — `ai.providers` missing `AIConfigManager`).

## 3. Bookkeeping surfaces (update every resolved item)

1. This file: flip the checklist box `- [ ]`→`- [x]` + RESOLVED note; update **§NEXT**.
2. Standard `Code Review Standards and Process.md` §9 row: append a **RESOLVED (session N)** note (and recolour if appropriate).
3. `MEMORY.md` pointer (session N + next ID).
4. Daily log `.workbuddy-ai/memory/YYYY-MM-DD.md` (create if missing; append-only).

---

## NEXT

Next: **🔴 RED LOOP COMPLETE** — all 39 🔴 items resolved (H303 was the last; DRIFT: already fixed + tested). The separate 🟡 YELLOW loop resumes at **H66**.

---


## Checklist — 39 🔴 items (in standard §9 order)

- [x] **H1** | 🔴 | `settings.local.json`

  \- Issue: Live OpenRouter API key committed in plaintext

  \- Action: Revoke+rotate, `.gitignore`, purge history

  \- ✅ RESOLVED (session 80, drift): repo-side completed in session 30 — key value scrubbed from the working file, `settings.local.json` added to `.gitignore` (L98) and untracked (`git rm --cached`). Re-verified: working file now holds only an OpenRouter doc snippet, no `sk-` token, no live secret. **USER ACTIONS PENDING (not code):** (1) revoke+rotate the key at openrouter.ai; (2) purge git history (commit 09bf20b) — `git filter-repo --path settings.local.json --invert-paths` then force-push both remotes.
- [x] **H3** | 🔴 | `lib/security.py:72`

  \- Issue: Hardcoded default `PASSWORD="password"`

  \- Action: Generate at runtime / require set on first boot

  \- ✅ RESOLVED (session 81, drift): verified gone — `lib/security.py:72` is now `from dataclasses import ...`; the only `PASSWORD` match is `PamModuleType.PASSWORD = "password"` (L85), the PAM module-**type** enum label (auth/account/session/password), explicitly commented "NOT a credential". Scoped `grep PASSWORD lib/` finds no credential constant. No code change needed.
- [x] **H12** | 🔴 | \`\`ai/` self-healing (design)`

  \- Issue: AI hot-patch path, if enabled, applies generated code

  \- Action: Require capability scope + sandbox + audit log + rollback test before auto-apply (see §4.2)

  \- ✅ RESOLVED (session 82, drift): the gate already exists — `ai/self_healing.py` carries the `[H12 GATE]` mandate and `mitigate()` requires `CAP_SYS_ADMIN` (fail-closed via `core.capability_gate.gate.require`) with before/after audit records; it deliberately never executes generated code. Verified: `grep -E '\b(exec|eval|compile)\s*\(' ai/` → 0 matches; the only hot-patch mention is a `FUTURE:` comment. Covered by `tests/test_ai_governance_security.py::TestSelfHealingGate` (3 passed). No code change needed.
- [x] **H18** | 🔴 | \`\`ai/umer_ai.py:LocalAIAssistant.query`(→`OnlineProvider`)`

  \- Issue: The assistant delegates to `OnlineProvider` (POSTs the user prompt to an external API) **without** an `AIGovernance.check_consent(...)` gate. The module's own header guarantees *"NO user data leaves the device by default"* — a network egress with no explicit, logged consent violates the §4.3 opt-in mandate and the privacy guarantee

  \- Action: Add a consent check (`AIGovernance.check_consent("online_ai")`, logged) before any outbound `providers["online"].query()`; default-deny. Wire `AIGovernance` into `LocalAIAssistant.__init__`

  \- ✅ RESOLVED (session 83, drift): consent gate already wired — `LocalAIAssistant.query` routes through the consent-gated `ai.assistant_service.ChatService` (`_chat_service.chat`), catches `PermissionError` → "[Consent required]"; `__init__` holds no live providers (`self.providers = {}`). `assistant_service._check_consent_or_raise` → `governance.check_consent(provider.id)` (fail-closed). Regression-tested by `tests/test_ai_providers.py::TestConsentGate` + `tests/test_ai_governance_security.py::TestConsentWiring` (11 passed). No code change needed.
- [x] **H46** | 🔴 | `cloud/ota_updater/update_system.py:48-60`

  \- Issue: **Fail-open OTA signature verification.** `verify_and_apply` returns `True` and **applies the update even when `self.crypto is None`** ("No crypto engine — skipping signature check"), and even when a crypto engine is present it calls `self.crypto.sign(payload)` (self-signs) and prints "PASS (simulated)" — it never verifies the manifest's signature (`simulated_dilithium_sig_abc123`). A real PQC `CryptoEngine.verify` exists in `security/crypto_engine.py`/`quantum/crypto_pqc.py` but is unused. An attacker who controls the update source can push an unsigned/unverified payload that gets applied. S…

  \- Action: Make verification **fail-closed**: require `self.crypto` and call `verify(pubkey, payload, manifest["signature"])`; on missing/invalid signature → abort + return False, never apply. Wire to the real `Dilithium`/`ML-DSA` verify path. 🔴 until fixed

  \- ✅ RESOLVED (session 84, drift): H46 already fail-closed — `verify_and_apply` (`cloud/ota_updater/update_system.py:251`) refuses when the crypto engine / trusted key / signature is missing (L276-281), on a verify error (L284-287), and on a signature mismatch (L288-291); the update is never applied. This 🔴 row is a stale duplicate of the existing 🟢 H46 row (`:61-86`). Covered by `tests/test_ota.py` (**7 passed**). No code change needed.
- [x] **H51** | 🔴 | `compatibility/container.py:12-23`

  \- Issue: **Fail-open zero-trust capability gate.** `ZeroTrustContainer.execute_binary` calls `self.capabilities.check(self.container_id, "HARDWARE")` but only *prints* a "Restricting direct hardware access" message when it fails — it does **not** abort or actually restrict; the binary still runs (the method even says "Simulating binary execution"). The capability-check result is ignored → fail-open, same class as H17/H27/H28/H46. The class is named "ZeroTrustContainer" yet enforces nothing

  \- Action: Enforce the check: on `check()` returning False, refuse to launch (raise/return error). Wire `ZeroTrustContainer` into the real launch path or delete it (it is currently unused — see H54)

  \- ✅ RESOLVED (session 85, drift): H51 already fail-closed — `ZeroTrustContainer.execute_binary` now gates execution on `self.capabilities.query(self.container_id, "HARDWARE")` and **returns False** when the capability is missing (`compatibility/container.py:73-78`), logging a DENIED warning; the in-code comment states it 'no longer merely prints and runs'. `print(`/`Simulating` occurrences: 0. Covered by `tests/test_zero_trust_container.py` (**5 passed**). No code change needed.
- [x] **H146** | 🔴 | `lib/ssl_libs.py:414-427,225-245`

  \- Issue: **CA trust verification is fail-open** — `_check_is_trusted` returns `True` whenever ANY `ca-certificates.crt` file exists on disk ("If store exists, assume basic trust", L424); `check_trust` (L225-245) treats any `is_ca` cert as trusted and only string-matches `issuer==subject` — no cryptographic signature validation. Same family as H17/H111/H128/H129.

  \- Action: Verify signatures against an actual trust store; never trust on mere file presence

  \- ✅ RESOLVED (session 86, drift): H146 already fail-closed — `_check_is_trusted` (`lib/ssl_libs.py:548-569`) now returns **False** unless the candidate's real SHA-256 fingerprint matches a cert in a configured CA bundle; the docstring states the old 'trust on mere bundle presence' behaviour is gone and it 'default[s] to NOT trusted'. Verified in-process: no-bundle → False, empty-fp → False. Dedicated regression suite `tests/test_ssl.py` (H146: fail-closed on unknown cert, no-bundle, expired, CA-shortcut). No code change needed.
- [x] **H147** | 🔴 | `lib/ssl_libs.py:82-92`

  \- Issue: **Certificate expiry is never enforced** — `CertInfo.is_expired` unconditionally returns `False` (L83-87) and `days_until_expiry` returns a hardcoded `365` (L92), so expired certificates pass every check. Decorative/expiry fail-open (same family as H111).

  \- Action: Compute real `not_after` and compare to current time

  \- ✅ RESOLVED (session 87, drift): H147 already enforced — `CertInfo.is_expired` (`lib/ssl_libs.py:106-122`) now parses the real `not_after` (naive → UTC) and returns `expiry <= now`; `days_until_expiry` (`:125-139`) computes real signed days (-1 when unknown). The docstring records the old hard-coded `False`/`365` is gone. Verified in-process: past → True/-2474d, future → False/+26381d, empty → False/-1, naive-past → True. Covered by `tests/test_ssl.py` + `tests/test_ssl_security.py`. No code change needed.
- [x] **H152** | 🔴 | `quantum/crypto_pqc.py:36-46`

  \- Issue: **Silent classical-crypto fallback** - when `liboqs-python` is missing, PQC sign/verify silently falls back to classical crypto (or no-op) instead of failing closed, breaking the §4.2 PQC mandate (fail-open under the zero-trust crypto requirement).

  \- Action: Fail CLOSED when the PQC backend is unavailable; never silently downgrade

  \- ✅ RESOLVED (session 88, drift): H152 addressed — the fallback is no longer silent. `PostQuantumCrypto.__init__` logs a WARNING when liboqs is absent, exposes `is_post_quantum` (False under fallback), and provides `assert_post_quantum()` which **raises RuntimeError** so security-critical callers refuse non-PQC operation (`quantum/crypto_pqc.py:273-297`). Verified in-process: backend=fallback, is_post_quantum=False, assert_post_quantum → RuntimeError, sign/verify round-trip OK, tampered → False. Dedicated regression suite `tests/test_pqc.py` (H152) + `tests/test_quantum_security.py`. No code change needed.
- [x] **H156** | 🔴 | ``media/mount_ops.py`, `media/auto_mount.py`, `media/udisks2.py``

  \- Issue: **No `CapabilityManager` gate on the privileged mount path** - `mount_ops.mount`, `auto_mount._handle_hotplug` (auto-mounts on `ADD`), and `udisks2.UDisks2Client.mount` run with no capability check (same "privileged op / no gate" family as H27/H28/H46/H51/H60/H66/H73/H80/H85/H92/H110).

  \- Action: Route all mount/auto-mount/udisks2 mount through `CapabilityManager`

  \- ✅ RESOLVED (session 89, drift): H156 already gated — `media/mount_ops.py` is the single chokepoint: `mount()` (L496), `unmount()` (L539) and `remount()` (L590) each call `gate.require(CAP_FS_ADMIN)` (fail-closed when a manager is wired). Both `media/auto_mount.py` (`_handle_hotplug` → `_do_mount`) and `media/udisks2.py` (`UDisks2Client.mount`) import and route through `mount_ops` — no ungated path; the only `subprocess` uses in `media/` are read-only `blkid` queries. Verified in-process: mount/unmount/remount all raise `PermissionError` under a strict gate. Dedicated 4-test block in `tests/test_cap_gate.py` (H156). No code change needed.
- [x] **H157** | 🔴 | \`\`media/auto_mount.py:\_do_mount` (L282-284)`

  \- Issue: **Removable media auto-mounted `rw` without `noexec,nodev,nosuid`** - builds options from empty `policy.default_options` + `ro` and calls `mount_ops.mount()` directly, bypassing `MountManager.allocate()` (which sets them) + `filesystem.mount_options_for(removable=True)` -> setuid-on-USB executes -> privilege escalation.

  \- Action: Force `noexec,nosuid,nodev` for all removable media via `MountManager.allocate`/`mount_options_for`

  \- ✅ RESOLVED (session 90, drift): H157 already hardened — `AutoMountPolicy.effective_options` (`media/auto_mount.py:100-121`) appends `nodev`, `nosuid`, `noexec` to **every** auto-mount option set (they 'can never be dropped on this path'); `_do_mount` (L322) now builds its options from it before calling `mount_ops.mount`. Verified in-process: vfat/ext4 → ['rw','nodev','nosuid','noexec'], iso9660 → ['ro','nodev','nosuid','noexec']. Covered by `tests/test_media.py` (test_do_mount_uses_effective_options + hardening tests). No code change needed.
- [x] **H166** | 🔴 | ``mnt/mount_ops.py`, `mnt/mount_point.py`, `mnt/fstab.py``

  \- Issue: **No `CapabilityManager` gate on privileged mount ops** - `MountManager.mount`/`umount`/`remount`, `MountPointManager.create`/`remove`, and `Fstab.write_file` (writes `/etc/fstab`) run with no capability check (same family as H27/H28/H46/H51/H60/H66/H73/H80/H85/H92/H110/H156).

  \- Action: Route all through `CapabilityManager`

  \- ✅ RESOLVED (session 91, drift): H166 already gated — all six privileged ops require `fs.admin` via `gate.require(CAP_FS_ADMIN)` (fail-closed when a CapabilityManager is wired): `mnt/mount_ops.py` mount (L365), umount (L430), remount (L468); `mnt/mount_point.py` create (L234), remove (L318); `mnt/fstab.py` write_file (L383). `mnt/user_mount.py` imports `MountManager` from `mount_ops` (no ungated path). Verified in-process: all six raise `PermissionError` under a strict gate. Dedicated 4-test block in `tests/test_cap_gate.py` (H166, L217-290) + `tests/test_mnt_security.py`. No code change needed.
- [x] **H167** | 🔴 | \`\`mnt/mount_point.py:remove(force=True)` (L279-315)`

  \- Issue: **`shutil.rmtree` on a non-symlink-checked path -> TOCTOU arbitrary delete** - `remove(force=True)` rmtrees a path only `os.path.normpath`-validated; `_validate_path` is NOT called in `remove`, so a symlink swap deletes an arbitrary tree (the one genuinely new hotspot in `mnt/`).

  \- Action: `realpath` + reject symlinks before `rmtree`; call `_validate_path`

  \- ✅ RESOLVED (session 92, drift): H167 already guarded — `MountPointManager.remove(force=True)` (`mnt/mount_point.py:340-361`) now refuses `os.path.islink(path)` (L350-352), refuses empty/`/`/drive-root `realpath` targets (L353-357), and re-stats (`islink(real) or not isdir(real)`) immediately before the destructive call to narrow the TOCTOU window (L358-360). The unvalidated `shutil.rmtree` is gone. Covered by the dedicated `tests/test_mnt_security.py` (H167 + H168) → 5 passed. No code change needed.
- [x] **H168** | 🔴 | \`\`mnt/fstab.py:write_file` (L334)`

  \- Issue: **Un-gated privileged `/etc/fstab` write + drops comments/header** - `write_file` writes `/etc/fstab` with no capability gate and `to_string()` silently drops `_comments`/`_header` (round-trip data loss).

  \- Action: Gate `write_file` on `CapabilityManager`; preserve comments/header

  \- ✅ RESOLVED (session 93, drift): H168 already fixed on both halves — (1) `Fstab.write_file` (`mnt/fstab.py:375-401`) now calls `gate.require(CAP_FS_ADMIN)` (L383, fail-closed when a manager is wired); (2) `to_string()` (L358-373) now emits `self._header` (L367-368) and `self._comments` (L369) before the entry lines — the docstring records they 'used to be dropped on write, destroying operator documentation in the boot-critical /etc/fstab'. Verified in-process: 3 comments in → 3 comments out, entry preserved. Covered by `tests/test_mnt_security.py` (H167+H168) → 5 passed. No code change needed.
- [x] **H184** | 🔴 | \`\`opt/` (all privileged ops)`

  \- Issue: **No `CapabilityManager` gate on ANY privileged `/opt` op** - `OptManager.install/remove/update`, `OptPackage.install/remove`, `OptConfig.install_config/remove_config`, `OptIntegration.install_package/remove_package`, `OptHierarchy.bootstrap/register`, `OptEnvManager.write_profile_d`, `VarOptManager.write_file/remove_package_dir` all mutate `/opt`/`/etc/opt`/`/var/opt`/`/etc/profile.d`/`/var/lib` with no capability check (same family as H27/H110/H156/H166/H177). Installs code that becomes a `$PATH` entry → high blast radius.

  \- Action: Route all privileged ops through `CapabilityManager` (e.g. `opt:install`, `opt:remove`, `fs:etc-write`)

  \- ✅ RESOLVED (session 94, FIX — not drift): wired the remaining ungated opt/ modules to core.capability_gate; every privileged op now calls `gate.require(CAP_FS_ADMIN)` (fail-closed when a CapabilityManager is wired). config.py (install_config/remove_config/install_package/remove_package), hierarchy.py (bootstrap/register_package/unregister_package), env.py (write_profile_d), var.py (ensure_package_dir/remove_package_dir/write_file/cleanup_empty/cleanup_stale). 20 gates total across opt/. Verified fail-closed in-process; new 6-test H184 block in tests/test_cap_gate.py (6 passed); opt suites green.
- [x] **H185** | 🔴 | ``opt/var.py:189` `write_file` / `opt/config.py:73` `install_config``

  \- Issue: **Path traversal via unvalidated `filename`/`config_file`/`package_name` in file writes** - `VarOptManager.write_file`/`read_file` build `pkg_dir / filename` (filename unvalidated) → arbitrary file write/read outside `/var/opt` (e.g. `filename="../../etc/passwd"`); `OptConfig.install_config`/`get_config` build `etc_opt_root / package_name / config_file` (config_file unvalidated) → write/read outside `/etc/opt`.

  \- Action: Reject `..` segments; resolve with `realpath` and assert the result is under the intended root

  \- ✅ RESOLVED (session 95, drift): H185 already guarded — `opt/var.py` `_pkg_dir` uses `safe_child(root, provider)`/`safe_child(root, package)` (L117-118); `write_file`/`read_file` use `safe_join(pkg_dir, filename)` (L258/L279) and catch PathTraversalError. `opt/config.py` `get_config_path` uses `safe_child(etc_opt_root, package_name)` + `safe_join(base, config_file)` (L96/L98) with install_config→ValueError, get_config→None, remove_config→False. Verified in-process: write_file('../../etc/passwd')→False, \_pkg_dir traversal→PathTraversalError, install_config traversal→ValueError, nested config_file traversal→ValueError. Covered by tests/test_opt.py (H185/H186 traversal regression). No code change needed.
- [x] **H186** | 🔴 | \`\`opt/manager.py:208` `remove`/`opt/package.py:346` `remove_package`/`opt/package.py:236` `OptPackage.remove`/`opt…`    - Issue: **Path traversal via unvalidated`name`/`provider`in`shutil.rmtree`** - `rmtree(self.opt_root / provider / name)`etc. with no validation →`name="../../etc"`deletes an arbitrary directory outside`/opt`.     - Action: Validate `name`/`provider`(allowlist charset, no`..`); `realpath`+ confirm under root before`rmtree\`

  \- ✅ RESOLVED (session 96, drift): H186 already guarded — `opt/manager.py` `_scoped_path` (L208-215) uses `safe_child` and its docstring records it 'Replaces the previous `root / (provider + "/" + name)` string join, which let a traversal name escape the managed root'; `remove` (L217) wraps all three targets in try/except `PathTraversalError` → path=None (never rmtree'd). `opt/package.py` `_setup_paths` contains provider+name via `safe_child` (L91-94, L104-111) so a traversal name raises in the constructor; `OptPackage.remove` gates on CAP_FS_ADMIN and rmtrees only the contained `base_path`; `PackageOptManager.remove_package` uses `safe_child` + `PathTraversalError` → False (L438-444). Verified in-process: manager.remove('../../etc') → paths_removed=[], OptPackage('../../etc') → PathTraversalError, remove_package('../../etc') → False. Covered by tests/test_opt.py (H185/H186 regression). No code change needed.
- [x] **H187** | 🔴 | ``opt/package.py:161,185` `create_launcher_script`/`create_wrapper_script``

  \- Issue: **Command injection in generated launcher/wrapper scripts** - writes `exec {command} {' '.join(args)} "$@"` and `export {key}="{value}"` into a `#!/bin/bash` script with no shell-escaping → crafted `command`/`args`/`environment` yields arbitrary code execution when the script runs (it lands in `/opt/<pkg>/bin`, which `env.write_profile_d` adds to `$PATH`).

  \- Action: Use `shlex.quote` on every interpolated value, or write a fixed exec template that passes args through without re-parsing

  \- ✅ RESOLVED (session 97, drift): H187 already hardened — `create_launcher_script` (`opt/package.py:234-262`) validates the script name (`_validate_script_name`, no separators/traversal), rejects control chars in the command + every arg (`_reject_shell_metachar`), and builds the exec line with `shlex.quote` — the docstring records the old raw interpolation ('previously `exec {command} {' '.join(args)} "$@"` — a crafted arg like `; rm -rf / #` injected commands'). `create_wrapper_script` (L264-317) does the same for target/pre/post args, requires env keys to match `[A-Za-z_][A-Za-z0-9_]*` and `shlex.quote`s every env value; `_comment_safe` neutralizes newlines in comments. Verified in-process: arg `; rm -rf / #` → single quoted token; control-char command → ValueError; env `$(touch /tmp/pwned)` → single-quoted; traversal name `../evil` → ValueError. Dedicated `tests/test_opt_security.py` (H184+H187) → 8 passed. No code change needed.
- [x] **H194** | 🔴 | ``packages/umer_pkg.py:357,363` `_install_single`/`tarfile.extractall``

  \- Issue: **Tar-slip path traversal on install** - members filtered only by naive string-prefix `m.name.startswith("files/")`, which does NOT stop `files/../../etc/x`; combined with `tarfile.extractall(path=dest, members=...)` called **without `filter=`** (legacy fully-trusted behavior in Python 3.12+: no path sanitization, no perm/owner stripping) → absolute paths / `../` / symlink & hardlink members extract **anywhere** on disk. A malicious `.umerpkg` writes arbitrary files (`~/.bashrc`, cron, SSH `authorized_keys`) outside the package dir (CVE-2007-4559 family; cf. H83/H93).

  \- Action: Use `filter="data"`; reject any member whose `realpath` escapes `dest`; never trust the string prefix.

  \- ✅ RESOLVED (session 98, FIX — hardening): H194 was *mostly* already fixed (`_install_single` used `safe_child` for the install dir, selected only `files/` members, and passed `filter="data"` to `extractall`), BUT the code documented a knowingly-unsafe fallback: `_FILTER_KW = {}` on Python < 3.12, where the naive prefix filter alone does NOT stop `files/../../etc`. Hardened with a new version-independent guard `_safe_tar_members(tar, prefix)` (`packages/umer_pkg.py`) that drops any member whose name is absolute or contains a `..` segment, now used by `_install_single`; `filter="data"` remains as defence-in-depth. Verified in-process: slip member `files/../../escape.txt` refused, legit `files/ok.txt` kept, and with `_FILTER_KW={}` (simulated <3.12) nothing escapes. New 2-test block in `tests/test_packages.py` (3 passed incl. the pre-existing H194 test); full packages suites 29 passed (was 27) — no regressions.
- [x] **H195** | 🔴 | ``packages/umer_pkg.py:347,510` `_install_single`/`build``

  \- Issue: **Untrusted manifest `name`/`version` → attacker-controlled paths** - `dest = os.path.join(install_dir, manifest.name)` and `pkg_filename = f"{pm.name}-{pm.version}.umerpkg"` use values straight from the archive manifest (untrusted). A manifest `name: "../../../../.config/evil"` creates/extracts under `install_dir/../../` → arbitrary dir creation + write outside `~/.umer/packages`; `build` output path likewise traversable.

  \- Action: Validate `name`/`version` against `^[a-zA-Z0-9._+-]+$` before building any path.

  \- ✅ RESOLVED (session 99, drift): H195 already guarded — both path builders use `safe_child` (containment, which is stronger than a regex allowlist): `build` (`packages/umer_pkg.py:766-773`) forms `pkg_filename = f"{pm.name}-{pm.version}.umerpkg"` then `safe_child(output_dir, pkg_filename)` with `PathTraversalError` → ValueError (the comment records 'a malicious name could otherwise write anywhere via "../../etc/x"'); `_install_single` (L577) does `dest = safe_child(self._install_dir, name)`. Verified in-process: build with name `../../etc/evil` → ValueError, version `../../x` → ValueError, normal build OK, nothing escapes. Covered by `tests/test_packages.py::test_install_refuses_traversal_name` + `test_build_refuses_traversal_name` (H195). No code change needed.
- [x] **H196** | 🔴 | ``packages/umer_pkg.py:250,268` `_verify_hash``

  \- Issue: **"Signed" archives overstated; verification fails OPEN** - docstring advertises "Signed .umerpkg archives" but only a SHA3-256 **self-hash** of `manifest.json` exists (no public-key/signature anywhere); `_verify_hash` returns `True` when the `HASH` file is absent ("dev mode" → skip). So unsigned packages pass; integrity is self-referential, not authenticated (same family as H51/H111/H146/H154).

  \- Action: Verify against a pinned public-key signature; refuse install when no signature/HASH present (fail CLOSED).

  \- ✅ RESOLVED (session 100, drift): premise stale — verification is now fail-CLOSED. Public `verify_package` (`packages/umer_pkg.py:322`) delegates to `_verify_package` (L440), which refuses on: missing HASH/manifest.json; integrity-hash mismatch; missing `SIGNATURE` member (unsigned); manifest without a signer `key_id`; a `key_id` absent from the pinned chain-of-trust (`self._trusted_keys` ← `TRUSTED_PUBLIC_KEYS`); and an invalid Ed25519 signature. `_install_single` (L565) calls `_verify_package` BEFORE extracting, so `install` and `update` (update → remove + `_install_single`) are fail-closed; `_verify_hash` (L395) is itself fail-closed too. Probe: unsigned → `verify_package` False ('no SIGNATURE (unsigned)'); manifest without key_id → False ('manifest has no signer key_id'). Covered by `tests/test_packages.py::test_verify_package_fails_when_unsigned` / `_untrusted_key` / `_signature_tampered` + `test_verify_hash_fails_when_hash_missing`. No code change needed.
- [x] **H197** | 🔴 | ``packages/umer_pkg.py:250,277` `_verify_hash``

  \- Issue: **Integrity check ignores the `files/` payload** - `_verify_hash` hashes only `manifest.json` bytes, contradicting the docstring ("SHA3-256 of manifest.json + files/ tree"); the actual payload (`files/`) is never hashed/verified, so a tampered payload is undetectable even when a HASH is present.

  \- Action: Hash the full extracted tree (or a manifest-listed file list) and verify against the signature.

  \- ✅ RESOLVED (session 100, drift): premise stale — `_package_integrity_hash` (L114-125) hashes `b"manifest:" + manifest_bytes + b"|files:" +` every `(name, data)` in the `files/` payload (sorted, NUL-separated), so the full payload IS covered, not just `manifest.json`. Both `_verify_hash` (L433) and `_verify_package` (L480) call it, and `_verify_package` binds the same digest into the Ed25519-signed message (L498 `pub.verify(sig, computed_hash.encode())`). Probe: tampering `files/main.py` while keeping the stale HASH → `_verify_hash` False + `verify_package` False ('Package hash MISMATCH'). Covered by `tests/test_packages.py::test_verify_hash_detects_tampered_payload`. No code change needed.
- [x] **H198** | 🔴 | ``packages/umer_pkg.py:285,390,414` `install`/`remove`/`update``

  \- Issue: **No `CapabilityManager` gate on privileged ops** - docstring claims "system-wide requires admin grant" but there is no capability/admin check on `install`/`remove`/`update`/`build`; they `rmtree`/`copytree`/`extractall` the user filesystem unchecked (same family as H184/H156/H166/H177). Scope is user-space `~/.umer/...` (lower blast radius than `opt/`), but the zero-trust gate is still absent.

  \- Action: Route privileged install/remove/update through `CapabilityManager` (e.g. `pkg:install`/`pkg:remove`).

  \- ✅ RESOLVED (session 100, drift + new test): `gate.require(CAP_FS_ADMIN)` is present at the top of every privileged op — `install` (L517), `remove` (L635), `update` (L668) — via `from core.capability_gate import gate, CAP_FS_ADMIN` (L68/72). A wired CapabilityManager that denies the cap makes all three raise `PermissionError` (fail-closed). NEW test added: `tests/test_cap_gate.py::test_packages_privileged_ops_deny_without_fs_admin` (locks the gate in). No production code change needed.
- [x] **H205** | 🔴 | ``proc/procfs.py:177` + `proc/nodes.py:95` `ProcFileSystem.write`/`ProcFile.write``

  \- Issue: **Write path has no authorization — only per-file read-only `mode`** - `procfs.write` delegates straight to `node.write(data)`; `ProcFile.write` raises `PermissionError` only when `_write is None`, i.e. it enforces the cosmetic `mode="r--r--r--"` string but performs **no UID/owner check and no `CapabilityManager`** anywhere. `mode="rw-r--r--"` is decorative.

  \- Action: Add a `CapabilityManager.require(...)` check (or at minimum an owner/UID check) at the top of `ProcFileSystem.write` and gate every writable node.

  \- ✅ RESOLVED (session 101, drift): the chokepoint IS gated — `ProcFileSystem.write` (`proc/procfs.py:202-222`) calls `gate.require(CAP_SYS_ADMIN)` (L211, import L50) before resolving/writing. Every write path flows through it: direct callers and the VFS bridge `_hooked_write_file` (L310-314) both delegate to `self.write(...)`; `ProcFile.write` (nodes.py) is only reached from this gated method within `proc/`. Reads are unaffected. Covered by `tests/test_proc_cap_gate.py::test_procfs_write_denied_without_cap` / `_allowed_with_cap` / `test_procfs_read_not_gated`. Probe: `fs.write('/proc/sys/kernel/hostname','evil')` → PermissionError ("Capability 'sys.admin' not held by pid N"); `/proc/meminfo` still reads. No code change needed.
- [x] **H206** | 🔴 | ``proc/sysctl_fs.py:26-225` `register_sysctl_entries``

  \- Issue: **`/proc/sys/*` mutation gated by nothing** - ~60 writable sysctl params (kernel.hostname/panic_timeout/hung_task_timeout, vm.drop_caches/swappiness/overcommit_memory/min_free_kbytes, net.ipv4.ip_forward/tcp_syncookies/icmp_echo_ignore_all/ip_local_port_range, fs.file-max/pipe-max-size, net.core.somaxconn/rmem_max/wmem_max) are rewritten via `setattr(adapter,…)` / `registry.set(…)` with no `CAP_SYS_ADMIN`/`CAP_NET_ADMIN` check. On real Linux these require privilege; unprivileged in-process mutation is a posture-weakening / DoS primitive (disable TCP syncookies, enable IP forwarding, drop page…

  \- Action: Gate sysctl writes behind `CapabilityManager.require("sys_admin")`; route net.* through `cap_net_admin`, and validate/range-check int/bool sysctls.

  \- ✅ RESOLVED (session 101, drift): every writable sysctl IS gated — `register_sysctl_entries` builds all `write=True` entries through `_rfile` → `writable_func`, whose first statement is `gate.require(CAP_SYS_ADMIN)` (`proc/sysctl_fs.py:54-59`, import L39); the file's only ungated write handlers are no-op `lambda text: None` stubs that mutate nothing. Defense-in-depth alongside the `ProcFileSystem.write` chokepoint. Covered by `tests/test_proc_cap_gate.py::test_sysctl_write_denied_without_cap` / `_allowed_with_cap`. Probe: `fs.write('/proc/sys/fs/file-max','65536')` without cap → PermissionError. No code change needed.
- [x] **H207** | 🔴 | ``proc/pid_entries.py:258` `oom_score_adj``

  \- Issue: **Per-PID `oom_score_adj` writable with no cap gate** - `write=lambda text, p=pid: adapter.oom_adj.__setitem__(p, text.strip())` lets any caller re-weight the OOM killer for ANY pid, evading OOM protection on critical processes or forcing denial-of-memory.

  \- Action: Require `cap_sys_admin` (real Linux uses `CAP_SYS_RESOURCE` for own / `CAP_SYS_ADMIN` for others) before writing `oom_adj`/`oom_score_adj`.

  \- ✅ RESOLVED (session 101, drift): `oom_score_adj` IS gated — `proc/pid_entries.py:276-277` wires `write=lambda text, p=pid: (gate.require(CAP_SYS_ADMIN), adapter.oom_adj.__setitem__(p, text.strip()))` (import L36). Covered by `tests/test_proc_cap_gate.py::test_oom_score_adj_denied_without_cap` / `_allowed_with_cap`. Probe: `fs.write('/proc/1000/oom_score_adj','500')` without cap → PermissionError. No code change needed.
- [x] **H208** | 🔴 | ``proc/system_files.py:524` `smp_affinity``

  \- Issue: **`/proc/irq/<n>/smp_affinity` writable with no cap gate** - `write=lambda text, i=irq: adapter.irq_affinity.__setitem__(i, text.strip() + "\n")` mutates IRQ affinity (a `CAP_SYS_NICE`/`CAP_SYS_ADMIN` op on real Linux) with no privilege check, allowing unprivileged degradation of I/O/IRQ determinism.

  \- Action: Require `cap_sys_nice`/`cap_sys_admin`; validate the affinity mask format.

  \- ✅ RESOLVED (session 101, drift): `smp_affinity` IS gated — `proc/system_files.py:540-541` wires `write=lambda text, i=irq: (gate.require(CAP_SYS_ADMIN), adapter.irq_affinity.__setitem__(i, text.strip()))` (import L31). Covered by `tests/test_proc_cap_gate.py::test_smp_affinity_denied_without_cap` / `_allowed_with_cap`. Probe: `fs.write('/proc/irq/0/smp_affinity','1')` without cap → PermissionError. No code change needed.
- [x] **H215** | 🔴 | `quantum/crypto_pqc.py:22`

  \- Issue: **H7 Apache-2.0 header stray** - docstring line `Licence: GPL-3.0 (GNU General Public License Version 3)` (British spelling) in a UmerOS file that must carry the canonical GPL-3.0 header; contradicts the adopted H7 → GPL-3.0 decision (same family as mnt H176 / opt H183 / packages H200 / legal).

  \- Action: Replace with the canonical GPL-3.0 header (and `Licence`→`License`).

  \- ✅ RESOLVED (session 103, re-applied; originally session 102, drift): premise stale — `quantum/crypto_pqc.py` already carries the canonical GPL-3.0 header block (L1-12) and `License: GPL-3.0` (L42, American spelling, no `(GNU General Public License Version 3)` suffix, no Apache text anywhere in the file). Enforced by `tests/test_quantum_security.py::TestCryptoPqcHeader::test_canonical_license_tag`. Bonus: canonicalized the still-non-canonical `License: GPL-3.0 (GNU General Public License Version 3)` in `quantum/quantum_sim.py:33` (standard H223, 💭) → `License: GPL-3.0`; no remaining spelled-out `Version 3` in `quantum/*.py`. No change needed to crypto_pqc.py.
- [x] **H216** | 🔴 | ``quantum/crypto_pqc.py` `PostQuantumCrypto``

  \- Issue: **Silent classical-crypto downgrade advertised as Post-Quantum** - when `import oqs` fails, the facade silently selects `_FallbackBackend` (Ed25519 + AES-256-GCM); its docstring states it is "not quantum-safe, but API-compatible" yet the public class/callers still read as PQC. No warning/exception is raised, so callers believe they have quantum-safe crypto (H152 family, re-confirmed here).

  \- Action: Fail CLOSED: raise/warning when `liboqs` is missing and the requested op is PQC-only; never silently downgrade a "Post-Quantum" API to classical.

  \- ✅ RESOLVED (session 103, drift): the silent downgrade was already fixed — `PostQuantumCrypto.__init__` (`quantum/crypto_pqc.py:273-285`) logs an explicit `log.warning(...)` when it selects the classical `_FallbackBackend` ("using CLASSICAL fallback (Ed25519/AES-256-GCM) — NOT quantum-safe"); the module-level `import oqs` guard (L65-79) also warns. It exposes `is_post_quantum` (False under fallback) and `assert_post_quantum()` (L287-297) which **raises `RuntimeError`** fail-closed. Covered by `tests/test_pqc.py::test_pqc_reports_fallback_honestly` (`is_post_quantum is False`, `backend == 'fallback'`, `pytest.raises(RuntimeError)`). Probe: 2 warnings logged at construction; `assert_post_quantum()` raised RuntimeError. No code change needed.
- [x] **H217** | 🔴 | ``quantum/cloud/auth.py:278-288` `AuthManager.save_to_file``

  \- Issue: **Provider credentials persisted as plaintext JSON** - `path.write_text(json.dumps(creds.to_dict()…))` writes IBM/IonQ/AWS/Rigetti tokens to disk with no `0600` mode, no keyring, and no encryption (secret-at-rest). Tokens are also loaded from `UMEROS_IBM_TOKEN`/`UMEROS_IONQ_KEY`/`UMEROS_AWS_*`/`UMEROS_RIGETTI_KEY` env vars.

  \- Action: Write with `mode=0o600`; prefer OS keyring / encrypted store; never log secrets (current `__repr__` is safe - keep it).

  \- ✅ RESOLVED (session 106, re-applied; originally session 104, drift): credentials are already encrypted at rest. `AuthManager.save_to_file` (`quantum/cloud/auth.py:319-363`) seals `creds.to_dict()` with **AES-256-GCM** (L348) and writes an envelope `{"v":1,"enc":"aes256gcm",...}` (L352-358) with `os.chmod(path, 0o600)` (L360); `load_from_file` (L272-317) reads the envelope and refuses legacy plaintext files (L307-312); `_local_auth_key` = SHA-256(`UMEROS_QUANTUM_AUTH_KEY`) or a 0600 keyfile; `__repr__` reports only booleans/providers. Covered by `tests/test_quantum_security.py::TestAuthAtRest`. No code change needed.
- [x] **H221** | 🔴 | \`\`quantum/quantum_server.py:76-82,490-494` FastAPI app`

  \- Issue: **Unauthenticated network surface, wildcard CORS, binds 0.0.0.0** - `CORSMiddleware(allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])` + `uvicorn.run(app, host="0.0.0.0", port=8420)` and **no authn/authz on any endpoint** (`/api/simulate`, `/api/transpile`, `/api/algorithms/{name}/run`, `/api/status`, `/api/noise-model`, `/api/pulse/validate`, `/api/qasm/export`). Any host that can reach the port can drive simulation/algorithm runs with no capability check (H184/H198/H205 family).

  \- Action: Gate every endpoint behind authn + a `CapabilityManager` check; replace `allow_origins=["*"]` with an explicit allowlist; bind `127.0.0.1` unless a real reverse proxy is configured.

  \- ✅ RESOLVED (session 106, re-applied; originally session 105, drift + new test): network posture already hardened — `_allowed_origins()` (`quantum/quantum_server.py:88-95`) is loopback-only by default (no `["*"]`), env-overridable; the bearer gate `_auth_dependency` (L105-113) is applied app-wide via `dependencies=[Depends(_auth_dependency)]` (L120) → 401 on bad/missing token when `UMEROS_QS_TOKEN` is set; `__main__` binds `127.0.0.1` (L542) and refuses a remote host without a token (guard moved above `import uvicorn` to fail fast). NEW test class `tests/test_quantum_security.py::TestServerPosture` (6 tests). Full quantum suite 182 passed.
- [x] **H244** | 🔴 | ``security/security.py:45,83-93,111-117` `SecureBoot``

  \- Issue: **Fail-open secure boot (allow-unknown default)** - `strict_mode=False` by default, so `verify_image`/`verify_bytes` return `True` for any component with no trust-store entry (Dev Mode: Allowing unknown component); the module docstring claims every image is hash-verified against the trust store but the default path skips verification entirely. The hash/compare logic is real (SHA3-256 + `hmac.compare_digest`), the policy default is the gap.

  \- Action: Default `strict_mode=True` (fail CLOSED); in dev, log and refuse unknown components instead of silently allowing; keep hash verification as the only accept path.

  \- ✅ RESOLVED (session 106, drift): premise stale — `SecureBoot.__init__` already defaults to `strict_mode: bool = True` (`security/security.py:58`). Unknown components (no trust entry, no caller `expected_hash`) are denied in BOTH modes: strict raises `PermissionError` (`verify_image` L104-108, `verify_bytes` L131-135); dev mode logs a warning and returns **False** (deny). Hash comparison is real (`hmac.compare_digest`, SHA3-256). Covered by `tests/test_security.py::TestSecureBoot` (`test_default_is_strict_mode`, `test_verify_image_unknown_component_denied`, `_denied_dev_mode`, matching/mismatching hash). Probe: default strict True; strict unknown → PermissionError; dev unknown → False. No code change needed.
- [x] **H245** | 🔴 | ``security/antivirus/api_server.py:6,113-137` `create_app`/`web.run_app``

  \- Issue: **Unauthenticated AV API with destructive endpoints** - aiohttp server on `127.0.0.1:9095` has NO authn/authz; `POST /api/quarantine` and `/api/quarantine/delete` can delete files, `/api/scan/directory` scans any path, `/api/realtime/watch` watches any dir. Any local process can quarantine/delete files with no capability gate (zero-trust violation; H64/H221 family, localhost-scoped so lower blast radius than 0.0.0.0).

  \- Action: Require a capability token or mTLS on every route (or bind a unix socket with restricted perms); gate destructive endpoints behind `CapabilityManager`; consider not exposing scan/quarantine over a network API at all.

  \- ✅ RESOLVED (session 108, re-applied; originally session 107, **REAL FIX**): the H245 remediation had broken indentation — AST proved `create_app()` (`security/antivirus/api_server.py`) had no `return` (returned None) and all 13 route registrations + `return app` were dead code inside `_auth_middleware`, which was never attached to the app (so `main()` → `web.run_app(None)` and no routes existed). Fixed: `_DESTRUCTIVE`/`_auth_middleware` at module level; `create_app()` now builds `web.Application(middlewares=[_auth_middleware])`, registers all 13 routes, returns the app; destructive paths additionally require `gate.require(CAP_FS_ADMIN)` (403). NEW test `tests/test_antivirus_api_security.py` (5 tests).
- [x] **H246** | 🔴 | ``security/sandbox.py:35-104` `SecuritySandbox``

  \- Issue: **SecuritySandbox provides no real isolation (masquerades as zero-trust)** - processes/permissions live in an in-memory dict, `fs_root` defaults to `"/"`, no namespaces/seccomp/chroot are ever created; `check_permission`/`grant_permission` are advisory-only and NOT wired to any `CapabilityManager` despite the docstring (Integrates with the CapabilityManager). `resolve_path` uses correct `realpath`+`commonpath` jail logic, but nothing forces callers to route through it, so the sandbox enforces nothing.

  \- Action: Either implement real isolation (clone/namespaces/seccomp/chroot via the kernel) or relabel the module simulated like `sbin/`; wire `check_permission` to the real `CapabilityManager`; never default `fs_root="/"`.

  \- ✅ RESOLVED (session 108, **REAL FIX**): `security/sandbox.py` was partly aspirational — the docstrings claimed "Zero-Trust process isolation" and "Integrates with the CapabilityManager" while the class was advisory-only, `fs_root` defaulted to "/", and `check_permission` never consulted the real gate. Fixed: (a) consolidated the triple docstring into an honest one (in-process ADVISORY isolation, no namespaces/seccomp/chroot; real containment lives in `kernel/umer_kernel.py`); (b) `check_permission` now calls `core.capability_gate.gate.require(permission, pid=pid)` — a wired CapabilityManager that denies makes `check_permission` return False (probe: local grant present + denying gate → False); (c) `fs_root` no longer defaults to "/" — `ProcessRecord.fs_root`/`register_process(fs_root=...)` default to `None` and `resolve_path` fails CLOSED ("no fs_root jail configured") for unconfined PIDs. `register_process` was already real (the old `print` → `log`). NEW tests in `tests/test_security.py::TestSecuritySandbox` (`test_fs_root_never_defaults_to_root`, `test_resolve_path_fails_closed_without_jail`, `test_resolve_path_jails_inside_fs_root`, `test_check_permission_denied_by_capability_gate`). Security suites 75 passed.
- [x] **H265** | 🔴 | ``srv/backup.py:153-154` `restore_backup`/`_extract_archive``

  \- Issue: **Tar extraction without `filter=` (CVE-2007-4559 path traversal)** - `tarfile.open(archive_path, "r:*")` then `tar.extractall(temp_dir)` with no `filter=` argument (Python >=3.12 default is `None`, which warns but still extracts member paths unchecked), so a hostile archive with `../` or absolute paths writes outside `temp_dir` during backup restore.

  \- Action: Pass `filter="data"` (or `filter="tar"` on older Pythons) to `extractall`; additionally reject members whose resolved name escapes `temp_dir` via `os.path.realpath` containment.

  \- ✅ RESOLVED (session 109, **REAL FIX**): drift-recon found the tar branch already passes `filter="data"` on Python >=3.12 (`_FILTER_KW`, L74) — so the standard's premise (no `filter=` at all) was stale — BUT that kwarg does not exist on <3.12, where `_FILTER_KW` is `{}` (unguarded, the exact H194 pattern). Fixed version-independently: new `_assert_safe_tar_members(tar)` rejects any member whose name is absolute or contains a `..` segment before `extractall`, so a hostile `../` or absolute member raises `ValueError` on every interpreter; `filter="data"` kept as an extra >=3.12 layer. Guarded by the existing `tests/test_srv.py::test_restore_refuses_traversal_archive`.
- [x] **H266** | 🔴 | ``srv/backup.py:157` `restore_backup``

  \- Issue: **Zip extraction without `filter=` (zip-slip)** - `zipf.extractall(temp_dir)` with no `filter=`; `zipfile` does not strip leading `/` or `../` on its own, so a crafted entry (`../../etc/cron.d/x`) escapes `temp_dir` and overwrites arbitrary files during restore.

  \- Action: Pass `filter="data"` to `extractall`; or iterate members and skip any whose resolved path is outside `temp_dir`.

  \- ✅ RESOLVED (session 109, **REAL FIX**): the zip branch was doubly wrong — (a) `zipfile.ZipFile.extractall()` accepts **no** `filter=` kwarg on any Python (verified live on 3.13: `ZipFile.extractall() got an unexpected keyword argument 'filter'`), so the old `zipf.extractall(temp_dir, **_FILTER_KW)` raised `TypeError` on >=3.12 (a live restore bug); and (b) there was no member validation. Fixed: `_assert_safe_zip_members(zipf)` rejects absolute / `..`-bearing names before extraction, then `zipf.extractall(temp_dir)` is called without the bogus kwarg. NEW tests `tests/test_srv.py::test_backup_restore_zip` (zip round-trip) + `test_restore_refuses_traversal_zip` (zip-slip refused).
- [x] **H267** | 🔴 | ``srv/backup.py:181` `restore_backup``

  \- Issue: **Destructive `shutil.rmtree` with no capability gate** - when `overwrite=True`, the destination folder is `shutil.rmtree(dest_folder)`-ed before extraction; there is no `CapabilityManager` check or root-uid assertion, so any caller (or any code that reaches `restore_backup`) can irreversibly delete a service data tree.

  \- Action: Gate the destructive delete behind a `CapabilityManager` capability and an explicit confirm; refuse to delete if the target is not under the resolved `/srv` root.

  \- ✅ RESOLVED (session 110, **PARTIAL REAL FIX**): drift-recon found most of the premise stale — `restore_backup` already calls `gate.require(CAP_BACKUP)` (fail-closed when a CapabilityManager is wired) and `dest_folder` is already built via `safe_join(target_root, …)`, so it is contained under the resolved srv root, and `overwrite=True` is the explicit confirm. BUT a real residual hole remained: `safe_join(root, ".")` tolerates `.` and returns `root` itself, so a manifest with `service_name: "."` made `dest_folder == target_root` and `shutil.rmtree(dest_folder)` would delete the **entire /srv root**. Fixed: before the delete, refuse unless `dest_folder` is a *proper* descendant of `target_root` (`dest_folder != target_root and target_root in dest_folder.parents`) → `ValueError`. NEW test `tests/test_srv.py::test_restore_refuses_rmtree_of_srv_root`.
- [x] **H268** | 🔴 | ``srv/hierarchy.py:275-290` `delete_service_tree``

  \- Issue: **Destructive `shutil.rmtree` gated only by `force=True`, no capability check** - `if not force: raise PermissionError(...)` then `shutil.rmtree(target)`; `force` is a plain boolean from the CLI, not a capability, so `srv_ctl remove --force` deletes an arbitrary resolved service tree with no zero-trust gate (H27/H92/H110/H205 family).

  \- Action: Require a `CapabilityManager` capability to delete; do not treat `force` as the gate; realpath + confirm the target is under `/srv` before any delete.

  \- ✅ RESOLVED (session 111, **PARTIAL REAL FIX**): drift-recon found the "no capability check" premise stale — `delete_service_tree` already calls `gate.require(CAP_FS_ADMIN)` (fail-closed when a CapabilityManager is wired) and `force=True` is the explicit admin confirm. BUT the destructive path had **no containment**: `target = self.root / service_name` meant a name like `"../../etc"` would `shutil.rmtree("/etc")` (CWE-22). Fixed: resolve via `safe_join(self.root, service_name)` (supports nested `domain/service` names), refuse `PathTraversalError` with `PermissionError`, and never delete the root itself (`service_name="."`). NEW tests `tests/test_srv.py::test_delete_service_tree_refuses_traversal` + `test_delete_service_tree_removes_contained_tree`.
- [x] **H303** | 🔴 | \`\`var/directory_manager.py:77,87,94,184,106,212`, `var/spool_manager.py:63,86,93,123,130,151,163`, `var/log_manager.py:6…`    - Issue: **Path-traversal → arbitrary FS delete/write/RCE (CWE-22)** -`name`/`username`/`directory`/`filename`are joined as`self.<x>\_path / param`with no scoping or`realpath`-under-root check; `Path`collapses`..`, so `remove_local_item("../../etc/passwd")`→`unlink("/etc/passwd")`, `VarDirectoryManager.remove_local_item("../etc")`→`shutil.rmtree("/etc")`, and `SpoolManager.set_cron_user("../../etc/cron.d/x", jobs)`→writes `/etc/cron.d/x`(**cron RCE as root**);`LogManager.write_log("../../etc/cron.d/x", …)`→arbitrary append. Read/list variants expose arbitrary file content (`read_mailbox("../..…

  \- Action: Validate + normalize every path param (reject `..`/absolute, resolve with `realpath` and assert it stays under the manager root); provide a shared `safe_join(root, name)` helper used by all three managers.

  \- ✅ RESOLVED (session 112, **DRIFT**): drift-recon found H303 already fully remediated — all three managers (plus `cache_manager.py` + `mail_manager.py`) resolve every caller-supplied name through `safe_child`/`safe_join` from `var/_path_guard.py` (a thin shim over the canonical `core.path_guard`), catching `PathTraversalError` and refusing fail-closed; the code carries explicit `[FIX H303]` markers, and the companion H304 cap-gates (`gate.require(CAP_FS_ADMIN)`) are applied on the privileged ops too. `tests/test_var.py` has dedicated H303 regression tests (`test_set_cron_user_cannot_escape_root`, `test_write_log_cannot_escape_root`, `test_create_local_directory_rejects_traversal`, `test_remove_local_item_rejects_traversal`, `test_read_mailbox_rejects_traversal`, `test_cache_rejects_traversal`, `test_safe_child_helper_refuses_escapes`) → 32 passed. No unguarded `self.<x>_path / param` joins remain (only trusted-root construction).
