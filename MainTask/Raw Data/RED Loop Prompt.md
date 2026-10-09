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
- Internet / R&D is allowed whenever it helps.
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
Next: **H46** — `cloud/ota_updater/update_system.py:48-60` fail-open OTA signature verification. Say **"continues"** for H46.

---

## Checklist — 39 🔴 items (in standard §9 order)

- [x] **H1** | 🔴 | ``settings.local.json``
      - Issue: Live OpenRouter API key committed in plaintext
      - Action: Revoke+rotate, `.gitignore`, purge history
      - ✅ RESOLVED (session 80, drift): repo-side completed in session 30 — key value scrubbed from the working file, `settings.local.json` added to `.gitignore` (L98) and untracked (`git rm --cached`). Re-verified: working file now holds only an OpenRouter doc snippet, no `sk-` token, no live secret. **USER ACTIONS PENDING (not code):** (1) revoke+rotate the key at openrouter.ai; (2) purge git history (commit 09bf20b) — `git filter-repo --path settings.local.json --invert-paths` then force-push both remotes.
- [x] **H3** | 🔴 | ``lib/security.py:72``
      - Issue: Hardcoded default `PASSWORD="password"`
      - Action: Generate at runtime / require set on first boot
      - ✅ RESOLVED (session 81, drift): verified gone — `lib/security.py:72` is now `from dataclasses import ...`; the only `PASSWORD` match is `PamModuleType.PASSWORD = "password"` (L85), the PAM module-**type** enum label (auth/account/session/password), explicitly commented "NOT a credential". Scoped `grep PASSWORD lib/` finds no credential constant. No code change needed.
- [x] **H12** | 🔴 | ``ai/` self-healing (design)`
      - Issue: AI hot-patch path, if enabled, applies generated code
      - Action: Require capability scope + sandbox + audit log + rollback test before auto-apply (see §4.2)
      - ✅ RESOLVED (session 82, drift): the gate already exists — `ai/self_healing.py` carries the `[H12 GATE]` mandate and `mitigate()` requires `CAP_SYS_ADMIN` (fail-closed via `core.capability_gate.gate.require`) with before/after audit records; it deliberately never executes generated code. Verified: `grep -E '\b(exec|eval|compile)\s*\(' ai/` → 0 matches; the only hot-patch mention is a `FUTURE:` comment. Covered by `tests/test_ai_governance_security.py::TestSelfHealingGate` (3 passed). No code change needed.
- [x] **H18** | 🔴 | ``ai/umer_ai.py:LocalAIAssistant.query` (→ `OnlineProvider`)`
      - Issue: The assistant delegates to `OnlineProvider` (POSTs the user prompt to an external API) **without** an `AIGovernance.check_consent(...)` gate. The module's own header guarantees *"NO user data leaves the device by default"* — a network egress with no explicit, logged consent violates the §4.3 opt-in mandate and the privacy guarantee
      - Action: Add a consent check (`AIGovernance.check_consent("online_ai")`, logged) before any outbound `providers["online"].query()`; default-deny. Wire `AIGovernance` into `LocalAIAssistant.__init__`
      - ✅ RESOLVED (session 83, drift): consent gate already wired — `LocalAIAssistant.query` routes through the consent-gated `ai.assistant_service.ChatService` (`_chat_service.chat`), catches `PermissionError` → "[Consent required]"; `__init__` holds no live providers (`self.providers = {}`). `assistant_service._check_consent_or_raise` → `governance.check_consent(provider.id)` (fail-closed). Regression-tested by `tests/test_ai_providers.py::TestConsentGate` + `tests/test_ai_governance_security.py::TestConsentWiring` (11 passed). No code change needed.
- [ ] **H46** | 🔴 | ``cloud/ota_updater/update_system.py:48-60``
      - Issue: **Fail-open OTA signature verification.** `verify_and_apply` returns `True` and **applies the update even when `self.crypto is None`** ("No crypto engine — skipping signature check"), and even when a crypto engine is present it calls `self.crypto.sign(payload)` (self-signs) and prints "PASS (simulated)" — it never verifies the manifest's signature (`simulated_dilithium_sig_abc123`). A real PQC `CryptoEngine.verify` exists in `security/crypto_engine.py`/`quantum/crypto_pqc.py` but is unused. An attacker who controls the update source can push an unsigned/unverified payload that gets applied. S…
      - Action: Make verification **fail-closed**: require `self.crypto` and call `verify(pubkey, payload, manifest["signature"])`; on missing/invalid signature → abort + return False, never apply. Wire to the real `Dilithium`/`ML-DSA` verify path. 🔴 until fixed
