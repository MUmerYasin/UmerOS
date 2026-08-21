# UmerOS — Long-term Project Memory

## Standing working conventions (Code Review Expert / Kim)
- **Review-standard-first workflow:** After *every* study (file/folder/design/dependency), update `MainTask/Raw Data/Code Review Standards and Process.md` — bump version, fold findings into §1/§4/§7/§9/§11. Standing user instruction; do not treat studies as read-only.
- **Authoritative sources (priority):** `Skills/Context File/umer_os_skills.json` > `MainTask/prompt/*.md` > `MainTask/Raw Data/*.docx` > repo + `LICENSE`/`setup.py` (repo wins when a source is aspirational, e.g. README "Project Structure").

## Decided inconsistencies
- **H7 → GPL-3.0 canonical.** Sweep Apache-2.0 strays in prompts/docs/code to GPLv3.
- **H11 → Flutter (Dart) canonical frontend.** Backend = Python only. Drop `kivy` from `requirements.txt`; `ui/*.py` (Tkinter/CLI) is retired legacy (H25). UI MUST follow HCI (Nielsen 10) — §4.8.

## Folder scope map (studied 1→kernel; full detail in the standard)
- `boot/` = `/boot` mgmt toolkit (FHS/GRUB/EFI/SB). 🔴 H27 verify_kernel trusts missing, H28 is_binary_trusted trusts DISABLED, H29 init auto-accepts waiver. +H30–H34.
- `bin/` = ~44 FHS user cmd modules (19k LOC). H6/H35 wrong exec sig (27/44); 🔴 H37 LoginCommand -f auth bypass. H36/H38/H39/H40. Subprocess injection-safe.
- `build/` = PyInstaller output; only `.spec` reviewable → 🔴 H42 unsigned (codesign=None); H41 ships Tkinter not Flutter. H43–H45.
- `cloud/` = OTA updater. 🔴 H46 verify_and_apply fail-open (no real verify). H47–H49.
- `compatibility/` = foreign-OS app layer. 🔴 H51 ZeroTrustContainer fail-open gate; H50/H52/H53/H54. Best tier-labels.
- `core/` = base `Command` class. H55 fix exec sig (ROOT of H6/H35); H56 privileges unenforced; H57.
- `dev/` = ~43 `/dev` node modules. 🟡 H60 os.mknod no cap gate; H59 0o666 default; H58/H61. Cleanest folder.
- `drivers/` = 75 driver modules (~35k LOC). 🔴 H64 driver_service static JWT "test-secret" + unauth /metrics; 🟡 H66 no cap gate MMIO/PCI/crypto. H62/H63/H69.
- `etc/` = 81 `/etc` cfg modules (24k LOC). 🔴 H73 sudoers no cap gate + NOPASSWD; 🟡 H72 pam permit non-blocking. H70/H71.
- `examples/` = 2 demo modules (62 LOC). 💭 H74/H75 (teaches open pattern).
- `feedback/` = BROKEN pkg (imports missing modules). 🟡 H76/H77/H78/H79.
- `fs/` = VFS over QFS CAS. 🟡 H80 no cap gate; H81 Apache stray; H82. First tier-label folder.
- `home/` = `/home` subsystem (10 files). 🔴 H83 tar extractall no filter; 🟡 H84 path-traversal username; H85/H86/H87/H88.
- `HostFiles/` = 3 text assets. 🟡 H90 HostBridge host write + auto-open (legacy H25); H89.
- `initrd/` = 17 early-boot modules (5k LOC, best baseline). 🔴 H91 eval(); H92 no cap gate boot ops; H93 cpio traversal; H94/H95/H96/H97.
- `installer/` = 3 files. 🔴 H98 double UmerInstaller; H99 waiver fail-open; H101 rollback rmtree; H100/H102–H109.
- `kernel/` = 40-file microkernel (~10k LOC). Two tiers: strong baseline cluster + off-baseline toy/REPL cluster. 🔴 H110 no-op placeholders → zero-trust/IPC/mem INERT (real modules commented out L1569-71); H111 dummy CryptoEngine.verify→True; H112 SecuritySandbox.register only prints. H113–H127 (sudo no auth, kill/shutdown ungated, cap lifecycle unwired, GUI Popen Tkinter, ipc try_receive skips HMAC, is_root bypass, cgroup implicit-allow, umer_kernel1 dep, Kivy drift, dead REPLs, import-time crypto, kivy req, udev RUN unimpl+0o666, panic taint ValueError).
- `legal/` = 12-file compliance/consent package (92K) — implements licensing/consent/safety the §4.2/§4.3 mandate. 🔴 H128 license framework codifies **Apache-2.0 as primary, no GPL-3.0** (H7 lives here — resolve it in this folder); H129 license audit fail-open (any "License"/"Copyright" = compliant); H130 `get_license_text("GPL-3.0")` returns Apache-2.0 text. 🔴 H131 consent gate fails OPEN (non-TTY auto-grant) + H135 `cli.py consent` hardcodes "I AGREE". 🟡 H132 forgeable "crypto" consent token; H136 decorative DCO; H138 hardcoded PQC/PGP fingerprints; H139 soft/fail-open `safety_check`. 🟡/🔴 H140 broken `test_legal.py` Test 4 (name not in roster → test fails); H141 tests encode fail-open consent CLI. 💭 H137 real PII/IBANs hardcoded.
- `lib/` = 33-source FHS `/lib` simulation (25 top-level + 8 `lostfound/`): shared-lib/ELF/dynamic-linker/kernel-module/fs-layout. **Best-disciplined folder in the study** (every module has full baseline; zero dangerous calls; `lostfound/fsck.py` fail-closed). 🔴 H3 `PASSWORD="password"` security.py:72 re-confirmed (latent). 🔴 H146 `ssl_libs.py:414-427` `_check_is_trusted` trusts on mere CA-bundle file presence + `check_trust` trusts any `is_ca` (trust fail-open, H17/H111 family). 🔴 H147 `ssl_libs.py:82-92` `is_expired`→False + `days_until_expiry`→365 (certs never expire). 💭 H148 `ssl_libs.py` "simplified" string-parse sim, no `cryptography` (needs `[EXPERIMENTAL]`). 🟡 H149 ~23 `lib/` files + README:138 Apache-2.0 — **largest Apache-2.0 cluster, H7**. 💭 H150 `security.py` registers `pam_permit.so` "Always permit" (low-risk fail-open trap).
- `liboqs/` = **upstream Open Quantum Safe C library, vendored UNPINNED** (no `.gitmodules` at repo root → can silently drift from upstream; MIT license, conflicts with H7 GPL-3.0 canonical → H151 🟡). 5,665 `.c`/`.h` files with **real, audited** FIPS-203/204/205 PQC (`ml_kem`=ML-KEM/Kyber, `ml_dsa`=ML-DSA/Dilithium, `slh_dsa`=SPHINCS+) — supplies the §4.2 zero-trust PQC mandate **only if UmerOS binds to it**. Python surface = 28 upstream `scripts/`+`tests/` `.py` (injection-safe: `subprocess.run` list-args, no `shell=True`/`eval`/`exec`/`pickle`/`ctypes`; `return True` hits benign = CBOM "needs-update" flag + feature-detection helpers). **Live PQC is NOT wired to the vendored C** — UmerOS uses `quantum/crypto_pqc.py` (`import oqs`→`liboqs-python`; `[TODAY]`-tier, **Apache-2.0 stray H7**, and **silent classical-crypto fallback** when liboqs-python missing → H152 🔴) + `kernel/pqcrypto_.py` (commented `pqcrypto` *example*, divergent pure-Python backend → H153 🟡). 🔴 H154 `cloud/ota_updater/update_system.py:33` hardcodes `simulated_dilithium_sig_abc123` in a "verify signature" step (reinforces H46/H111 dummy-crypto). 💭 H155 vendored `liboqs/` is dead/unwired (integration gap).
- `media/` = **12 FHS `/media` removable-media modules** — FHS mount subsystem. 🔴 **H156** no `CapabilityManager` gate on `mount_ops.mount`/`auto_mount._handle_hotplug`/`udisks2.UDisks2Client.mount` (zero-trust gap, H27/H110 family); 🔴 **H157** `auto_mount._do_mount` mounts removable media `rw` without `noexec,nodev,nosuid` (bypasses `MountManager.allocate` + `filesystem.mount_options_for`, setuid-on-USB → priv-esc). 🟡 H158 `permissions.py` authz unwired + `" optical"` literal bug; 🟡 H159 `fstab.add()` skips `validate()`; 🟡 H160 5 Apache-2.0 strays + 7 missing headers (H7). 💭 H161 3 broken + 1 non-conformant `_selftest()`; H162 `cleanup.py __import__("re")`; H163 `filesystem.FsType.NVME` nonexistent + `EXT4` dup; H164 `mount_ops._real_unmount` dead code; H165 `auto_mount.user_mode` decorative + no-consent auto-mount. Generally well-disciplined baseline + injection-safe subprocess + safe cleanup scoping.
- `mnt/` = **7 FHS `/mnt` admin-mount modules** — privileged counterpart to `media/`. 🔴 **H166** no `CapabilityManager` gate on `MountManager.mount`/`umount`/`remount`/`MountPointManager.create`/`remove`/`Fstab.write_file`; 🔴 **H167** `MountPointManager.remove(force=True)` `shutil.rmtree` on non-symlink-checked path (TOCTOU arbitrary delete); 🔴 **H168** `Fstab.write_file` un-gated `/etc/fstab` write + drops comments/header. 🟡 H169 user mounts add `nosuid,nodev` not `noexec`; H170 `MntValidator` advisory-only; H171 `_save_mtab` rewrites whole `/etc/mtab` from partial list. 💭 H172 `_enforce_user` dead; H173 `int()` on fstab `dump`/`pass` uncaught; H174 `to_string` drops comments; H175 shell-string logging. 🟡 H176 6 Apache-2.0 strays ("Licence: Apache 2.0", British spelling) + missing `__init__` header (H7). **More disciplined than media/**: all 7 `_selftest()`s functional + `audit.py` safe JSONL key-filtered deserialize.
- `network/` = **6 FHS-style networking modules (~37 KB)** — well-disciplined baseline + injection-safe `subprocess` (argv-list, no `shell=True`) + TLS verified by default + `tcp_server.py` is a **model for abuse controls** (conn caps, per-IP rate limit, read timeout, max msg size). **But the whole egress surface is zero-trust-gapped and one "encryption" is a footgun**: 🔴 **H177** no `CapabilityManager` gate on ANY egress (DNS/HTTP/TCP/VPN — H27/H110/H156/H166 family); 🔴 **H178** `HTTPClient._validate_url` (http_client.py:227) doesn't block loopback/link-local/private → SSRF (`http://169.254.169.254` cloud metadata passes). 🟡 H179 `VPNTunnel._xor_frame` is reversible XOR, not encryption (honestly "simulation" but a footgun); 🟡 H180 `DNSResolver` uses plaintext host resolver, DoH never enforced (spoofable). 💭 H181 no license headers + `__init__` missing `from __future__` (H7); H182 no `_selftest()` in any module.
- `opt/` = **14 FHS `/opt` add-on-software modules** — better baseline than media/mnt/network (env/fhs/hierarchy/var have `from __future__` + `logging` + functional `_selftest()`; `fhs.OptFHSValidator` is a model auditor). **But the privileged install/remove/write surface is zero-trust-gapped with concrete bugs**: 🔴 **H184** no `CapabilityManager` gate on any privileged op (installs `$PATH` entries — high blast radius); 🔴 **H185** unvalidated `filename`/`config_file` → arbitrary file read/write outside `/var/opt` & `/etc/opt`; 🔴 **H186** unvalidated `name`/`provider` in `shutil.rmtree` → arbitrary dir deletion (`name="../../etc"`); 🔴 **H187** unescaped `command`/`args` in generated launcher/wrapper scripts → code execution. 🟡 H188 discovered `bin_path` injected into `/etc/profile.d` + `~/.bashrc`; 🟡 H189 `OptPackage` hardcodes real `/etc/opt`/`/var/opt` (ignores `opt_root`); 🟡 H193 service manager executes any discovered script. 💭 H190 `verify_integrity` mislabeled (no hashing); H191 missing `from __future__` in 10 modules; H192 no `_selftest()` in 10 modules (`test_opt.py` ignores them + no security tests).
- `packages/` = **3 modules (635 LOC)** — user-space package manager (`umer_pkg.py` `UmerPackageManager`/`PackageManifest`/`DependencyResolver`, `repository.py` `PackageRepository`/`PackageInfo`, `__init__`). **Best baseline of the small folders** (`umer_pkg.py` full baseline + correct topological `DependencyResolver` w/ cycle detection + atomic snapshot+rollback; `_verify_hash` fails CLOSED on mismatch; real `hashlib.sha3_256`). `repository.py` clean in-memory catalog. **But the install/extract surface has concrete high-severity bugs**: 🔴 **H194** tar-slip — `tarfile.extractall` without `filter=` + naive `files/` prefix → `../`/abs/symlink traversal (arbitrary write, CVE-2007-4559 family, cf. H83/H93); 🔴 **H195** untrusted manifest `name`/`version` → attacker-controlled `dest`/filename path traversal; 🔴 **H196** "Signed" overstated — only SHA3 self-hash, NO signature + `_verify_hash` fails OPEN when HASH absent; 🔴 **H197** integrity check hashes only `manifest.json`, never the `files/` payload (tamper-undetectable); 🔴 **H198** no `CapabilityManager` gate on `install`/`remove`/`update` (docstring claims admin grant — absent; user-space scope, lower blast radius than `opt/`). 🟡 H199 lexicographic version compare in `update` → upgrades silently skipped; 🟡 H200 H7 `Licence: Apache 2.0` in `umer_pkg.py` + 2 files no header; 🟡 H201 `_find_in_registry` fuzzy `startswith(name)` match; 🟡 H204 symlink/hardlink extraction + no permission `filter`. 💭 H202 missing `from __future__` in 2 modules; H203 no `_selftest()` + `print` in `repository.py`.

## Known 🔴 security hotspots (fail-open / cap-gate / dummy-crypto family)
- H1 live OpenRouter key `settings.local.json`.
- H2→H91 `eval()` initrd history.
- H3 `PASSWORD="password"` lib/security.py.
- H17 SecureBoot.verify_image fail-open.
- H27 boot verify_kernel trusts missing.
- H28 efi is_binary_trusted trusts DISABLED.
- H29 boot init auto-accepts waiver.
- H37 bin LoginCommand -f auth bypass.
- H46 cloud OTA verify_and_apply fail-open.
- H51 compatibility ZeroTrustContainer fail-open gate.
- H60 dev os.mknod no cap gate.
- H64 drivers static JWT + unauth /metrics.
- H66 drivers no cap gate MMIO/PCI/crypto.
- H73 etc sudoers no cap gate + NOPASSWD.
- H83 home tar extractall no filter.
- H91 initrd eval().
- H92 initrd no cap gate on boot ops.
- H93 initrd cpio traversal.
- H98 installer double UmerInstaller.
- H99 installer waiver fail-open.
- H101 installer rollback rmtree.
- **H110 kernel no-op placeholders → zero-trust/IPC/mem account INERT.**
- **H111 kernel dummy CryptoEngine.verify → True.**
- **H112 kernel SecuritySandbox.register only prints.**
- **H128 legal license framework Apache-2.0 primary, no GPL-3.0 (H7 lives here).**
- **H129 legal license audit fail-open (any "License"/"Copyright" = compliant).**
- **H130 legal `get_license_text("GPL-3.0")` returns Apache-2.0 text.**
- **H131 legal consent gate fails OPEN (non-TTY auto-grant).**
- **H135 legal `cli.py consent` hardcodes "I AGREE" (auto-grants).**
- **H146 lib `ssl_libs.py:414-427` `_check_is_trusted` returns True on mere CA-bundle file presence + `check_trust` trusts any `is_ca` (trust/verify fail-open, H17/H111/H129 family).**
- **H147 lib `ssl_libs.py:82-92` `is_expired` always False + `days_until_expiry` hardcoded 365 (certificates never expire; expiry fail-open).**
- **H152 quantum/crypto_pqc.py:36-46 silent classical-crypto fallback when liboqs-python missing (fail-open under §4.2 PQC mandate; also Apache-2.0 stray, H7).**
- **H154 cloud/ota_updater/update_system.py:33 hardcoded `simulated_dilithium_sig_abc123` (fake PQC sig; reinforces H46/H111).**
- **H156 media/ mount/auto-mount/udisks2 paths have NO `CapabilityManager` gate (privileged op, zero-trust gap; H27/H110 family).**
- **H157 media/auto_mount._do_mount mounts removable media `rw` without `noexec,nodev,nosuid` (bypasses `MountManager.allocate` + `filesystem.mount_options_for`, setuid-on-USB → privilege escalation).**
- **H166 mnt/ mount/remove/fstab-write paths have NO `CapabilityManager` gate (privileged op, zero-trust gap; H27/H110/H156 family).**
- **H167 mnt/`MountPointManager.remove(force=True)` `shutil.rmtree` on a non-symlink-checked path (TOCTOU → arbitrary directory deletion; the one genuinely new hotspot in `mnt/`).**
- **H168 mnt/`Fstab.write_file` writes `/etc/fstab` un-gated (privileged path write) and silently drops comments/header (round-trip data loss).**
- **H177 network/ NO `CapabilityManager` gate on ANY egress (DNS resolve, HTTP request, TCP connect, VPN connect — all privileged network ops run ungated; H27/H110/H156/H166 family).**
- **H178 network/`HTTPClient._validate_url` (http_client.py:227) omits loopback/link-local/private blocking → SSRF (`http://169.254.169.254` cloud metadata, `http://127.0.0.1`, `http://[::1]` all pass); `NetworkStack.connect`/`send_tcp` lack host-range guard too.**
- **H184 opt/ NO `CapabilityManager` gate on ANY privileged /opt op (install/remove/update/bootstrap/write_profile_d/registry/rmtree) — installs code that becomes a `$PATH` entry (high blast radius; H27/H110/H156/H166/H177 family).**
- **H185 opt/ `var.write_file`/`read_file` + `config.install_config`/`get_config` unvalidated `filename`/`config_file`/`package_name` → arbitrary file read/write outside `/var/opt` & `/etc/opt` (path traversal).**
- **H186 opt/ `shutil.rmtree` on unvalidated `name`/`provider` across `manager.remove`/`package.OptManager.remove_package`/`OptPackage.remove`/`config.remove_*`/`var.remove_package_dir` → arbitrary directory deletion (path traversal; `name="../../etc"`).**
- **H187 opt/ `OptPackage.create_launcher_script`/`create_wrapper_script` interpolate `command`/`args`/`environment` unescaped into `#!/bin/bash` → code execution when the script runs (script lands in `/opt/<pkg>/bin` which `env` adds to `$PATH`).**
- **H194 packages/ `tarfile.extractall` (umer_pkg.py:357,363) without `filter=` + naive `files/` string-prefix → `../`/absolute/symlink tar-slip, arbitrary file write anywhere (CVE-2007-4559 family, cf. H83/H93).**
- **H195 packages/ untrusted manifest `name`/`version` (umer_pkg.py:347,510) → attacker-controlled `dest`/filename path traversal outside `~/.umer/packages`.**
- **H196 packages/ `_verify_hash` (umer_pkg.py:250,268) "Signed" overstated — SHA3 self-hash only, no signature; fails OPEN when HASH absent (H51/H111/H146/H154 family).**
- **H197 packages/ `_verify_hash` (umer_pkg.py:250,277) hashes only `manifest.json`, never the `files/` payload → tampered payload undetectable (contract-violating).**
- **H198 packages/ NO `CapabilityManager` gate on `install`/`remove`/`update` (umer_pkg.py) — docstring claims admin grant absent; user-space scope, H27/H110/H156/H166/H177/H184 family.**

## Project layout notes
- ~735 active Python modules; `tests/` unittest/pytest split, NO CI test step; `security_scan.yml` only workflow.
- `Old Linux Code/` (~93k files) reference-only, excluded from review.
- **Cross-cutting remediation pass (offered 14×, NOT yet requested):** fix the fail-open / cap-gating / dummy-crypto family — H17/H27/H28/H29/H46/H51/H60/H64/H66/H73/H83/H91/H92/H93/H98/H99/H101/H110/H111/H112/H113/H115/H117/**H128/H129/H130/H131/H135**/**H146/H147**/**H152/H154**/**H156/H157**/**H166/H167/H168**/**H177/H178**/**H184/H185/H186/H187**/**H194/H195/H196/H197/H198**. `lib/` adds 2 new 🔴 (SSL trust + expiry); `liboqs/` adds 2 new 🔴 (silent PQC fallback + OTA fake sig); `media/` adds 2 new 🔴 (no cap gate on mount/auto-mount + removable media mounted rw without `noexec,nosuid,nodev`); `mnt/` adds 3 new 🔴 (no cap gate on mount/remove/fstab-write + rmtree symlink TOCTOU + fstab write un-gated/drops comments); `network/` adds 2 new 🔴 (no cap gate on any egress + SSRF egress with no internal-range block); `opt/` adds 4 new 🔴 (no cap gate on privileged ops + path-traversal file read/write + rmtree path-traversal deletion + command injection in generated launcher/wrapper scripts); `packages/` adds 5 new 🔴 (tar-slip on `extractall` + untrusted manifest `name`/`version` path traversal + fail-open "Signed" verification + `files/` payload never integrity-checked + no cap gate on install/remove/update). Awaits user go-ahead.