- [ ] **H51** | 🔴 | ``compatibility/container.py:12-23``
      - Issue: **Fail-open zero-trust capability gate.** `ZeroTrustContainer.execute_binary` calls `self.capabilities.check(self.container_id, "HARDWARE")` but only *prints* a "Restricting direct hardware access" message when it fails — it does **not** abort or actually restrict; the binary still runs (the method even says "Simulating binary execution"). The capability-check result is ignored → fail-open, same class as H17/H27/H28/H46. The class is named "ZeroTrustContainer" yet enforces nothing
      - Action: Enforce the check: on `check()` returning False, refuse to launch (raise/return error). Wire `ZeroTrustContainer` into the real launch path or delete it (it is currently unused — see H54)
- [ ] **H146** | 🔴 | ``lib/ssl_libs.py:414-427,225-245``
      - Issue: **CA trust verification is fail-open** — `_check_is_trusted` returns `True` whenever ANY `ca-certificates.crt` file exists on disk ("If store exists, assume basic trust", L424); `check_trust` (L225-245) treats any `is_ca` cert as trusted and only string-matches `issuer==subject` — no cryptographic signature validation. Same family as H17/H111/H128/H129.
      - Action: Verify signatures against an actual trust store; never trust on mere file presence
- [ ] **H147** | 🔴 | ``lib/ssl_libs.py:82-92``
      - Issue: **Certificate expiry is never enforced** — `CertInfo.is_expired` unconditionally returns `False` (L83-87) and `days_until_expiry` returns a hardcoded `365` (L92), so expired certificates pass every check. Decorative/expiry fail-open (same family as H111).
      - Action: Compute real `not_after` and compare to current time
- [ ] **H152** | 🔴 | ``quantum/crypto_pqc.py:36-46``
      - Issue: **Silent classical-crypto fallback** - when `liboqs-python` is missing, PQC sign/verify silently falls back to classical crypto (or no-op) instead of failing closed, breaking the §4.2 PQC mandate (fail-open under the zero-trust crypto requirement).
      - Action: Fail CLOSED when the PQC backend is unavailable; never silently downgrade
- [ ] **H156** | 🔴 | ``media/mount_ops.py`, `media/auto_mount.py`, `media/udisks2.py``
      - Issue: **No `CapabilityManager` gate on the privileged mount path** - `mount_ops.mount`, `auto_mount._handle_hotplug` (auto-mounts on `ADD`), and `udisks2.UDisks2Client.mount` run with no capability check (same "privileged op / no gate" family as H27/H28/H46/H51/H60/H66/H73/H80/H85/H92/H110).
      - Action: Route all mount/auto-mount/udisks2 mount through `CapabilityManager`
- [ ] **H157** | 🔴 | ``media/auto_mount.py:_do_mount` (L282-284)`
      - Issue: **Removable media auto-mounted `rw` without `noexec,nodev,nosuid`** - builds options from empty `policy.default_options` + `ro` and calls `mount_ops.mount()` directly, bypassing `MountManager.allocate()` (which sets them) + `filesystem.mount_options_for(removable=True)` -> setuid-on-USB executes -> privilege escalation.
      - Action: Force `noexec,nosuid,nodev` for all removable media via `MountManager.allocate`/`mount_options_for`
- [ ] **H166** | 🔴 | ``mnt/mount_ops.py`, `mnt/mount_point.py`, `mnt/fstab.py``
      - Issue: **No `CapabilityManager` gate on privileged mount ops** - `MountManager.mount`/`umount`/`remount`, `MountPointManager.create`/`remove`, and `Fstab.write_file` (writes `/etc/fstab`) run with no capability check (same family as H27/H28/H46/H51/H60/H66/H73/H80/H85/H92/H110/H156).
      - Action: Route all through `CapabilityManager`
- [ ] **H167** | 🔴 | ``mnt/mount_point.py:remove(force=True)` (L279-315)`
      - Issue: **`shutil.rmtree` on a non-symlink-checked path -> TOCTOU arbitrary delete** - `remove(force=True)` rmtrees a path only `os.path.normpath`-validated; `_validate_path` is NOT called in `remove`, so a symlink swap deletes an arbitrary tree (the one genuinely new hotspot in `mnt/`).
      - Action: `realpath` + reject symlinks before `rmtree`; call `_validate_path`
- [ ] **H168** | 🔴 | ``mnt/fstab.py:write_file` (L334)`
      - Issue: **Un-gated privileged `/etc/fstab` write + drops comments/header** - `write_file` writes `/etc/fstab` with no capability gate and `to_string()` silently drops `_comments`/`_header` (round-trip data loss).
      - Action: Gate `write_file` on `CapabilityManager`; preserve comments/header
- [ ] **H184** | 🔴 | ``opt/` (all privileged ops)`
      - Issue: **No `CapabilityManager` gate on ANY privileged `/opt` op** - `OptManager.install/remove/update`, `OptPackage.install/remove`, `OptConfig.install_config/remove_config`, `OptIntegration.install_package/remove_package`, `OptHierarchy.bootstrap/register`, `OptEnvManager.write_profile_d`, `VarOptManager.write_file/remove_package_dir` all mutate `/opt`/`/etc/opt`/`/var/opt`/`/etc/profile.d`/`/var/lib` with no capability check (same family as H27/H110/H156/H166/H177). Installs code that becomes a `$PATH` entry → high blast radius.
      - Action: Route all privileged ops through `CapabilityManager` (e.g. `opt:install`, `opt:remove`, `fs:etc-write`)
- [ ] **H185** | 🔴 | ``opt/var.py:189` `write_file` / `opt/config.py:73` `install_config``
      - Issue: **Path traversal via unvalidated `filename`/`config_file`/`package_name` in file writes** - `VarOptManager.write_file`/`read_file` build `pkg_dir / filename` (filename unvalidated) → arbitrary file write/read outside `/var/opt` (e.g. `filename="../../etc/passwd"`); `OptConfig.install_config`/`get_config` build `etc_opt_root / package_name / config_file` (config_file unvalidated) → write/read outside `/etc/opt`.
      - Action: Reject `..` segments; resolve with `realpath` and assert the result is under the intended root
- [ ] **H186** | 🔴 | ``opt/manager.py:208` `remove` / `opt/package.py:346` `remove_package` / `opt/package.py:236` `OptPackage.remove` / `opt…`
      - Issue: **Path traversal via unvalidated `name`/`provider` in `shutil.rmtree`** - `rmtree(self.opt_root / provider / name)` etc. with no validation → `name="../../etc"` deletes an arbitrary directory outside `/opt`.
      - Action: Validate `name`/`provider` (allowlist charset, no `..`); `realpath` + confirm under root before `rmtree`
- [ ] **H187** | 🔴 | ``opt/package.py:161,185` `create_launcher_script`/`create_wrapper_script``
      - Issue: **Command injection in generated launcher/wrapper scripts** - writes `exec {command} {' '.join(args)} "$@"` and `export {key}="{value}"` into a `#!/bin/bash` script with no shell-escaping → crafted `command`/`args`/`environment` yields arbitrary code execution when the script runs (it lands in `/opt/<pkg>/bin`, which `env.write_profile_d` adds to `$PATH`).
      - Action: Use `shlex.quote` on every interpolated value, or write a fixed exec template that passes args through without re-parsing
- [ ] **H194** | 🔴 | ``packages/umer_pkg.py:357,363` `_install_single`/`tarfile.extractall``
      - Issue: **Tar-slip path traversal on install** - members filtered only by naive string-prefix `m.name.startswith("files/")`, which does NOT stop `files/../../etc/x`; combined with `tarfile.extractall(path=dest, members=...)` called **without `filter=`** (legacy fully-trusted behavior in Python 3.12+: no path sanitization, no perm/owner stripping) → absolute paths / `../` / symlink & hardlink members extract **anywhere** on disk. A malicious `.umerpkg` writes arbitrary files (`~/.bashrc`, cron, SSH `authorized_keys`) outside the package dir (CVE-2007-4559 family; cf. H83/H93).
      - Action: Use `filter="data"`; reject any member whose `realpath` escapes `dest`; never trust the string prefix.
- [ ] **H195** | 🔴 | ``packages/umer_pkg.py:347,510` `_install_single`/`build``
      - Issue: **Untrusted manifest `name`/`version` → attacker-controlled paths** - `dest = os.path.join(install_dir, manifest.name)` and `pkg_filename = f"{pm.name}-{pm.version}.umerpkg"` use values straight from the archive manifest (untrusted). A manifest `name: "../../../../.config/evil"` creates/extracts under `install_dir/../../` → arbitrary dir creation + write outside `~/.umer/packages`; `build` output path likewise traversable.
      - Action: Validate `name`/`version` against `^[a-zA-Z0-9._+-]+$` before building any path.
- [ ] **H196** | 🔴 | ``packages/umer_pkg.py:250,268` `_verify_hash``
      - Issue: **"Signed" archives overstated; verification fails OPEN** - docstring advertises "Signed .umerpkg archives" but only a SHA3-256 **self-hash** of `manifest.json` exists (no public-key/signature anywhere); `_verify_hash` returns `True` when the `HASH` file is absent ("dev mode" → skip). So unsigned packages pass; integrity is self-referential, not authenticated (same family as H51/H111/H146/H154).
      - Action: Verify against a pinned public-key signature; refuse install when no signature/HASH present (fail CLOSED).
- [ ] **H197** | 🔴 | ``packages/umer_pkg.py:250,277` `_verify_hash``
      - Issue: **Integrity check ignores the `files/` payload** - `_verify_hash` hashes only `manifest.json` bytes, contradicting the docstring ("SHA3-256 of manifest.json + files/ tree"); the actual payload (`files/`) is never hashed/verified, so a tampered payload is undetectable even when a HASH is present.
      - Action: Hash the full extracted tree (or a manifest-listed file list) and verify against the signature.
- [ ] **H198** | 🔴 | ``packages/umer_pkg.py:285,390,414` `install`/`remove`/`update``
      - Issue: **No `CapabilityManager` gate on privileged ops** - docstring claims "system-wide requires admin grant" but there is no capability/admin check on `install`/`remove`/`update`/`build`; they `rmtree`/`copytree`/`extractall` the user filesystem unchecked (same family as H184/H156/H166/H177). Scope is user-space `~/.umer/...` (lower blast radius than `opt/`), but the zero-trust gate is still absent.
      - Action: Route privileged install/remove/update through `CapabilityManager` (e.g. `pkg:install`/`pkg:remove`).
- [ ] **H205** | 🔴 | ``proc/procfs.py:177` + `proc/nodes.py:95` `ProcFileSystem.write`/`ProcFile.write``
      - Issue: **Write path has no authorization — only per-file read-only `mode`** - `procfs.write` delegates straight to `node.write(data)`; `ProcFile.write` raises `PermissionError` only when `_write is None`, i.e. it enforces the cosmetic `mode="r--r--r--"` string but performs **no UID/owner check and no `CapabilityManager`** anywhere. `mode="rw-r--r--"` is decorative.
      - Action: Add a `CapabilityManager.require(...)` check (or at minimum an owner/UID check) at the top of `ProcFileSystem.write` and gate every writable node.
- [ ] **H206** | 🔴 | ``proc/sysctl_fs.py:26-225` `register_sysctl_entries``
      - Issue: **`/proc/sys/*` mutation gated by nothing** - ~60 writable sysctl params (kernel.hostname/panic_timeout/hung_task_timeout, vm.drop_caches/swappiness/overcommit_memory/min_free_kbytes, net.ipv4.ip_forward/tcp_syncookies/icmp_echo_ignore_all/ip_local_port_range, fs.file-max/pipe-max-size, net.core.somaxconn/rmem_max/wmem_max) are rewritten via `setattr(adapter,…)` / `registry.set(…)` with no `CAP_SYS_ADMIN`/`CAP_NET_ADMIN` check. On real Linux these require privilege; unprivileged in-process mutation is a posture-weakening / DoS primitive (disable TCP syncookies, enable IP forwarding, drop page…
      - Action: Gate sysctl writes behind `CapabilityManager.require("sys_admin")`; route net.* through `cap_net_admin`, and validate/range-check int/bool sysctls.
- [ ] **H207** | 🔴 | ``proc/pid_entries.py:258` `oom_score_adj``
      - Issue: **Per-PID `oom_score_adj` writable with no cap gate** - `write=lambda text, p=pid: adapter.oom_adj.__setitem__(p, text.strip())` lets any caller re-weight the OOM killer for ANY pid, evading OOM protection on critical processes or forcing denial-of-memory.
      - Action: Require `cap_sys_admin` (real Linux uses `CAP_SYS_RESOURCE` for own / `CAP_SYS_ADMIN` for others) before writing `oom_adj`/`oom_score_adj`.
- [ ] **H208** | 🔴 | ``proc/system_files.py:524` `smp_affinity``
      - Issue: **`/proc/irq/<n>/smp_affinity` writable with no cap gate** - `write=lambda text, i=irq: adapter.irq_affinity.__setitem__(i, text.strip() + "\n")` mutates IRQ affinity (a `CAP_SYS_NICE`/`CAP_SYS_ADMIN` op on real Linux) with no privilege check, allowing unprivileged degradation of I/O/IRQ determinism.
      - Action: Require `cap_sys_nice`/`cap_sys_admin`; validate the affinity mask format.
- [ ] **H215** | 🔴 | ``quantum/crypto_pqc.py:22``
      - Issue: **H7 Apache-2.0 header stray** - docstring line `Licence: GPL-3.0 (GNU General Public License Version 3)` (British spelling) in a UmerOS file that must carry the canonical GPL-3.0 header; contradicts the adopted H7 → GPL-3.0 decision (same family as mnt H176 / opt H183 / packages H200 / legal).
      - Action: Replace with the canonical GPL-3.0 header (and `Licence`→`License`).
- [ ] **H216** | 🔴 | ``quantum/crypto_pqc.py` `PostQuantumCrypto``
      - Issue: **Silent classical-crypto downgrade advertised as Post-Quantum** - when `import oqs` fails, the facade silently selects `_FallbackBackend` (Ed25519 + AES-256-GCM); its docstring states it is "not quantum-safe, but API-compatible" yet the public class/callers still read as PQC. No warning/exception is raised, so callers believe they have quantum-safe crypto (H152 family, re-confirmed here).
      - Action: Fail CLOSED: raise/warning when `liboqs` is missing and the requested op is PQC-only; never silently downgrade a "Post-Quantum" API to classical.
- [ ] **H217** | 🔴 | ``quantum/cloud/auth.py:278-288` `AuthManager.save_to_file``
      - Issue: **Provider credentials persisted as plaintext JSON** - `path.write_text(json.dumps(creds.to_dict()…))` writes IBM/IonQ/AWS/Rigetti tokens to disk with no `0600` mode, no keyring, and no encryption (secret-at-rest). Tokens are also loaded from `UMEROS_IBM_TOKEN`/`UMEROS_IONQ_KEY`/`UMEROS_AWS_*`/`UMEROS_RIGETTI_KEY` env vars.
      - Action: Write with `mode=0o600`; prefer OS keyring / encrypted store; never log secrets (current `__repr__` is safe - keep it).
- [ ] **H221** | 🔴 | ``quantum/quantum_server.py:76-82,490-494` FastAPI app`
      - Issue: **Unauthenticated network surface, wildcard CORS, binds 0.0.0.0** - `CORSMiddleware(allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])` + `uvicorn.run(app, host="0.0.0.0", port=8420)` and **no authn/authz on any endpoint** (`/api/simulate`, `/api/transpile`, `/api/algorithms/{name}/run`, `/api/status`, `/api/noise-model`, `/api/pulse/validate`, `/api/qasm/export`). Any host that can reach the port can drive simulation/algorithm runs with no capability check (H184/H198/H205 family).
      - Action: Gate every endpoint behind authn + a `CapabilityManager` check; replace `allow_origins=["*"]` with an explicit allowlist; bind `127.0.0.1` unless a real reverse proxy is configured.
- [ ] **H244** | 🔴 | ``security/security.py:45,83-93,111-117` `SecureBoot``
      - Issue: **Fail-open secure boot (allow-unknown default)** - `strict_mode=False` by default, so `verify_image`/`verify_bytes` return `True` for any component with no trust-store entry (Dev Mode: Allowing unknown component); the module docstring claims every image is hash-verified against the trust store but the default path skips verification entirely. The hash/compare logic is real (SHA3-256 + `hmac.compare_digest`), the policy default is the gap.
      - Action: Default `strict_mode=True` (fail CLOSED); in dev, log and refuse unknown components instead of silently allowing; keep hash verification as the only accept path.
- [ ] **H245** | 🔴 | ``security/antivirus/api_server.py:6,113-137` `create_app`/`web.run_app``
      - Issue: **Unauthenticated AV API with destructive endpoints** - aiohttp server on `127.0.0.1:9095` has NO authn/authz; `POST /api/quarantine` and `/api/quarantine/delete` can delete files, `/api/scan/directory` scans any path, `/api/realtime/watch` watches any dir. Any local process can quarantine/delete files with no capability gate (zero-trust violation; H64/H221 family, localhost-scoped so lower blast radius than 0.0.0.0).
      - Action: Require a capability token or mTLS on every route (or bind a unix socket with restricted perms); gate destructive endpoints behind `CapabilityManager`; consider not exposing scan/quarantine over a network API at all.
- [ ] **H246** | 🔴 | ``security/sandbox.py:35-104` `SecuritySandbox``
      - Issue: **SecuritySandbox provides no real isolation (masquerades as zero-trust)** - processes/permissions live in an in-memory dict, `fs_root` defaults to `"/"`, no namespaces/seccomp/chroot are ever created; `check_permission`/`grant_permission` are advisory-only and NOT wired to any `CapabilityManager` despite the docstring (Integrates with the CapabilityManager). `resolve_path` uses correct `realpath`+`commonpath` jail logic, but nothing forces callers to route through it, so the sandbox enforces nothing.
      - Action: Either implement real isolation (clone/namespaces/seccomp/chroot via the kernel) or relabel the module simulated like `sbin/`; wire `check_permission` to the real `CapabilityManager`; never default `fs_root="/"`.
- [ ] **H265** | 🔴 | ``srv/backup.py:153-154` `restore_backup`/`_extract_archive``
      - Issue: **Tar extraction without `filter=` (CVE-2007-4559 path traversal)** - `tarfile.open(archive_path, "r:*")` then `tar.extractall(temp_dir)` with no `filter=` argument (Python >=3.12 default is `None`, which warns but still extracts member paths unchecked), so a hostile archive with `../` or absolute paths writes outside `temp_dir` during backup restore.
      - Action: Pass `filter="data"` (or `filter="tar"` on older Pythons) to `extractall`; additionally reject members whose resolved name escapes `temp_dir` via `os.path.realpath` containment.
- [ ] **H266** | 🔴 | ``srv/backup.py:157` `restore_backup``
      - Issue: **Zip extraction without `filter=` (zip-slip)** - `zipf.extractall(temp_dir)` with no `filter=`; `zipfile` does not strip leading `/` or `../` on its own, so a crafted entry (`../../etc/cron.d/x`) escapes `temp_dir` and overwrites arbitrary files during restore.
      - Action: Pass `filter="data"` to `extractall`; or iterate members and skip any whose resolved path is outside `temp_dir`.
- [ ] **H267** | 🔴 | ``srv/backup.py:181` `restore_backup``
      - Issue: **Destructive `shutil.rmtree` with no capability gate** - when `overwrite=True`, the destination folder is `shutil.rmtree(dest_folder)`-ed before extraction; there is no `CapabilityManager` check or root-uid assertion, so any caller (or any code that reaches `restore_backup`) can irreversibly delete a service data tree.
      - Action: Gate the destructive delete behind a `CapabilityManager` capability and an explicit confirm; refuse to delete if the target is not under the resolved `/srv` root.
- [ ] **H268** | 🔴 | ``srv/hierarchy.py:275-290` `delete_service_tree``
      - Issue: **Destructive `shutil.rmtree` gated only by `force=True`, no capability check** - `if not force: raise PermissionError(...)` then `shutil.rmtree(target)`; `force` is a plain boolean from the CLI, not a capability, so `srv_ctl remove --force` deletes an arbitrary resolved service tree with no zero-trust gate (H27/H92/H110/H205 family).
      - Action: Require a `CapabilityManager` capability to delete; do not treat `force` as the gate; realpath + confirm the target is under `/srv` before any delete.
- [ ] **H303** | 🔴 | ``var/directory_manager.py:77,87,94,184,106,212`, `var/spool_manager.py:63,86,93,123,130,151,163`, `var/log_manager.py:6…`
      - Issue: **Path-traversal → arbitrary FS delete/write/RCE (CWE-22)** - `name`/`username`/`directory`/`filename` are joined as `self.<x>_path / param` with no scoping or `realpath`-under-root check; `Path` collapses `..`, so `remove_local_item("../../etc/passwd")`→`unlink("/etc/passwd")`, `VarDirectoryManager.remove_local_item("../etc")`→`shutil.rmtree("/etc")`, and `SpoolManager.set_cron_user("../../etc/cron.d/x", jobs)`→writes `/etc/cron.d/x` (**cron RCE as root**); `LogManager.write_log("../../etc/cron.d/x", …)`→arbitrary append. Read/list variants expose arbitrary file content (`read_mailbox("../..…
      - Action: Validate + normalize every path param (reject `..`/absolute, resolve with `realpath` and assert it stays under the manager root); provide a shared `safe_join(root, name)` helper used by all three managers.
